# TerminalBenchAnalysis

Tools and data for collecting, indexing, and characterizing Terminal-Bench
trajectory traces.

This repository contains a balanced sample of Terminal-Bench trajectories,
leaderboard metadata, and analysis outputs used to study how coding agents move
through terminal-based tasks.

## Repository Contents

```text
.
|-- collect_tbench_leaderboard.py        # Leaderboard scraper and trajectory downloader
|-- leaderboard_v2.json                  # Terminal-Bench v2 leaderboard metadata
|-- trajectory_index_balanced_12.json    # Index for the collected trajectory sample
|-- trajectories_balanced_12/            # Full trajectory JSON files
`-- analysis/
    |-- characterize_trajectories.py     # Corpus characterization script
    |-- corpus_stats.json                # Aggregate corpus statistics
    |-- trajectory_summary.csv           # Per-trajectory summary table
    |-- trajectory_summary.jsonl         # Per-trajectory summary records
    |-- command_patterns.csv             # Extracted command-pattern counts
    |-- representative_snippets.jsonl    # Example trajectory snippets
    `-- trajectory_corpus_characterization.md
```

Trajectory files are organized as:

```text
trajectories_balanced_12/{scaffold}/{model}/{taskChecksum}_{trialId}.json
```

## Dataset Snapshot

- 5,265 trajectory JSON files
- 218 unique Terminal-Bench tasks
- 6 scaffolds: `claude-code`, `hookele`, `mini-swe-agent`, `openhands`,
  `terminus-2`, and `vix`
- 12 scaffold/model submissions sampled with a balanced strategy
- Common trajectory envelope: `schema_version`, `session_id`, `agent`, `steps`,
  and `final_metrics`

The master index is [`trajectory_index_balanced_12.json`](trajectory_index_balanced_12.json).
Each record includes:

- `scaffold`
- `model`
- `taskName`
- `taskChecksum`
- `trialId`
- `reward`
- `cost`
- `duration`
- `filePath`

## Setup

The collection script uses Python and `requests`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install requests
```

If you already have a thesis/project virtual environment, you can use that
instead of creating `.venv`.

## Usage

Run commands from the repository root:

```powershell
cd TerminalBenchAnalysis
```

Refresh leaderboard metadata:

```powershell
python collect_tbench_leaderboard.py --output leaderboard_v2.json
```

Check which leaderboard submissions expose trajectory pages:

```powershell
python collect_tbench_leaderboard.py `
  --check-trajectory-availability `
  --leaderboard-json leaderboard_v2.json
```

Collect the balanced trajectory sample:

```powershell
python collect_tbench_leaderboard.py `
  --collect-trajectories `
  --leaderboard-json leaderboard_v2.json `
  --sample-n 12 `
  --strategy balanced `
  --trajectories-dir trajectories_balanced_12 `
  --trajectory-index trajectory_index_balanced_12.json
```

Run a smaller debug collection:

```powershell
python collect_tbench_leaderboard.py `
  --collect-trajectories `
  --leaderboard-json leaderboard_v2.json `
  --sample-n 3 `
  --strategy balanced `
  --task-limit 5 `
  --trial-limit 2 `
  --trajectories-dir trajectories_debug `
  --trajectory-index trajectory_index_debug.json
```

Regenerate the corpus characterization artifacts:

```powershell
python analysis\characterize_trajectories.py `
  --root trajectories_balanced_12 `
  --leaderboard leaderboard_v2.json `
  --out analysis
```

## Analysis Outputs

The analysis pipeline produces:

- [`analysis/corpus_stats.json`](analysis/corpus_stats.json): aggregate corpus
  statistics, scaffold/model counts, schema coverage, command counts, and
  distribution summaries
- [`analysis/trajectory_summary.csv`](analysis/trajectory_summary.csv):
  tabular per-trajectory metadata
- [`analysis/command_patterns.csv`](analysis/command_patterns.csv): extracted
  command patterns grouped by inferred purpose
- [`analysis/representative_snippets.jsonl`](analysis/representative_snippets.jsonl):
  representative examples for qualitative inspection
- [`analysis/trajectory_corpus_characterization.md`](analysis/trajectory_corpus_characterization.md):
  narrative summary of the corpus

## Loading the Index

```python
import json
import pandas as pd

with open("trajectory_index_balanced_12.json", encoding="utf-8") as f:
    index = json.load(f)

df = pd.DataFrame(index)
print(df.groupby("scaffold")["reward"].agg(["count", "mean"]).round(2))
```

## Notes

- `leaderboard_v2.json` stores aggregate leaderboard task/scaffold/model
  metadata, including fields such as `taskName`, `taskChecksum`, `nTrials`,
  `avgResolutionRate`, and `successCount`.
- Individual trajectory JSON files do not consistently expose per-run pass/fail
  labels; use the index and leaderboard metadata when joining outcomes.
- Some generated analysis files may contain local absolute paths from the
  machine that produced them. These paths are metadata only and are not required
  to load the repository data.
