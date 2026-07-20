#!/usr/bin/env python3
"""Scrape Terminal-Bench task.toml metadata from GitHub.

Outputs:
- data/raw/terminal_bench_2_task_toml_metadata_current.json
- data/processed_live/task_mining/terminal_bench_2_task_toml_metadata_current.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
DEFAULT_JSON_OUTPUT = DATA_DIR / "raw" / "terminal_bench_2_task_toml_metadata_current.json"
DEFAULT_CSV_OUTPUT = (
    DATA_DIR / "processed_live" / "task_mining" / "terminal_bench_2_task_toml_metadata_current.csv"
)

DEFAULT_OWNER = "harbor-framework"
DEFAULT_REPO = "terminal-bench-2"
DEFAULT_REF = "main"
HEADERS = {
    "User-Agent": "TerminalBenchAnalysis/1.0",
    "Accept": "application/vnd.github+json",
}


def request_text(url: str, accept: str | None = None, retries: int = 3) -> str:
    headers = dict(HEADERS)
    if accept is not None:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Could not fetch {url}: {last_error}")


def github_tree(owner: str, repo: str, ref: str) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
    payload = json.loads(request_text(url))
    tree = payload.get("tree")
    if not isinstance(tree, list):
        raise RuntimeError(f"Unexpected GitHub tree response from {url}")
    if payload.get("truncated"):
        raise RuntimeError("GitHub tree response was truncated; use a narrower ref or a local checkout.")
    return [entry for entry in tree if isinstance(entry, dict)]


def raw_url(owner: str, repo: str, ref: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


def normalize_task_name(name: Any, fallback_slug: str) -> str:
    value = str(name or "").strip()
    if value.startswith("terminal-bench/"):
        return value.split("/", 1)[1]
    return value or fallback_slug


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None or value == "":
        return []
    return [str(value)]


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_task_toml(text: str, source_path: str, source_url: str) -> dict[str, Any]:
    parsed = tomllib.loads(text)
    task = parsed.get("task") if isinstance(parsed.get("task"), dict) else {}
    metadata = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else {}
    verifier = parsed.get("verifier") if isinstance(parsed.get("verifier"), dict) else {}
    agent = parsed.get("agent") if isinstance(parsed.get("agent"), dict) else {}
    environment = parsed.get("environment") if isinstance(parsed.get("environment"), dict) else {}

    task_slug = source_path.split("/", 1)[0]
    task_name = normalize_task_name(task.get("name"), task_slug)

    return {
        "task_name": task_name,
        "task_slug": task_slug,
        "terminal_bench_task_name": task.get("name", ""),
        "description": task.get("description", ""),
        "keywords": as_list(task.get("keywords")),
        "difficulty": metadata.get("difficulty", ""),
        "category": metadata.get("category", ""),
        "tags": as_list(metadata.get("tags")),
        "expert_time_estimate_min": as_float(metadata.get("expert_time_estimate_min")),
        "junior_time_estimate_min": as_float(metadata.get("junior_time_estimate_min")),
        "agent_timeout_sec": as_float(agent.get("timeout_sec")),
        "verifier_timeout_sec": as_float(verifier.get("timeout_sec")),
        "environment_build_timeout_sec": as_float(environment.get("build_timeout_sec")),
        "allow_internet": environment.get("allow_internet", ""),
        "cpus": environment.get("cpus", ""),
        "memory_mb": environment.get("memory_mb", ""),
        "storage_mb": environment.get("storage_mb", ""),
        "gpus": environment.get("gpus", ""),
        "docker_image": environment.get("docker_image", ""),
        "source_path": source_path,
        "source_url": source_url,
    }


def scrape_task_toml_metadata(owner: str, repo: str, ref: str) -> list[dict[str, Any]]:
    tree = github_tree(owner, repo, ref)
    task_toml_paths = sorted(
        entry["path"]
        for entry in tree
        if entry.get("type") == "blob" and str(entry.get("path", "")).endswith("/task.toml")
    )
    if not task_toml_paths:
        raise RuntimeError("No task.toml files found in repository tree.")

    rows: list[dict[str, Any]] = []
    for path in task_toml_paths:
        url = raw_url(owner, repo, ref, path)
        text = request_text(url, accept="text/plain")
        rows.append(parse_task_toml(text, path, url))
    return rows


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "task_name",
        "task_slug",
        "terminal_bench_task_name",
        "difficulty",
        "category",
        "tags",
        "keywords",
        "expert_time_estimate_min",
        "junior_time_estimate_min",
        "agent_timeout_sec",
        "verifier_timeout_sec",
        "environment_build_timeout_sec",
        "allow_internet",
        "cpus",
        "memory_mb",
        "storage_mb",
        "gpus",
        "docker_image",
        "source_path",
        "source_url",
        "description",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["tags"] = "|".join(row.get("tags", []))
            out["keywords"] = "|".join(row.get("keywords", []))
            writer.writerow(out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--ref", default=DEFAULT_REF)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = scrape_task_toml_metadata(args.owner, args.repo, args.ref)
    write_json(args.json_output, rows)
    write_csv(args.csv_output, rows)

    complete_estimates = sum(
        row.get("expert_time_estimate_min") is not None and row.get("junior_time_estimate_min") is not None
        for row in rows
    )
    print(f"Wrote {len(rows)} task.toml metadata rows")
    print(f"Rows with expert and junior estimates: {complete_estimates}")
    print(f"JSON: {args.json_output}")
    print(f"CSV: {args.csv_output}")


if __name__ == "__main__":
    main()
