#!/usr/bin/env python3
"""Scrape versioned Terminal-Bench task metadata from Hugging Face.

Outputs:
- data/raw/{benchmark}/hf_task_metadata.json
- data/processed_live/task_mining/{benchmark}_hf_task_metadata.csv
- data/processed_live/longitudinal/tb3_tb4_task_version_audit.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed_live"
TASK_MINING_DIR = PROCESSED_DIR / "task_mining"
LONGITUDINAL_DIR = PROCESSED_DIR / "longitudinal"

HF_DATASET = "harborframework/terminal-bench"
HF_API_BASE = "https://huggingface.co/api/datasets"
HF_RAW_BASE = "https://huggingface.co/datasets"
HEADERS = {
    "User-Agent": "TerminalBenchAnalysis/1.0",
}


@dataclass(frozen=True)
class BenchmarkSpec:
    benchmark: str
    version: str
    revision: str


DEFAULT_BENCHMARKS = (
    BenchmarkSpec(
        benchmark="terminal_bench_3_0",
        version="3.0",
        revision="d525857a0bcdef31b3054683b6e7274de3d567d8",
    ),
    BenchmarkSpec(
        benchmark="terminal_bench_4_0",
        version="4.0",
        revision="3b8d57a69a7d28b73238c7ce9ecc62c8c794bff9",
    ),
)


def request_bytes(url: str, retries: int = 3) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Could not fetch {url}: {last_error}")


def request_json(url: str) -> Any:
    return json.loads(request_bytes(url).decode("utf-8"))


def tree_url(revision: str, path: str, *, recursive: bool) -> str:
    dataset = urllib.parse.quote(HF_DATASET, safe="/")
    suffix = f"{HF_API_BASE}/{dataset}/tree/{revision}/{path.strip('/')}"
    if recursive:
        suffix += "?recursive=true"
    return suffix


def raw_url(revision: str, path: str) -> str:
    quoted_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    return f"{HF_RAW_BASE}/{HF_DATASET}/raw/{revision}/{quoted_path}"


def list_task_dirs(revision: str) -> list[str]:
    entries = request_json(tree_url(revision, "tasks", recursive=True))
    if not isinstance(entries, list):
        raise RuntimeError("Unexpected Hugging Face tree response for tasks.")
    return sorted({
        str(entry["path"]).split("/")[1]
        for entry in entries
        if isinstance(entry, dict)
        and str(entry.get("path", "")).startswith("tasks/")
        and len(str(entry.get("path", "")).split("/")) >= 2
    })


def list_task_tree(revision: str, task_name: str) -> list[dict[str, Any]]:
    entries = request_json(tree_url(revision, f"tasks/{task_name}", recursive=True))
    if not isinstance(entries, list):
        raise RuntimeError(f"Unexpected Hugging Face tree response for {task_name}.")
    return [entry for entry in entries if isinstance(entry, dict)]


def file_identity(entry: dict[str, Any]) -> dict[str, Any]:
    lfs = entry.get("lfs") if isinstance(entry.get("lfs"), dict) else {}
    return {
        "path": entry.get("path", ""),
        "type": entry.get("type", ""),
        "oid": entry.get("oid", ""),
        "size": entry.get("size", ""),
        "lfs_oid": lfs.get("oid", ""),
        "lfs_size": lfs.get("size", ""),
        "xet_hash": entry.get("xetHash", ""),
    }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


CANARY_RE = re.compile(r"^\s*<!--\s*harbor-canary GUID .*?-->\s*", flags=re.IGNORECASE)
TIMEOUT_RE = re.compile(
    r"\n?You have \d+(?:\.\d+)? seconds to complete this task\. "
    r"Do not cheat by using online solutions or hints specific to this task\.\s*$",
    flags=re.IGNORECASE,
)


def normalized_instruction(text: str) -> str:
    """Normalize release boilerplate out of task instructions for version audits."""
    text = CANARY_RE.sub("", text)
    text = TIMEOUT_RE.sub("", text)
    return text.strip()


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_text(payload)


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in {None, ""}:
        return []
    return [str(value)]


def as_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_task_name(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if text.startswith("terminal-bench/"):
        return text.rsplit("/", 1)[-1]
    return text or fallback


def parse_task_toml(text: str, task_slug: str) -> dict[str, Any]:
    parsed = tomllib.loads(text)
    task = parsed.get("task") if isinstance(parsed.get("task"), dict) else {}
    metadata = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else {}
    verifier = parsed.get("verifier") if isinstance(parsed.get("verifier"), dict) else {}
    agent = parsed.get("agent") if isinstance(parsed.get("agent"), dict) else {}
    environment = parsed.get("environment") if isinstance(parsed.get("environment"), dict) else {}

    expert_hours = as_float(metadata.get("expert_time_estimate_hours"))
    expert_minutes = as_float(metadata.get("expert_time_estimate_min"))
    if expert_minutes is None and expert_hours is not None:
        expert_minutes = expert_hours * 60.0

    return {
        "task_name": normalize_task_name(task.get("name"), task_slug),
        "terminal_bench_task_name": task.get("name", ""),
        "description": task.get("description", ""),
        "authors": json.dumps(task.get("authors", []), ensure_ascii=False),
        "category": metadata.get("category", ""),
        "subcategory": metadata.get("subcategory", ""),
        "difficulty": metadata.get("difficulty") or "unknown",
        "tags": as_list(metadata.get("tags")),
        "expert_time_estimate_min": expert_minutes,
        "expert_time_estimate_hours": expert_hours,
        "junior_time_estimate_min": as_float(metadata.get("junior_time_estimate_min")),
        "agent_timeout_sec": as_float(agent.get("timeout_sec")),
        "verifier_timeout_sec": as_float(verifier.get("timeout_sec")),
        "verifier_environment_mode": verifier.get("environment_mode", ""),
        "environment_build_timeout_sec": as_float(environment.get("build_timeout_sec")),
        "allow_internet": environment.get("allow_internet", ""),
        "cpus": environment.get("cpus", ""),
        "memory_mb": environment.get("memory_mb", ""),
        "storage_mb": environment.get("storage_mb", ""),
        "gpus": environment.get("gpus", ""),
        "docker_image": environment.get("docker_image", ""),
        "artifacts": as_list(parsed.get("artifacts")),
    }


def maybe_fetch_text(revision: str, path: str) -> str:
    try:
        return request_bytes(raw_url(revision, path)).decode("utf-8")
    except RuntimeError:
        return ""


def scrape_benchmark(spec: BenchmarkSpec) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task_slug in list_task_dirs(spec.revision):
        tree = list_task_tree(spec.revision, task_slug)
        file_entries = [
            file_identity(entry)
            for entry in tree
            if entry.get("type") == "file"
        ]
        manifest_hash = sha256_json(sorted(file_entries, key=lambda item: str(item["path"])))

        task_toml_path = f"tasks/{task_slug}/task.toml"
        instruction_path = f"tasks/{task_slug}/instruction.md"
        readme_path = f"tasks/{task_slug}/README.md"
        task_toml = maybe_fetch_text(spec.revision, task_toml_path)
        instruction = maybe_fetch_text(spec.revision, instruction_path)
        readme = maybe_fetch_text(spec.revision, readme_path)
        parsed = parse_task_toml(task_toml, task_slug) if task_toml else {
            "task_name": task_slug,
            "terminal_bench_task_name": "",
            "description": "",
            "authors": "[]",
            "category": "",
            "subcategory": "",
            "difficulty": "",
            "tags": [],
            "expert_time_estimate_min": None,
            "expert_time_estimate_hours": None,
            "junior_time_estimate_min": None,
            "agent_timeout_sec": None,
            "verifier_timeout_sec": None,
            "verifier_environment_mode": "",
            "environment_build_timeout_sec": None,
            "allow_internet": "",
            "cpus": "",
            "memory_mb": "",
            "storage_mb": "",
            "gpus": "",
            "docker_image": "",
            "artifacts": [],
        }
        row = {
            "benchmark": spec.benchmark,
            "benchmark_version": spec.version,
            "hf_dataset": HF_DATASET,
            "hf_revision": spec.revision,
            "task_slug": task_slug,
            **parsed,
            "instruction_sha256": sha256_text(instruction) if instruction else "",
            "instruction_normalized_sha256": (
                sha256_text(normalized_instruction(instruction)) if instruction else ""
            ),
            "instruction_chars": len(instruction),
            "instruction_normalized_chars": len(normalized_instruction(instruction)) if instruction else 0,
            "task_toml_sha256": sha256_text(task_toml) if task_toml else "",
            "task_toml_chars": len(task_toml),
            "readme_sha256": sha256_text(readme) if readme else "",
            "readme_chars": len(readme),
            "package_manifest_sha256": manifest_hash,
            "package_file_count": len(file_entries),
            "package_total_listed_bytes": sum(int(item.get("size") or 0) for item in file_entries),
            "task_toml_source_url": raw_url(spec.revision, task_toml_path),
            "instruction_source_url": raw_url(spec.revision, instruction_path),
            "readme_source_url": raw_url(spec.revision, readme_path),
            "task_tree_url": f"{HF_RAW_BASE}/{HF_DATASET}/tree/{spec.revision}/tasks/{task_slug}",
            "package_manifest": file_entries,
        }
        rows.append(row)
    return rows


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def csv_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["tags"] = "|".join(row.get("tags", []))
    out["artifacts"] = "|".join(row.get("artifacts", []))
    out.pop("package_manifest", None)
    return out


def write_task_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "benchmark",
        "benchmark_version",
        "task_name",
        "task_slug",
        "terminal_bench_task_name",
        "category",
        "subcategory",
        "difficulty",
        "tags",
        "expert_time_estimate_min",
        "expert_time_estimate_hours",
        "junior_time_estimate_min",
        "agent_timeout_sec",
        "verifier_timeout_sec",
        "verifier_environment_mode",
        "environment_build_timeout_sec",
        "allow_internet",
        "cpus",
        "memory_mb",
        "storage_mb",
        "gpus",
        "docker_image",
        "artifacts",
        "instruction_sha256",
        "instruction_normalized_sha256",
        "instruction_chars",
        "instruction_normalized_chars",
        "task_toml_sha256",
        "task_toml_chars",
        "readme_sha256",
        "readme_chars",
        "package_manifest_sha256",
        "package_file_count",
        "package_total_listed_bytes",
        "hf_dataset",
        "hf_revision",
        "task_toml_source_url",
        "instruction_source_url",
        "readme_source_url",
        "task_tree_url",
        "description",
        "authors",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(csv_row(row))


def join_values(values: list[Any]) -> str:
    unique = sorted({str(value) for value in values if str(value)})
    return "|".join(unique)


def build_tb3_tb4_audit(rows_by_benchmark: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    tb3 = {row["task_name"]: row for row in rows_by_benchmark.get("terminal_bench_3_0", [])}
    tb4 = {row["task_name"]: row for row in rows_by_benchmark.get("terminal_bench_4_0", [])}
    task_names = sorted(set(tb3) | set(tb4))
    rows: list[dict[str, Any]] = []
    for task_name in task_names:
        row3 = tb3.get(task_name)
        row4 = tb4.get(task_name)
        in_tb3 = row3 is not None
        in_tb4 = row4 is not None
        instruction_same = (
            in_tb3
            and in_tb4
            and row3.get("instruction_sha256")
            and row3.get("instruction_sha256") == row4.get("instruction_sha256")
        )
        instruction_normalized_same = (
            in_tb3
            and in_tb4
            and row3.get("instruction_normalized_sha256")
            and row3.get("instruction_normalized_sha256") == row4.get("instruction_normalized_sha256")
        )
        task_toml_same = (
            in_tb3
            and in_tb4
            and row3.get("task_toml_sha256")
            and row3.get("task_toml_sha256") == row4.get("task_toml_sha256")
        )
        package_same = (
            in_tb3
            and in_tb4
            and row3.get("package_manifest_sha256")
            and row3.get("package_manifest_sha256") == row4.get("package_manifest_sha256")
        )
        if not in_tb3:
            classification = "Added in TB4.0"
        elif not in_tb4:
            classification = "Only in TB3.0"
        elif package_same:
            classification = "Package identical"
        elif instruction_normalized_same:
            classification = "Only release boilerplate changed"
        elif instruction_same:
            classification = "Instruction identical; package changed"
        else:
            classification = "Instruction changed"

        rows.append(
            {
                "task_name": task_name,
                "in_tb3": int(in_tb3),
                "in_tb4": int(in_tb4),
                "classification": classification,
                "instruction_identical": int(bool(instruction_same)),
                "instruction_normalized_identical": int(bool(instruction_normalized_same)),
                "task_toml_identical": int(bool(task_toml_same)),
                "package_manifest_identical": int(bool(package_same)),
                "tb3_instruction_sha256": row3.get("instruction_sha256", "") if row3 else "",
                "tb4_instruction_sha256": row4.get("instruction_sha256", "") if row4 else "",
                "tb3_instruction_normalized_sha256": row3.get("instruction_normalized_sha256", "") if row3 else "",
                "tb4_instruction_normalized_sha256": row4.get("instruction_normalized_sha256", "") if row4 else "",
                "tb3_task_toml_sha256": row3.get("task_toml_sha256", "") if row3 else "",
                "tb4_task_toml_sha256": row4.get("task_toml_sha256", "") if row4 else "",
                "tb3_package_manifest_sha256": row3.get("package_manifest_sha256", "") if row3 else "",
                "tb4_package_manifest_sha256": row4.get("package_manifest_sha256", "") if row4 else "",
                "tb3_category": row3.get("category", "") if row3 else "",
                "tb4_category": row4.get("category", "") if row4 else "",
                "tb3_subcategory": row3.get("subcategory", "") if row3 else "",
                "tb4_subcategory": row4.get("subcategory", "") if row4 else "",
                "tb3_agent_timeout_sec": row3.get("agent_timeout_sec", "") if row3 else "",
                "tb4_agent_timeout_sec": row4.get("agent_timeout_sec", "") if row4 else "",
                "tb3_instruction_chars": row3.get("instruction_chars", "") if row3 else "",
                "tb4_instruction_chars": row4.get("instruction_chars", "") if row4 else "",
                "tb3_instruction_normalized_chars": row3.get("instruction_normalized_chars", "") if row3 else "",
                "tb4_instruction_normalized_chars": row4.get("instruction_normalized_chars", "") if row4 else "",
                "tb3_package_file_count": row3.get("package_file_count", "") if row3 else "",
                "tb4_package_file_count": row4.get("package_file_count", "") if row4 else "",
                "notes": (
                    "Exact instruction.md SHA-256 and package manifest SHA-256 match."
                    if package_same
                    else (
                        "Instruction differs only in release boilerplate removed by normalization."
                        if instruction_normalized_same
                        else (
                        "Instruction text matches exactly, but at least one task package file identity differs."
                        if instruction_same
                        else (
                            "Task exists in both versions but instruction.md differs."
                            if in_tb3 and in_tb4
                            else "Task is not present in both versions."
                        )
                        )
                    )
                ),
            }
        )
    return rows


def write_audit_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "task_name",
        "in_tb3",
        "in_tb4",
        "classification",
        "instruction_identical",
        "instruction_normalized_identical",
        "task_toml_identical",
        "package_manifest_identical",
        "tb3_instruction_sha256",
        "tb4_instruction_sha256",
        "tb3_instruction_normalized_sha256",
        "tb4_instruction_normalized_sha256",
        "tb3_task_toml_sha256",
        "tb4_task_toml_sha256",
        "tb3_package_manifest_sha256",
        "tb4_package_manifest_sha256",
        "tb3_category",
        "tb4_category",
        "tb3_subcategory",
        "tb4_subcategory",
        "tb3_agent_timeout_sec",
        "tb4_agent_timeout_sec",
        "tb3_instruction_chars",
        "tb4_instruction_chars",
        "tb3_instruction_normalized_chars",
        "tb4_instruction_normalized_chars",
        "tb3_package_file_count",
        "tb4_package_file_count",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--task-mining-dir", type=Path, default=TASK_MINING_DIR)
    parser.add_argument("--longitudinal-dir", type=Path, default=LONGITUDINAL_DIR)
    parser.add_argument(
        "--audit-csv",
        type=Path,
        default=LONGITUDINAL_DIR / "tb3_tb4_task_version_audit.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows_by_benchmark: dict[str, list[dict[str, Any]]] = {}
    for spec in DEFAULT_BENCHMARKS:
        rows = scrape_benchmark(spec)
        rows_by_benchmark[spec.benchmark] = rows
        write_json(args.raw_dir / spec.benchmark / "hf_task_metadata.json", rows)
        write_task_csv(args.task_mining_dir / f"{spec.benchmark}_hf_task_metadata.csv", rows)
        print(f"{spec.benchmark}: scraped {len(rows)} tasks from {spec.revision}")

    combined_rows = [row for rows in rows_by_benchmark.values() for row in rows]
    write_task_csv(args.task_mining_dir / "terminal_bench_3_4_hf_task_metadata.csv", combined_rows)
    audit_rows = build_tb3_tb4_audit(rows_by_benchmark)
    write_audit_csv(args.audit_csv, audit_rows)

    counts: dict[str, int] = {}
    for row in audit_rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    print("TB3/TB4 task-version audit:")
    for label, count in sorted(counts.items()):
        print(f"  {label}: {count}")
    print(f"Wrote {args.audit_csv}")


if __name__ == "__main__":
    main()
