#!/usr/bin/env python3
"""Scrape Harbor Hub task-page prose for Terminal-Bench 3.0/4.0 tasks.

Hugging Face task.toml metadata contains structured fields, but Harbor Hub task
pages expose richer narrative sections such as "Difficulty explanation". This
script scrapes those sections and writes both a standalone task-page table and
an enriched TB3/TB4 metadata table.

Outputs:
- data/raw/harbor_task_pages/terminal_bench_task_pages.json
- data/processed_live/task_mining/terminal_bench_3_4_harbor_task_pages.csv
- data/processed_live/task_mining/terminal_bench_3_4_task_metadata_enriched.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed_live"
TASK_MINING_DIR = PROCESSED_DIR / "task_mining"

HF_METADATA_DEFAULT = TASK_MINING_DIR / "terminal_bench_3_4_hf_task_metadata.csv"
RAW_OUT_DEFAULT = RAW_DIR / "harbor_task_pages" / "terminal_bench_task_pages.json"
PAGES_CSV_DEFAULT = TASK_MINING_DIR / "terminal_bench_3_4_harbor_task_pages.csv"
ENRICHED_CSV_DEFAULT = TASK_MINING_DIR / "terminal_bench_3_4_task_metadata_enriched.csv"
HARBOR_TASK_BASE = "https://hub.harborframework.com/tasks/terminal-bench"
HEADERS = {"User-Agent": "TerminalBenchAnalysis/1.0"}
SECTION_MAP = {
    "Task Metadata": "harbor_task_metadata_text",
    "Change Log": "harbor_change_log",
    "Difficulty explanation": "difficulty_explanation",
    "Solution explanation": "solution_explanation",
    "Verification explanation": "verification_explanation",
    "Relevant experience": "relevant_experience",
}
PAGE_FIELDS = [
    "task_name",
    "harbor_task_url",
    "http_status",
    "page_title",
    "harbor_task_metadata_text",
    "harbor_change_log",
    "difficulty_explanation",
    "solution_explanation",
    "verification_explanation",
    "relevant_experience",
    "scrape_error",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-csv", type=Path, default=HF_METADATA_DEFAULT)
    parser.add_argument("--raw-out", type=Path, default=RAW_OUT_DEFAULT)
    parser.add_argument("--pages-csv", type=Path, default=PAGES_CSV_DEFAULT)
    parser.add_argument("--enriched-csv", type=Path, default=ENRICHED_CSV_DEFAULT)
    parser.add_argument("--sleep-sec", type=float, default=0.1)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def task_url(task_name: str) -> str:
    return f"{HARBOR_TASK_BASE}/{urllib.parse.quote(task_name.strip(), safe='')}"


def request_text(url: str, retries: int = 3) -> tuple[int, str]:
    request = urllib.request.Request(url, headers=HEADERS)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return int(response.status), response.read().decode("utf-8", errors="replace")
        except (TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Could not fetch {url}: {last_error}")


def normalize_ws(text: str) -> str:
    return " ".join(text.split()).strip()


def section_text(soup: BeautifulSoup, heading: str) -> str:
    header = soup.find(lambda tag: tag.name == "h2" and tag.get_text(" ", strip=True) == heading)
    if header is None:
        return ""
    parts: list[str] = []
    sibling = header.find_next_sibling()
    while sibling is not None and sibling.name != "h2":
        text = sibling.get_text(" ", strip=True)
        if text:
            parts.append(text)
        sibling = sibling.find_next_sibling()
    return normalize_ws("\n".join(parts))


def page_title(soup: BeautifulSoup) -> str:
    headings = [
        heading.get_text(" ", strip=True)
        for heading in soup.find_all("h1")
        if heading.get_text(" ", strip=True)
    ]
    for heading in headings:
        if " / " not in heading:
            return heading
    return headings[-1] if headings else ""


def parse_task_page(task_name: str, status: int, html: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    row: dict[str, Any] = {
        "task_name": task_name,
        "harbor_task_url": url,
        "http_status": status,
        "page_title": page_title(soup),
        "scrape_error": "",
    }
    for heading, field in SECTION_MAP.items():
        row[field] = section_text(soup, heading)
    return row


def scrape_task(task_name: str) -> dict[str, Any]:
    url = task_url(task_name)
    try:
        status, html = request_text(url)
        return parse_task_page(task_name, status, html, url)
    except Exception as exc:
        return {
            "task_name": task_name,
            "harbor_task_url": url,
            "http_status": "",
            "page_title": "",
            "harbor_task_metadata_text": "",
            "harbor_change_log": "",
            "difficulty_explanation": "",
            "solution_explanation": "",
            "verification_explanation": "",
            "relevant_experience": "",
            "scrape_error": str(exc),
        }


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAGE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_enriched_metadata(metadata_path: Path, pages_csv: Path, enriched_csv: Path) -> None:
    metadata = pd.read_csv(metadata_path, low_memory=False)
    pages = pd.read_csv(pages_csv, low_memory=False)
    keep = [
        "task_name",
        "harbor_task_url",
        "difficulty_explanation",
        "solution_explanation",
        "verification_explanation",
        "relevant_experience",
        "harbor_change_log",
    ]
    pages = pages[keep].drop_duplicates("task_name")
    enriched = metadata.merge(pages, on="task_name", how="left", validate="many_to_one")
    enriched_csv.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(enriched_csv, index=False)


def main() -> None:
    args = parse_args()
    metadata = pd.read_csv(args.metadata_csv, usecols=["task_name"])
    task_names = sorted(metadata["task_name"].dropna().astype(str).unique())
    if args.limit is not None:
        task_names = task_names[: args.limit]

    rows: list[dict[str, Any]] = []
    for index, task_name in enumerate(task_names, start=1):
        row = scrape_task(task_name)
        rows.append(row)
        has_difficulty = bool(row.get("difficulty_explanation"))
        status = row.get("http_status") or "ERR"
        print(f"[{index}/{len(task_names)}] {task_name}: {status}, difficulty={int(has_difficulty)}")
        if args.sleep_sec > 0:
            time.sleep(args.sleep_sec)

    write_json(args.raw_out, rows)
    write_csv(args.pages_csv, rows)
    write_enriched_metadata(args.metadata_csv, args.pages_csv, args.enriched_csv)

    scraped = sum(1 for row in rows if row.get("difficulty_explanation"))
    errors = sum(1 for row in rows if row.get("scrape_error"))
    print(f"Difficulty explanations scraped: {scraped}/{len(rows)}")
    print(f"Scrape errors: {errors}")
    print(f"Wrote {args.raw_out}")
    print(f"Wrote {args.pages_csv}")
    print(f"Wrote {args.enriched_csv}")


if __name__ == "__main__":
    main()
