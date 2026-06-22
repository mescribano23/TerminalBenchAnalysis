#!/usr/bin/env python3
"""Characterize TerminalBench trajectory JSON files.

Outputs:
- data/processed/trajectory_summary.csv
- data/processed/leaderboard_submission_summary.csv
- data/processed/corpus_stats.json
- data/processed/command_patterns.csv
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


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
ROOT_DEFAULT = DATA_DIR / "trajectories" / "current_leaderboard"
OUT_DEFAULT = DATA_DIR / "processed"
LEADERBOARD_DEFAULT = DATA_DIR / "raw" / "leaderboard_submissions_current.json"
INDEX_DEFAULT = DATA_DIR / "indexes" / "trajectory_trials_current.json"

BASH_FENCE_RE = re.compile(r"```(?:bash|sh|shell)?\s*\n(.*?)```", re.IGNORECASE | re.DOTALL)
COMPLETE_RE = re.compile(r"\bCOMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\b")

OFFICIAL_LEADERBOARD_FIELDS = [
    "leaderboard_accuracy",
    "leaderboard_accuracy_percent",
    "leaderboard_stderr",
    "leaderboard_stderr_percent",
    "leaderboard_accuracy_ci95_pm_percent",
    "leaderboard_accuracy_display",
    "leaderboard_date",
    "leaderboard_agent_display_name",
    "leaderboard_model_display",
    "leaderboard_agent_organization",
    "leaderboard_model_organization",
]

COMPUTED_SUBMISSION_FIELDS = [
    "computed_submission_task_count",
    "computed_submission_success_count",
    "computed_submission_trial_count",
    "computed_submission_accuracy",
    "computed_submission_accuracy_percent",
    "computed_submission_weighted_trial_accuracy",
    "computed_submission_weighted_trial_accuracy_percent",
    "computed_submission_task_rate_variance",
    "computed_submission_accuracy_pm_percent",
    "computed_submission_binomial_accuracy_variance",
    "computed_submission_accuracy_display",
]


def leaderboard_display_name(entry: dict[str, Any]) -> str:
    agent_display_name = str(entry.get("agent") or entry.get("leaderboard_agent_display_name") or "").strip()
    if agent_display_name:
        return agent_display_name
    model_display_name = str(entry.get("model") or entry.get("leaderboard_model_display") or "").strip()
    if model_display_name:
        return model_display_name
    return str(entry.get("scaffold") or "").strip()


PURPOSE_PATTERNS: list[tuple[str, list[re.Pattern[str]]]] = [
    ("environment_inspection", [
        re.compile(r"^(ls|pwd|tree|find\b.*(?:-maxdepth|/app|\.)|du\b|df\b|whoami|env\b|printenv\b|uname\b)", re.I),
        re.compile(r"\b(ls -|pwd|tree|find\s+\.)\b", re.I),
    ]),
    ("file_content_search", [
        re.compile(r"^(rg|grep|ack|ag)\b", re.I),
        re.compile(r"\b(rg|grep|ack|ag)\b", re.I),
    ]),
    ("reading_files", [
        re.compile(r"^(cat|sed\s+-n|nl\b|head\b|tail\b|less\b|more\b|jq\b)", re.I),
        re.compile(r"\b(cat|sed\s+-n|nl\s+-ba|head|tail|jq)\b", re.I),
    ]),
    ("editing_writing_files", [
        re.compile(r"\b(cat\s+<<.*>|apply_patch|python\s+- <<|python3\s+- <<|perl\s+-pi|sed\s+-i|tee\b|echo\b.*>|printf\b.*>|touch\b|mkdir\b|mv\b|cp\b|rm\b)", re.I),
        re.compile(r"\b(vim|nano|ed)\b", re.I),
    ]),
    ("dependency_setup", [
        re.compile(r"\b(pip|pip3|uv|poetry|npm|pnpm|yarn|apt-get|apt|apk|cargo\s+(add|fetch|install)|go\s+mod|bundle\s+install|gem\s+install|conda|mamba)\b", re.I),
    ]),
    ("running_scripts_tests", [
        re.compile(r"\b(pytest|unittest|go\s+test|cargo\s+test|npm\s+test|pnpm\s+test|yarn\s+test|make\s+test|bats|rspec|mvn\s+test|gradle\s+test)\b", re.I),
        re.compile(r"^(python|python3|node|ruby|perl|bash|sh|Rscript|julia)\b", re.I),
        re.compile(r"\b(rustc|g\+\+|gcc|javac|java|tsc|mypy|ruff|eslint)\b", re.I),
    ]),
    ("debugging_diagnostics", [
        re.compile(r"\b(strace|gdb|lldb|pdb|ipdb|valgrind|lsof|ps\b|top\b|kill\b|curl\b|wget\b|diff\b|git\s+diff|git\s+status|git\s+log)\b", re.I),
        re.compile(r"\b(print|debug|trace|diagnos|repro|inspect)\b", re.I),
    ]),
    ("final_verification", [
        COMPLETE_RE,
        re.compile(r"\b(final|verify|verification|validate|all tests|submit)\b", re.I),
    ]),
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_trajectory_index(path: Path, root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Load the trajectory index and key it by corpus-relative path."""
    if not path.exists():
        return {}, {"path": display_path(path), "exists": False}

    text = path.read_text(encoding="utf-8")
    normalized_file_paths = False
    try:
        entries = json.loads(text)
    except json.JSONDecodeError:
        # Some older generated indexes used Windows paths with invalid JSON
        # escapes in filePath. Normalize only filePath strings and retry.
        def fix_filepath(match: re.Match[str]) -> str:
            nonlocal normalized_file_paths
            normalized_file_paths = True
            value = match.group(1).replace("\\", "/")
            value = re.sub(r"/+", "/", value)
            return f'"filePath": "{value}"'

        fixed = re.sub(r'"filePath"\s*:\s*"([^"]*)"', fix_filepath, text)
        entries = json.loads(fixed)

    if not isinstance(entries, list):
        return {}, {"path": display_path(path), "exists": True, "entry_count": 0, "error": "index root is not a list"}

    root_key = display_path(root).replace("\\", "/").rstrip("/")
    by_rel: dict[str, dict[str, Any]] = {}
    reward_counts: Counter[str] = Counter()
    missing_reward = 0
    invalid_reward = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        reward = entry.get("reward")
        if reward in {"", None}:
            missing_reward += 1
        else:
            try:
                reward_float = float(reward)
                if reward_float in {0.0, 1.0}:
                    reward_counts[str(int(reward_float))] += 1
                else:
                    invalid_reward += 1
                    reward_counts[str(reward_float)] += 1
            except (TypeError, ValueError):
                invalid_reward += 1
                reward_counts[str(reward)] += 1

        file_path = str(entry.get("filePath", "")).replace("\\", "/")
        file_path = re.sub(r"/+", "/", file_path)
        rel_key = ""
        if root_key and file_path.startswith(f"{root_key}/"):
            rel_key = file_path[len(root_key) + 1 :]
        else:
            marker = "data/trajectories/balanced_12/"
            if marker in file_path:
                rel_key = file_path.split(marker, 1)[1]
        if rel_key:
            by_rel[rel_key] = entry

    return by_rel, {
        "path": display_path(path),
        "exists": True,
        "entry_count": len(entries),
        "matched_path_key_count": len(by_rel),
        "reward_counts": dict(reward_counts),
        "missing_reward_count": missing_reward,
        "invalid_reward_count": invalid_reward,
        "normalized_file_paths_on_load": normalized_file_paths,
    }


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


