#!/usr/bin/env python3
"""RQ1.3 task-balanced configuration efficiency figures.

An agent configuration is a normalized scaffold/model_dir combination. The
analysis uses canonical effective-submission/task aggregation before computing
configuration-level pass rates and effort, so tasks rather than raw trajectory
counts define the main configuration summaries.

Outputs:
- data/processed_live/diminishing_returns/rq1_3_configuration_efficiency.csv
 - reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_token_pareto.png
 - reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_duration_pareto.png
 - reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_steps_pareto.png
 - reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_shell_invocations_pareto.png
 - reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_tool_calls_pareto.png
 - reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_observed_cost_pareto.png
 - reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_token_pareto.png
 - reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_duration_pareto.png
 - reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_steps_pareto.png
 - reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_shell_invocations_pareto.png
 - reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_tool_calls_pareto.png
 - reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_observed_cost_pareto.png
"""

from __future__ import annotations

import argparse
import itertools
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

from scripts.benchmark_paths import find_repo_root
from scripts.analysis.plot_style import OTHER_COLOR, PRINT_DPI, colorblind_cycle
from scripts.analysis.submission_task_balancing import EFFECTIVE_SUBMISSION_ID, ensure_effective_submission_id


REPO_ROOT = find_repo_root(Path(__file__).resolve().parent)
INPUT_DEFAULT = REPO_ROOT / "data" / "processed_live" / "terminal_bench_2_0" / "trajectory_summary.csv"
OUT_DEFAULT = REPO_ROOT / "data" / "processed_live" / "diminishing_returns"
FIGURES_DEFAULT = REPO_ROOT / "reports" / "diminishing_returns"

TOTAL_TASKS = 89
MIN_CONFIG_TASKS = 80
MIN_CONFIG_TRAJECTORIES = 300
MIN_SHARED_TASKS = 50
MAX_MODEL_PARETO_MODELS = 17
SIMILAR_PASS_RATE_PP = 5.0

CONFIG_COLUMNS = ["scaffold", "model_dir"]
SUBMISSION_COLUMNS = ["scaffold", "agent_version", "leaderboard_model", "leaderboard_provider", "leaderboard_date"]
EFFORT_METRICS = [
    "total_tokens",
    "duration_seconds",
    "step_count",
    "shell_invocation_count",
    "tool_call_count",
    "cost_usd_positive",
]

PARETO_METRICS = [
    {
        "name": "token",
        "metric": "total_tokens",
        "effort_col": "task_balanced_median_total_tokens",
        "task_count_col": "total_tokens_task_count",
        "status_col": "token_pareto",
        "figure_name": "rq1_3_configuration_token_pareto.png",
        "scaffold_figure_name": "rq1_3_by_scaffold_configuration_token_pareto.png",
        "model_figure_name": "rq1_3_by_model_configuration_token_pareto.png",
        "xlabel": "Task-balanced median total tokens",
        "title": "RQ1.3 configuration efficiency: token Pareto frontier",
        "formatter": "count",
        "label_domination": True,
    },
    {
        "name": "duration",
        "metric": "duration_seconds",
        "effort_col": "task_balanced_median_duration_seconds",
        "task_count_col": "duration_seconds_task_count",
        "status_col": "duration_pareto",
        "figure_name": "rq1_3_configuration_duration_pareto.png",
        "scaffold_figure_name": "rq1_3_by_scaffold_configuration_duration_pareto.png",
        "model_figure_name": "rq1_3_by_model_configuration_duration_pareto.png",
        "xlabel": "Task-balanced median duration",
        "title": "RQ1.3 configuration efficiency: duration Pareto frontier",
        "formatter": "duration",
        "label_domination": True,
    },
    {
        "name": "steps",
        "metric": "step_count",
        "effort_col": "task_balanced_median_step_count",
        "task_count_col": "step_count_task_count",
        "status_col": "steps_pareto",
        "figure_name": "rq1_3_configuration_steps_pareto.png",
        "scaffold_figure_name": "rq1_3_by_scaffold_configuration_steps_pareto.png",
        "model_figure_name": "rq1_3_by_model_configuration_steps_pareto.png",
        "xlabel": "Task-balanced median steps",
        "title": "RQ1.3 configuration efficiency: step-count Pareto frontier",
        "formatter": "count",
        "label_domination": False,
    },
    {
        "name": "shell invocations",
        "metric": "shell_invocation_count",
        "effort_col": "task_balanced_median_shell_invocation_count",
        "task_count_col": "shell_invocation_count_task_count",
        "status_col": "shell_invocations_pareto",
        "figure_name": "rq1_3_configuration_shell_invocations_pareto.png",
        "scaffold_figure_name": "rq1_3_by_scaffold_configuration_shell_invocations_pareto.png",
        "model_figure_name": "rq1_3_by_model_configuration_shell_invocations_pareto.png",
        "xlabel": "Task-balanced median shell invocations",
        "title": "RQ1.3 configuration efficiency: shell-invocation Pareto frontier",
        "formatter": "count",
        "label_domination": False,
    },
    {
        "name": "tool calls",
        "metric": "tool_call_count",
        "effort_col": "task_balanced_median_tool_call_count",
        "task_count_col": "tool_call_count_task_count",
        "status_col": "tool_calls_pareto",
        "figure_name": "rq1_3_configuration_tool_calls_pareto.png",
        "scaffold_figure_name": "rq1_3_by_scaffold_configuration_tool_calls_pareto.png",
        "model_figure_name": "rq1_3_by_model_configuration_tool_calls_pareto.png",
        "xlabel": "Task-balanced median tool calls",
        "title": "RQ1.3 configuration efficiency: tool-call Pareto frontier",
        "formatter": "count",
        "label_domination": False,
    },
    {
        "name": "observed cost",
        "metric": "cost_usd_positive",
        "effort_col": "task_balanced_median_cost_usd_positive",
        "task_count_col": "cost_usd_positive_task_count",
        "status_col": "observed_cost_pareto",
        "figure_name": "rq1_3_configuration_observed_cost_pareto.png",
        "scaffold_figure_name": "rq1_3_by_scaffold_configuration_observed_cost_pareto.png",
        "model_figure_name": "rq1_3_by_model_configuration_observed_cost_pareto.png",
        "xlabel": "Task-balanced median observed positive cost (USD)",
        "title": "RQ1.3 configuration efficiency: observed-cost Pareto frontier",
        "formatter": "currency",
        "label_domination": False,
    },
]

