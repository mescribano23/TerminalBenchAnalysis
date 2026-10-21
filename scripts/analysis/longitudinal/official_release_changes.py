"""Official release grouping for RQ3.1 only; instruction audits remain metadata."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
LONG = ROOT / "data/processed_live/longitudinal"
CROSSWALK = LONG / "inputs/official_release_task_crosswalk.csv"
EXPECTED = {"2.0->2.1": (28, 61), "3.0->4.0": (19, 47)}
LABELS = {"fixed": "Release-fixed", "not_listed_as_fixed": "Not listed as fixed"}


def load_crosswalk(path: Path = CROSSWALK) -> pd.DataFrame:
    crosswalk = pd.read_csv(path, keep_default_na=False)
    if crosswalk.duplicated(["version_pair", "task_name"]).any():
        raise ValueError("Duplicate official crosswalk task IDs")
    if set(crosswalk.version_pair) != set(EXPECTED) or not crosswalk.task_name.eq(crosswalk.official_task_id).all():
        raise ValueError("Unexpected transition or non-exact official task ID mapping")
    for pair, counts in EXPECTED.items():
        group = crosswalk[crosswalk.version_pair.eq(pair)]
        shared = group[group.release_status.ne("removed")]
        observed = tuple(int(shared.release_status.eq(status).sum())
                         for status in ["fixed", "not_listed_as_fixed"])
        if observed != counts or len(shared) != sum(counts):
            raise ValueError(f"{pair}: unexpected official release counts {observed}")
        removed = group[group.release_status.eq("removed")]
        if len(removed) != (8 if pair == "3.0->4.0" else 0):
            raise ValueError(f"{pair}: unexpected removed task count")
        if not shared.in_old.eq(1).all() or not shared.in_new.eq(1).all() or not removed.in_new.eq(0).all():
            raise ValueError(f"{pair}: release classification conflicts with dataset membership")
    return crosswalk


def add_release_status(adjacent: pd.DataFrame, pair: str,
                       crosswalk: pd.DataFrame | None = None) -> pd.DataFrame:
    crosswalk = load_crosswalk() if crosswalk is None else crosswalk
    metadata = crosswalk[crosswalk.version_pair.eq(pair) & crosswalk.release_status.ne("removed")]
    group = adjacent[adjacent.version_pair.eq(pair)].copy()
    if group.task_name.duplicated().any() or set(group.task_name) != set(metadata.task_name):
        raise ValueError(f"{pair}: paired task IDs differ from official crosswalk")
    if not group.submission_unit.eq("source").all() or not group.task_weighting.eq("submission-balanced").all():
        raise ValueError("RQ3.1 requires source-submission-balanced task pass rates")
    if group[["task_weighted_pass_rate_old", "task_weighted_pass_rate_new"]].isna().any().any():
        raise ValueError(f"{pair}: missing paired pass rates")
    group = group.merge(metadata.drop(columns="version_pair"), on="task_name", validate="one_to_one")
    group["improvement_pp"] = 100 * (group.task_weighted_pass_rate_new - group.task_weighted_pass_rate_old)
    return group


def build_release_summary(adjacent: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pair in EXPECTED:
        group = add_release_status(adjacent, pair)
        for status, subset in [("all_tasks", group)] + [
            (status, group[group.release_status.eq(status)])
            for status in ["not_listed_as_fixed", "fixed"]
        ]:
            rows.append(dict(version_pair=pair, task_set=status,
                label=LABELS.get(status, "All shared tasks"), n_tasks=len(subset),
                old_pass_rate=100 * subset.task_weighted_pass_rate_old.mean(),
                new_pass_rate=100 * subset.task_weighted_pass_rate_new.mean(),
                mean_change_pp=subset.improvement_pp.mean(), median_change_pp=subset.improvement_pp.median(),
                min_change_pp=subset.improvement_pp.min(), max_change_pp=subset.improvement_pp.max()))
    return pd.DataFrame(rows)
