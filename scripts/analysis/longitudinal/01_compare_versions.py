#!/usr/bin/env python3
"""Descriptive 2.0 vs 2.1 trajectory and task-composition comparisons."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from scripts.benchmark_paths import find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
PROCESSED_DIR = REPO_ROOT / "data" / "processed_live"
LONGITUDINAL_DIR = PROCESSED_DIR / "longitudinal"
REPORTS_DIR = REPO_ROOT / "reports" / "longitudinal"

BENCHMARKS = ("terminal_bench_2_0", "terminal_bench_2_1")
METRICS = [
    "passed",
    "step_count",
    "agent_step_count",
    "tool_call_count",
    "command_count",
    "message_chars",
    "observation_chars",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
    "duration_seconds",
]
PRIMARY_METRICS = ["passed", "step_count", "command_count", "tool_call_count", "total_tokens", "duration_seconds"]
METRIC_LABELS = {
    "passed": "Pass rate",
    "step_count": "Steps",
    "agent_step_count": "Agent steps",
    "tool_call_count": "Tool calls",
    "command_count": "Commands",
    "message_chars": "Message chars",
    "observation_chars": "Observation chars",
    "prompt_tokens": "Prompt tokens",
    "completion_tokens": "Completion tokens",
    "total_tokens": "Total tokens",
    "cost_usd": "Cost USD",
    "duration_seconds": "Duration seconds",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=LONGITUDINAL_DIR / "trajectory_longitudinal.csv")
    parser.add_argument("--command-pattern-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--out", type=Path, default=LONGITUDINAL_DIR / "version_compare")
    parser.add_argument("--figures-dir", type=Path, default=REPORTS_DIR)
    return parser.parse_args()


def clean_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def finite_values(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values[np.isfinite(values)]


def summarize(values: pd.Series) -> dict[str, Any]:
    values = finite_values(values)
    if values.empty:
        return {
            "n": 0,
            "missing": int(series_len_safe(values)),
            "mean": np.nan,
            "median": np.nan,
            "p25": np.nan,
            "p75": np.nan,
            "p90": np.nan,
        }
    return {
        "n": int(values.shape[0]),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "p25": float(values.quantile(0.25)),
        "p75": float(values.quantile(0.75)),
        "p90": float(values.quantile(0.90)),
    }


def series_len_safe(values: pd.Series) -> int:
    return int(values.shape[0])


def standardized_mean_difference(a: pd.Series, b: pd.Series) -> float | None:
    a = finite_values(a)
    b = finite_values(b)
    if a.empty or b.empty:
        return None
    pooled = math.sqrt((float(a.var(ddof=1)) + float(b.var(ddof=1))) / 2)
    if pooled == 0 or math.isnan(pooled):
        return None
    return float((b.mean() - a.mean()) / pooled)


def ks_p_value(a: pd.Series, b: pd.Series) -> float | None:
    a = finite_values(a)
    b = finite_values(b)
    if a.empty or b.empty:
        return None
    return float(stats.ks_2samp(a, b).pvalue)


def raw_metric_tables(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    diff_rows: list[dict[str, Any]] = []
    groups = {benchmark: df[df["benchmark"].eq(benchmark)] for benchmark in BENCHMARKS}

    for metric in METRICS:
        for benchmark, group in groups.items():
            s = summarize(group[metric])
            s.update({"benchmark": benchmark, "metric": metric, "metric_label": METRIC_LABELS.get(metric, metric)})
            s["missing"] = int(pd.to_numeric(group[metric], errors="coerce").isna().sum())
            summary_rows.append(s)

        a = finite_values(groups[BENCHMARKS[0]][metric])
        b = finite_values(groups[BENCHMARKS[1]][metric])
        mean_a = float(a.mean()) if not a.empty else np.nan
        mean_b = float(b.mean()) if not b.empty else np.nan
        med_a = float(a.median()) if not a.empty else np.nan
        med_b = float(b.median()) if not b.empty else np.nan
        diff_rows.append(
            {
                "metric": metric,
                "metric_label": METRIC_LABELS.get(metric, metric),
                "n_2_0": int(a.shape[0]),
                "n_2_1": int(b.shape[0]),
                "mean_2_0": mean_a,
                "mean_2_1": mean_b,
                "mean_diff_2_1_minus_2_0": mean_b - mean_a,
                "mean_ratio_2_1_over_2_0": mean_b / mean_a if mean_a not in {0, np.nan} and not np.isnan(mean_a) else np.nan,
                "median_2_0": med_a,
                "median_2_1": med_b,
                "median_diff_2_1_minus_2_0": med_b - med_a,
                "standardized_mean_difference": standardized_mean_difference(a, b),
                "ks_p_value": ks_p_value(a, b) if metric != "passed" else None,
            }
        )

    return pd.DataFrame(summary_rows), pd.DataFrame(diff_rows)


def composition_table(df: pd.DataFrame, column: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_by_benchmark = df.groupby("benchmark").size()
    task_total_by_benchmark = df.groupby("benchmark")["task_name"].nunique()
    for (benchmark, level), group in df.groupby(["benchmark", column], dropna=False):
        rows.append(
            {
                "dimension": column,
                "benchmark": benchmark,
                "level": "missing" if pd.isna(level) else str(level),
                "trajectory_count": int(group.shape[0]),
                "trajectory_share": float(group.shape[0] / total_by_benchmark.loc[benchmark]),
                "task_count": int(group["task_name"].nunique()),
                "task_share": float(group["task_name"].nunique() / task_total_by_benchmark.loc[benchmark]),
                "pass_rate": float(group["passed"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["dimension", "level", "benchmark"])


def task_matched_differences(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metric_agg = {
        metric: "mean" if metric == "passed" else "median"
        for metric in PRIMARY_METRICS
    }
    by_task = (
        df.groupby(["task_name", "benchmark"], as_index=False)
        .agg(
            trajectory_count=("rel_path", "size"),
            category=("category", "first"),
            difficulty=("difficulty", "first"),
            **{metric: (metric, agg) for metric, agg in metric_agg.items()},
        )
    )
    wide = by_task.pivot(index="task_name", columns="benchmark", values=PRIMARY_METRICS + ["trajectory_count"])
    detail_rows: list[dict[str, Any]] = []
    for task in wide.index:
        row: dict[str, Any] = {"task_name": task}
        meta = by_task[by_task["task_name"].eq(task)].iloc[0]
        row["category"] = meta["category"]
        row["difficulty"] = meta["difficulty"]
        has_both = True
        for benchmark in BENCHMARKS:
            try:
                count = wide.loc[task, ("trajectory_count", benchmark)]
            except KeyError:
                count = np.nan
            row[f"trajectory_count_{benchmark}"] = count
            has_both = has_both and pd.notna(count) and count > 0
        row["in_both_versions"] = bool(has_both)
        for metric in PRIMARY_METRICS:
            values = {}
            for benchmark in BENCHMARKS:
                try:
                    values[benchmark] = wide.loc[task, (metric, benchmark)]
                except KeyError:
                    values[benchmark] = np.nan
                row[f"{metric}_{benchmark}"] = values[benchmark]
            row[f"{metric}_diff_2_1_minus_2_0"] = values[BENCHMARKS[1]] - values[BENCHMARKS[0]]
        detail_rows.append(row)
    detail = pd.DataFrame(detail_rows).sort_values("task_name")

    summary_rows = []
    matched = detail[detail["in_both_versions"]].copy()
    for metric in PRIMARY_METRICS:
        diffs = finite_values(matched[f"{metric}_diff_2_1_minus_2_0"])
        summary_rows.append(
            {
                "metric": metric,
                "metric_label": METRIC_LABELS.get(metric, metric),
                "matched_task_count": int(diffs.shape[0]),
                "mean_task_difference": float(diffs.mean()) if not diffs.empty else np.nan,
                "median_task_difference": float(diffs.median()) if not diffs.empty else np.nan,
                "tasks_higher_in_2_1": int((diffs > 0).sum()),
                "tasks_lower_in_2_1": int((diffs < 0).sum()),
                "wilcoxon_p_value": float(stats.wilcoxon(diffs).pvalue) if int((diffs != 0).sum()) > 0 else None,
            }
        )
    return detail, pd.DataFrame(summary_rows)


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    mask = pd.to_numeric(values, errors="coerce").notna() & pd.to_numeric(weights, errors="coerce").notna()
    values = pd.to_numeric(values[mask], errors="coerce")
    weights = pd.to_numeric(weights[mask], errors="coerce")
    total = float(weights.sum())
    if total == 0:
        return np.nan
    return float((values * weights).sum() / total)


def reweighted_differences(df: pd.DataFrame) -> pd.DataFrame:
    groups = {benchmark: df[df["benchmark"].eq(benchmark)].copy() for benchmark in BENCHMARKS}
    task_props = {
        benchmark: group["task_name"].value_counts(normalize=True)
        for benchmark, group in groups.items()
    }
    rows: list[dict[str, Any]] = []

    work = df.copy()
    task_counts = work.groupby(["benchmark", "task_name"]).size().rename("n").reset_index()
    work = work.merge(task_counts, on=["benchmark", "task_name"], how="left")
    work["uniform_task_weight"] = 1.0 / work["n"]

    target = task_props[BENCHMARKS[0]]
    observed = task_props[BENCHMARKS[1]]
    reweight_map = (target / observed).replace([np.inf, -np.inf], np.nan).dropna()
    groups[BENCHMARKS[1]]["weight_to_2_0_task_mix"] = groups[BENCHMARKS[1]]["task_name"].map(reweight_map).fillna(0.0)

    for metric in PRIMARY_METRICS:
        raw_2_0 = float(finite_values(groups[BENCHMARKS[0]][metric]).mean())
        raw_2_1 = float(finite_values(groups[BENCHMARKS[1]][metric]).mean())
        uniform_2_0 = weighted_mean(
            work.loc[work["benchmark"].eq(BENCHMARKS[0]), metric],
            work.loc[work["benchmark"].eq(BENCHMARKS[0]), "uniform_task_weight"],
        )
        uniform_2_1 = weighted_mean(
            work.loc[work["benchmark"].eq(BENCHMARKS[1]), metric],
            work.loc[work["benchmark"].eq(BENCHMARKS[1]), "uniform_task_weight"],
        )
        reweighted_2_1 = weighted_mean(
            groups[BENCHMARKS[1]][metric],
            groups[BENCHMARKS[1]]["weight_to_2_0_task_mix"],
        )
        rows.append(
            {
                "metric": metric,
                "metric_label": METRIC_LABELS.get(metric, metric),
                "raw_2_0_mean": raw_2_0,
                "raw_2_1_mean": raw_2_1,
                "raw_diff_2_1_minus_2_0": raw_2_1 - raw_2_0,
                "two_1_reweighted_to_2_0_task_mix": reweighted_2_1,
                "task_mix_adjusted_diff": reweighted_2_1 - raw_2_0,
                "trajectory_mix_component": raw_2_1 - reweighted_2_1,
                "uniform_task_2_0_mean": uniform_2_0,
                "uniform_task_2_1_mean": uniform_2_1,
                "uniform_task_diff_2_1_minus_2_0": uniform_2_1 - uniform_2_0,
            }
        )
    return pd.DataFrame(rows)


def overlapping_agent_differences(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    support = df.groupby(["benchmark", "agent_key"]).size().reset_index(name="n")
    common_agents = sorted(
        set(support.loc[support["benchmark"].eq(BENCHMARKS[0]), "agent_key"])
        & set(support.loc[support["benchmark"].eq(BENCHMARKS[1]), "agent_key"])
    )
    subset = df[df["agent_key"].isin(common_agents)].copy()
    if subset.empty:
        return pd.DataFrame(), pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for (agent_key, task_name), group in subset.groupby(["agent_key", "task_name"]):
        versions = set(group["benchmark"])
        if not set(BENCHMARKS).issubset(versions):
            continue
        row: dict[str, Any] = {"agent_key": agent_key, "task_name": task_name}
        row["scaffold"] = group["scaffold"].iloc[0]
        row["model_dir"] = group["model_dir"].iloc[0]
        row["category"] = group["category"].iloc[0]
        row["difficulty"] = group["difficulty"].iloc[0]
        versions_text = (
            group.groupby("benchmark")["agent_version"]
            .agg(lambda s: "|".join(sorted({str(v) for v in s.dropna().unique()})))
            .to_dict()
        )
        row["agent_versions_2_0"] = versions_text.get(BENCHMARKS[0], "")
        row["agent_versions_2_1"] = versions_text.get(BENCHMARKS[1], "")
        for metric in PRIMARY_METRICS:
            means = group.groupby("benchmark")[metric].mean()
            row[f"{metric}_2_0"] = means.get(BENCHMARKS[0], np.nan)
            row[f"{metric}_2_1"] = means.get(BENCHMARKS[1], np.nan)
            row[f"{metric}_diff_2_1_minus_2_0"] = row[f"{metric}_2_1"] - row[f"{metric}_2_0"]
        rows.append(row)
    detail = pd.DataFrame(rows)

    summary_rows: list[dict[str, Any]] = []
    if not detail.empty:
        for (agent_key, scaffold, model_dir), group in detail.groupby(["agent_key", "scaffold", "model_dir"]):
            for metric in PRIMARY_METRICS:
                diffs = finite_values(group[f"{metric}_diff_2_1_minus_2_0"])
                summary_rows.append(
                    {
                        "agent_key": agent_key,
                        "scaffold": scaffold,
                        "model_dir": model_dir,
                        "metric": metric,
                        "metric_label": METRIC_LABELS.get(metric, metric),
                        "matched_task_count": int(diffs.shape[0]),
                        "mean_task_difference": float(diffs.mean()) if not diffs.empty else np.nan,
                        "median_task_difference": float(diffs.median()) if not diffs.empty else np.nan,
                    }
                )
    return detail, pd.DataFrame(summary_rows)


def command_pattern_shift(command_pattern_dir: Path) -> pd.DataFrame:
    frames = []
    for benchmark in BENCHMARKS:
        path = command_pattern_dir / benchmark / "command_patterns.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if "command_head" not in df.columns or "count" not in df.columns:
            continue
        df = df[["command_head", "count", "example_command"]].copy()
        df["benchmark"] = benchmark
        frames.append(df)
    if len(frames) != 2:
        return pd.DataFrame()
    commands = pd.concat(frames, ignore_index=True)
    totals = commands.groupby("benchmark")["count"].sum()
    commands["share"] = commands["count"] / commands["benchmark"].map(totals)
    wide = commands.pivot_table(index="command_head", columns="benchmark", values=["count", "share"], fill_value=0)
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    examples = commands.groupby("command_head")["example_command"].first()
    out = wide.reset_index().merge(examples.rename("example_command"), on="command_head", how="left")
    out["share_diff_2_1_minus_2_0"] = out.get(f"share_{BENCHMARKS[1]}", 0) - out.get(f"share_{BENCHMARKS[0]}", 0)
    out["log2_share_ratio_2_1_over_2_0"] = np.log2(
        (out.get(f"share_{BENCHMARKS[1]}", 0) + 1e-6) / (out.get(f"share_{BENCHMARKS[0]}", 0) + 1e-6)
    )
    return out.sort_values("share_diff_2_1_minus_2_0", ascending=False)


def plot_primary_differences(diff: pd.DataFrame, path: Path) -> None:
    subset = diff[diff["metric"].isin(PRIMARY_METRICS)].copy()
    if subset.empty:
        return
    subset["label"] = subset["metric"].map(METRIC_LABELS)

    fig, axes = plt.subplots(2, 3, figsize=(11, 6.4))
    axes_flat = axes.flatten()
    colors = ["#4c78a8", "#f58518"]
    labels = ["2.0", "2.1"]

    for ax, (_, row) in zip(axes_flat, subset.iterrows()):
        if row["metric"] == "passed":
            values = [row["mean_2_0"], row["mean_2_1"]]
            value_kind = "Mean"
        else:
            values = [row["median_2_0"], row["median_2_1"]]
            value_kind = "Median"
        bars = ax.bar(labels, values, color=colors, width=0.58)
        finite = [float(value) for value in values if pd.notna(value) and np.isfinite(value)]
        ymax = max(finite) if finite else 1.0
        ypad = ymax * 0.18 if ymax > 0 else 1.0
        ax.set_ylim(0, ymax + ypad)
        ax.set_title(f"{row['label']} ({value_kind.lower()})")
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", length=0)

        for bar, value in zip(bars, values):
            if pd.isna(value) or not np.isfinite(value):
                continue
            if row["metric"] == "passed":
                label = f"{value:.1%}"
            else:
                label = f"{value:,.0f}" if abs(value) >= 10 else f"{value:.2g}"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + ypad * 0.08,
                label,
                ha="center",
                va="bottom",
                fontsize=9,
            )

    for ax in axes_flat[len(subset):]:
        ax.axis("off")

    fig.suptitle("Primary trajectory metrics by benchmark version", y=0.98)
    fig.supxlabel("Benchmark version")
    fig.supylabel("Metric value")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input, low_memory=False)
    required = {"benchmark", "rel_path", "task_name", "scaffold", "model_dir", "agent_key", "passed", *METRICS}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{args.input} is missing required columns: {', '.join(missing)}")
    df = clean_numeric(df, METRICS)

    summary, raw_diff = raw_metric_tables(df)
    composition = pd.concat(
        [
            composition_table(df, "difficulty"),
            composition_table(df, "category"),
            composition_table(df, "scaffold"),
            composition_table(df, "agent_key"),
        ],
        ignore_index=True,
    )
    task_detail, task_summary = task_matched_differences(df)
    reweighted = reweighted_differences(df)
    agent_detail, agent_summary = overlapping_agent_differences(df)
    commands = command_pattern_shift(args.command_pattern_dir)

    summary.to_csv(args.out / "version_metric_summary.csv", index=False)
    raw_diff.to_csv(args.out / "raw_version_differences.csv", index=False)
    composition.to_csv(args.out / "composition_by_version.csv", index=False)
    task_detail.to_csv(args.out / "task_matched_metric_differences.csv", index=False)
    task_summary.to_csv(args.out / "task_matched_summary.csv", index=False)
    reweighted.to_csv(args.out / "task_mix_reweighted_differences.csv", index=False)
    agent_detail.to_csv(args.out / "overlapping_agent_task_differences.csv", index=False)
    agent_summary.to_csv(args.out / "overlapping_agent_summary.csv", index=False)
    if not commands.empty:
        commands.to_csv(args.out / "command_pattern_shift.csv", index=False)

    plot_primary_differences(raw_diff, args.figures_dir / "median_metric_shift.png")

    print(f"Wrote comparison tables to {args.out}")
    print(f"Wrote figures to {args.figures_dir}")


if __name__ == "__main__":
    main()
