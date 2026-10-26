#!/usr/bin/env python3
"""Token-accounting analysis for longitudinal Terminal-Bench runs.

The final thesis analysis keeps only three ideas:
- clean model-version comparisons show heterogeneous token changes;
- trajectory-level input tokens are the sum of input tokens from successive
  model calls, and input contexts usually grow during a trajectory.

Outputs:
- data/processed_live/longitudinal/token_accounting/token_vs_logged_text_monthly.csv
- optional with --include-comparisons: token_accounting/token_accounting_comparisons.csv
- data/processed_live/longitudinal/token_accounting/input_context_growth_summary.csv
- data/processed_live/longitudinal/token_accounting/input_context_audit.json
- reports/longitudinal/token_accounting/token_vs_logged_text_over_time.png
- reports/longitudinal/token_accounting/input_token_accumulation.png
- reports/longitudinal/token_accounting/input_context_growth_distribution.png
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT_GUESS = Path(__file__).resolve().parents[3]
if str(REPO_ROOT_GUESS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_GUESS))

from scripts.analysis.plot_style import COLORBLIND_PALETTE, PASS_COLOR, thesis_style, paper_axis_labels, save_paper_figure
from scripts.benchmark_paths import find_repo_root
from scripts.analysis.submission_task_balancing import SOURCE_SUBMISSION_ID, ensure_source_submission_id


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
LONGITUDINAL_DIR = REPO_ROOT / "data" / "processed_live" / "longitudinal"
TRAJECTORY_CSV = LONGITUDINAL_DIR / "trajectory_longitudinal.csv"
TRAJECTORY_ROOT = REPO_ROOT / "data" / "trajectories"
OUT_DIR = LONGITUDINAL_DIR / "token_accounting"
FIGURES_DIR = REPO_ROOT / "reports" / "longitudinal" / "token_accounting"

COMPARISONS_CSV = OUT_DIR / "token_accounting_comparisons.csv"
MONTHLY_TOKEN_TEXT_CSV = OUT_DIR / "token_vs_logged_text_monthly.csv"
TOKEN_TEXT_OVER_TIME_FIG = FIGURES_DIR / "token_vs_logged_text_over_time.png"
INPUT_ACCUMULATION_FIG = FIGURES_DIR / "input_token_accumulation.png"
INPUT_CONTEXT_DISTRIBUTION_FIG = FIGURES_DIR / "input_context_growth_distribution.png"
INPUT_CONTEXT_SUMMARY_CSV = OUT_DIR / "input_context_growth_summary.csv"
INPUT_CONTEXT_AUDIT_JSON = OUT_DIR / "input_context_audit.json"
MIN_RELIABLE_MONTH_TRAJECTORIES = 100

REQUIRED_COLUMNS = {
    SOURCE_SUBMISSION_ID,
    "benchmark",
    "benchmark_version",
    "rel_path",
    "scaffold",
    "model_dir",
    "task_name",
    "message_chars",
    "reasoning_chars",
    "observation_chars",
    "prompt_tokens",
    "completion_tokens",
    "historical_leaderboard_timestamp",
    "total_tokens",
}


@dataclass(frozen=True)
class ComparisonSpec:
    comparison_id: str
    scaffold: str
    earlier_model: str
    earlier_benchmark: str
    later_model: str
    later_benchmark: str


COMPARISONS = [
    ComparisonSpec("codex_gpt5_to_gpt55", "codex", "gpt-5", "2.0", "gpt-5.5", "2.1"),
    ComparisonSpec("codex_gpt5_to_gpt56_luna", "codex", "gpt-5", "2.0", "gpt-5.6-luna", "2.1"),
    ComparisonSpec("codex_gpt5_to_gpt56_terra", "codex", "gpt-5", "2.0", "gpt-5.6-terra", "2.1"),
    ComparisonSpec("gemini_cli_25pro_to_3pro", "gemini-cli", "gemini-2.5-pro", "2.0", "gemini-3-pro-preview", "2.1"),
    ComparisonSpec(
        "claude_code_opus46_to_opus47",
        "claude-code",
        "claude-opus-4-6",
        "2.0",
        "claude-opus-4-7",
        "2.1",
    ),
    ComparisonSpec(
        "claude_code_sonnet45_to_sonnet5",
        "claude-code",
        "claude-sonnet-4-5-20250929",
        "2.0",
        "claude-sonnet-5",
        "2.1",
    ),
    ComparisonSpec("terminus2_gpt52_to_gpt55", "terminus-2", "gpt-5.2", "2.0", "gpt-5.5", "2.1"),
    ComparisonSpec(
        "terminus2_gemini3_to_31",
        "terminus-2",
        "gemini-3-pro-preview",
        "2.0",
        "gemini-3.1-pro-preview",
        "2.1",
    ),
    ComparisonSpec(
        "terminus2_opus46_to_opus47",
        "terminus-2",
        "claude-opus-4-6",
        "2.0",
        "claude-opus-4-7",
        "2.1",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monthly-only", action="store_true", help="Refresh historical-date monthly summaries without reparsing unaffected raw token metrics")
    parser.add_argument("--include-comparisons", action="store_true",
                        help="Also export exploratory model-progression comparisons.")
    parser.add_argument("--trajectory-csv", type=Path, default=TRAJECTORY_CSV)
    parser.add_argument("--trajectory-root", type=Path, default=TRAJECTORY_ROOT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR)
    parser.add_argument("--workers", type=int, default=24)
    return parser.parse_args()


def require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def numeric(value: Any) -> float:
    if value in {"", None}:
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def pct_change(earlier: float, later: float) -> float:
    if pd.isna(earlier) or pd.isna(later) or earlier == 0:
        return math.nan
    return (later / earlier - 1.0) * 100.0


def format_pct(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value:+.0f}%"


def format_value(value: float) -> str:
    if pd.isna(value):
        return "NA"
    if abs(value) >= 1000:
        return f"{value / 1000:.1f}k"
    return f"{value:.0f}"


def format_millions(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value / 1_000_000:.1f}M"


def format_arrow(earlier: float, later: float) -> str:
    return f"{format_value(earlier)} -> {format_value(later)}"


def model_label(model: str) -> str:
    labels = {
        "gpt-5": "GPT-5",
        "gpt-5.2": "GPT-5.2",
        "gpt-5.5": "GPT-5.5",
        "gpt-5.6-luna": "GPT-5.6 Luna",
        "gpt-5.6-terra": "GPT-5.6 Terra",
        "gemini-2.5-pro": "Gemini 2.5 Pro",
        "gemini-3-pro-preview": "Gemini 3 Pro",
        "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
        "claude-opus-4-6": "Opus 4.6",
        "claude-opus-4-7": "Opus 4.7",
        "claude-sonnet-4-5-20250929": "Sonnet 4.5",
        "claude-sonnet-5": "Sonnet 5",
    }
    return labels.get(model, model)


def scaffold_label(scaffold: str) -> str:
    labels = {
        "codex": "Codex",
        "gemini-cli": "Gemini CLI",
        "claude-code": "Claude Code",
        "terminus-2": "Terminus-2",
        "mini-swe-agent": "mini-swe-agent",
        "openhands": "OpenHands",
        "terminus-3-3": "Terminus-3.3",
        "terminus-kira-env-bootstrap": "Terminus Kira env bootstrap",
        "judy": "Judy",
    }
    return labels.get(scaffold, scaffold)


def benchmark_label(version: Any) -> str:
    return f"Terminal-Bench {version}"


def comparison_label(row: Any) -> str:
    return f"{scaffold_label(row.scaffold)}: {model_label(row.earlier_model)} -> {model_label(row.later_model)}"


def read_trajectories(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=sorted(REQUIRED_COLUMNS), low_memory=False)
    require_columns(df, REQUIRED_COLUMNS, str(path))
    df = ensure_source_submission_id(df)
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    for column in [
        "message_chars",
        "reasoning_chars",
        "observation_chars",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    ]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["submission_datetime"] = pd.to_datetime(df["historical_leaderboard_timestamp"], errors="coerce", utc=True)
    df["submission_month"] = df["submission_datetime"].dt.tz_convert(None).dt.to_period("M").dt.to_timestamp()
    df["logged_chars"] = df["message_chars"] + df["reasoning_chars"] + df["observation_chars"]
    return df


def benchmark_version_composition(group: pd.DataFrame) -> str:
    counts = group["benchmark_version"].value_counts().sort_index()
    return "; ".join(f"TB{version}: {count}" for version, count in counts.items())


def build_monthly_token_text_summary(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    metrics = ["prompt_tokens", "completion_tokens", "total_tokens", "logged_chars"]
    dated = df.dropna(subset=["submission_month"]).copy()
    if dated.empty:
        raise ValueError("No trajectories with recorded historical leaderboard date (event semantics unverified)s were available.")

    rows: list[dict[str, Any]] = []
    for month, group in dated.groupby("submission_month", sort=True):
        row: dict[str, Any] = {
            "month": month,
            "aggregation": "hierarchical_source_submission_task",
            "trajectory_n": int(group.shape[0]),
            "benchmark_version_composition": benchmark_version_composition(group),
            "tb20_trajectory_n": int(group["benchmark_version"].eq("2.0").sum()),
            "tb21_trajectory_n": int(group["benchmark_version"].eq("2.1").sum()),
        }
        for metric in metrics:
            valid = group[metric].dropna()
            row[f"{metric}_n"] = int(valid.shape[0])
            row[f"median_{metric}"] = task_balanced_median(group, metric)
        rows.append(row)

    monthly = pd.DataFrame(rows).sort_values("month").reset_index(drop=True)
    all_months = pd.DataFrame(
        {"month": pd.date_range(monthly["month"].min(), monthly["month"].max(), freq="MS")}
    )
    monthly = all_months.merge(monthly, on="month", how="left")
    count_columns = [
        "trajectory_n",
        "tb20_trajectory_n",
        "tb21_trajectory_n",
        *[f"{metric}_n" for metric in metrics],
    ]
    monthly[count_columns] = monthly[count_columns].fillna(0).astype(int)
    monthly["benchmark_version_composition"] = monthly["benchmark_version_composition"].fillna("no submissions")
    monthly["reliable_month"] = (
        monthly[[f"{metric}_n" for metric in metrics]].min(axis=1) >= MIN_RELIABLE_MONTH_TRAJECTORIES
    )
    reliable = monthly[monthly["reliable_month"]].copy()
    if reliable.empty:
        raise ValueError(
            f"No month had at least {MIN_RELIABLE_MONTH_TRAJECTORIES} valid trajectories for all four metrics."
        )

    baseline_idx = reliable.index[0]
    baseline = monthly.loc[baseline_idx]
    for metric in metrics:
        baseline_value = float(baseline[f"median_{metric}"])
        if pd.isna(baseline_value) or baseline_value == 0:
            raise ValueError(f"Baseline month has invalid median for {metric}.")
        monthly[f"indexed_{metric}"] = 100.0 * monthly[f"median_{metric}"] / baseline_value

    monthly["month"] = pd.to_datetime(monthly["month"]).dt.strftime("%Y-%m")
    baseline = monthly.loc[baseline_idx]
    return monthly, baseline


def first_tb21_month(monthly: pd.DataFrame) -> pd.Timestamp | None:
    tb21_months = monthly.loc[monthly["tb21_trajectory_n"].gt(0), "month"]
    if tb21_months.empty:
        return None
    return pd.to_datetime(tb21_months.iloc[0])


def plot_token_text_over_time(monthly: pd.DataFrame, out: Path) -> None:
    thesis_style()
    plot_df = monthly.copy()
    plot_df["month_dt"] = pd.to_datetime(plot_df["month"])
    fig, ax_tokens = plt.subplots(figsize=(7.2, 3.55))
    ax_chars = ax_tokens.twinx()

    token_series = [
        ("median_prompt_tokens", "Input tokens", COLORBLIND_PALETTE[0]),
        ("median_completion_tokens", "Output tokens", COLORBLIND_PALETTE[4]),
        ("median_total_tokens", "Total tokens", COLORBLIND_PALETTE[3]),
    ]
    handles = []
    labels = []
    for column, label, color in token_series:
        line = ax_tokens.plot(
            plot_df["month_dt"],
            plot_df[column] / 1000.0,
            marker="o",
            markersize=3.5,
            linewidth=1.7,
            color=color,
            label=label,
        )
        handles.extend(line)
        labels.append(label)

    char_line = ax_chars.plot(
        plot_df["month_dt"],
        plot_df["median_logged_chars"] / 1000.0,
        marker="o",
        markersize=3.5,
        linewidth=1.7,
        color=COLORBLIND_PALETTE[2],
        label="Logged characters",
    )
    handles.extend(char_line)
    labels.append("Logged characters")

    transition_month = first_tb21_month(plot_df)
    if transition_month is not None:
        ax_tokens.axvline(transition_month, color="#777777", linestyle=(0, (2, 3)), linewidth=0.9, alpha=0.7)
        y_top = ax_tokens.get_ylim()[1]
        ax_tokens.text(
            transition_month,
            y_top * 0.60,
            " first TB2.1 month",
            rotation=90,
            va="top",
            ha="left",
            fontsize=9.5,
            color="#555555",
        )

    ax_tokens.set_xlabel("Historical leaderboard month (semantics unverified)")
    ax_tokens.set_ylabel("Tokens (thousands)\nMonthly hierarchical median")
    ax_chars.set_ylabel("Logged characters (thousands)\nMonthly hierarchical median")
    ax_tokens.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax_tokens.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax_tokens.yaxis.set_major_formatter(lambda value, _: f"{value:.0f}")
    ax_chars.yaxis.set_major_formatter(lambda value, _: f"{value:.0f}")
    ax_tokens.grid(axis="y", color="#E5E5E5", linewidth=0.8)
    ax_tokens.legend(handles, labels, frameon=False, ncol=2, loc="upper left")
    fig.autofmt_xdate(rotation=35, ha="right")
    paper_axis_labels(fig)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    save_paper_figure(fig, out, bbox_inches="tight", dpi=300)
    plt.close(fig)


def reliable_endpoints(monthly: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    reliable = monthly[monthly["reliable_month"]].copy()
    if reliable.empty:
        raise ValueError("No reliable months are available for endpoint reporting.")
    return reliable.iloc[0], reliable.iloc[-1]


def print_monthly_token_text_summary(monthly: pd.DataFrame, baseline: pd.Series, out_csv: Path, out_fig: Path) -> None:
    first, last = reliable_endpoints(monthly)
    print("\nLongitudinal token/text monthly medians")
    print(f"Reliable-month threshold: at least {MIN_RELIABLE_MONTH_TRAJECTORIES} valid trajectories per metric.")
    print(
        "Date coverage: "
        f"{monthly['month'].iloc[0]} through {monthly['month'].iloc[-1]} "
        f"({monthly.shape[0]} calendar months)."
    )
    print(f"Baseline month: {baseline['month']} (trajectory_n={int(baseline['trajectory_n'])}).")
    no_submission = monthly[monthly["trajectory_n"].eq(0)]
    if not no_submission.empty:
        print(f"Months with no submissions retained as gaps: {', '.join(no_submission['month'])}.")
    low_n = monthly[monthly["trajectory_n"].gt(0) & monthly["trajectory_n"].lt(500)]
    if not low_n.empty:
        low_months = ", ".join(f"{row.month} (n={int(row.trajectory_n)})" for row in low_n.itertuples(index=False))
        print(f"Small monthly samples retained and flagged by N: {low_months}.")

    print(
        f"First reliable month: {first['month']} (trajectory_n={int(first['trajectory_n'])}); "
        f"last reliable month: {last['month']} (trajectory_n={int(last['trajectory_n'])})."
    )
    for label, metric in [
        ("Input tokens", "prompt_tokens"),
        ("Output tokens", "completion_tokens"),
        ("Total tokens", "total_tokens"),
        ("Logged characters", "logged_chars"),
    ]:
        earlier = float(first[f"median_{metric}"])
        later = float(last[f"median_{metric}"])
        print(f"{label}: {format_value(earlier)} -> {format_value(later)} ({pct_change(earlier, later):+.1f}%).")

    print("Monthly medians balance trials within source-submission/task, submissions within task, then tasks in each dated monthly cohort; monthly task support and configuration composition may change.")
    print(f"Wrote monthly CSV to {out_csv}")
    print(f"Wrote monthly figure to {out_fig}")


def comparison_groups() -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for spec in COMPARISONS:
        rows.append(
            {
                "benchmark_version": spec.earlier_benchmark,
                "scaffold": spec.scaffold,
                "model_dir": spec.earlier_model,
            }
        )
        rows.append(
            {
                "benchmark_version": spec.later_benchmark,
                "scaffold": spec.scaffold,
                "model_dir": spec.later_model,
            }
        )
    return pd.DataFrame(rows).drop_duplicates()


def select_rows_for_analysis(df: pd.DataFrame) -> pd.DataFrame:
    selected = df.merge(comparison_groups(), on=["benchmark_version", "scaffold", "model_dir"], how="inner")
    if selected.empty:
        raise ValueError("No trajectory rows matched the token-accounting comparison set.")
    return selected.drop_duplicates(["benchmark", "rel_path"]).reset_index(drop=True)


def trajectory_path(row: pd.Series, root: Path) -> Path:
    rel_path = str(row["rel_path"]).replace("\\", "/")
    return root / str(row["benchmark"]) / Path(rel_path)


def parse_raw_trajectory(row: pd.Series, root: Path) -> dict[str, Any]:
    path = trajectory_path(row, root)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Trajectory JSON is not an object: {path}")

    prompt_calls: list[float] = []

    steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    for step in steps:
        if not isinstance(step, dict):
            continue
        metrics = step.get("metrics") if isinstance(step.get("metrics"), dict) else {}
        if not metrics:
            continue

        prompt = numeric(metrics.get("prompt_tokens"))
        if not pd.isna(prompt):
            prompt_calls.append(prompt)

    first_prompt = prompt_calls[0] if prompt_calls else math.nan
    last_prompt = prompt_calls[-1] if prompt_calls else math.nan
    diffs = np.diff(prompt_calls) if len(prompt_calls) >= 2 else np.array([])
    adjacent_transition_count = int(len(diffs))
    adjacent_increase_count = int((diffs > 0).sum()) if adjacent_transition_count else 0
    adjacent_increase_share = (
        adjacent_increase_count / adjacent_transition_count if adjacent_transition_count else math.nan
    )

    return {
        SOURCE_SUBMISSION_ID: row[SOURCE_SUBMISSION_ID],
        "benchmark": row["benchmark"],
        "benchmark_version": row["benchmark_version"],
        "rel_path": row["rel_path"],
        "task_name": row["task_name"],
        "scaffold": row["scaffold"],
        "model_dir": row["model_dir"],
        "logged_chars": row["logged_chars"],
        "prompt_tokens": row["prompt_tokens"],
        "completion_tokens": row["completion_tokens"],
        "total_tokens": row["total_tokens"],
        "prompt_calls": prompt_calls,
        "prompt_calls_sum": float(sum(prompt_calls)) if prompt_calls else math.nan,
        "prompt_call_count": len(prompt_calls),
        "first_call_prompt_tokens": first_prompt,
        "last_call_prompt_tokens": last_prompt,
        "final_to_first_prompt_ratio": last_prompt / first_prompt if first_prompt else math.nan,
        "adjacent_transition_count": adjacent_transition_count,
        "adjacent_increase_count": adjacent_increase_count,
        "adjacent_increase_share": adjacent_increase_share,
        "mostly_increasing": adjacent_increase_share >= 0.5 if not pd.isna(adjacent_increase_share) else False,
        "trajectory_path": str(path.relative_to(REPO_ROOT)),
    }


def parse_raw_metrics(df: pd.DataFrame, root: Path, workers: int) -> pd.DataFrame:
    rows = [row for _, row in df.iterrows()]
    parsed: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(parse_raw_trajectory, row, root) for row in rows]
        for idx, future in enumerate(as_completed(futures), start=1):
            parsed.append(future.result())
            if idx % 2500 == 0:
                print(f"Parsed {idx:,} raw trajectories...")
    return pd.DataFrame(parsed).sort_values(["benchmark", "rel_path"]).reset_index(drop=True)


def task_balanced_values(df: pd.DataFrame, metric: str) -> pd.Series:
    """One median per task after balancing source submissions and their trials."""
    if metric not in df.columns or df.empty:
        return pd.Series(dtype=float)
    # Keep the source level even for a single configuration: it may have
    # multiple submissions with unequal numbers of repeated trials.
    df = ensure_source_submission_id(df)
    submission_task = df.groupby([SOURCE_SUBMISSION_ID, "task_name"])[metric].median()
    return submission_task.groupby("task_name").median().dropna()


def task_balanced_median(df: pd.DataFrame, metric: str) -> float:
    values = task_balanced_values(df, metric)
    return float(values.median()) if not values.empty else math.nan


def summarize_side(df: pd.DataFrame, spec: ComparisonSpec, side: str, shared_tasks: set[str]) -> dict[str, Any]:
    model = spec.earlier_model if side == "earlier" else spec.later_model
    version = spec.earlier_benchmark if side == "earlier" else spec.later_benchmark
    group = df[
        df["benchmark_version"].eq(version)
        & df["scaffold"].eq(spec.scaffold)
        & df["model_dir"].eq(model)
        & df["task_name"].isin(shared_tasks)
    ]
    row: dict[str, Any] = {
        "trajectory_count": int(group.shape[0]),
        "task_count": int(group["task_name"].nunique()),
    }
    for metric in [
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "logged_chars",
    ]:
        row[metric] = task_balanced_median(group, metric)
    return row


def build_comparisons(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in COMPARISONS:
        earlier_tasks = set(
            df.loc[
                df["benchmark_version"].eq(spec.earlier_benchmark)
                & df["scaffold"].eq(spec.scaffold)
                & df["model_dir"].eq(spec.earlier_model),
                "task_name",
            ].dropna()
        )
        later_tasks = set(
            df.loc[
                df["benchmark_version"].eq(spec.later_benchmark)
                & df["scaffold"].eq(spec.scaffold)
                & df["model_dir"].eq(spec.later_model),
                "task_name",
            ].dropna()
        )
        shared_tasks = earlier_tasks.intersection(later_tasks)
        if not shared_tasks:
            raise ValueError(f"No shared tasks for comparison {spec.comparison_id}")

        earlier = summarize_side(df, spec, "earlier", shared_tasks)
        later = summarize_side(df, spec, "later", shared_tasks)

        row: dict[str, Any] = {
            "comparison_id": spec.comparison_id,
            "scaffold": spec.scaffold,
            "earlier_model": spec.earlier_model,
            "later_model": spec.later_model,
            "earlier_benchmark": spec.earlier_benchmark,
            "later_benchmark": spec.later_benchmark,
            "shared_task_count": len(shared_tasks),
        }
        for metric in ["prompt_tokens", "completion_tokens", "total_tokens", "logged_chars"]:
            row[f"{metric}_earlier"] = earlier[metric]
            row[f"{metric}_later"] = later[metric]
            row[f"{metric}_change_pct"] = pct_change(earlier[metric], later[metric])

        rows.append(row)

    order = [
        "comparison_id",
        "scaffold",
        "earlier_model",
        "later_model",
        "earlier_benchmark",
        "later_benchmark",
        "shared_task_count",
        "prompt_tokens_earlier",
        "prompt_tokens_later",
        "prompt_tokens_change_pct",
        "completion_tokens_earlier",
        "completion_tokens_later",
        "completion_tokens_change_pct",
        "total_tokens_earlier",
        "total_tokens_later",
        "total_tokens_change_pct",
        "logged_chars_earlier",
        "logged_chars_later",
        "logged_chars_change_pct",
    ]
    return pd.DataFrame(rows)[order]


def validate_metrics(df: pd.DataFrame) -> dict[str, int]:
    tolerance = 1e-6
    token_rows = df[["prompt_tokens", "completion_tokens", "total_tokens"]].dropna()
    token_bad = token_rows[
        (token_rows["prompt_tokens"] + token_rows["completion_tokens"] - token_rows["total_tokens"]).abs()
        > tolerance
    ]

    results = {
        "token_arithmetic_checked": int(token_rows.shape[0]),
        "token_arithmetic_invalid": int(token_bad.shape[0]),
    }
    if results["token_arithmetic_invalid"]:
        raise ValueError(f"Validation failed: {results}")
    return results


def context_accumulation_trajectory_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Measure prompt growth for trajectories with a positive initial count."""
    eligible = df[
        df["prompt_call_count"].ge(2)
        & df["first_call_prompt_tokens"].gt(0)
        & df["prompt_tokens"].notna()
    ].copy()
    eligible["per_call_prompt_sum"] = eligible["prompt_calls_sum"]
    eligible["trajectory_prompt_tokens"] = eligible["prompt_tokens"]
    diff = (eligible["per_call_prompt_sum"] - eligible["trajectory_prompt_tokens"]).abs()
    integer_like = (
        np.isclose(eligible["per_call_prompt_sum"], np.round(eligible["per_call_prompt_sum"]))
        & np.isclose(eligible["trajectory_prompt_tokens"], np.round(eligible["trajectory_prompt_tokens"]))
    )
    eligible["sum_matches_trajectory_prompt"] = np.where(
        integer_like,
        eligible["per_call_prompt_sum"].eq(eligible["trajectory_prompt_tokens"]),
        diff <= 1e-6,
    )
    eligible["last_gt_first"] = eligible["last_call_prompt_tokens"] > eligible["first_call_prompt_tokens"]
    eligible["final_to_first_prompt_ratio"] = (
        eligible["last_call_prompt_tokens"] / eligible["first_call_prompt_tokens"]
    )
    return eligible


