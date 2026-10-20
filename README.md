# TerminalBenchAnalysis

Tools for collecting Terminal-Bench leaderboard data, downloading trajectory traces, and regenerating the analysis tables and figures used in this project.

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

reports/                             # Regenerated figures
```

Trajectory files are organized as:

```text
data/trajectories/{benchmark}/{scaffold}/{model}/{taskChecksum}_{trialId}.json
```

## Requirements

- Python 3 with `venv` support.
- Git if you are cloning the repository.
- Internet access for scraping benchmark metadata and downloading trajectories.
- Optional: OpenAI and/or Anthropic API access for LLM-based labeling.
- Optional: Ollama for local LLM labeling.

The commands below use **Windows PowerShell** unless stated otherwise.

## Setup

Run all commands from the repository root.

### 1. Create a virtual environment

```powershell
python -m venv .venv
```

### 2. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, allow it for the current terminal session and activate the environment again:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\.venv\Scripts\Activate.ps1
```

When activation succeeds, the prompt should start with `(.venv)`.

On macOS/Linux, use:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

With the virtual environment activated:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Restore large processed tables

Three large generated CSVs are stored as lossless `.csv.gz` files in normal Git. Restore their original paths before running analyses or tests:

```powershell
python -m scripts.prepare_processed_tables
```

This uses only the Python standard library. It restores missing files and refuses to overwrite differing local CSVs. These three compressed tables do not require Git LFS; the raw trajectory files still use LFS.

After intentionally regenerating these CSVs, refresh the compressed copies before committing:

```powershell
python -m scripts.prepare_processed_tables --pack
python -m scripts.prepare_processed_tables --check
git add data/processed_live/terminal_bench_2_0/trajectory_summary.csv.gz data/processed_live/longitudinal/trajectory_longitudinal.csv.gz data/processed_live/longitudinal/tb3_tb4/trajectory_longitudinal.csv.gz
```

The uncompressed copies stay local and are ignored by Git. Compression preserves every byte; analysis scripts and their CSV paths are unchanged.

### 5. Optional: configure LLM labelers

Most analysis scripts do **not** require external LLMs. The LLM-labeling scripts in `scripts/analysis/longitudinal/` can use OpenAI, Anthropic, Ollama, or multiple labelers together.

#### OpenAI

Set the API key in the current PowerShell session:

```powershell
$env:OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
```

#### Anthropic

Set the API key in the current PowerShell session:

```powershell
$env:ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY"
```

These environment variables apply only to the current terminal session. Do not store API keys in the repository or commit them to Git.

#### Ollama

Ollama is only required if you want to use a local model such as `qwen2.5:7b-instruct`.

Install Ollama on Windows:

```powershell
irm https://ollama.com/install.ps1 | iex
```

Close and reopen PowerShell after installation, then verify:

```powershell
ollama --version
```

If PowerShell reports that `ollama` is not recognized, first check that the executable exists:

```powershell
Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
```

If this returns `True`, add Ollama to the current terminal's `PATH`:

```powershell
$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"
```

Then verify again:

```powershell
ollama --version
```

Download the local model used by this repository:

```powershell
ollama pull qwen2.5:7b-instruct
```

Confirm that it is available:

```powershell
ollama list
```

You only need to download the model once.

If a Python labeling script cannot connect to Ollama, start the Ollama server in a separate terminal:

```powershell
ollama serve
```

Leave that terminal open while running the labeling script.

### 6. Verify the environment

```powershell
python --version
python -m pip --version
```

If using Ollama:

```powershell
ollama --version
ollama list
```

## Run Everything In Order

### 1. Refresh Source Data

Scrape Terminal-Bench 2.0 leaderboard metadata:

```powershell
python -m scripts.mining.00_scrape_terminal_bench_2_0_leaderboard
```

The Terminal-Bench 2.0 metadata scrape also resolves and saves the complete trial metadata cache, so it is slower than a leaderboard-table-only refresh.

Scrape Harbor-hosted Terminal-Bench leaderboard metadata:

```powershell
python -m scripts.mining.01_scrape_harbor_terminal_bench_leaderboard

python -m scripts.mining.01_scrape_harbor_terminal_bench_leaderboard `
  --benchmark terminal_bench_3_0

python -m scripts.mining.01_scrape_harbor_terminal_bench_leaderboard `
  --benchmark terminal_bench_4_0
```

Scrape Terminal-Bench 2.0 task metadata:

```powershell
python -m scripts.mining.02_scrape_terminal_bench_2_0_task_catalog
```

Scrape Terminal-Bench 2.0 `task.toml` metadata from GitHub, including expert and junior time estimates:

```powershell
python -m scripts.mining.03_scrape_terminal_bench_2_0_task_toml_metadata
```

### 2. Collect Trajectories

Collect all available Terminal-Bench trajectories after refreshing leaderboard and trial metadata:

```powershell
python -m scripts.mining.00_scrape_terminal_bench_2_0_leaderboard `
  --download-trajectories

python -m scripts.mining.01_scrape_harbor_terminal_bench_leaderboard `
  --download-trajectories

python -m scripts.mining.01_scrape_harbor_terminal_bench_leaderboard `
  --benchmark terminal_bench_3_0 `
  --download-trajectories

python -m scripts.mining.01_scrape_harbor_terminal_bench_leaderboard `
  --benchmark terminal_bench_4_0 `
  --download-trajectories
```

Terminal-Bench 2.0 trajectories are resolved from the trial pages exposed by tbench.ai. Some pages may explicitly report that no trajectory data is available; those records are reported as failures instead of being silently skipped.

### 3. Build Core Analysis Tables

Build trajectory-level summaries from the downloaded trajectories and trial index:

```powershell
python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_2_0

python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_2_1

python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_3_0

python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_4_0
```

`data/processed_live/terminal_bench_2_0/parser_validation_sample.csv` is a prepared 24-trajectory manual-validation sample covering all 12 TB2.0 scaffolds, pass/fail outcomes, providers, and submission dates; it has not itself been manually validated.

The trajectory parser reports `shell_invocation_count`, not a decomposed shell-command count. A shell invocation is one extracted shell call or environment interaction; compound expressions issued together, such as `cd repo && pip install -r requirements.txt && pytest`, count as one invocation.

Regenerate leaderboard-level summaries and figures:

```powershell
python -m scripts.analysis.01_analyze_leaderboard_superficial `
  --benchmark terminal_bench_2_0

python -m scripts.analysis.01_analyze_leaderboard_superficial `
  --benchmark terminal_bench_2_1

python -m scripts.analysis.01_analyze_leaderboard_superficial `
  --benchmark terminal_bench_3_0

python -m scripts.analysis.01_analyze_leaderboard_superficial `
  --benchmark terminal_bench_4_0
```

The public-trajectory subset is not treated as an unbiased sample of all leaderboard submissions. The reproducible availability audit outputs are:

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

The human-time comparison uses the submission-balanced median observed duration
per task as the primary agent-duration statistic. It reports paired Cohen's
`dz` and a two-sided Wilcoxon signed-rank test against expert and junior
estimates. Successful-only task duration remains a descriptive robustness
check; this is not a causal or literal human-versus-agent speed comparison.

### 5. Analyze Effort, Success, and Diminishing Returns

Regenerate the RQ1 statistical table:

```powershell
python -m scripts.analysis.diminishing_returns.00_analyze_diminishing_returns
```

RQ1 uses two explicit aggregation levels. Pooled trajectory-level summaries
remain trajectory-weighted descriptive views. Task-balanced RQ1 summaries use
`source_submission_id` to aggregate repeated trials to submission-task
units before averaging over tasks, so duplicated retries do not reweight a
task. Task-balanced contrasts use the shared minimum-support rule defined in
`scripts/analysis/support_thresholds.py`. RQ1.1 task pass/fail contrasts require
at least three distinct source submissions in each outcome for a task-metric
pair. All eight success/failure effort measures receive paired Cohen's `dz`
and a two-sided Wilcoxon test. The six pre-existing curvature measures retain
their task-conditioned quadratic logistic specifications.

