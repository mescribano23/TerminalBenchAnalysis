#!/usr/bin/env python3
"""RQ2.3 tool-use association analysis.

Main question:
How does trajectory-level tool use relate to success across task domains?

Outputs:
- reports/tasks/tools/rq2_3_tool_success_association_by_category.png
- reports/tasks/tools/rq2_3_tool_success_association_by_difficulty.png, only if informative
- reports/tasks/tools/rq2_3_functional_success_association_by_category.png
- reports/tasks/tools/rq2_3_functional_success_association_by_difficulty.png, only if informative
- data/processed_live/task_mining/tools/rq2_3_functional_behavior_inference.csv

Behavior use is measured per trajectory. Repeated trials are not aggregated
within submissions. Overall descriptive results are pooled over trajectories.
Category and difficulty summaries are task-balanced: tool use is still measured
per trajectory, but used-vs-not-used success contrasts are first computed within
each task and then averaged across eligible tasks. Overall functional contrasts
also receive paired task-level Cohen's dz and Wilcoxon signed-rank inference.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT_CANDIDATE = SCRIPT_DIR.parent.parent.parent
if str(REPO_ROOT_CANDIDATE) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_CANDIDATE))

from scripts.analysis.support_thresholds import MINIMUM_SUPPORT_PER_COMPARISON_CELL
from scripts.analysis.statistical_helpers import paired_cohens_dz, two_sided_signed_rank
from scripts.analysis.plot_style import (
    DIVERGING_CMAP,
    FAIL_COLOR,
    HEATMAP_DPI,
    PASS_COLOR,
    colorblind_cmap,
    heatmap_text_color,
)
from scripts.benchmark_paths import find_repo_root


REPO_ROOT = find_repo_root(SCRIPT_DIR)
DATA_DIR = REPO_ROOT / "data"
DATA_PROCESSED_LIVE_DIR = DATA_DIR / "processed_live"
REPORTS_DIR = REPO_ROOT / "reports"

BENCHMARK_DEFAULT = "terminal_bench_2_0"
TRAJECTORY_SUMMARY_DEFAULT = DATA_PROCESSED_LIVE_DIR / BENCHMARK_DEFAULT / "trajectory_summary.csv"
TRAJECTORY_ROOT_DEFAULT = DATA_DIR / "trajectories" / BENCHMARK_DEFAULT
TASKS_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining" / "terminal_bench_2_task_toml_metadata.csv"
OUT_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining" / "tools"
FIGURES_DEFAULT = REPORTS_DIR / "tasks" / "tools"

MAIN_TOOL_FAMILIES = ("terminal", "file_search_read", "file_edit", "web_or_network")
FUNCTIONAL_FAMILIES = (
    "inspect_search",
    "modify_write",
    "execute_run",
    "test_validate",
    "environment_dependencies",
    "version_control",
    "data_query_transform",
    "network_external",
    "media_specialized",
)
OUTCOME_COLUMNS = {"reward_outcome", "outcome", "reward"}
COMMAND_ARGUMENT_KEYS = ("command", "cmd", "keystrokes", "action", "input", "code")
MIN_CELL_SUPPORT_DEFAULT = MINIMUM_SUPPORT_PER_COMPARISON_CELL
DIFFICULTY_FIGURE_MIN_RANGE_PP_DEFAULT = 5.0
EXAMPLES_PER_FUNCTIONAL_FAMILY = 5

BASH_FENCE_RE = re.compile(r"```(?:bash|sh|shell)\s*\n(.*?)```", re.IGNORECASE | re.DOTALL)
FUNCTION_TAG_RE = re.compile(
    r"<function(?:=|>)\s*([A-Za-z0-9_.:-]+)\s*>?(.*?)(?=<function(?:=|>)|</function_calls>|$)",
    re.IGNORECASE | re.DOTALL,
)

TOOL_NAME_FAMILY_RULES: list[tuple[str, str]] = [
    (r"\b(run_shell_command|execute_bash|fenced_bash|bash|bashoutput|killshell|shell|terminal)\b", "terminal"),
    (r"\b(str_replace_editor|edit|multiedit|editor|write|write_file|patch|apply_patch)\b", "file_edit"),
    (r"\b(read|view|open|glob|grep|search|find|list)\b", "file_search_read"),
    (r"\b(browser|web|webfetch|fetch|http|get_url)\b", "web_or_network"),
    (r"\b(task_tracker|todo|todowrite|task|plan)\b", "task_management"),
    (r"\b(think|reason)\b", "reasoning"),
    (r"\b(finish|final|submit)\b", "finish_submit"),
]

DECLARATION_PATTERNS: list[tuple[str, str]] = [
    (r"\b(run_shell_command|execute_bash|bash|shell|terminal)\b", "terminal"),
    (r"\b(str_replace_editor|editor|write_file|apply_patch|patch)\b", "file_edit"),
    (r"\b(glob|grep|search|read|view|open file|file search)\b", "file_search_read"),
    (r"\b(browser|web search|fetch|http|get_url)\b", "web_or_network"),
    (r"\b(task_tracker|todo|plan)\b", "task_management"),
    (r"\b(think)\b", "reasoning"),
    (r"\b(finish|submit final)\b", "finish_submit"),
]

TOOL_FAMILY_DISPLAY = {
    "terminal": "Terminal",
    "file_search_read": "File search/read",
    "file_edit": "File edit",
    "web_or_network": "Web/network",
    "task_management": "Task management",
    "reasoning": "Reasoning tool",
    "finish_submit": "Finish/submit",
    "unknown_other": "Unknown/other",
}
TOOL_FAMILY_DISPLAY_ORDER = [TOOL_FAMILY_DISPLAY[family] for family in MAIN_TOOL_FAMILIES]

FUNCTIONAL_FAMILY_DISPLAY = {
    "inspect_search": "Inspect/search",
    "modify_write": "Modify/write",
    "execute_run": "Execute/run",
    "test_validate": "Test/validate",
    "environment_dependencies": "Environment/dependencies",
    "version_control": "Version control",
    "data_query_transform": "Data query/transform",
    "network_external": "Network/external",
    "media_specialized": "Media/specialized",
}
FUNCTIONAL_FAMILY_DISPLAY_ORDER = [FUNCTIONAL_FAMILY_DISPLAY[family] for family in FUNCTIONAL_FAMILIES]
CORE_FUNCTIONAL_FAMILY_DISPLAY_ORDER = [
    FUNCTIONAL_FAMILY_DISPLAY[family]
    for family in ("inspect_search", "modify_write", "execute_run", "test_validate")
]

DIFFICULTY_ORDER = ["easy", "medium", "hard"]
CATEGORY_DISPLAY_LABELS = {
    "data-processing": "data\nproc.",
    "data-science": "data-\nscience",
    "debugging": "debugging",
    "file-operations": "file\nops.",
    "machine-learning": "machine\nlearning",
    "mathematics": "mathematics",
    "model-training": "model-\ntraining",
    "scientific-computing": "scientific\ncomputing",
    "security": "security",
    "software-engineering": "software\neng.",
    "system-administration": "system\nadmin",
}
OBSOLETE_FIGURES = (
    "rq2_3_tool_success_association_overall.png",
    "rq2_3_tool_use_by_category.png",
    "rq2_3_tool_use_by_difficulty.png",
    "heatmap_tool_availability_category_delta.png",
    "heatmap_tool_use_category_delta.png",
)
OBSOLETE_TABLES = (
    "rq2_3_tool_availability_audit.csv",
    "rq2_3_tool_use_overall.csv",
    "rq2_3_tool_use_by_category.csv",
    "rq2_3_tool_use_by_difficulty.csv",
    "rq2_3_functional_use_overall.csv",
    "rq2_3_functional_use_by_category.csv",
    "rq2_3_functional_use_by_difficulty.csv",
    "rq2_3_functional_wilcoxon.csv",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-summary", type=Path, default=TRAJECTORY_SUMMARY_DEFAULT)
    parser.add_argument("--trajectory-root", type=Path, default=TRAJECTORY_ROOT_DEFAULT)
    parser.add_argument("--tasks", type=Path, default=TASKS_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DEFAULT)
    parser.add_argument("--max-trajectories", type=int, default=None)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--progress-every", type=int, default=1000)
    parser.add_argument("--difficulty-figure-min-range-pp", type=float, default=DIFFICULTY_FIGURE_MIN_RANGE_PP_DEFAULT)
    args = parser.parse_args()
    args.min_cell_support = MIN_CELL_SUPPORT_DEFAULT
    return args


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


def normalize_name(value: Any) -> str:
    return re.sub(r"\s+", "_", textish(value, 300).strip().lower()).replace("-", "_")


def tool_family(tool_name: str, has_command: bool = False) -> str:
    normalized_tool = normalize_name(tool_name)
    for pattern, family in TOOL_NAME_FAMILY_RULES:
        if re.search(pattern, normalized_tool, re.IGNORECASE):
            return family
    if has_command:
        return "terminal"
    return "unknown_other"


def command_from_args(args: Any) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return args
    if isinstance(args, dict):
        for key in COMMAND_ARGUMENT_KEYS:
            if key in args:
                return textish(args[key], 5000)
    return ""


def extract_structured_tool_calls(step: dict[str, Any]) -> list[tuple[str, bool, str]]:
    raw_calls = step.get("tool_calls") or []
    if not isinstance(raw_calls, list):
        raw_calls = [raw_calls]

    calls: list[tuple[str, bool, str]] = []
    for call in raw_calls:
        if not isinstance(call, dict):
            command = textish(call, 1000)
            calls.append(("", bool(command), command))
            continue
        tool = textish(
            call.get("name")
            or call.get("tool_name")
            or call.get("function_name")
            or call.get("type")
            or "",
            200,
        )
        args = call.get("arguments") or call.get("args") or call.get("input")
        fn = call.get("function")
        if isinstance(fn, dict):
            tool = tool or textish(fn.get("name") or "", 200)
            args = args if args is not None else fn.get("arguments")
        command = command_from_args(args)
        if not command:
            command = command_from_args(call)
        calls.append((tool, bool(command), command))
    return calls


def extract_embedded_function_calls(message: str) -> list[tuple[str, bool, str]]:
    return [
        (match.group(1).strip(), bool(match.group(2).strip()), match.group(2).strip())
        for match in FUNCTION_TAG_RE.finditer(message or "")
    ]


def extract_fenced_shell_commands(message: str) -> list[str]:
    return [match.group(1).strip() for match in BASH_FENCE_RE.finditer(message or "") if match.group(1).strip()]


def command_segments(command: str) -> list[str]:
    cleaned = re.sub(r"\\\s*\n", " ", command or "")
    if "<<" in cleaned:
        cleaned = re.split(r"<<\s*['\"]?[A-Za-z0-9_]+['\"]?", cleaned, maxsplit=1)[0]
    cleaned = "\n".join(line for line in cleaned.splitlines() if not line.lstrip().startswith("#"))
    return [segment.strip() for segment in re.split(r"\s*(?:&&|\|\||;|\n)\s*", cleaned) if segment.strip()]


def command_matches(segment: str, pattern: str) -> bool:
    return bool(re.search(pattern, segment, re.IGNORECASE))


def shell_surface(segment: str) -> str:
    surface = re.split(r"<<\s*['\"]?[A-Za-z0-9_]+['\"]?", segment or "", maxsplit=1)[0]
    return surface.split("|", 1)[0].strip()


def functional_families_from_command(command: str) -> set[str]:
    families: set[str] = set()
    for segment in command_segments(command):
        lowered = shell_surface(segment).lower()
        if not lowered:
            continue

        is_test = any(
            command_matches(lowered, pattern)
            for pattern in [
                r"\b(pytest|tox|nox|unittest|nosetests)\b",
                r"\bpython(?:3)?\s+-m\s+(pytest|unittest|mypy|ruff|flake8|pyright|pylint)\b",
                r"\b(npm|pnpm|yarn)\s+(run\s+)?(test|lint|check|typecheck|build)\b",
                r"\b(cargo|go|mvn|gradle)\s+(test|check|build|verify)\b",
                r"\bmake\s+([A-Za-z0-9_.-]*-)?(test|check|validate|build)\b",
                r"\b(ruff|flake8|mypy|pyright|pylint|eslint|tsc|shellcheck|black\s+--check|prettier\s+--check)\b",
                r"\b(?:python|python3|node|bash|sh)\s+[^;\n]*(?:test|validate|validation|check)[^;\n]*\.(py|sh|js|ts)\b",
                r"(^|\s)\./[^;\n]*(?:test|validate|validation|check)[^;\n]*",
            ]
        )
        if is_test:
            families.add("test_validate")

        if any(
            command_matches(lowered, pattern)
            for pattern in [
                r"(^|\s)(?:ls|dir|pwd|cat|less|more|head|tail|find|grep|rg|tree|wc)\b",
                r"\bsed\s+-n\b",
                r"\bawk\b",
                r"\bstat\b",
            ]
        ):
            families.add("inspect_search")

        if any(
            command_matches(lowered, pattern)
            for pattern in [
                r"\bapply_patch\b",
                r"\b(?:sed|perl)\s+[^;\n]*(?:-i|-pi)\b",
                r"(^|\s)(?:cp|mv|rm|mkdir|touch|chmod|chown)\b",
                r"(?:^|[\s])(?:echo|printf)\b[^;\n]*(?<![0-9])>{1,2}\s*(?!&)[A-Za-z0-9_./-]",
                r"(?:^|[\s])cat\s+>\s*[A-Za-z0-9_./-]",
                r"\btee\s+",
            ]
        ):
            families.add("modify_write")

        if any(
            command_matches(lowered, pattern)
            for pattern in [
                r"\b(pip|pip3)\s+install\b",
                r"\bpython(?:3)?\s+-m\s+pip\s+install\b",
                r"\b(uv|poetry|pipenv)\s+(pip\s+)?install\b",
                r"\b(npm|pnpm|yarn)\s+(install|add|ci)\b",
                r"\b(apt|apt-get|apk|yum|dnf|brew|conda|mamba)\s+(install|update|create|env)\b",
                r"\b(cargo\s+add|go\s+get|gem\s+install)\b",
            ]
        ):
            families.add("environment_dependencies")

        if command_matches(
            lowered,
            r"(^|\s)git\s+(status|diff|log|show|checkout|restore|commit|add|clone|branch|switch|reset|rev-parse|grep|ls-files|blame|remote|fetch|pull|push)\b",
        ):
            families.add("version_control")

        if any(
            command_matches(lowered, pattern)
            for pattern in [
                r"^(?:sudo\s+)?(?:sqlite3|psql|mysql|duckdb|jq|xsv|mlr|csvcut|csvgrep|csvstat|csvkit)\b",
                r"\bselect\s+.+\bfrom\b",
            ]
        ):
            families.add("data_query_transform")

        if any(
            command_matches(lowered, pattern)
            for pattern in [
                r"^(?:sudo\s+)?(?:curl|wget|http|httpie)\s+(-|https?://|www\.)",
            ]
        ):
            families.add("network_external")

        if any(
            command_matches(lowered, pattern)
            for pattern in [
                r"^(?:sudo\s+)?(?:ffmpeg|ffprobe|magick|convert|identify|tesseract|ocrmypdf|pdftotext|sox|exiftool)\b",
            ]
        ):
            families.add("media_specialized")

        is_execute = any(
            command_matches(lowered, pattern)
            for pattern in [
                r"(^|\s)(?:python|python3|node|ruby|perl|java|Rscript)\s+(?!-m\s+(pytest|unittest|mypy|ruff|flake8|pyright|pylint|pip)\b)",
                r"\b(go\s+run|cargo\s+run|dotnet\s+run|mvn\s+exec)\b",
                r"(^|\s)(?:bash|sh)\s+[^;\n]+\.(sh|bash)\b",
                r"(^|\s)\./[A-Za-z0-9_.\-/]+",
            ]
        )
        if is_execute and not is_test:
            families.add("execute_run")

    return families


def functional_families_for_invocation(tool_name: str, command: str) -> set[str]:
    family = tool_family(tool_name, bool(command))
    behaviors: set[str] = set()
    if family == "file_search_read":
        behaviors.add("inspect_search")
    elif family == "file_edit":
        behaviors.add("modify_write")
    elif family == "web_or_network":
        behaviors.add("network_external")

    if family == "terminal":
        behaviors.update(functional_families_from_command(command))
    return behaviors


def clean_example(value: str, max_len: int = 120) -> str:
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def add_behavior_examples(
    examples: dict[str, list[str]],
    behaviors: set[str],
    tool_name: str,
    command: str,
) -> None:
    source = clean_example(command) if command else clean_example(tool_name)
    if not source:
        return
    label = clean_example(f"{tool_name}: {source}" if tool_name else source)
    for behavior in behaviors:
        bucket = examples.setdefault(behavior, [])
        if label not in bucket and len(bucket) < EXAMPLES_PER_FUNCTIONAL_FAMILY:
            bucket.append(label)


def declared_families_from_steps(steps: list[Any]) -> set[str]:
    families: set[str] = set()
    for step in steps:
        if not isinstance(step, dict) or step.get("source") not in {"system", "developer"}:
            continue
        message = textish(step.get("message"), 30000).lower()
        for pattern, family in DECLARATION_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                families.add(family)
        for tool_name, has_command, _command in extract_embedded_function_calls(message):
            families.add(tool_family(tool_name, has_command))
    return families


def load_trajectories(path: Path, max_trajectories: int | None = None) -> pd.DataFrame:
    identity_columns = {"benchmark", "rel_path", "task_name", "scaffold", "model_dir", "agent_version"}
    df = pd.read_csv(path, usecols=lambda column: column in identity_columns | OUTCOME_COLUMNS)
    if "task_name" not in df.columns or "rel_path" not in df.columns:
        raise ValueError(f"{path} must contain task_name and rel_path.")

    if "reward_outcome" in df.columns:
        df["outcome"] = df["reward_outcome"]
    elif "outcome" not in df.columns and "reward" in df.columns:
        reward = pd.to_numeric(df["reward"], errors="coerce")
        df["outcome"] = reward.map({1.0: "pass", 0.0: "fail"})
    if "outcome" not in df.columns:
        raise ValueError(f"{path} must contain reward_outcome, outcome, or reward.")

    df = df[df["outcome"].isin(["pass", "fail"])].copy()
    if max_trajectories is not None:
        df = df.head(max_trajectories).copy()
    if df.empty:
        raise ValueError(f"{path} has no pass/fail trajectory rows.")

    for column in identity_columns:
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].fillna("").astype(str)
    df["passed"] = (df["outcome"] == "pass").astype(int)
    df["trajectory_id"] = df["benchmark"] + "|" + df["rel_path"].str.replace("\\", "/", regex=False)
    df["configuration_id"] = (
        df["benchmark"]
        + "|"
        + df["scaffold"]
        + "|"
        + df["model_dir"]
        + "|"
        + df["agent_version"]
    )
    return df.reset_index(drop=True)


def load_tasks(path: Path) -> pd.DataFrame:
    task_df = pd.read_csv(path)
    required = {"task_name", "category", "difficulty"}
    missing = required.difference(task_df.columns)
    if missing:
        raise ValueError(f"{path} is missing required fields: {', '.join(sorted(missing))}")
    return task_df[["task_name", "category", "difficulty"]].drop_duplicates("task_name")


def resolve_trajectory_path(root: Path, rel_path: str) -> Path:
    path = Path(str(rel_path))
    return path if path.is_absolute() else root / path


def parse_trajectory(row: Any, trajectory_root: Path) -> dict[str, Any]:
    path = resolve_trajectory_path(trajectory_root, row.rel_path)
    used_families: set[str] = set()
    used_behavior_families: set[str] = set()
    behavior_examples: dict[str, list[str]] = {}
    declared_families: set[str] = set()
    parse_error = ""

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and isinstance(data.get("trajectory"), dict):
            data = data["trajectory"]
        steps = data.get("steps") if isinstance(data, dict) and isinstance(data.get("steps"), list) else []
        declared_families = declared_families_from_steps(steps)

        for step in steps:
            if not isinstance(step, dict) or step.get("source") != "agent":
                continue
            message = textish(step.get("message"), 30000)
            calls = extract_structured_tool_calls(step)
            calls.extend(extract_embedded_function_calls(message))
            if not calls:
                calls.extend(("fenced_bash", True, command) for command in extract_fenced_shell_commands(message))
            seen_calls: set[tuple[str, str]] = set()
            for tool_name, has_command, command in calls:
                dedupe_key = (normalize_name(tool_name), command.strip())
                if dedupe_key in seen_calls:
                    continue
                seen_calls.add(dedupe_key)
                used_families.add(tool_family(tool_name, has_command))
                behaviors = functional_families_for_invocation(tool_name, command)
                used_behavior_families.update(behaviors)
                add_behavior_examples(behavior_examples, behaviors, tool_name, command)
    except (OSError, json.JSONDecodeError) as exc:
        parse_error = str(exc)

    result = {
        "trajectory_id": row.trajectory_id,
        "configuration_id": row.configuration_id,
        "benchmark": row.benchmark,
        "rel_path": row.rel_path,
        "task_name": row.task_name,
        "scaffold": row.scaffold,
        "model_dir": row.model_dir,
        "agent_version": row.agent_version,
        "outcome": row.outcome,
        "passed": row.passed,
        "parse_error": parse_error,
        "all_used_tool_families": "|".join(sorted(used_families)),
        "all_used_functional_families": "|".join(sorted(used_behavior_families)),
        "functional_examples_json": json.dumps(behavior_examples, ensure_ascii=False, sort_keys=True),
        "declared_tool_families": "|".join(sorted(declared_families)),
    }
    for family in MAIN_TOOL_FAMILIES:
        result[f"used_{family}"] = int(family in used_families)
    for family in FUNCTIONAL_FAMILIES:
        result[f"used_{family}"] = int(family in used_behavior_families)
    return result


def parse_all_trajectories(
    trajectories: pd.DataFrame,
    trajectory_root: Path,
    workers: int,
    progress_every: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total = int(trajectories.shape[0])
    worker_count = max(1, int(workers))

    if worker_count == 1:
        for index, row in enumerate(trajectories.itertuples(index=False), start=1):
            rows.append(parse_trajectory(row, trajectory_root))
            if progress_every and index % progress_every == 0:
                print(f"Parsed {index:,}/{total:,} trajectories.", flush=True)
        return pd.DataFrame(rows)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(parse_trajectory, row, trajectory_root) for row in trajectories.itertuples(index=False)]
        for index, future in enumerate(as_completed(futures), start=1):
            rows.append(future.result())
            if progress_every and index % progress_every == 0:
                print(f"Parsed {index:,}/{total:,} trajectories.", flush=True)
    return pd.DataFrame(rows)


def rate(numer: int, denom: int) -> float | None:
    return numer / denom if denom else None


def difference_pp(used_rate: float | None, not_used_rate: float | None) -> float | None:
    if used_rate is None or not_used_rate is None:
        return None
    if pd.isna(used_rate) or pd.isna(not_used_rate):
        return None
    return 100.0 * (used_rate - not_used_rate)


def summarize_group(df: pd.DataFrame, group_columns: list[str], task_counts: pd.DataFrame | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped: Iterable[tuple[Any, pd.DataFrame]]
    grouped = [((), df)] if not group_columns else df.groupby(group_columns, dropna=False, sort=False)

    for keys, group in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = {column: value for column, value in zip(group_columns, keys)}
        if not group_columns:
            base["group"] = "overall"
        elif len(group_columns) == 1:
            base["group"] = keys[0]
        else:
            base["group"] = "|".join(str(value) for value in keys)

        n_total = int(group.shape[0])
        pass_count = int(group["passed"].sum())
        fail_count = n_total - pass_count
        if task_counts is not None and len(group_columns) == 1:
            count_match = task_counts[task_counts[group_columns[0]].eq(keys[0])]
            if not count_match.empty:
                base["n_tasks"] = int(count_match["n_tasks"].iloc[0])
                base["single_task_category"] = bool(count_match["n_tasks"].iloc[0] == 1)

        for family in MAIN_TOOL_FAMILIES:
            used = group[group[f"used_{family}"].eq(1)]
            not_used = group[group[f"used_{family}"].eq(0)]
            passes = group[group["passed"].eq(1)]
            fails = group[group["passed"].eq(0)]
            n_used = int(used.shape[0])
            n_not_used = int(not_used.shape[0])
            pass_rate_used = rate(int(used["passed"].sum()), n_used)
            pass_rate_not_used = rate(int(not_used["passed"].sum()), n_not_used)
            pass_using_count = int(passes[f"used_{family}"].sum())
            fail_using_count = int(fails[f"used_{family}"].sum())
            rows.append(
                {
                    **base,
                    "tool_family": family,
                    "tool_family_display": TOOL_FAMILY_DISPLAY[family],
                    "n_total": n_total,
                    "n_used": n_used,
                    "n_not_used": n_not_used,
                    "use_rate": rate(n_used, n_total),
                    "pass_count": pass_count,
                    "fail_count": fail_count,
                    "pass_trajectories_using_count": pass_using_count,
                    "fail_trajectories_using_count": fail_using_count,
                    "pass_trajectories_using_rate": rate(pass_using_count, int(passes.shape[0])),
                    "fail_trajectories_using_rate": rate(fail_using_count, int(fails.shape[0])),
                    "pass_rate_used": pass_rate_used,
                    "pass_rate_not_used": pass_rate_not_used,
                    "pass_rate_difference_pp": difference_pp(pass_rate_used, pass_rate_not_used),
                }
            )
    return pd.DataFrame(rows)


def summarize_functional_group(df: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped: Iterable[tuple[Any, pd.DataFrame]]
    grouped = [((), df)] if not group_columns else df.groupby(group_columns, dropna=False, sort=False)

    for keys, group in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = {column: value for column, value in zip(group_columns, keys)}
        if not group_columns:
            base["group"] = "overall"
        elif len(group_columns) == 1:
            base["group"] = keys[0]
        else:
            base["group"] = "|".join(str(value) for value in keys)

        n_total = int(group.shape[0])
        pass_count = int(group["passed"].sum())
        fail_count = n_total - pass_count
        passes = group[group["passed"].eq(1)]
        fails = group[group["passed"].eq(0)]

        for family in FUNCTIONAL_FAMILIES:
            used = group[group[f"used_{family}"].eq(1)]
            not_used = group[group[f"used_{family}"].eq(0)]
            n_used = int(used.shape[0])
            n_not_used = int(not_used.shape[0])
            pass_rate_used = rate(int(used["passed"].sum()), n_used)
            pass_rate_not_used = rate(int(not_used["passed"].sum()), n_not_used)
            pass_using_count = int(passes[f"used_{family}"].sum())
            fail_using_count = int(fails[f"used_{family}"].sum())
            rows.append(
                {
                    **base,
                    "behavior_family": family,
                    "behavior_family_display": FUNCTIONAL_FAMILY_DISPLAY[family],
                    "n_total": n_total,
                    "n_used": n_used,
                    "n_not_used": n_not_used,
                    "use_rate": rate(n_used, n_total),
                    "pass_count": pass_count,
                    "fail_count": fail_count,
                    "pass_trajectories_using_count": pass_using_count,
                    "fail_trajectories_using_count": fail_using_count,
                    "pass_trajectories_using_rate": rate(pass_using_count, int(passes.shape[0])),
                    "fail_trajectories_using_rate": rate(fail_using_count, int(fails.shape[0])),
                    "pass_rate_used": pass_rate_used,
                    "pass_rate_not_used": pass_rate_not_used,
                    "pass_rate_difference_pp": difference_pp(pass_rate_used, pass_rate_not_used),
                }
            )
    return pd.DataFrame(rows)


def build_task_tool_contrasts(parsed: pd.DataFrame, min_cell_support: int) -> pd.DataFrame:
    """Compute trajectory-level tool-use contrasts separately within each task."""
    rows: list[dict[str, Any]] = []
    grouped = parsed.groupby(["task_name", "category", "difficulty"], dropna=False, sort=False)
    for (task_name, category, difficulty), group in grouped:
        n_total = int(group.shape[0])
        pass_count = int(group["passed"].sum())
        for family in MAIN_TOOL_FAMILIES:
            used = group[group[f"used_{family}"].eq(1)]
            not_used = group[group[f"used_{family}"].eq(0)]
            n_used = int(used.shape[0])
            n_not_used = int(not_used.shape[0])
            pass_rate_used = rate(int(used["passed"].sum()), n_used)
            pass_rate_not_used = rate(int(not_used["passed"].sum()), n_not_used)
            pass_rate_difference_pp = difference_pp(pass_rate_used, pass_rate_not_used)
            rows.append(
                {
                    "task_name": task_name,
                    "category": category,
                    "difficulty": difficulty,
                    "tool_family": family,
                    "tool_family_display": TOOL_FAMILY_DISPLAY[family],
                    "n_total": n_total,
                    "n_used": n_used,
                    "n_not_used": n_not_used,
                    "use_rate": rate(n_used, n_total),
                    "pass_count": pass_count,
                    "pass_rate_used": pass_rate_used,
                    "pass_rate_not_used": pass_rate_not_used,
                    "pass_rate_difference_pp": pass_rate_difference_pp,
                    "support_ok": bool(
                        n_used >= min_cell_support
                        and n_not_used >= min_cell_support
                        and pass_rate_difference_pp is not None
                        and not pd.isna(pass_rate_difference_pp)
                    ),
                }
            )
    return pd.DataFrame(rows)


def build_task_functional_contrasts(parsed: pd.DataFrame, min_cell_support: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = parsed.groupby(["task_name", "category", "difficulty"], dropna=False, sort=False)
    for (task_name, category, difficulty), group in grouped:
        n_total = int(group.shape[0])
        pass_count = int(group["passed"].sum())
        for family in FUNCTIONAL_FAMILIES:
            used = group[group[f"used_{family}"].eq(1)]
            not_used = group[group[f"used_{family}"].eq(0)]
            n_used = int(used.shape[0])
            n_not_used = int(not_used.shape[0])
            pass_rate_used = rate(int(used["passed"].sum()), n_used)
            pass_rate_not_used = rate(int(not_used["passed"].sum()), n_not_used)
            pass_rate_difference_pp = difference_pp(pass_rate_used, pass_rate_not_used)
            rows.append(
                {
                    "task_name": task_name,
                    "category": category,
                    "difficulty": difficulty,
                    "behavior_family": family,
                    "behavior_family_display": FUNCTIONAL_FAMILY_DISPLAY[family],
                    "n_total": n_total,
                    "n_used": n_used,
                    "n_not_used": n_not_used,
                    "use_rate": rate(n_used, n_total),
                    "pass_count": pass_count,
                    "pass_rate_used": pass_rate_used,
                    "pass_rate_not_used": pass_rate_not_used,
                    "pass_rate_difference_pp": pass_rate_difference_pp,
                    "support_ok": bool(
                        n_used >= min_cell_support
                        and n_not_used >= min_cell_support
                        and pass_rate_difference_pp is not None
                        and not pd.isna(pass_rate_difference_pp)
                    ),
                }
            )
    return pd.DataFrame(rows)


def summarize_task_balanced(
    task_contrasts: pd.DataFrame,
    dimension: str,
    task_counts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if task_contrasts.empty:
        return pd.DataFrame(rows)

    total_tasks = (
        task_contrasts[["task_name", dimension]]
        .drop_duplicates()
        .groupby(dimension, dropna=False)["task_name"]
        .nunique()
        .to_dict()
    )

    for (group_value, family), group in task_contrasts.groupby([dimension, "tool_family"], dropna=False, sort=False):
        eligible = group[group["support_ok"]].copy()
        diffs = eligible["pass_rate_difference_pp"].dropna()
        row: dict[str, Any] = {
            dimension: group_value,
            "group": group_value,
            "tool_family": family,
            "tool_family_display": TOOL_FAMILY_DISPLAY[family],
            "total_tasks": int(total_tasks.get(group_value, 0)),
            "eligible_tasks": int(eligible["task_name"].nunique()),
            "mean_task_pass_rate_difference_pp": float(diffs.mean()) if not diffs.empty else np.nan,
            "median_task_pass_rate_difference_pp": float(diffs.median()) if not diffs.empty else np.nan,
            "min_task_pass_rate_difference_pp": float(diffs.min()) if not diffs.empty else np.nan,
            "max_task_pass_rate_difference_pp": float(diffs.max()) if not diffs.empty else np.nan,
            "mean_task_n_used": float(eligible["n_used"].mean()) if not eligible.empty else np.nan,
            "mean_task_n_not_used": float(eligible["n_not_used"].mean()) if not eligible.empty else np.nan,
        }
        if task_counts is not None and dimension in task_counts.columns:
            count_match = task_counts[task_counts[dimension].eq(group_value)]
            if not count_match.empty:
                n_tasks = int(count_match["n_tasks"].iloc[0])
                row["n_tasks"] = n_tasks
                row["single_task_category"] = bool(n_tasks == 1)
        rows.append(row)

    sort_columns = [dimension, "tool_family"]
    return pd.DataFrame(rows).sort_values(sort_columns).reset_index(drop=True)


def summarize_functional_task_balanced(
    task_contrasts: pd.DataFrame,
    dimension: str,
    task_counts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if task_contrasts.empty:
        return pd.DataFrame(rows)

    total_tasks = (
        task_contrasts[["task_name", dimension]]
        .drop_duplicates()
        .groupby(dimension, dropna=False)["task_name"]
        .nunique()
        .to_dict()
    )

    for (group_value, family), group in task_contrasts.groupby([dimension, "behavior_family"], dropna=False, sort=False):
        eligible = group[group["support_ok"]].copy()
        diffs = eligible["pass_rate_difference_pp"].dropna()
        row: dict[str, Any] = {
            dimension: group_value,
            "group": group_value,
            "behavior_family": family,
            "behavior_family_display": FUNCTIONAL_FAMILY_DISPLAY[family],
            "total_tasks": int(total_tasks.get(group_value, 0)),
            "eligible_tasks": int(eligible["task_name"].nunique()),
            "mean_task_pass_rate_difference_pp": float(diffs.mean()) if not diffs.empty else np.nan,
            "median_task_pass_rate_difference_pp": float(diffs.median()) if not diffs.empty else np.nan,
            "min_task_pass_rate_difference_pp": float(diffs.min()) if not diffs.empty else np.nan,
            "max_task_pass_rate_difference_pp": float(diffs.max()) if not diffs.empty else np.nan,
            "total_used_trajectories": int(eligible["n_used"].sum()) if not eligible.empty else 0,
            "total_not_used_trajectories": int(eligible["n_not_used"].sum()) if not eligible.empty else 0,
            "mean_task_n_used": float(eligible["n_used"].mean()) if not eligible.empty else np.nan,
            "mean_task_n_not_used": float(eligible["n_not_used"].mean()) if not eligible.empty else np.nan,
        }
        if task_counts is not None and dimension in task_counts.columns:
            count_match = task_counts[task_counts[dimension].eq(group_value)]
            if not count_match.empty:
                n_tasks = int(count_match["n_tasks"].iloc[0])
                row["n_tasks"] = n_tasks
                row["single_task_category"] = bool(n_tasks == 1)
        rows.append(row)

    sort_columns = [dimension, "behavior_family"]
    return pd.DataFrame(rows).sort_values(sort_columns).reset_index(drop=True)


def summarize_functional_wilcoxon(task_contrasts: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family in FUNCTIONAL_FAMILIES:
        eligible = task_contrasts[
            task_contrasts["behavior_family"].eq(family)
            & task_contrasts["support_ok"]
            & task_contrasts["pass_rate_difference_pp"].notna()
        ].copy()
        differences = eligible["pass_rate_difference_pp"].astype(float).to_numpy()
        statistic, p_value, nonzero_pairs = two_sided_signed_rank(differences)
        all_family = task_contrasts[task_contrasts["behavior_family"].eq(family)]
        n_total = int(all_family["n_total"].sum())
        n_used = int(all_family["n_used"].sum())
        rows.append(
            {
                "behavior": FUNCTIONAL_FAMILY_DISPLAY[family],
                "behavior_family": family,
                "use_rate": n_used / n_total if n_total else np.nan,
                "eligible_tasks": int(eligible["task_name"].nunique()),
                "mean_pass_rate_difference_pp": float(np.mean(differences)) if len(differences) else np.nan,
                "median_pass_rate_difference_pp": float(np.median(differences)) if len(differences) else np.nan,
                "cohens_dz": paired_cohens_dz(differences),
                "wilcoxon_statistic": statistic,
                "p_value": p_value,
                "nonzero_task_pairs": nonzero_pairs,
            }
        )
    return pd.DataFrame(rows)


def pct_label(value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{100.0 * value:.0f}%"


def pp_label(value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{value:+.0f} pp"


def supported_difference(df: pd.DataFrame, min_cell_support: int) -> pd.Series:
    return (
        df["n_used"].ge(min_cell_support)
        & df["n_not_used"].ge(min_cell_support)
        & df["pass_rate_difference_pp"].notna()
    )


def plot_overall_pass_rates(overall: pd.DataFrame, out_path: Path) -> None:
    df = overall.copy()
    x = np.arange(len(df))
    width = 0.36

    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    used_bars = ax.bar(x - width / 2, df["pass_rate_used"], width, label="Used", color=PASS_COLOR)
    not_used_bars = ax.bar(x + width / 2, df["pass_rate_not_used"], width, label="Not used", color=FAIL_COLOR)

    ax.set_title("Tool-use association with success overall")
    ax.set_ylabel("Pass rate")
    ax.set_ylim(0, max(0.62, float(np.nanmax(df[["pass_rate_used", "pass_rate_not_used"]].to_numpy())) + 0.12))
    ax.set_xticks(x)
    ax.set_xticklabels(df["tool_family_display"], rotation=20, ha="right")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{value * 100:.0f}%"))
    ax.legend(frameon=False, ncols=2, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)

    for bars in (used_bars, not_used_bars):
        for bar in bars:
            height = bar.get_height()
            if np.isfinite(height):
                ax.text(bar.get_x() + bar.get_width() / 2, height + 0.012, pct_label(height), ha="center", va="bottom", fontsize=8)

    for i, row in enumerate(df.itertuples(index=False)):
        notes = []
        if row.use_rate >= 0.95:
            notes.append("near-universal")
        if row.use_rate <= 0.01:
            notes.append("sparse use")
        if row.n_used < 50 or row.n_not_used < 50:
            notes.append("limited contrast")
        if notes:
            ax.text(i, -0.09, "\n".join(notes), transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=7, color="#555555")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_difference_heatmap(
    df: pd.DataFrame,
    dimension: str,
    title: str,
    out_path: Path,
    dimension_order: list[str] | None = None,
    family_display_column: str = "tool_family_display",
    family_display_order: list[str] | None = None,
    transpose: bool = False,
    annotation_fontsize: float = 9.5,
    colorbar_label: str | None = "Mean task-level pass-rate difference (used - not used, pp)",
    x_label_map: dict[str, str] | None = None,
    x_label_rotation: int = 35,
    figure_height_scale: float = 0.55,
) -> bool:
    if df.empty:
        return False

    plot_df = df.copy()
    if dimension == "category" and "single_task_category" in plot_df.columns:
        plot_df = plot_df[~plot_df["single_task_category"].fillna(False)].copy()
    plot_df = plot_df[plot_df["eligible_tasks"].gt(0)].copy()
    plot_df["plot_difference_pp"] = plot_df["mean_task_pass_rate_difference_pp"]
    if plot_df["plot_difference_pp"].dropna().empty:
        return False

    pivot = plot_df.pivot_table(
        index=family_display_column,
        columns=dimension,
        values="plot_difference_pp",
        aggfunc="mean",
    )
    if pivot.empty:
        return False

    if family_display_order:
        ordered_index = [value for value in family_display_order if value in pivot.index]
        ordered_index.extend(value for value in pivot.index if value not in ordered_index)
        pivot = pivot.loc[ordered_index]

    if dimension_order:
        ordered = [value for value in dimension_order if value in pivot.columns]
        ordered.extend(value for value in pivot.columns if value not in ordered)
        pivot = pivot[ordered]
    else:
        ordered_columns = plot_df.groupby(dimension)["eligible_tasks"].sum().sort_values(ascending=False).index.tolist()
        pivot = pivot[[value for value in ordered_columns if value in pivot.columns]]

    display = pivot.T if transpose else pivot
    values = display.to_numpy(dtype=float)
    max_abs = float(np.nanmax(np.abs(values)))
    if not np.isfinite(max_abs) or max_abs == 0:
        max_abs = 1.0

    fig_width = max(7.0, min(18.0, 1.0 + 1.1 * len(display.columns)))
    fig_height = max(3.8, 1.05 + figure_height_scale * len(display.index))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    cmap = colorblind_cmap(DIVERGING_CMAP)
    image = ax.imshow(values, cmap=cmap, vmin=-max_abs, vmax=max_abs, aspect="auto")
    ax.set_title(title)
    ax.set_xticks(np.arange(len(display.columns)))
    x_labels = [x_label_map.get(str(value), str(value)) if x_label_map else str(value) for value in display.columns]
    x_label_alignment = "right" if x_label_rotation else "center"
    ax.set_xticklabels(x_labels, rotation=x_label_rotation, ha=x_label_alignment)
    ax.set_yticks(np.arange(len(display.index)))
    ax.set_yticklabels(display.index)
    ax.tick_params(axis="both", length=0)

    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            value = values[i, j]
            if np.isfinite(value):
                ax.text(
                    j,
                    i,
                    pp_label(value),
                    ha="center",
                    va="center",
                    fontsize=annotation_fontsize,
                    color=heatmap_text_color(float(value), cmap, -max_abs, max_abs),
                )

    cbar = fig.colorbar(image, ax=ax)
    if colorbar_label:
        cbar.set_label(colorbar_label)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=HEATMAP_DPI)
    plt.close(fig)
    return True


def category_order_by_core_functional_signal(functional_by_category: pd.DataFrame) -> list[str]:
    plot_df = functional_by_category.copy()
    if "single_task_category" in plot_df.columns:
        plot_df = plot_df[~plot_df["single_task_category"].fillna(False)].copy()
    plot_df = plot_df[
        plot_df["eligible_tasks"].gt(0)
        & plot_df["behavior_family_display"].isin(CORE_FUNCTIONAL_FAMILY_DISPLAY_ORDER)
    ].copy()
    if plot_df.empty:
        return []
    return (
        plot_df.groupby("category")["mean_task_pass_rate_difference_pp"]
        .mean()
        .sort_values(ascending=False)
        .index.astype(str)
        .tolist()
    )


def display_order_by_mean_signal(
    df: pd.DataFrame,
    display_column: str,
    fallback_order: list[str],
) -> list[str]:
    plot_df = df.copy()
    if "single_task_category" in plot_df.columns:
        plot_df = plot_df[~plot_df["single_task_category"].fillna(False)].copy()
    plot_df = plot_df[plot_df["eligible_tasks"].gt(0)].copy()
    if plot_df.empty or display_column not in plot_df.columns:
        return fallback_order

    signal_order = (
        plot_df.groupby(display_column)
        .agg(
            mean_signal=("mean_task_pass_rate_difference_pp", "mean"),
            eligible_tasks=("eligible_tasks", "sum"),
        )
        .sort_values(["mean_signal", "eligible_tasks"], ascending=[False, False])
        .index.astype(str)
        .tolist()
    )
    ordered = [value for value in signal_order if value in fallback_order]
    ordered.extend(value for value in fallback_order if value not in ordered)
    return ordered


def difficulty_pattern_is_informative(
    by_difficulty: pd.DataFrame,
    min_range_pp: float,
    family_column: str = "tool_family",
) -> bool:
    supported = by_difficulty[by_difficulty["eligible_tasks"].gt(0)].copy()
    for _, group in supported.groupby(family_column):
        if group["difficulty"].nunique() < 2:
            continue
        if (
            group["mean_task_pass_rate_difference_pp"].max()
            - group["mean_task_pass_rate_difference_pp"].min()
            >= min_range_pp
        ):
            return True
    return False


def cleanup_obsolete_figures(figures_dir: Path, retained: set[Path]) -> list[Path]:
    removed: list[Path] = []
    figures_dir.mkdir(parents=True, exist_ok=True)
    for name in OBSOLETE_FIGURES:
        path = figures_dir / name
        if path.exists() and path.resolve() not in retained:
            path.unlink()
            removed.append(path)
    return removed


def cleanup_obsolete_tables(out_dir: Path) -> list[Path]:
    removed: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in OBSOLETE_TABLES:
        path = out_dir / name
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed


def print_overall_association(overall: pd.DataFrame) -> None:
    print("\nOverall association")
    print("| Tool family | Use rate | Pass rate used | Pass rate not used | Difference |")
    print("| ----------- | -------: | -------------: | -----------------: | ---------: |")
    for row in overall.itertuples(index=False):
        print(
            f"| {row.tool_family_display} | {pct_label(row.use_rate)} | "
            f"{pct_label(row.pass_rate_used)} | {pct_label(row.pass_rate_not_used)} | "
            f"{pp_label(row.pass_rate_difference_pp)} |"
        )


def functional_eligible_task_counts(task_contrasts: pd.DataFrame) -> dict[str, int]:
    eligible = task_contrasts[task_contrasts["support_ok"] & task_contrasts["category"].notna()].copy()
    return eligible.groupby("behavior_family")["task_name"].nunique().to_dict()


def collect_functional_examples(parsed: pd.DataFrame) -> dict[str, list[str]]:
    examples: dict[str, list[str]] = {family: [] for family in FUNCTIONAL_FAMILIES}
    for raw in parsed["functional_examples_json"].dropna():
        try:
            row_examples = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row_examples, dict):
            continue
        for family in FUNCTIONAL_FAMILIES:
            for example in row_examples.get(family, []):
                if example not in examples[family] and len(examples[family]) < EXAMPLES_PER_FUNCTIONAL_FAMILY:
                    examples[family].append(example)
    return examples


def print_functional_taxonomy_examples(examples: dict[str, list[str]]) -> None:
    print("\nFunctional taxonomy validation examples")
    for family in FUNCTIONAL_FAMILIES:
        sample = examples.get(family, [])
        if sample:
            print(f"- {FUNCTIONAL_FAMILY_DISPLAY[family]}: " + "; ".join(sample))
        else:
            print(f"- {FUNCTIONAL_FAMILY_DISPLAY[family]}: no examples observed")


def print_functional_coverage(
    overall: pd.DataFrame,
    task_contrasts: pd.DataFrame,
    parsed: pd.DataFrame,
) -> None:
    eligible_counts = functional_eligible_task_counts(task_contrasts)
    print("\nFunctional coverage")
    print("| Behavior family | Trajectories | Use rate | Eligible category tasks | Notes |")
    print("| --------------- | -----------: | -------: | ----------------------: | ----- |")
    for row in overall.itertuples(index=False):
        notes = []
        if row.use_rate >= 0.90:
            notes.append("near-universal")
        if row.use_rate <= 0.01:
            notes.append("extremely rare")
        used = parsed[parsed[f"used_{row.behavior_family}"].eq(1)]
        if not used.empty and "scaffold" in used.columns:
            top_scaffold_share = used["scaffold"].value_counts(normalize=True).iloc[0]
            if top_scaffold_share >= 0.75:
                notes.append("scaffold-concentrated")
        print(
            f"| {row.behavior_family_display} | {row.n_used:,} | {pct_label(row.use_rate)} | "
            f"{eligible_counts.get(row.behavior_family, 0):,} | {', '.join(notes)} |"
        )


def print_functional_overall_association(overall: pd.DataFrame) -> None:
    print("\nFunctional overall association")
    print("| Behavior family | Use rate | Pass rate used | Pass rate not used | Difference |")
    print("| --------------- | -------: | -------------: | -----------------: | ---------: |")
    for row in overall.itertuples(index=False):
        print(
            f"| {row.behavior_family_display} | {pct_label(row.use_rate)} | "
            f"{pct_label(row.pass_rate_used)} | {pct_label(row.pass_rate_not_used)} | "
            f"{pp_label(row.pass_rate_difference_pp)} |"
        )


def print_functional_wilcoxon(wilcoxon_results: pd.DataFrame) -> None:
    print("\nFunctional Wilcoxon signed-rank checks")
    print("| Behavior family | Eligible tasks | Mean diff | Median diff | Cohen's dz | p-value |")
    print("| --------------- | -------------: | --------: | ----------: | ----------: | ------: |")
    for row in wilcoxon_results.itertuples(index=False):
        p_value = "" if pd.isna(row.p_value) else f"{row.p_value:.4g}"
        marker = " *" if not pd.isna(row.p_value) and row.p_value < 0.05 else ""
        print(
            f"| {FUNCTIONAL_FAMILY_DISPLAY[row.behavior_family]} | {row.eligible_tasks:,} | "
            f"{pp_label(row.mean_pass_rate_difference_pp)} | {pp_label(row.median_pass_rate_difference_pp)} | "
            f"{row.cohens_dz:.3f} | {p_value}{marker} |"
        )


def category_findings(by_category: pd.DataFrame) -> list[dict[str, Any]]:
    df = by_category[by_category["eligible_tasks"].gt(0)].copy()
    if "single_task_category" in df.columns:
        df = df[~df["single_task_category"].fillna(False)].copy()
    findings: list[dict[str, Any]] = []
    for family in MAIN_TOOL_FAMILIES:
        family_rows = df[df["tool_family"].eq(family)].copy()
        if family_rows.empty:
            continue
        positive = (
            family_rows[family_rows["mean_task_pass_rate_difference_pp"].gt(0)]
            .sort_values(["mean_task_pass_rate_difference_pp", "eligible_tasks"], ascending=[False, False])
            .head(3)
        )
        negative = (
            family_rows[family_rows["mean_task_pass_rate_difference_pp"].lt(0)]
            .sort_values(["mean_task_pass_rate_difference_pp", "eligible_tasks"], ascending=[True, False])
            .head(3)
        )
        for direction, rows in [("positive", positive), ("negative", negative)]:
            for row in rows.itertuples(index=False):
                findings.append(
                    {
                        "tool_family": row.tool_family,
                        "tool_family_display": row.tool_family_display,
                        "direction": direction,
                        "category": row.category,
                        "eligible_tasks": row.eligible_tasks,
                        "mean_task_pass_rate_difference_pp": row.mean_task_pass_rate_difference_pp,
                        "median_task_pass_rate_difference_pp": row.median_task_pass_rate_difference_pp,
                    }
                )
    return findings


def functional_category_findings(by_category: pd.DataFrame) -> list[dict[str, Any]]:
    df = by_category[by_category["eligible_tasks"].gt(0)].copy()
    if "single_task_category" in df.columns:
        df = df[~df["single_task_category"].fillna(False)].copy()
    findings: list[dict[str, Any]] = []
    for family in FUNCTIONAL_FAMILIES:
        family_rows = df[df["behavior_family"].eq(family)].copy()
        if family_rows.empty:
            continue
        positive = (
            family_rows[family_rows["mean_task_pass_rate_difference_pp"].gt(0)]
            .sort_values(["mean_task_pass_rate_difference_pp", "eligible_tasks"], ascending=[False, False])
            .head(3)
        )
        negative = (
            family_rows[family_rows["mean_task_pass_rate_difference_pp"].lt(0)]
            .sort_values(["mean_task_pass_rate_difference_pp", "eligible_tasks"], ascending=[True, False])
            .head(3)
        )
        for direction, rows in [("positive", positive), ("negative", negative)]:
            for row in rows.itertuples(index=False):
                findings.append(
                    {
                        "behavior_family": row.behavior_family,
                        "behavior_family_display": row.behavior_family_display,
                        "direction": direction,
                        "category": row.category,
                        "eligible_tasks": row.eligible_tasks,
                        "mean_task_pass_rate_difference_pp": row.mean_task_pass_rate_difference_pp,
                        "median_task_pass_rate_difference_pp": row.median_task_pass_rate_difference_pp,
                    }
                )
    return findings


def print_category_findings(by_category: pd.DataFrame) -> None:
    print("\nTask-balanced category-level findings")
    findings = category_findings(by_category)
    if not findings:
        print("- No supported category-level contrasts after excluding single-task categories.")
        return
    for family in MAIN_TOOL_FAMILIES:
        rows = [row for row in findings if row["tool_family"] == family]
        print(f"\n{TOOL_FAMILY_DISPLAY[family]}")
        if not rows:
            print("- No supported positive or negative category differences.")
            continue
        for row in rows:
            print(
                f"- {row['direction']}: {row['category']}, "
                f"mean task delta {pp_label(row['mean_task_pass_rate_difference_pp'])}, "
                f"median {pp_label(row['median_task_pass_rate_difference_pp'])}, "
                f"eligible_tasks={row['eligible_tasks']:,}"
            )


def print_functional_category_findings(by_category: pd.DataFrame) -> None:
    print("\nFunctional task-balanced category-level findings")
    findings = functional_category_findings(by_category)
    if not findings:
        print("- No supported functional category-level contrasts after excluding single-task categories.")
        return
    for family in FUNCTIONAL_FAMILIES:
        rows = [row for row in findings if row["behavior_family"] == family]
        print(f"\n{FUNCTIONAL_FAMILY_DISPLAY[family]}")
        if not rows:
            print("- No supported positive or negative category differences.")
            continue
        for row in rows:
            print(
                f"- {row['direction']}: {row['category']}, "
                f"mean task delta {pp_label(row['mean_task_pass_rate_difference_pp'])}, "
                f"median {pp_label(row['median_task_pass_rate_difference_pp'])}, "
                f"eligible_tasks={row['eligible_tasks']:,}"
            )


def print_difficulty_findings(by_difficulty: pd.DataFrame, informative: bool) -> None:
    print("\nTask-balanced difficulty-level findings")
    for difficulty in DIFFICULTY_ORDER:
        subset = by_difficulty[by_difficulty["difficulty"].eq(difficulty)].copy()
        if subset.empty:
            continue
        pieces = []
        for row in subset.itertuples(index=False):
            if row.eligible_tasks > 0:
                pieces.append(
                    f"{row.tool_family} {pp_label(row.mean_task_pass_rate_difference_pp)} "
                    f"({row.eligible_tasks} tasks)"
                )
            else:
                pieces.append(f"{row.tool_family} sparse")
        print(f"- {difficulty}: " + ", ".join(pieces))
    if informative:
        print("- The difficulty-specific association varies enough to retain a difficulty figure.")
    else:
        print("- No informative difficulty-specific pattern was found; omit the difficulty figure from the paper.")


def print_functional_difficulty_findings(by_difficulty: pd.DataFrame, informative: bool) -> None:
    print("\nFunctional task-balanced difficulty-level findings")
    for difficulty in DIFFICULTY_ORDER:
        subset = by_difficulty[by_difficulty["difficulty"].eq(difficulty)].copy()
        if subset.empty:
            continue
        pieces = []
        for row in subset.itertuples(index=False):
            if row.eligible_tasks > 0:
                pieces.append(
                    f"{row.behavior_family} {pp_label(row.mean_task_pass_rate_difference_pp)} "
                    f"({row.eligible_tasks} tasks)"
                )
            else:
                pieces.append(f"{row.behavior_family} sparse")
        print(f"- {difficulty}: " + ", ".join(pieces))
    if informative:
        print("- The difficulty-specific functional association varies enough to retain a difficulty figure.")
    else:
        print("- No informative difficulty-specific functional pattern was found; omit the difficulty figure from the paper.")


def strongest_contrast(
    df: pd.DataFrame,
    dimension: str,
    family: str,
    value_column: str,
    positive: bool,
    min_cell_support: int | None = None,
) -> pd.Series | None:
    subset = df[df["tool_family"].eq(family)].copy()
    if dimension == "category" and "single_task_category" in subset.columns:
        subset = subset[~subset["single_task_category"].fillna(False)].copy()
    if min_cell_support is not None:
        subset = subset[supported_difference(subset, min_cell_support)].copy()
    elif "eligible_tasks" in subset.columns:
        subset = subset[subset["eligible_tasks"].gt(0)].copy()
    subset = subset[subset[value_column].notna()].copy()
    subset = subset[subset[value_column].gt(0) if positive else subset[value_column].lt(0)]
    if subset.empty:
        return None
    ascending = not positive
    return subset.sort_values(value_column, ascending=ascending).iloc[0]


def contrast_label(row: pd.Series | None, dimension: str, value_column: str, support_column: str | None = None) -> str:
    if row is None:
        return "none"
    support = ""
    if support_column and support_column in row:
        support = f", {support_column}={int(row[support_column])}"
    return f"{row[dimension]} {pp_label(row[value_column])}{support}"


def print_pooled_comparison(
    pooled_by_category: pd.DataFrame,
    by_category: pd.DataFrame,
    pooled_by_difficulty: pd.DataFrame,
    by_difficulty: pd.DataFrame,
    min_cell_support: int,
) -> None:
    print("\nComparison with previous pooled summaries")
    print("Category changes per tool")
    for family in MAIN_TOOL_FAMILIES:
        before_pos = strongest_contrast(
            pooled_by_category, "category", family, "pass_rate_difference_pp", True, min_cell_support
        )
        after_pos = strongest_contrast(
            by_category, "category", family, "mean_task_pass_rate_difference_pp", True
        )
        before_neg = strongest_contrast(
            pooled_by_category, "category", family, "pass_rate_difference_pp", False, min_cell_support
        )
        after_neg = strongest_contrast(
            by_category, "category", family, "mean_task_pass_rate_difference_pp", False
        )
        print(
            f"- {TOOL_FAMILY_DISPLAY[family]}: strongest positive "
            f"{contrast_label(before_pos, 'category', 'pass_rate_difference_pp')} -> "
            f"{contrast_label(after_pos, 'category', 'mean_task_pass_rate_difference_pp', 'eligible_tasks')}; "
            f"strongest negative "
            f"{contrast_label(before_neg, 'category', 'pass_rate_difference_pp')} -> "
            f"{contrast_label(after_neg, 'category', 'mean_task_pass_rate_difference_pp', 'eligible_tasks')}."
        )

    print("Difficulty changes per tool")
    for family in MAIN_TOOL_FAMILIES:
        pieces = []
        pooled_family = pooled_by_difficulty[pooled_by_difficulty["tool_family"].eq(family)].copy()
        balanced_family = by_difficulty[by_difficulty["tool_family"].eq(family)].copy()
        for difficulty in DIFFICULTY_ORDER:
            pooled_row = pooled_family[pooled_family["difficulty"].eq(difficulty)]
            balanced_row = balanced_family[balanced_family["difficulty"].eq(difficulty)]
            pooled_value = ""
            if not pooled_row.empty and bool(supported_difference(pooled_row, min_cell_support).iloc[0]):
                pooled_value = pp_label(float(pooled_row["pass_rate_difference_pp"].iloc[0]))
            balanced_value = ""
            if not balanced_row.empty and int(balanced_row["eligible_tasks"].iloc[0]) > 0:
                balanced_value = pp_label(float(balanced_row["mean_task_pass_rate_difference_pp"].iloc[0]))
            pieces.append(f"{difficulty}: pooled {pooled_value or 'sparse'}, task-balanced {balanced_value or 'sparse'}")
        print(f"- {TOOL_FAMILY_DISPLAY[family]}: " + "; ".join(pieces))


def print_level_comparison(interface_overall: pd.DataFrame, functional_overall: pd.DataFrame) -> None:
    interface_range = (
        float(interface_overall["pass_rate_difference_pp"].max() - interface_overall["pass_rate_difference_pp"].min())
        if not interface_overall.empty
        else 0.0
    )
    functional_range = (
        float(functional_overall["pass_rate_difference_pp"].max() - functional_overall["pass_rate_difference_pp"].min())
        if not functional_overall.empty
        else 0.0
    )
    strongest = functional_overall.sort_values("pass_rate_difference_pp", ascending=False).head(3)
    rare = functional_overall[functional_overall["use_rate"].le(0.01)]["behavior_family_display"].tolist()
    near_universal = functional_overall[functional_overall["use_rate"].ge(0.90)]["behavior_family_display"].tolist()

    print("\nLevel 1 vs Level 2 comparison")
    print(
        f"- Interface-level overall differences span {pp_label(interface_range)}; "
        f"functional-level differences span {pp_label(functional_range)}."
    )
    if not strongest.empty:
        pieces = [
            f"{row.behavior_family_display} {pp_label(row.pass_rate_difference_pp)}"
            for row in strongest.itertuples(index=False)
        ]
        print("- Strongest positive functional associations: " + ", ".join(pieces) + ".")
    if near_universal:
        print("- Near-universal functional families: " + ", ".join(near_universal) + ".")
    if rare:
        print("- Extremely rare functional families: " + ", ".join(rare) + ".")


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    trajectories = load_trajectories(args.trajectory_summary, args.max_trajectories)
    tasks = load_tasks(args.tasks)
    task_counts = tasks.groupby("category", as_index=False).agg(n_tasks=("task_name", "nunique"))

    parsed = parse_all_trajectories(trajectories, args.trajectory_root, args.workers, args.progress_every)
    parsed = parsed.merge(tasks, on="task_name", how="left", validate="many_to_one")

    overall = summarize_group(parsed, [])
    pooled_by_category = summarize_group(parsed.dropna(subset=["category"]), ["category"], task_counts=task_counts)
    pooled_by_difficulty = summarize_group(parsed.dropna(subset=["difficulty"]), ["difficulty"])
    task_contrasts = build_task_tool_contrasts(parsed, args.min_cell_support)
    by_category = summarize_task_balanced(
        task_contrasts.dropna(subset=["category"]),
        "category",
        task_counts=task_counts,
    )
    by_difficulty = summarize_task_balanced(task_contrasts.dropna(subset=["difficulty"]), "difficulty")
    functional_overall = summarize_functional_group(parsed, [])
    functional_task_contrasts = build_task_functional_contrasts(parsed, args.min_cell_support)
    functional_by_category = summarize_functional_task_balanced(
        functional_task_contrasts.dropna(subset=["category"]),
        "category",
        task_counts=task_counts,
    )
    functional_by_difficulty = summarize_functional_task_balanced(
        functional_task_contrasts.dropna(subset=["difficulty"]),
        "difficulty",
    )
    functional_wilcoxon = summarize_functional_wilcoxon(functional_task_contrasts)
    functional_inference_path = args.out / "rq2_3_functional_behavior_inference.csv"
    functional_wilcoxon.to_csv(functional_inference_path, index=False)

    removed_tables = cleanup_obsolete_tables(args.out)

    category_figure = args.figures_dir / "rq2_3_tool_success_association_by_category.png"
    difficulty_figure = args.figures_dir / "rq2_3_tool_success_association_by_difficulty.png"
    functional_category_figure = args.figures_dir / "rq2_3_functional_success_association_by_category.png"
    functional_difficulty_figure = args.figures_dir / "rq2_3_functional_success_association_by_difficulty.png"
    category_order = category_order_by_core_functional_signal(functional_by_category)
    functional_category_family_order = display_order_by_mean_signal(
        functional_by_category,
        "behavior_family_display",
        FUNCTIONAL_FAMILY_DISPLAY_ORDER,
    )

    category_plotted = plot_difference_heatmap(
        by_category,
        "category",
        "Task-balanced tool-use association with success by category",
        category_figure,
        dimension_order=category_order,
        family_display_order=TOOL_FAMILY_DISPLAY_ORDER,
    )
    retained_figures = {category_figure.resolve()} if category_plotted else set()
    removed_current_figures: list[Path] = []
    if not category_plotted and category_figure.exists():
        category_figure.unlink()
        removed_current_figures.append(category_figure)

    functional_category_plotted = plot_difference_heatmap(
        functional_by_category,
        "category",
        "Task-balanced functional association with success by category",
        functional_category_figure,
        dimension_order=category_order,
        family_display_column="behavior_family_display",
        family_display_order=functional_category_family_order,
        annotation_fontsize=9.0,
        x_label_map=CATEGORY_DISPLAY_LABELS,
        x_label_rotation=0,
        figure_height_scale=0.42,
    )
    if functional_category_plotted:
        retained_figures.add(functional_category_figure.resolve())
    elif functional_category_figure.exists():
        functional_category_figure.unlink()
        removed_current_figures.append(functional_category_figure)

    difficulty_informative = difficulty_pattern_is_informative(
        by_difficulty,
        args.difficulty_figure_min_range_pp,
    )
    if difficulty_informative:
        if plot_difference_heatmap(
            by_difficulty,
            "difficulty",
            "Task-balanced tool-use association with success by difficulty",
            difficulty_figure,
            dimension_order=DIFFICULTY_ORDER,
            family_display_order=TOOL_FAMILY_DISPLAY_ORDER,
        ):
            retained_figures.add(difficulty_figure.resolve())
    elif difficulty_figure.exists():
        difficulty_figure.unlink()
        removed_current_figures.append(difficulty_figure)

    functional_difficulty_informative = difficulty_pattern_is_informative(
        functional_by_difficulty,
        args.difficulty_figure_min_range_pp,
        family_column="behavior_family",
    )
    if functional_difficulty_informative:
        if plot_difference_heatmap(
            functional_by_difficulty,
            "difficulty",
            "Task-balanced functional association with success by difficulty",
            functional_difficulty_figure,
            dimension_order=DIFFICULTY_ORDER,
            family_display_column="behavior_family_display",
            family_display_order=FUNCTIONAL_FAMILY_DISPLAY_ORDER,
            transpose=True,
            annotation_fontsize=11,
            colorbar_label=None,
        ):
            retained_figures.add(functional_difficulty_figure.resolve())
    elif functional_difficulty_figure.exists():
        functional_difficulty_figure.unlink()
        removed_current_figures.append(functional_difficulty_figure)

    removed_figures = removed_current_figures + cleanup_obsolete_figures(args.figures_dir, retained_figures)

    parse_errors = parsed["parse_error"].astype(str).ne("").sum()
    print(f"Processed {parsed.shape[0]:,} trajectories.")
    if parse_errors:
        print(f"Warning: {parse_errors:,} trajectories could not be parsed.")
    print_overall_association(overall)
    print_category_findings(by_category)
    print_difficulty_findings(by_difficulty, difficulty_informative)
    print_pooled_comparison(
        pooled_by_category,
        by_category,
        pooled_by_difficulty,
        by_difficulty,
        args.min_cell_support,
    )
    examples = collect_functional_examples(parsed)
    print_functional_taxonomy_examples(examples)
    print_functional_coverage(functional_overall, functional_task_contrasts, parsed)
    print_functional_overall_association(functional_overall)
    print_functional_wilcoxon(functional_wilcoxon)
    print_functional_category_findings(functional_by_category)
    print_functional_difficulty_findings(functional_by_difficulty, functional_difficulty_informative)
    print_level_comparison(overall, functional_overall)

    print("\nFinal figures")
    print(f"- {functional_inference_path}: overall task-level functional-behavior inference.")
    if category_plotted:
        print(f"- {category_figure}: task-balanced category-level pass-rate differences.")
    if difficulty_informative and difficulty_figure.resolve() in retained_figures:
        print(f"- {difficulty_figure}: task-balanced difficulty-level pass-rate differences.")
    if functional_category_plotted:
        print(f"- {functional_category_figure}: task-balanced functional category-level pass-rate differences.")
    if functional_difficulty_informative and functional_difficulty_figure.resolve() in retained_figures:
        print(f"- {functional_difficulty_figure}: task-balanced functional difficulty-level pass-rate differences.")

    print("\nRemoved figures")
    if removed_figures:
        for path in removed_figures:
            print(f"- {path}")
    else:
        print("- None")

    print("\nRemoved tables")
    if removed_tables:
        for path in removed_tables:
            print(f"- {path}")
    else:
        print("- None")

    print("\nMethodological confirmation")
    print(
        "Interface and functional behavior use are measured at the trajectory level. The overall tables remain "
        "trajectory-pooled. Category and difficulty tables are task-balanced by first computing each task's used-vs-not-used "
        "success contrast, retaining task-tool cells only when at least "
        f"{args.min_cell_support} used and {args.min_cell_support} not-used trajectories are observed, "
        "and then averaging eligible task contrasts. Trials are not aggregated within submissions. "
        "The only inferential check is an unadjusted two-sided Wilcoxon signed-rank test across eligible "
        "task-level functional contrasts; no category/difficulty significance tests, multiple-testing "
        "correction, submission aggregation, or causal models are used."
    )


if __name__ == "__main__":
    main()
