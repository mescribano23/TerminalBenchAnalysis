#!/usr/bin/env python3
"""Visible-text/token accounting audit for Terminal-Bench trajectories.

This optional audit tokenizes only the readable text persisted in trajectory
JSON files and compares it with provider-reported token usage. It is meant to
show that visible trajectory text is not a reliable proxy for billed or
reported model tokens.

Outputs:
- data/processed_live/longitudinal/visible_text_token_accounting_summary.csv
- data/processed_live/longitudinal/visible_text_tokenizer_coverage_by_model.csv
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

REPO_ROOT_GUESS = Path(__file__).resolve().parents[3]
if str(REPO_ROOT_GUESS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_GUESS))

from scripts.benchmark_paths import find_repo_root


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
LONGITUDINAL_DIR = REPO_ROOT / "data" / "processed_live" / "longitudinal"
TRAJECTORY_CSV = LONGITUDINAL_DIR / "trajectory_longitudinal.csv"
TRAJECTORY_ROOT = REPO_ROOT / "data" / "trajectories"
SUMMARY_CSV = LONGITUDINAL_DIR / "visible_text_token_accounting_summary.csv"
COVERAGE_CSV = LONGITUDINAL_DIR / "visible_text_tokenizer_coverage_by_model.csv"

MODEL_SOURCES = {"agent", "assistant", "model"}
REASONING_KEYS = ("reasoning_content",)

characterize = importlib.import_module("scripts.analysis.00_characterize_trajectories")
extract_observation_text = characterize.extract_observation_text
textish = characterize.textish


@dataclass(frozen=True)
class TokenizerSpec:
    tokenizer_name: str
    source: str
    policy: str


class TokenizerRegistry:
    """Strict model-specific tokenizer registry.

    We only use tokenizers that directly match the persisted model identifier
    through tiktoken's exact OpenAI model registry. There is no tokenizer-family
    fallback and no characters-per-token approximation.
    """

    def __init__(self) -> None:
        self._specs: dict[str, TokenizerSpec | None] = {}
        self._counters: dict[str, Any] = {}
        self._tiktoken: Any | None = None

    def get_model_specific_tokenizer(self, provider: str, model: str) -> TokenizerSpec | None:
        key = f"{provider}::{model}"
        if key in self._specs:
            return self._specs[key]

        if not model:
            spec = None
        elif provider == "openai":
            spec = self._load_openai_tiktoken(key, model)
        else:
            spec = None

        self._specs[key] = spec
        return spec

    def count_many(self, provider: str, model: str, parts: Iterable[str]) -> float:
        spec = self.get_model_specific_tokenizer(provider, model)
        if spec is None:
            return math.nan
        clean_parts = [part for part in parts if part]
        if not clean_parts:
            return 0.0
        return float(self._counters[f"{provider}::{model}"](clean_parts))

    def _load_openai_tiktoken(self, key: str, model: str) -> TokenizerSpec | None:
        try:
            if self._tiktoken is None:
                import tiktoken

                self._tiktoken = tiktoken
            if model not in self._tiktoken.model.MODEL_TO_ENCODING:
                return None
            encoding = self._tiktoken.encoding_for_model(model)
        except Exception:
            return None

        self._counters[key] = lambda parts, enc=encoding: sum(
            len(tokens) for tokens in enc.encode_ordinary_batch(parts, num_threads=1)
        )
        return TokenizerSpec(
            tokenizer_name=f"tiktoken:{encoding.name}",
            source="openai/tiktoken",
            policy="exact OpenAI model registry match",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-csv", type=Path, default=TRAJECTORY_CSV)
    parser.add_argument("--trajectory-root", type=Path, default=TRAJECTORY_ROOT)
    parser.add_argument("--summary-csv", type=Path, default=SUMMARY_CSV)
    parser.add_argument("--coverage-csv", type=Path, default=COVERAGE_CSV)
    parser.add_argument("--details-csv", type=Path, default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    return parser.parse_args()


def numeric(value: Any) -> float:
    if value in {"", None}:
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def finite(value: float) -> bool:
    return not pd.isna(value) and math.isfinite(float(value))


def safe_ratio(num: float, den: float) -> float:
    if not finite(num) or not finite(den) or den <= 0:
        return math.nan
    return num / den


def median(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").replace([math.inf, -math.inf], math.nan).dropna()
    return float(values.median()) if len(values) else math.nan


def quantile(series: pd.Series, q: float) -> float:
    values = pd.to_numeric(series, errors="coerce").replace([math.inf, -math.inf], math.nan).dropna()
    return float(values.quantile(q)) if len(values) else math.nan


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def collect_persisted_text(data: dict[str, Any]) -> dict[str, list[str]]:
    parts = {
        "messages": [],
        "reasoning": [],
        "observations": [],
        "model_visible": [],
    }
    steps = data.get("steps")
    if not isinstance(steps, list):
        return parts

    for raw_step in steps:
        if not isinstance(raw_step, dict):
            continue
        source = str(raw_step.get("source") or "").lower()
        message = textish(raw_step.get("message"), 20000)
        reasoning = "\n".join(textish(raw_step.get(key), 20000) for key in REASONING_KEYS if raw_step.get(key))
        observation = extract_observation_text(raw_step)

        if message:
            parts["messages"].append(message)
            if source in MODEL_SOURCES:
                parts["model_visible"].append(message)
        if reasoning:
            parts["reasoning"].append(reasoning)
            if source in MODEL_SOURCES:
                parts["model_visible"].append(reasoning)
        if observation:
            parts["observations"].append(observation)

    return parts


def extract_usage(data: dict[str, Any], row: pd.Series) -> dict[str, float]:
    fm = data.get("final_metrics") if isinstance(data.get("final_metrics"), dict) else {}
    prompt = numeric(fm.get("total_prompt_tokens"))
    completion = numeric(fm.get("total_completion_tokens"))
    total = numeric(fm.get("total_tokens"))

    if not finite(prompt):
        prompt = numeric(row.get("prompt_tokens"))
    if not finite(completion):
        completion = numeric(row.get("completion_tokens"))
    if not finite(total):
        total = numeric(row.get("total_tokens"))
    if not finite(total) and finite(prompt) and finite(completion):
        total = prompt + completion

    return {
        "reported_input_tokens": prompt,
        "reported_output_tokens": completion,
        "reported_total_tokens": total,
    }


def read_trajectories(path: Path) -> pd.DataFrame:
    required = {
        "benchmark",
        "benchmark_version",
        "rel_path",
        "scaffold",
        "model_dir",
        "task_name",
        "file_task_id",
        "file_run_id",
        "submission_provider",
        "submission_date",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "message_chars",
        "reasoning_chars",
        "observation_chars",
    }
    df = pd.read_csv(path, usecols=sorted(required), low_memory=False)
    df = df[df["benchmark_version"].astype(str).isin(["2.0", "2.1"])].copy()
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    for column in [
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "message_chars",
        "reasoning_chars",
        "observation_chars",
    ]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["logged_readable_chars"] = (
        df["message_chars"].fillna(0) + df["reasoning_chars"].fillna(0) + df["observation_chars"].fillna(0)
    )
    return df


def tokenizer_coverage(df: pd.DataFrame, registry: TokenizerRegistry) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = (
        df.groupby(["benchmark_version", "submission_provider", "model_dir"], dropna=False)
        .size()
        .reset_index(name="trajectory_count")
        .sort_values(["benchmark_version", "submission_provider", "model_dir"])
    )
    for row in grouped.itertuples(index=False):
        provider = str(row.submission_provider or "").lower()
        model = str(row.model_dir or "")
        spec = registry.get_model_specific_tokenizer(provider, model)
        rows.append(
            {
                "benchmark_version": row.benchmark_version,
                "provider": provider,
                "model_dir": model,
                "trajectory_count": int(row.trajectory_count),
                "model_specific_tokenizer_available": spec is not None,
                "tokenizer_name": spec.tokenizer_name if spec else "",
                "tokenizer_source": spec.source if spec else "",
                "tokenizer_policy": spec.policy if spec else "",
            }
        )
    return pd.DataFrame(rows)


def add_tokenizer_availability(df: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    availability = {
        (row.benchmark_version, row.provider, row.model_dir): bool(row.model_specific_tokenizer_available)
        for row in coverage.itertuples(index=False)
    }
    out = df.copy()
    out["provider"] = out["submission_provider"].fillna("").astype(str).str.lower()
    out["model_specific_tokenizer_available"] = out.apply(
        lambda row: availability[(row["benchmark_version"], row["provider"], str(row["model_dir"] or ""))],
        axis=1,
    )
    return out


def analyze_tokenizable_row(row: pd.Series, registry: TokenizerRegistry, trajectory_root: Path) -> dict[str, Any]:
    provider = str(row.get("provider") or "").lower()
    model = str(row["model_dir"])
    spec = registry.get_model_specific_tokenizer(provider, model)
    if spec is None:
        raise AssertionError("analyze_tokenizable_row called without a tokenizer")

    path = trajectory_root / str(row["benchmark"]) / str(row["rel_path"])
    data = load_json(path)
    text_parts = collect_persisted_text(data)
    visible_parts = text_parts["messages"] + text_parts["reasoning"] + text_parts["observations"]
    visible_text_tokens = registry.count_many(provider, model, visible_parts)
    visible_model_output_tokens = registry.count_many(provider, model, text_parts["model_visible"])
    usage = extract_usage(data, row)

    result: dict[str, Any] = {
        "benchmark_version": row["benchmark_version"],
        "benchmark": row["benchmark"],
        "rel_path": row["rel_path"],
        "task_name": row["task_name"],
        "file_task_id": row["file_task_id"],
        "file_run_id": row["file_run_id"],
        "scaffold": row["scaffold"],
        "model_dir": model,
        "provider": provider,
        "submission_date": row["submission_date"],
        "tokenizer_name": spec.tokenizer_name,
        "tokenizer_source": spec.source,
        "tokenizer_policy": spec.policy,
        "logged_readable_chars": row["logged_readable_chars"],
        "extracted_readable_chars": sum(len(part) for part in visible_parts),
        "visible_text_tokens": visible_text_tokens,
        "visible_model_output_tokens": visible_model_output_tokens,
    }
    result.update(usage)
    result["reported_input_to_visible_text_ratio"] = safe_ratio(
        result["reported_input_tokens"], visible_text_tokens
    )
    result["reported_total_to_visible_text_ratio"] = safe_ratio(
        result["reported_total_tokens"], visible_text_tokens
    )
    result["visible_model_output_to_reported_output_ratio"] = safe_ratio(
        visible_model_output_tokens, result["reported_output_tokens"]
    )
    return result


def build_audit(df: pd.DataFrame, registry: TokenizerRegistry, trajectory_root: Path) -> pd.DataFrame:
    rows = [
        analyze_tokenizable_row(row, registry, trajectory_root)
        for _, row in df[df["model_specific_tokenizer_available"]].iterrows()
    ]
    columns = [
        "benchmark_version",
        "benchmark",
        "rel_path",
        "task_name",
        "file_task_id",
        "file_run_id",
        "scaffold",
        "model_dir",
        "provider",
        "submission_date",
        "tokenizer_name",
        "tokenizer_source",
        "tokenizer_policy",
        "logged_readable_chars",
        "extracted_readable_chars",
        "visible_text_tokens",
        "visible_model_output_tokens",
        "reported_input_tokens",
        "reported_output_tokens",
        "reported_total_tokens",
        "reported_input_to_visible_text_ratio",
        "reported_total_to_visible_text_ratio",
        "visible_model_output_to_reported_output_ratio",
    ]
    audit = pd.DataFrame(rows, columns=columns)
    if audit.empty:
        return audit
    paired = (
        audit["visible_text_tokens"].apply(finite)
        & audit["visible_text_tokens"].gt(0)
        & audit["reported_input_tokens"].apply(finite)
        & audit["reported_total_tokens"].apply(finite)
    )
    return audit[paired].reset_index(drop=True)


def build_summary(df: pd.DataFrame, audit: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version, group in df.groupby("benchmark_version", dropna=False):
        version = str(version)
        version_audit = audit[audit["benchmark_version"].astype(str).eq(version)]
        tokenizer_n = int(group["model_specific_tokenizer_available"].sum())
        rows.append(
            {
                "benchmark_version": version,
                "benchmark_trajectory_count": int(len(group)),
                "n_model_specific_tokenizer": tokenizer_n,
                "model_specific_tokenizer_pct": tokenizer_n / len(group) * 100.0 if len(group) else math.nan,
                "n_paired_visible_text": int(len(version_audit)),
                "median_visible_text_tokens": median(version_audit["visible_text_tokens"]),
                "median_reported_input_tokens": median(version_audit["reported_input_tokens"]),
                "median_reported_output_tokens": median(version_audit["reported_output_tokens"]),
                "median_reported_total_tokens": median(version_audit["reported_total_tokens"]),
                "median_reported_input_to_visible_text_ratio": median(
                    version_audit["reported_input_to_visible_text_ratio"]
                ),
                "q25_reported_input_to_visible_text_ratio": quantile(
                    version_audit["reported_input_to_visible_text_ratio"], 0.25
                ),
                "q75_reported_input_to_visible_text_ratio": quantile(
                    version_audit["reported_input_to_visible_text_ratio"], 0.75
                ),
                "median_reported_total_to_visible_text_ratio": median(
                    version_audit["reported_total_to_visible_text_ratio"]
                ),
                "q25_reported_total_to_visible_text_ratio": quantile(
                    version_audit["reported_total_to_visible_text_ratio"], 0.25
                ),
                "q75_reported_total_to_visible_text_ratio": quantile(
                    version_audit["reported_total_to_visible_text_ratio"], 0.75
                ),
                "median_visible_model_output_to_reported_output_ratio": median(
                    version_audit["visible_model_output_to_reported_output_ratio"]
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("benchmark_version").reset_index(drop=True)


def print_summary(summary: pd.DataFrame, coverage: pd.DataFrame, audit: pd.DataFrame) -> None:
    print("Visible-text tokenizer coverage")
    print(
        summary[
            [
                "benchmark_version",
                "benchmark_trajectory_count",
                "n_model_specific_tokenizer",
                "model_specific_tokenizer_pct",
                "n_paired_visible_text",
            ]
        ].to_csv(index=False)
    )
    print("Available model-specific tokenizers")
    available = coverage[coverage["model_specific_tokenizer_available"]].copy()
    if available.empty:
        print("none")
    else:
        print(
            available[
                [
                    "benchmark_version",
                    "provider",
                    "model_dir",
                    "trajectory_count",
                    "tokenizer_name",
                    "tokenizer_source",
                    "tokenizer_policy",
                ]
            ].to_csv(index=False)
        )
    print("Visible text vs reported tokens")
    if audit.empty:
        print("No paired rows with model-specific tokenizers.")
    else:
        print(
            summary[
                [
                    "benchmark_version",
                    "median_visible_text_tokens",
                    "median_reported_input_tokens",
                    "median_reported_total_tokens",
                    "median_reported_input_to_visible_text_ratio",
                    "median_reported_total_to_visible_text_ratio",
                    "median_visible_model_output_to_reported_output_ratio",
                ]
            ].to_csv(index=False)
        )


def main() -> None:
    args = parse_args()
    df = read_trajectories(args.trajectory_csv)
    if args.max_rows:
        df = df.head(args.max_rows).copy()

    registry = TokenizerRegistry()
    coverage = tokenizer_coverage(df, registry)
    df = add_tokenizer_availability(df, coverage)
    audit = build_audit(df, registry, args.trajectory_root)
    summary = build_summary(df, audit)

    args.summary_csv.parent.mkdir(parents=True, exist_ok=True)
    args.coverage_csv.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary_csv, index=False, na_rep="NA")
    coverage.to_csv(args.coverage_csv, index=False, na_rep="NA")
    if args.details_csv is not None:
        args.details_csv.parent.mkdir(parents=True, exist_ok=True)
        audit.to_csv(args.details_csv, index=False, na_rep="NA")

    print_summary(summary, coverage, audit)
    print("Files written")
    print(f"- {args.summary_csv}")
    print(f"- {args.coverage_csv}")
    if args.details_csv is not None:
        print(f"- {args.details_csv}")


if __name__ == "__main__":
    main()
