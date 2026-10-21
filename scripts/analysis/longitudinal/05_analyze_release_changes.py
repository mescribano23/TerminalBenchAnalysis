#!/usr/bin/env python3
"""RQ3.1 task pass-rate comparisons by official release fixes.

Rates come from the existing source-submission-balanced adjacent-task table:
trials within source submission/task, submissions within task, equal task weight.
The archived instruction audits remain separate metadata in the crosswalk.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from scripts.analysis.plot_style import PASS_COLOR
from scripts.analysis.longitudinal.official_release_changes import (
    ROOT, LONG, EXPECTED, add_release_status, build_release_summary,
)

TB2_0_COLOR = "#6F6F6F"
TB2_1_COLOR = PASS_COLOR
TB3_0_COLOR = "#D55E00"
TB4_0_COLOR = "#009E73"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjacent-csv", type=Path, default=LONG / "task_composition/adjacent_version_task_changes.csv")
    parser.add_argument("--four-version-out", type=Path, default=ROOT / "reports/longitudinal/pass_rate_official_release_changes_all_versions.png")
    parser.add_argument("--out-dir", type=Path, default=LONG)
    parser.add_argument("--include-diagnostics", action="store_true",
                        help="Also export the redundant per-task release-status join.")
    return parser.parse_args()


def thesis_style() -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
        "axes.titlesize": 10, "axes.labelsize": 9, "xtick.labelsize": 8,
        "ytick.labelsize": 8, "legend.fontsize": 8, "axes.spines.top": False,
        "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white"})


def one_decimal(value: float) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def annotate_bar(ax: plt.Axes, bar: plt.Rectangle, value: float) -> None:
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        value + 1.6,
        f"{one_decimal(value)}%",
        ha="center",
        va="bottom",
        fontsize=8,
        color="#333333",
    )


def plot_pair_panel(
    ax: plt.Axes,
    summary: pd.DataFrame,
    title: str,
    old_label: str,
    new_label: str,
    old_color: str,
    new_color: str,
) -> None:
    plot_df = summary.copy()
    plot_df["plot_label"] = [
        f"All\n(n={int(row.n_tasks)})"
        if row.task_set == "all_tasks"
        else f"{row.label}\n(n={int(row.n_tasks)})"
        for row in plot_df.itertuples(index=False)
    ]
    bar_width = 0.18
    gap = 0.0
    group_spacing = 3.2 * bar_width
    x = np.arange(plot_df.shape[0]) * group_spacing
    old_values = plot_df["old_pass_rate"].astype(float).to_numpy()
    new_values = plot_df["new_pass_rate"].astype(float).to_numpy()
    offset = (bar_width + gap) / 2
    bars_old = ax.bar(
        x - offset,
        old_values,
        bar_width,
        label=old_label,
        color=old_color,
        edgecolor="none",
    )
    bars_new = ax.bar(
        x + offset,
        new_values,
        bar_width,
        label=new_label,
        color=new_color,
        edgecolor="none",
    )
    for bar, value in zip(bars_old, old_values):
        annotate_bar(ax, bar, value)
    for bar, value in zip(bars_new, new_values):
        annotate_bar(ax, bar, value)
    ax.set_xticks(x)
    ax.set_xticklabels(plot_df["plot_label"])
    ax.set_xlim(x[0] - 2 * bar_width, x[-1] + 2 * bar_width)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=100, decimals=0))
    ax.grid(axis="y", color="#D0D0D0", alpha=0.55, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=2, loc="upper left", bbox_to_anchor=(0.0, 1.0), handlelength=1.2)


def plot_four_version_robustness(
    tb2_summary: pd.DataFrame,
    tb3_tb4_summary: pd.DataFrame,
    out: Path,
) -> None:
    thesis_style()
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.1), sharey=True)

    tb2_panel = tb2_summary.rename(
        columns={"tb2_0_pass_rate": "old_pass_rate", "tb2_1_pass_rate": "new_pass_rate"}
    )
    plot_pair_panel(
        axes[0],
        tb2_panel,
        "TB2.0 to TB2.1",
        "TB2.0",
        "TB2.1",
        TB2_0_COLOR,
        TB2_1_COLOR,
    )
    plot_pair_panel(
        axes[1],
        tb3_tb4_summary,
        "TB3.0 to TB4.0",
        "TB3.0",
        "TB4.0",
        TB3_0_COLOR,
        TB4_0_COLOR,
    )
    axes[0].set_ylabel("Task-weighted pass rate (%)")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(w_pad=0.8)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    adjacent = pd.read_csv(args.adjacent_csv)
    summary = build_release_summary(adjacent)
    for pair in EXPECTED:
        rows = summary[summary.version_pair.eq(pair)].set_index("task_set")
        groups = rows.loc[["fixed", "not_listed_as_fixed"]]
        for col in ["old_pass_rate", "new_pass_rate", "mean_change_pp"]:
            if not np.isclose(np.average(groups[col], weights=groups.n_tasks), rows.loc["all_tasks", col]):
                raise ValueError(f"{pair}: subset means do not reconcile to all shared tasks")
    plot_four_version_robustness(summary[summary.version_pair.eq("2.0->2.1")],
                                 summary[summary.version_pair.eq("3.0->4.0")], args.four_version_out)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.out_dir / "rq3_1_official_release_summary.csv", index=False)
    if args.include_diagnostics:
        tasks = pd.concat([add_release_status(adjacent, pair) for pair in EXPECTED], ignore_index=True)
        tasks.to_csv(args.out_dir / "rq3_1_official_release_task_changes.csv", index=False)
    print(summary.to_string(index=False))
    print(f"Wrote {args.four_version_out}")


if __name__ == "__main__":
    main()
