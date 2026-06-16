#!/usr/bin/env python3
"""Collect Terminal-Bench v2 leaderboard task data.

The tbench.ai pages server-render leaderboard data into the HTML, including
Next.js RSC payload chunks in ``<script>`` tags. This scraper intentionally uses
only ``requests``, ``BeautifulSoup``, and Python's standard library.
"""

from __future__ import annotations

import argparse
import html
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

from .build_trajectory_index import TrajectoryIndexWriter
from .sampling_strategies import sample_submissions, submission_score


BASE_URL = "https://www.tbench.ai"
DEFAULT_LEADERBOARD_URL = f"{BASE_URL}/leaderboard/terminal-bench/2.0"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
DEFAULT_OUTPUT_PATH = DATA_DIR / "raw" / "leaderboard_submissions_current.json"
DEFAULT_TRAJECTORIES_DIR = DATA_DIR / "trajectories" / "sample"
DEFAULT_TRAJECTORY_INDEX = DATA_DIR / "indexes" / "trajectory_index.json"
REQUEST_DELAY_SECONDS = 0.5
NORMAL_95_CI_MULTIPLIER = 1.96

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

RSC_DEFINITION_RE = re.compile(r"(?m)^([0-9a-z]+):", re.IGNORECASE)
RSC_REFERENCE_RE = re.compile(r"^\$([0-9a-z]+)$", re.IGNORECASE)


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
    variants = [text for text in (decoded_payload, script_text, html_text) if text]

    index = 0
    while index < len(variants):
        normalized = normalize_payload_text(variants[index])
        if normalized not in variants:
            variants.append(normalized)
        index += 1

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


def parse_json_prefix(text: str) -> Any | None:
    try:
        value, _ = json.JSONDecoder().raw_decode(text.lstrip())
    except json.JSONDecodeError:
        return None
    return value


def extract_rsc_references(payload_text: str) -> dict[str, Any]:
    references: dict[str, Any] = {}
    matches = list(RSC_DEFINITION_RE.finditer(payload_text))
    for index, match in enumerate(matches):
        value_start = match.end()
        value_end = matches[index + 1].start() if index + 1 < len(matches) else len(payload_text)
        value_text = payload_text[value_start:value_end].strip()
        parsed = parse_json_prefix(value_text)
        if parsed is not None:
            references[match.group(1)] = parsed
    return references


def extract_rsc_text_references(payload_strings: list[str]) -> dict[str, str]:
    """Resolve Next Flight text records like ``31:T<hex_length>,...``.

    Large text values can be split across multiple ``__next_f.push`` chunks, and
    a consumed chunk can itself contain another ``NUMBER:T...`` record. Scan the
    complete Flight stream so each text reference is discovered independently.
    """
    references: dict[str, str] = {}
    flight_stream = "".join(payload_strings)
    for match in re.finditer(
        r"(?<![0-9A-Za-z])([0-9a-z]+):T([0-9a-f]+),",
        flight_stream,
        flags=re.IGNORECASE,
    ):
        reference_id = match.group(1)
        expected_length = int(match.group(2), 16)
        content_start = match.end()
        references[reference_id] = flight_stream[
            content_start : content_start + expected_length
        ]

    return references


def build_rsc_reference_lookup(payload_strings: list[str]) -> dict[str, Any]:
    decoded_payload = "\n".join(payload_strings)
    references = extract_rsc_references(decoded_payload)
    references.update(extract_rsc_text_references(payload_strings))
    return references


