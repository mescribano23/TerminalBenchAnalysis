#!/usr/bin/env python3
"""Analyze benchmark-version trajectory-effort changes for RQ3.3.

This script compares two Terminal-Bench versions' trajectory effort on a
longitudinal dataset. The default TB2.0/TB2.1 figure establishes the RQ3.3 token anomaly:
observable trajectory-effort measures generally decrease or grow modestly,
while reported token usage increases more strongly.
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

from scripts.analysis.plot_style import COLORBLIND_PALETTE, NEUTRAL_COLOR
from scripts.benchmark_paths import find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
LONGITUDINAL_DIR = REPO_ROOT / "data" / "processed_live" / "longitudinal"
TRAJECTORY_CSV = LONGITUDINAL_DIR / "trajectory_longitudinal.csv"
TB3_TB4_TRAJECTORY_CSV = LONGITUDINAL_DIR / "tb3_tb4" / "trajectory_longitudinal.csv"
TASK_AUDIT_CSV = LONGITUDINAL_DIR / "task_version_audit.csv"
TASK_CHANGES_CSV = LONGITUDINAL_DIR / "task_composition" / "adjacent_version_task_changes.csv"
FIGURE_DIR = REPO_ROOT / "reports" / "longitudinal"
BASELINE_FIGURE_PATH = FIGURE_DIR / "performance_effort_change_over_time_tb2_0_to_tb2_1.png"
TB3_TB4_FIGURE_PATH = FIGURE_DIR / "performance_effort_change_over_time_tb3_0_to_tb4_0.png"
POOLED_SUMMARY_CSV = LONGITUDINAL_DIR / "task_balanced_effort_pooled_summary.csv"
TASK_BALANCED_SUMMARY_CSV = LONGITUDINAL_DIR / "task_balanced_effort_summary.csv"

BASELINE_LABEL = "Terminal-Bench 2.0"
COMPARISON_LABEL = "Terminal-Bench 2.1"
BASELINE_VERSION = "2.0"
COMPARISON_VERSION = "2.1"

REQUIRED_COLUMNS = {
    "benchmark_version",
    "submission_id",
    "task_name",
    "step_count",
    "shell_invocation_count",
    "tool_call_count",
    "duration_seconds",
    "message_chars",
    "reasoning_chars",
    "observation_chars",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
}

EFFORT_COLOR = NEUTRAL_COLOR
TEXT_COLOR = COLORBLIND_PALETTE[2]
INPUT_TOKEN_COLOR = COLORBLIND_PALETTE[0]
OUTPUT_TOKEN_COLOR = COLORBLIND_PALETTE[4]
TOTAL_TOKEN_COLOR = COLORBLIND_PALETTE[3]


def metric_spec(key: str, label: str, column: str, color: str) -> dict[str, str]:
    return {"key": key, "label": label, "column": column, "aggregation": "median", "color": color}


METRICS = [
    metric_spec("steps", "Steps", "step_count", EFFORT_COLOR),
    metric_spec("shell_invocations", "Shell invocations", "shell_invocation_count", EFFORT_COLOR),
    metric_spec("tool_calls", "Structured tool calls", "tool_call_count", EFFORT_COLOR),
    # duration_seconds is the existing benchmark-reported duration field in
    # the longitudinal dataset, not a reconstruction from trajectory timestamps.
    metric_spec("duration", "Duration", "duration_seconds", EFFORT_COLOR),
    metric_spec("chars", "Logged trajectory characters", "logged_chars", TEXT_COLOR),
    metric_spec("prompt_tokens", "Prompt/input tokens", "prompt_tokens", INPUT_TOKEN_COLOR),
    metric_spec("completion_tokens", "Completion/output tokens", "completion_tokens", OUTPUT_TOKEN_COLOR),
    metric_spec("total_tokens", "Total tokens", "total_tokens", TOTAL_TOKEN_COLOR),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-csv", type=Path, default=TRAJECTORY_CSV)
    parser.add_argument("--task-audit-csv", type=Path, default=TASK_AUDIT_CSV)
    parser.add_argument("--task-changes-csv", type=Path, default=TASK_CHANGES_CSV)
    parser.add_argument("--baseline-version", default=BASELINE_VERSION)
    parser.add_argument("--comparison-version", default=COMPARISON_VERSION)
    parser.add_argument("--baseline-label", default=None)
    parser.add_argument("--comparison-label", default=None)
    parser.add_argument(
        "--include-tb3-tb4",
        action="store_true",
        help="Also write a separate TB3.0->TB4.0 effort-change figure.",
    )
    parser.add_argument("--tb3-tb4-trajectory-csv", type=Path, default=TB3_TB4_TRAJECTORY_CSV)
    parser.add_argument("--pooled-summary-csv", type=Path, default=POOLED_SUMMARY_CSV)
    parser.add_argument("--task-balanced-summary-csv", type=Path, default=TASK_BALANCED_SUMMARY_CSV)
    parser.add_argument("--out", type=Path, default=BASELINE_FIGURE_PATH)
    parser.add_argument("--tb3-tb4-out", type=Path, default=TB3_TB4_FIGURE_PATH)
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


def require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def load_trajectories(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df = df[[column for column in sorted(REQUIRED_COLUMNS) if column in df.columns]].copy()
    require_columns(df, REQUIRED_COLUMNS, str(path))
    df = df.copy()
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    for column in REQUIRED_COLUMNS.difference({"benchmark_version", "submission_id", "task_name"}):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["logged_chars"] = df["message_chars"] + df["reasoning_chars"] + df["observation_chars"]
    return df.dropna(subset=["benchmark_version"])


def version_display_label(version: str) -> str:
    return f"TB{version}"


def full_version_label(version: str) -> str:
    return f"Terminal-Bench {version}"


def load_tb2_instruction_unchanged_tasks(path: Path) -> set[str]:
    audit = pd.read_csv(path, usecols=["task_name", "classification"])
    return set(audit.loc[audit["classification"].eq("Identical"), "task_name"].astype(str))


def load_adjacent_instruction_unchanged_tasks(path: Path, baseline_version: str, comparison_version: str) -> set[str]:
    if not path.exists():
        return set()
    changes = pd.read_csv(path, low_memory=False)
    required = {"version_pair", "task_name", "tb3_tb4_change_classification_new"}
    if not required.issubset(changes.columns):
        return set()
    pair = f"{baseline_version}->{comparison_version}"
    unchanged_labels = {"Only release boilerplate changed", "Package identical"}
    unchanged = changes[
        changes["version_pair"].astype(str).eq(pair)
        & changes["tb3_tb4_change_classification_new"].astype(str).isin(unchanged_labels)
    ]
    return set(unchanged["task_name"].astype(str))


def load_instruction_unchanged_tasks(args: argparse.Namespace) -> set[str]:
    baseline_version = str(args.baseline_version)
    comparison_version = str(args.comparison_version)
    if baseline_version == BASELINE_VERSION and comparison_version == COMPARISON_VERSION:
        return load_tb2_instruction_unchanged_tasks(args.task_audit_csv)
    return load_adjacent_instruction_unchanged_tasks(
        args.task_changes_csv,
        baseline_version,
        comparison_version,
    )


def version_subset(df: pd.DataFrame, version: str) -> pd.DataFrame:
    return df[df["benchmark_version"] == version].copy()


def metric_value(series: pd.Series, aggregation: str) -> float:
    valid = series.dropna()
    if valid.empty:
        return np.nan
    if aggregation == "mean":
        return float(valid.mean())
    if aggregation == "median":
        return float(valid.median())
    raise ValueError(f"Unknown aggregation: {aggregation}")


def summarize_periods(
    df: pd.DataFrame,
    baseline_version: str,
    comparison_version: str,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    periods = {
        "early": version_subset(df, baseline_version),
        "late": version_subset(df, comparison_version),
    }
    empty_periods = [name for name, subset in periods.items() if subset.empty]
    if empty_periods:
        raise ValueError(f"No trajectories found for benchmark version group(s): {', '.join(empty_periods)}")

    rows: list[dict[str, object]] = []
    for metric in METRICS:
        early = periods["early"][metric["column"]]
        late = periods["late"][metric["column"]]
        early_value = metric_value(early, metric["aggregation"])
        late_value = metric_value(late, metric["aggregation"])
        if pd.isna(early_value) or pd.isna(late_value):
            raise ValueError(f"Metric {metric['label']!r} has no valid value in one or both periods.")
        if early_value == 0:
            raise ValueError(f"Metric {metric['label']!r} has zero early-period baseline.")
        later_relative = late_value / early_value
        rows.append(
            {
                "key": metric["key"],
                "metric": metric["label"],
                "column": metric["column"],
                "aggregation": metric["aggregation"],
                "early_value": early_value,
                "late_value": late_value,
                "early_valid_n": int(early.notna().sum()),
                "late_valid_n": int(late.notna().sum()),
                "early_relative": 1.0,
                "late_relative": later_relative,
                "relative_change_pct": (later_relative - 1.0) * 100,
                "color": metric["color"],
            }
        )
    return pd.DataFrame(rows), periods


def direction(change: float) -> str:
    if pd.isna(change):
        return "missing"
    if change > 0:
        return "increase"
    if change < 0:
        return "decrease"
    return "tie"


def build_task_balanced_outputs(
    df: pd.DataFrame,
    unchanged_tasks: set[str],
    baseline_version: str,
    comparison_version: str,
) -> pd.DataFrame:
    summary_rows: list[dict[str, object]] = []
    for metric in METRICS:
        column = str(metric["column"])
        medians = task_metric_pairs(df, column)
        if baseline_version not in medians.columns or comparison_version not in medians.columns:
            continue
        medians = medians.dropna(subset=[baseline_version, comparison_version]).copy()
        medians["paired_change"] = medians[comparison_version] - medians[baseline_version]
        medians["paired_relative_change_pct"] = (
            medians[comparison_version] / medians[baseline_version] - 1.0
        ) * 100.0
        subsets = [("all_shared_tasks", medians)]
        if unchanged_tasks:
            subsets.append(("instruction_unchanged", medians.loc[medians.index.intersection(unchanged_tasks)]))
        for task_set, subset in subsets:
            n_tasks = int(len(subset))
            increasing = int((subset["paired_change"] > 0).sum())
            decreasing = int((subset["paired_change"] < 0).sum())
            ties = int((subset["paired_change"] == 0).sum())
            median_change = float(subset["paired_change"].median()) if n_tasks else np.nan
            summary_rows.append(
                {
                    "metric": metric["key"],
                    "metric_display": metric["label"],
                    "task_set": task_set,
                    "n_tasks_with_both_versions": n_tasks,
                    "median_paired_change": median_change,
                    "median_paired_relative_change_pct": (
                        float(subset["paired_relative_change_pct"].replace([np.inf, -np.inf], np.nan).median())
                        if n_tasks
                        else np.nan
                    ),
                    "direction": direction(median_change),
                    "tasks_increasing_n": increasing,
                    "tasks_increasing_fraction": increasing / n_tasks if n_tasks else np.nan,
                    "tasks_decreasing_n": decreasing,
                    "tasks_decreasing_fraction": decreasing / n_tasks if n_tasks else np.nan,
                    "tasks_tied_n": ties,
                }
            )
    return pd.DataFrame(summary_rows)


def task_metric_pairs(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Return submission-balanced task medians, with versions as columns."""
    work = df[["submission_id", "task_name", "benchmark_version", column]].dropna().copy()
    if work["submission_id"].astype(str).str.strip().eq("").any():
        raise ValueError(f"Metric {column!r} has rows with empty submission_id values.")
    submission_task = (
        work.groupby(["submission_id", "task_name", "benchmark_version"], as_index=False)[column]
        .median()
        .rename(columns={column: "submission_task_median"})
    )
    return (
        submission_task.groupby(["task_name", "benchmark_version"])["submission_task_median"]
        .median()
        .unstack()
    )


