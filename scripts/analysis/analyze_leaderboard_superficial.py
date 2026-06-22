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
import os
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
FIGURES_DIR = REPORTS_DIR / "figures_live"
INPUT_DEFAULT = DATA_PROCESSED_DIR / "leaderboard_submission_summary.csv"
OUT_DEFAULT = DATA_PROCESSED_DIR
REPORT_DEFAULT = REPORTS_DIR / "leaderboard_superficial_analysis.md"

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


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def numeric_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "p25": None,
            "median": None,
            "mean": None,
            "p75": None,
            "p90": None,
            "max": None,
            "std": None,
        }
    return {
        "count": len(values),
        "min": min(values),
        "p25": percentile(values, 0.25),
        "median": median(values),
        "mean": mean(values),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "max": max(values),
        "std": sample_std(values),
    }


def fmt_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}%"


def fmt_num(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


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


def one_way_eta_squared(rows: list[dict[str, Any]], key: str) -> dict[str, float | int | None]:
    usable = [
        row
        for row in rows
        if row.get("analysis_accuracy_percent") is not None and str(row.get(key, "")) != ""
    ]
    if len(usable) < 2:
        return {"n": len(usable), "groups": 0, "eta_squared": None}
    overall = mean(float(row["analysis_accuracy_percent"]) for row in usable)
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in usable:
        grouped[str(row[key])].append(float(row["analysis_accuracy_percent"]))
    total_ss = sum((float(row["analysis_accuracy_percent"]) - overall) ** 2 for row in usable)
    between_ss = sum(len(values) * (mean(values) - overall) ** 2 for values in grouped.values())
    return {
        "n": len(usable),
        "groups": len(grouped),
        "eta_squared": between_ss / total_ss if total_ss else None,
    }


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


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def markdown_link_path(target: Path, markdown_file: Path) -> str:
    return Path(os.path.relpath(target.resolve(), start=markdown_file.parent.resolve())).as_posix()


def figure_caption(path: Path) -> str:
    captions = {
        "leaderboard_accuracy_distribution": "Leaderboard accuracy distribution",
        "leaderboard_accuracy_by_scaffold": "Leaderboard accuracy by scaffold",
        "leaderboard_accuracy_by_model_component": "Leaderboard accuracy by model component",
        "leaderboard_largest_accuracy_ranges": "Largest within-label accuracy ranges",
    }
    return captions.get(path.stem, path.stem.replace("_", " ").title())


def grouped_accuracy_values(rows: list[dict[str, Any]], key: str, groups: list[dict[str, Any]], limit: int) -> list[tuple[str, list[float]]]:
    selected_keys = [str(group.get(key, "")) for group in groups if (group.get("row_count") or 0) >= 2][:limit]
    grouped: dict[str, list[float]] = {value: [] for value in selected_keys}
    for row in rows:
        value = str(row.get(key, ""))
        if value not in grouped or row.get("analysis_accuracy_percent") is None:
            continue
        grouped[value].append(float(row["analysis_accuracy_percent"]))
    return [(value, grouped[value]) for value in selected_keys if grouped[value]]


def plot_violin_box(
    grouped_values: list[tuple[str, list[float]]],
    title: str,
    xlabel: str,
    path: Path,
) -> Path | None:
    if not grouped_values:
        return None

    labels = [f"{label}\n(n={len(values)})" for label, values in grouped_values]
    values = [group_values for _, group_values in grouped_values]
    height = max(5.0, min(13.5, 1.4 + len(values) * 0.46))
    fig, ax = plt.subplots(figsize=(10.5, height))

    parts = ax.violinplot(values, vert=False, showmeans=False, showmedians=False, showextrema=False)
    for body in parts["bodies"]:
        body.set_facecolor("#7aa6c2")
        body.set_edgecolor("#3d5f73")
        body.set_alpha(0.45)

    ax.boxplot(
        values,
        vert=False,
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
            group_values,
            np.full(len(group_values), position) + jitter,
            s=16,
            color="#1f2d3a",
            alpha=0.65,
            linewidths=0,
        )

    ax.set_yticks(range(1, len(labels) + 1))
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlim(0, 100)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_overall_accuracy_distribution(rows: list[dict[str, Any]], path: Path) -> Path | None:
    accuracies = [float(row["analysis_accuracy_percent"]) for row in rows if row.get("analysis_accuracy_percent") is not None]
    if not accuracies:
        return None

    fig, (ax_hist, ax_box) = plt.subplots(
        2,
        1,
        figsize=(9.5, 6.0),
        gridspec_kw={"height_ratios": [3.0, 1.0]},
        sharex=True,
    )
    ax_hist.hist(accuracies, bins=np.arange(0, 105, 5), color="#6c8ebf", edgecolor="white")
    ax_hist.axvline(mean(accuracies), color="#c44e52", linewidth=1.8, label=f"Mean {mean(accuracies):.1f}%")
    ax_hist.axvline(median(accuracies), color="#2f6f4e", linewidth=1.8, linestyle="--", label=f"Median {median(accuracies):.1f}%")
    ax_hist.set_ylabel("Submission rows")
    ax_hist.set_title("Leaderboard submission accuracy distribution")
    ax_hist.grid(axis="y", alpha=0.25)
    ax_hist.legend(frameon=False)

    ax_box.violinplot([accuracies], vert=False, showmeans=False, showmedians=False, showextrema=False)
    ax_box.boxplot([accuracies], vert=False, widths=0.32, showfliers=False)
    ax_box.set_yticks([])
    ax_box.set_xlabel("Official leaderboard accuracy (%)")
    ax_box.grid(axis="x", alpha=0.25)

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_accuracy_ranges(
    scaffold_groups: list[dict[str, Any]],
    exploded_model_groups: list[dict[str, Any]],
    path: Path,
    limit: int = 15,
) -> Path | None:
    scaffold_multi = [row for row in scaffold_groups if (row.get("distinct_model_count") or 0) > 1][:limit]
    model_multi = [row for row in exploded_model_groups if (row.get("distinct_scaffold_count") or 0) > 1][:limit]
    if not scaffold_multi and not model_multi:
        return None

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 6.4), sharex=True)
    panels = [
        (axes[0], scaffold_multi, "scaffold", "Top same-scaffold ranges"),
        (axes[1], model_multi, "model_component", "Top model-component ranges"),
    ]
    for ax, rows, key, title in panels:
        labels = [str(row.get(key, "")) for row in rows][::-1]
        ranges = [float(row.get("accuracy_range_percent") or 0.0) for row in rows][::-1]
        counts = [int(row.get("row_count") or 0) for row in rows][::-1]
        y = np.arange(len(labels))
        ax.barh(y, ranges, color="#8f7ab8")
        ax.set_yticks(y)
        ax.set_yticklabels([f"{label} (n={count})" for label, count in zip(labels, counts)], fontsize=8)
        ax.set_title(title)
        ax.set_xlabel("Accuracy range (percentage points)")
        ax.grid(axis="x", alpha=0.25)
    fig.suptitle("Largest within-label leaderboard accuracy spreads", y=0.995)
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

    overall = plot_overall_accuracy_distribution(rows, figures_dir / "leaderboard_accuracy_distribution.png")
    if overall is not None:
        figures.append(overall)

    scaffold_values = grouped_accuracy_values(rows, "scaffold", scaffold_groups, limit=20)
    scaffold_plot = plot_violin_box(
        scaffold_values,
        "Leaderboard accuracy by scaffold",
        "Official leaderboard accuracy (%)",
        figures_dir / "leaderboard_accuracy_by_scaffold.png",
    )
    if scaffold_plot is not None:
        figures.append(scaffold_plot)

    model_values = grouped_accuracy_values(exploded_rows, "model_component", exploded_model_groups, limit=20)
    model_plot = plot_violin_box(
        model_values,
        "Leaderboard accuracy by model component",
        "Official leaderboard accuracy (%)",
        figures_dir / "leaderboard_accuracy_by_model_component.png",
    )
    if model_plot is not None:
        figures.append(model_plot)

    range_plot = plot_accuracy_ranges(
        scaffold_groups,
        exploded_model_groups,
        figures_dir / "leaderboard_largest_accuracy_ranges.png",
    )
    if range_plot is not None:
        figures.append(range_plot)

    return figures


def markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], limit: int) -> str:
    selected = rows[:limit]
    out = [
        "| " + " | ".join(label for _, label in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in selected:
        cells: list[str] = []
        for key, _ in columns:
            value = row.get(key)
            if key.endswith("_percent") or key in {
                "mean_accuracy_percent",
                "weighted_accuracy_percent",
                "accuracy_range_percent",
                "accuracy_std_percent",
                "best_accuracy_percent",
                "worst_accuracy_percent",
                "min_accuracy_percent",
                "max_accuracy_percent",
                "success_rate",
                "token_coverage",
                "duration_coverage",
                "cost_coverage",
            }:
                if key in {"success_rate", "token_coverage", "duration_coverage", "cost_coverage"} and value is not None:
                    cells.append(fmt_pct(float(value) * 100.0))
                else:
                    cells.append(fmt_pct(value))
            elif "variance" in key:
                cells.append(fmt_num(value, 4))
            elif isinstance(value, float):
                cells.append(fmt_num(value))
            else:
                cells.append(str(value) if value is not None else "")
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def write_report(
    path: Path,
    rows: list[dict[str, Any]],
    scaffold_groups: list[dict[str, Any]],
    model_groups: list[dict[str, Any]],
    exploded_model_groups: list[dict[str, Any]],
    decomposition: dict[str, Any],
    figures: list[Path],
    out_dir: Path,
) -> None:
    accuracies = [float(row["analysis_accuracy_percent"]) for row in rows if row.get("analysis_accuracy_percent") is not None]
    variances = [float(row["analysis_task_rate_variance"]) for row in rows if row.get("analysis_task_rate_variance") is not None]
    pms = [float(row["analysis_pm_percent"]) for row in rows if row.get("analysis_pm_percent") is not None]
    ranked_rows = sorted(rows, key=lambda row: row.get("leaderboard_rank") or 999999)
    scaffold_multi = [row for row in scaffold_groups if (row.get("distinct_model_count") or 0) > 1]
    model_multi = [row for row in model_groups if (row.get("distinct_scaffold_count") or 0) > 1]
    exploded_multi = [row for row in exploded_model_groups if (row.get("distinct_scaffold_count") or 0) > 1]
    accuracy_summary = numeric_summary(accuracies)
    variance_summary = numeric_summary(variances)
    pm_summary = numeric_summary(pms)
    figure_lines: list[str] = []
    for figure in figures:
        figure_lines.extend(
            [
                f"![{figure_caption(figure)}]({markdown_link_path(figure, path)})",
                "",
            ]
        )

    lines = [
        "# Superficial Terminal-Bench Leaderboard Analysis",
        "",
        "This report uses the current leaderboard snapshot and stays at submission-row level. "
        "Accuracy and +/- use scraped official leaderboard fields.",
        "",
        "## Overall Submission-Level Picture",
        "",
        f"- Submission rows: {len(rows)}.",
        f"- Rows with local trajectories: {sum(1 for row in rows if row.get('has_trajectories'))}.",
        f"- Unique scaffolds: {len({row.get('scaffold') for row in rows})}.",
        f"- Unique exact model labels: {len({row.get('leaderboard_model') for row in rows})}.",
        f"- Leaderboard accuracy: mean {fmt_pct(accuracy_summary['mean'])}, median {fmt_pct(accuracy_summary['median'])}, range {fmt_pct(accuracy_summary['min'])}-{fmt_pct(accuracy_summary['max'])}.",
        f"- Within-submission task-rate variance: mean {fmt_num(variance_summary['mean'], 4)}, median {fmt_num(variance_summary['median'], 4)}.",
        f"- Leaderboard +/- estimate: mean {fmt_pct(pm_summary['mean'])}, median {fmt_pct(pm_summary['median'])}.",
        "",
        "## Preliminary Reading",
        "",
        f"- Same-scaffold comparisons are available for {len(scaffold_multi)} scaffolds. "
        f"The largest accuracy ranges are `{scaffold_multi[0]['scaffold']}` ({fmt_pct(scaffold_multi[0]['accuracy_range_percent'])}), "
        f"`{scaffold_multi[1]['scaffold']}` ({fmt_pct(scaffold_multi[1]['accuracy_range_percent'])}), and "
        f"`{scaffold_multi[2]['scaffold']}` ({fmt_pct(scaffold_multi[2]['accuracy_range_percent'])}).",
        f"- Same-model comparisons are available for {len(model_multi)} exact model labels. "
        f"The largest exact-model ranges are `{model_multi[0]['leaderboard_model']}` ({fmt_pct(model_multi[0]['accuracy_range_percent'])}), "
        f"`{model_multi[1]['leaderboard_model']}` ({fmt_pct(model_multi[1]['accuracy_range_percent'])}), and "
        f"`{model_multi[2]['leaderboard_model']}` ({fmt_pct(model_multi[2]['accuracy_range_percent'])}).",
        f"- After splitting comma-separated model labels, {len(exploded_multi)} model components appear with more than one scaffold. "
        "This view is useful for spotting mixed-model or ensemble rows that would otherwise hide under a combined label.",
        "- The eta-squared values below are descriptive only. They are inflated when many groups have one or two rows, so they should guide where to inspect next rather than settle the scaffold-vs-model question.",
        "",
        "## Visual Diagnostics",
        "",
        "These figures are intended as a first-pass visualization of the leaderboard rows. Violin widths show the distribution shape, box plots show the median and interquartile range, and individual dots show the actual submission rows.",
        "",
        *figure_lines,
        "## Top Rows by Accuracy",
        "",
        markdown_table(
            ranked_rows,
            [
                ("leaderboard_rank", "Rank"),
                ("scaffold", "Scaffold"),
                ("leaderboard_model", "Model"),
                ("analysis_accuracy_percent", "Official accuracy"),
                ("analysis_pm_percent", "+/-"),
                ("has_trajectories", "Has trajectories"),
            ],
            15,
        ),
        "",
        "## Same Scaffold, Different Models",
        "",
        "These groups show how much leaderboard accuracy moves when the scaffold label is fixed and the model label changes. "
        "Large ranges suggest model choice matters within that scaffold, although scaffold versions are not collapsed here.",
        "",
        markdown_table(
            scaffold_multi,
            [
                ("scaffold", "Scaffold"),
                ("row_count", "Rows"),
                ("distinct_model_count", "Models"),
                ("mean_accuracy_percent", "Mean acc."),
                ("accuracy_range_percent", "Range"),
                ("accuracy_std_percent", "Std."),
                ("best_accuracy_percent", "Best"),
                ("worst_accuracy_percent", "Worst"),
            ],
            20,
        ),
        "",
        "## Same Model, Different Scaffolds",
        "",
        "These groups show how much leaderboard accuracy moves when the exact model label is fixed and the scaffold changes. "
        "Large ranges suggest scaffold choice matters for that model.",
        "",
        markdown_table(
            model_multi,
            [
                ("leaderboard_model", "Model"),
                ("row_count", "Rows"),
                ("distinct_scaffold_count", "Scaffolds"),
                ("mean_accuracy_percent", "Mean acc."),
                ("accuracy_range_percent", "Range"),
                ("accuracy_std_percent", "Std."),
                ("best_accuracy_percent", "Best"),
                ("worst_accuracy_percent", "Worst"),
            ],
            20,
        ),
        "",
        "## Same Model Component, Different Scaffolds",
        "",
        "Some leaderboard rows list model ensembles or multiple model names. This exploded view splits comma-separated model labels before grouping, so mixed-model rows can still contribute to model-level pattern finding.",
        "",
        markdown_table(
            exploded_multi,
            [
                ("model_component", "Model component"),
                ("row_count", "Rows"),
                ("distinct_scaffold_count", "Scaffolds"),
                ("mean_accuracy_percent", "Mean acc."),
                ("accuracy_range_percent", "Range"),
                ("accuracy_std_percent", "Std."),
                ("best_accuracy_percent", "Best"),
                ("worst_accuracy_percent", "Worst"),
            ],
            20,
        ),
        "",
        "## Coarse Variance Attribution",
        "",
        "This is a one-way ANOVA-style eta-squared diagnostic on scraped official leaderboard accuracy, not a causal estimate and not a local reward-derived accuracy. "
        "It asks how much row-level official accuracy variance is associated with grouping by one label at a time.",
        "",
        f"- Scaffold label eta-squared: {fmt_num(decomposition['scaffold']['eta_squared'], 3)} across {decomposition['scaffold']['groups']} scaffold groups.",
        f"- Exact model label eta-squared: {fmt_num(decomposition['leaderboard_model']['eta_squared'], 3)} across {decomposition['leaderboard_model']['groups']} model groups.",
        f"- Exploded model component eta-squared: {fmt_num(decomposition['model_component']['eta_squared'], 3)} across {decomposition['model_component']['groups']} model-component groups.",
        "",
        "## Generated Artifacts",
        "",
        f"- `{relative_path(out_dir / 'leaderboard_scaffold_variance.csv')}`",
        f"- `{relative_path(out_dir / 'leaderboard_model_variance.csv')}`",
        f"- `{relative_path(out_dir / 'leaderboard_model_component_variance.csv')}`",
        *[f"- `{relative_path(figure)}`" for figure in figures],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--report", type=Path, default=REPORT_DEFAULT)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR)
    args = parser.parse_args()

    rows = load_rows(args.input)
    args.out.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    scaffold_groups = group_rows(rows, "scaffold")
    model_groups = group_rows(rows, "leaderboard_model")
    exploded_rows = exploded_model_rows(rows)
    exploded_model_groups = group_rows(exploded_rows, "model_component")
    decomposition = {
        "scaffold": one_way_eta_squared(rows, "scaffold"),
        "leaderboard_model": one_way_eta_squared(rows, "leaderboard_model"),
        "model_component": one_way_eta_squared(exploded_rows, "model_component"),
    }

    write_csv(args.out / "leaderboard_scaffold_variance.csv", scaffold_groups)
    write_csv(args.out / "leaderboard_model_variance.csv", model_groups)
    write_csv(args.out / "leaderboard_model_component_variance.csv", exploded_model_groups)

    figures = plot_leaderboard_figures(
        rows,
        scaffold_groups,
        exploded_rows,
        exploded_model_groups,
        args.figures_dir,
    )

    write_report(
        args.report,
        rows,
        scaffold_groups,
        model_groups,
        exploded_model_groups,
        decomposition,
        figures,
        args.out,
    )


if __name__ == "__main__":
    main()
