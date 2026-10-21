#!/usr/bin/env python3
"""Compare difficulty composition and pass rates across TB2.0/TB2.1/TB3.0/TB4.0.

Difficulty labels are intentionally author-intended/static labels:
- TB2.0/TB2.1 use the native task.toml difficulty metadata.
- TB3.0/TB4.0 use LLM labels generated from Harbor task-page
  difficulty_explanation text by 02_label_task_difficulty.py.

Observed pass rates are joined only after labels are fixed. Aggregation is
hierarchical: trajectory -> submission-task -> task -> difficulty/version.
TB3/TB4 labels estimate author-intended difficulty; they are not ground truth.

Outputs:
- data/processed_live/longitudinal/difficulty_over_versions/difficulty_summary.csv
- reports/longitudinal/difficulty_over_versions/difficulty_distribution_over_versions.png
- reports/longitudinal/difficulty_over_versions/pass_rate_by_difficulty_over_versions.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

REPO_ROOT_GUESS = Path(__file__).resolve().parents[3]
if str(REPO_ROOT_GUESS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_GUESS))

from scripts.analysis.plot_style import COLORBLIND_PALETTE, thesis_style
from scripts.benchmark_paths import find_repo_root
from scripts.analysis.longitudinal.difficulty_protocol import require_difficulty_protocol
from scripts.analysis.submission_task_balancing import SOURCE_SUBMISSION_ID, ensure_source_submission_id


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
LONGITUDINAL_DIR = REPO_ROOT / "data" / "processed_live" / "longitudinal"
TB2_TRAJECTORY_DEFAULT = LONGITUDINAL_DIR / "trajectory_longitudinal.csv"
TB3_TB4_TRAJECTORY_DEFAULT = LONGITUDINAL_DIR / "tb3_tb4" / "trajectory_longitudinal.csv"
TB3_TB4_LABELS_DEFAULT = LONGITUDINAL_DIR / "inputs/tb3_tb4_task_difficulty_llm_labels.csv"
OUT_DIR_DEFAULT = LONGITUDINAL_DIR / "difficulty_over_versions"
FIGURES_DIR_DEFAULT = REPO_ROOT / "reports" / "longitudinal" / "difficulty_over_versions"

VERSIONS = ["2.0", "2.1", "3.0", "4.0"]
VERSION_LABELS = {"2.0": "TB2.0", "2.1": "TB2.1", "3.0": "TB3.0", "4.0": "TB4.0"}
DIFFICULTY_VERSION_LABELS = {
    version: f"{label}\n{'Native metadata' if version in {'2.0', '2.1'} else 'LLM estimate'}"
    for version, label in VERSION_LABELS.items()
}
DIFFICULTY_ORDER = ["easy", "medium", "hard"]
DIFFICULTY_COLORS = {
    "easy": COLORBLIND_PALETTE[2],
    "medium": COLORBLIND_PALETTE[4],
    "hard": COLORBLIND_PALETTE[1],
}
EXPECTED_LABEL_TARGET = "author_intended_static_task_difficulty"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tb2-trajectories", type=Path, default=TB2_TRAJECTORY_DEFAULT)
    parser.add_argument("--tb3-tb4-trajectories", type=Path, default=TB3_TB4_TRAJECTORY_DEFAULT)
    parser.add_argument("--tb3-tb4-labels", type=Path, default=TB3_TB4_LABELS_DEFAULT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT)
    parser.add_argument("--submission-unit", choices=["source", "leaderboard-url"], default="source")
    parser.add_argument("--include-sensitivities", action="store_true",
                        help="Also write URL-grouped pass-rate tables using the same fixed labels.")
    parser.add_argument("--include-diagnostics", action="store_true",
                        help="Also export separate distribution, pass-rate and adjacent-change tables.")
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR_DEFAULT)
    return parser.parse_args()


def require_columns(df: pd.DataFrame, required: set[str], path: Path) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")


def load_trajectories(path: Path, versions: set[str]) -> pd.DataFrame:
    required = {"benchmark_version", "task_name", "submission_id", "passed", "reward"}
    df = pd.read_csv(path, low_memory=False)
    require_columns(df, required, path)
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    df = df[df["benchmark_version"].isin(versions)].copy()
    df["passed"] = pd.to_numeric(df["passed"], errors="coerce")
    df["reward"] = pd.to_numeric(df["reward"], errors="coerce")
    return df[df["reward"].isin([0.0, 1.0])].copy()


def normalize_difficulty(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower()


def load_tb2_labels(tb2: pd.DataFrame) -> pd.DataFrame:
    required = {"benchmark_version", "task_name", "difficulty"}
    missing = sorted(required.difference(tb2.columns))
    if missing:
        raise ValueError(f"TB2 trajectory table is missing columns for native difficulty labels: {missing}")
    labels = tb2[["benchmark_version", "task_name", "difficulty"]].drop_duplicates().copy()
    labels["difficulty_label"] = normalize_difficulty(labels["difficulty"])
    labels = labels[labels["difficulty_label"].isin(DIFFICULTY_ORDER)].copy()
    labels["difficulty_source"] = "tb2_native_task_metadata"
    labels["label_target"] = EXPECTED_LABEL_TARGET
    return labels[["benchmark_version", "task_name", "difficulty_label", "difficulty_source", "label_target"]]


def load_tb3_tb4_labels(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run `python -m scripts.analysis.longitudinal.02_label_task_difficulty` first."
        )
    labels = pd.read_csv(path, low_memory=False)
    require_difficulty_protocol(labels, path)
    required = {"benchmark_version", "task_name", "llm_difficulty_label"}
    require_columns(labels, required, path)
    labels["benchmark_version"] = labels["benchmark_version"].astype(str)
    labels["difficulty_label"] = normalize_difficulty(labels["llm_difficulty_label"])
    source_counts = labels["label_source"].fillna("").astype(str).value_counts().to_dict() if "label_source" in labels.columns else {}
    error_count = (
        int(labels["llm_rationale"].fillna("").astype(str).str.startswith("ERROR:").sum())
        if "llm_rationale" in labels.columns
        else 0
    )
    if "label_target" in labels.columns:
        target = labels["label_target"].fillna("").astype(str).str.strip()
        invalid = target.ne("") & target.ne(EXPECTED_LABEL_TARGET)
        if invalid.any():
            examples = labels.loc[invalid, ["benchmark_version", "task_name", "label_target"]].head(5)
            raise ValueError(
                "TB3/TB4 labels have an unexpected label_target. "
                f"Expected {EXPECTED_LABEL_TARGET!r}. Examples: {examples.to_dict(orient='records')}"
            )
    raw_row_count = int(labels.shape[0])
    labels = labels[labels["difficulty_label"].isin(DIFFICULTY_ORDER)].copy()
    if labels.empty:
        raise ValueError(
            f"{path} contains no valid easy/medium/hard TB3/TB4 labels. "
            f"Rows read: {raw_row_count}; label_source counts: {source_counts}; "
            f"error rows: {error_count}. Rerun "
            "`python -m scripts.analysis.longitudinal.02_label_task_difficulty` "
            "after configuring the fixed three-LLM panel."
        )
    labels["difficulty_source"] = "llm_from_harbor_difficulty_explanation"
    labels["label_target"] = EXPECTED_LABEL_TARGET
    keep = ["benchmark_version", "task_name", "difficulty_label", "difficulty_source", "label_target"]
    labels = labels.sort_values(["benchmark_version", "task_name"]).drop_duplicates(
        ["benchmark_version", "task_name"], keep="last"
    )
    missing_versions = sorted({"3.0", "4.0"}.difference(set(labels["benchmark_version"])))
    if missing_versions:
        counts = labels["benchmark_version"].value_counts().to_dict()
        raise ValueError(
            f"{path} is missing valid difficulty labels for version(s): {', '.join(missing_versions)}. "
            f"Valid label counts by version: {counts}."
        )
    return labels[keep].copy()


def build_distribution(labels: pd.DataFrame) -> pd.DataFrame:
    tasks = labels.drop_duplicates(["benchmark_version", "task_name"]).copy()
    totals = tasks.groupby("benchmark_version")["task_name"].nunique().rename("version_task_count")
    grouped = (
        tasks.groupby(["benchmark_version", "difficulty_label"], as_index=False)
        .agg(n_tasks=("task_name", "nunique"))
        .merge(totals, on="benchmark_version", how="left")
    )
    grouped["task_share"] = grouped["n_tasks"] / grouped["version_task_count"]
    grouped["difficulty_order"] = grouped["difficulty_label"].map(DIFFICULTY_ORDER.index)
    return grouped.sort_values(["benchmark_version", "difficulty_order"])


def build_task_pass_rates(
    trajectories: pd.DataFrame, labels: pd.DataFrame, *, submission_unit: str = "source"
) -> pd.DataFrame:
    if submission_unit == "source":
        trajectories = ensure_source_submission_id(trajectories)
        identity = SOURCE_SUBMISSION_ID
    elif submission_unit == "leaderboard-url":
        identity = "source_submission_url"
    else:
        raise ValueError(f"Unknown submission unit: {submission_unit}")
    df = trajectories.merge(labels, on=["benchmark_version", "task_name"], how="inner", validate="many_to_one")
    if df.empty:
        raise ValueError("No trajectory rows matched difficulty labels.")
    submission_task = (
        df.groupby(["benchmark_version", "difficulty_label", "task_name", identity], as_index=False)
        .agg(
            n_trials=("passed", "size"),
            pass_count=("passed", "sum"),
            submission_task_pass_rate=("passed", "mean"),
        )
    )
    task_rates = (
        submission_task.groupby(["benchmark_version", "difficulty_label", "task_name"], as_index=False)
        .agg(
            n_submissions=(identity, "nunique"),
            n_trials=("n_trials", "sum"),
            pass_count=("pass_count", "sum"),
            task_pass_rate=("submission_task_pass_rate", "mean"),
        )
    )
    task_rates["pooled_task_pass_rate"] = task_rates["pass_count"] / task_rates["n_trials"]
    task_rates["submission_unit"] = submission_unit
    return task_rates


def build_pass_rate_summary(task_rates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (version, label), subset in task_rates.groupby(["benchmark_version", "difficulty_label"]):
        rows.append(
            {
                "benchmark_version": version,
                "task_weighting": "submission-balanced",
                "submission_unit": str(subset["submission_unit"].iloc[0]),
                "version_label": VERSION_LABELS.get(str(version), str(version)),
                "difficulty_label": label,
                "difficulty_order": DIFFICULTY_ORDER.index(label),
                "n_tasks": int(subset["task_name"].nunique()),
                "n_trials": int(subset["n_trials"].sum()),
                "task_weighted_pass_rate": float(subset["task_pass_rate"].mean()),
                "task_median_pass_rate": float(subset["task_pass_rate"].median()),
                "task_pass_rate_p25": float(subset["task_pass_rate"].quantile(0.25)),
                "task_pass_rate_p75": float(subset["task_pass_rate"].quantile(0.75)),
                "pooled_task_mean_pass_rate": float(subset["pooled_task_pass_rate"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["benchmark_version", "difficulty_order"])


def build_adjacent_changes(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for old_version, new_version in [("2.0", "2.1"), ("2.1", "3.0"), ("3.0", "4.0")]:
        old = summary[summary["benchmark_version"].eq(old_version)].copy()
        new = summary[summary["benchmark_version"].eq(new_version)].copy()
        paired = old.merge(new, on="difficulty_label", suffixes=("_old", "_new"))
        if paired.empty:
            continue
        paired.insert(0, "version_pair", f"{old_version}->{new_version}")
        paired["task_weighted_pass_rate_change_pp"] = (
            paired["task_weighted_pass_rate_new"] - paired["task_weighted_pass_rate_old"]
        ) * 100.0
        paired["task_count_change"] = paired["n_tasks_new"] - paired["n_tasks_old"]
        rows.append(paired)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True).sort_values(["version_pair", "difficulty_order_old"])


def plot_distribution(distribution: pd.DataFrame, path: Path) -> None:
    thesis_style()
    fig, ax = plt.subplots(figsize=(6.8, 3.25))
    pivot = (
        distribution.pivot(index="benchmark_version", columns="difficulty_label", values="task_share")
        .reindex(index=VERSIONS, columns=DIFFICULTY_ORDER)
        .fillna(0.0)
    )
    x = np.arange(len(VERSIONS))
    bottom = np.zeros(len(VERSIONS))
    for difficulty in DIFFICULTY_ORDER:
        values = pivot[difficulty].to_numpy()
        ax.bar(
            x,
            values,
            bottom=bottom,
            color=DIFFICULTY_COLORS[difficulty],
            edgecolor="white",
            linewidth=0.6,
            label=difficulty.capitalize(),
        )
        bottom += values
    ax.set_ylabel("Share of tasks")
    ax.set_xticks(x)
    ax.set_xticklabels([DIFFICULTY_VERSION_LABELS[version] for version in VERSIONS])
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.grid(axis="y", color="#D0D0D0", alpha=0.45, linewidth=0.7)
    ax.set_axisbelow(True)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_pass_rates(summary: pd.DataFrame, path: Path) -> None:
    thesis_style()
    fig, ax = plt.subplots(figsize=(7.0, 3.55))
    x = np.arange(len(VERSIONS))
    offsets = {"easy": -0.16, "medium": 0.0, "hard": 0.16}
    for difficulty in DIFFICULTY_ORDER:
        subset = summary[summary["difficulty_label"].eq(difficulty)].copy()
        values = (
            subset.set_index("benchmark_version")["task_weighted_pass_rate"]
            .reindex(VERSIONS)
            .to_numpy(dtype=float)
        )
        present = ~np.isnan(values)
        ax.plot(
            x[present] + offsets[difficulty],
            values[present],
            marker="o",
            linewidth=1.6,
            markersize=5,
            color=DIFFICULTY_COLORS[difficulty],
            label=difficulty.capitalize(),
        )
        for xi, yi in zip(x[present] + offsets[difficulty], values[present]):
            ax.text(xi, yi + 0.025, f"{yi:.0%}", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("Pass rate")
    ax.set_xticks(x)
    ax.set_xticklabels([DIFFICULTY_VERSION_LABELS[version] for version in VERSIONS])
    ax.set_ylim(0, min(1.05, max(0.2, float(summary["task_weighted_pass_rate"].max()) + 0.16)))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))
    ax.grid(axis="y", color="#D0D0D0", alpha=0.45, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.13))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def print_summary(distribution: pd.DataFrame, pass_summary: pd.DataFrame) -> None:
    print("Difficulty labels: TB2.x native metadata; TB3/TB4 LLM estimates")
    for row in distribution.itertuples(index=False):
        print(f"{row.benchmark_version},{row.difficulty_label},{row.n_tasks},{row.task_share:.1%}")
    print("")
    print("Task-weighted pass rate by difficulty")
    for row in pass_summary.itertuples(index=False):
        print(
            f"{row.benchmark_version},{row.difficulty_label},{row.n_tasks},"
            f"{row.task_weighted_pass_rate:.1%}"
        )


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    tb2 = load_trajectories(args.tb2_trajectories, {"2.0", "2.1"})
    tb3_tb4 = load_trajectories(args.tb3_tb4_trajectories, {"3.0", "4.0"})
    labels = pd.concat(
        [load_tb2_labels(tb2), load_tb3_tb4_labels(args.tb3_tb4_labels)],
        ignore_index=True,
    )
    trajectories = pd.concat([tb2, tb3_tb4], ignore_index=True)
    distribution = build_distribution(labels)
    task_rates = build_task_pass_rates(trajectories, labels, submission_unit=args.submission_unit)
    pass_summary = build_pass_rate_summary(task_rates)
    changes = build_adjacent_changes(pass_summary)

    distribution_path = args.out_dir / "difficulty_distribution_over_versions.csv"
    pass_summary_path = args.out_dir / "pass_rate_by_difficulty_over_versions.csv"
    changes_path = args.out_dir / "pass_rate_change_by_difficulty_over_versions.csv"
    summary_path = args.out_dir / "difficulty_summary.csv"
    combined = distribution.merge(
        pass_summary.rename(columns={"n_tasks": "n_tasks_with_trials"}),
        on=["benchmark_version", "difficulty_label", "difficulty_order"],
        how="outer", validate="one_to_one",
    ).sort_values(["benchmark_version", "difficulty_order"], kind="stable")
    combined.to_csv(summary_path, index=False)
    if args.include_diagnostics:
        distribution.to_csv(distribution_path, index=False)
        pass_summary.to_csv(pass_summary_path, index=False)
        changes.to_csv(changes_path, index=False)
    if args.include_sensitivities:
        url_summary = build_pass_rate_summary(build_task_pass_rates(
            trajectories, labels, submission_unit="leaderboard-url",
        ))
        url_summary.to_csv(args.out_dir / "pass_rate_by_difficulty_over_versions_url_sensitivity.csv", index=False)
        build_adjacent_changes(url_summary).to_csv(
            args.out_dir / "pass_rate_change_by_difficulty_over_versions_url_sensitivity.csv", index=False,
        )

    distribution_figure = args.figures_dir / "difficulty_distribution_over_versions.png"
    pass_rate_figure = args.figures_dir / "pass_rate_by_difficulty_over_versions.png"
    plot_distribution(distribution, distribution_figure)
    plot_pass_rates(pass_summary, pass_rate_figure)

    print_summary(distribution, pass_summary)
    print(f"Wrote {summary_path}")
    print(f"Wrote {distribution_figure}")
    print(f"Wrote {pass_rate_figure}")


if __name__ == "__main__":
    main()
