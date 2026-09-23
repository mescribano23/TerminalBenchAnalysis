#!/usr/bin/env python3
"""Label TB2 tasks into the TB3/TB4 category taxonomy with an LLM.

The script assigns each TB2 task to exactly one of the broad category labels
used natively by Terminal-Bench 3.0/4.0:
Software, Science, ML, Operations, Security, Hardware, or Media.

The labeler uses only task metadata and optional instruction text. It rejects
empirical run/result columns so category labels can be used for downstream
performance comparisons without leakage.

Rows are written incrementally to a CSV cache.

Examples:
    python -m scripts.analysis.longitudinal.06_label_tb2_task_categories_with_llm --model gpt-4o-mini
    python -m scripts.analysis.longitudinal.06_label_tb2_task_categories_with_llm --provider ollama --model qwen2.5:7b-instruct
    python -m scripts.analysis.longitudinal.06_label_tb2_task_categories_with_llm --force --labeler openai:gpt-4o-mini --labeler anthropic:claude-haiku-4-5-20251001 --labeler ollama:qwen2.5:7b-instruct
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT_GUESS = Path(__file__).resolve().parents[3]
if str(REPO_ROOT_GUESS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_GUESS))

from scripts.benchmark_paths import find_repo_root
from scripts.analysis.longitudinal.llm_consensus import (
    add_provider_args,
    consensus_label,
    preflight_provider,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
TASK_MINING_DIR = REPO_ROOT / "data" / "processed_live" / "task_mining"
LONGITUDINAL_DIR = REPO_ROOT / "data" / "processed_live" / "longitudinal"
TB2_METADATA_DEFAULT = TASK_MINING_DIR / "terminal_bench_2_task_toml_metadata.csv"
OUT_DEFAULT = LONGITUDINAL_DIR / "tb2_task_category_llm_labels.csv"

TARGET_CATEGORIES = ["Software", "Science", "ML", "Operations", "Security", "Hardware", "Media"]
LABEL_TARGET = "tb3_tb4_unified_task_category"
FORBIDDEN_EMPIRICAL_COLUMNS = {
    "reward",
    "reward_outcome",
    "passed",
    "outcome",
    "leaderboard_accuracy",
    "leaderboard_accuracy_submission",
    "submission_official_pass_rate",
    "task_weighted_pass_rate",
    "pass_rate",
    "task_pass_rate",
    "pooled_pass_rate",
    "pass_count",
    "fail_count",
    "n_passed",
    "n_failed",
    "n_trials",
    "duration_seconds",
    "observed_median_duration_min",
    "observed_mean_duration_min",
    "step_count",
    "agent_step_count",
    "tool_call_count",
    "shell_invocation_count",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
}
OUTPUT_COLUMNS = [
    "task_name",
    "llm_category_label",
    "llm_confidence",
    "llm_rationale",
    "llm_model",
    "label_source",
    "label_target",
    "consensus_status",
    "consensus_vote_count",
    "consensus_votes_json",
    "native_category",
    "native_difficulty",
    "expert_time_estimate_min",
    "junior_time_estimate_min",
    "agent_timeout_sec",
    "tags",
    "keywords",
    "description",
    "source_url",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-csv", type=Path, default=TB2_METADATA_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    add_provider_args(parser, default_model="gpt-4o-mini")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep-sec", type=float, default=0.2)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--include-instruction-text",
        action="store_true",
        help="Fetch instruction.md next to each task.toml source URL and include a truncated excerpt.",
    )
    parser.add_argument("--instruction-char-limit", type=int, default=6000)
    return parser.parse_args()


def normalize_text(value: object, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none"}:
        return fallback
    return text


def normalize_category(value: object) -> str:
    text = normalize_text(value)
    for category in TARGET_CATEGORIES:
        if text.lower() == category.lower():
            return category
    raise ValueError(f"Unexpected category from model: {text!r}")


def load_metadata(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing metadata CSV: {path}")
    df = pd.read_csv(path, low_memory=False)
    forbidden = sorted(FORBIDDEN_EMPIRICAL_COLUMNS.intersection(df.columns))
    if forbidden:
        raise ValueError(
            f"{path} appears to contain empirical run/result columns and must not be used "
            f"for LLM category labeling: {', '.join(forbidden)}. Use task metadata, "
            "for example data/processed_live/task_mining/terminal_bench_2_task_toml_metadata.csv."
        )
    required = {"task_name", "category", "difficulty"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")
    for column in [
        "tags",
        "keywords",
        "description",
        "expert_time_estimate_min",
        "junior_time_estimate_min",
        "agent_timeout_sec",
        "source_url",
    ]:
        if column not in df.columns:
            df[column] = ""
    df["task_name"] = df["task_name"].map(normalize_text)
    df = df[df["task_name"].ne("")].copy()
    df = df.sort_values("task_name").drop_duplicates("task_name")
    for column in ["expert_time_estimate_min", "junior_time_estimate_min", "agent_timeout_sec"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def load_existing(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    existing = pd.read_csv(path, low_memory=False)
    for column in OUTPUT_COLUMNS:
        if column not in existing.columns:
            existing[column] = ""
    existing["task_name"] = existing["task_name"].map(normalize_text)
    return existing[OUTPUT_COLUMNS].copy()


def valid_completed_labels(labels: pd.DataFrame) -> pd.DataFrame:
    if labels.empty:
        return labels.copy()
    labels = labels.copy()
    normalized = labels["llm_category_label"].fillna("").astype(str).str.strip()
    valid_categories = {category.lower() for category in TARGET_CATEGORIES}
    source = labels["label_source"].fillna("").astype(str).str.strip().str.lower()
    rationale = labels["llm_rationale"].fillna("").astype(str)
    valid = (
        normalized.str.lower().isin(valid_categories)
        & ~source.isin({"error"})
        & ~rationale.str.startswith("ERROR:")
    )
    labels.loc[valid, "llm_category_label"] = normalized[valid].map(normalize_category)
    return labels[valid].copy()


def task_key(row: pd.Series) -> str:
    return str(row["task_name"])


def source_instruction_url(source_url: object) -> str:
    url = normalize_text(source_url)
    if not url.endswith("/task.toml"):
        return ""
    return url[: -len("task.toml")] + "instruction.md"


def fetch_instruction_excerpt(row: pd.Series, char_limit: int) -> str:
    url = source_instruction_url(row.get("source_url"))
    if not url:
        return ""
    request = urllib.request.Request(url, headers={"User-Agent": "TerminalBenchAnalysis/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            text = response.read().decode("utf-8", errors="replace")
    except (TimeoutError, urllib.error.URLError, OSError):
        return ""
    text = text.strip()
    if len(text) <= char_limit:
        return text
    return text[:char_limit].rstrip() + "\n[truncated]"


def row_evidence(row: pd.Series, instruction_excerpt: str = "") -> str:
    pieces = [
        f"Task name: {row.get('task_name', '')}",
        f"Native TB2 category: {normalize_text(row.get('category'), 'unknown')}",
        f"Native TB2 difficulty: {normalize_text(row.get('difficulty'), 'unknown')}",
        f"Tags: {normalize_text(row.get('tags'), 'none')}",
        f"Keywords: {normalize_text(row.get('keywords'), 'none')}",
        f"Description: {normalize_text(row.get('description'), 'none')}",
        f"Expert time estimate minutes: {row.get('expert_time_estimate_min', '')}",
        f"Junior time estimate minutes: {row.get('junior_time_estimate_min', '')}",
        f"Agent timeout seconds: {row.get('agent_timeout_sec', '')}",
    ]
    if instruction_excerpt:
        pieces.append(f"Instruction excerpt:\n{instruction_excerpt}")
    return "\n".join(pieces)


def build_prompt(row: pd.Series, instruction_excerpt: str = "") -> str:
    categories = "\n".join(
        [
            "- Software: programming, debugging, application/library implementation, build failures, tests, code repair.",
            "- Science: mathematics, statistics, scientific computing, simulations, domain science analysis.",
            "- ML: machine learning, data science, modeling, training, inference, evaluation, structured data analysis.",
            "- Operations: shell workflows, filesystems, system administration, data wrangling, deployment/configuration, automation.",
            "- Security: exploitation, vulnerability analysis, sanitization bypasses, cryptography, forensics, secure coding.",
            "- Hardware: circuits, HDL, embedded systems, firmware, robotics, sensors, hardware-adjacent tasks.",
            "- Media: images, audio, video, layout, graphics, computer vision/media processing.",
        ]
    )
    return f"""Map this Terminal-Bench 2 task into the Terminal-Bench 3/4 category taxonomy.

