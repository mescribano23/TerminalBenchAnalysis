#!/usr/bin/env python3
"""Task-domain success table and simple figures.

Outputs:
- data/processed_live/task_mining/task_domain_outcome.csv
- data/processed_live/task_mining/task_domain_effort_summary.csv
- reports/category_analysis/task_domain_success_task_weighted.png
- reports/category_analysis/task_domain_pass_fail_counts.png
- reports/category_analysis/task_domain_task_coverage.png
- reports/category_analysis/pie_chart_task_domain_pass_fail_distribution.png
- reports/category_analysis/effort_vars/task_domain_effort_*.png
- reports/category_analysis/effort_vars/heatmap_task_domain_effort_median.png
- data/processed_live/task_mining/model_scaffold/*.csv
- reports/category_analysis/model_scaffold/*.png
- reports/category_analysis/stacked_scaffold_category_composition.png
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


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
DATA_PROCESSED_LIVE_DIR = DATA_DIR / "processed_live"
REPORTS_DIR = REPO_ROOT / "reports"

TRAJECTORY_DEFAULT = DATA_PROCESSED_LIVE_DIR / "trajectory_summary.csv"
TASKS_DEFAULT = DATA_DIR / "raw" / "terminal_bench_2_tasks_current.json"
OUT_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining"
FIGURES_DEFAULT = REPORTS_DIR / "category_analysis"

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
    required = {"id", "category"}
    missing = required.difference(task_df.columns)
    if missing:
        raise ValueError(f"{path} is missing required task fields: {', '.join(sorted(missing))}")
    return task_df[["id", "category"]].rename(columns={"id": "task_name"})


def model_source_type(row: pd.Series) -> str:
    model_text = " ".join(
        str(row.get(column, "")).lower().replace("_", "-")
        for column in ["model_dir", "model_name", "leaderboard_model"]
    )
    if any(keyword in model_text for keyword in OPEN_SOURCE_MODEL_KEYWORDS):
        return "open_source_or_open_weight"
    return "closed_source"


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


def build_domain_table(trajectories: pd.DataFrame, tasks: pd.DataFrame) -> pd.DataFrame:
    df = trajectories.merge(tasks, on="task_name", how="left", validate="many_to_one")
    missing = df["category"].isna()
    if missing.any():
        missing_tasks = sorted(df.loc[missing, "task_name"].dropna().unique().tolist())
        preview = ", ".join(missing_tasks[:8])
        raise ValueError(f"Task metadata missing for {missing.sum()} trajectory rows. Examples: {preview}")

    task_rates = (
        df.groupby(["category", "task_name"], as_index=False)
        .agg(
            task_trajectory_count=("passed", "size"),
            task_pass_count=("passed", "sum"),
            task_pass_rate=("passed", "mean"),
        )
    )

    rows: list[dict[str, Any]] = []
    for category, group in df.groupby("category", sort=False):
        n_trajectories = int(group.shape[0])
        pass_count = int(group["passed"].sum())
        fail_count = n_trajectories - pass_count
        pass_rate = pass_count / n_trajectories if n_trajectories else None

        category_task_rates = task_rates.loc[task_rates["category"] == category, "task_pass_rate"]
        n_tasks = int(category_task_rates.shape[0])
        task_mean_pass_rate = float(category_task_rates.mean()) if n_tasks else None

        rows.append(
            {
                "category": category,
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
    return out.sort_values(
        ["n_tasks", "n_trajectories", "category"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def build_effort_summary(trajectories: pd.DataFrame, tasks: pd.DataFrame) -> pd.DataFrame:
    df = trajectories.merge(tasks, on="task_name", how="left", validate="many_to_one")
    missing = df["category"].isna()
    if missing.any():
        missing_tasks = sorted(df.loc[missing, "task_name"].dropna().unique().tolist())
        preview = ", ".join(missing_tasks[:8])
        raise ValueError(f"Task metadata missing for {missing.sum()} trajectory rows. Examples: {preview}")

    rows: list[dict[str, Any]] = []
    for category, group in df.groupby("category", sort=False):
        for variable, display_name in EFFORT_DISPLAY_NAMES.items():
            if variable not in group.columns:
                continue
            values = group[variable].dropna()
            rows.append(
                {
                    "category": category,
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

    return pd.DataFrame(rows).sort_values(["variable", "median", "category"], ascending=[True, False, True])


def merge_task_categories(trajectories: pd.DataFrame, tasks: pd.DataFrame) -> pd.DataFrame:
    df = trajectories.merge(tasks, on="task_name", how="left", validate="many_to_one")
    missing = df["category"].isna()
    if missing.any():
        missing_tasks = sorted(df.loc[missing, "task_name"].dropna().unique().tolist())
        preview = ", ".join(missing_tasks[:8])
        raise ValueError(f"Task metadata missing for {missing.sum()} trajectory rows. Examples: {preview}")
    return df


def build_stratified_pass_rates(
    trajectories: pd.DataFrame,
    tasks: pd.DataFrame,
    group_columns: list[str],
) -> pd.DataFrame:
    df = merge_task_categories(trajectories, tasks)
    rows = (
        df.groupby([*group_columns, "category"], as_index=False)
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

    sort_columns = [*group_columns, "category"]
    return rows.sort_values(sort_columns).reset_index(drop=True)


def figure_height(row_count: int) -> float:
    return max(4.8, 1.6 + row_count * 0.34)


def figure_width(column_count: int) -> float:
    return max(10.5, min(22.0, 4.0 + column_count * 0.8))


def category_count_label(row: pd.Series) -> str:
    return (
        f"{row['category']} "
        f"(tasks={int(row['n_tasks'])}, traj={int(row['n_trajectories']):,})"
        f"{'*' if row['low_task_count'] else ''}"
    )


def category_count_label_multiline(row: pd.Series) -> str:
    return (
        f"{row['category']}\n"
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


def plot_task_weighted_success(domain_table: pd.DataFrame, figures_dir: Path) -> Path:
    plot_df = domain_table.sort_values("task_mean_pass_rate", ascending=False).copy()
    plot_df["category_label"] = plot_df.apply(category_count_label, axis=1)
    fig, ax = plt.subplots(figsize=(9.5, figure_height(len(plot_df))))
    ax.barh(plot_df["category_label"], plot_df["task_mean_pass_rate"])
    ax.invert_yaxis()
    format_success_rate_axis(ax)
    ax.set_xlabel("Task-weighted pass rate")
    ax.set_ylabel("Category")
    ax.set_title("Task-weighted pass rate by task category")
    note = (
        "Note: Bars show the mean pass rate across tasks.\n"
        "Labels show distinct tasks and trajectories; * marks categories with fewer than five tasks."
    )
    fig.text(
        0.01,
        0.015,
        textwrap.fill(note, width=120),
        fontsize=8.5,
        color="#333333",
    )
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    path = figures_dir / "task_domain_success_task_weighted.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_task_coverage(domain_table: pd.DataFrame, figures_dir: Path) -> Path:
    plot_df = domain_table.sort_values("n_tasks", ascending=False)
    fig, ax = plt.subplots(figsize=(9.5, figure_height(len(plot_df))))
    ax.barh(plot_df["category"], plot_df["n_tasks"])
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.25)
    ax.set_xlabel("Distinct tasks")
    ax.set_ylabel("Category")
    ax.set_title("Number of distinct tasks per category")
    fig.tight_layout()
    path = figures_dir / "task_domain_task_coverage.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_pass_fail_counts(domain_table: pd.DataFrame, figures_dir: Path) -> Path:
    plot_df = domain_table.sort_values("n_trajectories", ascending=False).copy()
    plot_df["category_label"] = plot_df.apply(category_count_label_multiline, axis=1)

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
    ax.set_xlabel("Category")
    ax.set_ylabel("Trajectory count")
    ax.set_title("Pass/fail trajectories by task category")
    ax.legend(frameon=False)
    fig.tight_layout()

    path = figures_dir / "task_domain_pass_fail_counts.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def autopct_visible(pct: float) -> str:
    return f"{pct:.1f}%" if pct >= 3 else ""


def plot_pass_fail_pie_charts(domain_table: pd.DataFrame, figures_dir: Path) -> Path:
    plot_df = domain_table.sort_values(
        ["n_trajectories", "category"],
        ascending=[False, True],
    ).copy()
    labels = plot_df["category"].tolist()
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

    fig.suptitle("Distribution of passing and failing trajectories by task category", fontsize=16)
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

    path = figures_dir / "pie_chart_task_domain_pass_fail_distribution.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def slugify(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "_" for char in value]
    return "_".join("".join(chars).strip("_").split("_")) or "unknown"


def format_cell_value(value: float) -> str:
    if abs(value) < 10 and value != int(value):
        return f"{value:,.2f}"
    return f"{value:,.0f}"


def plot_effort_by_category(
    effort_summary: pd.DataFrame,
    domain_table: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    paths: list[Path] = []
    effort_figures_dir = figures_dir / "effort_vars"
    effort_figures_dir.mkdir(parents=True, exist_ok=True)
    domain_lookup = domain_table.set_index("category")[["n_tasks", "n_trajectories", "low_task_count"]].rename(
        columns={"n_trajectories": "label_n_trajectories"}
    )
    for variable, display_name in EFFORT_DISPLAY_NAMES.items():
        subset = effort_summary[effort_summary["variable"] == variable].dropna(subset=["median"]).copy()
        if subset.empty:
            continue
        subset = subset.merge(domain_lookup, left_on="category", right_index=True, how="left")
        subset = subset.sort_values("median", ascending=False)
        subset["category_label"] = subset.apply(
            lambda row: (
                f"{row['category']} "
                f"(tasks={int(row['n_tasks'])}, traj={int(row['label_n_trajectories']):,})"
                f"{'*' if row['low_task_count'] else ''}"
            ),
            axis=1,
        )

        fig, ax = plt.subplots(figsize=(9.5, figure_height(len(subset))))
        ax.barh(subset["category_label"], subset["median"])
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.25)
        ax.set_xlabel(f"Median {display_name.lower()}")
        ax.set_ylabel("Category")
        ax.set_title(f"Median {display_name.lower()} by task category")
        fig.tight_layout()

        path = effort_figures_dir / f"task_domain_effort_{slugify(variable)}.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        paths.append(path)
    return paths


def plot_effort_heatmap(
    effort_summary: pd.DataFrame,
    domain_table: pd.DataFrame,
    figures_dir: Path,
) -> Path | None:
    effort_figures_dir = figures_dir / "effort_vars"
    effort_figures_dir.mkdir(parents=True, exist_ok=True)

    domain_lookup = domain_table.set_index("category")[["n_tasks", "n_trajectories", "low_task_count"]]
    category_order = domain_table.sort_values(
        ["n_tasks", "n_trajectories", "category"],
        ascending=[False, False, True],
    )["category"].tolist()
    heatmap = (
        effort_summary.pivot(index="category", columns="variable_display", values="median")
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
    ax.set_ylabel("Category")
    ax.set_title("Median trajectory effort by task category, ordered by task coverage")

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

    path = effort_figures_dir / "heatmap_task_domain_effort_median.png"
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
    category_order = domain_table.sort_values(
        ["n_tasks", "n_trajectories", "category"],
        ascending=[False, False, True],
    )["category"].tolist()

    heatmap = (
        work.pivot(index="entity", columns="category", values="pass_rate")
        .reindex(index=entity_order, columns=category_order)
        .astype(float)
    )
    counts = (
        work.pivot(index="entity", columns="category", values="n_trajectories")
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
    ax.set_xlabel("Task category")
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
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    composition = scaffold_category_rates.copy()
    composition["trajectory_share"] = composition["n_trajectories"] / composition["total_trajectories"]
    category_order = domain_table.sort_values(
        ["n_tasks", "n_trajectories", "category"],
        ascending=[False, False, True],
    )["category"].tolist()
    scaffold_order = (
        composition[["scaffold", "total_trajectories"]]
        .drop_duplicates()
        .sort_values(["total_trajectories", "scaffold"], ascending=[False, True])
        ["scaffold"]
        .tolist()
    )
    shares = (
        composition.pivot(index="scaffold", columns="category", values="trajectory_share")
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
    ax.set_title("Task category composition by scaffold")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4, frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
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
) -> list[Path]:
    tables_dir = out_dir / "model_scaffold"
    tables_dir.mkdir(parents=True, exist_ok=True)

    model_category_rates.to_csv(tables_dir / "model_category_pass_rates.csv", index=False)
    scaffold_category_rates.to_csv(tables_dir / "scaffold_category_pass_rates.csv", index=False)
    provider_category_rates.to_csv(tables_dir / "provider_category_pass_rates.csv", index=False)
    source_category_rates.to_csv(tables_dir / "source_category_pass_rates.csv", index=False)

    figure_base = figures_dir / "model_scaffold"
    figure_base.mkdir(parents=True, exist_ok=True)
    paths = [
        plot_category_pass_rate_heatmap(
            model_category_rates,
            ["model_dir"],
            domain_table,
            "Category-stratified pass rates by model",
            figure_base / "heatmap_model_category_pass_rates.png",
        ),
        plot_category_pass_rate_heatmap(
            scaffold_category_rates,
            ["scaffold"],
            domain_table,
            "Category-stratified pass rates by scaffold",
            figure_base / "heatmap_scaffold_category_pass_rates.png",
        ),
        plot_category_pass_rate_heatmap(
            provider_category_rates,
            ["model_provider"],
            domain_table,
            "Category-stratified pass rates by model provider",
            figure_base / "heatmap_provider_category_pass_rates.png",
        ),
        plot_category_pass_rate_heatmap(
            source_category_rates,
            ["model_source"],
            domain_table,
            "Category-stratified pass rates by model source type",
            figure_base / "heatmap_source_category_pass_rates.png",
        ),
        plot_scaffold_category_composition(
            scaffold_category_rates,
            domain_table,
            figures_dir / "stacked_scaffold_category_composition.png",
        ),
    ]
    return paths


def plot_domain_figures(
    domain_table: pd.DataFrame,
    effort_summary: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    effort_heatmap = plot_effort_heatmap(effort_summary, domain_table, figures_dir)
    return [
        plot_task_weighted_success(domain_table, figures_dir),
        plot_pass_fail_counts(domain_table, figures_dir),
        plot_pass_fail_pie_charts(domain_table, figures_dir),
        plot_task_coverage(domain_table, figures_dir),
        *plot_effort_by_category(effort_summary, domain_table, figures_dir),
        *([effort_heatmap] if effort_heatmap is not None else []),
    ]


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks(args.tasks)
    trajectories = load_trajectories(args.trajectories)
    domain_table = build_domain_table(trajectories, tasks)
    effort_summary = build_effort_summary(trajectories, tasks)
    model_category_rates = build_stratified_pass_rates(trajectories, tasks, ["model_dir"])
    scaffold_category_rates = build_stratified_pass_rates(trajectories, tasks, ["scaffold"])
    provider_category_rates = build_stratified_pass_rates(trajectories, tasks, ["model_provider"])
    source_category_rates = build_stratified_pass_rates(trajectories, tasks, ["model_source"])

    out_path = args.out / "task_domain_outcome.csv"
    effort_out_path = args.out / "task_domain_effort_summary.csv"
    domain_table.to_csv(out_path, index=False)
    effort_summary.to_csv(effort_out_path, index=False)
    figure_paths = plot_domain_figures(domain_table, effort_summary, args.figures_dir)
    model_scaffold_figure_paths = write_model_scaffold_outputs(
        args.out,
        args.figures_dir,
        domain_table,
        model_category_rates,
        scaffold_category_rates,
        provider_category_rates,
        source_category_rates,
    )
    print(f"Wrote {out_path}")
    print(f"Wrote {effort_out_path}")
    print(f"Wrote {len(figure_paths)} figures to {args.figures_dir}")
    print(f"Wrote {len(model_scaffold_figure_paths)} model/scaffold figures to {args.figures_dir / 'model_scaffold'}")


if __name__ == "__main__":
    main()
