#!/usr/bin/env python3
"""Descriptive diminishing-returns analysis for Terminal-Bench trajectories.

Outputs:
- data/processed/diminishing_returns_effort_bins.csv
- data/processed/diminishing_returns_variable_coverage.csv
- reports/diminishing_returns/diminishing_returns_*.png
- reports/diminishing_returns/by_outcome/barcharts/diminishing_returns_by_outcome_*.png
- reports/diminishing_returns/by_outcome/box_plots/diminishing_returns_performance_box_*.png
- reports/diminishing_returns/by_outcome/stacked/diminishing_returns_outcome_stacked_*.png
- optional reports/diminishing_returns/by_scaffold/diminishing_returns_*.png heatmaps
- optional reports/diminishing_returns/by_model/diminishing_returns_*.png heatmaps
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
REPORTS_DIR = REPO_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "diminishing_returns"

INPUT_DEFAULT = DATA_PROCESSED_DIR / "trajectory_summary.csv"
OUT_DEFAULT = DATA_PROCESSED_DIR

EFFORT_VARIABLES = [
    "step_count",
    "step_count_scaffold_ratio",
    "command_count",
    "tool_call_count",
    "total_tokens",
    "duration_seconds_from_timestamps",
    "cost_usd_positive",
]

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
    "step_count_scaffold_ratio": "Step count / scaffold median",
    "command_count": "Command count",
    "tool_call_count": "Tool call count",
    "total_tokens": "Total tokens",
    "duration_seconds_from_timestamps": "Duration seconds",
    "cost_usd_positive": "Positive cost USD",
}

BIN_SPECS = {
    "step_count": ([0, 10, 25, 50, 100, 200, math.inf], ["0-10", "11-25", "26-50", "51-100", "101-200", ">200"]),
    "step_count_scaffold_ratio": ([0, 0.5, 1, 2, 4, math.inf], ["<=0.5x", "0.5-1x", "1-2x", "2-4x", ">4x"]),
    "command_count": ([-0.5, 0.5, 5, 15, 40, math.inf], ["0", "1-5", "6-15", "16-40", ">40"]),
    "tool_call_count": ([-0.5, 5, 15, 35, 75, 150, math.inf], ["0-5", "6-15", "16-35", "36-75", "76-150", ">150"]),
    "total_tokens": (
        [-0.5, 10_000, 100_000, 500_000, 1_000_000, 3_000_000, 10_000_000, math.inf],
        ["0-10k", "10k-100k", "100k-500k", "500k-1M", "1M-3M", "3M-10M", ">10M"],
    ),
    "duration_seconds_from_timestamps": (
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
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR)
    parser.add_argument(
        "--by-scaffold",
        action="store_true",
        help="Also write appendix-style grouped plots with one series per scaffold.",
    )
    parser.add_argument(
        "--by-model",
        action="store_true",
        help="Also write appendix-style grouped plots with one series per model_dir.",
    )
    return parser.parse_args()


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    p = successes / total
    denom = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denom
    half = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denom
    return max(0.0, center - half), min(1.0, center + half)


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "reward" not in df.columns:
        raise ValueError(f"{path} must contain a reward column.")

    df["reward"] = pd.to_numeric(df["reward"], errors="coerce")
    binary_mask = df["reward"].isin([0, 1])
    df = df.loc[binary_mask].copy()
    if df.empty:
        raise ValueError("No rows with binary reward values 0 or 1 were found.")
    df["passed"] = df["reward"].astype(int)

    required_numeric = [
        "step_count",
        "command_count",
        "tool_call_count",
        "total_tokens",
        "duration_seconds_from_timestamps",
        "cost_usd",
    ]
    missing = [column for column in required_numeric if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    for column in required_numeric:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    if "scaffold" not in df.columns:
        raise ValueError("trajectory_summary.csv must contain a scaffold column.")
    df["scaffold"] = df["scaffold"].fillna("unknown").astype(str)
    if "model_dir" in df.columns:
        df["model_dir"] = df["model_dir"].fillna("unknown").astype(str)

    scaffold_medians = df.groupby("scaffold")["step_count"].transform("median")
    df["step_count_scaffold_ratio"] = df["step_count"] / scaffold_medians.replace(0, np.nan)
    df["cost_usd_positive"] = df["cost_usd"].where(df["cost_usd"] > 0)

    return df


def build_variable_coverage(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variable in EFFORT_VARIABLES:
        valid = df[variable].dropna()
        rows.append(
            {
                "variable": variable,
                "variable_display": DISPLAY_NAMES[variable],
                "trajectory_count": len(df),
                "complete_case_count": int(valid.shape[0]),
                "complete_case_fraction": float(valid.shape[0] / len(df)),
                "positive_count": int((valid > 0).sum()),
                "zero_count": int((valid == 0).sum()),
                "median": float(valid.median()) if len(valid) else None,
                "p90": float(valid.quantile(0.90)) if len(valid) else None,
                "max": float(valid.max()) if len(valid) else None,
            }
        )
    return pd.DataFrame(rows)


def bin_series(series: pd.Series, variable: str) -> pd.Categorical:
    edges, labels = BIN_SPECS[variable]
    return pd.cut(
        series,
        bins=edges,
        labels=labels,
        include_lowest=True,
        right=True,
        ordered=True,
    )


def build_effort_bins(df: pd.DataFrame, group_column: str | None = None) -> pd.DataFrame:
    if group_column is not None and group_column not in df.columns:
        raise ValueError(f"Cannot build grouped plots because {group_column!r} is missing.")

    rows: list[dict[str, Any]] = []
    for variable in EFFORT_VARIABLES:
        columns = [variable, "passed"] if group_column is None else [group_column, variable, "passed"]
        work = df[columns].dropna().copy()
        work["effort_bin"] = bin_series(work[variable], variable)
        groups = [(None, work)] if group_column is None else work.groupby(group_column)

        for group_value, group_frame in groups:
            for bin_order, (label, bin_group) in enumerate(group_frame.groupby("effort_bin", observed=False), start=1):
                n = int(len(bin_group))
                passes = int(bin_group["passed"].sum()) if n else 0
                ci_low, ci_high = wilson_interval(passes, n)
                row = {
                    "variable": variable,
                    "variable_display": DISPLAY_NAMES[variable],
                    "bin_order": bin_order,
                    "effort_bin": str(label),
                    "n": n,
                    "pass_count": passes,
                    "success_rate": passes / n if n else None,
                    "success_rate_ci95_low": ci_low,
                    "success_rate_ci95_high": ci_high,
                }
                if group_column is not None:
                    row.update({"group_column": group_column, "group_value": str(group_value)})
                rows.append(row)
    return pd.DataFrame(rows)


def plot_effort_bins(
    bins: pd.DataFrame,
    figures_dir: Path,
    group_column: str | None = None,
) -> list[Path]:
    paths: list[Path] = []
    group_label = {"scaffold": "scaffold", "model_dir": "model"}.get(group_column)
    output_dir = figures_dir if group_label is None else figures_dir / f"by_{group_label}"
    output_dir.mkdir(parents=True, exist_ok=True)

    for variable in EFFORT_VARIABLES:
        subset = bins[(bins["variable"] == variable) & (bins["n"] > 0)].sort_values("bin_order")
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

        path = output_dir / f"diminishing_returns_{variable}.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        paths.append(path)

    return paths


def is_open_source_model(row: pd.Series) -> bool:
    model_text = " ".join(
        str(row.get(column, "")).lower().replace("_", "-")
        for column in ["model_dir", "model_name"]
    )
    return any(keyword in model_text for keyword in OPEN_SOURCE_MODEL_KEYWORDS)


def plot_model_provider_heatmaps(
    df: pd.DataFrame,
    figures_dir: Path,
    output_name: str = "by_provider",
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
        if provider_df.empty:
            continue
        provider_bins[provider] = build_effort_bins(provider_df, group_column="model_dir")

    for variable in EFFORT_VARIABLES:
        _, labels = BIN_SPECS[variable]
        panels: list[tuple[str, pd.DataFrame, pd.DataFrame, list[str]]] = []

        for provider, bins in provider_bins.items():
            subset = bins[(bins["variable"] == variable) & (bins["n"] > 0)].sort_values("bin_order")
            if subset.empty:
                continue

            order_frame = (
                subset.groupby("group_value", as_index=False)
                .agg(pass_count=("pass_count", "sum"), n=("n", "sum"))
                .assign(overall_success_rate=lambda frame: frame["pass_count"] / frame["n"])
                .sort_values(["overall_success_rate", "n", "group_value"], ascending=[False, False, True])
            )
            group_order = order_frame["group_value"].tolist()
            heatmap = (
                subset.pivot(index="group_value", columns="effort_bin", values="success_rate")
                .reindex(index=group_order, columns=labels)
                .astype(float)
            )
            counts = (
                subset.pivot(index="group_value", columns="effort_bin", values="n")
                .reindex(index=group_order, columns=labels)
                .fillna(0)
                .astype(int)
            )
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
        cmap = plt.get_cmap("RdYlGn").copy()
        cmap.set_bad("#f2f2f2")
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
                    text_color = "white" if rate < 0.45 else "black"
                    ax.text(
                        column_index,
                        row_index,
                        f"{rate:.0%}\nn={n}",
                        ha="center",
                        va="center",
                        fontsize=6.3,
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

        path = output_dir / f"diminishing_returns_{variable}.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        paths.append(path)

    return paths


def plot_model_provider_source_heatmaps(df: pd.DataFrame, figures_dir: Path) -> list[Path]:
    source_mask = df.apply(is_open_source_model, axis=1)
    paths: list[Path] = []
    paths.extend(
        plot_model_provider_heatmaps(
            df[source_mask].copy(),
            figures_dir,
            output_name="by_provider_open_source",
            title_suffix=" (open-source/open-weight models)",
        )
    )
    paths.extend(
        plot_model_provider_heatmaps(
            df[~source_mask].copy(),
            figures_dir,
            output_name="by_provider_closed_source",
            title_suffix=" (closed-source models)",
        )
    )
    return paths


def plot_effort_bins_by_outcome(bins: pd.DataFrame, figures_dir: Path) -> list[Path]:
    paths: list[Path] = []
    output_dir = figures_dir / "by_outcome" / "barcharts"
    output_dir.mkdir(parents=True, exist_ok=True)

    for variable in EFFORT_VARIABLES:
        subset = bins[(bins["variable"] == variable) & (bins["n"] > 0)].sort_values("bin_order")
        if subset.empty:
            continue

        _, labels = BIN_SPECS[variable]
        x = subset["bin_order"].to_numpy(dtype=float)
        success_rate = subset["success_rate"].to_numpy(dtype=float)
        pass_count = subset["pass_count"].to_numpy(dtype=float)
        fail_count = subset["n"].to_numpy(dtype=float) - pass_count

        fig, ax_count = plt.subplots(figsize=(8.8, 4.9))
        bar_width = 0.34
        ax_count.bar(
            x - bar_width / 2,
            fail_count,
            width=bar_width,
            color="#c97b63",
            alpha=0.78,
            label="Failed trajectories",
        )
        ax_count.bar(
            x + bar_width / 2,
            pass_count,
            width=bar_width,
            color="#6aa57a",
            alpha=0.78,
            label="Passed trajectories",
        )
        ax_count.set_ylabel("Trajectory count")
        ax_count.set_xlabel(DISPLAY_NAMES[variable])
        ax_count.set_xticks(range(1, len(labels) + 1))
        ax_count.set_xticklabels(labels, rotation=25, ha="right")
        max_count = max(float(pass_count.max()), float(fail_count.max()))
        if max_count > 0:
            ax_count.set_ylim(0, max_count * 1.28)
        ax_count.grid(axis="y", alpha=0.2)

        ax_rate = ax_count.twinx()
        ax_rate.plot(
            x,
            success_rate,
            marker="o",
            linewidth=1.8,
            color="#1f2d3a",
            label="Success rate",
        )
        ax_rate.set_ylim(0, 1)
        ax_rate.set_ylabel("Success rate")

        count_handles, count_labels = ax_count.get_legend_handles_labels()
        rate_handles, rate_labels = ax_rate.get_legend_handles_labels()
        ax_count.legend(
            count_handles + rate_handles,
            count_labels + rate_labels,
            frameon=False,
            loc="upper left",
            bbox_to_anchor=(0.0, 1.0),
        )
        ax_count.set_title(f"Terminal-Bench outcomes and success rate by {DISPLAY_NAMES[variable].lower()}")
        fig.tight_layout()

        path = output_dir / f"diminishing_returns_by_outcome_{variable}.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        paths.append(path)

    return paths


def plot_effort_performance_box_plots(df: pd.DataFrame, figures_dir: Path) -> list[Path]:
    if "leaderboard_accuracy_percent" not in df.columns:
        return []

    paths: list[Path] = []
    output_dir = figures_dir / "by_outcome" / "box_plots"
    output_dir.mkdir(parents=True, exist_ok=True)

    work = df.copy()
    work["performance_percent"] = pd.to_numeric(work["leaderboard_accuracy_percent"], errors="coerce")
    work = work.dropna(subset=["performance_percent", "passed"])
    if work.empty:
        return []

    for variable in EFFORT_VARIABLES:
        subset = work[[variable, "passed", "performance_percent"]].dropna().copy()
        if subset.empty:
            continue

        _, labels = BIN_SPECS[variable]
        subset["effort_bin"] = bin_series(subset[variable], variable)
        grouped_values: dict[int, list[np.ndarray]] = {}
        for outcome_value in [0, 1]:
            values: list[np.ndarray] = []
            outcome_subset = subset[subset["passed"] == outcome_value]
            for label in labels:
                bin_values = outcome_subset.loc[
                    outcome_subset["effort_bin"].astype(str) == label,
                    "performance_percent",
                ].to_numpy(dtype=float)
                values.append(bin_values)
            grouped_values[outcome_value] = values

        if not any(len(values) for outcome_values in grouped_values.values() for values in outcome_values):
            continue

        fig, ax = plt.subplots(figsize=(11.2, 5.8))
        positions = np.arange(1, len(labels) + 1)
        panels = [
            (0, "Failed trajectories", "#c97b63", -0.18),
            (1, "Passed trajectories", "#6aa57a", 0.18),
        ]
        for outcome_value, _title, color, offset in panels:
            values = grouped_values[outcome_value]
            plot_positions = positions + offset
            non_empty_positions = [
                position for position, bin_values in zip(plot_positions, values) if len(bin_values)
            ]
            non_empty_values = [bin_values for bin_values in values if len(bin_values)]

            if non_empty_values:
                parts = ax.violinplot(
                    non_empty_values,
                    positions=non_empty_positions,
                    vert=True,
                    widths=0.34,
                    showmeans=False,
                    showmedians=False,
                    showextrema=False,
                )
                for body in parts["bodies"]:
                    body.set_facecolor(color)
                    body.set_edgecolor("#2f3337")
                    body.set_alpha(0.42)

                ax.boxplot(
                    non_empty_values,
                    positions=non_empty_positions,
                    widths=0.15,
                    patch_artist=True,
                    showfliers=False,
                    boxprops={"facecolor": "#ffffff", "edgecolor": "#243b4a", "linewidth": 1.1},
                    medianprops={"color": "#1f2d3a", "linewidth": 1.7},
                    whiskerprops={"color": "#243b4a", "linewidth": 1.0},
                    capprops={"color": "#243b4a", "linewidth": 1.0},
                )

        fail_values = grouped_values[0]
        pass_values = grouped_values[1]
        tick_labels = [
            f"{label}\nF={len(fail_bin):,} P={len(pass_bin):,}"
            for label, fail_bin, pass_bin in zip(labels, fail_values, pass_values)
        ]
        ax.set_xticks(positions)
        ax.set_xticklabels(tick_labels, rotation=30, ha="right", fontsize=8)
        ax.set_xlim(0.45, len(labels) + 0.55)
        ax.set_ylim(0, 100)
        ax.set_ylabel("Leaderboard performance (%)")
        ax.set_xlabel(DISPLAY_NAMES[variable])
        ax.set_title(f"Leaderboard performance by {DISPLAY_NAMES[variable].lower()} and trajectory outcome")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(
            handles=[
                Patch(facecolor="#c97b63", edgecolor="#2f3337", alpha=0.42, label="Failed trajectories"),
                Patch(facecolor="#6aa57a", edgecolor="#2f3337", alpha=0.42, label="Passed trajectories"),
            ],
            frameon=False,
            loc="upper right",
        )
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

        _, labels = BIN_SPECS[variable]
        x = subset["bin_order"].to_numpy(dtype=float)
        total = subset["n"].to_numpy(dtype=float)
        pass_count = subset["pass_count"].to_numpy(dtype=float)
        fail_count = total - pass_count
        pass_share = pass_count / total
        fail_share = fail_count / total

        fig, ax = plt.subplots(figsize=(8.5, 4.8))
        ax.bar(x, pass_share, width=0.74, color="#6aa57a", alpha=0.82, label="Passed trajectories")
        ax.bar(x, fail_share, width=0.74, bottom=pass_share, color="#c97b63", alpha=0.82, label="Failed trajectories")
        for position, fail_value, pass_value in zip(x, fail_share, pass_share):
            if pass_value >= 0.04:
                ax.text(
                    position,
                    pass_value / 2,
                    f"{pass_value:.0%}",
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="#1f2d3a",
                )
            if fail_value >= 0.04:
                ax.text(
                    position,
                    pass_value + fail_value / 2,
                    f"{fail_value:.0%}",
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="#1f2d3a",
                )

        tick_labels = [f"{label}\n(n={int(n):,})" for label, n in zip(labels, total)]
        ax.set_xticks(range(1, len(labels) + 1))
        ax.set_xticklabels(tick_labels, rotation=25, ha="right")
        ax.set_ylim(0, 1.18)
        ax.set_ylabel("Share of trajectories in bin")
        ax.set_xlabel(DISPLAY_NAMES[variable])
        ax.set_title(f"Terminal-Bench outcome composition by {DISPLAY_NAMES[variable].lower()}")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(1.0, 1.02))
        fig.tight_layout()

        path = output_dir / f"diminishing_returns_outcome_stacked_{variable}.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        paths.append(path)

    return paths


def plot_grouped_heatmap(subset: pd.DataFrame, variable: str, group_label: str) -> plt.Figure:
    _, labels = BIN_SPECS[variable]
    order_frame = (
        subset.groupby("group_value", as_index=False)
        .agg(pass_count=("pass_count", "sum"), n=("n", "sum"))
        .assign(overall_success_rate=lambda frame: frame["pass_count"] / frame["n"])
        .sort_values(["overall_success_rate", "n", "group_value"], ascending=[False, False, True])
    )
    group_order = order_frame["group_value"].tolist()

    heatmap = (
        subset.pivot(index="group_value", columns="effort_bin", values="success_rate")
        .reindex(index=group_order, columns=labels)
        .astype(float)
    )
    counts = (
        subset.pivot(index="group_value", columns="effort_bin", values="n")
        .reindex(index=group_order, columns=labels)
        .fillna(0)
        .astype(int)
    )

    row_count = max(1, len(group_order))
    figure_height = min(14.0, max(4.8, 1.6 + row_count * 0.34))
    fig, ax = plt.subplots(figsize=(10.5, figure_height))

    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad("#f2f2f2")
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
                text_color = "white" if rate < 0.45 else "black"
                ax.text(
                    column_index,
                    row_index,
                    f"{rate:.0%}\nn={n}",
                    ha="center",
                    va="center",
                    fontsize=6.5,
                    color=text_color,
                )

    return fig


def plot_overall_series(ax: plt.Axes, subset: pd.DataFrame) -> None:
    x = subset["bin_order"].to_numpy(dtype=float)
    y = subset["success_rate"].to_numpy(dtype=float)
    yerr = np.vstack(
        [
            y - subset["success_rate_ci95_low"].to_numpy(dtype=float),
            subset["success_rate_ci95_high"].to_numpy(dtype=float) - y,
        ]
    )
    ax.errorbar(x, y, yerr=yerr, marker="o", linewidth=1.8, capsize=4, color="#1f77b4")


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    df = load_data(args.input)
    coverage = build_variable_coverage(df)
    bins = build_effort_bins(df)
    figures = plot_effort_bins(bins, args.figures_dir)
    outcome_figures = plot_effort_bins_by_outcome(bins, args.figures_dir)
    outcome_box_figures = plot_effort_performance_box_plots(df, args.figures_dir)
    outcome_stacked_figures = plot_effort_outcome_stacked_bars(bins, args.figures_dir)
    grouped_figures: list[Path] = []
    if args.by_scaffold:
        scaffold_bins = build_effort_bins(df, group_column="scaffold")
        grouped_figures.extend(plot_effort_bins(scaffold_bins, args.figures_dir, "scaffold"))
    if args.by_model:
        model_bins = build_effort_bins(df, group_column="model_dir")
        grouped_figures.extend(plot_effort_bins(model_bins, args.figures_dir, "model_dir"))
        grouped_figures.extend(plot_model_provider_heatmaps(df, args.figures_dir))
        grouped_figures.extend(plot_model_provider_source_heatmaps(df, args.figures_dir))

    bins_path = args.out / "diminishing_returns_effort_bins.csv"
    coverage_path = args.out / "diminishing_returns_variable_coverage.csv"
    bins.to_csv(bins_path, index=False)
    coverage.to_csv(coverage_path, index=False)

    print(f"Wrote {bins_path}")
    print(f"Wrote {coverage_path}")
    print(f"Wrote {len(figures)} figures to {args.figures_dir}")
    print(f"Wrote {len(outcome_figures)} by-outcome figures to {args.figures_dir / 'by_outcome' / 'barcharts'}")
    print(f"Wrote {len(outcome_box_figures)} by-outcome box plots to {args.figures_dir / 'by_outcome' / 'box_plots'}")
    print(f"Wrote {len(outcome_stacked_figures)} by-outcome stacked plots to {args.figures_dir / 'by_outcome' / 'stacked'}")
    if grouped_figures:
        print(f"Wrote {len(grouped_figures)} optional grouped figures to {args.figures_dir}")


if __name__ == "__main__":
    main()
