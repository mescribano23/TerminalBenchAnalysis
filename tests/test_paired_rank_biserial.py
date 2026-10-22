"""Focused signed-rank checks; no model fitting, raw JSON parsing or plotting."""

import csv
import hashlib
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from scripts.analysis.statistical_helpers import (
    numeric_values, paired_rank_biserial, two_sided_signed_rank,
)


results = importlib.import_module("scripts.analysis.02_build_statistical_results")
rq1 = importlib.import_module("scripts.analysis.diminishing_returns.00_analyze_effort_success")
tools = importlib.import_module("scripts.analysis.tasks.02_analyze_tool_use")


def signed_sums(differences):
    nonzero = numeric_values(differences)
    nonzero = nonzero[nonzero != 0]
    ranks = rankdata(abs(nonzero), method="average")
    return ranks[nonzero > 0].sum(), ranks[nonzero < 0].sum(), len(nonzero)


def saved_rows(path):
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.reader(handle))
    fixture = Path(__file__).parent / "fixtures" / "paired_wilcoxon_preserved_results.json"
    return json.loads(fixture.read_text(encoding="utf-8"))[path.relative_to(results.REPO_ROOT).as_posix()]["rows"]


def saved_inference(path):
    buffer = io.StringIO()
    csv.writer(buffer).writerows(saved_rows(path))
    buffer.seek(0)
    return pd.read_csv(buffer)


def preserved_cells_digest(path, excluded):
    rows = saved_rows(path)
    indices = [i for i, column in enumerate(rows[0]) if column not in excluded]
    cells = [[row[i] for i in indices] for row in rows]
    return hashlib.sha256(json.dumps(cells, ensure_ascii=False).encode("utf-8")).hexdigest()


class RankBiserialTests(unittest.TestCase):
    def test_positive_negative_and_single_pair(self):
        self.assertEqual(paired_rank_biserial([1, 2, 3]), 1)
        self.assertEqual(paired_rank_biserial([-1, -2, -3]), -1)
        self.assertEqual(paired_rank_biserial([2]), 1)

    def test_balanced_signed_ranks(self):
        self.assertEqual(paired_rank_biserial([1, -2, -3, 4]), 0)

    def test_exact_zeros_are_excluded_but_tiny_values_are_ranked(self):
        self.assertEqual(paired_rank_biserial([0, -0.0, 1, -2]), -1 / 3)
        self.assertEqual(paired_rank_biserial([0, 1e-20]), 1)

    def test_tied_absolute_values_use_average_ranks(self):
        # |D| ranks: 1.5, 1.5, 3; R+=4.5 and R-=1.5.
        self.assertEqual(paired_rank_biserial([1, -1, 2]), 0.5)

    def test_missing_and_nonfinite_values_match_test_filtering(self):
        differences = [None, np.nan, np.inf, -np.inf, "bad", "1", -2, 0]
        self.assertEqual(paired_rank_biserial(differences), -1 / 3)
        self.assertEqual(two_sided_signed_rank(differences), two_sided_signed_rank([1, -2, 0]))

    def test_empty_and_all_zero_are_undefined(self):
        for differences in ([], [None, np.inf], [0, -0.0, 0]):
            with self.subTest(differences=differences):
                self.assertTrue(np.isnan(paired_rank_biserial(differences)))
        self.assertEqual(two_sided_signed_rank([0, 0]), (0, 1, 0))
        statistic, p_value, n = two_sided_signed_rank([])
        self.assertTrue(np.isnan(statistic) and np.isnan(p_value))
        self.assertEqual(n, 0)

    def test_signed_sums_match_w_and_preserve_orientation(self):
        for differences in ([1, -1, 2, 0], [-5, 2, 4, -7, np.nan], [2, 2, 2]):
            positive, negative, nonzero = signed_sums(differences)
            statistic, _, count = two_sided_signed_rank(differences)
            self.assertEqual(count, nonzero)
            self.assertEqual(statistic, min(positive, negative))
            self.assertEqual(paired_rank_biserial(differences), (positive - negative) / (positive + negative))
            self.assertEqual(paired_rank_biserial(-np.asarray(differences)), -paired_rank_biserial(differences))


