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
        else:
            marker = "data/trajectories/balanced_12/"
            if marker in file_path:
                rel_key = file_path.split(marker, 1)[1]
        if rel_key:
            by_rel[rel_key] = entry

    return by_rel


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


def command_text(value: Any, max_len: int = 5000) -> str:
    """Normalize command-like tool arguments across scaffold schemas."""
    if isinstance(value, list) and all(isinstance(part, (str, int, float, bool)) for part in value):
        return " ".join(shlex.quote(str(part)) for part in value)[:max_len]
    return textish(value, max_len)


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
            for key in COMMAND_ARGUMENT_KEYS:
                if key in args:
                    command = command_text(args[key], 5000)
                    break
        if not command:
            for key in COMMAND_ARGUMENT_KEYS:
                if key in call:
                    command = command_text(call[key], 5000)
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
    task_rate_variance = sample_variance(rates)
    computed = {
        "leaderboard_rank": rank if rank is not None else "",
        "computed_submission_success_count": total_successes,
        "computed_submission_trial_count": total_trials,
        "computed_submission_task_rate_variance": task_rate_variance if task_rate_variance is not None else "",
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
    index_by_rel = load_trajectory_index(args.trajectory_index, root)
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
                            "leaderboard_model": entry.get("model", ""),
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
        agent = data.get("agent") if isinstance(data.get("agent"), dict) else {}
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
        index_meta = index_by_rel.get(rel_key, {})
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
        command_count = 0
        source_counts = Counter()
        has_final_marker = False

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
            if COMPLETE_RE.search(msg) or COMPLETE_RE.search(obs_text):
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
                command_count += 1
                head = shell_head(cmd)
                command_head_counter[head] += 1
                if head not in command_head_examples:
                    cmd_lines = cmd.strip().splitlines()
                    command_head_examples[head] = (cmd_lines[0] if cmd_lines else "<blank>")[:240]

        row = {
            "rel_path": str(rel),
            "scaffold": scaffold,
            "model_dir": model_dir,
            "agent_version": version,
            "model_name": model_name,
            "original_format": original_format,
            "task_id": task_id,
            "task_name": task_name,
            "file_task_id": file_task_id,
            "file_run_id": file_run_id,
            "reward": reward,
            "reward_outcome": outcome,
            "leaderboard_model": leaderboard_meta.get("leaderboard_model", ""),
            "leaderboard_accuracy": leaderboard_meta.get("leaderboard_accuracy", ""),
            "leaderboard_model_organization": leaderboard_meta.get("leaderboard_model_organization", ""),
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
            "cost_usd": round(cost_usd, 8) if cost_metric_steps else "",
            "duration_seconds": duration_seconds if duration_seconds is not None else "",
            "has_final_marker": has_final_marker,
        }
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
        "rel_path", "scaffold", "model_dir", "agent_version", "model_name", "original_format",
        "task_id", "file_task_id", "task_name", "file_run_id", "reward", "reward_outcome",
        "leaderboard_model", "leaderboard_accuracy", "leaderboard_model_organization",
        "step_count", "agent_step_count", "user_step_count", "system_step_count",
        "tool_call_count", "command_count", "message_chars", "reasoning_chars", "observation_chars",
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

    with (out / "command_patterns.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["rank", "count", "command_head", "example_command"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        rank = 1
        for head, count in command_head_counter.most_common(300):
            example = command_head_examples.get(head, head)
            writer.writerow({
                "rank": rank,
                "count": count,
                "command_head": head,
                "example_command": example,
            })
            rank += 1

    outcome_feature_rows: list[dict[str, Any]] = []
    feature_fields = [
        "step_count",
        "command_count",
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

    step_counts = [int(r["step_count"]) for r in rows if r.get("step_count") != ""]
    command_counts = [int(r["command_count"]) for r in rows if r.get("command_count") != ""]
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
            "leaderboard": display_path(args.leaderboard) if args.leaderboard.exists() else "",
            "trajectory_index": display_path(args.trajectory_index) if args.trajectory_index.exists() else "",
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
            "command_count": summarize_numeric(command_counts),
            "tool_call_count": summarize_numeric(tool_counts),
            "total_tokens": summarize_numeric(tokens),
            "cost_usd": summarize_numeric(costs),
            "duration_seconds": summarize_numeric(durations),
        },
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
