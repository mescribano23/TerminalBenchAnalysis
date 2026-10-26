"""Agreement coefficients, vote completeness, and reused labeling units."""

import importlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


reliability = importlib.import_module("scripts.analysis.longitudinal.11_analyze_label_reliability")


class LabelReliabilityTests(unittest.TestCase):
    def test_krippendorff_published_binary_example(self):
        # Krippendorff, Computing Alpha-Reliability, section A:
        # 20 ratings; pooled counts 14 and 6; four disagreeing units.
        counts = [[1, 1], [2, 0], [2, 0], [2, 0], [1, 1],
                  [2, 0], [2, 0], [1, 1], [0, 2], [1, 1]]
        result = reliability.reliability_from_counts(counts)
        self.assertAlmostEqual(result["fleiss_kappa"], 1 / 21)
        self.assertAlmostEqual(result["krippendorff_alpha_nominal"], 2 / 21)
        self.assertAlmostEqual(result["krippendorff_alpha_ordinal"], 2 / 21)
        self.assertAlmostEqual(result["raw_pairwise_agreement"], 0.6)

    def test_perfect_agreement_across_multiple_classes(self):
        result = reliability.reliability_from_counts([[3, 0, 0], [0, 3, 0], [0, 0, 3]])
        for name in ("fleiss_kappa", "krippendorff_alpha_nominal", "krippendorff_alpha_ordinal"):
            self.assertEqual(result[name], 1)

    def test_unanimous_one_class_is_undefined_not_perfect_reliability(self):
        result = reliability.reliability_from_counts([[0, 0, 3], [0, 0, 3]])
        self.assertEqual(result["raw_pairwise_agreement"], 1)
        for name in ("fleiss_kappa", "krippendorff_alpha_nominal", "krippendorff_alpha_ordinal"):
            self.assertTrue(np.isnan(result[name]))

    def test_three_way_disagreement_can_have_negative_reliability(self):
        result = reliability.reliability_from_counts([[1, 1, 1], [1, 1, 1]])
        self.assertAlmostEqual(result["fleiss_kappa"], -0.5)
        self.assertAlmostEqual(result["krippendorff_alpha_nominal"], -0.25)
        self.assertEqual(result["n_unanimous"], 0)

    def test_alpha_finite_sample_identity_and_absent_class(self):
        counts = [[0, 1, 2], [0, 0, 3], [0, 3, 0], [0, 1, 2]]
        result = reliability.reliability_from_counts(counts)
        self.assertAlmostEqual(result["krippendorff_alpha_nominal"],
                               1 - (1 - result["fleiss_kappa"]) * 11 / 12)
        self.assertAlmostEqual(result["krippendorff_alpha_nominal"], result["krippendorff_alpha_ordinal"])

    def test_invalid_counts_rejected(self):
        for counts in ([], [[1, 0], [1, 2]], [[-1, 4]], [[1.5, 1.5]], [[np.nan, 3]]):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                reliability.reliability_from_counts(counts)

    def test_complete_tie_included_without_consensus_or_gold(self):
        row = {
            "task_name": "test", "llm_model": reliability.DIFFICULTY_PANEL,
            "neutralization_model": reliability.DIFFICULTY_NEUTRALIZER.id,
            "consensus_votes_json": json.dumps([
                {"provider": spec.provider, "model": spec.model, "label": label, "error": ""}
                for spec, label in zip(reliability.DIFFICULTY_LABELERS, reliability.LABELS)
            ]),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "votes.csv"
            pd.DataFrame([row]).to_csv(path, index=False)
            votes = reliability.load_difficulty_votes(path, "test")
            self.assertEqual(votes[reliability.RATERS].iloc[0].tolist(), reliability.LABELS)
            # Blank/failed votes must never become a fourth category or be
            # imputed from the consensus.
            raw = json.loads(row["consensus_votes_json"])
            raw[1]["label"] = ""
            raw[1]["error"] = "backend error"
            row["consensus_votes_json"] = json.dumps(raw)
            pd.DataFrame([row]).to_csv(path, index=False)
            with self.assertRaises(ValueError):
                reliability.load_difficulty_votes(path, "test")

    def test_ordinal_reference_with_unequal_category_frequencies(self):
        # Pooled counts (4,5,3) give squared ordinal distances 20.25,72.25,16.
        # Observed disagreement sum=257.5; expected sum=3024/11.
        counts = np.array([[2, 1, 0], [0, 2, 1], [1, 0, 2], [1, 2, 0]])
        result = reliability.reliability_from_counts(counts)
        self.assertAlmostEqual(result["krippendorff_alpha_ordinal"], 383 / 6048)

    def test_reused_evidence_deduplicated_but_changed_evidence_retained(self):
        metadata = pd.DataFrame([
            {"benchmark_version": "3.0", "task_name": "same", "description": "original"},
            {"benchmark_version": "4.0", "task_name": "same", "description": "original"},
            {"benchmark_version": "3.0", "task_name": "changed", "description": "old"},
            {"benchmark_version": "4.0", "task_name": "changed", "description": "new"},
        ])
        votes = metadata[["benchmark_version", "task_name"]].copy()
        for rater in reliability.RATERS:
            votes[rater] = "hard"
        assigned = reliability.assign_production_units(votes, metadata)
        self.assertEqual(assigned.labeling_unit_id.nunique(), 3)
        votes.loc[1, reliability.RATERS[0]] = "medium"
        with self.assertRaises(ValueError):
            reliability.assign_production_units(votes, metadata)


if __name__ == "__main__":
    unittest.main()
