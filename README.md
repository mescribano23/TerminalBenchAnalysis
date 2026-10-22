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

Analysis entry points use consecutive two-digit numbers within each folder.
Shared helpers have no numeric prefix. Numbers describe local stages; run the
root `02_build_statistical_results` after the RQ-specific result generators.

```text
scripts/analysis/
|-- 00_characterize_trajectories.py
|-- 01_analyze_leaderboard.py
|-- 02_build_statistical_results.py
|-- diminishing_returns/
|   |-- 00_analyze_effort_success.py
|   |-- 01_plot_effort_success.py
|   `-- 02_plot_configuration_efficiency.py
|-- tasks/
|   |-- 00_analyze_task_domains.py
|   |-- 01_analyze_time_estimates.py
|   |-- 02_analyze_tool_use.py
|   `-- tags/
|       |-- 00_analyze_task_tags.py
|       `-- 01_analyze_tag_effort.py
`-- longitudinal/
    |-- 00_build_dataset.py
    |-- 01_label_tb2_task_categories.py
    |-- 02_label_task_difficulty.py
    |-- 03_analyze_task_composition.py
    |-- 04_analyze_performance.py
    |-- 05_analyze_release_changes.py
    |-- 06_analyze_pass_rate_changes.py
    |-- 07_analyze_difficulty.py
    |-- 08_analyze_effort_changes.py
    |-- 09_analyze_token_accounting.py
    `-- 10_analyze_character_token_usage.py
```

The labeling stages reuse the retained category/difficulty caches; existing
results do not require fresh LLM calls. The commands below give the required
arguments for each dataset and analysis.

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

The trajectory parser reports `shell_invocation_count`, not a decomposed shell-command count. A shell invocation is one extracted shell call or environment interaction; compound expressions issued together, such as `cd repo && pip install -r requirements.txt && pytest`, count as one invocation.

Regenerate leaderboard-level summaries and figures:

```powershell
python -m scripts.analysis.01_analyze_leaderboard `
  --benchmark terminal_bench_2_0

python -m scripts.analysis.01_analyze_leaderboard `
  --benchmark terminal_bench_2_1