The paper-facing source of truth for RQ1 statistics is:

```text
data/processed_live/diminishing_returns/rq1_final_statistical_results.csv
data/processed_live/diminishing_returns/rq1_within_task_effort_summary.csv
data/processed_live/diminishing_returns/rq1_within_task_effort_by_task.csv
data/processed_live/diminishing_returns/rq1_task_outcome_eligibility_thresholds.csv
data/processed_live/diminishing_returns/rq1_1_success_failure_inference.csv
data/processed_live/diminishing_returns/rq1_2_quadratic_regression.csv
```

Regenerate the descriptive effort-bin success-rate figures and appendix-style grouped figures:

```powershell
python -m scripts.analysis.diminishing_returns.01_plot_diminishing_returns
python -m scripts.analysis.diminishing_returns.02_plot_rq1_3_scaffold_model_effects
```

These figures are descriptive visualizations; the statistical table above is
the inferential source of truth. The task-balanced effort-success bin comparison assigns
bins at the trajectory level, aggregates trajectories within each
source-submission/task/bin cell, averages those cells within task, and then
averages tasks within each effort bin. RQ1.3 configuration efficiency uses the
same submission-task hierarchy before rolling up to scaffold/model
configurations. The consolidated efficiency figures use one point per complete
model + scaffold configuration: color identifies the scaffold, labels name the
important model + scaffold combinations, point size reflects trajectory
support, and the black line traces the configuration-level Pareto frontier.
These figures do not estimate separate causal effects of models or scaffolds.

The saved equal-frequency binning robustness check yields the same qualitative shape as the fixed-bin analysis for all six effort measures: pass rates rise from the lowest-effort bins to an intermediate peak and then decline in the highest-effort bins.
The descriptive/visual outputs are:

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

reports/diminishing_returns/configuration_pareto/rq1_3_configuration_token_pareto.png
reports/diminishing_returns/configuration_pareto/rq1_3_configuration_duration_pareto.png
reports/diminishing_returns/configuration_pareto/rq1_3_configuration_steps_pareto.png
reports/diminishing_returns/configuration_pareto/rq1_3_configuration_shell_invocations_pareto.png
reports/diminishing_returns/configuration_pareto/rq1_3_configuration_tool_calls_pareto.png
reports/diminishing_returns/configuration_pareto/rq1_3_configuration_observed_cost_pareto.png
reports/diminishing_returns/**/*.png
```

The consolidated configuration Pareto views are the default outputs. The
earlier by-model and by-scaffold figures are preserved; pass
`--include-legacy-pareto` to include those views in a future run.

### 6. Analyze Terminal-Bench 2.0 to 2.1 Longitudinal Changes

Build the per-benchmark trajectory tables, then run the longitudinal pipeline:

```powershell
python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_2_0

python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_2_1

python -m scripts.analysis.longitudinal.00_build_dataset

python -m scripts.analysis.longitudinal.01_analyze_instruction_change_robustness

python -m scripts.analysis.longitudinal.02_analyze_pass_rate_changes

python -m scripts.analysis.longitudinal.03_analyze_effort_changes

python -m scripts.analysis.longitudinal.04_analyze_token_accounting
```

For RQ3.1, where TB3.0 and TB4.0 can be compared only as unmatched benchmark task pools, run the descriptive performance-over-version analysis:

```powershell
python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_3_0

python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_4_0

