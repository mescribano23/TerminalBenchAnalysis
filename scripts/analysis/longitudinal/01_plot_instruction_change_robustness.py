#!/usr/bin/env python3
"""Plot the RQ3 instruction-change robustness check."""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

REPO_ROOT_GUESS = Path(__file__).resolve().parents[3]
if str(REPO_ROOT_GUESS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_GUESS))

from scripts.benchmark_paths import find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
LONGITUDINAL_DIR = REPO_ROOT / "data" / "processed_live" / "longitudinal"
TRAJECTORY_CSV = LONGITUDINAL_DIR / "trajectory_longitudinal.csv"
FIGURE_PATH = REPO_ROOT / "reports" / "longitudinal" / "pass_rate_instruction_change_robustness.png"
VERSION_ORDER = ["2.0", "2.1"]

# Source of truth: supplied TB2.0->TB2.1 instruction changelog. The changelog
# lists 11 instruction/test-alignment clarifications and 5 multimodal
# capability-boundary instructions; path-tracing appears in both groups.
DOCUMENTED_INSTRUCTION_CHANGE_TASKS = {
    "adaptive-rejection-sampler",
    "build-pmars",
    "caffe-cifar-10",
    "chess-best-move",
    "code-from-image",
    "extract-moves-from-video",
    "financial-document-processor",
    "hf-model-inference",
    "install-windows-3.11",
    "mteb-retrieve",
    "path-tracing",
    "polyglot-c-py",
    "protein-assembly",
    "sam-cell-seg",
    "train-fasttext",
}

TB2_0_COLOR = "#6F6F6F"
TB2_1_COLOR = "#2F6F73"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-csv", type=Path, default=TRAJECTORY_CSV)
    parser.add_argument("--out", type=Path, default=FIGURE_PATH)
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


def percent(value: float) -> float:
    return 100 * value


def one_decimal(value: float) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def build_robustness_summary(trajectory_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(
        trajectory_csv,
        usecols=["benchmark_version", "task_name", "passed"],
        low_memory=False,
    )
    df = df.copy()
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    df["task_name"] = df["task_name"].astype(str)
    df["passed"] = pd.to_numeric(df["passed"], errors="coerce")
    df = df[df["benchmark_version"].isin(VERSION_ORDER)].dropna(subset=["passed"])

    task_sets = {
        version: set(df.loc[df["benchmark_version"].eq(version), "task_name"].unique())
        for version in VERSION_ORDER
    }
    shared_tasks = set.intersection(*task_sets.values())
    documented_tasks = DOCUMENTED_INSTRUCTION_CHANGE_TASKS.intersection(shared_tasks)
    missing_documented = sorted(DOCUMENTED_INSTRUCTION_CHANGE_TASKS.difference(shared_tasks))
    if missing_documented:
        raise ValueError(
            "Documented instruction-change tasks missing from shared task set: "
            + ", ".join(missing_documented)
        )

    rows: list[dict[str, object]] = []
    subsets = [
        ("all_shared_tasks", shared_tasks),
        ("no_documented_instruction_change", shared_tasks.difference(documented_tasks)),
        ("documented_instruction_changes", documented_tasks),
    ]
    for task_set, tasks in subsets:
        subset = df[df["task_name"].isin(tasks)]
        by_version = subset.groupby("benchmark_version")["passed"].agg(["sum", "size", "mean"])
        tb2_0 = by_version.loc["2.0"]
        tb2_1 = by_version.loc["2.1"]
        rows.append(
            {
                "task_set": task_set,
                "n_tasks": len(tasks),
                "tb2_0_n_passed": int(tb2_0["sum"]),
                "tb2_0_n_trajectories": int(tb2_0["size"]),
                "tb2_0_pass_rate": percent(float(tb2_0["mean"])),
                "tb2_1_n_passed": int(tb2_1["sum"]),
                "tb2_1_n_trajectories": int(tb2_1["size"]),
                "tb2_1_pass_rate": percent(float(tb2_1["mean"])),
                "pass_rate_change_pp": percent(float(tb2_1["mean"] - tb2_0["mean"])),
            }
        )

    summary = pd.DataFrame(rows)
    rate_columns = ["tb2_0_pass_rate", "tb2_1_pass_rate", "pass_rate_change_pp"]
    summary[rate_columns] = summary[rate_columns].round(2)
    return summary


def validate_summary(summary: pd.DataFrame) -> pd.DataFrame:
    required = {
        "task_set",
        "n_tasks",
        "tb2_0_pass_rate",
        "tb2_1_pass_rate",
        "pass_rate_change_pp",
    }
    missing = sorted(required.difference(summary.columns))
    if missing:
        raise ValueError(f"Robustness summary is missing columns: {', '.join(missing)}")

    order = [
        "all_shared_tasks",
        "no_documented_instruction_change",
        "documented_instruction_changes",
    ]
    labels = {
        "all_shared_tasks": "All tasks\n(n=89)",
        "no_documented_instruction_change": "No instruction change\n(n=74)",
        "documented_instruction_changes": "Instruction changed\n(n=15)",
    }
    summary = summary.set_index("task_set").loc[order].reset_index()
    expected_tasks = [89, 74, 15]
    if summary["n_tasks"].astype(int).tolist() != expected_tasks:
        raise ValueError(
            "Unexpected task counts in robustness summary: "
            + ", ".join(map(str, summary["n_tasks"].tolist()))
        )
    return summary.assign(plot_label=summary["task_set"].map(labels))


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


def plot(summary: pd.DataFrame, out: Path) -> None:
    thesis_style()
    fig, ax = plt.subplots(figsize=(6.3, 3.7))

    x = np.arange(summary.shape[0])
    width = 0.28
    tb2_0_values = summary["tb2_0_pass_rate"].astype(float).to_numpy()
    tb2_1_values = summary["tb2_1_pass_rate"].astype(float).to_numpy()

    bars_20 = ax.bar(
        x - width / 2,
        tb2_0_values,
        width,
        label="TB2.0",
        color=TB2_0_COLOR,
        edgecolor="none",
    )
    bars_21 = ax.bar(
        x + width / 2,
        tb2_1_values,
        width,
        label="TB2.1",
        color=TB2_1_COLOR,
        edgecolor="none",
    )

    for bar, value in zip(bars_20, tb2_0_values):
        annotate_bar(ax, bar, value)
    for bar, value in zip(bars_21, tb2_1_values):
        annotate_bar(ax, bar, value)

    ax.set_title("Pass Rates by Task-Change Subset")
    ax.set_ylabel("Pass rate (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(summary["plot_label"])
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=100, decimals=0))
    ax.grid(axis="y", color="#D0D0D0", alpha=0.55, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=2, loc="upper left", bbox_to_anchor=(0.0, 1.0), handlelength=1.2)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    summary = validate_summary(build_robustness_summary(args.trajectory_csv))
    plot(summary, args.out)
    print(f"Wrote figure to {args.out}")
    print(summary[["task_set", "n_tasks", "tb2_0_pass_rate", "tb2_1_pass_rate", "pass_rate_change_pp"]].to_csv(index=False))


if __name__ == "__main__":
    main()