def resolve_rsc_references(value: Any, references: dict[str, Any], seen: set[str] | None = None) -> Any:
    if seen is None:
        seen = set()

    if isinstance(value, str):
        match = RSC_REFERENCE_RE.fullmatch(value)
        if match:
            reference_id = match.group(1)
            if reference_id in references and reference_id not in seen:
                return resolve_rsc_references(
                    references[reference_id], references, seen | {reference_id}
                )
        return value

    if isinstance(value, list):
        return [resolve_rsc_references(item, references, seen) for item in value]

    if isinstance(value, dict):
        return {
            key: resolve_rsc_references(item, references, seen)
            for key, item in value.items()
        }

    return value


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
    accuracy_percent = accuracy * 100.0 if accuracy is not None else None
    stderr_percent = stderr * 100.0 if stderr is not None else None
    ci95_pm_percent = stderr * NORMAL_95_CI_MULTIPLIER * 100.0 if stderr is not None else None
    accuracy_display = (
        f"{accuracy_percent:.1f}%+/- {ci95_pm_percent:.1f}"
        if accuracy_percent is not None and ci95_pm_percent is not None
        else ""
    )
    return {
        "leaderboard_accuracy": accuracy if accuracy is not None else "",
        "leaderboard_accuracy_percent": accuracy_percent if accuracy_percent is not None else "",
        "leaderboard_stderr": stderr if stderr is not None else "",
        "leaderboard_stderr_percent": stderr_percent if stderr_percent is not None else "",
        "leaderboard_accuracy_ci95_pm_percent": ci95_pm_percent if ci95_pm_percent is not None else "",
        "leaderboard_accuracy_display": accuracy_display,
        "leaderboard_date": submission.leaderboard_date,
        "leaderboard_agent_display_name": submission.leaderboard_agent_display_name,
        "leaderboard_model_display": submission.leaderboard_model_display,
        "leaderboard_agent_organization": submission.leaderboard_agent_organization,
        "leaderboard_model_organization": submission.leaderboard_model_organization,
    }


def submission_url_from_record(submission: dict[str, Any], bench_version: str = "2.0") -> str:
    tasks = submission.get("tasks") or []
    for task in tasks:
        trial_url = task.get("trialUrl")
        task_checksum = task.get("taskChecksum")
        if isinstance(trial_url, str) and isinstance(task_checksum, str):
            suffix = f"/{quote(task_checksum, safe='')}"
            if trial_url.endswith(suffix):
                return trial_url[: -len(suffix)]
            return trial_url.rsplit("/", 1)[0]

    return canonical_submission_url(
        bench_version=bench_version,
        scaffold=str(submission["scaffold"]),
        scaffold_version=str(submission.get("scaffold_version", "unknown")),
        model=str(submission["model"]),
        provider=str(submission.get("provider", "")),
    )


def safe_path_component(value: object) -> str:
    text = str(value).strip() or "unknown"
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip(" ._")
    return text[:160] or "unknown"


def first_task_with_url(submission: dict[str, Any]) -> dict[str, Any] | None:
    for task in submission.get("tasks") or []:
        if task.get("trialUrl") and task.get("taskChecksum"):
            return task
    return None


def page_has_no_trajectory_marker(html_text: str) -> bool:
    return "No trajectory data available" in html_text


def check_single_submission_trajectory_availability(
    session: requests.Session,
    submission: dict[str, Any],
) -> tuple[bool, str]:
    task = first_task_with_url(submission)
    if not task:
        return False, "no task URL available"

    task_url = str(task["trialUrl"])
    task_html = fetch_html(session, task_url)
    trials = extract_trials(task_html)
    if not trials:
        return False, "no trial records found on first task page"

    trial_id = str(trials[0].get("trialId") or "")
    if not trial_id:
        return False, "first trial record has no trialId"

    trial_url = f"{task_url.rstrip('/')}/{quote(trial_id, safe='')}"
    trial_html = fetch_html(session, trial_url)
    if page_has_no_trajectory_marker(trial_html):
        return False, "trial page says no trajectory data available"

    try:
        extract_trajectory(trial_html)
    except ValueError:
        return False, "trajectory object not found"

    return True, "trajectory object found"


