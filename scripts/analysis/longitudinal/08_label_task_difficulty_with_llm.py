#!/usr/bin/env python3
"""Label TB3/TB4 difficulty with the fixed neutralized three-LLM consensus.

The script creates a comparable easy/medium/hard label for TB3/TB4 task-version
rows. It uses the scraped Harbor difficulty_explanation when present, otherwise a
structured difficulty basis built from the task metadata: expert time estimate,
category/subcategory/tags, resource limits, package size, optional instruction
text, and fixed TB2 author-labeled calibration examples.

The labeler must not see empirical run outcomes. It rejects inputs containing
trajectory, leaderboard, pass-rate, token, cost, or duration columns so the
resulting labels can later be compared against observed performance without
leakage.

Rows are written incrementally to a CSV cache, so interrupted or repeated runs
reuse existing labels.

New labels require OPENAI_API_KEY, ANTHROPIC_API_KEY, and Ollama with
qwen2.5:7b-instruct. Cached runs make no LLM calls.

Example:
    python -m scripts.analysis.longitudinal.08_label_task_difficulty_with_llm
    python -m scripts.analysis.longitudinal.08_label_task_difficulty_with_llm --validate-native-tb2-difficulty
"""

from __future__ import annotations

import argparse
import json
import os
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
    LabelerSpec,
    call_labeler,
    consensus_label,
    preflight_provider,
)
from scripts.analysis.longitudinal.difficulty_protocol import (
    DIFFICULTY_LABELERS,
    DIFFICULTY_NEUTRALIZER,
    DIFFICULTY_PANEL,
    require_difficulty_protocol,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
TASK_MINING_DIR = REPO_ROOT / "data" / "processed_live" / "task_mining"
LONGITUDINAL_DIR = REPO_ROOT / "data" / "processed_live" / "longitudinal"
OUT_DEFAULT = LONGITUDINAL_DIR / "tb3_tb4_task_difficulty_llm_labels.csv"
VALIDATION_OUT_DEFAULT = LONGITUDINAL_DIR / "tb2_difficulty_prompt_validation.csv"
VALIDATION_SUMMARY_DEFAULT = LONGITUDINAL_DIR / "tb2_difficulty_prompt_validation_summary.csv"
VALIDATION_CONFUSION_DEFAULT = LONGITUDINAL_DIR / "tb2_difficulty_prompt_validation_confusion.csv"
TB2_METADATA_DEFAULT = TASK_MINING_DIR / "terminal_bench_2_task_toml_metadata.csv"
TB3_TB4_METADATA_DEFAULT = TASK_MINING_DIR / "terminal_bench_3_4_hf_task_metadata.csv"
TB3_TB4_ENRICHED_METADATA_DEFAULT = TASK_MINING_DIR / "terminal_bench_3_4_task_metadata_enriched.csv"

OUTPUT_COLUMNS = [
    "benchmark_version",
    "task_name",
    "llm_difficulty_label",
    "llm_difficulty_score",
    "llm_confidence",
    "llm_rationale",
    "llm_model",
    "label_source",
    "label_target",
    "consensus_status",
    "consensus_vote_count",
    "consensus_votes_json",
    "category",
    "subcategory",
    "native_difficulty",
    "expert_time_estimate_min",
    "junior_time_estimate_min",
    "agent_timeout_sec",
    "difficulty_explanation",
    "difficulty_evidence_source",
    "neutralized_difficulty_explanation",
    "neutralized_description",
    "neutralized_instruction_excerpt",
    "neutralization_model",
    "neutralization_modified_fields",
    "neutralization_rationale",
    "tags",
    "description",
    "instruction_source_url",
    "task_tree_url",
]
VALIDATION_OUTPUT_COLUMNS = [
    "validation_pool",
    "task_name",
    "gold_difficulty_label",
    "llm_difficulty_label",
    "llm_difficulty_score",
    "correct",
    "llm_confidence",
    "llm_rationale",
    "llm_model",
    "label_source",
    "label_target",
    "consensus_status",
    "consensus_vote_count",
    "consensus_votes_json",
    "category",
    "tags",
    "description",
    "neutralized_description",
    "neutralization_model",
    "neutralization_modified_fields",
    "neutralization_rationale",
    "expert_time_estimate_min",
    "junior_time_estimate_min",
    "agent_timeout_sec",
    "sample_seed",
]
VALID_LABELS = {"easy", "medium", "hard"}
DIFFICULTY_ORDER = ["easy", "medium", "hard"]
DEFAULT_VERSIONS = ["3.0", "4.0"]
LABEL_TARGET = "author_intended_static_task_difficulty"
UNCHANGED_TASK_KEY_COLUMNS = [
    "task_name",
    "__instruction_identity__",
    "difficulty_explanation",
    "description",
    "category",
    "subcategory",
    "tags",
    "expert_time_estimate_min",
    "junior_time_estimate_min",
]
LABEL_RESULT_COLUMNS = [
    "llm_difficulty_label",
    "llm_difficulty_score",
    "llm_confidence",
    "llm_rationale",
    "llm_model",
    "label_source",
    "label_target",
    "consensus_status",
    "consensus_vote_count",
    "consensus_votes_json",
]
TB2_CALIBRATION_EXAMPLES = [
    {
        "label": "easy",
        "task_name": "fix-git",
        "category": "software-engineering",
        "expert_time_estimate_min": 5,
        "description": (
            "Recover lost Git commits from a detached HEAD state and merge them "
            "back into the master branch."
        ),
    },
    {
        "label": "easy",
        "task_name": "cobol-modernization",
        "category": "software-engineering",
        "expert_time_estimate_min": 20,
        "description": (
            "Reverse-engineer and reimplement a COBOL program's business logic "
            "in Python with exact output reproduction."
        ),
    },
    {
        "label": "medium",
        "task_name": "mailman",
        "category": "system-administration",
        "expert_time_estimate_min": 60,
        "description": (
            "Configure a functional mailing list server by integrating postfix "
            "and mailman3 with join, leave, and announce workflows."
        ),
    },
    {
        "label": "medium",
        "task_name": "sqlite-db-truncate",
        "category": "debugging",
        "expert_time_estimate_min": 60,
        "description": (
            "Recover data from a corrupted SQLite database using binary file "
            "analysis and data recovery techniques."
        ),
    },
    {
        "label": "medium",
        "task_name": "rstan-to-pystan",
        "category": "data-science",
        "expert_time_estimate_min": 180,
        "description": (
            "Convert an RStan Gaussian Process script to functionally equivalent "
            "PyStan code, including installation, hyperparameter mapping, and "
            "posterior verification."
        ),
    },
    {
        "label": "hard",
        "task_name": "path-tracing-reverse",
        "category": "software-engineering",
        "expert_time_estimate_min": 120,
        "description": (
            "Reverse-engineer a compiled path tracing renderer and recreate "
            "functionally identical C source code under size constraints."
        ),
    },
    {
        "label": "hard",
        "task_name": "torch-tensor-parallelism",
        "category": "software-engineering",
        "expert_time_estimate_min": 240,
        "description": (
            "Implement tensor parallelism for PyTorch linear layers with correct "
            "weight sharding, distributed forward/backward passes, and gradients "
            "across multiple processes."
        ),
    },
    {
        "label": "hard",
        "task_name": "regex-chess",
        "category": "software-engineering",
        "expert_time_estimate_min": 1440,
        "description": (
            "Implement a complete chess move generator using only regular "
            "expression transformations on FEN notation."
        ),
    },
]
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metadata-csv",
        type=Path,
        nargs="*",
        default=[
            TB3_TB4_ENRICHED_METADATA_DEFAULT
            if TB3_TB4_ENRICHED_METADATA_DEFAULT.exists()
            else TB3_TB4_METADATA_DEFAULT
        ],
        help=(
            "Task metadata CSVs. Defaults to the Harbor-enriched TB3/TB4 metadata "
            "when available, otherwise the Hugging Face metadata."
        ),
    )
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.set_defaults(labeler=[spec.id for spec in DIFFICULTY_LABELERS])
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    parser.add_argument(
        "--versions",
        nargs="+",
        default=DEFAULT_VERSIONS,
        help="Benchmark versions to label. Defaults to 3.0 4.0.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of unlabeled rows to process.")
    parser.add_argument("--sleep-sec", type=float, default=0.2, help="Delay between API calls.")
    parser.add_argument("--force", action="store_true", help="Relabel rows already present in the output CSV.")
    parser.add_argument(
        "--include-instruction-text",
        action="store_true",
        help="Fetch instruction.md from instruction_source_url and include a truncated excerpt in the prompt.",
    )
    parser.add_argument(
        "--instruction-char-limit",
        type=int,
        default=6000,
        help="Maximum instruction.md characters to include when --include-instruction-text is set.",
    )
    parser.add_argument(
        "--validate-native-tb2-difficulty",
        action="store_true",
        help=(
            "Run the production difficulty labeler on held-out TB2 tasks with "
            "their native difficulty hidden, then score the consensus label "
            "against the withheld native label."
        ),
    )
    parser.add_argument(
        "--validation-per-difficulty",
        type=int,
        default=10,
        help=(
            "Validation tasks to sample per native label. Defaults to 10; the "
            "held-out easy pool only has 2 tasks after calibration exclusions."
        ),
    )
    parser.add_argument("--validation-sample-seed", type=int, default=20260920)
    parser.add_argument(
        "--validation-summary-out",
        type=Path,
        default=VALIDATION_SUMMARY_DEFAULT,
        help="Summary CSV written by --validate-native-tb2-difficulty.",
    )
    parser.add_argument(
        "--validation-confusion-out",
        type=Path,
        default=VALIDATION_CONFUSION_DEFAULT,
        help="Confusion-matrix CSV written by --validate-native-tb2-difficulty.",
    )
    return parser.parse_args()


