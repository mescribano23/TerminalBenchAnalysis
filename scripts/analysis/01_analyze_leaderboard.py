#!/usr/bin/env python3
"""Describe Terminal-Bench leaderboard accuracy and trajectory coverage.

This pass intentionally stays close to leaderboard-level metrics:
- submission accuracy
- task-level accuracy variance within each submission
- passed trials / total trials
- accuracy variation among rows sharing a scaffold
- accuracy variation among rows sharing a model
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.analysis.plot_style import FAIL_COLOR, PASS_COLOR, thesis_style, paper_axis_labels, save_paper_figure
from scripts.benchmark_paths import SUPPORTED_BENCHMARKS, paths_for_benchmark


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_PROCESSED_LIVE_DIR = REPO_ROOT / "data" / "processed_live"
REPORTS_DIR = REPO_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "general_characteristics" / "terminal_bench_2_0"
INPUT_DEFAULT = DATA_PROCESSED_LIVE_DIR / "terminal_bench_2_0" / "leaderboard_submission_summary.csv"
OUT_DEFAULT = DATA_PROCESSED_LIVE_DIR / "terminal_bench_2_0"

INT_FIELDS = (
    "computed_submission_success_count",
    "computed_submission_trial_count",
)

FLOAT_FIELDS = (
    "leaderboard_accuracy",
    "leaderboard_stderr",
    "computed_submission_task_rate_variance",
)


def parse_float(value: Any) -> float | None:
    if value in {"", None}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    if value in {"", None}:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def sample_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))


def split_multi(value: str) -> list[str]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    return parts or [value.strip()]


def row_label(row: dict[str, Any]) -> str:
    version = row.get("scaffold_version") or "unknown"
    return f"{row.get('scaffold', '')} {version} / {row.get('leaderboard_model', '')}"


def representative_display_name(items: list[dict[str, Any]], key: str) -> str:
    if key == "scaffold":
        field = "leaderboard_agent_display_name"
    else:
        field = "leaderboard_model_display"

    names = sorted(
        {
            str(row.get(field, "")).strip()
            for row in items
            if str(row.get(field, "")).strip()
        }
    )
    return ", ".join(names)


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        raw_rows = list(csv.DictReader(f))

    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        row = dict(raw)
        row["leaderboard_rank"] = parse_int(row.get("leaderboard_rank"))
        row["has_trajectories"] = str(row.get("has_trajectories", "")).lower() == "true"
        for key in INT_FIELDS:
            row[key] = parse_int(row.get(key))
        for key in FLOAT_FIELDS:
            row[key] = parse_float(row.get(key))
        leaderboard_accuracy = row.get("leaderboard_accuracy")
        leaderboard_stderr = row.get("leaderboard_stderr")
        row["analysis_accuracy_percent"] = (
            leaderboard_accuracy * 100.0
            if leaderboard_accuracy is not None
            else None
        )
        row["analysis_pm_percent"] = (
            leaderboard_stderr * 1.96 * 100.0
            if leaderboard_stderr is not None
            else None
        )
        row["analysis_task_rate_variance"] = row.get("computed_submission_task_rate_variance")
        rows.append(row)
    return rows


def group_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, ""))].append(row)

    summaries: list[dict[str, Any]] = []
    for value, items in grouped.items():
        accuracies = [
            float(row["analysis_accuracy_percent"])
            for row in items
            if row.get("analysis_accuracy_percent") is not None
        ]
        variances = [
            float(row["analysis_task_rate_variance"])
            for row in items
            if row.get("analysis_task_rate_variance") is not None
        ]
        total_successes = sum(int(row.get("computed_submission_success_count") or 0) for row in items)
        total_trials = sum(int(row.get("computed_submission_trial_count") or 0) for row in items)
        best = max(items, key=lambda row: row.get("analysis_accuracy_percent") or -1)
        worst = min(items, key=lambda row: row.get("analysis_accuracy_percent") or 101)
        distinct_scaffolds = sorted({str(row.get("scaffold", "")) for row in items})
        distinct_models = sorted({str(row.get("leaderboard_model", "")) for row in items})
        summary = {
            key: value,
            "display_name": representative_display_name(items, key),
            "row_count": len(items),
            "distinct_scaffold_count": len(distinct_scaffolds),
            "distinct_model_count": len(distinct_models),
            "has_trajectories_rows": sum(1 for row in items if row.get("has_trajectories")),
            "success_count": total_successes,
            "trial_count": total_trials,
            "weighted_accuracy_percent": (total_successes / total_trials * 100.0) if total_trials else None,
            "mean_accuracy_percent": mean(accuracies) if accuracies else None,
            "median_accuracy_percent": median(accuracies) if accuracies else None,
            "min_accuracy_percent": min(accuracies) if accuracies else None,
            "max_accuracy_percent": max(accuracies) if accuracies else None,
            "accuracy_range_percent": (max(accuracies) - min(accuracies)) if accuracies else None,
            "accuracy_std_percent": sample_std(accuracies),
            "mean_task_rate_variance": mean(variances) if variances else None,
            "best_rank": best.get("leaderboard_rank"),
            "best_accuracy_percent": best.get("analysis_accuracy_percent"),
            "best_row": row_label(best),
            "worst_rank": worst.get("leaderboard_rank"),
            "worst_accuracy_percent": worst.get("analysis_accuracy_percent"),
            "worst_row": row_label(worst),
        }
        summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            -(item.get("accuracy_range_percent") or 0.0),
            -(item.get("row_count") or 0),
            str(item.get(key, "")),
        )
    )
    return summaries


def exploded_model_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exploded: list[dict[str, Any]] = []
    for row in rows:
        for model in split_multi(str(row.get("leaderboard_model", ""))):
            item = dict(row)
            item["model_component"] = model
            exploded.append(item)
    return exploded


def grouped_accuracy_values(rows: list[dict[str, Any]], key: str, groups: list[dict[str, Any]], limit: int) -> list[tuple[str, list[float]]]:
    selected_keys = [str(group.get(key, "")) for group in groups if (group.get("row_count") or 0) >= 2][:limit]
    grouped: dict[str, list[float]] = {value: [] for value in selected_keys}
    for row in rows:
        value = str(row.get(key, ""))
        if value not in grouped or row.get("analysis_accuracy_percent") is None:
            continue
        grouped[value].append(float(row["analysis_accuracy_percent"]))
    return [(value, grouped[value]) for value in selected_keys if grouped[value]]


def order_groups_by_leaderboard_rank(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        groups,
        key=lambda group: (
            int(group.get("best_rank") or 999999),
            str(group.get("scaffold") or group.get("model_component") or group.get("leaderboard_model") or ""),
        ),
    )


def plot_violin_box(
    grouped_values: list[tuple[str, list[float]]],
    title: str,
    ylabel: str,
    path: Path,
) -> Path | None:
    if not grouped_values:
        return None

    labels = [f"{label}\n(n={len(values)})" for label, values in grouped_values]
    values = [group_values for _, group_values in grouped_values]
    width = max(10.5, min(18.0, 3.2 + len(values) * 0.62))
    fig, ax = plt.subplots(figsize=(width, 6.05))

    parts = ax.violinplot(values, vert=True, showmeans=False, showmedians=False, showextrema=False)
    for body in parts["bodies"]:
        body.set_facecolor(PASS_COLOR)
        body.set_edgecolor(PASS_COLOR)
        body.set_alpha(0.45)

    ax.boxplot(
        values,
        vert=True,
        widths=0.22,
        patch_artist=True,
        showfliers=False,
        boxprops={"facecolor": "#ffffff", "edgecolor": "#243b4a", "linewidth": 1.1},
        medianprops={"color": FAIL_COLOR, "linewidth": 1.6},
        whiskerprops={"color": "#243b4a", "linewidth": 1.0},
        capprops={"color": "#243b4a", "linewidth": 1.0},
    )

    rng = np.random.default_rng(7)
    for position, group_values in enumerate(values, start=1):
        jitter = rng.normal(0, 0.035, len(group_values))
        ax.scatter(
            np.full(len(group_values), position) + jitter,
            group_values,
            s=16,
            color="#1f2d3a",
            alpha=0.65,
            linewidths=0,
        )

    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, fontsize=9.5, rotation=45, ha="right")
    ax.set_ylim(0, 100)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Groups ordered by best leaderboard rank")
    ax.grid(axis="y", alpha=0.25)
    paper_axis_labels(fig)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    save_paper_figure(fig, path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_leaderboard_figures(
    rows: list[dict[str, Any]],
    scaffold_groups: list[dict[str, Any]],
    exploded_rows: list[dict[str, Any]],
    exploded_model_groups: list[dict[str, Any]],
    figures_dir: Path,
) -> list[Path]:
    figures: list[Path] = []

    scaffold_values = grouped_accuracy_values(rows, "scaffold", order_groups_by_leaderboard_rank(scaffold_groups), limit=20)
    scaffold_plot = plot_violin_box(
        scaffold_values,
        "Leaderboard accuracy by scaffold",
        "Official leaderboard accuracy (%)",
        figures_dir / "leaderboard_accuracy_by_scaffold.png",
    )
    if scaffold_plot is not None:
        figures.append(scaffold_plot)

    model_values = grouped_accuracy_values(
        exploded_rows,
        "model_component",
        order_groups_by_leaderboard_rank(exploded_model_groups),
        limit=20,
    )
    model_plot = plot_violin_box(
        model_values,
        "Leaderboard accuracy by model component",
        "Official leaderboard accuracy (%)",
        figures_dir / "leaderboard_accuracy_by_model_component.png",
    )
    if model_plot is not None:
        figures.append(model_plot)

    return figures


def summarize_availability(rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    df["availability_group"] = np.where(df["has_trajectories"], "trajectory_available", "trajectory_unavailable")
    df["leaderboard_date_parsed"] = pd.to_datetime(df["leaderboard_date"], errors="coerce")
    by_group = (
        df.groupby("availability_group", as_index=False)
        .agg(
            submission_count=("availability_group", "size"),
            median_leaderboard_accuracy=("leaderboard_accuracy", "median"),
            mean_leaderboard_accuracy=("leaderboard_accuracy", "mean"),
            min_leaderboard_accuracy=("leaderboard_accuracy", "min"),
            max_leaderboard_accuracy=("leaderboard_accuracy", "max"),
            median_trial_count=("computed_submission_trial_count", "median"),
            min_trial_count=("computed_submission_trial_count", "min"),
            max_trial_count=("computed_submission_trial_count", "max"),
            median_success_count=("computed_submission_success_count", "median"),
            first_submission_date=("leaderboard_date_parsed", "min"),
            median_submission_date=("leaderboard_date_parsed", "median"),
            last_submission_date=("leaderboard_date_parsed", "max"),
        )
        .sort_values("availability_group")
    )
    for column in ["first_submission_date", "median_submission_date", "last_submission_date"]:
        by_group[column] = by_group[column].dt.date.astype("string")

    def grouped(column: str) -> pd.DataFrame:
        out = (
            df.groupby(column, dropna=False)
            .agg(
                submission_count=(column, "size"),
                trajectory_available_count=("has_trajectories", "sum"),
                median_leaderboard_accuracy=("leaderboard_accuracy", "median"),
            )
            .reset_index()
        )
        out["trajectory_unavailable_count"] = out["submission_count"] - out["trajectory_available_count"]
        out["trajectory_available_fraction"] = out["trajectory_available_count"] / out["submission_count"]
        return out.sort_values(["submission_count", "trajectory_available_count", column], ascending=[False, False, True])

    return by_group, grouped("scaffold"), grouped("leaderboard_model")


def main() -> None:
    thesis_style()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmark",
        choices=SUPPORTED_BENCHMARKS,
        default=None,
        help=(
            "Resolve input/out/figure paths for a benchmark. Omit to use "
            "the Terminal-Bench 2.0 defaults."
        ),
    )
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--figures-dir", type=Path, default=None)
    args = parser.parse_args()

    benchmark_paths = (
        paths_for_benchmark(REPO_ROOT, args.benchmark)
        if args.benchmark is not None
        else None
    )
    input_path = (
        args.input
        or (
            benchmark_paths.processed_dir / "leaderboard_submission_summary.csv"
            if benchmark_paths
            else INPUT_DEFAULT
        )
    )
    out = args.out or (benchmark_paths.processed_dir if benchmark_paths else OUT_DEFAULT)
    figures_dir = args.figures_dir or (
        benchmark_paths.figures_dir if benchmark_paths else FIGURES_DIR
    )

    rows = load_rows(input_path)
    out.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    scaffold_groups = group_rows(rows, "scaffold")
    exploded_rows = exploded_model_rows(rows)
    exploded_model_groups = group_rows(exploded_rows, "model_component")

    plot_leaderboard_figures(
        rows,
        scaffold_groups,
        exploded_rows,
        exploded_model_groups,
        figures_dir,
    )
    availability_summary, availability_by_scaffold, availability_by_model = summarize_availability(rows)
    for frame, name in [
        (availability_summary, "leaderboard_trajectory_availability_summary.csv"),
        (availability_by_scaffold, "leaderboard_trajectory_availability_by_scaffold.csv"),
        (availability_by_model, "leaderboard_trajectory_availability_by_model.csv"),
    ]:
        path = out / name
        frame.to_csv(path, index=False)
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
