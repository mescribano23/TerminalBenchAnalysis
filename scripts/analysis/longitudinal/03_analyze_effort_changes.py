#!/usr/bin/env python3
"""Analyze benchmark-version trajectory-effort changes for RQ3.3.

This script compares two Terminal-Bench versions' trajectory effort on a
longitudinal dataset. The default TB2.0/TB2.1 figure establishes the RQ3.3 token anomaly:
observable trajectory-effort measures generally decrease or grow modestly,
while reported token usage increases more strongly.
"""

from __future__ import annotations

import argparse
import json
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
from scripts.analysis.submission_task_balancing import (
    EFFECTIVE_SUBMISSION_COMPONENTS,
    EFFECTIVE_SUBMISSION_ID,
    ensure_effective_submission_id,
)
from scripts.analysis.statistical_helpers import paired_cohens_dz, two_sided_signed_rank
from scripts.benchmark_paths import find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
LONGITUDINAL_DIR = REPO_ROOT / "data" / "processed_live" / "longitudinal"
TRAJECTORY_CSV = LONGITUDINAL_DIR / "trajectory_longitudinal.csv"
TB3_TB4_TRAJECTORY_CSV = LONGITUDINAL_DIR / "tb3_tb4" / "trajectory_longitudinal.csv"
TASK_AUDIT_CSV = LONGITUDINAL_DIR / "task_version_audit.csv"
TASK_CHANGES_CSV = LONGITUDINAL_DIR / "task_composition" / "adjacent_version_task_changes.csv"
FIGURE_DIR = REPO_ROOT / "reports" / "longitudinal"
BASELINE_FIGURE_PATH = FIGURE_DIR / "effort_change_pooled_refreshed_tb2_0_to_tb2_1.png"
TB3_TB4_FIGURE_PATH = FIGURE_DIR / "effort_change_pooled_refreshed_tb3_0_to_tb4_0.png"
POOLED_SUMMARY_CSV = LONGITUDINAL_DIR / "pooled_effort_summary_refreshed.csv"
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
TOKEN_COLUMNS = {"prompt_tokens", "completion_tokens", "total_tokens"}


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
    parser.add_argument("--tb3-tb4-pooled-summary-csv", type=Path,
                        default=LONGITUDINAL_DIR / "tb3_tb4" / "pooled_effort_summary_refreshed.csv")
    parser.add_argument("--tb3-tb4-task-balanced-summary-csv", type=Path,
                        default=LONGITUDINAL_DIR / "tb3_tb4" / "task_balanced_effort_summary.csv")
    parser.add_argument(
        "--task-weighting",
        choices=["submission-balanced", "trial-weighted"],
        default="submission-balanced",
        help=(
            "Task comparison aggregation: median within each submission/task/version, "
            "then across submissions (default), or median across all trials per task/version. "
            "Pooled summaries and figures always use trajectory-level medians."
        ),
    )
    parser.add_argument("--out", type=Path, default=BASELINE_FIGURE_PATH)
    parser.add_argument(
        "--submission-unit", choices=["effective", "leaderboard-url"], default="effective",
        help="Effective submission IDs are primary; leaderboard URLs are an explicit sensitivity analysis.",
    )
    parser.add_argument("--tb3-tb4-out", type=Path, default=TB3_TB4_FIGURE_PATH)
    parser.add_argument("--combined-out", type=Path, default=None,
                        help="Optionally also write the preserved combined TB2/TB3 comparison figure.")
    parser.add_argument("--include-sensitivities", action="store_true",
                        help="Also export URL-grouped and trial-weighted tables and paired URL/effective tests.")
    parser.add_argument("--output-root", type=Path,
                        help="Mirror default output paths under this directory for reproduction checks.")
    args = parser.parse_args()
    if args.include_sensitivities and (args.task_weighting != "submission-balanced" or args.submission_unit != "effective"):
        parser.error("--include-sensitivities requires the primary submission-balanced/effective settings.")
    if args.output_root is not None:
        args.output_root = args.output_root.resolve()
        if args.output_root.is_relative_to(REPO_ROOT / "data" / "trajectories"):
            parser.error("Output root must be outside raw trajectories.")
        for name in ("out", "tb3_tb4_out", "pooled_summary_csv", "task_balanced_summary_csv",
                     "tb3_tb4_pooled_summary_csv", "tb3_tb4_task_balanced_summary_csv"):
            if getattr(args, name) == parser.get_default(name):
                setattr(args, name, args.output_root / getattr(args, name).relative_to(REPO_ROOT))
    return args


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


