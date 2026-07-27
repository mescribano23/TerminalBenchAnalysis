# TerminalBenchAnalysis

Tools for collecting Terminal-Bench leaderboard data, downloading trajectory
traces, and regenerating the analysis tables and figures used in this project.

## Repository Layout

```text
scripts/
|-- mining/                         # Data collection and trajectory indexing
`-- analysis/                       # Trajectory, leaderboard, task, and tag analyses

data/
|-- raw/{benchmark}/                # Scraped source data
|-- indexes/{benchmark}/            # Trajectory trial indexes
|-- trajectories/                   # Downloaded trajectory JSON files
`-- processed_live/                 # Regenerated analysis tables

reports/                           # Regenerated figures
```

Trajectory files are organized as:

```text
data/trajectories/{benchmark}/{scaffold}/{model}/{taskChecksum}_{trialId}.json
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

Scrape Terminal-Bench 2.0 leaderboard metadata:

```powershell
python -m scripts.mining.00_scrape_terminal_bench_2_0_leaderboard --benchmark terminal_bench_2_0
```

Scrape Terminal-Bench 2.1 leaderboard metadata from Harbor Hub:

```powershell
python -m scripts.mining.01_scrape_terminal_bench_2_1_leaderboard --benchmark terminal_bench_2_1 --skip-trajectories
```

Scrape Terminal-Bench 2.0 task metadata:

```powershell
python -m scripts.mining.02_scrape_terminal_bench_2_0_task_catalog
```

Scrape Terminal-Bench 2.0 `task.toml` metadata from GitHub, including
expert and junior time estimates:

```powershell
python -m scripts.mining.03_scrape_terminal_bench_2_0_task_toml_metadata
```

### 2. Collect Trajectories

Collect all Terminal-Bench 2.1 Harbor leaderboard trajectories:

```powershell
python -m scripts.mining.01_scrape_terminal_bench_2_1_leaderboard --benchmark terminal_bench_2_1
```

For a quick smoke test, use a smaller debug collection instead:

```powershell
python -m scripts.mining.00_scrape_terminal_bench_2_0_leaderboard `
  --collect-trajectories `
  --sample-n 3 `
  --task-limit 5 `
  --trial-limit 2 `
  --trajectories-dir data\trajectories\terminal_bench_2_0_debug `
  --trajectory-index data\indexes\terminal_bench_2_0\trajectory_trials_debug.json
```

For a quick Terminal-Bench 2.1 smoke test:

```powershell
python -m scripts.mining.01_scrape_terminal_bench_2_1_leaderboard `
  --benchmark terminal_bench_2_1 `
  --limit 1 `
  --trial-limit 2 `
  --trajectories-dir data\trajectories\terminal_bench_2_1_debug `
  --trajectory-index data\indexes\terminal_bench_2_1\trajectory_trials_debug_2_1.json `
  --output data\raw\terminal_bench_2_1\leaderboard_submissions_debug_2_1.json
```

### 3. Build Core Analysis Tables

Build trajectory-level summaries from the downloaded trajectories and trial
index:

```powershell
python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_0
python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_1
```

Regenerate leaderboard-level summaries and figures:

```powershell
python -m scripts.analysis.01_analyze_leaderboard_superficial --benchmark terminal_bench_2_0
python -m scripts.analysis.01_analyze_leaderboard_superficial --benchmark terminal_bench_2_1
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

### 6. Analyze Terminal-Bench 2.0 vs 2.1 Trajectory Drift

First make sure each benchmark has its own characterized trajectory table:

```powershell
python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_0
python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_1
```

Build the combined, version-labelled trajectory table:

```powershell
python -m scripts.analysis.longitudinal.00_build_longitudinal_dataset
```

Run descriptive comparisons: raw metric shifts, task overlap, task-matched
differences, task-mix reweighting, overlapping agent-key checks, and
command-pattern drift:

```powershell
python -m scripts.analysis.longitudinal.01_compare_versions
```

Fit adjusted version models to test whether 2.1 differences remain after
task, scaffold, model, and agent-key controls:

```powershell
python -m scripts.analysis.longitudinal.02_fit_adjusted_version_models
```

The main outputs are written under:

```text
data/processed_live/longitudinal/
reports/longitudinal/
```

## Useful Maintenance Commands

Refresh only official leaderboard row metrics without re-fetching every
submission task page:

```powershell
python -m scripts.mining.00_scrape_terminal_bench_2_0_leaderboard --refresh-row-metrics-only
```

Check which leaderboard submissions expose trajectory pages:

```powershell
python -m scripts.mining.00_scrape_terminal_bench_2_0_leaderboard --check-trajectory-availability
```

With `--benchmark`, generated analysis tables are written under
`data/processed_live/{benchmark}/`; generated figures are written under
`reports/general_characteristics/{benchmark}/`.
