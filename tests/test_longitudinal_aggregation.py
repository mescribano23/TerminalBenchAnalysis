"""Hand-calculated regression checks for the longitudinal aggregation units."""
import importlib
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

effort = importlib.import_module('scripts.analysis.longitudinal.03_analyze_effort_changes')
composition = importlib.import_module('scripts.analysis.longitudinal.07_analyze_task_composition_over_versions')
difficulty = importlib.import_module('scripts.analysis.longitudinal.09_analyze_difficulty_over_versions')
pass_changes = importlib.import_module('scripts.analysis.longitudinal.02_analyze_pass_rate_changes')
audit = importlib.import_module('scripts.analysis.10_build_statistical_audit')
from scripts.analysis.submission_task_balancing import ensure_effective_submission_id


def fixture():
    rows = []
    for version, values, rewards in [('2.0', [1,9,30], [0,1,1]), ('2.1', [3,5,10], [1,0,0])]:
        for index, (value, passed) in enumerate(zip(values, rewards)):
            for _ in range(3 if index == 0 else 1):
                rows.append({'benchmark':'terminal_bench_'+version.replace('.','_'),
                    'benchmark_version':version, 'task_name':'task', 'scaffold':'agent',
                    'model_dir':f'model{index}', 'agent_version':'v1',
                    'leaderboard_model':f'model{index}', 'leaderboard_provider':'provider',
                    'leaderboard_date':'2026-01-01', 'source_submission_url':'shared' if index<2 else 'separate',
                    'source_submission_id':f'{version}:source{index}',
                    'submission_id':'shared' if index<2 else 'separate',
                    'duration_seconds':value, 'step_count':value, 'passed':passed})
    return ensure_effective_submission_id(pd.DataFrame(rows))


class AggregationTests(unittest.TestCase):
    def test_monthly_pass_rates_accept_normalized_historical_dates(self):
        rows = pd.DataFrame({
            'source_submission_id': ['a', 'a', 'b'],
            'historical_leaderboard_timestamp': pd.to_datetime(['2026-01-31', '2026-01-31', '2026-02-01']),
            'difficulty': ['easy', 'easy', 'easy'],
            'task_name': ['task1', 'task2', 'task1'],
            'passed': [0, 1, 1],
        })
        summary = pass_changes.monthly_difficulty_summary(pass_changes.difficulty_submission_summary(rows))
        self.assertEqual(summary.submission_month.tolist(), [pd.Timestamp('2026-01-01'), pd.Timestamp('2026-02-01')])
        self.assertEqual(summary.median_pass_rate.tolist(), [0.5, 1.0])
        self.assertEqual(summary.submission_count.tolist(), [1, 1])

    def test_effective_url_and_trial_units_differ(self):
        data=fixture()
        effective=effort.task_metric_pairs(data,'step_count').loc['task']
        urls=effort.task_metric_pairs(data,'step_count',submission_unit='leaderboard-url').loc['task']
        trials=effort.task_metric_pairs(data,'step_count',task_weighting='trial-weighted').loc['task']
        self.assertEqual(effective.to_dict(),{'2.0':9.0,'2.1':5.0})
        self.assertEqual(urls.to_dict(),{'2.0':15.5,'2.1':6.5})
        self.assertEqual(trials.to_dict(),{'2.0':1.0,'2.1':3.0})

    def test_submission_balancing_resists_duplicated_trials(self):
        data=fixture()
        duplicate=data[data.model_dir.eq('model0')]
        pd.testing.assert_frame_equal(effort.task_metric_pairs(data,'step_count'),
            effort.task_metric_pairs(pd.concat([data,duplicate,duplicate]),'step_count'))

    def test_primary_cli_defaults(self):
        for module in (effort,composition,difficulty):
            with patch('sys.argv',['analysis']):
                self.assertEqual(module.parse_args().submission_unit,'source')

    def test_count_labels_preserve_fractional_task_medians(self):
        self.assertEqual(effort.format_raw('steps',76.25),'76.25')
        self.assertEqual(effort.format_raw('shell_invocations',20.5),'20.5')

    def test_composition_pass_rates_use_effective_units(self):
        data=fixture()
        result=composition.build_observed_task_duration(data).set_index('benchmark_version')
        self.assertAlmostEqual(result.loc['2.0','task_weighted_pass_rate'],2/3)
        self.assertAlmostEqual(result.loc['2.1','task_weighted_pass_rate'],1/3)
        self.assertEqual(result.loc['2.0','observed_median_duration_min'],9/60)
        url=composition.build_observed_task_duration(data,submission_unit='leaderboard-url').set_index('benchmark_version')
        self.assertAlmostEqual(url.loc['2.0','task_weighted_pass_rate'],0.625)

    def test_difficulty_rates_match_composition_units(self):
        data=fixture()
        labels=pd.DataFrame({'benchmark_version':['2.0','2.1'],'task_name':['task','task'],'difficulty_label':['medium','medium']})
        rates=difficulty.build_task_pass_rates(data,labels).set_index('benchmark_version')
        self.assertAlmostEqual(rates.loc['2.0','task_pass_rate'],2/3)
        self.assertAlmostEqual(rates.loc['2.1','task_pass_rate'],1/3)
        self.assertEqual(rates.loc['2.0','n_submissions'],3)

    def test_shared_configuration_summary_uses_effective_units(self):
        data=fixture().query("benchmark_version == '2.0'").copy()
        data['total_tokens']=data.step_count
        self.assertEqual(audit.task_balanced_config_median(data),9)

    def test_include_tb3_tb4_writes_both_task_tables(self):
        first=fixture()
        for metric in effort.METRICS:
            if metric['column'] not in first:
                first[metric['column']]=first.step_count*100
        second=first.copy()
        second['benchmark_version']=second.benchmark_version.replace({'2.0':'3.0','2.1':'4.0'})
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            argv=['03','--include-tb3-tb4','--out',str(root/'balanced2.png'),
                '--tb3-tb4-out',str(root/'balanced3.png'),'--pooled-summary-csv',str(root/'pool2.csv'),
                '--task-balanced-summary-csv',str(root/'tasks2.csv'),
                '--tb3-tb4-pooled-summary-csv',str(root/'pool3.csv'),
                '--tb3-tb4-task-balanced-summary-csv',str(root/'tasks3.csv')]
            with patch('sys.argv',argv),patch.object(effort,'load_trajectories',side_effect=[first,second]),\
                patch.object(effort,'load_instruction_unchanged_tasks',return_value=set()),\
                patch.object(effort,'load_adjacent_instruction_unchanged_tasks',return_value=set()),\
                patch.object(effort,'plot') as render,patch('builtins.print'):
                effort.main()
            rendered = {call.args[1].name for call in render.call_args_list}
            self.assertEqual(rendered, {'balanced2.png', 'balanced3.png'})
            self.assertTrue(all(call.kwargs['aggregation_label'] == 'Source submissions, shared tasks'
                                for call in render.call_args_list))
            for name in ['tasks2.csv','tasks3.csv']:
                table=pd.read_csv(root/name)
                self.assertTrue(table.submission_unit.eq('source').all())
                self.assertTrue(table.task_weighting.eq('submission-balanced').all())
                self.assertTrue(table.n_tasks_with_both_versions.eq(1).all())


if __name__=='__main__':
    unittest.main()