def context_summary_row(group_type: str, group_name: str, group: pd.DataFrame) -> dict[str, Any]:
    ratios = task_balanced_values(group, "final_to_first_prompt_ratio")
    return {
        "group_type": group_type,
        "group": group_name,
        "ratio_aggregation": "hierarchical_source_submission_task",
        "frequency_aggregation": "record_counts",
        "ratio_tasks": len(ratios),
        "source_submissions": group[SOURCE_SUBMISSION_ID].nunique(),
        "eligible_trajectories": int(group.shape[0]),
        "exact_sum_count": int(group["sum_matches_trajectory_prompt"].sum()),
        "exact_sum_pct": float(group["sum_matches_trajectory_prompt"].mean() * 100.0),
        "last_gt_first_count": int(group["last_gt_first"].sum()),
        "last_gt_first_pct": float(group["last_gt_first"].mean() * 100.0),
        "mostly_increasing_count": int(group["mostly_increasing"].sum()),
        "mostly_increasing_pct": float(group["mostly_increasing"].mean() * 100.0),
        "median_final_first_ratio": float(ratios.median()) if not ratios.empty else math.nan,
        "q1_final_first_ratio": float(ratios.quantile(0.25)) if not ratios.empty else math.nan,
        "q3_final_first_ratio": float(ratios.quantile(0.75)) if not ratios.empty else math.nan,
    }