def format_raw(key: str, value: float) -> str:
    if key == "duration":
        return f"{value:.0f} s"
    if key in {"chars", "prompt_tokens", "completion_tokens", "total_tokens"}:
        return f"{value / 1000:.1f}k"
    return f"{value:.0f}"


def add_formatted_columns(summary: pd.DataFrame) -> pd.DataFrame:
    summary = summary.copy()
    summary["early_label"] = [
        format_raw(key, value) for key, value in zip(summary["key"], summary["early_value"])
    ]
    summary["late_label"] = [
        format_raw(key, value) for key, value in zip(summary["key"], summary["late_value"])
    ]
    return summary


def annotate_bar(ax: plt.Axes, y: float, change: float, early_label: str, late_label: str) -> None:
    label = f"{change:+.1f}%  ({early_label} -> {late_label})"
    if change >= 0:
        ax.text(change + 1.2, y, label, ha="left", va="center", fontsize=8, color="#333333")
    else:
        ax.text(1.2, y, label, ha="left", va="center", fontsize=8, color="#333333")


def plot_summary_panel(
    ax: plt.Axes,
    summary: pd.DataFrame,
    title: str,
    max_abs: float,
) -> None:
    y_positions = np.arange(len(summary), dtype=float)
    summary = summary.copy()
    summary["y"] = y_positions

    ax.set_xlim(-max_abs - 18.0, max_abs + 38.0)
    ax.set_ylim(-0.42, len(summary) - 0.58)
    ax.axvline(0.0, color="#666666", linewidth=0.8, linestyle=(0, (2, 2)), zorder=0)

    for row in summary.itertuples(index=False):
        y = float(row.y)
        change = float(row.relative_change_pct)
        ax.barh(y, change, height=0.42, color=str(row.color), edgecolor="none")
        annotate_bar(ax, y, change, str(row.early_label), str(row.late_label))

    ax.set_title(title)
    ax.set_yticks(y_positions)
    ax.set_yticklabels(summary["metric"])
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(mticker.MultipleLocator(20))
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=100, decimals=0))
    ax.grid(axis="x", color="#D0D0D0", alpha=0.5, linewidth=0.7)
    ax.set_axisbelow(True)