SCAFFOLD_ORDER = [
    "terminus-2",
    "mini-swe-agent",
    "openhands",
    "claude-code",
    "codex",
    "gemini-cli",
    "terminus-3-3",
    "terminus-kira-env-bootstrap",
    "nexau",
    "deepagent-harbor",
    "hookele",
    "judy",
]

SCAFFOLD_COLORS = dict(zip(SCAFFOLD_ORDER, colorblind_cycle(len(SCAFFOLD_ORDER))))
MODEL_COLORS = colorblind_cycle(24)
OTHER_MODEL_COLOR = OTHER_COLOR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DEFAULT)
    parser.add_argument("--min-config-tasks", type=int, default=MIN_CONFIG_TASKS)
    parser.add_argument("--min-config-trajectories", type=int, default=MIN_CONFIG_TRAJECTORIES)
    parser.add_argument("--min-shared-tasks", type=int, default=MIN_SHARED_TASKS)
    parser.add_argument("--max-model-pareto-models", type=int, default=MAX_MODEL_PARETO_MODELS)
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


def scaffold_label(scaffold: str) -> str:
    labels = {
        "mini-swe-agent": "mini-swe-agent",
        "terminus-kira-env-bootstrap": "Terminus Kira",
        "terminus-3-3": "Terminus 3.3",
        "terminus-2": "Terminus 2",
        "gemini-cli": "Gemini CLI",
        "claude-code": "Claude Code",
        "deepagent-harbor": "DeepAgent Harbor",
        "openhands": "OpenHands",
        "codex": "Codex",
        "hookele": "Hookele",
        "nexau": "Nexau",
        "judy": "Judy",
    }
    return labels.get(scaffold, scaffold)


def scaffold_short_label(scaffold: str) -> str:
    labels = {
        "mini-swe-agent": "MSA",
        "terminus-kira-env-bootstrap": "Kira",
        "terminus-3-3": "T3.3",
        "terminus-2": "T2",
        "gemini-cli": "Gemini CLI",
        "claude-code": "Claude Code",
        "deepagent-harbor": "DeepAgent",
        "openhands": "OpenHands",
        "codex": "Codex",
        "hookele": "Hookele",
        "nexau": "Nexau",
        "judy": "Judy",
    }
    return labels.get(scaffold, scaffold)


def model_label(model: str) -> str:
    labels = {
        "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
        "claude-opus-4-1-20250805": "Claude Opus 4.1",
        "claude-opus-4-5-20251101": "Claude Opus 4.5",
        "claude-opus-4-6": "Claude Opus 4.6",
        "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
        "gemini-2.5-flash": "Gemini 2.5 Flash",
        "gemini-2.5-pro": "Gemini 2.5 Pro",
        "gemini-3-pro-preview": "Gemini 3 Pro",
        "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
        "gpt-5": "GPT-5",
        "gpt-5-codex": "GPT-5 Codex",
        "gpt-5-mini": "GPT-5 Mini",
        "gpt-5-nano": "GPT-5 Nano",
        "gpt-5.1-codex-mini": "GPT-5.1 Codex Mini",
        "gpt-5.2-codex": "GPT-5.2 Codex",
        "gpt-5.5": "GPT-5.5",
        "grok-code-fast-1": "Grok Code Fast 1",
        "openai_gpt-oss-120b": "GPT-OSS 120B",
        "openai_gpt-oss-20b": "GPT-OSS 20B",
    }
    return labels.get(model, model.replace("_", "/"))


def config_plot_label(row: Any) -> str:
    labels = {
        "claude-haiku-4-5-20251001": "Haiku 4.5",
        "claude-opus-4-6": "Opus 4.6",
        "gemini-2.5-flash": "Gemini 2.5 Flash",
        "gemini-2.5-pro": "Gemini 2.5 Pro",
        "gemini-3-pro-preview": "Gemini 3",
        "gemini-3.1-pro-preview": "Gemini 3.1",
        "gpt-5": "GPT-5",
        "gpt-5-mini": "GPT-5 Mini",
        "gpt-5-nano": "GPT-5 Nano",
        "gpt-5.1": "GPT-5.1",
        "gpt-5.1-codex-mini": "GPT-5.1 Mini",
        "gpt-5.2": "GPT-5.2",
        "gpt-5.5": "GPT-5.5",
        "grok-4-0709": "grok-4",
        "openai_gpt-oss-120b": "GPT-OSS 120B",
        "openai_gpt-oss-20b": "GPT-OSS 20B",
    }
    model = labels.get(str(row.model_dir), model_label(str(row.model_dir)))
    return f"{model}\n{scaffold_short_label(str(row.scaffold))}"


def config_label(row: Any) -> str:
    return f"{model_label(str(row.model_dir))} / {scaffold_label(str(row.scaffold))}"


def compact_count(value: float) -> str:
    if pd.isna(value):
        return "NA"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2g}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f}k"
    return f"{value:.0f}"


def compact_duration(value: float) -> str:
    if pd.isna(value):
        return "NA"
    if value >= 60:
        return f"{value / 60:.1f}m"
    return f"{value:.0f}s"


def fmt_pct(value: float) -> str:
    return "NA" if pd.isna(value) else f"{value:.1f}%"


def fmt_pp(value: float) -> str:
    return "NA" if pd.isna(value) else f"{value:+.1f} pp"


def fmt_ratio(value: float) -> str:
    return "NA" if pd.isna(value) else f"{value:.2f}x"


def count_tick(value: float, _position: int) -> str:
    if value <= 0 or not np.isfinite(value):
        return ""
    return compact_count(value)


def currency_tick(value: float, _position: int) -> str:
    if value <= 0 or not np.isfinite(value):
        return ""
    if value < 1:
        return f"${value:.2f}"
    return f"${value:g}"


def seconds_tick(value: float, _position: int) -> str:
    if value <= 0 or not np.isfinite(value):
        return ""
    if value >= 60:
        minutes = value / 60
        return f"{minutes:.0f}m" if minutes >= 10 else f"{minutes:.1f}m"
    return f"{value:g}s"