def collect_key_paths(data: Any, prefix: str = "", max_depth: int = 4, limit: int = 5000) -> list[str]:
    out: list[str] = []

    def walk(obj: Any, path: str, depth: int) -> None:
        if len(out) >= limit or depth > max_depth:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{path}.{k}" if path else k
                out.append(p)
                walk(v, p, depth + 1)
        elif isinstance(obj, list):
            if obj:
                walk(obj[0], f"{path}[]", depth + 1)

    walk(data, prefix, 0)
    return out


def textish(value: Any, max_len: int = 20000) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:max_len]
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False)[:max_len]
    except TypeError:
        return str(value)[:max_len]


def extract_observation_text(step: dict[str, Any]) -> str:
    chunks: list[str] = []
    obs = step.get("observation")
    if obs is None:
        return ""

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in {"content", "output", "stdout", "stderr", "message", "text"} and not isinstance(v, (dict, list)):
                    chunks.append(textish(v, 5000))
                else:
                    walk(v)
        elif isinstance(obj, list):
            for v in obj[:10]:
                walk(v)
        elif isinstance(obj, str):
            chunks.append(obj[:5000])

    walk(obs)
    return "\n".join(c for c in chunks if c)


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
            calls.append({"tool": "", "command": textish(call, 1000), "raw": textish(call, 2000)})
            continue
        tool = textish(call.get("name") or call.get("tool_name") or call.get("function_name") or call.get("type") or "", 200)
        args = call.get("arguments") or call.get("args") or call.get("input")
        fn = call.get("function")
        if isinstance(fn, dict):
            tool = tool or textish(fn.get("name") or "", 200)
            args = args if args is not None else fn.get("arguments")
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
                args = parsed
            except json.JSONDecodeError:
                pass
        command = ""
        if isinstance(args, dict):
            for key in ("command", "cmd", "action", "input", "code"):
                if key in args:
                    command = textish(args[key], 5000)
                    break
        if not command:
            for key in ("command", "cmd", "action", "input", "code"):
                if key in call:
                    command = textish(call[key], 5000)
                    break
        calls.append({"tool": tool, "command": command, "raw": textish(call, 5000)})
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