python -m scripts.analysis.01_analyze_leaderboard `
  --benchmark terminal_bench_3_0

python -m scripts.analysis.01_analyze_leaderboard `
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
python -m scripts.analysis.tasks.tags.01_analyze_tag_effort
```

Compare trajectory durations with expert and junior task time estimates:

```powershell
python -m scripts.analysis.tasks.01_analyze_time_estimates
```

The human-time comparison uses the submission-balanced median observed duration
per task as the primary agent-duration statistic. Comparisons with expert and
junior estimates are descriptive only because observed agent durations and
estimated human completion times measure different constructs. Medians, paired
differences, duration-to-estimate ratios, and successful-only comparisons are
retained without hypothesis tests or standardized effect sizes; this is not a
causal or literal human-versus-agent speed comparison. The descriptive summary
is saved to
`data/processed_live/task_mining/time_estimates/rq2_2_human_time_description.csv`.

### 5. Analyze Effort, Success, and Diminishing Returns

Regenerate the RQ1 statistical table:

```powershell
python -m scripts.analysis.diminishing_returns.00_analyze_effort_success
```

RQ1 uses two explicit aggregation levels. Pooled trajectory-level summaries
remain trajectory-weighted descriptive views. Task-balanced RQ1 summaries use
`source_submission_id` to aggregate repeated trials to submission-task
units before averaging over tasks, so duplicated retries do not reweight a
task. Task-balanced contrasts use the shared minimum-support rule defined in
`scripts/analysis/support_thresholds.py`. RQ1.1 task pass/fail contrasts require
at least three distinct source submissions in each outcome for a task-metric
pair. All eight success/failure effort measures receive matched-pairs rank-biserial correlation (`rank_biserial`)
and a two-sided Wilcoxon test. The six pre-existing curvature measures retain
their task-conditioned quadratic logistic specifications.

All paired Wilcoxon analyses (RQ1.1, RQ2.3 functional behavior, RQ3.1 version
performance, and RQ3.3 effort including submission-unit sensitivities) use
matched-pairs rank-biserial correlation: `r_rb = (R+ - R-) / (R+ + R-)`.
Ranks are assigned to absolute nonzero task differences, with average ranks for
ties. The shared helper uses the Wilcoxon test's finite-value filtering and
exact-zero exclusion (`zero_method="wilcox"`); empty or all-zero contrasts have
undefined effects (`NaN`). Positive effects follow success minus failure,
used minus not used, or newer minus older version, respectively. A signed-rank
balance can differ in sign from a mean or median difference. No standardized
mean-difference magnitude thresholds are applied to these correlations.
Independent-group Mann-Whitney tests retain Cliff's delta; Spearman correlations
and quadratic regressions retain their existing methods.

The paper-facing source of truth for RQ1 statistics is:

```text
data/processed_live/diminishing_returns/rq1_final_statistical_results.csv
data/processed_live/diminishing_returns/rq1_within_task_effort_summary.csv
data/processed_live/diminishing_returns/rq1_within_task_effort_by_task.csv
data/processed_live/diminishing_returns/rq1_task_outcome_eligibility_thresholds.csv
data/processed_live/diminishing_returns/rq1_1_success_failure_inference.csv
data/processed_live/diminishing_returns/rq1_2_quadratic_regression.csv
```

The compact RQ1.2 regression table retains both coefficients (`beta_1`, `beta_2`)
and `p_value_beta_2`, and appends the saved vertex in standardized and original
units (`turning_point_z`, `turning_point_effort_value`), observed standardized
limits (`z_min`, `z_max`), trajectory/task counts, and
`vertex_strictly_inside_range`. Each model uses individual trajectories with
`z = (log(1+x) - mu) / sigma`, where sigma is the population SD of log effort
in the eligible fitting sample. Task-specific intercepts are conditioned out;
there is no common beta0. The vertex is `-beta_1 / (2*beta_2)` on the z scale
and `exp(mu + sigma*z_peak) - 1` in original units.

All six estimated vertices lie strictly inside their observed z ranges.
Negative curvature is statistically significant for Steps, Total tokens,
Duration, and Positive reported cost; Shell invocations and Structured tool
calls have estimated inverted-U shapes with nonsignificant quadratic terms.
Peak locations are point estimates without confidence intervals and should
not be interpreted as causal effects or optimal effort budgets. The statistical
report presents the coefficients, peaks, ranges, and sample counts together.
These reporting fields use existing model results; no refitting is required.

Regenerate the descriptive effort-bin success-rate figures and appendix-style grouped figures:

```powershell
python -m scripts.analysis.diminishing_returns.01_plot_effort_success
python -m scripts.analysis.diminishing_returns.02_plot_configuration_efficiency
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

The saved equal-frequency binning robustness check yields the same qualitative shape as the fixed-bin analysis for all six effort measures: pass rates rise from the lowest-effort bins to an intermediate peak and then decline in the highest-effort bins. This is a descriptive binning result and does not imply statistically significant quadratic curvature for every metric.
The descriptive/visual outputs are:

```text
data/processed_live/diminishing_returns/rq1_effort_bin_summary.csv
data/processed_live/diminishing_returns/rq1_effort_quantile_bins.csv
data/processed_live/diminishing_returns/rq1_effort_bin_robustness_summary.csv
data/processed_live/terminal_bench_2_0/rq1_task_balanced_effort_success.csv
data/processed_live/diminishing_returns/rq1_task_balanced_effort_success_change_summary.csv
data/processed_live/diminishing_returns/rq1_3_configuration_efficiency.csv

reports/diminishing_returns/effort_bins/rq1_pooled_vs_task_balanced_effort_success.png


reports/diminishing_returns/configuration_pareto/rq1_3_configuration_token_pareto.png
reports/diminishing_returns/configuration_pareto/rq1_3_configuration_duration_pareto.png
reports/diminishing_returns/configuration_pareto/rq1_3_configuration_steps_pareto.png
reports/diminishing_returns/configuration_pareto/rq1_3_configuration_shell_invocations_pareto.png
reports/diminishing_returns/configuration_pareto/rq1_3_configuration_tool_calls_pareto.png
reports/diminishing_returns/configuration_pareto/rq1_3_configuration_observed_cost_pareto.png
reports/diminishing_returns/**/*.png
```

