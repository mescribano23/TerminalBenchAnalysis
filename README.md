# TerminalBenchAnalysis

Tools and data for collecting, indexing, and characterizing Terminal-Bench
leaderboard submissions and trajectory traces.

## Repository Layout

```text
.
|-- scripts/
|   |-- mining/
|   |   |-- scrape_tbench_leaderboard.py     # Scrape leaderboard and download trajectories
|   |   |-- scrape_tbench_benchmarks.py      # Scrape benchmark task metadata from tbench.ai
|   |   |-- sampling_strategies.py           # Submission sampling strategies
|   |   `-- build_trajectory_index.py        # Trajectory index loading/checkpointing
|   `-- analysis/
|       |-- characterize_trajectories.py     # Build trajectory/corpus summary tables
|       |-- analyze_leaderboard_superficial.py
|       |-- diminishing_returns/
|       |   `-- analyze_diminishing_returns.py
|       `-- tasks/
|           |-- analyze_task_domains.py      # Task category/difficulty summaries and figures
|           `-- tags/
|               |-- analyze_task_tags.py
|               |-- analyze_tag_effort.py
|               `-- cluster_task_tags.py
|-- data/
|   |-- raw/
|   |   |-- leaderboard_submissions_current.json
|   |   `-- leaderboard_submissions_historical.json
|   |-- indexes/
|   |   |-- trajectory_trials_current.json
|   |   |-- trajectory_trials_balanced_12.json
|   |   `-- trajectory_trials_historical.json
|   |-- trajectories/
|   |   |-- current_leaderboard/              # Current downloaded trajectory JSON files
|   |   `-- balanced_12/                     # Historical balanced trajectory sample
|   `-- processed_live/
|       |-- trajectory_summary.csv           # One row per local trajectory
|       |-- trajectory_features_by_outcome.csv
|       |-- task_mining/                     # Task category/difficulty analysis tables
|       |-- diminishing_returns/             # Diminishing-returns analysis tables
|       |-- leaderboard_submission_summary.csv
|       |-- leaderboard_scaffold_variance.csv
|       |-- leaderboard_model_variance.csv
|       |-- leaderboard_model_component_variance.csv
|       |-- corpus_stats.json
|       `-- command_patterns.csv
`-- reports/
    |-- general_characteristics/              # Leaderboard characterization figures
    |-- tasks/                                # Task category, difficulty, and tag figures
    `-- diminishing_returns/                  # Diminishing-returns analysis figures
```

Trajectory files are organized as:

```text
data/trajectories/{corpus}/{scaffold}/{model}/{taskChecksum}_{trialId}.json
```

## Dataset Snapshot

- 5,265 trajectory JSON files.
- 218 unique Terminal-Bench tasks in the local trajectory sample.
- 6 local trajectory scaffolds: `claude-code`, `hookele`, `mini-swe-agent`,
  `openhands`, `terminus-2`, and `vix`.
- 12 scaffold/model submissions sampled with a balanced strategy.

The master trajectory index is:

```text
data/indexes/trajectory_trials_balanced_12.json
```

## Setup

The collection script uses Python, `requests`, and `beautifulsoup4`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install requests beautifulsoup4 pandas numpy matplotlib
```

Run commands from the repository root:

```powershell
cd TerminalBenchAnalysis
```

## Collection

Refresh leaderboard metadata:

```powershell
python -m scripts.mining.scrape_tbench_leaderboard
```

Scrape Terminal-Bench 2.0 task metadata from the benchmark page:

```powershell
python -m scripts.mining.scrape_tbench_benchmarks
```

This generates:

- `data/raw/terminal_bench_2_tasks_current.json`
- `data/processed_live/task_mining/terminal_bench_2_tasks_current.csv`

Each record includes the task `id`, `category`, `difficulty`, full task
`description`, and `tags`. The script reads the live page at
`https://www.tbench.ai/benchmarks/terminal-bench-2` and resolves the embedded
Next.js payload before writing the outputs.

Refresh only the official leaderboard row metrics, without re-fetching every
submission task page:

```powershell
python -m scripts.mining.scrape_tbench_leaderboard --refresh-row-metrics-only
```

Check which leaderboard submissions expose trajectory pages:

```powershell
python -m scripts.mining.scrape_tbench_leaderboard --check-trajectory-availability
```

