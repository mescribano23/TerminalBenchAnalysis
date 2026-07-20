# TerminalBenchAnalysis

Tools for collecting Terminal-Bench leaderboard data, downloading trajectory
traces, and regenerating the analysis tables and figures used in this project.

## Repository Layout

```text
scripts/
|-- mining/                         # Data collection and trajectory indexing
`-- analysis/                       # Trajectory, leaderboard, task, and tag analyses

data/
|-- raw/                            # Scraped source data
|-- indexes/                        # Trajectory trial indexes
|-- trajectories/                   # Downloaded trajectory JSON files
`-- processed_live/                 # Regenerated analysis tables

reports/                           # Regenerated figures
```

Trajectory files are organized as:

```text
data/trajectories/{corpus}/{scaffold}/{model}/{taskChecksum}_{trialId}.json
```

## Setup

Run these commands from the repository root.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, allow scripts for the current session:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\.venv\Scripts\Activate.ps1
```

## Run Everything In Order

### 1. Refresh Source Data

Scrape the current leaderboard metadata:

```powershell
python -m scripts.mining.00_scrape_tbench_leaderboard
```

Scrape Terminal-Bench 2.0 task metadata:

```powershell
python -m scripts.mining.01_scrape_tbench_benchmarks
```

Scrape Terminal-Bench 2.0 `task.toml` metadata from GitHub, including
expert and junior time estimates:

```powershell
python -m scripts.mining.04_scrape_tbench_task_toml_metadata
```

### 2. Collect Trajectories

Collect the balanced trajectory sample used by the analysis:

```powershell
python -m scripts.mining.00_scrape_tbench_leaderboard `
  --collect-trajectories `
  --sample-n 12 `
  --strategy balanced `
  --trajectories-dir data\trajectories\balanced_12 `
  --trajectory-index data\indexes\trajectory_trials_balanced_12.json
```

For a quick smoke test, use a smaller debug collection instead:

```powershell
python -m scripts.mining.00_scrape_tbench_leaderboard `
  --collect-trajectories `
  --sample-n 3 `
  --strategy top `
  --task-limit 5 `
  --trial-limit 2 `
  --trajectories-dir data\trajectories\debug `
  --trajectory-index data\indexes\trajectory_trials_debug.json
```

### 3. Build Core Analysis Tables

Build trajectory-level summaries from the downloaded trajectories and trial
index:

```powershell
python -m scripts.analysis.00_characterize_trajectories
```

Regenerate leaderboard-level summaries and figures:

```powershell
python -m scripts.analysis.01_analyze_leaderboard_superficial
```

### 4. Analyze Tasks

Regenerate task category and difficulty analyses:

```powershell
python -m scripts.analysis.tasks.00_analyze_task_domains
```

Summarize task tags and tag groups:

```powershell
python -m scripts.analysis.tasks.tags.00_analyze_task_tags
```

Cluster tags semantically:

```powershell
python -m scripts.analysis.tasks.tags.01_cluster_task_tags
```

Analyze effort by tag group and semantic tag cluster:

```powershell
python -m scripts.analysis.tasks.tags.02_analyze_tag_effort
```

Compare trajectory durations with expert and junior task time estimates:

```powershell
python -m scripts.analysis.tasks.01_analyze_time_estimates
```

### 5. Analyze Diminishing Returns

Regenerate the main diminishing-returns analysis:

```powershell
python -m scripts.analysis.diminishing_returns.00_analyze_diminishing_returns
```

Optionally add grouped appendix-style figures:

```powershell
python -m scripts.analysis.diminishing_returns.00_analyze_diminishing_returns --by-scaffold
python -m scripts.analysis.diminishing_returns.00_analyze_diminishing_returns --by-model
```

## Useful Maintenance Commands

Refresh only official leaderboard row metrics without re-fetching every
submission task page:

```powershell
python -m scripts.mining.00_scrape_tbench_leaderboard --refresh-row-metrics-only
```

Check which leaderboard submissions expose trajectory pages:

```powershell
python -m scripts.mining.00_scrape_tbench_leaderboard --check-trajectory-availability
```

Generated analysis tables are written under `data/processed_live/`; generated
figures are written under `reports/`.
