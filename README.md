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
python -m scripts.mining.00_scrape_terminal_bench_2_0_leaderboard
```

The Terminal-Bench 2.0 metadata scrape also resolves and saves the complete
trial metadata cache, so it is slower than a leaderboard-table-only refresh.

Scrape Terminal-Bench 2.1 leaderboard metadata from Harbor Hub:

```powershell
python -m scripts.mining.01_scrape_terminal_bench_2_1_leaderboard
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

Collect all available Terminal-Bench 2.0 and 2.1 trajectories after refreshing
leaderboard and trial metadata:

```powershell
python -m scripts.mining.00_scrape_terminal_bench_2_0_leaderboard --download-trajectories
python -m scripts.mining.01_scrape_terminal_bench_2_1_leaderboard --download-trajectories
```

Terminal-Bench 2.0 trajectories are resolved from the trial pages exposed by
tbench.ai. Some pages may explicitly report that no trajectory data is
available; those records are reported as failures instead of being silently
skipped.

### 3. Build Core Analysis Tables

Build trajectory-level summaries from the downloaded trajectories and trial
index:

```powershell
python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_0
python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_1
```

`data/processed_live/terminal_bench_2_0/trajectory_schema_inspection.csv` documents the scaffold-stratified TB2.0 schema inspection used during trajectory parser development.

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

### 6. Analyze Terminal-Bench 2.0 to 2.1 Longitudinal Changes

Build the per-benchmark trajectory tables, then run the longitudinal pipeline:

```powershell
python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_0
python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_1
python -m scripts.analysis.longitudinal.00_build_longitudinal_dataset
python -m scripts.analysis.longitudinal.01_plot_instruction_change_robustness
python -m scripts.analysis.longitudinal.02_analyze_longitudinal_changes
python -m scripts.analysis.longitudinal.03_analyze_performance_effort_over_time
python -m scripts.analysis.longitudinal.04_analyze_token_accounting
```

The main longitudinal token-accounting result is reported at the full-dataset
population level:

- logged characters: 31,829 -> 35,584 (+11.8%)
- reported input tokens: 189,811 -> 264,066 (+39.1%)
- reported output tokens: 8,788 -> 13,562 (+54.3%)
- reported total tokens: 206,147 -> 281,590 (+36.6%)

Optional visible-text tokenization audit:

```powershell
python -m scripts.analysis.longitudinal.05_analyze_visible_text_token_accounting
```

This audit tests whether tokenizing the readable text saved in trajectory JSON
files can stand in for provider-reported token usage. It uses only exact
model-specific tokenizers from the installed `tiktoken` OpenAI model registry;
there is no tokenizer-family fallback and no characters-per-token
approximation. With the current local tokenizer registry, the usable cohort is
`openai/gpt-5` in TB2.0: 1,713 trajectories have an exact tokenizer available
(5.51% of TB2.0), and 1,712 have paired visible-text and reported-token values.
No TB2.1 model currently has an exact model-specific tokenizer in the local
registry.

For the paired `gpt-5` cohort, persisted readable trajectory text is far below
reported token usage:

- median visible-text tokens: 6,544
- median reported input tokens: 86,867
- median reported total tokens: 108,429
- median reported-input / visible-text-token ratio: 13.65x
- median reported-total / visible-text-token ratio: 17.30x
- median visible model-output tokens / reported output tokens: 0.10x

These numbers support treating provider-reported tokens as the primary token
accounting field: the trajectory text omits repeated context, hidden or
serialized tool state, provider-side formatting, and other processing that is
not visible as plain saved text. The retained audit outputs are:

```text
data/processed_live/longitudinal/visible_text_token_accounting_summary.csv
data/processed_live/longitudinal/visible_text_tokenizer_coverage_by_model.csv
```

Use `--details-csv PATH` only when row-level visible-text audit data are needed.

The longitudinal analyses use different denominators depending on which fields
are required.

- 38,604 = all retained TB2.0/TB2.1 trajectories in the pooled longitudinal dataset.
- 34,862 = the subset where the raw trajectory contains at least two valid per-call prompt token values.
  The excluded 3,742 trajectories are still valid for pass-rate, effort, logged-character, and benchmark-level token summaries. They are excluded only from the per-call context accumulation analysis because they lack enough per-call prompt-token detail to measure within-trajectory growth.
  Instruction-change robustness uses the audited stored-instruction split: 67 instruction-unchanged tasks (29,011 trajectories) and 22 instruction-changed tasks (9,593 trajectories).

## Useful Maintenance Commands

Retry missing, empty, or malformed trajectory files from saved trial metadata
without refreshing the leaderboard:

```powershell
python -m scripts.mining.00_scrape_terminal_bench_2_0_leaderboard --retry-trajectories
python -m scripts.mining.01_scrape_terminal_bench_2_1_leaderboard --retry-trajectories
```

With `--benchmark`, generated analysis tables are written under
`data/processed_live/{benchmark}/`; generated figures are written under
`reports/general_characteristics/{benchmark}/`.
