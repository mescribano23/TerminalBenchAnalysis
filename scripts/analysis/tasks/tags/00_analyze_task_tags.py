#!/usr/bin/env python3
"""Summarize Terminal-Bench task tags.

Outputs:
- data/processed_live/task_mining/tags/task_tag_counts.csv
- data/processed_live/task_mining/tags/tag_groups.csv
- data/processed_live/task_mining/tags/tag_summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


def find_repo_root(start: Path) -> Path:
    for path in (start, *start.parents):
        if (path / "data").exists() and (path / "reports").exists() and (path / "scripts").exists():
            return path
    raise ValueError(f"Could not find repository root from {start}")


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = find_repo_root(SCRIPT_DIR)
DATA_DIR = REPO_ROOT / "data"
DATA_PROCESSED_LIVE_DIR = DATA_DIR / "processed_live"

TASKS_DEFAULT = DATA_DIR / "raw" / "terminal_bench_2_tasks_current.json"
OUT_DEFAULT = DATA_PROCESSED_LIVE_DIR / "task_mining" / "tags"


TAG_GROUP_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "Software engineering, build, and debugging",
        (
            "coding",
            "software-engineering",
            "debugging",
            "dependency",
            "compilation",
            "compiler",
            "build",
            "c-programming",
            "cpp",
            "python-extension",
            "python-migration",
            "legacy-modernization",
            "legacy-software",
            "performance-optimization",
            "software-installation",
            "troubleshooting",
            "memory-management",
            "concurrency",
            "async",
            "bash",
            "terminal",
            "git",
            "version-control",
        ),
    ),
    (
        "Systems, administration, and infrastructure",
        (
            "system",
            "sys-admin",
            "virtualization",
            "qemu",
            "vnc",
            "windows",
            "retro-computing",
            "email-server",
            "debian",
            "web-server",
            "mailing-list",
        ),
    ),
    (
        "Security, privacy, and recovery",
        (
            "security",
            "code-vulnerability",
            "common-weakness-enumeration",
            "decrypt",
            "encryption",
            "recovery",
        ),
    ),
    (
        "Data processing, querying, and documents",
        (
            "data-processing",
            "file-operations",
            "database",
            "etl",
            "schema-mapping",
            "conflict-resolution",
            "pandas",
            "parquet",
            "sql-query",
            "sparql-query",
            "query-optimization",
            "knowledge-graph",
            "information-retrieval",
            "retrieval",
            "api",
            "log-analysis",
            "ocr",
            "document-processing",
            "latex",
            "large-scale-text-manipulation",
            "text-editing",
            "vim",
            "regex",
            "string-parsing",
            "report-generation",
            "financial",
        ),
    ),
    (
        "Machine learning and data science",
        (
            "machine-learning",
            "data-science",
            "statistics",
            "stats",
            "bayesian",
            "mcmc",
            "stan",
            "rstan",
            "pystan",
            "mteb",
            "pytorch",
            "huggingface",
            "caffe",
            "cnn",
            "datasets",
            "tokenization",
            "batching",
            "inference",
            "data",
            "fitting",
            "gaussian-process",
        ),
    ),
    (
        "Scientific computing and simulation",
        (
            "scientific-computing",
            "simulation",
            "physics",
            "biology",
            "cloning",
            "proteins",
            "histopathology",
            "climate-science",
            "mujoco",
            "research",
            "adaptive-rejection-sampling",
            "applied-statistics",
            "numerical-approximation",
        ),
    ),
    (
        "Optimization, constraints, and scheduling",
        (
            "optimization",
            "numerical-optimization",
            "combinatorial-optimization",
            "constraint",
            "constraint-satisfaction",
            "scheduling",
            "calendar",
            "ics-parsing",
            "temporal-reasoning",
        ),
    ),
    (
        "Media, graphics, and games",
        (
            "image-processing",
            "images",
            "video-processing",
            "graphics",
            "ray-tracing",
            "gaming",
            "pmars",
            "corewars",
        ),
    ),
    (
        "Web",
        (
            "web",
        ),
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, default=TASKS_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    return parser.parse_args()


def load_tasks(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        tasks = json.load(handle)
    if not isinstance(tasks, list):
        raise ValueError(f"{path} must contain a JSON list.")
    return [task for task in tasks if isinstance(task, dict)]


def normalized_tags(task: dict[str, Any]) -> list[str]:
    tags = task.get("tags") or []
    if not isinstance(tags, list):
        return []
    return sorted({str(tag).strip() for tag in tags if str(tag).strip()})


def tag_group(tag: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")
    for group, patterns in TAG_GROUP_RULES:
        if any(pattern in normalized for pattern in patterns):
            return group
    return "Other / singleton-specific"


def pct(part: int, total: int) -> float:
    return part / total if total else 0.0


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_task_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in tasks:
        tags = normalized_tags(task)
        rows.append(
            {
                "task_name": task.get("id", ""),
                "category": task.get("category", ""),
                "difficulty": task.get("difficulty", ""),
                "tag_count": len(tags),
                "tags": "|".join(tags),
            }
        )
    return sorted(rows, key=lambda row: str(row["task_name"]))


def counter_display(counter: Counter[str]) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common())


def build_frequency_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total_tasks = len(tasks)
    by_tag_categories: dict[str, Counter[str]] = defaultdict(Counter)
    by_tag_difficulties: dict[str, Counter[str]] = defaultdict(Counter)
    tag_tasks: dict[str, set[str]] = defaultdict(set)

    for task in tasks:
        task_name = str(task.get("id", ""))
        category = str(task.get("category", ""))
        difficulty = str(task.get("difficulty", ""))
        for tag in normalized_tags(task):
            by_tag_categories[tag][category] += 1
            by_tag_difficulties[tag][difficulty] += 1
            tag_tasks[tag].add(task_name)

    rows: list[dict[str, Any]] = []
    for tag, task_names in tag_tasks.items():
        category_counts = by_tag_categories[tag]
        dominant_category, dominant_count = category_counts.most_common(1)[0]
        rows.append(
            {
                "tag": tag,
                "n_tasks": len(task_names),
                "pct_tasks": round(pct(len(task_names), total_tasks), 4),
                "is_singleton": len(task_names) == 1,
                "dominant_category": dominant_category,
                "dominant_category_task_count": dominant_count,
                "categories": counter_display(category_counts),
                "difficulties": counter_display(by_tag_difficulties[tag]),
            }
        )

    return sorted(rows, key=lambda row: (-int(row["n_tasks"]), str(row["tag"])))


def build_group_rows(frequency_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "tag_group": tag_group(str(row["tag"])),
            "tag": row["tag"],
            "n_tasks": row["n_tasks"],
            "pct_tasks": row["pct_tasks"],
            "dominant_category": row["dominant_category"],
            "is_singleton": row["is_singleton"],
        }
        for row in frequency_rows
    ]
    return sorted(rows, key=lambda row: (str(row["tag_group"]), -int(row["n_tasks"]), str(row["tag"])))


def write_summary(path: Path, task_rows: list[dict[str, Any]], frequency_rows: list[dict[str, Any]]) -> None:
    tag_counts = [int(row["tag_count"]) for row in task_rows]
    summary = {
        "n_tasks": len(task_rows),
        "n_tasks_with_tags": sum(1 for count in tag_counts if count > 0),
        "n_tasks_without_tags": sum(1 for count in tag_counts if count == 0),
        "n_unique_tags": len(frequency_rows),
        "n_tag_assignments": sum(tag_counts),
        "mean_tags_per_task": round(mean(tag_counts), 4) if tag_counts else 0,
        "median_tags_per_task": median(tag_counts) if tag_counts else 0,
        "min_tags_per_task": min(tag_counts) if tag_counts else 0,
        "max_tags_per_task": max(tag_counts) if tag_counts else 0,
        "n_singleton_tags": sum(1 for row in frequency_rows if row["is_singleton"]),
        "n_reused_tags": sum(1 for row in frequency_rows if not row["is_singleton"]),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")


def main() -> None:
    args = parse_args()
    tasks = load_tasks(args.tasks)
    task_rows = build_task_rows(tasks)
    frequency_rows = build_frequency_rows(tasks)
    group_rows = build_group_rows(frequency_rows)

    write_csv(
        args.out / "task_tag_counts.csv",
        task_rows,
        ["task_name", "category", "difficulty", "tag_count", "tags"],
    )
    write_csv(
        args.out / "tag_groups.csv",
        group_rows,
        ["tag_group", "tag", "n_tasks", "pct_tasks", "dominant_category", "is_singleton"],
    )
    write_summary(args.out / "tag_summary.json", task_rows, frequency_rows)

    total_assignments = sum(int(row["tag_count"]) for row in task_rows)
    tagged_tasks = sum(1 for row in task_rows if int(row["tag_count"]) > 0)
    print(f"Tasks: {len(tasks)}")
    print(f"Tasks with tags: {tagged_tasks}")
    print(f"Tasks without tags: {len(tasks) - tagged_tasks}")
    print(f"Total tag assignments: {total_assignments}")
    print(f"Unique tags: {len(frequency_rows)}")
    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
