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


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DATA_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
REPORTS_DIR = REPO_ROOT / "reports"
INPUT_DEFAULT = DATA_PROCESSED_DIR / "leaderboard_submission_summary.csv"
TRAJECTORY_SUMMARY_DEFAULT = DATA_PROCESSED_DIR / "trajectory_summary.csv"
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


def load_trajectory_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        raw_rows = list(csv.DictReader(f))

    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        row = dict(raw)
        row["reward"] = parse_float(row.get("reward"))
        row["total_tokens"] = parse_float(row.get("total_tokens"))
        row["duration_seconds_from_timestamps"] = parse_float(row.get("duration_seconds_from_timestamps"))
        row["cost_usd"] = parse_float(row.get("cost_usd"))
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


def exploded_trajectory_model_component_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exploded: list[dict[str, Any]] = []
    for row in rows:
        model_value = str(row.get("model_dir") or row.get("leaderboard_model") or "")
        for model in split_multi(model_value):
            item = dict(row)
            item["model_component"] = model
            exploded.append(item)
    return exploded


def summarize_efficiency_group(items: list[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
    trajectory_count = len(items)
    pass_items = [row for row in items if row.get("reward_outcome") == "pass"]
    fail_items = [row for row in items if row.get("reward_outcome") == "fail"]
    pass_count = len(pass_items)
    fail_count = len(fail_items)
    labeled_count = pass_count + fail_count

    token_values = [row["total_tokens"] for row in items if row.get("total_tokens") is not None]
    duration_values = [
        row["duration_seconds_from_timestamps"]
        for row in items
        if row.get("duration_seconds_from_timestamps") is not None
    ]
    cost_values = [row["cost_usd"] for row in items if row.get("cost_usd") is not None]
    token_summary = numeric_summary(token_values)
    duration_summary = numeric_summary(duration_values)
    cost_summary = numeric_summary(cost_values)

    token_pass_values = [row["total_tokens"] for row in pass_items if row.get("total_tokens") is not None]
    token_fail_values = [row["total_tokens"] for row in fail_items if row.get("total_tokens") is not None]
    duration_pass_values = [
        row["duration_seconds_from_timestamps"]
        for row in pass_items
        if row.get("duration_seconds_from_timestamps") is not None
    ]
    duration_fail_values = [
        row["duration_seconds_from_timestamps"]
        for row in fail_items
        if row.get("duration_seconds_from_timestamps") is not None
    ]
    cost_pass_values = [row["cost_usd"] for row in pass_items if row.get("cost_usd") is not None]
    cost_fail_values = [row["cost_usd"] for row in fail_items if row.get("cost_usd") is not None]

    return {
        key: value,
        "trajectory_count": trajectory_count,
        "trajectory_count_with_tokens": len(token_values),
        "trajectory_count_with_duration": len(duration_values),
        "trajectory_count_with_cost": len(cost_values),
        "token_coverage": len(token_values) / trajectory_count if trajectory_count else None,
        "duration_coverage": len(duration_values) / trajectory_count if trajectory_count else None,
        "cost_coverage": len(cost_values) / trajectory_count if trajectory_count else None,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "success_rate": pass_count / labeled_count if labeled_count else None,
        "mean_total_tokens": token_summary["mean"],
        "median_total_tokens": token_summary["median"],
        "p90_total_tokens": token_summary["p90"],
        "mean_duration_seconds": duration_summary["mean"],
        "median_duration_seconds": duration_summary["median"],
        "p90_duration_seconds": duration_summary["p90"],
        "mean_cost_usd": cost_summary["mean"],
        "median_cost_usd": cost_summary["median"],
        "p90_cost_usd": cost_summary["p90"],
        "mean_tokens_pass": mean(token_pass_values) if token_pass_values else None,
        "mean_tokens_fail": mean(token_fail_values) if token_fail_values else None,
        "mean_duration_pass": mean(duration_pass_values) if duration_pass_values else None,
        "mean_duration_fail": mean(duration_fail_values) if duration_fail_values else None,
        "mean_cost_pass": mean(cost_pass_values) if cost_pass_values else None,
        "mean_cost_fail": mean(cost_fail_values) if cost_fail_values else None,
        "tokens_per_pass": sum(token_values) / pass_count if pass_count and token_values else None,
        "seconds_per_pass": sum(duration_values) / pass_count if pass_count and duration_values else None,
        "cost_per_pass": sum(cost_values) / pass_count if pass_count and cost_values else None,
    }


def efficiency_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, ""))].append(row)

    summaries = [summarize_efficiency_group(items, key, value) for value, items in grouped.items()]
    summaries.sort(
        key=lambda item: (
            -(item.get("success_rate") or 0.0),
            -(item.get("trajectory_count") or 0),
            str(item.get(key, "")),
        )
    )
    return summaries


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
    scaffold_efficiency: list[dict[str, Any]],
    model_component_efficiency: list[dict[str, Any]],
    decomposition: dict[str, Any],
) -> None:
    accuracies = [float(row["analysis_accuracy_percent"]) for row in rows if row.get("analysis_accuracy_percent") is not None]
    variances = [float(row["analysis_task_rate_variance"]) for row in rows if row.get("analysis_task_rate_variance") is not None]
    pms = [float(row["analysis_pm_percent"]) for row in rows if row.get("analysis_pm_percent") is not None]
    total_successes = sum(int(row.get("computed_submission_success_count") or 0) for row in rows)
    total_trials = sum(int(row.get("computed_submission_trial_count") or 0) for row in rows)
    ranked_rows = sorted(rows, key=lambda row: row.get("leaderboard_rank") or 999999)
    scaffold_multi = [row for row in scaffold_groups if (row.get("distinct_model_count") or 0) > 1]
    model_multi = [row for row in model_groups if (row.get("distinct_scaffold_count") or 0) > 1]
    exploded_multi = [row for row in exploded_model_groups if (row.get("distinct_scaffold_count") or 0) > 1]
    accuracy_summary = numeric_summary(accuracies)
    variance_summary = numeric_summary(variances)
    pm_summary = numeric_summary(pms)

    lines = [
        "# Superficial Terminal-Bench Leaderboard Analysis",
        "",
        "This report uses `data/processed/leaderboard_submission_summary.csv` and stays at submission-row level. "
        "Accuracy and +/- use scraped official leaderboard fields; task-rate variance remains a computed diagnostic from per-task resolution rates. "
        "Passed task-trials are represented by computed aggregate counts (`computed_submission_success_count`). Trajectory-level pass/fail analysis now lives in the trajectory characterization outputs via the validated reward index.",
        "",
        "## Overall Submission-Level Picture",
        "",
        f"- Submission rows: {len(rows)}.",
        f"- Rows with local trajectories: {sum(1 for row in rows if row.get('has_trajectories'))}.",
        f"- Unique scaffolds: {len({row.get('scaffold') for row in rows})}.",
        f"- Unique exact model labels: {len({row.get('leaderboard_model') for row in rows})}.",
        f"- Total passed task-trials: {total_successes} / {total_trials} ({fmt_pct(total_successes / total_trials * 100.0 if total_trials else None)}).",
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
        "## Top Rows by Accuracy",
        "",
        markdown_table(
            ranked_rows,
            [
                ("leaderboard_rank", "Rank"),
                ("scaffold", "Scaffold"),
                ("leaderboard_model", "Model"),
                ("computed_submission_success_count", "Passed"),
                ("computed_submission_trial_count", "Trials"),
                ("analysis_accuracy_percent", "Accuracy"),
                ("analysis_task_rate_variance", "Task-rate variance"),
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
        "This is a one-way ANOVA-style eta-squared diagnostic on submission accuracy, not a causal estimate. "
        "It asks how much row-level accuracy variance is associated with grouping by one label at a time.",
        "",
        f"- Scaffold label eta-squared: {fmt_num(decomposition['scaffold']['eta_squared'], 3)} across {decomposition['scaffold']['groups']} scaffold groups.",
        f"- Exact model label eta-squared: {fmt_num(decomposition['leaderboard_model']['eta_squared'], 3)} across {decomposition['leaderboard_model']['groups']} model groups.",
        f"- Exploded model component eta-squared: {fmt_num(decomposition['model_component']['eta_squared'], 3)} across {decomposition['model_component']['groups']} model-component groups.",
        "",
        "## Trajectory Resource Efficiency",
        "",
        "The companion efficiency files use local trajectory rows from `data/processed/trajectory_summary.csv`, not the full leaderboard. "
        "Coverage columns report how many local trajectories support token, duration, and cost estimates.",
        "",
        "For model components, multi-model rows are duplicated across components and are not credit-apportioned. "
        "Component-level token, duration, and cost metrics should be read as association or presence metrics: submissions involving this model component had this resource profile.",
        "",
        "Top sampled scaffolds by trajectory success rate:",
        "",
        markdown_table(
            scaffold_efficiency,
            [
                ("scaffold", "Scaffold"),
                ("trajectory_count", "Trajectories"),
                ("pass_count", "Passes"),
                ("fail_count", "Failures"),
                ("success_rate", "Success rate"),
                ("median_total_tokens", "Median tokens"),
                ("median_duration_seconds", "Median sec."),
                ("median_cost_usd", "Median cost"),
                ("tokens_per_pass", "Tokens/pass"),
            ],
            12,
        ),
        "",
        "Top sampled model components by trajectory success rate:",
        "",
        markdown_table(
            model_component_efficiency,
            [
                ("model_component", "Model component"),
                ("trajectory_count", "Trajectories"),
                ("pass_count", "Passes"),
                ("fail_count", "Failures"),
                ("success_rate", "Success rate"),
                ("median_total_tokens", "Median tokens"),
                ("median_duration_seconds", "Median sec."),
                ("median_cost_usd", "Median cost"),
                ("tokens_per_pass", "Tokens/pass"),
            ],
            12,
        ),
        "",
        "## Generated Artifacts",
        "",
        "- `data/processed/leaderboard_scaffold_variance.csv`",
        "- `data/processed/leaderboard_model_variance.csv`",
        "- `data/processed/leaderboard_model_component_variance.csv`",
        "- `data/processed/trajectory_scaffold_efficiency.csv`",
        "- `data/processed/trajectory_model_component_efficiency.csv`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--trajectory-summary", type=Path, default=TRAJECTORY_SUMMARY_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--report", type=Path, default=REPORT_DEFAULT)
    args = parser.parse_args()

    rows = load_rows(args.input)
    trajectory_rows = load_trajectory_rows(args.trajectory_summary)
    args.out.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    scaffold_groups = group_rows(rows, "scaffold")
    model_groups = group_rows(rows, "leaderboard_model")
    exploded_rows = exploded_model_rows(rows)
    exploded_model_groups = group_rows(exploded_rows, "model_component")
    scaffold_efficiency = efficiency_rows(trajectory_rows, "scaffold")
    trajectory_component_rows = exploded_trajectory_model_component_rows(trajectory_rows)
    model_component_efficiency = efficiency_rows(trajectory_component_rows, "model_component")
    decomposition = {
        "scaffold": one_way_eta_squared(rows, "scaffold"),
        "leaderboard_model": one_way_eta_squared(rows, "leaderboard_model"),
        "model_component": one_way_eta_squared(exploded_rows, "model_component"),
    }

    write_csv(args.out / "leaderboard_scaffold_variance.csv", scaffold_groups)
    write_csv(args.out / "leaderboard_model_variance.csv", model_groups)
    write_csv(args.out / "leaderboard_model_component_variance.csv", exploded_model_groups)
    write_csv(args.out / "trajectory_scaffold_efficiency.csv", scaffold_efficiency)
    write_csv(args.out / "trajectory_model_component_efficiency.csv", model_component_efficiency)

    write_report(
        args.report,
        rows,
        scaffold_groups,
        model_groups,
        exploded_model_groups,
        scaffold_efficiency,
        model_component_efficiency,
        decomposition,
    )


if __name__ == "__main__":
    main()
