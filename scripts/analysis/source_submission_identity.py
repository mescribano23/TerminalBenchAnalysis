"""Resolve leaderboard membership from retained acquisition evidence, never URLs on trajectories.

TB2 membership is reconstructed (not an independently retained UUID-to-source link).
Harbor membership is explicit in the retained trial records. Raw snapshots are read only.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

SOURCE_SUBMISSION_ID = "source_submission_id"
DATE_SEMANTICS = "historical_leaderboard_metadata.date; submission/publication semantics unverified"
IDENTITY_FIELDS = [
    SOURCE_SUBMISSION_ID, "source_submission_url", "source_scaffold_version",
    "leaderboard_model", "leaderboard_provider", "leaderboard_accuracy",
    "leaderboard_date", "leaderboard_model_organization", "leaderboard_agent_organization",
    "historical_leaderboard_date", "date_provenance", "date_semantics",
    "source_identity_status", "source_identity_method", "source_identity_evidence",
    "source_row_uuid", "trial_started_at", "trial_finished_at",
]


def source_id(benchmark: str, url: str) -> str:
    """Stable under metadata/date/configuration changes; benchmark namespaces the source."""
    url = str(url).strip().rstrip("/")
    if not url:
        raise ValueError("A source submission needs an authoritative source URL")
    if "/rows/" in url:
        return f"{benchmark}:harbor:{urlsplit(url).path.rsplit('/', 1)[-1]}"
    return f"{benchmark}:tbench:{url}"


class SourceResolver:
    def __init__(self, benchmark: str, leaderboard_path: Path, trials_path: Path):
        self.benchmark = benchmark
        self.source_file = leaderboard_path.as_posix()
        self.entries = json.loads(leaderboard_path.read_text(encoding="utf-8"))
        self.public = [x for x in self.entries if x.get("has_trajectories")]
        self.by_config = {}
        self.by_row = {}
        for entry in self.public:
            self.by_config.setdefault((entry["scaffold"], entry["model"]), []).append(entry)
            if "/rows/" in entry["submission_url"]:
                key = entry["submission_url"].rstrip("/").rsplit("/", 1)[-1]
                if key in self.by_row:
                    raise ValueError(f"Duplicate source row {key}")
                self.by_row[key] = entry
        self.trials = {}
        if trials_path.exists():
            for trial in json.loads(trials_path.read_text(encoding="utf-8")):
                key = str(trial.get("id") or trial.get("trialId") or "")
                if key in self.trials:
                    raise ValueError(f"Duplicate raw trial UUID {key}")
                self.trials[key] = trial

    def resolve(self, row: dict, index: dict) -> tuple[dict, dict]:
        uuid = str(row.get("file_run_id") or index.get("trialId") or "")
        trial = self.trials.get(uuid, {})
        if self.benchmark == "terminal_bench_2_0":
            if not index or str(index.get("trialId")) != uuid:
                raise ValueError(f"Missing exact acquisition index UUID: {uuid}")
            if str(index.get("scaffold")) != str(row.get("scaffold")):
                raise ValueError(f"Acquisition scaffold conflict: {uuid}")
            explicit_url = index.get("source_submission_url") or trial.get("submission_url")
            candidates = self.by_config.get((index.get("scaffold"), index.get("model")), [])
            if explicit_url:
                candidates = [x for x in candidates if x["submission_url"] == explicit_url]
            if len(candidates) > 1:
                candidates = [x for x in candidates if str(x.get("scaffold_version")) == str(row.get("agent_version"))]
            if len(candidates) != 1:
                raise ValueError(f"Unresolved TB2 source membership for {uuid}: {len(candidates)} exact candidates")
            entry = candidates[0]
            task = [t for t in entry.get("tasks", []) if str(t.get("taskChecksum")) == str(index.get("taskChecksum"))]
            if len(task) != 1 or str(task[0]["taskName"]) != str(index.get("taskName")):
                raise ValueError(f"Source task conflict: {uuid}")
            status, method = "reconstructed", "exact_acquisition_scaffold_model; agent_version_if_ambiguous; task_checksum"
            evidence = "retained acquisition index; source snapshot; trajectory agent version; original UUID-source cache absent"
            if explicit_url:
                status, method = "validated_acquisition_source_url", "explicit_retained_trial_source_url_with_exact_configuration_and_task_validation"
                evidence = "explicit source URL retained by acquisition; trial UUID, configuration and task corroborated"
        else:
            row_uuid = str(trial.get("harbor_leaderboard_row_id") or "")
            if row_uuid not in self.by_row:
                raise ValueError(f"Missing authoritative Harbor trial-row association: {uuid}")
            for field, source_field in [("scaffold", "agent_name"), ("agent_version", "agent_version")]:
                if str(row.get(field) or "") != str(trial.get(source_field) or ""):
                    raise ValueError(f"Harbor {field} conflicts with trajectory for {uuid}")
            entry = self.by_row[row_uuid]
            status, method = "validated_trial_uuid", "retained_harbor_trial_uuid_to_row_uuid"
            evidence = "retained leaderboard_trials.json id + harbor_leaderboard_row_id"
        date = str(entry.get("leaderboard_date") or "")
        result = {
            SOURCE_SUBMISSION_ID: source_id(self.benchmark, entry["submission_url"]),
            "source_submission_url": entry["submission_url"],
            "source_scaffold_version": entry.get("scaffold_version", ""),
            "leaderboard_model": entry.get("model", ""),
            "leaderboard_provider": entry.get("provider", ""),
            "leaderboard_accuracy": entry.get("leaderboard_accuracy", ""),
            "leaderboard_date": date,
            "historical_leaderboard_date": date,
            "leaderboard_model_organization": entry.get("leaderboard_model_organization", ""),
            "leaderboard_agent_organization": entry.get("leaderboard_agent_organization", ""),
            "date_provenance": self.source_file + "#leaderboard_date",
            "date_semantics": DATE_SEMANTICS,
            "source_identity_status": status, "source_identity_method": method,
            "source_identity_evidence": evidence,
            "source_row_uuid": entry["submission_url"].rstrip("/").rsplit("/", 1)[-1] if self.by_row else "",
            "trial_started_at": trial.get("started_at", ""),
            "trial_finished_at": trial.get("finished_at", ""),
        }
        return result, entry


def ensure_source_submission_id(df: pd.DataFrame) -> pd.DataFrame:
    """Fail closed: never infer membership from a cached URL or configuration."""
    if SOURCE_SUBMISSION_ID not in df:
        raise ValueError("Missing source_submission_id; run the source-identity reconciliation first")
    values = df[SOURCE_SUBMISSION_ID].fillna("").astype(str).str.strip()
    if values.eq("").any() or values.str.contains(":unresolved:", regex=False).any():
        raise ValueError("Submission-balanced analysis cannot include unresolved source membership")
    out = df.copy()
    out[SOURCE_SUBMISSION_ID] = values
    if "source_identity_status" in out and not out.source_identity_status.isin(["reconstructed", "validated_trial_uuid", "validated_acquisition_source_url"]).all():
        raise ValueError("Unvalidated source submission identity")
    if {"scaffold", "model_dir"}.issubset(out.columns):
        from scripts.analysis.submission_task_balancing import ensure_config_id
        out = ensure_config_id(out)
    return out
