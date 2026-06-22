# TerminalBenchAnalysis

Tools and data for collecting, indexing, and characterizing Terminal-Bench
leaderboard submissions and trajectory traces.

## Repository Layout

```text
.
|-- scripts/
|   |-- mining/
|   |   |-- scrape_tbench_leaderboard.py     # Scrape leaderboard and download trajectories
|   |   |-- sampling_strategies.py           # Submission sampling strategies
|   |   `-- build_trajectory_index.py        # Trajectory index loading/checkpointing
|   `-- analysis/
|       |-- characterize_trajectories.py     # Build trajectory/corpus summary tables
|       |-- analyze_leaderboard_superficial.py
|       `-- analyze_diminishing_returns.py
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
|   `-- processed/
|       |-- trajectory_summary.csv           # One row per local trajectory
|       |-- trajectory_features_by_outcome.csv
|       |-- diminishing_returns_effort_bins.csv
|       |-- diminishing_returns_variable_coverage.csv
|       |-- leaderboard_submission_summary.csv
|       |-- leaderboard_scaffold_variance.csv
|       |-- leaderboard_model_variance.csv
|       |-- leaderboard_model_component_variance.csv
|       |-- corpus_stats.json
|       `-- command_patterns.csv
`-- reports/
    |-- general_characteristics/              # Leaderboard characterization figures
    `-- figures_live/                         # Other generated analysis figures
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
python -m pip install requests beautifulsoup4
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

Regenerate the diminishing-returns CSVs and figures:

```powershell
python -m scripts.analysis.analyze_diminishing_returns
```

Optionally add grouped appendix-style figures:

```powershell
python -m scripts.analysis.analyze_diminishing_returns --by-scaffold
python -m scripts.analysis.analyze_diminishing_returns --by-model
```

These grouped figures are written under `reports/figures/by_scaffold/` and
`reports/figures/by_model/`.

## Main Outputs

- `data/processed/trajectory_summary.csv`: one row per local trajectory with
  scaffold/model/task metadata, reward-backed pass/fail labels, step counts,
  command counts, token/cost fields, and joined leaderboard metadata.
- `data/processed/trajectory_features_by_outcome.csv`: passed-vs-failed
  trajectory summaries for length, commands, tool calls, tokens, cost, and
  duration.
- `data/processed/diminishing_returns_effort_bins.csv`: trajectory success rates
  with Wilson confidence intervals across effort bins for steps,
  scaffold-normalized steps, commands, tool calls, tokens, duration, and positive
  reported cost.
- `data/processed/diminishing_returns_variable_coverage.csv`: complete-case,
  positive, zero, and distribution coverage for each effort variable, including
  the positive-cost subset.
- `data/processed/leaderboard_submission_summary.csv`: one row per leaderboard
  submission with official scraped accuracy/error fields and separate computed
  task-level metrics.
- `data/processed/leaderboard_scaffold_variance.csv`: same-scaffold,
  different-model comparisons.
- `data/processed/leaderboard_model_variance.csv`: same-model,
  different-scaffold comparisons.
- `data/processed/leaderboard_model_component_variance.csv`: model comparison
  after splitting comma-separated multi-model rows.
- `reports/general_characteristics/`: first-pass live leaderboard visualizations,
  including accuracy distribution, scaffold/model-component violin-box plots,
  and largest within-label accuracy ranges.
- `data/processed/corpus_stats.json`: aggregate corpus statistics.
- `data/processed/command_patterns.csv`: extracted command-pattern counts.

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
