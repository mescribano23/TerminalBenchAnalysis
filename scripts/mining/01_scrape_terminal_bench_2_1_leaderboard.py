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

TrajectoryIndexWriter = _trajectory_index.TrajectoryIndexWriter
safe_path_component = _trajectory_index.safe_path_component
trajectory_file_status = _trajectory_index.trajectory_file_status
trajectory_payload_status = _trajectory_index.trajectory_payload_status


BASE_URL = "https://hub.harborframework.com"
DATASET_PATH = "/datasets/terminal-bench/terminal-bench-2-1/6"
LEADERBOARD_NAME = "main"
LEADERBOARD_ID = "60330f75-0dd8-47ea-bd1d-e2ea28945731"
FALLBACK_LEADERBOARD_ROWS_ACTION = "40d0c0e1ea147434f80751e4618cd32b9b43a808e3"
FALLBACK_ROW_TRIALS_ACTION = "40269c9e2f18a71b154c6cdd0116fe738ae39d2e57"

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

DEFAULT_BENCHMARK = "terminal_bench_2_1"
REQUEST_DELAY_SECONDS = 0.2
INDEX_CHECKPOINT_INTERVAL = 250

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

        total_pages = int(data.get("total_pages") or page)
        if page >= total_pages:
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


def task_records(row_id: str, trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        records.append(record)
    return records


def submission_record(row: dict[str, Any], trials: list[dict[str, Any]]) -> dict[str, Any]:
    identity = row_identity(row, trials)
    return {
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
        "tasks": task_records(str(row["id"]), trials),
    }


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
) -> tuple[int, int, list[tuple[str, str]]]:
    index_writer = TrajectoryIndexWriter(
        index_path=index_path,
        checkpoint_interval=index_checkpoint_interval,
    )
    pruned = index_writer.prune_invalid_file_entries(REPO_ROOT)
    indexed = 0
    fetched = 0
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

            is_valid, reason = trajectory_file_status(output_path)
            if is_valid:
                index_writer.upsert(entry)
                index_writer.checkpoint()
                indexed += 1
                continue
            index_writer.remove(entry)
            if reason != "missing":
                print(
                    f"  warning: retrying invalid trajectory file {output_path}: {reason}",
                    file=sys.stderr,
                )

            try:
                trajectory = fetch_trajectory(session, trial)
            except (requests.RequestException, json.JSONDecodeError) as exc:
                failures.append((trial_id, str(exc)))
                print(f"  warning: trajectory failed for {trial_id}: {exc}", file=sys.stderr)
                continue
            payload_is_valid, payload_reason = trajectory_payload_status(trajectory)
            if not payload_is_valid:
                failures.append((trial_id, payload_reason))
                print(
                    f"  warning: trajectory failed for {trial_id}: {payload_reason}",
                    file=sys.stderr,
                )
                continue

            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(trajectory, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            index_writer.upsert(entry)
            index_writer.checkpoint()
            indexed += 1
            fetched += 1

    index_writer.checkpoint(force=True)
    if pruned:
        print(f"Removed {pruned} stale trajectory index entries")
    return indexed, fetched, failures


def download_trajectories_from_trials_file(
    trials_path: Path,
    trajectories_dir: Path,
    trajectory_index: Path,
) -> int:
    try:
        trials = json.loads(trials_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read {trials_path}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(trials, list):
        print(f"{trials_path} does not contain a JSON list", file=sys.stderr)
        return 1

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

    session = requests.Session()
    indexed, fetched, failures = download_trajectories(
        session=session,
        submissions_by_row_id=submissions_by_row_id,
        trials_by_row_id=trials_by_row_id,
        trajectories_dir=trajectories_dir,
        index_path=trajectory_index,
        index_checkpoint_interval=INDEX_CHECKPOINT_INTERVAL,
    )
    print(f"Indexed {indexed} trajectories under {trajectories_dir}; fetched {fetched}")
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
    trials_output_path: Path,
    trajectories_dir: Path,
    trajectory_index: Path,
    download_trajectories_enabled: bool,
) -> int:
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
    for index, row in enumerate(rows, start=1):
        row_id = str(row["id"])
        display = label_from_link((row.get("metadata") or {}).get("agent_display"))
        model = label_from_link((row.get("metadata") or {}).get("model_display"))
        print(f"[{index}/{len(rows)}] row={row_id} {display} / {model}")
        try:
            trials = iter_row_trials(
                session,
                row_id=row_id,
                action_id=row_trials_action_id,
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

        submission = submission_record(row, trials)
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
    trials_output_path.parent.mkdir(parents=True, exist_ok=True)
    trials_output_path.write_text(
        json.dumps(all_trial_records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(all_trial_records)} trial metadata records to {trials_output_path}")

    if download_trajectories_enabled:
        indexed, fetched, trajectory_failures = download_trajectories(
            session=session,
            submissions_by_row_id=submissions_by_row_id,
            trials_by_row_id=trials_by_row_id,
            trajectories_dir=trajectories_dir,
            index_path=trajectory_index,
            index_checkpoint_interval=INDEX_CHECKPOINT_INTERVAL,
        )
        failures.extend(trajectory_failures)
        print(f"Indexed {indexed} trajectories under {trajectories_dir}; fetched {fetched}")
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--download-trajectories",
        action="store_true",
        help="Scrape metadata, then download all available trajectory JSON.",
    )
    mode.add_argument(
        "--retry-trajectories",
        action="store_true",
        help="Download/retry trajectories from the saved Harbor trial metadata cache.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    benchmark_paths = paths_for_benchmark(REPO_ROOT, DEFAULT_BENCHMARK)

    if args.retry_trajectories:
        return download_trajectories_from_trials_file(
            trials_path=benchmark_paths.leaderboard_trials,
            trajectories_dir=benchmark_paths.trajectories_dir,
            trajectory_index=benchmark_paths.trajectory_index,
        )

    return scrape_harbor_leaderboard(
        output_path=benchmark_paths.leaderboard_submissions,
        trials_output_path=benchmark_paths.leaderboard_trials,
        trajectories_dir=benchmark_paths.trajectories_dir,
        trajectory_index=benchmark_paths.trajectory_index,
        download_trajectories_enabled=args.download_trajectories,
    )


if __name__ == "__main__":
    raise SystemExit(main())
