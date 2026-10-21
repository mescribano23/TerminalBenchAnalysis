#!/usr/bin/env python3
"""Scrape Terminal-Bench 2.0 leaderboard rows, task results, and trajectories.

The tbench.ai pages server-render leaderboard data into the HTML, including
Next.js RSC payload chunks in ``<script>`` tags. This scraper intentionally uses
only ``requests``, ``BeautifulSoup``, and Python's standard library.
"""

from __future__ import annotations

import argparse
import html
import importlib
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from scripts.benchmark_paths import paths_for_benchmark
from scripts.mining.rsc_helpers import (
    build_rsc_reference_lookup,
    resolve_rsc_references,
)

_trajectory_index = importlib.import_module(".04_trajectory_index_helpers", __package__)

TrajectoryIndexWriter = _trajectory_index.TrajectoryIndexWriter
safe_path_component = _trajectory_index.safe_path_component
trajectory_file_status = _trajectory_index.trajectory_file_status
trajectory_payload_status = _trajectory_index.trajectory_payload_status

BASE_URL = "https://www.tbench.ai"
DEFAULT_LEADERBOARD_URL = f"{BASE_URL}/leaderboard/terminal-bench/2.0"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_BENCHMARK = "terminal_bench_2_0"
REQUEST_DELAY_SECONDS = 0.5
INDEX_CHECKPOINT_INTERVAL = 250
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TEXT_SUBMISSION_RE = re.compile(
    r"(?P<url>"
    r"(?:https?://(?:www\.)?tbench\.ai)?"
    r"/leaderboard/terminal-bench/"
    r"[^/\"'<>\s?#,\]\)}]+/"
    r"[^/\"'<>\s?#,\]\)}]+/"
    r"[^/\"'<>\s?#,\]\)}]+/"
    r"[^/\"'<>\s?#,@\]\)}]+@[^/\"'<>\s?#,\]\)}]+"
    r")(?=[\"'<>\s?#,\]\)}]|$)"
)

TASK_RE = re.compile(
    r'"taskName"\s*:\s*"(?P<taskName>(?:\\.|[^"\\])*)"\s*,\s*'
    r'"taskChecksum"\s*:\s*"(?P<taskChecksum>(?:\\.|[^"\\])*)"\s*,\s*'
    r'"nTrials"\s*:\s*(?P<nTrials>\d+)\s*,\s*'
    r'"avgResolutionRate"\s*:\s*(?P<avgResolutionRate>[\d.]+)\s*,\s*'
    r'"successCount"\s*:\s*(?P<successCount>\d+)'
)

ROW_SUBMISSION_RE = re.compile(
    r'"agentName"\s*:\s*"(?P<scaffold>(?:\\.|[^"\\])*)"\s*,\s*'
    r'"agentVersion"\s*:\s*"(?P<scaffold_version>(?:\\.|[^"\\])*)"\s*,\s*'
    r'"modelNames"\s*:\s*\[(?P<model_names>[^\]]*)\]\s*,\s*'
    r'"modelProviders"\s*:\s*\[(?P<model_providers>[^\]]*)\]'
)

ROW_OBJECT_RE = re.compile(
    r"\{"
    r"(?=[^{}]*\"agentName\")"
    r"(?=[^{}]*\"agentVersion\")"
    r"(?=[^{}]*\"modelNames\")"
    r"(?=[^{}]*\"modelProviders\")"
    r"[^{}]*"
    r"\}"
)

ARRAY_STRING_RE = re.compile(r'"((?:\\.|[^"\\])*)"')

TRIAL_OBJECT_RE = re.compile(
    r"\{(?=[^{}]*\"trialName\")(?=[^{}]*\"trialId\")[^{}]*\}"
)