python -m scripts.analysis.longitudinal.05_analyze_performance_over_versions
```

This writes:

```text
data/processed_live/longitudinal/rq3_1_version_performance_summary.csv
reports/longitudinal/rq3_1_performance_over_versions.png
```

To extend the descriptive longitudinal analysis with TB3.0/TB4.0 task composition, task-page difficulty explanations, and comparable LLM-derived difficulty labels, first scrape the Harbor Hub task pages:

```powershell
python -m scripts.mining.07_scrape_harbor_task_pages
```

This writes:

```text
data/processed_live/task_mining/terminal_bench_3_4_harbor_task_pages.csv
data/processed_live/task_mining/terminal_bench_3_4_task_metadata_enriched.csv
data/raw/harbor_task_pages/terminal_bench_task_pages.json
```

Then rebuild the TB3/TB4 longitudinal table with the enriched task metadata:

```powershell
python -m scripts.analysis.longitudinal.00_build_dataset `
  --benchmarks terminal_bench_3_0 terminal_bench_4_0 `
  --task-metadata data\processed_live\task_mining\terminal_bench_3_4_task_metadata_enriched.csv `
  --out data\processed_live\longitudinal\tb3_tb4
```

#### Label TB2 task categories with LLMs

Map the TB2.0/TB2.1 tasks into the native TB3.0/TB4.0 category taxonomy with one or more LLM labelers.

Before running this step:

- Set `OPENAI_API_KEY` if using the OpenAI labeler.
- Set `ANTHROPIC_API_KEY` if using the Anthropic labeler.
- Install Ollama and pull `qwen2.5:7b-instruct` if using the local Ollama labeler.

To reproduce the three-labeler consensus used in this project:

```powershell
$env:OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
$env:ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY"

ollama pull qwen2.5:7b-instruct

python -m scripts.analysis.longitudinal.06_label_tb2_task_categories_with_llm `
  --force `
  --labeler openai:gpt-4o-mini `
  --labeler anthropic:claude-haiku-4-5-20251001 `
  --labeler ollama:qwen2.5:7b-instruct
```

If `ollama` is not recognized on Windows but Ollama is installed, run:

```powershell
$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"
```

Then retry the command.

The target taxonomy is the seven broad categories used by TB3.0/TB4.0:

`Software`, `Science`, `ML`, `Operations`, `Security`, `Hardware`, and `Media`.

The labeler sees only TB2 task metadata and optional task instructions, not trajectory outcomes, pass rates, run duration, token usage, costs, or model names.

Multiple `--labeler provider:model` arguments produce a consensus label and retain the full vote audit in `consensus_votes_json`.

It writes:

```text
data/processed_live/longitudinal/tb2_task_category_llm_labels.csv
```

Generate the task-composition and time-estimate summaries:

```powershell
python -m scripts.analysis.longitudinal.07_analyze_task_composition_over_versions
```

This uses the native TB3.0/TB4.0 category labels and the LLM-assigned TB2 labels to create one `unified_category` taxonomy across all four versions. It also describes task pools, metadata estimates, and observed run durations.

This writes:

```text
data/processed_live/longitudinal/task_composition/version_task_composition_summary.csv
data/processed_live/longitudinal/task_composition/category_composition_by_version.csv
data/processed_live/longitudinal/task_composition/adjacent_version_task_changes.csv
reports/longitudinal/task_composition/task_composition_over_versions.png
reports/longitudinal/task_composition/task_time_estimates_over_versions.png
```

#### Label TB3/TB4 task difficulty with LLMs

TB3/TB4 difficulty labeling uses one fixed protocol: GPT-4o mini neutralizes the evidence, then GPT-4o mini, Claude Haiku 4.5 (`claude-haiku-4-5-20251001`), and Qwen2.5 7B Instruct vote on `easy`, `medium`, or `hard`. To run it:

```powershell
$env:OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
$env:ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY"

ollama pull qwen2.5:7b-instruct

python -m scripts.analysis.longitudinal.08_label_task_difficulty_with_llm
```

The `ollama pull` command is harmless if the model is already installed; Ollama will reuse the local copy.

The OpenAI and Anthropic keys are read from `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`. Setting them this way keeps them out of the repository and only applies to the current terminal session. Do not commit API keys to files.

The labeler writes incrementally to:

```text
data/processed_live/longitudinal/tb3_tb4_task_difficulty_llm_labels.csv
```

