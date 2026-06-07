# TerminalBenchAnalysis

Tools and data for collecting, indexing, and characterizing Terminal-Bench
leaderboard submissions and trajectory traces.

## Repository Layout

```text
.
|-- scripts/
|   |-- collect_tbench_leaderboard.py        # Scrape leaderboard and download trajectories
|   |-- characterize_trajectories.py         # Build trajectory/corpus summary tables
|   `-- analyze_leaderboard_superficial.py   # Accuracy and scaffold/model variance analysis
|-- data/
|   |-- raw/
|   |   `-- leaderboard_v2.json              # Collected Terminal-Bench v2 leaderboard metadata
|   |-- indexes/
|   |   `-- trajectory_index_balanced_12.json
|   |-- trajectories/
|   |   `-- balanced_12/                     # Downloaded trajectory JSON files
|   `-- processed/
|       |-- trajectory_summary.csv           # One row per local trajectory
|       |-- trajectory_outcome_by_scaffold_model.csv
|       |-- trajectory_features_by_outcome.csv
|       |-- leaderboard_submission_summary.csv
|       |-- leaderboard_scaffold_variance.csv
|       |-- leaderboard_model_variance.csv
|       |-- leaderboard_model_component_variance.csv
|       |-- corpus_stats.json
|       |-- command_patterns.csv
|       `-- representative_snippets.jsonl
`-- reports/
    |-- leaderboard_superficial_analysis.md
    `-- trajectory_corpus_characterization.md
```

Trajectory files are organized as:

```text
data/trajectories/balanced_12/{scaffold}/{model}/{taskChecksum}_{trialId}.json
```

## Dataset Snapshot

- 5,265 trajectory JSON files.
- 218 unique Terminal-Bench tasks in the local trajectory sample.
- 6 local trajectory scaffolds: `claude-code`, `hookele`, `mini-swe-agent`,
  `openhands`, `terminus-2`, and `vix`.
- 12 scaffold/model submissions sampled with a balanced strategy.

The master trajectory index is:

```text
data/indexes/trajectory_index_balanced_12.json
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
python scripts\collect_tbench_leaderboard.py
```

Refresh only the official leaderboard row metrics, without re-fetching every
submission task page:

```powershell
python scripts\collect_tbench_leaderboard.py --refresh-row-metrics-only
```

Check which leaderboard submissions expose trajectory pages:

```powershell
python scripts\collect_tbench_leaderboard.py --check-trajectory-availability
```

Collect the balanced trajectory sample:

```powershell
python scripts\collect_tbench_leaderboard.py `
  --collect-trajectories `
  --sample-n 12 `
  --strategy balanced `
  --trajectories-dir data\trajectories\balanced_12 `
  --trajectory-index data\indexes\trajectory_index_balanced_12.json
```

Run a smaller debug collection:

```powershell
python scripts\collect_tbench_leaderboard.py `
  --collect-trajectories `
  --sample-n 3 `
  --strategy balanced `
  --task-limit 5 `
  --trial-limit 2 `
  --trajectories-dir data\trajectories\debug `
  --trajectory-index data\indexes\trajectory_index_debug.json
```

## Analysis

Regenerate trajectory and corpus artifacts:

```powershell
python scripts\characterize_trajectories.py
```

Regenerate the superficial leaderboard analysis:

```powershell
python scripts\analyze_leaderboard_superficial.py
```

## Main Outputs

- `data/processed/trajectory_summary.csv`: one row per local trajectory with
  scaffold/model/task metadata, reward-backed pass/fail labels, step counts,
  command counts, token/cost fields, and joined leaderboard metadata.
- `data/processed/trajectory_outcome_by_scaffold_model.csv`: trajectory-level
  pass/fail counts and success rates by local scaffold/model directory.
- `data/processed/trajectory_features_by_outcome.csv`: passed-vs-failed
  trajectory summaries for length, commands, tool calls, tokens, cost, and
  duration.
- `data/processed/leaderboard_submission_summary.csv`: one row per leaderboard
  submission with official scraped accuracy/error fields and separate computed
  task-level metrics.
- `reports/leaderboard_superficial_analysis.md`: readable accuracy, variance,
  and scaffold/model comparison report.
- `data/processed/leaderboard_scaffold_variance.csv`: same-scaffold,
  different-model comparisons.
- `data/processed/leaderboard_model_variance.csv`: same-model,
  different-scaffold comparisons.
- `data/processed/leaderboard_model_component_variance.csv`: model comparison
  after splitting comma-separated multi-model rows.
- `data/processed/corpus_stats.json`: aggregate corpus statistics.
- `data/processed/command_patterns.csv`: extracted command-pattern counts.
- `data/processed/representative_snippets.jsonl`: examples for qualitative
  inspection.
- `reports/trajectory_corpus_characterization.md`: narrative corpus summary.

## Loading The Index

```python
import json
import pandas as pd

with open("data/indexes/trajectory_index_balanced_12.json", encoding="utf-8") as f:
    index = json.load(f)

df = pd.DataFrame(index)
print(df.groupby("scaffold")["reward"].agg(["count", "mean"]).round(2))
```

## Notes

- `data/raw/leaderboard_v2.json` stores collected leaderboard metadata,
  including per-task `taskName`, `taskChecksum`, `nTrials`,
  `avgResolutionRate`, and `successCount`.
- Local trajectory JSON files do not consistently expose per-run pass/fail
  labels, but `data/indexes/trajectory_index_balanced_12.json` now provides
  reliable per-run `reward` labels for the local balanced sample. In that index,
  `reward == 1.0` is treated as pass and `reward == 0.0` as fail.
- Reward was validated against leaderboard task aggregates: complete local
  `(task, scaffold, model)` groups match `avgResolutionRate` exactly; only
  partial groups differ because fewer than all leaderboard trials were
  downloaded.
- Generated analysis files use repo-relative paths where possible. These paths
  are metadata only and are not required to load the repository data.
