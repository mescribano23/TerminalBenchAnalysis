#!/usr/bin/env python3
"""Plot benchmark-version trajectory-effort changes for RQ3.

This script compares Terminal-Bench 2.0 and 2.1 trajectory effort on the
unified longitudinal dataset. The figure establishes the RQ3 token anomaly:
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

from scripts.benchmark_paths import find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
LONGITUDINAL_DIR = REPO_ROOT / "data" / "processed_live" / "longitudinal"
TRAJECTORY_CSV = LONGITUDINAL_DIR / "trajectory_longitudinal.csv"
FIGURE_PATH = REPO_ROOT / "reports" / "longitudinal" / "performance_effort_change_over_time.png"

BASELINE_LABEL = "Terminal-Bench 2.0"
COMPARISON_LABEL = "Terminal-Bench 2.1"
BASELINE_VERSION = "2.0"
COMPARISON_VERSION = "2.1"

REQUIRED_COLUMNS = {
    "benchmark_version",
    "step_count",
    "command_count",
    "tool_call_count",
    "duration_seconds",
    "message_chars",
    "reasoning_chars",
    "observation_chars",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
}

EFFORT_COLOR = "#595959"
TEXT_COLOR = "#4F7D5A"
INPUT_TOKEN_COLOR = "#2F6FAD"
OUTPUT_TOKEN_COLOR = "#9A7A24"
TOTAL_TOKEN_COLOR = "#7A4D7E"


METRICS = [
    {
        "key": "steps",
        "label": "Steps",
        "column": "step_count",
        "aggregation": "median",
        "color": EFFORT_COLOR,
    },
    {
        "key": "commands",
        "label": "Commands",
        "column": "command_count",
        "aggregation": "median",
        "color": EFFORT_COLOR,
    },
    {
        "key": "tool_calls",
        "label": "Tool calls",
        "column": "tool_call_count",
        "aggregation": "median",
        "color": EFFORT_COLOR,
    },
    # duration_seconds is the existing benchmark-reported duration field in
    # the longitudinal dataset, not a reconstruction from trajectory timestamps.
    {
        "key": "duration",
        "label": "Duration",
        "column": "duration_seconds",
        "aggregation": "median",
        "color": EFFORT_COLOR,
    },
    {
        "key": "chars",
        "label": "Logged trajectory characters",
        "column": "logged_chars",
        "aggregation": "median",
        "color": TEXT_COLOR,
    },
    {
        "key": "prompt_tokens",
        "label": "Prompt/input tokens",
        "column": "prompt_tokens",
        "aggregation": "median",
        "color": INPUT_TOKEN_COLOR,
    },
    {
        "key": "completion_tokens",
        "label": "Completion/output tokens",
        "column": "completion_tokens",
        "aggregation": "median",
        "color": OUTPUT_TOKEN_COLOR,
    },
    {
        "key": "total_tokens",
        "label": "Total tokens",
        "column": "total_tokens",
        "aggregation": "median",
        "color": TOTAL_TOKEN_COLOR,
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-csv", type=Path, default=TRAJECTORY_CSV)
    parser.add_argument("--out", type=Path, default=FIGURE_PATH)
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
    df = pd.read_csv(path, usecols=sorted(REQUIRED_COLUMNS), low_memory=False)
    require_columns(df, REQUIRED_COLUMNS, str(path))
    df = df.copy()
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    for column in REQUIRED_COLUMNS.difference({"benchmark_version"}):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["logged_chars"] = df["message_chars"] + df["reasoning_chars"] + df["observation_chars"]
    return df.dropna(subset=["benchmark_version"])


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


def summarize_periods(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    periods = {
        "early": version_subset(df, BASELINE_VERSION),
        "late": version_subset(df, COMPARISON_VERSION),
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
        ax.text(change - 1.2, y, label, ha="right", va="center", fontsize=8, color="#333333")


def plot(summary: pd.DataFrame, out: Path) -> None:
    thesis_style()
    fig_height = max(3.8, 0.48 * len(summary) + 0.9)
    fig, ax = plt.subplots(figsize=(6.6, fig_height))

    y_positions = np.arange(len(summary), dtype=float)
    summary = summary.copy()
    summary["y"] = y_positions

    max_abs = max(5.0, float(summary["relative_change_pct"].abs().max()))
    ax.set_xlim(-max_abs - 18.0, max_abs + 38.0)
    ax.set_ylim(-0.55, len(summary) - 0.45)
    ax.axvline(0.0, color="#666666", linewidth=0.8, linestyle=(0, (2, 2)), zorder=0)

    for row in summary.itertuples(index=False):
        y = float(row.y)
        change = float(row.relative_change_pct)
        ax.barh(y, change, height=0.56, color=str(row.color), edgecolor="none")
        annotate_bar(ax, y, change, str(row.early_label), str(row.late_label))

    ax.set_title("Trajectory-effort changes from Terminal-Bench 2.0 to 2.1")
    ax.set_xlabel("Median change from TB2.0 to TB2.1")
    ax.set_yticks(y_positions)
    ax.set_yticklabels(summary["metric"])
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(mticker.MultipleLocator(20))
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=100, decimals=0))
    ax.grid(axis="x", color="#D0D0D0", alpha=0.5, linewidth=0.7)
    ax.set_axisbelow(True)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def print_summary(summary: pd.DataFrame, periods: dict[str, pd.DataFrame], out: Path) -> None:
    print("Benchmark-version comparison: Terminal-Bench 2.0 versus Terminal-Bench 2.1.")
    for name, label in [("early", BASELINE_LABEL), ("late", COMPARISON_LABEL)]:
        subset = periods[name]
        print(f"{label}: {subset.shape[0]} trajectories")
    print("Duration field: duration_seconds (benchmark-reported; no timestamp reconstruction).")
    print("Missing values are handled per metric via valid/non-missing observations.")
    print("")
    print("Metric,2.0,2.1,2.0_valid_n,2.1_valid_n,relative_change_pct")
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
    trajectories = load_trajectories(args.trajectory_csv)
    summary, periods = summarize_periods(trajectories)
    summary = add_formatted_columns(summary)
    plot(summary, args.out)
    print_summary(summary, periods, args.out)


if __name__ == "__main__":
    main()