class SavedAnalysisTests(unittest.TestCase):
    def test_rq1_audited_vectors_and_original_aggregation(self):
        trajectories = rq1.load_data(rq1.INPUT_DEFAULT)
        saved = results.read_required(results.DIM_DIR / "rq1_within_task_effort_by_task.csv")
        for metric, expected in {
            "completion_tokens": (85, 85, 1944, 1711, 0.063748290, -29.5),
            "shell_invocation_count": (86, 81, 1825, 1496, 0.099066546, 0.375),
        }.items():
            with self.subTest(metric=metric):
                pairs, *_ = rq1.task_medians(trajectories, metric)
                differences = pairs.difference
                n, nonzero, positive, negative, effect, median = expected
                self.assertEqual(len(differences), n)
                self.assertEqual(signed_sums(differences), (positive, negative, nonzero))
                self.assertAlmostEqual(paired_rank_biserial(differences), effect, places=9)
                self.assertEqual(differences.median(), median)
                np.testing.assert_array_equal(differences, saved.loc[saved.metric.eq(metric), "within_task_difference_pass_minus_fail"])

    def test_rq1_all_effects_and_tests_match_original_vectors(self):
        detail = results.read_required(results.DIM_DIR / "rq1_within_task_effort_by_task.csv")
        for row in results.read_required(results.RQ1_1).itertuples(index=False):
            differences = detail.loc[detail.metric.eq(row.metric), "within_task_difference_pass_minus_fail"]
            statistic, p_value, _ = two_sided_signed_rank(differences)
            self.assertEqual(len(differences), row.eligible_tasks)
            self.assertEqual(differences.median(), row.median_task_difference)
            self.assertAlmostEqual(paired_rank_biserial(differences), row.rank_biserial, places=14)
            self.assertEqual(statistic, row.wilcoxon_statistic)
            self.assertAlmostEqual(p_value, row.p_value, places=14)

    def test_rq2_support_rule_and_used_minus_unused_direction(self):
        contrasts = pd.DataFrame({
            "behavior_family": ["inspect_search"] * 5,
            "task_name": list("abcde"), "support_ok": [True, True, True, False, True],
            "pass_rate_difference_pp": [1.0, -1.0, 2.0, -99.0, np.nan],
            "n_total": [10] * 5, "n_used": [5] * 5,
        })
        row = tools.summarize_functional_wilcoxon(contrasts).iloc[0]
        self.assertEqual(row.eligible_tasks, 3)
        self.assertEqual(row.rank_biserial, 0.5)
        self.assertEqual(row.mean_pass_rate_difference_pp, 2 / 3)
        self.assertEqual(row.median_pass_rate_difference_pp, 1)
        self.assertEqual((row.wilcoxon_statistic, row.p_value, row.nonzero_task_pairs), two_sided_signed_rank([1, -1, 2]))

    def test_version_performance_matches_original_pairs(self):
        actual = results.build_version_performance(results.read_required(results.ADJACENT_CHANGES))
        saved = saved_inference(results.LONG_DIR / "rq3_1_version_performance_inference.csv")
        pd.testing.assert_frame_equal(actual, saved, rtol=1e-13, atol=1e-12)

    def test_primary_effort_matches_original_pairs(self):
        actual = results.build_effort_inference()
        saved = saved_inference(results.LONG_DIR / "rq3_3_effort_inference.csv")
        # The historical pooled headline fields are no longer exported. The
        # shared-task medians and every inferential quantity must stay intact.
        saved = saved.drop(columns=["old_headline_median", "new_headline_median",
                                    "reported_percentage_change", "headline_aggregation"])
        pd.testing.assert_frame_equal(actual, saved, rtol=1e-13, atol=1e-12)

    def test_effort_sensitivity_writer_preserves_newer_minus_older(self):
        effort = importlib.import_module("scripts.analysis.longitudinal.08_analyze_effort_changes")
        rows = []
        for task, difference in zip("abc", [1, -2, 3]):
            for version, value in [("2.0", 10), ("2.1", 10 + difference)]:
                row = {"task_name": task, "benchmark_version": version,
                       "source_submission_id": task + version, "submission_id": task + version,
                       "source_submission_url": task + version}
                row.update({metric["column"]: value for metric in effort.METRICS})
                rows.append(row)
        with tempfile.TemporaryDirectory() as directory, patch.object(effort, "plot"):
            path = Path(directory)
            inference = effort.write_balanced_exports(pd.DataFrame(rows), set(), "2.0", "2.1", path,
                                                     path / "unused.png", include_sensitivities=True)
        self.assertEqual(len(inference), 10)
        for row in inference:
            self.assertEqual(row["rank_biserial"], 1 / 3)
            self.assertEqual(row["eligible_tasks"], 3)
            self.assertEqual(row["median_paired_task_difference"], 1)
            self.assertEqual((row["wilcoxon_statistic"], row["p_value"], row["nonzero_task_pairs"]),
                             two_sided_signed_rank([1, -2, 3]))

    def test_all_other_saved_cells_match_pre_correction_snapshot(self):
        fixture = Path(__file__).parent / "fixtures" / "paired_wilcoxon_preserved_results.json"
        for relative, baseline in json.loads(fixture.read_text(encoding="utf-8")).items():
            with self.subTest(path=relative):
                self.assertEqual(preserved_cells_digest(results.REPO_ROOT / relative, baseline["excluded"]), baseline["sha256"])
                if "independent_rows_sha256" in baseline:
                    with (results.REPO_ROOT / relative).open(encoding="utf-8", newline="") as handle:
                        rows = list(csv.reader(handle))
                    test_index = rows[0].index("test")
                    independent = [rows[0]] + [row for row in rows[1:] if row[test_index] != "two-sided Wilcoxon signed-rank"]
                    self.assertEqual(hashlib.sha256(json.dumps(independent, ensure_ascii=False).encode("utf-8")).hexdigest(),
                                     baseline["independent_rows_sha256"])


if __name__ == "__main__":
    unittest.main()