@dataclass(frozen=True)
class Submission:
    url: str
    bench_version: str
    scaffold: str
    scaffold_version: str
    model: str
    provider: str
    leaderboard_accuracy: float | None = None
    leaderboard_stderr: float | None = None
    leaderboard_date: str = ""
    leaderboard_agent_display_name: str = ""
    leaderboard_model_display: str = ""
    leaderboard_agent_organization: str = ""
    leaderboard_model_organization: str = ""


SubmissionKey = tuple[str, str, str, str]


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def submission_key_from_submission(submission: Submission) -> SubmissionKey:
    return (
        submission.scaffold,
        submission.scaffold_version,
        submission.model,
        submission.provider,
    )


def submission_key_from_record(row: dict[str, object]) -> SubmissionKey:
    return (
        str(row.get("scaffold", "")),
        str(row.get("scaffold_version", "")),
        str(row.get("model", "")),
        str(row.get("provider", "")),
    )


def fetch_html(session: requests.Session, url: str) -> str:
    time.sleep(REQUEST_DELAY_SECONDS)
    response = session.get(url, headers=HEADERS, timeout=45)
    response.raise_for_status()
    return response.text


def normalize_payload_text(text: str) -> str:
    """Normalize common HTML, JSON, and Next/RSC escape sequences."""
    normalized = html.unescape(text)
    replacements = {
        r"\/": "/",
        r"\u002f": "/",
        r"\u002F": "/",
        r"\u0022": '"',
        r"\u0027": "'",
        r"\u003a": ":",
        r"\u003A": ":",
        r"\u002c": ",",
        r"\u002C": ",",
        r"\u005b": "[",
        r"\u005B": "[",
        r"\u005d": "]",
        r"\u005D": "]",
        r"\u007b": "{",
        r"\u007B": "{",
        r"\u007d": "}",
        r"\u007D": "}",
        r"\"": '"',
    }
    for _ in range(4):
        before = normalized
        for escaped, plain in replacements.items():
            normalized = normalized.replace(escaped, plain)
        if normalized == before:
            break
    return normalized


def decode_jsonish_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value.replace(r"\"", '"').replace(r"\\", "\\")


def canonical_submission_url(
    bench_version: str,
    scaffold: str,
    scaffold_version: str,
    model: str,
    provider: str,
) -> str:
    safe = "-._~"
    model_names = model.split(",")
    providers = provider.split(",")
    if len(model_names) == len(providers) and len(model_names) > 1:
        model_provider_raw = ",".join(
            f"{model_name}@{model_provider}"
            for model_name, model_provider in zip(model_names, providers)
        )
    else:
        model_provider_raw = f"{model}@{provider}"
    model_provider = quote(model_provider_raw, safe=safe)
    return (
        f"{BASE_URL}/leaderboard/terminal-bench/"
        f"{quote(bench_version, safe=safe)}/"
        f"{quote(scaffold, safe=safe)}/"
        f"{quote(scaffold_version, safe=safe)}/"
        f"{model_provider}"
    )


def parse_submission_url(raw_url: str) -> Submission | None:
    raw_url = normalize_payload_text(raw_url.strip())
    absolute_url = urljoin(BASE_URL, raw_url)
    split_url = urlsplit(absolute_url)
    if split_url.netloc not in {"www.tbench.ai", "tbench.ai"}:
        return None

    path_parts = split_url.path.rstrip("/").split("/")
    if len(path_parts) != 7 or path_parts[1:3] != ["leaderboard", "terminal-bench"]:
        return None

    bench_version = unquote(path_parts[3])
    scaffold = unquote(path_parts[4])
    scaffold_version = unquote(path_parts[5])
    model_provider = unquote(path_parts[6])
    if "@" not in model_provider:
        return None

    model_names: list[str] = []
    providers: list[str] = []
    for part in model_provider.split(","):
        if "@" not in part:
            return None
        model_name, model_provider_name = part.rsplit("@", 1)
        model_names.append(model_name)
        providers.append(model_provider_name)
    model = ",".join(model_names)
    provider = ",".join(providers)
    return Submission(
        url=canonical_submission_url(
            bench_version, scaffold, scaffold_version, model, provider
        ),
        bench_version=bench_version,
        scaffold=scaffold,
        scaffold_version=scaffold_version,
        model=model,
        provider=provider,
    )