def axis_formatter(kind: str) -> FuncFormatter:
    if kind == "duration":
        return FuncFormatter(seconds_tick)
    if kind == "currency":
        return FuncFormatter(currency_tick)
    return FuncFormatter(count_tick)


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    required = {
        "reward",
        "scaffold",
        "model_dir",
        "agent_version",
        "leaderboard_model",
        "leaderboard_provider",
        "leaderboard_date",
        "leaderboard_model_organization",
        "task_name",
        "step_count",
        "shell_invocation_count",
        "tool_call_count",
        "total_tokens",
        "duration_seconds",
        "cost_usd",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")

    df = df.copy()
    df["passed"] = pd.to_numeric(df["reward"], errors="coerce")
    df = df[df["passed"].isin([0, 1])].copy()
    for column in ["total_tokens", "duration_seconds", "step_count", "shell_invocation_count", "tool_call_count", "cost_usd"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["total_tokens"] = df["total_tokens"].where(df["total_tokens"] > 0)
    df["cost_usd_positive"] = df["cost_usd"].where(df["cost_usd"] > 0)

    for column in [
        "benchmark",
        "scaffold",
        "model_dir",
        "agent_version",
        "leaderboard_model",
        "leaderboard_provider",
        "leaderboard_date",
        "leaderboard_model_organization",
        "task_name",
    ]:
        if column in df.columns:
            df[column] = df[column].fillna("unknown").astype(str)
    if "benchmark" not in df.columns:
        df["benchmark"] = "terminal_bench_2_0"
    df["leaderboard_model_organization"] = df["leaderboard_model_organization"].replace({"Minimax": "MiniMax"})
    return ensure_effective_submission_id(df)


def submission_task_summary(df: pd.DataFrame) -> pd.DataFrame:
    keys = [*CONFIG_COLUMNS, "leaderboard_model_organization", "config_id", EFFECTIVE_SUBMISSION_ID, "task_name"]
    base = (
        df.groupby(keys)
        .agg(trajectory_count=("passed", "size"), pass_rate=("passed", "mean"))
        .reset_index()
    )
    for metric in EFFORT_METRICS:
        metric_frame = (
            df.dropna(subset=[metric])
            .groupby(keys)[metric]
            .median()
            .rename(metric)
            .reset_index()
        )
        base = base.merge(metric_frame, on=keys, how="left")
    return base


def config_task_summary(submission_task: pd.DataFrame) -> pd.DataFrame:
    keys = [*CONFIG_COLUMNS, "leaderboard_model_organization", "config_id", "task_name"]
    base = (
        submission_task.groupby(keys)
        .agg(
            submission_count=(EFFECTIVE_SUBMISSION_ID, "nunique"),
            trajectory_count=("trajectory_count", "sum"),
            pass_rate=("pass_rate", "mean"),
        )
        .reset_index()
    )
    for metric in EFFORT_METRICS:
        metric_frame = (
            submission_task.dropna(subset=[metric])
            .groupby(keys)[metric]
            .median()
            .rename(metric)
            .reset_index()
        )
        base = base.merge(metric_frame, on=keys, how="left")
    return base


def config_summary(config_task: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    base = (
        config_task.groupby([*CONFIG_COLUMNS, "leaderboard_model_organization", "config_id"])
        .agg(
            task_count=("task_name", "nunique"),
            submission_task_count=("submission_count", "sum"),
            trajectory_count=("trajectory_count", "sum"),
            task_balanced_pass_rate=("pass_rate", "mean"),
            median_task_trajectory_count=("trajectory_count", "median"),
        )
        .reset_index()
    )
    submission_counts = (
        df.groupby([*CONFIG_COLUMNS, "config_id"])[EFFECTIVE_SUBMISSION_ID]
        .nunique()
        .rename("submission_count")
        .reset_index()
    )
    base = base.merge(submission_counts, on=[*CONFIG_COLUMNS, "config_id"], how="left")
    for metric in EFFORT_METRICS:
        metric_summary = (
            config_task.dropna(subset=[metric])
            .groupby([*CONFIG_COLUMNS, "config_id"])
            .agg(
                **{
                    f"task_balanced_median_{metric}": (metric, "median"),
                    f"{metric}_task_count": ("task_name", "nunique"),
                }
            )
            .reset_index()
        )
        base = base.merge(metric_summary, on=[*CONFIG_COLUMNS, "config_id"], how="left")
    base["task_balanced_pass_rate_pct"] = 100.0 * base["task_balanced_pass_rate"]
    return base


def support_summary(configs: pd.DataFrame, args: argparse.Namespace) -> dict[str, Any]:
    retained = configs[
        configs["task_count"].ge(args.min_config_tasks)
        & configs["trajectory_count"].ge(args.min_config_trajectories)
    ].copy()
    return {
        "before": int(configs.shape[0]),
        "after": int(retained.shape[0]),
        "threshold": (
            f">= {args.min_config_tasks}/{TOTAL_TASKS} tasks and "
            f">= {args.min_config_trajectories} trajectories"
        ),
        "median_task_coverage_before": float(configs["task_count"].median()),
        "median_task_coverage_after": float(retained["task_count"].median()) if not retained.empty else math.nan,
        "models": int(retained["model_dir"].nunique()),
        "scaffolds": int(retained["scaffold"].nunique()),
    }


def eligible_configs(configs: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    out = configs[
        configs["task_count"].ge(args.min_config_tasks)
        & configs["trajectory_count"].ge(args.min_config_trajectories)
    ].copy()
    if out.empty:
        raise ValueError("No configurations met the support threshold.")
    return out.sort_values(["task_balanced_pass_rate_pct", "trajectory_count"], ascending=[False, False]).reset_index(
        drop=True
    )


def metric_configs(configs: pd.DataFrame, spec: dict[str, Any], args: argparse.Namespace) -> pd.DataFrame:
    effort_col = spec["effort_col"]
    task_count_col = spec["task_count_col"]
    out = configs[
        configs[effort_col].notna()
        & configs[effort_col].gt(0)
        & configs[task_count_col].ge(args.min_config_tasks)
    ].copy()
    return out.reset_index(drop=True)


def add_pareto_status(configs: pd.DataFrame, effort_col: str, status_col: str) -> pd.DataFrame:
    out = configs.copy()
    values = out[["task_balanced_pass_rate_pct", effort_col]].to_numpy(dtype=float)
    pareto = []
    for i, (pass_i, effort_i) in enumerate(values):
        if pd.isna(pass_i) or pd.isna(effort_i):
            pareto.append(False)
            continue
        dominated = False
        for j, (pass_j, effort_j) in enumerate(values):
            if i == j or pd.isna(pass_j) or pd.isna(effort_j):
                continue
            if pass_j >= pass_i and effort_j <= effort_i and (pass_j > pass_i or effort_j < effort_i):
                dominated = True
                break
        pareto.append(not dominated)
    out[status_col] = pareto
    return out


def add_metric_pareto_status(configs: pd.DataFrame, spec: dict[str, Any], args: argparse.Namespace) -> pd.DataFrame:
    out = configs.copy()
    out[spec["status_col"]] = False
    eligible = metric_configs(out, spec, args)
    if eligible.empty:
        return out
    eligible = add_pareto_status(eligible, spec["effort_col"], spec["status_col"])
    frontier_ids = set(eligible.loc[eligible[spec["status_col"]], "config_id"])
    out.loc[out["config_id"].isin(frontier_ids), spec["status_col"]] = True
    return out


def representative_models(configs: pd.DataFrame, max_models: int) -> list[str]:
    if max_models <= 0:
        return []

    selected: list[str] = []

    def add_model(model: str) -> None:
        if model not in selected and len(selected) < max_models:
            selected.append(model)

    for spec in PARETO_METRICS[:2]:
        frontier = pareto_frontier(configs, spec["effort_col"], spec["status_col"])
        for model in frontier["model_dir"]:
            add_model(str(model))

    status_cols = [spec["status_col"] for spec in PARETO_METRICS if spec["status_col"] in configs.columns]
    frontier_configs = configs[configs[status_cols].any(axis=1)].copy()
    model_priority = (
        frontier_configs.groupby("model_dir", as_index=False)
        .agg(frontier_points=("config_id", "size"), best_pass_rate=("task_balanced_pass_rate_pct", "max"))
        .sort_values(["frontier_points", "best_pass_rate"], ascending=False)
    )
    for model in model_priority["model_dir"]:
        add_model(str(model))

    for model in configs.sort_values("task_balanced_pass_rate_pct", ascending=False)["model_dir"]:
        add_model(str(model))

    return selected


def pareto_frontier(configs: pd.DataFrame, effort_col: str, status_col: str) -> pd.DataFrame:
    return configs[configs[status_col]].sort_values([effort_col, "task_balanced_pass_rate_pct"]).reset_index(drop=True)


def marker_sizes(counts: pd.Series) -> np.ndarray:
    root = np.sqrt(counts.to_numpy(dtype=float))
    return 30 + 5.5 * root


def max_min_ratio(a: float, b: float) -> float:
    if pd.isna(a) or pd.isna(b) or min(a, b) <= 0:
        return math.nan
    return max(a, b) / min(a, b)


def strongest_domination_examples(configs: pd.DataFrame, effort_col: str, max_examples: int = 3) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dominated in configs.itertuples(index=False):
        dominated_effort = getattr(dominated, effort_col)
        if pd.isna(dominated_effort) or dominated_effort <= 0:
            continue
        candidates = configs[
            (configs["config_id"].ne(dominated.config_id))
            & configs["task_balanced_pass_rate_pct"].ge(dominated.task_balanced_pass_rate_pct)
            & configs[effort_col].le(dominated_effort)
            & (
                configs["task_balanced_pass_rate_pct"].gt(dominated.task_balanced_pass_rate_pct)
                | configs[effort_col].lt(dominated_effort)
            )
        ].copy()
        if candidates.empty:
            continue
        candidates["effort_ratio"] = dominated_effort / candidates[effort_col]
        candidates["pass_rate_gain_pp"] = (
            candidates["task_balanced_pass_rate_pct"] - dominated.task_balanced_pass_rate_pct
        )
        best = candidates.sort_values(["effort_ratio", "pass_rate_gain_pp"], ascending=False).iloc[0]
        rows.append(
            {
                "dominates_config_id": best["config_id"],
                "dominated_config_id": dominated.config_id,
                "dominates_model": best["model_dir"],
                "dominates_scaffold": best["scaffold"],
                "dominated_model": dominated.model_dir,
                "dominated_scaffold": dominated.scaffold,
                "pass_rate_gain_pp": float(best["pass_rate_gain_pp"]),
                "dominates_pass_rate_pct": float(best["task_balanced_pass_rate_pct"]),
                "dominated_pass_rate_pct": float(dominated.task_balanced_pass_rate_pct),
                "dominates_effort": float(best[effort_col]),
                "dominated_effort": float(dominated_effort),
                "effort_ratio": float(best["effort_ratio"]),
                "effort_reduction_pct": float((1.0 - best[effort_col] / dominated_effort) * 100.0),
            }
        )
    return sorted(rows, key=lambda row: (row["effort_ratio"], row["pass_rate_gain_pp"]), reverse=True)[:max_examples]


def interesting_label_ids(
    configs: pd.DataFrame,
    effort_col: str,
    status_col: str,
    max_labels: int = 4,
    include_domination: bool = True,
) -> set[str]:
    ids: set[str] = set(pareto_frontier(configs, effort_col, status_col)["config_id"])
    if include_domination:
        for example in strongest_domination_examples(configs, effort_col, max_labels):
            ids.add(str(example["dominates_config_id"]))
            ids.add(str(example["dominated_config_id"]))
    return ids


def label_offset(config_id: str, effort_col: str, i: int) -> tuple[int, int]:
    token_offsets = {
        "mini-swe-agent|openai_gpt-oss-20b": (5, -13),
        "mini-swe-agent|openai_gpt-oss-120b": (8, -15),
        "terminus-2|openai_gpt-oss-120b": (-40, 9),
        "terminus-2|grok-4-0709": (5, 8),
        "terminus-2|gpt-5-mini": (8, -16),
        "mini-swe-agent|gpt-5": (-45, 8),
        "terminus-2|gpt-5": (8, -15),
        "terminus-2|minimax-m2.5": (5, 8),
        "terminus-2|gpt-5.1": (-56, -12),
        "terminus-2|gpt-5.2": (5, 10),
        "terminus-2|gemini-3-pro-preview": (-55, 9),
        "terminus-2|claude-opus-4-6": (6, 8),
        "terminus-3-3|gemini-3.1-pro-preview": (8, -13),
        "terminus-kira-env-bootstrap|claude-opus-4-6": (5, 7),
        "claude-code|claude-haiku-4-5-20251001": (6, -14),
        "openhands|claude-haiku-4-5-20251001": (6, -10),
        "openhands|gemini-2.5-flash": (-42, -15),
    }
    duration_offsets = {
        "mini-swe-agent|openai_gpt-oss-20b": (5, 5),
        "codex|gpt-5-nano": (5, -12),
        "mini-swe-agent|openai_gpt-oss-120b": (5, 8),
        "codex|gpt-5-mini": (5, -10),
        "codex|gpt-5": (5, 8),
        "hookele|gpt-5.1-codex-mini": (5, -7),
        "nexau|gpt-5.5": (5, 7),
    }
    if "total_tokens" in effort_col:
        offsets = token_offsets
    elif "duration_seconds" in effort_col:
        offsets = duration_offsets
    else:
        offsets = {}
    return offsets.get(config_id, (5, 6 if i % 2 == 0 else -10))


def plot_pareto(
    configs: pd.DataFrame,
    effort_col: str,
    status_col: str,
    xlabel: str,
    title: str,
    out: Path,
    formatter: str = "count",
    include_domination_labels: bool = True,
) -> None:
    thesis_style()
    fig, ax = plt.subplots(figsize=(8.0, 5.1))
    sizes = marker_sizes(configs["trajectory_count"])
    frontier = pareto_frontier(configs, effort_col, status_col)

    for scaffold in SCAFFOLD_ORDER:
        subset = configs[configs["scaffold"].eq(scaffold)]
        if subset.empty:
            continue
        ax.scatter(
            subset[effort_col],
            subset["task_balanced_pass_rate_pct"],
            s=sizes[subset.index],
            color=SCAFFOLD_COLORS.get(scaffold, "#777777"),
            alpha=0.62,
            edgecolor="white",
            linewidth=0.6,
            label=scaffold_label(scaffold),
        )

    ax.scatter(
        frontier[effort_col],
        frontier["task_balanced_pass_rate_pct"],
        s=marker_sizes(frontier["trajectory_count"]) + 45,
        facecolor="none",
        edgecolor="#222222",
        linewidth=1.3,
        zorder=4,
    )
    ax.plot(frontier[effort_col], frontier["task_balanced_pass_rate_pct"], color="#222222", linewidth=1.0, zorder=3)

    label_ids = interesting_label_ids(
        configs,
        effort_col,
        status_col,
        include_domination=include_domination_labels,
    )
    for i, row in enumerate(configs[configs["config_id"].isin(label_ids)].itertuples(index=False)):
        dx, dy = label_offset(row.config_id, effort_col, i)
        ax.annotate(
            config_plot_label(row),
            (getattr(row, effort_col), row.task_balanced_pass_rate_pct),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=5.9,
            color="#222222",
            zorder=5,
        )

    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(axis_formatter(formatter))
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Task-balanced pass rate (%)")
    ax.set_title(title)
    ax.grid(color="#DADADA", linewidth=0.7, alpha=0.65)
    ax.set_axisbelow(True)
    ax.margins(x=0.08)
    ax.set_ylim(0, min(95, max(88, configs["task_balanced_pass_rate_pct"].max() + 8)))
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.38),
        ncol=4,
        frameon=False,
        columnspacing=1.1,
        handletextpad=0.4,
    )
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=PRINT_DPI, bbox_inches="tight")
    plt.close(fig)


def plot_pareto_by_model(
    configs: pd.DataFrame,
    effort_col: str,
    status_col: str,
    xlabel: str,
    title: str,
    out: Path,
    formatter: str,
    highlighted_models: list[str],
) -> None:
    thesis_style()
    fig, ax = plt.subplots(figsize=(8.0, 5.1))
    sizes = marker_sizes(configs["trajectory_count"])
    frontier = pareto_frontier(configs, effort_col, status_col)
    model_colors = {model: MODEL_COLORS[index % len(MODEL_COLORS)] for index, model in enumerate(highlighted_models)}
    plot_data = configs.copy()
    plot_data["model_group"] = np.where(plot_data["model_dir"].isin(highlighted_models), plot_data["model_dir"], "Other models")

    other = plot_data[plot_data["model_group"].eq("Other models")]
    if not other.empty:
        ax.scatter(
            other[effort_col],
            other["task_balanced_pass_rate_pct"],
            s=sizes[other.index],
            color=OTHER_MODEL_COLOR,
            alpha=0.42,
            edgecolor="white",
            linewidth=0.45,
            label="Other models",
        )

    for model in highlighted_models:
        subset = plot_data[plot_data["model_group"].eq(model)]
        if subset.empty:
            continue
        ax.scatter(
            subset[effort_col],
            subset["task_balanced_pass_rate_pct"],
            s=sizes[subset.index],
            color=model_colors[model],
            alpha=0.72,
            edgecolor="white",
            linewidth=0.6,
            label=model_label(model),
        )

    ax.scatter(
        frontier[effort_col],
        frontier["task_balanced_pass_rate_pct"],
        s=marker_sizes(frontier["trajectory_count"]) + 45,
        facecolor="none",
        edgecolor="#222222",
        linewidth=1.3,
        zorder=4,
    )
    ax.plot(frontier[effort_col], frontier["task_balanced_pass_rate_pct"], color="#222222", linewidth=1.0, zorder=3)

    label_ids = set(frontier["config_id"])
    for i, row in enumerate(configs[configs["config_id"].isin(label_ids)].itertuples(index=False)):
        dx, dy = label_offset(row.config_id, effort_col, i)
        ax.annotate(
            config_plot_label(row),
            (getattr(row, effort_col), row.task_balanced_pass_rate_pct),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=5.9,
            color="#222222",
            zorder=5,
        )

    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(axis_formatter(formatter))
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Task-balanced pass rate (%)")
    ax.set_title(title)
    ax.grid(color="#DADADA", linewidth=0.7, alpha=0.65)
    ax.set_axisbelow(True)
    ax.margins(x=0.08)
    ax.set_ylim(0, min(95, max(88, configs["task_balanced_pass_rate_pct"].max() + 8)))
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.48),
        ncol=4,
        frameon=False,
        columnspacing=1.0,
        handletextpad=0.4,
    )
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=PRINT_DPI, bbox_inches="tight")
    plt.close(fig)


