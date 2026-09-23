#!/usr/bin/env python3
"""Analyze RQ3.1 performance changes across Terminal-Bench versions.

This analysis intentionally does not treat benchmark versions as matched task
sets. Terminal-Bench 3.0 and 4.0 do not currently have task-level metadata and
task identity needed for the existing difficulty/category longitudinal changes,
so RQ3.1 is limited to descriptive performance over benchmark versions.

Outputs:
- data/processed_live/longitudinal/rq3_1_version_performance_summary.csv
- reports/longitudinal/rq3_1_performance_over_versions.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

REPO_ROOT_GUESS = Path(__file__).resolve().parents[3]
if str(REPO_ROOT_GUESS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_GUESS))

from scripts.analysis.plot_style import COLORBLIND_PALETTE
from scripts.benchmark_paths import SUPPORTED_BENCHMARKS, find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
PROCESSED_DIR = REPO_ROOT / "data" / "processed_live"
LONGITUDINAL_DIR = PROCESSED_DIR / "longitudinal"
FIGURES_DIR = REPO_ROOT / "reports" / "longitudinal"

VERSION_SUMMARY_CSV = LONGITUDINAL_DIR / "rq3_1_version_performance_summary.csv"
FIGURE_PATH = FIGURES_DIR / "rq3_1_performance_over_versions.png"

DEFAULT_BENCHMARKS = (
    "terminal_bench_2_0",
    "terminal_bench_2_1",
    "terminal_bench_3_0",
    "terminal_bench_4_0",
)

REQUIRED_COLUMNS = {
    "benchmark",
    "scaffold",
    "model_dir",
    "task_name",
    "reward",
}

OPTIONAL_COLUMNS = [
    "effective_submission_id",
    "source_submission_url",
    "leaderboard_date",
    "leaderboard_accuracy",
    "leaderboard_provider",
]

POOLED_COLOR = COLORBLIND_PALETTE[0]
TASK_WEIGHTED_COLOR = COLORBLIND_PALETTE[2]
SUBMISSION_COLOR = "#7A7A7A"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--out-dir", type=Path, default=LONGITUDINAL_DIR)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR)
    parser.add_argument(
        "--benchmarks",
        nargs="+",
        default=list(DEFAULT_BENCHMARKS),
        choices=SUPPORTED_BENCHMARKS,
        help="Benchmark trajectory_summary.csv directories to include.",
    )
    return parser.parse_args()


def thesis_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 120,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def benchmark_version_label(benchmark: str) -> str:
    return benchmark.replace("terminal_bench_", "").replace("_", ".")


def require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def read_trajectory_table(processed_dir: Path, benchmark: str) -> pd.DataFrame:
    path = processed_dir / benchmark / "trajectory_summary.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Regenerate it with "
            f"`python -m scripts.analysis.00_characterize_trajectories --benchmark {benchmark}`."
        )
    columns = pd.read_csv(path, nrows=0).columns.tolist()
    usecols = [column for column in [*sorted(REQUIRED_COLUMNS), *OPTIONAL_COLUMNS] if column in columns]
    df = pd.read_csv(path, usecols=usecols, low_memory=False)
    require_columns(df, REQUIRED_COLUMNS, str(path))
    df = df.copy()
    df["benchmark"] = benchmark
    df["benchmark_version"] = benchmark_version_label(benchmark)
    for column in OPTIONAL_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df["reward"] = pd.to_numeric(df["reward"], errors="coerce")
    df["passed"] = df["reward"].where(df["reward"].isin([0.0, 1.0]))
    df["task_name"] = df["task_name"].astype(str)
    df["scaffold"] = df["scaffold"].fillna("unknown").astype(str)
    df["model_dir"] = df["model_dir"].fillna("unknown").astype(str)
    df["submission_key"] = submission_key(df)
    df["leaderboard_date"] = pd.to_datetime(df["leaderboard_date"], errors="coerce", utc=True)
    return df.dropna(subset=["passed"])


def submission_key(df: pd.DataFrame) -> pd.Series:
    candidates = [
        df.get("effective_submission_id", pd.Series("", index=df.index)).fillna("").astype(str),
        df.get("source_submission_url", pd.Series("", index=df.index)).fillna("").astype(str),
    ]
    key = candidates[0].where(candidates[0].str.len().gt(0), candidates[1])
    fallback = (
        df["benchmark"].astype(str)
        + "::"
        + df["scaffold"].fillna("unknown").astype(str)
        + "::"
        + df["model_dir"].fillna("unknown").astype(str)
    )
    return key.where(key.str.len().gt(0), fallback)


def load_trajectories(processed_dir: Path, benchmarks: list[str]) -> pd.DataFrame:
    frames = [read_trajectory_table(processed_dir, benchmark) for benchmark in benchmarks]
    if not frames:
        raise ValueError("At least one benchmark is required.")
    return pd.concat(frames, ignore_index=True)


def version_sort_key(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in str(version).split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(999)
    return tuple(parts)


def task_weighted_rate(df: pd.DataFrame) -> float:
    submission_task_rates = (
        df.groupby(["submission_key", "task_name"], as_index=False)
        .agg(submission_task_pass_rate=("passed", "mean"))
    )
    task_rates = submission_task_rates.groupby("task_name")["submission_task_pass_rate"].mean()
    return float(task_rates.mean()) if not task_rates.empty else np.nan


def build_version_summary(df: pd.DataFrame) -> pd.DataFrame:
    submission_rates = (
        df.groupby(["benchmark_version", "submission_key", "task_name"], as_index=False)
        .agg(submission_task_pass_rate=("passed", "mean"))
        .groupby(["benchmark_version", "submission_key"], as_index=False)
        .agg(submission_pass_rate=("submission_task_pass_rate", "mean"))
    )
    rows: list[dict[str, object]] = []
    for version, group in df.groupby("benchmark_version", sort=False):
        version_submission_rates = submission_rates.loc[
            submission_rates["benchmark_version"].eq(version), "submission_pass_rate"
        ]
        rows.append(
            {
                "benchmark_version": version,
                "benchmark": group["benchmark"].mode().iat[0],
                "trajectory_count": int(group.shape[0]),
                "task_count": int(group["task_name"].nunique()),
                "submission_count": int(group["submission_key"].nunique()),
                "scaffold_count": int(group["scaffold"].nunique()),
                "model_count": int(group["model_dir"].nunique()),
                "pooled_pass_rate": float(group["passed"].mean()),
                "task_weighted_pass_rate": task_weighted_rate(group),
                "median_submission_pass_rate": float(version_submission_rates.median())
                if not version_submission_rates.empty
                else np.nan,
                "mean_submission_pass_rate": float(version_submission_rates.mean())
                if not version_submission_rates.empty
                else np.nan,
            }
        )
    summary = pd.DataFrame(rows)
    summary["_sort"] = summary["benchmark_version"].map(version_sort_key)
    return summary.sort_values("_sort").drop(columns="_sort").reset_index(drop=True)


def build_submission_summary(df: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "benchmark_version",
        "benchmark",
        "submission_key",
        "scaffold",
        "model_dir",
    ]
    submission_task = (
        df.groupby(
            [
                *keys,
                "task_name",
            ],
            as_index=False,
        )
        .agg(
            submission_task_trajectory_count=("passed", "size"),
            submission_task_pass_rate=("passed", "mean"),
            leaderboard_date=("leaderboard_date", "min"),
            leaderboard_accuracy=("leaderboard_accuracy", "first"),
            leaderboard_provider=("leaderboard_provider", "first"),
        )
    )
    summary = (
        submission_task.groupby(keys, as_index=False)
        .agg(
            trajectory_count=("submission_task_trajectory_count", "sum"),
            task_count=("task_name", "nunique"),
            pass_rate=("submission_task_pass_rate", "mean"),
            leaderboard_date=("leaderboard_date", "min"),
            leaderboard_accuracy=("leaderboard_accuracy", "first"),
            leaderboard_provider=("leaderboard_provider", "first"),
        )
        .sort_values(["benchmark_version", "scaffold", "model_dir", "submission_key"])
    )
    pooled = (
        df.groupby(keys, as_index=False)
        .agg(pooled_submission_pass_rate=("passed", "mean"))
    )
    summary = summary.merge(pooled, on=keys, how="left")
    summary["leaderboard_accuracy"] = pd.to_numeric(summary["leaderboard_accuracy"], errors="coerce")
    summary["_sort"] = summary["benchmark_version"].map(version_sort_key)
    return summary.sort_values(["_sort", "scaffold", "model_dir"]).drop(columns="_sort").reset_index(drop=True)


def format_pct(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{100 * value:.1f}%"


def annotate_line(
    ax: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    labels: list[str],
    color: str,
    *,
    x_offset: float = 0.0,
    y_offset: float = 0.025,
    va: str = "bottom",
) -> None:
    for xpos, ypos, label in zip(x, y, labels):
        if pd.isna(ypos):
            continue
        ax.text(
            xpos + x_offset,
            ypos + y_offset,
            label,
            ha="center",
            va=va,
            fontsize=8,
            color=color,
        )


def plot(version_summary: pd.DataFrame, submission_summary: pd.DataFrame, out: Path) -> None:
    thesis_style()
    x = np.arange(version_summary.shape[0], dtype=float)
    pooled = version_summary["pooled_pass_rate"].astype(float).to_numpy()
    task_weighted = version_summary["task_weighted_pass_rate"].astype(float).to_numpy()

    fig, ax = plt.subplots(figsize=(6.7, 3.9))
    ax.plot(
        x,
        pooled,
        color=POOLED_COLOR,
        marker="o",
        linewidth=2.0,
        label="Pooled trajectory pass rate",
    )
    ax.plot(
        x,
        task_weighted,
        color=TASK_WEIGHTED_COLOR,
        marker="s",
        linewidth=2.0,
        label="Task-weighted pass rate",
    )

    rng = np.random.default_rng(31)
    for idx, version in enumerate(version_summary["benchmark_version"]):
        rates = submission_summary.loc[
            submission_summary["benchmark_version"].eq(version), "pass_rate"
        ].dropna()
        if rates.empty:
            continue
        jitter = rng.uniform(-0.06, 0.06, size=len(rates))
        ax.scatter(
            np.full(len(rates), idx, dtype=float) + jitter,
            rates,
            s=16,
            color=SUBMISSION_COLOR,
            alpha=0.26,
            edgecolor="none",
            label="Submission pass rate" if idx == 0 else None,
        )

    annotate_line(
        ax,
        x,
        pooled,
        [format_pct(value) for value in version_summary["pooled_pass_rate"]],
        POOLED_COLOR,
        x_offset=-0.06,
        y_offset=-0.028,
        va="top",
    )
    annotate_line(
        ax,
        x,
        task_weighted,
        [format_pct(value) for value in version_summary["task_weighted_pass_rate"]],
        TASK_WEIGHTED_COLOR,
        x_offset=0.06,
        y_offset=0.028,
        va="bottom",
    )

    xtick_labels = [
        f"TB{row.benchmark_version}\n{int(row.task_count)} tasks, {int(row.trajectory_count):,} traj."
        for row in version_summary.itertuples(index=False)
    ]
    ax.set_xticks(x)
    ax.set_xticklabels(xtick_labels)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Pass rate")
    ax.set_xlabel("")
    ax.set_title("RQ3.1 Performance Across Terminal-Bench Versions")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=0))
    ax.grid(axis="y", color="#D0D0D0", alpha=0.55, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="best")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def print_summary(version_summary: pd.DataFrame, out: Path) -> None:
    print("RQ3.1 performance-over-version summary")
    print("Scope: descriptive pass-rate comparison over unmatched benchmark task pools.")
    print("")
    print(
        "version,trajectories,tasks,submissions,pooled_pass_rate,"
        "task_weighted_pass_rate,median_submission_pass_rate"
    )
    for row in version_summary.itertuples(index=False):
        print(
            f"{row.benchmark_version},{int(row.trajectory_count)},{int(row.task_count)},"
            f"{int(row.submission_count)},{format_pct(row.pooled_pass_rate)},"
            f"{format_pct(row.task_weighted_pass_rate)},"
            f"{format_pct(row.median_submission_pass_rate)}"
        )
    print("")
    print(f"Wrote figure to {out}")


def main() -> None:
    args = parse_args()
    trajectories = load_trajectories(args.processed_dir, args.benchmarks)
    version_summary = build_version_summary(trajectories)
    submission_summary = build_submission_summary(trajectories)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    version_csv = args.out_dir / VERSION_SUMMARY_CSV.name
    figure_path = args.figures_dir / FIGURE_PATH.name

    version_summary.to_csv(version_csv, index=False)
    plot(version_summary, submission_summary, figure_path)

    print_summary(version_summary, figure_path)
    print(f"Wrote {version_csv}")


if __name__ == "__main__":
    main()
