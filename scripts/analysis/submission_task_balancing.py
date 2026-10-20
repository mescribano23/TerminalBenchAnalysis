"""Shared submission/task balancing helpers."""

from __future__ import annotations

import pandas as pd

from scripts.analysis.source_submission_identity import SOURCE_SUBMISSION_ID, ensure_source_submission_id


EFFECTIVE_SUBMISSION_ID = "effective_submission_id"
CONFIG_ID = "config_id"

CONFIG_COLUMNS = ["scaffold", "model_dir"]
EFFECTIVE_SUBMISSION_COMPONENTS = [
    "benchmark",
    "source_submission_url",
    "scaffold",
    "model_dir",
    "agent_version",
    "leaderboard_model",
    "leaderboard_provider",
    "leaderboard_date",
]


def _clean_component(value: object) -> str:
    if pd.isna(value):
        return "unknown"
    text = str(value).strip()
    return text if text else "unknown"


def ensure_config_id(df: pd.DataFrame) -> pd.DataFrame:
    """Return a frame with the canonical scaffold/model configuration identifier."""
    out = df.copy()
    missing = [column for column in CONFIG_COLUMNS if column not in out.columns]
    if missing:
        raise ValueError(f"Cannot build {CONFIG_ID}; missing columns: {', '.join(missing)}")
    out[CONFIG_ID] = out[CONFIG_COLUMNS].apply(lambda column: column.map(_clean_component)).agg("|".join, axis=1)
    return out


def build_effective_submission_id(row: pd.Series | dict[str, object]) -> str:
    """Build a configuration/version metadata fingerprint, never the balancing unit."""
    return "|".join(_clean_component(row.get(column, "unknown")) for column in EFFECTIVE_SUBMISSION_COMPONENTS)


def ensure_effective_submission_id(df: pd.DataFrame) -> pd.DataFrame:
    """Return a frame with the canonical effective submission id populated."""
    out = df.copy()
    if "source_submission_url" not in out.columns:
        out["source_submission_url"] = "unknown"
    missing = [column for column in EFFECTIVE_SUBMISSION_COMPONENTS if column not in out.columns]
    if missing:
        raise ValueError(
            f"Cannot build {EFFECTIVE_SUBMISSION_ID}; missing columns: {', '.join(missing)}"
        )
    for column in EFFECTIVE_SUBMISSION_COMPONENTS:
        out[column] = out[column].map(_clean_component)
    out = ensure_config_id(out)
    out[EFFECTIVE_SUBMISSION_ID] = out[EFFECTIVE_SUBMISSION_COMPONENTS].agg("|".join, axis=1)
    return out