def classify_command(command: str, step_index: int, step_count: int) -> str:
    text = (command or "").strip()
    if not text:
        return "unknown"
    if COMPLETE_RE.search(text):
        return "final_verification"
    if step_count and step_index >= max(1, math.floor(step_count * 0.8)):
        if re.search(r"\b(pytest|test|check|verify|validate|rustc|g\+\+|gcc|make|npm\s+test|go\s+test|cargo\s+test)\b", text, re.I):
            return "final_verification"
    for label, patterns in PURPOSE_PATTERNS:
        if label == "editing_writing_files" and any(p.search(text) for p in patterns):
            return label
    for label, patterns in PURPOSE_PATTERNS:
        if label in {"final_verification", "editing_writing_files"}:
            continue
        if any(p.search(text) for p in patterns):
            return label
    return "other"


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
        "min": min(values),
        "p25": percentile(values, 0.25),
        "median": median(values),
        "mean": mean(values),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "max": max(values),
    }


def parse_float(value: Any) -> float | None:
    if value in {"", None}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


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
    weighted_trial_accuracy = (total_successes / total_trials) if total_trials else None
    accuracy = mean(rates) if rates else weighted_trial_accuracy
    task_rate_variance = sample_variance(rates)
    task_rate_std_error = math.sqrt(task_rate_variance / len(rates)) if task_rate_variance is not None and rates else None
    binomial_p = weighted_trial_accuracy if weighted_trial_accuracy is not None else accuracy
    binomial_variance = (
        binomial_p * (1.0 - binomial_p) / total_trials
        if binomial_p is not None and total_trials
        else None
    )
    accuracy_percent = accuracy * 100.0 if accuracy is not None else None
    accuracy_pm_percent = task_rate_std_error * 100.0 if task_rate_std_error is not None else None
    accuracy_display = (
        f"{accuracy_percent:.1f}%+/- {accuracy_pm_percent:.1f}"
        if accuracy_percent is not None and accuracy_pm_percent is not None
        else (f"{accuracy_percent:.1f}%+/- N/A" if accuracy_percent is not None else "")
    )
    computed = {
        "leaderboard_rank": rank if rank is not None else "",
        "computed_submission_task_count": len(tasks),
        "computed_submission_success_count": total_successes,
        "computed_submission_trial_count": total_trials,
        "computed_submission_accuracy": accuracy if accuracy is not None else "",
        "computed_submission_accuracy_percent": accuracy_percent if accuracy_percent is not None else "",
        "computed_submission_weighted_trial_accuracy": weighted_trial_accuracy if weighted_trial_accuracy is not None else "",
        "computed_submission_weighted_trial_accuracy_percent": weighted_trial_accuracy * 100.0 if weighted_trial_accuracy is not None else "",
        "computed_submission_task_rate_variance": task_rate_variance if task_rate_variance is not None else "",
        "computed_submission_accuracy_pm_percent": accuracy_pm_percent if accuracy_pm_percent is not None else "",
        "computed_submission_binomial_accuracy_variance": binomial_variance if binomial_variance is not None else "",
        "computed_submission_accuracy_display": accuracy_display,
    }
    return computed


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


