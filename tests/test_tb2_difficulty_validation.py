"""Held-out coverage, cached runs, and multiclass metric denominators."""

import contextlib
import importlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


labeler = importlib.import_module("scripts.analysis.longitudinal.02_label_task_difficulty")


class TB2DifficultyValidationTests(unittest.TestCase):
    def test_full_pool_excludes_all_eight_prompt_examples(self):
        metadata = labeler.load_tb2_validation_metadata(labeler.TB2_METADATA_DEFAULT)
        anchors = labeler.calibration_task_names()
        sample = labeler.select_validation_sample(
            metadata, per_difficulty=None, sample_seed=20260920, excluded_tasks=anchors,
        )
        self.assertEqual(len(metadata), 89)
        self.assertEqual(len(anchors), 8)
        self.assertTrue(anchors <= set(metadata.task_name))
        self.assertEqual(len(sample), 81)
        self.assertEqual(sample.difficulty.value_counts().to_dict(), {"medium": 52, "hard": 27, "easy": 2})
        self.assertFalse(anchors & set(sample.task_name))
        self.assertFalse(sample.task_name.duplicated().any())

    def test_historical_sample_is_subset_of_full_pool(self):
        metadata = labeler.load_tb2_validation_metadata(labeler.TB2_METADATA_DEFAULT)
        sample = labeler.select_validation_sample(
            metadata, per_difficulty=10, sample_seed=20260920,
            excluded_tasks=labeler.calibration_task_names(),
        )
        self.assertEqual(sample.difficulty.value_counts().to_dict(), {"medium": 10, "hard": 10, "easy": 2})
        # This compares selection against the original retained predictions.
        cached = labeler.load_existing_validation(labeler.VALIDATION_OUT_DEFAULT)
        self.assertTrue(set(sample.task_name) <= set(cached.task_name))
        with self.assertRaises(ValueError):
            labeler.select_validation_sample(metadata, per_difficulty=0, sample_seed=1, excluded_tasks=set())

    def test_imbalanced_metrics_with_no_easy_predictions(self):
        gold = pd.Series(["easy", "medium", "medium", "medium", "hard"], index=[9, 8, 7, 6, 5])
        predicted = pd.Series(["medium", "medium", "medium", "hard", "hard"])
        metrics = labeler.classification_metrics(gold, predicted)
        self.assertEqual(metrics["precision_easy"], 0)
        self.assertEqual(metrics["recall_easy"], 0)
        self.assertAlmostEqual(metrics["precision_macro"], 7 / 18)
        self.assertAlmostEqual(metrics["recall_macro"], 5 / 9)
        self.assertAlmostEqual(metrics["f1_macro"], 4 / 9)
        self.assertAlmostEqual(metrics["precision_weighted"], 0.5)
        self.assertAlmostEqual(metrics["recall_weighted"], 0.6)
        self.assertAlmostEqual(metrics["f1_weighted"], 8 / 15)
        for metric in ("precision", "recall", "f1"):
            self.assertAlmostEqual(metrics[f"{metric}_micro"], 0.6)

    def test_missing_class_still_counts_in_macro_average(self):
        metrics = labeler.classification_metrics(pd.Series(["hard"]), pd.Series(["hard"]))
        self.assertAlmostEqual(metrics["f1_macro"], 1 / 3)
        self.assertEqual(metrics["f1_weighted"], 1)
        with self.assertRaises(ValueError):
            labeler.classification_metrics(pd.Series(["hard"]), pd.Series([""]))

    def write_outputs(self, root, rows, expected):
        return labeler.write_validation_outputs(
            root / "labels.csv", root / "summary.csv", root / "confusion.csv", rows,
            include_diagnostics=True, expected_tasks=expected,
        )

    def test_consensus_and_individual_metrics_exclude_errors_and_recompute_correctness(self):
        gold = ["easy", "medium", "medium", "medium", "hard"]
        predictions = ["medium", "medium", "medium", "hard", "hard"]
        rows = []
        for i, (actual, predicted) in enumerate(zip(gold, predictions)):
            votes = [
                {"provider": spec.provider, "model": spec.model, "label": predicted, "error": ""}
                for spec in labeler.DIFFICULTY_LABELERS
            ]
            rows.append({
                "task_name": f"task-{i}", "gold_difficulty_label": actual,
                "llm_difficulty_label": predicted, "correct": False,
                "label_source": "consensus", "llm_model": labeler.DIFFICULTY_PANEL,
                "neutralization_model": labeler.DIFFICULTY_NEUTRALIZER.id,
                "consensus_vote_count": 3, "consensus_status": "unanimous",
                "consensus_votes_json": json.dumps(votes),
            })
        rows.append({"task_name": "failed", "gold_difficulty_label": "easy",
                     "llm_difficulty_label": "", "label_source": "error"})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary, confusion = self.write_outputs(root, rows, expected=7)
            self.assertEqual(len(summary), 4)
            self.assertTrue(summary.n_expected_tasks.eq(7).all())
            self.assertTrue(summary.n_tasks.eq(5).all())
            self.assertTrue(summary.n_unscored_tasks.eq(2).all())
            self.assertTrue(summary.n_correct.eq(3).all())
            self.assertTrue(summary.accuracy.eq(0.6).all())
            self.assertFalse(summary.validation_complete.any())
            self.assertEqual(confusion.n.sum(), 5)
            self.assertEqual(len(pd.read_csv(root / "labels.csv")), 6)
            self.assertAlmostEqual(summary.iloc[0].f1_weighted, 8 / 15)

    def test_bad_panel_provenance_is_rejected(self):
        rows = [{"task_name": "invalid", "gold_difficulty_label": "easy",
                 "llm_difficulty_label": "easy", "label_source": "consensus"}]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                self.write_outputs(Path(directory), rows, expected=1)

    def test_cached_only_run_reports_partial_coverage_without_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cached = labeler.load_existing_validation(labeler.VALIDATION_OUT_DEFAULT)
            # Keep just one existing row so this remains a partial-cache test
            # after the user completes the expanded run.
            cached.iloc[:1].to_csv(root / "labels.csv", index=False)
            argv = ["label", "--validate-native-tb2-difficulty", "--limit", "0",
                    "--include-diagnostics", "--out", str(root / "labels.csv"),
                    "--validation-summary-out", str(root / "summary.csv"),
                    "--validation-confusion-out", str(root / "confusion.csv")]
            with patch("sys.argv", argv), patch.object(labeler, "preflight_provider") as preflight, \
                    patch.object(labeler, "label_task") as call, contextlib.redirect_stdout(io.StringIO()) as output:
                labeler.main()
            preflight.assert_not_called()
            call.assert_not_called()
            summary = pd.read_csv(root / "summary.csv")
            self.assertTrue(summary.n_expected_tasks.eq(81).all())
            self.assertTrue(summary.n_tasks.eq(1).all())
            self.assertIn("INCOMPLETE validation", output.getvalue())

    def test_complete_cache_requires_no_providers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cached = labeler.load_existing_validation(labeler.VALIDATION_OUT_DEFAULT)
            cached.to_csv(root / "labels.csv", index=False)
            argv = ["label", "--validate-native-tb2-difficulty", "--validation-per-difficulty", "10",
                    "--include-diagnostics", "--out", str(root / "labels.csv"),
                    "--validation-summary-out", str(root / "summary.csv"),
                    "--validation-confusion-out", str(root / "confusion.csv")]
            with patch("sys.argv", argv), patch.object(labeler, "preflight_provider") as preflight, \
                    patch.object(labeler, "label_task") as call, contextlib.redirect_stdout(io.StringIO()):
                labeler.main()
            preflight.assert_not_called()
            call.assert_not_called()
            summary = pd.read_csv(root / "summary.csv")
            self.assertTrue(summary.validation_complete.all())
            self.assertTrue(summary.n_tasks.eq(22).all())
            # Consensus score of the original 22-task cache is preserved.
            self.assertEqual(summary.iloc[0].n_correct, 14)


if __name__ == "__main__":
    unittest.main()