Collect the balanced trajectory sample:

```powershell
python -m scripts.mining.scrape_tbench_leaderboard `
  --collect-trajectories `
  --sample-n 12 `
  --strategy balanced `
  --trajectories-dir data\trajectories\balanced_12 `
  --trajectory-index data\indexes\trajectory_trials_balanced_12.json
```

Run a smaller debug collection:

```powershell
python -m scripts.mining.scrape_tbench_leaderboard `
  --collect-trajectories `
  --sample-n 3 `
  --strategy top `
  --task-limit 5 `
  --trial-limit 2 `
  --trajectories-dir data\trajectories\debug `
  --trajectory-index data\indexes\trajectory_trials_debug.json
```

## Analysis

Regenerate trajectory and corpus artifacts:

```powershell
python -m scripts.analysis.characterize_trajectories
```

Regenerate the superficial leaderboard analysis artifacts:

```powershell
python -m scripts.analysis.analyze_leaderboard_superficial
```

This also writes first-pass leaderboard characterization figures under
`reports/general_characteristics/`.

Regenerate task-domain category and difficulty CSVs and figures:

```powershell
python -m scripts.analysis.tasks.analyze_task_domains
```

This reads `data/processed_live/trajectory_summary.csv` and
`data/raw/terminal_bench_2_tasks_current.json`, then writes category and
difficulty summaries under `data/processed_live/task_mining/category/` and
`data/processed_live/task_mining/difficulty/`, and figures under
`reports/tasks/`.

Regenerate the diminishing-returns CSVs and figures:

```powershell
python -m scripts.analysis.diminishing_returns.analyze_diminishing_returns
```

Optionally add grouped appendix-style figures:

```powershell
python -m scripts.analysis.diminishing_returns.analyze_diminishing_returns --by-scaffold
python -m scripts.analysis.diminishing_returns.analyze_diminishing_returns --by-model
```

These grouped figures are written under `reports/diminishing_returns/by_scaffold/`
and `reports/diminishing_returns/by_model/`.

## Main Outputs

Created by `python -m scripts.analysis.characterize_trajectories`:

- `data/processed_live/trajectory_summary.csv`: one row per local trajectory with
  scaffold/model/task metadata, reward-backed pass/fail labels, step counts,
  command counts, token/cost fields, and joined leaderboard metadata.
- `data/processed_live/trajectory_features_by_outcome.csv`: passed-vs-failed
  trajectory summaries for length, commands, tool calls, tokens, cost, and
  duration.
- `data/processed_live/corpus_stats.json`: aggregate corpus statistics.
- `data/processed_live/command_patterns.csv`: extracted command-pattern counts.

Created by `python -m scripts.analysis.analyze_leaderboard_superficial`:

- `data/processed_live/leaderboard_submission_summary.csv`: one row per
  leaderboard submission with official scraped accuracy/error fields and
  separate computed task-level metrics.
- `data/processed_live/leaderboard_scaffold_variance.csv`: same-scaffold,
  different-model comparisons.
- `data/processed_live/leaderboard_model_variance.csv`: same-model,
  different-scaffold comparisons.
- `data/processed_live/leaderboard_model_component_variance.csv`: model
  comparison after splitting comma-separated multi-model rows.
- `reports/general_characteristics/`: first-pass live leaderboard visualizations,
  including accuracy distribution, scaffold/model-component violin-box plots,
  and largest within-label accuracy ranges.

Created by `python -m scripts.mining.scrape_tbench_benchmarks`:

- `data/raw/terminal_bench_2_tasks_current.json`: canonical scraped
  Terminal-Bench 2.0 task metadata used by the task-domain analysis.
- `data/processed_live/task_mining/terminal_bench_2_tasks_current.csv`: CSV
  export of the same task metadata, with task `id`, `category`, `difficulty`,
  `description`, and `tags`.

Created by `python -m scripts.analysis.tasks.analyze_task_domains`:

- `data/processed_live/task_mining/category/task_domain_outcome.csv`: one row per task
  category with task counts, trajectory counts, pass/fail counts,
  trajectory-weighted pass rate, and task-weighted pass rate.
- `data/processed_live/task_mining/category/task_domain_effort_summary.csv`: one row per
  task category and effort variable with median, mean, p75, p90, and max effort
  values. The `reports/tasks/category/effort_vars/` heatmap plots medians.