def pairwise_config_metrics(config_task: pd.DataFrame, left_id: str, right_id: str, min_shared_tasks: int) -> dict[str, Any] | None:
    left = config_task[config_task["config_id"].eq(left_id)].copy()
    right = config_task[config_task["config_id"].eq(right_id)].copy()
    shared_tasks = sorted(set(left["task_name"]).intersection(right["task_name"]))
    if len(shared_tasks) < min_shared_tasks:
        return None
    left = left[left["task_name"].isin(shared_tasks)]
    right = right[right["task_name"].isin(shared_tasks)]
    left_row = left.iloc[0]
    right_row = right.iloc[0]
    result: dict[str, Any] = {
        "left_config_id": left_id,
        "right_config_id": right_id,
        "left_scaffold": left_row["scaffold"],
        "right_scaffold": right_row["scaffold"],
        "left_model": left_row["model_dir"],
        "right_model": right_row["model_dir"],
        "shared_tasks": len(shared_tasks),
        "left_pass_rate_pct": 100.0 * float(left["pass_rate"].mean()),
        "right_pass_rate_pct": 100.0 * float(right["pass_rate"].mean()),
    }
    for metric in EFFORT_METRICS:
        result[f"left_{metric}"] = float(left[metric].median()) if left[metric].notna().any() else math.nan
        result[f"right_{metric}"] = float(right[metric].median()) if right[metric].notna().any() else math.nan
    result["pass_rate_diff_pp"] = result["left_pass_rate_pct"] - result["right_pass_rate_pct"]
    result["token_ratio"] = max_min_ratio(result["left_total_tokens"], result["right_total_tokens"])
    result["duration_ratio"] = max_min_ratio(result["left_duration_seconds"], result["right_duration_seconds"])
    return result