def load_trajectories(
    path: Path, *, task_weighting: str = "submission-balanced", submission_unit: str = "effective"
) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    retained_columns = REQUIRED_COLUMNS | set(EFFECTIVE_SUBMISSION_COMPONENTS) | {EFFECTIVE_SUBMISSION_ID}
    df = df[[column for column in sorted(retained_columns) if column in df.columns]].copy()
    required = REQUIRED_COLUMNS if task_weighting == "submission-balanced" else REQUIRED_COLUMNS - {"submission_id"}
    require_columns(df, required, str(path))
    df = df.copy()
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    for column in REQUIRED_COLUMNS.difference({"benchmark_version", "submission_id", "task_name"}):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    for column in TOKEN_COLUMNS:
        df.loc[df[column] <= 0, column] = np.nan
    if task_weighting == "submission-balanced" and submission_unit == "effective":
        df = ensure_effective_submission_id(df)
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
    *,
    task_weighting: str = "submission-balanced",
    submission_unit: str = "effective",
) -> pd.DataFrame:
    summary_rows: list[dict[str, object]] = []
    for metric in METRICS:
        column = str(metric["column"])
        medians = task_metric_pairs(df, column, task_weighting=task_weighting, submission_unit=submission_unit)
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
                    "task_weighting": task_weighting,
                    "submission_unit": submission_unit if task_weighting == "submission-balanced" else "all-trials",
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


