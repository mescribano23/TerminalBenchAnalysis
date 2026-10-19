#!/usr/bin/env python3
"""Characterize TerminalBench trajectory JSON files.

Outputs:
- data/processed_live/{benchmark}/trajectory_summary.csv
- data/processed_live/{benchmark}/leaderboard_submission_summary.csv
- data/processed_live/{benchmark}/corpus_stats.json
- data/processed_live/{benchmark}/shell_invocation_patterns.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shlex
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

from scripts.benchmark_paths import SUPPORTED_BENCHMARKS, paths_for_benchmark
from scripts.analysis.submission_task_balancing import build_effective_submission_id


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
ROOT_DEFAULT = DATA_DIR / "trajectories" / "terminal_bench_2_0"
OUT_DEFAULT = DATA_DIR / "processed"
LEADERBOARD_DEFAULT = DATA_DIR / "raw" / "terminal_bench_2_0" / "leaderboard_submissions.json"
LEADERBOARD_TRIALS_DEFAULT = DATA_DIR / "raw" / "terminal_bench_2_0" / "leaderboard_trials.json"
INDEX_DEFAULT = DATA_DIR / "indexes" / "terminal_bench_2_0" / "trajectory_trials.json"

BASH_FENCE_RE = re.compile(r"```(?:bash|sh|shell)?\s*\n(.*?)```", re.IGNORECASE | re.DOTALL)
COMPLETE_RE = re.compile(r"\bCOMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\b")
COMMAND_ARGUMENT_KEYS = ("command", "cmd", "keystrokes", "action", "input", "code")

OFFICIAL_LEADERBOARD_FIELDS = [
    "leaderboard_accuracy",
    "leaderboard_stderr",
    "leaderboard_date",
    "leaderboard_agent_display_name",
    "leaderboard_model_display",
    "leaderboard_agent_organization",
    "leaderboard_model_organization",
]

COMPUTED_SUBMISSION_FIELDS = [
    "computed_submission_success_count",
    "computed_submission_trial_count",
    "computed_submission_task_rate_variance",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_trajectory_index(path: Path, root: Path) -> dict[str, dict[str, Any]]:
    """Load the trajectory index and key it by corpus-relative path."""
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    try:
        entries = json.loads(text)
    except json.JSONDecodeError:
        # Some older generated indexes used Windows paths with invalid JSON
        # escapes in filePath. Normalize only filePath strings and retry.
        def fix_filepath(match: re.Match[str]) -> str:
            value = match.group(1).replace("\\", "/")
            value = re.sub(r"/+", "/", value)
            return f'"filePath": "{value}"'

        fixed = re.sub(r'"filePath"\s*:\s*"([^"]*)"', fix_filepath, text)
        entries = json.loads(fixed)

    if not isinstance(entries, list):
        return {}

    root_key = display_path(root).replace("\\", "/").rstrip("/")
    by_rel: dict[str, dict[str, Any]] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        file_path = str(entry.get("filePath", "")).replace("\\", "/")
        file_path = re.sub(r"/+", "/", file_path)
        rel_key = ""
        if root_key and file_path.startswith(f"{root_key}/"):
            rel_key = file_path[len(root_key) + 1 :]
        if rel_key:
            by_rel[rel_key] = entry

    return by_rel


def load_leaderboard_trial_rows(path: Path) -> dict[str, str]:
    """Return Harbor trial id -> leaderboard row id mappings when available."""
    if not path.exists():
        return {}
    entries = load_json(path)
    if not isinstance(entries, list):
        return {}

    by_trial_id: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        trial_id = str(entry.get("id") or "").strip()
        row_id = str(entry.get("harbor_leaderboard_row_id") or "").strip()
        if trial_id and row_id:
            by_trial_id[trial_id] = row_id
    return by_trial_id


def harbor_row_id_from_url(url: Any) -> str:
    text = str(url or "").strip().rstrip("/")
    marker = "/rows/"
    if marker not in text:
        return ""
    return text.rsplit(marker, 1)[-1]


def reward_outcome(reward: Any) -> str:
    if reward in {"", None}:
        return ""
    try:
        value = float(reward)
    except (TypeError, ValueError):
        return ""
    if value == 1.0:
        return "pass"
    if value == 0.0:
        return "fail"
    return f"score_{value}"


def display_path(path: Path) -> str:
    """Return a repo-relative path when possible, keeping generated files portable."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def scalar_value(data: Any, names: set[str], max_depth: int = 4) -> Any:
    """Find the first scalar value for a key in a nested JSON-like object."""
    def walk(obj: Any, depth: int) -> Any:
        if depth > max_depth:
            return None
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in names and not isinstance(v, (dict, list)):
                    return v
            for v in obj.values():
                found = walk(v, depth + 1)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for v in obj:
                found = walk(v, depth + 1)
                if found is not None:
                    return found
        return None
    return walk(data, 0)