The configuration Pareto figures are the retained RQ1.3 views.

### 6. Analyze Terminal-Bench 2.0 to 2.1 Longitudinal Changes

Build the per-benchmark trajectory tables, then run the longitudinal pipeline:

```powershell
python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_2_0

python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_2_1

python -m scripts.analysis.longitudinal.00_build_dataset

python -m scripts.analysis.longitudinal.06_analyze_pass_rate_changes

python -m scripts.analysis.longitudinal.08_analyze_effort_changes

python -m scripts.analysis.longitudinal.09_analyze_token_accounting
```

For RQ3.1, where TB3.0 and TB4.0 can be compared only as unmatched benchmark task pools, run the descriptive performance-over-version analysis:

```powershell
python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_3_0

python -m scripts.analysis.00_characterize_trajectories `
  --benchmark terminal_bench_4_0

python -m scripts.analysis.longitudinal.04_analyze_performance
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

python -m scripts.analysis.longitudinal.01_label_tb2_task_categories `
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
data/processed_live/longitudinal/inputs/tb2_task_category_llm_labels.csv
```

Generate the task-composition and time-estimate summaries:

```powershell
python -m scripts.analysis.longitudinal.03_analyze_task_composition
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

python -m scripts.analysis.longitudinal.02_label_task_difficulty
```

The `ollama pull` command is harmless if the model is already installed; Ollama will reuse the local copy.

The OpenAI and Anthropic keys are read from `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`. Setting them this way keeps them out of the repository and only applies to the current terminal session. Do not commit API keys to files.

The labeler writes incrementally to:

```text
data/processed_live/longitudinal/inputs/tb3_tb4_task_difficulty_llm_labels.csv
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
python -m scripts.analysis.longitudinal.02_label_task_difficulty `
  --validate-native-tb2-difficulty
```

By default this samples up to ten held-out tasks per native difficulty after
excluding calibration anchors. Because TB2 has only two non-anchor easy tasks,
the default sample is two easy, ten medium, and ten hard tasks. It writes:

```text
data/processed_live/longitudinal/inputs/tb2_difficulty_prompt_validation.csv
```

Validation scores and confusion counts are computed from the retained per-task votes and printed without creating extra CSVs. Use `02_label_task_difficulty --include-diagnostics` to export those optional sidecars.

After labels are generated, compare difficulty distributions and difficulty-stratified pass rates across all four benchmark versions:

```powershell
python -m scripts.analysis.longitudinal.07_analyze_difficulty
```

This combines native TB2.0/TB2.1 task difficulty metadata with TB3.0/TB4.0 LLM labels derived from Harbor difficulty explanations. This is the only longitudinal script that consumes the LLM difficulty-label file.

Treat the TB3/TB4 difficulty distributions as LLM-assigned estimates of author-intended task difficulty, not ground truth. Native difficulty is `unknown` for all 140 TB3/TB4 task-version records. The retained neutralized three-labeler consensus recovered 14 of 22 held-out native TB2 labels (63.6% agreement): 0/2 easy, 7/10 medium, and 7/10 hard. Individual agreement is 14/22 (63.6%) for GPT-4o mini, 12/22 (54.5%) for Claude Haiku 4.5, and 15/22 (68.2%) for Qwen2.5 7B. The retained validation votes support scores for all three voters and their consensus. This small, class-imbalanced TB2 validation is not a measured accuracy on TB3/TB4. The canonical label file now contains the matching neutralized-panel results: 72 hard and 2 medium tasks in TB3.0, and 65 hard and 1 medium in TB4.0.

It writes:

```text
data/processed_live/longitudinal/difficulty_over_versions/difficulty_summary.csv
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

RQ3.3 uses hierarchical medians for every default descriptive estimate: take the
median across trials within each source-submission/task pair, the median across
source submissions within each task, then the median across tasks. Calculate
ratios per trajectory before applying this hierarchy; do not divide aggregated
character and token medians. Version comparisons use metric-valid shared tasks
(89 TB2 tasks and 66 TB3/TB4 tasks). Configuration summaries use their available
eligible tasks, whose counts are exported. Counts and coverage percentages are
record-level diagnostics, not hierarchical estimates.