def check_trajectory_availability(
    leaderboard_path: Path,
    limit: int | None = None,
) -> int:
    leaderboard = json.loads(leaderboard_path.read_text(encoding="utf-8"))
    session = requests.Session()
    rows_to_check = leaderboard[:limit] if limit is not None else leaderboard

    available = 0
    unavailable = 0
    print(f"Checking trajectory availability for {len(rows_to_check)} submissions")

    for index, submission in enumerate(rows_to_check, start=1):
        label = f"{submission.get('scaffold')} / {submission.get('model')}"
        try:
            has_trajectories, reason = check_single_submission_trajectory_availability(
                session, submission
            )
        except requests.RequestException as exc:
            has_trajectories = False
            reason = f"request failed: {exc}"

        submission["has_trajectories"] = has_trajectories
        if has_trajectories:
            available += 1
        else:
            unavailable += 1
        print(
            f"[{index}/{len(rows_to_check)}] {label}: "
            f"has_trajectories={has_trajectories} ({reason})"
        )

    leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
    leaderboard_path.write_text(
        json.dumps(leaderboard, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    unchecked = len(leaderboard) - len(rows_to_check)
    print("\nAvailability summary")
    print(f"  checked: {len(rows_to_check)}")
    print(f"  available: {available}")
    print(f"  unavailable: {unavailable}")
    print(f"  unchecked: {unchecked}")
    print(f"  updated: {leaderboard_path}")
    return 0


def collect_trajectories(
    leaderboard_path: Path,
    sample_n: int,
    strategy: str,
    trajectories_dir: Path,
    index_path: Path,
    task_limit: int | None = None,
    trial_limit: int | None = None,
    index_checkpoint_interval: int = 250,
    sample_start_index: int = 1,
) -> int:
    leaderboard = json.loads(leaderboard_path.read_text(encoding="utf-8"))
    full_sample = sample_submissions(sample_n, strategy, leaderboard)
    if sample_start_index < 1:
        raise ValueError("--sample-start-index must be 1 or greater.")
    sampled = full_sample[sample_start_index - 1 :]
    session = requests.Session()

    trajectory_index = TrajectoryIndexWriter(
        index_path=index_path,
        checkpoint_interval=index_checkpoint_interval,
    )

    submissions_processed = 0
    tasks_fetched = 0
    trials_downloaded = 0
    passed_trials = 0
    total_cost_cents = 0.0
    total_duration_seconds = 0.0
    failures: list[tuple[str, str]] = []

    print(
        f"Sampling {len(sampled)} of {len(full_sample)} submissions from {leaderboard_path} "
        f"with strategy={strategy!r}, start_index={sample_start_index}"
    )

    for submission_index, submission in enumerate(sampled, start=sample_start_index):
        submissions_processed += 1
        submission_url = submission_url_from_record(submission)
        tasks = list(submission.get("tasks") or [])
        if task_limit is not None:
            tasks = tasks[:task_limit]

        print(
            f"[{submission_index}/{len(sampled)}] "
            f"{submission.get('scaffold')} / {submission.get('model')} "
            f"score={submission_score(submission):.3f}, tasks={len(tasks)}"
        )

        for task_index, task in enumerate(tasks, start=1):
            task_checksum = str(task.get("taskChecksum", ""))
            task_name = str(task.get("taskName", ""))
            task_url = str(task.get("trialUrl") or f"{submission_url}/{quote(task_checksum, safe='')}")

            try:
                task_html = fetch_html(session, task_url)
                trials = extract_trials(task_html)
            except (requests.RequestException, ValueError) as exc:
                failures.append((task_url, str(exc)))
                print(f"  warning: task fetch failed: {task_url}: {exc}", file=sys.stderr)
                continue

            tasks_fetched += 1
            if trial_limit is not None:
                trials = trials[:trial_limit]
            print(f"  task {task_index}/{len(tasks)} {task_name}: {len(trials)} trials")

            for trial in trials:
                trial_id = str(trial.get("trialId", ""))
                if not trial_id:
                    continue

                trial_url = f"{task_url.rstrip('/')}/{quote(trial_id, safe='')}"
                scaffold = str(submission.get("scaffold", "unknown"))
                model = str(submission.get("model", "unknown"))
                output_dir = trajectories_dir / safe_path_component(scaffold) / safe_path_component(model)
                output_path = output_dir / f"{safe_path_component(task_checksum)}_{safe_path_component(trial_id)}.json"
                reward = float(trial.get("reward", 0.0) or 0.0)
                cost_cents = float(trial.get("costCents", 0.0) or 0.0)
                duration_seconds = float(trial.get("durationSeconds", 0.0) or 0.0)
                entry = {
                    "scaffold": scaffold,
                    "model": model,
                    "taskName": task_name,
                    "taskChecksum": task_checksum,
                    "trialId": trial_id,
                    "reward": reward,
                    "cost": cost_cents,
                    "duration": duration_seconds,
                    "filePath": output_path.as_posix(),
                }

                if output_path.exists():
                    trajectory_index.upsert(entry)
                    trials_downloaded += 1
                    passed_trials += 1 if reward > 0 else 0
                    total_cost_cents += cost_cents
                    total_duration_seconds += duration_seconds
                    trajectory_index.checkpoint()
                    continue

                try:
                    trial_html = fetch_html(session, trial_url)
                    trajectory = extract_trajectory(trial_html)
                except (requests.RequestException, ValueError) as exc:
                    failures.append((trial_url, str(exc)))
                    print(
                        f"  warning: trial download failed: {trial_url}: {exc}",
                        file=sys.stderr,
                    )
                    continue

                output_dir.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    json.dumps(trajectory, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

                trajectory_index.upsert(entry)

                trials_downloaded += 1
                passed_trials += 1 if reward > 0 else 0
                total_cost_cents += cost_cents
                total_duration_seconds += duration_seconds
                trajectory_index.checkpoint()

    trajectory_index.checkpoint(force=True)

    pass_rate = passed_trials / trials_downloaded if trials_downloaded else 0.0
    print("\nProgress summary")
    print(f"  submissions processed: {submissions_processed}")
    print(f"  tasks fetched: {tasks_fetched}")
    print(f"  trials downloaded: {trials_downloaded}")
    print(f"  pass rate: {pass_rate:.2%}")
    print(
        f"  estimated total cost: ${total_cost_cents / 100:.4f} "
        f"({total_cost_cents:.4f} cents)"
    )
    print(f"  total trial duration: {total_duration_seconds:.1f}s")
    print(f"  index file: {index_path}")

    if failures:
        print(f"Completed with {len(failures)} failures:", file=sys.stderr)
        for url, error in failures[:20]:
            print(f"  {url}: {error}", file=sys.stderr)
        if len(failures) > 20:
            print(f"  ... {len(failures) - 20} more", file=sys.stderr)
        return 1

    return 0


def collect_leaderboard(
    leaderboard_url: str,
    output_path: Path,
    limit: int | None = None,
) -> int:
    existing_by_key: dict[tuple[str, str, str, str], dict[str, object]] = {}
    if output_path.exists():
        try:
            existing_rows = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing_rows = []
        if isinstance(existing_rows, list):
            for row in existing_rows:
                if not isinstance(row, dict):
                    continue
                key = (
                    str(row.get("scaffold", "")),
                    str(row.get("scaffold_version", "")),
                    str(row.get("model", "")),
                    str(row.get("provider", "")),
                )
                existing_by_key[key] = row

    session = requests.Session()
    print(f"Fetching leaderboard: {leaderboard_url}")
    leaderboard_html = fetch_html(session, leaderboard_url)
    submissions = extract_submission_links(leaderboard_html, leaderboard_url)
    if limit is not None:
        submissions = submissions[:limit]

    print(f"Found {len(submissions)} submission URLs")
    rows: list[dict[str, object]] = []
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

        key = (
            submission.scaffold,
            submission.scaffold_version,
            submission.model,
            submission.provider,
        )
        existing = existing_by_key.get(key, {})
        official_metrics = leaderboard_accuracy_record(submission)
        for metric_key, metric_value in list(official_metrics.items()):
            if metric_value in {"", None} and existing.get(metric_key) not in {"", None}:
                official_metrics[metric_key] = existing[metric_key]
        rows.append(
            {
                "scaffold": submission.scaffold,
                "scaffold_version": submission.scaffold_version,
                "model": submission.model,
                "provider": submission.provider,
                "has_trajectories": existing.get("has_trajectories", ""),
                "submission_url": submission.url,
                **official_metrics,
                "tasks": tasks,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(rows)} submissions to {output_path}")

    if failures:
        print(f"Completed with {len(failures)} failed submission fetches:", file=sys.stderr)
        for url, error in failures:
            print(f"  {url}: {error}", file=sys.stderr)
        return 1
    return 0


def refresh_leaderboard_row_metrics(
    leaderboard_url: str,
    leaderboard_path: Path,
) -> int:
    try:
        rows = json.loads(leaderboard_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read {leaderboard_path}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(rows, list):
        print(f"{leaderboard_path} does not contain a JSON list", file=sys.stderr)
        return 1

    session = requests.Session()
    print(f"Fetching leaderboard row metrics: {leaderboard_url}")
    leaderboard_html = fetch_html(session, leaderboard_url)
    submissions = extract_submission_links(leaderboard_html, leaderboard_url)
    metrics_by_key = {
        (
            submission.scaffold,
            submission.scaffold_version,
            submission.model,
            submission.provider,
        ): leaderboard_accuracy_record(submission)
        for submission in submissions
        if submission.leaderboard_accuracy is not None
    }

    updated = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (
            str(row.get("scaffold", "")),
            str(row.get("scaffold_version", "")),
            str(row.get("model", "")),
            str(row.get("provider", "")),
        )
        metrics = metrics_by_key.get(key)
        if not metrics:
            continue
        row.update(metrics)
        updated += 1

    leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
    leaderboard_path.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Updated official leaderboard metrics for {updated}/{len(rows)} rows in {leaderboard_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Terminal-Bench leaderboard task data from tbench.ai HTML."
    )
    parser.add_argument("--leaderboard-url", default=DEFAULT_LEADERBOARD_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--collect-trajectories",
        action="store_true",
        help="Load an existing leaderboard JSON and download sampled trial trajectories.",
    )
    parser.add_argument(
        "--check-trajectory-availability",
        action="store_true",
        help=(
            "Fetch one trial page per submission, mark has_trajectories in the "
            "leaderboard JSON, then exit."
        ),
    )
    parser.add_argument(
        "--refresh-row-metrics-only",
        action="store_true",
        help=(
            "Fetch the leaderboard table and update official row-level "
            "accuracy/stderr fields in an existing leaderboard JSON."
        ),
    )
    parser.add_argument(
        "--leaderboard-json",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Existing leaderboard JSON to sample from when --collect-trajectories is used.",
    )
    parser.add_argument(
        "--sample-n",
        type=int,
        default=3,
        help="Number of submissions to sample for trajectory collection.",
    )
    parser.add_argument(
        "--sample-start-index",
        type=int,
        default=1,
        help=(
            "1-based index into the sampled submission list where collection "
            "should start; useful when resuming a long run."
        ),
    )
    parser.add_argument(
        "--strategy",
        choices=["top", "balanced"],
        default="top",
        help="Sampling strategy for --collect-trajectories.",
    )
    parser.add_argument(
        "--trajectories-dir",
        type=Path,
        default=DEFAULT_TRAJECTORIES_DIR,
        help="Directory where trajectory JSON files are saved.",
    )
    parser.add_argument(
        "--trajectory-index",
        type=Path,
        default=DEFAULT_TRAJECTORY_INDEX,
        help="Master trajectory index JSON path.",
    )
    parser.add_argument(
        "--index-checkpoint-interval",
        type=int,
        default=250,
        help=(
            "Write the trajectory index after this many updates during "
            "--collect-trajectories. Use 0 to write only at the end."
        ),
    )
    parser.add_argument(
        "--task-limit",
        type=int,
        default=None,
        help="Only fetch the first N tasks per sampled submission; useful for smoke tests.",
    )
    parser.add_argument(
        "--trial-limit",
        type=int,
        default=None,
        help="Only download the first N trials per task; useful for smoke tests.",
    )
    parser.add_argument(
        "--availability-limit",
        type=int,
        default=None,
        help="Only check the first N submissions for trajectory availability.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only fetch the first N submissions; useful for smoke tests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.refresh_row_metrics_only:
        return refresh_leaderboard_row_metrics(
            leaderboard_url=args.leaderboard_url,
            leaderboard_path=args.leaderboard_json,
        )

    if args.check_trajectory_availability:
        return check_trajectory_availability(
            leaderboard_path=args.leaderboard_json,
            limit=args.availability_limit,
        )

    if args.collect_trajectories:
        return collect_trajectories(
            leaderboard_path=args.leaderboard_json,
            sample_n=args.sample_n,
            strategy=args.strategy,
            trajectories_dir=args.trajectories_dir,
            index_path=args.trajectory_index,
            task_limit=args.task_limit,
            trial_limit=args.trial_limit,
            index_checkpoint_interval=args.index_checkpoint_interval,
            sample_start_index=args.sample_start_index,
        )

    return collect_leaderboard(
        leaderboard_url=args.leaderboard_url,
        output_path=args.output,
        limit=args.limit,
    )


if __name__ == "__main__":
    raise SystemExit(main())
