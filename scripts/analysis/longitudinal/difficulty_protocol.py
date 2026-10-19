"""The single supported, neutralized three-LLM difficulty-labeling protocol."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

from scripts.analysis.longitudinal.llm_consensus import LabelerSpec


DIFFICULTY_LABELERS = (
    LabelerSpec("openai", "gpt-4o-mini"),
    LabelerSpec("anthropic", "claude-haiku-4-5-20251001"),
    LabelerSpec("ollama", "qwen2.5:7b-instruct"),
)
DIFFICULTY_PANEL = ";".join(spec.id for spec in DIFFICULTY_LABELERS)
DIFFICULTY_NEUTRALIZER = DIFFICULTY_LABELERS[0]


def require_difficulty_protocol(labels: pd.DataFrame, path: Path) -> None:
    """Reject unneutralized, mixed-panel, or incomplete-vote results."""
    required = {
        "llm_model", "neutralization_model", "consensus_votes_json",
        "consensus_vote_count", "label_source", "llm_difficulty_label",
    }
    missing = sorted(required.difference(labels.columns))
    if missing:
        raise ValueError(f"{path} lacks difficulty protocol provenance: {', '.join(missing)}")
    valid = (
        labels["llm_model"].eq(DIFFICULTY_PANEL)
        & labels["neutralization_model"].eq(DIFFICULTY_NEUTRALIZER.id)
        & labels["label_source"].eq("consensus")
        & pd.to_numeric(labels["consensus_vote_count"], errors="coerce").eq(3)
    )
    if not valid.all():
        raise ValueError(f"{path} must use the fixed three-LLM panel after GPT-4o mini neutralization.")
    expected = {spec.id for spec in DIFFICULTY_LABELERS}
    for index, row in labels.iterrows():
        try:
            votes = json.loads(row["consensus_votes_json"])
            identities = {f"{vote['provider']}:{vote['model']}" for vote in votes}
            if len(votes) != 3 or identities != expected:
                raise ValueError("expected one vote from each configured labeler")
            if any(vote.get("error") or vote.get("label") not in {"easy", "medium", "hard"} for vote in votes):
                raise ValueError("invalid or missing vote")
            counts = Counter(vote["label"] for vote in votes)
            label, count = counts.most_common(1)[0]
            if count < 2 or label != row["llm_difficulty_label"]:
                raise ValueError("saved label does not match the three-model consensus")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path} has invalid difficulty votes at row {index}: {exc}") from exc
