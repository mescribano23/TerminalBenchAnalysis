#!/usr/bin/env python3
"""Fit adjusted models for whether 2.1 differences survive task/agent controls.

Success is modeled with a clustered linear probability model. Effort metrics
are modeled with clustered OLS on log1p(metric). This keeps the default run
fast and easy to reproduce while still answering whether the 2.1 indicator
survives task/scaffold/model adjustment.
"""

from __future__ import annotations

import argparse
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
from scipy import linalg

from scripts.benchmark_paths import find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
PROCESSED_DIR = REPO_ROOT / "data" / "processed_live"
LONGITUDINAL_DIR = PROCESSED_DIR / "longitudinal"

EFFORT_METRICS = ["step_count", "command_count", "tool_call_count", "total_tokens", "duration_seconds"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=LONGITUDINAL_DIR / "trajectory_longitudinal.csv")
    parser.add_argument("--out", type=Path, default=LONGITUDINAL_DIR / "adjusted_models")
    return parser.parse_args()


def independent_columns(X: pd.DataFrame) -> tuple[list[str], list[str], int]:
    values = np.asarray(X, dtype=float)
    if values.size == 0:
        return [], list(X.columns), 0
    q, r, piv = linalg.qr(values, mode="economic", pivoting=True)
    if r.size == 0:
        rank = 0
    else:
        tol = np.finfo(float).eps * max(values.shape) * abs(r).max()
        rank = int((np.abs(np.diag(r)) > tol).sum())
    keep_positions = sorted(piv[:rank].tolist())
    kept = X.columns[keep_positions].tolist()
    dropped = [column for column in X.columns if column not in kept]
    return kept, dropped, X.shape[1] - rank


def build_design(formula: str, df: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame, list[str], int]:
    y, X = patsy.dmatrices(formula, df, return_type="dataframe", NA_action="drop")
    kept, dropped, rank_deficiency = independent_columns(X)
    return y.iloc[:, 0], X[kept], dropped, rank_deficiency


def fit_ols(formula: str, df: pd.DataFrame) -> dict[str, Any]:
    try:
        y, X, dropped, rank_deficiency = build_design(formula, df)
        model_df = df.loc[y.index].copy()
        groups = model_df["task_name"].astype(str)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = sm.OLS(y, X)
            result = model.fit(cov_type="cluster", cov_kwds={"groups": groups})
        version_cols = [column for column in result.params.index if column.startswith("C(benchmark")]
        if not version_cols:
            return {
                "estimate": None,
                "std_error": None,
                "p_value": None,
                "ci95_low": None,
                "ci95_high": None,
                "version_column": "",
                "failure": "No benchmark coefficient retained after rank check.",
                "n": int(model_df.shape[0]),
                "n_tasks": int(model_df["task_name"].nunique()),
                "rank_deficiency": rank_deficiency,
                "dropped_columns": "|".join(dropped),
                "warnings": "; ".join(sorted({str(w.message) for w in caught})),
            }
        column = version_cols[0]
        conf = result.conf_int().loc[column]
        estimate = float(result.params[column])
        is_log_response = formula.strip().startswith("log1p_")
        return {
            "estimate": estimate,
            "std_error": float(result.bse[column]),
            "p_value": float(result.pvalues[column]),
            "ci95_low": float(conf.iloc[0]),
            "ci95_high": float(conf.iloc[1]),
            "exponentiated_estimate": math.exp(estimate) if is_log_response else None,
            "exponentiated_ci95_low": math.exp(float(conf.iloc[0])) if is_log_response else None,
            "exponentiated_ci95_high": math.exp(float(conf.iloc[1])) if is_log_response else None,
            "version_column": column,
            "failure": "",
            "n": int(model_df.shape[0]),
            "n_tasks": int(model_df["task_name"].nunique()),
            "rank_deficiency": rank_deficiency,
            "dropped_columns": "|".join(dropped),
            "warnings": "; ".join(sorted({str(w.message) for w in caught})),
        }
    except Exception as exc:
        return {
            "estimate": None,
            "std_error": None,
            "p_value": None,
            "ci95_low": None,
            "ci95_high": None,
            "exponentiated_estimate": None,
            "exponentiated_ci95_low": None,
            "exponentiated_ci95_high": None,
            "version_column": "",
            "failure": f"{type(exc).__name__}: {exc}",
            "n": 0,
            "n_tasks": 0,
            "rank_deficiency": 0,
            "dropped_columns": "",
            "warnings": "",
        }