def classify_shared_domination(global_example: dict[str, Any], shared: dict[str, Any] | None, effort_metric: str) -> str:
    if shared is None:
        return "insufficient shared tasks"
    left_is_dominator = shared["left_config_id"] == global_example["dominates_config_id"]
    dom_prefix = "left" if left_is_dominator else "right"
    dominated_prefix = "right" if left_is_dominator else "left"
    dom_pass = shared[f"{dom_prefix}_pass_rate_pct"]
    dominated_pass = shared[f"{dominated_prefix}_pass_rate_pct"]
    dom_effort = shared[f"{dom_prefix}_{effort_metric}"]
    dominated_effort = shared[f"{dominated_prefix}_{effort_metric}"]
    if (
        not pd.isna(dom_pass)
        and not pd.isna(dominated_pass)
        and not pd.isna(dom_effort)
        and not pd.isna(dominated_effort)
        and dom_pass >= dominated_pass
        and dom_effort <= dominated_effort
        and (dom_pass > dominated_pass or dom_effort < dominated_effort)
    ):
        return "robust on shared tasks"
    if (
        not pd.isna(dom_pass)
        and not pd.isna(dominated_pass)
        and not pd.isna(dom_effort)
        and not pd.isna(dominated_effort)
        and dom_pass >= dominated_pass
        and dom_effort > dominated_effort
    ):
        return "performance advantage remains but effort advantage reverses"
    if (
        not pd.isna(dom_pass)
        and not pd.isna(dominated_pass)
        and not pd.isna(dom_effort)
        and not pd.isna(dominated_effort)
        and dom_pass < dominated_pass
        and dom_effort <= dominated_effort
    ):
        return "effort advantage remains but performance advantage reverses"
    return "reversed or weaker on shared tasks"


