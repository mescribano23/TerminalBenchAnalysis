"""Verify RQ1.2 reporting from saved results without refitting any model."""

import importlib
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd


analysis = importlib.import_module("scripts.analysis.diminishing_returns.00_analyze_effort_success")
results = importlib.import_module("scripts.analysis.02_build_statistical_results")


class RegressionReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = pd.read_csv(analysis.OUT_DEFAULT / "rq1_final_statistical_results.csv")
        cls.compact = pd.read_csv(results.RQ1_2)

    def test_export_matches_saved_results_without_refitting(self):
        with patch.object(analysis, "fit_quadratic_conditional_logit", side_effect=AssertionError("Unexpected refit")):
            actual = analysis.rq1_2_regression_table(self.full)
        pd.testing.assert_frame_equal(actual, self.compact, check_exact=True)
        self.assertEqual(actual.columns[:4].tolist(), ["metric", "beta_1", "beta_2", "p_value_beta_2"])
        self.assertEqual(actual.metric.tolist(), analysis.METRICS)
        self.assertTrue(actual.vertex_strictly_inside_range.all())

    def test_vertex_support_is_strict_and_handles_missing_values(self):
        table = self.full.iloc[:4].copy()
        table.loc[table.index[0], "turning_point_z"] = table.iloc[0].z_min
        table.loc[table.index[1], "turning_point_z"] = table.iloc[1].z_max
        table.loc[table.index[2], "turning_point_z"] = np.nextafter(table.iloc[2].z_min, np.inf)
        table.loc[table.index[3], "turning_point_z"] = np.nan
        actual = analysis.rq1_2_regression_table(table)
        self.assertEqual(actual.vertex_strictly_inside_range.tolist(), [False, False, True, False])

    def test_saved_vertices_ranges_and_populations_match_fitting_samples(self):
        trajectories = analysis.load_data(analysis.INPUT_DEFAULT)
        for row in self.compact.itertuples(index=False):
            with self.subTest(metric=row.metric):
                work = analysis.model_frame(trajectories, row.metric)
                peak = -row.beta_1 / (2 * row.beta_2)
                original_peak = np.expm1(
                    work.attrs["log_effort_mean"] + work.attrs["log_effort_std"] * peak
                )
                np.testing.assert_allclose(peak, row.turning_point_z, rtol=1e-13, atol=1e-14)
                np.testing.assert_allclose(original_peak, row.turning_point_effort_value, rtol=1e-12)
                np.testing.assert_allclose([work.E.min(), work.E.max()], [row.z_min, row.z_max], atol=1e-12)
                self.assertEqual(len(work), row.model_observation_count)
                self.assertEqual(work.task_name.nunique(), row.model_task_strata_count)
                self.assertLess(row.z_min, peak)
                self.assertLess(peak, row.z_max)

    def test_report_separates_interior_peaks_from_significant_curvature(self):
        report = results.REPORT_DEFAULT.read_text(encoding="utf-8")
        section = report.split("### RQ1.2\n", 1)[1].split("### RQ2.1\n", 1)[0]
        rows = [line.strip("| ").split(" | ") for line in section.splitlines() if line.startswith("| ")][2:]
        self.assertEqual(len(rows), 6)
        significant = {row[0] for row in rows if row[-1] == "significant"}
        self.assertEqual(significant, {"Steps", "Total tokens", "Duration", "Positive reported cost"})
        self.assertTrue(all(row[7] == "yes" for row in rows))
        for wording in ("no common beta0", "point estimates without confidence intervals", "descriptive effort-bin figures"):
            self.assertIn(wording, section)


if __name__ == "__main__":
    unittest.main()
