"""Shared submission/task balancing helpers."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


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
    """Build the canonical effective submission identifier used for balancing.

    Terminal-Bench 2.0 trajectory metadata does not expose a stable numeric
    submission id, so analyses use this metadata-derived submission instance.
    Including model_dir prevents multi-model leaderboard rows from collapsing
    distinct model/scaffold configurations into one balancing unit.
    """
    return "|".join(_clean_component(row.get(column, "unknown")) for column in EFFECTIVE_SUBMISSION_COMPONENTS)


def ensure_effective_submission_id(df: pd.DataFrame) -> pd.DataFrame:
    """Return a frame with the canonical effective submission id populated."""
    out = df.copy()
    if EFFECTIVE_SUBMISSION_ID in out.columns:
        values = out[EFFECTIVE_SUBMISSION_ID].map(_clean_component)
        if values.ne("unknown").all():
            out[EFFECTIVE_SUBMISSION_ID] = values
            return ensure_config_id(out)

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


def aggregate_submission_task_success(
    df: pd.DataFrame,
    *,
    group_columns: Iterable[str] = (),
    outcome_column: str = "passed",
) -> pd.DataFrame:
    """Aggregate binary success as trials -> submission-task -> task/group."""
    group_columns = list(group_columns)
    work = ensure_effective_submission_id(df)
    keys = [EFFECTIVE_SUBMISSION_ID, "task_name", *group_columns]
    return (
        work.groupby(keys, as_index=False)
        .agg(
            submission_task_trajectory_count=(outcome_column, "size"),
            submission_task_success=(outcome_column, "mean"),
        )
    )


def aggregate_submission_task_effort(
    df: pd.DataFrame,
    metric: str,
    *,
    group_columns: Iterable[str] = (),
) -> pd.DataFrame:
    """Aggregate effort as trials -> submission-task median."""
    group_columns = list(group_columns)
    work = ensure_effective_submission_id(df).dropna(subset=[metric]).copy()
    keys = [EFFECTIVE_SUBMISSION_ID, "task_name", *group_columns]
    return (
        work.groupby(keys, as_index=False)[metric]
        .median()
        .rename(columns={metric: "submission_task_median"})
    )
