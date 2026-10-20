#!/usr/bin/env python3
"""Build a unified trajectory table for Terminal-Bench 2.x longitudinal analyses.

Terminal-Bench 2.0 and 2.1 contain the same tasks, so the default output
combines both benchmark versions and attaches task metadata plus submission
metadata needed for descriptive comparisons. Benchmark version is retained as a
primary comparison column.

Inputs are the per-benchmark outputs from:

    python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_0
    python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_1

The final trajectory table and compact audit are written under
data/processed_live/longitudinal by default.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.benchmark_paths import find_repo_root
from scripts.analysis.source_submission_identity import source_id, ensure_source_submission_id, SourceResolver


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INDEXES_DIR = DATA_DIR / "indexes"
TRAJECTORIES_DIR = DATA_DIR / "trajectories"
PROCESSED_DIR = DATA_DIR / "processed_live"
TASK_MINING_DIR = PROCESSED_DIR / "task_mining"
OUT_DEFAULT = PROCESSED_DIR / "longitudinal"

BENCHMARKS = ("terminal_bench_2_0", "terminal_bench_2_1")
SUBMISSION_FILES = ("leaderboard_submissions_historical.json", "leaderboard_submissions.json")
REQUIRED_TRAJECTORY_COLUMNS = {
    "benchmark",
    "rel_path",
    "scaffold",
    "model_dir",
    "agent_version",
    "model_name",
    "task_name",
    "file_task_id",
    "file_run_id",
    "reward",
    "reward_outcome",
    "step_count",
    "agent_step_count",
    "tool_call_count",
    "shell_invocation_count",
    "message_chars",
    "reasoning_chars",
    "observation_chars",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
    "duration_seconds",
}
EFFORT_COLUMNS = [
    "step_count",
    "agent_step_count",
    "tool_call_count",
    "shell_invocation_count",
    "message_chars",
    "reasoning_chars",
    "observation_chars",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
    "duration_seconds",
]


characterize = importlib.import_module("scripts.analysis.00_characterize_trajectories")
load_trajectory_index = characterize.load_trajectory_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--indexes-dir", type=Path, default=INDEXES_DIR)
    parser.add_argument("--trajectories-dir", type=Path, default=TRAJECTORIES_DIR)
    parser.add_argument(
        "--benchmarks",
        nargs="+",
        default=list(BENCHMARKS),
        help="Benchmark directories to combine. Defaults to Terminal-Bench 2.0 and 2.1.",
    )
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


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_key_part(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("\\", "_").replace("/", "_")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("._")


def submission_key(scaffold: Any, scaffold_version: Any, model: Any) -> tuple[str, str, str]:
    return (
        normalize_key_part(scaffold),
        normalize_key_part(scaffold_version),
        normalize_key_part(model),
    )


def submission_key_without_version(scaffold: Any, model: Any) -> tuple[str, str]:
    return (normalize_key_part(scaffold), normalize_key_part(model))


def benchmark_version_label(benchmark: str) -> str:
    return benchmark.replace("terminal_bench_", "").replace("_", ".")


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
    df["benchmark_version"] = benchmark_version_label(benchmark)
    df["rel_path_norm"] = df["rel_path"].astype(str).str.replace("\\", "/", regex=False)
    return df


def read_index_table(indexes_dir: Path, trajectories_dir: Path, benchmark: str) -> pd.DataFrame:
    index_path = indexes_dir / benchmark / "trajectory_trials.json"
    root = trajectories_dir / benchmark
    by_rel = load_trajectory_index(index_path, root)
    rows: list[dict[str, Any]] = []
    for rel_path, entry in by_rel.items():
        rows.append(
            {
                "benchmark": benchmark,
                "rel_path_norm": rel_path,
                "index_scaffold": entry.get("scaffold", ""),
                "index_model": entry.get("model", ""),
                "index_task_name": entry.get("taskName", ""),
                "index_task_checksum": entry.get("taskChecksum", ""),
                "index_trial_id": entry.get("trialId", ""),
                "index_reward": entry.get("reward", ""),
                "index_cost_raw": entry.get("cost", ""),
                "index_duration_seconds": entry.get("duration", ""),
                "index_file_path": entry.get("filePath", ""),
            }
        )
    return pd.DataFrame(rows)


def submission_id(benchmark: str, row: dict[str, Any]) -> str:
    return source_id(benchmark, row["submission_url"])


def read_submission_table(raw_dir: Path, benchmark: str) -> pd.DataFrame:
    rows: dict[str, dict[str, Any]] = {}
    for filename in SUBMISSION_FILES:
        path = raw_dir / benchmark / filename
        if not path.exists():
            continue
        data = load_json(path)
        if not isinstance(data, list):
            continue
        for entry in data:
            if not isinstance(entry, dict):
                continue
            sid = submission_id(benchmark, entry)
            tasks = [task for task in entry.get("tasks", []) if isinstance(task, dict)]
            official_trial_count = sum(int(task.get("nTrials", 0) or 0) for task in tasks)
            official_success_count = sum(int(task.get("successCount", 0) or 0) for task in tasks)
            rows[sid] = {
                "benchmark": benchmark,
                "submission_id": sid,
                "submission_url": entry.get("submission_url", ""),
                "submission_scaffold": entry.get("scaffold", ""),
                "submission_scaffold_version": entry.get("scaffold_version", ""),
                "submission_model": entry.get("model", ""),
                "submission_provider": entry.get("provider", ""),
                "submission_has_trajectories": entry.get("has_trajectories", ""),
                "submission_timestamp": entry.get("leaderboard_date", ""),
                "leaderboard_accuracy_submission": entry.get("leaderboard_accuracy", ""),
                "leaderboard_stderr_submission": entry.get("leaderboard_stderr", ""),
                "leaderboard_agent_display_name": entry.get("leaderboard_agent_display_name", ""),
                "leaderboard_model_display": entry.get("leaderboard_model_display", ""),
                "leaderboard_agent_organization": entry.get("leaderboard_agent_organization", ""),
                "leaderboard_model_organization_submission": entry.get("leaderboard_model_organization", ""),
                "submission_source_file": filename,
                "submission_official_task_count": len(tasks),
                "submission_official_trial_count": official_trial_count,
                "submission_official_success_count": official_success_count,
                "submission_official_pass_rate": (
                    official_success_count / official_trial_count if official_trial_count else np.nan
                ),
            }
    submissions = pd.DataFrame(rows.values())
    if submissions.empty:
        return submissions
    submissions["submission_timestamp"] = pd.to_datetime(
        submissions["submission_timestamp"], errors="coerce", utc=True
    )
    submissions["submission_date"] = submissions["submission_timestamp"].dt.date.astype("string")
    submissions["submission_key_full"] = [
        submission_key(row.submission_scaffold, row.submission_scaffold_version, row.submission_model)
        for row in submissions.itertuples(index=False)
    ]
    submissions["submission_key_no_version"] = [
        submission_key_without_version(row.submission_scaffold, row.submission_model)
        for row in submissions.itertuples(index=False)
    ]
    return submissions


def candidate_map(submissions: pd.DataFrame, key_column: str) -> dict[Any, pd.DataFrame]:
    if submissions.empty:
        return {}
    return {
        key: group.reset_index(drop=True)
        for key, group in submissions.groupby(key_column, dropna=False)
    }


def same_timestamp(candidates: pd.DataFrame) -> bool:
    timestamps = candidates["submission_timestamp"].dropna().unique()
    return len(timestamps) == 1


def attach_submission_metadata(trajectories: pd.DataFrame, submissions: pd.DataFrame) -> pd.DataFrame:
    """Join only independently resolved source IDs; no URL/configuration fallback."""
    trajectories = ensure_source_submission_id(trajectories)
    lookup = submissions.set_index("submission_id")
    if not lookup.index.is_unique:
        raise ValueError("Duplicate authoritative source IDs")
    ids = trajectories["source_submission_id"]
    if not ids.isin(lookup.index).all():
        raise ValueError("Resolved source submission missing from the retained snapshot")
    matched = lookup.loc[ids].reset_index()
    if not matched.submission_url.reset_index(drop=True).eq(trajectories.source_submission_url.reset_index(drop=True)).all():
        raise ValueError("Source ID / URL conflict; reconcile acquisition membership first")
    matched["submission_match_status"] = trajectories.source_identity_status.to_numpy()
    matched["submission_match_method"] = trajectories.source_identity_method.to_numpy()
    matched["submission_candidate_count"] = 1
    matched["submission_candidate_ids"] = ids.to_numpy()
    matched["submission_timestamp"] = pd.to_datetime(matched["submission_timestamp"], errors="raise", utc=True)
    matched["historical_leaderboard_timestamp"] = matched.submission_timestamp
    timestamp_naive = matched["submission_timestamp"].dt.tz_convert(None)
    matched["submission_period"] = timestamp_naive.dt.to_period("M").astype("string")
    matched["submission_period_start"] = timestamp_naive.dt.to_period("M").dt.start_time
    # submission_timestamp is a compatibility alias, not a verified publication time.
    overlap = set(matched.columns) & set(trajectories.columns)
    return pd.concat([trajectories.drop(columns=list(overlap)).reset_index(drop=True), matched], axis=1)


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
        "subcategory",
        "tags",
        "keywords",
        "instruction_sha256",
        "instruction_normalized_sha256",
        "task_toml_sha256",
        "readme_sha256",
        "package_manifest_sha256",
        "instruction_chars",
        "instruction_normalized_chars",
        "package_file_count",
        "package_total_listed_bytes",
        "hf_revision",
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
        "difficulty_explanation",
        "solution_explanation",
        "verification_explanation",
        "relevant_experience",
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


def duplicate_summary(df: pd.DataFrame) -> dict[str, Any]:
    within = df.duplicated(["benchmark", "rel_path"], keep=False)
    cross_key_columns = ["scaffold", "model_dir", "task_name", "file_run_id"]
    cross = (
        df.dropna(subset=["file_run_id"])
        .groupby(cross_key_columns, dropna=False)["benchmark"]
        .nunique()
        .reset_index(name="benchmark_count")
    )
    cross = cross[cross["benchmark_count"] > 1]
    return {
        "within_benchmark_duplicate_rows": int(within.sum()),
        "cross_version_duplicate_candidate_count": int(cross.shape[0]),
        "cross_version_duplicate_candidate_examples": cross.head(20).to_dict(orient="records"),
    }


def effort_coverage(df: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for column in EFFORT_COLUMNS:
        values = pd.to_numeric(df[column], errors="coerce") if column in df.columns else pd.Series(dtype=float)
        out[column] = {
            "non_missing": int(values.notna().sum()),
            "missing": int(values.isna().sum()),
            "positive": int((values > 0).sum()),
        }
    return out


def build_audit(
    df: pd.DataFrame,
    tasks: pd.DataFrame,
    missing_meta: pd.DataFrame,
    benchmarks: tuple[str, ...],
) -> dict[str, Any]:
    by_version: dict[str, Any] = {}
    for benchmark, group in df.groupby("benchmark"):
        binary = group["passed"].notna()
        by_version[benchmark] = {
            "trajectory_count": int(group.shape[0]),
            "submission_count": int(group["source_submission_id"].replace("", np.nan).nunique()),
            "task_count": int(group["task_name"].nunique()),
            "scaffold_count": int(group["scaffold"].nunique()),
            "model_dir_count": int(group["model_dir"].nunique()),
            "binary_outcome_count": int(binary.sum()),
            "pass_rate": float(group.loc[binary, "passed"].mean()) if binary.any() else None,
            "missing_submission_timestamp_rows": int(group["submission_timestamp"].isna().sum()),
        }
    task_sets = {
        benchmark: set(group["task_name"].dropna().astype(str))
        for benchmark, group in df.groupby("benchmark")
    }
    overlap = sorted(set.intersection(*task_sets.values())) if task_sets else []
    match_counts = df["submission_match_status"].value_counts(dropna=False).to_dict()
    ambiguous = df[df["submission_match_status"].astype(str).str.startswith("ambiguous")].copy()
    unmatched = df[df["submission_match_status"].eq("unmatched")].copy()
    index_missing = df[df["index_trial_id"].isna() | df["index_trial_id"].eq("")].copy()
    return {
        "inputs": {
            "benchmarks": list(benchmarks),
            "task_metadata_rows": int(tasks.shape[0]),
        },
        "by_version": by_version,
        "task_overlap": {
            "common_task_count": len(overlap),
            "only_by_benchmark": {
                benchmark: sorted(task_sets.get(benchmark, set()) - set(overlap))
                for benchmark in benchmarks
            },
        },
        "metadata_join": {
            "missing_metadata_rows": int(missing_meta.shape[0]),
            "missing_metadata_task_count": int(missing_meta["task_name"].nunique())
            if not missing_meta.empty
            else 0,
            "missing_metadata_examples": sorted(
                missing_meta["task_name"].dropna().astype(str).unique()
            )[:20],
        },
        "trajectory_index_join": {
            "missing_index_rows": int(index_missing.shape[0]),
            "missing_index_examples": index_missing[
                ["benchmark", "rel_path", "scaffold", "model_dir", "task_name", "file_run_id"]
            ]
            .head(20)
            .to_dict(orient="records"),
        },
        "submission_linkage": {
            "match_status_counts": {str(k): int(v) for k, v in match_counts.items()},
            "missing_submission_timestamp_rows": int(df["submission_timestamp"].isna().sum()),
            "ambiguous_match_examples": ambiguous[
                [
                    "benchmark",
                    "scaffold",
                    "agent_version",
                    "model_dir",
                    "submission_candidate_count",
                    "submission_candidate_ids",
                    "submission_timestamp",
                ]
            ]
            .drop_duplicates()
            .head(20)
            .assign(submission_timestamp=lambda x: x["submission_timestamp"].astype(str))
            .to_dict(orient="records"),
            "unmatched_examples": unmatched[
                ["benchmark", "rel_path", "scaffold", "agent_version", "model_dir", "task_name"]
            ]
            .head(20)
            .to_dict(orient="records"),
        },
        "duplicates": duplicate_summary(df),
        "effort_variable_coverage": effort_coverage(df),
    }


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    benchmarks = tuple(args.benchmarks)
    if not benchmarks:
        raise ValueError("At least one benchmark is required.")

    frames: list[pd.DataFrame] = []
    for benchmark in benchmarks:
        trajectories = read_trajectory_table(args.processed_dir, benchmark)
        index = read_index_table(args.indexes_dir, args.trajectories_dir, benchmark)
        if not index.empty:
            trajectories = trajectories.merge(
                index,
                on=["benchmark", "rel_path_norm"],
                how="left",
                validate="one_to_one",
            )
        else:
            trajectories["index_trial_id"] = ""
        resolver = SourceResolver(benchmark, args.raw_dir / benchmark / "leaderboard_submissions.json", args.raw_dir / benchmark / "leaderboard_trials.json")
        evidence = {x["trialId"]: x for x in load_json(args.indexes_dir / benchmark / "trajectory_trials.json")}
        resolved = pd.DataFrame([resolver.resolve(row, evidence.get(row["file_run_id"], {}))[0]
                                 for row in trajectories.to_dict(orient="records")])
        if "source_submission_id" in trajectories and not trajectories.source_submission_id.reset_index(drop=True).eq(resolved.source_submission_id).all():
            raise ValueError("Cached source IDs conflict with independently resolved acquisition membership")
        trajectories = pd.concat([trajectories.drop(columns=list(set(trajectories.columns) & set(resolved.columns))).reset_index(drop=True), resolved], axis=1)
        submissions = read_submission_table(args.raw_dir, benchmark)
        trajectories = attach_submission_metadata(trajectories, submissions)
        frames.append(trajectories)

    trajectories = pd.concat(frames, ignore_index=True)
    tasks = read_task_metadata(args.task_metadata)

    numeric_columns = [
        "reward",
        *EFFORT_COLUMNS,
        "expert_time_estimate_min",
        "junior_time_estimate_min",
        "agent_timeout_sec",
        "verifier_timeout_sec",
        "environment_build_timeout_sec",
        "cpus",
        "memory_mb",
        "storage_mb",
        "gpus",
        "leaderboard_accuracy_submission",
        "leaderboard_stderr_submission",
        "submission_official_task_count",
        "submission_official_trial_count",
        "submission_official_success_count",
        "submission_official_pass_rate",
    ]
    trajectories = numeric_clean(trajectories, numeric_columns)
    trajectories["passed"] = trajectories["reward"].where(trajectories["reward"].isin([0.0, 1.0]))
    trajectories["passed"] = trajectories["passed"].astype("float")
    trajectories["agent_key"] = (
        trajectories["scaffold"].fillna("unknown") + "::" + trajectories["model_dir"].fillna("unknown")
    )
    trajectories["cost_usd_positive"] = trajectories["cost_usd"].where(trajectories["cost_usd"] > 0)

    df = trajectories.merge(tasks, on="task_name", how="left", validate="many_to_one")
    missing_meta = df[df["category"].isna() | df["difficulty"].isna()].copy()

    df.to_csv(args.out / "trajectory_longitudinal.csv", index=False)
    with (args.out / "longitudinal_data_audit.json").open("w", encoding="utf-8") as f:
        json.dump(build_audit(df, tasks, missing_meta, benchmarks), f, indent=2, default=str)

    print(f"Wrote longitudinal trajectories to {args.out / 'trajectory_longitudinal.csv'}")
    print(f"Wrote audit to {args.out / 'longitudinal_data_audit.json'}")


if __name__ == "__main__":
    main()