`rq3_3_aggregation_diagnostics.csv` and `rq3_3_configuration_diagnostics.csv`
contain only hierarchical descriptive estimates. The combined master statistical
CSV contains paired tests. Separate effort and figure-summary sidecars are optional.

The primary unit is the validated or explicitly reconstructed `source_submission_id`, consistently with RQ1 and RQ3.1. Use `--submission-unit leaderboard-url` only for the explicitly named URL sensitivity.

Select this hierarchy explicitly with `--task-weighting submission-balanced`
(the default). Use `--task-weighting trial-weighted` to reproduce the earlier
median across all trials within each task/version, which gives submissions
with more repeated trials more influence. New task-balanced summaries record
the selected method in a `task_weighting` column. This option affects paired
task summaries. Explicitly requested pooled sensitivity exports retain their trajectory-level definition. Non-primary weighting modes write tables only.

The retained `effort_change_submission_balanced_*` figures provide the primary longitudinal evidence. Pooled figures and their older filename copies have been removed. Older figures remain recoverable from Git history. Both TB2 and TB3/TB4 figures use source-submission balancing.
Optional comparisons require `--include-diagnostics` or `--include-sensitivities` and should write to separate output paths using
`--task-balanced-summary-csv`, `--pooled-summary-csv`, and `--out`.
With `--include-tb3-tb4`, the effort script writes the two source-submission-balanced comparison figures.

Generate the character/token results and reasoning coverage tables with:

```powershell
python -m scripts.analysis.longitudinal.10_analyze_character_token_usage
```

This writes three CSVs under `data/processed_live/longitudinal/`:
`rq3_3_aggregation_diagnostics.csv`, `rq3_3_configuration_diagnostics.csv`, and
`rq3_3_reasoning_coverage.csv`. It writes no figures and does not refit models.
The default exports use the source-submission/task hierarchy throughout. Ratios are calculated per trajectory before
aggregation; missing, zero, nonnumeric, negative, and nonfinite total-token
counts are separate exclusion reasons. Counter completeness remains record-level
coverage. The `primary_reasoning:` rows use complete explicit per-call usage or
final-only totals, exclude inferred zeros, and use identical eligible trajectories
for original and adjusted ratios. Their aggregation is labeled
`hierarchical_source_submission_task`. Exact token reconciliation is a separate
QC diagnostic.

For primary reasoning eligibility, every relevant agent step must report finite,
nonnegative completion and reasoning counts, with reasoning no greater than
completion. Explicit zeros are valid; missing counters, including those on
zero-completion error steps, are not inferred. Final-only reasoning totals are
accepted with valid explicit final completion totals where per-call fields are
absent; they do not repair partial per-call reporting. Trajectory completion and
total tokens must be positive, total tokens must cover completion tokens, logged
characters must be finite and nonnegative, and total minus reasoning must remain
positive. All three measures use the same eligible population.

The TB4.0 primary population is 13 configurations / 5,530 trajectories: 4,872 with
complete per-call reporting and 658 with final-only totals. The hierarchical medians are:

| Configuration | Eligible trajectories | Tasks | Reasoning / completion | Logged / total | Logged / (total - reasoning) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gemini 3.8 Flash / mini-swe-agent | 330 | 66 | 64.1% | 0.01053577 | 0.01059505 |
| Claude Sonnet 5 / claude-code | 296 | 61 | 77.6% | 0.03469670 | 0.03541703 |

Historical coverage on positive-completion calls is 4,941/4,947; 4,779 also
reconcile call/final completion totals. The all-relevant-call rule excludes 69
additional records (65 zero-completion steps without reasoning counters and four
unmetered steps). Among 4,872 primary per-call trajectories, 4,710 reconcile final
completion totals; the remaining 162 stay eligible. Full explicit text-plus-reasoning
decomposition exists in 659 eligible trajectories and reconciles in all 659.

Compute `R/C`, `L/T`, and `L/(T-R)` per trajectory before taking hierarchical
configuration medians; `L = message_chars + reasoning_chars + observation_chars`. Token totals
prefer final metrics, with the existing summed-step fallback. Missing character
components invalidate the sum. Logged characters can contain repeated text and
serialized observation wrappers, so they are not unique readable prose.

