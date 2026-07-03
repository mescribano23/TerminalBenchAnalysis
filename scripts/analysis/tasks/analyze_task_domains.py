#!/usr/bin/env python3
"""Task-domain success table and simple figures.

Outputs:
- data/processed_live/task_mining/category/task_domain_outcome.csv
- data/processed_live/task_mining/category/task_domain_effort_summary.csv
- data/processed_live/task_mining/difficulty/task_difficulty_outcome.csv
- data/processed_live/task_mining/difficulty/task_difficulty_effort_summary.csv
- data/processed_live/task_mining/category_difficulty/category_difficulty_composition.csv
- data/processed_live/task_mining/category_difficulty/category_difficulty_pass_rates.csv
- reports/tasks/category/task_domain_success_task_weighted.png
- reports/tasks/category/task_domain_pass_fail_counts.png
- reports/tasks/category/task_domain_task_coverage.png
- reports/tasks/category/pie_chart_task_domain_pass_fail_distribution.png
- reports/tasks/category/effort_vars/heatmap_task_domain_effort_median.png
- data/processed_live/task_mining/category/model_scaffold/*.csv
- data/processed_live/task_mining/difficulty/model_scaffold/*.csv
- reports/tasks/category/model_scaffold/*.png
- reports/tasks/category/stacked_scaffold_category_composition.png
- reports/tasks/difficulty/*.png
- reports/tasks/difficulty/model_scaffold/*.png
- reports/tasks/category_difficulty/*.png
"""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter
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
TASKS_DEFAULT = DATA_DIR / "raw" / "terminal_bench_2_tasks_current.json"
OUT_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining"
FIGURES_DEFAULT = REPORTS_DIR / "tasks"