def prepare_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    required = {"benchmark", "task_name", "scaffold", "model_dir", "agent_key", "passed", *EFFORT_METRICS}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")
    df = df.copy()
    df["benchmark"] = pd.Categorical(df["benchmark"], categories=["terminal_bench_2_0", "terminal_bench_2_1"])
    for column in ["passed", *EFFORT_METRICS]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["scaffold"] = df["scaffold"].fillna("unknown").astype(str)
    df["model_dir"] = df["model_dir"].fillna("unknown").astype(str)
    df["agent_key"] = df["agent_key"].fillna(df["scaffold"] + "::" + df["model_dir"]).astype(str)
    df["task_name"] = df["task_name"].fillna("unknown").astype(str)
    df["category"] = df["category"].fillna("unknown").astype(str)
    df["difficulty"] = df["difficulty"].fillna("unknown").astype(str)
    return df


def model_specs(response: str) -> list[tuple[str, str]]:
    base_response = "passed" if response == "passed" else f"log1p_{response}"
    return [
        ("version_only", f"{base_response} ~ C(benchmark)"),
        ("task_fixed_effects", f"{base_response} ~ C(benchmark) + C(task_name)"),
        ("task_and_scaffold", f"{base_response} ~ C(benchmark) + C(task_name) + C(scaffold)"),
        ("task_scaffold_model", f"{base_response} ~ C(benchmark) + C(task_name) + C(scaffold) + C(model_dir)"),
        ("task_and_agent_key", f"{base_response} ~ C(benchmark) + C(task_name) + C(agent_key)"),
    ]


def fit_all(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    pass_df = df[df["passed"].isin([0.0, 1.0])].copy()
    for spec_name, formula in model_specs("passed"):
        result = fit_ols(formula, pass_df)
        result.update({"outcome": "passed", "model_spec": spec_name, "family": "linear_probability_ols", "formula": formula})
        rows.append(result)

    for metric in EFFORT_METRICS:
        work = df[pd.to_numeric(df[metric], errors="coerce").notna()].copy()
        work[f"log1p_{metric}"] = np.log1p(work[metric].clip(lower=0))
        for spec_name, formula in model_specs(metric):
            result = fit_ols(formula, work)
            result.update({"outcome": metric, "model_spec": spec_name, "family": "ols_log1p", "formula": formula})
            rows.append(result)
    return pd.DataFrame(rows)


def fit_common_agent_subset(df: pd.DataFrame) -> pd.DataFrame:
    support = df.groupby(["benchmark", "agent_key"]).size().reset_index(name="n")
    common_agents = sorted(
        set(support.loc[support["benchmark"].eq("terminal_bench_2_0"), "agent_key"])
        & set(support.loc[support["benchmark"].eq("terminal_bench_2_1"), "agent_key"])
    )
    subset = df[df["agent_key"].isin(common_agents)].copy()
    if subset.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    pass_df = subset[subset["passed"].isin([0.0, 1.0])].copy()
    formula = "passed ~ C(benchmark) + C(task_name) + C(agent_key)"
    result = fit_ols(formula, pass_df)
    result.update({"outcome": "passed", "model_spec": "common_agent_task_fixed_effects", "family": "linear_probability_ols", "formula": formula})
    rows.append(result)
    for metric in EFFORT_METRICS:
        work = subset[pd.to_numeric(subset[metric], errors="coerce").notna()].copy()
        work[f"log1p_{metric}"] = np.log1p(work[metric].clip(lower=0))
        formula = f"log1p_{metric} ~ C(benchmark) + C(task_name) + C(agent_key)"
        result = fit_ols(formula, work)
        result.update({"outcome": metric, "model_spec": "common_agent_task_fixed_effects", "family": "ols_log1p", "formula": formula})
        rows.append(result)
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    df = prepare_data(args.input)
    models = fit_all(df)
    common = fit_common_agent_subset(df)
    models.to_csv(args.out / "adjusted_version_models.csv", index=False)
    common.to_csv(args.out / "common_agent_adjusted_version_models.csv", index=False)

    print(f"Wrote adjusted model tables to {args.out}")


if __name__ == "__main__":
    main()