def parse_bench_version(url: str) -> str:
    path = unquote(urlsplit(urljoin(BASE_URL, url)).path)
    marker = "/leaderboard/terminal-bench/"
    if marker not in path:
        return "2.0"
    return path.split(marker, 1)[1].split("/", 1)[0]


def parse_jsonish_string_array(raw_array_body: str) -> list[str]:
    return [
        decode_jsonish_string(match.group(1))
        for match in ARRAY_STRING_RE.finditer(raw_array_body)
    ]


def jsonish_array_body(object_text: str, field_name: str) -> str | None:
    match = re.search(
        rf'"{re.escape(field_name)}"\s*:\s*\[(?P<value>[^\]]*)\]',
        object_text,
    )
    if not match:
        return None
    return match.group("value")


def optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def row_submission_from_object(object_text: str, bench_version: str) -> list[Submission]:
    scaffold = json_field_string(object_text, "agentName")
    scaffold_version = json_field_string(object_text, "agentVersion")
    model_body = jsonish_array_body(object_text, "modelNames")
    provider_body = jsonish_array_body(object_text, "modelProviders")
    if scaffold is None or scaffold_version is None or model_body is None or provider_body is None:
        return []

    model_names = parse_jsonish_string_array(model_body)
    model_providers = parse_jsonish_string_array(provider_body)
    leaderboard_accuracy = json_field_number(object_text, "accuracy")
    leaderboard_stderr = json_field_number(object_text, "stderr")
    leaderboard_date = json_field_string(object_text, "date") or ""
    agent_display_name = json_field_string(object_text, "agent") or ""
    agent_organization = json_field_string(object_text, "agentOrganization") or ""
    model_display_body = jsonish_array_body(object_text, "model")
    model_org_body = jsonish_array_body(object_text, "modelOrganization")
    model_display = ",".join(parse_jsonish_string_array(model_display_body or ""))
    model_organization = ",".join(parse_jsonish_string_array(model_org_body or ""))

    submissions: list[Submission] = []
    for model, provider in row_model_provider_pairs(model_names, model_providers):
        submissions.append(
            Submission(
                url=canonical_submission_url(
                    bench_version, scaffold, scaffold_version, model, provider
                ),
                bench_version=bench_version,
                scaffold=scaffold,
                scaffold_version=scaffold_version,
                model=model,
                provider=provider,
                leaderboard_accuracy=optional_float(leaderboard_accuracy),
                leaderboard_stderr=optional_float(leaderboard_stderr),
                leaderboard_date=leaderboard_date,
                leaderboard_agent_display_name=agent_display_name,
                leaderboard_model_display=model_display,
                leaderboard_agent_organization=agent_organization,
                leaderboard_model_organization=model_organization,
            )
        )
    return submissions


def row_model_provider_pairs(
    model_names: list[str], model_providers: list[str]
) -> list[tuple[str, str]]:
    if not model_names or not model_providers:
        return []

    if len(model_names) == 1 and len(model_providers) == 1:
        return [(model_names[0], model_providers[0])]

    # A leaderboard row is one submission. Multi-model rows are routed as
    # comma-joined model/provider pairs, e.g. model-a@provider-a,model-b@provider-b.
    if len(model_names) == len(model_providers):
        return [(",".join(model_names), ",".join(model_providers))]

    if len(model_providers) == 1:
        return [(model_name, model_providers[0]) for model_name in model_names]

    if len(model_names) == 1:
        return [(model_names[0], model_provider) for model_provider in model_providers]

    return list(zip(model_names, model_providers))