ENTITY_COLUMNS = {"scaffold", "model_dir"}
MODEL_META_COLUMNS = {"leaderboard_model", "leaderboard_model_organization", "model_name"}
OUTCOME_COLUMNS = {"task_name", "reward_outcome", "outcome", "reward"}
EFFORT_DISPLAY_NAMES = {
    "step_count": "Step count",
    "command_count": "Command count",
    "tool_call_count": "Tool call count",
    "total_tokens": "Total tokens",
    "duration_seconds_from_timestamps": "Duration seconds",
    "cost_usd_positive": "Positive cost USD",
}
EFFORT_SOURCE_COLUMNS = set(EFFORT_DISPLAY_NAMES) - {"cost_usd_positive"} | {"cost_usd"}
OPEN_SOURCE_MODEL_KEYWORDS = (
    "deepseek",
    "glm",
    "gpt-oss",
    "kimi",
    "minimax",
    "qwen",
)
DIFFICULTY_ORDER = ["easy", "medium", "hard"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectories", type=Path, default=TRAJECTORY_DEFAULT)
    parser.add_argument("--tasks", type=Path, default=TASKS_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DEFAULT)
    return parser.parse_args()


def load_tasks(path: Path) -> pd.DataFrame:
    with path.open(encoding="utf-8") as f:
        tasks: list[dict[str, Any]] = json.load(f)
    task_df = pd.DataFrame(tasks)
    required = {"id", "category", "difficulty"}
    missing = required.difference(task_df.columns)
    if missing:
        raise ValueError(f"{path} is missing required task fields: {', '.join(sorted(missing))}")
    return task_df[["id", "category", "difficulty"]].rename(columns={"id": "task_name"})


def model_source_type(row: pd.Series) -> str:
    model_text = " ".join(
        str(row.get(column, "")).lower().replace("_", "-")
        for column in ["model_dir", "model_name", "leaderboard_model"]
    )
    if any(keyword in model_text for keyword in OPEN_SOURCE_MODEL_KEYWORDS):
        return "open_source_or_open_weight"
    return "closed_source"


def dimension_sort_key(series: pd.Series, dimension_column: str) -> pd.Series:
    if dimension_column != "difficulty":
        return series.astype(str)
    order = {value: index for index, value in enumerate(DIFFICULTY_ORDER)}
    return series.astype(str).map(order).fillna(len(order))


def ordered_dimension_values(domain_table: pd.DataFrame, dimension_column: str) -> list[str]:
    if dimension_column == "difficulty":
        values = domain_table[dimension_column].astype(str).tolist()
        ordered = [value for value in DIFFICULTY_ORDER if value in values]
        ordered.extend(sorted(value for value in values if value not in DIFFICULTY_ORDER))
        return ordered
    return domain_table.sort_values(
        ["n_tasks", "n_trajectories", dimension_column],
        ascending=[False, False, True],
    )[dimension_column].tolist()


def load_trajectories(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        usecols=lambda column: column in OUTCOME_COLUMNS | EFFORT_SOURCE_COLUMNS | ENTITY_COLUMNS | MODEL_META_COLUMNS,
    )
    if "task_name" not in df.columns:
        raise ValueError(f"{path} must contain task_name.")

    if "reward_outcome" in df.columns:
        df["outcome"] = df["reward_outcome"]
    elif "outcome" not in df.columns and "reward" in df.columns:
        reward = pd.to_numeric(df["reward"], errors="coerce")
        df["outcome"] = reward.map({1.0: "pass", 0.0: "fail"})

    if "outcome" not in df.columns:
        raise ValueError(f"{path} must contain reward_outcome, outcome, or reward.")

    df = df[df["outcome"].isin(["pass", "fail"])].copy()
    if df.empty:
        raise ValueError(f"{path} has no pass/fail rows.")
    df["passed"] = (df["outcome"] == "pass").astype(int)

    for column in EFFORT_SOURCE_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    if "cost_usd" in df.columns:
        df["cost_usd_positive"] = df["cost_usd"].where(df["cost_usd"] > 0)
    for column in ENTITY_COLUMNS:
        if column not in df.columns:
            raise ValueError(f"{path} must contain {column}.")
        df[column] = df[column].fillna("unknown").astype(str)
    if "leaderboard_model_organization" in df.columns:
        df["model_provider"] = df["leaderboard_model_organization"].fillna("unknown").astype(str)
        df["model_provider"] = df["model_provider"].replace({"Minimax": "MiniMax"})
    else:
        df["model_provider"] = "unknown"
    df["model_source"] = df.apply(model_source_type, axis=1)

    columns = ["task_name", "outcome", "passed", "scaffold", "model_dir", "model_provider", "model_source"]
    columns.extend(column for column in EFFORT_DISPLAY_NAMES if column in df.columns)
    return df[columns]


def build_domain_table(
    trajectories: pd.DataFrame,
    tasks: pd.DataFrame,
    dimension_column: str = "category",
) -> pd.DataFrame:
    df = trajectories.merge(tasks, on="task_name", how="left", validate="many_to_one")
    missing = df[dimension_column].isna()
    if missing.any():
        missing_tasks = sorted(df.loc[missing, "task_name"].dropna().unique().tolist())
        preview = ", ".join(missing_tasks[:8])
        raise ValueError(f"Task metadata missing for {missing.sum()} trajectory rows. Examples: {preview}")

    task_rates = (
        df.groupby([dimension_column, "task_name"], as_index=False)
        .agg(
            task_trajectory_count=("passed", "size"),
            task_pass_count=("passed", "sum"),
            task_pass_rate=("passed", "mean"),
        )
    )

    rows: list[dict[str, Any]] = []
    for dimension_value, group in df.groupby(dimension_column, sort=False):
        n_trajectories = int(group.shape[0])
        pass_count = int(group["passed"].sum())
        fail_count = n_trajectories - pass_count
        pass_rate = pass_count / n_trajectories if n_trajectories else None

        dimension_task_rates = task_rates.loc[task_rates[dimension_column] == dimension_value, "task_pass_rate"]
        n_tasks = int(dimension_task_rates.shape[0])
        task_mean_pass_rate = float(dimension_task_rates.mean()) if n_tasks else None

        rows.append(
            {
                dimension_column: dimension_value,
                "n_tasks": n_tasks,
                "n_trajectories": n_trajectories,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "pass_rate": pass_rate,
                "task_mean_pass_rate": task_mean_pass_rate,
                "low_task_count": n_tasks < 5,
            }
        )

    out = pd.DataFrame(rows)
    if dimension_column == "difficulty":
        return (
            out.assign(_dimension_order=dimension_sort_key(out[dimension_column], dimension_column))
            .sort_values(["_dimension_order", dimension_column])
            .drop(columns="_dimension_order")
            .reset_index(drop=True)
        )
    return out.sort_values(
        ["n_tasks", "n_trajectories", dimension_column],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def build_effort_summary(
    trajectories: pd.DataFrame,
    tasks: pd.DataFrame,
    dimension_column: str = "category",
) -> pd.DataFrame:
    df = trajectories.merge(tasks, on="task_name", how="left", validate="many_to_one")
    missing = df[dimension_column].isna()
    if missing.any():
        missing_tasks = sorted(df.loc[missing, "task_name"].dropna().unique().tolist())
        preview = ", ".join(missing_tasks[:8])
        raise ValueError(f"Task metadata missing for {missing.sum()} trajectory rows. Examples: {preview}")

    rows: list[dict[str, Any]] = []
    for dimension_value, group in df.groupby(dimension_column, sort=False):
        for variable, display_name in EFFORT_DISPLAY_NAMES.items():
            if variable not in group.columns:
                continue
            values = group[variable].dropna()
            rows.append(
                {
                    dimension_column: dimension_value,
                    "variable": variable,
                    "variable_display": display_name,
                    "n_trajectories": int(group.shape[0]),
                    "complete_case_count": int(values.shape[0]),
                    "median": float(values.median()) if len(values) else None,
                    "mean": float(values.mean()) if len(values) else None,
                    "p75": float(values.quantile(0.75)) if len(values) else None,
                    "p90": float(values.quantile(0.90)) if len(values) else None,
                    "max": float(values.max()) if len(values) else None,
                }
            )

    out = pd.DataFrame(rows)
    if dimension_column == "difficulty":
        return (
            out.assign(_dimension_order=dimension_sort_key(out[dimension_column], dimension_column))
            .sort_values(["variable", "_dimension_order", dimension_column])
            .drop(columns="_dimension_order")
            .reset_index(drop=True)
        )
    return out.sort_values(["variable", "median", dimension_column], ascending=[True, False, True]).reset_index(
        drop=True
    )


def merge_task_metadata(
    trajectories: pd.DataFrame,
    tasks: pd.DataFrame,
    dimension_column: str = "category",
) -> pd.DataFrame:
    df = trajectories.merge(tasks, on="task_name", how="left", validate="many_to_one")
    missing = df[dimension_column].isna()
    if missing.any():
        missing_tasks = sorted(df.loc[missing, "task_name"].dropna().unique().tolist())
        preview = ", ".join(missing_tasks[:8])
        raise ValueError(f"Task metadata missing for {missing.sum()} trajectory rows. Examples: {preview}")
    return df


def build_stratified_pass_rates(
    trajectories: pd.DataFrame,
    tasks: pd.DataFrame,
    group_columns: list[str],
    dimension_column: str = "category",
) -> pd.DataFrame:
    df = merge_task_metadata(trajectories, tasks, dimension_column)
    rows = (
        df.groupby([*group_columns, dimension_column], as_index=False)
        .agg(
            n_tasks=("task_name", "nunique"),
            n_trajectories=("passed", "size"),
            pass_count=("passed", "sum"),
        )
    )
    rows["fail_count"] = rows["n_trajectories"] - rows["pass_count"]
    rows["pass_rate"] = rows["pass_count"] / rows["n_trajectories"]

    totals = (
        df.groupby(group_columns, as_index=False)
        .agg(
            total_tasks=("task_name", "nunique"),
            total_trajectories=("passed", "size"),
            total_pass_count=("passed", "sum"),
        )
    )
    totals["total_pass_rate"] = totals["total_pass_count"] / totals["total_trajectories"]
    rows = rows.merge(totals, on=group_columns, how="left", validate="many_to_one")

    sort_columns = [*group_columns, dimension_column]
    if dimension_column == "difficulty":
        return (
            rows.assign(_dimension_order=dimension_sort_key(rows[dimension_column], dimension_column))
            .sort_values([*group_columns, "_dimension_order", dimension_column])
            .drop(columns="_dimension_order")
            .reset_index(drop=True)
        )
    return rows.sort_values(sort_columns).reset_index(drop=True)


def build_category_difficulty_pass_rates(trajectories: pd.DataFrame, tasks: pd.DataFrame) -> pd.DataFrame:
    df = trajectories.merge(tasks, on="task_name", how="left", validate="many_to_one")
    missing = df["category"].isna() | df["difficulty"].isna()
    if missing.any():
        missing_tasks = sorted(df.loc[missing, "task_name"].dropna().unique().tolist())
        preview = ", ".join(missing_tasks[:8])
        raise ValueError(f"Task metadata missing category/difficulty for {missing.sum()} rows. Examples: {preview}")

    rows = (
        df.groupby(["category", "difficulty"], as_index=False)
        .agg(
            n_tasks=("task_name", "nunique"),
            n_trajectories=("passed", "size"),
            pass_count=("passed", "sum"),
        )
    )
    rows["fail_count"] = rows["n_trajectories"] - rows["pass_count"]
    rows["pass_rate"] = rows["pass_count"] / rows["n_trajectories"]
    return (
        rows.assign(_difficulty_order=dimension_sort_key(rows["difficulty"], "difficulty"))
        .sort_values(["category", "_difficulty_order", "difficulty"])
        .drop(columns="_difficulty_order")
        .reset_index(drop=True)
    )


def build_category_difficulty_composition(category_difficulty_rates: pd.DataFrame) -> pd.DataFrame:
    totals = (
        category_difficulty_rates.groupby("category", as_index=False)
        .agg(
            category_total_tasks=("n_tasks", "sum"),
            category_total_trajectories=("n_trajectories", "sum"),
            category_pass_count=("pass_count", "sum"),
        )
    )
    out = category_difficulty_rates.merge(totals, on="category", how="left", validate="many_to_one")
    out["trajectory_share_within_category"] = out["n_trajectories"] / out["category_total_trajectories"]
    out["task_share_within_category"] = out["n_tasks"] / out["category_total_tasks"]
    return out[
        [
            "category",
            "difficulty",
            "n_tasks",
            "n_trajectories",
            "pass_count",
            "category_total_tasks",
            "category_total_trajectories",
            "category_pass_count",
            "task_share_within_category",
            "trajectory_share_within_category",
        ]
    ]


def figure_height(row_count: int) -> float:
    return max(4.8, 1.6 + row_count * 0.34)


def figure_width(column_count: int) -> float:
    return max(10.5, min(22.0, 4.0 + column_count * 0.8))


def category_count_label(row: pd.Series, dimension_column: str = "category") -> str:
    return (
        f"{row[dimension_column]} "
        f"(tasks={int(row['n_tasks'])}, traj={int(row['n_trajectories']):,})"
        f"{'*' if row['low_task_count'] else ''}"
    )


def category_count_label_multiline(row: pd.Series, dimension_column: str = "category") -> str:
    return (
        f"{row[dimension_column]}\n"
        f"(tasks={int(row['n_tasks'])}, traj={int(row['n_trajectories']):,})"
        f"{'*' if row['low_task_count'] else ''}"
    )


def format_category_axis(ax: plt.Axes) -> None:
    ax.tick_params(axis="x", labelrotation=55)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")


def format_success_rate_axis(ax: plt.Axes) -> None:
    ax.set_xlim(0, 1)
    ax.grid(axis="x", alpha=0.25)


def plot_task_weighted_success(
    domain_table: pd.DataFrame,
    figures_dir: Path,
    dimension_column: str = "category",
    dimension_label: str = "task category",
    output_prefix: str = "task_domain",
) -> Path:
    plot_df = domain_table.sort_values("task_mean_pass_rate", ascending=False).copy()
    plot_df["category_label"] = plot_df.apply(lambda row: category_count_label(row, dimension_column), axis=1)
    fig, ax = plt.subplots(figsize=(9.5, figure_height(len(plot_df))))
    ax.barh(plot_df["category_label"], plot_df["task_mean_pass_rate"])
    ax.invert_yaxis()
    format_success_rate_axis(ax)
    ax.set_xlabel("Task-weighted pass rate")
    ax.set_ylabel(dimension_label[:1].upper() + dimension_label[1:])
    ax.set_title(f"Task-weighted pass rate by {dimension_label}")
    note = (
        "Note: Bars show the mean pass rate across tasks.\n"
        f"Labels show distinct tasks and trajectories; * marks {dimension_label}s with fewer than five tasks."
    )
    fig.text(
        0.01,
        0.015,
        textwrap.fill(note, width=120),
        fontsize=8.5,
        color="#333333",
    )
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    path = figures_dir / f"{output_prefix}_success_task_weighted.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_task_coverage(
    domain_table: pd.DataFrame,
    figures_dir: Path,
    dimension_column: str = "category",
    dimension_label: str = "task category",
    output_prefix: str = "task_domain",
) -> Path:
    plot_df = domain_table.sort_values("n_tasks", ascending=False)
    fig, ax = plt.subplots(figsize=(9.5, figure_height(len(plot_df))))
    ax.barh(plot_df[dimension_column], plot_df["n_tasks"])
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.25)
    ax.set_xlabel("Distinct tasks")
    ax.set_ylabel(dimension_label[:1].upper() + dimension_label[1:])
    ax.set_title(f"Number of distinct tasks per {dimension_label}")
    fig.tight_layout()
    path = figures_dir / f"{output_prefix}_task_coverage.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_pass_fail_counts(
    domain_table: pd.DataFrame,
    figures_dir: Path,
    dimension_column: str = "category",
    dimension_label: str = "task category",
    output_prefix: str = "task_domain",
) -> Path:
    plot_df = domain_table.sort_values("n_trajectories", ascending=False).copy()
    plot_df["category_label"] = plot_df.apply(lambda row: category_count_label_multiline(row, dimension_column), axis=1)

    fig, ax = plt.subplots(figsize=(figure_width(len(plot_df)), 7.0))
    ax.bar(plot_df["category_label"], plot_df["pass_count"], label="Pass")
    ax.bar(
        plot_df["category_label"],
        plot_df["fail_count"],
        bottom=plot_df["pass_count"],
        label="Fail",
    )
    ax.grid(axis="y", alpha=0.25)
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    format_category_axis(ax)
    ax.set_xlabel(dimension_label[:1].upper() + dimension_label[1:])
    ax.set_ylabel("Trajectory count")
    ax.set_title(f"Pass/fail trajectories by {dimension_label}")
    ax.legend(frameon=False)
    fig.tight_layout()

    path = figures_dir / f"{output_prefix}_pass_fail_counts.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def autopct_visible(pct: float) -> str:
    return f"{pct:.1f}%" if pct >= 3 else ""