Choose exactly one target category from:
Software, Science, ML, Operations, Security, Hardware, Media.

Use the same standard across all tasks. Prefer the category that describes the
primary work required to solve the task, not just incidental tools. Use the
native TB2 category/tags as evidence, but you may override them when the task
description clearly belongs in a different TB3/TB4 category.

Do not use empirical performance. Do not use leaderboard accuracy, trajectory
outcomes, pass/fail counts, run duration, token usage, costs, model names, or
any knowledge of how current agents performed on this task.

Target category definitions:
{categories}

Return JSON only with:
- label: one of Software, Science, ML, Operations, Security, Hardware, Media
- confidence: number from 0 to 1
- rationale: one concise sentence explaining the category

Task evidence:
{row_evidence(row, instruction_excerpt)}
"""


def normalize_label_response(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "llm_category_label": normalize_category(parsed.get("label", "")),
        "llm_confidence": float(parsed.get("confidence", 0.0)),
        "llm_rationale": normalize_text(parsed.get("rationale")),
    }


def label_task(prompt: str, args: argparse.Namespace) -> dict[str, Any]:
    return consensus_label(
        prompt,
        args,
        system_prompt=(
            "You are a careful benchmark curator. Map tasks into a fixed category "
            "taxonomy. Return valid JSON only."
        ),
        max_tokens=180,
        normalize_response=normalize_label_response,
        label_key="llm_category_label",
        confidence_key="llm_confidence",
        rationale_key="llm_rationale",
    )


def output_row(row: pd.Series, label: dict[str, Any], model: str, source: str) -> dict[str, Any]:
    return {
        "task_name": row.get("task_name", ""),
        **label,
        "llm_model": model,
        "label_source": source,
        "label_target": LABEL_TARGET,
        "consensus_status": label.get("consensus_status", ""),
        "consensus_vote_count": label.get("consensus_vote_count", ""),
        "consensus_votes_json": label.get("consensus_votes_json", ""),
        "native_category": normalize_text(row.get("category")),
        "native_difficulty": normalize_text(row.get("difficulty"), "unknown"),
        "expert_time_estimate_min": row.get("expert_time_estimate_min", ""),
        "junior_time_estimate_min": row.get("junior_time_estimate_min", ""),
        "agent_timeout_sec": row.get("agent_timeout_sec", ""),
        "tags": normalize_text(row.get("tags")),
        "keywords": normalize_text(row.get("keywords")),
        "description": normalize_text(row.get("description")),
        "source_url": normalize_text(row.get("source_url")),
    }


def write_labels(path: Path, labels: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(labels)
    for column in OUTPUT_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    out = out[OUTPUT_COLUMNS].sort_values("task_name")
    out.to_csv(path, index=False)


def main() -> None:
    args = parse_args()
    metadata = load_metadata(args.metadata_csv)
    existing = load_existing(args.out)
    retained_existing = valid_completed_labels(existing) if not args.force else existing.iloc[0:0].copy()
    existing_keys = {task_key(row) for _, row in retained_existing.iterrows()}
    work = metadata[[task_key(row) not in existing_keys for _, row in metadata.iterrows()]].copy()
    if args.limit is not None:
        work = work.head(args.limit).copy()

    preflight_provider(args)

    labels = retained_existing.to_dict(orient="records")
    dropped_existing = len(existing) - len(retained_existing) if not args.force else len(existing)
    print(f"Existing valid labels retained: {len(labels)}")
    if dropped_existing:
        print(f"Existing invalid/error labels to relabel: {dropped_existing}")
    print(f"Rows to label: {len(work)}")

    for index, row in enumerate(work.itertuples(index=False), start=1):
        row_series = pd.Series(row._asdict())
        try:
            instruction_excerpt = (
                fetch_instruction_excerpt(row_series, args.instruction_char_limit)
                if args.include_instruction_text
                else ""
            )
            label = label_task(build_prompt(row_series, instruction_excerpt), args)
            source = label.get("label_source", "consensus")
            model = label.get("llm_model", args.model)
        except Exception as exc:
            label = {
                "llm_category_label": "",
                "llm_confidence": "",
                "llm_rationale": f"ERROR: {exc}",
            }
            source = "error"
            model = args.model
        labels.append(output_row(row_series, label, model, source))
        write_labels(args.out, labels)
        print(f"[{index}/{len(work)}] {row_series['task_name']}: {label.get('llm_category_label', '')}")
        if args.sleep_sec > 0:
            time.sleep(args.sleep_sec)

    write_labels(args.out, labels)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
