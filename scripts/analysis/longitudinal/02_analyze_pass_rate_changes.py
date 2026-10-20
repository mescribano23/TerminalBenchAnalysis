#!/usr/bin/env python3
"""Analyze Terminal-Bench 2.0 to 2.1 pass-rate changes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

REPO_ROOT_GUESS = Path(__file__).resolve().parents[3]
if str(REPO_ROOT_GUESS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_GUESS))

from scripts.analysis.plot_style import FAIL_COLOR, PASS_COLOR
from scripts.benchmark_paths import find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
LONGITUDINAL_DIR = REPO_ROOT / "data" / "processed_live" / "longitudinal"
TRAJECTORY_CSV = LONGITUDINAL_DIR / "trajectory_longitudinal.csv"
FIGURES_DIR = REPO_ROOT / "reports" / "longitudinal"

VERSION_ORDER = ["2.0", "2.1"]
DIFFICULTY_ORDER = ["easy", "medium", "hard"]
DIFFICULTY_COLORS = {
    "easy": PASS_COLOR,
    "medium": "#E69F00",
    "hard": FAIL_COLOR,
}
DIFFICULTY_MARKERS = {
    "easy": "o",
    "medium": "s",
    "hard": "^",
}
REQUIRED_COLUMNS = {
    "benchmark_version",
    "source_submission_id",
    "historical_leaderboard_timestamp",
    "task_name",
    "passed",
    "difficulty",
    "category",
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monthly-summary-csv", type=Path, default=REPO_ROOT / "data/processed_live/longitudinal/monthly_pass_rate_historical_dates.csv")
    parser.add_argument("--trajectory-csv", type=Path, default=TRAJECTORY_CSV)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR)
    parser.add_argument(
        "--max-categories",
        type=int,
        default=10,
        help="Maximum number of highest-gain categories to show in the category figure.",
    )
    return parser.parse_args()


def thesis_style() -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 120,
        }
    )


def save_png(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def percent(series: pd.Series | np.ndarray | float) -> pd.Series | np.ndarray | float:
    return 100 * series


def load_trajectories(path: Path) -> pd.DataFrame:
    usecols = sorted(REQUIRED_COLUMNS)
    df = pd.read_csv(path, usecols=usecols, low_memory=False)
    require_columns(df, REQUIRED_COLUMNS, str(path))
    df = df.copy()
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    df["task_name"] = df["task_name"].astype(str)
    df["difficulty"] = df["difficulty"].fillna("unknown").astype(str)
    df["category"] = df["category"].fillna("unknown").astype(str)
    df["passed"] = pd.to_numeric(df["passed"], errors="coerce")
    df["historical_leaderboard_timestamp"] = pd.to_datetime(
        df["historical_leaderboard_timestamp"],
        errors="coerce",
        utc=True,
    ).dt.tz_convert(None)
    df = df[df["benchmark_version"].isin(VERSION_ORDER)].dropna(subset=["passed"])
    task_sets = {
        version: set(df.loc[df["benchmark_version"] == version, "task_name"].unique())
        for version in VERSION_ORDER
    }
    shared_tasks = sorted(set.intersection(*task_sets.values()))
    if not shared_tasks:
        raise ValueError("No shared tasks found between Terminal-Bench 2.0 and 2.1.")
    return df[df["task_name"].isin(shared_tasks)].copy()


def task_metadata(df: pd.DataFrame) -> pd.DataFrame:
    rows = (
        df.groupby("task_name", as_index=False)
        .agg(
            difficulty=("difficulty", lambda x: x.mode().iat[0] if not x.mode().empty else "unknown"),
            category=("category", lambda x: x.mode().iat[0] if not x.mode().empty else "unknown"),
        )
        .sort_values("task_name")
    )
    return rows


def task_level_changes(df: pd.DataFrame) -> pd.DataFrame:
    submission_task = (
        df.groupby(["source_submission_id", "task_name", "benchmark_version"], as_index=False)
        .agg(n_trajectories=("passed", "size"), submission_task_pass_rate=("passed", "mean"))
    )
    rates = (
        submission_task.groupby(["task_name", "benchmark_version"], as_index=False)
        .agg(
            n_trajectories=("n_trajectories", "sum"),
            pass_rate=("submission_task_pass_rate", "mean"),
        )
    )
    rate_wide = rates.pivot(index="task_name", columns="benchmark_version", values="pass_rate")
    n_wide = rates.pivot(index="task_name", columns="benchmark_version", values="n_trajectories")
    missing_versions = [version for version in VERSION_ORDER if version not in rate_wide.columns]
    if missing_versions:
        raise ValueError(f"Missing task rates for benchmark version(s): {missing_versions}")
    out = task_metadata(df).merge(rate_wide[VERSION_ORDER].reset_index(), on="task_name", how="inner")
    out = out.rename(columns={"2.0": "tb2_0_pass_rate", "2.1": "tb2_1_pass_rate"})
    out["tb2_0_n_trajectories"] = n_wide["2.0"].reindex(out["task_name"]).to_numpy(dtype=int)
    out["tb2_1_n_trajectories"] = n_wide["2.1"].reindex(out["task_name"]).to_numpy(dtype=int)
    out["pass_rate_change_pp"] = percent(out["tb2_1_pass_rate"] - out["tb2_0_pass_rate"])
    out["change_group"] = np.select(
        [
            out["pass_rate_change_pp"] >= 25,
            out["pass_rate_change_pp"] >= 5,
            out["pass_rate_change_pp"] <= -5,
        ],
        ["substantial improvement", "moderate improvement", "decline"],
        default="approximately unchanged",
    )
    out["persistent_low_performance"] = (out["tb2_0_pass_rate"] <= 0.10) & (out["tb2_1_pass_rate"] <= 0.10)
    for column in ["tb2_0_pass_rate", "tb2_1_pass_rate"]:
        out[column] = percent(out[column])
    return out.sort_values("pass_rate_change_pp", ascending=False).reset_index(drop=True)


def summarize_group(task_changes: pd.DataFrame, group_col: str) -> pd.DataFrame:
    # Use mean task-level pass rates so groups are not dominated by tasks with
    # more trajectories. The pooled-rate check is computed separately.
    summary = (
        task_changes.groupby(group_col, as_index=False)
        .agg(
            n_tasks=("task_name", "nunique"),
            tb2_0_pass_rate=("tb2_0_pass_rate", "mean"),
            tb2_1_pass_rate=("tb2_1_pass_rate", "mean"),
            pass_rate_change_pp=("pass_rate_change_pp", "mean"),
        )
        .sort_values("pass_rate_change_pp", ascending=False)
    )
    if group_col == "difficulty":
        order = {name: idx for idx, name in enumerate(DIFFICULTY_ORDER)}
        summary = summary.sort_values(group_col, key=lambda s: s.map(order).fillna(99))
    return summary.reset_index(drop=True)


def pooled_group_summary(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    task_info = task_metadata(df)
    grouped = df.merge(task_info, on="task_name", suffixes=("", "_task"))
    group_values = grouped[f"{group_col}_task"] if f"{group_col}_task" in grouped.columns else grouped[group_col]
    grouped = grouped.assign(_group=group_values)
    rates = (
        grouped.groupby(["_group", "benchmark_version"], as_index=False)
        .agg(pass_rate=("passed", "mean"))
        .pivot(index="_group", columns="benchmark_version", values="pass_rate")
    )
    rates["pooled_change_pp"] = percent(rates["2.1"] - rates["2.0"])
    return rates[["pooled_change_pp"]].reset_index().rename(columns={"_group": group_col})


def aggregation_check(df: pd.DataFrame, summary: pd.DataFrame, group_col: str) -> str:
    pooled = pooled_group_summary(df, group_col)
    merged = summary[[group_col, "pass_rate_change_pp"]].merge(pooled, on=group_col, how="left")
    merged["absolute_difference_pp"] = (merged["pass_rate_change_pp"] - merged["pooled_change_pp"]).abs()
    max_diff = merged["absolute_difference_pp"].max()
    if pd.isna(max_diff) or max_diff < 5:
        return f"{group_col}: pooled and mean task-level changes tell the same story (max difference {max_diff:.1f} pp)."
    return f"{group_col}: aggregation choice is material (max difference {max_diff:.1f} pp)."


def difficulty_submission_summary(df: pd.DataFrame) -> pd.DataFrame:
    group_columns = ["source_submission_id", "historical_leaderboard_timestamp", "difficulty"]
    per_task = (
        df.dropna(subset=["historical_leaderboard_timestamp"])
        .groupby([*group_columns, "task_name"], as_index=False)
        .agg(
            task_pass_rate=("passed", "mean"),
            task_trajectory_count=("passed", "size"),
        )
    )
    summary = (
        per_task.groupby(group_columns, as_index=False)
        .agg(
            task_count=("task_name", "nunique"),
            trajectory_count=("task_trajectory_count", "sum"),
            task_weighted_pass_rate=("task_pass_rate", "mean"),
        )
        .sort_values(["historical_leaderboard_timestamp", "difficulty", "source_submission_id"])
    )
    # load_trajectories already normalizes these timestamps to timezone-naive UTC.
    summary["submission_month"] = summary["historical_leaderboard_timestamp"].dt.to_period("M").dt.to_timestamp()
    return summary


def monthly_difficulty_summary(difficulty_summary: pd.DataFrame) -> pd.DataFrame:
    return (
        difficulty_summary.groupby(["submission_month", "difficulty"], as_index=False)
        .agg(
            submission_count=("source_submission_id", "nunique"),
            median_pass_rate=("task_weighted_pass_rate", "median"),
        )
        .sort_values(["difficulty", "submission_month"])
    )


def plot_difficulty(df: pd.DataFrame, path: Path) -> None:
    difficulty_summary = difficulty_submission_summary(df)
    monthly = monthly_difficulty_summary(difficulty_summary)
    difficulties = [
        difficulty
        for difficulty in DIFFICULTY_ORDER
        if difficulty in set(difficulty_summary["difficulty"])
    ]
    difficulties.extend(sorted(set(difficulty_summary["difficulty"]).difference(DIFFICULTY_ORDER)))

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for difficulty in difficulties:
        submissions = difficulty_summary[difficulty_summary["difficulty"].eq(difficulty)]
        difficulty_monthly = monthly[monthly["difficulty"].eq(difficulty)]
        if submissions.empty:
            continue

        color = DIFFICULTY_COLORS.get(difficulty, "#666666")
        marker = DIFFICULTY_MARKERS.get(difficulty, "o")
        ax.scatter(
            submissions["historical_leaderboard_timestamp"],
            submissions["task_weighted_pass_rate"],
            s=18,
            alpha=0.24,
            color=color,
            marker=marker,
            edgecolor="none",
        )
        ax.plot(
            difficulty_monthly["submission_month"],
            difficulty_monthly["median_pass_rate"],
            marker=marker,
            markersize=5,
            linewidth=1.8,
            color=color,
            label=difficulty.capitalize(),
        )

    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Task-weighted pass rate")
    ax.set_xlabel("Leaderboard submission date")
    ax.set_title(
        "Submission performance over time by task difficulty\n"
        "Faint points are submission/difficulty values; lines show monthly medians"
    )
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=0))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False, loc="best")
    fig.tight_layout()
    save_png(fig, path)


def plot_category(summary: pd.DataFrame, path: Path, max_categories: int) -> None:
    plot_df = (
        summary.sort_values("pass_rate_change_pp", ascending=False)
        .head(max_categories)
        .sort_values("pass_rate_change_pp", ascending=True)
    )
    height = max(3.2, 0.32 * len(plot_df) + 0.8)
    fig, ax = plt.subplots(figsize=(6.2, height))
    colors = np.where(plot_df["pass_rate_change_pp"] >= 0, PASS_COLOR, FAIL_COLOR)
    ax.barh(plot_df["category"], plot_df["pass_rate_change_pp"], color=colors)
    ax.axvline(0, color="#555555", linewidth=0.8)
    ax.set_xlabel("TB2.1 - TB2.0 pass-rate change (percentage points)")
    ax.set_ylabel("")
    ax.set_title(f"Top {len(plot_df)} Pass Rate Gains by Task Category")
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f pp"))
    save_png(fig, path)


def main() -> None:
    args = parse_args()
    thesis_style()
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    df = load_trajectories(args.trajectory_csv)
    all_tasks = set(df["task_name"].unique())
    task_changes = task_level_changes(df)
    if len(task_changes) != len(all_tasks):
        raise ValueError("Task-level comparison has missing or duplicate task rows.")

    difficulty_changes = summarize_group(task_changes, "difficulty")
    category_changes = summarize_group(task_changes, "category")
    difficulty_check = aggregation_check(df, difficulty_changes, "difficulty")
    category_check = aggregation_check(df, category_changes, "category")

    monthly = monthly_difficulty_summary(difficulty_submission_summary(df))
    monthly["date_variable"] = "historical_leaderboard_timestamp"
    monthly["date_semantics"] = "historical snapshot metadata.date; submission/publication meaning unverified"
    args.monthly_summary_csv.parent.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(args.monthly_summary_csv, index=False)
    plot_difficulty(df, args.figures_dir / "pass_rate_change_by_difficulty.png")
    plot_category(
        category_changes,
        args.figures_dir / "pass_rate_change_by_category.png",
        args.max_categories,
    )

    print(f"Shared tasks matched: {len(all_tasks)}")
    print(difficulty_check)
    print(category_check)
    print(f"Category figure shows top {min(args.max_categories, len(category_changes))} of {len(category_changes)} categories.")
    print(f"Wrote figures to {args.figures_dir}")


if __name__ == "__main__":
    main()
