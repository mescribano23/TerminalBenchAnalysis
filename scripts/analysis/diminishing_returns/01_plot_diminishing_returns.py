#!/usr/bin/env python3
"""Descriptive RQ1 effort-bin figures.

This script regenerates the full reports/diminishing_returns figure tree from
trajectory-level data. The pooled estimates remain trajectory-level. The
task-balanced estimates bin trajectories first, then average within
effective-submission/task/bin cells before averaging over tasks. It
intentionally contains no statistical modeling.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

from scripts.benchmark_paths import find_repo_root
from scripts.analysis.plot_style import (
    FAIL_COLOR,
    HEATMAP_DPI,
    PASS_COLOR,
    colorblind_cmap,
    heatmap_text_color,
)
from scripts.analysis.submission_task_balancing import EFFECTIVE_SUBMISSION_ID, ensure_effective_submission_id


REPO_ROOT = find_repo_root(Path(__file__).resolve().parent)
INPUT_DEFAULT = REPO_ROOT / "data" / "processed_live" / "terminal_bench_2_0" / "trajectory_summary.csv"
OUT_DEFAULT = REPO_ROOT / "data" / "processed_live" / "diminishing_returns"
FIGURES_DEFAULT = REPO_ROOT / "reports" / "diminishing_returns"
TASK_BALANCED_DEFAULT = (
    REPO_ROOT / "data" / "processed_live" / "terminal_bench_2_0" / "rq1_task_balanced_effort_success.csv"
)

EFFORT_VARIABLES = [
    "step_count",
    "shell_invocation_count",
    "tool_call_count",
    "total_tokens",
    "duration_seconds",
    "cost_usd_positive",
]
BIN_ROBUSTNESS_VARIABLES = EFFORT_VARIABLES
TASK_BALANCED_VARIABLES = EFFORT_VARIABLES
TASK_BALANCED_FIGURE_VARIABLES = ["step_count", "duration_seconds", "total_tokens", "cost_usd_positive"]

MODEL_PROVIDER_HEATMAPS = ["OpenAI", "Anthropic", "Google", "DeepSeek"]
OPEN_SOURCE_MODEL_KEYWORDS = (
    "deepseek",
    "glm",
    "gpt-oss",
    "kimi",
    "minimax",
    "qwen",
)

DISPLAY_NAMES = {
    "step_count": "Step count",
    "shell_invocation_count": "Shell invocation count",
    "tool_call_count": "Structured tool call count",
    "total_tokens": "Total tokens",
    "duration_seconds": "Duration seconds",
    "cost_usd_positive": "Positive cost USD",
}

LOG_SCALE_BOX_VARIABLES = {"total_tokens", "cost_usd_positive"}


def compact_count_tick(value: float, _position: int) -> str:
    if value <= 0 or not np.isfinite(value):
        return ""
    if value >= 1_000_000:
        number = value / 1_000_000
        return f"{number:g}M"
    if value >= 1_000:
        number = value / 1_000
        return f"{number:g}k"
    return f"{value:g}"


def compact_cost_tick(value: float, _position: int) -> str:
    if value <= 0 or not np.isfinite(value):
        return ""
    if value >= 1:
        return f"${value:g}"
    return f"${value:.3g}"

BIN_SPECS = {
    "step_count": ([0, 10, 25, 50, 100, 200, math.inf], ["0-10", "11-25", "26-50", "51-100", "101-200", ">200"]),
    "shell_invocation_count": ([-0.5, 0.5, 5, 15, 40, math.inf], ["0", "1-5", "6-15", "16-40", ">40"]),
    "tool_call_count": ([-0.5, 5, 15, 35, 75, 150, math.inf], ["0-5", "6-15", "16-35", "36-75", "76-150", ">150"]),
    "total_tokens": (
        [-0.5, 10_000, 100_000, 500_000, 1_000_000, 3_000_000, 10_000_000, math.inf],
        ["0-10k", "10k-100k", "100k-500k", "500k-1M", "1M-3M", "3M-10M", ">10M"],
    ),
    "duration_seconds": (
        [-0.000001, 10, 60, 300, 900, 1800, 3600, math.inf],
        ["0-10s", "10-60s", "1-5m", "5-15m", "15-30m", "30-60m", ">60m"],
    ),
    "cost_usd_positive": (
        [0, 0.001, 0.01, 0.05, 0.10, 0.50, 1.00, math.inf],
        ["<=$0.001", "$0.001-0.01", "$0.01-0.05", "$0.05-0.10", "$0.10-0.50", "$0.50-1", ">$1"],
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DEFAULT)
    parser.add_argument("--task-balanced-out", type=Path, default=TASK_BALANCED_DEFAULT)
    return parser.parse_args()


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    if "reward" not in df.columns:
        raise ValueError(f"{path} must contain a reward column.")

    df["reward"] = pd.to_numeric(df["reward"], errors="coerce")
    df = df[df["reward"].isin([0, 1])].copy()
    if df.empty:
        raise ValueError("No rows with binary reward values 0 or 1 were found.")
    df["passed"] = df["reward"].astype(int)

    required_numeric = [
        "step_count",
        "shell_invocation_count",
        "tool_call_count",
        "total_tokens",
        "duration_seconds",
        "cost_usd",
    ]
    missing = [column for column in required_numeric if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    for column in required_numeric:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["total_tokens"] = df["total_tokens"].where(df["total_tokens"] > 0)

    if "scaffold" not in df.columns:
        raise ValueError("trajectory_summary.csv must contain a scaffold column.")
    df["scaffold"] = df["scaffold"].fillna("unknown").astype(str)

    if "model_dir" not in df.columns:
        raise ValueError("trajectory_summary.csv must contain a model_dir column.")
    df["model_dir"] = df["model_dir"].fillna("unknown").astype(str)

    if "leaderboard_model_organization" in df.columns:
        df["leaderboard_model_organization"] = (
            df["leaderboard_model_organization"].fillna("unknown").astype(str).replace({"Minimax": "MiniMax"})
        )

    df["cost_usd_positive"] = df["cost_usd"].where(df["cost_usd"] > 0)
    return ensure_effective_submission_id(df)


def bin_series(series: pd.Series, variable: str) -> pd.Categorical:
    edges, labels = BIN_SPECS[variable]
    return pd.cut(series, bins=edges, labels=labels, include_lowest=True, right=True, ordered=True)


def build_effort_bins(df: pd.DataFrame, group_column: str | None = None) -> pd.DataFrame:
    if group_column is not None and group_column not in df.columns:
        raise ValueError(f"Cannot build grouped plots because {group_column!r} is missing.")

    rows: list[dict[str, object]] = []
    for variable in EFFORT_VARIABLES:
        columns = [variable, "passed", "task_name"] if group_column is None else [group_column, variable, "passed", "task_name"]
        work = df[columns].dropna().copy()
        work["effort_bin"] = bin_series(work[variable], variable)
        groups = [(None, work)] if group_column is None else work.groupby(group_column)

        for group_value, group_frame in groups:
            for bin_order, (label, bin_group) in enumerate(group_frame.groupby("effort_bin", observed=False), start=1):
                n = int(len(bin_group))
                passes = int(bin_group["passed"].sum()) if n else 0
                task_count = int(bin_group["task_name"].nunique()) if n else 0
                row = {
                    "metric": variable,
                    "variable": variable,
                    "variable_display": DISPLAY_NAMES[variable],
                    "bin_order": bin_order,
                    "bin_label": str(label),
                    "effort_bin": str(label),
                    "bin_lower": BIN_SPECS[variable][0][bin_order - 1],
                    "bin_upper": BIN_SPECS[variable][0][bin_order],
                    "trajectory_count": n,
                    "n": n,
                    "task_count": task_count,
                    "pass_count": passes,
                    "pass_rate": passes / n if n else None,
                    "success_rate": passes / n if n else None,
                }
                if group_column is not None:
                    row.update({"group_column": group_column, "group_value": str(group_value)})
                rows.append(row)
    return pd.DataFrame(rows)


def build_task_balanced_effort_success(df: pd.DataFrame, pooled_bins: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    pooled_lookup = pooled_bins.set_index(["metric", "bin_order"])

    for variable in TASK_BALANCED_VARIABLES:
        work = df[[EFFECTIVE_SUBMISSION_ID, "task_name", variable, "passed"]].dropna().copy()
        if work.empty:
            continue
        work["effort_bin"] = bin_series(work[variable], variable)
        _, labels = BIN_SPECS[variable]

        for bin_order, label in enumerate(labels, start=1):
            bin_group = work[work["effort_bin"].astype(str).eq(label)].copy()
            pooled_row = pooled_lookup.loc[(variable, bin_order)]
            if bin_group.empty:
                submission_task_rates = pd.DataFrame()
                task_rates = np.array([], dtype=float)
            else:
                submission_task_rates = (
                    bin_group.groupby([EFFECTIVE_SUBMISSION_ID, "task_name"], as_index=False)
                    .agg(
                        submission_task_bin_trajectory_count=("passed", "size"),
                        submission_task_bin_pass_rate=("passed", "mean"),
                    )
                )
                task_rates = (
                    submission_task_rates.groupby("task_name")["submission_task_bin_pass_rate"]
                    .mean()
                    .to_numpy(dtype=float)
                )
            rows.append(
                {
                    "metric": variable,
                    "metric_display": DISPLAY_NAMES[variable],
                    "bin_order": bin_order,
                    "bin_label": label,
                    "effort_bin": label,
                    "bin_lower": BIN_SPECS[variable][0][bin_order - 1],
                    "bin_upper": BIN_SPECS[variable][0][bin_order],
                    "trajectory_count": int(pooled_row["trajectory_count"]),
                    "task_count": int(pooled_row["task_count"]),
                    "submission_task_bin_count": int(len(submission_task_rates)),
                    "pass_count": int(pooled_row["pass_count"]),
                    "pooled_pass_rate": float(pooled_row["pass_rate"]) if pd.notna(pooled_row["pass_rate"]) else np.nan,
                    "task_balanced_pass_rate": float(task_rates.mean()) if len(task_rates) else np.nan,
                }
            )

    return pd.DataFrame(rows)


def task_balanced_change_summary(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if old.empty or "task_balanced_pass_rate" not in old.columns:
        return pd.DataFrame()
    keys = ["metric", "bin_order", "bin_label"]
    merged = old[keys + ["task_balanced_pass_rate"]].rename(
        columns={"task_balanced_pass_rate": "old_task_balanced_pass_rate"}
    ).merge(
        new[keys + ["task_balanced_pass_rate"]].rename(
            columns={"task_balanced_pass_rate": "corrected_task_balanced_pass_rate"}
        ),
        on=keys,
        how="inner",
    )
    if merged.empty:
        return pd.DataFrame()
    merged["change_pp"] = 100 * (
        merged["corrected_task_balanced_pass_rate"] - merged["old_task_balanced_pass_rate"]
    )

    rows: list[dict[str, object]] = []
    for metric, group in merged.groupby("metric"):
        max_row = group.loc[group["change_pp"].abs().idxmax()]
        rows.append(
            {
                "metric": metric,
                "max_abs_change_pp": float(group["change_pp"].abs().max()),
                "max_change_bin": max_row["bin_label"],
                "max_change_pp": float(max_row["change_pp"]),
            }
        )
    return pd.DataFrame(rows)


def qualitative_pattern(rates: pd.Series) -> str:
    values = rates.dropna().to_numpy(dtype=float)
    if len(values) < 2:
        return "insufficient_data"
    peak_index = int(np.argmax(values))
    if peak_index < len(values) - 1 and values[peak_index] - values[-1] >= 0.05:
        return "increases_then_declines"
    if abs(values[-1] - values[0]) < 0.03:
        return "plateaus_or_flat"
    if values[-1] > values[0]:
        return "increases"
    return "declines"


def build_quantile_bins(df: pd.DataFrame, q: int = 5) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for variable in BIN_ROBUSTNESS_VARIABLES:
        work = df[[variable, "passed"]].dropna().copy()
        if work.empty:
            continue
        work["effort_bin"] = pd.qcut(work[variable], q=q, duplicates="drop")
        for bin_order, (label, bin_group) in enumerate(work.groupby("effort_bin", observed=True), start=1):
            n = int(len(bin_group))
            passes = int(bin_group["passed"].sum())
            interval = label if isinstance(label, pd.Interval) else None
            rows.append(
                {
                    "metric": variable,
                    "metric_display": DISPLAY_NAMES[variable],
                    "scheme": "equal_frequency_quantile",
                    "bin_order": bin_order,
                    "bin_label": str(label),
                    "bin_lower": interval.left if interval is not None else None,
                    "bin_upper": interval.right if interval is not None else None,
                    "n": n,
                    "pass_count": passes,
                    "pass_rate": passes / n if n else None,
                }
            )
    return pd.DataFrame(rows)


def build_bin_robustness_summary(fixed_bins: pd.DataFrame, quantile_bins: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for variable in BIN_ROBUSTNESS_VARIABLES:
        fixed = fixed_bins[(fixed_bins["variable"].eq(variable)) & (fixed_bins["n"] > 0)].sort_values("bin_order")
        quantile = quantile_bins[quantile_bins["metric"].eq(variable)].sort_values("bin_order")
        fixed_pattern = qualitative_pattern(fixed["pass_rate"])
        quantile_pattern = qualitative_pattern(quantile["pass_rate"])
        rows.append(
            {
                "metric": variable,
                "metric_display": DISPLAY_NAMES[variable],
                "fixed_bin_count": int(fixed.shape[0]),
                "quantile_bin_count": int(quantile.shape[0]),
                "fixed_pattern": fixed_pattern,
                "quantile_pattern": quantile_pattern,
                "qualitative_result_changed": fixed_pattern != quantile_pattern,
                "fixed_first_pass_rate": float(fixed["pass_rate"].iloc[0]) if not fixed.empty else None,
                "fixed_peak_pass_rate": float(fixed["pass_rate"].max()) if not fixed.empty else None,
                "fixed_last_pass_rate": float(fixed["pass_rate"].iloc[-1]) if not fixed.empty else None,
                "quantile_first_pass_rate": float(quantile["pass_rate"].iloc[0]) if not quantile.empty else None,
                "quantile_peak_pass_rate": float(quantile["pass_rate"].max()) if not quantile.empty else None,
                "quantile_last_pass_rate": float(quantile["pass_rate"].iloc[-1]) if not quantile.empty else None,
            }
        )
    return pd.DataFrame(rows)


def heatmap_frames(subset: pd.DataFrame, variable: str) -> tuple[list[str], list[str], pd.DataFrame, pd.DataFrame]:
    _, labels = BIN_SPECS[variable]
    order_frame = (
        subset.groupby("group_value", as_index=False)
        .agg(pass_count=("pass_count", "sum"), n=("n", "sum"))
        .assign(overall_success_rate=lambda frame: frame["pass_count"] / frame["n"])
        .sort_values(["overall_success_rate", "n", "group_value"], ascending=[False, False, True])
    )
    group_order = order_frame["group_value"].tolist()
    heatmap = subset.pivot(index="group_value", columns="effort_bin", values="success_rate").reindex(
        index=group_order,
        columns=labels,
    )
    counts = subset.pivot(index="group_value", columns="effort_bin", values="n").reindex(
        index=group_order,
        columns=labels,
    )
    return labels, group_order, heatmap.astype(float), counts.fillna(0).astype(int)


def plot_overall_series(ax: plt.Axes, subset: pd.DataFrame) -> None:
    x = subset["bin_order"].to_numpy(dtype=float)
    y = subset["success_rate"].to_numpy(dtype=float)
    ax.bar(x, y, width=0.72, color=PASS_COLOR, alpha=0.88)


def plot_grouped_heatmap(
    subset: pd.DataFrame,
    variable: str,
    group_label: str,
    annotation_fontsize: float = 8.0,
) -> plt.Figure:
    labels, group_order, heatmap, counts = heatmap_frames(subset, variable)
    row_count = max(1, len(group_order))
    figure_height = min(14.0, max(4.8, 1.6 + row_count * 0.34))
    fig, ax = plt.subplots(figsize=(10.5, figure_height))

    cmap = colorblind_cmap()
    matrix = np.ma.masked_invalid(heatmap.to_numpy(dtype=float))
    image = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_yticks(range(len(group_order)))
    ax.set_yticklabels(group_order, fontsize=8 if row_count > 20 else 9)
    ax.set_xlabel(DISPLAY_NAMES[variable])
    ax.set_ylabel(group_label[:1].upper() + group_label[1:])
    ax.set_title(f"Terminal-Bench success rate by {DISPLAY_NAMES[variable].lower()} and {group_label}")

    ax.set_xticks(np.arange(-0.5, len(labels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, row_count, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.0)
    ax.tick_params(which="minor", bottom=False, left=False)

    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    colorbar.set_label("Success rate")

    if row_count <= 18:
        for row_index, group_value in enumerate(group_order):
            for column_index, label in enumerate(labels):
                rate = heatmap.loc[group_value, label]
                n = counts.loc[group_value, label]
                if pd.isna(rate) or n == 0:
                    continue
                text_color = heatmap_text_color(float(rate), cmap, 0, 1)
                ax.text(
                    column_index,
                    row_index,
                    f"{rate:.0%}\nn={n}",
                    ha="center",
                    va="center",
                    fontsize=annotation_fontsize,
                    color=text_color,
                )

    return fig


def plot_effort_bins(
    bins: pd.DataFrame,
    figures_dir: Path,
    group_column: str | None = None,
) -> list[Path]:
    paths: list[Path] = []
    group_label = {"scaffold": "scaffold", "model_dir": "model"}.get(group_column)
    output_dir = figures_dir / "effort_bins" if group_label is None else figures_dir / f"by_{group_label}"
    output_dir.mkdir(parents=True, exist_ok=True)

    for variable in EFFORT_VARIABLES:
        subset = bins[(bins["variable"] == variable) & (bins["n"] > 0)].sort_values("bin_order")
        if subset.empty:
            continue

        if group_label is None:
            fig, ax = plt.subplots(figsize=(8.5, 4.8))
            plot_overall_series(ax, subset)
            _, labels = BIN_SPECS[variable]
            ax.set_xticks(range(1, len(labels) + 1))
            ax.set_xticklabels(labels, rotation=25, ha="right")
            ax.set_ylim(0, 1)
            ax.set_ylabel("Success rate")
            ax.set_xlabel(DISPLAY_NAMES[variable])
            ax.set_title(f"Terminal-Bench success rate by {DISPLAY_NAMES[variable].lower()}")
            ax.grid(axis="y", alpha=0.25)
        else:
            fig = plot_grouped_heatmap(subset, variable, group_label)
        fig.tight_layout()

        heatmap_suffix = "_heatmap" if group_label is not None else ""
        path = output_dir / f"diminishing_returns_{variable}{heatmap_suffix}.png"
        fig.savefig(path, dpi=HEATMAP_DPI if group_label is not None else 180)
        plt.close(fig)
        paths.append(path)

    return paths


def plot_pooled_vs_task_balanced(task_balanced: pd.DataFrame, figures_dir: Path) -> Path | None:
    output_dir = figures_dir / "effort_bins"
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_data = task_balanced[task_balanced["metric"].isin(TASK_BALANCED_FIGURE_VARIABLES)].copy()
    if plot_data.empty:
        return None

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.0), sharey=True)
    axes = axes.ravel()
    colors = {"pooled": PASS_COLOR, "task_balanced": FAIL_COLOR}

    for ax, variable in zip(axes, TASK_BALANCED_FIGURE_VARIABLES):
        subset = plot_data[plot_data["metric"].eq(variable)].sort_values("bin_order")
        subset = subset[subset["trajectory_count"] > 0]
        if subset.empty:
            continue
        x = np.arange(len(subset), dtype=float)
        pooled = subset["pooled_pass_rate"].to_numpy(dtype=float)
        balanced = subset["task_balanced_pass_rate"].to_numpy(dtype=float)
        width = 0.38

        ax.bar(x - width / 2, pooled, width=width, color=colors["pooled"], label="Pooled")
        ax.bar(x + width / 2, balanced, width=width, color=colors["task_balanced"], label="Task-balanced")
        ax.set_title(DISPLAY_NAMES[variable])
        ax.set_xticks(x)
        ax.set_xticklabels(subset["bin_label"].tolist(), rotation=28, ha="right")
        ax.set_xlabel(DISPLAY_NAMES[variable])
        ax.set_ylim(0, 1)
        ax.grid(axis="y", alpha=0.25)

    axes[0].set_ylabel("Pass rate")
    axes[2].set_ylabel("Pass rate")
    axes[-1].legend(frameon=False, loc="upper right")
    fig.suptitle("Pooled vs task-balanced effort-bin success rates", y=0.995)
    fig.tight_layout()
    path = output_dir / "rq1_pooled_vs_task_balanced_effort_success.png"
    fig.savefig(path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return path


def is_open_source_model(row: pd.Series) -> bool:
    model_text = " ".join(
        str(row.get(column, "")).lower().replace("_", "-")
        for column in ["model_dir", "model_name"]
    )
    return any(keyword in model_text for keyword in OPEN_SOURCE_MODEL_KEYWORDS)


def plot_model_provider_heatmaps(
    df: pd.DataFrame,
    figures_dir: Path,
    output_name: str,
    title_suffix: str = "",
) -> list[Path]:
    if "leaderboard_model_organization" not in df.columns:
        return []

    output_dir = figures_dir / "by_model" / output_name
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    provider_bins: dict[str, pd.DataFrame] = {}
    for provider in MODEL_PROVIDER_HEATMAPS:
        provider_df = df[df["leaderboard_model_organization"].eq(provider)].copy()
        if not provider_df.empty:
            provider_bins[provider] = build_effort_bins(provider_df, group_column="model_dir")

    for variable in EFFORT_VARIABLES:
        panels: list[tuple[str, pd.DataFrame, pd.DataFrame, list[str]]] = []

        for provider, bins in provider_bins.items():
            subset = bins[(bins["variable"] == variable) & (bins["n"] > 0)].sort_values("bin_order")
            if subset.empty:
                continue

            labels, group_order, heatmap, counts = heatmap_frames(subset, variable)
            panels.append((provider, heatmap, counts, group_order))

        if not panels:
            continue

        row_counts = [max(1, len(group_order)) for _, _, _, group_order in panels]
        figure_height = min(18.0, max(7.0, 2.4 + sum(row_counts) * 0.33 + len(panels) * 0.45))
        fig, axes = plt.subplots(
            len(panels),
            1,
            figsize=(11.8, figure_height),
            sharex=True,
            gridspec_kw={"height_ratios": row_counts},
        )
        axes = np.atleast_1d(axes)
        cmap = colorblind_cmap()
        image = None

        for ax, (provider, heatmap, counts, group_order), row_count in zip(axes, panels, row_counts):
            matrix = np.ma.masked_invalid(heatmap.to_numpy(dtype=float))
            image = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1)
            ax.set_yticks(range(len(group_order)))
            ax.set_yticklabels(group_order, fontsize=8 if row_count > 12 else 9)
            ax.set_ylabel(provider)
            ax.set_title(f"{provider} models", loc="left", fontsize=10, pad=6)
            ax.set_xticks(np.arange(-0.5, len(labels), 1), minor=True)
            ax.set_yticks(np.arange(-0.5, row_count, 1), minor=True)
            ax.grid(which="minor", color="white", linewidth=1.0)
            ax.tick_params(which="minor", bottom=False, left=False)

            for row_index, group_value in enumerate(group_order):
                for column_index, label in enumerate(labels):
                    rate = heatmap.loc[group_value, label]
                    n = counts.loc[group_value, label]
                    if pd.isna(rate) or n == 0:
                        continue
                    text_color = heatmap_text_color(float(rate), cmap, 0, 1)
                    ax.text(
                        column_index,
                        row_index,
                        f"{rate:.0%}\nn={n}",
                        ha="center",
                        va="center",
                        fontsize=7.5,
                        color=text_color,
                    )

        axes[-1].set_xticks(range(len(labels)))
        axes[-1].set_xticklabels(labels, rotation=30, ha="right")
        axes[-1].set_xlabel(DISPLAY_NAMES[variable])
        for ax in axes[:-1]:
            ax.tick_params(labelbottom=False)

        fig.suptitle(
            f"Terminal-Bench success rate by {DISPLAY_NAMES[variable].lower()} and model, facetted by provider{title_suffix}",
            y=0.995,
        )
        fig.subplots_adjust(top=0.95, bottom=0.09, left=0.29, right=0.84, hspace=0.38)
        if image is not None:
            colorbar_ax = fig.add_axes([0.885, 0.36, 0.018, 0.28])
            colorbar = fig.colorbar(image, cax=colorbar_ax)
            colorbar.set_label("Success rate")

        path = output_dir / f"diminishing_returns_{variable}_heatmap.png"
        fig.savefig(path, dpi=HEATMAP_DPI)
        plt.close(fig)
        paths.append(path)

    return paths


def plot_provider_heatmaps(df: pd.DataFrame, figures_dir: Path) -> list[Path]:
    if "leaderboard_model_organization" not in df.columns:
        return []

    output_dir = figures_dir / "by_model" / "by_provider"
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    provider_bins = build_effort_bins(df, group_column="leaderboard_model_organization")

    for variable in EFFORT_VARIABLES:
        subset = provider_bins[(provider_bins["variable"] == variable) & (provider_bins["n"] > 0)].sort_values(
            "bin_order"
        )
        if subset.empty:
            continue

        fig = plot_grouped_heatmap(subset, variable, "provider")
        fig.tight_layout()
        path = output_dir / f"diminishing_returns_{variable}_heatmap.png"
        fig.savefig(path, dpi=HEATMAP_DPI)
        plt.close(fig)
        paths.append(path)

    return paths


def plot_model_provider_source_heatmaps(df: pd.DataFrame, figures_dir: Path) -> list[Path]:
    source_mask = df.apply(is_open_source_model, axis=1)
    paths: list[Path] = []
    paths.extend(
        plot_model_provider_heatmaps(
            df[~source_mask].copy(),
            figures_dir,
            output_name="by_provider_closed_source",
            title_suffix=" (closed-source models)",
        )
    )
    return paths


def plot_effort_performance_box_plots(df: pd.DataFrame, figures_dir: Path) -> list[Path]:
    paths: list[Path] = []
    output_dir = figures_dir / "by_outcome" / "box_plots"
    output_dir.mkdir(parents=True, exist_ok=True)

    for variable in EFFORT_VARIABLES:
        subset = df[[variable, "passed"]].dropna().copy()
        if subset.empty:
            continue

        grouped_values = {
            0: subset.loc[subset["passed"] == 0, variable].to_numpy(dtype=float),
            1: subset.loc[subset["passed"] == 1, variable].to_numpy(dtype=float),
        }
        if not any(len(values) for values in grouped_values.values()):
            continue

        fig, ax = plt.subplots(figsize=(6.8, 5.4))
        for outcome_value, color, position in [(0, FAIL_COLOR, 1), (1, PASS_COLOR, 2)]:
            values = grouped_values[outcome_value]
            if len(values) == 0:
                continue

            parts = ax.violinplot(
                [values],
                positions=[position],
                orientation="vertical",
                widths=0.58,
                showmeans=False,
                showmedians=False,
                showextrema=False,
            )
            for body in parts["bodies"]:
                body.set_facecolor(color)
                body.set_edgecolor("#2f3337")
                body.set_alpha(0.42)

            ax.boxplot(
                [values],
                positions=[position],
                widths=0.25,
                patch_artist=True,
                showfliers=False,
                boxprops={"facecolor": "#ffffff", "edgecolor": "#243b4a", "linewidth": 1.1},
                medianprops={"color": "#1f2d3a", "linewidth": 1.7},
                whiskerprops={"color": "#243b4a", "linewidth": 1.0},
                capprops={"color": "#243b4a", "linewidth": 1.0},
            )

        ax.set_xticks([1, 2])
        ax.set_xticklabels([f"Fail\nn={len(grouped_values[0]):,}", f"Pass\nn={len(grouped_values[1]):,}"])
        ax.set_xlim(0.45, 2.55)
        if variable in LOG_SCALE_BOX_VARIABLES:
            ax.set_yscale("log")
            if variable == "total_tokens":
                ax.yaxis.set_major_formatter(FuncFormatter(compact_count_tick))
            elif variable == "cost_usd_positive":
                ax.yaxis.set_major_formatter(FuncFormatter(compact_cost_tick))
        ax.set_ylabel(DISPLAY_NAMES[variable])
        ax.set_xlabel("Trajectory outcome")
        ax.set_title(f"{DISPLAY_NAMES[variable]} by trajectory outcome")
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()

        path = output_dir / f"diminishing_returns_performance_box_{variable}.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        paths.append(path)

    return paths


def plot_effort_outcome_stacked_bars(bins: pd.DataFrame, figures_dir: Path) -> list[Path]:
    paths: list[Path] = []
    output_dir = figures_dir / "by_outcome" / "stacked"
    output_dir.mkdir(parents=True, exist_ok=True)

    for variable in EFFORT_VARIABLES:
        subset = bins[(bins["variable"] == variable) & (bins["n"] > 0)].sort_values("bin_order")
        if subset.empty:
            continue

        x = subset["bin_order"].to_numpy(dtype=float)
        total = subset["n"].to_numpy(dtype=float)
        pass_count = subset["pass_count"].to_numpy(dtype=float)
        fail_count = total - pass_count

        fig, ax = plt.subplots(figsize=(8.5, 4.8))
        ax.bar(x, pass_count, width=0.74, color=PASS_COLOR, alpha=0.82, label="Passed trajectories")
        ax.bar(x, fail_count, width=0.74, bottom=pass_count, color=FAIL_COLOR, alpha=0.82, label="Failed trajectories")
        ax.set_xticks(x)
        ax.set_xticklabels(
            [f"{row.effort_bin}\n(n={int(row.n):,})" for row in subset.itertuples(index=False)],
            rotation=25,
            ha="right",
        )
        if len(total) and float(total.max()) > 0:
            ax.set_ylim(0, float(total.max()) * 1.12)
        ax.set_ylabel("Trajectory count")
        ax.set_xlabel(DISPLAY_NAMES[variable])
        ax.set_title(f"Terminal-Bench outcome counts by {DISPLAY_NAMES[variable].lower()}")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(1.0, 1.02))
        fig.tight_layout()

        path = output_dir / f"diminishing_returns_outcome_stacked_{variable}.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        paths.append(path)

    return paths


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    df = load_data(args.input)
    bins = build_effort_bins(df)
    scaffold_bins = build_effort_bins(df, group_column="scaffold")
    quantile_bins = build_quantile_bins(df)
    robustness = build_bin_robustness_summary(bins, quantile_bins)
    old_task_balanced = (
        pd.read_csv(args.task_balanced_out, low_memory=False)
        if args.task_balanced_out.exists()
        else pd.DataFrame()
    )
    task_balanced = build_task_balanced_effort_success(df, bins)
    task_balanced_changes = task_balanced_change_summary(old_task_balanced, task_balanced)

    summary_path = args.out / "rq1_effort_bin_summary.csv"
    quantile_path = args.out / "rq1_effort_quantile_bins.csv"
    robustness_path = args.out / "rq1_effort_bin_robustness_summary.csv"
    task_balanced_path = args.task_balanced_out
    task_balanced_changes_path = args.out / "rq1_task_balanced_effort_success_change_summary.csv"
    task_balanced_path.parent.mkdir(parents=True, exist_ok=True)
    bins.to_csv(summary_path, index=False)
    quantile_bins.to_csv(quantile_path, index=False)
    robustness.to_csv(robustness_path, index=False)
    task_balanced.to_csv(task_balanced_path, index=False)
    if not task_balanced_changes.empty:
        task_balanced_changes.to_csv(task_balanced_changes_path, index=False)

    figure_groups = {
        "effort_bins": plot_effort_bins(bins, args.figures_dir),
        "effort_bin_task_balancing": [
            path for path in [plot_pooled_vs_task_balanced(task_balanced, args.figures_dir)] if path is not None
        ],
        "by_scaffold": plot_effort_bins(scaffold_bins, args.figures_dir, "scaffold"),
        "by_provider": plot_provider_heatmaps(df, args.figures_dir),
        "by_provider_source": plot_model_provider_source_heatmaps(df, args.figures_dir),
        "by_outcome_box": plot_effort_performance_box_plots(df, args.figures_dir),
        "by_outcome_stacked": plot_effort_outcome_stacked_bars(bins, args.figures_dir),
    }
    figure_paths = [path for paths in figure_groups.values() for path in paths]

    print(f"Wrote {summary_path}")
    print(f"Wrote {quantile_path}")
    print(f"Wrote {robustness_path}")
    print(f"Wrote {task_balanced_path}")
    if not task_balanced_changes.empty:
        print(f"Wrote {task_balanced_changes_path}")
    for name, paths in figure_groups.items():
        print(f"Wrote {len(paths)} {name} figures")
    print(f"Wrote {len(figure_paths)} figures under {args.figures_dir}")


if __name__ == "__main__":
    main()