The LLM label is intentionally an author-intended, static task-difficulty label. It is based on task-page and task-metadata fields such as `difficulty_explanation`, category, tags, expert time estimate, and fixed TB2.0/TB2.1 author-labeled easy/medium/hard examples used as scale anchors.

Before the three voting labelers see each task, GPT-4o mini removes wording that could directly steer the vote, such as "challenging", "easy", "hard", or direct difficulty-label recommendations. Factual requirements, constraints, technical terms, names, numbers, and time estimates are preserved. The output CSV keeps both raw and neutralized evidence fields and all three votes for audit. The difficulty workflow supports only this panel and mandatory neutralization; the downstream analysis rejects files with incompatible or missing provenance. Cached valid labels are reused; add `--force` only to relabel them.

It must not use trajectory outcomes, leaderboard accuracy, pass rates, run duration, token usage, cost, model names, or other empirical run results. The labeler rejects inputs containing these result columns so that the labels can later be compared against observed pass rates without leakage.

#### Validate the difficulty prompt on held-out TB2 labels

To check whether the difficulty prompt can recover known native TB2 labels, run a
held-out validation sample. The sampled tasks exclude the fixed calibration
examples shown in the prompt, and each sampled task's actual native difficulty
is withheld from the LLM input and joined back only for scoring:

```powershell
python -m scripts.analysis.longitudinal.08_label_task_difficulty_with_llm `
  --validate-native-tb2-difficulty