def summarize_context_accumulation(eligible: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if eligible.empty:
        return pd.DataFrame()

    rows.append(context_summary_row("overall", "overall", eligible))

    scaffold_counts = eligible["scaffold"].value_counts()
    scaffold_order = [
        scaffold
        for scaffold in [
            "codex",
            "gemini-cli",
            "claude-code",
            "terminus-2",
            "mini-swe-agent",
            "openhands",
            "terminus-3-3",
            "terminus-kira-env-bootstrap",
            "judy",
        ]
        if scaffold in scaffold_counts.index
    ]
    scaffold_order.extend([scaffold for scaffold in scaffold_counts.index if scaffold not in scaffold_order])
    for scaffold in scaffold_order:
        group = eligible[eligible["scaffold"].eq(scaffold)]
        rows.append(context_summary_row("scaffold", scaffold_label(scaffold), group))

    for version in sorted(eligible["benchmark_version"].dropna().astype(str).unique()):
        group = eligible[eligible["benchmark_version"].astype(str).eq(version)]
        rows.append(context_summary_row("benchmark_version", benchmark_label(version), group))

    order = [
        "group_type",
        "group",
        "ratio_aggregation",
        "frequency_aggregation",
        "ratio_tasks",
        "source_submissions",
        "eligible_trajectories",
        "exact_sum_count",
        "exact_sum_pct",
        "last_gt_first_count",
        "last_gt_first_pct",
        "mostly_increasing_count",
        "mostly_increasing_pct",
        "median_final_first_ratio",
        "q1_final_first_ratio",
        "q3_final_first_ratio",
    ]
    return pd.DataFrame(rows)[order]


def context_audit(scanned: pd.DataFrame, all_eligible: pd.DataFrame) -> dict[str, Any]:
    prompt_metric_rows = scanned["prompt_call_count"].ge(1)
    at_least_two_prompt_calls = scanned["prompt_call_count"].ge(2)
    exact_sum_rate = (
        float(all_eligible["sum_matches_trajectory_prompt"].mean() * 100.0) if not all_eligible.empty else math.nan
    )

    return {
        "total_trajectories_scanned": int(scanned.shape[0]),
        "any_per_call_prompt_metrics": int(prompt_metric_rows.sum()),
        "at_least_two_valid_prompt_calls": int(at_least_two_prompt_calls.sum()),
        "eligible_trajectories": int(all_eligible.shape[0]),
        "excluded_trajectories": int(scanned.shape[0] - all_eligible.shape[0]),
        "excluded_nonpositive_first_prompt": int(
            (at_least_two_prompt_calls & scanned["first_call_prompt_tokens"].le(0)).sum()
        ),
        "exact_sum_match_rate_overall": exact_sum_rate,
    }


def accumulation_score(prompt_calls: list[float]) -> float:
    if len(prompt_calls) < 4:
        return -math.inf
    diffs = np.diff(prompt_calls)
    increasing_share = float((diffs > 0).mean()) if len(diffs) else 0.0
    growth = prompt_calls[-1] / prompt_calls[0] if prompt_calls[0] else 0.0
    return increasing_share * 100.0 + growth + math.log1p(sum(prompt_calls)) / 10.0


def choose_accumulation_examples(df: pd.DataFrame, max_examples: int = 3) -> pd.DataFrame:
    tolerance = 1e-6
    candidates = df[
        df["prompt_calls"].apply(lambda x: isinstance(x, list) and len(x) >= 4)
        & df["first_call_prompt_tokens"].gt(0)
        & df["prompt_tokens"].notna()
        & ((df["prompt_calls_sum"] - df["prompt_tokens"]).abs() <= tolerance)
    ].copy()
    if candidates.empty:
        raise ValueError("No trajectories with exact per-call prompt-token sums were available for Figure 2.")

    targets = [
        ("codex", "gpt-5.6-luna", "2.1"),
        ("gemini-cli", "gemini-3-pro-preview", "2.1"),
        ("terminus-2", "claude-opus-4-7", "2.1"),
    ]
    selected: list[pd.Series] = []
    used_paths: set[str] = set()
    candidates["accumulation_score"] = candidates["prompt_calls"].apply(accumulation_score)

    for scaffold, model, version in targets:
        subset = candidates[
            candidates["scaffold"].eq(scaffold)
            & candidates["model_dir"].eq(model)
            & candidates["benchmark_version"].eq(version)
        ].sort_values("accumulation_score", ascending=False)
        if not subset.empty:
            row = subset.iloc[0]
            selected.append(row)
            used_paths.add(str(row["trajectory_path"]))

    if len(selected) < max_examples:
        remaining = candidates[~candidates["trajectory_path"].isin(used_paths)].sort_values(
            "accumulation_score", ascending=False
        )
        for _, row in remaining.head(max_examples - len(selected)).iterrows():
            selected.append(row)

    return pd.DataFrame(selected[:max_examples]).reset_index(drop=True)


def plot_input_accumulation(examples: pd.DataFrame, out: Path) -> None:
    thesis_style()
    fig, axes = plt.subplots(len(examples), 1, figsize=(7.4, 6.2), sharex=False)
    if len(examples) == 1:
        axes = [axes]
    for ax, row in zip(axes, examples.itertuples(index=False)):
        calls = list(row.prompt_calls)
        x = np.arange(1, len(calls) + 1)
        ax.plot(x, np.array(calls) / 1000.0, marker="o", linewidth=1.8, color=PASS_COLOR)
        ax.fill_between(x, np.array(calls) / 1000.0, color=PASS_COLOR, alpha=0.12)
        ax.set_ylabel("Input tokens\n(thousands)")
        ax.grid(axis="y", color="#E5E5E5", linewidth=0.8)
        ax.text(
            0.99,
            0.06,
            f"Cumulative input: {format_millions(row.prompt_tokens)} tokens across {len(calls)} calls",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9.5,
            bbox={"facecolor": "white", "edgecolor": "#DDDDDD", "boxstyle": "round,pad=0.25"},
        )
        ax.set_xlim(1, len(calls))
    axes[-1].set_xlabel("Model call index")
    paper_axis_labels(fig)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    save_paper_figure(fig, out, bbox_inches="tight", dpi=300)
    plt.close(fig)


def plot_input_context_distribution(eligible: pd.DataFrame, out: Path) -> None:
    thesis_style()
    fig, ax_dist = plt.subplots(figsize=(7.6, max(4.0, 0.42 * eligible["scaffold"].nunique() + 1.5) - 0.35))
    counts = eligible["scaffold"].value_counts()
    scaffold_order = [
        scaffold
        for scaffold in [
            "codex",
            "gemini-cli",
            "claude-code",
            "terminus-2",
            "mini-swe-agent",
            "openhands",
            "terminus-3-3",
            "terminus-kira-env-bootstrap",
            "judy",
        ]
        if scaffold in counts.index
    ]
    scaffold_order.extend([scaffold for scaffold in counts.index if scaffold not in scaffold_order])
    distribution = []
    labels = []
    for scaffold in scaffold_order:
        values = task_balanced_values(eligible[eligible["scaffold"].eq(scaffold)], "final_to_first_prompt_ratio")
        if values.empty:
            continue
        distribution.append(values.to_numpy())
        labels.append(f"{scaffold_label(scaffold)} ({len(values):,} tasks)")
    ax_dist.boxplot(
        distribution,
        vert=False,
        tick_labels=labels,
        showfliers=False,
        patch_artist=True,
        boxprops={"facecolor": "#D7E3EF", "edgecolor": PASS_COLOR},
        medianprops={"color": PASS_COLOR, "linewidth": 1.5},
        whiskerprops={"color": PASS_COLOR},
        capprops={"color": PASS_COLOR},
    )
    ax_dist.axvline(1.0, color="#777777", linestyle="--", linewidth=1.0)
    ax_dist.set_xlabel("Submission-balanced task median of\nfinal / first call input")
    ax_dist.grid(axis="x", color="#E5E5E5", linewidth=0.8)
    ax_dist.set_xscale("symlog", linthresh=1.0)
    ax_dist.set_xlim(left=0)

    paper_axis_labels(fig)

    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    save_paper_figure(fig, out, bbox_inches="tight", dpi=300)
    plt.close(fig)


def print_table_1(comparisons: pd.DataFrame) -> None:
    print("\nTable 1 - Longitudinal token growth")
    rows = []
    for row in comparisons.itertuples(index=False):
        rows.append(
            {
                "Comparison": comparison_label(row),
                "Input earlier -> later": format_arrow(row.prompt_tokens_earlier, row.prompt_tokens_later),
                "Input Delta%": format_pct(row.prompt_tokens_change_pct),
                "Output earlier -> later": format_arrow(row.completion_tokens_earlier, row.completion_tokens_later),
                "Output Delta%": format_pct(row.completion_tokens_change_pct),
                "Total earlier -> later": format_arrow(row.total_tokens_earlier, row.total_tokens_later),
                "Total Delta%": format_pct(row.total_tokens_change_pct),
                "Logged chars Delta%": format_pct(row.logged_chars_change_pct),
            }
        )
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    trajectories = read_trajectories(args.trajectory_csv)
    monthly_token_text, monthly_baseline = build_monthly_token_text_summary(trajectories)
    monthly_csv_path = args.out_dir / MONTHLY_TOKEN_TEXT_CSV.name
    monthly_fig_path = args.figures_dir / TOKEN_TEXT_OVER_TIME_FIG.name
    monthly_token_text["date_variable"] = "historical_leaderboard_timestamp"
    monthly_token_text["date_semantics"] = "historical snapshot metadata.date; submission/publication meaning unverified"
    monthly_token_text.to_csv(monthly_csv_path, index=False, na_rep="NA")
    plot_token_text_over_time(monthly_token_text, monthly_fig_path)
    print_monthly_token_text_summary(monthly_token_text, monthly_baseline, monthly_csv_path, monthly_fig_path)

    if args.monthly_only:
        return

    selected = select_rows_for_analysis(trajectories)
    print(f"Selected {selected.shape[0]:,} trajectories from {len(COMPARISONS)} clean model progressions.")

    print(f"Scanning {trajectories.shape[0]:,} trajectories for expanded input-context accumulation.")
    parsed_all = parse_raw_metrics(trajectories, args.trajectory_root, args.workers)
    parsed = parsed_all.merge(selected[["benchmark", "rel_path"]], on=["benchmark", "rel_path"],
                              how="inner", validate="one_to_one")
    validation = validate_metrics(parsed)
    comparisons = build_comparisons(parsed) if args.include_comparisons else None
    all_context_eligible = context_accumulation_trajectory_metrics(parsed_all)
    context_summary = summarize_context_accumulation(all_context_eligible)
    audit = context_audit(parsed_all, all_context_eligible)
    context_summary.to_csv(args.out_dir / INPUT_CONTEXT_SUMMARY_CSV.name, index=False)
    (args.out_dir / INPUT_CONTEXT_AUDIT_JSON.name).write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )

    examples = choose_accumulation_examples(parsed)
    accumulation_bad = examples[
        (examples["prompt_calls_sum"] - examples["prompt_tokens"]).abs() > 1e-6
    ]
    if not accumulation_bad.empty:
        raise ValueError("Figure 2 example validation failed: per-call prompt sums do not match trajectory totals.")

    if args.include_comparisons:
        comparisons.to_csv(args.out_dir / COMPARISONS_CSV.name, index=False, na_rep="NA")
    plot_input_accumulation(examples, args.figures_dir / INPUT_ACCUMULATION_FIG.name)
    plot_input_context_distribution(
        all_context_eligible,
        args.figures_dir / INPUT_CONTEXT_DISTRIBUTION_FIG.name,
    )

    print("\nValidation")
    for key, value in validation.items():
        print(f"{key}: {value}")
    print(f"input_accumulation_examples_checked: {len(examples)}")
    print("input_accumulation_sum_invalid: 0")
    print("\nInput-context audit")
    print(f"total_trajectories_scanned: {audit['total_trajectories_scanned']:,}")
    print(f"any_per_call_prompt_metrics: {audit['any_per_call_prompt_metrics']:,}")
    print(f"at_least_two_valid_prompt_calls: {audit['at_least_two_valid_prompt_calls']:,}")
    print(f"eligible_trajectories: {audit['eligible_trajectories']:,}")
    print(f"excluded_nonpositive_first_prompt: {audit['excluded_nonpositive_first_prompt']:,}")
    print(f"exact_sum_match_rate_overall: {audit['exact_sum_match_rate_overall']:.1f}%")
    print("\nInput-context accumulation summary")
    print("Eligibility: at least two recorded prompt-token counts, a positive first count, and an available trajectory prompt-token total.")
    print(context_summary.to_string(index=False, float_format=lambda value: f"{value:.1f}"))

    print("\nInput-accumulation trajectories")
    for row in examples.itertuples(index=False):
        print(
            f"- {scaffold_label(row.scaffold)} / {model_label(row.model_dir)} / {row.task_name}: "
            f"{row.prompt_call_count} calls, sum={format_value(row.prompt_tokens)}, {row.trajectory_path}"
        )

    if args.include_comparisons:
        print_table_1(comparisons)

    print("\nFiles written")
    print(f"- {monthly_csv_path}")
    print(f"- {monthly_fig_path}")
    if args.include_comparisons:
        print(f"- {args.out_dir / COMPARISONS_CSV.name}")
    print(f"- {args.out_dir / INPUT_CONTEXT_SUMMARY_CSV.name}")
    print(f"- {args.out_dir / INPUT_CONTEXT_AUDIT_JSON.name}")
    print(f"- {args.figures_dir / INPUT_ACCUMULATION_FIG.name}")
    print(f"- {args.figures_dir / INPUT_CONTEXT_DISTRIBUTION_FIG.name}")


if __name__ == "__main__":
    main()
