#!/usr/bin/env python3
"""Analyze the RQ4 instruction-change robustness check.

The instruction-changed/unchanged task split is loaded from the repository's
processed longitudinal audit rather than from an external changelog.
Reported pass rates are task-weighted: each task contributes one pass rate per
benchmark version, and task pass rates are averaged within each subset.
"""

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
AUDIT_CSV = LONGITUDINAL_DIR / "task_version_audit.csv"
FIGURE_PATH = REPO_ROOT / "reports" / "longitudinal" / "pass_rate_instruction_change_robustness.png"
VERSION_ORDER = ["2.0", "2.1"]

EXPECTED_COUNTS = {
    "instruction_changed": 22,
    "instruction_unchanged": 67,
}

TB2_0_COLOR = "#6F6F6F"
TB2_1_COLOR = "#2F6F73"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-csv", type=Path, default=TRAJECTORY_CSV)
    parser.add_argument("--audit-csv", type=Path, default=AUDIT_CSV)
    parser.add_argument("--task-changes-csv", type=Path, default=None)
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


def percent(value: pd.Series | float) -> pd.Series | float:
    return 100 * value


def one_decimal(value: float) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def load_audit(path: Path) -> pd.DataFrame:
    audit = pd.read_csv(path, usecols=["task_name", "classification"])
    audit = audit.copy()
    audit["task_name"] = audit["task_name"].astype(str)
    audit["instruction_status"] = audit["classification"].map(
        {
            "Changed": "instruction_changed",
            "Identical": "instruction_unchanged",
        }
    )
    unsupported = audit[audit["instruction_status"].isna()]
    if not unsupported.empty:
        details = unsupported[["task_name", "classification"]].to_dict(orient="records")
        raise ValueError(f"Audit contains unsupported instruction classifications: {details}")
    if audit["task_name"].duplicated().any():
        duplicates = sorted(audit.loc[audit["task_name"].duplicated(), "task_name"].unique())
        raise ValueError("Audit contains duplicate task names: " + ", ".join(duplicates))

    counts = audit["instruction_status"].value_counts().to_dict()
    for status, expected in EXPECTED_COUNTS.items():
        observed = int(counts.get(status, 0))
        if observed != expected:
            raise ValueError(f"Expected {expected} {status} tasks, found {observed}.")
    if int(sum(counts.values())) != 89:
        raise ValueError(f"Expected 89 audited tasks, found {sum(counts.values())}.")
    return audit[["task_name", "instruction_status"]]


def load_trajectories(path: Path) -> pd.DataFrame:
    usecols = ["benchmark_version", "task_name", "passed", "difficulty", "category"]
    df = pd.read_csv(path, usecols=usecols, low_memory=False)
    df = df.copy()
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    df["task_name"] = df["task_name"].astype(str)
    df["difficulty"] = df["difficulty"].fillna("unknown").astype(str)
    df["category"] = df["category"].fillna("unknown").astype(str)
    df["passed"] = pd.to_numeric(df["passed"], errors="coerce")
    return df[df["benchmark_version"].isin(VERSION_ORDER)].dropna(subset=["passed"])


def validate_task_mapping(df: pd.DataFrame, audit: pd.DataFrame) -> list[str]:
    task_sets = {
        version: set(df.loc[df["benchmark_version"].eq(version), "task_name"].unique())
        for version in VERSION_ORDER
    }
    shared_tasks = sorted(set.intersection(*task_sets.values()))
    audit_tasks = set(audit["task_name"])
    missing_from_audit = sorted(set(shared_tasks) - audit_tasks)
    missing_from_data = sorted(audit_tasks - set(shared_tasks))
    if missing_from_audit or missing_from_data:
        raise ValueError(
            "Task classification mismatch. "
            f"Missing from audit: {missing_from_audit}; missing from data: {missing_from_data}"
        )
    if len(shared_tasks) != 89:
        raise ValueError(f"Expected 89 shared tasks, found {len(shared_tasks)}.")
    return shared_tasks


def modal_value(series: pd.Series) -> str:
    mode = series.dropna().astype(str).mode()
    return mode.iat[0] if not mode.empty else "unknown"


