"""Release provenance, grouping and aggregation regression checks for RQ3.1."""
import importlib
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analysis.longitudinal import official_release_changes as release

results = importlib.import_module("scripts.analysis.02_build_statistical_results")


class OfficialReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.crosswalk = release.load_crosswalk()
        cls.adjacent = pd.read_csv(results.ADJACENT_CHANGES)

    def test_tb21_input_preserves_release_and_pr26_membership(self):
        tb2 = self.crosswalk[self.crosswalk.version_pair.eq("2.0->2.1")]
        fixed = set(tb2.loc[tb2.release_status.eq("fixed"), "task_name"])
        pr26 = set(tb2.loc[pd.to_numeric(tb2.listed_in_tb21_pr53).eq(1), "task_name"])
        self.assertEqual((len(fixed), len(pr26)), (28, 26))
        self.assertTrue(pr26 <= fixed)
        self.assertEqual(fixed - pr26, {"crack-7z-hash", "gpt2-codegolf"})
        self.assertTrue(tb2.official_source_url.eq("https://www.tbench.ai/news/terminal-bench-2-1").all())

    def test_removed_tasks_excluded_and_global_resources_explicit(self):
        group = release.add_release_status(self.adjacent, "3.0->4.0")
        self.assertEqual(group.release_status.value_counts().to_dict(), {"not_listed_as_fixed": 47, "fixed": 19})
        self.assertTrue(group.global_resource_calibration.eq(1).all())
        removed = self.crosswalk[self.crosswalk.release_status.eq("removed")]
        self.assertEqual(len(removed), 8)
        self.assertTrue(removed.new_n_trajectories.eq(0).all())
        self.assertFalse(set(removed.task_name) & set(group.task_name))

    def test_instruction_metadata_does_not_define_release_group(self):
        group = release.add_release_status(self.adjacent, "2.0->2.1")
        self.assertEqual(len(group[group.release_status.eq("fixed") & group.legacy_instruction_status.eq("unchanged")]), 17)
        self.assertEqual(len(group[group.release_status.eq("fixed") & group.legacy_instruction_status.eq("changed")]), 11)

    def test_unknown_missing_duplicate_task_ids_fail(self):
        for changed in [self.adjacent.iloc[1:], pd.concat([self.adjacent, self.adjacent.iloc[[0]]])]:
            with self.assertRaises(ValueError):
                release.add_release_status(changed, "2.0->2.1")
        changed = self.adjacent.copy()
        changed.loc[0, "task_name"] = "invented-alias"
        with self.assertRaises(ValueError):
            release.add_release_status(changed, "2.0->2.1")

    def test_wrong_aggregation_unit_rejected(self):
        changed = self.adjacent.copy()
        changed["submission_unit"] = "leaderboard-url"
        with self.assertRaises(ValueError):
            release.add_release_status(changed, "2.0->2.1")

    def test_task_rates_preserve_original_submission_balancing(self):
        for pair, file in [("2.0->2.1", results.TB2_TRAJECTORIES), ("3.0->4.0", results.TB34_TRAJECTORIES)]:
            df = pd.read_csv(file, usecols=["benchmark_version", "source_submission_id", "task_name", "passed"])
            df.benchmark_version = df.benchmark_version.astype(str)
            rates = df.groupby(["benchmark_version", "source_submission_id", "task_name"]).passed.mean().groupby(["benchmark_version", "task_name"]).mean()
            result = release.add_release_status(self.adjacent, pair).set_index("task_name")
            for version, col in zip(pair.split("->"), ["task_weighted_pass_rate_old", "task_weighted_pass_rate_new"]):
                np.testing.assert_allclose(result[col], rates.loc[version].reindex(result.index), rtol=0, atol=1e-14)

    def test_between_group_inference_uses_same_method(self):
        actual = results.build_release_comparisons(self.adjacent).set_index("transition")
        for pair in release.EXPECTED:
            group = release.add_release_status(self.adjacent, pair)
            x = group[group.release_status.eq("fixed")].improvement_pp
            y = group[group.release_status.eq("not_listed_as_fixed")].improvement_pp
            # Independent pairwise enumeration verifies Cliff's delta direction and ties.
            delta = np.sign(x.to_numpy()[:, None] - y.to_numpy()[None, :]).mean()
            u, p = results.two_sided_mann_whitney(x, y)
            self.assertAlmostEqual(actual.loc[pair, "cliffs_delta"], delta)
            self.assertEqual(actual.loc[pair, "mann_whitney_u"], u)
            self.assertEqual(actual.loc[pair, "p_value"], p)

    def test_scoped_master_preserves_every_unrelated_row_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "master_inferential_results.csv"
            path.write_bytes((results.OUT_DEFAULT / path.name).read_bytes())
            before = path.read_bytes().splitlines(keepends=True)
            master = pd.read_csv(path)
            master["analysis"] = master.analysis.replace({"instruction-change robustness": "official release-fix comparison"})
            results.write_scoped_master(path, master)
            after = path.read_bytes().splitlines(keepends=True)
            self.assertEqual(len(before), len(after))
            for old, new in zip(before, after):
                if not old.startswith((b"RQ3.1,official release-fix comparison,", b"RQ3.1,instruction-change robustness,")):
                    self.assertEqual(old, new)


if __name__ == "__main__":
    unittest.main()
