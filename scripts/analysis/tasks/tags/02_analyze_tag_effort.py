#!/usr/bin/env python3
"""Analyze Terminal-Bench tags against trajectory effort variables.

Outputs:
- reports/tasks/tags/heatmap_tag_group_effort_median_lift.png
- reports/tasks/tags/heatmap_semantic_cluster_effort_median_lift.png
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
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
TAGS_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining" / "tags" / "task_tag_counts.csv"
TAG_GROUPS_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining" / "tags" / "tag_groups.csv"
SEMANTIC_CLUSTERS_DEFAULT = (
    DATA_PROCESSED_LIVE_DIR / "task_mining" / "tags" / "semantic_clusters" / "tag_semantic_clusters.csv"
)
OUT_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining" / "tags"
FIGURES_DEFAULT = REPORTS_DIR / "tasks" / "tags"

OUTCOME_COLUMNS = {"task_name", "reward_outcome", "outcome", "reward"}
EFFORT_DISPLAY_NAMES = {
    "step_count": "Step count",
    "agent_step_count": "Agent step count",
    "tool_call_count": "Tool call count",
    "command_count": "Command count",
    "total_tokens": "Total tokens",
    "duration_seconds_from_timestamps": "Duration seconds",
    "cost_usd_positive": "Positive cost USD",
}
EFFORT_SOURCE_COLUMNS = set(EFFORT_DISPLAY_NAMES) - {"cost_usd_positive"} | {"cost_usd"}
HEATMAP_VARIABLES = [
    "step_count",
    "agent_step_count",
    "tool_call_count",
    "command_count",
    "total_tokens",
    "duration_seconds_from_timestamps",
    "cost_usd_positive",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectories", type=Path, default=TRAJECTORY_DEFAULT)
    parser.add_argument("--task-tags", type=Path, default=TAGS_DEFAULT)
    parser.add_argument("--tag-groups", type=Path, default=TAG_GROUPS_DEFAULT)
    parser.add_argument("--semantic-clusters", type=Path, default=SEMANTIC_CLUSTERS_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DEFAULT)
    return parser.parse_args()


def normalize_tag_key(tag: Any) -> str:
    return str(tag).strip().lower().replace("_", "-")


def load_trajectories(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        usecols=lambda column: column in OUTCOME_COLUMNS | EFFORT_SOURCE_COLUMNS,
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

    columns = ["task_name", "outcome", "passed"]
    columns.extend(column for column in EFFORT_DISPLAY_NAMES if column in df.columns)
    return df[columns]


def load_task_tags(path: Path) -> pd.DataFrame:
    task_tags = pd.read_csv(path)
    required = {"task_name", "tags"}
    missing = required.difference(task_tags.columns)
    if missing:
        raise ValueError(f"{path} is missing required fields: {', '.join(sorted(missing))}")

    rows: list[dict[str, Any]] = []
    for row in task_tags.itertuples(index=False):
        tags = getattr(row, "tags")
        if not isinstance(tags, str) or not tags.strip():
            continue
        for tag in tags.split("|"):
            tag = tag.strip()
            if not tag:
                continue
            rows.append({"task_name": row.task_name, "tag": tag, "tag_key": normalize_tag_key(tag)})
    if not rows:
        raise ValueError(f"{path} has no task tags.")
    return pd.DataFrame(rows).drop_duplicates(["task_name", "tag"])


def load_tag_groups(path: Path) -> pd.DataFrame:
    tag_groups = pd.read_csv(path, usecols=["tag", "tag_group"])
    tag_groups["tag_key"] = tag_groups["tag"].map(normalize_tag_key)
    return tag_groups[["tag_key", "tag_group"]].drop_duplicates("tag_key")


def load_semantic_clusters(path: Path) -> pd.DataFrame:
    clusters = pd.read_csv(path)
    clusters["tag_key"] = clusters["tag"].map(normalize_tag_key)
    clusters["cluster_id"] = clusters["cluster_id"].astype(int)
    if "tag_count" in clusters.columns:
        clusters["tag_count"] = pd.to_numeric(clusters["tag_count"], errors="coerce").fillna(0).astype(int)
    else:
        clusters["tag_count"] = 1
    return clusters[["tag_key", "cluster_id", "tag", "tag_count"]].drop_duplicates(["tag_key", "cluster_id"])


def build_memberships(
    task_tags: pd.DataFrame,
    tag_groups: pd.DataFrame,
    semantic_clusters: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    tag_membership = task_tags[["task_name", "tag"]].drop_duplicates()

    group_membership = (
        task_tags.merge(tag_groups, on="tag_key", how="left", validate="many_to_one")
        .dropna(subset=["tag_group"])
        [["task_name", "tag_group"]]
        .drop_duplicates()
    )

    cluster_membership = (
        task_tags.merge(semantic_clusters[["tag_key", "cluster_id"]], on="tag_key", how="left", validate="many_to_many")
        .dropna(subset=["cluster_id"])
        [["task_name", "cluster_id"]]
        .drop_duplicates()
    )
    cluster_membership["cluster_id"] = cluster_membership["cluster_id"].astype(int)

    return {
        "tag": tag_membership,
        "tag_group": group_membership,
        "semantic_cluster": cluster_membership,
    }


def global_effort_baselines(trajectories: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    baselines: dict[str, dict[str, float | None]] = {}
    for variable in EFFORT_DISPLAY_NAMES:
        if variable not in trajectories.columns:
            continue
        values = trajectories[variable].dropna()
        baselines[variable] = {
            "median": float(values.median()) if len(values) else None,
            "mean": float(values.mean()) if len(values) else None,
        }
    return baselines


def build_outcome_table(
    trajectories: pd.DataFrame,
    membership: pd.DataFrame,
    dimension_column: str,
) -> pd.DataFrame:
    df = trajectories.merge(membership, on="task_name", how="inner", validate="many_to_many")

    task_rates = (
        df.groupby([dimension_column, "task_name"], as_index=False)
        .agg(
            task_trajectory_count=("passed", "size"),
            task_pass_count=("passed", "sum"),
            task_pass_rate=("passed", "mean"),
        )
    )

    rows: list[dict[str, Any]] = []
    for value, group in df.groupby(dimension_column, sort=False):
        n_trajectories = int(group.shape[0])
        pass_count = int(group["passed"].sum())
        value_task_rates = task_rates.loc[task_rates[dimension_column] == value, "task_pass_rate"]
        n_tasks = int(value_task_rates.shape[0])
        rows.append(
            {
                dimension_column: value,
                "n_tasks": n_tasks,
                "n_trajectories": n_trajectories,
                "pass_count": pass_count,
                "fail_count": n_trajectories - pass_count,
                "pass_rate": pass_count / n_trajectories if n_trajectories else None,
                "task_mean_pass_rate": float(value_task_rates.mean()) if n_tasks else None,
                "low_task_count": n_tasks < 5,
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(["n_tasks", "n_trajectories", dimension_column], ascending=[False, False, True])
        .reset_index(drop=True)
    )


def build_effort_summary(
    trajectories: pd.DataFrame,
    membership: pd.DataFrame,
    dimension_column: str,
    baselines: dict[str, dict[str, float | None]],
) -> pd.DataFrame:
    df = trajectories.merge(membership, on="task_name", how="inner", validate="many_to_many")
    rows: list[dict[str, Any]] = []

    task_counts = df.groupby(dimension_column)["task_name"].nunique()
    for value, group in df.groupby(dimension_column, sort=False):
        for variable, display_name in EFFORT_DISPLAY_NAMES.items():
            if variable not in group.columns:
                continue
            values = group[variable].dropna()
            median = float(values.median()) if len(values) else None
            mean = float(values.mean()) if len(values) else None
            baseline_median = baselines.get(variable, {}).get("median")
            baseline_mean = baselines.get(variable, {}).get("mean")
            rows.append(
                {
                    dimension_column: value,
                    "variable": variable,
                    "variable_display": display_name,
                    "n_tasks": int(task_counts.loc[value]),
                    "n_trajectories": int(group.shape[0]),
                    "complete_case_count": int(values.shape[0]),
                    "median": median,
                    "mean": mean,
                    "p75": float(values.quantile(0.75)) if len(values) else None,
                    "p90": float(values.quantile(0.90)) if len(values) else None,
                    "max": float(values.max()) if len(values) else None,
                    "global_median": baseline_median,
                    "global_mean": baseline_mean,
                    "median_lift_vs_global": median / baseline_median if median is not None and baseline_median else None,
                    "mean_lift_vs_global": mean / baseline_mean if mean is not None and baseline_mean else None,
                    "low_task_count": int(task_counts.loc[value]) < 5,
                }
            )

    return (
        pd.DataFrame(rows)
        .sort_values(["variable", "median", dimension_column], ascending=[True, False, True])
        .reset_index(drop=True)
    )


def cluster_labels(semantic_clusters: pd.DataFrame, max_tags: int = 4) -> dict[int, str]:
    labels: dict[int, str] = {}
    for cluster_id, group in semantic_clusters.groupby("cluster_id"):
        top_tags = (
            group.sort_values(["tag_count", "tag"], ascending=[False, True])["tag"]
            .drop_duplicates()
            .head(max_tags)
            .tolist()
        )
        labels[int(cluster_id)] = f"Cluster {int(cluster_id)}: {', '.join(top_tags)}"
    return labels


def figure_height(n_rows: int) -> float:
    return max(4.8, min(15.0, 1.0 + n_rows * 0.42))


def format_heatmap_value(value: float, variable: str) -> str:
    if variable == "cost_usd_positive":
        return f"${value:.2f}"
    if variable in {"prompt_tokens", "completion_tokens", "total_tokens"}:
        return f"{value / 1000:.0f}k"
    if variable == "duration_seconds_from_timestamps":
        return f"{value:.0f}s"
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.1f}"


def plot_effort_lift_heatmap(
    effort_summary: pd.DataFrame,
    outcome_table: pd.DataFrame,
    dimension_column: str,
    label_lookup: dict[Any, str],
    title: str,
    path: Path,
) -> Path | None:
    effort = effort_summary[effort_summary["variable"].isin(HEATMAP_VARIABLES)].copy()
    if effort.empty:
        return None

    order = (
        outcome_table.sort_values(["n_tasks", "n_trajectories", dimension_column], ascending=[False, False, True])[
            dimension_column
        ]
        .drop_duplicates()
        .tolist()
    )
    variable_labels = [EFFORT_DISPLAY_NAMES[variable] for variable in HEATMAP_VARIABLES if variable in effort["variable"].values]
    lift = (
        effort.pivot(index=dimension_column, columns="variable_display", values="median_lift_vs_global")
        .reindex(index=order, columns=variable_labels)
        .astype(float)
    )
    medians = (
        effort.pivot(index=dimension_column, columns="variable_display", values="median")
        .reindex(index=order, columns=variable_labels)
        .astype(float)
    )
    variable_by_label = {display: variable for variable, display in EFFORT_DISPLAY_NAMES.items()}
    if lift.empty:
        return None

    outcome_lookup = outcome_table.set_index(dimension_column)
    row_labels = []
    for value in lift.index:
        base_label = label_lookup.get(value, str(value))
        row_labels.append(
            "\n".join(
                textwrap.wrap(
                    f"{base_label} (tasks={int(outcome_lookup.loc[value, 'n_tasks'])}, "
                    f"traj={int(outcome_lookup.loc[value, 'n_trajectories']):,})",
                    width=52,
                )
            )
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13.5, figure_height(len(lift))))
    cmap = plt.get_cmap("RdYlBu_r").copy()
    cmap.set_bad("#f2f2f2")
    matrix = np.ma.masked_invalid(lift.to_numpy(dtype=float))
    image = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0.4, vmax=2.4)

    ax.set_xticks(range(len(lift.columns)))
    ax.set_xticklabels(lift.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels)
    ax.set_xlabel("Effort metric")
    ax.set_ylabel("Tag cluster")
    ax.set_title(title)

    for row_index in range(lift.shape[0]):
        for column_index in range(lift.shape[1]):
            lift_value = lift.iat[row_index, column_index]
            median_value = medians.iat[row_index, column_index]
            if pd.isna(lift_value) or pd.isna(median_value):
                continue
            variable = variable_by_label[str(lift.columns[column_index])]
            text_color = "white" if lift_value >= 1.65 else "black"
            ax.text(
                column_index,
                row_index,
                f"{lift_value:.1f}x\n{format_heatmap_value(median_value, variable)}",
                ha="center",
                va="center",
                fontsize=7,
                color=text_color,
            )

    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    colorbar.set_label("Median effort lift vs global median")
    fig.text(
        0.5,
        0.015,
        "Cell text shows lift versus global median, then raw median value. Rows are ordered by task coverage.",
        fontsize=9,
        ha="center",
        va="top",
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def write_figures(
    figures_dir: Path,
    group_outcome: pd.DataFrame,
    group_effort: pd.DataFrame,
    cluster_outcome: pd.DataFrame,
    cluster_effort: pd.DataFrame,
    semantic_clusters: pd.DataFrame,
) -> list[Path]:
    figure_paths: list[Path] = []
    group_path = plot_effort_lift_heatmap(
        group_effort,
        group_outcome,
        "tag_group",
        {},
        "Median trajectory effort by manual tag group",
        figures_dir / "heatmap_tag_group_effort_median_lift.png",
    )
    if group_path is not None:
        figure_paths.append(group_path)

    semantic_path = plot_effort_lift_heatmap(
        cluster_effort,
        cluster_outcome,
        "cluster_id",
        cluster_labels(semantic_clusters),
        "Median trajectory effort by semantic tag cluster",
        figures_dir / "heatmap_semantic_cluster_effort_median_lift.png",
    )
    if semantic_path is not None:
        figure_paths.append(semantic_path)
    return figure_paths


def write_outputs(
    trajectories: pd.DataFrame,
    memberships: dict[str, pd.DataFrame],
    figures_dir: Path,
    semantic_clusters: pd.DataFrame,
) -> list[Path]:
    baselines = global_effort_baselines(trajectories)

    group_outcome = build_outcome_table(trajectories, memberships["tag_group"], "tag_group")
    group_effort = build_effort_summary(trajectories, memberships["tag_group"], "tag_group", baselines)
    cluster_outcome = build_outcome_table(trajectories, memberships["semantic_cluster"], "cluster_id")
    cluster_effort = build_effort_summary(trajectories, memberships["semantic_cluster"], "cluster_id", baselines)

    return write_figures(
        figures_dir,
        group_outcome,
        group_effort,
        cluster_outcome,
        cluster_effort,
        semantic_clusters,
    )


def main() -> None:
    args = parse_args()
    trajectories = load_trajectories(args.trajectories)
    task_tags = load_task_tags(args.task_tags)
    tag_groups = load_tag_groups(args.tag_groups)
    semantic_clusters = load_semantic_clusters(args.semantic_clusters)
    memberships = build_memberships(task_tags, tag_groups, semantic_clusters)
    figure_paths = write_outputs(
        trajectories,
        memberships,
        args.figures_dir,
        semantic_clusters,
    )

    print(f"Loaded {trajectories.shape[0]} pass/fail trajectories")
    print(f"Loaded {task_tags['task_name'].nunique()} tagged tasks and {task_tags['tag'].nunique()} tags")
    for key, membership in memberships.items():
        dimension_column = "cluster_id" if key == "semantic_cluster" else key
        print(f"{key}: {membership[dimension_column].nunique()} values, {membership.shape[0]} task memberships")
    print("Wrote figures:")
    for path in figure_paths:
        print(f"- {path}")


if __name__ == "__main__":
    main()