def textish(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def command_text(value: Any) -> str:
    """Normalize command-like tool arguments across scaffold schemas."""
    if isinstance(value, list) and all(isinstance(part, (str, int, float, bool)) for part in value):
        return " ".join(shlex.quote(str(part)) for part in value)
    return textish(value)


def extract_observation_info(step: dict[str, Any]) -> tuple[int, bool]:
    char_count = 0
    chunk_count = 0
    has_final_marker = False
    obs = step.get("observation")
    if obs is None:
        return 0, False

    def add_text(value: Any) -> None:
        nonlocal char_count, chunk_count, has_final_marker
        text = textish(value)
        if not text:
            return
        if chunk_count:
            char_count += 1
        char_count += len(text)
        chunk_count += 1
        if COMPLETE_RE.search(text):
            has_final_marker = True

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in {"content", "output", "stdout", "stderr", "message", "text"} and not isinstance(v, (dict, list)):
                    add_text(v)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, str):
            add_text(obj)

    walk(obs)
    return char_count, has_final_marker


def extract_commands_from_text(text: str) -> list[str]:
    commands: list[str] = []
    for match in BASH_FENCE_RE.finditer(text or ""):
        block = match.group(1).strip()
        if block:
            commands.append(block)
    return commands


def extract_tool_calls(step: dict[str, Any]) -> list[dict[str, str]]:
    calls: list[dict[str, str]] = []
    raw_calls = step.get("tool_calls") or []
    if not isinstance(raw_calls, list):
        raw_calls = [raw_calls]
    for call in raw_calls:
        if not isinstance(call, dict):
            calls.append({"tool": "", "command": textish(call), "raw": "1"})
            continue
        tool = textish(call.get("name") or call.get("tool_name") or call.get("function_name") or call.get("type") or "")
        args = call.get("arguments") or call.get("args") or call.get("input")
        fn = call.get("function")
        if isinstance(fn, dict):
            tool = tool or textish(fn.get("name") or "")
            args = args if args is not None else fn.get("arguments")
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
                args = parsed
            except json.JSONDecodeError:
                pass
        command = ""
        if isinstance(args, dict):
            for key in COMMAND_ARGUMENT_KEYS:
                if key in args:
                    command = command_text(args[key])
                    break
        if not command:
            for key in COMMAND_ARGUMENT_KEYS:
                if key in call:
                    command = command_text(call[key])
                    break
        calls.append({"tool": tool, "command": command, "raw": "1"})
    return calls


def shell_head(command: str) -> str:
    first_line = (command or "").strip().splitlines()[0] if (command or "").strip() else ""
    first_segment = re.split(r"\s*(?:&&|\|\||;|\|)\s*", first_line)[0]
    try:
        parts = shlex.split(first_segment, posix=True)
    except ValueError:
        parts = first_segment.split()
    if not parts:
        return ""
    if parts[0] in {"sudo", "env", "timeout", "xvfb-run"} and len(parts) > 1:
        return parts[1]
    return parts[0]


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    return values[f] * (c - k) + values[c] * (k - f)


def summarize_numeric(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "median": median(values),
        "p90": percentile(values, 0.90),
    }


