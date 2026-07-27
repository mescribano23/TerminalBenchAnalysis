#!/usr/bin/env python3
"""Build a benchmark-versioned trajectory table for 2.0 vs 2.1 analyses.

Inputs are the per-benchmark outputs from:

    python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_0
    python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_1

Outputs are written under data/processed_live/longitudinal by default.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.benchmark_paths import find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
DATA_DIR = REPO_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed_live"
TASK_MINING_DIR = PROCESSED_DIR / "task_mining"
OUT_DEFAULT = PROCESSED_DIR / "longitudinal"

BENCHMARKS = ("terminal_bench_2_0", "terminal_bench_2_1")
REQUIRED_TRAJECTORY_COLUMNS = {
    "benchmark",
    "rel_path",
    "scaffold",
    "model_dir",
    "agent_version",
    "model_name",
    "task_name",
    "file_task_id",
    "reward",
    "reward_outcome",
    "step_count",
    "agent_step_count",
    "tool_call_count",
    "command_count",
    "message_chars",
    "reasoning_chars",
    "observation_chars",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
    "duration_seconds",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument(
        "--task-metadata",
        type=Path,
        default=TASK_MINING_DIR / "terminal_bench_2_task_toml_metadata.csv",
        help="Task-level metadata with difficulty, category, tags, and time estimates.",
    )
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    return parser.parse_args()


def validate_columns(df: pd.DataFrame, required: set[str], path: Path) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")


def read_trajectory_table(processed_dir: Path, benchmark: str) -> pd.DataFrame:
    path = processed_dir / benchmark / "trajectory_summary.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Regenerate it with "
            f"`python -m scripts.analysis.00_characterize_trajectories --benchmark {benchmark}`."
        )
    df = pd.read_csv(path, low_memory=False)
    validate_columns(df, REQUIRED_TRAJECTORY_COLUMNS, path)
    df = df.copy()
    df["benchmark"] = benchmark
    df["benchmark_version"] = benchmark.replace("terminal_bench_", "").replace("_", ".")
    return df


def read_task_metadata(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing task metadata: {path}")
    tasks = pd.read_csv(path)
    validate_columns(tasks, {"task_name", "difficulty", "category"}, path)

    keep = [
        "task_name",
        "task_slug",
        "terminal_bench_task_name",
        "difficulty",
        "category",
        "tags",
        "keywords",
        "expert_time_estimate_min",
        "junior_time_estimate_min",
        "agent_timeout_sec",
        "verifier_timeout_sec",
        "environment_build_timeout_sec",
        "allow_internet",
        "cpus",
        "memory_mb",
        "storage_mb",
        "gpus",
        "description",
    ]
    keep = [column for column in keep if column in tasks.columns]
    tasks = tasks[keep].drop_duplicates("task_name").copy()
    return tasks


def numeric_clean(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def build_audit(df: pd.DataFrame, tasks: pd.DataFrame, missing_meta: pd.DataFrame) -> dict[str, Any]:
    by_version: dict[str, Any] = {}
    for benchmark, group in df.groupby("benchmark"):
        binary = group["passed"].notna()
        by_version[benchmark] = {
            "trajectory_count": int(group.shape[0]),
            "task_count": int(group["task_name"].nunique()),
            "scaffold_count": int(group["scaffold"].nunique()),
            "model_dir_count": int(group["model_dir"].nunique()),
            "binary_outcome_count": int(binary.sum()),
            "pass_rate": float(group.loc[binary, "passed"].mean()) if binary.any() else None,
        }
    task_sets = {
        benchmark: set(group["task_name"].dropna().astype(str))
        for benchmark, group in df.groupby("benchmark")
    }
    overlap = sorted(set.intersection(*task_sets.values())) if task_sets else []
    return {
        "inputs": {
            "benchmarks": list(BENCHMARKS),
            "task_metadata_rows": int(tasks.shape[0]),
        },
        "by_version": by_version,
        "task_overlap": {
            "common_task_count": len(overlap),
            "only_terminal_bench_2_0": sorted(task_sets.get("terminal_bench_2_0", set()) - set(overlap)),
            "only_terminal_bench_2_1": sorted(task_sets.get("terminal_bench_2_1", set()) - set(overlap)),
        },
        "metadata_join": {
            "missing_metadata_rows": int(missing_meta.shape[0]),
            "missing_metadata_task_count": int(missing_meta["task_name"].nunique()) if not missing_meta.empty else 0,
            "missing_metadata_examples": sorted(missing_meta["task_name"].dropna().astype(str).unique())[:20],
        },
    }


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    trajectories = pd.concat(
        [read_trajectory_table(args.processed_dir, benchmark) for benchmark in BENCHMARKS],
        ignore_index=True,
    )
    tasks = read_task_metadata(args.task_metadata)

    numeric_columns = [
        "reward",
        "step_count",
        "agent_step_count",
        "tool_call_count",
        "command_count",
        "message_chars",
        "reasoning_chars",
        "observation_chars",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cost_usd",
        "duration_seconds",
        "expert_time_estimate_min",
        "junior_time_estimate_min",
        "agent_timeout_sec",
        "verifier_timeout_sec",
        "environment_build_timeout_sec",
        "cpus",
        "memory_mb",
        "storage_mb",
        "gpus",
    ]
    trajectories = numeric_clean(trajectories, numeric_columns)
    trajectories["passed"] = trajectories["reward"].where(trajectories["reward"].isin([0.0, 1.0]))
    trajectories["passed"] = trajectories["passed"].astype("float")
    trajectories["agent_key"] = trajectories["scaffold"].fillna("unknown") + "::" + trajectories["model_dir"].fillna("unknown")

    df = trajectories.merge(tasks, on="task_name", how="left", validate="many_to_one")
    missing_meta = df[df["category"].isna() | df["difficulty"].isna()].copy()

    coverage = (
        df.groupby(["task_name", "benchmark"], as_index=False)
        .agg(
            trajectory_count=("rel_path", "size"),
            pass_rate=("passed", "mean"),
            median_step_count=("step_count", "median"),
            median_command_count=("command_count", "median"),
            median_duration_seconds=("duration_seconds", "median"),
        )
        .merge(tasks, on="task_name", how="left")
        .sort_values(["task_name", "benchmark"])
    )

    task_presence = (
        coverage.pivot_table(index="task_name", columns="benchmark", values="trajectory_count", fill_value=0)
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for benchmark in BENCHMARKS:
        if benchmark not in task_presence.columns:
            task_presence[benchmark] = 0
    task_presence["in_both_versions"] = (task_presence[BENCHMARKS[0]] > 0) & (task_presence[BENCHMARKS[1]] > 0)
    task_presence = task_presence.merge(tasks, on="task_name", how="left")

    df.to_csv(args.out / "trajectory_longitudinal.csv", index=False)
    coverage.to_csv(args.out / "task_version_coverage.csv", index=False)
    task_presence.to_csv(args.out / "task_overlap.csv", index=False)
    with (args.out / "longitudinal_data_audit.json").open("w", encoding="utf-8") as f:
        json.dump(build_audit(df, tasks, missing_meta), f, indent=2)

    print(f"Wrote longitudinal trajectories to {args.out / 'trajectory_longitudinal.csv'}")
    print(f"Wrote task coverage to {args.out / 'task_version_coverage.csv'}")
    print(f"Wrote audit to {args.out / 'longitudinal_data_audit.json'}")


if __name__ == "__main__":
    main()
