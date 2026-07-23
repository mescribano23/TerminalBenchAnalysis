#!/usr/bin/env python3
"""Top-submission sampling helpers for Terminal-Bench trajectory mining."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT / "data" / "raw" / "terminal_bench_2_0" / "leaderboard_submissions.json"
)


def submission_score(submission: dict[str, Any]) -> float:
    tasks = submission.get("tasks") or []
    total_trials = sum(int(task.get("nTrials", 0) or 0) for task in tasks)
    if total_trials:
        total_successes = sum(int(task.get("successCount", 0) or 0) for task in tasks)
        return total_successes / total_trials

    rates = [
        float(task.get("avgResolutionRate", 0.0) or 0.0)
        for task in tasks
        if "avgResolutionRate" in task
    ]
    if rates:
        return sum(rates) / len(rates)
    return 0.0


def sample_submissions(
    n: int,
    submissions: list[dict[str, Any]] | None = None,
    leaderboard_path: Path = DEFAULT_OUTPUT_PATH,
) -> list[dict[str, Any]]:
    if n <= 0:
        return []
    if submissions is None:
        submissions = json.loads(leaderboard_path.read_text(encoding="utf-8"))

    eligible_submissions = [
        submission
        for submission in submissions
        if submission.get("has_trajectories", True) is not False
    ]
    scored = sorted(eligible_submissions, key=submission_score)
    if n >= len(scored):
        return list(reversed(scored))
    return list(reversed(scored))[:n]
