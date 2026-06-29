#!/usr/bin/env python3
"""Scrape Terminal-Bench benchmark task metadata from tbench.ai.

The benchmark page server-renders a Next.js payload with the full task list.
This script extracts the task metadata we need for analysis:

- id
- category
- difficulty
- description
- tags

By default it writes a JSON file and a CSV file under the repository data
directories.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Iterable


BASE_URL = "https://www.tbench.ai"
DEFAULT_URL = f"{BASE_URL}/benchmarks/terminal-bench-2"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
DEFAULT_JSON_OUTPUT = DATA_DIR / "raw" / "terminal_bench_2_tasks_current.json"
DEFAULT_CSV_OUTPUT = (
    DATA_DIR / "processed_live" / "task_mining" / "terminal_bench_2_tasks_current.csv"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

RSC_DEFINITION_RE = re.compile(r"(?m)^([0-9a-z]+):", re.IGNORECASE)
RSC_REFERENCE_RE = re.compile(r"^\$([0-9a-z]+)$", re.IGNORECASE)


def fetch_html(url: str) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def iter_script_texts(html_text: str) -> Iterable[str]:
    for match in re.finditer(r"<script\b[^>]*>(.*?)</script>", html_text, flags=re.DOTALL | re.IGNORECASE):
        text = match.group(1)
        if text:
            yield html.unescape(text)


def collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(collect_strings(item))
        return strings
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(collect_strings(item))
        return strings
    return []


def extract_next_payload_strings(html_text: str) -> list[str]:
    payload_strings: list[str] = []
    for script_text in iter_script_texts(html_text):
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


def extract_rsc_text_references(payload_strings: list[str]) -> dict[str, str]:
    """Resolve Next Flight text records like ``31:T<hex_length>,...``."""
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
        references[reference_id] = flight_stream[content_start : content_start + expected_length]

    return references


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


def build_rsc_reference_lookup(payload_strings: list[str]) -> dict[str, Any]:
    decoded_payload = "\n".join(payload_strings)
    references = extract_rsc_references(decoded_payload)
    references.update(extract_rsc_text_references(payload_strings))
    return references


def resolve_rsc_references(
    value: Any, references: dict[str, Any], seen: set[str] | None = None
) -> Any:
    if seen is None:
        seen = set()

    if isinstance(value, str):
        match = RSC_REFERENCE_RE.fullmatch(value)
        if match:
            reference_id = match.group(1)
            if reference_id in references and reference_id not in seen:
                return resolve_rsc_references(references[reference_id], references, seen | {reference_id})
        return value

    if isinstance(value, list):
        return [resolve_rsc_references(item, references, seen) for item in value]

    if isinstance(value, dict):
        return {
            key: resolve_rsc_references(item, references, seen)
            for key, item in value.items()
        }

    return value


def normalize_payload_text(text: str) -> str:
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
    }
    for _ in range(4):
        before = normalized
        for escaped, plain in replacements.items():
            normalized = normalized.replace(escaped, plain)
        if normalized == before:
            break
    return normalized


def extract_tasks_payload(html_text: str) -> str:
    """Return the JSON array text for the benchmark tasks."""
    payload_text = "\n".join(extract_next_payload_strings(html_text))
    payload_text = normalize_payload_text(payload_text)

    key = '"tasks":['
    start = payload_text.find(key)
    if start == -1:
        raise RuntimeError("Could not locate tasks array in the benchmark page payload")

    array_start = start + len('"tasks":')
    if payload_text[array_start] != "[":
        raise RuntimeError("Unexpected payload format while locating tasks array")

    depth = 0
    in_string = False
    escaped = False
    for index in range(array_start, len(payload_text)):
        char = payload_text[index]
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
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return payload_text[array_start : index + 1]

    raise RuntimeError("Unterminated tasks array in benchmark payload")


def parse_tasks(html_text: str) -> list[dict[str, Any]]:
    payload_strings = extract_next_payload_strings(html_text)
    references = build_rsc_reference_lookup(payload_strings)
    tasks_json = extract_tasks_payload(html_text)
    tasks = json.loads(tasks_json)
    if not isinstance(tasks, list):
        raise RuntimeError("Parsed tasks payload is not a list")

    normalized: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        resolved_task = resolve_rsc_references(task, references)
        normalized.append(
            {
                "id": resolved_task.get("id", ""),
                "category": resolved_task.get("category", ""),
                "difficulty": resolved_task.get("difficulty", ""),
                "description": resolved_task.get("instruction", ""),
                "tags": resolved_task.get("tags", []),
            }
        )
    return normalized


def write_json(path: Path, tasks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(tasks, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_csv(path: Path, tasks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "category", "difficulty", "description", "tags"],
        )
        writer.writeheader()
        for task in tasks:
            writer.writerow(
                {
                    "id": task["id"],
                    "category": task["category"],
                    "difficulty": task["difficulty"],
                    "description": task["description"],
                    "tags": "|".join(task.get("tags", [])),
                }
            )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape Terminal-Bench 2.0 task metadata from tbench.ai."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Benchmark page URL to scrape")
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_OUTPUT,
        help="Output JSON path",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=DEFAULT_CSV_OUTPUT,
        help="Output CSV path",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    html_text = fetch_html(args.url)
    tasks = parse_tasks(html_text)

    write_json(args.json_output, tasks)
    write_csv(args.csv_output, tasks)

    print(f"Wrote {len(tasks)} tasks")
    print(f"JSON: {args.json_output}")
    print(f"CSV: {args.csv_output}")


if __name__ == "__main__":
    main()