def extract_row_submissions(text: str, bench_version: str) -> Iterable[Submission]:
    yielded = False
    for object_match in ROW_OBJECT_RE.finditer(text):
        for submission in row_submission_from_object(object_match.group(0), bench_version):
            yielded = True
            yield submission
    if yielded:
        return

    for match in ROW_SUBMISSION_RE.finditer(text):
        scaffold = decode_jsonish_string(match.group("scaffold"))
        scaffold_version = decode_jsonish_string(match.group("scaffold_version"))
        model_names = parse_jsonish_string_array(match.group("model_names"))
        model_providers = parse_jsonish_string_array(match.group("model_providers"))
        for model, provider in row_model_provider_pairs(model_names, model_providers):
            yield Submission(
                url=canonical_submission_url(
                    bench_version, scaffold, scaffold_version, model, provider
                ),
                bench_version=bench_version,
                scaffold=scaffold,
                scaffold_version=scaffold_version,
                model=model,
                provider=provider,
            )


def keep_richer_submission(
    submissions_by_url: dict[str, Submission],
    submission: Submission,
) -> None:
    existing = submissions_by_url.get(submission.url)
    if existing is None:
        submissions_by_url[submission.url] = submission
        return
    if existing.leaderboard_accuracy is None and submission.leaderboard_accuracy is not None:
        submissions_by_url[submission.url] = submission


def iter_script_texts(soup: BeautifulSoup) -> Iterable[str]:
    for script in soup.find_all("script"):
        text = script.string if script.string is not None else script.get_text()
        if text:
            yield text


def collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(collect_strings(item))
        return strings
    if isinstance(value, dict):
        strings = []
        for item in value.values():
            strings.extend(collect_strings(item))
        return strings
    return []