def plot_pass_fail_pie_charts(
    domain_table: pd.DataFrame,
    figures_dir: Path,
    dimension_column: str = "category",
    dimension_label: str = "task category",
    output_prefix: str = "task_domain",
) -> Path:
    plot_df = domain_table.sort_values(
        ["n_trajectories", dimension_column],
        ascending=[False, True],
    ).copy()
    labels = plot_df[dimension_column].tolist()
    colors = plt.get_cmap("tab20").colors[: len(labels)]

    fig, axes = plt.subplots(1, 2, figsize=(13, 8.2))
    legend_handles = None
    for ax, count_column, title in [
        (axes[0], "pass_count", "Passing trajectories"),
        (axes[1], "fail_count", "Failing trajectories"),
    ]:
        total = int(plot_df[count_column].sum())
        wedges, _, _ = ax.pie(
            plot_df[count_column],
            labels=None,
            colors=colors,
            startangle=90,
            counterclock=False,
            autopct=autopct_visible,
            pctdistance=0.72,
            textprops={"fontsize": 10},
        )
        if legend_handles is None:
            legend_handles = wedges
        for autotext in ax.texts:
            if "%" in autotext.get_text():
                autotext.set_fontsize(11)
        ax.set_title(f"{title}\n(n={total:,})", fontsize=14, y=0.92)

    fig.suptitle(f"Distribution of passing and failing trajectories by {dimension_label}", fontsize=16)
    if legend_handles is not None:
        fig.legend(
            legend_handles,
            labels,
            loc="lower center",
            ncol=4,
            frameon=False,
            fontsize=11,
        )
    fig.tight_layout(rect=(0, 0.17, 1, 0.94), w_pad=0.0)
    fig.subplots_adjust(wspace=-0.15)

    path = figures_dir / f"pie_chart_{output_prefix}_pass_fail_distribution.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def format_cell_value(value: float) -> str:
    if abs(value) < 10 and value != int(value):
        return f"{value:,.2f}"
    return f"{value:,.0f}"


