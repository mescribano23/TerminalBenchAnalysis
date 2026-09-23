#!/usr/bin/env python3
"""Read-only longitudinal model-population audit for Terminal-Bench.

This script intentionally writes only inside its containing audit directory.
It reads the existing processed summaries, raw leaderboard metadata, raw
trajectory indexes, and raw trajectory JSON files.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_PATH = Path(__file__).resolve()
OUT_DIR = SCRIPT_PATH.parent
REPO_ROOT = SCRIPT_PATH.parents[4]
DATA_DIR = REPO_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed_live"
RAW_DIR = DATA_DIR / "raw"
INDEX_DIR = DATA_DIR / "indexes"
TRAJ_DIR = DATA_DIR / "trajectories"

BENCHMARKS = [
    ("terminal_bench_2_0", "TB2.0"),
    ("terminal_bench_2_1", "TB2.1"),
    ("terminal_bench_3_0", "TB3.0"),
    ("terminal_bench_4_0", "TB4.0"),
]
VERSION_ORDER = {label: idx for idx, (_, label) in enumerate(BENCHMARKS)}

TOKEN_KEY_RE = re.compile(r"token", re.IGNORECASE)
REASONING_KEY_RE = re.compile(r"reason", re.IGNORECASE)
THINKING_KEY_RE = re.compile(r"think|thought", re.IGNORECASE)
CACHED_KEY_RE = re.compile(r"cache|cached", re.IGNORECASE)
TIMESTAMP_KEY_RE = re.compile(r"(^timestamp$|_at$|date$|time$)", re.IGNORECASE)
JSON_TOKEN_FIELD_RE = re.compile(
    r'"([^"\\]*(?:token|Token)[^"\\]*)"\s*:\s*(null|-?\d+(?:\.\d+)?|"[^"\\]*")'
)
JSON_TIMESTAMP_FIELD_RE = re.compile(
    r'"([^"\\]*(?:timestamp|_at|date|time)[^"\\]*)"\s*:\s*"([^"\\]+)"',
    re.IGNORECASE,
)


def write_csv(df: pd.DataFrame, name: str) -> Path:
    path = OUT_DIR / name
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {path}")
    df.to_csv(path, index=False)
    return path


def write_text(text: str, name: str) -> Path:
    path = OUT_DIR / name
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {path}")
    path.write_text(text, encoding="utf-8")
    return path


def normalize_date(value: Any) -> str:
    if value in {"", None} or (isinstance(value, float) and math.isnan(value)):
        return ""
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return ""
    return ts.date().isoformat()


def normalize_timestamp(value: Any) -> str:
    if value in {"", None} or (isinstance(value, float) and math.isnan(value)):
        return ""
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return ""
    return ts.isoformat()


def median_date(values: pd.Series) -> str:
    parsed = pd.to_datetime(values.dropna().astype(str), errors="coerce", utc=True).dropna()
    if parsed.empty:
        return ""
    return parsed.sort_values().iloc[len(parsed) // 2].date().isoformat()


def join_distinct(values: Any, limit: int | None = None) -> str:
    if isinstance(values, pd.Series):
        raw_values = values.tolist()
    else:
        raw_values = list(values)
    seen: list[str] = []
    for value in raw_values:
        if value in {"", None}:
            continue
        if isinstance(value, float) and math.isnan(value):
            continue
        text = str(value)
        if text and text not in seen:
            seen.append(text)
    seen.sort()
    if limit is not None and len(seen) > limit:
        return "; ".join(seen[:limit]) + f"; ... (+{len(seen) - limit} more)"
    return "; ".join(seen)


def pct(n: float, d: float) -> float:
    if not d:
        return np.nan
    return 100.0 * n / d


def parse_row_id(url: Any) -> str:
    text = str(url or "").strip().rstrip("/")
    marker = "/rows/"
    if marker in text:
        return text.rsplit(marker, 1)[-1]
    return ""


def load_processed() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for benchmark, label in BENCHMARKS:
        path = PROCESSED_DIR / benchmark / "trajectory_summary.csv"
        df = pd.read_csv(path, low_memory=False)
        df["benchmark_version"] = label
        df["benchmark"] = benchmark
        for col in [
            "reward",
            "step_count",
            "tool_call_count",
            "shell_invocation_count",
            "message_chars",
            "reasoning_chars",
            "observation_chars",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost_usd",
            "duration_seconds",
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["model"] = df["model_name"].astype("string").fillna("")
        df["task_for_count"] = df["task_name"].astype("string").fillna("")
        df.loc[df["task_for_count"].eq(""), "task_for_count"] = df["file_task_id"].astype("string").fillna("")
        df["logged_readable_chars"] = (
            df["message_chars"].fillna(0)
            + df["reasoning_chars"].fillna(0)
            + df["observation_chars"].fillna(0)
        )
        df["tokens_per_logged_char"] = np.where(
            (df["total_tokens"] > 0) & (df["logged_readable_chars"] > 0),
            df["total_tokens"] / df["logged_readable_chars"],
            np.nan,
        )
        df["cost_usd_positive"] = df["cost_usd"].where(df["cost_usd"] > 0)
        df["passed"] = df["reward"].eq(1.0)
        df["leaderboard_date_raw"] = df["leaderboard_date"].astype("string").fillna("")
        df["leaderboard_date_iso"] = df["leaderboard_date_raw"].map(normalize_date)
        df["source_row_id"] = df["source_submission_url"].map(parse_row_id)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_trials() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for benchmark, label in BENCHMARKS:
        path = RAW_DIR / benchmark / "leaderboard_trials.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue
        for entry in data:
            if not isinstance(entry, dict):
                continue
            submission = entry.get("submission") if isinstance(entry.get("submission"), dict) else {}
            rows.append(
                {
                    "benchmark": benchmark,
                    "benchmark_version": label,
                    "file_run_id": str(entry.get("id") or ""),
                    "trial_harbor_row_id": entry.get("harbor_leaderboard_row_id", ""),
                    "trial_started_at_raw": entry.get("started_at", ""),
                    "trial_finished_at_raw": entry.get("finished_at", ""),
                    "trial_started_at_iso": normalize_timestamp(entry.get("started_at", "")),
                    "trial_finished_at_iso": normalize_timestamp(entry.get("finished_at", "")),
                    "trial_started_date_iso": normalize_date(entry.get("started_at", "")),
                    "trial_finished_date_iso": normalize_date(entry.get("finished_at", "")),
                    "trial_job_id": entry.get("job_id", ""),
                    "trial_job_name": entry.get("job_name", ""),
                    "trial_job_title": entry.get("job_title", ""),
                    "trial_status": entry.get("status", ""),
                    "trial_error_type": entry.get("error_type", ""),
                    "trial_agent_name": entry.get("agent_name", ""),
                    "trial_agent_version": entry.get("agent_version", ""),
                    "trial_model_name": entry.get("model_name", ""),
                    "trial_input_tokens": entry.get("input_tokens", ""),
                    "trial_output_tokens": entry.get("output_tokens", ""),
                    "trial_cache_tokens": entry.get("cache_tokens", ""),
                    "trial_cost_usd": entry.get("cost_usd", ""),
                    "trial_submission_scaffold": submission.get("scaffold", ""),
                    "trial_submission_scaffold_version": submission.get("scaffold_version", ""),
                    "trial_submission_model": submission.get("model", ""),
                    "trial_submission_provider": submission.get("provider", ""),
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(["benchmark", "file_run_id"], keep="first")


def classify_token_key(key: str) -> tuple[bool, bool, bool]:
    has_token = bool(TOKEN_KEY_RE.search(key))
    if not has_token:
        return False, False, False
    return (
        bool(REASONING_KEY_RE.search(key)),
        bool(THINKING_KEY_RE.search(key)),
        bool(CACHED_KEY_RE.search(key)),
    )


def numeric_value(value: Any) -> float | None:
    if value in {"", None}:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def scan_trajectory(row: dict[str, Any]) -> dict[str, Any]:
    path = TRAJ_DIR / row["benchmark"] / str(row["rel_path"])
    path = Path(str(path).replace("\\", "/"))
    out: dict[str, Any] = {
        "benchmark": row["benchmark"],
        "rel_path": row["rel_path"],
        "reasoning_token_field_present_trajectory": False,
        "thinking_token_field_present_trajectory": False,
        "cached_token_field_present_trajectory": False,
        "reasoning_or_thinking_nonzero_trajectory": False,
        "reasoning_token_fields_observed": "",
        "thinking_token_fields_observed": "",
        "cached_token_fields_observed": "",
        "reasoning_thinking_token_fields_observed": "",
        "all_token_fields_observed": "",
        "trajectory_first_timestamp_raw": "",
        "trajectory_last_timestamp_raw": "",
        "trajectory_first_timestamp_iso": "",
        "trajectory_last_timestamp_iso": "",
        "trajectory_timestamp_field_names": "",
        "reasoning_thinking_field_values_json": "{}",
    }
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        out["trajectory_scan_error"] = str(exc)
        return out

    reason_fields: set[str] = set()
    think_fields: set[str] = set()
    cache_fields: set[str] = set()
    all_token_fields: set[str] = set()
    rt_sums: dict[str, float] = {}
    timestamps: list[tuple[str, str]] = []
    timestamp_field_names: set[str] = set()

    for key, raw_value in JSON_TIMESTAMP_FIELD_RE.findall(text):
        normalized = normalize_timestamp(raw_value)
        if normalized:
            timestamps.append((raw_value, normalized))
            timestamp_field_names.add(key)

    for key, raw_value in JSON_TOKEN_FIELD_RE.findall(text):
        is_reason, is_think, is_cache = classify_token_key(key)
        all_token_fields.add(key)
        if not (is_reason or is_think or is_cache):
            continue
        if is_reason:
            reason_fields.add(key)
        if is_think:
            think_fields.add(key)
        if is_cache:
            cache_fields.add(key)
        if is_reason or is_think:
            value_number = numeric_value(raw_value.strip('"'))
            if value_number is not None:
                rt_sums[key] = rt_sums.get(key, 0.0) + value_number

    if timestamps:
        timestamps.sort(key=lambda item: item[1])
        out["trajectory_first_timestamp_raw"] = timestamps[0][0]
        out["trajectory_last_timestamp_raw"] = timestamps[-1][0]
        out["trajectory_first_timestamp_iso"] = timestamps[0][1]
        out["trajectory_last_timestamp_iso"] = timestamps[-1][1]
        out["trajectory_timestamp_field_names"] = join_distinct(timestamp_field_names, 25)

    rt_fields = sorted(reason_fields | think_fields)
    out["reasoning_token_field_present_trajectory"] = bool(reason_fields)
    out["thinking_token_field_present_trajectory"] = bool(think_fields)
    out["cached_token_field_present_trajectory"] = bool(cache_fields)
    out["reasoning_or_thinking_nonzero_trajectory"] = any(value > 0 for value in rt_sums.values())
    out["reasoning_token_fields_observed"] = "; ".join(sorted(reason_fields))
    out["thinking_token_fields_observed"] = "; ".join(sorted(think_fields))
    out["cached_token_fields_observed"] = "; ".join(sorted(cache_fields))
    out["reasoning_thinking_token_fields_observed"] = "; ".join(rt_fields)
    out["all_token_fields_observed"] = "; ".join(sorted(all_token_fields))
    out["reasoning_thinking_field_values_json"] = json.dumps(rt_sums, sort_keys=True)
    return out


def scan_all_trajectories(df: pd.DataFrame) -> pd.DataFrame:
    """Return targeted raw-token metadata without full-corpus raw scanning.

    The full trajectory corpus is roughly 35 GB. The complete trajectory-level
    effort/timing counts already come from processed summaries and Harbor trial
    rows; here we only add exact raw reasoning/thinking token evidence for the
    TB4.0 configuration directories where direct key searches found explicit
    fields.
    """
    base = df[["benchmark", "rel_path"]].copy()
    for col, value in {
        "reasoning_token_field_present_trajectory": False,
        "thinking_token_field_present_trajectory": False,
        "cached_token_field_present_trajectory": False,
        "reasoning_or_thinking_nonzero_trajectory": False,
        "reasoning_token_fields_observed": "",
        "thinking_token_fields_observed": "",
        "cached_token_fields_observed": "",
        "reasoning_thinking_token_fields_observed": "",
        "all_token_fields_observed": "",
        "trajectory_first_timestamp_raw": "",
        "trajectory_last_timestamp_raw": "",
        "trajectory_first_timestamp_iso": "",
        "trajectory_last_timestamp_iso": "",
        "trajectory_timestamp_field_names": "",
        "reasoning_thinking_field_values_json": "{}",
    }.items():
        base[col] = value

    targets = (
        ("terminal_bench_4_0", "mini-swe-agent/gemini-3.8-flash", "reasoning_tokens", r"reasoning_tokens.: *[0-9]+"),
        ("terminal_bench_4_0", "grok-build/grok-4.6", "total_reasoning_tokens", r"total_reasoning_tokens.: *[0-9]+"),
        ("terminal_bench_4_0", "claude-code", "thinking_tokens", r"thinking_tokens.: *[0-9]+"),
    )
    rel_to_idx = {
        (row.benchmark, str(row.rel_path).replace("\\", "/")): idx
        for idx, row in base.iterrows()
    }
    for benchmark, rel_prefix, expected_field, pattern in targets:
        root = TRAJ_DIR / benchmark / rel_prefix
        if not root.exists():
            continue
        search_root = root.relative_to(REPO_ROOT).as_posix()
        command = ["rg", "--path-separator", "/", "-o", pattern, search_root]
        result = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True)
        if result.returncode not in {0, 1}:
            continue
        per_file: dict[str, float] = {}
        for line in result.stdout.splitlines():
            if ":" not in line:
                continue
            path_text, match_text = line.split(":", 1)
            value_match = re.search(r"([0-9]+)$", match_text.strip())
            if not value_match:
                continue
            norm_path = path_text.replace("\\", "/")
            marker = f"data/trajectories/{benchmark}/"
            if marker not in norm_path:
                continue
            rel = norm_path.split(marker, 1)[1]
            per_file[rel] = per_file.get(rel, 0.0) + float(value_match.group(1))
        for rel, total_value in per_file.items():
            idx = rel_to_idx.get((benchmark, rel))
            if idx is None:
                continue
            sums = {expected_field: total_value}
            fields = [expected_field]
            reason_fields = [field for field in fields if "reason" in field.lower()]
            think_fields = [field for field in fields if "think" in field.lower()]
            base.at[idx, "reasoning_token_field_present_trajectory"] = bool(reason_fields)
            base.at[idx, "thinking_token_field_present_trajectory"] = bool(think_fields)
            base.at[idx, "reasoning_or_thinking_nonzero_trajectory"] = any(value > 0 for value in sums.values())
            base.at[idx, "reasoning_token_fields_observed"] = "; ".join(reason_fields)
            base.at[idx, "thinking_token_fields_observed"] = "; ".join(think_fields)
            base.at[idx, "reasoning_thinking_token_fields_observed"] = "; ".join(fields)
            base.at[idx, "all_token_fields_observed"] = "; ".join(fields)
            base.at[idx, "reasoning_thinking_field_values_json"] = json.dumps(sums, sort_keys=True)

    return base


def add_audit_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["trajectory_first_date_iso"] = df["trajectory_first_timestamp_iso"].map(normalize_date)
    df["trajectory_last_date_iso"] = df["trajectory_last_timestamp_iso"].map(normalize_date)

    def pick(row: pd.Series) -> pd.Series:
        if row.get("leaderboard_date_iso"):
            return pd.Series(["leaderboard_date", row.get("leaderboard_date_raw", ""), row.get("leaderboard_date_iso", "")])
        if row.get("trial_started_date_iso"):
            return pd.Series(["trial_started_at", row.get("trial_started_at_raw", ""), row.get("trial_started_date_iso", "")])
        if row.get("trajectory_first_date_iso"):
            return pd.Series(["trajectory_first_step_timestamp", row.get("trajectory_first_timestamp_raw", ""), row.get("trajectory_first_date_iso", "")])
        return pd.Series(["missing", "", ""])

    df[["audit_date_source", "audit_date_raw", "audit_date_iso"]] = df.apply(pick, axis=1)
    return df


def agg_config(df: pd.DataFrame) -> pd.DataFrame:
    total_by_version = df.groupby("benchmark_version").size().to_dict()

    def summarize(group: pd.DataFrame) -> pd.Series:
        total = total_by_version[group.name[0]]
        total_token_present = group["total_tokens"].notna().sum()
        cost_present = group["cost_usd"].notna().sum()
        rt_nonzero = group["reasoning_or_thinking_nonzero_trajectory"].sum()
        distinct_submission_ids = group["effective_submission_id"].dropna().astype(str)
        raw_dates = group["leaderboard_date_raw"]
        iso_dates = group["leaderboard_date_iso"]
        return pd.Series(
            {
                "n_trajectories": len(group),
                "percentage_of_version_trajectories": pct(len(group), total),
                "n_tasks": group["task_for_count"].nunique(),
                "pass_rate": group["passed"].mean(),
                "median_steps": group["step_count"].median(),
                "median_shell_invocations": group["shell_invocation_count"].median(),
                "median_structured_tool_calls": group["tool_call_count"].median(),
                "median_duration_seconds": group["duration_seconds"].median(),
                "median_logged_readable_chars": group["logged_readable_chars"].median(),
                "median_input_tokens": group["prompt_tokens"].median(),
                "median_output_tokens": group["completion_tokens"].median(),
                "median_total_tokens": group["total_tokens"].median(),
                "median_tokens_per_logged_char": group["tokens_per_logged_char"].median(),
                "median_cost_usd_positive": group["cost_usd_positive"].median(),
                "n_with_total_tokens": int(total_token_present),
                "pct_missing_total_tokens": pct(len(group) - total_token_present, len(group)),
                "n_with_cost": int(cost_present),
                "pct_missing_cost": pct(len(group) - cost_present, len(group)),
                "earliest_submission_date": join_distinct(iso_dates[iso_dates.ne("")].sort_values().head(1)),
                "latest_submission_date": join_distinct(iso_dates[iso_dates.ne("")].sort_values().tail(1)),
                "median_submission_date": median_date(iso_dates),
                "all_distinct_submission_dates_raw": join_distinct(raw_dates),
                "all_distinct_submission_dates_iso": join_distinct(iso_dates),
                "number_of_distinct_submissions": distinct_submission_ids.nunique(),
                "submission_source_identifiers": join_distinct(distinct_submission_ids, 30),
                "source_submission_url": join_distinct(group["source_submission_url"], 30),
                "scaffold_version": join_distinct(group["source_scaffold_version"]),
                "model_version_string_or_identifier": str(group.name[2]),
                "model_dir_values": join_distinct(group["model_dir"]),
                "leaderboard_model_values": join_distinct(group["leaderboard_model"]),
                "leaderboard_provider_values": join_distinct(group["leaderboard_provider"]),
                "trial_started_at_earliest": join_distinct(group["trial_started_at_iso"].dropna().sort_values().head(1)),
                "trial_started_at_latest": join_distinct(group["trial_started_at_iso"].dropna().sort_values().tail(1)),
                "trial_finished_at_earliest": join_distinct(group["trial_finished_at_iso"].dropna().sort_values().head(1)),
                "trial_finished_at_latest": join_distinct(group["trial_finished_at_iso"].dropna().sort_values().tail(1)),
                "trajectory_first_timestamp_earliest": join_distinct(group["trajectory_first_timestamp_iso"].dropna().sort_values().head(1)),
                "trajectory_last_timestamp_latest": join_distinct(group["trajectory_last_timestamp_iso"].dropna().sort_values().tail(1)),
                "audit_date_source_values": join_distinct(group["audit_date_source"]),
                "earliest_audit_date": join_distinct(group["audit_date_iso"][group["audit_date_iso"].ne("")].sort_values().head(1)),
                "latest_audit_date": join_distinct(group["audit_date_iso"][group["audit_date_iso"].ne("")].sort_values().tail(1)),
                "reasoning_token_field_present": bool(group["reasoning_token_field_present_trajectory"].any()),
                "thinking_token_field_present": bool(group["thinking_token_field_present_trajectory"].any()),
                "cached_token_field_present": bool(group["cached_token_field_present_trajectory"].any()),
                "reasoning_or_thinking_nonzero_trajectory_count": int(rt_nonzero),
                "reasoning_or_thinking_nonzero_percentage": pct(rt_nonzero, len(group)),
                "reasoning_thinking_token_fields_observed": join_distinct(
                    "; ".join(group["reasoning_thinking_token_fields_observed"].dropna()).split("; ")
                ),
                "cached_token_fields_observed": join_distinct(
                    "; ".join(group["cached_token_fields_observed"].dropna()).split("; ")
                ),
            }
        )

    result = (
        df.groupby(["benchmark_version", "scaffold", "model"], dropna=False)
        .apply(summarize, include_groups=False)
        .reset_index()
    )
    result["_version_order"] = result["benchmark_version"].map(VERSION_ORDER)
    return result.sort_values(["_version_order", "scaffold", "model"]).drop(columns="_version_order")


def agg_model_population(df: pd.DataFrame) -> pd.DataFrame:
    total_by_version = df.groupby("benchmark_version").size().to_dict()
    rows: list[dict[str, Any]] = []
    for version, group in df.groupby("benchmark_version"):
        total = total_by_version[version]
        for model, mg in group.groupby("model", dropna=False):
            rows.append(
                {
                    "benchmark_version": version,
                    "model": model,
                    "n_trajectories": len(mg),
                    "percentage_of_version_trajectories": pct(len(mg), total),
                    "unique_scaffolds_for_model": mg["scaffold"].nunique(),
                    "earliest_submission_or_run_date": join_distinct(mg["audit_date_iso"][mg["audit_date_iso"].ne("")].sort_values().head(1)),
                    "latest_submission_or_run_date": join_distinct(mg["audit_date_iso"][mg["audit_date_iso"].ne("")].sort_values().tail(1)),
                    "date_source_values": join_distinct(mg["audit_date_source"]),
                }
            )
    result = pd.DataFrame(rows)
    result["_version_order"] = result["benchmark_version"].map(VERSION_ORDER)
    return result.sort_values(["_version_order", "n_trajectories", "model"], ascending=[True, False, True]).drop(columns="_version_order")


def model_entry_exit(model_pop: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    all_models = sorted(model_pop["model"].dropna().unique())
    counts = {
        (row.benchmark_version, row.model): row.n_trajectories
        for row in model_pop.itertuples(index=False)
    }
    for model in all_models:
        subset = model_pop[model_pop["model"].eq(model)]
        present_versions = sorted(subset["benchmark_version"], key=lambda v: VERSION_ORDER[v])
        first = present_versions[0] if present_versions else ""
        rows.append(
            {
                "model": model,
                "present_in_TB2.0": "TB2.0" in present_versions,
                "present_in_TB2.1": "TB2.1" in present_versions,
                "present_in_TB3.0": "TB3.0" in present_versions,
                "present_in_TB4.0": "TB4.0" in present_versions,
                "n_TB2.0": counts.get(("TB2.0", model), 0),
                "n_TB2.1": counts.get(("TB2.1", model), 0),
                "n_TB3.0": counts.get(("TB3.0", model), 0),
                "n_TB4.0": counts.get(("TB4.0", model), 0),
                "earliest_observed_submission_date": join_distinct(subset["earliest_submission_or_run_date"].sort_values().head(1)),
                "latest_observed_submission_date": join_distinct(subset["latest_submission_or_run_date"].sort_values().tail(1)),
                "first_benchmark_version_observed": first,
                "entry_exit_highlight": "; ".join(
                    tag
                    for tag, cond in [
                        ("first_in_TB2.1_relative_to_TB2.0", first == "TB2.1"),
                        ("disappears_after_TB2.0", present_versions == ["TB2.0"]),
                        ("first_in_TB3.0", first == "TB3.0"),
                        ("first_in_TB4.0", first == "TB4.0"),
                    ]
                    if cond
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["first_benchmark_version_observed", "model"])


def scaffold_controlled_changes(configs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    transitions = [("TB2.0", "TB2.1"), ("TB2.1", "TB3.0"), ("TB3.0", "TB4.0")]
    for earlier, later in transitions:
        e = configs[configs["benchmark_version"].eq(earlier)]
        l = configs[configs["benchmark_version"].eq(later)]
        common_scaffolds = sorted(set(e["scaffold"]).intersection(l["scaffold"]))
        for scaffold in common_scaffolds:
            eg = e[e["scaffold"].eq(scaffold)]
            lg = l[l["scaffold"].eq(scaffold)]
            for erow in eg.itertuples(index=False):
                for lrow in lg.itertuples(index=False):
                    rows.append(
                        {
                            "benchmark_transition": f"{earlier} -> {later}",
                            "scaffold": scaffold,
                            "earlier_model": erow.model,
                            "earlier_n": erow.n_trajectories,
                            "earlier_trajectory_share_pct": erow.percentage_of_version_trajectories,
                            "earlier_submission_date_s": erow.all_distinct_submission_dates_iso,
                            "later_model": lrow.model,
                            "later_n": lrow.n_trajectories,
                            "later_trajectory_share_pct": lrow.percentage_of_version_trajectories,
                            "later_submission_date_s": lrow.all_distinct_submission_dates_iso,
                        }
                    )
    return pd.DataFrame(rows)


def token_density_by_model(df: pd.DataFrame) -> pd.DataFrame:
    model_pop = agg_model_population(df)
    rows: list[dict[str, Any]] = []
    totals = df.groupby("benchmark_version").size().to_dict()
    for (version, model), group in df.groupby(["benchmark_version", "model"], dropna=False):
        rows.append(
            {
                "benchmark_version": version,
                "model": model,
                "n_trajectories": len(group),
                "percentage_of_version_trajectories": pct(len(group), totals[version]),
                "earliest_submission_date": join_distinct(group["audit_date_iso"][group["audit_date_iso"].ne("")].sort_values().head(1)),
                "latest_submission_date": join_distinct(group["audit_date_iso"][group["audit_date_iso"].ne("")].sort_values().tail(1)),
                "median_logged_readable_chars": group["logged_readable_chars"].median(),
                "median_input_tokens": group["prompt_tokens"].median(),
                "median_output_tokens": group["completion_tokens"].median(),
                "median_total_tokens": group["total_tokens"].median(),
                "median_tokens_per_logged_char": group["tokens_per_logged_char"].median(),
                "median_steps": group["step_count"].median(),
                "pass_rate": group["passed"].mean(),
                "percentage_with_nonzero_reasoning_or_thinking_tokens": pct(
                    group["reasoning_or_thinking_nonzero_trajectory"].sum(), len(group)
                ),
            }
        )
    result = pd.DataFrame(rows)
    result["_version_order"] = result["benchmark_version"].map(VERSION_ORDER)
    return result.sort_values(["_version_order", "n_trajectories", "model"], ascending=[True, False, True]).drop(columns="_version_order")


def reasoning_thinking_evidence(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        values = json.loads(row["reasoning_thinking_field_values_json"] or "{}")
        for field, value in values.items():
            rows.append(
                {
                    "benchmark_version": row["benchmark_version"],
                    "model": row["model"],
                    "scaffold": row["scaffold"],
                    "submission_or_run_date": row["audit_date_iso"],
                    "token_field_name": field,
                    "trajectory_key": idx,
                    "field_value": value,
                    "output_completion_tokens": row["completion_tokens"],
                    "valid_share": value > 0 and pd.notna(row["completion_tokens"]) and row["completion_tokens"] > 0,
                    "share_of_output_completion_tokens": (
                        value / row["completion_tokens"]
                        if value > 0 and pd.notna(row["completion_tokens"]) and row["completion_tokens"] > 0
                        else np.nan
                    ),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "benchmark_version",
                "model",
                "scaffold",
                "submission_or_run_date_s",
                "n_trajectories",
                "token_field_name",
                "number_with_field_populated",
                "percentage_with_field_populated",
                "number_with_value_gt_0",
                "percentage_with_value_gt_0",
                "median_reasoning_thinking_tokens_among_positive",
                "median_output_completion_tokens",
                "median_reasoning_thinking_share_of_output_completion_tokens",
            ]
        )
    field_df = pd.DataFrame(rows)
    total_group_sizes = df.groupby(["benchmark_version", "model", "scaffold"]).size()
    out_rows: list[dict[str, Any]] = []
    for key, group in field_df.groupby(["benchmark_version", "model", "scaffold", "token_field_name"], dropna=False):
        version, model, scaffold, field = key
        total_n = int(total_group_sizes.loc[(version, model, scaffold)])
        positive = group[group["field_value"] > 0]
        out_rows.append(
            {
                "benchmark_version": version,
                "model": model,
                "scaffold": scaffold,
                "submission_or_run_date_s": join_distinct(group["submission_or_run_date"]),
                "n_trajectories": total_n,
                "token_field_name": field,
                "number_with_field_populated": group["trajectory_key"].nunique(),
                "percentage_with_field_populated": pct(group["trajectory_key"].nunique(), total_n),
                "number_with_value_gt_0": positive["trajectory_key"].nunique(),
                "percentage_with_value_gt_0": pct(positive["trajectory_key"].nunique(), total_n),
                "median_reasoning_thinking_tokens_among_positive": positive["field_value"].median(),
                "median_output_completion_tokens": group["output_completion_tokens"].median(),
                "median_reasoning_thinking_share_of_output_completion_tokens": group[
                    "share_of_output_completion_tokens"
                ].median(),
            }
        )
    result = pd.DataFrame(out_rows)
    result["_version_order"] = result["benchmark_version"].map(VERSION_ORDER)
    return result.sort_values(["_version_order", "model", "scaffold", "token_field_name"]).drop(columns="_version_order")


def chronological_table(df: pd.DataFrame) -> pd.DataFrame:
    total_by_version = df.groupby("benchmark_version").size().to_dict()
    rows: list[dict[str, Any]] = []
    for (date, version, scaffold, model), group in df.groupby(["audit_date_iso", "benchmark_version", "scaffold", "model"], dropna=False):
        rows.append(
            {
                "submission_date": date or "",
                "benchmark_version": version,
                "scaffold": scaffold,
                "model": model,
                "n_trajectories": len(group),
                "percentage_of_version_trajectories": pct(len(group), total_by_version[version]),
                "median_total_tokens": group["total_tokens"].median(),
                "median_tokens_per_logged_char": group["tokens_per_logged_char"].median(),
                "date_source_values": join_distinct(group["audit_date_source"]),
            }
        )
    result = pd.DataFrame(rows)
    result["_date"] = pd.to_datetime(result["submission_date"], errors="coerce")
    result["_version_order"] = result["benchmark_version"].map(VERSION_ORDER)
    return result.sort_values(["_date", "_version_order", "scaffold", "model"], na_position="last").drop(columns=["_date", "_version_order"])


def headline_table(df: pd.DataFrame) -> pd.DataFrame:
    configs = df.groupby(["benchmark_version", "scaffold", "model"]).size().reset_index(name="n")
    rows: list[dict[str, Any]] = []
    for version, group in df.groupby("benchmark_version"):
        model_counts = group["model"].value_counts()
        top5 = model_counts.head(5)
        rows.append(
            {
                "version": version,
                "total_trajectories": len(group),
                "date_range_of_submissions": f"{join_distinct(group['audit_date_iso'][group['audit_date_iso'].ne('')].sort_values().head(1))} to {join_distinct(group['audit_date_iso'][group['audit_date_iso'].ne('')].sort_values().tail(1))}",
                "unique_models": group["model"].nunique(),
                "unique_configs": len(configs[configs["benchmark_version"].eq(version)]),
                "top_5_models_by_trajectory_share": "; ".join(
                    f"{model} ({pct(n, len(group)):.1f}%)" for model, n in top5.items()
                ),
                "share_of_trajectories_from_top_5_models": pct(top5.sum(), len(group)),
                "median_total_tokens": group["total_tokens"].median(),
                "median_logged_chars": group["logged_readable_chars"].median(),
                "median_tokens_logged_char": group["tokens_per_logged_char"].median(),
                "median_steps": group["step_count"].median(),
                "pass_rate": group["passed"].mean(),
            }
        )
    result = pd.DataFrame(rows)
    result["_version_order"] = result["version"].map(VERSION_ORDER)
    return result.sort_values("_version_order").drop(columns="_version_order")


def transition_new_models(df: pd.DataFrame, earlier: str, later: str) -> pd.DataFrame:
    earlier_models = set(df.loc[df["benchmark_version"].eq(earlier), "model"])
    later_df = df[df["benchmark_version"].eq(later)]
    new_df = later_df[~later_df["model"].isin(earlier_models)]
    total_later = len(later_df)
    rows: list[dict[str, Any]] = []
    for model, group in new_df.groupby("model"):
        rows.append(
            {
                "benchmark_transition": f"{earlier} -> {later}",
                "model": model,
                "n_trajectories_in_later_version": len(group),
                "percentage_of_later_version_trajectories": pct(len(group), total_later),
                "median_total_tokens": group["total_tokens"].median(),
                "median_tokens_per_logged_char": group["tokens_per_logged_char"].median(),
                "submission_or_run_date_s": join_distinct(group["audit_date_iso"]),
                "scaffolds": join_distinct(group["scaffold"]),
            }
        )
    return pd.DataFrame(rows).sort_values("n_trajectories_in_later_version", ascending=False)


def model_name_flags(model: str) -> str:
    flags: list[str] = []
    lower = model.lower()
    if "/" in model:
        flags.append("provider_or_namespace_prefix")
    if "preview" in lower:
        flags.append("preview_variant")
    if "custom" in lower:
        flags.append("custom_variant")
    if re.search(r"20\d{6}", model):
        flags.append("dated_snapshot")
    if re.search(r"[-_.](mini|nano|flash|pro|sonnet|opus|haiku|luna|terra|astra|xhigh|max|lightning)\b", lower):
        flags.append("version_or_tier_suffix")
    return "; ".join(flags)


def model_name_audit(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model, group in df.groupby("model", dropna=False):
        rows.append(
            {
                "raw_model_name": model,
                "benchmark_versions": join_distinct(group["benchmark_version"]),
                "scaffolds": join_distinct(group["scaffold"]),
                "observed_submission_or_run_dates": join_distinct(group["audit_date_iso"]),
                "n_trajectories_total": len(group),
                "apparent_alias_preview_snapshot_or_spelling_flags": model_name_flags(str(model)),
            }
        )
    return pd.DataFrame(rows).sort_values("raw_model_name")


def reliability_audit(df: pd.DataFrame, configs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version, group in df.groupby("benchmark_version"):
        rows.append(
            {
                "benchmark_version": version,
                "field_used_as_primary_submission_date": "leaderboard_date from trajectory_summary.csv when available; otherwise trial_started_at; otherwise first trajectory step timestamp",
                "primary_date_source_counts": join_distinct(
                    [f"{k}:{v}" for k, v in group["audit_date_source"].value_counts().items()]
                ),
                "leaderboard_date_nonmissing_trajectory_count": int(group["leaderboard_date_iso"].ne("").sum()),
                "trial_started_at_nonmissing_trajectory_count": int(group["trial_started_at_iso"].fillna("").ne("").sum()),
                "trajectory_step_timestamp_nonmissing_trajectory_count": int(group["trajectory_first_timestamp_iso"].fillna("").ne("").sum()),
                "trajectory_count": len(group),
                "configs_with_multiple_submission_dates": int(
                    configs[configs["benchmark_version"].eq(version)]["all_distinct_submission_dates_iso"]
                    .fillna("")
                    .map(lambda x: len([p for p in x.split("; ") if p]) > 1)
                    .sum()
                ),
                "configs_with_multiple_submission_ids": int(
                    configs[configs["benchmark_version"].eq(version)]["number_of_distinct_submissions"].gt(1).sum()
                ),
                "models_with_multiple_observed_dates": int(
                    group.groupby("model")["audit_date_iso"].agg(lambda s: s[s.ne("")].nunique()).gt(1).sum()
                ),
                "date_missing_trajectory_count": int(group["audit_date_iso"].eq("").sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("benchmark_version", key=lambda s: s.map(VERSION_ORDER))


def notes_text(df: pd.DataFrame, configs: pd.DataFrame, reasoning: pd.DataFrame, reliability: pd.DataFrame) -> str:
    token_fields = {
        version: join_distinct("; ".join(group["all_token_fields_observed"].dropna()).split("; "), 100)
        for version, group in df.groupby("benchmark_version")
    }
    rt_fields = join_distinct(reasoning["token_field_name"].unique()) if not reasoning.empty else ""
    return "\n".join(
        [
            "# Longitudinal model-population audit notes",
            "",
            "Sources used:",
            "- `data/processed_live/{terminal_bench_*}/trajectory_summary.csv`: trajectory rows, scaffold, `model_name`, task, reward, step/tool/shell counts, chars, tokens, cost, duration, leaderboard date, source URL, source scaffold version.",
            "- `data/raw/{terminal_bench_*}/leaderboard_submissions.json` and TB2.0 `leaderboard_submissions_historical.json`: upstream leaderboard dates/URLs summarized into `trajectory_summary.csv`.",
            "- `data/raw/{terminal_bench_2_1,terminal_bench_3_0,terminal_bench_4_0}/leaderboard_trials.json`: Harbor trial `started_at`, `finished_at`, trial status/job metadata, and raw trial token/cost fields where present.",
            "- `data/trajectories/{terminal_bench_*}/**/*.json`: trajectory step timestamps and raw token-accounting field names/values.",
            "",
            "Column choices:",
            "- Model population/configuration tables use exact `model_name` from the processed trajectory summary as `model`; `model_dir` and `leaderboard_model` are retained in detailed outputs as provenance because they can differ.",
            "- `median_logged_readable_chars` is `message_chars + reasoning_chars + observation_chars`, matching existing longitudinal analysis scripts.",
            "- Primary `submission_date`/`audit_date` is `leaderboard_date` when present, then Harbor `trial_started_at`, then first trajectory step timestamp. The date-source column records which fallback was used.",
            "- `median_cost_usd_positive` is computed only over positive costs; `n_with_cost` counts non-missing `cost_usd` values.",
            "",
            "Token schema notes:",
            *[f"- {version}: token-like fields observed in raw trajectories: {fields}" for version, fields in token_fields.items()],
            f"- Explicit reasoning/thinking token fields observed: {rt_fields or 'none'}",
            "- Cache token fields are present in raw trajectory metrics in all four versions, but trial-level `cache_tokens` is available only where Harbor trial rows exist.",
            "",
            "Date reliability:",
            reliability.to_markdown(index=False),
            "",
            "Data-quality cautions:",
            "- Token fields have different schemas across versions and scaffolds; raw trajectory metrics often include provider/scaffold-specific `extra` structures.",
            "- Some trajectories lack `total_tokens` and/or positive cost values, especially where runs were cancelled or no metric steps were parsed.",
            "- Explicit reasoning/thinking token metadata is observable only where provider/scaffold metrics include such fields; absence of a field is not evidence about model capability.",
            "- Trajectory weighting is uneven: benchmark versions contain different numbers of trajectories per model/configuration.",
            "- Leaderboard dates, Harbor trial run timestamps, and trajectory step timestamps are different date concepts and should not be treated as interchangeable without checking `audit_date_source` and the reliability table.",
        ]
    )


def print_table(title: str, df: pd.DataFrame, max_rows: int = 20) -> None:
    print(f"\n## {title}")
    if df.empty:
        print("(empty)")
        return
    display = df.head(max_rows)
    with pd.option_context("display.max_columns", 20, "display.width", 220, "display.max_colwidth", 80):
        print(display.to_string(index=False))
    if len(df) > max_rows:
        print(f"... {len(df) - max_rows} more rows in CSV")


def main() -> None:
    df = load_processed()
    trials = load_trials()
    if not trials.empty:
        df = df.merge(trials, on=["benchmark", "benchmark_version", "file_run_id"], how="left")
    for col in [
        "trial_started_at_raw",
        "trial_finished_at_raw",
        "trial_started_at_iso",
        "trial_finished_at_iso",
        "trial_started_date_iso",
        "trial_finished_date_iso",
    ]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")

    scans = scan_all_trajectories(df)
    df = df.merge(scans, on=["benchmark", "rel_path"], how="left")
    bool_cols = [
        "reasoning_token_field_present_trajectory",
        "thinking_token_field_present_trajectory",
        "cached_token_field_present_trajectory",
        "reasoning_or_thinking_nonzero_trajectory",
    ]
    for col in bool_cols:
        df[col] = df[col].fillna(False).astype(bool)
    if "trial_cache_tokens" in df.columns:
        trial_cache_present = df["trial_cache_tokens"].notna() & df["trial_cache_tokens"].astype("string").fillna("").ne("")
        df["cached_token_field_present_trajectory"] = df["cached_token_field_present_trajectory"] | trial_cache_present
        df.loc[trial_cache_present & df["cached_token_fields_observed"].eq(""), "cached_token_fields_observed"] = "cache_tokens"
    for col in [
        "reasoning_token_fields_observed",
        "thinking_token_fields_observed",
        "cached_token_fields_observed",
        "reasoning_thinking_token_fields_observed",
        "all_token_fields_observed",
        "trajectory_first_timestamp_raw",
        "trajectory_last_timestamp_raw",
        "trajectory_first_timestamp_iso",
        "trajectory_last_timestamp_iso",
        "trajectory_timestamp_field_names",
        "reasoning_thinking_field_values_json",
    ]:
        df[col] = df[col].fillna("")
    df = add_audit_dates(df)

    configs = agg_config(df)
    model_pop = agg_model_population(df)
    entry_exit = model_entry_exit(model_pop)
    scaffold_changes = scaffold_controlled_changes(configs)
    token_density = token_density_by_model(df)
    reasoning = reasoning_thinking_evidence(df)
    chronological = chronological_table(df)
    headline = headline_table(df)
    new_21 = transition_new_models(df, "TB2.0", "TB2.1")
    new_40 = transition_new_models(df, "TB3.0", "TB4.0")
    model_audit = model_name_audit(df)
    reliability = reliability_audit(df, configs)

    trajectory_cols = [
        "benchmark_version",
        "benchmark",
        "rel_path",
        "scaffold",
        "model",
        "model_dir",
        "leaderboard_model",
        "agent_version",
        "source_scaffold_version",
        "source_submission_url",
        "effective_submission_id",
        "task_for_count",
        "file_run_id",
        "reward",
        "passed",
        "step_count",
        "tool_call_count",
        "shell_invocation_count",
        "logged_readable_chars",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "tokens_per_logged_char",
        "cost_usd",
        "duration_seconds",
        "leaderboard_date_raw",
        "leaderboard_date_iso",
        "trial_started_at_raw",
        "trial_finished_at_raw",
        "trial_started_at_iso",
        "trial_finished_at_iso",
        "trajectory_first_timestamp_raw",
        "trajectory_last_timestamp_raw",
        "trajectory_first_timestamp_iso",
        "trajectory_last_timestamp_iso",
        "audit_date_source",
        "audit_date_raw",
        "audit_date_iso",
        "reasoning_token_field_present_trajectory",
        "thinking_token_field_present_trajectory",
        "cached_token_field_present_trajectory",
        "reasoning_or_thinking_nonzero_trajectory",
        "reasoning_token_fields_observed",
        "thinking_token_fields_observed",
        "cached_token_fields_observed",
        "reasoning_thinking_token_fields_observed",
        "all_token_fields_observed",
        "reasoning_thinking_field_values_json",
    ]
    write_csv(df[trajectory_cols], "trajectory_level_enriched_audit.csv")
    write_csv(configs, "config_level_detailed.csv")
    write_csv(model_pop, "A_model_population_by_version.csv")
    write_csv(entry_exit, "B_model_entry_exit.csv")
    write_csv(scaffold_changes, "C_scaffold_controlled_model_changes.csv")
    write_csv(token_density, "D_token_density_by_model.csv")
    write_csv(reasoning, "E_reasoning_thinking_token_evidence.csv")
    write_csv(chronological, "F_chronological_model_population.csv")
    write_csv(pd.concat([new_21, new_40], ignore_index=True), "F_transition_new_models.csv")
    write_csv(headline, "G_composition_weighted_headline.csv")
    write_csv(reliability, "H_submission_date_reliability_audit.csv")
    write_csv(model_audit, "I_model_name_audit.csv")
    write_text(notes_text(df, configs, reasoning, reliability), "J_data_quality_notes.md")

    print_table("G. Composition-Weighted Headline", headline, 10)
    print_table("A. Model Population by Version", model_pop, 80)
    print_table("B. Model Entry/Exit Highlights", entry_exit[entry_exit["entry_exit_highlight"].ne("")], 80)
    print_table("C. Scaffold-Controlled Model Changes", scaffold_changes, 60)
    print_table("D. Token Density by Model", token_density, 80)
    print_table("E. Direct Reasoning/Thinking Token Evidence", reasoning, 80)
    print_table("F. Chronological Model-Population View", chronological, 80)
    print_table("F. Newly Appearing Models in Requested Transitions", pd.concat([new_21, new_40], ignore_index=True), 80)
    print_table("H. Submission-Date Reliability Audit", reliability, 20)
    print_table("I. Model-Name Audit", model_audit, 120)
    print(f"\nWrote audit CSVs and notes to: {OUT_DIR}")


if __name__ == "__main__":
    main()