- `data/processed_live/task_mining/difficulty/task_difficulty_outcome.csv`: one row per
  task difficulty with task counts, trajectory counts, pass/fail counts,
  trajectory-weighted pass rate, and task-weighted pass rate.
- `data/processed_live/task_mining/difficulty/task_difficulty_effort_summary.csv`: one row
  per task difficulty and effort variable with median, mean, p75, p90, and max
  effort values.
- `data/processed_live/task_mining/category/model_scaffold/model_category_pass_rates.csv`:
  category pass rates grouped by model.
- `data/processed_live/task_mining/category/model_scaffold/scaffold_category_pass_rates.csv`:
  category pass rates grouped by scaffold. The stacked scaffold composition
  figure derives category shares from this table.
- `data/processed_live/task_mining/category/model_scaffold/provider_category_pass_rates.csv`:
  category pass rates grouped by model provider.
- `data/processed_live/task_mining/category/model_scaffold/source_category_pass_rates.csv`:
  category pass rates grouped by open/closed source classification.
- `data/processed_live/task_mining/difficulty/model_scaffold/model_difficulty_pass_rates.csv`:
  difficulty pass rates grouped by model.
- `data/processed_live/task_mining/difficulty/model_scaffold/scaffold_difficulty_pass_rates.csv`:
  difficulty pass rates grouped by scaffold.
- `data/processed_live/task_mining/difficulty/model_scaffold/provider_difficulty_pass_rates.csv`:
  difficulty pass rates grouped by model provider.
- `data/processed_live/task_mining/difficulty/model_scaffold/source_difficulty_pass_rates.csv`:
  difficulty pass rates grouped by open/closed source classification.
- `data/processed_live/task_mining/category_difficulty/category_difficulty.csv`:
  combined table with the easy/medium/hard mix within each task category (with task
  and trajectory shares), and pass rates for each category/difficulty pair (with
  pass/fail counts).
- `reports/tasks/category/`: task-category figures, including
  task-weighted success, pass/fail counts, task coverage, effort-variable median
  plots, model and scaffold category heatmaps, provider/source heatmaps, and
  scaffold category composition.
- `reports/tasks/difficulty/`: the same outcome, effort,
  model/scaffold, provider/source, and composition views stratified by task
  difficulty.
- `reports/tasks/category_difficulty/`: difficulty composition by
  category and category/difficulty pass-rate heatmap.

Created by `python -m scripts.analysis.diminishing_returns.analyze_diminishing_returns`:

- `data/processed_live/diminishing_returns/diminishing_returns_effort_bins.csv`: trajectory success
  rates with Wilson confidence intervals across effort bins for steps,
  scaffold-normalized steps, commands, tool calls, tokens, duration, and positive
  reported cost.
- `data/processed_live/diminishing_returns/diminishing_returns_variable_coverage.csv`:
  complete-case, positive, zero, and distribution coverage for each effort
  variable, including the positive-cost subset.
- `reports/diminishing_returns/`: pass-rate figures by effort bin. With
  `--by-scaffold` and `--by-model`, this also writes grouped scaffold, model,
  provider, and provider-facetted heatmaps.

## Loading The Index

```python
import json
import pandas as pd

with open("data/indexes/trajectory_trials_balanced_12.json", encoding="utf-8") as f:
    index = json.load(f)

df = pd.DataFrame(index)
print(df.groupby("scaffold")["reward"].agg(["count", "mean"]).round(2))
```

## Notes

- `data/raw/leaderboard_submissions_current.json` stores collected leaderboard metadata,
  including per-task `taskName`, `taskChecksum`, `nTrials`,
  `avgResolutionRate`, and `successCount`.
- Local trajectory JSON files do not consistently expose per-run pass/fail
  labels, but `data/indexes/trajectory_trials_balanced_12.json` now provides
  reliable per-run `reward` labels for the local balanced sample. In that index,
  `reward == 1.0` is treated as pass and `reward == 0.0` as fail.
- Reward was validated against leaderboard task aggregates: complete local
  `(task, scaffold, model)` groups match `avgResolutionRate` exactly; only
  partial groups differ because fewer than all leaderboard trials were
  downloaded.
- Generated analysis files use repo-relative paths where possible. These paths
  are metadata only and are not required to load the repository data.
