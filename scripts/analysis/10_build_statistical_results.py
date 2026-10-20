#!/usr/bin/env python3
"""Build the compact inferential tables and thesis-facing statistical results.

This script consumes the RQ-specific outputs produced by the existing analysis
scripts and adds the longitudinal paired/independent-task comparisons requested
for the thesis. It never reads or modifies raw trajectory JSON.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import io
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.analysis.statistical_helpers import (
    cliffs_delta,
    paired_cohens_dz,
    two_sided_mann_whitney,
    two_sided_signed_rank,
)
from scripts.benchmark_paths import find_repo_root
from scripts.analysis.submission_task_balancing import SOURCE_SUBMISSION_ID, ensure_source_submission_id
from scripts.analysis.longitudinal.official_release_changes import add_release_status, EXPECTED


REPO_ROOT = find_repo_root(Path(__file__).resolve().parent)
PROCESSED = REPO_ROOT / "data" / "processed_live"
DIM_DIR = PROCESSED / "diminishing_returns"
TASK_DIR = PROCESSED / "task_mining"
LONG_DIR = PROCESSED / "longitudinal"
OUT_DEFAULT = PROCESSED / "statistical_analysis"
REPORT_DEFAULT = REPO_ROOT / "reports" / "statistical_results.md"

ADJACENT_CHANGES = LONG_DIR / "task_composition" / "adjacent_version_task_changes.csv"
TB2_TRAJECTORIES = LONG_DIR / "trajectory_longitudinal.csv"
TB34_TRAJECTORIES = LONG_DIR / "tb3_tb4" / "trajectory_longitudinal.csv"

RQ1_1 = DIM_DIR / "rq1_1_success_failure_inference.csv"
RQ1_2 = DIM_DIR / "rq1_2_quadratic_regression.csv"
RQ1_FULL = DIM_DIR / "rq1_final_statistical_results.csv"
RQ2_1 = TASK_DIR / "rq2_1_difficulty_significance.csv"
RQ2_2_HUMAN = TASK_DIR / "time_estimates" / "rq2_2_human_time_inference.csv"
RQ2_3 = TASK_DIR / "tools" / "rq2_3_functional_behavior_inference.csv"
MEDIA_TASKS = TASK_DIR / "tags" / "perceptual_media_tasks.csv"

METRIC_LABELS = {
    "step_count": "Steps",
    "shell_invocation_count": "Shell invocations",
    "tool_call_count": "Structured tool calls",
    "prompt_tokens": "Input tokens",
    "completion_tokens": "Output tokens",
    "total_tokens": "Total tokens",
    "duration_seconds": "Duration",
    "cost_usd_positive": "Cost",
    "steps": "Steps",
    "shell_invocations": "Shell invocations",
    "tool_calls": "Structured tool calls",
    "duration": "Duration",
}
METRIC_UNITS = {
    "step_count": "steps",
    "shell_invocation_count": "invocations",
    "tool_call_count": "calls",
    "prompt_tokens": "tokens",
    "completion_tokens": "tokens",
    "total_tokens": "tokens",
    "duration_seconds": "seconds",
    "cost_usd_positive": "USD",
    "steps": "steps",
    "shell_invocations": "invocations",
    "tool_calls": "calls",
    "duration": "seconds",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--report", type=Path, default=REPORT_DEFAULT)
    parser.add_argument("--output-root", type=Path,
                        help="Mirror repository output paths under this directory; keep source inputs unchanged.")
    parser.add_argument("--rq3-1-only", action="store_true",
                        help="Update release-group results using existing unrelated RQ outputs.")
    return parser.parse_args()


def read_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing prerequisite output: {path}")
    return pd.read_csv(path, low_memory=False)


def write_scoped_master(path: Path, master: pd.DataFrame) -> None:
    """Replace only the two grouping rows, preserving unrelated CSV bytes."""
    source = path if path.exists() else OUT_DEFAULT / path.name
    lines = source.read_bytes().decode("utf-8").splitlines(keepends=True)
    replacements = master[master.analysis.eq("official release-fix comparison")].set_index("comparison", drop=False)
    replaced = set()
    for index, line in enumerate(lines[1:], start=1):
        row = next(csv.reader([line]))
        if row[0] == "RQ3.1" and row[1] in {"instruction-change robustness", "official release-fix comparison"}:
            pair = row[2]
            newline = "\r\n" if line.endswith("\r\n") else "\n"
            buffer = io.StringIO()
            replacements.loc[[pair]].to_csv(buffer, index=False, header=False, lineterminator=newline)
            lines[index] = buffer.getvalue()
            replaced.add(pair)
    if replaced != set(EXPECTED):
        raise ValueError("Scoped master update did not find both RQ3.1 grouping rows")
    path.write_bytes("".join(lines).encode("utf-8"))


def paired_summary(differences: pd.Series) -> dict[str, float | int]:
    clean = pd.to_numeric(differences, errors="coerce").dropna()
    statistic, p_value, nonzero = two_sided_signed_rank(clean)
    return {
        "n": int(clean.shape[0]),
        "mean": float(clean.mean()) if not clean.empty else np.nan,
        "median": float(clean.median()) if not clean.empty else np.nan,
        "cohens_dz": paired_cohens_dz(clean),
        "wilcoxon_statistic": statistic,
        "p_value": p_value,
        "nonzero_pairs": nonzero,
    }


def build_media_description(adjacent: pd.DataFrame) -> pd.DataFrame:
    media_tasks = set(read_required(MEDIA_TASKS)["task_name"].astype(str))
    tb2 = adjacent[adjacent["version_pair"].astype(str).eq("2.0->2.1")].copy()
    if tb2["task_name"].nunique() != 89:
        raise ValueError("Media description expected 89 TB2.0/TB2.1 shared tasks.")
    media = tb2[tb2["task_name"].astype(str).isin(media_tasks)]["task_weighted_pass_rate_old"]
    other = tb2[~tb2["task_name"].astype(str).isin(media_tasks)]["task_weighted_pass_rate_old"]
    return pd.DataFrame(
        [
            {
                "analysis_status": "post-hoc exploratory",
                "media_task_count": int(media.shape[0]),
                "other_task_count": int(other.shape[0]),
                "media_mean_task_pass_rate": float(media.mean()),
                "other_mean_task_pass_rate": float(other.mean()),
                "percentage_point_difference": float((media.mean() - other.mean()) * 100.0),
            }
        ]
    )


def build_version_performance(adjacent: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for pair, expected_n in [("2.0->2.1", 89), ("3.0->4.0", 66)]:
        group = adjacent[adjacent["version_pair"].astype(str).eq(pair)].copy()
        group = group.dropna(
            subset=["task_weighted_pass_rate_old", "task_weighted_pass_rate_new"]
        )
        if group["task_name"].nunique() != expected_n or group["task_name"].duplicated().any():
            raise ValueError(f"{pair} expected {expected_n} unique paired tasks.")
        difference_pp = (
            group["task_weighted_pass_rate_new"] - group["task_weighted_pass_rate_old"]
        ) * 100.0
        stats = paired_summary(difference_pp)
        old_rate = float(group["task_weighted_pass_rate_old"].mean())
        new_rate = float(group["task_weighted_pass_rate_new"].mean())
        rows.append(
            {
                "transition": pair,
                "shared_tasks": stats["n"],
                "old_task_balanced_pass_rate": old_rate,
                "new_task_balanced_pass_rate": new_rate,
                "overall_change_pp": (new_rate - old_rate) * 100.0,
                "mean_task_change_pp": stats["mean"],
                "median_task_change_pp": stats["median"],
                "cohens_dz": stats["cohens_dz"],
                "wilcoxon_statistic": stats["wilcoxon_statistic"],
                "p_value": stats["p_value"],
                "nonzero_task_pairs": stats["nonzero_pairs"],
            }
        )
    return pd.DataFrame(rows)


def build_release_comparisons(adjacent: pd.DataFrame, *, pr26_sensitivity: bool = False) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for pair, (expected_changed, expected_unchanged) in EXPECTED.items():
        group = add_release_status(adjacent, pair)
        fixed = group["release_status"].eq("fixed")
        if pr26_sensitivity:
            if pair != "2.0->2.1":
                continue
            fixed = pd.to_numeric(group["listed_in_tb21_pr53"]).eq(1)
            expected_changed, expected_unchanged = 26, 63
        changed = group.loc[fixed, "improvement_pp"]
        unchanged = group.loc[~fixed, "improvement_pp"]
        if len(changed) != expected_changed or len(unchanged) != expected_unchanged:
            raise ValueError(
                f"{pair} classification counts were {len(changed)} changed/{len(unchanged)} unchanged."
            )
        statistic, p_value = two_sided_mann_whitney(changed, unchanged)
        rows.append(
            {
                "transition": pair,
                "classification_basis": "official PR53 26-task sensitivity" if pr26_sensitivity else "official release named fixes",
                "n_changed": int(len(changed)),
                "n_unchanged": int(len(unchanged)),
                "mean_improvement_changed_pp": float(changed.mean()),
                "mean_improvement_unchanged_pp": float(unchanged.mean()),
                "median_improvement_changed_pp": float(changed.median()),
                "median_improvement_unchanged_pp": float(unchanged.median()),
                "raw_difference_in_mean_improvement_pp": float(changed.mean() - unchanged.mean()),
                "cliffs_delta": cliffs_delta(changed, unchanged),
                "mann_whitney_u": statistic,
                "p_value": p_value,
            }
        )
    return pd.DataFrame(rows)


def pooled_effort_lookup(path: Path) -> pd.DataFrame:
    pooled = read_required(path).copy()
    return pooled.set_index("key")


def build_effort_inference() -> pd.DataFrame:
    effort_module = importlib.import_module("scripts.analysis.longitudinal.03_analyze_effort_changes")
    specs = [
        (
            "2.0->2.1",
            TB2_TRAJECTORIES,
            "2.0",
            "2.1",
            LONG_DIR / "pooled_effort_summary_refreshed.csv",
            89,
        ),
        (
            "3.0->4.0",
            TB34_TRAJECTORIES,
            "3.0",
            "4.0",
            LONG_DIR / "tb3_tb4" / "pooled_effort_summary_refreshed.csv",
            66,
        ),
    ]
    primary_metrics = {"steps", "shell_invocations", "tool_calls", "duration", "total_tokens"}
    rows: list[dict[str, Any]] = []
    for transition, source, old_version, new_version, pooled_path, expected_tasks in specs:
        trajectories = effort_module.load_trajectories(source, submission_unit="source")
        pooled = pooled_effort_lookup(pooled_path)
        for metric in effort_module.METRICS:
            key = str(metric["key"])
            if key not in primary_metrics:
                continue
            pairs = effort_module.task_metric_pairs(trajectories, str(metric["column"]), submission_unit="source")
            if old_version not in pairs.columns or new_version not in pairs.columns:
                raise ValueError(f"{transition} {key} is missing a benchmark version.")
            pairs = pairs.dropna(subset=[old_version, new_version])
            if len(pairs) != expected_tasks:
                raise ValueError(f"{transition} {key} expected {expected_tasks} task pairs, found {len(pairs)}.")
            differences = pairs[new_version] - pairs[old_version]
            stats = paired_summary(differences)
            headline = pooled.loc[key]
            rows.append(
                {
                    "transition": transition,
                    "metric": key,
                    "task_weighting": "submission-balanced",
                    "submission_unit": "source",
                    "eligible_tasks": stats["n"],
                    "old_headline_median": float(headline["early_value"]),
                    "new_headline_median": float(headline["late_value"]),
                    "reported_percentage_change": float(headline["relative_change_pct"]),
                    "headline_aggregation": "pooled trajectories; descriptive only",
                    "old_task_balanced_median": float(pairs[old_version].median()),
                    "new_task_balanced_median": float(pairs[new_version].median()),
                    "task_balanced_median_change_pct": float((pairs[new_version].median() / pairs[old_version].median() - 1) * 100),
                    "mean_paired_task_difference": stats["mean"],
                    "median_paired_task_difference": stats["median"],
                    "cohens_dz": stats["cohens_dz"],
                    "wilcoxon_statistic": stats["wilcoxon_statistic"],
                    "p_value": stats["p_value"],
                    "nonzero_task_pairs": stats["nonzero_pairs"],
                }
            )
    return pd.DataFrame(rows)


def task_balanced_config_median(group: pd.DataFrame) -> float:
    group = ensure_source_submission_id(group)
    submission_task = (
        group.dropna(subset=[SOURCE_SUBMISSION_ID, "task_name", "total_tokens"])
        .groupby([SOURCE_SUBMISSION_ID, "task_name"], as_index=False)["total_tokens"]
        .median()
    )
    task_medians = submission_task.groupby("task_name")["total_tokens"].median()
    return float(task_medians.median()) if not task_medians.empty else np.nan


def build_shared_configuration_tokens() -> pd.DataFrame:
    usecols = [
        "benchmark_version",
        "submission_id",
        SOURCE_SUBMISSION_ID,
        "task_name",
        "scaffold",
        "model_dir",
        "total_tokens",
    ]
    df = pd.read_csv(TB34_TRAJECTORIES, usecols=usecols, low_memory=False)
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    df["total_tokens"] = pd.to_numeric(df["total_tokens"], errors="coerce").where(lambda x: x > 0)
    configurations = (
        df.dropna(subset=["total_tokens"])
        .groupby(["scaffold", "model_dir"])["benchmark_version"]
        .agg(lambda values: set(values))
    )
    configurations = configurations[configurations.map(lambda versions: {"3.0", "4.0"}.issubset(versions))]
    rows: list[dict[str, Any]] = []
    for scaffold, model in configurations.index:
        subset = df[df["scaffold"].eq(scaffold) & df["model_dir"].eq(model)].copy()
        task_sets = {
            version: set(
                subset.loc[
                    subset["benchmark_version"].eq(version) & subset["total_tokens"].notna(),
                    "task_name",
                ]
            )
            for version in ["3.0", "4.0"]
        }
        shared_tasks = task_sets["3.0"].intersection(task_sets["4.0"])
        old = task_balanced_config_median(
            subset[subset["benchmark_version"].eq("3.0") & subset["task_name"].isin(shared_tasks)]
        )
        new = task_balanced_config_median(
            subset[subset["benchmark_version"].eq("4.0") & subset["task_name"].isin(shared_tasks)]
        )
        change = (new / old - 1.0) * 100.0
        rows.append(
            {
                "configuration": f"{scaffold} / {model}",
                "task_weighting": "submission-balanced",
                "submission_unit": "source",
                "shared_tasks": len(shared_tasks),
                "old_median_tokens": old,
                "new_median_tokens": new,
                "percentage_change": change,
                "direction": "increase" if change > 0 else "decrease" if change < 0 else "tie",
            }
        )
    return pd.DataFrame(rows).sort_values("configuration").reset_index(drop=True)


def master_row(**kwargs: Any) -> dict[str, Any]:
    columns = [
        "rq", "analysis", "comparison", "metric", "n", "raw_effect", "raw_effect_unit",
        "effect_size_type", "effect_size", "test", "test_statistic", "p_value", "direction",
        "source_file", "task_observation_function",
    ]
    return {column: kwargs.get(column, "") for column in columns}


def build_master(
    rq1: pd.DataFrame,
    rq12: pd.DataFrame,
    rq2difficulty: pd.DataFrame,
    human: pd.DataFrame,
    behavior: pd.DataFrame,
    performance: pd.DataFrame,
    instruction: pd.DataFrame,
    effort: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in rq1.itertuples(index=False):
        rows.append(master_row(
            rq="RQ1.1", analysis="successful vs failed trajectories", comparison="success - failure",
            metric=METRIC_LABELS.get(row.metric, row.metric), n=row.eligible_tasks,
            raw_effect=row.median_task_difference, raw_effect_unit=METRIC_UNITS.get(row.metric, "units"),
            effect_size_type="cohens_dz", effect_size=row.cohens_dz,
            test="two-sided Wilcoxon signed-rank", test_statistic=row.wilcoxon_statistic,
            p_value=row.p_value, direction="positive = higher for successful trajectories",
            source_file="terminal_bench_2_0/trajectory_summary.csv",
            task_observation_function="task_medians",
        ))
    full = read_required(RQ1_FULL).set_index("metric")
    for row in rq12.itertuples(index=False):
        detail = full.loc[row.metric]
        rows.append(master_row(
            rq="RQ1.2", analysis="quadratic conditional logistic regression",
            comparison="H0: beta_2 = 0", metric=METRIC_LABELS.get(row.metric, row.metric),
            n=int(detail["model_task_strata_count"]), raw_effect=row.beta_2,
            raw_effect_unit="standardized quadratic log-effort coefficient",
            effect_size_type="beta_2", effect_size=row.beta_2,
            test="two-sided Wald z test", test_statistic=float(row.beta_2 / detail["se_beta_2"]),
            p_value=row.p_value_beta_2, direction="negative = concave-down conditional relationship",
            source_file="terminal_bench_2_0/trajectory_summary.csv",
            task_observation_function="model_frame + fit_quadratic_conditional_logit",
        ))
    difficulty = rq2difficulty.iloc[0]
    rows.append(master_row(
        rq="RQ2.1", analysis="difficulty vs task pass rate", comparison="ordinal difficulty",
        metric="Task-balanced pass rate", n=int(difficulty["n_tasks"]), raw_effect=difficulty["spearman_rho"],
        raw_effect_unit="rho", effect_size_type="spearman_rho", effect_size=difficulty["spearman_rho"],
        test="two-sided Spearman rank correlation", test_statistic=difficulty["spearman_rho"],
        p_value=difficulty["p_value"], direction="negative = lower pass rate at greater difficulty",
        source_file="longitudinal/trajectory_longitudinal.csv + TB2 task metadata",
        task_observation_function="submission_task_pass_rates",
    ))
    for row in human.itertuples(index=False):
        rows.append(master_row(
            rq="RQ2.2", analysis="agent duration vs human estimate", comparison=f"agent - {row.comparison}",
            metric="Duration", n=row.n_tasks, raw_effect=row.median_difference_min,
            raw_effect_unit="minutes", effect_size_type="cohens_dz", effect_size=row.cohens_dz,
            test="two-sided Wilcoxon signed-rank", test_statistic=row.wilcoxon_statistic,
            p_value=row.p_value, direction="negative = agent duration is shorter",
            source_file="longitudinal/trajectory_longitudinal.csv + terminal_bench_2_task_toml_metadata.csv",
            task_observation_function="build_task_average_duration_comparison",
        ))
    for row in behavior.itertuples(index=False):
        rows.append(master_row(
            rq="RQ2.3", analysis="functional behavior use vs success", comparison="used - not used",
            metric=row.behavior, n=row.eligible_tasks, raw_effect=row.mean_pass_rate_difference_pp,
            raw_effect_unit="percentage points (mean task contrast)", effect_size_type="cohens_dz",
            effect_size=row.cohens_dz, test="two-sided Wilcoxon signed-rank",
            test_statistic=row.wilcoxon_statistic, p_value=row.p_value,
            direction="positive = behavior use associated with higher success",
            source_file="terminal_bench_2_0 trajectories + task metadata",
            task_observation_function="build_task_functional_contrasts",
        ))
    for row in performance.itertuples(index=False):
        rows.append(master_row(
            rq="RQ3.1", analysis="benchmark-version performance", comparison=row.transition,
            metric="Task-balanced pass rate", n=row.shared_tasks, raw_effect=row.overall_change_pp,
            raw_effect_unit="percentage points", effect_size_type="cohens_dz", effect_size=row.cohens_dz,
            test="two-sided Wilcoxon signed-rank", test_statistic=row.wilcoxon_statistic,
            p_value=row.p_value, direction="positive = higher performance in the newer version",
            source_file="longitudinal/task_composition/adjacent_version_task_changes.csv",
            task_observation_function="build_observed_task_duration + build_adjacent_changes",
        ))
    for row in instruction.itertuples(index=False):
        rows.append(master_row(
            rq="RQ3.1", analysis="official release-fix comparison", comparison=row.transition,
            metric="Task pass-rate improvement", n=int(row.n_changed + row.n_unchanged),
            raw_effect=row.raw_difference_in_mean_improvement_pp, raw_effect_unit="percentage points",
            effect_size_type="cliffs_delta", effect_size=row.cliffs_delta,
            test="two-sided Mann-Whitney U", test_statistic=row.mann_whitney_u,
            p_value=row.p_value, direction="positive = release-fixed tasks tended to improve more",
            source_file="adjacent_version_task_changes.csv + official_release_task_crosswalk.csv",
            task_observation_function="build_adjacent_changes; independent release-fixed/not-listed-as-fixed task split",
        ))
    for row in effort.itertuples(index=False):
        rows.append(master_row(
            rq="RQ3.3", analysis="benchmark-version interaction/resource change", comparison=row.transition,
            metric=METRIC_LABELS.get(row.metric, row.metric), n=row.eligible_tasks,
            raw_effect=row.median_paired_task_difference, raw_effect_unit=METRIC_UNITS.get(row.metric, "units"),
            effect_size_type="cohens_dz", effect_size=row.cohens_dz,
            test="two-sided Wilcoxon signed-rank", test_statistic=row.wilcoxon_statistic,
            p_value=row.p_value, direction="positive = metric increased in the newer version",
            source_file=("longitudinal/trajectory_longitudinal.csv" if row.transition == "2.0->2.1"
                         else "longitudinal/tb3_tb4/trajectory_longitudinal.csv"),
            task_observation_function="task_metric_pairs (submission-task median -> task median)",
        ))
    master = pd.DataFrame(rows)
    master["significant_alpha_0_05"] = pd.to_numeric(master["p_value"], errors="coerce").lt(0.05)
    return master


def p_text(value: float) -> str:
    return f"{value:.3g}"


def num(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def validate_results(
    master: pd.DataFrame,
    rq1: pd.DataFrame,
    human: pd.DataFrame,
    behavior: pd.DataFrame,
    performance: pd.DataFrame,
    instruction: pd.DataFrame,
    effort: pd.DataFrame,
) -> None:
    """Fail fast on unit, pairing, and effect-size invariants."""

    def check(name: str, condition: bool, detail: str) -> None:
        if not condition:
            raise AssertionError(f"Validation failed: {name}: {detail}")

    rq1_detail = read_required(DIM_DIR / "rq1_within_task_effort_by_task.csv")
    for row in rq1.itertuples(index=False):
        differences = rq1_detail.loc[
            rq1_detail["metric"].eq(row.metric),
            "within_task_difference_pass_minus_fail",
        ]
        check(
            f"RQ1.1 {row.metric} exact dz vector",
            len(differences) == row.eligible_tasks
            and np.isclose(paired_cohens_dz(differences), row.cohens_dz, equal_nan=True),
            f"{len(differences)} paired task differences",
        )

    duration_tasks = read_required(TASK_DIR / "time_estimates" / "task_average_duration_comparison.csv")
    for row in human.itertuples(index=False):
        estimate = f"{row.comparison}_time_estimate_min"
        pairs = duration_tasks[["median_duration_min", estimate]].dropna()
        differences = pairs["median_duration_min"] - pairs[estimate]
        check(
            f"RQ2.2 {row.comparison} exact dz vector",
            len(pairs) == row.n_tasks
            and np.isclose(paired_cohens_dz(differences), row.cohens_dz, equal_nan=True),
            f"{len(pairs)} paired tasks",
        )

    check("RQ2.3 nine behavior families", len(behavior) == 9, "all requested families present")
    check(
        "RQ2.3 support rule",
        behavior["eligible_tasks"].between(1, 89).all(),
        "eligible cells require >=3 used and >=3 non-used trajectories within task",
    )
    check(
        "RQ3.1 paired task counts",
        performance.set_index("transition")["shared_tasks"].to_dict() == {"2.0->2.1": 89, "3.0->4.0": 66},
        "exactly 89 and 66 shared tasks",
    )
    check(
        "RQ3.1 independent official release groups",
        instruction[["n_changed", "n_unchanged"]].astype(int).values.tolist() == [[28, 61], [19, 47]],
        "release-fixed and not-listed-as-fixed tasks are disjoint and exhaustive; removed tasks excluded",
    )
    check(
        "RQ3.3 metric-wise paired tasks",
        effort.groupby("transition")["eligible_tasks"].agg(["min", "max"]).eq(
            pd.DataFrame({"min": [89, 66], "max": [89, 66]}, index=["2.0->2.1", "3.0->4.0"])
        ).all().all(),
        "missing pairs are removed per metric; all five primary metrics are complete",
    )
    check(
        "Master contains inferential rows only",
        not master["analysis"].str.contains("media|composition|Pareto|configuration", case=False, regex=True).any(),
        f"{len(master)} inferential rows",
    )
    check(
        "P-values bounded",
        pd.to_numeric(master["p_value"], errors="coerce").between(0, 1).all(),
        "all inferential p-values lie in [0,1]",
    )
    check(
        "No confidence intervals in thesis-facing outputs",
        not any("ci" in column.lower() for column in master.columns)
        and not any("ci" in column.lower() for column in rq1.columns),
        "master and compact RQ1.1 tables contain no CI columns",
    )


def build_report(
    master: pd.DataFrame,
    rq1: pd.DataFrame,
    rq12: pd.DataFrame,
    difficulty: pd.DataFrame,
    media: pd.DataFrame,
    human: pd.DataFrame,
    behavior: pd.DataFrame,
    performance: pd.DataFrame,
    instruction: pd.DataFrame,
    effort: pd.DataFrame,
    configs: pd.DataFrame,
) -> str:
    lines = [
        "# Statistical results",
        "",
        "## Analysis methods",
        "",
        "Primary RQ3.1, RQ3.2 and RQ3.3 aggregation uses resolved source_submission_id values, consistently with RQ1. RQ3.3 takes medians within source submission-task pairs, medians across submissions within tasks, then compares paired shared tasks. Leaderboard-URL grouping is retained as an explicit sensitivity analysis. RQ2.1 and RQ2.2 now use the same actual source submission unit; RQ2.3 retains trajectory use/non-use cells with at least three trajectories per cell. Configuration fingerprints are separate from source submission identity. Historical scraped dates are preserved; their submission/publication semantics remain unverified. Only source-submission-balanced RQ3.3 effort figures are retained; pooled trajectory medians remain descriptive diagnostics in CSV tables.",
        "",
        "RQ1.3 remains a descriptive Pareto analysis. The media comparison is post-hoc exploratory. RQ3.2 composition analyses and exact shared-configuration token comparisons remain descriptive. Cost is not a current longitudinal headline metric and its incomplete, configuration-dependent coverage does not support adding a primary RQ3.3 test. No confidence intervals, multiplicity correction, or extra subgroup tests were added.",
        "",
        "For RQ1.1 shell invocations and output tokens, the median task difference and dz have opposite signs. This is not a coding discrepancy: dz follows the mean paired difference by definition, while the requested raw effect is the median paired difference; skewed task differences can make their signs differ.",
        "",
        "## Formulas and implementation",
        "",
        "For paired task differences D, Cohen's dz is mean(D) / sd(D) with sample SD (ddof=1). The two-sided Wilcoxon test uses the same D values, `zero_method='wilcox'`, and reports W=0, p=1 for an all-zero contrast. Cliff's delta is (# changed>unchanged - # changed<unchanged)/(n_changed*n_unchanged), paired with a two-sided Mann-Whitney U test. The RQ1.2 test is H0: beta2=0 versus H1: beta2!=0.",
        "",
        "## Thesis-ready results",
        "",
        "### RQ1.1",
        "",
    ]
    for row in rq1.itertuples(index=False):
        sig = "significant" if row.p_value < 0.05 else "not significant"
        lines.append(f"- {METRIC_LABELS.get(row.metric, row.metric)}: median delta = {num(row.median_task_difference)}, dz = {num(row.cohens_dz)}, W = {num(row.wilcoxon_statistic, 1)}, p = {p_text(row.p_value)} ({sig}; n = {row.eligible_tasks}).")
    lines.extend(["", "### RQ1.2", ""])
    for row in rq12.itertuples(index=False):
        lines.append(f"- {METRIC_LABELS.get(row.metric, row.metric)}: beta1 = {num(row.beta_1)}, beta2 = {num(row.beta_2)}, p(beta2) = {p_text(row.p_value_beta_2)}.")
    d = difficulty.iloc[0]
    lines.extend([
        "", "### RQ2.1", "",
        f"- Difficulty and task pass rate: Spearman rho = {num(d.spearman_rho)}, p = {p_text(d.p_value)}, n = {int(d.n_tasks)} tasks.",
        "", "### RQ2.2", "",
    ])
    m = media.iloc[0]
    lines.append(f"- Post-hoc exploratory media finding: {m.media_task_count} media tasks averaged {100*m.media_mean_task_pass_rate:.1f}% versus {100*m.other_mean_task_pass_rate:.1f}% for {m.other_task_count} other tasks (delta = {m.percentage_point_difference:.1f} pp); no confirmatory test or Cliff's delta is reported.")
    for row in human.itertuples(index=False):
        lines.append(f"- Agent vs {row.comparison}: median agent duration = {row.median_agent_duration_min:.2f} min, median estimate = {row.median_human_estimate_min:.2f} min, median paired delta = {row.median_difference_min:.2f} min, dz = {num(row.cohens_dz)}, W = {num(row.wilcoxon_statistic, 1)}, p = {p_text(row.p_value)} (n = {row.n_tasks}). Success-only median = {row.success_only_median_agent_duration_min:.2f} min; median paired delta = {row.success_only_median_difference_min:.2f} min and median agent/estimate ratio = {row.success_only_median_agent_to_human_ratio:.3f} (descriptive only).")
    lines.extend(["", "### RQ2.3", ""])
    for row in behavior.itertuples(index=False):
        sig = "significant" if row.p_value < 0.05 else "not significant"
        lines.append(f"- {row.behavior}: use rate = {100*row.use_rate:.1f}%, mean/median delta = {row.mean_pass_rate_difference_pp:.2f}/{row.median_pass_rate_difference_pp:.2f} pp, dz = {num(row.cohens_dz)}, W = {num(row.wilcoxon_statistic, 1)}, p = {p_text(row.p_value)} ({sig}; n = {row.eligible_tasks}).")
    lines.extend(["", "### RQ3.1", ""])
    for row in performance.itertuples(index=False):
        lines.append(f"- {row.transition}: {100*row.old_task_balanced_pass_rate:.1f}% -> {100*row.new_task_balanced_pass_rate:.1f}% (delta = {row.overall_change_pp:.2f} pp; mean/median task delta = {row.mean_task_change_pp:.2f}/{row.median_task_change_pp:.2f} pp), dz = {num(row.cohens_dz)}, W = {num(row.wilcoxon_statistic, 1)}, p = {p_text(row.p_value)} (n = {row.shared_tasks}).")
    for row in instruction.itertuples(index=False):
        lines.append(f"- Official release-fix comparison, {row.transition}: release-fixed tasks improved by {row.mean_improvement_changed_pp:.2f} pp on average (median {row.median_improvement_changed_pp:.2f}) versus {row.mean_improvement_unchanged_pp:.2f} pp (median {row.median_improvement_unchanged_pp:.2f}) for tasks not listed as fixed; between-group mean difference = {row.raw_difference_in_mean_improvement_pp:.2f} pp, Cliff's delta = {num(row.cliffs_delta)}, U = {num(row.mann_whitney_u, 1)}, p = {p_text(row.p_value)} (n = {row.n_changed}/{row.n_unchanged}).")
    lines.extend(["", "### RQ3.3", ""])
    for row in effort.itertuples(index=False):
        lines.append(f"- {row.transition}, {METRIC_LABELS.get(row.metric, row.metric)}: source-submission-balanced shared-task medians {row.old_task_balanced_median:.3g} -> {row.new_task_balanced_median:.3g} ({row.task_balanced_median_change_pct:+.1f}% ratio of cross-task medians); mean/median paired task delta = {row.mean_paired_task_difference:.3g}/{row.median_paired_task_difference:.3g}, dz = {num(row.cohens_dz)}, W = {num(row.wilcoxon_statistic, 1)}, p = {p_text(row.p_value)} (n = {row.eligible_tasks}). Refreshed pooled trajectory medians are descriptive only: {row.old_headline_median:.3g} -> {row.new_headline_median:.3g} ({row.reported_percentage_change:+.1f}%).")
    increases = int(configs["percentage_change"].gt(0).sum())
    lines.extend([
        "", "### Shared TB3.0/TB4.0 configurations (descriptive)", "",
    ])
    for row in configs.itertuples(index=False):
        lines.append(f"- {row.configuration}: {row.old_median_tokens:,.0f} -> {row.new_median_tokens:,.0f} tokens ({row.percentage_change:+.1f}%, {row.direction}; {row.shared_tasks} shared tasks).")
    lines.append(f"- Summary: {increases}/{len(configs)} increased; median change {configs.percentage_change.median():+.1f}%, range {configs.percentage_change.min():+.1f}% to {configs.percentage_change.max():+.1f}%; no significance test.")
    lines.extend([
        "", "## Suggested methodology wording", "",
        "Statistical inference used tasks as the unit of analysis after task-balanced aggregation: where submission identifiers were available, trajectories were first summarized within submission-task pairs and then across submissions. Paired task comparisons used two-sided Wilcoxon signed-rank tests with paired Cohen's dz, while comparisons of independent task groups used two-sided Mann-Whitney U tests with Cliff's delta. Ordinal difficulty associations used Spearman's rho, and RQ1.2 retained the quadratic conditional-logistic coefficient beta2 and its two-sided test of H0: beta2=0. Post-hoc media, Pareto, composition, subgroup, diagnostic token, and sparse shared-configuration analyses remained descriptive.",
        "", "## Thesis wording changes", "",
        "No thesis manuscript or Results-section source file is present in the repository, so exact sentence-level edits could not be marked in place. Apply these claim-level replacements:",
        "",
        "- RQ1.1: reserve 'statistically significant' for metrics with p<0.05 in the table above, and always pair it with the signed median difference and dz. Do not infer the task-level direction from pooled success/failure medians where the repository flags a reversal.",
        "- RQ2.3: use 'was associated with' rather than causal language. State that support means three use and three non-use trajectories per task, not three distinct submissions, and do not claim subgroup significance from category/difficulty figures.",
        "- RQ3.1: state improvement using the paired shared-task results. Use official release-fixed versus not-listed-as-fixed task groups and the between-group Mann-Whitney/Cliff comparison. TB2.1 uses the 28 enumerated release IDs; the README/PR count of 26 differs by crack-7z-hash and gpt2-codegolf. TB4.0 calibrates resources for all retained tasks, so the 47 tasks not listed as fixed are not wholly unchanged. Separate within-group p-values do not test the between-group contrast.",
        "- RQ3.3: use source-submission-balanced shared-task medians for the main figures and text. Distinguish ratios of cross-task medians from the paired absolute differences used for inference. Describe increases/decreases as statistically supported only where the paired Wilcoxon p-value is below 0.05, and include dz.",
        "- Cost: do not add a longitudinal cost test. Cost is not a current headline RQ3.3 metric; positive-cost coverage is 25,840/38,604 (66.9%) for TB2.0/TB2.1 and 7,362/10,239 (71.9%) for TB3.0/TB4.0, and coverage is configuration-dependent, so comparability is inadequate for the requested primary analysis.",
        "", "## Master inferential table", "",
        f"The machine-readable table contains {len(master)} inferential rows. Descriptive-only analyses are deliberately excluded.",
        "",
        "| RQ | Analysis | Comparison | Metric | n | Raw effect | Effect size | Test statistic | p | Direction |",
        "| --- | --- | --- | --- | --: | --: | ---: | --: | --: | --- |",
    ])
    for row in master.itertuples(index=False):
        lines.append(
            f"| {row.rq} | {row.analysis} | {row.comparison} | {row.metric} | {int(row.n)} | "
            f"{float(row.raw_effect):.4g} {row.raw_effect_unit} | {row.effect_size_type}={float(row.effect_size):.4g} | "
            f"{float(row.test_statistic):.4g} | {float(row.p_value):.4g} | {row.direction} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()

    def output_path(path: Path) -> Path:
        if args.output_root is not None and path.is_relative_to(REPO_ROOT):
            return args.output_root.resolve() / path.relative_to(REPO_ROOT)
        return path

    if args.output_root is not None and args.output_root.resolve().is_relative_to(REPO_ROOT / "data" / "trajectories"):
        raise ValueError("Output root must be outside raw trajectories.")
    args.out = output_path(args.out)
    args.report = output_path(args.report)
    args.out.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    task_output = output_path(TASK_DIR)
    long_output = output_path(LONG_DIR)
    task_output.mkdir(parents=True, exist_ok=True)
    long_output.mkdir(parents=True, exist_ok=True)

    rq1 = read_required(RQ1_1)
    rq12 = read_required(RQ1_2)
    difficulty = read_required(RQ2_1)
    human = read_required(RQ2_2_HUMAN)
    behavior = read_required(RQ2_3)
    adjacent = read_required(ADJACENT_CHANGES)

    media = build_media_description(adjacent)
    performance = build_version_performance(adjacent)
    instruction = build_release_comparisons(adjacent)
    effort = read_required(LONG_DIR / "rq3_3_effort_inference.csv") if args.rq3_1_only else build_effort_inference()
    configurations = read_required(LONG_DIR / "rq3_3_shared_configuration_tokens_tb3_tb4.csv") if args.rq3_1_only else build_shared_configuration_tokens()
    master = build_master(rq1, rq12, difficulty, human, behavior, performance, instruction, effort)
    validate_results(master, rq1, human, behavior, performance, instruction, effort)

    instruction.to_csv(long_output / "rq3_1_official_release_change_inference.csv", index=False)
    build_release_comparisons(adjacent, pr26_sensitivity=True).to_csv(
        long_output / "rq3_1_official_release_pr26_sensitivity.csv", index=False)
    if not args.rq3_1_only:
        media.to_csv(task_output / "rq2_2_media_exploratory.csv", index=False)
        performance.to_csv(long_output / "rq3_1_version_performance_inference.csv", index=False)
        effort.to_csv(long_output / "rq3_3_effort_inference.csv", index=False)
        configurations.to_csv(long_output / "rq3_3_shared_configuration_tokens_tb3_tb4.csv", index=False)
    if args.rq3_1_only:
        write_scoped_master(args.out / "master_inferential_results.csv", master)
    else:
        master.to_csv(args.out / "master_inferential_results.csv", index=False)
    args.report.write_text(
        build_report(
            master, rq1, rq12, difficulty, media, human, behavior,
            performance, instruction, effort, configurations,
        ),
        encoding="utf-8",
    )

    display_columns = [
        "rq", "analysis", "comparison", "metric", "n", "raw_effect",
        "effect_size_type", "effect_size", "test_statistic", "p_value",
    ]
    print(master[display_columns].to_string(index=False))
    print(f"\nWrote {args.out / 'master_inferential_results.csv'}")
    print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
