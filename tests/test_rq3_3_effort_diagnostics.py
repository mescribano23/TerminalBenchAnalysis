"""RQ3.3 estimands and populations; no plotting, labelers or model fitting."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

diag = importlib.import_module("scripts.analysis.longitudinal.10_analyze_character_token_usage")
accounting = importlib.import_module("scripts.analysis.longitudinal.09_analyze_token_accounting")


def fixture():
    rows = []
    for version, values in [("2.0", [1, 9, 30]), ("2.1", [3, 5, 10])]:
        for task, numbers in [("a", values), ("b", [100, 200, 300])]:
            for source, value in enumerate(numbers):
                for trial in range(5 if task == "a" and source == 0 else 1):
                    row = {"benchmark_version": version, "benchmark": "tb" + version,
                           "task_name": task, "source_submission_id": f"{version}:source{source}",
                           "source_submission_url": "alias" if source < 2 else "other",
                           "submission_id": "same_legacy_key", "scaffold": "agent", "model_dir": "model",
                           "rel_path": f"{task}-{source}-{trial}.json"}
                    row.update({m["column"]: value for m in diag.effort.METRICS if m["column"] != "logged_chars"})
                    row.update(message_chars=value, reasoning_chars=0, observation_chars=0)
                    rows.append(row)
    return pd.DataFrame(rows)


def load_fixture(frame):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "input.csv"
        frame.to_csv(path, index=False)
        return diag.read_dataset(path)


class EstimandTests(unittest.TestCase):
    def test_all_three_median_levels_and_source_ids(self):
        frame = load_fixture(fixture())
        result = diag.version_comparisons(frame, "2.0", "2.1")
        g = result[result.metric.eq("step_count")].set_index("aggregation")
        self.assertEqual(g.loc["hierarchical_shared_tasks", "old_value"], 104.5)
        self.assertEqual(g.loc["hierarchical_shared_tasks", "new_value"], 102.5)
        self.assertEqual(g.loc["pooled_shared_tasks", "old_value"], 5)
        self.assertEqual(g.loc["hierarchical_shared_tasks", "old_source_submission_task_pairs"], 6)
        self.assertEqual(g.loc["hierarchical_shared_tasks", "old_source_submissions"], 3)
        self.assertEqual(g.loc["hierarchical_shared_tasks", "old_valid_trajectories"], 10)

    def test_repeated_trials_do_not_add_submission_weight(self):
        df = load_fixture(fixture())
        duplicate = df[df.task_name.eq("a") & df[diag.SID].str.endswith("source0")]
        more = pd.concat([df, duplicate, duplicate], ignore_index=True)
        for v in ["2.0", "2.1"]:
            self.assertEqual(diag.median(df[df.benchmark_version.eq(v)], "step_count", True),
                             diag.median(more[more.benchmark_version.eq(v)], "step_count", True))

    def test_ratio_is_computed_before_aggregation(self):
        df = fixture().iloc[:3].copy()
        df[diag.SID] = ["a", "b", "c"]
        df.rel_path = ["a.json", "b.json", "c.json"]
        df.message_chars = [10, 100, 10]
        df.total_tokens = [1, 100, 100]
        df = load_fixture(df)
        self.assertEqual(diag.median(df, "logged_chars_per_total_token", True), 1)
        self.assertEqual(diag.median(df, "logged_chars", True) / diag.median(df, "total_tokens", True), .1)

    def test_distinct_invalid_token_reasons_and_positive_filter(self):
        status = diag.token_status(pd.Series([None, 0, -1, np.inf, "bad", 2]))
        self.assertEqual(status.tolist(), ["missing", "zero", "negative", "nonfinite", "nonnumeric", "valid_positive"])
        df = fixture().iloc[:6].copy()
        df.total_tokens = [None, 0, -1, np.inf, "bad", 2]
        df = load_fixture(df)
        self.assertEqual(df.total_tokens.notna().sum(), 1)
        self.assertEqual(df.logged_chars.notna().sum(), 6)
        self.assertEqual(df.logged_chars_positive_total.notna().sum(), 1)
        self.assertEqual(df.logged_chars_per_total_token.notna().sum(), 1)

    def test_missing_character_components_are_not_imputed(self):
        df = fixture().iloc[:1].copy()
        df.observation_chars = np.nan
        loaded = load_fixture(df)
        self.assertTrue(loaded.total_tokens.notna().all())
        self.assertTrue(loaded.logged_chars.isna().all())

    def test_metric_missing_tasks_are_paired_and_disclosed(self):
        df = load_fixture(fixture())
        df.loc[df.task_name.eq("a") & df.benchmark_version.eq("2.0"), "logged_chars_per_total_token"] = np.nan
        out = diag.version_comparisons(df, "2.0", "2.1")
        row = out[out.metric.eq("logged_chars_per_total_token") & out.aggregation.eq("hierarchical_shared_tasks")].iloc[0]
        self.assertEqual(row.expected_shared_tasks, 2)
        self.assertEqual(row.metric_paired_tasks, 1)
        self.assertEqual(row.dropped_shared_tasks, "a")
        self.assertEqual(row.old_tasks, 1)
        self.assertEqual(row.new_tasks, 1)

    def test_duplicate_canonical_records_fail(self):
        df = fixture()
        with self.assertRaisesRegex(ValueError, "Duplicate trajectory"):
            load_fixture(pd.concat([df, df.iloc[:1]]))

    def test_existing_effort_loader_also_rejects_infinite_tokens(self):
        df = fixture()
        df.total_tokens = np.inf
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            df.to_csv(path, index=False)
            self.assertTrue(diag.effort.load_trajectories(path).total_tokens.isna().all())

    def test_accounting_comparisons_keep_submission_level(self):
        frame = fixture().query("benchmark_version == '2.0'")
        self.assertEqual(accounting.task_balanced_median(frame, "step_count"), 104.5)


class RawCoverageTests(unittest.TestCase):
    def test_final_only_counter_does_not_imply_per_call_completeness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "tb4" / "run.json"
            path.parent.mkdir()
            path.write_text(json.dumps({"steps": [], "final_metrics": {
                "extra": {"total_reasoning_tokens": 7}
            }}), encoding="utf-8")
            raw = diag.raw_accounting({"benchmark": "tb4", "rel_path": "run.json"}, root)
        self.assertEqual(raw["final_reasoning_tokens"], 7)
        self.assertEqual(raw["explicit_counters"], 0)
        self.assertEqual(raw["positive_completion_calls"], 0)

    def test_codex_reasoning_output_counter_is_included(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "tb4" / "run.json"
            path.parent.mkdir()
            path.write_text(json.dumps({"steps": [{"metrics": {
                "completion_tokens": 10, "extra": {"reasoning_output_tokens": 7}
            }}]}), encoding="utf-8")
            raw = diag.raw_accounting({"benchmark": "tb4", "rel_path": "run.json"}, root)
        self.assertEqual(raw["reasoning_tokens"], 7)
        self.assertEqual(raw["explicit_counters"], 1)
        self.assertEqual(raw["missing_counters"], 0)

    def test_all_tb4_scaffolds_are_scanned_for_counter_presence(self):
        df = fixture().iloc[:2].copy()
        df.benchmark_version = "4.0"
        df.scaffold = ["codex", "grok-build"]
        with patch.object(diag, "raw_accounting", side_effect=lambda row, root: row) as parse:
            raw = diag.read_raw_accounting(df, Path("unused"), 1)
        self.assertEqual(len(raw), 2)
        self.assertEqual(parse.call_count, 2)

    def test_counter_coverage_is_not_a_hierarchical_quantity(self):
        def call(comp, details):
            return {"metrics": {"completion_tokens": comp, "extra": {"completion_tokens_details": details}}}
        rows = fixture().iloc[:3].copy()
        rows.benchmark_version = "4.0"
        rows.rel_path = ["explicit.json", "infer_zero.json", "missing.json"]
        rows.completion_tokens = [10, 13, 13]
        steps = [
            [call(10, {"reasoning_tokens": 5})],
            [call(10, {"reasoning_tokens": 5}), call(3, {"text_tokens": 3})],
            [call(10, {"reasoning_tokens": 5}), call(3, {})],
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for row, calls in zip(rows.to_dict("records"), steps):
                path = root / row["benchmark"] / row["rel_path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"steps": calls}), encoding="utf-8")
            raw = pd.DataFrame([diag.raw_accounting(row, root) for row in rows.to_dict("records")])
        loaded = load_fixture(rows)
        _, coverage = diag.accounting_outputs(loaded, raw)
        row = coverage.iloc[0]
        self.assertEqual(row.records, 3)
        self.assertEqual(row.explicit_complete, 1)
        self.assertEqual(row.eligible_trajectories, 0)  # fixture totals are below completion totals
        self.assertNotIn("complete_allowing_flagged_zero_inference", coverage.columns)
        self.assertEqual(row.aggregation, "record_counts")


class ReasoningEligibilityTests(unittest.TestCase):
    @staticmethod
    def call(completion=10, reasoning=5, text=None):
        details = {} if reasoning is None else {"reasoning_tokens": reasoning}
        if text is not None:
            details["text_tokens"] = text
        return {"source": "agent", "metrics": {"completion_tokens": completion,
                "extra": {"completion_tokens_details": details}}}

    def evaluate(self, trajectories, completions=None, totals=None):
        rows = fixture().iloc[:len(trajectories)].copy()
        rows.benchmark_version = "4.0"
        rows.rel_path = [f"run{i}.json" for i in range(len(rows))]
        rows.completion_tokens = completions if completions is not None else 10
        rows.total_tokens = totals if totals is not None else 100
        rows.message_chars = 20
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for row, obj in zip(rows.to_dict("records"), trajectories):
                path = root / row["benchmark"] / row["rel_path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(obj), encoding="utf-8")
            raw = pd.DataFrame([diag.raw_accounting(row, root) for row in rows.to_dict("records")])
        loaded = load_fixture(rows)
        return diag.reasoning_eligibility(loaded, raw), diag.accounting_outputs(loaded, raw)

    def test_explicit_zero_is_valid_and_equality_never_infers_zero(self):
        merged, _ = self.evaluate([
            {"steps": [self.call(reasoning=0, text=10)]},
            {"steps": [self.call(reasoning=None, text=10)]},
        ])
        self.assertEqual(merged.reasoning_eligible.tolist(), [True, False])
        self.assertEqual(merged.reported_reasoning_tokens.iloc[0], 0)
        self.assertTrue(pd.isna(merged.reported_reasoning_tokens.iloc[1]))

    def test_partial_calls_and_unmetered_agent_steps_cannot_be_repaired(self):
        final = {"total_completion_tokens": 20, "extra": {"total_reasoning_tokens": 5}}
        merged, _ = self.evaluate([
            {"steps": [self.call(), self.call(reasoning=None, text=10)], "final_metrics": final},
            {"steps": [self.call(), self.call(completion=None)]},
            {"steps": [self.call(), {"source": "agent"}]},
        ], completions=[20, 20, 20])
        self.assertFalse(merged.reasoning_eligible.any())
        self.assertTrue(merged.reported_reasoning_tokens.isna().all())

    def test_zero_completion_error_step_still_requires_explicit_reasoning(self):
        merged, _ = self.evaluate([
            {"steps": [self.call(), self.call(completion=0, reasoning=0)]},
            {"steps": [self.call(), self.call(completion=0, reasoning=None)]},
        ])
        self.assertEqual(merged.reasoning_eligible.tolist(), [True, False])

    def test_reconciliation_failures_are_qc_and_not_eligibility(self):
        merged, (rows, coverage) = self.evaluate([
            {"steps": [self.call(text=2)]},  # 10 != 5 + 2
            {"steps": [self.call(text=5)]},  # call 10 != trajectory 12
        ], completions=[10, 12])
        self.assertTrue(merged.reasoning_eligible.all())
        self.assertEqual(merged.completion_totals_reconcile.tolist(), [True, False])
        self.assertEqual(coverage.iloc[0].calls_failing_text_plus_reasoning_reconciliation, 1)
        self.assertEqual(coverage.iloc[0].eligible_full_text_accounting_reconciles, 1)
        out = pd.DataFrame(rows)
        primary = out[out.diagnostic.str.startswith("primary_reasoning:") & out.aggregation.eq("pooled_trajectories")]
        self.assertEqual(set(primary.valid_trajectories), {2})
        self.assertAlmostEqual(primary.set_index("metric").loc["reasoning_share_of_completion", "value"], (0.5 + 5/12)/2)

    def test_final_only_explicit_totals_and_zero_are_usable(self):
        merged, _ = self.evaluate([
            {"steps": [{"source": "agent"}], "final_metrics": {
                "total_completion_tokens": 10, "extra": {"total_reasoning_tokens": 5}}},
            {"steps": [], "final_metrics": {
                "total_completion_tokens": 10, "extra": {"total_reasoning_tokens": 0}}},
            {"steps": [], "final_metrics": {"extra": {"total_reasoning_tokens": 5}}},
        ])
        self.assertEqual(merged.reasoning_eligible.tolist(), [True, True, False])
        self.assertEqual(merged.reasoning_counter_source.tolist(), ["final_only", "final_only", "unusable"])

    def test_invalid_call_counters_are_rejected(self):
        for completion, reason in [(10, -1), (10, 11), (10, float("inf")), (10, "5"),
                                   (10, True), (-1, 0), (float("inf"), 0), (None, 0)]:
            with self.subTest(completion=completion, reasoning=reason):
                merged, _ = self.evaluate([{"steps": [self.call(completion, reason)]}])
                self.assertFalse(merged.reasoning_eligible.iloc[0])

    def test_invalid_final_totals_are_rejected(self):
        for reason, completion in [(-1, 10), (11, 10), (float("inf"), 10), (0, True), (0, 0), (0, -1)]:
            with self.subTest(reasoning=reason, completion=completion):
                merged, _ = self.evaluate([{"steps": [], "final_metrics": {
                    "total_completion_tokens": completion, "extra": {"total_reasoning_tokens": reason}}}])
                self.assertFalse(merged.reasoning_eligible.iloc[0])

    def test_invalid_trajectory_completion_totals_are_rejected(self):
        for completion in [None, 0, -1, float("inf"), "bad", 4]:
            with self.subTest(completion=completion):
                merged, _ = self.evaluate([{"steps": [self.call()]}], completions=[completion])
                self.assertFalse(merged.reasoning_eligible.iloc[0])

    def test_per_call_source_is_preferred_and_invalid_calls_never_use_final_fallback(self):
        final = {"total_completion_tokens": 10, "extra": {"total_reasoning_tokens": 7}}
        null_call = self.call()
        null_call["metrics"]["extra"]["completion_tokens_details"]["reasoning_tokens"] = None
        merged, _ = self.evaluate([
            {"steps": [self.call(reasoning=5)], "final_metrics": final},
            {"steps": [self.call(reasoning="bad")], "final_metrics": final},
            {"steps": [null_call], "final_metrics": final},
        ])
        self.assertEqual(merged.reasoning_eligible.tolist(), [True, False, False])
        self.assertEqual(merged.reported_reasoning_tokens.iloc[0], 5)

    def test_total_denominators_and_same_before_after_population(self):
        for total in [None, 0, -1, float("inf"), "bad", 9, 10, 100]:
            with self.subTest(total=total):
                merged, (rows, _) = self.evaluate([{"steps": [self.call(reasoning=10)]}], totals=[total])
                expected = total == 100
                self.assertEqual(bool(merged.reasoning_eligible.iloc[0]), expected)
                primary = [r for r in rows if r["diagnostic"].startswith("primary_reasoning:")]
                self.assertEqual(len(primary), 6 if expected else 0)
                if expected:
                    pooled = {r["metric"]: r for r in primary if r["aggregation"] == "pooled_trajectories"}
                    self.assertEqual({r["valid_trajectories"] for r in pooled.values()}, {1})
                    self.assertAlmostEqual(pooled["logged_chars_per_total_token"]["value"], .2)
                    self.assertAlmostEqual(pooled["logged_chars_per_nonreason_total_token"]["value"], 20/90)
                    self.assertEqual(pooled["reasoning_share_of_completion"]["value"], 1)


class CanonicalExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames = [diag.read_dataset(diag.LONG / "trajectory_longitudinal.csv"),
                      diag.read_dataset(diag.LONG / "tb3_tb4/trajectory_longitudinal.csv")]

    def test_main_figure_data_and_token_populations_preserved(self):
        for df, old, new, tasks, populations, pairs, sources, folder in [
            (self.frames[0], "2.0", "2.1", 89, [30126, 7434], [6376, 1507], [72, 17], diag.LONG),
            (self.frames[1], "3.0", "4.0", 66, [3510, 5902], [718, 1187], [11, 18], diag.LONG / "tb3_tb4"),
        ]:
            actual = diag.version_comparisons(df, old, new)
            hierarchical = actual[actual.aggregation.eq("hierarchical_shared_tasks")].set_index("metric")
            saved = pd.read_csv(diag.LONG / "rq3_3_aggregation_diagnostics.csv")
            saved = saved[saved.transition.eq(f"{old}->{new}") & saved.aggregation.eq("hierarchical_shared_tasks")]
            saved = saved.copy()
            saved[["old_version", "new_version"]] = saved[["old_version", "new_version"]].astype(str)
            saved["dropped_shared_tasks"] = saved.dropped_shared_tasks.fillna("")
            pd.testing.assert_frame_equal(
                actual[actual.aggregation.eq("hierarchical_shared_tasks")].reset_index(drop=True),
                saved.reset_index(drop=True), check_dtype=False, rtol=1e-13, atol=1e-12,
            )
            figures = diag.effort.summarize_task_balanced_periods(df, old, new)
            for row in figures.itertuples(index=False):
                np.testing.assert_allclose(hierarchical.loc[row.column, ["old_value", "new_value", "percentage_change"]].to_numpy(dtype=float),
                                           [row.early_value, row.late_value, row.relative_change_pct], rtol=1e-13)
            self.assertTrue(hierarchical.metric_paired_tasks.eq(tasks).all())
            total = hierarchical.loc["total_tokens"]
            for prefix, n, p, s in zip(["old", "new"], populations, pairs, sources):
                self.assertEqual(total[f"{prefix}_valid_trajectories"], n)
                self.assertEqual(total[f"{prefix}_source_submission_task_pairs"], p)
                self.assertEqual(total[f"{prefix}_source_submissions"], s)
        self.assertEqual(self.frames[0].query("benchmark_version == '2.0'").total_token_status.eq("zero").sum(), 455)

    def test_tb3_ratio_uses_66_shared_tasks(self):
        out = diag.version_comparisons(self.frames[1], "3.0", "4.0")
        row = out[out.metric.eq("logged_chars_per_total_token") & out.aggregation.eq("hierarchical_shared_tasks")].iloc[0]
        self.assertAlmostEqual(row.old_value, 0.05081338661685076)
        self.assertAlmostEqual(row.new_value, 0.05575090310281244)
        self.assertAlmostEqual(row.percentage_change, 9.716960066433145)

    def test_astra_five_sources_and_six_of_seven_configurations(self):
        rows = pd.DataFrame(diag.configuration_comparisons(pd.concat(self.frames, ignore_index=True)))
        astra = rows[rows.diagnostic.eq("codex/gpt-6-astra") & rows.aggregation.str.startswith("hierarchical")].iloc[0]
        self.assertEqual(astra.source_submissions, 5)
        self.assertEqual(astra.valid_trajectories, 1650)
        self.assertEqual(astra.value, 1846448)
        matched = rows[rows.diagnostic.str.startswith("matched_tokens:") & rows.aggregation.str.startswith("hierarchical")]
        matrix = matched.pivot(index="diagnostic", columns="benchmark_version", values="value")
        self.assertEqual(len(matrix), 7)
        self.assertEqual((matrix['4.0'] > matrix['3.0']).sum(), 6)

    def test_accounting_comparisons_use_shared_tasks_and_source_hierarchy(self):
        frame = load_fixture(fixture())
        spec = accounting.ComparisonSpec("fixture", "agent", "model", "2.0", "model", "2.1")
        with patch.object(accounting, "COMPARISONS", [spec]):
            row = accounting.build_comparisons(frame).iloc[0]
        self.assertEqual(row.shared_task_count, 2)
        for metric in ["prompt_tokens", "completion_tokens", "total_tokens", "logged_chars"]:
            self.assertEqual(row[f"{metric}_earlier"], 104.5)
            self.assertEqual(row[f"{metric}_later"], 102.5)
            self.assertAlmostEqual(row[f"{metric}_change_pct"], (102.5 / 104.5 - 1) * 100)

    def test_primary_reasoning_exports_have_paired_populations(self):
        coverage = pd.read_csv(diag.LONG / "rq3_3_reasoning_coverage.csv")
        tb4 = coverage[coverage.benchmark_version.eq(4)]
        self.assertEqual(tb4.eligible_trajectories.sum(), 5530)
        self.assertEqual(tb4.eligible_trajectories.gt(0).sum(), 13)
        self.assertEqual(tb4.eligible_per_call.sum(), 4872)
        self.assertEqual(tb4.eligible_final_only.sum(), 658)
        self.assertEqual(tb4.explicit_complete.sum(), 4941)
        self.assertEqual(tb4.explicit_complete_but_primary_ineligible.sum(), 69)
        self.assertEqual(tb4.eligible_per_call_and_completion_totals_reconcile.sum(), 4710)
        exported = pd.read_csv(diag.LONG / "rq3_3_configuration_diagnostics.csv")
        primary = exported[exported.diagnostic.str.startswith("primary_reasoning:") &
                           exported.aggregation.eq("pooled_trajectories")]
        self.assertEqual(len(primary), 39)
        self.assertTrue(primary.groupby("diagnostic").valid_trajectories.nunique().eq(1).all())
        metrics = ["reasoning_share_of_completion", "logged_chars_per_total_token",
                   "logged_chars_per_nonreason_total_token"]
        for config, n, expected in [
            ("mini-swe-agent/gemini-3.8-flash", 330,
             [.6433466809601105, .010312857749416687, .010353040264788047]),
            ("claude-code/claude-sonnet-5", 296,
             [.7761525458335765, .03464063490482088, .035126525726855415]),
        ]:
            rows = primary[primary.diagnostic.eq("primary_reasoning:" + config)].set_index("metric")
            self.assertTrue(rows.valid_trajectories.eq(n).all())
            np.testing.assert_allclose(rows.loc[metrics, "value"], expected, rtol=1e-13)


if __name__ == "__main__":
    unittest.main()
