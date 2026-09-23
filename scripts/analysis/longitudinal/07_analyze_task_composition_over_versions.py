#!/usr/bin/env python3
"""Analyze task composition, time estimates, and observed durations by TB version.

The outputs are task-balanced at the version level: observed "real time" is
summarized first within each submission-task pair, then across submissions for
each task, then across tasks for each version/category.

Outputs:
- data/processed_live/longitudinal/task_composition/version_task_composition_summary.csv
- data/processed_live/longitudinal/task_composition/category_composition_by_version.csv
- data/processed_live/longitudinal/task_composition/adjacent_version_task_changes.csv
- reports/longitudinal/task_composition/task_composition_over_versions.png
- reports/longitudinal/task_composition/task_time_estimates_over_versions.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT_GUESS = Path(__file__).resolve().parents[3]
if str(REPO_ROOT_GUESS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_GUESS))

from scripts.analysis.plot_style import COLORBLIND_PALETTE, OTHER_COLOR, colorblind_cycle
from scripts.benchmark_paths import find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
LONGITUDINAL_DIR = REPO_ROOT / "data" / "processed_live" / "longitudinal"
OUT_DIR_DEFAULT = LONGITUDINAL_DIR / "task_composition"
FIGURES_DIR_DEFAULT = REPO_ROOT / "reports" / "longitudinal" / "task_composition"
TB2_LONGITUDINAL_DEFAULT = LONGITUDINAL_DIR / "trajectory_longitudinal.csv"
TB3_TB4_LONGITUDINAL_DEFAULT = LONGITUDINAL_DIR / "tb3_tb4" / "trajectory_longitudinal.csv"
TB3_TB4_AUDIT_DEFAULT = LONGITUDINAL_DIR / "tb3_tb4_task_version_audit.csv"
TB2_CATEGORY_LABELS_DEFAULT = LONGITUDINAL_DIR / "tb2_task_category_llm_labels.csv"

VERSIONS = ["2.0", "2.1", "3.0", "4.0"]
ADJACENT_VERSION_PAIRS = [("2.0", "2.1"), ("2.1", "3.0"), ("3.0", "4.0")]
UNIFIED_CATEGORIES = ["Software", "Science", "ML", "Operations", "Security", "Hardware", "Media"]
TASK_METADATA_COLUMNS = [
    "benchmark",
    "benchmark_version",
    "task_name",
    "category",
    "subcategory",
    "difficulty",
    "tags",
    "description",
    "difficulty_explanation",
    "solution_explanation",
    "verification_explanation",
    "relevant_experience",
    "expert_time_estimate_min",
    "junior_time_estimate_min",
    "agent_timeout_sec",
    "verifier_timeout_sec",
    "environment_build_timeout_sec",
    "instruction_chars",
    "instruction_normalized_chars",
    "package_file_count",
    "package_total_listed_bytes",
    "cpus",
    "memory_mb",
    "storage_mb",
    "gpus",
]
NUMERIC_COLUMNS = [
    "expert_time_estimate_min",
    "junior_time_estimate_min",
    "agent_timeout_sec",
    "verifier_timeout_sec",
    "environment_build_timeout_sec",
    "instruction_chars",
    "instruction_normalized_chars",
    "package_file_count",
    "package_total_listed_bytes",
    "cpus",
    "memory_mb",
    "storage_mb",
    "gpus",
]
VERSION_LABELS = {
    "2.0": "TB2.0",
    "2.1": "TB2.1",
    "3.0": "TB3.0",
    "4.0": "TB4.0",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tb2-longitudinal", type=Path, default=TB2_LONGITUDINAL_DEFAULT)
    parser.add_argument("--tb3-tb4-longitudinal", type=Path, default=TB3_TB4_LONGITUDINAL_DEFAULT)
    parser.add_argument("--tb3-tb4-audit", type=Path, default=TB3_TB4_AUDIT_DEFAULT)
    parser.add_argument("--tb2-category-labels", type=Path, default=TB2_CATEGORY_LABELS_DEFAULT)
    parser.add_argument(
        "--allow-rule-based-tb2-category-fallback",
        action="store_true",
        help="Use a transparent rule-based TB2 category mapping when LLM labels are unavailable.",
    )
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR_DEFAULT)
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


def load_longitudinal(paths: list[Path]) -> pd.DataFrame:
    frames = []
    required = {"benchmark_version", "task_name", "submission_id", "duration_seconds", "passed"}
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Missing longitudinal table: {path}")
        df = pd.read_csv(path, low_memory=False)
        missing = sorted(required.difference(df.columns))
        if missing:
            raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    df = df[df["benchmark_version"].isin(VERSIONS)].copy()
    for column in NUMERIC_COLUMNS + ["duration_seconds", "passed"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def normalize_text(value: object, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none"}:
        return fallback
    return text


def rule_based_unified_category(category: object) -> str:
    text = normalize_text(category, "").strip().lower()
    mapping = {
        "software": "Software",
        "software-engineering": "Software",
        "debugging": "Software",
        "science": "Science",
        "scientific-computing": "Science",
        "mathematics": "Science",
        "ml": "ML",
        "machine-learning": "ML",
        "data-science": "ML",
        "data-processing": "ML",
        "model-training": "ML",
        "operations": "Operations",
        "system-administration": "Operations",
        "file-operations": "Operations",
        "security": "Security",
        "hardware": "Hardware",
        "media": "Media",
        "video-processing": "Media",
    }
    return mapping.get(text, "Other")


def build_task_metadata(df: pd.DataFrame) -> pd.DataFrame:
    keep = [column for column in TASK_METADATA_COLUMNS if column in df.columns]
    tasks = (
        df[keep]
        .sort_values(["benchmark_version", "task_name"])
        .drop_duplicates(["benchmark_version", "task_name"])
        .copy()
    )
    for column in TASK_METADATA_COLUMNS:
        if column not in tasks.columns:
            tasks[column] = np.nan
    tasks["category"] = tasks["category"].map(lambda value: normalize_text(value))
    tasks["subcategory"] = tasks["subcategory"].map(lambda value: normalize_text(value, ""))
    tasks["difficulty"] = tasks["difficulty"].map(lambda value: normalize_text(value))
    for column in NUMERIC_COLUMNS:
        tasks[column] = pd.to_numeric(tasks[column], errors="coerce")
    return tasks


def valid_unified_category(value: object) -> str:
    text = normalize_text(value, "")
    for category in UNIFIED_CATEGORIES:
        if text.lower() == category.lower():
            return category
    return ""


def attach_unified_categories(
    tasks: pd.DataFrame,
    tb2_category_labels_path: Path,
    allow_rule_based_tb2_category_fallback: bool,
) -> pd.DataFrame:
    tasks = tasks.copy()
    tasks["unified_category"] = tasks["category"].map(rule_based_unified_category)
    tasks["category_label_source"] = "rule_based_fallback"
    tb34_mask = tasks["benchmark_version"].astype(str).isin({"3.0", "4.0"})
    tasks.loc[tb34_mask, "unified_category"] = tasks.loc[tb34_mask, "category"].map(valid_unified_category)
    tasks.loc[tb34_mask, "category_label_source"] = "native_tb3_tb4"

    tb2_mask = tasks["benchmark_version"].astype(str).isin({"2.0", "2.1"})
    if tb2_category_labels_path.exists():
        labels = pd.read_csv(tb2_category_labels_path, low_memory=False)
        required = {"task_name", "llm_category_label"}
        missing = sorted(required.difference(labels.columns))
        if missing:
            raise ValueError(f"{tb2_category_labels_path} is missing required columns: {', '.join(missing)}")
        labels = labels.copy()
        labels["task_name"] = labels["task_name"].map(normalize_text)
        labels["unified_category_llm"] = labels["llm_category_label"].map(valid_unified_category)
        if "label_source" in labels.columns:
            source = labels["label_source"].fillna("").astype(str).str.strip().str.lower()
        else:
            source = pd.Series("", index=labels.index)
        if "llm_rationale" in labels.columns:
            rationale = labels["llm_rationale"].fillna("").astype(str)
        else:
            rationale = pd.Series("", index=labels.index)
        labels = labels[
            labels["task_name"].ne("")
            & labels["unified_category_llm"].ne("")
            & source.ne("error")
            & ~rationale.str.startswith("ERROR:")
        ].copy()
        labels = labels.sort_values("task_name").drop_duplicates("task_name", keep="last")
        tasks = tasks.merge(
            labels[["task_name", "unified_category_llm"]],
            on="task_name",
            how="left",
            validate="many_to_one",
        )
        tb2_mask = tasks["benchmark_version"].astype(str).isin({"2.0", "2.1"})
        has_llm = tb2_mask & tasks["unified_category_llm"].fillna("").astype(str).ne("")
        tasks.loc[has_llm, "unified_category"] = tasks.loc[has_llm, "unified_category_llm"]
        tasks.loc[has_llm, "category_label_source"] = "llm_tb2_to_tb3_tb4_taxonomy"
        tasks = tasks.drop(columns=["unified_category_llm"])

    missing_tb2 = tb2_mask & tasks["category_label_source"].ne("llm_tb2_to_tb3_tb4_taxonomy")
    if not allow_rule_based_tb2_category_fallback and missing_tb2.any():
        examples = tasks.loc[missing_tb2, ["benchmark_version", "task_name", "category"]].head(10)
        raise ValueError(
            "Missing valid LLM TB2 category labels. Run "
            "`python -m scripts.analysis.longitudinal.06_label_tb2_task_categories_with_llm --model gpt-4o-mini` "
            "or pass --allow-rule-based-tb2-category-fallback for exploratory runs. "
            f"Examples: {examples.to_dict(orient='records')}"
        )
    if tasks["unified_category"].eq("Other").any() and not allow_rule_based_tb2_category_fallback:
        examples = tasks.loc[tasks["unified_category"].eq("Other"), ["benchmark_version", "task_name", "category"]].head(10)
        raise ValueError(f"Unmapped task categories remain: {examples.to_dict(orient='records')}")
    return tasks


def build_observed_task_duration(df: pd.DataFrame) -> pd.DataFrame:
    duration_df = df[
        df["duration_seconds"].notna()
        & df["duration_seconds"].ge(0)
        & df["submission_id"].notna()
        & df["submission_id"].astype(str).ne("")
    ].copy()
    duration_df["duration_min"] = duration_df["duration_seconds"] / 60.0
    submission_task = (
        duration_df.groupby(["benchmark_version", "task_name", "submission_id"], as_index=False)
        .agg(
            n_trajectories=("duration_min", "size"),
            submission_task_median_duration_min=("duration_min", "median"),
            submission_task_mean_duration_min=("duration_min", "mean"),
            submission_task_pass_rate=("passed", "mean"),
        )
    )
    task_duration = (
        submission_task.groupby(["benchmark_version", "task_name"], as_index=False)
        .agg(
            n_submissions=("submission_id", "nunique"),
            n_trajectories=("n_trajectories", "sum"),
            observed_median_duration_min=("submission_task_median_duration_min", "median"),
            observed_mean_duration_min=("submission_task_median_duration_min", "mean"),
            observed_p75_duration_min=("submission_task_median_duration_min", lambda values: values.quantile(0.75)),
            task_weighted_pass_rate=("submission_task_pass_rate", "mean"),
        )
    )
    return task_duration


def attach_change_audit(tasks: pd.DataFrame, audit_path: Path) -> pd.DataFrame:
    tasks = tasks.copy()
    tasks["tb3_tb4_change_classification"] = ""
    if not audit_path.exists():
        return tasks
    audit = pd.read_csv(audit_path, usecols=["task_name", "classification"])
    audit = audit.rename(columns={"classification": "tb3_tb4_change_classification"})
    tasks = tasks.merge(audit, on="task_name", how="left", suffixes=("", "_audit"))
    if "tb3_tb4_change_classification_audit" in tasks.columns:
        tasks["tb3_tb4_change_classification"] = tasks[
            "tb3_tb4_change_classification_audit"
        ].fillna(tasks["tb3_tb4_change_classification"])
        tasks = tasks.drop(columns=["tb3_tb4_change_classification_audit"])
    tasks["tb3_tb4_change_classification"] = tasks["tb3_tb4_change_classification"].fillna("")
    return tasks


def distribution_summary(values: pd.Series, prefix: str) -> dict[str, float | int]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            f"{prefix}_n": 0,
            f"{prefix}_mean": np.nan,
            f"{prefix}_median": np.nan,
            f"{prefix}_p25": np.nan,
            f"{prefix}_p75": np.nan,
            f"{prefix}_max": np.nan,
        }
    return {
        f"{prefix}_n": int(clean.shape[0]),
        f"{prefix}_mean": float(clean.mean()),
        f"{prefix}_median": float(clean.median()),
        f"{prefix}_p25": float(clean.quantile(0.25)),
        f"{prefix}_p75": float(clean.quantile(0.75)),
        f"{prefix}_max": float(clean.max()),
    }


def build_version_summary(task_version: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for version in VERSIONS:
        subset = task_version[task_version["benchmark_version"].eq(version)].copy()
        if subset.empty:
            continue
        row: dict[str, object] = {
            "benchmark_version": version,
            "version_label": VERSION_LABELS[version],
            "n_tasks": int(subset["task_name"].nunique()),
            "n_categories": int(subset["category"].nunique()),
            "n_unified_categories": int(subset["unified_category"].nunique()),
            "n_tasks_with_expert_estimate": int(subset["expert_time_estimate_min"].notna().sum()),
            "n_tasks_with_junior_estimate": int(subset["junior_time_estimate_min"].notna().sum()),
            "n_tasks_with_observed_duration": int(subset["observed_median_duration_min"].notna().sum()),
        }
        row.update(distribution_summary(subset["expert_time_estimate_min"], "expert_estimate_min"))
        row.update(distribution_summary(subset["junior_time_estimate_min"], "junior_estimate_min"))
        row.update(distribution_summary(subset["agent_timeout_sec"] / 60.0, "agent_timeout_min"))
        row.update(distribution_summary(subset["observed_median_duration_min"], "observed_task_median_duration_min"))
        row.update(distribution_summary(subset["task_weighted_pass_rate"], "task_weighted_pass_rate"))
        rows.append(row)
    return pd.DataFrame(rows)


def build_category_summary(task_version: pd.DataFrame) -> pd.DataFrame:
    grouped = task_version.groupby(
        ["benchmark_version", "unified_category", "category", "category_label_source"],
        dropna=False,
    )
    rows: list[dict[str, object]] = []
    totals = task_version.groupby("benchmark_version")["task_name"].nunique().to_dict()
    for (version, unified_category, category, category_label_source), subset in grouped:
        n_tasks = int(subset["task_name"].nunique())
        row: dict[str, object] = {
            "benchmark_version": version,
            "version_label": VERSION_LABELS.get(str(version), str(version)),
            "unified_category": unified_category,
            "category": category,
            "category_label_source": category_label_source,
            "n_tasks": n_tasks,
            "task_share": n_tasks / totals.get(version, n_tasks) if totals.get(version) else np.nan,
            "n_tasks_with_observed_duration": int(subset["observed_median_duration_min"].notna().sum()),
            "median_task_weighted_pass_rate": float(subset["task_weighted_pass_rate"].median())
            if subset["task_weighted_pass_rate"].notna().any()
            else np.nan,
        }
        row.update(distribution_summary(subset["expert_time_estimate_min"], "expert_estimate_min"))
        row.update(distribution_summary(subset["observed_median_duration_min"], "observed_task_median_duration_min"))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["benchmark_version", "unified_category", "category"])


def ratio_change(new: pd.Series, old: pd.Series) -> pd.Series:
    old = pd.to_numeric(old, errors="coerce")
    new = pd.to_numeric(new, errors="coerce")
    return (new / old.replace(0, np.nan) - 1.0) * 100.0


def build_adjacent_changes(task_version: pd.DataFrame) -> pd.DataFrame:
    fields = [
        "expert_time_estimate_min",
        "junior_time_estimate_min",
        "agent_timeout_sec",
        "observed_median_duration_min",
        "observed_mean_duration_min",
        "task_weighted_pass_rate",
        "category",
        "unified_category",
        "category_label_source",
        "difficulty",
        "tb3_tb4_change_classification",
    ]
    rows: list[pd.DataFrame] = []
    base = task_version[["benchmark_version", "task_name", *fields]].copy()
    for old_version, new_version in ADJACENT_VERSION_PAIRS:
        old = base[base["benchmark_version"].eq(old_version)].drop(columns=["benchmark_version"])
        new = base[base["benchmark_version"].eq(new_version)].drop(columns=["benchmark_version"])
        paired = old.merge(new, on="task_name", how="inner", suffixes=("_old", "_new"))
        if paired.empty:
            continue
        paired.insert(0, "version_pair", f"{old_version}->{new_version}")
        paired.insert(1, "old_version", old_version)
        paired.insert(2, "new_version", new_version)
        for column in [
            "expert_time_estimate_min",
            "junior_time_estimate_min",
            "agent_timeout_sec",
            "observed_median_duration_min",
            "observed_mean_duration_min",
            "task_weighted_pass_rate",
        ]:
            paired[f"{column}_change"] = paired[f"{column}_new"] - paired[f"{column}_old"]
            paired[f"{column}_relative_change_pct"] = ratio_change(
                paired[f"{column}_new"], paired[f"{column}_old"]
            )
        rows.append(paired)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True).sort_values(["version_pair", "task_name"])


def format_minutes(value: float) -> str:
    if pd.isna(value):
        return "NA"
    if value < 60:
        return f"{value:.0f}m"
    hours = value / 60.0
    if hours < 24:
        return f"{hours:.1f}h".replace(".0h", "h")
    return f"{hours / 24.0:.1f}d".replace(".0d", "d")


def plot_composition(task_version: pd.DataFrame, category_summary: pd.DataFrame, out: Path) -> None:
    thesis_style()
    fig, ax = plt.subplots(figsize=(7.2, 3.15))

    category_order = (
        category_summary.groupby("unified_category")["n_tasks"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    colors = {category: color for category, color in zip(category_order, colorblind_cycle(len(category_order)))}
    colors.setdefault("Other", OTHER_COLOR)

    pivot = (
        task_version.groupby(["benchmark_version", "unified_category"])["task_name"]
        .nunique()
        .unstack(fill_value=0)
        .reindex(index=VERSIONS, columns=category_order, fill_value=0)
    )
    shares = pivot.div(pivot.sum(axis=1), axis=0).fillna(0.0)
    left = np.zeros(len(shares))
    x = np.arange(len(shares))
    for category in category_order:
        ax.bar(
            x,
            shares[category].to_numpy(),
            bottom=left,
            color=colors[category],
            edgecolor="white",
            linewidth=0.5,
            label=category,
        )
        left += shares[category].to_numpy()
    ax.set_title("Task Composition by Terminal-Bench Version")
    ax.set_ylabel("Share of tasks")
    ax.set_xticks(x)
    ax.set_xticklabels([VERSION_LABELS[v] for v in VERSIONS])
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=7, fontsize=8)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=0.75)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def boxplot_metric(ax: plt.Axes, task_version: pd.DataFrame, column: str, title: str, ylabel: str) -> None:
    data = [
        task_version.loc[task_version["benchmark_version"].eq(version), column].dropna().to_numpy()
        for version in VERSIONS
    ]
    ax.boxplot(
        data,
        tick_labels=[VERSION_LABELS[v] for v in VERSIONS],
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "#111111", "linewidth": 1.2},
        boxprops={"facecolor": "#E8E8E8", "edgecolor": "#555555"},
        whiskerprops={"color": "#555555"},
        capprops={"color": "#555555"},
    )
    for position, values in enumerate(data, start=1):
        if len(values) == 0:
            continue
        jitter = np.linspace(-0.12, 0.12, len(values)) if len(values) > 1 else np.array([0.0])
        ax.scatter(
            np.full(len(values), position) + jitter,
            values,
            s=13,
            color=COLORBLIND_PALETTE[(position - 1) % len(COLORBLIND_PALETTE)],
            alpha=0.42,
            linewidths=0,
            zorder=2,
        )
        median = float(np.median(values))
        ax.text(position, median, format_minutes(median), ha="center", va="bottom", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color="#D0D0D0", alpha=0.5, linewidth=0.7)
    ax.set_axisbelow(True)


def plot_time_estimates(task_version: pd.DataFrame, out: Path) -> None:
    thesis_style()
    task_version = task_version.copy()
    task_version["agent_timeout_min"] = task_version["agent_timeout_sec"] / 60.0
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.15))

    boxplot_metric(
        axes[0],
        task_version,
        "expert_time_estimate_min",
        "Expert Estimates",
        "Minutes per task",
    )
    boxplot_metric(
        axes[1],
        task_version,
        "agent_timeout_min",
        "Agent Timeout",
        "Minutes per task",
    )
    boxplot_metric(
        axes[2],
        task_version,
        "observed_median_duration_min",
        "Observed Run Duration",
        "Task median minutes",
    )
    axes[0].set_yscale("symlog", linthresh=60)
    axes[1].set_yscale("symlog", linthresh=60)
    axes[2].set_yscale("symlog", linthresh=10)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=0.8)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def print_headline(version_summary: pd.DataFrame, adjacent_changes: pd.DataFrame, figure_paths: list[Path]) -> None:
    print("Task composition and time summary")
    print("version,n_tasks,expert_median,expert_p75,observed_task_median_duration_median")
    for row in version_summary.itertuples(index=False):
        print(
            f"{row.benchmark_version},{row.n_tasks},"
            f"{format_minutes(row.expert_estimate_min_median)},"
            f"{format_minutes(row.expert_estimate_min_p75)},"
            f"{format_minutes(row.observed_task_median_duration_min_median)}"
        )
    if not adjacent_changes.empty:
        print("")
        print("Adjacent version shared-task counts")
        counts = adjacent_changes.groupby("version_pair")["task_name"].nunique()
        for pair, count in counts.items():
            print(f"{pair}: {count} shared tasks")
    for figure_path in figure_paths:
        print(f"Wrote figure to {figure_path}")


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    trajectories = load_longitudinal([args.tb2_longitudinal, args.tb3_tb4_longitudinal])
    task_metadata = build_task_metadata(trajectories)
    task_metadata = attach_unified_categories(
        task_metadata,
        args.tb2_category_labels,
        args.allow_rule_based_tb2_category_fallback,
    )
    observed_duration = build_observed_task_duration(trajectories)
    task_version = task_metadata.merge(
        observed_duration,
        on=["benchmark_version", "task_name"],
        how="left",
        validate="one_to_one",
    )
    task_version = attach_change_audit(task_version, args.tb3_tb4_audit)
    version_summary = build_version_summary(task_version)
    category_summary = build_category_summary(task_version)
    adjacent_changes = build_adjacent_changes(task_version)

    version_summary_path = args.out_dir / "version_task_composition_summary.csv"
    category_summary_path = args.out_dir / "category_composition_by_version.csv"
    adjacent_changes_path = args.out_dir / "adjacent_version_task_changes.csv"
    composition_figure_path = args.figures_dir / "task_composition_over_versions.png"
    time_figure_path = args.figures_dir / "task_time_estimates_over_versions.png"

    version_summary.to_csv(version_summary_path, index=False)
    category_summary.to_csv(category_summary_path, index=False)
    adjacent_changes.to_csv(adjacent_changes_path, index=False)
    plot_composition(task_version, category_summary, composition_figure_path)
    plot_time_estimates(task_version, time_figure_path)

    print_headline(version_summary, adjacent_changes, [composition_figure_path, time_figure_path])
    print(f"Wrote {version_summary_path}")
    print(f"Wrote {category_summary_path}")
    print(f"Wrote {adjacent_changes_path}")


if __name__ == "__main__":
    main()