def build_task_changes(df: pd.DataFrame, audit: pd.DataFrame) -> pd.DataFrame:
    shared_tasks = validate_task_mapping(df, audit)
    df = df[df["task_name"].isin(shared_tasks)].copy()
    task_meta = (
        df.groupby("task_name", as_index=False)
        .agg(difficulty=("difficulty", modal_value), category=("category", modal_value))
    )
    rates = (
        df.groupby(["task_name", "benchmark_version"], as_index=False)
        .agg(n_trajectories=("passed", "size"), pass_rate=("passed", "mean"))
    )
    rate_wide = rates.pivot(index="task_name", columns="benchmark_version", values="pass_rate")
    n_wide = rates.pivot(index="task_name", columns="benchmark_version", values="n_trajectories")
    missing_versions = [version for version in VERSION_ORDER if version not in rate_wide.columns]
    if missing_versions:
        raise ValueError(f"Missing task pass rates for benchmark version(s): {missing_versions}")

    out = (
        task_meta.merge(audit, on="task_name", how="inner", validate="one_to_one")
        .merge(rate_wide[VERSION_ORDER].reset_index(), on="task_name", how="inner")
        .rename(columns={"2.0": "tb2_0_pass_rate", "2.1": "tb2_1_pass_rate"})
    )
    out["tb2_0_n_trajectories"] = n_wide["2.0"].reindex(out["task_name"]).to_numpy(dtype=int)
    out["tb2_1_n_trajectories"] = n_wide["2.1"].reindex(out["task_name"]).to_numpy(dtype=int)
    out["change_pp"] = percent(out["tb2_1_pass_rate"] - out["tb2_0_pass_rate"])
    out["tb2_0_pass_rate"] = percent(out["tb2_0_pass_rate"])
    out["tb2_1_pass_rate"] = percent(out["tb2_1_pass_rate"])
    out["instruction_status"] = pd.Categorical(
        out["instruction_status"],
        categories=["instruction_unchanged", "instruction_changed"],
        ordered=True,
    )
    return out.sort_values(["instruction_status", "task_name"]).reset_index(drop=True)


def subset_summary_row(task_changes: pd.DataFrame, task_set: str, label: str) -> dict[str, object]:
    if task_changes.empty:
        raise ValueError(f"Task subset {task_set} is empty.")
    return {
        "task_set": task_set,
        "label": label,
        "n_tasks": int(task_changes["task_name"].nunique()),
        "tb2_0_pass_rate": float(task_changes["tb2_0_pass_rate"].mean()),
        "tb2_1_pass_rate": float(task_changes["tb2_1_pass_rate"].mean()),
        "pass_rate_change_pp": float(task_changes["change_pp"].mean()),
        "tb2_0_n_trajectories": int(task_changes["tb2_0_n_trajectories"].sum()),
        "tb2_1_n_trajectories": int(task_changes["tb2_1_n_trajectories"].sum()),
    }


def build_robustness_summary(task_changes: pd.DataFrame) -> pd.DataFrame:
    rows = [
        subset_summary_row(task_changes, "all_tasks", "All tasks"),
        subset_summary_row(
            task_changes[task_changes["instruction_status"].eq("instruction_unchanged")],
            "instruction_unchanged",
            "Instruction-unchanged",
        ),
        subset_summary_row(
            task_changes[task_changes["instruction_status"].eq("instruction_changed")],
            "instruction_changed",
            "Instruction-changed",
        ),
    ]
    summary = pd.DataFrame(rows)
    expected = [89, 67, 22]
    observed = summary["n_tasks"].astype(int).tolist()
    if observed != expected:
        raise ValueError(f"Unexpected task counts in robustness summary: {observed}")
    rate_columns = ["tb2_0_pass_rate", "tb2_1_pass_rate", "pass_rate_change_pp"]
    summary[rate_columns] = summary[rate_columns].round(4)
    return summary


def add_improvement_bins(task_changes: pd.DataFrame) -> pd.DataFrame:
    task_changes = task_changes.copy()
    task_changes["improvement_bin"] = np.select(
        [
            task_changes["change_pp"] >= 25,
            task_changes["change_pp"] >= 5,
            task_changes["change_pp"] <= -5,
        ],
        [">= +25 pp", "+5 to < +25 pp", "<= -5 pp"],
        default="approximately unchanged (-5 to +5 pp)",
    )
    return task_changes


def improvement_bin_summary(task_changes: pd.DataFrame) -> pd.DataFrame:
    task_changes = add_improvement_bins(task_changes)
    bins = [
        ">= +25 pp",
        "+5 to < +25 pp",
        "approximately unchanged (-5 to +5 pp)",
        "<= -5 pp",
    ]
    subsets = [
        ("all_tasks", task_changes),
        ("instruction_unchanged", task_changes[task_changes["instruction_status"].eq("instruction_unchanged")]),
        ("instruction_changed", task_changes[task_changes["instruction_status"].eq("instruction_changed")]),
    ]
    rows: list[dict[str, object]] = []
    for task_set, subset in subsets:
        counts = subset["improvement_bin"].value_counts().to_dict()
        for bin_label in bins:
            rows.append(
                {
                    "task_set": task_set,
                    "improvement_bin": bin_label,
                    "n_tasks": int(counts.get(bin_label, 0)),
                }
            )
    return pd.DataFrame(rows)


