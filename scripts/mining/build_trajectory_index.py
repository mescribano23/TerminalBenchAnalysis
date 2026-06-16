#!/usr/bin/env python3
"""Trajectory index helpers for Terminal-Bench trajectory mining."""

from __future__ import annotations

import json
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

    def checkpoint(self, force: bool = False) -> None:
        if self.pending_updates == 0 and not force:
            return
        if force or (
            self.checkpoint_interval > 0
            and self.pending_updates >= self.checkpoint_interval
        ):
            write_trajectory_index(self.index_path, self.by_key)
            self.pending_updates = 0