def plot(
    summary: pd.DataFrame,
    out: Path,
    baseline_label: str,
    comparison_label: str,
    baseline_short: str,
    comparison_short: str,
) -> None:
    thesis_style()
    fig_height = max(2.65, 0.28 * len(summary) + 0.55)
    fig, ax = plt.subplots(figsize=(6.6, fig_height))
    max_abs = max(5.0, float(summary["relative_change_pct"].abs().max()))
    plot_summary_panel(
        ax,
        summary,
        f"Trajectory-effort changes from {baseline_label} to {comparison_label}",
        max_abs,
    )
    ax.set_xlabel(f"Median change from {baseline_short} to {comparison_short}")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def print_summary(
    summary: pd.DataFrame,
    periods: dict[str, pd.DataFrame],
    out: Path,
    baseline_version: str,
    comparison_version: str,
    baseline_label: str,
    comparison_label: str,
) -> None:
    print(f"Benchmark-version comparison: {baseline_label} versus {comparison_label}.")
    for name, label in [("early", baseline_label), ("late", comparison_label)]:
        subset = periods[name]
        print(f"{label}: {subset.shape[0]} trajectories")
    print("Duration field: duration_seconds (benchmark-reported; no timestamp reconstruction).")
    print("Missing values are handled per metric via valid/non-missing observations.")
    print("")
    print(f"Metric,{baseline_version},{comparison_version},{baseline_version}_valid_n,{comparison_version}_valid_n,relative_change_pct")
    for row in summary.itertuples(index=False):
        print(
            f"{row.metric},{row.early_label},{row.late_label},"
            f"{row.early_valid_n},{row.late_valid_n},{row.relative_change_pct:+.1f}%"
        )
    print("")
    print("Aggregation: per-version medians over all trajectories with non-missing values for each metric.")
    print(f"Wrote figure to {out}")


