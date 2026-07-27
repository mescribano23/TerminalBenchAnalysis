#!/usr/bin/env python3
"""Trajectory index helpers for Terminal-Bench trajectory mining."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


IndexKey = tuple[str, str, str, str]


def load_existing_index(index_path: Path) -> list[dict[str, Any]]:
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    return []


def index_key(entry: dict[str, Any]) -> IndexKey:
    return (
        str(entry.get("scaffold", "")),
        str(entry.get("model", "")),
        str(entry.get("taskChecksum", "")),
        str(entry.get("trialId", "")),
    )


def write_trajectory_index(index_path: Path, index_by_key: dict[IndexKey, dict[str, Any]]) -> None:
    index_path.write_text(
        json.dumps(list(index_by_key.values()), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def safe_path_component(value: object) -> str:
    text = str(value).strip() or "unknown"
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip(" ._")
    return text[:160] or "unknown"


def looks_like_api_error(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    error_keys = {"error", "detail", "statusCode", "status_code"}
    if any(key in value for key in error_keys):
        return True
    return set(value) <= {"message", "code", "status"} and "message" in value


def trajectory_payload_status(value: Any) -> tuple[bool, str]:
    if looks_like_api_error(value):
        return False, "API error payload"
    if isinstance(value, list):
        if not value:
            return False, "empty JSON payload"
        if not all(isinstance(item, dict) for item in value):
            return False, "trajectory list must contain objects"
        return True, "valid"
    if not isinstance(value, dict) or not value:
        return False, "empty JSON payload"
    if "trajectory" in value:
        return trajectory_payload_status(value["trajectory"])
    steps = value.get("steps")
    if not isinstance(steps, list) or not steps:
        return False, "trajectory object has no non-empty steps list"
    if not all(isinstance(step, dict) for step in steps):
        return False, "trajectory steps must contain objects"
    return True, "valid"


def trajectory_file_status(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    if not path.is_file():
        return False, "not a file"
    try:
        if path.stat().st_size == 0:
            return False, "empty"
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"malformed: {exc}"
    return trajectory_payload_status(value)


class TrajectoryIndexWriter:
    def __init__(self, index_path: Path, checkpoint_interval: int = 250) -> None:
        self.index_path = index_path
        self.checkpoint_interval = checkpoint_interval
        self.pending_updates = 0
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        entries = load_existing_index(index_path)
        self.by_key = {index_key(entry): entry for entry in entries}

    def upsert(self, entry: dict[str, Any]) -> None:
        self.by_key[index_key(entry)] = entry
        self.pending_updates += 1

    def remove(self, entry: dict[str, Any]) -> None:
        key = index_key(entry)
        if key in self.by_key:
            del self.by_key[key]
            self.pending_updates += 1

    def prune_invalid_file_entries(self, repo_root: Path | None = None) -> int:
        removed = 0
        for key, entry in list(self.by_key.items()):
            raw_path = entry.get("filePath")
            if not raw_path:
                del self.by_key[key]
                removed += 1
                continue
            path = Path(str(raw_path))
            if not path.is_absolute() and repo_root is not None:
                path = repo_root / path
            is_valid, _ = trajectory_file_status(path)
            if not is_valid:
                del self.by_key[key]
                removed += 1
        if removed:
            self.pending_updates += removed
        return removed

    def checkpoint(self, force: bool = False) -> None:
        if self.pending_updates == 0 and not force:
            return
        if force or (
            self.checkpoint_interval > 0
            and self.pending_updates >= self.checkpoint_interval
        ):
            write_trajectory_index(self.index_path, self.by_key)
            self.pending_updates = 0