```

By default this samples up to ten held-out tasks per native difficulty after
excluding calibration anchors. Because TB2 has only two non-anchor easy tasks,
the default sample is two easy, ten medium, and ten hard tasks. It writes:

```text
data/processed_live/longitudinal/tb2_difficulty_prompt_validation.csv
data/processed_live/longitudinal/tb2_difficulty_prompt_validation_summary.csv
data/processed_live/longitudinal/tb2_difficulty_prompt_validation_confusion.csv
```

After labels are generated, compare difficulty distributions and difficulty-stratified pass rates across all four benchmark versions:

```powershell
python -m scripts.analysis.longitudinal.09_analyze_difficulty_over_versions
```

This combines native TB2.0/TB2.1 task difficulty metadata with TB3.0/TB4.0 LLM labels derived from Harbor difficulty explanations. This is the only longitudinal script that consumes the LLM difficulty-label file.

Treat the TB3/TB4 difficulty distributions as LLM-assigned estimates of author-intended task difficulty, not ground truth. Native difficulty is `unknown` for all 140 TB3/TB4 task-version records. The retained neutralized three-labeler consensus recovered 14 of 22 held-out native TB2 labels (63.6% agreement): 0/2 easy, 7/10 medium, and 7/10 hard. Individual agreement is 14/22 (63.6%) for GPT-4o mini, 12/22 (54.5%) for Claude Haiku 4.5, and 15/22 (68.2%) for Qwen2.5 7B. The validation summary records all three voters and their consensus. This small, class-imbalanced TB2 validation is not a measured accuracy on TB3/TB4. The canonical label file now contains the matching neutralized-panel results: 72 hard and 2 medium tasks in TB3.0, and 65 hard and 1 medium in TB4.0.

It writes:

```text
data/processed_live/longitudinal/difficulty_over_versions/difficulty_distribution_over_versions.csv
data/processed_live/longitudinal/difficulty_over_versions/pass_rate_by_difficulty_over_versions.csv
data/processed_live/longitudinal/difficulty_over_versions/pass_rate_change_by_difficulty_over_versions.csv
reports/longitudinal/difficulty_over_versions/difficulty_distribution_over_versions.png
reports/longitudinal/difficulty_over_versions/pass_rate_by_difficulty_over_versions.png
```

New labeling requires both API keys and a running Ollama instance with `qwen2.5:7b-instruct`. Cached labeling and validation runs make no LLM calls.

If the script cannot connect to Ollama, run:

```powershell
ollama serve
```

in a separate terminal and retry.

RQ3.1 performance-over-version results remain descriptive. Because TB3.0 and TB4.0 are not task-matched to TB2.x in this dataset, the TB3/TB4 composition and LLM-difficulty analyses should be interpreted as task-pool characterization and stratified descriptive robustness checks, not as a pure within-task causal difficulty trend across all four benchmark versions.

For the TB2.0 -> TB2.1 performance headline, use the RQ3.1 submission-balanced, task-weighted result consistently: 36.6304% -> 75.0782%, an increase of **38.45 percentage points**. Compute each submission-task pass rate, average equally across submissions within each task, and then average equally across the 89 tasks. The earlier **39.27 pp** result pools trajectories within each task before averaging across tasks (35.8213% -> 75.0943%); the fully pooled trajectory result is **39.05 pp** (36.0705% -> 75.1233%). These are different aggregations of the same 31,103 TB2.0 and 7,501 TB2.1 trajectories. Reserve 38.45 pp for the main task-weighted claim, and name the weighting whenever reporting an alternative. This describes changes in the observed submission populations, not the isolated effect of benchmark fixes on a fixed agent/model population.

The preserved longitudinal token-accounting outputs report the following historical full-dataset summaries (not refreshed after the complete-text parser restoration):

- logged characters: 31,829 -> 35,584 (+11.8%)
- reported input tokens: 189,811 -> 264,066 (+39.1%)
- reported output tokens: 8,788 -> 13,562 (+54.3%)
- reported total tokens: 206,147 -> 281,590 (+36.6%)

Historical RQ3.3 figures keep pooled trajectory medians as descriptive
statistics. Primary longitudinal evidence comes from submission-balanced task
tables, paired tests, and separately named figures. The task table first takes the median within
each source-submission/task pair, then the median across submissions for each shared
task, and finally summarizes paired task changes.

The primary unit is the validated or explicitly reconstructed `source_submission_id`, consistently with RQ1 and RQ3.1. Use `--submission-unit leaderboard-url` only for the explicitly named URL sensitivity.

Select this hierarchy explicitly with `--task-weighting submission-balanced`
(the default). Use `--task-weighting trial-weighted` to reproduce the earlier
median across all trials within each task/version, which gives submissions
with more repeated trials more influence. New task-balanced summaries record
the selected method in a `task_weighting` column. This option affects paired
task summaries; the pooled medians shown in the effort figures retain their
trajectory-level definition.

Existing pooled figures and medians remain descriptive historical views; separately named balanced figures provide the primary longitudinal evidence. Historical outputs remain recoverable from Git history. Active TB2 and TB3/TB4 task tables both use source-submission balancing.
Any comparison of methods should write to separate output paths using
`--task-balanced-summary-csv`, `--pooled-summary-csv`, and `--out`.
The optional `--combined-out` retains the earlier combined effort figure when
used with `--include-tb3-tb4`.

```text
data/processed_live/longitudinal/pooled_effort_summary_refreshed.csv
data/processed_live/longitudinal/task_balanced_effort_summary.csv
data/processed_live/longitudinal/tb3_tb4/pooled_effort_summary_refreshed.csv
data/processed_live/longitudinal/tb3_tb4/task_balanced_effort_summary.csv
```

The principal TB2.0 -> TB2.1 comparison characterizes changes in the observed leaderboard/agent-system population. Exact same recorded scaffold+model-id overlap is limited to `gemini-cli/gemini-3.1-pro-preview` and `terminus-2/gemini-3-pro-preview`, both spanning 89 tasks, so same-configuration comparisons are narrow descriptive robustness checks rather than evidence that isolates temporal or model effects. The `gemini-3-pro-preview` string is endpoint provenance, not an asserted underlying-model equivalence: Google released `gemini-3.1-pro-preview` on 2026-02-19 and changed `gemini-3-pro-preview` to point to `gemini-3.1-pro-preview` on 2026-03-09, so post-switch rows can resolve differently from pre-switch rows. No model equivalences are inferred beyond mappings explicitly encoded in retained scripts.

The longitudinal analyses use different denominators depending on which fields are required.

- 38,604 = all retained TB2.0/TB2.1 trajectories in the pooled longitudinal dataset.
- Core observable-effort fields have complete coverage in this dataset: steps, shell invocations, structured tool calls, benchmark-reported duration, and logged readable characters are available for 38,604/38,604 trajectories.
- Provider-reported token fields are available for 38,042/38,604 trajectories (98.5%).
- Reported cost is available for 25,840/38,604 trajectories (66.9%) and is configuration-dependent; cost analyses therefore describe the cost-observed subset.
- 34,463 = the prompt-growth population, requiring at least two valid per-call prompt token values, a positive first count, and an available trajectory prompt-token total.

The prompt-growth analysis excludes 4,141 trajectories: 3,742 lack the required per-call coverage and 399 have a zero first recorded count. These exclusions apply only to this analysis; other analyses retain their own metric-specific populations.

For RQ3.3, **34,139 of 34,463 eligible trajectories (99.06%)** have a strictly larger last recorded prompt-token count than their first. The positive-first-count rule applies consistently to both growth frequencies and first-to-last ratios. Intermediate calls need not increase monotonically. Agreement between the per-call sum and trajectory prompt total is a diagnostic, not an inclusion gate; it holds for 33,155/34,463 (96.20%). The stashed saved results record this single population in `token_accounting/input_context_growth_summary.csv` and its coverage in `token_accounting/input_context_audit.json`.

Instruction-change robustness uses the audited stored-instruction split: 67 instruction-unchanged tasks (29,011 trajectories) and 22 instruction-changed tasks (9,593 trajectories).

This split concerns stored instruction text only. It does not identify every benchmark modification or establish unchanged tests, environments, resources, or oracle solutions. The [official TB2.1 release](https://www.tbench.ai/news/terminal-bench-2-1) reports fixes to 28 tasks; 11 overlap our 22 stored instruction changes, while 17 have no instruction change in the stored classification. The completed release-document cross-check also flagged a provenance issue: replaying the comparison against the currently available catalog and representative TB2.1 prompts gave 24 changed / 65 unchanged, with `mailman` and `path-tracing-reverse` differing from the stored classification. Keep 22/67 explicitly attributed to the stored audit and treat its exact reproduction as unresolved; do not silently substitute 24/65 into the existing robustness analysis.

### 7. Build the Statistical Audit and Master Table

After regenerating the RQ-specific analyses above, build the integrated audit:

```powershell
python -m scripts.analysis.10_build_statistical_audit
```

This writes the compact master inferential table, provenance/unit audit, RQ3
paired tables, exploratory media summary, shared TB3.0/TB4.0 configuration
summary, and the thesis-ready report:

```text
data/processed_live/statistical_analysis/master_inferential_results.csv
data/processed_live/statistical_analysis/analysis_provenance_and_units.csv
data/processed_live/statistical_analysis/validation_checks.csv
data/processed_live/longitudinal/rq3_1_version_performance_inference.csv
data/processed_live/longitudinal/rq3_1_instruction_change_inference.csv
data/processed_live/longitudinal/rq3_3_effort_inference.csv
reports/statistical_analysis_audit.md
```


To reproduce the current longitudinal tables, balanced and pooled figures, captions, and sensitivities using the retained processed inputs and fixed difficulty labels, run:

```powershell
python -m scripts.analysis.longitudinal.07_analyze_task_composition_over_versions --include-sensitivities
python -m scripts.analysis.longitudinal.03_analyze_effort_changes --include-tb3-tb4 --include-sensitivities
python -m scripts.analysis.longitudinal.09_analyze_difficulty_over_versions --include-sensitivities
python -m scripts.analysis.10_build_statistical_audit --include-sensitivities
```

The sensitivity flag adds separately named URL-grouped tables; RQ3.3 also exports trial-weighted tables. It does not change the primary source-submission aggregation. The effort script writes matched-task vectors and figure data alongside the summary tables. Difficulty analysis reads the validated caches without invoking labelers. The statistical script retains all 40 inferential rows and its validation checks.

For comparison runs, use `--output-root PATH` with the effort and statistical scripts to mirror their output layout under another directory. For task composition and difficulty analysis, use `--out-dir PATH` and `--figures-dir PATH`. Inputs continue to come from the repository. Existing historical pooled figures retain their original filenames.

RQ3.3 filenames distinguish `effort_change_submission_balanced_*` (primary source-submission/shared-task estimates) from `effort_change_pooled_refreshed_*` (descriptive full-text/positive-token trajectory medians). Original `performance_effort_change_over_time*` figures remain historical. Figure percentages compare cross-task medians; paired tests use absolute task differences. Captions and exact method definitions are saved in `reports/longitudinal/effort_figure_captions.json`.

The RQ3.1 shared-task change is +38.45 pp for TB2.0–TB2.1 and +14.34 pp for TB3.0–TB4.0. Both the headline and paired tests use the same actual source submission units. The [statistical report](reports/statistical_analysis_audit.md) provides p-values and effect sizes.

Aggregation regression checks can be run with `python -m unittest discover -s tests -v`. The fixed-label provenance is retained in `reports/longitudinal/difficulty_over_versions/provenance.json`. Historical manuscript comparisons and recovery records are archived separately from the replication package and remain in Git history (results commit `0852679b`, manuscript comparison commit `990866ea`).

## Useful Maintenance Commands

Retry missing, empty, or malformed trajectory files from saved trial metadata without refreshing the leaderboard:

```powershell
python -m scripts.mining.00_scrape_terminal_bench_2_0_leaderboard `
  --retry-trajectories

python -m scripts.mining.01_scrape_harbor_terminal_bench_leaderboard `
  --retry-trajectories

