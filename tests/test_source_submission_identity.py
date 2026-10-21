"""Source evidence regressions, including the former substring/first-candidate failures."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import importlib
import tempfile
import shutil

import pandas as pd

from scripts.analysis.source_submission_identity import SourceResolver, ensure_source_submission_id, source_id

ROOT = Path(__file__).resolve().parents[1]
effort = importlib.import_module('scripts.analysis.longitudinal.08_analyze_effort_changes')
performance = importlib.import_module('scripts.analysis.longitudinal.04_analyze_performance')
builder = importlib.import_module('scripts.analysis.longitudinal.00_build_dataset')


class SourceIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        b = 'terminal_bench_2_0'
        raw = ROOT / 'data/raw' / b
        cls.resolver = SourceResolver(b, raw/'leaderboard_submissions.json', raw/'leaderboard_trials.json')
        cls.index = {r['trialId']: r for r in json.loads((ROOT/'data/indexes'/b/'trajectory_trials.json').read_text(encoding='utf-8'))}
        cls.tb2 = pd.read_csv(ROOT/'data/processed_live'/b/'trajectory_summary.csv', low_memory=False)

    def resolve_example(self, scaffold, model, version=None):
        subset = self.tb2[self.tb2.scaffold.eq(scaffold) & self.tb2.model_dir.eq(model)]
        if version:
            subset = subset[subset.agent_version.eq(version)]
        row = subset.iloc[0].to_dict()
        row['source_submission_url'] = 'https://wrong.example/ignored'
        return self.resolver.resolve(row, self.index[row['file_run_id']])[0]

    def test_codex_gpt5_does_not_match_gpt55(self):
        result = self.resolve_example('codex', 'gpt-5')
        self.assertIn('/0.53.0/gpt-5%40openai', result['source_submission_url'])
        self.assertEqual(result['historical_leaderboard_date'], '2025-11-04')

    def test_prefixed_oss_does_not_take_sonnet_first_candidate(self):
        result = self.resolve_example('mini-swe-agent', 'openai_gpt-oss-20b')
        self.assertIn('openai%2Fgpt-oss-20b', result['source_submission_url'])
        self.assertEqual(result['leaderboard_provider'], 'together_ai')

    def test_gemini_versions_resolve_to_distinct_source_rows(self):
        first = self.resolve_example('gemini-cli', 'gemini-3.1-pro-preview', '0.34.0')
        second = self.resolve_example('gemini-cli', 'gemini-3.1-pro-preview', '0.35.0')
        self.assertNotEqual(first['source_submission_id'], second['source_submission_id'])
        row = self.tb2[self.tb2.model_dir.eq('gemini-3.1-pro-preview') & self.tb2.scaffold.eq('gemini-cli')].iloc[0].to_dict()
        row['agent_version'] = 'unrecorded'
        with self.assertRaisesRegex(ValueError, 'exact candidates'):
            self.resolver.resolve(row, self.index[row['file_run_id']])

    def test_missing_evidence_and_stale_url_fail_closed(self):
        with self.assertRaises(ValueError):
            ensure_source_submission_id(pd.DataFrame({'source_submission_url': ['known-looking-url']}))
        row = self.tb2.iloc[0].to_dict()
        with self.assertRaises(ValueError):
            self.resolver.resolve(row, {})
        trajectories = self.tb2.iloc[:1].copy()
        trajectories['source_submission_url'] = 'wrong'
        sources = builder.read_submission_table(ROOT/'data/raw', 'terminal_bench_2_0')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            builder.attach_submission_metadata(trajectories, sources)

    def test_devin_one_source_astra_five_sources_and_no_telemetry_loss(self):
        total = 0; uuids = []
        for v, sources, n in [('2_0',74,31103),('2_1',17,7501),('3_0',12,4337),('4_0',18,5902)]:
            frame = pd.read_csv(ROOT/f'data/processed_live/terminal_bench_{v}/trajectory_summary.csv', low_memory=False)
            self.assertEqual(len(frame),n); self.assertEqual(frame.source_submission_id.nunique(),sources)
            self.assertFalse(frame.source_submission_id.isna().any())
            total += len(frame); uuids.extend(frame.file_run_id)
            if v == '3_0':
                devin = frame[frame.scaffold.eq('devin')]
                self.assertEqual(devin.source_submission_id.nunique(),1)
                self.assertEqual(devin.agent_version.nunique(),2)
                self.assertEqual(int(frame.reward.isin([0,1]).sum()),4279)
            if v == '4_0':
                astra = frame[frame.model_dir.eq('gpt-6-astra')]
                self.assertEqual(astra.source_submission_id.nunique(),5)
                self.assertEqual(len(astra),1650)
        self.assertEqual(total,48843); self.assertEqual(len(set(uuids)),48843)

    def test_source_weighting_pools_versions_before_taking_task_median(self):
        frame = pd.DataFrame({
            'benchmark_version':['3.0']*5+['4.0']*2, 'task_name':['task']*7,
            'source_submission_id':['devin','devin','devin','devin','other','next','other-next'],
            'effective_submission_id':['devin-old','devin-new','devin-new','devin-new','other','next','other-next'],
            'step_count':[1,9,9,9,30,3,10]})
        pairs = effort.task_metric_pairs(frame,'step_count')
        self.assertEqual(pairs.loc['task','3.0'],19.5)  # median(median(1,9,9,9),30)
        self.assertEqual(pairs.loc['task','4.0'],6.5)
        # Source success uses all binary trials in the row, then equal source weights.
        frame['passed']=[0,1,1,1,1,1,0]
        frame['submission_key']=frame.source_submission_id
        self.assertEqual(performance.task_weighted_rate(frame[frame.benchmark_version.eq('3.0')]),.875)

    def test_source_id_is_independent_of_date_or_agent_version(self):
        url='https://hub.harborframework.com/rows/row-uuid'
        self.assertEqual(source_id('benchmark',url),'benchmark:harbor:row-uuid')

    def test_future_acquisition_indexes_preserve_explicit_source_links(self):
        tb2 = importlib.import_module('scripts.mining.00_scrape_terminal_bench_2_0_leaderboard')
        harbor = importlib.import_module('scripts.mining.01_scrape_harbor_terminal_bench_leaderboard')
        entry = tb2.trial_index_entry({'submission':{'scaffold':'codex','model':'gpt-5','scaffold_version':'0.53.0','provider':'openai'},
                                      'submission_url':'https://source.example/submission','trialId':'trial'},ROOT/'data/example.json')
        self.assertEqual(entry['source_submission_url'],'https://source.example/submission')
        self.assertEqual(entry['source_scaffold_version'],'0.53.0')
        entry = harbor.trial_index_entry({'scaffold':'devin','model':'swe'},
                    {'id':'trial','harbor_leaderboard_row_id':'original-row'},ROOT/'data/example.json')
        self.assertEqual(entry['harbor_leaderboard_row_id'],'original-row')

    def test_characterizer_end_to_end_ignores_bad_url_candidates(self):
        characterizer = importlib.import_module('scripts.analysis.00_characterize_trajectories')
        row = self.tb2[self.tb2.model_dir.eq('openai_gpt-oss-20b') & self.tb2.scaffold.eq('mini-swe-agent')].iloc[0]
        record = dict(self.index[row.file_run_id])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'trajectories'; out = Path(directory)/'out'
            relative = Path(str(row.rel_path).replace('\\','/'))
            target = root/relative; target.parent.mkdir(parents=True)
            shutil.copyfile(ROOT/'data/trajectories/terminal_bench_2_0'/relative,target)
            record['filePath'] = target.as_posix()
            index = Path(directory)/'index.json'; index.write_text(json.dumps([record]),encoding='utf-8')
            argv=['characterize','--benchmark','terminal_bench_2_0','--root',str(root),'--out',str(out),
                  '--trajectory-index',str(index),'--leaderboard',str(ROOT/'data/raw/terminal_bench_2_0/leaderboard_submissions.json')]
            with patch('sys.argv',argv),patch('builtins.print'):
                characterizer.main()
            result = pd.read_csv(out/'trajectory_summary.csv')
            self.assertEqual(len(result),1)
            self.assertEqual(len(result.columns),len(set(result.columns)))
            self.assertIn('openai%2Fgpt-oss-20b',result.source_submission_url.iloc[0])
            self.assertEqual(result.source_identity_status.iloc[0],'reconstructed')
            for column in ['step_count', 'message_chars', 'reasoning_chars', 'observation_chars',
                           'tool_call_count', 'shell_invocation_count', 'prompt_tokens',
                           'completion_tokens', 'total_tokens']:
                if pd.isna(row[column]):
                    self.assertTrue(pd.isna(result[column].iloc[0]), column)
                else:
                    self.assertEqual(result[column].iloc[0], row[column], column)


if __name__ == '__main__':
    unittest.main()
