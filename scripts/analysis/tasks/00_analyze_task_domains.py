#!/usr/bin/env python3
"""Task-domain success table and simple figures.

Outputs:
- data/processed_live/task_mining/category/task_domain_outcome.csv
- data/processed_live/task_mining/category/task_domain_effort_summary.csv
- data/processed_live/task_mining/difficulty/task_difficulty_outcome.csv
- data/processed_live/task_mining/rq2_1_difficulty_significance.csv
- data/processed_live/task_mining/difficulty/task_difficulty_effort_summary.csv
- data/processed_live/task_mining/difficulty/task_difficulty_token_alignment_summary.csv
- data/processed_live/task_mining/difficulty/task_difficulty_token_alignment_by_task.csv
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
from scipy.stats import spearmanr

from scripts.benchmark_paths import find_repo_root
from scripts.analysis.plot_style import (
    FAIL_COLOR,
    HEATMAP_DPI,
    LOW_GOOD_CMAP,
    PASS_COLOR,
    colorblind_cmap,
    colorblind_cycle,
    heatmap_text_color,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
DATA_DIR = REPO_ROOT / "data"
DATA_PROCESSED_LIVE_DIR = DATA_DIR / "processed_live"
REPORTS_DIR = REPO_ROOT / "reports"

TRAJECTORY_DEFAULT = DATA_PROCESSED_LIVE_DIR / "longitudinal" / "trajectory_longitudinal.csv"
TASKS_DEFAULT = DATA_DIR / "raw" / "terminal_bench_2_0" / "terminal_bench_2_tasks.json"
OUT_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining"
FIGURES_DEFAULT = REPORTS_DIR / "tasks"
BENCHMARK_VERSION_DEFAULT = "2.0"

ENTITY_COLUMNS = {"scaffold", "model_dir"}
MODEL_META_COLUMNS = {"leaderboard_model", "leaderboard_model_organization", "model_name"}
OUTCOME_COLUMNS = {"task_name", "reward_outcome", "outcome", "reward"}
BALANCING_COLUMNS = {"source_submission_id", "benchmark_version"}
EFFORT_DISPLAY_NAMES = {
    "step_count": "Step count",
    "shell_invocation_count": "Shell invocation count",
    "tool_call_count": "Structured tool call count",
    "total_tokens": "Total tokens",
    "duration_seconds": "Duration seconds",
    "cost_usd_positive": "Positive cost USD",
}
EFFORT_HEATMAP_LABELS = {
    "Step count": "Steps",
    "Shell invocation count": "Shell calls",
    "Structured tool call count": "Tool calls",
    "Total tokens": "Tokens",
    "Duration seconds": "Duration",
    "Positive cost USD": "Cost",
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
    parser.add_argument("--benchmark-version", default=BENCHMARK_VERSION_DEFAULT)
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
        usecols=lambda column: column
        in OUTCOME_COLUMNS | EFFORT_SOURCE_COLUMNS | ENTITY_COLUMNS | MODEL_META_COLUMNS | BALANCING_COLUMNS,
    )
    if "task_name" not in df.columns:
        raise ValueError(f"{path} must contain task_name.")
    if "benchmark_version" in df.columns:
        df["benchmark_version"] = df["benchmark_version"].astype(str)

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
    if "source_submission_id" in df.columns:
        columns.append("source_submission_id")
    if "benchmark_version" in df.columns:
        columns.append("benchmark_version")
    columns.extend(column for column in EFFORT_DISPLAY_NAMES if column in df.columns)
    return df[columns]


def filter_benchmark_version(df: pd.DataFrame, benchmark_version: str | None) -> pd.DataFrame:
    if not benchmark_version:
        return df
    if "benchmark_version" not in df.columns:
        raise ValueError("Balanced RQ2 analysis requires benchmark_version in the trajectory table.")
    subset = df[df["benchmark_version"].astype(str).eq(str(benchmark_version))].copy()
    if subset.empty:
        raise ValueError(f"No trajectories found for benchmark_version={benchmark_version!r}.")
    return subset


def require_submission_id(df: pd.DataFrame) -> None:
    if "source_submission_id" not in df.columns:
        raise ValueError("Balanced RQ2 analysis requires submission_id in the trajectory table.")
    if df["source_submission_id"].isna().any():
        raise ValueError("Balanced RQ2 analysis found missing submission_id values.")


def submission_task_pass_rates(df: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    require_submission_id(df)
    st_columns = ["source_submission_id", "task_name", *group_columns]
    submission_task = (
        df.groupby(st_columns, as_index=False)
        .agg(
            submission_task_trajectory_count=("passed", "size"),
            submission_task_pass_count=("passed", "sum"),
            submission_task_pass_rate=("passed", "mean"),
        )
    )
    return (
        submission_task.groupby(["task_name", *group_columns], as_index=False)
        .agg(
            task_submission_count=("source_submission_id", "nunique"),
            task_trajectory_count=("submission_task_trajectory_count", "sum"),
            task_pass_count=("submission_task_pass_count", "sum"),
            task_pass_rate=("submission_task_pass_rate", "mean"),
        )
    )


def trajectory_pooled_task_pass_rates(df: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    return (
        df.groupby(["task_name", *group_columns], as_index=False)
        .agg(
            trajectory_pooled_task_trajectory_count=("passed", "size"),
            trajectory_pooled_task_pass_count=("passed", "sum"),
            trajectory_pooled_task_pass_rate=("passed", "mean"),
        )
    )


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

    task_rates = submission_task_pass_rates(df, [dimension_column])
    pooled_task_rates = trajectory_pooled_task_pass_rates(df, [dimension_column])
    pooled_task_rates = pooled_task_rates.rename(
        columns={"trajectory_pooled_task_pass_rate": "trajectory_pooled_task_mean_input"}
    )

    rows: list[dict[str, Any]] = []
    for dimension_value, group in df.groupby(dimension_column, sort=False):
        n_trajectories = int(group.shape[0])
        pass_count = int(group["passed"].sum())
        fail_count = n_trajectories - pass_count
        trajectory_pooled_pass_rate = pass_count / n_trajectories if n_trajectories else None

        dimension_task_rates = task_rates.loc[task_rates[dimension_column] == dimension_value]
        dimension_pooled_task_rates = pooled_task_rates.loc[pooled_task_rates[dimension_column] == dimension_value]
        n_tasks = int(dimension_task_rates["task_name"].nunique())
        task_mean_pass_rate = (
            float(dimension_task_rates["task_pass_rate"].mean()) if n_tasks else None
        )
        trajectory_pooled_task_mean_pass_rate = (
            float(dimension_pooled_task_rates["trajectory_pooled_task_mean_input"].mean()) if n_tasks else None
        )

        rows.append(
            {
                dimension_column: dimension_value,
                "n_tasks": n_tasks,
                "n_trajectories": n_trajectories,
                "n_submission_task_combinations": int(dimension_task_rates["task_submission_count"].sum()),
                "pass_count": pass_count,
                "fail_count": fail_count,
                "pass_rate": task_mean_pass_rate,
                "task_mean_pass_rate": task_mean_pass_rate,
                "trajectory_pooled_pass_rate": trajectory_pooled_pass_rate,
                "trajectory_pooled_task_mean_pass_rate": trajectory_pooled_task_mean_pass_rate,
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


def build_rq2_1_difficulty_significance(
    trajectories: pd.DataFrame,
    tasks: pd.DataFrame,
) -> pd.DataFrame:
    df = trajectories.merge(tasks, on="task_name", how="left", validate="many_to_one")
    missing = df["difficulty"].isna()
    if missing.any():
        missing_tasks = sorted(df.loc[missing, "task_name"].dropna().unique().tolist())
        preview = ", ".join(missing_tasks[:8])
        raise ValueError(f"Task difficulty missing for {missing.sum()} trajectory rows. Examples: {preview}")

    task_rates = submission_task_pass_rates(df, ["difficulty"])
    task_rates = task_rates.loc[task_rates["difficulty"].isin(DIFFICULTY_ORDER)].copy()
    task_rates["difficulty_ordinal"] = task_rates["difficulty"].map(
        {difficulty: index + 1 for index, difficulty in enumerate(DIFFICULTY_ORDER)}
    )

    if len(task_rates) < 2:
        rho = np.nan
        p_value = np.nan
    else:
        result = spearmanr(task_rates["difficulty_ordinal"], task_rates["task_pass_rate"])
        rho = float(result.statistic)
        p_value = float(result.pvalue)

    return pd.DataFrame(
        [
            {
                "n_tasks": int(task_rates["task_name"].nunique()),
                "spearman_rho": rho,
                "p_value": p_value,
            }
        ]
    )


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
    for variable, display_name in EFFORT_DISPLAY_NAMES.items():
        if variable not in df.columns:
            continue
        metric_work = df[["source_submission_id", "task_name", dimension_column, variable]].dropna().copy()
        submission_task = (
            metric_work.groupby(["source_submission_id", "task_name", dimension_column], as_index=False)[variable]
            .median()
            .rename(columns={variable: "submission_task_median"})
        )
        task_effort = (
            submission_task.groupby(["task_name", dimension_column], as_index=False)
            .agg(
                task_submission_count=("source_submission_id", "nunique"),
                task_effort=("submission_task_median", "median"),
            )
        )

        for dimension_value, group in df.groupby(dimension_column, sort=False):
            task_values = task_effort.loc[task_effort[dimension_column] == dimension_value]
            values = task_values["task_effort"].dropna()
            trajectory_values = group[variable].dropna()
            rows.append(
                {
                    dimension_column: dimension_value,
                    "variable": variable,
                    "variable_display": display_name,
                    "n_trajectories": int(group.shape[0]),
                    "complete_case_count": int(trajectory_values.shape[0]),
                    "n_tasks": int(task_values["task_name"].nunique()),
                    "n_submission_task_combinations": int(task_values["task_submission_count"].sum()),
                    "median": float(values.median()) if len(values) else None,
                    "mean": float(values.mean()) if len(values) else None,
                    "p75": float(values.quantile(0.75)) if len(values) else None,
                    "p90": float(values.quantile(0.90)) if len(values) else None,
                    "max": float(values.max()) if len(values) else None,
                    "trajectory_level_median": float(trajectory_values.median()) if len(trajectory_values) else None,
                    "trajectory_level_mean": float(trajectory_values.mean()) if len(trajectory_values) else None,
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


def build_task_difficulty_token_alignment(
    trajectories: pd.DataFrame,
    tasks: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = merge_task_metadata(trajectories, tasks, "difficulty")
    if "total_tokens" not in df.columns:
        raise ValueError("Trajectory table must contain total_tokens for token/difficulty alignment.")

    token_df = df[df["difficulty"].isin(DIFFICULTY_ORDER) & df["total_tokens"].gt(0)].copy()
    if token_df.empty:
        raise ValueError("No positive total_tokens rows are available for token/difficulty alignment.")

    difficulty_order = {difficulty: index + 1 for index, difficulty in enumerate(DIFFICULTY_ORDER)}
    token_df["difficulty_ordinal"] = token_df["difficulty"].map(difficulty_order)
    token_df["log10_total_tokens"] = np.log10(token_df["total_tokens"])

    by_task = (
        token_df.groupby(["task_name", "difficulty", "category"], as_index=False)
        .agg(
            n_positive_token_trajectories=("total_tokens", "size"),
            median_total_tokens=("total_tokens", "median"),
            mean_total_tokens=("total_tokens", "mean"),
            q25_total_tokens=("total_tokens", lambda values: values.quantile(0.25)),
            q75_total_tokens=("total_tokens", lambda values: values.quantile(0.75)),
        )
        .assign(
            difficulty_ordinal=lambda rows: rows["difficulty"].map(difficulty_order),
            log10_median_total_tokens=lambda rows: np.log10(rows["median_total_tokens"]),
        )
    )

    rows: list[dict[str, Any]] = []

    def add_row(section: str, metric: str, value: Any, difficulty: str = "", comparison: str = "") -> None:
        rows.append(
            {
                "section": section,
                "difficulty": difficulty,
                "comparison": comparison,
                "metric": metric,
                "value": value,
            }
        )

    for difficulty in DIFFICULTY_ORDER:
        task_group = by_task[by_task["difficulty"].eq(difficulty)]["median_total_tokens"]
        trajectory_group = token_df[token_df["difficulty"].eq(difficulty)]["total_tokens"]
        add_row("task_level_distribution", "n_tasks", int(task_group.shape[0]), difficulty)
        add_row("task_level_distribution", "median_task_median_total_tokens", float(task_group.median()), difficulty)
        add_row("task_level_distribution", "q25_task_median_total_tokens", float(task_group.quantile(0.25)), difficulty)
        add_row("task_level_distribution", "q75_task_median_total_tokens", float(task_group.quantile(0.75)), difficulty)
        add_row("trajectory_level_distribution", "n_positive_token_trajectories", int(trajectory_group.shape[0]), difficulty)
        add_row("trajectory_level_distribution", "median_total_tokens", float(trajectory_group.median()), difficulty)
        add_row("trajectory_level_distribution", "q25_total_tokens", float(trajectory_group.quantile(0.25)), difficulty)
        add_row("trajectory_level_distribution", "q75_total_tokens", float(trajectory_group.quantile(0.75)), difficulty)

    task_medians = by_task.groupby("difficulty")["median_total_tokens"].median()
    easy_max = by_task.loc[by_task["difficulty"].eq("easy"), "median_total_tokens"].max()
    add_row(
        "overlap",
        "share_hard_tasks_below_medium_task_median",
        float((by_task.loc[by_task["difficulty"].eq("hard"), "median_total_tokens"] < task_medians["medium"]).mean()),
        comparison="hard_vs_medium",
    )
    add_row(
        "overlap",
        "share_medium_tasks_above_hard_task_median",
        float((by_task.loc[by_task["difficulty"].eq("medium"), "median_total_tokens"] > task_medians["hard"]).mean()),
        comparison="medium_vs_hard",
    )
    add_row(
        "overlap",
        "share_easy_tasks_above_medium_task_median",
        float((by_task.loc[by_task["difficulty"].eq("easy"), "median_total_tokens"] > task_medians["medium"]).mean()),
        comparison="easy_vs_medium",
    )
    add_row(
        "overlap",
        "share_hard_tasks_below_easy_task_max",
        float((by_task.loc[by_task["difficulty"].eq("hard"), "median_total_tokens"] < easy_max).mean()),
        comparison="hard_vs_easy",
    )

    for harder, easier in [("medium", "easy"), ("hard", "medium"), ("hard", "easy")]:
        harder_values = by_task.loc[by_task["difficulty"].eq(harder), "median_total_tokens"].to_numpy(dtype=float)
        easier_values = by_task.loc[by_task["difficulty"].eq(easier), "median_total_tokens"].to_numpy(dtype=float)
        superiority = (
            (harder_values[:, None] > easier_values[None, :]).sum()
            + 0.5 * (harder_values[:, None] == easier_values[None, :]).sum()
        ) / (len(harder_values) * len(easier_values))
        add_row(
            "stochastic_superiority",
            "prob_harder_task_median_exceeds_easier",
            float(superiority),
            comparison=f"{harder}_vs_{easier}",
        )

    summary = pd.DataFrame(rows)
    by_task = (
        by_task.assign(_difficulty_order=dimension_sort_key(by_task["difficulty"], "difficulty"))
        .sort_values(["_difficulty_order", "median_total_tokens", "task_name"])
        .drop(columns="_difficulty_order")
        .reset_index(drop=True)
    )
    return summary, by_task


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
    task_rates = submission_task_pass_rates(df, [*group_columns, dimension_column])
    pooled_task_rates = trajectory_pooled_task_pass_rates(df, [*group_columns, dimension_column])
    rows = (
        task_rates.groupby([*group_columns, dimension_column], as_index=False)
        .agg(
            n_tasks=("task_name", "nunique"),
            n_submission_task_combinations=("task_submission_count", "sum"),
            n_trajectories=("task_trajectory_count", "sum"),
            pass_count=("task_pass_count", "sum"),
            pass_rate=("task_pass_rate", "mean"),
        )
    )
    rows["fail_count"] = rows["n_trajectories"] - rows["pass_count"]

    pooled = (
        pooled_task_rates.groupby([*group_columns, dimension_column], as_index=False)
        .agg(
            trajectory_pooled_task_mean_pass_rate=("trajectory_pooled_task_pass_rate", "mean"),
            trajectory_pooled_pass_count=("trajectory_pooled_task_pass_count", "sum"),
            trajectory_pooled_trajectory_count=("trajectory_pooled_task_trajectory_count", "sum"),
        )
    )
    pooled["trajectory_pooled_pass_rate"] = (
        pooled["trajectory_pooled_pass_count"] / pooled["trajectory_pooled_trajectory_count"]
    )
    rows = rows.merge(
        pooled[
            [
                *group_columns,
                dimension_column,
                "trajectory_pooled_pass_rate",
                "trajectory_pooled_task_mean_pass_rate",
            ]
        ],
        on=[*group_columns, dimension_column],
        how="left",
        validate="one_to_one",
    )

    totals = (
        submission_task_pass_rates(df, group_columns).groupby(group_columns, as_index=False)
        .agg(
            total_tasks=("task_name", "nunique"),
            total_submission_task_combinations=("task_submission_count", "sum"),
            total_trajectories=("task_trajectory_count", "sum"),
            total_pass_count=("task_pass_count", "sum"),
            total_pass_rate=("task_pass_rate", "mean"),
        )
    )
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

    task_rates = submission_task_pass_rates(df, ["category", "difficulty"])
    pooled_task_rates = trajectory_pooled_task_pass_rates(df, ["category", "difficulty"])
    rows = (
        task_rates.groupby(["category", "difficulty"], as_index=False)
        .agg(
            n_tasks=("task_name", "nunique"),
            n_submission_task_combinations=("task_submission_count", "sum"),
            n_trajectories=("task_trajectory_count", "sum"),
            pass_count=("task_pass_count", "sum"),
            pass_rate=("task_pass_rate", "mean"),
        )
    )
    rows["fail_count"] = rows["n_trajectories"] - rows["pass_count"]
    pooled = (
        pooled_task_rates.groupby(["category", "difficulty"], as_index=False)
        .agg(
            trajectory_pooled_task_mean_pass_rate=("trajectory_pooled_task_pass_rate", "mean"),
            trajectory_pooled_pass_count=("trajectory_pooled_task_pass_count", "sum"),
            trajectory_pooled_trajectory_count=("trajectory_pooled_task_trajectory_count", "sum"),
        )
    )
    pooled["trajectory_pooled_pass_rate"] = (
        pooled["trajectory_pooled_pass_count"] / pooled["trajectory_pooled_trajectory_count"]
    )
    rows = rows.merge(
        pooled[
            [
                "category",
                "difficulty",
                "trajectory_pooled_pass_rate",
                "trajectory_pooled_task_mean_pass_rate",
            ]
        ],
        on=["category", "difficulty"],
        how="left",
        validate="one_to_one",
    )
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


def pass_fail_counts_height(column_count: int) -> float:
    return min(7.0, max(3.8, 2.8 + column_count * 0.3))


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


def format_success_rate_y_axis(ax: plt.Axes) -> None:
    ax.set_ylim(0, 1)
    ax.grid(axis="y", alpha=0.25)


def plot_task_weighted_success(
    domain_table: pd.DataFrame,
    figures_dir: Path,
    dimension_column: str = "category",
    dimension_label: str = "task category",
    output_prefix: str = "task_domain",
) -> Path:
    plot_df = domain_table.sort_values("task_mean_pass_rate", ascending=False).copy()
    if dimension_column == "category":
        plot_df["category_label"] = plot_df.apply(
            lambda row: category_count_label_multiline(row, dimension_column),
            axis=1,
        )
        fig, ax = plt.subplots(figsize=(12.5, 6.2))
        ax.bar(plot_df["category_label"], plot_df["task_mean_pass_rate"], width=0.78, color=PASS_COLOR)
        format_success_rate_y_axis(ax)
        format_category_axis(ax)
        ax.set_xlabel(dimension_label[:1].upper() + dimension_label[1:])
        ax.set_ylabel("Task-weighted pass rate")
    else:
        plot_df["category_label"] = plot_df.apply(lambda row: category_count_label(row, dimension_column), axis=1)
        bar_height = 0.8
        plot_height = 2.5 if dimension_column == "difficulty" else figure_height(len(plot_df))
        fig, ax = plt.subplots(figsize=(9.5, plot_height))
        ax.barh(plot_df["category_label"], plot_df["task_mean_pass_rate"], height=bar_height, color=PASS_COLOR)
        ax.invert_yaxis()
        format_success_rate_axis(ax)
        ax.set_xlabel("Task-weighted pass rate")
        ax.set_ylabel(dimension_label[:1].upper() + dimension_label[1:])
    ax.set_title(f"Task-weighted pass rate by {dimension_label}")
    note = (
        "Note: Bars show the mean pass rate across tasks after averaging repeated trials within each submission-task pair.\n"
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
    ax.barh(plot_df[dimension_column], plot_df["n_tasks"], color=PASS_COLOR)
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

    fig, ax = plt.subplots(figsize=(figure_width(len(plot_df)), pass_fail_counts_height(len(plot_df))))
    ax.bar(plot_df["category_label"], plot_df["pass_count"], label="Pass", color=PASS_COLOR)
    ax.bar(
        plot_df["category_label"],
        plot_df["fail_count"],
        bottom=plot_df["pass_count"],
        label="Fail",
        color=FAIL_COLOR,
    )
    ax.grid(axis="y", alpha=0.25)
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    if len(plot_df) <= 4:
        ax.tick_params(axis="x", labelrotation=0)
    else:
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
    colors = colorblind_cycle(len(labels))

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


def format_cell_value(value: float, variable_display: str | None = None) -> str:
    if variable_display == "Total tokens":
        return f"{value / 1_000:,.0f}k"
    if variable_display == "Duration seconds":
        return f"{value / 60:,.1f}m"
    if variable_display == "Positive cost USD":
        return f"${value:,.2f}"
    if abs(value) < 10 and value != int(value):
        return f"{value:,.2f}"
    return f"{value:,.0f}"


def wrap_heatmap_label(label: str, width: int = 16) -> str:
    return "\n".join(textwrap.wrap(label, width=width, break_long_words=False))


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

    if dimension_column == "category":
        category_order = normalized.mean(axis=1, skipna=True).sort_values(ascending=False).index.tolist()
        heatmap = heatmap.reindex(category_order)
        normalized = normalized.reindex(category_order)
        plot_values = heatmap
        plot_normalized = normalized
        x_labels = [
            wrap_heatmap_label(EFFORT_HEATMAP_LABELS.get(label, label), 11) for label in plot_values.columns
        ]
        y_labels = plot_values.index.tolist()
        figsize = (13.2, 5.8)
    else:
        plot_values = heatmap
        plot_normalized = normalized
        x_labels = [
            wrap_heatmap_label(EFFORT_HEATMAP_LABELS.get(label, label), 11) for label in plot_values.columns
        ]
        if dimension_column == "difficulty":
            y_labels = plot_values.index.tolist()
            figsize = (10.8, 4.4)
        else:
            y_labels = [
                f"{category} (tasks={int(domain_lookup.loc[category, 'n_tasks'])}, "
                f"traj={int(domain_lookup.loc[category, 'n_trajectories']):,})"
                f"{'*' if domain_lookup.loc[category, 'low_task_count'] else ''}"
                for category in plot_values.index
            ]
            figsize = (11.5, figure_height(len(plot_values)))

    fig, ax = plt.subplots(figsize=figsize)
    cmap = colorblind_cmap(LOW_GOOD_CMAP)
    matrix = np.ma.masked_invalid(plot_normalized.to_numpy(dtype=float))
    image = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1)

    ax.set_xticks(range(len(x_labels)))
    if dimension_column == "category":
        ax.set_xticklabels(x_labels, rotation=0, ha="center", fontsize=11.0)
    else:
        ax.set_xticklabels(x_labels, rotation=0, ha="center", fontsize=10.5)
    ax.set_yticks(range(len(y_labels)))
    y_label_fontsize = 11.0 if dimension_column == "category" else 11 if dimension_column == "difficulty" else None
    ax.set_yticklabels(y_labels, fontsize=y_label_fontsize)
    ax.set_xlabel("Effort variable", fontsize=11.5 if dimension_column == "category" else None)
    ax.set_ylabel(
        dimension_label[:1].upper() + dimension_label[1:],
        fontsize=11.5 if dimension_column == "category" else None,
    )
    order_note = "overall normalized effort" if dimension_column == "category" else "task coverage"
    ax.set_title(f"Median trajectory effort by {dimension_label}", pad=16)

    ax.set_xticks(np.arange(plot_values.shape[1] + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(plot_values.shape[0] + 1) - 0.5, minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5)
    ax.tick_params(which="minor", bottom=False, left=False)

    for row_index in range(plot_values.shape[0]):
        for column_index in range(plot_values.shape[1]):
            value = plot_values.iat[row_index, column_index]
            if pd.isna(value):
                continue
            text_color = heatmap_text_color(float(plot_normalized.iat[row_index, column_index]), cmap, 0, 1)
            ax.text(
                column_index,
                row_index,
                format_cell_value(float(value), str(plot_values.columns[column_index])),
                ha="center",
                va="center",
                fontsize=12.25 if dimension_column == "category" else 15.0,
                color=text_color,
            )

    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    colorbar.set_label("Column-normalized effort (green=low, red=high)", fontsize=10.25)
    fig.tight_layout()

    path = effort_figures_dir / f"heatmap_{output_prefix}_effort_median.png"
    fig.savefig(path, dpi=HEATMAP_DPI, bbox_inches="tight")
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

    cmap = colorblind_cmap()
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
                text_color = heatmap_text_color(float(rate), cmap, 0, 1)
                ax.text(
                    column_index,
                    row_index,
                    f"{rate:.2f}",
                    ha="center",
                    va="center",
                    fontsize=8.0 if row_count > 20 else 9.0,
                    color=text_color,
                )

    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    colorbar.set_label("Pass rate")
    fig.tight_layout()
    fig.savefig(path, dpi=HEATMAP_DPI)
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
    colors = colorblind_cycle(len(category_order))
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
    colors = {"easy": PASS_COLOR, "medium": "#E69F00", "hard": FAIL_COLOR}
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

    heatmap = (
        pass_rates.pivot(index="difficulty", columns="category", values="pass_rate")
        .reindex(index=difficulty_order, columns=category_order)
        .astype(float)
    )
    counts = (
        pass_rates.pivot(index="difficulty", columns="category", values="n_trajectories")
        .reindex(index=difficulty_order, columns=category_order)
        .fillna(0)
        .astype(int)
    )

    fig, ax = plt.subplots(figsize=(figure_width(len(category_order)), 5.2))
    cmap = colorblind_cmap()
    matrix = np.ma.masked_invalid(heatmap.to_numpy(dtype=float))
    image = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1)

    ax.set_xticks(range(len(category_order)))
    ax.set_xticklabels(category_order, rotation=40, ha="right", fontsize=10)
    ax.set_yticks(range(len(difficulty_order)))
    ax.set_yticklabels(difficulty_order)
    ax.set_xlabel("Task category")
    ax.set_ylabel("Task difficulty")
    ax.set_title("Pass rate by task category and difficulty")
    ax.set_xticks(np.arange(-0.5, len(category_order), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(difficulty_order), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.0)
    ax.tick_params(which="minor", bottom=False, left=False)

    for row_index, difficulty in enumerate(difficulty_order):
        for column_index, category in enumerate(category_order):
            rate = heatmap.loc[difficulty, category]
            count = counts.loc[difficulty, category]
            if pd.isna(rate) or count == 0:
                continue
            text_color = heatmap_text_color(float(rate), cmap, 0, 1)
            ax.text(
                column_index,
                row_index,
                f"{rate:.2f}",
                ha="center",
                va="center",
                fontsize=13,
                color=text_color,
            )

    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    colorbar.set_label("Pass rate")
    fig.tight_layout()
    fig.savefig(path, dpi=HEATMAP_DPI)
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

    rate_columns = [
        dimension_column,
        "n_tasks",
        "n_submission_task_combinations",
        "n_trajectories",
        "pass_count",
        "fail_count",
        "pass_rate",
        "trajectory_pooled_pass_rate",
        "trajectory_pooled_task_mean_pass_rate",
    ]
    model_table = model_category_rates[
        ["model_dir", *rate_columns]
    ]
    scaffold_table = scaffold_category_rates[
        ["scaffold", *rate_columns]
    ]
    provider_table = provider_category_rates[
        ["model_provider", *rate_columns]
    ]
    source_table = source_category_rates[
        ["model_source", *rate_columns]
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
    include_task_weighted_success: bool = True,
    include_effort_heatmap: bool = True,
) -> list[Path]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        plot_pass_fail_counts(domain_table, figures_dir, dimension_column, dimension_label, output_prefix),
        plot_pass_fail_pie_charts(domain_table, figures_dir, dimension_column, dimension_label, output_prefix),
        plot_task_coverage(domain_table, figures_dir, dimension_column, dimension_label, output_prefix),
    ]
    if include_task_weighted_success:
        paths.insert(
            0,
            plot_task_weighted_success(domain_table, figures_dir, dimension_column, dimension_label, output_prefix),
        )
    if include_effort_heatmap:
        effort_heatmap = plot_effort_heatmap(
            effort_summary,
            domain_table,
            figures_dir,
            dimension_column,
            dimension_label,
            output_prefix,
        )
        if effort_heatmap is not None:
            paths.append(effort_heatmap)
    return paths


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks(args.tasks)
    trajectories = filter_benchmark_version(load_trajectories(args.trajectories), args.benchmark_version)
    require_submission_id(trajectories)
    domain_table = build_domain_table(trajectories, tasks)
    effort_summary = build_effort_summary(trajectories, tasks)
    difficulty_table = build_domain_table(trajectories, tasks, "difficulty")
    difficulty_significance = build_rq2_1_difficulty_significance(trajectories, tasks)
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
    token_alignment_summary, token_alignment_by_task = build_task_difficulty_token_alignment(trajectories, tasks)

    category_out_dir = args.out / "category"
    difficulty_out_dir = args.out / "difficulty"
    category_difficulty_out_dir = args.out / "category_difficulty"
    category_out_dir.mkdir(parents=True, exist_ok=True)
    difficulty_out_dir.mkdir(parents=True, exist_ok=True)
    category_difficulty_out_dir.mkdir(parents=True, exist_ok=True)

    out_path = category_out_dir / "task_domain_outcome.csv"
    effort_out_path = category_out_dir / "task_domain_effort_summary.csv"
    difficulty_out_path = difficulty_out_dir / "task_difficulty_outcome.csv"
    difficulty_significance_path = args.out / "rq2_1_difficulty_significance.csv"
    difficulty_effort_out_path = difficulty_out_dir / "task_difficulty_effort_summary.csv"
    token_alignment_summary_path = difficulty_out_dir / "task_difficulty_token_alignment_summary.csv"
    token_alignment_by_task_path = difficulty_out_dir / "task_difficulty_token_alignment_by_task.csv"
    category_difficulty_out_path = category_difficulty_out_dir / "category_difficulty.csv"
    domain_table.drop(columns=["low_task_count"]).to_csv(out_path, index=False)
    effort_summary.drop(columns=["complete_case_count"]).to_csv(effort_out_path, index=False)
    difficulty_table.drop(columns=["low_task_count"]).to_csv(difficulty_out_path, index=False)
    difficulty_significance.to_csv(difficulty_significance_path, index=False)
    difficulty_effort_summary.drop(columns=["complete_case_count"]).to_csv(difficulty_effort_out_path, index=False)
    token_alignment_summary.to_csv(token_alignment_summary_path, index=False)
    token_alignment_by_task.to_csv(token_alignment_by_task_path, index=False)
    category_difficulty_rates[
        [
            "category",
            "difficulty",
            "n_tasks",
            "n_submission_task_combinations",
            "n_trajectories",
            "pass_count",
            "fail_count",
            "pass_rate",
            "trajectory_pooled_pass_rate",
            "trajectory_pooled_task_mean_pass_rate",
        ]
    ].to_csv(category_difficulty_out_path, index=False)
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
    print(f"Wrote {difficulty_significance_path}")
    print(f"Wrote {difficulty_effort_out_path}")
    print(f"Wrote {token_alignment_summary_path}")
    print(f"Wrote {token_alignment_by_task_path}")
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
