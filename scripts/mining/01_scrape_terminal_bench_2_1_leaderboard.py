#!/usr/bin/env python3
"""Scrape Terminal-Bench 2.1 leaderboard rows, trials, and trajectories.

Terminal-Bench 2.0 was hosted on tbench.ai; Terminal-Bench 2.1 is hosted on
Harbor Hub. Harbor's leaderboard and row tables are fetched through Next.js
server actions, while trajectories are exposed by a JSON API. This script keeps
the saved leaderboard, trajectory files, and trajectory index compatible with
the existing 2.0 mining outputs.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from scripts.benchmark_paths import paths_for_benchmark

_trajectory_index = importlib.import_module(".04_trajectory_index_helpers", __package__)
_tbench_scraper = importlib.import_module(
    ".00_scrape_terminal_bench_2_0_leaderboard",
    __package__,
)

TrajectoryIndexWriter = _trajectory_index.TrajectoryIndexWriter
safe_path_component = _tbench_scraper.safe_path_component


BASE_URL = "https://hub.harborframework.com"
DATASET_PATH = "/datasets/terminal-bench/terminal-bench-2-1/6"
LEADERBOARD_NAME = "main"
LEADERBOARD_ID = "60330f75-0dd8-47ea-bd1d-e2ea28945731"
FALLBACK_LEADERBOARD_ROWS_ACTION = "40d0c0e1ea147434f80751e4618cd32b9b43a808e3"
FALLBACK_ROW_TRIALS_ACTION = "40269c9e2f18a71b154c6cdd0116fe738ae39d2e57"

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

DEFAULT_BENCHMARK = "terminal_bench_2_1"
BENCHMARK_TRIALS_SENTINEL = Path("__benchmark_trials__")
REQUEST_DELAY_SECONDS = 0.2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

CHUNK_SRC_RE = re.compile(r'src="(?P<src>/_next/static/chunks/[^"]+\.js(?:\?[^"]*)?)"')
SERVER_REFERENCE_RE = re.compile(
    r'"(?P<action>[0-9a-f]{40,48})".{0,300}?"(?P<name>[^"]+)"',
    flags=re.DOTALL,
)


def row_url(row_id: str, page: int = 1) -> str:
    return (
        f"{BASE_URL}{DATASET_PATH}/leaderboards/{LEADERBOARD_NAME}/rows/"
        f"{quote(row_id, safe='')}?tab=results&page={page}"
    )


def main_leaderboard_url() -> str:
    return f"{BASE_URL}{DATASET_PATH}?tab=leaderboard&leaderboard={LEADERBOARD_NAME}"


def action_headers(action_id: str, referer: str) -> dict[str, str]:
    return {
        **HEADERS,
        "Next-Action": action_id,
        "Accept": "text/x-component",
        "Content-Type": "text/plain;charset=UTF-8",
        "Origin": BASE_URL,
        "Referer": referer,
    }


def fetch_text(session: requests.Session, url: str) -> str:
    time.sleep(REQUEST_DELAY_SECONDS)
    response = session.get(url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def discover_server_action_id(
    session: requests.Session,
    page_url: str,
    action_name: str,
    fallback_action_id: str,
) -> str:
    """Find a Next.js server-action id in the current Harbor chunks.

    Harbor redeploys can change server-action IDs. The public page lists the
    current chunk files, so resolve the action ID at runtime and keep the
    known-good ID only as a fallback.
    """
    try:
        html_text = fetch_text(session, page_url)
    except requests.RequestException as exc:
        print(
            f"  warning: could not discover {action_name}; using fallback: {exc}",
            file=sys.stderr,
        )
        return fallback_action_id

    for match in CHUNK_SRC_RE.finditer(html_text):
        chunk_url = f"{BASE_URL}{match.group('src')}"
        try:
            chunk_text = fetch_text(session, chunk_url)
        except requests.RequestException:
            continue
        if action_name not in chunk_text:
            continue
        for reference in SERVER_REFERENCE_RE.finditer(chunk_text):
            if reference.group("name") == action_name:
                return reference.group("action")

    print(
        f"  warning: could not find {action_name}; using fallback action id",
        file=sys.stderr,
    )
    return fallback_action_id


def extract_server_action_payload(text: str, required_key: str) -> dict[str, Any]:
    for line in text.splitlines():
        if ":" not in line:
            continue
        prefix, payload = line.split(":", 1)
        if not prefix.isalnum() or not payload.startswith("{"):
            continue
        try:
            value = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and required_key in value:
            return value
    raise ValueError(f"server action payload with key {required_key!r} not found")


def post_server_action(
    session: requests.Session,
    url: str,
    action_id: str,
    args: list[Any],
    required_key: str,
) -> dict[str, Any]:
    time.sleep(REQUEST_DELAY_SECONDS)
    response = session.post(
        url,
        headers=action_headers(action_id, url),
        data=json.dumps(args, separators=(",", ":")),
        timeout=60,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    return extract_server_action_payload(response.text, required_key)


def fetch_leaderboard(session: requests.Session, action_id: str) -> dict[str, Any]:
    return post_server_action(
        session=session,
        url=main_leaderboard_url(),
        action_id=action_id,
        args=[LEADERBOARD_ID],
        required_key="rows",
    )


def fetch_row_trials_page(
    session: requests.Session,
    row_id: str,
    page: int,
    action_id: str,
) -> dict[str, Any]:
    url = row_url(row_id, page=page)
    return post_server_action(
        session=session,
        url=url,
        action_id=action_id,
        args=[{"leaderboardId": LEADERBOARD_ID, "rowIds": [row_id], "page": page}],
        required_key="items",
    )


def iter_row_trials(
    session: requests.Session,
    row_id: str,
    action_id: str,
    page_limit: int | None = None,
    trial_limit: int | None = None,
) -> list[dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    page = 1
    while True:
        data = fetch_row_trials_page(
            session,
            row_id=row_id,
            page=page,
            action_id=action_id,
        )
        trials.extend(data["items"])
        if trial_limit is not None and len(trials) >= trial_limit:
            return trials[:trial_limit]

        total_pages = int(data.get("total_pages") or page)
        if page >= total_pages:
            return trials
        if page_limit is not None and page >= page_limit:
            return trials
        page += 1


def label_from_link(value: Any) -> str:
    if isinstance(value, dict):
        label = value.get("label")
        if isinstance(label, str):
            return label
        url = value.get("url")
        if isinstance(url, str):
            return url
    return str(value) if value not in {None, ""} else ""


def slug_from_task_name(task_name: str) -> str:
    return task_name.rsplit("/", 1)[-1] if "/" in task_name else task_name


def duration_seconds(trial: dict[str, Any]) -> float:
    started_at = trial.get("started_at")
    finished_at = trial.get("finished_at")
    if not isinstance(started_at, str) or not isinstance(finished_at, str):
        return 0.0
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return max(0.0, (end - start).total_seconds())


def optional_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def row_identity(row: dict[str, Any], trials: list[dict[str, Any]]) -> dict[str, str]:
    first_trial = trials[0] if trials else {}
    metadata = row.get("metadata") or {}
    metrics = row.get("metrics") or {}

    scaffold = first_trial.get("agent_name")
    scaffold_version = first_trial.get("agent_version")
    model = first_trial.get("model_name")
    provider = first_trial.get("model_provider")

    return {
        "scaffold": str(scaffold or label_from_link(metadata.get("agent_display")) or "unknown"),
        "scaffold_version": str(scaffold_version or "unknown"),
        "model": str(model or label_from_link(metadata.get("model_display")) or "unknown"),
        "provider": str(provider or ""),
        "leaderboard_agent_display_name": label_from_link(metadata.get("agent_display")),
        "leaderboard_model_display": label_from_link(metadata.get("model_display")),
        "leaderboard_agent_organization": label_from_link(metadata.get("agent_org")),
        "leaderboard_model_organization": label_from_link(metadata.get("model_org")),
        "leaderboard_date": str(metadata.get("date") or ""),
        "leaderboard_accuracy_display": str(metrics.get("display_accuracy") or ""),
    }


def leaderboard_metrics(row: dict[str, Any]) -> dict[str, Any]:
    metrics = row.get("metrics") or {}
    accuracy_percent = optional_float(metrics.get("accuracy"))
    stderr_percent = optional_float(metrics.get("accuracy_stderr"))
    accuracy = accuracy_percent / 100 if accuracy_percent is not None else ""
    stderr = stderr_percent / 100 if stderr_percent is not None else ""
    ci95 = stderr_percent * 1.96 if stderr_percent is not None else ""
    return {
        "leaderboard_accuracy": accuracy,
        "leaderboard_accuracy_percent": accuracy_percent if accuracy_percent is not None else "",
        "leaderboard_stderr": stderr,
        "leaderboard_stderr_percent": stderr_percent if stderr_percent is not None else "",
        "leaderboard_accuracy_ci95_pm_percent": ci95,
    }


def task_records(
    row_id: str,
    trials: list[dict[str, Any]],
    include_harbor_metadata: bool = False,
) -> list[dict[str, Any]]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trial in trials:
        task_name = str(trial.get("task_name") or trial.get("name") or "unknown")
        by_task[task_name].append(trial)

    records: list[dict[str, Any]] = []
    for harbor_task_name, task_trials in sorted(by_task.items()):
        task_name = slug_from_task_name(harbor_task_name)
        successes = sum(1 for trial in task_trials if float(trial.get("reward") or 0.0) > 0)
        n_trials = len(task_trials)
        record = {
            "taskName": task_name,
            "taskChecksum": task_name,
            "nTrials": n_trials,
            "avgResolutionRate": successes / n_trials if n_trials else 0.0,
            "successCount": successes,
            "trialUrl": (
                f"{row_url(row_id, page=1).split('?', 1)[0]}"
                f"?tab=results&task={quote(harbor_task_name, safe='')}"
            ),
        }
        if include_harbor_metadata:
            record["harborTaskName"] = harbor_task_name
        records.append(record)
    return records


def submission_record(
    row: dict[str, Any],
    trials: list[dict[str, Any]],
    include_harbor_metadata: bool = False,
) -> dict[str, Any]:
    identity = row_identity(row, trials)
    record = {
        "scaffold": identity["scaffold"],
        "scaffold_version": identity["scaffold_version"],
        "model": identity["model"],
        "provider": identity["provider"],
        "has_trajectories": True,
        "submission_url": row_url(str(row["id"]), page=1).split("?", 1)[0],
        **leaderboard_metrics(row),
        "leaderboard_accuracy_display": identity["leaderboard_accuracy_display"],
        "leaderboard_date": identity["leaderboard_date"],
        "leaderboard_agent_display_name": identity["leaderboard_agent_display_name"],
        "leaderboard_model_display": identity["leaderboard_model_display"],
        "leaderboard_agent_organization": identity["leaderboard_agent_organization"],
        "leaderboard_model_organization": identity["leaderboard_model_organization"],
        "tasks": task_records(
            str(row["id"]),
            trials,
            include_harbor_metadata=include_harbor_metadata,
        ),
    }
    if include_harbor_metadata:
        record.update(
            {
                "harbor_leaderboard_row_id": row.get("id"),
                "harbor_leaderboard_rank": row.get("rank"),
                "harbor_leaderboard_metrics": row.get("metrics") or {},
                "harbor_leaderboard_metadata": row.get("metadata") or {},
            }
        )
    return record


def trajectory_url(trial: dict[str, Any]) -> str:
    trial_id = str(trial["id"])
    return f"{BASE_URL}/api/trials/{quote(trial_id, safe='')}/trajectory"


def fetch_trajectory(
    session: requests.Session,
    trial: dict[str, Any],
    attempts: int = 3,
) -> dict[str, Any]:
    trial_id = str(trial["id"])
    job_id = str(trial["job_id"])
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        time.sleep(REQUEST_DELAY_SECONDS * attempt)
        try:
            response = session.get(
                trajectory_url(trial),
                headers={**HEADERS, "Accept": "application/json"},
                params={
                    "jobId": job_id,
                    "trajectory_path": f"trials/{trial_id}/trajectory.json",
                },
                timeout=180,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            print(
                f"  warning: retrying trajectory {trial_id} "
                f"after attempt {attempt}/{attempts}: {exc}",
                file=sys.stderr,
            )
    if last_error is None:
        raise RuntimeError(f"trajectory fetch failed for {trial_id}")
    raise last_error


def trial_index_entry(
    submission: dict[str, Any],
    trial: dict[str, Any],
    output_path: Path,
) -> dict[str, Any]:
    task_name = slug_from_task_name(str(trial.get("task_name") or trial.get("name") or "unknown"))
    cost_usd = optional_float(trial.get("cost_usd")) or 0.0
    return {
        "scaffold": str(submission["scaffold"]),
        "model": str(submission["model"]),
        "taskName": task_name,
        "taskChecksum": task_name,
        "trialId": str(trial["id"]),
        "reward": float(trial.get("reward") or 0.0),
        "cost": cost_usd * 100,
        "duration": duration_seconds(trial),
        "filePath": index_file_path(output_path),
    }


def index_file_path(output_path: Path) -> str:
    try:
        return output_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return output_path.as_posix()


def download_trajectories(
    session: requests.Session,
    submissions_by_row_id: dict[str, dict[str, Any]],
    trials_by_row_id: dict[str, list[dict[str, Any]]],
    trajectories_dir: Path,
    index_path: Path,
    index_checkpoint_interval: int,
) -> tuple[int, list[tuple[str, str]]]:
    index_writer = TrajectoryIndexWriter(
        index_path=index_path,
        checkpoint_interval=index_checkpoint_interval,
    )
    downloaded = 0
    failures: list[tuple[str, str]] = []

    for row_id, submission in submissions_by_row_id.items():
        scaffold = str(submission.get("scaffold", "unknown"))
        model = str(submission.get("model", "unknown"))
        output_dir = trajectories_dir / safe_path_component(scaffold) / safe_path_component(model)

        for trial in trials_by_row_id[row_id]:
            trial_id = str(trial["id"])
            task_checksum = slug_from_task_name(
                str(trial.get("task_name") or trial.get("name") or "unknown")
            )
            output_path = output_dir / (
                f"{safe_path_component(task_checksum)}_{safe_path_component(trial_id)}.json"
            )
            entry = trial_index_entry(submission, trial, output_path)

            if output_path.exists():
                index_writer.upsert(entry)
                index_writer.checkpoint()
                downloaded += 1
                continue

            try:
                trajectory = fetch_trajectory(session, trial)
            except (requests.RequestException, json.JSONDecodeError) as exc:
                failures.append((trial_id, str(exc)))
                print(f"  warning: trajectory failed for {trial_id}: {exc}", file=sys.stderr)
                continue

            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(trajectory, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            index_writer.upsert(entry)
            index_writer.checkpoint()
            downloaded += 1

    index_writer.checkpoint(force=True)
    return downloaded, failures


def download_trajectories_from_trials_file(
    trials_path: Path,
    trajectories_dir: Path,
    trajectory_index: Path,
    index_checkpoint_interval: int,
    trial_id_filter: list[str] | None = None,
) -> int:
    trials = json.loads(trials_path.read_text(encoding="utf-8"))
    if not isinstance(trials, list):
        print(f"{trials_path} does not contain a JSON list", file=sys.stderr)
        return 1

    wanted = set(trial_id_filter or [])
    if wanted:
        trials = [trial for trial in trials if str(trial.get("id")) in wanted]

    submissions_by_row_id: dict[str, dict[str, Any]] = {}
    trials_by_row_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trial in trials:
        if not isinstance(trial, dict) or not trial.get("id") or not trial.get("job_id"):
            continue
        row_id = str(trial.get("harbor_leaderboard_row_id") or "unknown")
        submission = trial.get("submission") if isinstance(trial.get("submission"), dict) else {}
        submissions_by_row_id.setdefault(
            row_id,
            {
                "scaffold": submission.get("scaffold") or trial.get("agent_name") or "unknown",
                "model": submission.get("model") or trial.get("model_name") or "unknown",
            },
        )
        trials_by_row_id[row_id].append(trial)

    if wanted and len(trials) != len(wanted):
        found = {str(trial.get("id")) for trial in trials}
        missing = sorted(wanted - found)
        print(
            f"  warning: {len(missing)} requested trial ids were not in {trials_path}: "
            f"{', '.join(missing)}",
            file=sys.stderr,
        )

    session = requests.Session()
    total, failures = download_trajectories(
        session=session,
        submissions_by_row_id=submissions_by_row_id,
        trials_by_row_id=trials_by_row_id,
        trajectories_dir=trajectories_dir,
        index_path=trajectory_index,
        index_checkpoint_interval=index_checkpoint_interval,
    )
    print(f"Wrote/indexed {total} trajectories under {trajectories_dir}")
    print(f"Trajectory index: {trajectory_index}")

    if failures:
        print(f"Completed with {len(failures)} failures:", file=sys.stderr)
        for key, error in failures[:20]:
            print(f"  {key}: {error}", file=sys.stderr)
        if len(failures) > 20:
            print(f"  ... {len(failures) - 20} more", file=sys.stderr)
        return 1
    return 0


def scrape_harbor_leaderboard(
    output_path: Path,
    trials_output_path: Path | None,
    trajectories_dir: Path,
    trajectory_index: Path,
    limit: int | None,
    row_start_index: int,
    row_id_filter: list[str] | None,
    page_limit: int | None,
    trial_limit: int | None,
    skip_trajectories: bool,
    include_harbor_metadata: bool,
    index_checkpoint_interval: int,
) -> int:
    if row_start_index < 1:
        raise ValueError("--row-start-index must be 1 or greater.")

    session = requests.Session()
    print(f"Fetching Harbor leaderboard: {main_leaderboard_url()}")
    leaderboard_action_id = discover_server_action_id(
        session=session,
        page_url=main_leaderboard_url(),
        action_name="fetchLeaderboardWithRows",
        fallback_action_id=FALLBACK_LEADERBOARD_ROWS_ACTION,
    )
    leaderboard = fetch_leaderboard(session, action_id=leaderboard_action_id)
    rows = list(leaderboard["rows"])
    if row_id_filter:
        wanted = set(row_id_filter)
        rows = [row for row in rows if str(row.get("id")) in wanted]
    if limit is not None:
        rows = rows[:limit]
    rows = rows[row_start_index - 1 :]

    row_trials_action_id = (
        discover_server_action_id(
            session=session,
            page_url=row_url(str(rows[0]["id"]), page=1),
            action_name="fetchLeaderboardRowTrials",
            fallback_action_id=FALLBACK_ROW_TRIALS_ACTION,
        )
        if rows
        else FALLBACK_ROW_TRIALS_ACTION
    )

    submissions: list[dict[str, Any]] = []
    all_trial_records: list[dict[str, Any]] = []
    submissions_by_row_id: dict[str, dict[str, Any]] = {}
    trials_by_row_id: dict[str, list[dict[str, Any]]] = {}
    failures: list[tuple[str, str]] = []

    print(f"Found {len(rows)} leaderboard rows to scrape")
    for index, row in enumerate(rows, start=row_start_index):
        row_id = str(row["id"])
        display = label_from_link((row.get("metadata") or {}).get("agent_display"))
        model = label_from_link((row.get("metadata") or {}).get("model_display"))
        print(f"[{index}/{row_start_index + len(rows) - 1}] row={row_id} {display} / {model}")
        try:
            trials = iter_row_trials(
                session,
                row_id=row_id,
                action_id=row_trials_action_id,
                page_limit=page_limit,
                trial_limit=trial_limit,
            )
        except (requests.RequestException, ValueError) as exc:
            failures.append((row_id, str(exc)))
            print(f"  warning: trial metadata failed for row {row_id}: {exc}", file=sys.stderr)
            continue

        if not trials:
            failures.append((row_id, "no trial metadata returned"))
            print(
                f"  warning: trial metadata returned zero records for row {row_id}",
                file=sys.stderr,
            )
            continue

        submission = submission_record(
            row,
            trials,
            include_harbor_metadata=include_harbor_metadata,
        )
        submissions.append(submission)
        submissions_by_row_id[row_id] = submission
        trials_by_row_id[row_id] = trials
        all_trial_records.extend(
            {
                "harbor_leaderboard_row_id": row_id,
                "submission": {
                    "scaffold": submission["scaffold"],
                    "scaffold_version": submission["scaffold_version"],
                    "model": submission["model"],
                    "provider": submission["provider"],
                },
                **trial,
            }
            for trial in trials
        )
        print(f"  trials={len(trials)}, tasks={len(submission['tasks'])}")

    if failures:
        print("Aborting before writing outputs because row trial metadata failed.", file=sys.stderr)
        print(f"Completed with {len(failures)} failures:", file=sys.stderr)
        for key, error in failures[:20]:
            print(f"  {key}: {error}", file=sys.stderr)
        if len(failures) > 20:
            print(f"  ... {len(failures) - 20} more", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(submissions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(submissions)} submissions to {output_path}")
    if trials_output_path is not None:
        trials_output_path.parent.mkdir(parents=True, exist_ok=True)
        trials_output_path.write_text(
            json.dumps(all_trial_records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Wrote {len(all_trial_records)} trial metadata records to {trials_output_path}")

    if not skip_trajectories:
        total, trajectory_failures = download_trajectories(
            session=session,
            submissions_by_row_id=submissions_by_row_id,
            trials_by_row_id=trials_by_row_id,
            trajectories_dir=trajectories_dir,
            index_path=trajectory_index,
            index_checkpoint_interval=index_checkpoint_interval,
        )
        failures.extend(trajectory_failures)
        print(f"Wrote/indexed {total} trajectories under {trajectories_dir}")
        print(f"Trajectory index: {trajectory_index}")

    if failures:
        print(f"Completed with {len(failures)} failures:", file=sys.stderr)
        for key, error in failures[:20]:
            print(f"  {key}: {error}", file=sys.stderr)
        if len(failures) > 20:
            print(f"  ... {len(failures) - 20} more", file=sys.stderr)
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Terminal-Bench 2.1 data from Harbor Hub."
    )
    parser.add_argument(
        "--benchmark",
        choices=[DEFAULT_BENCHMARK],
        default=DEFAULT_BENCHMARK,
        help="Benchmark namespace used to resolve default data paths.",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--trials-output",
        type=Path,
        default=None,
        help=(
            "Harbor-specific raw trial metadata cache. Defaults to the "
            "benchmark raw folder; use --no-trials-output to skip it."
        ),
    )
    parser.add_argument(
        "--no-trials-output",
        action="store_true",
        help="Do not write the Harbor trial metadata cache.",
    )
    parser.add_argument("--trajectories-dir", type=Path, default=None)
    parser.add_argument("--trajectory-index", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Only scrape the first N rows.")
    parser.add_argument(
        "--row-start-index",
        type=int,
        default=1,
        help="1-based row offset for resuming metadata collection.",
    )
    parser.add_argument(
        "--row-id",
        action="append",
        default=None,
        help="Only scrape this Harbor leaderboard row id; repeat for multiple rows.",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=None,
        help="Only fetch the first N trial pages per row.",
    )
    parser.add_argument(
        "--trial-limit",
        type=int,
        default=None,
        help="Only fetch/download the first N trials per row.",
    )
    parser.add_argument(
        "--skip-trajectories",
        action="store_true",
        help="Save leaderboard metadata, but do not download trajectory JSON.",
    )
    parser.add_argument(
        "--include-harbor-metadata",
        action="store_true",
        help="Include Harbor-only metadata fields in the leaderboard JSON.",
    )
    parser.add_argument(
        "--download-trajectories-from-trials",
        type=Path,
        nargs="?",
        const=BENCHMARK_TRIALS_SENTINEL,
        default=None,
        help=(
            "Download/retry trajectories from an existing Harbor trial metadata "
            "JSON instead of scraping leaderboard/trial tables first. If no "
            "path is supplied, use the benchmark raw trial cache."
        ),
    )
    parser.add_argument(
        "--trial-id",
        action="append",
        default=None,
        help=(
            "With --download-trajectories-from-trials, only retry this trial id; "
            "repeat for multiple ids."
        ),
    )
    parser.add_argument(
        "--index-checkpoint-interval",
        type=int,
        default=250,
        help="Write the trajectory index after this many updates; use 0 for final-only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    benchmark_paths = paths_for_benchmark(REPO_ROOT, args.benchmark)
    output_path = args.output or benchmark_paths.leaderboard_submissions
    trials_output_path = (
        None
        if args.no_trials_output
        else args.trials_output or benchmark_paths.leaderboard_trials
    )
    trajectories_dir = args.trajectories_dir or benchmark_paths.trajectories_dir
    trajectory_index = args.trajectory_index or benchmark_paths.trajectory_index

    if args.download_trajectories_from_trials is not None:
        trials_path = (
            benchmark_paths.leaderboard_trials
            if args.download_trajectories_from_trials == BENCHMARK_TRIALS_SENTINEL
            else args.download_trajectories_from_trials
        )
        return download_trajectories_from_trials_file(
            trials_path=trials_path,
            trajectories_dir=trajectories_dir,
            trajectory_index=trajectory_index,
            index_checkpoint_interval=args.index_checkpoint_interval,
            trial_id_filter=args.trial_id,
        )

    return scrape_harbor_leaderboard(
        output_path=output_path,
        trials_output_path=trials_output_path,
        trajectories_dir=trajectories_dir,
        trajectory_index=trajectory_index,
        limit=args.limit,
        row_start_index=args.row_start_index,
        row_id_filter=args.row_id,
        page_limit=args.page_limit,
        trial_limit=args.trial_limit,
        skip_trajectories=args.skip_trajectories,
        include_harbor_metadata=args.include_harbor_metadata,
        index_checkpoint_interval=args.index_checkpoint_interval,
    )


if __name__ == "__main__":
    raise SystemExit(main())
