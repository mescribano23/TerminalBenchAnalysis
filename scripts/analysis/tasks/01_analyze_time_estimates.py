#!/usr/bin/env python3
"""Compare trajectory durations with task.toml human time estimates.

Outputs:
- data/processed_live/task_mining/time_estimates/trajectory_time_estimate_comparison.csv
- data/processed_live/task_mining/time_estimates/task_average_duration_comparison.csv
- data/processed_live/task_mining/time_estimates/task_time_estimate_distribution_summary.csv
- reports/tasks/time_estimates/distribution_task_time_estimates.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.benchmark_paths import find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
DATA_DIR = REPO_ROOT / "data"
DATA_PROCESSED_LIVE_DIR = DATA_DIR / "processed_live"
REPORTS_DIR = REPO_ROOT / "reports"

TRAJECTORY_DEFAULT = DATA_PROCESSED_LIVE_DIR / "terminal_bench_2_0" / "trajectory_summary.csv"
ESTIMATES_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining" / "terminal_bench_2_task_toml_metadata.csv"
OUT_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining" / "time_estimates"
FIGURES_DEFAULT = REPORTS_DIR / "tasks" / "time_estimates"

OUTCOME_COLUMNS = {"task_name", "reward_outcome", "outcome", "reward"}
TRAJECTORY_COLUMNS = {
    "scaffold",
    "model_dir",
    "duration_seconds",
}
ESTIMATE_COLUMNS = {
    "task_name",
    "expert_time_estimate_min",
    "junior_time_estimate_min",
}
COMPARISON_OUTPUT_COLUMNS = [
    "scaffold",
    "model_dir",
    "task_name",
    "passed",
    "duration_seconds",
    "expert_time_estimate_min",
    "junior_time_estimate_min",
    "has_valid_time_comparison",
]
TIME_ESTIMATE_LABELS = {
    "expert_time_estimate_min": "Expert estimate",
    "junior_time_estimate_min": "Junior estimate",
}
TIME_ESTIMATE_COLORS = {
    "expert_time_estimate_min": "#4f8f63",
    "junior_time_estimate_min": "#73a6c8",
}
TASK_DURATION_OUTPUT_COLUMNS = [
    "task_name",
    "n_trajectories",
    "n_passed",
    "pass_rate",
    "mean_duration_min",
    "median_duration_min",
    "expert_time_estimate_min",
    "junior_time_estimate_min",
    "mean_duration_vs_expert_estimate",
    "mean_duration_vs_junior_estimate",
]
OBSERVED_MEAN_DURATION_LABEL = "Observed mean duration"
OBSERVED_MEAN_DURATION_COLOR = "#c65d4a"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectories", type=Path, default=TRAJECTORY_DEFAULT)
    parser.add_argument("--estimates", type=Path, default=ESTIMATES_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DEFAULT)
    return parser.parse_args()


def load_trajectories(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=lambda column: column in OUTCOME_COLUMNS | TRAJECTORY_COLUMNS)
    if "task_name" not in df.columns:
        raise ValueError(f"{path} must contain task_name.")
    if "duration_seconds" not in df.columns:
        raise ValueError(f"{path} must contain duration_seconds.")

    if "reward_outcome" in df.columns:
        df["outcome"] = df["reward_outcome"]
    elif "outcome" not in df.columns and "reward" in df.columns:
        reward = pd.to_numeric(df["reward"], errors="coerce")
        df["outcome"] = reward.map({1.0: "pass", 0.0: "fail"})

    if "outcome" not in df.columns:
        raise ValueError(f"{path} must contain reward_outcome, outcome, or reward.")

    df = df[df["outcome"].isin(["pass", "fail"])].copy()
    if df.empty:
        raise ValueError(f"{path} has no pass/fail trajectory rows.")

    for column in ["scaffold", "model_dir"]:
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].fillna("").astype(str)

    df["duration_seconds"] = pd.to_numeric(df["duration_seconds"], errors="coerce")
    df["passed"] = (df["outcome"] == "pass").astype(int)
    return df


def load_estimates(path: Path) -> pd.DataFrame:
    estimates = pd.read_csv(path, usecols=lambda column: column in ESTIMATE_COLUMNS)
    missing = ESTIMATE_COLUMNS.difference(estimates.columns)
    if missing:
        raise ValueError(f"{path} is missing required fields: {', '.join(sorted(missing))}")
    estimates = estimates.drop_duplicates("task_name").copy()
    for column in ["expert_time_estimate_min", "junior_time_estimate_min"]:
        estimates[column] = pd.to_numeric(estimates[column], errors="coerce")
    return estimates


def solve_time_band(row: pd.Series) -> str:
    if not bool(row["passed"]):
        return "failed"
    if bool(row["within_expert_time"]):
        return "expert_or_faster"
    if bool(row["within_junior_time"]):
        return "between_expert_and_junior"
    return "slower_than_junior"


def build_trajectory_comparison(trajectories: pd.DataFrame, estimates: pd.DataFrame) -> pd.DataFrame:
    df = trajectories.merge(estimates, on="task_name", how="left", validate="many_to_one")
    df["has_time_estimate"] = df["expert_time_estimate_min"].notna() & df["junior_time_estimate_min"].notna()
    df["has_valid_duration"] = df["duration_seconds"].notna() & (df["duration_seconds"] >= 0)
    df["has_valid_time_comparison"] = (
        df["has_time_estimate"]
        & df["has_valid_duration"]
        & (df["expert_time_estimate_min"] > 0)
        & (df["junior_time_estimate_min"] > 0)
        & (df["junior_time_estimate_min"] >= df["expert_time_estimate_min"])
    )

    df["duration_min"] = df["duration_seconds"] / 60
    df["duration_vs_expert_estimate"] = df["duration_min"] / df["expert_time_estimate_min"]
    df["duration_vs_junior_estimate"] = df["duration_min"] / df["junior_time_estimate_min"]
    denominator = df["junior_time_estimate_min"] - df["expert_time_estimate_min"]
    df["human_time_position"] = (df["duration_min"] - df["expert_time_estimate_min"]) / denominator.replace(0, np.nan)
    df["within_expert_time"] = df["duration_min"] <= df["expert_time_estimate_min"]
    df["within_junior_time"] = df["duration_min"] <= df["junior_time_estimate_min"]
    df["solved_within_expert_estimate"] = df["passed"].eq(1) & df["within_expert_time"]
    df["solved_within_junior_estimate"] = df["passed"].eq(1) & df["within_junior_time"]
    df["solve_time_band"] = df.apply(solve_time_band, axis=1)

    return df


def valid_task_estimates(estimates: pd.DataFrame) -> pd.DataFrame:
    return estimates[
        estimates["expert_time_estimate_min"].notna()
        & estimates["junior_time_estimate_min"].notna()
        & (estimates["expert_time_estimate_min"] > 0)
        & (estimates["junior_time_estimate_min"] > 0)
        & (estimates["junior_time_estimate_min"] >= estimates["expert_time_estimate_min"])
    ].copy()


def summarize_task_time_distributions(
    estimates: pd.DataFrame,
    task_duration_comparison: pd.DataFrame,
) -> pd.DataFrame:
    work = valid_task_estimates(estimates)
    rows: list[dict[str, object]] = []
    percentiles = {
        "p10_min": 0.10,
        "p25_min": 0.25,
        "median_min": 0.50,
        "p75_min": 0.75,
        "p90_min": 0.90,
        "p95_min": 0.95,
    }
    for column, label in TIME_ESTIMATE_LABELS.items():
        values = work[column].dropna()
        if values.empty:
            continue
        row = {
            "estimate_type": label,
            "n_tasks": int(values.shape[0]),
            "min_min": float(values.min()),
            "mean_min": float(values.mean()),
            "max_min": float(values.max()),
        }
        row.update({name: float(values.quantile(q)) for name, q in percentiles.items()})
        rows.append(row)
    if not task_duration_comparison.empty:
        values = task_duration_comparison["mean_duration_min"].dropna()
        if not values.empty:
            row = {
                "estimate_type": OBSERVED_MEAN_DURATION_LABEL,
                "n_tasks": int(values.shape[0]),
                "min_min": float(values.min()),
                "mean_min": float(values.mean()),
                "max_min": float(values.max()),
            }
            row.update({name: float(values.quantile(q)) for name, q in percentiles.items()})
            rows.append(row)
    return pd.DataFrame(rows)


def build_task_average_duration_comparison(comparison: pd.DataFrame) -> pd.DataFrame:
    duration_df = comparison[
        comparison["has_valid_time_comparison"]
        & comparison["duration_min"].notna()
        & comparison["duration_seconds"].ge(0)
    ].copy()
    if duration_df.empty:
        return pd.DataFrame(columns=TASK_DURATION_OUTPUT_COLUMNS)

    grouped = (
        duration_df.groupby("task_name", as_index=False)
        .agg(
            n_trajectories=("duration_min", "size"),
            n_passed=("passed", "sum"),
            mean_duration_min=("duration_min", "mean"),
            median_duration_min=("duration_min", "median"),
            expert_time_estimate_min=("expert_time_estimate_min", "first"),
            junior_time_estimate_min=("junior_time_estimate_min", "first"),
        )
        .sort_values("task_name")
    )
    grouped["pass_rate"] = grouped["n_passed"] / grouped["n_trajectories"]
    grouped["mean_duration_vs_expert_estimate"] = (
        grouped["mean_duration_min"] / grouped["expert_time_estimate_min"]
    )
    grouped["mean_duration_vs_junior_estimate"] = (
        grouped["mean_duration_min"] / grouped["junior_time_estimate_min"]
    )
    return grouped.loc[:, TASK_DURATION_OUTPUT_COLUMNS]


def format_minutes(value: float) -> str:
    def compact(number: float) -> str:
        if np.isclose(number, round(number)):
            return str(int(round(number)))
        return f"{number:.1f}".rstrip("0").rstrip(".")

    if value < 1:
        return f"{compact(value * 60)}s"
    if value < 60:
        return f"{compact(value)}m"
    if value < 60 * 24:
        hours = value / 60
        return f"{compact(hours)}h"
    days = value / (60 * 24)
    return f"{compact(days)}d"


def plot_task_time_estimate_distribution(
    estimates: pd.DataFrame,
    task_duration_comparison: pd.DataFrame,
    path: Path,
) -> Path | None:
    plot_df = valid_task_estimates(estimates)
    if plot_df.empty:
        return None

    duration_df = task_duration_comparison[
        task_duration_comparison["mean_duration_min"].notna()
        & task_duration_comparison["mean_duration_min"].ge(0)
    ].copy()
    if duration_df.empty:
        return None

    distribution_series = [
        (
            TIME_ESTIMATE_LABELS["expert_time_estimate_min"],
            plot_df["expert_time_estimate_min"],
            TIME_ESTIMATE_COLORS["expert_time_estimate_min"],
            0.44,
        ),
        (
            TIME_ESTIMATE_LABELS["junior_time_estimate_min"],
            plot_df["junior_time_estimate_min"],
            TIME_ESTIMATE_COLORS["junior_time_estimate_min"],
            0.44,
        ),
        (
            OBSERVED_MEAN_DURATION_LABEL,
            duration_df["mean_duration_min"],
            OBSERVED_MEAN_DURATION_COLOR,
            0.54,
        ),
    ]
    all_values = pd.concat([series for _, series, _, _ in distribution_series], ignore_index=True).dropna()
    axis_max = float(all_values.max())
    shared_bins = np.array(
        [
            0,
            1 / 60,
            5 / 60,
            10 / 60,
            30 / 60,
            1,
            2,
            5,
            10,
            15,
            30,
            60,
            120,
            240,
            480,
            960,
            2880,
            7920,
            19200,
        ],
        dtype=float,
    )
    shared_bins = shared_bins[shared_bins <= axis_max]
    if shared_bins[-1] < axis_max:
        shared_bins = np.append(shared_bins, axis_max)

    fig, ax = plt.subplots(figsize=(10.8, 5.9))
    median_annotations: list[tuple[float, str, str]] = []

    for label, series, color, alpha in distribution_series:
        values = series.dropna().to_numpy(dtype=float)
        if len(values) == 0:
            continue
        ax.hist(
            values,
            bins=shared_bins,
            weights=np.ones_like(values) / len(values),
            alpha=alpha,
            color=color,
            edgecolor=color,
            linewidth=1.0,
            label=f"{label} (n={len(values):,})",
        )
        median_value = float(np.median(values))
        ax.axvline(
            median_value,
            color=color,
            linestyle="--",
            linewidth=1.1,
            alpha=0.85,
        )
        median_annotations.append(
            (median_value, f"{label} median: {format_minutes(median_value)}", color)
        )

    note = "Observed mean uses one averaged value per task; distributions are normalized by task count."
    ax.text(
        0.012,
        0.96,
        note,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        color="#333333",
    )
    ax.set_xscale("symlog", linthresh=1)
    ax.set_xlim(0, axis_max)
    ax.set_xlabel("Time per task (minutes, symlog scale)")
    ax.set_ylabel("Share of tasks per bin")
    ax.set_title("Task-level distributions of estimates and observed mean duration")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, loc="upper right")
    for label_y, (median_value, label, color) in zip(
        [0.78, 0.68, 0.58],
        median_annotations,
    ):
        ax.text(
            median_value,
            label_y,
            label,
            transform=ax.get_xaxis_transform(),
            rotation=90,
            ha="right",
            va="top",
            fontsize=8.5,
            color=color,
        )
    tick_values = [0, 1, 5, 10, 15, 30, 60, 120, 240, 480, 960, 2880, 7920, 19200]
    tick_values = [value for value in tick_values if 0 <= value <= axis_max]
    ax.set_xticks(tick_values)
    ax.set_xticklabels([format_minutes(value) for value in tick_values])

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    trajectories = load_trajectories(args.trajectories)
    estimates = load_estimates(args.estimates)
    comparison = build_trajectory_comparison(trajectories, estimates)

    comparison_path = args.out / "trajectory_time_estimate_comparison.csv"
    task_duration_comparison_path = args.out / "task_average_duration_comparison.csv"
    estimate_distribution_summary_path = args.out / "task_time_estimate_distribution_summary.csv"

    comparison.loc[:, COMPARISON_OUTPUT_COLUMNS].to_csv(comparison_path, index=False)
    task_duration_comparison = build_task_average_duration_comparison(comparison)
    task_duration_comparison.to_csv(task_duration_comparison_path, index=False)
    summarize_task_time_distributions(estimates, task_duration_comparison).to_csv(
        estimate_distribution_summary_path,
        index=False,
    )

    distribution_path = plot_task_time_estimate_distribution(
        estimates,
        task_duration_comparison,
        args.figures_dir / "distribution_task_time_estimates.png",
    )

    complete_cases = int(comparison["has_valid_time_comparison"].sum())
    print(f"Loaded {len(trajectories)} pass/fail trajectories")
    print(f"Loaded {len(estimates)} task estimate rows")
    print(f"Valid trajectory/time-estimate comparisons: {complete_cases}")
    print(f"Task-level average duration rows: {len(task_duration_comparison)}")
    print(f"Wrote {comparison_path}")
    print(f"Wrote {task_duration_comparison_path}")
    print(f"Wrote {estimate_distribution_summary_path}")
    for figure_path in [distribution_path]:
        if figure_path is not None:
            print(f"Wrote {figure_path}")


if __name__ == "__main__":
    main()