def gain_distribution_summary(task_changes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for status in ["instruction_unchanged", "instruction_changed"]:
        subset = task_changes[task_changes["instruction_status"].eq(status)]
        rows.append(
            {
                "task_set": status,
                "n_tasks": int(subset["task_name"].nunique()),
                "mean_change_pp": float(subset["change_pp"].mean()),
                "median_change_pp": float(subset["change_pp"].median()),
                "min_change_pp": float(subset["change_pp"].min()),
                "max_change_pp": float(subset["change_pp"].max()),
            }
        )
    return pd.DataFrame(rows).round(4)


def validate_reconciliation(task_changes: pd.DataFrame, summary: pd.DataFrame) -> None:
    unchanged = set(
        task_changes.loc[
            task_changes["instruction_status"].eq("instruction_unchanged"),
            "task_name",
        ]
    )
    changed = set(
        task_changes.loc[
            task_changes["instruction_status"].eq("instruction_changed"),
            "task_name",
        ]
    )
    if unchanged & changed:
        raise ValueError("Instruction-changed and instruction-unchanged task groups overlap.")
    if len(unchanged) != 67 or len(changed) != 22 or len(unchanged | changed) != 89:
        raise ValueError("Instruction task group counts do not reconcile to 89.")
    all_row = summary.loc[summary["task_set"].eq("all_tasks")].iloc[0]
    weighted_change = (
        67 / 89 * summary.loc[summary["task_set"].eq("instruction_unchanged"), "pass_rate_change_pp"].iat[0]
        + 22 / 89 * summary.loc[summary["task_set"].eq("instruction_changed"), "pass_rate_change_pp"].iat[0]
    )
    if abs(float(all_row["pass_rate_change_pp"]) - float(weighted_change)) > 1e-3:
        raise ValueError("Changed/unchanged task-weighted changes do not reconcile to all-task change.")


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

    plot_df = summary.copy()
    plot_df["plot_label"] = [
        f"All tasks\n(n={int(row.n_tasks)})"
        if row.task_set == "all_tasks"
        else f"{row.label}\n(n={int(row.n_tasks)})"
        for row in plot_df.itertuples(index=False)
    ]
    x = np.arange(plot_df.shape[0])
    width = 0.28
    tb2_0_values = plot_df["tb2_0_pass_rate"].astype(float).to_numpy()
    tb2_1_values = plot_df["tb2_1_pass_rate"].astype(float).to_numpy()

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

    ax.set_title("Task-Weighted Pass Rates by Instruction-Change Subset")
    ax.set_ylabel("Task-weighted pass rate (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(plot_df["plot_label"])
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


def write_outputs(
    task_changes: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    task_changes = add_improvement_bins(task_changes)
    bins = improvement_bin_summary(task_changes)
    gains = gain_distribution_summary(task_changes)
    if args.task_changes_csv is not None:
        task_changes_out = task_changes.copy()
        task_changes_out["instruction_status"] = task_changes_out["instruction_status"].astype(str)
        task_changes_out[
            [
                "task_name",
                "instruction_status",
                "tb2_0_pass_rate",
                "tb2_1_pass_rate",
                "change_pp",
                "difficulty",
                "category",
                "tb2_0_n_trajectories",
                "tb2_1_n_trajectories",
                "improvement_bin",
            ]
        ].to_csv(args.task_changes_csv, index=False)
    return bins, gains


def print_summary(
    summary: pd.DataFrame,
    bins: pd.DataFrame,
    gains: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    print("Task-weighted pass-rate summary")
    print(summary[["task_set", "n_tasks", "tb2_0_pass_rate", "tb2_1_pass_rate", "pass_rate_change_pp"]].to_csv(index=False))
    print("Improvement bins")
    print(bins.to_csv(index=False))
    print("Gain distribution")
    print(gains.to_csv(index=False))
    print("Aggregation: each task has equal weight within each subset; task pass rates are means over that task's trajectories per benchmark version.")
    if args.task_changes_csv is not None:
        print(f"Wrote per-task CSV to {args.task_changes_csv}")
    print(f"Wrote figure to {args.out}")


def main() -> None:
    args = parse_args()
    audit = load_audit(args.audit_csv)
    trajectories = load_trajectories(args.trajectory_csv)
    task_changes = build_task_changes(trajectories, audit)
    summary = build_robustness_summary(task_changes)
    validate_reconciliation(task_changes, summary)
    plot(summary, args.out)
    bins, gains = write_outputs(task_changes, args)
    print_summary(summary, bins, gains, args)


if __name__ == "__main__":
    main()
