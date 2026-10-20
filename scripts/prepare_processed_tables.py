"""Restore large CSVs from Git-tracked gzip copies, or refresh those copies."""

from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TABLES = (
    Path("data/processed_live/terminal_bench_2_0/trajectory_summary.csv"),
    Path("data/processed_live/longitudinal/trajectory_longitudinal.csv"),
    Path("data/processed_live/longitudinal/tb3_tb4/trajectory_longitudinal.csv"),
)


def packed_path(csv_path: Path) -> Path:
    return csv_path.with_suffix(".csv.gz")


def content_hash(path: Path, *, compressed: bool = False) -> str:
    digest = hashlib.sha256()
    opener = gzip.open if compressed else open
    with opener(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_table(csv_path: Path) -> None:
    """Compare exact bytes, including encoding and line endings."""
    if content_hash(csv_path) != content_hash(packed_path(csv_path), compressed=True):
        raise ValueError(
            f"{csv_path} differs from its compressed copy. "
            "If the CSV was intentionally regenerated, run with --pack. "
            "Existing CSVs are never overwritten by restore."
        )


def pack_table(csv_path: Path) -> None:
    """Atomically write deterministic gzip bytes without altering the CSV."""
    destination = packed_path(csv_path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as target:
            temporary = Path(target.name)
            with csv_path.open("rb") as source:
                with gzip.GzipFile(
                    filename="", fileobj=target, mode="wb", compresslevel=6, mtime=0
                ) as compressed:
                    shutil.copyfileobj(source, compressed)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def restore_table(csv_path: Path) -> None:
    """Restore a missing CSV; refuse to overwrite differing local evidence."""
    if csv_path.exists():
        check_table(csv_path)
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=csv_path.parent, delete=False) as target:
            temporary = Path(target.name)
            with gzip.open(packed_path(csv_path), "rb") as source:
                shutil.copyfileobj(source, target)
        # Check again in case the destination appeared while decompressing.
        if csv_path.exists():
            check_table(csv_path)
        else:
            temporary.replace(csv_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--pack", action="store_true", help="Refresh gzip copies after regenerating CSVs")
    mode.add_argument("--check", action="store_true", help="Verify local CSVs match their gzip copies")
    args = parser.parse_args()
    action = pack_table if args.pack else check_table if args.check else restore_table
    for relative_path in TABLES:
        action(ROOT / relative_path)
        print(f"OK: {relative_path.as_posix()}")


if __name__ == "__main__":
    main()