def normalize_text(value: object, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none"}:
        return fallback
    return text


def normalize_version(value: object) -> str:
    text = normalize_text(value)
    if text:
        return text
    return ""


def load_metadata(paths: list[Path]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Missing metadata CSV: {path}")
        df = pd.read_csv(path, low_memory=False)
        forbidden = sorted(FORBIDDEN_EMPIRICAL_COLUMNS.intersection(df.columns))
        if forbidden:
            raise ValueError(
                f"{path} appears to contain empirical run/result columns and must not be used "
                f"for LLM difficulty labeling: {', '.join(forbidden)}. Use task metadata, "
                "for example data/processed_live/task_mining/terminal_bench_3_4_task_metadata_enriched.csv."
            )
        if "task_name" not in df.columns:
            raise ValueError(f"{path} must contain task_name.")
        if "benchmark_version" not in df.columns:
            expanded = []
            for version in ["2.0", "2.1"]:
                copy = df.copy()
                copy["benchmark_version"] = version
                copy["benchmark"] = f"terminal_bench_{version.replace('.', '_')}"
                expanded.append(copy)
            df = pd.concat(expanded, ignore_index=True)
        rows.append(df)

    combined = pd.concat(rows, ignore_index=True)
    for column in [
        "category",
        "subcategory",
        "difficulty",
        "tags",
        "description",
        "expert_time_estimate_min",
        "junior_time_estimate_min",
        "agent_timeout_sec",
        "difficulty_explanation",
        "instruction_chars",
        "instruction_normalized_chars",
        "package_file_count",
        "package_total_listed_bytes",
        "instruction_source_url",
        "task_tree_url",
    ]:
        if column not in combined.columns:
            combined[column] = ""
    combined["benchmark_version"] = combined["benchmark_version"].map(normalize_version)
    combined["task_name"] = combined["task_name"].map(normalize_text)
    combined = combined[combined["benchmark_version"].ne("") & combined["task_name"].ne("")].copy()
    combined = combined.sort_values(["benchmark_version", "task_name"]).drop_duplicates(
        ["benchmark_version", "task_name"]
    )
    numeric_columns = [
        "expert_time_estimate_min",
        "junior_time_estimate_min",
        "agent_timeout_sec",
        "instruction_chars",
        "instruction_normalized_chars",
        "package_file_count",
        "package_total_listed_bytes",
    ]
    for column in numeric_columns:
        combined[column] = pd.to_numeric(combined[column], errors="coerce")
    return combined


def calibration_task_names() -> set[str]:
    return {
        normalize_text(example["task_name"])
        for example in TB2_CALIBRATION_EXAMPLES
    }


def load_tb2_validation_metadata(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing TB2 metadata CSV: {path}")
    df = pd.read_csv(path, low_memory=False)
    required = {"task_name", "difficulty", "category", "description"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")
    for column in [
        "tags",
        "expert_time_estimate_min",
        "junior_time_estimate_min",
        "agent_timeout_sec",
    ]:
        if column not in df.columns:
            df[column] = ""
    df["task_name"] = df["task_name"].map(normalize_text)
    df["difficulty"] = normalize_text_series(df["difficulty"])
    df = df[df["task_name"].ne("") & df["difficulty"].isin(VALID_LABELS)].copy()
    return df.sort_values("task_name").drop_duplicates("task_name")


def select_validation_sample(
    metadata: pd.DataFrame,
    *,
    per_difficulty: int,
    sample_seed: int,
    excluded_tasks: set[str],
) -> pd.DataFrame:
    held_out = metadata[~metadata["task_name"].isin(excluded_tasks)].copy()
    pieces = []
    for offset, label in enumerate(DIFFICULTY_ORDER):
        pool = held_out[held_out["difficulty"].eq(label)].copy()
        n = min(per_difficulty, len(pool))
        if n:
            pieces.append(pool.sample(n=n, random_state=sample_seed + offset))
    if not pieces:
        raise ValueError("No held-out validation tasks are available after calibration exclusions.")
    sample = pd.concat(pieces, ignore_index=True)
    order = {label: index for index, label in enumerate(DIFFICULTY_ORDER)}
    sample["difficulty_order"] = sample["difficulty"].map(order)
    return sample.sort_values(["difficulty_order", "task_name"]).drop(columns=["difficulty_order"])


def validation_sample_summary(
    metadata: pd.DataFrame,
    sample: pd.DataFrame,
    excluded_tasks: set[str],
) -> pd.DataFrame:
    held_out = metadata[~metadata["task_name"].isin(excluded_tasks)].copy()
    rows = []
    for label in DIFFICULTY_ORDER:
        rows.append(
            {
                "gold_difficulty_label": label,
                "available_held_out_tasks": int(held_out["difficulty"].eq(label).sum()),
                "sampled_tasks": int(sample["difficulty"].eq(label).sum()),
            }
        )
    return pd.DataFrame(rows)


def load_existing(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    existing = pd.read_csv(path, low_memory=False)
    for column in OUTPUT_COLUMNS:
        if column not in existing.columns:
            existing[column] = ""
    existing["benchmark_version"] = existing["benchmark_version"].map(normalize_version)
    existing["task_name"] = existing["task_name"].map(normalize_text)
    return existing[OUTPUT_COLUMNS].copy()


def valid_completed_labels(labels: pd.DataFrame) -> pd.DataFrame:
    if labels.empty:
        return labels.copy()
    labels = labels.copy()
    labels["llm_difficulty_label"] = normalize_text_series(labels["llm_difficulty_label"])
    source = labels["label_source"].fillna("").astype(str).str.strip().str.lower()
    rationale = labels["llm_rationale"].fillna("").astype(str)
    valid = (
        labels["llm_difficulty_label"].isin(VALID_LABELS)
        & ~source.isin({"error"})
        & ~rationale.str.startswith("ERROR:")
    )
    return labels[valid].copy()


def normalize_text_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower()


def task_key(row: pd.Series) -> tuple[str, str]:
    return (str(row["benchmark_version"]), str(row["task_name"]))


def unchanged_task_key(row: pd.Series) -> tuple[str, ...]:
    values = []
    for column in UNCHANGED_TASK_KEY_COLUMNS:
        if column == "__instruction_identity__":
            value = (
                normalize_text(row.get("instruction_normalized_sha256"))
                or normalize_text(row.get("instruction_sha256"))
                or normalize_text(row.get("instruction_source_url"))
            )
        else:
            value = normalize_text(row.get(column))
        values.append(value)
    return tuple(values)


def reusable_label_from_output(row: dict[str, Any]) -> dict[str, Any]:
    return {column: row.get(column, "") for column in LABEL_RESULT_COLUMNS}


def reusable_neutralization_from_output(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "difficulty_explanation": normalize_text(
            row.get("neutralized_difficulty_explanation"),
            normalize_text(row.get("difficulty_explanation")),
        ),
        "description": normalize_text(
            row.get("neutralized_description"),
            normalize_text(row.get("description")),
        ),
        "instruction_excerpt": normalize_text(row.get("neutralized_instruction_excerpt")),
        "model": normalize_text(row.get("neutralization_model")),
        "modified_fields": [
            field
            for field in normalize_text(row.get("neutralization_modified_fields")).split(";")
            if field
        ],
        "rationale": normalize_text(row.get("neutralization_rationale")),
    }


def valid_output_record(row: dict[str, Any]) -> bool:
    label = normalize_text(row.get("llm_difficulty_label")).lower()
    source = normalize_text(row.get("label_source")).lower()
    rationale = str(row.get("llm_rationale") or "")
    return label in VALID_LABELS and source != "error" and not rationale.startswith("ERROR:")


def index_reusable_outputs(
    labels: list[dict[str, Any]],
    metadata_by_task_key: dict[tuple[str, str], pd.Series],
) -> dict[tuple[str, ...], dict[str, Any]]:
    reusable: dict[tuple[str, ...], dict[str, Any]] = {}
    for label_row in labels:
        if not valid_output_record(label_row):
            continue
        key = (
            normalize_version(label_row.get("benchmark_version")),
            normalize_text(label_row.get("task_name")),
        )
        metadata_row = metadata_by_task_key.get(key)
        if metadata_row is None:
            continue
        identity = unchanged_task_key(metadata_row)
        reusable.setdefault(identity, label_row)
    return reusable


def planned_label_call_counts(
    work: pd.DataFrame,
    reusable_by_identity: dict[tuple[str, ...], dict[str, Any]],
) -> tuple[int, int]:
    seen = set(reusable_by_identity)
    calls = 0
    reused = 0
    for _, row in work.iterrows():
        identity = unchanged_task_key(row)
        if identity in seen:
            reused += 1
        else:
            calls += 1
            seen.add(identity)
    return calls, reused


def difficulty_explanation(row: pd.Series) -> tuple[str, str]:
    source_override = normalize_text(row.get("_difficulty_explanation_source"))
    explanation = normalize_text(row.get("difficulty_explanation"))
    if explanation:
        return explanation, source_override or "difficulty_explanation"
    pieces = [
        f"expert estimate {row.get('expert_time_estimate_min', '')} minutes",
        f"category {normalize_text(row.get('category'), 'unknown')}",
        f"subcategory {normalize_text(row.get('subcategory'), 'unknown')}",
        f"tags {normalize_text(row.get('tags'), 'none')}",
        f"agent timeout {row.get('agent_timeout_sec', '')} seconds",
        f"instruction length {row.get('instruction_normalized_chars', row.get('instruction_chars', ''))} characters",
        f"package file count {row.get('package_file_count', '')}",
        f"package listed bytes {row.get('package_total_listed_bytes', '')}",
    ]
    return "; ".join(pieces), "metadata_derived"


def fetch_instruction_excerpt(row: pd.Series, char_limit: int) -> str:
    url = normalize_text(row.get("instruction_source_url"))
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
    explanation, explanation_source = difficulty_explanation(row)
    pieces = [
        f"Benchmark version: {row.get('benchmark_version', '')}",
        f"Task name: {row.get('task_name', '')}",
        f"Native difficulty: {normalize_text(row.get('difficulty'), 'unknown')}",
        f"Difficulty explanation source: {explanation_source}",
        f"Difficulty explanation: {explanation}",
        f"Category: {normalize_text(row.get('category'), 'unknown')}",
        f"Subcategory: {normalize_text(row.get('subcategory'), 'unknown')}",
        f"Tags: {normalize_text(row.get('tags'), 'none')}",
        f"Description: {normalize_text(row.get('description'), 'none')}",
        f"Expert time estimate minutes: {row.get('expert_time_estimate_min', '')}",
        f"Junior time estimate minutes: {row.get('junior_time_estimate_min', '')}",
        f"Agent timeout seconds: {row.get('agent_timeout_sec', '')}",
        f"Instruction characters: {row.get('instruction_normalized_chars', row.get('instruction_chars', ''))}",
        f"Package file count: {row.get('package_file_count', '')}",
        f"Package listed bytes: {row.get('package_total_listed_bytes', '')}",
    ]
    if instruction_excerpt:
        pieces.append(f"Instruction excerpt:\n{instruction_excerpt}")
    return "\n".join(pieces)


def neutralization_field_prompt(field: str, text: str) -> str:
    return f"""Remove difficulty-leading wording from this task evidence field.

Field name: {field}

Remove only words, clauses, or sentences that explicitly tell a later judge how
easy, medium, hard, simple, complex, challenging, trivial, demanding, advanced,
or straightforward the task is. Also remove direct recommendations about the
final difficulty label.

Preserve factual task requirements, technical terminology, constraints, tools,
file names, package names, numbers, time estimates, resource limits, benchmark
metadata, and acceptance criteria. Do not simplify the task or make it sound
easier or harder. Do not remove technical words such as "hard-coded" or "hard
drive" when they are not difficulty judgments.

If there is no difficulty-leading wording to remove, return the original text
exactly. Return only the neutralized field text between <neutralized_text> and
</neutralized_text>.

<task_evidence>
{text}
</task_evidence>

<neutralized_text>
"""


def extract_neutralized_text(raw: str, original: str) -> str:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("text").strip()
    start_tag = "<neutralized_text>"
    end_tag = "</neutralized_text>"
    if start_tag in text:
        text = text.split(start_tag, 1)[1]
    if end_tag in text:
        text = text.split(end_tag, 1)[0]
    text = text.strip()
    if text.lower() in {"", "no changes needed", "no change needed", "unchanged"}:
        return original
    return text


def neutralize_field(field: str, text: str, spec: LabelerSpec, args: argparse.Namespace) -> str:
    if not text:
        return ""
    max_tokens = max(700, min(5000, int(len(text) / 3) + 500))
    raw = call_labeler(
        neutralization_field_prompt(field, text),
        spec,
        args,
        system_prompt=(
            "You are a neutral evidence editor. Remove only text that biases a "
            "later difficulty label while preserving factual task content. "
            "Return only the requested neutralized text."
        ),
        max_tokens=max_tokens,
    )
    return extract_neutralized_text(raw, text)


def neutralize_task_evidence(
    row: pd.Series,
    instruction_excerpt: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    explanation, _ = difficulty_explanation(row)
    originals = {
        "difficulty_explanation": explanation,
        "description": normalize_text(row.get("description")),
        "instruction_excerpt": instruction_excerpt,
    }
    spec = DIFFICULTY_NEUTRALIZER
    neutralized = {
        field: neutralize_field(field, value, spec, args)
        for field, value in originals.items()
    }
    modified_fields = [
        field
        for field, value in neutralized.items()
        if value != originals.get(field, "")
    ]
    return {
        **neutralized,
        "modified_fields": sorted(modified_fields),
        "rationale": (
            "Removed difficulty-leading wording from task evidence."
            if modified_fields
            else ""
        ),
        "model": spec.id,
    }


def row_with_neutralized_evidence(row: pd.Series, neutralization: dict[str, Any]) -> pd.Series:
    _, explanation_source = difficulty_explanation(row)
    neutralized = row.copy()
    neutralized["difficulty_explanation"] = neutralization.get(
        "difficulty_explanation",
        normalize_text(row.get("difficulty_explanation")),
    )
    neutralized["_difficulty_explanation_source"] = explanation_source
    neutralized["description"] = neutralization.get("description", normalize_text(row.get("description")))
    return neutralized


def validation_row_evidence(row: pd.Series) -> str:
    pieces = [
        "Benchmark pool: Terminal-Bench 2 native task metadata",
        f"Task name: {row.get('task_name', '')}",
        f"Category: {normalize_text(row.get('category'), 'unknown')}",
        f"Tags: {normalize_text(row.get('tags'), 'none')}",
        f"Description: {normalize_text(row.get('description'), 'none')}",
        f"Expert time estimate minutes: {row.get('expert_time_estimate_min', '')}",
        f"Junior time estimate minutes: {row.get('junior_time_estimate_min', '')}",
        f"Agent timeout seconds: {row.get('agent_timeout_sec', '')}",
    ]
    return "\n".join(pieces)


def calibration_examples_text() -> str:
    pieces = []
    for example in TB2_CALIBRATION_EXAMPLES:
        pieces.append(
            "\n".join(
                [
                    f"- Label: {example['label']}",
                    f"  TB2 task: {example['task_name']}",
                    f"  Category: {example['category']}",
                    f"  Expert time estimate minutes: {example['expert_time_estimate_min']}",
                    f"  Description: {example['description']}",
                ]
            )
        )
    return "\n\n".join(pieces)


def build_validation_prompt(
    row: pd.Series,
) -> str:
    examples = f"""
Calibration examples from TB2.0/TB2.1 native author-assigned difficulties.
Use these only as scale anchors. The task to label below is not one of these
calibration examples.

{calibration_examples_text()}
"""
    return f"""Label the task difficulty as easy, medium, or hard.

Use the same standard across benchmark versions. The target label is the
author-intended static task difficulty: what the task author/benchmark curator
appears to believe the task demands before seeing any agent runs.

Do not use empirical performance. Do not use leaderboard accuracy, trajectory
outcomes, pass/fail counts, run duration, token usage, costs, model names, or
any knowledge of how current agents performed on this task. If you recognize the
task from outside knowledge, ignore any remembered results and label only from
the author-facing task evidence below.

Validation constraint: the task's true native difficulty label has been
withheld. Predict it only from the task evidence.

{examples}

Return JSON only with:
- label: one of easy, medium, hard
- score: integer 1 to 3, where 1=easy, 2=medium, 3=hard
- confidence: number from 0 to 1
- rationale: one concise sentence of at most 25 words, with no quotation marks or newlines

Task evidence:
{validation_row_evidence(row)}
"""


def build_prompt(
    row: pd.Series,
    instruction_excerpt: str = "",
) -> str:
    examples = f"""
Calibration examples from TB2.0/TB2.1 native author-assigned difficulties.
Use these only as scale anchors. They are not empirical run results.

{calibration_examples_text()}
"""
    return f"""Label the task difficulty as easy, medium, or hard.

Use the same standard across benchmark versions. The target label is the
author-intended static task difficulty: what the task author/benchmark curator
appears to believe the task demands before seeing any agent runs.

Do not use empirical performance. Do not use leaderboard accuracy, trajectory
outcomes, pass/fail counts, run duration, token usage, costs, model names, or
any knowledge of how current agents performed on this task. If you recognize the
task from outside knowledge, ignore any remembered results and label only from
the author-facing task evidence below.

Primary evidence: use the difficulty explanation field when present. If the
field is metadata-derived, treat it as supporting evidence and use the task
metadata and instruction excerpt to calibrate the label.

{examples}

Return JSON only with:
- label: one of easy, medium, hard
- score: integer 1 to 3, where 1=easy, 2=medium, 3=hard
- confidence: number from 0 to 1
- rationale: one concise sentence of at most 25 words, with no quotation marks or newlines

Task evidence:
{row_evidence(row, instruction_excerpt)}
"""


def normalize_label_response(parsed: dict[str, Any]) -> dict[str, Any]:
    label = str(parsed.get("label", "")).strip().lower()
    if label not in VALID_LABELS:
        raise ValueError(f"Unexpected label from model: {label!r}")
    score = int(parsed.get("score", {"easy": 1, "medium": 2, "hard": 3}[label]))
    confidence = float(parsed.get("confidence", 0.0))
    rationale = normalize_text(parsed.get("rationale"))
    return {
        "llm_difficulty_label": label,
        "llm_difficulty_score": score,
        "llm_confidence": confidence,
        "llm_rationale": rationale,
    }


def label_task(prompt: str, args: argparse.Namespace) -> dict[str, Any]:
    return consensus_label(
        prompt,
        args,
        system_prompt=(
            "You are a careful benchmark curator. Produce calibrated, comparable "
            "difficulty labels for terminal-based tasks. Return valid compact JSON only."
        ),
        max_tokens=600,
        normalize_response=normalize_label_response,
        label_key="llm_difficulty_label",
        confidence_key="llm_confidence",
        rationale_key="llm_rationale",
    )


def output_row(
    row: pd.Series,
    label: dict[str, Any],
    model: str,
    source: str,
    neutralization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    explanation, explanation_source = difficulty_explanation(row)
    neutralization = neutralization or {}
    return {
        "benchmark_version": row.get("benchmark_version", ""),
        "task_name": row.get("task_name", ""),
        **label,
        "llm_difficulty_score": label.get(
            "llm_difficulty_score",
            {"easy": 1, "medium": 2, "hard": 3}.get(str(label.get("llm_difficulty_label", "")).lower(), ""),
        ),
        "llm_model": model,
        "label_source": source,
        "label_target": LABEL_TARGET,
        "consensus_status": label.get("consensus_status", ""),
        "consensus_vote_count": label.get("consensus_vote_count", ""),
        "consensus_votes_json": label.get("consensus_votes_json", ""),
        "category": normalize_text(row.get("category")),
        "subcategory": normalize_text(row.get("subcategory")),
        "native_difficulty": normalize_text(row.get("difficulty"), "unknown"),
        "expert_time_estimate_min": row.get("expert_time_estimate_min", ""),
        "junior_time_estimate_min": row.get("junior_time_estimate_min", ""),
        "agent_timeout_sec": row.get("agent_timeout_sec", ""),
        "difficulty_explanation": explanation,
        "difficulty_evidence_source": explanation_source,
        "neutralized_difficulty_explanation": neutralization.get("difficulty_explanation", explanation),
        "neutralized_description": neutralization.get("description", normalize_text(row.get("description"))),
        "neutralized_instruction_excerpt": neutralization.get("instruction_excerpt", ""),
        "neutralization_model": neutralization.get("model", ""),
        "neutralization_modified_fields": ";".join(neutralization.get("modified_fields", [])),
        "neutralization_rationale": neutralization.get("rationale", ""),
        "tags": normalize_text(row.get("tags")),
        "description": normalize_text(row.get("description")),
        "instruction_source_url": normalize_text(row.get("instruction_source_url")),
        "task_tree_url": normalize_text(row.get("task_tree_url")),
    }


def write_labels(path: Path, labels: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(labels)
    for column in OUTPUT_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    out = out[OUTPUT_COLUMNS].sort_values(["benchmark_version", "task_name"])
    out.to_csv(path, index=False)


def validation_output_row(
    row: pd.Series,
    label: dict[str, Any],
    args: argparse.Namespace,
    neutralization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gold = normalize_text(row.get("difficulty")).lower()
    predicted = normalize_text(label.get("llm_difficulty_label")).lower()
    neutralization = neutralization or {}
    return {
        "validation_pool": "terminal_bench_2_held_out_native_difficulty",
        "task_name": row.get("task_name", ""),
        "gold_difficulty_label": gold,
        "llm_difficulty_label": predicted,
        "llm_difficulty_score": label.get(
            "llm_difficulty_score",
            {"easy": 1, "medium": 2, "hard": 3}.get(predicted, ""),
        ),
        "correct": bool(predicted == gold) if predicted else False,
        "llm_confidence": label.get("llm_confidence", ""),
        "llm_rationale": label.get("llm_rationale", ""),
        "llm_model": label.get("llm_model", DIFFICULTY_PANEL),
        "label_source": label.get("label_source", ""),
        "label_target": "held_out_native_tb2_difficulty_validation",
        "consensus_status": label.get("consensus_status", ""),
        "consensus_vote_count": label.get("consensus_vote_count", ""),
        "consensus_votes_json": label.get("consensus_votes_json", ""),
        "category": normalize_text(row.get("category")),
        "tags": normalize_text(row.get("tags")),
        "description": normalize_text(row.get("description")),
        "neutralized_description": neutralization.get("description", normalize_text(row.get("description"))),
        "neutralization_model": neutralization.get("model", ""),
        "neutralization_modified_fields": ";".join(neutralization.get("modified_fields", [])),
        "neutralization_rationale": neutralization.get("rationale", ""),
        "expert_time_estimate_min": row.get("expert_time_estimate_min", ""),
        "junior_time_estimate_min": row.get("junior_time_estimate_min", ""),
        "agent_timeout_sec": row.get("agent_timeout_sec", ""),
        "sample_seed": args.validation_sample_seed,
    }


def load_existing_validation(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=VALIDATION_OUTPUT_COLUMNS)
    existing = pd.read_csv(path, low_memory=False)
    for column in VALIDATION_OUTPUT_COLUMNS:
        if column not in existing.columns:
            existing[column] = ""
    existing["task_name"] = existing["task_name"].map(normalize_text)
    existing["llm_difficulty_label"] = normalize_text_series(existing["llm_difficulty_label"])
    source = existing["label_source"].fillna("").astype(str).str.strip().str.lower()
    rationale = existing["llm_rationale"].fillna("").astype(str)
    valid = (
        existing["task_name"].ne("")
        & existing["llm_difficulty_label"].isin(VALID_LABELS)
        & ~source.isin({"error"})
        & ~rationale.str.startswith("ERROR:")
    )
    return existing.loc[valid, VALIDATION_OUTPUT_COLUMNS].copy()


def write_validation_outputs(
    out_path: Path,
    summary_path: Path,
    confusion_path: Path,
    rows: list[dict[str, Any]],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(rows)
    for column in VALIDATION_OUTPUT_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    if not out.empty:
        out = out[VALIDATION_OUTPUT_COLUMNS].sort_values(["gold_difficulty_label", "task_name"])
    else:
        out = out[VALIDATION_OUTPUT_COLUMNS]
    out.to_csv(out_path, index=False)

    scored = out.copy()
    if not scored.empty:
        scored["correct"] = scored["correct"].astype(str).str.lower().isin({"true", "1"})
    summary_rows: list[dict[str, Any]] = []
    summary_columns = [
        "labeler",
        "n_tasks",
        "n_correct",
        "accuracy",
        "n_unanimous",
        "n_majority",
        "n_tie",
    ]
    for label in DIFFICULTY_ORDER:
        summary_columns.extend([f"n_{label}", f"n_{label}_correct", f"accuracy_{label}"])
    if not scored.empty:
        predictions = {"consensus": scored}
        for spec in DIFFICULTY_LABELERS:
            individual = scored.copy()
            individual["llm_difficulty_label"] = scored["consensus_votes_json"].map(
                lambda raw: next(
                    (vote.get("label", "") for vote in json.loads(raw if isinstance(raw, str) and raw.strip() else "[]")
                     if f"{vote.get('provider')}:{vote.get('model')}" == spec.id),
                    "",
                )
            )
            predictions[spec.id] = individual
        for labeler, predicted in predictions.items():
            correct = predicted["gold_difficulty_label"].eq(predicted["llm_difficulty_label"])
            row: dict[str, Any] = {
                "labeler": labeler,
                "n_tasks": int(len(predicted)),
                "n_correct": int(correct.sum()),
                "accuracy": float(correct.mean()),
                **{
                    f"n_{status}": int(scored["consensus_status"].eq(status).sum())
                    if labeler == "consensus" else ""
                    for status in ("unanimous", "majority", "tie")
                },
            }
            for label in DIFFICULTY_ORDER:
                subset = predicted["gold_difficulty_label"].eq(label)
                row[f"n_{label}"] = int(subset.sum())
                row[f"n_{label}_correct"] = int(correct[subset].sum())
                row[f"accuracy_{label}"] = float(correct[subset].mean()) if subset.any() else ""
            summary_rows.append(row)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows, columns=summary_columns).to_csv(summary_path, index=False)

    if scored.empty:
        confusion = pd.DataFrame(
            columns=["gold_difficulty_label", "llm_difficulty_label", "n"]
        )
    else:
        confusion = (
            scored.groupby(["gold_difficulty_label", "llm_difficulty_label"])
            .size()
            .reset_index(name="n")
            .sort_values(["gold_difficulty_label", "llm_difficulty_label"])
        )
    confusion_path.parent.mkdir(parents=True, exist_ok=True)
    confusion.to_csv(confusion_path, index=False)


def run_tb2_native_difficulty_validation(args: argparse.Namespace) -> None:
    if args.out == OUT_DEFAULT:
        args.out = VALIDATION_OUT_DEFAULT
    metadata_paths = args.metadata_csv or []
    default_production_metadata = {TB3_TB4_ENRICHED_METADATA_DEFAULT, TB3_TB4_METADATA_DEFAULT}
    if len(metadata_paths) == 1 and metadata_paths[0] in default_production_metadata:
        metadata_path = TB2_METADATA_DEFAULT
    else:
        metadata_path = metadata_paths[0] if metadata_paths else TB2_METADATA_DEFAULT
    metadata = load_tb2_validation_metadata(metadata_path)
    excluded_tasks = calibration_task_names()
    sample = select_validation_sample(
        metadata,
        per_difficulty=args.validation_per_difficulty,
        sample_seed=args.validation_sample_seed,
        excluded_tasks=excluded_tasks,
    )
    sample_summary = validation_sample_summary(metadata, sample, excluded_tasks)
    print("Held-out validation sample by native label:")
    print(sample_summary.to_string(index=False))

    existing = load_existing_validation(args.out)
    retained = existing.iloc[0:0].copy() if args.force else existing
    sampled_tasks = set(sample["task_name"])
    retained = retained[retained["task_name"].isin(sampled_tasks)].copy()
    require_difficulty_protocol(retained, args.out)
    completed_tasks = set(retained["task_name"])
    work = sample[~sample["task_name"].isin(completed_tasks)].copy()
    if args.limit is not None:
        work = work.head(args.limit).copy()

    if len(work) > 0:
        preflight_provider(args)
    else:
        print("All requested validation tasks are already cached; aggregating only.")

    labels = retained.to_dict(orient="records")
    print(f"Existing valid validation labels retained: {len(labels)}")
    print(f"Validation tasks to label: {len(work)}")

    for index, row in enumerate(work.itertuples(index=False), start=1):
        row_series = pd.Series(row._asdict())
        neutralization: dict[str, Any] = {}
        try:
            neutralization = neutralize_task_evidence(row_series, "", args)
            neutralized_row = row_with_neutralized_evidence(row_series, neutralization)
            label = label_task(
                build_validation_prompt(neutralized_row),
                args,
            )
            source = label.get("label_source", "consensus")
        except Exception as exc:
            label = {
                "llm_difficulty_label": "",
                "llm_difficulty_score": "",
                "llm_confidence": "",
                "llm_rationale": f"ERROR: {exc}",
                "label_source": "error",
                "llm_model": DIFFICULTY_PANEL,
            }
            source = "error"
        labels.append(validation_output_row(row_series, label, args, neutralization))
        write_validation_outputs(args.out, args.validation_summary_out, args.validation_confusion_out, labels)
        predicted = label.get("llm_difficulty_label", "")
        gold = row_series["difficulty"]
        status = "ERROR" if source == "error" else ("correct" if predicted == gold else "wrong")
        print(
            f"[{index}/{len(work)}] {row_series['task_name']}: "
            f"gold={gold} consensus={predicted or 'no-label'} ({status})"
        )
        if args.sleep_sec > 0:
            time.sleep(args.sleep_sec)

    write_validation_outputs(args.out, args.validation_summary_out, args.validation_confusion_out, labels)
    print(f"Wrote validation labels: {args.out}")
    print(f"Wrote validation summary: {args.validation_summary_out}")
    print(f"Wrote validation confusion matrix: {args.validation_confusion_out}")
    summary = pd.read_csv(args.validation_summary_out) if args.validation_summary_out.exists() else pd.DataFrame()
    if not summary.empty:
        print(summary.to_string(index=False))


def main() -> None:
    args = parse_args()
    if args.validate_native_tb2_difficulty:
        run_tb2_native_difficulty_validation(args)
        return

    all_metadata = load_metadata(args.metadata_csv)
    versions = {str(version) for version in args.versions}
    metadata = all_metadata[all_metadata["benchmark_version"].astype(str).isin(versions)].copy()
    metadata_by_task_key = {
        task_key(row): row
        for _, row in all_metadata.iterrows()
    }
    existing = load_existing(args.out)
    retained_existing = valid_completed_labels(existing) if not args.force else existing.iloc[0:0].copy()
    require_difficulty_protocol(retained_existing, args.out)
    existing_keys = {task_key(row) for _, row in retained_existing.iterrows()}
    work = metadata[[task_key(row) not in existing_keys for _, row in metadata.iterrows()]].copy()
    if args.limit is not None:
        work = work.head(args.limit).copy()

    labels = retained_existing.to_dict(orient="records")
    reusable_by_identity = index_reusable_outputs(labels, metadata_by_task_key)
    planned_label_calls, planned_reused_labels = planned_label_call_counts(work, reusable_by_identity)

    if planned_label_calls > 0:
        preflight_provider(args)

    dropped_existing = len(existing) - len(retained_existing) if not args.force else len(existing)
    print(f"Existing valid labels retained: {len(labels)}")
    if dropped_existing:
        print(f"Existing invalid/error labels to relabel: {dropped_existing}")
    print(f"Rows needing output: {len(work)}")
    print(f"Rows requiring LLM labels: {planned_label_calls}")
    if planned_reused_labels:
        print(f"Rows reused from unchanged tasks: {planned_reused_labels}")

    for index, row in enumerate(work.itertuples(index=False), start=1):
        row_series = pd.Series(row._asdict())
        neutralization: dict[str, Any] = {}
        reuse_source = reusable_by_identity.get(unchanged_task_key(row_series))
        try:
            if reuse_source is not None:
                label = reusable_label_from_output(reuse_source)
                neutralization = reusable_neutralization_from_output(reuse_source)
            else:
                instruction_excerpt = (
                    fetch_instruction_excerpt(row_series, args.instruction_char_limit)
                    if args.include_instruction_text
                    else ""
                )
                neutralization = neutralize_task_evidence(row_series, instruction_excerpt, args)
                neutralized_row = row_with_neutralized_evidence(row_series, neutralization)
                label = label_task(
                    build_prompt(
                        neutralized_row,
                        neutralization.get("instruction_excerpt", instruction_excerpt),
                    ),
                    args,
                )
            source = label.get("label_source", "consensus")
            model = label.get("llm_model", DIFFICULTY_PANEL)
        except Exception as exc:
            label = {
                "llm_difficulty_label": "",
                "llm_difficulty_score": "",
                "llm_confidence": "",
                "llm_rationale": f"ERROR: {exc}",
            }
            source = "error"
            model = DIFFICULTY_PANEL
        labels.append(output_row(row_series, label, model, source, neutralization))
        if reuse_source is None and valid_output_record(labels[-1]):
            reusable_by_identity.setdefault(unchanged_task_key(row_series), labels[-1])
        write_labels(args.out, labels)
        reuse_note = " (reused)" if reuse_source is not None else ""
        print(
            f"[{index}/{len(work)}] {row_series['benchmark_version']} {row_series['task_name']}: "
            f"{label.get('llm_difficulty_label', '')}{reuse_note}"
        )
        if reuse_source is None and args.sleep_sec > 0:
            time.sleep(args.sleep_sec)

    write_labels(args.out, labels)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