def task_metric_pairs(
    df: pd.DataFrame, column: str, *, task_weighting: str = "submission-balanced", submission_unit: str = "effective"
) -> pd.DataFrame:
    """Return explicitly weighted task medians, with versions as columns.

    Submission balancing gives each submission equal weight within a task.
    Trial weighting preserves the original median across all trials, allowing
    submissions with more repeated trials to contribute more observations.
    """
    if task_weighting == "trial-weighted":
        return (
            df[["task_name", "benchmark_version", column]]
            .dropna()
            .groupby(["task_name", "benchmark_version"])[column]
            .median()
            .unstack()
        )
    if task_weighting != "submission-balanced":
        raise ValueError(f"Unknown task weighting: {task_weighting}")
    if submission_unit == "effective":
        if EFFECTIVE_SUBMISSION_ID not in df:
            df = ensure_effective_submission_id(df)
        identity = EFFECTIVE_SUBMISSION_ID
    elif submission_unit == "leaderboard-url":
        identity = "submission_id"
    else:
        raise ValueError(f"Unknown submission unit: {submission_unit}")
    work = df[[identity, "task_name", "benchmark_version", column]].dropna().copy()
    if work[identity].astype(str).str.strip().eq("").any():
        raise ValueError(f"Metric {column!r} has rows with empty {identity} values.")
    submission_task = (
        work.groupby([identity, "task_name", "benchmark_version"], as_index=False)[column]
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
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def summarize_task_balanced_periods(
    df: pd.DataFrame, baseline_version: str, comparison_version: str,
    *, submission_unit: str = "effective",
) -> pd.DataFrame:
    """Describe matched tasks after submission-task and across-submission medians.

    The figure percentage is the ratio of cross-task medians. Paired absolute
    and relative changes are separate columns; tests use the absolute changes.
    """
    rows = []
    for metric in METRICS:
        pairs = task_metric_pairs(df, metric["column"], submission_unit=submission_unit)
        pairs = pairs.dropna(subset=[baseline_version, comparison_version])
        early, late = pairs[baseline_version], pairs[comparison_version]
        relative = ((late / early.where(early.ne(0))) - 1) * 100
        early_value, late_value = float(early.median()), float(late.median())
        rows.append({
            "key": metric["key"], "metric": metric["label"], "column": metric["column"],
            "aggregation": "median across matched task medians after submission balancing",
            "task_weighting": "submission-balanced", "submission_unit": submission_unit,
            "early_value": early_value, "late_value": late_value,
            "early_valid_n": len(pairs), "late_valid_n": len(pairs),
            "early_relative": 1.0, "late_relative": late_value / early_value if early_value else np.nan,
            "relative_change_pct": (late_value / early_value - 1) * 100 if early_value else np.nan,
            "median_paired_change": float((late - early).median()),
            "median_paired_relative_change_pct": float(relative.median()),
            "relative_valid_task_pairs": int(relative.notna().sum()),
            "color": metric["color"],
        })
    return pd.DataFrame(rows)


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
    *, aggregation_label: str = "Pooled trajectories (descriptive)",
) -> None:
    thesis_style()
    fig_height = max(2.65, 0.28 * len(summary) + 0.55)
    fig, ax = plt.subplots(figsize=(6.6, fig_height))
    max_abs = max(5.0, float(summary["relative_change_pct"].abs().max()))
    plot_summary_panel(
        ax,
        summary,
        f"{baseline_short} to {comparison_short}: {aggregation_label}",
        max_abs,
    )
    ax.set_xlabel("Change in median (%)")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_combined(comparisons: list[dict[str, object]], out: Path) -> None:
    thesis_style()
    max_abs = max(
        5.0,
        max(float(comparison["summary"]["relative_change_pct"].abs().max()) for comparison in comparisons),
    )
    fig_height = max(5.6, 0.28 * len(METRICS) * len(comparisons) + 1.45)
    fig, axes = plt.subplots(len(comparisons), 1, figsize=(7.2, fig_height), sharex=True)
    if len(comparisons) == 1:
        axes = [axes]

    for ax, comparison in zip(axes, comparisons):
        plot_summary_panel(
            ax,
            comparison["summary"],
            str(comparison["title"]),
            max_abs,
        )
    axes[-1].set_xlabel("Median change within comparison")
    fig.suptitle("Trajectory-Effort Changes Across Benchmark Version Pairs", y=1.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(h_pad=1.0)
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


def write_balanced_exports(
    trajectories: pd.DataFrame, unchanged_tasks: set[str], old: str, new: str,
    table_dir: Path, figure_dir: Path, pooled_figure: Path, *, include_sensitivities: bool,
    output_root: Path | None,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    """Export shared-task figure data, paired vectors, sensitivities and captions.

    Uses the same aggregation functions as the primary task table. The five
    existing inferential metrics remain distinct from eight plotted summaries.
    """
    inference: list[dict[str, object]] = []
    captions: list[dict[str, str]] = []
    stem = f"tb{old.replace('.', '_')}_to_tb{new.replace('.', '_')}"
    primary_metrics = {"steps", "shell_invocations", "tool_calls", "duration", "total_tokens"}

    def caption_path(path: Path) -> str:
        for base in (output_root, REPO_ROOT):
            if base is not None and path.is_relative_to(base):
                return path.relative_to(base).as_posix()
        return path.as_posix()

    units = ["effective", "leaderboard-url"] if include_sensitivities else ["effective"]
    for unit in units:
        if unit == "leaderboard-url":
            build_task_balanced_outputs(
                trajectories, unchanged_tasks, old, new, submission_unit=unit,
            ).to_csv(table_dir / "task_balanced_effort_summary_url_sensitivity.csv", index=False)
        figures = summarize_task_balanced_periods(trajectories, old, new, submission_unit=unit)
        figures.to_csv(table_dir / f"effort_figure_data_submission_balanced_{unit}.csv", index=False)
        detail = []
        for metric in METRICS:
            pairs = task_metric_pairs(trajectories, metric["column"], submission_unit=unit).dropna(subset=[old, new])
            differences = pairs[new] - pairs[old]
            relative = (pairs[new] / pairs[old].where(pairs[old].ne(0)) - 1) * 100
            for task, row in pairs.iterrows():
                detail.append({
                    "transition": old + "->" + new, "metric": metric["key"], "task_name": task,
                    "submission_unit": unit, "old_value": row[old], "new_value": row[new],
                    "paired_difference": row[new] - row[old], "paired_relative_change_pct": relative.loc[task],
                })
            if include_sensitivities and metric["key"] in primary_metrics:
                statistic, p_value, nonzero = two_sided_signed_rank(differences)
                inference.append({
                    "transition": old + "->" + new, "metric": metric["key"],
                    "task_weighting": "submission-balanced", "submission_unit": unit,
                    "eligible_tasks": len(pairs), "mean_paired_task_difference": differences.mean(),
                    "median_paired_task_difference": differences.median(),
                    "cohens_dz": paired_cohens_dz(differences), "wilcoxon_statistic": statistic,
                    "p_value": p_value, "nonzero_task_pairs": nonzero,
                })
        pd.DataFrame(detail).to_csv(table_dir / f"paired_effort_tasks_{unit}.csv", index=False)
        if unit == "effective":
            path = figure_dir / f"effort_change_submission_balanced_{stem}.png"
            plot(add_formatted_columns(figures), path, "TB" + old, "TB" + new, "TB" + old, "TB" + new,
                 aggregation_label="Effective submissions, shared tasks")
            captions.append({"path": caption_path(path), "caption": f"TB{old} to TB{new}: medians within effective submission-task pairs, then medians across submissions within tasks, then medians across matched tasks. Bars show the ratio of cross-task medians; paired absolute changes determine inference. Metric-specific missing pairs are excluded. Eight descriptive metrics are plotted; five pre-existing primary metrics are tested."})
    if include_sensitivities:
        build_task_balanced_outputs(
            trajectories, unchanged_tasks, old, new, task_weighting="trial-weighted",
        ).to_csv(table_dir / "task_balanced_effort_summary_trial_weighted_sensitivity.csv", index=False)
    captions.append({"path": caption_path(pooled_figure), "caption": f"Refreshed descriptive trajectory medians for all retained TB{old}/TB{new} records, including unpaired task pools. Uses complete logged text and positive reported token values. Not submission-balanced; no task-level significance is implied. Historical pooled figures remain unchanged."})
    return inference, captions


def main() -> None:
    args = parse_args()
    baseline_version = str(args.baseline_version)
    comparison_version = str(args.comparison_version)
    baseline_label = args.baseline_label or full_version_label(baseline_version)
    comparison_label = args.comparison_label or full_version_label(comparison_version)
    baseline_short = version_display_label(baseline_version)
    comparison_short = version_display_label(comparison_version)
    trajectories = load_trajectories(args.trajectory_csv, task_weighting=args.task_weighting, submission_unit=args.submission_unit)
    summary, periods = summarize_periods(trajectories, baseline_version, comparison_version)
    summary["aggregation_scope"] = "all retained trajectories; descriptive"
    summary = add_formatted_columns(summary)
    unchanged_tasks = load_instruction_unchanged_tasks(args)
    task_balanced_summary = build_task_balanced_outputs(
        trajectories,
        unchanged_tasks,
        baseline_version,
        comparison_version,
        task_weighting=args.task_weighting,
        submission_unit=args.submission_unit,
    )
    args.pooled_summary_csv.parent.mkdir(parents=True, exist_ok=True)
    args.task_balanced_summary_csv.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.pooled_summary_csv, index=False)
    task_balanced_summary.to_csv(args.task_balanced_summary_csv, index=False)
    plot(summary, args.out, baseline_label, comparison_label, baseline_short, comparison_short)
    exports = [(trajectories, unchanged_tasks, baseline_version, comparison_version,
                args.task_balanced_summary_csv.parent, args.out.parent, args.out)]
    if args.include_tb3_tb4:
        tb3_tb4_trajectories = load_trajectories(args.tb3_tb4_trajectory_csv, task_weighting=args.task_weighting, submission_unit=args.submission_unit)
        tb3_tb4_summary, _ = summarize_periods(tb3_tb4_trajectories, "3.0", "4.0")
        tb3_tb4_summary["aggregation_scope"] = "all retained trajectories; descriptive"
        tb3_tb4_summary = add_formatted_columns(tb3_tb4_summary)
        tb3_tb4_tasks = build_task_balanced_outputs(
            tb3_tb4_trajectories,
            load_adjacent_instruction_unchanged_tasks(args.task_changes_csv, "3.0", "4.0"),
            "3.0", "4.0", task_weighting=args.task_weighting, submission_unit=args.submission_unit,
        )
        for path, table in [(args.tb3_tb4_pooled_summary_csv, tb3_tb4_summary),
                            (args.tb3_tb4_task_balanced_summary_csv, tb3_tb4_tasks)]:
            path.parent.mkdir(parents=True, exist_ok=True)
            table.to_csv(path, index=False)
        exports.append((tb3_tb4_trajectories,
                        load_adjacent_instruction_unchanged_tasks(args.task_changes_csv, "3.0", "4.0"),
                        "3.0", "4.0", args.tb3_tb4_task_balanced_summary_csv.parent,
                        args.tb3_tb4_out.parent, args.tb3_tb4_out))
        plot(
            tb3_tb4_summary,
            args.tb3_tb4_out,
            "Terminal-Bench 3.0",
            "Terminal-Bench 4.0",
            "TB3.0",
            "TB4.0",
        )
        if args.combined_out is not None:
            plot_combined(
                [
                    {"summary": summary, "title": f"{baseline_label} to {comparison_label}"},
                    {"summary": tb3_tb4_summary, "title": "Terminal-Bench 3.0 to Terminal-Bench 4.0"},
                ],
                args.combined_out,
            )
    if args.task_weighting == "submission-balanced" and args.submission_unit == "effective":
        inference, captions = [], []
        for export in exports:
            rows, descriptions = write_balanced_exports(
                *export, include_sensitivities=args.include_sensitivities, output_root=args.output_root,
            )
            inference.extend(rows)
            captions.extend(descriptions)
        if args.include_sensitivities:
            pd.DataFrame(inference).to_csv(
                args.task_balanced_summary_csv.parent / "rq3_3_submission_unit_sensitivity_inference.csv", index=False,
            )
        caption_file = args.out.parent / "effort_figure_captions.json"
        caption_file.parent.mkdir(parents=True, exist_ok=True)
        caption_file.write_text(json.dumps(captions, indent=2) + "\n", encoding="utf-8")
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
    print(f"Task comparison weighting: {args.task_weighting}")
    print(f"Submission unit: {args.submission_unit}")
    if args.include_tb3_tb4:
        print(f"Wrote TB3.0/TB4.0 figure to {args.tb3_tb4_out}")


if __name__ == "__main__":
    main()