The hierarchical TB3/TB4 logged-character/total-token ratio is 0.0508 -> 0.0558
(+9.7%), versus 0.1808 -> 0.1704 (-5.8%) for TB2.0/TB2.1. The main effort
figures, paired tests, shared-configuration token comparisons, and Astra-removal
results already used the hierarchy and retain their validated values.

Manuscript changes needed when replacing pooled descriptive estimates:

- Prompt growth: replace the pooled final/first median **9.48x** with the
  hierarchical median **10.71x** (34,463 trajectories / 82 sources / 89 tasks).
  The observed frequency **34,139/34,463 (99.06%)** remains a record count.
- TB2 mini-swe-agent reasoning shares: GPT-5 **77.7%** (432 trajectories / 89 tasks)
  and GPT-5-mini **71.0%** (434 / 89), replacing 78.5% and 70.9%.
- Muse Spark 1.1 (445 / 89): message/completion **0.1880 -> 0.4732** after
  removing reported per-call reasoning; reasoning/completion **56.9%**. Name the
  numerator and denominator explicitly. Logged/total is **0.0842 -> 0.0859**.
- Known mini-swe-agent elision on the main comparison task sets: logged/total
  **0.1704 -> 0.1734** in TB2.1, **0.0508 -> 0.0508** in TB3.0, and
  **0.0558 -> 0.0584** in TB4.0. Within TB4 mini-swe-agent, hierarchical logged
  characters rise from **213,768.75 to 409,845.75 (+91.7%)**, replacing +64.3%.
- TB2.1 configuration logged/total ratios: GPT-5.5 **0.3511** with Terminus-2
  versus **0.0831** with Codex; Gemini 3.1 Pro **0.4815** with Terminus-2 versus
  **0.0649** with Gemini CLI.
- Replace the TB3/TB4 ratio range 0.053--0.056 with the explicit paired comparison
  **0.0508 -> 0.0558**. The corresponding TB2 range is **0.1704--0.1808**.
- TB4 reasoning examples: Gemini **64.1%, 0.0105 -> 0.0106** (330 / 66);
  Sonnet **77.6%, 0.0347 -> 0.0354** (296 / 61). These changes from the latest
  pooled exports reflect weighting only; the eligible populations are unchanged.
  The older 78.0%, 0.0407 -> 0.0431 Sonnet claim also used a different population.

Monthly token/text summaries and prompt-growth ratio summaries use the same
hierarchy within their descriptive cohorts. Their task support and configuration
composition can vary over time. Prompt-growth quartiles and boxplots summarize
submission-balanced task medians; plot sample labels count tasks. Growth and
reconciliation frequencies are explicitly labeled `record_counts`.

Manuscript-ready method wording:

> We report hierarchical medians throughout: we first take the median across
> trials within each source-submission/task pair, then across source submissions
> within each task, and finally across tasks. Ratios are computed per trajectory
> before aggregation. Version comparisons use metric-valid shared tasks;
> configuration-level summaries use their available eligible tasks. Telemetry
> coverage and accounting-quality frequencies are reported as record counts.

Manuscript-ready TB4 reasoning wording:

> In TB4.0, reasoning telemetry is exposed by 13 model-scaffold configurations
> covering 5,605 trajectories. We retain 5,530 trajectories with complete explicit
> per-call counters or valid final-only totals. The hierarchical median share of
> reasoning tokens in completion usage is 64.1% for Gemini 3.8 Flash with
> mini-swe-agent (330 trajectories, 66 tasks) and 77.6% for Claude Sonnet 5 with
> claude-code (296 trajectories, 61 tasks). Excluding reported reasoning tokens
> changes their hierarchical median logged-character/total-token ratios from
> 0.0105 to 0.0106 and from 0.0347 to 0.0354, respectively. Original and adjusted
> ratios use identical eligible trajectories. Completion-token reconciliation
> is a separate quality-control diagnostic, not an inclusion requirement.

The statistical builder computes effort summaries directly from the retained
trajectory datasets. It does not require intermediate effort CSVs. Use
`08_analyze_effort_changes --include-diagnostics` to export those optional tables.