def parse_float(value: Any) -> float | None:
    if value in {"", None}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sample_variance(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = mean(values)
    return sum((value - avg) ** 2 for value in values) / (len(values) - 1)


def submission_accuracy_summary(entry: dict[str, Any], rank: int | None = None) -> dict[str, Any]:
    tasks = [task for task in entry.get("tasks", []) if isinstance(task, dict)]
    total_trials = sum(int(task.get("nTrials", 0) or 0) for task in tasks)
    total_successes = sum(int(task.get("successCount", 0) or 0) for task in tasks)
    rates = [
        float(task.get("avgResolutionRate", 0.0) or 0.0)
        for task in tasks
        if "avgResolutionRate" in task
    ]
    task_rate_variance = sample_variance(rates)
    computed = {
        "leaderboard_rank": rank if rank is not None else "",
        "computed_submission_success_count": total_successes,
        "computed_submission_trial_count": total_trials,
        "computed_submission_task_rate_variance": task_rate_variance if task_rate_variance is not None else "",
    }
    return computed


def write_parser_validation_sample(rows: list[dict[str, Any]], root: Path, out: Path) -> None:
    sample_rows: list[dict[str, Any]] = []
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            str(row.get("scaffold", "")),
            str(row.get("reward_outcome", "")),
            str(row.get("leaderboard_date", "")),
            str(row.get("rel_path", "")),
        ),
    )
    by_scaffold: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted_rows:
        if row.get("reward_outcome") in {"pass", "fail"}:
            by_scaffold[str(row.get("scaffold", ""))].append(row)

    selected_providers: set[str] = set()
    for scaffold, scaffold_rows in sorted(by_scaffold.items()):
        for outcome in ("pass", "fail"):
            candidates = [row for row in scaffold_rows if row.get("reward_outcome") == outcome]
            if candidates:
                selected = next(
                    (
                        row
                        for row in candidates
                        if str(row.get("leaderboard_provider", "")).strip()
                        and str(row.get("leaderboard_provider", "")).strip() not in selected_providers
                    ),
                    candidates[0],
                )
                sample_rows.append(selected)
                provider = str(selected.get("leaderboard_provider", "")).strip()
                if provider:
                    selected_providers.add(provider)

    output_rows: list[dict[str, Any]] = []
    for row in sample_rows:
        rel_path = str(row.get("rel_path", ""))
        raw_path = root / rel_path
        raw_steps: list[Any] = []
        final_metrics: dict[str, Any] = {}
        read_error = ""
        try:
            data = load_json(raw_path)
            if isinstance(data.get("steps"), list):
                raw_steps = data["steps"]
            if isinstance(data.get("final_metrics"), dict):
                final_metrics = data["final_metrics"]
        except Exception as exc:
            read_error = str(exc)

        raw_tool_call_count = 0
        raw_tool_call_steps = 0
        command_examples: list[str] = []
        observation_steps = 0
        metrics_steps = 0
        reasoning_steps = 0
        for step in raw_steps:
            if not isinstance(step, dict):
                continue
            calls = extract_tool_calls(step)
            raw_calls = step.get("tool_calls") or []
            if raw_calls and not isinstance(raw_calls, list):
                raw_calls = [raw_calls]
            if raw_calls:
                raw_tool_call_steps += 1
                raw_tool_call_count += len(raw_calls)
            for call in calls:
                command = call.get("command", "")
                if command and len(command_examples) < 2:
                    command_examples.append(command.replace("\n", "\\n")[:180])
            if step.get("observation") is not None:
                observation_steps += 1
            if isinstance(step.get("metrics"), dict) and step.get("metrics"):
                metrics_steps += 1
            if step.get("reasoning_content"):
                reasoning_steps += 1

        output_rows.append(
            {
                "benchmark": row.get("benchmark", ""),
                "scaffold": row.get("scaffold", ""),
                "model_dir": row.get("model_dir", ""),
                "provider": row.get("leaderboard_provider", ""),
                "leaderboard_date": row.get("leaderboard_date", ""),
                "task_name": row.get("task_name", ""),
                "reward": row.get("reward", ""),
                "outcome": row.get("reward_outcome", ""),
                "rel_path": rel_path.replace("\\", "/"),
                "repository_path": display_path(raw_path).replace("\\", "/"),
                "raw_step_count": len(raw_steps),
                "parsed_step_count": row.get("step_count", ""),
                "raw_tool_call_count": raw_tool_call_count,
                "parsed_tool_call_count": row.get("tool_call_count", ""),
                "raw_tool_call_steps": raw_tool_call_steps,
                "parsed_shell_invocation_count": row.get("shell_invocation_count", ""),
                "shell_invocation_examples": " || ".join(command_examples),
                "observation_steps": observation_steps,
                "parsed_observation_chars": row.get("observation_chars", ""),
                "metrics_steps_raw": metrics_steps,
                "parsed_metric_step_count": row.get("metric_step_count", ""),
                "parsed_prompt_tokens": row.get("prompt_tokens", ""),
                "parsed_completion_tokens": row.get("completion_tokens", ""),
                "parsed_total_tokens": row.get("total_tokens", ""),
                "final_metrics_keys": "|".join(sorted(final_metrics.keys())[:20]),
                "reasoning_steps": reasoning_steps,
                "parsed_reasoning_chars": row.get("reasoning_chars", ""),
                "duration_seconds": row.get("duration_seconds", ""),
                "manual_validation_status": "prepared_for_researcher_review",
                "read_error": read_error,
            }
        )

    fields = [
        "benchmark",
        "scaffold",
        "model_dir",
        "provider",
        "leaderboard_date",
        "task_name",
        "reward",
        "outcome",
        "rel_path",
        "repository_path",
        "raw_step_count",
        "parsed_step_count",
        "raw_tool_call_count",
        "parsed_tool_call_count",
        "raw_tool_call_steps",
        "parsed_shell_invocation_count",
        "shell_invocation_examples",
        "observation_steps",
        "parsed_observation_chars",
        "metrics_steps_raw",
        "parsed_metric_step_count",
        "parsed_prompt_tokens",
        "parsed_completion_tokens",
        "parsed_total_tokens",
        "final_metrics_keys",
        "reasoning_steps",
        "parsed_reasoning_chars",
        "duration_seconds",
        "manual_validation_status",
        "read_error",
    ]
    with (out / "parser_validation_sample.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)


def official_leaderboard_summary(entry: dict[str, Any]) -> dict[str, Any]:
    return {field: entry.get(field, "") for field in OFFICIAL_LEADERBOARD_FIELDS}


def outcome_label(data: dict[str, Any]) -> str:
    containers = [data]
    if isinstance(data.get("final_metrics"), dict):
        containers.append(data["final_metrics"])
    for obj in containers:
        for key in ("success", "passed", "pass", "resolved", "is_success", "is_correct"):
            if key not in obj:
                continue
            val = obj.get(key)
            if isinstance(val, bool):
                return "pass" if val else "fail"
            if isinstance(val, (int, float)) and val in {0, 1}:
                return "pass" if val == 1 else "fail"
        for key in ("score", "reward"):
            if key in obj and isinstance(obj.get(key), (int, float)):
                score = obj.get(key)
                if score == 1:
                    return "pass"
                if score == 0:
                    return "fail"
                return f"score_{score}"
        for key in ("result", "status", "outcome"):
            if key not in obj or not isinstance(obj.get(key), str):
                continue
            result = obj.get(key)
            low = result.lower()
            if low in {"pass", "passed", "success", "succeeded", "resolved", "correct"}:
                return "pass"
            if low in {"fail", "failed", "failure", "unresolved", "incorrect", "error"}:
                return "fail"
            return low[:80]
    return "missing"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--benchmark",
        choices=SUPPORTED_BENCHMARKS,
        default=None,
        help=(
            "Resolve root/out/leaderboard/index paths for a benchmark. "
            "Omit to use the Terminal-Bench 2.0 defaults."
        ),
    )
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--leaderboard", type=Path, default=None)
    ap.add_argument("--leaderboard-trials", type=Path, default=None)
    ap.add_argument("--trajectory-index", type=Path, default=None)
    args = ap.parse_args()

    benchmark_paths = (
        paths_for_benchmark(REPO_ROOT, args.benchmark)
        if args.benchmark is not None
        else None
    )
    root = args.root or (benchmark_paths.trajectories_dir if benchmark_paths else ROOT_DEFAULT)
    out = args.out or (benchmark_paths.processed_dir if benchmark_paths else OUT_DEFAULT)
    benchmark_name = benchmark_paths.benchmark if benchmark_paths else "terminal_bench_2_0"
    leaderboard_path = (
        args.leaderboard
        or (benchmark_paths.leaderboard_submissions if benchmark_paths else LEADERBOARD_DEFAULT)
    )
    leaderboard_trials_path = (
        args.leaderboard_trials
        or (benchmark_paths.leaderboard_trials if benchmark_paths else LEADERBOARD_TRIALS_DEFAULT)
    )
    trajectory_index = (
        args.trajectory_index
        or (benchmark_paths.trajectory_index if benchmark_paths else INDEX_DEFAULT)
    )

    out.mkdir(parents=True, exist_ok=True)

    paths = sorted(root.rglob("*.json"))
    index_by_rel = load_trajectory_index(trajectory_index, root)
    leaderboard_row_by_trial_id = load_leaderboard_trial_rows(leaderboard_trials_path)
    leaderboard_by_checksum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    leaderboard_by_row_id: dict[str, dict[str, Any]] = {}
    leaderboard_task_names: dict[str, str] = {}
    leaderboard_submissions: list[dict[str, Any]] = []
    if leaderboard_path.exists():
        try:
            leaderboard = load_json(leaderboard_path)
            if isinstance(leaderboard, list):
                for rank, entry in enumerate(leaderboard, start=1):
                    if not isinstance(entry, dict):
                        continue
                    submission_summary = {
                        "leaderboard_rank": rank,
                        "scaffold": entry.get("scaffold", ""),
                        "scaffold_version": entry.get("scaffold_version", ""),
                        "leaderboard_model": entry.get("model", ""),
                        "provider": entry.get("provider", ""),
                        "has_trajectories": entry.get("has_trajectories", ""),
                        "submission_url": entry.get("submission_url", ""),
                        **official_leaderboard_summary(entry),
                        **submission_accuracy_summary(entry, rank),
                    }
                    leaderboard_submissions.append(submission_summary)
                    row_id = harbor_row_id_from_url(submission_summary.get("submission_url", ""))
                    if row_id:
                        leaderboard_by_row_id[row_id] = {
                            "scaffold": entry.get("scaffold", ""),
                            "scaffold_version": entry.get("scaffold_version", ""),
                            "provider": entry.get("provider", ""),
                            "leaderboard_model": entry.get("model", ""),
                            "leaderboard_date": entry.get("leaderboard_date", ""),
                            "submission_url": entry.get("submission_url", ""),
                            "leaderboard_accuracy": submission_summary["leaderboard_accuracy"],
                            "leaderboard_model_organization": submission_summary["leaderboard_model_organization"],
                        }
                    for task in entry.get("tasks", []):
                        if not isinstance(task, dict):
                            continue
                        checksum = task.get("taskChecksum")
                        if not checksum:
                            continue
                        merged = {
                            "scaffold": entry.get("scaffold", ""),
                            "scaffold_version": entry.get("scaffold_version", ""),
                            "provider": entry.get("provider", ""),
                            "leaderboard_model": entry.get("model", ""),
                            "leaderboard_date": entry.get("leaderboard_date", ""),
                            "submission_url": entry.get("submission_url", ""),
                            "taskName": task.get("taskName", ""),
                            "nTrials": task.get("nTrials", ""),
                            "successCount": task.get("successCount", ""),
                            "leaderboard_accuracy": submission_summary["leaderboard_accuracy"],
                            "leaderboard_model_organization": submission_summary["leaderboard_model_organization"],
                        }
                        leaderboard_by_checksum[str(checksum)].append(merged)
                        if task.get("taskName"):
                            leaderboard_task_names[str(checksum)] = str(task.get("taskName"))
        except Exception:
            leaderboard_by_checksum = defaultdict(list)
            leaderboard_submissions = []
    leaderboard_cells = [item for items in leaderboard_by_checksum.values() for item in items]
    leaderboard_success_total = sum(int(item.get("successCount") or 0) for item in leaderboard_cells)
    leaderboard_trial_total = sum(int(item.get("nTrials") or 0) for item in leaderboard_cells)
    rows: list[dict[str, Any]] = []
    file_task_ids: set[str] = set()
    task_names: set[str] = set()
    command_head_counter = Counter()
    command_head_examples: dict[str, str] = {}

    for path in paths:
        try:
            data = load_json(path)
        except Exception as exc:
            rows.append({"path": display_path(path), "parse_error": str(exc)})
            continue
        if not isinstance(data, dict):
            continue

        rel = path.relative_to(root)
        rel_key = rel.as_posix()
        parts = rel.parts
        scaffold = parts[0] if len(parts) >= 1 else ""
        model_dir = parts[1] if len(parts) >= 2 else ""
        filename = path.stem
        file_task_id = filename.split("_", 1)[0] if "_" in filename else filename
        file_run_id = filename.split("_", 1)[1] if "_" in filename else ""
        index_meta = index_by_rel.get(rel_key, {})
        agent = data.get("agent") if isinstance(data.get("agent"), dict) else {}
        model_name = textish(agent.get("model_name") or model_dir)
        version = textish(agent.get("version") or "")
        extra = agent.get("extra") if isinstance(agent.get("extra"), dict) else {}
        original_format = textish(extra.get("original_format") or "")
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        task_id = textish(scalar_value(data, {"task_id", "task_name", "taskName", "instance_id"}, max_depth=5) or file_task_id)
        task_name = leaderboard_task_names.get(file_task_id, "")
        leaderboard_matches = [
            m for m in leaderboard_by_checksum.get(file_task_id, [])
            if str(m.get("scaffold", "")).lower() == scaffold.lower()
        ]
        if model_dir:
            model_low = model_dir.lower().replace("_", "-")
            exactish = [
                m for m in leaderboard_matches
                if str(m.get("leaderboard_model", "")).lower().replace("_", "-") in model_low
                or model_low in str(m.get("leaderboard_model", "")).lower().replace("_", "-")
            ]
            if exactish:
                leaderboard_matches = exactish
        exact_row_id = (
            leaderboard_row_by_trial_id.get(file_run_id)
            or leaderboard_row_by_trial_id.get(str(index_meta.get("trialId") or ""))
        )
        leaderboard_meta = (
            leaderboard_by_row_id.get(exact_row_id, {})
            if exact_row_id
            else {}
        ) or (leaderboard_matches[0] if leaderboard_matches else {})
        reward = index_meta.get("reward", "")
        outcome_from_reward = reward_outcome(reward)
        outcome = outcome_from_reward or outcome_label(data)
        duration_seconds = parse_float(index_meta.get("duration"))

        prompt_tokens = 0
        completion_tokens = 0
        cost_usd = 0.0
        metric_steps = 0
        cost_metric_steps = 0
        message_chars = 0
        reasoning_chars = 0
        obs_chars = 0
        tool_call_count = 0
        shell_invocation_count = 0
        source_counts = Counter()
        has_final_marker = False

        for idx, raw_step in enumerate(steps, start=1):
            if not isinstance(raw_step, dict):
                continue
            source_counts[textish(raw_step.get("source") or "")] += 1
            msg = textish(raw_step.get("message"))
            reasoning = textish(raw_step.get("reasoning_content"))
            obs_char_count, obs_has_final_marker = extract_observation_info(raw_step)
            message_chars += len(msg)
            reasoning_chars += len(reasoning)
            obs_chars += obs_char_count
            if COMPLETE_RE.search(msg) or obs_has_final_marker:
                has_final_marker = True

            metrics = raw_step.get("metrics") if isinstance(raw_step.get("metrics"), dict) else {}
            if metrics:
                metric_steps += 1
                prompt_tokens += int(metrics.get("prompt_tokens") or 0)
                completion_tokens += int(metrics.get("completion_tokens") or 0)
                if metrics.get("cost_usd") not in {"", None}:
                    try:
                        cost_usd += float(metrics.get("cost_usd"))
                        cost_metric_steps += 1
                    except (TypeError, ValueError):
                        pass

            calls = extract_tool_calls(raw_step)
            tool_call_count += len([c for c in calls if c.get("raw")])
            step_commands: list[tuple[str, str]] = []
            for call in calls:
                cmd = call.get("command", "")
                if cmd:
                    step_commands.append((call.get("tool", ""), cmd))
            if not step_commands and raw_step.get("source") == "agent":
                for cmd in extract_commands_from_text(msg):
                    step_commands.append(("fenced_bash", cmd))

            for tool, cmd in step_commands:
                shell_invocation_count += 1
                head = shell_head(cmd)
                command_head_counter[head] += 1
                if head not in command_head_examples:
                    cmd_lines = cmd.strip().splitlines()
                    command_head_examples[head] = (cmd_lines[0] if cmd_lines else "<blank>")[:240]

        row = {
            "benchmark": benchmark_name,
            "rel_path": str(rel),
            "scaffold": scaffold,
            "model_dir": model_dir,
            "agent_version": version,
            "model_name": model_name,
            "original_format": original_format,
            "source_scaffold_version": leaderboard_meta.get("scaffold_version", ""),
            "source_submission_url": leaderboard_meta.get("submission_url", ""),
            "task_id": task_id,
            "task_name": task_name,
            "file_task_id": file_task_id,
            "file_run_id": file_run_id,
            "reward": reward,
            "reward_outcome": outcome,
            "leaderboard_model": leaderboard_meta.get("leaderboard_model", ""),
            "leaderboard_accuracy": leaderboard_meta.get("leaderboard_accuracy", ""),
            "leaderboard_provider": leaderboard_meta.get("provider", ""),
            "leaderboard_date": leaderboard_meta.get("leaderboard_date", ""),
            "leaderboard_model_organization": leaderboard_meta.get("leaderboard_model_organization", ""),
            "step_count": len(steps),
            "agent_step_count": source_counts.get("agent", 0),
            "user_step_count": source_counts.get("user", 0),
            "system_step_count": source_counts.get("system", 0),
            "tool_call_count": tool_call_count,
            "shell_invocation_count": shell_invocation_count,
            "message_chars": message_chars,
            "reasoning_chars": reasoning_chars,
            "observation_chars": obs_chars,
            "metric_step_count": metric_steps,
            "prompt_tokens": prompt_tokens if metric_steps else "",
            "completion_tokens": completion_tokens if metric_steps else "",
            "total_tokens": prompt_tokens + completion_tokens if metric_steps else "",
            "cost_usd": round(cost_usd, 8) if cost_metric_steps else "",
            "duration_seconds": duration_seconds if duration_seconds is not None else "",
            "has_final_marker": has_final_marker,
        }
        row["effective_submission_id"] = build_effective_submission_id(row)
        final_metrics = data.get("final_metrics") if isinstance(data.get("final_metrics"), dict) else {}
        if final_metrics:
            row["prompt_tokens"] = final_metrics.get("total_prompt_tokens", row["prompt_tokens"])
            row["completion_tokens"] = final_metrics.get("total_completion_tokens", row["completion_tokens"])
            if row["prompt_tokens"] != "" and row["completion_tokens"] != "":
                row["total_tokens"] = int(row["prompt_tokens"] or 0) + int(row["completion_tokens"] or 0)
            if final_metrics.get("total_cost_usd") not in {"", None}:
                row["cost_usd"] = final_metrics.get("total_cost_usd", row["cost_usd"])
        rows.append(row)
        file_task_ids.add(file_task_id)
        if task_name:
            task_names.add(task_name)

    csv_fields = [
        "benchmark",
        "rel_path", "scaffold", "model_dir", "agent_version", "model_name", "original_format",
        "effective_submission_id", "source_scaffold_version", "source_submission_url",
        "task_id", "file_task_id", "task_name", "file_run_id", "reward", "reward_outcome",
        "leaderboard_model", "leaderboard_accuracy", "leaderboard_provider", "leaderboard_date",
        "leaderboard_model_organization",
        "step_count", "agent_step_count", "user_step_count", "system_step_count",
        "tool_call_count", "shell_invocation_count", "message_chars", "reasoning_chars", "observation_chars",
        "metric_step_count", "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd",
        "duration_seconds", "has_final_marker",
    ]
    with (out / "trajectory_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    submission_fields = [
        "leaderboard_rank", "scaffold", "scaffold_version", "leaderboard_model", "provider", "submission_url",
        "has_trajectories",
        *OFFICIAL_LEADERBOARD_FIELDS,
        *COMPUTED_SUBMISSION_FIELDS,
    ]
    with (out / "leaderboard_submission_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=submission_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leaderboard_submissions)

    with (out / "shell_invocation_patterns.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["rank", "count", "shell_invocation_head", "example_shell_invocation"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        rank = 1
        for head, count in command_head_counter.most_common(300):
            example = command_head_examples.get(head, head)
            writer.writerow({
                "rank": rank,
                "count": count,
                "shell_invocation_head": head,
                "example_shell_invocation": example,
            })
            rank += 1

    outcome_feature_rows: list[dict[str, Any]] = []
    feature_fields = [
        "step_count",
        "shell_invocation_count",
        "tool_call_count",
        "total_tokens",
        "cost_usd",
        "duration_seconds",
    ]
    for outcome_name in ("pass", "fail"):
        items = [row for row in rows if row.get("reward_outcome") == outcome_name]
        summary_row: dict[str, Any] = {"reward_outcome": outcome_name, "trajectory_count": len(items)}
        for field in feature_fields:
            values = [parse_float(row.get(field)) for row in items]
            values = [value for value in values if value is not None]
            summary = summarize_numeric(values)
            for stat in ("median", "p90"):
                summary_row[f"{field}_{stat}"] = summary.get(stat, "")
        outcome_feature_rows.append(summary_row)

    with (out / "trajectory_features_by_outcome.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(outcome_feature_rows[0].keys()) if outcome_feature_rows else ["reward_outcome", "trajectory_count"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(outcome_feature_rows)

    parser_validation_sample_path = out / "parser_validation_sample.csv"
    if benchmark_name == "terminal_bench_2_0":
        write_parser_validation_sample(rows, root, out)

    step_counts = [int(r["step_count"]) for r in rows if r.get("step_count") != ""]
    shell_invocation_counts = [int(r["shell_invocation_count"]) for r in rows if r.get("shell_invocation_count") != ""]
    tool_counts = [int(r["tool_call_count"]) for r in rows if r.get("tool_call_count") != ""]
    costs = [float(r["cost_usd"]) for r in rows if r.get("cost_usd") not in {"", None}]
    tokens = [float(r["total_tokens"]) for r in rows if r.get("total_tokens") not in {"", None}]
    durations = [float(r["duration_seconds"]) for r in rows if r.get("duration_seconds") not in {"", None}]
    leaderboard_accuracies = [
        float(s["leaderboard_accuracy"])
        for s in leaderboard_submissions
        if s.get("leaderboard_accuracy") not in {"", None}
    ]
    reward_values = [parse_float(r.get("reward")) for r in rows]
    reward_values = [value for value in reward_values if value is not None]
    reward_outcome_counts = Counter(str(r.get("reward_outcome", "")) for r in rows)
    pass_count = reward_outcome_counts.get("pass", 0)
    fail_count = reward_outcome_counts.get("fail", 0)
    binary_outcome_count = pass_count + fail_count

    stats = {
        "inputs": {
            "trajectory_root": display_path(root),
            "leaderboard": display_path(leaderboard_path) if leaderboard_path.exists() else "",
            "trajectory_index": display_path(trajectory_index) if trajectory_index.exists() else "",
        },
        "corpus": {
            "trajectory_count": len(rows),
            "unique_task_count": len(file_task_ids),
            "unique_task_name_count": len(task_names),
            "leaderboard_submission_count": len(leaderboard_submissions),
        },
        "outcomes": {
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pass_rate": pass_count / binary_outcome_count if binary_outcome_count else None,
            "reward_distribution": summarize_numeric(reward_values),
        },
        "leaderboard": {
            "aggregate_success_count": leaderboard_success_total,
            "aggregate_trial_count": leaderboard_trial_total,
            "aggregate_resolution_rate": (leaderboard_success_total / leaderboard_trial_total) if leaderboard_trial_total else None,
            "official_accuracy_distribution": summarize_numeric(leaderboard_accuracies),
        },
        "effort_distributions": {
            "step_count": summarize_numeric(step_counts),
            "shell_invocation_count": summarize_numeric(shell_invocation_counts),
            "tool_call_count": summarize_numeric(tool_counts),
            "total_tokens": summarize_numeric(tokens),
            "cost_usd": summarize_numeric(costs),
            "duration_seconds": summarize_numeric(durations),
        },
        "artifacts": {
            "trajectory_summary_csv": display_path(out / "trajectory_summary.csv"),
            "leaderboard_submission_summary_csv": display_path(out / "leaderboard_submission_summary.csv"),
            "shell_invocation_patterns_csv": display_path(out / "shell_invocation_patterns.csv"),
            "trajectory_features_by_outcome_csv": display_path(out / "trajectory_features_by_outcome.csv"),
            "parser_validation_sample_csv": (
                display_path(parser_validation_sample_path) if benchmark_name == "terminal_bench_2_0" else ""
            ),
        },
    }
    with (out / "corpus_stats.json").open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
