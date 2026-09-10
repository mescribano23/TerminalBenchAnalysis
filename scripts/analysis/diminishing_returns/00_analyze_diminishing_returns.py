#!/usr/bin/env python3
"""Final RQ1 effort-success statistics.

Task-balanced pass/fail contrasts use effective submission-task aggregation
before task-level medians, while pooled trajectory medians and
task-conditioned logistic models remain trajectory-level analyses.

Paper-facing output:
- data/processed_live/diminishing_returns/rq1_final_statistical_results.csv
- data/processed_live/diminishing_returns/rq1_within_task_effort_summary.csv
- data/processed_live/diminishing_returns/rq1_within_task_effort_by_task.csv
- data/processed_live/diminishing_returns/rq1_task_outcome_eligibility_thresholds.csv
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import norm, wilcoxon

from scripts.benchmark_paths import find_repo_root
from scripts.analysis.submission_task_balancing import EFFECTIVE_SUBMISSION_ID, ensure_effective_submission_id


REPO_ROOT = find_repo_root(Path(__file__).resolve().parent)
INPUT_DEFAULT = REPO_ROOT / "data" / "processed_live" / "terminal_bench_2_0" / "trajectory_summary.csv"
OUT_DEFAULT = REPO_ROOT / "data" / "processed_live" / "diminishing_returns"

MIN_OUTCOME_SUBMISSIONS = 3
METRICS = [
    "step_count",
    "shell_invocation_count",
    "tool_call_count",
    "total_tokens",
    "duration_seconds",
    "cost_usd_positive",
]
WITHIN_TASK_METRICS = [
    "step_count",
    "shell_invocation_count",
    "tool_call_count",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "duration_seconds",
    "cost_usd_positive",
]
DISPLAY_NAMES = {
    "step_count": "Step count",
    "shell_invocation_count": "Shell invocation count",
    "tool_call_count": "Structured tool call count",
    "prompt_tokens": "Prompt/input tokens",
    "completion_tokens": "Completion/output tokens",
    "total_tokens": "Total tokens",
    "duration_seconds": "Duration seconds",
    "cost_usd_positive": "Positive reported cost USD",
}
CLUSTER_COLUMNS = ["scaffold", "model_dir", "agent_version", "leaderboard_model"]
DIMINISHING_RETURNS_CURVE_SUPPORT = {"step_count", "duration_seconds"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    return parser.parse_args()


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df["reward"] = pd.to_numeric(df["reward"], errors="coerce")
    df = df[df["reward"].isin([0, 1])].copy()
    df["passed"] = df["reward"].astype(int)

    for column in [
        "step_count",
        "shell_invocation_count",
        "tool_call_count",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "duration_seconds",
        "cost_usd",
    ]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["total_tokens"] = df["total_tokens"].where(df["total_tokens"] > 0)
    df["cost_usd_positive"] = df["cost_usd"].where(df["cost_usd"] > 0)

    for column in CLUSTER_COLUMNS:
        if column in df.columns:
            df[column] = df[column].fillna("unknown").astype(str)
    return ensure_effective_submission_id(df)


def direction(pass_median: float, fail_median: float) -> str:
    if pass_median > fail_median:
        return "pass_higher"
    if fail_median > pass_median:
        return "fail_higher"
    return "tie"


def signed_rank(values: pd.Series) -> tuple[float, float]:
    diffs = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if len(diffs) == 0:
        return np.nan, np.nan
    if np.all(diffs == 0):
        return 0.0, 1.0
    result = wilcoxon(diffs, alternative="two-sided", zero_method="wilcox", method="auto")
    return float(result.statistic), float(result.pvalue)


def task_medians(df: pd.DataFrame, metric: str) -> tuple[pd.DataFrame, int, float, float, str]:
    work = df[["task_name", "passed", metric]].dropna().copy()
    pooled = work.groupby("passed")[metric].median()
    pooled_success = float(pooled.get(1, np.nan))
    pooled_failure = float(pooled.get(0, np.nan))

    balanced_work = df[[EFFECTIVE_SUBMISSION_ID, "task_name", "passed", metric]].dropna().copy()
    submission_task_outcome = (
        balanced_work.groupby([EFFECTIVE_SUBMISSION_ID, "task_name", "passed"], as_index=False)
        .agg(
            trajectory_count=(metric, "size"),
            submission_task_outcome_median=(metric, "median"),
        )
    )
    grouped = (
        submission_task_outcome.groupby(["task_name", "passed"])
        .agg(
            submission_count=(EFFECTIVE_SUBMISSION_ID, "nunique"),
            trajectory_count=("trajectory_count", "sum"),
            median=("submission_task_outcome_median", "median"),
        )
        .reset_index()
    )
    counts = grouped.pivot(index="task_name", columns="passed", values="submission_count").fillna(0)
    trajectory_counts = grouped.pivot(index="task_name", columns="passed", values="trajectory_count").fillna(0)
    medians = grouped.pivot(index="task_name", columns="passed", values="median")
    per_task = pd.DataFrame(
        {
            "fail_submission_count": counts.get(0, pd.Series(dtype=float)),
            "pass_submission_count": counts.get(1, pd.Series(dtype=float)),
            "fail_trajectory_count": trajectory_counts.get(0, pd.Series(dtype=float)),
            "pass_trajectory_count": trajectory_counts.get(1, pd.Series(dtype=float)),
            "fail_median": medians.get(0, pd.Series(dtype=float)),
            "pass_median": medians.get(1, pd.Series(dtype=float)),
        }
    ).reset_index()
    per_task = per_task[
        (per_task["pass_submission_count"] >= MIN_OUTCOME_SUBMISSIONS)
        & (per_task["fail_submission_count"] >= MIN_OUTCOME_SUBMISSIONS)
    ].copy()
    per_task["difference"] = per_task["pass_median"] - per_task["fail_median"]
    per_task["within_task_direction"] = np.select(
        [
            per_task["pass_median"] > per_task["fail_median"],
            per_task["fail_median"] > per_task["pass_median"],
        ],
        ["pass_higher", "fail_higher"],
        default="tie",
    )
    return per_task, int(len(work)), pooled_success, pooled_failure, direction(pooled_success, pooled_failure)


def eligibility_threshold_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for metric in WITHIN_TASK_METRICS:
        work = df[[EFFECTIVE_SUBMISSION_ID, "task_name", "passed", metric]].dropna().copy()
        submission_task_outcome = (
            work.groupby([EFFECTIVE_SUBMISSION_ID, "task_name", "passed"], as_index=False)[metric]
            .median()
        )
        counts = (
            submission_task_outcome.groupby(["task_name", "passed"])[EFFECTIVE_SUBMISSION_ID]
            .nunique()
            .reset_index(name="submission_count")
            .pivot(index="task_name", columns="passed", values="submission_count")
            .fillna(0)
        )
        pass_counts = counts.get(1, pd.Series(dtype=float))
        fail_counts = counts.get(0, pd.Series(dtype=float))
        for threshold in [2, 3, 4, 5]:
            rows.append(
                {
                    "metric": metric,
                    "metric_display": DISPLAY_NAMES.get(metric, metric),
                    "min_distinct_submissions_per_outcome": threshold,
                    "eligible_task_count": int(((pass_counts >= threshold) & (fail_counts >= threshold)).sum()),
                }
            )
    return pd.DataFrame(rows)


def within_task_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for metric in METRICS:
        per_task, _, pooled_success, pooled_failure, pooled_direction = task_medians(df, metric)
        eligible = int(len(per_task))
        success_more = int((per_task["difference"] > 0).sum())
        failure_more = int((per_task["difference"] < 0).sum())
        ties = int((per_task["difference"] == 0).sum())
        dominant_direction = (
            "pass_higher" if success_more > failure_more else "fail_higher" if failure_more > success_more else "tie"
        )
        statistic, p_value = signed_rank(per_task["difference"])
        q1 = float(per_task["difference"].quantile(0.25)) if eligible else np.nan
        q3 = float(per_task["difference"].quantile(0.75)) if eligible else np.nan

        rows.append(
            {
                "metric": metric,
                "metric_display": DISPLAY_NAMES.get(metric, metric),
                "pooled_success_median": pooled_success,
                "pooled_failure_median": pooled_failure,
                "pooled_direction": pooled_direction,
                "eligible_tasks": eligible,
                "median_task_pass_median": float(per_task["pass_median"].median()) if eligible else np.nan,
                "median_task_fail_median": float(per_task["fail_median"].median()) if eligible else np.nan,
                "within_task_median_difference": float(per_task["difference"].median()) if eligible else np.nan,
                "within_task_difference_q1": q1,
                "within_task_difference_q3": q3,
                "within_task_difference_iqr": q3 - q1,
                "tasks_success_more_n": success_more,
                "tasks_success_more_pct": success_more / eligible * 100 if eligible else np.nan,
                "tasks_failure_more_n": failure_more,
                "tasks_failure_more_pct": failure_more / eligible * 100 if eligible else np.nan,
                "tie_task_count": ties,
                "direction_reversal": pooled_direction != "tie"
                and dominant_direction != "tie"
                and pooled_direction != dominant_direction,
                "wilcoxon_statistic": statistic,
                "wilcoxon_p": p_value,
            }
        )

    return pd.DataFrame(rows)


def within_task_direction_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for metric in WITHIN_TASK_METRICS:
        per_task, complete_case_count, pooled_success, pooled_failure, pooled_direction = task_medians(df, metric)
        eligible = int(len(per_task))
        agree = int(per_task["within_task_direction"].eq(pooled_direction).sum())
        reverse = int(
            (
                (pooled_direction != "tie")
                & per_task["within_task_direction"].ne("tie")
                & per_task["within_task_direction"].ne(pooled_direction)
            ).sum()
        )
        pass_higher = int(per_task["difference"].gt(0).sum())
        fail_higher = int(per_task["difference"].lt(0).sum())
        ties = int(per_task["difference"].eq(0).sum())
        statistic, p_value = signed_rank(per_task["difference"])
        q1 = float(per_task["difference"].quantile(0.25)) if eligible else np.nan
        q3 = float(per_task["difference"].quantile(0.75)) if eligible else np.nan
        rows.append(
            {
                "metric": metric,
                "metric_display": DISPLAY_NAMES.get(metric, metric),
                "complete_case_count": complete_case_count,
                "pooled_success_median": pooled_success,
                "pooled_failure_median": pooled_failure,
                "pooled_direction": pooled_direction,
                "eligible_task_count": eligible,
                "pass_higher_task_count": pass_higher,
                "fail_higher_task_count": fail_higher,
                "tie_task_count": ties,
                "median_task_pass_median": float(per_task["pass_median"].median()) if eligible else np.nan,
                "median_task_fail_median": float(per_task["fail_median"].median()) if eligible else np.nan,
                "median_within_task_difference_pass_minus_fail": (
                    float(per_task["difference"].median()) if eligible else np.nan
                ),
                "within_task_difference_q1": q1,
                "within_task_difference_q3": q3,
                "within_task_difference_iqr": q3 - q1,
                "wilcoxon_statistic": statistic,
                "wilcoxon_p": p_value,
                "agree_with_pooled_task_count": agree,
                "agree_with_pooled_task_fraction": agree / eligible if eligible else np.nan,
                "reverse_pooled_task_count": reverse,
                "reverse_pooled_task_fraction": reverse / eligible if eligible else np.nan,
            }
        )
    return pd.DataFrame(rows)


def model_frame(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    columns = ["task_name", "passed", metric, *[c for c in CLUSTER_COLUMNS if c in df.columns]]
    work = df[columns].dropna().copy()
    transformed = np.log1p(pd.to_numeric(work[metric], errors="coerce").where(lambda s: s >= 0))
    work = work[np.isfinite(transformed)].copy()
    transformed = transformed.loc[work.index]
    work = work[work.groupby("task_name")["passed"].transform("nunique").eq(2)].copy()
    transformed = transformed.loc[work.index]
    log_effort_mean = float(transformed.mean())
    log_effort_std = float(transformed.std(ddof=0))
    work["log_effort"] = transformed
    work["E"] = (transformed - log_effort_mean) / log_effort_std
    work["E2"] = work["E"] ** 2
    work["cluster"] = work[[c for c in CLUSTER_COLUMNS if c in work.columns]].fillna("unknown").astype(str).agg("|".join, axis=1)
    work.attrs["log_effort_mean"] = log_effort_mean
    work.attrs["log_effort_std"] = log_effort_std
    return work


def conditional_moments(weights: np.ndarray, x: np.ndarray, successes: int) -> tuple[float, np.ndarray, np.ndarray]:
    p = x.shape[1]
    a = np.zeros(successes + 1)
    b = np.zeros((successes + 1, p))
    c = np.zeros((successes + 1, p, p))
    a[0] = 1.0
    log_scale = 0.0

    for index, (weight, row) in enumerate(zip(weights, x), start=1):
        upto = min(index, successes)
        old_a = a[:upto].copy()
        old_b = b[:upto].copy()
        old_c = c[:upto].copy()
        row_outer = np.outer(row, row)
        a[1 : upto + 1] += weight * old_a
        b[1 : upto + 1] += weight * (old_b + old_a[:, None] * row)
        c[1 : upto + 1] += weight * (
            old_c
            + old_b[:, :, None] * row[None, None, :]
            + row[None, :, None] * old_b[:, None, :]
            + old_a[:, None, None] * row_outer
        )
        scale = float(np.nanmax(a))
        if scale > 0 and np.isfinite(scale):
            a /= scale
            b /= scale
            c /= scale
            log_scale += math.log(scale)

    if a[successes] <= 0 or not np.isfinite(a[successes]):
        raise FloatingPointError("Conditional likelihood denominator could not be evaluated.")
    mean = b[successes] / a[successes]
    second = c[successes] / a[successes]
    return math.log(a[successes]) + log_scale, mean, second - np.outer(mean, mean)


def inclusion_probabilities(log_weights: np.ndarray, successes: int) -> np.ndarray:
    n = len(log_weights)
    prefix = np.full((n + 1, successes + 1), -np.inf)
    suffix = np.full((n + 1, successes + 1), -np.inf)
    prefix[0, 0] = 0.0
    suffix[n, 0] = 0.0

    for i, log_weight in enumerate(log_weights):
        prefix[i + 1, :] = prefix[i, :]
        upto = min(i + 1, successes)
        prefix[i + 1, 1 : upto + 1] = np.logaddexp(prefix[i, 1 : upto + 1], log_weight + prefix[i, :upto])

    for i in range(n - 1, -1, -1):
        suffix[i, :] = suffix[i + 1, :]
        upto = min(n - i, successes)
        suffix[i, 1 : upto + 1] = np.logaddexp(
            suffix[i + 1, 1 : upto + 1],
            log_weights[i] + suffix[i + 1, :upto],
        )

    probabilities = np.zeros(n)
    denominator = prefix[n, successes]
    for i, log_weight in enumerate(log_weights):
        terms = [
            prefix[i, left] + suffix[i + 1, successes - 1 - left]
            for left in range(successes)
            if left <= i and successes - 1 - left <= n - i - 1
        ]
        if terms:
            probabilities[i] = math.exp(log_weight + logsumexp(terms) - denominator)
    return np.clip(probabilities, 0.0, 1.0)


def conditional_components(
    beta: np.ndarray,
    groups: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
    score_clusters: bool = False,
) -> tuple[float, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    objective = 0.0
    gradient = np.zeros(len(beta))
    hessian = np.zeros((len(beta), len(beta)))
    cluster_scores: dict[str, np.ndarray] = {}

    for x, y, clusters in groups:
        successes = int(y.sum())
        eta = x @ beta
        shifted_eta = eta - float(np.max(eta))
        log_denominator, expected, covariance = conditional_moments(np.exp(shifted_eta), x, successes)
        objective -= float(shifted_eta[y == 1].sum() - log_denominator)
        gradient += expected - x[y == 1].sum(axis=0)
        hessian += covariance

        if score_clusters:
            probabilities = inclusion_probabilities(shifted_eta, successes)
            for cluster, score in zip(clusters, (y - probabilities)[:, None] * x):
                cluster_scores.setdefault(str(cluster), np.zeros(len(beta)))
                cluster_scores[str(cluster)] += score

    return objective, gradient, hessian, cluster_scores


def fit_quadratic_conditional_logit(work: pd.DataFrame) -> dict[str, Any]:
    groups = [
        (
            group[["E", "E2"]].to_numpy(dtype=float),
            group["passed"].to_numpy(dtype=int),
            group["cluster"].to_numpy(dtype=str),
        )
        for _, group in work.groupby("task_name", sort=False)
    ]
    beta = np.zeros(2)
    converged = False
    line_search_failed = False
    final_gradient_norm = np.nan
    iteration_count = 0

    for iteration in range(1, 61):
        iteration_count = iteration
        value, gradient, hessian, _ = conditional_components(beta, groups)
        final_gradient_norm = float(np.linalg.norm(gradient, ord=np.inf))
        if final_gradient_norm < 1e-6:
            converged = True
            break
        step = -np.linalg.pinv(hessian) @ gradient
        if np.linalg.norm(step) > 2.0:
            step *= 2.0 / np.linalg.norm(step)
        slope = float(gradient @ step)
        for power in range(30):
            candidate = beta + (0.5**power) * step
            try:
                candidate_value, _, _, _ = conditional_components(candidate, groups)
            except FloatingPointError:
                candidate_value = np.inf
            if np.isfinite(candidate_value) and candidate_value <= value + 1e-4 * (0.5**power) * slope:
                beta = candidate
                break
        else:
            line_search_failed = True
            raise RuntimeError("Conditional logit failed to find a stable Newton step.")

    _, gradient, hessian, cluster_scores = conditional_components(beta, groups, score_clusters=True)
    final_gradient_norm = float(np.linalg.norm(gradient, ord=np.inf))
    bread = np.linalg.pinv(hessian)
    scores = np.vstack(list(cluster_scores.values()))
    correction = (scores.shape[0] / (scores.shape[0] - 1)) * ((len(work) - 1) / (len(work) - 2))
    covariance = bread @ (correction * scores.T @ scores) @ bread
    se = np.sqrt(np.diag(covariance))
    finite_beta = bool(np.isfinite(beta).all())
    finite_covariance = bool(np.isfinite(covariance).all())
    finite_se = bool(np.isfinite(se).all())
    p_values = 2 * norm.sf(np.abs(beta / se))
    ci_low = beta - 1.96 * se
    ci_high = beta + 1.96 * se
    z_min = float(work["E"].min())
    z_max = float(work["E"].max())
    turning_point_z = float(-beta[0] / (2 * beta[1])) if beta[1] != 0 else np.nan
    turning_point_in_support = bool(np.isfinite(turning_point_z) and z_min <= turning_point_z <= z_max)
    if np.isfinite(turning_point_z):
        turning_point_percentile = float((work["E"] <= turning_point_z).mean() * 100)
        log_effort_mean = float(work.attrs["log_effort_mean"])
        log_effort_std = float(work.attrs["log_effort_std"])
        turning_point_effort = float(np.expm1(turning_point_z * log_effort_std + log_effort_mean))
    else:
        turning_point_percentile = np.nan
        turning_point_effort = np.nan
    return {
        "model_observation_count": int(len(work)),
        "model_task_strata_count": int(work["task_name"].nunique()),
        "model_cluster_count": int(work["cluster"].nunique()),
        "beta_1_log_effort_z": float(beta[0]),
        "beta_2_log_effort_z_squared": float(beta[1]),
        "se_beta_1": float(se[0]),
        "se_beta_2": float(se[1]),
        "beta_1_ci_low": float(ci_low[0]),
        "beta_1_ci_high": float(ci_high[0]),
        "beta_2_ci_low": float(ci_low[1]),
        "beta_2_ci_high": float(ci_high[1]),
        "beta_1_p": float(p_values[0]),
        "beta_2_p": float(p_values[1]),
        "quadratic_coefficient": float(beta[1]),
        "quadratic_p": float(p_values[1]),
        "turning_point_z": turning_point_z,
        "turning_point_in_empirical_support": turning_point_in_support,
        "turning_point_empirical_percentile": turning_point_percentile,
        "turning_point_effort_value": turning_point_effort,
        "turning_point_interpretable": bool(beta[1] < 0 and turning_point_in_support),
        "z_min": z_min,
        "z_max": z_max,
        "quadratic_converged": converged,
        "quadratic_iteration_count": iteration_count,
        "quadratic_final_gradient_norm": final_gradient_norm,
        "quadratic_finite_coefficients": finite_beta,
        "quadratic_finite_covariance": finite_covariance,
        "quadratic_finite_se": finite_se,
        "quadratic_line_search_failed": line_search_failed,
    }


def quadratic_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric in METRICS:
        rows.append({"metric": metric, **fit_quadratic_conditional_logit(model_frame(df, metric))})
    return pd.DataFrame(rows)


def final_results(df: pd.DataFrame) -> pd.DataFrame:
    result = within_task_rows(df).merge(quadratic_rows(df), on="metric", validate="one_to_one")
    result["wilcoxon_significant"] = result["wilcoxon_p"] < 0.05
    result["quadratic_significant"] = result["quadratic_p"] < 0.05
    result["diminishing_returns_supported"] = (
        result["metric"].isin(DIMINISHING_RETURNS_CURVE_SUPPORT)
        & (result["quadratic_coefficient"] < 0)
        & result["quadratic_significant"]
    )
    return result[
        [
            "metric",
            "metric_display",
            "pooled_success_median",
            "pooled_failure_median",
            "pooled_direction",
            "eligible_tasks",
            "median_task_pass_median",
            "median_task_fail_median",
            "within_task_median_difference",
            "within_task_difference_q1",
            "within_task_difference_q3",
            "within_task_difference_iqr",
            "tasks_success_more_n",
            "tasks_success_more_pct",
            "tasks_failure_more_n",
            "tasks_failure_more_pct",
            "tie_task_count",
            "direction_reversal",
            "wilcoxon_statistic",
            "wilcoxon_p",
            "wilcoxon_significant",
            "model_observation_count",
            "model_task_strata_count",
            "model_cluster_count",
            "beta_1_log_effort_z",
            "beta_2_log_effort_z_squared",
            "se_beta_1",
            "se_beta_2",
            "beta_1_ci_low",
            "beta_1_ci_high",
            "beta_2_ci_low",
            "beta_2_ci_high",
            "beta_1_p",
            "beta_2_p",
            "quadratic_coefficient",
            "quadratic_p",
            "quadratic_significant",
            "turning_point_z",
            "turning_point_in_empirical_support",
            "turning_point_empirical_percentile",
            "turning_point_effort_value",
            "turning_point_interpretable",
            "z_min",
            "z_max",
            "quadratic_converged",
            "quadratic_iteration_count",
            "quadratic_final_gradient_norm",
            "quadratic_finite_coefficients",
            "quadratic_finite_covariance",
            "quadratic_finite_se",
            "quadratic_line_search_failed",
            "diminishing_returns_supported",
        ]
    ]


def within_task_detail_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for metric in WITHIN_TASK_METRICS:
        per_task, _, _, _, pooled_direction = task_medians(df, metric)
        if per_task.empty:
            continue
        per_task["within_task_difference_pass_minus_fail"] = per_task.pop("difference")
        per_task["agrees_with_pooled_direction"] = per_task["within_task_direction"].eq(pooled_direction)
        per_task["reverses_pooled_direction"] = (
            pooled_direction != "tie"
        ) & per_task["within_task_direction"].ne("tie") & per_task["within_task_direction"].ne(pooled_direction)
        per_task.insert(0, "metric", metric)
        per_task.insert(1, "metric_display", DISPLAY_NAMES.get(metric, metric))
        rows.extend(per_task.to_dict(orient="records"))
    return pd.DataFrame(rows)


def metric_list(series: pd.Series) -> str:
    values = series.astype(str).tolist()
    return ", ".join(values) if values else "none"


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    df = load_data(args.input)
    within_summary = within_task_direction_summary(df)
    within_detail = within_task_detail_rows(df)
    eligibility = eligibility_threshold_rows(df)
    table = final_results(df)
    output_path = args.out / "rq1_final_statistical_results.csv"
    within_summary_path = args.out / "rq1_within_task_effort_summary.csv"
    within_detail_path = args.out / "rq1_within_task_effort_by_task.csv"
    eligibility_path = args.out / "rq1_task_outcome_eligibility_thresholds.csv"
    table.to_csv(output_path, index=False)
    within_summary.to_csv(within_summary_path, index=False)
    within_detail.to_csv(within_detail_path, index=False)
    eligibility.to_csv(eligibility_path, index=False)

    reversals = table.loc[table["direction_reversal"], "metric"]
    wilcoxon_sig = table.loc[table["wilcoxon_significant"], "metric"]
    diminishing = table.loc[table["diminishing_returns_supported"], "metric"]
    print(f"Reversal metrics: {metric_list(reversals)}")
    print(f"Significant Wilcoxon metrics: {metric_list(wilcoxon_sig)}")
    print(f"Diminishing-returns metrics: {metric_list(diminishing)}")
    print(f"Wrote {output_path}")
    print(f"Wrote {within_summary_path}")
    print(f"Wrote {within_detail_path}")
    print(f"Wrote {eligibility_path}")


if __name__ == "__main__":
    main()
