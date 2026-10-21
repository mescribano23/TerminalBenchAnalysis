"""Check descriptive RQ2.2 outputs without running analysis pipelines."""

import importlib
import unittest

import pandas as pd


time_estimates = importlib.import_module("scripts.analysis.tasks.01_analyze_time_estimates")
results = importlib.import_module("scripts.analysis.02_build_statistical_results")


class TimeDescriptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read = results.read_required
        cls.human = read(results.RQ2_2_HUMAN)
        cls.master = read(results.OUT_DEFAULT / "master_inferential_results.csv")
        cls.rq1 = read(results.RQ1_1)
        cls.rq12 = read(results.RQ1_2)
        cls.difficulty = read(results.RQ2_1)
        cls.behavior = read(results.RQ2_3)
        adjacent = read(results.ADJACENT_CHANGES)
        cls.performance = results.build_version_performance(adjacent)
        cls.instruction = results.build_release_comparisons(adjacent)
        cls.effort = results.build_effort_inference()

    def test_description_preserves_saved_values_and_task_populations(self):
        tasks = results.read_required(time_estimates.OUT_DEFAULT / "task_average_duration_comparison.csv")
        actual = time_estimates.build_rq2_2_time_description(tasks)
        pd.testing.assert_frame_equal(actual, self.human, rtol=1e-14, atol=1e-12)
        self.assertEqual(actual.comparison.tolist(), ["expert", "junior"])
        self.assertEqual(actual.n_tasks.tolist(), [88, 88])
        self.assertEqual(actual.success_only_eligible_tasks.tolist(), [86, 86])
        self.assertFalse(
            {"cohens_dz", "rank_biserial", "wilcoxon_statistic", "p_value", "nonzero_task_pairs"}
            & set(actual.columns)
        )

    def test_master_and_existing_validations_exclude_human_comparisons(self):
        actual = results.build_master(
            self.rq1, self.rq12, self.difficulty, self.behavior,
            self.performance, self.instruction, self.effort,
        )
        pd.testing.assert_frame_equal(actual, self.master, rtol=1e-14, atol=1e-12)
        self.assertEqual(len(actual), 38)
        self.assertFalse(actual.rq.eq("RQ2.2").any())
        results.validate_results(
            actual, self.rq1, self.behavior, self.performance, self.instruction, self.effort,
        )

    def test_saved_report_matches_formatter_and_keeps_rq2_2_descriptive(self):
        read = results.read_required
        report = results.build_report(
            self.master, self.rq1, self.rq12, self.difficulty,
            read(results.TASK_DIR / "rq2_2_media_exploratory.csv"), self.human,
            self.behavior, self.performance, self.instruction, self.effort,
            read(results.LONG_DIR / "rq3_3_shared_configuration_tokens_tb3_tb4.csv"),
        )
        self.assertEqual(report, results.REPORT_DEFAULT.read_text(encoding="utf-8"))
        section = report.split("### RQ2.2\n", 1)[1].split("### RQ2.3\n", 1)[0]
        for row in self.human.itertuples(index=False):
            self.assertIn(f"vs {row.comparison} estimate (descriptive only)", section)
        for marker in ("W =", "p =", "dz =", "r_rb =", "significant"):
            self.assertNotIn(marker, section)


if __name__ == "__main__":
    unittest.main()
