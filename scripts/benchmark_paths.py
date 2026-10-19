"""Shared benchmark-specific filesystem paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_BENCHMARKS = (
    "terminal_bench_2_0",
    "terminal_bench_2_1",
    "terminal_bench_3_0",
    "terminal_bench_4_0",
)


def find_repo_root(start: Path) -> Path:
    """Find the repository root from a script path."""
    for path in (start, *start.parents):
        if (
            (path / "data").exists()
            and (path / "reports").exists()
            and (path / "scripts").exists()
        ):
            return path
    raise ValueError(f"Could not find repository root from {start}")


@dataclass(frozen=True)
class BenchmarkPaths:
    benchmark: str
    raw_dir: Path
    indexes_dir: Path
    trajectories_dir: Path
    processed_dir: Path
    figures_dir: Path
    leaderboard_submissions: Path
    leaderboard_trials: Path
    trajectory_index: Path


def paths_for_benchmark(repo_root: Path, benchmark: str) -> BenchmarkPaths:
    """Return canonical data/report paths for a Terminal-Bench version."""
    if benchmark not in SUPPORTED_BENCHMARKS:
        choices = ", ".join(SUPPORTED_BENCHMARKS)
        raise ValueError(f"unknown benchmark {benchmark!r}; expected one of: {choices}")

    data_dir = repo_root / "data"
    raw_dir = data_dir / "raw" / benchmark
    indexes_dir = data_dir / "indexes" / benchmark

    trajectories_dir = data_dir / "trajectories" / benchmark

    processed_dir = data_dir / "processed_live" / benchmark
    figures_dir = repo_root / "reports" / "general_characteristics" / benchmark

    return BenchmarkPaths(
        benchmark=benchmark,
        raw_dir=raw_dir,
        indexes_dir=indexes_dir,
        trajectories_dir=trajectories_dir,
        processed_dir=processed_dir,
        figures_dir=figures_dir,
        leaderboard_submissions=raw_dir / "leaderboard_submissions.json",
        leaderboard_trials=raw_dir / "leaderboard_trials.json",
        trajectory_index=indexes_dir / "trajectory_trials.json",
    )
