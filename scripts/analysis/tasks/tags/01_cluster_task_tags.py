#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from collections import Counter, defaultdict

import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering

from scripts.benchmark_paths import find_repo_root


ROOT = find_repo_root(Path(__file__).resolve().parent)

TASKS_JSON = ROOT / "data/raw/terminal_bench_2_0/terminal_bench_2_tasks.json"
OUT_DIR = ROOT / "data/processed_live/task_mining/tags/semantic_clusters"
MODEL_NAME = "all-MiniLM-L6-v2"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Cluster Terminal-Bench task tags using semantic embeddings."
    )

    parser.add_argument(
        "--distance-threshold",
        type=float,
        default=0.65,
        help=(
            "Cosine-distance threshold for clustering. "
            "Lower = more clusters, higher = fewer clusters. "
            "Ignored if --n-clusters is set."
        ),
    )

    parser.add_argument(
        "--n-clusters",
        type=int,
        default=None,
        help="Force exactly this many clusters instead of using distance threshold.",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(TASKS_JSON, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    tag_counts = Counter()
    tag_tasks = defaultdict(list)

    for task in tasks:
        task_id = task.get("id", "unknown_task")
        for tag in task.get("tags", []):
            tag = tag.strip().lower().replace("_", "-")
            tag_counts[tag] += 1
            tag_tasks[tag].append(task_id)

    tags = sorted(tag_counts)

    model = SentenceTransformer(MODEL_NAME)
    phrases = [tag.replace("-", " ") for tag in tags]
    embeddings = model.encode(phrases, normalize_embeddings=True)

    if args.n_clusters is not None:
        clustering = AgglomerativeClustering(
            n_clusters=args.n_clusters,
            metric="cosine",
            linkage="average",
        )
        method = f"n_clusters={args.n_clusters}"
    else:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=args.distance_threshold,
            metric="cosine",
            linkage="average",
        )
        method = f"distance_threshold={args.distance_threshold}"

    labels = clustering.fit_predict(embeddings)

    rows = []
    for tag, cluster_id in zip(tags, labels):
        rows.append({
            "cluster_id": cluster_id,
            "tag": tag,
            "tag_count": tag_counts[tag],
            "tasks": "; ".join(sorted(tag_tasks[tag])),
        })

    df = pd.DataFrame(rows).sort_values(["cluster_id", "tag_count", "tag"])

    clusters_path = OUT_DIR / "tag_semantic_clusters.csv"
    df.drop(columns=["tag_count"]).to_csv(clusters_path, index=False)

    summary = (
        df.groupby("cluster_id")
        .agg(
            num_tags=("tag", "count"),
            tag_appearances=("tag_count", "sum"),
            tags=("tag", lambda x: "; ".join(x)),
        )
        .reset_index()
        .sort_values("tag_appearances", ascending=False)
    )

    summary_path = OUT_DIR / "tag_semantic_cluster_summary.csv"
    summary.to_csv(summary_path, index=False)

    print(f"Found {len(tags)} unique tags")
    print(f"Clustering method: {method}")
    print(f"Created {summary.shape[0]} clusters")
    print(f"Wrote {clusters_path}")
    print(f"Wrote {summary_path}")
    print()
    print(summary.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