def extract_next_payload_strings(html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    payload_strings: list[str] = []

    for script_text in iter_script_texts(soup):
        if "__next_f.push" not in script_text:
            continue

        for match in re.finditer(
            r"(?:self\.__next_f|(?:self\.__next_f=self\.__next_f\|\|\[\]))"
            r"\.push\((\[.*\])\)\s*;?",
            script_text,
            flags=re.DOTALL,
        ):
            try:
                chunk = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            payload_strings.extend(collect_strings(chunk))

    return payload_strings


def payload_text_variants(html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    script_text = "\n".join(iter_script_texts(soup))
    decoded_payload = "\n".join(extract_next_payload_strings(html_text))
    originals = [text for text in (decoded_payload, script_text, html_text) if text]
    candidates = [*originals, *(normalize_payload_text(text) for text in originals)]

    variants: list[str] = []
    seen: set[str] = set()
    for text in candidates:
        if text in seen:
            continue
        seen.add(text)
        variants.append(text)
    return variants


def extract_submission_links(html_text: str, leaderboard_url: str) -> list[Submission]:
    soup = BeautifulSoup(html_text, "html.parser")
    submissions_by_url: dict[str, Submission] = {}
    bench_version = parse_bench_version(leaderboard_url)

    for anchor in soup.find_all("a", href=True):
        submission = parse_submission_url(anchor["href"])
        if submission:
            keep_richer_submission(submissions_by_url, submission)

    searchable_texts = [html_text]
    searchable_texts.extend(iter_script_texts(soup))
    for text in searchable_texts:
        normalized = normalize_payload_text(text)
        for match in TEXT_SUBMISSION_RE.finditer(normalized):
            submission = parse_submission_url(match.group("url"))
            if submission:
                keep_richer_submission(submissions_by_url, submission)
        for submission in extract_row_submissions(normalized, bench_version):
            keep_richer_submission(submissions_by_url, submission)

    return list(submissions_by_url.values())


def extract_tasks(html_text: str, submission_url: str) -> list[dict[str, object]]:
    tasks_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for text in payload_text_variants(html_text):
        for match in TASK_RE.finditer(text):
            task_name = decode_jsonish_string(match.group("taskName"))
            task_checksum = decode_jsonish_string(match.group("taskChecksum"))
            key = (task_name, task_checksum)
            tasks_by_key.setdefault(
                key,
                {
                    "taskName": task_name,
                    "taskChecksum": task_checksum,
                    "nTrials": int(match.group("nTrials")),
                    "avgResolutionRate": float(match.group("avgResolutionRate")),
                    "successCount": int(match.group("successCount")),
                    "trialUrl": f"{submission_url.rstrip('/')}/{quote(task_checksum, safe='')}",
                },
            )

    return list(tasks_by_key.values())


def json_field_string(object_text: str, field_name: str) -> str | None:
    match = re.search(
        rf'"{re.escape(field_name)}"\s*:\s*"(?P<value>(?:\\.|[^"\\])*)"',
        object_text,
    )
    if not match:
        return None
    return decode_jsonish_string(match.group("value"))


def json_field_number(object_text: str, field_name: str) -> float | int | None:
    match = re.search(
        rf'"{re.escape(field_name)}"\s*:\s*(?P<value>-?\d+(?:\.\d+)?)',
        object_text,
    )
    if not match:
        return None
    raw_value = match.group("value")
    if "." in raw_value:
        return float(raw_value)
    return int(raw_value)


def extract_trials(html_text: str) -> list[dict[str, object]]:
    trials_by_id: dict[str, dict[str, object]] = {}
    fields = [
        "trialName",
        "trialId",
        "reward",
        "nInputTokens",
        "nOutputTokens",
        "nCacheTokens",
        "costCents",
        "durationSeconds",
    ]

    for text in payload_text_variants(html_text):
        for match in TRIAL_OBJECT_RE.finditer(text):
            object_text = match.group(0)
            trial_id = json_field_string(object_text, "trialId")
            trial_name = json_field_string(object_text, "trialName")
            if not trial_id or not trial_name:
                continue

            trial: dict[str, object] = {}
            for field in fields:
                if field in {"trialName", "trialId"}:
                    value = json_field_string(object_text, field)
                else:
                    value = json_field_number(object_text, field)
                if value is not None:
                    trial[field] = value

            trials_by_id.setdefault(trial_id, trial)

    return list(trials_by_id.values())


def find_json_object_after_key(text: str, key: str) -> str | None:
    key_match = re.search(rf'"{re.escape(key)}"\s*:', text)
    if not key_match:
        return None

    start = text.find("{", key_match.end())
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def extract_trajectory(html_text: str) -> dict[str, Any]:
    payload_strings = extract_next_payload_strings(html_text)
    decoded_payload = "\n".join(payload_strings)
    references = build_rsc_reference_lookup(payload_strings)
    search_texts = [decoded_payload] if decoded_payload else []
    search_texts.extend(payload_text_variants(html_text))

    for text in search_texts:
        object_text = find_json_object_after_key(text, "trajectory")
        if not object_text:
            continue
        try:
            trajectory = json.loads(object_text)
        except json.JSONDecodeError:
            continue
        return resolve_rsc_references(trajectory, references)

    raise ValueError("trajectory object not found in page payload")


def leaderboard_accuracy_record(submission: Submission) -> dict[str, object]:
    accuracy = submission.leaderboard_accuracy
    stderr = submission.leaderboard_stderr
    return {
        "leaderboard_accuracy": accuracy if accuracy is not None else "",
        "leaderboard_stderr": stderr if stderr is not None else "",
        "leaderboard_date": submission.leaderboard_date,
        "leaderboard_agent_display_name": submission.leaderboard_agent_display_name,
        "leaderboard_model_display": submission.leaderboard_model_display,
        "leaderboard_agent_organization": submission.leaderboard_agent_organization,
        "leaderboard_model_organization": submission.leaderboard_model_organization,
    }


def page_has_no_trajectory_marker(html_text: str) -> bool:
    return "No trajectory data available" in html_text


def trial_record(
    submission: dict[str, object],
    task: dict[str, object],
    trial: dict[str, object],
) -> dict[str, object]:
    task_url = str(task.get("trialUrl") or "")
    trial_id = str(trial.get("trialId") or "")
    return {
        "submission": {
            "scaffold": submission.get("scaffold"),
            "scaffold_version": submission.get("scaffold_version"),
            "model": submission.get("model"),
            "provider": submission.get("provider"),
        },
        "submission_url": submission.get("submission_url"),
        "taskName": task.get("taskName"),
        "taskChecksum": task.get("taskChecksum"),
        "taskUrl": task_url,
        "trialUrl": f"{task_url.rstrip('/')}/{quote(trial_id, safe='')}",
        **trial,
    }


def collect_submission_trial_metadata(
    session: requests.Session,
    submission: dict[str, object],
) -> tuple[list[dict[str, object]], list[tuple[str, str]]]:
    records: list[dict[str, object]] = []
    failures: list[tuple[str, str]] = []
    tasks = list(submission.get("tasks") or [])

    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_url = str(task.get("trialUrl") or "")
        if not task_url:
            failures.append((str(task.get("taskName") or "unknown"), "no task URL"))
            continue
        try:
            task_html = fetch_html(session, task_url)
            trials = extract_trials(task_html)
        except (requests.RequestException, ValueError) as exc:
            failures.append((task_url, str(exc)))
            print(f"  warning: trial metadata failed for {task_url}: {exc}", file=sys.stderr)
            continue

        records.extend(trial_record(submission, task, trial) for trial in trials)

    return records, failures


def index_file_path(output_path: Path) -> str:
    try:
        return output_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return output_path.as_posix()


def trial_output_path(trial: dict[str, object], trajectories_dir: Path) -> Path:
    submission = trial.get("submission") if isinstance(trial.get("submission"), dict) else {}
    scaffold = str(submission.get("scaffold") or "unknown")
    model = str(submission.get("model") or "unknown")
    task_checksum = str(trial.get("taskChecksum") or trial.get("taskName") or "unknown")
    trial_id = str(trial.get("trialId") or "unknown")
    return (
        trajectories_dir
        / safe_path_component(scaffold)
        / safe_path_component(model)
        / f"{safe_path_component(task_checksum)}_{safe_path_component(trial_id)}.json"
    )


def trial_index_entry(trial: dict[str, object], output_path: Path) -> dict[str, object]:
    submission = trial.get("submission") if isinstance(trial.get("submission"), dict) else {}
    return {
        "scaffold": str(submission.get("scaffold") or "unknown"),
        "model": str(submission.get("model") or "unknown"),
        "taskName": str(trial.get("taskName") or "unknown"),
        "taskChecksum": str(trial.get("taskChecksum") or trial.get("taskName") or "unknown"),
        "trialId": str(trial.get("trialId") or ""),
        "source_submission_url": str(trial.get("submission_url") or ""),
        "source_scaffold_version": str(submission.get("scaffold_version") or ""),
        "source_provider": str(submission.get("provider") or ""),
        "reward": float(trial.get("reward") or 0.0),
        "cost": float(trial.get("costCents") or 0.0),
        "duration": float(trial.get("durationSeconds") or 0.0),
        "filePath": index_file_path(output_path),
    }


def fetch_trial_trajectory(session: requests.Session, trial: dict[str, object]) -> dict[str, Any]:
    trial_url = str(trial.get("trialUrl") or "")
    if not trial_url:
        raise ValueError("trial metadata has no trialUrl")
    trial_html = fetch_html(session, trial_url)
    if page_has_no_trajectory_marker(trial_html):
        raise ValueError("trial page says no trajectory data available")
    return extract_trajectory(trial_html)


def download_trajectories_from_trial_records(
    trials: list[dict[str, object]],
    trajectories_dir: Path,
    index_path: Path,
) -> tuple[int, int, list[tuple[str, str]]]:
    session = requests.Session()
    index_writer = TrajectoryIndexWriter(
        index_path=index_path,
        checkpoint_interval=INDEX_CHECKPOINT_INTERVAL,
    )
    pruned = index_writer.prune_invalid_file_entries(REPO_ROOT)
    indexed = 0
    fetched = 0
    failures: list[tuple[str, str]] = []

    print(f"Checking {len(trials)} cached 2.0 trial records for trajectories")
    for index, trial in enumerate(trials, start=1):
        if not isinstance(trial, dict):
            failures.append((f"trial[{index}]", "trial record is not an object"))
            continue
        trial_id = str(trial.get("trialId") or "")
        if not trial_id:
            failures.append((f"trial[{index}]", "trial record has no trialId"))
            continue

        output_path = trial_output_path(trial, trajectories_dir)
        entry = trial_index_entry(trial, output_path)
        is_valid, reason = trajectory_file_status(output_path)
        if is_valid:
            index_writer.upsert(entry)
            index_writer.checkpoint()
            indexed += 1
            continue
        index_writer.remove(entry)
        if reason != "missing":
            print(
                f"  warning: retrying invalid trajectory file {output_path}: {reason}",
                file=sys.stderr,
            )

        try:
            trajectory = fetch_trial_trajectory(session, trial)
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            failures.append((trial_id, str(exc)))
            print(f"  warning: trajectory failed for {trial_id}: {exc}", file=sys.stderr)
            continue
        payload_is_valid, payload_reason = trajectory_payload_status(trajectory)
        if not payload_is_valid:
            failures.append((trial_id, payload_reason))
            print(
                f"  warning: trajectory failed for {trial_id}: {payload_reason}",
                file=sys.stderr,
            )
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(trajectory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        index_writer.upsert(entry)
        index_writer.checkpoint()
        indexed += 1
        fetched += 1

    index_writer.checkpoint(force=True)
    if pruned:
        print(f"Removed {pruned} stale trajectory index entries")
    return indexed, fetched, failures


def load_trial_metadata(trials_path: Path) -> list[dict[str, object]]:
    try:
        trials = read_json_file(trials_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {trials_path}: {exc}") from exc
    if not isinstance(trials, list):
        raise ValueError(f"{trials_path} does not contain a JSON list")
    return [trial for trial in trials if isinstance(trial, dict)]


def retry_trajectories_from_trials_file(
    trials_path: Path,
    trajectories_dir: Path,
    index_path: Path,
) -> int:
    try:
        trials = load_trial_metadata(trials_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    indexed, fetched, failures = download_trajectories_from_trial_records(
        trials=trials,
        trajectories_dir=trajectories_dir,
        index_path=index_path,
    )
    print(f"Indexed {indexed} trajectories under {trajectories_dir}; fetched {fetched}")
    print(f"Trajectory index: {index_path}")
    if failures:
        print(f"Completed with {len(failures)} failures:", file=sys.stderr)
        for key, error in failures[:20]:
            print(f"  {key}: {error}", file=sys.stderr)
        if len(failures) > 20:
            print(f"  ... {len(failures) - 20} more", file=sys.stderr)
        return 1
    return 0


def collect_leaderboard(
    leaderboard_url: str,
    output_path: Path,
    trials_output_path: Path,
    download_trajectories_enabled: bool,
    trajectories_dir: Path,
    trajectory_index: Path,
) -> int:
    existing_by_key: dict[SubmissionKey, dict[str, object]] = {}
    if output_path.exists():
        try:
            existing_rows = read_json_file(output_path)
        except (OSError, json.JSONDecodeError):
            existing_rows = []
        if isinstance(existing_rows, list):
            for row in existing_rows:
                if not isinstance(row, dict):
                    continue
                existing_by_key[submission_key_from_record(row)] = row

    session = requests.Session()
    print(f"Fetching leaderboard: {leaderboard_url}")
    leaderboard_html = fetch_html(session, leaderboard_url)
    submissions = extract_submission_links(leaderboard_html, leaderboard_url)

    print(f"Found {len(submissions)} submission URLs")
    rows: list[dict[str, object]] = []
    all_trial_records: list[dict[str, object]] = []
    failures: list[tuple[str, str]] = []

    for index, submission in enumerate(submissions, start=1):
        print(f"[{index}/{len(submissions)}] Fetching {submission.url}")
        try:
            submission_html = fetch_html(session, submission.url)
            tasks = extract_tasks(submission_html, submission.url)
        except requests.RequestException as exc:
            failures.append((submission.url, str(exc)))
            print(f"  warning: skipped after request error: {exc}", file=sys.stderr)
            continue

        if not tasks:
            print("  warning: no task records found", file=sys.stderr)

        existing = existing_by_key.get(submission_key_from_submission(submission), {})
        official_metrics = leaderboard_accuracy_record(submission)
        for metric_key, metric_value in list(official_metrics.items()):
            if metric_value in {"", None} and existing.get(metric_key) not in {"", None}:
                official_metrics[metric_key] = existing[metric_key]
        row = {
            "scaffold": submission.scaffold,
            "scaffold_version": submission.scaffold_version,
            "model": submission.model,
            "provider": submission.provider,
            "has_trajectories": existing.get("has_trajectories", ""),
            "submission_url": submission.url,
            **official_metrics,
            "tasks": tasks,
        }
        rows.append(row)

        trial_records, trial_failures = collect_submission_trial_metadata(session, row)
        all_trial_records.extend(trial_records)
        failures.extend(trial_failures)
        print(f"  cached trial records={len(trial_records)}, metadata failures={len(trial_failures)}")

    write_json_file(output_path, rows)
    print(f"Wrote {len(rows)} submissions to {output_path}")
    write_json_file(trials_output_path, all_trial_records)
    print(f"Wrote {len(all_trial_records)} trial metadata records to {trials_output_path}")

    if download_trajectories_enabled:
        indexed, fetched, trajectory_failures = download_trajectories_from_trial_records(
            trials=all_trial_records,
            trajectories_dir=trajectories_dir,
            index_path=trajectory_index,
        )
        failures.extend(trajectory_failures)
        print(f"Indexed {indexed} trajectories under {trajectories_dir}; fetched {fetched}")
        print(f"Trajectory index: {trajectory_index}")

    if failures:
        print(f"Completed with {len(failures)} failures:", file=sys.stderr)
        for url, error in failures:
            print(f"  {url}: {error}", file=sys.stderr)
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Terminal-Bench leaderboard task data from tbench.ai HTML."
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--download-trajectories",
        action="store_true",
        help="Scrape metadata, then download all available trajectory JSON.",
    )
    mode_group.add_argument(
        "--retry-trajectories",
        action="store_true",
        help="Download/retry trajectories from the saved trial metadata cache.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    benchmark_paths = paths_for_benchmark(REPO_ROOT, DEFAULT_BENCHMARK)

    if args.retry_trajectories:
        return retry_trajectories_from_trials_file(
            trials_path=benchmark_paths.leaderboard_trials,
            trajectories_dir=benchmark_paths.trajectories_dir,
            index_path=benchmark_paths.trajectory_index,
        )

    return collect_leaderboard(
        leaderboard_url=DEFAULT_LEADERBOARD_URL,
        output_path=benchmark_paths.leaderboard_submissions,
        trials_output_path=benchmark_paths.leaderboard_trials,
        download_trajectories_enabled=args.download_trajectories,
        trajectories_dir=benchmark_paths.trajectories_dir,
        trajectory_index=benchmark_paths.trajectory_index,
    )


if __name__ == "__main__":
    raise SystemExit(main())
