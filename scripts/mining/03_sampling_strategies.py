#!/usr/bin/env python3
"""Submission sampling strategies for Terminal-Bench trajectory mining."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "raw" / "leaderboard_submissions_current.json"


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


def select_evenly_spaced(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if count <= 0 or not items:
        return []
    if count >= len(items):
        return list(items)
    if count == 1:
        return [items[len(items) // 2]]

    selected: list[dict[str, Any]] = []
    last_index = len(items) - 1
    used_indices: set[int] = set()
    for step in range(count):
        index = round(step * last_index / (count - 1))
        while index in used_indices and index < last_index:
            index += 1
        while index in used_indices and index > 0:
            index -= 1
        used_indices.add(index)
        selected.append(items[index])
    return selected


def scaffold_name(submission: dict[str, Any]) -> str:
    return str(submission.get("scaffold", ""))


def tier_candidates_by_anchor(
    tier_items: list[dict[str, Any]],
    anchor_item: dict[str, Any],
) -> list[dict[str, Any]]:
    tier_positions = {id(item): index for index, item in enumerate(tier_items)}
    anchor_position = tier_positions.get(id(anchor_item), len(tier_items) // 2)

    return sorted(
        tier_items,
        key=lambda item: abs(tier_positions[id(item)] - anchor_position),
    )


def enforce_scaffold_cap_for_balanced_sample(
    selected_by_tier: list[list[dict[str, Any]]],
    tier_items: list[list[dict[str, Any]]],
    max_per_scaffold: int = 3,
) -> list[dict[str, Any]]:
    if max_per_scaffold <= 0:
        return [item for tier in selected_by_tier for item in tier]

    result_by_tier: list[list[dict[str, Any] | None]] = [
        [None for _ in tier_selection] for tier_selection in selected_by_tier
    ]
    scaffold_counts: dict[str, int] = {}
    used_ids: set[int] = set()
    tier_order = sorted(
        range(len(tier_items)),
        key=lambda index: (
            len({scaffold_name(item) for item in tier_items[index]}),
            -index,
        ),
    )

    for tier_index in tier_order:
        tier = tier_items[tier_index]
        for slot_index, anchor in enumerate(selected_by_tier[tier_index]):
            for candidate in tier_candidates_by_anchor(tier, anchor):
                candidate_id = id(candidate)
                candidate_scaffold = scaffold_name(candidate)
                if candidate_id in used_ids:
                    continue
                if scaffold_counts.get(candidate_scaffold, 0) >= max_per_scaffold:
                    continue

                result_by_tier[tier_index][slot_index] = candidate
                used_ids.add(candidate_id)
                scaffold_counts[candidate_scaffold] = (
                    scaffold_counts.get(candidate_scaffold, 0) + 1
                )
                break

    # If the cap is mathematically impossible inside the requested tiers, keep
    # the sample size stable by filling any remaining slots from the same tier.
    for tier_index, tier_selection in enumerate(result_by_tier):
        for slot_index, selected in enumerate(tier_selection):
            if selected is not None:
                continue
            anchor = selected_by_tier[tier_index][slot_index]
            for candidate in tier_candidates_by_anchor(tier_items[tier_index], anchor):
                if id(candidate) in used_ids:
                    continue
                tier_selection[slot_index] = candidate
                used_ids.add(id(candidate))
                break

    def flattened() -> list[dict[str, Any]]:
        return [
            item
            for tier_selection in result_by_tier
            for item in tier_selection
            if item is not None
        ]

    def counts_for(items: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            counts[scaffold_name(item)] = counts.get(scaffold_name(item), 0) + 1
        return counts

    def excess_for(counts: dict[str, int]) -> int:
        return sum(max(0, count - max_per_scaffold) for count in counts.values())

    def result_signature() -> tuple[int, ...]:
        return tuple(id(item) for item in flattened())

    seen_signatures = {result_signature()}
    max_iterations = max(1, sum(len(tier) for tier in result_by_tier) * 10)
    for _ in range(max_iterations):
        current_items = flattened()
        current_counts = counts_for(current_items)
        current_excess = excess_for(current_counts)
        if current_excess == 0:
            break

        selected_ids = {id(item) for item in current_items}
        best_swap: tuple[int, int, dict[str, Any]] | None = None
        best_key: tuple[int, int, int] | None = None

        for tier_index, tier_selection in enumerate(result_by_tier):
            tier_positions = {
                id(item): index for index, item in enumerate(tier_items[tier_index])
            }
            for slot_index, current in enumerate(tier_selection):
                if current is None:
                    continue
                if current_counts.get(scaffold_name(current), 0) <= max_per_scaffold:
                    continue

                anchor = selected_by_tier[tier_index][slot_index]
                anchor_position = tier_positions.get(id(anchor), len(tier_items[tier_index]) // 2)
                for candidate in tier_candidates_by_anchor(tier_items[tier_index], anchor):
                    candidate_id = id(candidate)
                    if candidate_id in selected_ids and candidate_id != id(current):
                        continue
                    if scaffold_name(candidate) == scaffold_name(current):
                        continue

                    new_counts = dict(current_counts)
                    new_counts[scaffold_name(current)] -= 1
                    new_counts[scaffold_name(candidate)] = (
                        new_counts.get(scaffold_name(candidate), 0) + 1
                    )
                    new_excess = excess_for(new_counts)
                    distance = abs(tier_positions.get(candidate_id, anchor_position) - anchor_position)
                    max_count_after = max(new_counts.values()) if new_counts else 0
                    key = (new_excess, max_count_after, distance)

                    original = result_by_tier[tier_index][slot_index]
                    result_by_tier[tier_index][slot_index] = candidate
                    signature = result_signature()
                    result_by_tier[tier_index][slot_index] = original
                    if signature in seen_signatures:
                        continue

                    if best_key is None or key < best_key:
                        best_key = key
                        best_swap = (tier_index, slot_index, candidate)

        if best_swap is None or best_key is None or best_key[0] > current_excess:
            break

        tier_index, slot_index, candidate = best_swap
        result_by_tier[tier_index][slot_index] = candidate
        seen_signatures.add(result_signature())

    return [
        item
        for tier_selection in result_by_tier
        for item in tier_selection
        if item is not None
    ]


def sample_submissions(
    n: int,
    strategy: str,
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
        return list(reversed(scored)) if strategy == "top" else scored

    if strategy == "top":
        return list(reversed(scored))[:n]
    if strategy == "balanced":
        low = scored[: len(scored) // 3]
        mid = scored[len(scored) // 3 : 2 * len(scored) // 3]
        high = scored[2 * len(scored) // 3 :]
        base = n // 3
        remainder = n % 3
        counts = [base, base, base]
        for index in range(remainder):
            counts[index] += 1
        tiers = [high, mid, low]
        selected_by_tier = [
            select_evenly_spaced(tier, count)
            for tier, count in zip(tiers, counts)
        ]
        return enforce_scaffold_cap_for_balanced_sample(
            selected_by_tier,
            tiers,
            max_per_scaffold=3,
        )

    raise ValueError(f"unknown sampling strategy: {strategy}")
