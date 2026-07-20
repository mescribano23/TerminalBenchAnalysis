#!/usr/bin/env python3
"""Compare trajectory durations with task.toml human time estimates.

Outputs:
- data/processed_live/task_mining/time_estimates/trajectory_time_estimate_comparison.csv
- data/processed_live/task_mining/time_estimates/task_time_estimate_distribution_summary.csv
- reports/tasks/time_estimates/distribution_task_time_estimates.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def find_repo_root(start: Path) -> Path:
    for path in (start, *start.parents):
        if (path / "data").exists() and (path / "reports").exists() and (path / "scripts").exists():
            return path
    raise ValueError(f"Could not find repository root from {start}")


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
DATA_DIR = REPO_ROOT / "data"
DATA_PROCESSED_LIVE_DIR = DATA_DIR / "processed_live"
REPORTS_DIR = REPO_ROOT / "reports"

TRAJECTORY_DEFAULT = DATA_PROCESSED_LIVE_DIR / "trajectory_summary.csv"
ESTIMATES_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining" / "terminal_bench_2_task_toml_metadata_current.csv"
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


def summarize_task_time_estimates(estimates: pd.DataFrame) -> pd.DataFrame:
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
    return pd.DataFrame(rows)


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
    comparison: pd.DataFrame,
    path: Path,
) -> Path | None:
    plot_df = valid_task_estimates(estimates)
    if plot_df.empty:
        return None

    duration_df = comparison[
        comparison["has_valid_time_comparison"]
        & comparison["duration_min"].notna()
        & (comparison["duration_seconds"] >= 0)
    ].copy()
    if duration_df.empty:
        return None

    estimate_values = pd.concat([plot_df[column] for column in TIME_ESTIMATE_LABELS], ignore_index=True)
    estimate_max = float(estimate_values.max())
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
    shared_bins = shared_bins[shared_bins <= estimate_max]
    if shared_bins[-1] < estimate_max:
        shared_bins = np.append(shared_bins, estimate_max)

    fig, (hist_ax, duration_ax) = plt.subplots(
        2,
        1,
        figsize=(10.8, 8.2),
        sharex=True,
        gridspec_kw={"height_ratios": [1.05, 1.0]},
    )

    for column, label in TIME_ESTIMATE_LABELS.items():
        values = plot_df[column].dropna().to_numpy(dtype=float)
        weights = np.ones_like(values) / len(values)
        hist_ax.hist(
            values,
            bins=shared_bins,
            weights=weights,
            alpha=0.52,
            color=TIME_ESTIMATE_COLORS[column],
            edgecolor="white",
            linewidth=0.7,
            label=label,
        )

        median_value = float(np.median(values))
        hist_ax.axvline(
            median_value,
            color=TIME_ESTIMATE_COLORS[column],
            linestyle="--",
            linewidth=1.1,
            alpha=0.8,
        )
        hist_ax.text(
            median_value,
            hist_ax.get_ylim()[1] * 0.92,
            f"median {format_minutes(median_value)}",
            rotation=90,
            va="top",
            ha="right",
            fontsize=8,
            color=TIME_ESTIMATE_COLORS[column],
        )

    hist_ax.set_xscale("symlog", linthresh=1)
    hist_ax.set_xlim(0, estimate_max)
    hist_ax.set_ylabel("Share of tasks per bin")
    hist_ax.set_title("Distribution of task-level human time estimates")
    hist_ax.grid(axis="y", alpha=0.25)
    hist_ax.legend(frameon=False, loc="upper right")
    estimate_tick_values = [0, 1, 5, 10, 15, 30, 60, 120, 240, 480, 960, 2880, 7920, 19200]
    estimate_tick_values = [value for value in estimate_tick_values if 0 <= value <= estimate_max]
    hist_ax.set_xticks(estimate_tick_values)
    hist_ax.set_xticklabels([format_minutes(value) for value in estimate_tick_values])

    duration_groups = [
        ("All covered trajectories", duration_df["duration_min"], "#9aa0a6", 0.50),
        ("Passed trajectories", duration_df.loc[duration_df["passed"].eq(1), "duration_min"], "#d9822b", 0.58),
    ]
    for label, values, color, alpha in duration_groups:
        values = values.dropna().to_numpy(dtype=float)
        if len(values) == 0:
            continue
        duration_ax.hist(
            values,
            bins=shared_bins,
            weights=np.ones_like(values) / len(values),
            alpha=alpha,
            color=color,
            edgecolor="white",
            linewidth=0.7,
            label=f"{label} (n={len(values):,})",
        )
        median_value = float(np.median(values))
        duration_ax.axvline(
            median_value,
            color=color,
            linestyle="--",
            linewidth=1.1,
            alpha=0.9,
        )

    duration_count = int(duration_df.shape[0])
    above_axis_count = int(duration_df["duration_min"].gt(estimate_max).sum())
    outside_note = "X-axis starts at 0; symlog scale preserves short durations and long tails."
    if above_axis_count:
        outside_note += f" Outside shown range: {above_axis_count:,} above {format_minutes(estimate_max)} ({above_axis_count / duration_count:.1%})."
    duration_ax.text(
        0.012,
        0.96,
        outside_note,
        transform=duration_ax.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        color="#333333",
    )
    duration_ax.set_xscale("symlog", linthresh=1)
    duration_ax.set_xlim(0, estimate_max)
    duration_ax.set_xlabel("Observed trajectory duration (minutes, symlog scale)")
    duration_ax.set_ylabel("Share of trajectories per bin")
    duration_ax.set_title("Observed trajectory duration distribution on the same x-axis")
    duration_ax.grid(axis="y", alpha=0.25)
    duration_ax.legend(frameon=False, loc="upper right")
    duration_ax.set_xticks(estimate_tick_values)
    duration_ax.set_xticklabels([format_minutes(value) for value in estimate_tick_values])

    fig.text(
        0.5,
        0.01,
        "Top panel uses task-level human estimates; bottom panel uses observed trajectory durations from covered runs.",
        ha="center",
        va="bottom",
        fontsize=8.5,
        color="#333333",
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
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
    estimate_distribution_summary_path = args.out / "task_time_estimate_distribution_summary.csv"

    comparison.loc[:, COMPARISON_OUTPUT_COLUMNS].to_csv(comparison_path, index=False)
    summarize_task_time_estimates(estimates).to_csv(estimate_distribution_summary_path, index=False)

    distribution_path = plot_task_time_estimate_distribution(
        estimates,
        comparison,
        args.figures_dir / "distribution_task_time_estimates.png",
    )

    complete_cases = int(comparison["has_valid_time_comparison"].sum())
    print(f"Loaded {len(trajectories)} pass/fail trajectories")
    print(f"Loaded {len(estimates)} task estimate rows")
    print(f"Valid trajectory/time-estimate comparisons: {complete_cases}")
    print(f"Wrote {comparison_path}")
    print(f"Wrote {estimate_distribution_summary_path}")
    for figure_path in [distribution_path]:
        if figure_path is not None:
            print(f"Wrote {figure_path}")


if __name__ == "__main__":
    main()
