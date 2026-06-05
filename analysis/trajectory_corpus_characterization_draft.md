# TerminalBench Trajectory Corpus Characterization Draft

Root inspected: `C:\Users\marin\OneDrive\Documentos\Tu Delft\MSc Thesis\terminal_bench_trajectory_work\trajectories_balanced_12`
Trajectory JSON files: 5265
Unique task ids inferred: 218

## Reproduce

```powershell
python terminal_bench_trajectory_work/analysis/characterize_trajectories.py
```

## Main Counts

- Scaffolds: [('terminus-2', 1362), ('mini-swe-agent', 1288), ('claude-code', 876), ('openhands', 868), ('vix', 440), ('hookele', 431)]
- Models: [('together_ai/openai/gpt-oss-20b', 466), ('fireworks_ai/accounts/fireworks/models/minimax-m2', 451), ('xai/grok-code-fast-1', 445), ('MiniMax-M2.1', 440), ('claude-opus-4-7', 440), ('claude-sonnet-4-5-20250929', 438), ('gemini/gemini-2.5-pro', 435), ('openai/gpt-5-mini', 434), ('claude-haiku-4-5-20251001', 433), ('moonshotai_Kimi-K2-Instruct-0905', 430), ('gpt-5.1-codex-mini', 426), ('anthropic/claude-sonnet-4-5-20250929', 419), ('gpt-5.1-codex-max', 5), ('claude-opus-4-5-20251101', 3)]
- Outcomes: [('missing', 5265)]
- Step counts: {'count': 5265, 'min': 2, 'p25': 11, 'median': 29, 'mean': 51.060778727445395, 'p75': 66, 'p90': 126.0, 'p95': 183.0, 'max': 796}
- Command counts: {'count': 5265, 'min': 0, 'p25': 0, 'median': 8, 'mean': 26.80949667616334, 'p75': 32, 'p90': 78.0, 'p95': 118.0, 'max': 792}
- Tool-call counts: {'count': 5265, 'min': 0, 'p25': 6, 'median': 19, 'mean': 37.383285849952514, 'p75': 48, 'p90': 95.0, 'p95': 139.0, 'max': 792}
- Cost presence: 5255 trajectories
- Token presence: 5265 trajectories

## Common Command Heads

- `cd`: 28884
- `cat`: 11594
- `str_replace`: 9589
- `python3`: 8078
- `view`: 6960
- `ls`: 5203
- `echo`: 4815
- `create`: 4595
- `#`: 4218
- `plan`: 4031
- `find`: 2620
- `grep`: 2350
- `sed`: 2039
- `pip`: 1968
- `which`: 1789
- `python`: 1498
- `curl`: 1431
- `apt-get`: 1421
- `pmars`: 1415
- `head`: 1364
- `mkdir`: 1184
- `import`: 1120
- `rm`: 1068
- `bash`: 1032
- `C-c`: 1032
- `gcc`: 940
- `cp`: 933
- `for`: 932
- `strings`: 893
- `sleep`: 867

## Candidate Purposes

- `other`: 52423
- `reading_files`: 18136
- `editing_writing_files`: 18097
- `running_scripts_tests`: 10034
- `environment_inspection`: 9961
- `file_content_search`: 9573
- `debugging_diagnostics`: 9488
- `final_verification`: 8513
- `dependency_setup`: 4917
- `unknown`: 10

See `terminal_bench_trajectory_work/analysis/corpus_stats.json`,
`terminal_bench_trajectory_work/analysis/trajectory_summary.csv`,
`terminal_bench_trajectory_work/analysis/command_patterns.csv`, and
`terminal_bench_trajectory_work/analysis/representative_snippets.jsonl` for details.