def similar_success_pairs(configs: pd.DataFrame, effort_col: str, max_examples: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for left, right in itertools.combinations(configs.itertuples(index=False), 2):
        pass_diff = abs(left.task_balanced_pass_rate_pct - right.task_balanced_pass_rate_pct)
        left_effort = getattr(left, effort_col)
        right_effort = getattr(right, effort_col)
        ratio = max_min_ratio(left_effort, right_effort)
        if pass_diff <= SIMILAR_PASS_RATE_PP and not pd.isna(ratio):
            rows.append(
                {
                    "left_config_id": left.config_id,
                    "right_config_id": right.config_id,
                    "left_model": left.model_dir,
                    "right_model": right.model_dir,
                    "left_scaffold": left.scaffold,
                    "right_scaffold": right.scaffold,
                    "left_pass_rate_pct": float(left.task_balanced_pass_rate_pct),
                    "right_pass_rate_pct": float(right.task_balanced_pass_rate_pct),
                    "pass_rate_diff_abs_pp": float(pass_diff),
                    "left_effort": float(left_effort),
                    "right_effort": float(right_effort),
                    "effort_ratio": float(ratio),
                }
            )
    return sorted(rows, key=lambda row: row["effort_ratio"], reverse=True)[:max_examples]


def same_model_pairs(configs: pd.DataFrame, config_task: pd.DataFrame, min_shared_tasks: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model, group in configs.groupby("model_dir"):
        if group["scaffold"].nunique() < 2:
            continue
        for left, right in itertools.combinations(group.itertuples(index=False), 2):
            pair = pairwise_config_metrics(config_task, left.config_id, right.config_id, min_shared_tasks)
            if pair is None:
                continue
            pair["model_dir"] = model
            pair["pass_rate_diff_abs_pp"] = abs(pair["pass_rate_diff_pp"])
            rows.append(pair)
    return pd.DataFrame(rows)


def write_efficiency_csv(configs: pd.DataFrame, out: Path) -> None:
    columns = [
        "scaffold",
        "model_dir",
        "leaderboard_model_organization",
        "task_count",
        "submission_count",
        "submission_task_count",
        "trajectory_count",
        "median_task_trajectory_count",
        "task_balanced_pass_rate_pct",
        "task_balanced_median_total_tokens",
        "task_balanced_median_duration_seconds",
        "task_balanced_median_step_count",
        "task_balanced_median_shell_invocation_count",
        "task_balanced_median_tool_call_count",
        "task_balanced_median_cost_usd_positive",
        "total_tokens_task_count",
        "duration_seconds_task_count",
        "step_count_task_count",
        "shell_invocation_count_task_count",
        "tool_call_count_task_count",
        "cost_usd_positive_task_count",
        "token_pareto",
        "duration_pareto",
        "steps_pareto",
        "shell_invocations_pareto",
        "tool_calls_pareto",
        "observed_cost_pareto",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    configs[columns].to_csv(out, index=False, na_rep="NA")


def print_frontier(configs: pd.DataFrame, status_col: str, effort_col: str, title: str) -> None:
    print(title)
    for row in pareto_frontier(configs, effort_col, status_col).itertuples(index=False):
        print(
            f"- {config_label(row)}: pass={fmt_pct(row.task_balanced_pass_rate_pct)}, "
            f"tokens={compact_count(row.task_balanced_median_total_tokens)}, "
            f"duration={compact_duration(row.task_balanced_median_duration_seconds)}, "
            f"tasks={int(row.task_count)}"
        )


def print_domination_examples(
    examples: list[dict[str, Any]],
    config_task: pd.DataFrame,
    effort_metric: str,
    min_shared_tasks: int,
    effort_label: str,
) -> list[dict[str, Any]]:
    checked = []
    print(f"Strongest {effort_label} domination examples")
    for example in examples:
        shared = pairwise_config_metrics(config_task, example["dominates_config_id"], example["dominated_config_id"], min_shared_tasks)
        status = classify_shared_domination(example, shared, effort_metric)
        checked.append({**example, "shared": shared, "shared_status": status})
        print(
            f"- {model_label(example['dominates_model'])} / {scaffold_label(example['dominates_scaffold'])} "
            f"vs {model_label(example['dominated_model'])} / {scaffold_label(example['dominated_scaffold'])}: "
            f"{fmt_pp(example['pass_rate_gain_pp'])} pass rate, "
            f"{example['effort_reduction_pct']:.1f}% fewer {effort_label}; {status}."
        )
        if shared is not None:
            print(
                f"  shared tasks={shared['shared_tasks']}; "
                f"pass {fmt_pct(shared['left_pass_rate_pct'])} vs {fmt_pct(shared['right_pass_rate_pct'])}; "
                f"tokens {compact_count(shared['left_total_tokens'])} vs {compact_count(shared['right_total_tokens'])}; "
                f"duration {compact_duration(shared['left_duration_seconds'])} vs {compact_duration(shared['right_duration_seconds'])}"
            )
    return checked


def print_similar_pairs(
    pairs: list[dict[str, Any]],
    effort_label: str,
    effort_metric: str,
    config_task: pd.DataFrame,
    min_shared_tasks: int,
) -> None:
    print(f"Similar-success pairs with largest {effort_label} differences")
    for pair in pairs:
        shared = pairwise_config_metrics(config_task, pair["left_config_id"], pair["right_config_id"], min_shared_tasks)
        shared_note = ""
        if shared is not None:
            shared_ratio = max_min_ratio(shared[f"left_{effort_metric}"], shared[f"right_{effort_metric}"])
            shared_diff = abs(shared["left_pass_rate_pct"] - shared["right_pass_rate_pct"])
            shared_note = (
                f"; shared tasks={shared['shared_tasks']}, shared pass diff={shared_diff:.1f} pp, "
                f"shared {effort_label} ratio={fmt_ratio(shared_ratio)}"
            )
        print(
            f"- {model_label(pair['left_model'])} / {scaffold_label(pair['left_scaffold'])} "
            f"vs {model_label(pair['right_model'])} / {scaffold_label(pair['right_scaffold'])}: "
            f"pass diff={pair['pass_rate_diff_abs_pp']:.1f} pp, "
            f"{effort_label} ratio={fmt_ratio(pair['effort_ratio'])}{shared_note}."
        )


def print_same_model_results(pairs: pd.DataFrame) -> None:
    print("Corrected shared-task same-model checks")
    for model in ["gpt-5", "claude-opus-4-6", "gemini-2.5-pro"]:
        subset = pairs[pairs["model_dir"].eq(model)].copy()
        if subset.empty:
            print(f"- {model_label(model)}: not eligible after shared-task filtering.")
            continue
        row = subset.sort_values("pass_rate_diff_abs_pp", ascending=False).iloc[0]
        print(
            f"- {model_label(model)}: {scaffold_label(row.left_scaffold)} vs {scaffold_label(row.right_scaffold)}, "
            f"shared tasks={int(row.shared_tasks)}, pass diff={row.pass_rate_diff_abs_pp:.1f} pp, "
            f"tokens={compact_count(row.left_total_tokens)} vs {compact_count(row.right_total_tokens)} "
            f"({fmt_ratio(row.token_ratio)}), duration={compact_duration(row.left_duration_seconds)} vs "
            f"{compact_duration(row.right_duration_seconds)} ({fmt_ratio(row.duration_ratio)})."
        )

    print("Strongest same-model scaffold performance differences")
    for row in pairs.sort_values(["pass_rate_diff_abs_pp", "token_ratio"], ascending=False).head(5).itertuples(index=False):
        print(
            f"- {model_label(row.model_dir)}: {scaffold_label(row.left_scaffold)} vs "
            f"{scaffold_label(row.right_scaffold)}, shared tasks={int(row.shared_tasks)}, "
            f"pass diff={row.pass_rate_diff_abs_pp:.1f} pp, token ratio={fmt_ratio(row.token_ratio)}, "
            f"duration ratio={fmt_ratio(row.duration_ratio)}."
        )

    similar = pairs[pairs["pass_rate_diff_abs_pp"].le(SIMILAR_PASS_RATE_PP)].copy()
    print("Strongest same-model efficiency example")
    if similar.empty:
        print("- No same-model scaffold pair had pass rates within 5 pp after shared-task matching.")
        return
    token_best = similar.sort_values("token_ratio", ascending=False).iloc[0]
    duration_best = similar.sort_values("duration_ratio", ascending=False).iloc[0]
    print(
        f"- Token: {model_label(token_best.model_dir)} under {scaffold_label(token_best.left_scaffold)} vs "
        f"{scaffold_label(token_best.right_scaffold)} differs by {token_best.pass_rate_diff_abs_pp:.1f} pp, "
        f"but uses {compact_count(token_best.left_total_tokens)} vs {compact_count(token_best.right_total_tokens)} "
        f"tokens ({fmt_ratio(token_best.token_ratio)})."
    )
    print(
        f"- Duration: {model_label(duration_best.model_dir)} under {scaffold_label(duration_best.left_scaffold)} vs "
        f"{scaffold_label(duration_best.right_scaffold)} differs by {duration_best.pass_rate_diff_abs_pp:.1f} pp, "
        f"but uses {compact_duration(duration_best.left_duration_seconds)} vs "
        f"{compact_duration(duration_best.right_duration_seconds)} ({fmt_ratio(duration_best.duration_ratio)})."
    )


def print_diagnostics(configs: pd.DataFrame) -> None:
    print("Secondary configuration-level Spearman diagnostics")
    for metric, label in [
        ("task_balanced_median_total_tokens", "tokens"),
        ("task_balanced_median_duration_seconds", "duration"),
        ("task_balanced_median_tool_call_count", "tool calls"),
    ]:
        sub = configs[["task_balanced_pass_rate_pct", metric]].dropna()
        corr = sub["task_balanced_pass_rate_pct"].rank().corr(sub[metric].rank()) if len(sub) > 2 else math.nan
        print(f"- {label}: rho={corr:.3f} (n={len(sub)})")


def print_secondary_frontier_summary(configs: pd.DataFrame, args: argparse.Namespace) -> None:
    print("Secondary Pareto-frontier plots")
    for spec in PARETO_METRICS[2:]:
        eligible = metric_configs(configs, spec, args)
        frontier = pareto_frontier(configs, spec["effort_col"], spec["status_col"])
        if eligible.empty or frontier.empty:
            print(f"- {spec['name']}: skipped because fewer than one configuration had sufficient metric coverage.")
            continue
        median_coverage = float(eligible[spec["task_count_col"]].median())
        print(
            f"- {spec['name']}: {frontier.shape[0]} nondominated configurations from "
            f"{eligible.shape[0]} eligible; median metric task coverage={median_coverage:.0f}."
        )


def print_results(configs: pd.DataFrame, config_task: pd.DataFrame, support: dict[str, Any], duration_plot_written: bool, args: argparse.Namespace) -> None:
    print("Configuration support")
    print(f"- Chosen threshold: {support['threshold']}.")
    print("- Rationale: this keeps configurations covering about 90% of TB2.0 tasks plus enough trials for stable task medians.")
    print(f"- Configurations before filtering: {support['before']}; retained: {support['after']}.")
    print(
        f"- Retained models={support['models']}, scaffolds={support['scaffolds']}, "
        f"median task coverage={support['median_task_coverage_after']:.0f}."
    )
    print("Main configuration-efficiency result")
    token_frontier = pareto_frontier(configs, "task_balanced_median_total_tokens", "token_pareto")
    duration_frontier = pareto_frontier(configs, "task_balanced_median_duration_seconds", "duration_pareto")
    print(f"- The token frontier contains {token_frontier.shape[0]} nondominated configurations out of {configs.shape[0]} retained.")
    print(f"- The duration frontier contains {duration_frontier.shape[0]} nondominated configurations.")
    print("- Configurations with similar task-balanced success can differ by large multiples in token use or runtime.")
    print(
        f"- The duration frontier {'is distinct from' if duration_plot_written else 'matches'} the token frontier, "
        "so runtime is treated as a secondary efficiency view."
    )
    print_frontier(configs, "token_pareto", "task_balanced_median_total_tokens", "Token Pareto frontier")
    print_frontier(configs, "duration_pareto", "task_balanced_median_duration_seconds", "Duration Pareto frontier")
    print_secondary_frontier_summary(configs, args)

    checked = print_domination_examples(
        strongest_domination_examples(configs, "task_balanced_median_total_tokens", 3),
        config_task,
        "total_tokens",
        args.min_shared_tasks,
        "tokens",
    )
    robust = [row for row in checked if row["shared_status"] == "robust on shared tasks"]
    weak = [row for row in checked if row["shared_status"] != "robust on shared tasks"]
    print("Task-composition robustness")
    print(f"- Robust on shared tasks: {len(robust)}/{len(checked)} highlighted token-domination examples.")
    if weak:
        print(
            "- Weaker or reversed examples: "
            + "; ".join(
                f"{model_label(row['dominates_model'])}/{scaffold_label(row['dominates_scaffold'])} vs "
                f"{model_label(row['dominated_model'])}/{scaffold_label(row['dominated_scaffold'])}"
                for row in weak
            )
        )
    print_similar_pairs(
        similar_success_pairs(configs, "task_balanced_median_total_tokens", 5),
        "token",
        "total_tokens",
        config_task,
        args.min_shared_tasks,
    )
    print_similar_pairs(
        similar_success_pairs(configs, "task_balanced_median_duration_seconds", 5),
        "duration",
        "duration_seconds",
        config_task,
        args.min_shared_tasks,
    )
    print_same_model_results(same_model_pairs(configs, config_task, args.min_shared_tasks))
    print_diagnostics(configs)
    print("Candidate answer to RQ1.3")
    print(
        "Agent configurations vary substantially in both task-balanced performance and resource use. "
        "The empirical token frontier identifies a small set of nondominated scaffold-model combinations, "
        "while many retained configurations are dominated by alternatives with equal or higher success and lower token use. "
        "Shared-task checks show that several same-model scaffold differences remain after controlling task composition, "
        "although some apparent global advantages weaken or reverse on matched tasks. Observed efficiency is therefore "
        "best described as a property of the complete model-scaffold configuration, without treating these descriptive "
        "comparisons as causal scaffold effects."
    )


def main() -> None:
    args = parse_args()
    df = load_data(args.input)
    submission_task = submission_task_summary(df)
    config_task = config_task_summary(submission_task)
    all_configs = config_summary(config_task, df)
    support = support_summary(all_configs, args)
    configs = eligible_configs(all_configs, args)
    for spec in PARETO_METRICS:
        configs = add_metric_pareto_status(configs, spec, args)

    out_csv = args.out / "rq1_3_configuration_efficiency.csv"

    write_efficiency_csv(configs, out_csv)
    figure_paths: list[Path] = []
    token_spec = PARETO_METRICS[0]
    duration_spec = PARETO_METRICS[1]
    token_frontier = set(configs.loc[configs[token_spec["status_col"]], "config_id"])
    duration_frontier = set(configs.loc[configs[duration_spec["status_col"]], "config_id"])
    duration_plot_written = duration_frontier != token_frontier
    highlighted_models = representative_models(configs, args.max_model_pareto_models)

    for spec in PARETO_METRICS:
        if spec["name"] == "duration" and not duration_plot_written:
            continue
        plot_configs = metric_configs(configs, spec, args)
        if plot_configs.empty:
            continue
        scaffold_fig_path = args.figures_dir / "by_scaffold_pareto" / spec["scaffold_figure_name"]
        plot_pareto(
            plot_configs,
            spec["effort_col"],
            spec["status_col"],
            spec["xlabel"],
            spec["title"],
            scaffold_fig_path,
            spec["formatter"],
            spec["label_domination"],
        )
        figure_paths.append(scaffold_fig_path)
        model_fig_path = args.figures_dir / "by_model_pareto" / spec["model_figure_name"]
        plot_pareto_by_model(
            plot_configs,
            spec["effort_col"],
            spec["status_col"],
            spec["xlabel"],
            spec["title"].replace("configuration efficiency:", "configuration efficiency by model:"),
            model_fig_path,
            spec["formatter"],
            highlighted_models,
        )
        figure_paths.append(model_fig_path)

    print_results(configs, config_task, support, duration_plot_written, args)
    print("By-model Pareto highlighting")
    print(
        f"- Highlighted {len(highlighted_models)} representative models; "
        f"the remaining {configs['model_dir'].nunique() - len(highlighted_models)} retained models are grouped as Other models."
    )
    print("- " + "; ".join(model_label(model) for model in highlighted_models))
    print("Files written")
    print(f"- {out_csv}")
    for fig_path in figure_paths:
        print(f"- {fig_path}")


if __name__ == "__main__":
    main()