def main() -> None:
    args = parse_args()
    baseline_version = str(args.baseline_version)
    comparison_version = str(args.comparison_version)
    baseline_label = args.baseline_label or full_version_label(baseline_version)
    comparison_label = args.comparison_label or full_version_label(comparison_version)
    baseline_short = version_display_label(baseline_version)
    comparison_short = version_display_label(comparison_version)
    trajectories = load_trajectories(args.trajectory_csv)
    summary, periods = summarize_periods(trajectories, baseline_version, comparison_version)
    summary = add_formatted_columns(summary)
    unchanged_tasks = load_instruction_unchanged_tasks(args)
    task_balanced_summary = build_task_balanced_outputs(
        trajectories,
        unchanged_tasks,
        baseline_version,
        comparison_version,
    )
    args.pooled_summary_csv.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.pooled_summary_csv, index=False)
    task_balanced_summary.to_csv(args.task_balanced_summary_csv, index=False)
    plot(summary, args.out, baseline_label, comparison_label, baseline_short, comparison_short)
    if args.include_tb3_tb4:
        tb3_tb4_trajectories = load_trajectories(args.tb3_tb4_trajectory_csv)
        tb3_tb4_summary, _ = summarize_periods(tb3_tb4_trajectories, "3.0", "4.0")
        tb3_tb4_summary = add_formatted_columns(tb3_tb4_summary)
        plot(
            tb3_tb4_summary,
            args.tb3_tb4_out,
            "Terminal-Bench 3.0",
            "Terminal-Bench 4.0",
            "TB3.0",
            "TB4.0",
        )
    print_summary(
        summary,
        periods,
        args.out,
        baseline_version,
        comparison_version,
        baseline_label,
        comparison_label,
    )
    print(f"Wrote {args.pooled_summary_csv}")
    print(f"Wrote {args.task_balanced_summary_csv}")
    if args.include_tb3_tb4:
        print(f"Wrote TB3.0/TB4.0 figure to {args.tb3_tb4_out}")


if __name__ == "__main__":
    main()