def plot_effort_heatmap(
    effort_summary: pd.DataFrame,
    domain_table: pd.DataFrame,
    figures_dir: Path,
    dimension_column: str = "category",
    dimension_label: str = "task category",
    output_prefix: str = "task_domain",
) -> Path | None:
    effort_figures_dir = figures_dir / "effort_vars"
    effort_figures_dir.mkdir(parents=True, exist_ok=True)

    domain_lookup = domain_table.set_index(dimension_column)[["n_tasks", "n_trajectories", "low_task_count"]]
    category_order = ordered_dimension_values(domain_table, dimension_column)
    heatmap = (
        effort_summary.pivot(index=dimension_column, columns="variable_display", values="median")
        .reindex(index=category_order, columns=list(EFFORT_DISPLAY_NAMES.values()))
        .astype(float)
    )
    if heatmap.empty:
        return None

    normalized = heatmap.copy()
    for column in normalized.columns:
        values = normalized[column]
        min_value = values.min(skipna=True)
        max_value = values.max(skipna=True)
        if pd.isna(min_value) or pd.isna(max_value) or min_value == max_value:
            normalized[column] = np.nan
        else:
            normalized[column] = (values - min_value) / (max_value - min_value)

    labels = [
        f"{category} (tasks={int(domain_lookup.loc[category, 'n_tasks'])}, "
        f"traj={int(domain_lookup.loc[category, 'n_trajectories']):,})"
        f"{'*' if domain_lookup.loc[category, 'low_task_count'] else ''}"
        for category in heatmap.index
    ]

    fig, ax = plt.subplots(figsize=(11.5, figure_height(len(heatmap))))
    cmap = plt.get_cmap("YlOrRd").copy()
    cmap.set_bad("#f2f2f2")
    matrix = np.ma.masked_invalid(normalized.to_numpy(dtype=float))
    image = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1)

    ax.set_xticks(range(len(heatmap.columns)))
    ax.set_xticklabels(heatmap.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Effort variable")
    ax.set_ylabel(dimension_label[:1].upper() + dimension_label[1:])
    ax.set_title(f"Median trajectory effort by {dimension_label}, ordered by task coverage")

    for row_index in range(heatmap.shape[0]):
        for column_index in range(heatmap.shape[1]):
            value = heatmap.iat[row_index, column_index]
            if pd.isna(value):
                continue
            text_color = "white" if normalized.iat[row_index, column_index] > 0.55 else "black"
            ax.text(
                column_index,
                row_index,
                format_cell_value(float(value)),
                ha="center",
                va="center",
                fontsize=7,
                color=text_color,
            )

    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    colorbar.set_label("Column-normalized median")
    fig.tight_layout()

    path = effort_figures_dir / f"heatmap_{output_prefix}_effort_median.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def entity_label(row: pd.Series, group_columns: list[str]) -> str:
    if group_columns == ["model_dir"]:
        return str(row["model_dir"])
    if group_columns == ["scaffold"]:
        return str(row["scaffold"])
    if group_columns == ["scaffold", "model_dir"]:
        return f"{row['scaffold']} / {row['model_dir']}"
    return " / ".join(str(row[column]) for column in group_columns)


def plot_category_pass_rate_heatmap(
    pass_rates: pd.DataFrame,
    group_columns: list[str],
    domain_table: pd.DataFrame,
    title: str,
    path: Path,
    dimension_column: str = "category",
    dimension_label: str = "task category",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    work = pass_rates.copy()
    work["entity"] = work.apply(lambda row: entity_label(row, group_columns), axis=1)
    entity_order = (
        work[["entity", "total_pass_rate", "total_trajectories"]]
        .drop_duplicates()
        .sort_values(["total_pass_rate", "total_trajectories", "entity"], ascending=[False, False, True])
        ["entity"]
        .tolist()
    )
    category_order = ordered_dimension_values(domain_table, dimension_column)

    heatmap = (
        work.pivot(index="entity", columns=dimension_column, values="pass_rate")
        .reindex(index=entity_order, columns=category_order)
        .astype(float)
    )
    counts = (
        work.pivot(index="entity", columns=dimension_column, values="n_trajectories")
        .reindex(index=entity_order, columns=category_order)
        .fillna(0)
        .astype(int)
    )

    row_count = len(heatmap)
    col_count = len(heatmap.columns)
    fig_width = max(12.0, min(19.0, 4.0 + col_count * 0.8))
    fig_height = max(5.5, min(30.0, 1.8 + row_count * 0.32))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad("#f2f2f2")
    matrix = np.ma.masked_invalid(heatmap.to_numpy(dtype=float))
    image = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1)

    ax.set_xticks(range(col_count))
    ax.set_xticklabels(heatmap.columns, rotation=40, ha="right")
    ax.set_yticks(range(row_count))
    ax.set_yticklabels(heatmap.index, fontsize=7 if row_count > 30 else 9)
    ax.set_xlabel(dimension_label[:1].upper() + dimension_label[1:])
    ax.set_ylabel(" / ".join(group_columns))
    ax.set_title(title)

    ax.set_xticks(np.arange(-0.5, col_count, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, row_count, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.8)
    ax.tick_params(which="minor", bottom=False, left=False)

    if row_count <= 35:
        for row_index, entity in enumerate(heatmap.index):
            for column_index, category in enumerate(heatmap.columns):
                rate = heatmap.loc[entity, category]
                count = counts.loc[entity, category]
                if pd.isna(rate) or count == 0:
                    continue
                text_color = "white" if rate < 0.35 else "black"
                ax.text(
                    column_index,
                    row_index,
                    f"{rate:.2f}\nn={count}",
                    ha="center",
                    va="center",
                    fontsize=5.5 if row_count > 20 else 6.5,
                    color=text_color,
                )

    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    colorbar.set_label("Pass rate")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_scaffold_category_composition(
    scaffold_category_rates: pd.DataFrame,
    domain_table: pd.DataFrame,
    path: Path,
    dimension_column: str = "category",
    dimension_label: str = "task category",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    composition = scaffold_category_rates.copy()
    composition["trajectory_share"] = composition["n_trajectories"] / composition["total_trajectories"]
    category_order = ordered_dimension_values(domain_table, dimension_column)
    scaffold_order = (
        composition[["scaffold", "total_trajectories"]]
        .drop_duplicates()
        .sort_values(["total_trajectories", "scaffold"], ascending=[False, True])
        ["scaffold"]
        .tolist()
    )
    shares = (
        composition.pivot(index="scaffold", columns=dimension_column, values="trajectory_share")
        .reindex(index=scaffold_order, columns=category_order)
        .fillna(0)
    )

    fig, ax = plt.subplots(figsize=(12.5, max(5.2, 1.4 + len(shares) * 0.38)))
    left = np.zeros(len(shares))
    colors = plt.get_cmap("tab20").colors
    for index, category in enumerate(category_order):
        values = shares[category].to_numpy(dtype=float)
        ax.barh(shares.index, values, left=left, label=category, color=colors[index % len(colors)])
        left += values

    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.grid(axis="x", alpha=0.25)
    ax.set_xlabel("Share of scaffold trajectories")
    ax.set_ylabel("Scaffold")
    ax.set_title(f"{dimension_label[:1].upper() + dimension_label[1:]} composition by scaffold")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4, frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_category_difficulty_composition(
    composition: pd.DataFrame,
    domain_table: pd.DataFrame,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    category_order = ordered_dimension_values(domain_table, "category")
    difficulty_order = [value for value in DIFFICULTY_ORDER if value in composition["difficulty"].unique()]
    shares = (
        composition.pivot(index="category", columns="difficulty", values="trajectory_share_within_category")
        .reindex(index=category_order, columns=difficulty_order)
        .fillna(0)
    )

    fig, ax = plt.subplots(figsize=(12.5, max(5.2, 1.4 + len(shares) * 0.38)))
    left = np.zeros(len(shares))
    colors = {"easy": "#4daf4a", "medium": "#ffbf50", "hard": "#e15759"}
    for difficulty in difficulty_order:
        values = shares[difficulty].to_numpy(dtype=float)
        ax.barh(shares.index, values, left=left, label=difficulty, color=colors.get(difficulty))
        left += values

    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.grid(axis="x", alpha=0.25)
    ax.set_xlabel("Share of category trajectories")
    ax.set_ylabel("Task category")
    ax.set_title("Task difficulty composition by category")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_category_difficulty_pass_rate_heatmap(
    pass_rates: pd.DataFrame,
    domain_table: pd.DataFrame,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    category_order = ordered_dimension_values(domain_table, "category")
    difficulty_order = [value for value in DIFFICULTY_ORDER if value in pass_rates["difficulty"].unique()]
    category_lookup = domain_table.set_index("category")[["n_tasks", "n_trajectories", "low_task_count"]]

    heatmap = (
        pass_rates.pivot(index="category", columns="difficulty", values="pass_rate")
        .reindex(index=category_order, columns=difficulty_order)
        .astype(float)
    )
    counts = (
        pass_rates.pivot(index="category", columns="difficulty", values="n_trajectories")
        .reindex(index=category_order, columns=difficulty_order)
        .fillna(0)
        .astype(int)
    )
    row_labels = [
        f"{category} (tasks={int(category_lookup.loc[category, 'n_tasks'])}, "
        f"traj={int(category_lookup.loc[category, 'n_trajectories']):,})"
        f"{'*' if category_lookup.loc[category, 'low_task_count'] else ''}"
        for category in heatmap.index
    ]

    fig, ax = plt.subplots(figsize=(10.5, figure_height(len(heatmap))))
    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad("#f2f2f2")
    matrix = np.ma.masked_invalid(heatmap.to_numpy(dtype=float))
    image = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1)

    ax.set_xticks(range(len(difficulty_order)))
    ax.set_xticklabels(difficulty_order, rotation=30, ha="right")
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=8 if len(row_labels) > 18 else 9)
    ax.set_xlabel("Task difficulty")
    ax.set_ylabel("Task category")
    ax.set_title("Pass rate by task category and difficulty")
    ax.set_xticks(np.arange(-0.5, len(difficulty_order), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(row_labels), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.0)
    ax.tick_params(which="minor", bottom=False, left=False)

    for row_index, category in enumerate(heatmap.index):
        for column_index, difficulty in enumerate(difficulty_order):
            rate = heatmap.loc[category, difficulty]
            count = counts.loc[category, difficulty]
            if pd.isna(rate) or count == 0:
                continue
            text_color = "white" if rate < 0.35 else "black"
            ax.text(
                column_index,
                row_index,
                f"{rate:.2f}\nn={count}",
                ha="center",
                va="center",
                fontsize=6.5,
                color=text_color,
            )

    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    colorbar.set_label("Pass rate")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def write_model_scaffold_outputs(
    out_dir: Path,
    figures_dir: Path,
    domain_table: pd.DataFrame,
    model_category_rates: pd.DataFrame,
    scaffold_category_rates: pd.DataFrame,
    provider_category_rates: pd.DataFrame,
    source_category_rates: pd.DataFrame,
    dimension_column: str = "category",
    dimension_label: str = "task category",
    file_label: str = "category",
) -> list[Path]:
    tables_dir = out_dir / "model_scaffold"
    tables_dir.mkdir(parents=True, exist_ok=True)

    model_table = model_category_rates[
        ["model_dir", dimension_column, "n_tasks", "n_trajectories", "pass_count", "fail_count", "pass_rate"]
    ]
    scaffold_table = scaffold_category_rates[
        ["scaffold", dimension_column, "n_tasks", "n_trajectories", "pass_count", "fail_count", "pass_rate"]
    ]
    provider_table = provider_category_rates[
        ["model_provider", dimension_column, "n_tasks", "n_trajectories", "pass_count", "fail_count", "pass_rate"]
    ]
    source_table = source_category_rates[
        ["model_source", dimension_column, "n_tasks", "n_trajectories", "pass_count", "fail_count", "pass_rate"]
    ]

    model_table.to_csv(tables_dir / f"model_{file_label}_pass_rates.csv", index=False)
    scaffold_table.to_csv(tables_dir / f"scaffold_{file_label}_pass_rates.csv", index=False)
    provider_table.to_csv(tables_dir / f"provider_{file_label}_pass_rates.csv", index=False)
    source_table.to_csv(tables_dir / f"source_{file_label}_pass_rates.csv", index=False)

    figure_base = figures_dir / "model_scaffold"
    figure_base.mkdir(parents=True, exist_ok=True)
    paths = [
        plot_category_pass_rate_heatmap(
            model_category_rates,
            ["model_dir"],
            domain_table,
            f"{dimension_label[:1].upper() + dimension_label[1:]}-stratified pass rates by model",
            figure_base / f"heatmap_model_{file_label}_pass_rates.png",
            dimension_column,
            dimension_label,
        ),
        plot_category_pass_rate_heatmap(
            scaffold_category_rates,
            ["scaffold"],
            domain_table,
            f"{dimension_label[:1].upper() + dimension_label[1:]}-stratified pass rates by scaffold",
            figure_base / f"heatmap_scaffold_{file_label}_pass_rates.png",
            dimension_column,
            dimension_label,
        ),
        plot_category_pass_rate_heatmap(
            provider_category_rates,
            ["model_provider"],
            domain_table,
            f"{dimension_label[:1].upper() + dimension_label[1:]}-stratified pass rates by model provider",
            figure_base / f"heatmap_provider_{file_label}_pass_rates.png",
            dimension_column,
            dimension_label,
        ),
        plot_category_pass_rate_heatmap(
            source_category_rates,
            ["model_source"],
            domain_table,
            f"{dimension_label[:1].upper() + dimension_label[1:]}-stratified pass rates by model source type",
            figure_base / f"heatmap_source_{file_label}_pass_rates.png",
            dimension_column,
            dimension_label,
        ),
        plot_scaffold_category_composition(
            scaffold_category_rates,
            domain_table,
            figures_dir / f"stacked_scaffold_{file_label}_composition.png",
            dimension_column,
            dimension_label,
        ),
    ]
    return paths


def plot_domain_figures(
    domain_table: pd.DataFrame,
    effort_summary: pd.DataFrame,
    figures_dir: Path,
    dimension_column: str = "category",
    dimension_label: str = "task category",
    output_prefix: str = "task_domain",
) -> list[Path]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    effort_heatmap = plot_effort_heatmap(
        effort_summary,
        domain_table,
        figures_dir,
        dimension_column,
        dimension_label,
        output_prefix,
    )
    return [
        plot_task_weighted_success(domain_table, figures_dir, dimension_column, dimension_label, output_prefix),
        plot_pass_fail_counts(domain_table, figures_dir, dimension_column, dimension_label, output_prefix),
        plot_pass_fail_pie_charts(domain_table, figures_dir, dimension_column, dimension_label, output_prefix),
        plot_task_coverage(domain_table, figures_dir, dimension_column, dimension_label, output_prefix),
        *([effort_heatmap] if effort_heatmap is not None else []),
    ]


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks(args.tasks)
    trajectories = load_trajectories(args.trajectories)
    domain_table = build_domain_table(trajectories, tasks)
    effort_summary = build_effort_summary(trajectories, tasks)
    difficulty_table = build_domain_table(trajectories, tasks, "difficulty")
    difficulty_effort_summary = build_effort_summary(trajectories, tasks, "difficulty")
    model_category_rates = build_stratified_pass_rates(trajectories, tasks, ["model_dir"])
    scaffold_category_rates = build_stratified_pass_rates(trajectories, tasks, ["scaffold"])
    provider_category_rates = build_stratified_pass_rates(trajectories, tasks, ["model_provider"])
    source_category_rates = build_stratified_pass_rates(trajectories, tasks, ["model_source"])
    model_difficulty_rates = build_stratified_pass_rates(trajectories, tasks, ["model_dir"], "difficulty")
    scaffold_difficulty_rates = build_stratified_pass_rates(trajectories, tasks, ["scaffold"], "difficulty")
    provider_difficulty_rates = build_stratified_pass_rates(trajectories, tasks, ["model_provider"], "difficulty")
    source_difficulty_rates = build_stratified_pass_rates(trajectories, tasks, ["model_source"], "difficulty")
    category_difficulty_rates = build_category_difficulty_pass_rates(trajectories, tasks)
    category_difficulty_composition = build_category_difficulty_composition(category_difficulty_rates)

    category_out_dir = args.out / "category"
    difficulty_out_dir = args.out / "difficulty"
    category_difficulty_out_dir = args.out / "category_difficulty"
    category_out_dir.mkdir(parents=True, exist_ok=True)
    difficulty_out_dir.mkdir(parents=True, exist_ok=True)
    category_difficulty_out_dir.mkdir(parents=True, exist_ok=True)

    out_path = category_out_dir / "task_domain_outcome.csv"
    effort_out_path = category_out_dir / "task_domain_effort_summary.csv"
    difficulty_out_path = difficulty_out_dir / "task_difficulty_outcome.csv"
    difficulty_effort_out_path = difficulty_out_dir / "task_difficulty_effort_summary.csv"
    category_difficulty_out_path = category_difficulty_out_dir / "category_difficulty.csv"
    domain_table.drop(columns=["low_task_count"]).to_csv(out_path, index=False)
    effort_summary.drop(columns=["complete_case_count"]).to_csv(effort_out_path, index=False)
    difficulty_table.drop(columns=["low_task_count"]).to_csv(difficulty_out_path, index=False)
    difficulty_effort_summary.drop(columns=["complete_case_count"]).to_csv(difficulty_effort_out_path, index=False)
    category_difficulty_rates[["category", "difficulty", "n_tasks", "n_trajectories", "pass_count", "fail_count", "pass_rate"]].to_csv(category_difficulty_out_path, index=False)
    category_figures_dir = args.figures_dir / "category"
    difficulty_figures_dir = args.figures_dir / "difficulty"
    category_difficulty_figures_dir = args.figures_dir / "category_difficulty"
    figure_paths = plot_domain_figures(domain_table, effort_summary, category_figures_dir)
    model_scaffold_figure_paths = write_model_scaffold_outputs(
        category_out_dir,
        category_figures_dir,
        domain_table,
        model_category_rates,
        scaffold_category_rates,
        provider_category_rates,
        source_category_rates,
    )
    difficulty_figure_paths = plot_domain_figures(
        difficulty_table,
        difficulty_effort_summary,
        difficulty_figures_dir,
        "difficulty",
        "task difficulty",
        "task_difficulty",
    )
    difficulty_model_scaffold_figure_paths = write_model_scaffold_outputs(
        difficulty_out_dir,
        difficulty_figures_dir,
        difficulty_table,
        model_difficulty_rates,
        scaffold_difficulty_rates,
        provider_difficulty_rates,
        source_difficulty_rates,
        "difficulty",
        "task difficulty",
        "difficulty",
    )
    category_difficulty_figure_paths = [
        plot_category_difficulty_composition(
            category_difficulty_composition,
            domain_table,
            category_difficulty_figures_dir / "stacked_category_difficulty_composition.png",
        ),
        plot_category_difficulty_pass_rate_heatmap(
            category_difficulty_rates,
            domain_table,
            category_difficulty_figures_dir / "heatmap_category_difficulty_pass_rates.png",
        ),
    ]
    print(f"Wrote {out_path}")
    print(f"Wrote {effort_out_path}")
    print(f"Wrote {difficulty_out_path}")
    print(f"Wrote {difficulty_effort_out_path}")
    print(f"Wrote {category_difficulty_out_path}")
    print(f"Wrote {len(figure_paths)} category figures to {category_figures_dir}")
    print(f"Wrote {len(model_scaffold_figure_paths)} category model/scaffold figures to {category_figures_dir / 'model_scaffold'}")
    print(f"Wrote {len(difficulty_figure_paths)} difficulty figures to {difficulty_figures_dir}")
    print(
        f"Wrote {len(difficulty_model_scaffold_figure_paths)} difficulty model/scaffold figures "
        f"to {difficulty_figures_dir / 'model_scaffold'}"
    )
    print(f"Wrote {len(category_difficulty_figure_paths)} category/difficulty figures to {category_difficulty_figures_dir}")


if __name__ == "__main__":
    main()