The principal TB2.0 -> TB2.1 comparison characterizes changes in the observed leaderboard/agent-system population. Exact same recorded scaffold+model-id overlap is limited to `gemini-cli/gemini-3.1-pro-preview` and `terminus-2/gemini-3-pro-preview`, both spanning 89 tasks, so same-configuration comparisons are narrow descriptive robustness checks rather than evidence that isolates temporal or model effects. The `gemini-3-pro-preview` string is endpoint provenance, not an asserted underlying-model equivalence: Google released `gemini-3.1-pro-preview` on 2026-02-19 and changed `gemini-3-pro-preview` to point to `gemini-3.1-pro-preview` on 2026-03-09, so post-switch rows can resolve differently from pre-switch rows. No model equivalences are inferred beyond mappings explicitly encoded in retained scripts.

The longitudinal analyses use different denominators depending on which fields are required.

- 38,604 = all retained TB2.0/TB2.1 trajectories in the pooled longitudinal dataset.
- Core observable-effort fields have complete coverage in this dataset: steps, shell invocations, structured tool calls, benchmark-reported duration, and logged readable characters are available for 38,604/38,604 trajectories.
- Provider-reported token fields are available for 38,042/38,604 trajectories (98.5%).
- Reported cost is available for 25,840/38,604 trajectories (66.9%) and is configuration-dependent; cost analyses therefore describe the cost-observed subset.
- 34,463 = the prompt-growth population, requiring at least two valid per-call prompt token values, a positive first count, and an available trajectory prompt-token total.

The prompt-growth analysis excludes 4,141 trajectories: 3,742 lack the required per-call coverage and 399 have a zero first recorded count. These exclusions apply only to this analysis; other analyses retain their own metric-specific populations.

For RQ3.3, **34,139 of 34,463 eligible trajectories (99.06%)** have a strictly larger last recorded prompt-token count than their first. The hierarchical median final/first ratio is **10.71x** across 89 tasks after balancing trials and source submissions (82 sources); the previous pooled median was 9.48x. The positive-first-count rule applies consistently to both growth frequencies and first-to-last ratios. Intermediate calls need not increase monotonically. Agreement between the per-call sum and trajectory prompt total is a diagnostic, not an inclusion gate; it holds for 33,155/34,463 (96.20%). The results record this single population in `token_accounting/input_context_growth_summary.csv` and its coverage in `token_accounting/input_context_audit.json`.

RQ3.1 groups tasks by the official release documentation: 28 release-fixed / 61 not listed as fixed for TB2.0?TB2.1, and 19 release-fixed / 47 not listed as fixed among the 66 shared TB3.0?TB4.0 tasks. The eight officially removed tasks exactly match the local TB3.0-only tasks and are excluded from paired inference. TB4.0 calibrates resources for all retained tasks, so ?not listed as fixed? does not establish unchanged environments, verifiers, or resources.

