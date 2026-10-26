#!/usr/bin/env python3
"""Compute inter-LLM difficulty reliability from saved votes; no API calls.

Report nominal Fleiss' kappa, nominal Krippendorff's alpha, and ordinal alpha
(easy < medium < hard). Analyze TB2 validation separately from TB3/TB4;
deduplicate reused TB3/TB4 labeling units using the labeler's evidence identity.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.analysis.longitudinal.difficulty_protocol import (
    DIFFICULTY_LABELERS, DIFFICULTY_NEUTRALIZER, DIFFICULTY_PANEL,
)

labeling = importlib.import_module("scripts.analysis.longitudinal.02_label_task_difficulty")
RATERS = [spec.id for spec in DIFFICULTY_LABELERS]
LABELS = ["easy", "medium", "hard"]
OUT_DEFAULT = labeling.LONGITUDINAL_DIR / "label_reliability"
REPORT_DEFAULT = REPO_ROOT / "reports/longitudinal/llm_label_reliability.md"


def reliability_from_counts(counts: np.ndarray) -> dict[str, float | int]:
    """Complete, equally sized panels; nominal and frequency-based ordinal alpha.

    Alpha uses observed coincidences sum((outer(n_i,n_i)-diag(n_i))/(r-1))
    and expected coincidences (outer(m,m)-diag(m))/(T-1). Ordinal distances
    are squared differences of pooled-frequency midranks, not fixed 1/2/3
    interval distances. One-class data have undefined chance-corrected scores.
    """
    counts = np.asarray(counts, dtype=float)
    if counts.ndim != 2 or not counts.size or not np.isfinite(counts).all():
        raise ValueError("Counts must be a nonempty, finite task-by-category matrix.")
    if (counts < 0).any() or not np.equal(counts, np.floor(counts)).all():
        raise ValueError("Category counts must be nonnegative integers.")
    totals = counts.sum(axis=1)
    if totals[0] < 2 or not np.equal(totals, totals[0]).all():
        raise ValueError("Each task must have the same number of ratings, at least two.")
    n_tasks, n_raters = len(counts), int(totals[0])
    marginals = counts.sum(axis=0)
    n_ratings = float(marginals.sum())
    observed = float(((counts * (counts - 1)).sum(axis=1) / (n_raters * (n_raters - 1))).mean())
    expected = float(((marginals / n_ratings) ** 2).sum())
    kappa = (observed - expected) / (1 - expected) if expected < 1 else float("nan")

    coincidences = (counts.T @ counts - np.diag(marginals)) / (n_raters - 1)
    expected_coincidences = (np.outer(marginals, marginals) - np.diag(marginals)) / (n_ratings - 1)
    nominal_distances = np.ones((len(marginals), len(marginals))) - np.eye(len(marginals))
    midranks = np.cumsum(marginals) - marginals / 2
    ordinal_distances = (midranks[:, None] - midranks[None, :]) ** 2

    def alpha(distances: np.ndarray) -> float:
        do = float((coincidences * distances).sum())
        de = float((expected_coincidences * distances).sum())
        return 1 - do / de if de > 0 else float("nan")

    return {
        "n_tasks": n_tasks, "n_raters": n_raters, "n_ratings": int(n_ratings),
        "n_unanimous": int((counts.max(axis=1) == n_raters).sum()),
        "raw_pairwise_agreement": observed, "chance_agreement": expected,
        "fleiss_kappa": kappa,
        "krippendorff_alpha_nominal": alpha(nominal_distances),
        "krippendorff_alpha_ordinal": alpha(ordinal_distances),
    }


def load_difficulty_votes(path: Path, dataset: str) -> pd.DataFrame:
    """Validate the actual votes, including complete three-way ties if present.

    The gold and consensus labels are deliberately not used as raters, and
    consensus correctness/agreement is never a selection criterion.
    """
    raw = pd.read_csv(path, dtype={"benchmark_version": str})
    required = {"task_name", "llm_model", "neutralization_model", "consensus_votes_json"}
    if not required <= set(raw.columns) or raw.empty:
        raise ValueError(f"{path}: missing difficulty vote provenance or no rows.")
    keys = ["benchmark_version", "task_name"] if "benchmark_version" in raw else ["task_name"]
    if raw.duplicated(keys).any():
        raise ValueError(f"{path}: duplicate task/version rows.")
    result = []
    for _, row in raw.iterrows():
        if row.llm_model != DIFFICULTY_PANEL or row.neutralization_model != DIFFICULTY_NEUTRALIZER.id:
            raise ValueError(f"{path}: {row.task_name}: incompatible panel or neutralizer.")
        votes = json.loads(row.consensus_votes_json)
        by_rater = {f"{v['provider']}:{v['model']}": v for v in votes}
        if len(votes) != 3 or set(by_rater) != set(RATERS):
            raise ValueError(f"{path}: {row.task_name}: expected one vote from each of three LLMs.")
        if any(v.get("error") or v.get("label") not in LABELS for v in votes):
            raise ValueError(f"{path}: {row.task_name}: missing, failed, or invalid LLM vote.")
        result.append({
            "dataset": dataset, "benchmark_version": row.get("benchmark_version", "2.0"),
            "task_name": row.task_name, **{rater: by_rater[rater]["label"] for rater in RATERS},
        })
    return pd.DataFrame(result)


def assign_production_units(votes: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
    """Reuse exactly the evidence-identity rule used when generating labels."""
    metadata_index = {
        (str(row.benchmark_version), row.task_name): row for _, row in metadata.iterrows()
    }
    identities = []
    for _, row in votes.iterrows():
        key = (str(row.benchmark_version), row.task_name)
        if key not in metadata_index:
            raise ValueError(f"No production metadata for {key}.")
        identities.append(labeling.unchanged_task_key(metadata_index[key]))
    unit_ids = {identity: f"production-{i:03d}" for i, identity in enumerate(sorted(set(identities)), 1)}
    out = votes.copy()
    out["labeling_unit_id"] = [unit_ids[identity] for identity in identities]
    for unit_id, group in out.groupby("labeling_unit_id"):
        if len(group[RATERS].drop_duplicates()) != 1:
            raise ValueError(f"Reused evidence {unit_id} has inconsistent votes; cannot deduplicate.")
    return out


def summarize(votes: pd.DataFrame, pool: str) -> dict:
    matrix = votes[RATERS].to_numpy()
    counts = np.column_stack([(matrix == label).sum(axis=1) for label in LABELS])
    return {"pool": pool, **reliability_from_counts(counts),
            **{f"n_votes_{label}": int(counts[:, i].sum()) for i, label in enumerate(LABELS)}}


def audit_category_votes(path: Path) -> pd.DataFrame:
    """Expose incomplete category panels without treating errors as categories."""
    raw = pd.read_csv(path)
    rows = []
    for rater in RATERS:
        valid, failed, missing = 0, 0, 0
        for value in raw.consensus_votes_json:
            votes = [v for v in json.loads(value) if f"{v.get('provider')}:{v.get('model')}" == rater]
            if len(votes) != 1:
                missing += 1
            elif votes[0].get("error") or not votes[0].get("label"):
                failed += 1
            else:
                valid += 1
        rows.append({"dataset": "TB2 category labels", "rater": rater, "n_tasks": len(raw),
                     "n_valid_votes": valid, "n_failed_votes": failed, "n_missing_votes": missing})
    return pd.DataFrame(rows)


def write_report(path: Path, summary: pd.DataFrame, audit: pd.DataFrame, out_dir: Path) -> None:
    by_pool = summary.set_index("pool")
    tb2 = by_pool.loc["TB2 held-out validation"]
    tb3 = by_pool.loc["TB3 task-version rows"]
    tb4 = by_pool.loc["TB4 task-version rows"]
    unique = by_pool.loc["TB3/TB4 distinct labeling units"]
    pooled = by_pool.loc["TB3/TB4 pooled task-version rows"]
    try:
        output_label = out_dir.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        output_label = out_dir.resolve().as_posix()

    def table_row(row) -> str:
        return (f"| {row.pool} | {row.n_tasks} | {row.n_unanimous} | "
                f"{row.raw_pairwise_agreement:.2%} | {row.chance_agreement:.2%} | "
                f"{row.fleiss_kappa:.4f} | {row.krippendorff_alpha_nominal:.4f} | "
                f"{row.krippendorff_alpha_ordinal:.4f} |")

    lines = [
        "# Inter-LLM difficulty-label reliability", "",
        "These coefficients measure agreement among the three saved LLM votes, not accuracy",
        "against native labels. Neither the native label nor the majority consensus is a fourth rater.",
        "No new LLM calls were made.", "",
        "## Results", "",
        "| Pool | Units | Unanimous | Raw pairwise agreement | Chance agreement | Fleiss kappa | Alpha nominal | Alpha ordinal |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        *[table_row(row) for row in summary.itertuples()], "",
        "All analyzed difficulty rows have one valid vote from each of GPT-4o mini,",
        "Claude Haiku 4.5, and Qwen2.5 7B, after GPT-4o mini neutralization.",
        "Complete three-way ties would also be included: reliability is calculated before consensus.", "",
        "## Units and interpretation", "",
        f"TB2 validation covers all {int(tb2.n_tasks)} non-calibration tasks; the eight labeled prompt examples are excluded.",
        "It is reported separately from production TB3/TB4 because the task populations and vote",
        "distributions differ. Pooling these populations would change the chance-agreement baseline.", "",
        f"TB3 and TB4 contain {int(tb3.n_tasks)} and {int(tb4.n_tasks)} task-version rows, respectively. Across versions, {int(pooled.n_tasks - unique.n_tasks)} rows",
        "reuse another row's label/votes for unchanged task evidence. The production labeling-unit",
        f"analysis counts each of the {int(unique.n_tasks)} distinct evidence identities once, using the same identity",
        "rule as the labeling script. Changed evidence for the same task name remains a separate unit.",
        f"The {int(pooled.n_tasks)}-row pooled result is a descriptive sensitivity that counts reused results again;",
        f"it is not {int(pooled.n_tasks)} separate labeling decisions. Units sharing a task name can remain related.", "",
        "TB2 has substantially more chance-corrected agreement than TB3/TB4. Production votes are",
        f"predominantly hard ({int(pooled.n_votes_hard)}/{int(pooled.n_ratings)} across task-version rows), with {int(pooled.n_votes_easy)} easy votes. This makes",
        f"expected chance agreement very high, explaining why {pooled.raw_pairwise_agreement:.2%} raw pairwise",
        "agreement coexists with low kappa/alpha. Raw agreement alone does not establish strong",
        "reliability in distinguishing difficulty classes. High reliability would not by itself",
        "establish correctness against native labels or empirical difficulty.", "",
        "The raters share a prompt, calibration examples, and neutralized evidence; GPT-4o mini",
        "also supplies the neutralization. The coefficients describe agreement within this",
        "specific panel and workflow. They do not establish independent judgments or",
        "generalization to other models, prompts, or repeated stochastic runs.", "",
        "## Definitions and computation", "",
        "Fleiss' kappa is nominal: all different labels count as disagreements. For task i,",
        "category counts n_ic, and r=3 raters, P_i = sum_c n_ic(n_ic-1)/(r(r-1)).",
        "Raw agreement P_o is the mean P_i. With pooled vote proportions p_c,",
        "chance agreement P_e = sum_c p_c^2 and kappa = (P_o-P_e)/(1-P_e).",
        "Raw pairwise agreement is the mean agreement over the three model pairs,",
        "not the proportion of tasks with unanimous votes.", "",
        "The usual Krippendorff statistic is **alpha**, not 'Krippendorff kappa'.",
        "Alpha = 1 - observed disagreement / expected disagreement. Nominal alpha uses",
        "a distance of zero for matching labels and one otherwise; unlike Fleiss' kappa,",
        "its expected disagreement uses sampling without replacement. For a complete panel",
        "with T ratings, alpha_nominal = 1 - (1-kappa)(T-1)/T. This finite-sample correction",
        "explains the small difference between the nominal coefficients.", "",
        "Difficulty is ordered easy < medium < hard, so ordinal alpha is reported as an",
        "additional measure. It uses squared differences of pooled-frequency midranks:",
        "delta(c,k)^2 = (sum_{g=c..k} n_g - (n_c+n_k)/2)^2 for c<k.",
        "This is Krippendorff's ordinal distance, not squared differences of fixed 1/2/3 scores.",
        "Where only medium/hard are observed, ordinal and nominal alpha coincide.",
        "If every rating uses a single category, chance-corrected coefficients are undefined",
        "and are exported as NaN rather than interpreted as perfect reliability.", "",
        "These are descriptive point estimates; no confidence intervals or significance tests are claimed.", "",
        "## Category-label coverage audit", "",
        "The separate TB2 category cache has incomplete three-model panels:", "",
        "| Rater | Tasks | Valid votes | Failed votes | Missing votes |",
        "| --- | ---: | ---: | ---: | ---: |",
        *[f"| {r.rater} | {r.n_tasks} | {r.n_valid_votes} | {r.n_failed_votes} | {r.n_missing_votes} |" for r in audit.itertuples()],
        "",
        "The retained Haiku category calls failed with an unexpected `temperature` argument.",
        "Consequently, a three-LLM category reliability coefficient cannot be calculated from",
        "that cache. Missing votes must not be counted as a category or replaced by the consensus.",
        "This does not affect the complete three-vote difficulty analyses above. Category labels",
        "would need a separate repair/rerun before reporting three-model category reliability.", "",
        "## Reproduction and sources", "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe -m scripts.analysis.longitudinal.11_analyze_label_reliability",
        "```", "",
        f"Outputs: `{output_label}/` contains `summary.csv`,",
        "`difficulty_votes.csv` (one column per LLM, with labeling-unit IDs), and",
        "`category_vote_coverage.csv`. All computations use existing NumPy/pandas dependencies.", "",
        "The implementation was independently checked against statsmodels 0.15.0 and",
        "krippendorff 0.9.0 on all five reported pools; all coefficients matched within 1e-12.",
        "Nominal and ordinal alpha were also checked on 100 random complete panels.",
        "Reference packages were installed in a temporary directory for verification;",
        "they are not required to run this script. Unit tests cover a published worked",
        "example, ordinal distances, negative/undefined coefficients, missing votes,",
        "three-way ties, and deduplication of reused evidence.", "",
        "Fleiss calculation follows the [statsmodels implementation](https://www.statsmodels.org/stable/_modules/statsmodels/stats/inter_rater.html).",
        "Alpha and its measurement-level distances follow [Krippendorff, Computing Alpha-Reliability](https://www.asc.upenn.edu/sites/default/files/2021-03/Computing%20Krippendorff%27s%20Alpha-Reliability.pdf).",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tb2-labels", type=Path, default=labeling.VALIDATION_OUT_DEFAULT)
    parser.add_argument("--production-labels", type=Path, default=labeling.OUT_DEFAULT)
    parser.add_argument("--production-metadata", type=Path, default=labeling.TB3_TB4_ENRICHED_METADATA_DEFAULT)
    parser.add_argument("--category-labels", type=Path, default=labeling.LONGITUDINAL_DIR / "inputs/tb2_task_category_llm_labels.csv")
    parser.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--report", type=Path, default=REPORT_DEFAULT)
    args = parser.parse_args()

    tb2 = load_difficulty_votes(args.tb2_labels, "TB2 validation")
    gold_metadata = labeling.load_tb2_validation_metadata(labeling.TB2_METADATA_DEFAULT)
    expected_tasks = set(gold_metadata.task_name) - labeling.calibration_task_names()
    if len(tb2) != len(expected_tasks) or set(tb2.task_name) != expected_tasks:
        raise ValueError("TB2 must contain all and only non-calibration validation tasks.")
    tb2["labeling_unit_id"] = "tb2-" + tb2.task_name
    production = load_difficulty_votes(args.production_labels, "TB3/TB4 production")
    production = assign_production_units(production, labeling.load_metadata([args.production_metadata]))
    unique = production.drop_duplicates("labeling_unit_id")
    summary = pd.DataFrame([
        summarize(tb2, "TB2 held-out validation"),
        summarize(production[production.benchmark_version.eq("3.0")], "TB3 task-version rows"),
        summarize(production[production.benchmark_version.eq("4.0")], "TB4 task-version rows"),
        summarize(unique, "TB3/TB4 distinct labeling units"),
        summarize(production, "TB3/TB4 pooled task-version rows"),
    ])
    audit = audit_category_votes(args.category_labels)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.out_dir / "summary.csv", index=False)
    pd.concat([tb2, production], ignore_index=True).to_csv(args.out_dir / "difficulty_votes.csv", index=False)
    audit.to_csv(args.out_dir / "category_vote_coverage.csv", index=False)
    write_report(args.report, summary, audit, args.out_dir)
    print(summary.to_string(index=False))
    print(f"Wrote reliability artifacts: {args.out_dir}")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
