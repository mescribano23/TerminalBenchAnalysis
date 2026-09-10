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

`data/processed_live/terminal_bench_2_0/parser_validation_sample.csv` is a prepared 24-trajectory manual-validation sample covering all 12 TB2.0 scaffolds, pass/fail outcomes, providers, and submission dates; it has not itself been manually validated.

The trajectory parser reports `shell_invocation_count`, not a decomposed shell-command count. A shell invocation is one extracted shell call or environment interaction; compound expressions issued together, such as `cd repo && pip install -r requirements.txt && pytest`, count as one invocation.

Regenerate leaderboard-level summaries and figures:

```powershell
python -m scripts.analysis.01_analyze_leaderboard_superficial --benchmark terminal_bench_2_0
python -m scripts.analysis.01_analyze_leaderboard_superficial --benchmark terminal_bench_2_1
```

The public-trajectory subset is not treated as an unbiased sample of all
leaderboard submissions. The reproducible availability audit outputs are:

```text
data/processed_live/{benchmark}/leaderboard_trajectory_availability_summary.csv
data/processed_live/{benchmark}/leaderboard_trajectory_availability_by_scaffold.csv
data/processed_live/{benchmark}/leaderboard_trajectory_availability_by_model.csv
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

This step also writes `data/processed_live/task_mining/tags/perceptual_media_tasks.csv`, a strict metadata-defined secondary/exploratory task group. Inclusion requires a task metadata tag in `ocr`, `image-processing`, `images`, or `video-processing`, or category `video-processing`; description-only keyword matches are not included.

Analyze effort by manual tag group:

```powershell
python -m scripts.analysis.tasks.tags.02_analyze_tag_effort
```

Compare trajectory durations with expert and junior task time estimates:

```powershell
python -m scripts.analysis.tasks.01_analyze_time_estimates
```

The human-time comparison uses median observed trajectory duration per task as the primary agent-duration statistic and retains mean duration as a sensitivity statistic. It is a descriptive comparison to benchmark time estimates, not a causal or literal human-versus-agent speed comparison.

### 5. Analyze Effort, Success, and Diminishing Returns

Regenerate the RQ1 statistical table:

```powershell
python -m scripts.analysis.diminishing_returns.00_analyze_diminishing_returns
```

RQ1 uses two explicit aggregation levels. Pooled trajectory-level summaries
remain trajectory-weighted descriptive views. Task-balanced RQ1 summaries use
`effective_submission_id` to aggregate repeated trials to submission-task
units before averaging over tasks, so duplicated retries do not reweight a
task. RQ1.1 task pass/fail contrasts require at least three distinct effective
submissions in each outcome for a task-metric pair; the retained six effort
measures are tested with Wilcoxon and task-conditioned quadratic logistic
specifications.

The paper-facing source of truth for RQ1 statistics is:

```text
data/processed_live/diminishing_returns/rq1_final_statistical_results.csv
data/processed_live/diminishing_returns/rq1_within_task_effort_summary.csv
data/processed_live/diminishing_returns/rq1_within_task_effort_by_task.csv
data/processed_live/diminishing_returns/rq1_task_outcome_eligibility_thresholds.csv
```

Regenerate the descriptive effort-bin success-rate figures and appendix-style
grouped figures:

```powershell
python -m scripts.analysis.diminishing_returns.01_plot_diminishing_returns
python -m scripts.analysis.diminishing_returns.02_plot_rq1_3_scaffold_model_effects
```

These figures are descriptive visualizations; the statistical table above is
the inferential source of truth. The task-balanced effort-success curve assigns
bins at the trajectory level, aggregates trajectories within each
effective-submission/task/bin cell, averages those cells within task, and then
averages tasks within each effort bin. RQ1.3 configuration efficiency uses the
same submission-task hierarchy before rolling up to scaffold/model
configurations. The descriptive/visual outputs are:

```text
data/processed_live/diminishing_returns/rq1_effort_bin_summary.csv
data/processed_live/diminishing_returns/rq1_effort_quantile_bins.csv
data/processed_live/diminishing_returns/rq1_effort_bin_robustness_summary.csv
data/processed_live/terminal_bench_2_0/rq1_task_balanced_effort_success.csv
data/processed_live/diminishing_returns/rq1_task_balanced_effort_success_change_summary.csv
data/processed_live/diminishing_returns/rq1_3_configuration_efficiency.csv
reports/diminishing_returns/effort_bins/rq1_pooled_vs_task_balanced_effort_success.png
reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_token_pareto.png
reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_duration_pareto.png
reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_steps_pareto.png
reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_shell_invocations_pareto.png
reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_tool_calls_pareto.png
reports/diminishing_returns/by_scaffold_pareto/rq1_3_by_scaffold_configuration_observed_cost_pareto.png
reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_token_pareto.png
reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_duration_pareto.png
reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_steps_pareto.png
reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_shell_invocations_pareto.png
reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_tool_calls_pareto.png
reports/diminishing_returns/by_model_pareto/rq1_3_by_model_configuration_observed_cost_pareto.png
reports/diminishing_returns/**/*.png
```

### 6. Analyze Terminal-Bench 2.0 to 2.1 Longitudinal Changes

Build the per-benchmark trajectory tables, then run the longitudinal pipeline:

```powershell
python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_0
python -m scripts.analysis.00_characterize_trajectories --benchmark terminal_bench_2_1
python -m scripts.analysis.longitudinal.00_build_dataset
python -m scripts.analysis.longitudinal.01_analyze_instruction_change_robustness
python -m scripts.analysis.longitudinal.02_analyze_pass_rate_changes
python -m scripts.analysis.longitudinal.03_analyze_effort_changes
python -m scripts.analysis.longitudinal.04_analyze_token_accounting
```

The main longitudinal token-accounting result is reported at the full-dataset
population level:

- logged characters: 31,829 -> 35,584 (+11.8%)
- reported input tokens: 189,811 -> 264,066 (+39.1%)
- reported output tokens: 8,788 -> 13,562 (+54.3%)
- reported total tokens: 206,147 -> 281,590 (+36.6%)

The main RQ4 effort figure keeps pooled trajectory medians as descriptive headline statistics. A task-balanced robustness table is also retained: for each of the 89 shared tasks, it computes the within-version task median in TB2.0 and TB2.1 and then summarizes paired changes over all shared tasks and over the 67 instruction-unchanged tasks.

```text
data/processed_live/longitudinal/task_balanced_effort_pooled_summary.csv
data/processed_live/longitudinal/task_balanced_effort_summary.csv
data/processed_live/longitudinal/task_balanced_effort_by_task.csv
data/processed_live/longitudinal/comparable_configuration_audit.csv
```

The principal TB2.0 -> TB2.1 comparison characterizes changes in the observed leaderboard/agent-system population. Exact same scaffold+model overlap is limited to `gemini-cli/gemini-3.1-pro-preview` and `terminus-2/gemini-3-pro-preview`, both spanning 89 tasks, so same-configuration comparisons are narrow descriptive robustness checks rather than evidence that isolates temporal or model effects. No model equivalences are inferred beyond mappings explicitly encoded in retained scripts.

The longitudinal analyses use different denominators depending on which fields
are required.

- 38,604 = all retained TB2.0/TB2.1 trajectories in the pooled longitudinal dataset.
- Core observable-effort fields have complete coverage in this dataset: steps, shell invocations, structured tool calls, benchmark-reported duration, and logged readable characters are available for 38,604/38,604 trajectories.
- Provider-reported token fields are available for 38,042/38,604 trajectories (98.5%).
- Reported cost is available for 25,840/38,604 trajectories (66.9%) and is configuration-dependent; cost analyses therefore describe the cost-observed subset.
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