python -m scripts.mining.01_scrape_harbor_terminal_bench_leaderboard `
  --benchmark terminal_bench_3_0 `
  --retry-trajectories

python -m scripts.mining.01_scrape_harbor_terminal_bench_leaderboard `
  --benchmark terminal_bench_4_0 `
  --retry-trajectories
```

With `--benchmark`, generated analysis tables are written under `data/processed_live/{benchmark}/`; generated figures are written under `reports/general_characteristics/{benchmark}/`.


### Source submission identity correction (20 October 2026)

Actual leaderboard submissions are the balancing unit: TB2.0 74, TB2.1 17,
TB3.0 12, TB4.0 18, with 48,843 retained trajectories. TB2.0 membership is
reconstructed from exact acquisition metadata and task evidence because its
original UUID-to-source cache is absent. Harbor membership uses retained trial
UUID-to-row UUID links. Both Devin versions belong to one TB3.0 submission;
the five Codex/Astra rows remain distinct.

`effective_submission_id` is now only an explicitly rebuilt configuration/metadata
fingerprint. `configuration_version_id` is distinct from source identity.
Original values are preserved in `legacy_*` columns. Primary CLI analyses use
`--submission-unit source`; corrected URL grouping is a sensitivity with the
same source partition. Existing `*_effective.csv` filenames are compatibility
aliases with `submission_unit=source`; prefer the new `*_source.csv` names.

Historical scraped dates are preserved, with repaired TB2.0 attribution.
`historical_leaderboard_timestamp` indexes descriptive historical-date cohorts;
its meaning as submission/publication time is unverified. Live leaderboard
dates were not substituted for historical snapshot dates. The original task-version
instruction audit remains an archival classification cache; its historical
full-leaderboard counts are not retained source-submission counts. Use the
new source-identity metadata sidecar for current corpus counts and date ranges.

Standalone diagnostic audits, temporary correction backups/comparisons and their
one-off generators have been removed. The retained report files are
`reports/manuscript_repository_consistency_20261019.md` and
`reports/statistical_analysis_audit.md`. Paper figures and their analysis scripts
remain. `10_build_statistical_audit.py` is retained because it computes the
paper inference tables and regenerates the retained statistical report.
Task-version instruction and label-validation caches remain analysis inputs.
The retained manuscript consistency report is historical and may reference
removed diagnostic artifacts.
