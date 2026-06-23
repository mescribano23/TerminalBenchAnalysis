#!/usr/bin/env python3
"""Superficial Terminal-Bench leaderboard analysis.

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
import io
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
REPORTS_DIR = REPO_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "general_characteristics"
INPUT_DEFAULT = DATA_PROCESSED_DIR / "leaderboard_submission_summary.csv"
OUT_DEFAULT = DATA_PROCESSED_DIR

INT_FIELDS = (
    "computed_submission_task_count",
    "computed_submission_success_count",
    "computed_submission_trial_count",
)

FLOAT_FIELDS = (
    "leaderboard_accuracy",
    "leaderboard_accuracy_percent",
    "leaderboard_stderr",
    "leaderboard_stderr_percent",
    "leaderboard_accuracy_ci95_pm_percent",
    "computed_submission_accuracy",
    "computed_submission_accuracy_percent",
    "computed_submission_weighted_trial_accuracy",
    "computed_submission_weighted_trial_accuracy_percent",
    "computed_submission_task_rate_variance",
    "computed_submission_accuracy_pm_percent",
    "computed_submission_binomial_accuracy_variance",
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
        row["analysis_accuracy_percent"] = row.get("leaderboard_accuracy_percent")
        row["analysis_pm_percent"] = row.get("leaderboard_accuracy_ci95_pm_percent")
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


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    content = buffer.getvalue()
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    try:
        path.write_text(content, encoding="utf-8")
    except PermissionError:
        if path.exists():
            print(f"warning: could not update locked file: {path}", file=sys.stderr)
            return
        raise


def slugify(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "_" for char in value]
    return "_".join("".join(chars).strip("_").split("_")) or "unknown"


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
    fig, ax = plt.subplots(figsize=(width, 6.4))

    parts = ax.violinplot(values, vert=True, showmeans=False, showmedians=False, showextrema=False)
    for body in parts["bodies"]:
        body.set_facecolor("#7aa6c2")
        body.set_edgecolor("#3d5f73")
        body.set_alpha(0.45)

    ax.boxplot(
        values,
        vert=True,
        widths=0.22,
        patch_artist=True,
        showfliers=False,
        boxprops={"facecolor": "#ffffff", "edgecolor": "#243b4a", "linewidth": 1.1},
        medianprops={"color": "#c44e52", "linewidth": 1.6},
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
    ax.set_xticklabels(labels, fontsize=8.0, rotation=45, ha="right")
    ax.set_ylim(0, 100)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Groups ordered by best leaderboard rank")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR)
    args = parser.parse_args()

    rows = load_rows(args.input)
    args.out.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    scaffold_groups = group_rows(rows, "scaffold")
    model_groups = group_rows(rows, "leaderboard_model")
    exploded_rows = exploded_model_rows(rows)
    exploded_model_groups = group_rows(exploded_rows, "model_component")

    write_csv(args.out / "leaderboard_scaffold_variance.csv", scaffold_groups)
    write_csv(args.out / "leaderboard_model_variance.csv", model_groups)
    write_csv(args.out / "leaderboard_model_component_variance.csv", exploded_model_groups)

    plot_leaderboard_figures(
        rows,
        scaffold_groups,
        exploded_rows,
        exploded_model_groups,
        args.figures_dir,
    )


if __name__ == "__main__":
    main()