The [TB2.1 release article](https://www.tbench.ai/news/terminal-bench-2-1) explicitly enumerates 28 IDs. The repository README says 26 and PR #53 enumerates 26: the article adds `crack-7z-hash` and `gpt2-codegolf`. The ID sets reconcile exactly, but the README count conflict remains; the reason for its count is unverified. The primary analysis uses the explicit final-release list and can export a PR26 sensitivity explicitly with `--include-sensitivities`. The required input `data/processed_live/longitudinal/inputs/official_release_task_crosswalk.csv` records exact task IDs, official source URLs, release classifications and the separate historical instruction classifications.

The original 22/67 TB2 and 11/55 shared TB3/TB4 instruction classifications remain input metadata for the existing RQ3.3 subgroup summaries. They do not define the RQ3.1 release groups.

To reproduce only the affected RQ3.1 outputs offline, without regenerating other RQ analyses:

```powershell
python -m scripts.analysis.longitudinal.05_analyze_release_changes
python -m scripts.analysis.02_build_statistical_results --rq3-1-only
```

These RQ3.1 commands consume the existing `task_composition/adjacent_version_task_changes.csv`; regenerate it with `03_analyze_task_composition` first if needed. The results scripts read the verified task mapping directly from `data/processed_live/longitudinal/inputs/official_release_task_crosswalk.csv` and check task IDs when joining it to the analysis data. The RQ3.1 script is `05_analyze_release_changes.py`, and its figure is `reports/longitudinal/pass_rate_official_release_changes_all_versions.png`. The primary release summary uses the `rq3_1_official_release_` prefix; inference is retained in the combined master statistical CSV. The redundant per-task release-status join requires `05_analyze_release_changes --include-diagnostics`; the PR26 sensitivity requires `02_build_statistical_results --include-sensitivities`. Aggregation remains source-submission-balanced within tasks with equal task weights; independent group inference retains two-sided Mann?Whitney U and Cliff's delta.

### 7. Generate Statistical Results

After regenerating the RQ-specific analyses above, generate the integrated results:

```powershell
python -m scripts.analysis.02_build_statistical_results
```

This writes the combined master inferential table (including all RQ3 paired tests), exploratory media summary, shared TB3.0/TB4.0 configuration summary, and the results report:

```text
data/processed_live/statistical_analysis/master_inferential_results.csv
reports/statistical_results.md
```


To reproduce the retained longitudinal results and submission-balanced effort figures using the processed inputs and fixed difficulty labels, run:

```powershell
python -m scripts.analysis.longitudinal.03_analyze_task_composition
python -m scripts.analysis.longitudinal.08_analyze_effort_changes --include-tb3-tb4
python -m scripts.analysis.longitudinal.07_analyze_difficulty
python -m scripts.analysis.longitudinal.10_analyze_character_token_usage
python -m scripts.analysis.02_build_statistical_results
```

The composition, effort and difficulty scripts support separately named URL-grouped sensitivity tables; RQ3.3 also exports trial-weighted tables. It does not change the primary source-submission aggregation. The effort script generates the primary figures from in-memory summaries. CSV sidecars require `--include-diagnostics`, and matched-task vectors require `--include-sensitivities`. Difficulty analysis reads the validated caches without invoking labelers. The statistical script generates all 38 inferential rows and checks their task counts and statistical invariants before writing them. RQ2.2 agent-duration versus human-estimate comparisons appear only in the descriptive report summary.

For comparison runs, use `--output-root PATH` with the effort and statistical scripts to mirror their output layout under another directory. For task composition and difficulty analysis, use `--out-dir PATH` and `--figures-dir PATH`. Inputs continue to come from the repository.

The two RQ3.3 effort figures are `effort_change_submission_balanced_tb2_0_to_tb2_1.png` and `effort_change_submission_balanced_tb3_0_to_tb4_0.png`. Figure percentages compare cross-task medians after source-submission balancing; paired tests use absolute task differences. Metric-specific missing pairs are excluded. Eight descriptive metrics are plotted, and five primary metrics are tested.

The RQ3.1 shared-task change is +38.45 pp for TB2.0Ã¢â‚¬â€œTB2.1 and +14.34 pp for TB3.0Ã¢â‚¬â€œTB4.0. Both the headline and paired tests use the same actual source submission units. The [statistical report](reports/statistical_results.md) provides p-values and effect sizes.

Aggregation regression checks can be run with `python -m unittest discover -s tests -v`.

## Useful Maintenance Commands

To regenerate the retained figures from the current datasets, run the commands below. They use retained task labels and raw trajectories; no scraping or LLM labeling is required. The effort generator writes only the two submission-balanced effort figures.

```powershell
python -m scripts.prepare_processed_tables
python -m scripts.analysis.diminishing_returns.01_plot_effort_success
python -m scripts.analysis.diminishing_returns.02_plot_configuration_efficiency
python -m scripts.analysis.01_analyze_leaderboard --benchmark terminal_bench_2_0
python -m scripts.analysis.01_analyze_leaderboard --benchmark terminal_bench_2_1
python -m scripts.analysis.01_analyze_leaderboard --benchmark terminal_bench_3_0
python -m scripts.analysis.01_analyze_leaderboard --benchmark terminal_bench_4_0
python -m scripts.analysis.tasks.00_analyze_task_domains
python -m scripts.analysis.tasks.01_analyze_time_estimates
python -m scripts.analysis.tasks.tags.01_analyze_tag_effort
python -m scripts.analysis.tasks.02_analyze_tool_use
python -m scripts.analysis.longitudinal.03_analyze_task_composition
python -m scripts.analysis.longitudinal.04_analyze_performance
python -m scripts.analysis.longitudinal.07_analyze_difficulty
python -m scripts.analysis.longitudinal.05_analyze_release_changes
python -m scripts.analysis.longitudinal.06_analyze_pass_rate_changes
python -m scripts.analysis.longitudinal.08_analyze_effort_changes --include-tb3-tb4
python -m scripts.analysis.longitudinal.09_analyze_token_accounting
```

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


### Source submission identity

Actual leaderboard submissions are the balancing unit: TB2.0 74, TB2.1 17,
TB3.0 12, TB4.0 18, with 48,843 retained trajectories. TB2.0 membership is
reconstructed from exact acquisition metadata and task evidence because its
original UUID-to-source cache is absent. Harbor membership uses retained trial
UUID-to-row UUID links. Both Devin versions belong to one TB3.0 submission;
the five Codex/Astra rows remain distinct.

`effective_submission_id` is a configuration/metadata
fingerprint. `configuration_version_id` is distinct from source identity.
Original values are preserved in `legacy_*` columns. Primary CLI analyses use
`--submission-unit source`; corrected URL grouping is a sensitivity with the
same source partition. Source-balanced figure data use `*_source.csv` names;
paired task vectors are optional exports.

Historical scraped dates are preserved, with repaired TB2.0 attribution.
`historical_leaderboard_timestamp` indexes descriptive historical-date cohorts;
its meaning as submission/publication time is unverified. Live leaderboard
dates were not substituted for historical snapshot dates. The original task-version
instruction audit remains an archival classification cache; its historical
full-leaderboard counts are not retained source-submission counts. Use the
new source-identity metadata sidecar for current corpus counts and date ranges.

The retained pipeline contains data acquisition, result generation, shared analysis helpers, and regression tests. The statistical results report is `reports/statistical_results.md`. Task-version classification and difficulty-label caches are required analysis inputs.

### Longitudinal results and inputs

`data/processed_live/longitudinal` contains 21 necessary CSVs, with eight at the
top level. The table below explains the retained layout.

| Location | Purpose |
| --- | --- |
| `trajectory_longitudinal.csv`, `tb3_tb4/trajectory_longitudinal.csv` | Two reusable trajectory datasets; their `.csv.gz` copies are Git storage inputs. |
| `inputs/` | Six required task mappings, historical task classifications, paid category/difficulty labels, and held-out validation votes. |
| `rq3_1_*summary.csv` | Current release-group and benchmark-version summaries. |
| `rq3_3_aggregation_diagnostics.csv` | Effort and character/token summaries for both transitions, with explicit aggregation and sample sizes. |
| `rq3_3_configuration_diagnostics.csv`, `rq3_3_reasoning_coverage.csv`, `rq3_3_shared_configuration_tokens_tb3_tb4.csv` | Configuration, reasoning and matched-system results used in the manuscript. |
| `monthly_pass_rate_historical_dates.csv` | Historical-date pass-rate figure data. |
| `task_composition/` | Task-pool/category summaries and the shared-task table required by the RQ3.1 analysis. |
| `difficulty_over_versions/difficulty_summary.csv` | Combined difficulty distribution and pass-rate results, keyed by version and difficulty. `n_tasks` is metadata coverage; `n_tasks_with_trials` is observed pass-rate coverage. Adjacent changes are computed from these rows. |
| `token_accounting/` | Context-growth and monthly character/token results. |

All paired tests, including RQ3.1 and RQ3.3, are retained in
`data/processed_live/statistical_analysis/master_inferential_results.csv`.
Separate per-RQ inference CSVs duplicate that result and are not prerequisites.
The statistical builder computes its summaries directly from the retained
inputs; `02_build_statistical_results --include-diagnostics` exports the
separate inference tables when explicitly needed.

Default commands do not recreate redundant sidecars. `--include-diagnostics`
opts into effort summaries/figure tables, separate difficulty tables, validation
summaries/confusion counts, or release task joins in their respective scripts.
URL/trial sensitivities and paired-task dumps require `--include-sensitivities`;
exploratory token comparisons require `09_analyze_token_accounting --include-comparisons`.
Write optional experiments outside the canonical result directory using
`--output-root`, `--out-dir`, or explicit output paths. Keep the input caches:
regenerating label caches may require paid LLM calls.