def duration_seconds(steps: list[dict[str, Any]]) -> float | None:
    from datetime import datetime

    times = []
    for step in steps:
        ts = step.get("timestamp")
        if not isinstance(ts, str):
            continue
        try:
            times.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
        except ValueError:
            pass
    if len(times) >= 2:
        return (max(times) - min(times)).total_seconds()
    return None


def quote_snippet(text: str, limit: int = 480) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--leaderboard", type=Path, default=LEADERBOARD_DEFAULT)
    ap.add_argument("--trajectory-index", type=Path, default=INDEX_DEFAULT)
    args = ap.parse_args()

    root = args.root
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    paths = sorted(root.rglob("*.json"))
    index_by_rel, index_stats = load_trajectory_index(args.trajectory_index, root)
    leaderboard_by_checksum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    leaderboard_task_names: dict[str, str] = {}
    leaderboard_submissions: list[dict[str, Any]] = []
    if args.leaderboard.exists():
        try:
            leaderboard = load_json(args.leaderboard)
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
                        "display_name": leaderboard_display_name(entry),
                        "submission_url": entry.get("submission_url", ""),
                        **official_leaderboard_summary(entry),
                        **submission_accuracy_summary(entry, rank),
                    }
                    leaderboard_submissions.append(submission_summary)
                    for task in entry.get("tasks", []):
                        if not isinstance(task, dict):
                            continue
                        checksum = task.get("taskChecksum")
                        if not checksum:
                            continue
                        merged = {
                            "scaffold": entry.get("scaffold", ""),
                            "scaffold_version": entry.get("scaffold_version", ""),
                            "leaderboard_model": entry.get("model", ""),
                            "provider": entry.get("provider", ""),
                            "display_name": leaderboard_display_name(entry),
                            "submission_url": entry.get("submission_url", ""),
                            "taskName": task.get("taskName", ""),
                            "taskChecksum": checksum,
                            "nTrials": task.get("nTrials", ""),
                            "avgResolutionRate": task.get("avgResolutionRate", ""),
                            "successCount": task.get("successCount", ""),
                            **{
                                field: submission_summary[field]
                                for field in OFFICIAL_LEADERBOARD_FIELDS
                            },
                            "trialUrl": task.get("trialUrl", ""),
                            **{
                                field: submission_summary[field]
                                for field in COMPUTED_SUBMISSION_FIELDS
                            },
                            "leaderboard_rank": submission_summary["leaderboard_rank"],
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
    all_key_paths = Counter()
    top_keys = Counter()
    agent_names = Counter()
    model_names = Counter()
    scaffolds = Counter()
    scaffold_models = Counter()
    original_formats = Counter()
    outcomes = Counter()
    task_ids = Counter()
    command_counter = Counter()
    command_head_counter = Counter()
    purpose_counter = Counter()
    purpose_by_scaffold = defaultdict(Counter)
    missing = Counter()
    schema_examples: dict[str, str] = {}

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
        agent = data.get("agent") if isinstance(data.get("agent"), dict) else {}
        agent_name = textish(agent.get("name") or scaffold, 200)
        model_name = textish(agent.get("model_name") or model_dir, 300)
        version = textish(agent.get("version") or "", 100)
        extra = agent.get("extra") if isinstance(agent.get("extra"), dict) else {}
        original_format = textish(extra.get("original_format") or "", 200)
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        task_id = textish(scalar_value(data, {"task_id", "task_name", "taskName", "instance_id"}, max_depth=5) or file_task_id, 300)
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
        leaderboard_meta = leaderboard_matches[0] if leaderboard_matches else {}
        trajectory_json_outcome = outcome_label(data)
        index_meta = index_by_rel.get(rel_key, {})
        reward = index_meta.get("reward", "")
        outcome_from_reward = reward_outcome(reward)
        outcome = outcome_from_reward or trajectory_json_outcome
        dur = duration_seconds([s for s in steps if isinstance(s, dict)])

        prompt_tokens = 0
        completion_tokens = 0
        cost_usd = 0.0
        metric_steps = 0
        message_chars = 0
        reasoning_chars = 0
        obs_chars = 0
        tool_call_count = 0
        command_count = 0
        source_counts = Counter()
        final_message = ""
        has_final_marker = False

        if not steps:
            missing["steps"] += 1
        for key in data.keys():
            top_keys[key] += 1
        for kp in collect_key_paths(data, max_depth=4):
            all_key_paths[kp] += 1

        for idx, raw_step in enumerate(steps, start=1):
            if not isinstance(raw_step, dict):
                continue
            source_counts[textish(raw_step.get("source") or "", 50)] += 1
            msg = textish(raw_step.get("message"), 20000)
            reasoning = textish(raw_step.get("reasoning_content"), 20000)
            obs_text = extract_observation_text(raw_step)
            message_chars += len(msg)
            reasoning_chars += len(reasoning)
            obs_chars += len(obs_text)
            if msg:
                final_message = msg
            if COMPLETE_RE.search(msg) or COMPLETE_RE.search(obs_text):
                has_final_marker = True

            metrics = raw_step.get("metrics") if isinstance(raw_step.get("metrics"), dict) else {}
            if metrics:
                metric_steps += 1
                prompt_tokens += int(metrics.get("prompt_tokens") or 0)
                completion_tokens += int(metrics.get("completion_tokens") or 0)
                try:
                    cost_usd += float(metrics.get("cost_usd") or 0.0)
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
                command_count += 1
                purpose = classify_command(cmd, idx, len(steps))
                head = shell_head(cmd)
                cmd_lines = cmd.strip().splitlines()
                command_counter[(cmd_lines[0] if cmd_lines else "<blank>")[:240]] += 1
                command_head_counter[head] += 1
                purpose_counter[purpose] += 1
                purpose_by_scaffold[scaffold][purpose] += 1

        row = {
            "path": display_path(path),
            "rel_path": str(rel),
            "file_size_bytes": path.stat().st_size,
            "schema_version": data.get("schema_version", ""),
            "session_id": data.get("session_id", ""),
            "scaffold": scaffold,
            "model_dir": model_dir,
            "agent_name": agent_name,
            "agent_version": version,
            "model_name": model_name,
            "original_format": original_format,
            "task_id": task_id,
            "task_name": task_name,
            "file_task_id": file_task_id,
            "file_run_id": file_run_id,
            "outcome": outcome,
            "reward": reward,
            "reward_outcome": outcome_from_reward,
            "trajectory_json_outcome": trajectory_json_outcome,
            "leaderboard_avg_resolution_rate": leaderboard_meta.get("avgResolutionRate", ""),
            "leaderboard_success_count": leaderboard_meta.get("successCount", ""),
            "leaderboard_n_trials": leaderboard_meta.get("nTrials", ""),
            "leaderboard_task_name": leaderboard_meta.get("taskName", ""),
            "leaderboard_model": leaderboard_meta.get("leaderboard_model", ""),
            "display_name": leaderboard_meta.get("display_name", ""),
            "submission_url": leaderboard_meta.get("submission_url", ""),
            "leaderboard_rank": leaderboard_meta.get("leaderboard_rank", ""),
            **{
                field: leaderboard_meta.get(field, "")
                for field in OFFICIAL_LEADERBOARD_FIELDS
            },
            **{
                field: leaderboard_meta.get(field, "")
                for field in COMPUTED_SUBMISSION_FIELDS
            },
            "step_count": len(steps),
            "agent_step_count": source_counts.get("agent", 0),
            "user_step_count": source_counts.get("user", 0),
            "system_step_count": source_counts.get("system", 0),
            "tool_call_count": tool_call_count,
            "command_count": command_count,
            "message_chars": message_chars,
            "reasoning_chars": reasoning_chars,
            "observation_chars": obs_chars,
            "metric_step_count": metric_steps,
            "prompt_tokens": prompt_tokens if metric_steps else "",
            "completion_tokens": completion_tokens if metric_steps else "",
            "total_tokens": prompt_tokens + completion_tokens if metric_steps else "",
            "cost_usd": round(cost_usd, 8) if metric_steps else "",
            "duration_seconds_from_timestamps": dur if dur is not None else "",
            "has_final_marker": has_final_marker,
            "final_message_snippet": quote_snippet(final_message, 500),
            "top_level_keys": ",".join(data.keys()),
        }
        final_metrics = data.get("final_metrics") if isinstance(data.get("final_metrics"), dict) else {}
        if final_metrics:
            row["prompt_tokens"] = final_metrics.get("total_prompt_tokens", row["prompt_tokens"])
            row["completion_tokens"] = final_metrics.get("total_completion_tokens", row["completion_tokens"])
            if row["prompt_tokens"] != "" and row["completion_tokens"] != "":
                row["total_tokens"] = int(row["prompt_tokens"] or 0) + int(row["completion_tokens"] or 0)
            if "total_cost_usd" in final_metrics:
                row["cost_usd"] = final_metrics.get("total_cost_usd", row["cost_usd"])
        rows.append(row)
        agent_names[agent_name] += 1
        model_names[model_name] += 1
        scaffolds[scaffold] += 1
        scaffold_models[f"{scaffold}/{model_dir}"] += 1
        original_formats[original_format] += 1
        outcomes[outcome] += 1
        task_ids[task_id] += 1
        if original_format and original_format not in schema_examples:
            schema_examples[original_format] = str(rel)

    csv_fields = [
        "rel_path", "path", "file_size_bytes", "schema_version", "session_id", "scaffold", "model_dir",
        "agent_name", "agent_version", "model_name", "original_format", "task_id", "file_task_id",
        "task_name", "file_run_id", "outcome", "reward", "reward_outcome", "trajectory_json_outcome",
        "leaderboard_avg_resolution_rate", "leaderboard_success_count",
        "leaderboard_n_trials", "leaderboard_task_name", "leaderboard_model", "submission_url",
        "leaderboard_rank", "display_name",
        *OFFICIAL_LEADERBOARD_FIELDS,
        *COMPUTED_SUBMISSION_FIELDS,
        "step_count", "agent_step_count", "user_step_count", "system_step_count",
        "tool_call_count", "command_count", "message_chars", "reasoning_chars", "observation_chars",
        "metric_step_count", "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd",
        "duration_seconds_from_timestamps", "has_final_marker", "final_message_snippet", "top_level_keys",
    ]
    with (out / "trajectory_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    submission_fields = [
        "leaderboard_rank", "scaffold", "scaffold_version", "leaderboard_model", "provider", "submission_url",
        "has_trajectories", "display_name",
        *OFFICIAL_LEADERBOARD_FIELDS,
        *COMPUTED_SUBMISSION_FIELDS,
    ]
    with (out / "leaderboard_submission_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=submission_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leaderboard_submissions)

    with (out / "command_patterns.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["rank", "count", "command_head", "purpose_candidate", "example_command"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        rank = 1
        for example, count in command_counter.most_common(300):
            purpose = classify_command(example, 0, 0)
            writer.writerow({
                "rank": rank,
                "count": count,
                "command_head": shell_head(example),
                "purpose_candidate": purpose,
                "example_command": example,
            })
            rank += 1

    outcome_feature_rows: list[dict[str, Any]] = []
    feature_fields = [
        "step_count",
        "command_count",
        "tool_call_count",
        "message_chars",
        "observation_chars",
        "total_tokens",
        "cost_usd",
        "duration_seconds_from_timestamps",
    ]
    for outcome_name in ("pass", "fail"):
        items = [row for row in rows if row.get("reward_outcome") == outcome_name]
        summary_row: dict[str, Any] = {"reward_outcome": outcome_name, "trajectory_count": len(items)}
        for field in feature_fields:
            values = [parse_float(row.get(field)) for row in items]
            values = [value for value in values if value is not None]
            summary = summarize_numeric(values)
            for stat in ("median", "mean", "p75", "p90", "max"):
                summary_row[f"{field}_{stat}"] = summary.get(stat, "")
        outcome_feature_rows.append(summary_row)

    with (out / "trajectory_features_by_outcome.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(outcome_feature_rows[0].keys()) if outcome_feature_rows else ["reward_outcome", "trajectory_count"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(outcome_feature_rows)

    step_counts = [int(r["step_count"]) for r in rows if r.get("step_count") != ""]
    command_counts = [int(r["command_count"]) for r in rows if r.get("command_count") != ""]
    tool_counts = [int(r["tool_call_count"]) for r in rows if r.get("tool_call_count") != ""]
    costs = [float(r["cost_usd"]) for r in rows if r.get("cost_usd") not in {"", None}]
    tokens = [float(r["total_tokens"]) for r in rows if r.get("total_tokens") not in {"", None}]
    durations = [float(r["duration_seconds_from_timestamps"]) for r in rows if r.get("duration_seconds_from_timestamps") not in {"", None}]
    leaderboard_rates = [float(r["leaderboard_avg_resolution_rate"]) for r in rows if r.get("leaderboard_avg_resolution_rate") not in {"", None}]
    submission_accuracies = [
        float(s["computed_submission_accuracy"])
        for s in leaderboard_submissions
        if s.get("computed_submission_accuracy") not in {"", None}
    ]
    leaderboard_accuracies = [
        float(s["leaderboard_accuracy"])
        for s in leaderboard_submissions
        if s.get("leaderboard_accuracy") not in {"", None}
    ]
    leaderboard_accuracy_pms = [
        float(s["leaderboard_accuracy_ci95_pm_percent"])
        for s in leaderboard_submissions
        if s.get("leaderboard_accuracy_ci95_pm_percent") not in {"", None}
    ]
    submission_accuracy_pms = [
        float(s["computed_submission_accuracy_pm_percent"])
        for s in leaderboard_submissions
        if s.get("computed_submission_accuracy_pm_percent") not in {"", None}
    ]
    submission_task_rate_variances = [
        float(s["computed_submission_task_rate_variance"])
        for s in leaderboard_submissions
        if s.get("computed_submission_task_rate_variance") not in {"", None}
    ]
    reward_values = [parse_float(r.get("reward")) for r in rows]
    reward_values = [value for value in reward_values if value is not None]
    reward_outcome_counts = Counter(str(r.get("reward_outcome", "")) for r in rows)

    # Coarse task-family hints from task ids and user prompt text.
    family_patterns = {
        "polyglot/compiler": re.compile(r"\b(polyglot|rustc|g\+\+|gcc|compiler|compile)\b", re.I),
        "python/data": re.compile(r"\b(python|pandas|numpy|csv|json|parquet|dataframe)\b", re.I),
        "web/api": re.compile(r"\b(http|api|server|flask|fastapi|express|request|curl)\b", re.I),
        "shell/filesystem": re.compile(r"\b(bash|shell|file|directory|path|chmod|tar|grep|sed|awk)\b", re.I),
        "ml/math": re.compile(r"\b(model|tensor|torch|sklearn|matrix|fibonacci|algorithm|numeric)\b", re.I),
        "database": re.compile(r"\b(sql|sqlite|postgres|database|query)\b", re.I),
        "build/test": re.compile(r"\b(make|cmake|pytest|test|package|dependency|install)\b", re.I),
        "security/crypto": re.compile(r"\b(crypto|hash|password|rsa|aes|decrypt|encrypt|vulnerab)\b", re.I),
    }
    family_counts = Counter()
    for row in rows:
        text = f"{row.get('task_id','')} {row.get('final_message_snippet','')}"
        matched = False
        for fam, pat in family_patterns.items():
            if pat.search(text):
                family_counts[fam] += 1
                matched = True
        if not matched:
            family_counts["unclassified_from_available_text"] += 1

    stats = {
        "root": display_path(root),
        "leaderboard": display_path(args.leaderboard) if args.leaderboard.exists() else "",
        "trajectory_index": index_stats,
        "trajectory_index_matched_rows": sum(1 for row in rows if row.get("reward") not in {"", None}),
        "trajectory_index_unmatched_rows": sum(1 for row in rows if row.get("reward") in {"", None}),
        "reward_distribution": summarize_numeric(reward_values),
        "reward_outcome_counts": reward_outcome_counts.most_common(),
        "leaderboard_task_checksum_count": len(leaderboard_by_checksum),
        "leaderboard_scaffold_model_task_cells": len(leaderboard_cells),
        "leaderboard_aggregate_success_count": leaderboard_success_total,
        "leaderboard_aggregate_trial_count": leaderboard_trial_total,
        "leaderboard_aggregate_resolution_rate": (leaderboard_success_total / leaderboard_trial_total) if leaderboard_trial_total else None,
        "leaderboard_submission_count": len(leaderboard_submissions),
        "leaderboard_official_accuracy_distribution": summarize_numeric(leaderboard_accuracies),
        "leaderboard_official_accuracy_ci95_pm_percent_distribution": summarize_numeric(leaderboard_accuracy_pms),
        "computed_submission_accuracy_distribution": summarize_numeric(submission_accuracies),
        "computed_submission_accuracy_pm_percent_distribution": summarize_numeric(submission_accuracy_pms),
        "computed_submission_task_rate_variance_distribution": summarize_numeric(submission_task_rate_variances),
        "trajectory_count": len(rows),
        "unique_task_count": len(task_ids),
        "top_level_keys": top_keys.most_common(),
        "common_key_paths": all_key_paths.most_common(120),
        "scaffolds": scaffolds.most_common(),
        "scaffold_models": scaffold_models.most_common(),
        "agent_names": agent_names.most_common(),
        "model_names": model_names.most_common(),
        "original_formats": original_formats.most_common(),
        "schema_examples_by_original_format": schema_examples,
        "outcomes": outcomes.most_common(),
        "step_count_distribution": summarize_numeric(step_counts),
        "command_count_distribution": summarize_numeric(command_counts),
        "tool_call_count_distribution": summarize_numeric(tool_counts),
        "cost_usd_distribution": summarize_numeric(costs),
        "total_token_distribution": summarize_numeric(tokens),
        "duration_seconds_distribution": summarize_numeric(durations),
        "leaderboard_avg_resolution_rate_distribution_for_matched_rows": summarize_numeric(leaderboard_rates),
        "metric_presence_count": len(costs),
        "missing_or_inconsistent": missing.most_common(),
        "command_head_counts": command_head_counter.most_common(100),
        "purpose_counts": purpose_counter.most_common(),
        "purpose_by_scaffold": {k: v.most_common() for k, v in purpose_by_scaffold.items()},
        "task_family_hints": family_counts.most_common(),
        "artifacts": {
            "trajectory_summary_csv": display_path(out / "trajectory_summary.csv"),
            "leaderboard_submission_summary_csv": display_path(out / "leaderboard_submission_summary.csv"),
            "command_patterns_csv": display_path(out / "command_patterns.csv"),
            "trajectory_features_by_outcome_csv": display_path(out / "trajectory_features_by_outcome.csv"),
        },
    }
    with (out / "corpus_stats.json").open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
