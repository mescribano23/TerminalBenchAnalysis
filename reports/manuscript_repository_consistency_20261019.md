# Manuscript–repository consistency audit

**Paper:** *What Pass Rates Don't Tell You: A Trajectory Analysis of Terminal-Bench Agents*  
**Audit date:** 19 October 2026  
**Authoritative checkout:** `7d3f0048da23ee541204c14e04bf9d44e7399f11`  
**Manuscript:** supplied attachment `C:/Users/marin/.codex/attachments/81307294-7b75-4eac-a0c1-03f1887d8d88/Pasted text.txt`, SHA-256 `131e8b1b3c003ae6c17e54922737ec1e33f84bde52ed8392bdfc54f7b95f8ccc`.

## 1. Scope, authority, and how to apply this report

This audit compares the active, uncommented text of the supplied manuscript with the current checkout, including processed tables, scripts, figures, and provenance. Manuscript line numbers below refer to the supplied attachment, not an Overleaf file. Distinctive quotations are the primary locators. Commented-out alternatives are not treated as published claims; their relevant stale values are identified separately. No Overleaf files were accessed or changed. The local checkout's commit was verified; remote publication was not independently revalidated.

All checks were read-only. No analysis entry point, statistical fit, labeling call, test suite that generates outputs, or figure generator was run. Inspection included arithmetic summaries of existing processed rows, direct comparison of stored values, SHA-256 checks, and reading the 66 indexed files omitted from the retained TB2.1 table; all 66 contain `null`. The requested report is the only repository file created. It is to remain uncommitted and unpushed.

The external archive consulted is `../TerminalBenchAnalysis-archives/cleanup-20261019-990866ea/`, particularly `files/reports/analysis_refresh_20261019/{manuscript_updates.md,before_after.md,master_before_after.csv,manuscript_direction_changes.csv,manuscript_artifacts.csv,rq3_3_aggregation_comparison.csv,shared_configuration_tokens_before_after.csv,provenance.json}`. Its historical values identify changes; **current files take precedence**. Historical verification logs are evidence of earlier checks, not checks rerun in this audit. In particular, their pre-commit statements about uncommitted work do not describe today's published checkout.

Statuses:

- **VERIFIED — correct:** matches retained current evidence at manuscript precision and for the stated population.
- **UPDATE REQUIRED — incorrect or outdated:** a current authoritative replacement exists.
- **WORDING CHANGE — numerical result correct but interpretation misleading:** includes missing estimator or population qualifiers and methodological imprecision.
- **UNVERIFIED — evidence insufficient:** a retained result, original provenance, or comparable protocol is absent. Do not invent a replacement number.

The final count uses **claim groups**, not individual digits or repeated occurrences: one V-register row or one R-register item is one group. Some groups contain several linked values or a complete table. Repeated abstract/discussion claims are separate revision locations. The appended evidence tables contain the exact values behind these groups, including values already correct. They are not extra claims added to inflate the count.

### Principal conclusions for the reviser

1. Retain **48,843 trajectories / 48,785 binary outcomes**, the version-specific retained counts, and the main RQ1 qualitative conclusions.
2. Primary RQ3 uses **effective submission IDs**; RQ2.1 and human-time RQ2.2 retain **URL grouping**; RQ2.3 compares trajectory cells within tasks without submission balancing. The media comparison is a separate **effective-ID**, exploratory analysis. A single universal description of hierarchical aggregation is inaccurate.
3. The **+14.58 pp** TB3.0→TB4.0 result is already correct. Its accompanying effect/test values are stale: use **`d_z=0.924`, `W=164`, `p=1.22×10^-8`, 66 tasks**. TB3.0's full 74-task rate is **23.2845139%**, whereas its 66-shared-task rate is **21.6088772%**.
4. Replace all ten RQ3.3 inferential effect/p-value pairs. Keep pooled medians as valid descriptions, explicitly separated from submission-balanced inference. Their directions agree for all eight stored measures; their magnitudes differ.
5. **Six of seven**, not all seven, matched configurations increase token use. Claude Code/Fable 5 decreases **4.97%**. This was already present in the historical seven-row comparison; it is a manuscript error, not a newly discovered refresh reversal.
6. Do not justify the retained difficulty panel by the manuscript's alternative-panel result: the Sonnet cache has **17/22 (77.3%)**, not 13/22, and does not establish equivalent neutralization. More seriously, the separate **category mapping** has only two valid votes per task, 89 Anthropic failures, and 22 recorded ties; it is not the validated three-voter difficulty protocol.
7. Several precise diagnostic numbers, tag/requirement pass rates, global interface rates, and collection dates lack sufficient retained evidence. Ready-to-paste conservative replacements below remove unsupported precision while preserving the research questions and paper structure.

## 2. Source and estimator key

All paths in this key are relative to the repository root. `P/` below abbreviates `data/processed_live/`; `A/` abbreviates the external archive's `files/reports/analysis_refresh_20261019/`. These abbreviations are defined here to make every row unambiguous.

| Key | Current evidence and exact identifying fields | Producer / implementation |
|---|---|---|
| S0 | `P/terminal_bench_{2_0,2_1,3_0,4_0}/trajectory_summary.csv`, `corpus_stats.json`; `data/indexes/{benchmark}/trajectory_trials.json` | `scripts/analysis/00_characterize_trajectories.py`; mining/index helpers |
| S1 | `P/terminal_bench_2_0/trajectory_features_by_outcome.csv`, rows `pass`, `fail`; metric median/p90 columns | `00_characterize_trajectories.py` |
| S2 | `P/diminishing_returns/rq1_1_success_failure_inference.csv`, key `metric`; `rq1_within_task_effort_{summary,by_task}.csv`; `rq1_task_outcome_eligibility_thresholds.csv` | `scripts/analysis/diminishing_returns/00_analyze_diminishing_returns.py::load_data,task_medians`; compact inference also exported by `10_build_statistical_audit.py` |
| S3 | `P/terminal_bench_2_0/rq1_task_balanced_effort_success.csv`, key `(metric,bin_label)`; `P/diminishing_returns/rq1_effort_{bin_robustness_summary,quantile_bins,bin_summary}.csv` | `scripts/analysis/diminishing_returns/01_plot_diminishing_returns.py` |
| S4 | `P/diminishing_returns/rq1_final_statistical_results.csv`, key `metric`, `beta_*`, `se_beta_*`, `model_*`, convergence fields; `rq1_2_quadratic_regression.csv` | `00_analyze_diminishing_returns.py::model_frame,fit_quadratic_conditional_logit`; compact export in statistical audit |
| S5 | `P/diminishing_returns/rq1_3_configuration_efficiency.csv`, key `(scaffold,model_dir)`, `task_balanced_*`, `token_pareto`, support columns | `scripts/analysis/diminishing_returns/02_plot_rq1_3_scaffold_model_effects.py` |
| S6 | `P/task_mining/difficulty/task_difficulty_{outcome,effort_summary}.csv`; `P/task_mining/category/task_domain_{outcome,effort_summary}.csv`; `category_difficulty/category_difficulty.csv`; `category/model_scaffold/{model,scaffold}_category_pass_rates.csv`; `rq2_1_difficulty_significance.csv` | `scripts/analysis/tasks/00_analyze_task_domains.py::submission_task_pass_rates,build_effort_summary,build_rq2_1_difficulty_significance` |
| S7 | `P/task_mining/rq2_2_media_exploratory.csv`; `tags/{perceptual_media_tasks.csv,task_tag_counts.csv,tag_groups.csv,tag_summary.json}` | `10_build_statistical_audit.py::build_media_description`; tag scripts `tasks/tags/00_analyze_task_tags.py`, `02_analyze_tag_effort.py` |
| S8 | `P/task_mining/time_estimates/rq2_2_human_time_inference.csv` (identical results in `P/task_mining/rq2_2_time_significance.csv`); `task_average_duration_comparison.csv`, key `task_name` | `scripts/analysis/tasks/01_analyze_time_estimates.py`; inference export in `10_build_statistical_audit.py` |
| S9 | `P/task_mining/tools/rq2_3_functional_behavior_inference.csv`, key `behavior_family`; four current tool/functional PNGs | `scripts/analysis/tasks/02_analyze_tool_availability_use.py::build_task_functional_contrasts,summarize_functional_wilcoxon`; support at lines 796–800 |
| S10 | `P/longitudinal/rq3_1_version_performance_summary.csv`, key `benchmark_version`; `rq3_1_version_performance_inference.csv`, key `transition`; `task_composition/adjacent_version_task_changes.csv`, key `(version_pair,task_name)` | `longitudinal/05_analyze_performance_over_versions.py`; `07_analyze_task_composition_over_versions.py::build_observed_task_duration,build_adjacent_changes`; `10_build_statistical_audit.py::build_version_performance` |
| S11 | `P/longitudinal/rq3_1_instruction_change_inference.csv`; `task_version_audit.csv`, `tb3_tb4_task_version_audit.csv` | `10_build_statistical_audit.py::add_instruction_status,build_instruction_comparisons`; longitudinal `01_analyze_instruction_change_robustness.py` **consumes**, not reconstructs, the TB2 audit |
| S12 | `P/longitudinal/tb3_tb4_task_difficulty_llm_labels.csv`; `tb2_difficulty_prompt_validation{,_summary,_confusion}.csv`; corresponding `_sonnet5*` files; `reports/longitudinal/difficulty_over_versions/provenance.json` | `longitudinal/08_label_task_difficulty_with_llm.py`, `difficulty_protocol.py`; downstream `09_analyze_difficulty_over_versions.py` |
| S13 | `P/longitudinal/tb2_task_category_llm_labels.csv`, `consensus_votes_json`, `consensus_vote_count`, `consensus_status`, `llm_category_label`; `task_composition/{version_task_composition_summary,category_composition_by_version}.csv` | `longitudinal/06_label_tb2_task_categories_with_llm.py`; `07_analyze_task_composition_over_versions.py::attach_unified_categories` |
| S14 | `P/longitudinal/difficulty_over_versions/pass_rate_{by_difficulty_over_versions,change_by_difficulty_over_versions}.csv` | `longitudinal/09_analyze_difficulty_over_versions.py`; effective-ID means |
| S15 | `P/longitudinal/pooled_effort_summary_refreshed.csv` and `P/longitudinal/tb3_tb4/pooled_effort_summary_refreshed.csv`, key `key`, `early_value`, `late_value`, `*_valid_n`, `relative_change_pct` | `longitudinal/03_analyze_effort_changes.py::load_trajectories,summarize_periods` |
| S16 | `P/longitudinal/rq3_3_effort_inference.csv`, key `(transition,metric)`; each transition's `paired_effort_tasks_effective.csv`, `effort_figure_data_submission_balanced_effective.csv`, `task_balanced_effort_summary.csv` | `03_analyze_effort_changes.py::task_metric_pairs,summarize_task_balanced_periods`; inference also `10_build_statistical_audit.py::build_effort_inference` |
| S17 | `P/longitudinal/rq3_3_shared_configuration_tokens_tb3_tb4.csv`, key `configuration`, `shared_tasks`, `old_median_tokens`, `new_median_tokens`, `percentage_change` | `10_build_statistical_audit.py::build_shared_configuration_tokens,task_balanced_config_median` |
| S18 | `P/longitudinal/token_accounting/{input_context_growth_summary.csv,input_context_audit.json,token_accounting_comparisons.csv,token_vs_logged_text_monthly.csv}` | `longitudinal/04_analyze_token_accounting.py` |
| S19 | `P/audit_only/longitudinal_model_population/{E_reasoning_thinking_token_evidence.csv,G_composition_weighted_headline.csv,J_data_quality_notes.md,config_level_detailed.csv,trajectory_level_enriched_audit.csv}` | colocated `build_longitudinal_model_population_audit.py`; a **different historical measurement pipeline**, not primary refreshed RQ3 evidence |
| S20 | `P/statistical_analysis/{master_inferential_results.csv,analysis_provenance_and_units.csv,validation_checks.csv}` | `scripts/analysis/10_build_statistical_audit.py`; shared `statistical_helpers.py` |

### Estimands, support, exclusions, and units

| Analysis | Unit and aggregation | Eligible sample / exclusions |
|---|---|---|
| Corpus / pooled RQ1.1 | Trajectory counts; pooled median per outcome | TB2.0 31,103 binary records. Raw summary tokens include reported zeros: 30,581 nonmissing. Positive-token analysis has 30,126. Positive cost: 20,401. Other primary measures: 31,103. |
| RQ1.1 inference | Median within **effective submission × task × outcome**; median across submissions within task/outcome; success-minus-failure task vector | At least 3 distinct effective submissions **per outcome and metric**. 86 tasks for interaction/duration, 85 tokens, 83 cost. `total_tokens>0`; input/output only nonmissing in this script; cost strictly positive. No fractional rewards in TB2.0. |
| RQ1.2 bins | Pass means within effective submission × task × bin; means across submissions and tasks; pooled rates separate | All binary TB2.0 records with relevant metric; total tokens are restricted to positive reports (30,126 trajectories); cost is also positive only. Tail samples and all bins in Appendix. Quantile robustness is **pooled**, not a second task-balanced analysis. |
| RQ1.2 regression | Individual trajectories conditioned on task; quadratic in population-standardized `log(1+x)` | Tasks must have both outcomes; 87 task strata except cost 86. Interaction/duration: 30,392 observations/74 clusters; positive tokens 29,441/72; positive cost 19,705/48. Clusters use `(scaffold,model_dir,agent_version,leaderboard_model)`, not the full effective ID. |
| RQ1.3 | Configuration descriptive pass means and continuous medians after effective-submission/task aggregation | At least 80 tasks and 300 trajectories; 71 eligible configurations, 69 with token estimates; 14 token-frontier points. Pair-specific descriptive comparisons can use a 50-shared-task threshold. Token estimates exclude nonpositive values. Two configurations with missing token estimates are not token-frontier candidates. |
| RQ2.1 | **URL** submission/task pass means; equal means across tasks. Continuous medians within URL/task, across URLs, across tasks in group | 89 tasks, 55 TB2.0 URL units; difficulty groups 4/55/30 tasks. Metric-wise nonmissing; positive cost. These tables do **not** filter zero token reports the same way as positive-token RQ1 and primary RQ3. |
| RQ2.2 tags / media | Tag metadata counts; stored media comparison uses effective-ID task pass means, then group means | Media 7 tasks versus 82 others; exploratory, no confirmatory p-value or Cliff's delta. Exact six quoted tag/requirement rates have no retained outcome table. |
| RQ2.2 human time | Medians within URL/task, across URLs within task; pair agent duration with estimate | 88 tasks with human estimates. Success-only comparison has 86 eligible tasks and is descriptive. All attempts primary, including failures. |
| RQ2.3 | Within-task pooled use and non-use trajectory pass rates; equal mean of eligible task contrasts | At least 3 **trajectories** in each cell. No effective-submission balancing. Nine families have 89,89,89,82,80,50,13,48,12 eligible tasks. Category/difficulty figures descriptive; no subgroup tests retained. |
| RQ3.1 / RQ3.2 performance | Binary pass means within effective submission/task/version; means across submissions, then tasks | Full versions: 31,103/7,501/4,279/5,902 binary records and 89/89/74/66 tasks. Paired transitions 89 and 66 shared tasks. Excludes 58 fractional TB3.0 rewards from outcomes only. |
| RQ3.2 composition | Counts and distributions of task metadata; continuous observed duration uses nested medians | Difficulty labels: 140 task-version records, 74+66; validation 22 held-out TB2 tasks. Composition is descriptive; **no new composition significance tests**. Junior estimates absent for TB3/TB4. |
| RQ3.3 pooled | Median over retained trajectories in each version; percentage is ratio of two pooled medians | Includes fractional-reward trajectories; no pairing or submission balancing. Token values strictly positive; 30,126/7,434/3,921/5,902 usable trajectories. |
| RQ3.3 inference | Median within effective submission/task/version, then median across submissions within task; pair shared tasks | 89 or 66 tasks for each of five primary measures. Includes fractional rewards when metric available. Metric-wise missing-pair removal; no 3-submission-per-outcome threshold. Tests use **absolute paired differences**. Ratios of cross-task medians and medians of paired percentage changes are different descriptive quantities. |
| Matched-configuration tokens | Same nested continuous medians, restricted to each exact scaffold/model pair's token-covered shared tasks | 8 exact pairs appear in both TB3/TB4, **7** have usable positive tokens in both. GLM-5.3: 65 shared token-covered tasks; other 6: 66. No significance tests. |

Wilcoxon tests are two-sided with `zero_method='wilcox'`, `method='auto'`. `d_z=mean(D)/sample_sd(D)` (`ddof=1`); the raw effect may be the **median** of D and need not share its sign. Mann–Whitney tests are two-sided; Cliff's delta is the normalized number of changed-group values greater minus smaller than unchanged-group values. Regression p-values are two-sided Wald tests; standard errors use the implemented cluster sandwich correction. Stored outputs use unadjusted alpha .05, without multiplicity correction or reported confidence intervals. The 40-row master table excludes descriptive analyses.

## 3. Revision register: exact locations, replacements, and LaTeX

Each item supplies current wording, correction, evidence, reason, and a complete replacement unit. Do not apply a paragraph twice when a later item gives a complete replacement for the same paragraph. The complete abstract/discussion/limitations/conclusion replacements in Section 4 incorporate the local changes.

### R01 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** Approach, Aggregation Strategy, lines 187–193: “We use two aggregation strategies” and “giving each task equal weight.”  
**Current:** one general hierarchy is presented as applying throughout.  
**Replacement / reason:** explicitly identify effective-ID, URL, and trajectory-cell analyses, and state the nested median procedure. The effective ID concatenates `benchmark, source_submission_url, scaffold, model_dir, agent_version, leaderboard_model, leaderboard_provider, leaderboard_date`, replacing empty components with `unknown`; URL rows can contain several model components.  
**Evidence:** `scripts/analysis/submission_task_balancing.py::EFFECTIVE_SUBMISSION_COMPONENTS`; S6, S8–S11, S16; S20 provenance rows. RQ2.2's media comparison is effective-ID based even though human time is URL based.

```latex
We distinguish pooled trajectory summaries from task-balanced summaries. Pooled summaries give each trajectory equal weight. For binary task-balanced outcomes, we first calculate pass rates within submission--task pairs, average across submissions within each task, and then average across tasks. For continuous measures, we take medians within submission--task pairs, medians across submissions within each task, and medians across the relevant tasks.

RQ1 and the primary RQ3 analyses identify submissions using the repository's effective submission identifier, which combines benchmark, source submission URL, scaffold, normalized model, agent version, recorded leaderboard model and provider, and submission date. This separates model components that share a leaderboard URL. RQ2.1 and the human-time comparison in RQ2.2 retain URL-based submission grouping; the exploratory media comparison uses effective submission identifiers. RQ2.3 instead compares trajectory-level use and non-use groups within each task, without submission balancing. These estimands are therefore distinguished throughout.

Binary analyses include only rewards of 0 or 1. Fractional rewards remain eligible for continuous-measure analyses. Missing telemetry is excluded only for the affected measure; positive-token and positive-cost restrictions are stated for the analyses that apply them.
```

### R02 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** Approach, Statistical Analysis, line 197: “Inferential analyses use task-level aggregates.”  
**Current:** overgeneralizes to RQ1.2 and omits unadjusted multiple testing.  
**Replacement:** task-level inference except trajectory-level conditional regression; define effect direction and no adjustment.  
**Evidence:** S4, S20; `statistical_helpers.py`; RQ1 regression `model_frame` and `fit_quadratic_conditional_logit`. **Reason:** actual observation unit and significance interpretation.

```latex
Except for RQ1.2's trajectory-level conditional logistic regressions, inferential comparisons use task-level observations. Paired task comparisons use two-sided Wilcoxon signed-rank tests and paired Cohen's $d_z$, calculated as the mean paired difference divided by its sample standard deviation. We separately report raw differences, which may be medians. Independent task groups use two-sided Mann--Whitney $U$ tests and Cliff's $delta$; ordinal associations use Spearman's $
ho$. RQ1.2 reports regression coefficients, cluster-robust standard errors, and two-sided Wald tests. We use $alpha=0.05$ without multiplicity adjustment, and interpret the resulting associations as observational.
```

### R03 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** Dataset and Corpus Construction, line 174: “derive canonical names from submission URLs.”  
**Current:** suggests that URLs alone define normalized models and submissions.  
**Replacement:** use stored normalized model components (`model_dir`), preserve raw names, and distinguish effective IDs.  
**Evidence:** S0 (`model_dir` versus `model_name`); characterization reads model directory at lines 660–668; `submission_task_balancing.py`. Raw names have 53/18/12/14 distinct values by version, while normalized components have 33/12/12/14. **Reason:** the actual model aggregation key is `model_dir`; path sanitization also occurs in mining helpers, and URL canonicalization is not the effective-ID rule.

```latex
The TB2.0 leaderboard contains 142 submissions across 89 tasks and 61,605 reported trials. The retained corpus comprises 31,103 trajectories, 12 scaffolds, and 33 normalized model components, represented by 74 effective submission identifiers and 55 distinct source submission URLs. We aggregate model components using the stored normalized model-directory identifier while retaining the raw model and leaderboard names as provenance. Of these trajectories, 11,219 are successful and 19,884 unsuccessful.
```

### R04 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** Trajectory Parsing and Normalization, line 182: “retain only valid JSON trajectory objects with a non-empty ... list of object entries.”  
**Current:** states a stronger enforcement rule than the characterization loop implements.  
**Replacement:** describe the observed retained corpus, rather than claiming the characterization script enforces every validation rule.  
**Evidence:** S0; 48,909 indexed records; all 66 TB2.1 records absent from retained summaries were directly read and are top-level `null`. `04_trajectory_index_helpers.py::trajectory_payload_status` checks nonempty object steps, while `00_characterize_trajectories.py` skips non-dict payloads, defaults missing steps to `[]`, and skips non-dict step entries. **Reason:** eligibility helper and final parser are different enforcement points; no full raw 34.9 GB rescan was performed.

```latex
We normalize the retained trajectory objects into a common representation linking task, model, scaffold, submission, outcome, and available telemetry. The four trajectory indexes contain 48,909 records, of which 48,843 appear in the retained summaries. The 66 excluded records are TB2.1 top-level \texttt{null} payloads. All retained summaries record nonzero step counts. The collection pipeline also includes checks for missing, empty, malformed, and non-trajectory payloads.
```

### R05 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** RQ1 metric definitions, line 230: “Step count captures the number of iterations.”  
**Current:** equates all recorded steps with agent iterations.  
**Replacement:** logged step entries can include system, user, and observation entries.  
**Evidence:** S0 `step_count`, `agent_step_count`, `user_step_count`, `system_step_count`; characterization sets `step_count=len(steps)`. **Reason:** measurement construct.

```latex
Step count measures the number of recorded trajectory entries, which can include agent, user, system, and observation entries depending on the logging schema. It is therefore a broad measure of recorded interaction rather than a standardized count of model iterations. Prior work similarly characterizes agent activity through actions or turns~\cite{arora_setupbench_2025,vats_scaffold_2026}. Shell invocations capture extracted terminal interactions, each counted once even when it contains chained commands, while structured tool-call count captures recorded tool invocations.
```

The active `tab:effort_metrics` should consequently use this complete environment (its numbers do not change):

```latex
\begin{table}[tb]
    \centering
    \caption{Interaction and resource-use measures used in RQ1.}
    \label{tab:effort_metrics}
    \resizebox{\columnwidth}{!}{%
    \begin{tabular}{lll}
        \hline
        Dimension & Measure & Operationalization \\
        \hline
        Interaction activity & Steps & Number of recorded trajectory entries \\
        Interaction activity & Shell invocations & Extracted shell calls or shell-style fenced blocks \\
        Interaction activity & Tool calls & Number of structured tool invocations \\
        Resource use & Tokens & Reported input plus completion/output usage \\
        Resource use & Duration & Benchmark-reported trajectory duration \\
        Resource use & Cost & Reported aggregate cost, with step-level fallback where available \\
        \hline
    \end{tabular}%
    }
\end{table}
```

### R06 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** RQ1.1 Results, line 246: “total tokens (239k vs. 166k)” and “token ... analyses include 30,581.”  
**Current:** pooled values are correct for nonmissing raw reports, but are easily conflated with the positive-token within-task analysis.  
**Replacement:** retain these pooled values and explicitly state the zero-token distinction.  
**Evidence:** S1 totals 166,391/239,455; S2 `complete_case_count` total tokens 30,126 and positive-token pooled medians 174,065/247,933. `corpus_stats.json` nonmissing tokens 30,581. **Reason:** different filters, not a numerical contradiction.

```latex
At the corpus level, failed trajectories show higher medians than successful ones for steps (22 vs.\ 19), shell invocations (22 vs.\ 18), tool calls (25 vs.\ 22), reported total tokens (239k vs.\ 166k), and duration (533 vs.\ 296~s); positive reported cost is the exception (0.167 vs.\ 0.205 USD). Interaction measures and duration cover all 31,103 trajectories. The raw pooled token summaries use 30,581 nonmissing reports, including reported zeros; the positive-token subset used for within-task total-token inference and RQ1.2 contains 30,126 trajectories. Positive-cost summaries cover 20,401 trajectories.
```

### R07 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ1.1, `tab:within-task-effort`, shell row: “$+0.50$ ... -0.006 ... 0.398.”  
**Current → replacement:** shell median **0.50→0.375 invocations**, `d_z -0.006→-0.014`, `p .398→.439`; `W=1496`, 86 tasks. Other seven rows remain correct at their displayed precision.  
**Evidence:** S2 row `shell_invocation_count`, `median_task_difference=0.375`, `cohens_dz=-0.0136526800336146`, `p_value=0.4385568751433467`; full saved precision in Appendix. **Reason:** refreshed shell parsing. The median and mean-standardized effect have different signs because task differences are skewed.

```latex
\begin{table}[tb]
  \centering
  \caption{Task-balanced differences (successful $-$ failed). Raw differences are medians across eligible task contrasts.}
  \label{tab:within-task-effort}
  \resizebox{\columnwidth}{!}{%
  \begin{tabular}{lrrrr}
  \hline
  Metric & Tasks & Median difference & Cohen's $d_z$ & $p$ \\
  \hline
  Steps              & 86 & $+2.00$     &  0.131 & 0.127 \\
  Shell invocations  & 86 & $+0.375$    & -0.014 & 0.439 \\
  Tool calls         & 86 & $+1.125$    &  0.104 & 0.118 \\
  Input tokens       & 85 & $+21{,}618$ &  0.254 & 0.015 \\
  Output tokens      & 85 & $-29.5$     &  0.164 & 0.610 \\
  Total tokens       & 85 & $+20{,}272$ &  0.246 & 0.025 \\
  Duration (s)       & 86 & $-44.89$    & -0.275 & 0.003 \\
  Cost (USD)         & 83 & $+0.0862$   &  0.457 & $<0.001$ \\
  \hline
  \end{tabular}%
  }
\end{table}
```

### R08 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** RQ1.1 after the table: “differences ... reverse direction” and “increasing the threshold to four ... 86 to 84.”  
**Current:** implies a uniform reversal across statistical summaries and threshold counts across metrics.  
**Replacement:** specify median contrasts; 86→84 is the step-count eligibility check.  
**Evidence:** S2, shell positive median/negative `d_z`; threshold table key `(step_count,3/4)`; durations remain negative. **Reason:** distinguish median from mean; metric-specific support.

```latex
Eligibility is assessed separately for each measure, requiring at least three distinct effective submissions per outcome. For step count, increasing this threshold from three to four reduces coverage from 86 to 84 tasks. The median successful-minus-failed contrasts for steps, shell invocations, and tool calls are positive, reversing their pooled median ordering, but none is statistically significant. Related work likewise discusses the limits of pooled effort comparisons~\cite{mehtiyev_beyond_2026}. For shell invocations, the positive median contrast and negative $d_z$ reflect different summaries of a skewed task-difference distribution. Successful trajectories use significantly more input and total tokens, finish significantly faster, and incur higher positive reported cost; output-token differences are not significant.
```

### R09 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ1.2 Results, line 369: “39.69\% for 16--40 invocations.”  
**Current → replacement:** **39.69→39.68%** (`100×0.396762...`). Other reported task-balanced peaks/tails remain correct: steps 38.88/8.73%, duration 39.29/2.49%, tokens 36.64/5.83%, calls 39.64%, cost 38.47/36.14%.  
**Evidence:** S3 `(shell_invocation_count,16-40).task_balanced_pass_rate`; 9,688 trajectories, 89 tasks, 3,823 submission-task-bin cells. **Reason:** stale shell peak / rounding. Correct full results paragraph:

```latex
In the task-balanced results, success generally increases initially and declines at high values of most measures. It peaks at 38.88\% for 11--25 steps, 39.29\% for 5--15 minutes, and 36.64\% for 100k--500k tokens, falling to 8.73\%, 2.49\%, and 5.83\% in the highest respective intervals. Shell invocations and tool calls peak at 39.68\% for 16--40 invocations and 39.64\% for 16--35 calls. Cost follows a flatter high-value pattern, reaching 38.47\% at \$0.50--\$1 and 36.14\% above \$1.
```

### R10 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** RQ1.2 Method, lines 319 and 338: “intervals for each measure ... x-axes” and “equal-frequency bins reproduce the same qualitative pattern.”  
**Current:** fails to specify pooled robustness, and the composite figure does not display every measure.  
**Replacement:** fixed bins versus pooled quantiles; conditional tests remain separate.  
**Evidence:** S3 `rq1_effort_bin_robustness_summary.csv` all six `qualitative_result_changed=False`; five nonempty quantile bins per measure, pooling trajectories. Fixed duration has seven defined intervals, one empty. **Reason:** estimand and figure coverage.

```latex
We assign trajectories to fixed, mutually exclusive intervals, with shared boundaries included in the lower interval. For steps these are 0--10, 11--25, 26--50, 51--100, 101--200, and $>200$; shell invocations use 0, 1--5, 6--15, 16--40, and $>40$, and structured tool calls use 0--5, 6--15, 16--35, 36--75, 76--150, and $>150$. Figure~\ref{fig:task-balanced-effort} shows selected measures. We calculate both pooled and task-balanced pass rates within fixed intervals, restricting token analyses to positive reported totals and cost analyses to positive reported costs. A separate pooled robustness analysis using five equal-frequency bins per measure retains an increase-then-decline pattern for all six measures. This robustness analysis does not provide an additional task-balanced or causal estimate.
```

The active regression paragraph's four significant coefficients/p-values and all-six convergence claim are correct. If restoring the **commented** curvature table, replace the shell row by `-0.293`, `0.1100`; its exact `beta_1=-0.0923289779354722`, `beta_2=-0.2927996496146946`, `SE(beta_2)=0.1831824811211977`. Full coefficients, standard errors, samples, and p-values are in the evidence appendix; no model was refit here.

### R11 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** RQ1.3 Method: “configuration-level efficiency using task-balanced estimates.”  
**Current:** omits support/telemetry restrictions and makes frontier endpoints sound universal.  
**Replacement:** qualify the token-covered descriptive frontier.  
**Evidence:** S5; source constants `MIN_CONFIG_TASKS=80`, `MIN_CONFIG_TRAJECTORIES=300`, `MIN_SHARED_TASKS=50`. 71 eligible rows, 69 nonmissing token estimates, 14 frontier rows. Nexau/GPT-5.5 has 84.7191% pass rate but no token median. **Reason:** missing data and differing task support prevent global efficiency ranking.

```latex
We compare model--scaffold configurations with at least 80 tasks and 300 trajectories, using task-balanced pass rates and nested median resource estimates. Of 71 eligible configurations, 69 have a usable token estimate. The token Pareto frontier is descriptive and restricted to these token-covered configurations; configurations without token telemetry cannot be placed on this frontier. Differences in task coverage and execution conditions also limit direct efficiency comparisons.
```

All numerical examples in the active two RQ1.3 Results paragraphs are correct at their stated precision; see V-register and full frontier appendix. The lone refreshed efficiency cell outside this text is OpenHands/Haiku 4.5 median shell invocations **20→22**, not token usage or frontier membership.

### R12 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ2.1 Results: “71.3\% ... 43.2\% ... 19.9\%” and “$\rho=-0.48$.”  
**Current → replacement:** URL-balanced rates **73.9%, 46.5%, 22.1%**; `rho=-0.4877929115830032`, so **-0.49** at two decimals; `p=1.2437418×10^-6`.  
**Evidence:** S6 `task_difficulty_outcome.csv.pass_rate`, easy/medium/hard, 4/55/30 tasks; `rq2_1_difficulty_significance.csv`, 89 tasks. **Reason:** current RQ2 output uses URL units and corrected source matching. The manuscript's old three rates closely match current **effective-ID RQ3** rates; do not silently relabel them as current RQ2 results.

```latex
Task success decreases with author-assigned difficulty. Using RQ2.1's URL-based task-balanced summaries, pass rates are 73.9\% for easy tasks, 46.5\% for medium tasks, and 22.1\% for hard tasks (Figure~\ref{fig:rq2_difficulty_pass_rate}); these groups contain four, 55, and 30 tasks, respectively. The task-level association is negative and significant ($\rho=-0.49$, $p<.001$; $n=89$ tasks).
```

### R13 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ2.1 Results: “408,813 tokens ... 719 seconds ... \$0.34 ... 167,730 ... 256 ... \$0.16.”  
**Current → replacement:** hard **407,300.5 tokens / 688.95625 s / $0.3695658125**; easy **151,973.25 tokens / 253.296 s / $0.18828898125**.  
**Evidence:** S6 difficulty effort rows `(hard/easy,total_tokens/duration_seconds/cost_usd_positive).median`; 30/4 tasks; source table includes submission-task counts. **Reason:** corrected URL/task source matching. These are medians of task-level medians, not pooled trajectory medians.

```latex
Resource use generally increases with difficulty, while interaction counts show a less consistent pattern (Figure~\ref{fig:rq2_difficulty_effort}). Hard tasks have a task-balanced median of approximately 407,301 tokens, 689 seconds, and \$0.37, compared with 151,973 tokens, 253 seconds, and \$0.19 for easy tasks. Hard tasks therefore combine lower observed success with higher resource use in these descriptive summaries.
```

### R14 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ2.1: “data-processing ... 58.1\% ... system-administration (45.4\%) ... debugging (44.0\%) ... security (40.4\%) ... mathematics (25.3\%) ... file-operations (21.3\%).”  
**Current → replacement:** **61.1, 47.6, 48.8, 44.3, 28.6, 23.7%**, respectively. Debugging now exceeds system administration.  
**Evidence:** S6 category `pass_rate`; task counts respectively 4,9,5,8,4,5. **Reason:** refreshed descriptive URL-balanced category rates and ranking.

```latex
Pass rates also vary across task categories. Among categories with multiple tasks, \texttt{data-processing} has the highest task-balanced pass rate (61.1\%), followed by \texttt{debugging} (48.8\%), \texttt{system-administration} (47.6\%), and \texttt{security} (44.3\%); \texttt{mathematics} (28.6\%) and \texttt{file-operations} (23.7\%) are lowest. These comparisons are descriptive and categories differ in their task and difficulty composition.
```

### R15 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ2.1: “88.2\%, 79.7\%, and 11.2\%” and hard-task rates “0.02, 0.02, and 0.04.”  
**Current → replacement:** personal-assistant **89.9%**, optimization **83.7%**, games **13.5%**; hard video-processing **0.0290909→0.03** as a proportion, model-training **0.0190909→0.02**, file-operations **0.0432099→0.04**.  
**Evidence:** S6 category and category-difficulty `pass_rate`; each example is one task. **Reason:** updated cells; avoid implying broad category evidence from one task.

```latex
Single-task categories illustrate the coarseness of author difficulty labels: \texttt{personal-assistant}, \texttt{optimization}, and \texttt{games} are all medium but have task-balanced pass rates of 89.9\%, 83.7\%, and 13.5\%, respectively. Among hard tasks, the single-task \texttt{video-processing}, \texttt{model-training}, and \texttt{file-operations} cells have pass rates of approximately 0.03, 0.02, and 0.04. These examples concern individual tasks and should not be read as stable estimates for entire domains.
```

### R16 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ2.1 category resources: “26 steps ... 363,000 tokens ... 482 seconds”; “\$0.325 ... 315,000 tokens.”  
**Current → replacement:** machine-learning **27 steps, 327,565.75 tokens, 587.6485 s**; mathematics **$0.4781241593750001, 409,170 tokens**.  
**Evidence:** S6 category effort `median`; machine-learning 3 tasks, mathematics 4. **Reason:** refreshed category medians. Model-training/scientific-computing remain relatively resource-intensive; their exact values appear in Appendix.

```latex
Categories also differ in interaction and resource use (Figure~\ref{fig:rq2_category_effort}). \texttt{machine-learning} has task-balanced medians of 27 steps, approximately 328,000 tokens, and 588 seconds. \texttt{mathematics} has the highest median positive reported cost (\$0.478), together with approximately 409,000 tokens. \texttt{model-training} and \texttt{scientific-computing} also have comparatively high token use and duration, whereas \texttt{personal-assistant} and \texttt{data-processing} have lower values. These category estimates are descriptive and some rely on few tasks.
```

### R17 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ2.1 model comparisons: Gemini security “77.6\%”; mathematics “84.4\%”, model training “74.6\%”, scientific computing “62.6\%.”  
**Current → replacement:** **76.7%, 85.0%, 74.2%, 65.4%**, respectively. Claude Opus 4.6 debugging **96.0%** and security **78.8%**, and Terminus 3.3 debugging **96.0%**, remain correct.  
**Evidence:** S6 `model_category_pass_rates.csv`, `model_dir=gemini-3.1-pro-preview` and categories above; `pass_rate`; 8/4/4/8 tasks. **Reason:** current marginal model rates after source correction.

```latex
Descriptive model-level summaries also vary by category. Claude Opus 4.6 reaches 96.0\% in debugging and 78.8\% in security; Gemini 3.1 Pro reaches 76.7\% in security, 85.0\% in mathematics, 74.2\% in model training, and 65.4\% in scientific computing. At the scaffold level, Terminus 3.3 reaches 96.0\% in debugging. These marginal model and scaffold summaries aggregate different configurations and do not isolate a model or scaffold effect.
```

### R18 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** RQ2.1: “strongest model--scaffold configurations ...” preceding marginal model/scaffold percentages; software-engineering configurations and provider-performance explanations.  
**Current:** marginal heatmap cells are presented as joint configuration evidence.  
**Replacement:** use the R17 paragraph and the following sentence; retain citations only as contextual external claims if checked against the bibliography.  
**Evidence:** S6 files contain separate `model_dir` and `scaffold` grouping, not a controlled joint contrast. S5 configuration estimates concern overall TB2.0, not category-specific top configurations. **Reason:** unsupported inference from marginal rankings.

```latex
The category heatmaps describe model-level and scaffold-level associations rather than controlled model--scaffold ablations. Configuration rankings and apparent specialization may also reflect task coverage, submission composition, and execution conditions, so they do not establish that changing one system component would cause the observed difference.
```

### R19 — UNVERIFIED — evidence insufficient

**Location / quote:** RQ2.2, `tab:tag-category-pass-rate`: tags **55.5%, 50.6%, 46.7%** and requirement groups **49.5%, 44.9%, 43.1%**; “strongest task tags and category groups.”  
**Current:** six precise task-balanced rates without a retained outcome table.  
**Replacement:** no authoritative replacement numbers are supplied. Keep metadata counts and the verified exploratory media comparison, or restore original result evidence in a separate authorized analysis. **Evidence:** S7 retains tag memberships/counts and a resource-lift PNG, but no tag/cluster outcome CSV; `02_analyze_tag_effort.py::build_outcome_table` specifies a possible computation, not its stored numerical result. The heatmap is pooled resource use and cannot verify these six pass rates. **Reason:** regeneration is outside this audit's authorization.

Complete conservative replacement for the table (same label; unsupported rows omitted):

```latex
\begin{table}[tb]
    \centering
    \caption{Exploratory task-balanced pass rates by media requirement.}
    \label{tab:tag-category-pass-rate}
    \begin{tabular}{lrr}
        \hline
        Task characteristic & Tasks & Pass rate \\
        \hline
        Media-related tasks & 7 & 16.0\% \\
        Remaining tasks & 82 & 38.4\% \\
        \hline
    \end{tabular}
\end{table}
```

```latex
Task metadata contain 126 distinct tags across 89 tasks; 95 tags occur only once, motivating broader requirement groups. In a post-hoc inspection, seven tasks were identified as having perceptual-media requirements. Their mean effective-submission-balanced task pass rate is 16.0\%, compared with 38.4\% for the other 82 tasks, a descriptive difference of $-22.4$ percentage points (Table~\ref{tab:tag-category-pass-rate}). This exploratory comparison has no confirmatory significance test and is not universal: \texttt{code-from-image} reaches 60.7\%.
```

### R20 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ2.2 time Results: “median agent trajectory lasts 7.11 minutes.”  
**Current → replacement:** **7.02420833→7.02 min**; human medians 60/240 min unchanged, `d_z=-.509/-.403` unchanged at manuscript precision. Expert `W=46`, `p=1.78328862×10^-15`; junior `W=1`, `p=3.86257573×10^-16`.  
**Evidence:** S8 expert/junior rows, 88 tasks; success-only 86 tasks, median **7.2065875→7.21 min**; paired medians **-46.9086/-235.344333 min**, not differences of the marginal medians. **Reason:** updated URL/task duration medians.

```latex
Human time estimates are available for 88 of the 89 tasks. Across these tasks, the median task-balanced agent duration is 7.02 minutes, compared with 60 minutes for experts and 240 minutes for junior developers. Median paired agent-minus-estimate differences are $-46.91$ and $-235.34$ minutes, with $d_z=-0.509$ and $d_z=-0.403$, respectively (both $p<.001$). Restricting to successful trajectories gives a descriptive median of 7.21 minutes across 86 eligible tasks. These comparisons concern observed agent attempts and benchmark human estimates, not measured human--agent speed differences under matched conditions.
```

### R21 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** RQ2.3 Method: “at least three trajectories in each group, following the same minimum-support rule as ... RQ1.1.”  
**Current:** the number 3 is shared but the units differ.  
**Replacement:** explicit trajectory cells without submission balancing; distinguish interface use from availability.  
**Evidence:** S9 lines 767–804; S2 requires distinct effective submissions. Declared tools may be absent from logs, so recorded use is not capability availability. AI assistance in historical taxonomy development has no archived prompt/review trail; fixed rules themselves are inspectable. **Reason:** actual support and measurement.

```latex
We map recorded tool names and terminal-command patterns to four interface families and nine fixed functional behavior families. A trajectory uses a behavior when at least one recorded invocation matches its rules; one invocation can match several families. For each task and behavior, we compare pooled pass rates of trajectories using and not using the behavior, requiring at least three trajectories in each cell. This differs from RQ1.1's threshold of three distinct effective submissions per outcome. We average eligible task contrasts for category and difficulty summaries without submission balancing. Recorded use does not establish tool availability or the absence of an unlogged capability.
```

### R22 — UNVERIFIED — evidence insufficient

**Location / quote:** RQ2.3 Results: terminal **95.8%**, edit **23.6%**, search/read **6.5%**, web/network **0.5%**, raw search/read difference **+12.7 pp**.  
**Current:** precise pooled interface rates.  
**Replacement:** no current retained CSV verifies the global rates or +12.7 pp. The four current interface/functional heatmaps show subgroup contrasts, not these global marginals. **Evidence:** S9 directory retains only the nine-family inference CSV; the script computes and prints interface summaries but removes other tables. **Reason:** missing retained result; do not reconstruct the raw parser here.

```latex
Interface-level comparisons describe the tools through which actions are recorded, whereas functional comparisons describe the purposes of those actions. The category heatmaps show that interface associations vary across task domains; a terminal invocation alone does not identify whether the agent inspected, modified, executed, or validated its work.
```

### R23 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ2.3 core-behavior paragraph and `tab:rq23-functional-use`, notably testing **+7.8 pp**, inspection `d_z=.784`, and use rates 77.2/61.0%.  
**Current → replacement:** inspection mean **9.458805 pp**, `d_z=.778821`, `p=3.75378279×10^-10`; testing **7.564402 pp**, `d_z=.487193`, `p=1.96619368×10^-5`; modification **77.3%**, execution **61.1%**. All nine exact rows appear in Appendix. Significance classifications remain unchanged.  
**Evidence:** S9 `behavior_family` rows; global use rates denominator 31,103 trajectories, task contrasts use the eligible task counts below. **Reason:** refreshed command memberships; no causal effects.

```latex
Four behaviors are significantly associated with higher within-task success: inspection/search (+9.5 pp), execution (+7.7 pp), testing/validation (+7.6 pp), and modification/writing (+5.7 pp). The remaining five behaviors have no significant overall association at the unadjusted 0.05 threshold (Table~\ref{tab:rq23-functional-use}). These are observational contrasts and may reflect task, system, and trajectory-stage selection.

\begin{table}[tb]
    \centering
    \caption{Within-task pass-rate differences. Positive $\Delta$ and $d_z$ indicate higher success among trajectories using the behavior. Tests are two-sided and unadjusted.}
    \label{tab:rq23-functional-use}
    \resizebox{\columnwidth}{!}{%
    \begin{tabular}{lrrrrr}
        \hline
        Behavior family & Use rate & Eligible tasks & Mean $\Delta$ & Cohen's $d_z$ & $p$ \\
        \hline
        Inspection/search              & 88.4\% & 89 & +9.5 pp &  0.779 & $3.75{\times}10^{-10}$ \\
        Modification/writing           & 77.3\% & 89 & +5.7 pp &  0.510 & $7.54{\times}10^{-6}$ \\
        Execution                      & 61.1\% & 89 & +7.7 pp &  0.520 & $1.08{\times}10^{-6}$ \\
        Testing/validation             & 12.0\% & 82 & +7.6 pp &  0.487 & $1.97{\times}10^{-5}$ \\
        Environment/dependencies       & 37.3\% & 80 & +2.3 pp &  0.120 & 0.183 \\
        Version control                & 10.6\% & 50 & -2.3 pp & -0.121 & 0.489 \\
        Data querying/transformation   &  4.0\% & 13 & -3.7 pp & -0.183 & 0.635 \\
        Network/external               & 10.1\% & 48 & -2.4 pp & -0.100 & 0.228 \\
        Specialized media processing   &  2.2\% & 12 & +2.0 pp &  0.098 & 0.622 \\
        \hline
    \end{tabular}%
    }
\end{table}
```

### R24 — UNVERIFIED — evidence insufficient

**Location / quote:** RQ2.3 difficulty paragraph: inspection **+17.2/+10.1/+7.3 pp**.  
**Current:** tenths precision absent from retained numerical subgroup tables.  
**Replacement:** the current difficulty PNG supports approximately **+17/+10/+7 pp**, and positive displayed contrasts for all four core families, but not the three exact tenths or subgroup significance.  
**Evidence:** `reports/tasks/tools/rq2_3_functional_success_association_by_difficulty.png`, visually inspected; rows easy/medium/hard and inspect/search column. **Reason:** PNG rounding and missing subgroup support tables. Do not imply these exact historical tenths are verified.

```latex
The displayed task-balanced contrasts for the four core behaviors remain positive across the three difficulty groups (Figure~\ref{fig:rq23-functional-difficulty}). Inspection/search is approximately +17 pp for easy tasks, +10 pp for medium tasks, and +7 pp for hard tasks. These subgroup patterns are descriptive; no separate subgroup significance tests are reported.
```

### R25 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** RQ2.3 category paragraph: “Inspection/search shows particularly large differences in system administration, data processing, debugging, and software engineering.”  
**Current:** includes software engineering among the strongest despite the current displayed debugging value being larger and software engineering only midrange.  
**Replacement:** use current visible values and preserve qualifications.  
**Evidence:** functional category PNG: inspection system administration +22, data processing +15, debugging +14, software engineering +12; testing security +20, debugging +15. Several modification cells are negative; not every core family is positive in every category. **Reason:** avoid universal or subgroup-significance interpretations.

```latex
Category-level patterns vary (Figure~\ref{fig:rq23-functional-category}). Inspection/search has large displayed contrasts in system administration, data processing, and debugging, while testing/validation is strongest in security and debugging. Several behaviors have weak or negative contrasts in particular categories. These descriptive patterns do not establish subgroup significance or causal benefits; agents reaching execution or validation may already have survived earlier setup stages.
```

### R26 — UNVERIFIED — evidence insufficient

**Location / quote:** RQ3.1 Method: “SHA-256 hashes of the stored instruction text identify 67 ... identical ... 22 ... changed.”  
**Current:** presents stored classes as a fully reproducible version comparison.  
**Replacement:** preserve **22/67 as stored strata**, disclose provenance limitations.  
**Evidence:** S11 `task_version_audit.csv.classification`, all stored hash equalities agree with class. However, only **23/89** saved TB2.0 hashes match the current raw catalog descriptions byte for byte; whitespace-collapse matches **87/89**, leaving `llm-inference-batching-scheduler` and `modernize-scientific-stack` unmatched under that simple normalization. The notes compare TB2.0 catalog descriptions with representative TB2.1 trajectory prompts and explicitly lack TB2.1 package checksums. The current analysis consumes the audit, with expected counts hard-coded, rather than rebuilding it. **Reason:** counts are verified as stored, original hash-generation normalization and representative-prompt selection are not fully reproducible from an audit builder. Do not replace the strata with newly guessed counts.

```latex
For TB2.0--TB2.1, we use the stored audit's partition of 22 instruction-changed and 67 instruction-unchanged tasks. The audit compares TB2.0 catalog descriptions with representative TB2.1 trajectory prompts, rather than complete task packages. Although its stored hash comparisons agree with this partition, the original text-normalization and prompt-selection provenance cannot be fully reconstructed from the retained audit. We therefore treat this partition as a sensitivity stratification and do not interpret unchanged instructions as unchanged execution conditions or packages.
```

### R27 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** RQ3.1 Method: TB3/TB4 “11 changed and 55 unchanged tasks.”  
**Current:** omits normalization of release boilerplate.  
**Replacement:** **11 normalized substantive instruction changes**, **54 release-boilerplate-only changes + 1 identical package**.  
**Evidence:** S11 `tb3_tb4_task_version_audit.csv.classification`; normalized SHA fields. Eight TB3-only tasks removed. The [official v4 release](https://github.com/harbor-framework/terminal-bench/releases/tag/v4.0.0) lists 19 named modified tasks plus a benchmark-wide `all` entry, separately from instruction hashing. **Reason:** raw text identity differs from normalized identity, and release changes include more than instruction edits.

```latex
TB4.0 retains 66 of the 74 TB3.0 tasks. The release notes list 19 named modified tasks in addition to benchmark-wide changes.\footnote{\url{https://github.com/harbor-framework/terminal-bench/releases/tag/v4.0.0}} In the stored task audit, 11 shared tasks have substantive instruction changes after release-boilerplate normalization; 54 differ only in that boilerplate and one has an identical package. We therefore use 11 changed and 55 normalized-instruction-unchanged tasks, without equating instruction stability with unchanged packages, timeouts, or execution conditions.
```

### R28 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ3.1 Results: “14.58 ... $d_z=0.908$, $p=1.80\times10^{-8}$”; instruction “$\delta=0.183$, $p=0.344$.”  
**Current → replacement:** retain **+14.58 pp**, replace paired `d_z=.924`, `p=1.22×10^-8`; instruction `delta=.208`, `p=.282`. Full-version TB3.0 **23.3%** remains correct; shared-task baseline is **21.61%**, not 23.3%. TB2 +38.45 pp and its effect/test remain correct.  
**Evidence:** S10/S11 exact transition rows. TB3 66 tasks: `W=164`, 62 nonzero pairs; changed/unchanged `U=365.5`, 11/55 tasks; mean improvements 20.123349/13.472485 pp. **Reason:** effective-ID grouping now aligns headline and paired inference.

```latex
Across all tasks in each version, effective-submission-balanced pass rates are 36.63\% in TB2.0, 75.08\% in TB2.1, 23.28\% in TB3.0, and 36.19\% in TB4.0. The fall from TB2.1 to TB3.0 compares substantially different task pools and is not a within-task decline.

Across the 89 shared TB2.0--TB2.1 tasks, pass rate increases by 38.45 percentage points ($d_z=1.803$, $W=1$, $p=2.64\times10^{-16}$). Sixty tasks improve by at least 25 points, 26 by 5--25 points, and three remain within $\pm5$ points; 88 improve and one declines by any amount. Instruction-changed tasks improve by 41.70 points on average versus 37.38 for the unchanged group, but the groups do not differ significantly (Cliff's $\delta=0.104$, $U=814$, $p=0.467$; 22 and 67 tasks).

Across the 66 tasks shared by TB3.0 and TB4.0, task-balanced pass rate rises from 21.61\% to 36.19\%, an increase of 14.58 percentage points ($d_z=0.924$, $W=164$, $p=1.22\times10^{-8}$). Fifty-one tasks improve, 11 decline, and four tie. The instruction-changed group improves by 20.12 points on average versus 13.47 for the normalized-instruction-unchanged group; this between-group difference is not significant (Cliff's $\delta=0.208$, $U=365.5$, $p=0.282$; 11 and 55 tasks). These observational gains are not isolated effects of instruction changes or model capability because evaluated systems and execution conditions also differ.
```

Shared-task median improvements are **36.7925278 pp** (TB2) and **13.8034188 pp** (TB3/TB4), distinct from the mean/headline gains. URL sensitivities are **+35.5852914** and **+14.3427704 pp**; both significant, but not primary replacements. The dormant TB2 matched-configuration paragraph should not be restored as fixed-model evidence without addressing the Gemini alias. Two exact labels overlap; the retained name alone does not prove a fixed provider endpoint. TB3/TB4 overlap contains 8 exact labels, including Grok with insufficient token coverage.

### R29 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ3.2 validation: alternative Sonnet panel “13 of 22 ... 59.1\% ... therefore retained the Haiku-based panel.”  
**Current → replacement:** the retained Sonnet cache records **17/22 (77.2727%)**, with 14 unanimous, 7 majority, 1 tie; **not 13/22**. Its model ID is `anthropic:claude-sonnet-5`. The cache lacks neutralization fields, unlike the fixed-panel validation; it cannot establish a controlled same-neutralization comparison.  
**Evidence:** S12 `_sonnet5.csv.correct` (17 true), `_sonnet5_summary.csv`, columns and votes; fixed-panel summary consensus 14/22. **Reason:** incorrect stored result and unsupported panel-selection rationale. Do not replace it with a claim that Sonnet is demonstrably better under the fixed protocol.

```latex
We use a fixed neutralized panel comprising \texttt{openai:gpt-4o-mini}, \texttt{anthropic:claude-haiku-4-5-20251001}, and \texttt{ollama:qwen2.5:7b-instruct}; \texttt{openai:gpt-4o-mini} neutralizes potentially leading wording before voting. Task-facing requirements and time estimates are preserved, while empirical outcomes and leaderboard information are excluded. The retained panel recovers 14 of 22 held-out native TB2 labels (63.6\%): 0/2 easy, 7/10 medium, and 7/10 hard. This small, imbalanced validation assesses agreement with author labels rather than accuracy on TB3/TB4. A historical Sonnet-based cache is not used to justify panel selection because equivalent neutralization provenance is not retained.
```

The fixed production cache has three valid votes per record and all 140 labels satisfy the stored consensus requirements; its distributions do not need regeneration. The held-out seed is `20260920`; calibration examples are excluded from validation by the labeling script. Individual held-out agreement: GPT-4o mini **14/22**, Haiku **12/22**, Qwen **15/22**. Retain the fixed protocol, but remove the false retrospective selection rationale.

### R30 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ3.2 Method: categories mapped “using the same three-LLM consensus procedure.”  
**Current → replacement:** the category cache attempted the same model identities but is **not a completed three-voter consensus**. All 89 rows have `consensus_vote_count=2`, an Anthropic `temperature` argument error, and 22 recorded ties with nevertheless assigned labels.  
**Evidence:** S13 every row's `consensus_votes_json`; error `Messages.create() got an unexpected keyword argument 'temperature'`; 67 `unanimous`/22 `tie` statuses. Current `llm_consensus.py` lines 286–288 rejects missing votes, and lines 294–296 leaves ties without a final label; `attach_unified_categories` checks valid category strings, not full voting provenance. Thus current category-generation code does not reproduce this historical cache as a completed three-voter protocol. **Reason:** methodological discrepancy and uncertain tie-resolution provenance. Stored category shares remain authoritative descriptions of this mapping, not validated ground truth.

```latex
For category comparisons, we use the seven TB3.0/TB4.0 groups: \texttt{Software}, \texttt{Science}, \texttt{ML}, \texttt{Operations}, \texttt{Security}, \texttt{Hardware}, and \texttt{Media}. TB3/TB4 categories are native. TB2.x uses a stored mapping into this taxonomy. Although three labelers were configured for that mapping, the retained cache contains two valid votes per task because the Anthropic call failed for all 89 tasks, and 22 records retain tied-vote status despite having a final category. The original tie-resolution provenance is incomplete. Category-composition results therefore describe this historical mapping and are interpreted cautiously; they do not share the validated three-voter difficulty protocol.
```

### R31 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ3.2 first Results paragraph: easy **70.53→92.50 (+21.97)**, medium **42.41→79.56 (+37.15)**, hard **19.11→64.58 (+45.47)**; gap closure **74.5/64.5/56.2%**.  
**Current → replacement:** effective-ID values **71.30→92.65 (+21.35)**, **43.23→79.55 (+36.32)**, **19.90→64.53 (+44.63)**; gap closure **74.4/64.0/55.7%**.  
**Evidence:** S14 `task_weighted_pass_rate` and change columns; easy 4, medium 55, hard 30 tasks. Gap closure is arithmetic `(new-old)/(1-old)` from these stored rates, not an extra fitted analysis. **Reason:** original paragraph used pooled-task means, not primary submission-balanced means.

```latex
TB2.1 has higher effective-submission-balanced pass rates across all author difficulty levels. Easy tasks increase from 71.30\% to 92.65\% (+21.35 pp), medium tasks from 43.23\% to 79.55\% (+36.32 pp), and hard tasks from 19.90\% to 64.53\% (+44.63 pp). Relative to each group's remaining gap to 100\%, these changes close approximately 74.4\%, 64.0\%, and 55.7\%, respectively. These difficulty-stratified comparisons are descriptive.
```

### R32 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ3.2 category gains: ML **31.1→88.6 (+57.5)**, data science **29.4→83.2 (+53.8)**, mathematics **23.4→75.9 (+52.5)**; media **15.4→64.0**.  
**Current → replacement:** ML **32.1→88.6 (+56.6)**, data science **30.5→83.3 (+52.8)**, mathematics **25.3→75.9 (+50.6)**; media **16.0→63.9%**. Extract-moves **14.8→14.7%**; video **25.9%** unchanged.  
**Evidence:** S10 adjacent table, transition `2.0->2.1`, equal mean across `category_old` groups (3/8/4 tasks), and seven media task IDs in S7. **Reason:** effective-ID category pass rates; no additional tests.

```latex
Within the shared TB2.x tasks, \texttt{machine-learning} increases from 32.1\% to 88.6\% (+56.6 pp), \texttt{data-science} from 30.5\% to 83.3\% (+52.8 pp), and \texttt{mathematics} from 25.3\% to 75.9\% (+50.6 pp). The seven exploratory perceptual-media tasks increase from 16.0\% to 63.9\%, although \texttt{video-processing} and \texttt{extract-moves-from-video} remain lower at 25.9\% and 14.7\%. These are descriptive comparisons of changing evaluated system populations on shared tasks.
```

The broad-category shares **Science 9.0/20.3/21.2%, Hardware 1.1/6.8/7.6%, ML 29.2/17.6/16.7%** remain numerically correct **conditional on the historical TB2 mapping**. Add R30's caveat rather than inventing revised category counts. The stored label distributions **4/55/30**, **0/2/72**, **0/1/65**, all-66 shared-label agreement, and no easy TB3/TB4 task remain correct.

### R33 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ3.2 task-time paragraph: “7.2 ... 6.3 ... 33.2 ... 24.6 minutes.”  
**Current → replacement:** TB3 full-task effective-ID median is **32.8711446041667→32.9 min**, not 33.2. TB2 **7.230533→7.2**, TB2.1 **6.29292→6.3**, TB4 **24.61785→24.6** remain correct.  
**Evidence:** S13 version summary `observed_task_median_duration_min_median`, 89/89/74/66 tasks. Expert means 206.7045/417.4054/392.5455; medians 60/240/240; timeouts 15/120/135 remain correct. Junior metadata: 88 estimates in each TB2 version, **none** in TB3/TB4. **Reason:** full 74-task descriptive summary differs from paired 66-task RQ3.3 duration baseline (33.2771 min).

```latex
Task-time estimates also change. Median expert estimates rise from 60 minutes in TB2.x to 240 minutes in both TB3.0 and TB4.0; means are 206.7, 417.4, and 392.5 minutes, respectively. Median agent timeouts rise from 15 to 120 and 135 minutes. Across all tasks in each version, effective-submission-balanced task median durations are 7.2 minutes in TB2.0, 6.3 in TB2.1, 32.9 in TB3.0, and 24.6 in TB4.0. Junior estimates are available for 88 TB2 tasks but absent for TB3/TB4, preventing the same longitudinal junior-time comparison. These composition and time summaries are descriptive, rather than additional significance tests.
```

### R34 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** RQ3.3 Method: “compare ... token usage, and cost.”  
**Current:** suggests cost is one of the primary longitudinal analyses, despite no such current inferential output.  
**Replacement:** five primary metrics, three descriptive diagnostics, no primary cost test.  
**Evidence:** S16 five metrics; S15 eight plotted measures; S20 report: positive cost coverage **25,840/38,604 (66.9%)**, **7,362/10,239 (71.9%)**, configuration-dependent. **Reason:** incomplete cost telemetry; do not introduce a new test.

```latex
We compare steps, shell invocations, structured tool calls, duration, and total reported tokens using paired shared tasks. For each measure, we take medians within effective submission--task--version cells and then across submissions within each task; paired absolute task differences provide the Wilcoxon test and $d_z$. We separately report pooled trajectory medians as descriptive statistics. Logged characters, input tokens, and completion/output tokens provide descriptive accounting diagnostics. Nonpositive token reports and metric-specific missing values are excluded for these resource summaries, while fractional-reward trajectories remain eligible. We do not add a primary longitudinal cost comparison because positive reported cost is incomplete and configuration-dependent.
```

### R35 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ3.3 `tab:rq33-inference`, all ten effect/p rows.  
**Current → replacement:** all ten `d_z` and p-values are obsolete for the primary effective-ID analysis. Correct values below.  
**Evidence:** S16 `(transition,metric)`, with eligible task counts **89/66**. Paired median changes: TB2 steps **-3.5**, shell **-4.5**, calls **-5**, duration **-57.802842 s**, tokens **+60,340**; TB3/TB4 **-10.25**, **-4.75**, **-10.25**, **-414.03829225 s**, **-1,925,222.5 tokens**. **Reason:** refreshed effective-submission balancing. All ten signs and unadjusted significance decisions remain the same.

```latex
\begin{table}[tb]
  \centering
  \caption{Paired shared-task inference after effective-submission balancing. Tests use absolute task differences; $n=89$ for TB2.0--TB2.1 and $n=66$ for TB3.0--TB4.0.}
  \label{tab:rq33-inference}
  \resizebox{\columnwidth}{!}{%
  \begin{tabular}{llrr}
  \hline
  Transition & Metric & Cohen's $d_z$ & $p$ \\
  \hline
  TB2.0--TB2.1 & Steps             & -0.313 & $8.89{\times}10^{-4}$ \\
              & Shell invocations & -0.524 & $1.18{\times}10^{-6}$ \\
              & Tool calls        & -0.417 & $3.05{\times}10^{-5}$ \\
              & Duration          & -0.139 & $4.73{\times}10^{-3}$ \\
              & Total tokens      &  0.297 & $1.60{\times}10^{-4}$ \\
  \hline
  TB3.0--TB4.0 & Steps             & -0.360 & $1.07{\times}10^{-5}$ \\
              & Shell invocations & -0.134 & $6.75{\times}10^{-3}$ \\
              & Tool calls        & -0.399 & $1.92{\times}10^{-5}$ \\
              & Duration          & -0.500 & $4.15{\times}10^{-8}$ \\
              & Total tokens      & -0.511 & $2.97{\times}10^{-6}$ \\
  \hline
  \end{tabular}%
  }
\end{table}
```

Use this complete paragraph alongside, rather than associating tests with pooled percentages:

```latex
The paired effective-submission-balanced analysis supports the same directions as the pooled descriptions for all five primary measures (Table~\ref{tab:rq33-inference}). In TB2.0--TB2.1, steps, shell invocations, tool calls, and duration decrease while total tokens increase; in TB3.0--TB4.0, all five decrease. All ten two-sided Wilcoxon tests are significant at the unadjusted 0.05 level. Ratios of cross-task medians give a 23.8\% token increase for TB2.0--TB2.1 and a 38.3\% reduction for TB3.0--TB4.0, distinct from the pooled 32.2\% increase and 34.3\% reduction. The tests assess paired absolute task differences, not either percentage ratio.
```

### R36 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ3.3 TB3→TB4 Results: “34.4\% ... 8.06M to 5.30M”, repeated before the matched-system paragraph.  
**Current → replacement:** positive-token pooled decline **34.2884609→34.3%**, not 34.4%; exact **8,064,089→5,299,037** tokens, **3,921/5,902** positive-token trajectories. Logged-text medians **379,444→305,219.5**, **-19.561385%** are correct as 379,444→305,220 / -19.6%.  
**Evidence:** S15 TB3/TB4 `total_tokens`, `chars`; full pools 4,337/5,902 retained, 74/66 tasks. Historical `performance_effort_pooled_summary.csv` uses **8,028,088.5→5,299,037 (-33.9937894%)** and smaller extracted text; these are separate preserved descriptions. **Reason:** correct percentage and matching refreshed figure, without replacing valid pooled medians with balanced estimates.

```latex
\textbf{TB3.0 to TB4.0}: In pooled retained trajectories, median steps decrease from 71 to 60 ($-15.5\%$), shell invocations from 55 to 47 ($-14.5\%$), structured tool calls from 75 to 63 ($-16.0\%$), and duration from 1973.4 to 1640.9 seconds ($-16.8\%$). Median logged text falls from 379,444 to approximately 305,220 characters ($-19.6\%$). Among positive token reports, median total tokens decrease from 8.06M to 5.30M ($-34.3\%$; $n=3,921$ and $n=5,902$). These pooled descriptions cover each version's full task pool and are distinct from the paired task-balanced inference. Median per-trajectory logged-character/token ratios are approximately 0.056 and 0.053, compared with 0.183 and 0.170 in TB2.0 and TB2.1.
```

The TB2 pooled primary measures and **+32.2%** total-token result remain correct. Exact input/output medians are **197,388.5→266,079** and **9,012→13,639.5**; the manuscript's integer presentations 197,389 and 13,640 are acceptable half-up rounded displays. The token-covered TB2.1 text median is **46,579.5**, displayed 46,580. The per-trajectory ratio decline is **6.8393%**, correctly 6.8%; it is not the ratio of the two medians.

### R37 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ3.3: “all seven ... use more tokens in TB4.0”; Discussion: “every matched ... pair.”  
**Current → replacement:** **6/7 increase**, median configuration percentage change **+18.8541384%**, range **-4.9678305% to +77.7288370%**. Claude Code/Fable 5 decreases **5,474,905→5,202,921 (-5.0%)**.  
**Evidence:** S17 all seven rows, exact task support in Appendix. There are 8 shared exact configuration labels, but Grok Build/Grok 4.6 lacks usable positive-token coverage in both versions. GLM-5.3 has **65**, not 66, shared token-covered tasks. **Reason:** false universal statement; this is not a refresh reversal in the seven-row comparison.

```latex
The matched-configuration description differs from the aggregate trend: six of the seven model--scaffold configurations with usable positive-token coverage in both versions have higher task-balanced token medians in TB4.0. Claude Code with Fable 5 decreases by 5.0\%; the median configuration change is +18.9\%, with a range from $-5.0\%$ to +77.7\%. Six comparisons cover 66 shared tasks and the GLM-5.3 comparison covers 65; these sparse configuration comparisons are descriptive and have no significance tests.

Population composition contributes substantially to the pooled token reduction. Codex with GPT-6 Astra accounts for 28.0\% of TB4.0 trajectories and has a pooled median of 1.80M tokens. Removing it raises the remaining TB4.0 pooled median from 5.30M to 8.73M, above TB3.0's 8.06M positive-token median. This exclusion comparison changes population composition and does not isolate a causal effect or establish efficiency at matched success.
```

Astra values are independently traceable to existing longitudinal rows: **1,650/5,902**, median **1,797,074.5**, remainder **8,731,532.5**. The archived S19 headline's raw name counts and old text extraction are not replacement sources for these refreshed quantities.

### R38 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ3.3 scaffold dependence: Gemini/Terminus “0.49.”  
**Current → replacement:** current TB2.1 median logged chars/token is **0.484715948→0.48** at two decimals (420 positive-token trajectories). Other displayed ratios remain correct: GPT-5.5 Terminus **0.360525932** (443), Codex **0.080233822** (444); Gemini CLI **0.067831227** (417).  
**Evidence:** `P/longitudinal/trajectory_longitudinal.csv`, filter `benchmark_version=2.1`, exact scaffold/model pair, `total_tokens>0`; median of `(message_chars+reasoning_chars+observation_chars)/total_tokens`. Producer is dataset builder plus longitudinal token-accounting measure definition. **Reason:** refreshed full text / exact rounding.

```latex
Token-use and logging relationships remain scaffold-dependent. In TB2.1, GPT-5.5 has a median 0.36 logged characters per reported token with Terminus-2 and 0.08 with Codex; Gemini 3.1 Pro has 0.48 with Terminus-2 and 0.07 with Gemini CLI. These descriptive ratios concern complete model--scaffold systems and their telemetry, rather than a standardized measure of model computation.
```

### R39 — UNVERIFIED — evidence insufficient

**Location / quote:** RQ3.3 hidden reasoning: mini-swe GPT-5 **432 / 78.5%**, GPT-5-mini **434 / 70.9%**, Gemini 2.5 **60/435**, Muse **0.20→0.48 / 56.1%**.  
**Current:** detailed per-call reasoning/accounting claims without a retained comparable calculation table. Configuration trajectory counts are present in S5, but that does not verify reasoning shares or completeness.  
**Replacement:** no speculative numeric replacement. Use the S19-backed TB4 Claude Sonnet example in R42, and retain general provider-accounting caveats only with checked citations. **Evidence:** S18 retains prompt growth, not these TB2 reasoning diagnostics; S19's explicit-token table covers TB4 and a different ratio definition. The exact historical diagnostic script/output is not retained in the inspected current/archived reports. **Reason:** insufficient evidence; do not reinterpret prompt tokens as hidden reasoning.

```latex
Some trajectories expose explicit reasoning or thinking-token fields, but coverage and accounting conventions vary across providers and scaffolds. Such fields can document model-side generation that is not reproduced in readable trajectory text. Their absence does not establish an absence of reasoning, and the character-to-token discrepancy cannot by itself quantify hidden reasoning.
```

### R40 — UNVERIFIED — evidence insufficient

**Location / quote:** RQ3.3 tool-output elision: first/last **5,000**, ratio **.170→.174**, **.053→.056**, TB4 mini-swe **+64.3%** characters.  
**Current:** corpus-adjustment statistics with no retained adjustment table or producer.  
**Replacement:** omit exact corrections. **Evidence:** S15/S18 store full extracted text, not a per-record omitted-length correction and its inclusion criteria; no retained elision diagnostic was found among the current analysis outputs or archived manuscript/before-after reports. **Reason:** cannot verify by simply reading a truncation marker; would require reconstructing an analysis.

```latex
Readable trajectories can omit or truncate tool output, prompts, and other context. Consequently, logged character counts measure retained content rather than all text processed by the model. The observed character-to-token ratio should be interpreted as a logging and accounting diagnostic, without assigning the unexplained difference to a single mechanism.
```

### R41 — UNVERIFIED — evidence insufficient

**Location / quote:** RQ3.3 tokenizer paragraph: **30%**, model shares **6.9/30.4%**, dividing by **1.3**, reductions “**2.\%** and **6.6%**.”  
**Current:** malformed “2.\%” plus an undocumented tokenizer sensitivity.  
**Replacement:** retain qualitative tokenizer incomparability, remove unverified arithmetic. **Evidence:** no retained model-to-tokenizer mapping or sensitivity table; S19 model population files use raw names and old text extraction, not this experiment. The cited bibliography entry is not supplied. **Reason:** exact reductions and affected-model membership cannot be independently verified; changing the typo to 2.0% would be a guessed replacement.

```latex
Tokenizers and provider accounting conventions introduce further variation in reported usage. The same readable text need not have the same token count across models, and repeated context, cached input, tool definitions, and unlogged prompts can also contribute. Reported tokens and logged characters therefore capture different constructs and should not be converted into a direct estimate of hidden reasoning or hardware computation.
```

### R42 — UNVERIFIED — evidence insufficient

**Location / quote:** final RQ3.3 paragraph: **7 configurations**, **2,304/2,309**, Gemini **64.3%**, Sonnet **78.0%**, ratios **.0103→.0104**, **.0407→.0431**.  
**Current:** mixes a plausible completeness audit with results that are not retained.  
**Replacement:** S19 supports the **seven explicit-counter groups totaling 2,309 trajectories** and Sonnet **329 / 78.0174%**, but not the **2,304 passing** or adjusted ratios. Its Gemini row uses reasoning/completion directly and gives **1.28669**, so it cannot validate a corrected completion share of .643. Do not treat 128.7% as a replacement scientific result; the denominator differs. **Evidence:** S19 E table and notes, every row; no comparable completeness-adjusted table. **Reason:** denominator/schema mismatch and missing audit.

```latex
The retained TB4.0 diagnostic identifies seven model--scaffold groups exposing explicit reasoning or thinking-token counters, covering 2,309 trajectories. For example, Claude Sonnet 5 with Claude Code has 329 trajectories and a median recorded thinking-token share of approximately 78.0\% of completion usage. Accounting conventions differ across these groups, so their shares are not directly interchangeable. These counters provide evidence of reasoning-related generation but do not quantify how much of the overall token-to-text discrepancy is due to reasoning rather than repeatedly processed input or omitted context.
```

This example is a **targeted descriptive audit**, not proof that all seven groups passed a uniform completeness protocol. The source diagnostic code is retained; it was not rerun here.

### R43 — UNVERIFIED — evidence insufficient

**Location / quote:** Dataset “June 18, 2026”; RQ3 footnotes “July 21, 2026” and “September 15, 2026” twice.  
**Current:** precise collection dates.  
**Replacement:** leave as author-supplied provenance only if separately documented, otherwise use snapshot wording below and remove the date clauses from the three existing footnotes while keeping their URLs. **Evidence:** stored `leaderboard_date`, submission timestamps, and S19 H date-reliability table establish **submission dates**, not fetch dates; retained source JSONs are bare lists without a scrape-time record. **Reason:** filesystem/Git timestamps cannot establish original collection dates.

```latex
We analyze stored snapshots of Terminal-Bench leaderboard metadata and available public per-trial trajectories. Submission dates identify leaderboard entries and are distinct from the dates on which those artifacts were collected.
```

Observed retained submission-date ranges are **2025-10-31–2026-05-14**, **2026-05-01–2026-07-11**, **2026-07-12–2026-08-18**, **2026-05-28–2026-09-03** for TB2.0/2.1/3.0/4.0. The apparently early TB4 dates are recorded source dates; do not relabel them as release or collection dates.

### R44 — UNVERIFIED — evidence insufficient

**Location / quote:** Parsing Method: “We inspected one TB2.0 trajectory from each ... 12 scaffolds ... holding the task constant.”  
**Current:** completed manual validation claim.  
**Replacement:** report the available review sample without claiming completed manual assessment. **Evidence:** S0 `parser_validation_sample.csv` has **24 rows across 12 scaffolds**, one common `tune-mjcf` example per scaffold and additional examples; every status is `prepared_for_researcher_review`, not a completed validation judgment. **Reason:** the sample supports review coverage, not evidence of the claimed completed historical review.

```latex
The repository provides a parser-review sample covering all 12 TB2.0 scaffolds, including a common \texttt{tune-mjcf} task example for each scaffold and additional examples. These records expose raw and parsed counts for review; their stored status indicates preparation for researcher review rather than a completed independent parser-validation assessment.
```

### R45 — UNVERIFIED — evidence insufficient

**Location / quote:** RQ3.3 population paragraph: exact model release dates **April 23, February 19, June 9, June 30, July 9**, default reasoning **medium/none**, GPT-5.5 “a tenth of submissions.”  
**Current:** provider-release and inference-setting claims are not established by repository telemetry.  
**Replacement:** preserve the supported recorded date range and population-change caveat; do not infer settings from model names. **Evidence:** S0/S19 date and model fields; reasoning settings and provider-side routing are not consistently stored; bibliography `main.bib` was not supplied with the manuscript. **Reason:** publication dates, model aliases, and actual per-run settings are different facts. This audit does not infer missing release/default facts from submission dates.

```latex
The evaluated population also changes: retained TB2.1 submission dates span May--July 2026 and include model families absent from much of the TB2.0 corpus. Recorded model names do not establish the reasoning settings, provider routing, or context-management policies used in each run. Cross-version changes therefore reflect the complete evaluated systems and their telemetry as well as the task pool.
```

### R46 — UNVERIFIED — evidence insufficient

**Location / quote:** Introduction “largest empirical analysis ... to date”; Background prior-work counts **200/300/3,843**, **1,794**, **64,380**, **50 tasks**.  
**Current:** literature priority and externally cited sample sizes.  
**Replacement:** repository size is verified; literature comparison remains citation-dependent. **Evidence:** S0 confirms own counts, not cited studies; supplied manuscript omits bibliography entries/full source papers. **Reason:** repository consistency does not establish external literature coverage. This is not a finding that those literature numbers are false. Retain only after a separate citation check; the following safe sentence replaces the priority claim and short comparative-size sentence without changing the RQs.

```latex
Our corpus supports a large-scale analysis of success, execution profiles, task characteristics, and agent behavior across four Terminal-Bench versions, comprising 48,843 retained leaderboard trajectories.
```

### R47 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** Abstract “32.2\% more ... despite increases among shared ... configurations.”  
**Current:** 32.2% is correct pooled; shared increase should not imply every configuration or causal population effects.  
**Replacement:** complete abstract in Section 4. **Evidence:** S15–S17; R37 six of seven. **Reason:** explicitly pooled, observational, and missing-telemetry scope.

### R48 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** Introduction “greater interaction and resource use are associated with higher success, but with diminishing returns”; “token use increases among ... shared.”  
**Current:** overstates a general positive association and omits configuration exception.  
**Replacement:** complete two-paragraph result summary in Section 4. **Evidence:** S2–S4, S16/S17. **Reason:** heterogeneous observational associations; moderate-level pattern and six-of-seven scope.

### R49 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** Discussion “both fall for population rather than system reasons” and “every matched ... pair used more tokens.”  
**Current:** causal attribution and false universal matched increase.  
**Replacement:** complete Discussion paragraphs in Section 4. **Evidence:** S16 decreases after task/submission balancing, S17 six of seven, R37 Astra exclusion. **Reason:** task/submission balancing does not hold configuration composition fixed, and the composition check does not isolate causation.

### R50 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** Implications “context ... settings substantially change token use for the same model”; behavior recommendations.  
**Current:** reasonable recommendations but should not imply interventions were tested.  
**Replacement:** Section 4 implication paragraph. **Evidence:** S5 configuration variation; S9 observational behavior; missing settings in R45. **Reason:** recommendations are hypotheses/design priorities, not estimated causal improvements.

### R51 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** Threats to Validity: mitigation by “separating changed and unchanged instructions”; construct claim “we separate input, output, and reasoning tokens where telemetry allows.”  
**Current:** omits stored-stratum, category-voting, multiplicity, support, and positive-token caveats.  
**Replacement:** complete Threats text in Section 4. **Evidence:** S11–S13, R26/R30/R39–R42; S20 no multiplicity adjustment. **Reason:** unresolved evidence must constrain interpretation, not be silently promoted to verified methodology.

### R52 — WORDING CHANGE — numerical result correct but interpretation misleading

**Location / quote:** Conclusion “success depends on ... how agents use their tools”; “more ... do not translate into higher success.”  
**Current:** causal and overly universal phrasing.  
**Replacement:** complete conclusion in Section 4; count 48,843 retained. **Evidence:** S2–S5/S9/S16. **Reason:** observed association and nonmonotonicity, without a controlled intervention.

### R53 — UPDATE REQUIRED — incorrect or outdated

**Location / quote:** RQ3 figure `fig:rq3_difficulty`, caption “Task-balanced pass rates by difficulty (TB2.0-2.1)”; RQ3 effort figures use `performance_effort_change_over_time_*.png` next to refreshed text.  
**Current:** current difficulty filename plots monthly submission performance; historical effort figures use older text/token populations.  
**Replacement:** figure mapping and complete environments in Section 5. **Evidence:** PNGs visually inspected, S15/S16 and `reports/longitudinal/effort_figure_captions.json`. **Reason:** content/caption/estimator mismatch. Overleaf image bytes were not supplied, so replacement means copy the current authoritative asset, not a claim that its existing bytes were hash-compared.

### R54 — UNVERIFIED — evidence insufficient

**Location / quote:** Discussion industry paragraph “In April 2026, GitHub introduced ... and then usage-based billing” and “OpenAI ... millions of tokens.”  
**Current:** external citation-dependent timing and usage claims.  
**Replacement:** no repository replacement number; preserve only with checked bibliography sources. **Evidence:** these events are not analysis outputs, and bibliography records are absent. **Reason:** outside what the retained repository verifies. A complete safe alternative is:

```latex
The distinction between visible interaction and reported model usage also matters for practical evaluation. A user-visible request or terminal action is an incomplete unit of resource accounting when context is repeatedly processed and logging conventions differ. Reporting token components and execution settings alongside task success would make these differences easier to assess.
```

## 4. Ready-to-paste cross-cutting narrative

These replacements consolidate R47–R52 and the substantive result corrections. They preserve the paper's RQs and structure. They replace complete existing narrative units, not the entire manuscript.

### Abstract (R47)

```latex
\begin{abstract}
Large language model agents are increasingly evaluated through task success on software engineering benchmarks, yet leaderboard scores provide limited insight into behavior, resource use, and efficiency. We analyze 48,843 publicly available trajectories across Terminal-Bench 2.0--4.0, examining associations among success, interaction activity, resource use, task characteristics, and agent behavior. Failed trajectories exhibit greater interaction and token use in pooled summaries, but several median relationships reverse within tasks. Success is generally highest at moderate levels of interaction and resource use, with statistical evidence of downward curvature varying across measures. Model--scaffold configurations show substantial performance--resource trade-offs, while harder tasks have lower success and generally higher resource use. Inspection, modification, execution, and validation are positively associated with within-task success. Longitudinally, TB2.1 has fewer interactions but 32.2\% higher pooled median reported tokens than TB2.0. TB4.0 has lower pooled token use than TB3.0, although six of seven shared configurations with usable token coverage have higher task-balanced token medians. These observational differences highlight the importance of task and system composition and the limits of resource-use telemetry. Meaningful evaluation therefore requires success rates to be complemented by task characteristics, system configurations, trajectory behavior, and consistent resource reporting.
\end{abstract}
```

### Introduction result summary (R48)

Replace the paragraphs beginning “Our results show” and “We also observe a change”:

```latex
Our results show that greater interaction and resource use are not monotonically associated with higher success. Pooled outcome differences can change after accounting for task and submission composition, and harder tasks generally use more resources while achieving lower success. Inspection, modification, execution, and validation are associated with higher within-task success, although these observational relationships do not identify causal benefits.

TB3.0 marks a substantial change in task composition and estimated completion time. From TB3.0 to TB4.0, success improves on 66 shared tasks while pooled interaction counts, duration, and token use decrease. Six of seven shared model--scaffold configurations with usable token coverage nevertheless have higher task-balanced token medians. The pooled and matched-configuration comparisons describe different evaluated populations, emphasizing the importance of system composition and reporting conventions.
```

The introduction corpus paragraph and contribution counts **48,843 / 31,103 / 7,501 / 4,337 / 5,902 / 162 / 15 / 53** remain unchanged. Optional copy edit: `normilized`→`normalized`. Remove or separately substantiate the priority claim as R46 specifies.

### Discussion (R49; external paragraph handled by R54)

```latex
Agent effort is not a single quantity. Within eligible tasks, successful trajectories have higher total-token medians and shorter duration (RQ1.1); across activity and resource levels, the observed relationship with success is nonmonotonic for several measures (RQ1.2). Across versions, visible interaction can decrease while reported tokens increase, as in TB2.0--TB2.1. TB3.0--TB4.0 instead shows decreases in both pooled summaries and effective-submission-balanced shared-task comparisons, while six of seven token-covered matched configurations increase token use. These estimands answer different questions and do not isolate the causes of the changes. Steps, duration, and reported tokens therefore cannot individually establish productive effort. Trace-level evaluation can examine useful actions, validation, and recovery without prescribing a fixed action sequence~\cite{grace_demystifying_2026}.

Lower pooled token use also does not establish improved efficiency at matched success. Removing Codex with GPT-6 Astra raises the TB4.0 pooled median above TB3.0's positive-token median, demonstrating sensitivity to population composition. However, one matched configuration decreases token use and six increase it. Efficiency comparisons should therefore identify the configuration, task set, outcome level, and telemetry definition, while recognizing that even exact recorded model names may conceal changes in provider routing or execution settings.
```

### Implications (R50)

The benchmark-designer paragraph can remain, with “make these differences visible” understood as a recommendation. Replace the scaffold paragraph and retain the model-developer paragraph's prospective framing:

```latex
\textbf{Scaffold builders} should evaluate scaffolds jointly with the models they serve, as observed performance and token use vary across their pairings. Inspection, modification, execution, and validation are useful workflow dimensions to record and investigate~\cite{englander_agents_2026}; their positive associations here do not demonstrate that adding or forcing these behaviors improves success. Context retention, caching, summarization, and reasoning settings should also be recorded and tested explicitly, so lower token use can be evaluated together with task success under comparable conditions.
```

### Threats to Validity (R51)

```latex
\textbf{Internal validity.} Models, scaffolds, task definitions, resource limits, and execution conditions change across versions. Shared-task and exact recorded-configuration comparisons reduce some differences but do not isolate causal effects. The TB2 instruction partition is a stored sensitivity stratification with incomplete original normalization and prompt-selection provenance; unchanged instructions do not establish unchanged packages. Training exposure and silent routing of model aliases also remain unknown. Behavior--success associations may reflect survivorship, since trajectories reaching execution or testing have often completed earlier stages, as well as differences in systems and task demands.

\textbf{External validity.} Retained TB2.0 trajectories cover 31,103 of 61,605 reported leaderboard trials and 74 of 142 leaderboard submissions. Available entries skew toward earlier, lower-performing systems, so behavioral results may underrepresent stronger or non-public systems. The study concerns command-line agents; generalization to IDE-based or repository-level workflows remains to be evaluated.

\textbf{Construct validity.} Recorded steps are schema-dependent trajectory entries, duration includes external latency, and human completion times are estimates rather than matched measurements. Tokenization, context processing, caching, omitted text, and reasoning-token accounting differ across providers and scaffolds. Positive-token filters also differ from raw nonmissing-token summaries and are stated separately. The fixed difficulty panel agrees with 14/22 held-out TB2 labels, including 0/2 easy tasks; its concentrated hard predictions are estimates rather than validated TB3/TB4 ground truth. The historical TB2 broad-category mapping contains only two valid votes per task and incompletely documented tie resolution, limiting category-composition interpretation.

\textbf{Conclusion validity.} Telemetry coverage and system representation are uneven, and task support differs across metrics and behavioral families. RQ2.1 and human-time RQ2.2 use URL grouping, primary RQ3 uses effective submission identifiers, and RQ2.3 uses within-task trajectory cells. These estimands should not be conflated. Statistical tests use unadjusted $\alpha=0.05$ without multiplicity correction; subgroup, composition, Pareto, token-accounting, and matched-configuration descriptions are not additional confirmatory tests.
```

### Conclusion and Future Work (R52)

```latex
Pass rates show whether an agent solved a task, but not how it proceeded, what resources it used, or where it struggled. Across 48,843 Terminal-Bench trajectories, success is associated with task characteristics, model--scaffold configurations, and recorded behavior, while greater interaction or resource use is not consistently associated with higher success. Trajectories remain an incomplete resource record: visible interaction can fall while reported tokens rise, context may be processed repeatedly, and providers and scaffolds differ in what they retain and report. Pooled trends can also differ from matched-configuration descriptions. Fair comparisons therefore require pass rates alongside task requirements, configuration information, trajectory behavior, and clearly defined resource measures. Future work should standardize input, cached, completion, and reasoning-token telemetry and execution settings, distinguish repeated context processing from model-side generation, validate behavioral mechanisms through controlled studies, and examine generalization to IDE-based and repository-level environments.
```

## 5. Figure and table replacement instructions

Copy assets only as part of manuscript revision; **this audit did not change or regenerate any figures**. The supplied manuscript contains filenames, not image bytes, so actual Overleaf asset identity is unverified. “Replace” means use the listed current repository asset for the revised claim. Labels can remain unchanged.

| Manuscript filename / label | Current repository asset | Action and caption |
|---|---|---|
| `images/RQ1/diminishing_returns_performance_box_total_tokens.png`, `fig:diminishing_pass_fail` | `reports/diminishing_returns/by_outcome/box_plots/diminishing_returns_performance_box_total_tokens.png` | Retain current asset. Caption should specify positive-token distributions on log scale; raw pooled table includes reported zeros. |
| `images/RQ1/rq1_pooled_vs_task_balanced_effort_success.png`, `fig:task-balanced-effort` | `reports/diminishing_returns/effort_bins/rq1_pooled_vs_task_balanced_effort_success.png` | Retain. Caption: pooled and effective-submission/task-balanced pass rates in fixed intervals for displayed measures; descriptive curves. |
| `images/RQ1/rq1_3_configuration_token_pareto.png`, `fig:rq13-scaffold-token-pareto` | `reports/diminishing_returns/configuration_pareto/rq1_3_configuration_token_pareto.png` | Retain. Qualify 69 token-covered eligible configurations; line is descriptive nondominated frontier. |
| `images/RQ2/task_difficulty_success_task_weighted.png` | `reports/tasks/difficulty/task_difficulty_success_task_weighted.png` | Replace with current: 73.9/46.5/22.1%, URL-balanced. |
| `images/RQ2/heatmap_task_difficulty_effort_median.png` | `reports/tasks/difficulty/effort_vars/heatmap_task_difficulty_effort_median.png` | Replace with current; nested medians using URL units, positive cost. |
| `images/RQ2/heatmap_task_domain_effort_median.png` | `reports/tasks/category/effort_vars/heatmap_task_domain_effort_median.png` | Replace with current updated category cells; same aggregation qualifier. |
| `images/RQ2/rq2_3_functional_success_association_by_difficulty.png` | `reports/tasks/tools/rq2_3_functional_success_association_by_difficulty.png` | Replace with current; descriptive within-task trajectory contrasts, support 3 use/3 non-use trajectories; no subgroup significance. |
| `images/RQ2/rq2_3_functional_success_association_by_category.png` | `reports/tasks/tools/rq2_3_functional_success_association_by_category.png` | Replace with current; same support/observational qualification. |
| `images/RQ3/pass_rate_instruction_change_robustness_all_versions.png` | `reports/longitudinal/pass_rate_instruction_change_robustness_all_versions.png` | Copy current if retained; caption distinguish stored TB2 strata and normalized TB3 strata. See provenance caveats R26/R27. |
| `images/RQ3/pass_rate_change_by_difficulty.png`, `fig:rq3_difficulty` | `reports/longitudinal/pass_rate_change_by_difficulty.png` | **This is a monthly submission/difficulty plot**, not version-level grouped rates. Retain only with corrected monthly caption below; R31 version rates come from S14. |
| Optional version-level difficulty replacement, same label if chosen | `reports/longitudinal/difficulty_over_versions/pass_rate_by_difficulty_over_versions.png` | Current grouped version plot; caption must distinguish native TB2 labels from LLM-assigned TB3/TB4 labels. If used instead, monthly paragraph need not cite it. |
| `images/RQ3/task_composition_over_versions.png` | `reports/longitudinal/task_composition/task_composition_over_versions.png` | Replace with current. Shares remain numerically correct; caption disclose historical TB2 mapping and two-vote/tie limitations. |
| `images/RQ3/performance_effort_change_over_time_tb2_0_to_tb2_1.png`, `fig:rq3_effort_2_21` | `reports/longitudinal/effort_change_pooled_refreshed_tb2_0_to_tb2_1.png` | Replace for the **existing pooled narrative**; caption explicitly descriptive, positive tokens. Preserve old repository figure as historical. |
| `images/RQ3/performance_effort_change_over_time_tb3_0_to_tb4_0.png`, `fig:rq3_effort_3_4` | `reports/longitudinal/effort_change_pooled_refreshed_tb3_0_to_tb4_0.png` | Replace for pooled full-text/positive-token narrative; -34.3% token change. |
| Optional balanced counterpart for either transition | `reports/longitudinal/effort_change_submission_balanced_tb2_0_to_tb2_1.png` and `...tb3_0_to_tb4_0.png` | Use only with balanced medians/percentages; captions from `effort_figure_captions.json`. Do not label pooled 32.2% as this figure's estimate. |
| Commented human-time figure | `reports/tasks/time_estimates/distribution_task_time_estimates.png` | If restored, copy current; actual attempt duration versus human estimates, not measured human completion comparison. |
| Commented longitudinal time figure | `reports/longitudinal/task_composition/task_time_estimates_over_versions.png` | If restored, copy current; full 74-task TB3 observed median 32.9 min. |
| Supplementary prompt/text figures | `reports/longitudinal/token_accounting/{input_context_growth_distribution,input_token_accumulation,token_vs_logged_text_over_time}.png` | Current refreshed assets, if used. Positive-first growth denominator 34,463; descriptive token/text accounting. |
| Shell Pareto, not active manuscript token figure | `reports/diminishing_returns/configuration_pareto/rq1_3_configuration_shell_invocations_pareto.png` | Replace only if used elsewhere; OpenHands/Haiku shell median changed. Other token frontier quantities unchanged. |

Complete figure environments for the two existing **pooled** results figures (copy repository assets into the indicated manuscript paths during revision):

```latex
\begin{figure}[tb]
    \centering
    \includegraphics[width=\columnwidth]{images/RQ3/effort_change_pooled_refreshed_tb2_0_to_tb2_1.png}
    \caption{Relative changes in pooled trajectory medians from TB2.0 to TB2.1. These descriptive summaries use full extracted logged text and positive reported tokens; paired task-level inference is reported separately.}
    \label{fig:rq3_effort_2_21}
\end{figure}

\begin{figure}[tb]
    \centering
    \includegraphics[width=\columnwidth]{images/RQ3/effort_change_pooled_refreshed_tb3_0_to_tb4_0.png}
    \caption{Relative changes in pooled trajectory medians from TB3.0 to TB4.0. Each version's full retained task pool is included, with positive token reports; these descriptive percentages are distinct from shared-task inference.}
    \label{fig:rq3_effort_3_4}
\end{figure}
```

Minimal correction retaining the **current monthly** difficulty figure:

```latex
\begin{figure}[tb]
    \centering
    \includegraphics[width=\columnwidth]{images/RQ3/pass_rate_change_by_difficulty.png}
    \caption{Submission-level task-weighted pass rates by author difficulty over recorded submission dates; lines show monthly medians. System and benchmark-version composition vary across months.}
    \label{fig:rq3_difficulty}
\end{figure}
```

Remove the R31 version-rate paragraph's reference to this monthly figure; attach `Figure~\ref{fig:rq3_difficulty}` to the monthly-results paragraph instead. Its counts are verified in existing rows: March 2026 **1 effective submission / 1 URL**, TongAgents (`judy`) with Gemini 3.1 Pro; May **14 effective submissions / 13 URLs**. The phrase “lower May median therefore mainly reflects composition” is too causal; use: `Monthly medians are sensitive to the represented systems: March contains one effective submission, whereas May contains 14. These are not repeated measurements of a fixed system population.`

If choosing the grouped version plot instead, use this complete alternative, not both under the same label:

```latex
\begin{figure}[tb]
    \centering
    \includegraphics[width=\columnwidth]{images/RQ3/pass_rate_by_difficulty_over_versions.png}
    \caption{Effective-submission-balanced pass rates by version and difficulty. TB2.x uses native labels; TB3.0/TB4.0 use the fixed neutralized three-model labels, which have limited held-out validation.}
    \label{fig:rq3_difficulty}
\end{figure}
```

Active numerical tables needing full replacement are **`tab:within-task-effort`**, **`tab:rq23-functional-use`**, **`tab:rq33-inference`**, and **`tab:tag-category-pass-rate`** (conservative removal of six unverifiable rows). The metric-definition table **`tab:effort_metrics`** needs wording clarification. All five complete environments are provided above. The commented pooled pass/fail table remains numerically correct for its raw nonmissing-token population and should not be replaced by positive-token medians without changing its population description.

## 6. Historical changes and interpretation boundaries

The archived 40-row before/after table records **20 numerically changed inferential rows**, **no significance-threshold crossings**, and **no reported inferential raw-effect sign reversals**. This does not mean every manuscript value matches its historical baseline: the manuscript mixes the refreshed +14.58 pp headline with older accompanying tests, says all seven token pairs increased despite the historical seven-row table already containing a decrease, and supplies a Sonnet validation result inconsistent with the retained cache.

The complete 31-row descriptive direction-change inventory is appended below. It contains 16 distinct quantity/task or comparison cases: seven task-duration-median changes, six task-duration-mean changes, two task pass-rate changes (with both absolute and relative rows for these 15 cases), and one model-progression logged-text percentage. The two shared-task performance reversals are **`biped-contact-dynamics` -0.4166667→+2.8205128 pp** and **`vf2-speedup-networkx` -3.1944444→+0.2991453 pp**. Hence improved/declined/tied counts change **49/13/4→51/11/4** in the historical-versus-current TB3/TB4 task comparison. TB2 remains **88/1/0**.

The separate Terminus-2 Opus 4.6→4.7 **logged-character** progression reverses **+4.5881061%→-1.1624341%**. This is not the seven-configuration TB3/TB4 token comparison. Current row `terminus2_opus46_to_opus47` in S18 verifies the new direction; the old value comes only from the external before/after record. Prompt-growth **34,139/34,463 = 99.0598613%**, median final/first **9.48056765×**, is correct. Historical reconstructed eligibility **34,862** included 399 nonpositive-first-prompt records; it is not a replacement denominator for the retained positive-first analysis. Exact prompt-sum agreement **33,155/34,463**, 96.2046253%, is diagnostic, not an eligibility filter.

No pooled-versus-balanced direction reversal occurs for the eight RQ3.3 measures. For TB2, interactions/duration fall and text/input/output/total tokens rise in both. For TB3/TB4, all eight fall in both. The **configuration-level** six-of-seven increase is a different conditioning operation; it does not overturn either pooled or task/submission-balanced findings. These estimands do not identify whether composition, task changes, inference settings, provider accounting, or underlying models cause the differences.

Historical pooled files are deliberately retained and differ from the refreshed descriptions. In particular, TB3 historical tokens include 3,924 nonmissing reports (three zeros) versus 3,921 positive reports; text extraction also changes. URL-grouped and trial-weighted sensitivity summaries remain separately named. The appended current sensitivity tables identify these estimates rather than silently substituting them for the primary effective-ID rows.

## 7. Unresolved evidence and actions for the manuscript

- **TB2 instruction provenance:** retain 22/67 as stored strata with explicit limitation. The original builder, normalization choices, and representative prompt selection are not fully independently reproducible; two catalog descriptions remain unmatched even under simple whitespace collapse. Do not infer package stability.
- **Category protocol:** current shares are conditional on historical labels, with two valid votes and 22 tied records; do not claim a validated three-voter mapping. Final tie assignments cannot be regenerated from the present consensus algorithm.
- **Sonnet alternative:** 17/22 is verified as stored; the manuscript's 13/22 and same-neutralization comparison are not supported. Keep the fixed panel and remove the comparative selection rationale.
- **Unretained results:** six tag/requirement pass rates, global interface marginals/+12.7 pp, exact difficulty-subgroup tenths, TB2 reasoning proportions, elision corrections, tokenizer sensitivity, and TB4 completeness-adjusted diagnostics remain unverified. Conservative replacements above require no new numbers.
- **Collection and human review provenance:** exact scrape dates and completed manual review are not independently established by date fields or a prepared sample. Keep only as explicitly author-documented provenance, or use the supplied conservative wording.
- **External claims:** literature priority, cited study sample sizes, provider release dates/default settings, and industry anecdotes are citation-dependent and not established by repository outputs. The two benchmark release pages were consulted for task evolution; this was not a full bibliography audit. No nonexistent replacement references are supplied.
- **Source-output drift:** the difficulty cache enforces a fixed complete-vote protocol; the category cache does not meet today's consensus generator's constraints. Existing category files were retained and not relabeled. Some saved table schemas also omit columns that current builders would export (e.g. `complete_case_count` in RQ2 effort summaries); absence is documented rather than assumed to be zero.

## 8. Final checklist by manuscript section

- [ ] **Abstract:** use R47; retain 48,843 and pooled +32.2%, qualify six of seven and observational interpretation.
- [ ] **Introduction:** preserve corpus/version counts; use R48; remove or substantiate priority claim; correct spelling of normalized.
- [ ] **Background:** separate citation-dependent literature counts from verified own corpus counts; do not claim benchmark annotation fields are complete across all versions (TB3/TB4 native difficulty unknown and junior estimates absent).
- [ ] **Approach:** distinguish effective IDs, URLs, and behavior trajectory cells; specify nested medians, regression exception, zeros/missingness, unadjusted tests; address collection/review provenance.
- [ ] **RQ1.1:** replace complete table; retain raw pooled medians and p90 values with population qualifiers; explain shell median versus `d_z` sign.
- [ ] **RQ1.2:** shell peak 39.68%; pooled quantile robustness; retain four significant curvature results and six convergence statements; avoid causal budgets or generalized monotone effort claims.
- [ ] **RQ1.3:** retain numerical token frontier/examples, state 80-task/300-trajectory support and missing token configurations; preserve descriptive interpretation.
- [ ] **RQ2.1:** update difficulty/category rates, rho, resources, model margins, and category ranking; use current three active RQ2.1 assets; distinguish marginal versus joint configurations.
- [ ] **RQ2.2:** replace unverified tag table with supported media comparison or provide independent source evidence; agent median 7.02 min; success-only 86 tasks and 7.21 min; no speedup interpretation.
- [ ] **RQ2.3:** trajectory-cell support, complete corrected nine-family table, current heatmaps, subgroup limitations and survivorship; omit unverified global interface rates.
- [ ] **RQ3 overview:** retain per-version retained/binary counts; call 74/17/13/18 **effective** submission counts, not unique URLs.
- [ ] **RQ3.1:** full versus shared TB3 task population; +14.58 pp with `.924 / 1.22e-8`; `.208 / .282` instruction test; stored 22/67 and normalized 11/55 qualifications; 51/11/4 task changes.
- [ ] **RQ3.2:** retain fixed-panel identities and 14/22, remove false Sonnet rationale; disclose historical category voting failures; update subgroup gains and TB3 duration 32.9 min; composition tests remain descriptive; correct monthly figure caption.
- [ ] **RQ3.3:** separate pooled and balanced values; replace all ten inference rows; pooled -34.3%; six of seven matched tokens, GLM 65 tasks; replace historical pooled assets for refreshed text; qualify diagnostics, zeros, and missingness.
- [ ] **Discussion:** remove “every matched” and causal “population rather than system reasons”; use matched-efficiency qualifications and R54's conservative external alternative if citations are not verified.
- [ ] **Implications:** retain recommendations as prospective design priorities, not experimentally established behavioral interventions.
- [ ] **Threats:** include label/category/provenance, schema, telemetry, support, multiple-testing, and survivorship limits.
- [ ] **Conclusion:** preserve own corpus count and research questions; use observational/nonmonotonic wording; avoid implying every matched system increased tokens.
- [ ] **Tables and captions:** copy the five complete table environments and current assets as specified; do not restore stale commented alternatives without their qualifiers.
- [ ] **Repository:** only this report is added; leave uncommitted; no push and no analysis regeneration.

## 9. Evidence appendix

The following tables transcribe existing current outputs or summarize existing processed rows for traceability. Values are displayed with up to 15 significant digits; original CSVs preserve full serialization precision. Rates are proportions unless explicitly `%` or `pp`; counts are integers. These tables are evidence, not newly generated analyses. No fitted model, significance test, labeling procedure, or raw-corpus behavior parser was rerun.


### A. Numerical claims already consistent

These numerical claims should remain at the stated precision. Methodological qualifiers and repeated-location wording corrections in the R-register still apply.

| ID | Status | Manuscript claim | Values to retain | Evidence / population |
|---|---|---|---|---|
| V01 | VERIFIED — correct | Corpus, abstract/introduction | 48,843 retained; 38,604 TB2.x and 10,239 TB3/TB4 | S0, retained row counts; version sum |
| V02 | VERIFIED — correct | Introduction and RQ3 overview | 31,103 / 7,501 / 4,337 / 5,902 retained by version | S0, each trajectory table / corpus.trajectory_count |
| V03 | VERIFIED — correct | Approach and RQ3 overview | 48,785 binary; TB3.0 4,279 | S0 reward in {0,1}; S10 trajectory_count |
| V04 | VERIFIED — correct | Approach fractional rewards | 58 = 52 erp-procurement-planning + 6 kv-live-surgery | S0 TB3 reward not in {0,1}; includes only retained records |
| V05 | VERIFIED — correct | Introduction/contribution | 162 unique task names across versions | S0 task_name union; not sum of version counts |
| V06 | VERIFIED — correct | Introduction/contribution | 15 scaffolds / 53 normalized model components | S0 scaffold and model_dir unions; not raw model_name |
| V07 | VERIFIED — correct | Introduction TB2.0 | 89 tasks / 12 scaffolds / 33 normalized components | S0 TB2 distinct task_name/scaffold/model_dir |
| V08 | VERIFIED — correct | Approach leaderboard | 142 submissions / 61,605 trials | S0 TB2 corpus_stats leaderboard; submission_summary |
| V09 | VERIFIED — correct | Approach outcomes | 11,219 successful / 19,884 failed TB2 trajectories | S1 trajectory_count pass/fail |
| V10 | VERIFIED — correct | Approach availability | 21.95 pp lower aggregate pass rate with public trajectories | S0 TB2 submission_summary; 11,655/32,412 versus 16,904/29,193; difference -21.9453880 pp |
| V11 | VERIFIED — correct | RQ1.1 pooled interaction/duration/cost | Fail/pass: 22/19 steps, 22/18 shell, 25/22 calls, 533/296 s, .167/.205 USD | S1 raw pooled medians; cost positive only |
| V12 | VERIFIED — correct | RQ1.1 raw pooled tokens | 166,391 pass / 239,455 fail; 30,581 nonmissing | S1; S0 corpus_stats; zeros included |
| V13 | VERIFIED — correct | RQ1.1 token p90 | 1,330,103.5 pass / 2,865,672.6 fail; 1.33M/2.87M display | S1 total_tokens_p90; raw reports |
| V14 | VERIFIED — correct | RQ1.1 seven unchanged task-test rows | Steps, calls, input, output, total tokens, duration, cost match displayed table precision | S2 metric rows excluding shell; exact values below |
| V15 | VERIFIED — correct | RQ1.1 step support sensitivity | 86 tasks at >=3, 84 at >=4 distinct submissions per outcome | S2 eligibility thresholds metric=step_count |
| V16 | VERIFIED — correct | RQ1.2 steps/duration/token peaks and tails | 38.88/8.73%, 39.29/2.49%, 36.64/5.83% | S3 task_balanced_pass_rate peak/highest bins |
| V17 | VERIFIED — correct | RQ1.2 tool-call peak | 39.64% in 16-35 structured calls | S3 tool_call_count,16-35 |
| V18 | VERIFIED — correct | RQ1.2 cost high intervals | 38.47% at $.50-1; 36.14% >$1 | S3 cost_usd_positive; task-balanced |
| V19 | VERIFIED — correct | RQ1.2 high-tail support | 786/493/667 trajectories, 86/71/41 tasks (>200 steps/>10M tokens/>60m) | S3 trajectory_count and task_count |
| V20 | VERIFIED — correct | RQ1.2 four significant curvature terms | Steps -.425,p .0028; tokens -.341,.0102; duration -.486,.0019; cost -.289,.0254 | S4 standardized coefficients and two-sided Wald p-values |
| V21 | VERIFIED — correct | RQ1.2 convergence | All six quadratic models converged; shell and calls nonsignificant | S4 quadratic_converged, beta_2_p |
| V22 | VERIFIED — correct | RQ1.3 token frontier endpoints | 3.4%/16k;14.3%/23k;62.9%/82k;74.4%/305k;76.5%/769k | S5 exact rows in frontier appendix; telemetry-qualified |
| V23 | VERIFIED — correct | RQ1.3 same-model scaffold comparisons | GPT-5 51.8/44.8/~35%; Gemini 74.4/60.9%; Opus 76.5/62.9/59.3% | S5 task_balanced_pass_rate_pct; support differs by row |
| V24 | VERIFIED — correct | RQ2.1 selected unchanged margins | Opus debugging96.0%,security78.8%; Terminus3.3 debugging96.0% | S6 model/scaffold category tables; not joint effects |
| V25 | VERIFIED — correct | RQ2.2 media comparison | 7/82 tasks;16.0/38.4%;-22.4pp | S7 exploratory effective-ID task means; no test |
| V26 | VERIFIED — correct | RQ2.2 media exception | code-from-image 60.7% TB2.0 | S10 adjacent 2.0->2.1 task row old rate=.606982... |
| V27 | VERIFIED — correct | RQ2.2 human estimates and rounded effects | 88 tasks;60/240min; d_z=-.509/-.403; both p<.001 | S8; agent median itself requires correction |
| V28 | VERIFIED — correct | RQ2.3 eligibility and broad significance | Nine families, eligible counts89/89/89/82/80/50/13/48/12; four core associations significant | S9; support is trajectories, not submissions |
| V29 | VERIFIED — correct | RQ3 corpus effective submissions | 74/17/13/18 effective units, scaffolds12/6/6/4, models33/12/12/14 | S0 effective_submission_id and S10 submission_count |
| V30 | VERIFIED — correct | RQ3.1 TB2 primary gain | 36.63->75.08%;+38.45pp;d_z1.803,p2.64e-16 | S10 89 shared tasks; effective IDs |
| V31 | VERIFIED — correct | RQ3.1 TB2 instruction test | Cliff delta .104,p .467 | S11 22/67 stored strata; provenance limitation R26 |
| V32 | VERIFIED — correct | RQ3.1 TB2 broad gains | 60 >=25pp,26 5-25pp,3 within +/-5pp;none decline >=5pp | S10 adjacent table, 89 tasks |
| V33 | VERIFIED — correct | RQ3.1 full-version TB3 rate | 23.3% at original one-decimal display | S10 version summary 74 tasks, rate .23284513909513907 |
| V34 | VERIFIED — correct | RQ3.1 TB3/TB4 gain headline | +14.58pp | S10 paired inference 66 tasks; accompanying tests require update |
| V35 | VERIFIED — correct | RQ3 retained task pools | TB3 74 tasks; TB4 retains66, removes8 | S0 and S11 task audit; no new TB4 task |
| V36 | VERIFIED — correct | RQ3.2 fixed difficulty panel | openai:gpt-4o-mini;anthropic:claude-haiku-4-5-20251001;ollama:qwen2.5:7b-instruct; GPT-4o-mini neutralizer | S12 fixed difficulty_protocol.py and valid production cache |
| V37 | VERIFIED — correct | RQ3.2 fixed-panel validation | 14/22=63.6%;sample2easy/10medium/10hard | S12 consensus validation summary; no Sonnet-selection rationale |
| V38 | VERIFIED — correct | RQ3.2 difficulty distributions | TB2 4easy/55medium/30hard;TB3 2medium/72hard;TB4 1medium/65hard | S12/S14; all66 shared tasks retain their saved label |
| V39 | VERIFIED — correct | RQ3.2 stored category shares | Science9.0/20.3/21.2%;Hardware1.1/6.8/7.6%;ML29.2/17.6/16.7% | S13 sum n_tasks across native category rows; conditional on historical mapping |
| V40 | VERIFIED — correct | RQ3.2 expert/timeouts | Expert medians60/240/240min;means206.7/417.4/392.5;timeouts15/120/135min | S13 full-version composition summary; descriptive |
| V41 | VERIFIED — correct | RQ3.3 TB2 pooled activity/duration | 21->18,-14.3%;20->15,-25%;23->19,-17.4%;408.9->376.9s,-7.8% | S15 pooled retained trajectories |
| V42 | VERIFIED — correct | RQ3.3 TB2 pooled token change | 213,974.5->282,852,+32.2%;input+34.8%;output+51.3% | S15 positive-token subset 30,126/7,434 |
| V43 | VERIFIED — correct | RQ3.3 full logged-text medians | TB2 36,828->46,348,+25.8%;TB3/TB4 379,444->305,219.5,-19.6% | S15 chars row; all retained records |
| V44 | VERIFIED — correct | RQ3.3 TB2 token-covered text/ratio | 37,241->46,579.5 chars; .182629863->.170139172 chars/token | S15 populations; longitudinal rows; median of per-trajectory ratios |
| V45 | VERIFIED — correct | RQ3.3 input accumulation | 34,139/34,463=99.06%;median final/first9.48x | S18 overall row; positive first prompt, >=2 calls |
| V46 | VERIFIED — correct | RQ3.3 three unchanged scaffold ratios | GPT-5.5 Terminus .36/Codex .08; Gemini CLI .07 | S15 source rows filtered TB2.1; R38 updates Gemini Terminus .49 |
| V47 | VERIFIED — correct | RQ3.3 Astra population sensitivity | 28.0%;1.80M tokens;exclusion5.30M->8.73M | S15 longitudinal TB4 codex/gpt-6-astra;1,650/5,902; no causal efficiency inference |
| V48 | VERIFIED — correct | RQ3.2 monthly support | March1 effective submission TongAgents/Gemini;May14 effective submissions | S0/S15 TB2x submission_timestamp month; URLs are1/13 |


### B. Corpus, units, and telemetry coverage

Source S0, stored `trajectory_summary.csv` columns named below. Counts are read-only summaries; fractional rewards remain in continuous-measure populations.

| Version | Retained | Binary | Tasks | Scaffolds | Model components | Effective submissions | Source URLs | Exact configurations | Nonmissing tokens | Positive tokens | Positive cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2.0 | 31103 | 31103 | 89 | 12 | 33 | 74 | 55 | 73 | 30581 | 30126 | 20401 |
| 2.1 | 7501 | 7501 | 89 | 6 | 12 | 17 | 17 | 17 | 7461 | 7434 | 5439 |
| 3.0 | 4337 | 4279 | 74 | 6 | 12 | 13 | 12 | 12 | 3924 | 3921 | 3458 |
| 4.0 | 5902 | 5902 | 66 | 4 | 14 | 18 | 18 | 14 | 5902 | 5902 | 3904 |


### C. Raw pooled outcome medians and p90 (zeros retained for tokens)

Source: `data/processed_live/terminal_bench_2_0/trajectory_features_by_outcome.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| reward_outcome | trajectory_count | step_count_median | step_count_p90 | shell_invocation_count_median | shell_invocation_count_p90 | tool_call_count_median | tool_call_count_p90 | total_tokens_median | total_tokens_p90 | cost_usd_median | cost_usd_p90 | duration_seconds_median | duration_seconds_p90 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pass | 11219 | 19 | 67 | 18 | 59 | 22 | 66 | 166391 | 1330103.5 | 0.204578625 | 1.253293725 | 296.228 | 984.5934 |
| fail | 19884 | 22 | 107 | 22 | 100 | 25 | 107 | 239455 | 2865672.6 | 0.16713255 | 1.8889569 | 533.2455 | 1863.356 |


### D. RQ1.1 complete current inferential table

Source: `data/processed_live/diminishing_returns/rq1_1_success_failure_inference.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| metric | eligible_tasks | median_task_difference | cohens_dz | wilcoxon_statistic | p_value |
|---|---|---|---|---|---|
| step_count | 86 | 2 | 0.130583798033597 | 1479.5 | 0.127194746755061 |
| shell_invocation_count | 86 | 0.375 | -0.0136526800336146 | 1496 | 0.438556875143347 |
| tool_call_count | 86 | 1.125 | 0.104213606844877 | 1398.5 | 0.11768846199576 |
| prompt_tokens | 85 | 21618 | 0.254136593484926 | 1274 | 0.015295497390481 |
| completion_tokens | 85 | -29.5 | 0.164443247924734 | 1711 | 0.609718457481134 |
| total_tokens | 85 | 20272 | 0.246160078290407 | 1316 | 0.0250084783275188 |
| duration_seconds | 86 | -44.88725 | -0.274727436357776 | 1190 | 0.0033871019599293 |
| cost_usd_positive | 83 | 0.086210475 | 0.457220299604996 | 385 | 7.02597366991317e-10 |


### E. RQ1.1 pooled filter populations and outcome-direction counts

Source: `data/processed_live/diminishing_returns/rq1_within_task_effort_summary.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| metric | complete_case_count | pooled_success_median | pooled_failure_median | eligible_task_count | pass_higher_task_count | fail_higher_task_count | tie_task_count | median_within_task_difference_pass_minus_fail |
|---|---|---|---|---|---|---|---|---|
| step_count | 31103 | 19 | 22 | 86 | 51 | 34 | 1 | 2 |
| shell_invocation_count | 31103 | 18 | 22 | 86 | 45 | 36 | 5 | 0.375 |
| tool_call_count | 31103 | 22 | 25 | 86 | 50 | 33 | 3 | 1.125 |
| prompt_tokens | 30581 | 153152 | 219321 | 85 | 56 | 29 | 0 | 21618 |
| completion_tokens | 30581 | 6641.5 | 10549 | 85 | 42 | 43 | 0 | -29.5 |
| total_tokens | 30126 | 174065 | 247933 | 85 | 54 | 31 | 0 | 20272 |
| duration_seconds | 31103 | 296.228 | 533.2455 | 86 | 28 | 58 | 0 | -44.88725 |
| cost_usd_positive | 20401 | 0.204578625 | 0.16713255 | 83 | 71 | 12 | 0 | 0.086210475 |


### F. RQ1.2 regression coefficients, standard errors, samples and diagnostics

Source: `data/processed_live/diminishing_returns/rq1_final_statistical_results.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| metric | model_observation_count | model_task_strata_count | model_cluster_count | beta_1_log_effort_z | se_beta_1 | beta_1_p | beta_2_log_effort_z_squared | se_beta_2 | beta_2_p | quadratic_converged |
|---|---|---|---|---|---|---|---|---|---|---|
| step_count | 30392 | 87 | 74 | 0.180934709940819 | 0.139977048490564 | 0.196148507476932 | -0.425470084515505 | 0.142511229363703 | 0.0028309689111176 | True |
| shell_invocation_count | 30392 | 87 | 74 | -0.0923289779354722 | 0.147366998496033 | 0.530971226337109 | -0.292799649614695 | 0.183182481121198 | 0.109953047575811 | True |
| tool_call_count | 30392 | 87 | 74 | -0.0178427756167521 | 0.165577746501322 | 0.914185509771138 | -0.249856511875574 | 0.213751027886619 | 0.242438390046896 | True |
| total_tokens | 29441 | 87 | 72 | 0.207426118992223 | 0.145123820240136 | 0.152916753643157 | -0.341139582591246 | 0.132757231552119 | 0.0101801391870454 | True |
| duration_seconds | 30392 | 87 | 74 | -0.252261623427298 | 0.108679078586988 | 0.020278163770281 | -0.486003629074745 | 0.156792174116877 | 0.0019373790337419 | True |
| cost_usd_positive | 19705 | 86 | 48 | 0.851828368759191 | 0.337017236403037 | 0.0114861027919309 | -0.288740205067501 | 0.129178666404831 | 0.0254041961388122 | True |


### G. Fixed effort intervals: pooled versus balanced rates and supports

Source: `data/processed_live/terminal_bench_2_0/rq1_task_balanced_effort_success.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| metric | metric_display | bin_order | bin_label | effort_bin | bin_lower | bin_upper | trajectory_count | task_count | submission_task_bin_count | pass_count | pooled_pass_rate | task_balanced_pass_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| step_count | Step count | 1 | 0-10 | 0-10 | 0 | 10 | 8372 | 89 | 2588 | 2812 | 0.335881509794553 | 0.268010076689159 |
| step_count | Step count | 2 | 11-25 | 11-25 | 10 | 25 | 9301 | 89 | 3477 | 4129 | 0.443930760133319 | 0.388848123662533 |
| step_count | Step count | 3 | 26-50 | 26-50 | 25 | 50 | 6445 | 89 | 2861 | 2436 | 0.377967416602017 | 0.375550382423242 |
| step_count | Step count | 4 | 51-100 | 51-100 | 50 | 100 | 4327 | 89 | 2008 | 1386 | 0.320314305523457 | 0.347132539082693 |
| step_count | Step count | 5 | 101-200 | 101-200 | 100 | 200 | 1872 | 87 | 983 | 394 | 0.210470085470085 | 0.23886437716211 |
| step_count | Step count | 6 | >200 | >200 | 200 | inf | 786 | 86 | 402 | 62 | 0.0788804071246819 | 0.0873260306774688 |
| shell_invocation_count | Shell invocation count | 1 | 0 | 0 | -0.5 | 0.5 | 1161 | 89 | 431 | 336 | 0.289405684754522 | 0.266583488296971 |
| shell_invocation_count | Shell invocation count | 2 | 1-5 | 1-5 | 0.5 | 5 | 4160 | 89 | 1601 | 1076 | 0.258653846153846 | 0.194304777153103 |
| shell_invocation_count | Shell invocation count | 3 | 6-15 | 6-15 | 5 | 15 | 7647 | 89 | 3028 | 3489 | 0.456257355825814 | 0.346409993511749 |
| shell_invocation_count | Shell invocation count | 4 | 16-40 | 16-40 | 15 | 40 | 9688 | 89 | 3823 | 4131 | 0.426403798513625 | 0.396761509684568 |
| shell_invocation_count | Shell invocation count | 5 | >40 | >40 | 40 | inf | 8447 | 89 | 2850 | 2187 | 0.25890848822067 | 0.300781585477223 |
| tool_call_count | Structured tool call count | 1 | 0-5 | 0-5 | -0.5 | 5 | 4120 | 89 | 1498 | 891 | 0.21626213592233 | 0.184127430478537 |
| tool_call_count | Structured tool call count | 2 | 6-15 | 6-15 | 5 | 15 | 7197 | 89 | 2788 | 3120 | 0.43351396415173 | 0.304995696566442 |
| tool_call_count | Structured tool call count | 3 | 16-35 | 16-35 | 15 | 35 | 8872 | 89 | 3608 | 4028 | 0.454012623985573 | 0.396412171491687 |
| tool_call_count | Structured tool call count | 4 | 36-75 | 36-75 | 35 | 75 | 6681 | 89 | 2943 | 2343 | 0.350696003592277 | 0.36440346819444 |
| tool_call_count | Structured tool call count | 5 | 76-150 | 76-150 | 75 | 150 | 3110 | 85 | 1558 | 715 | 0.229903536977492 | 0.260166462265647 |
| tool_call_count | Structured tool call count | 6 | >150 | >150 | 150 | inf | 1123 | 75 | 606 | 122 | 0.108637577916296 | 0.100301573637538 |
| total_tokens | Total tokens | 1 | 0-10k | 0-10k | -0.5 | 10000 | 1321 | 88 | 601 | 198 | 0.149886449659349 | 0.119893451760228 |
| total_tokens | Total tokens | 2 | 10k-100k | 10k-100k | 10000 | 100000 | 9338 | 89 | 3059 | 3827 | 0.409830798886271 | 0.297123255770559 |
| total_tokens | Total tokens | 3 | 100k-500k | 100k-500k | 100000 | 500000 | 9618 | 89 | 3691 | 3852 | 0.400499064254523 | 0.366436362060986 |
| total_tokens | Total tokens | 4 | 500k-1M | 500k-1M | 500000 | 1000000 | 3658 | 89 | 2031 | 1263 | 0.345270639693822 | 0.359800003338357 |
| total_tokens | Total tokens | 5 | 1M-3M | 1M-3M | 1000000 | 3000000 | 3919 | 89 | 1931 | 1103 | 0.281449349323807 | 0.327707056422428 |
| total_tokens | Total tokens | 6 | 3M-10M | 3M-10M | 3000000 | 10000000 | 1779 | 82 | 942 | 333 | 0.187183811129848 | 0.193880729928748 |
| total_tokens | Total tokens | 7 | >10M | >10M | 10000000 | inf | 493 | 71 | 280 | 49 | 0.0993914807302231 | 0.0582916833647222 |
| duration_seconds | Duration seconds | 1 | 0-10s | 0-10s | -1e-06 | 10 | 0 | 0 | 0 | 0 | NA | NA |
| duration_seconds | Duration seconds | 2 | 10-60s | 10-60s | 10 | 60 | 528 | 62 | 257 | 145 | 0.274621212121212 | 0.133646807941163 |
| duration_seconds | Duration seconds | 3 | 1-5m | 1-5m | 60 | 300 | 11806 | 89 | 3662 | 5516 | 0.467220057597832 | 0.347234745873957 |
| duration_seconds | Duration seconds | 4 | 5-15m | 5-15m | 300 | 900 | 10209 | 89 | 4043 | 4080 | 0.399647369967676 | 0.392874846821939 |
| duration_seconds | Duration seconds | 5 | 15-30m | 15-30m | 900 | 1800 | 5590 | 88 | 2497 | 1189 | 0.212701252236136 | 0.238078845210901 |
| duration_seconds | Duration seconds | 6 | 30-60m | 30-60m | 1800 | 3600 | 2303 | 73 | 1105 | 267 | 0.115935735996526 | 0.076174205380331 |
| duration_seconds | Duration seconds | 7 | >60m | >60m | 3600 | inf | 667 | 41 | 308 | 22 | 0.032983508245877 | 0.0248997854561878 |
| cost_usd_positive | Positive cost USD | 1 | <=$0.001 | <=$0.001 | 0 | 0.001 | 75 | 33 | 45 | 6 | 0.08 | 0.053030303030303 |
| cost_usd_positive | Positive cost USD | 2 | $0.001-0.01 | $0.001-0.01 | 0.001 | 0.01 | 2131 | 89 | 719 | 345 | 0.161895823557015 | 0.115592596645967 |
| cost_usd_positive | Positive cost USD | 3 | $0.01-0.05 | $0.01-0.05 | 0.01 | 0.05 | 3548 | 89 | 1318 | 1056 | 0.297632468996618 | 0.230969763775731 |
| cost_usd_positive | Positive cost USD | 4 | $0.05-0.10 | $0.05-0.10 | 0.05 | 0.1 | 2122 | 89 | 1097 | 823 | 0.387841658812441 | 0.297082319661415 |
| cost_usd_positive | Positive cost USD | 5 | $0.10-0.50 | $0.10-0.50 | 0.1 | 0.5 | 6667 | 89 | 2226 | 2932 | 0.439778011099445 | 0.377882331343882 |
| cost_usd_positive | Positive cost USD | 6 | $0.50-1 | $0.50-1 | 0.5 | 1 | 2518 | 89 | 1230 | 900 | 0.357426528991263 | 0.384683516144429 |
| cost_usd_positive | Positive cost USD | 7 | >$1 | >$1 | 1 | inf | 3340 | 89 | 1147 | 912 | 0.273053892215569 | 0.361408360688393 |


### H. Equal-frequency pooled robustness

Source: `data/processed_live/diminishing_returns/rq1_effort_bin_robustness_summary.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| metric | metric_display | fixed_bin_count | quantile_bin_count | fixed_pattern | quantile_pattern | qualitative_result_changed | fixed_first_pass_rate | fixed_peak_pass_rate | fixed_last_pass_rate | quantile_first_pass_rate | quantile_peak_pass_rate | quantile_last_pass_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| step_count | Step count | 6 | 5 | increases_then_declines | increases_then_declines | False | 0.335881509794553 | 0.443930760133319 | 0.0788804071246819 | 0.303346638010439 | 0.456053325065881 | 0.253832499596579 |
| shell_invocation_count | Shell invocation count | 5 | 5 | increases_then_declines | increases_then_declines | False | 0.289405684754522 | 0.456257355825814 | 0.25890848822067 | 0.297602055381102 | 0.472324723247232 | 0.229609210312956 |
| tool_call_count | Structured tool call count | 6 | 5 | increases_then_declines | increases_then_declines | False | 0.21626213592233 | 0.454012623985573 | 0.108637577916296 | 0.265964139666562 | 0.471615720524017 | 0.230199242548987 |
| total_tokens | Total tokens | 7 | 5 | increases_then_declines | increases_then_declines | False | 0.149886449659349 | 0.409830798886271 | 0.0993914807302231 | 0.325423166279456 | 0.43850622406639 | 0.237344398340249 |
| duration_seconds | Duration seconds | 6 | 5 | increases_then_declines | increases_then_declines | False | 0.274621212121212 | 0.467220057597832 | 0.032983508245877 | 0.431924127953705 | 0.486173633440514 | 0.181160585114933 |
| cost_usd_positive | Positive cost USD | 7 | 5 | increases_then_declines | increases_then_declines | False | 0.08 | 0.439778011099445 | 0.273053892215569 | 0.215143347218819 | 0.461519607843137 | 0.284803921568627 |


### I. Exact equal-frequency boundaries and pooled rates

Source: `data/processed_live/diminishing_returns/rq1_effort_quantile_bins.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| metric | metric_display | scheme | bin_order | bin_label | bin_lower | bin_upper | n | pass_count | pass_rate |
|---|---|---|---|---|---|---|---|---|---|
| step_count | Step count | equal_frequency_quantile | 1 | (0.999, 8.0] | 0.999 | 8 | 6514 | 1976 | 0.303346638010439 |
| step_count | Step count | equal_frequency_quantile | 2 | (8.0, 16.0] | 8 | 16 | 6451 | 2942 | 0.456053325065881 |
| step_count | Step count | equal_frequency_quantile | 3 | (16.0, 28.0] | 16 | 28 | 5793 | 2466 | 0.425686172967374 |
| step_count | Step count | equal_frequency_quantile | 4 | (28.0, 55.0] | 28 | 55 | 6148 | 2262 | 0.367924528301887 |
| step_count | Step count | equal_frequency_quantile | 5 | (55.0, 3006.0] | 55 | 3006 | 6197 | 1573 | 0.253832499596579 |
| shell_invocation_count | Shell invocation count | equal_frequency_quantile | 1 | (-0.001, 7.0] | -0.001 | 7 | 7006 | 2085 | 0.297602055381102 |
| shell_invocation_count | Shell invocation count | equal_frequency_quantile | 2 | (7.0, 15.0] | 7 | 15 | 5962 | 2816 | 0.472324723247232 |
| shell_invocation_count | Shell invocation count | equal_frequency_quantile | 3 | (15.0, 27.0] | 15 | 27 | 5957 | 2661 | 0.446701359744838 |
| shell_invocation_count | Shell invocation count | equal_frequency_quantile | 4 | (27.0, 52.0] | 27 | 52 | 6011 | 2241 | 0.372816503077691 |
| shell_invocation_count | Shell invocation count | equal_frequency_quantile | 5 | (52.0, 1589.0] | 52 | 1589 | 6167 | 1416 | 0.229609210312956 |
| tool_call_count | Structured tool call count | equal_frequency_quantile | 1 | (-0.001, 8.0] | -0.001 | 8 | 6358 | 1691 | 0.265964139666562 |
| tool_call_count | Structured tool call count | equal_frequency_quantile | 2 | (8.0, 17.0] | 8 | 17 | 6183 | 2916 | 0.471615720524017 |
| tool_call_count | Structured tool call count | equal_frequency_quantile | 3 | (17.0, 31.0] | 17 | 31 | 6354 | 2869 | 0.451526597418949 |
| tool_call_count | Structured tool call count | equal_frequency_quantile | 4 | (31.0, 59.0] | 31 | 59 | 6135 | 2345 | 0.382233088834556 |
| tool_call_count | Structured tool call count | equal_frequency_quantile | 5 | (59.0, 1654.0] | 59 | 1654 | 6073 | 1398 | 0.230199242548987 |
| total_tokens | Total tokens | equal_frequency_quantile | 1 | (573.999, 41455.0] | 573.999 | 41455 | 6026 | 1961 | 0.325423166279456 |
| total_tokens | Total tokens | equal_frequency_quantile | 2 | (41455.0, 128631.0] | 41455 | 128631 | 6025 | 2642 | 0.43850622406639 |
| total_tokens | Total tokens | equal_frequency_quantile | 3 | (128631.0, 347757.0] | 128631 | 347757 | 6025 | 2424 | 0.402323651452282 |
| total_tokens | Total tokens | equal_frequency_quantile | 4 | (347757.0, 1033979.0] | 347757 | 1033979 | 6025 | 2168 | 0.359834024896265 |
| total_tokens | Total tokens | equal_frequency_quantile | 5 | (1033979.0, 244237325.0] | 1033979 | 244237325 | 6025 | 1430 | 0.237344398340249 |
| duration_seconds | Duration seconds | equal_frequency_quantile | 1 | (21.394, 165.688] | 21.394 | 165.688 | 6221 | 2687 | 0.431924127953705 |
| duration_seconds | Duration seconds | equal_frequency_quantile | 2 | (165.688, 302.916] | 165.688 | 302.916 | 6220 | 3024 | 0.486173633440514 |
| duration_seconds | Duration seconds | equal_frequency_quantile | 3 | (302.916, 561.869] | 302.916 | 561.869 | 6221 | 2711 | 0.435782028612763 |
| duration_seconds | Duration seconds | equal_frequency_quantile | 4 | (561.869, 983.27] | 561.869 | 983.27 | 6220 | 1670 | 0.268488745980707 |
| duration_seconds | Duration seconds | equal_frequency_quantile | 5 | (983.27, 29715.844] | 983.27 | 29715.844 | 6221 | 1127 | 0.181160585114933 |
| cost_usd_positive | Positive cost USD | equal_frequency_quantile | 1 | (-0.000653, 0.0257] | -0.000653 | 0.0257 | 4081 | 878 | 0.215143347218819 |
| cost_usd_positive | Positive cost USD | equal_frequency_quantile | 2 | (0.0257, 0.109] | 0.0257 | 0.109 | 4080 | 1470 | 0.360294117647059 |
| cost_usd_positive | Positive cost USD | equal_frequency_quantile | 3 | (0.109, 0.296] | 0.109 | 0.296 | 4080 | 1883 | 0.461519607843137 |
| cost_usd_positive | Positive cost USD | equal_frequency_quantile | 4 | (0.296, 0.8] | 0.296 | 0.8 | 4080 | 1581 | 0.3875 |
| cost_usd_positive | Positive cost USD | equal_frequency_quantile | 5 | (0.8, 83.798] | 0.8 | 83.798 | 4080 | 1162 | 0.284803921568627 |


### J. Complete current token Pareto frontier and manuscript comparisons

Source S5; 71 eligible configurations, 69 token-covered, 14 token-frontier rows. Rates below are percentages.

| scaffold | model_dir | task_count | submission_count | trajectory_count | total_tokens_task_count | task_balanced_pass_rate_pct | task_balanced_median_total_tokens |
|---|---|---|---|---|---|---|---|
| terminus-kira-env-bootstrap | claude-opus-4-6 | 89 | 1 | 444 | 89 | 76.5168539325843 | 768635 |
| terminus-3-3 | gemini-3.1-pro-preview | 89 | 1 | 431 | 89 | 74.438202247191 | 304505 |
| terminus-2 | claude-opus-4-6 | 89 | 1 | 445 | 89 | 62.9213483146067 | 81896 |
| terminus-2 | gemini-3-pro-preview | 89 | 1 | 445 | 89 | 56.8539325842697 | 80897 |
| terminus-2 | gpt-5.2 | 89 | 1 | 443 | 89 | 53.876404494382 | 75956 |
| terminus-2 | gpt-5.1 | 89 | 1 | 445 | 89 | 47.5842696629214 | 68847 |
| terminus-2 | minimax-m2.5 | 88 | 1 | 411 | 88 | 42.5189393939394 | 56718.5 |
| terminus-2 | gpt-5 | 89 | 1 | 436 | 89 | 35 | 55827 |
| mini-swe-agent | gpt-5 | 89 | 1 | 432 | 89 | 34.9250936329588 | 54030 |
| terminus-2 | gpt-5-mini | 89 | 1 | 437 | 89 | 24.1011235955056 | 51909 |
| terminus-2 | grok-4-0709 | 89 | 1 | 436 | 89 | 23.1460674157303 | 27549.5 |
| terminus-2 | openai_gpt-oss-120b | 89 | 1 | 462 | 89 | 18.689138576779 | 26458 |
| mini-swe-agent | openai_gpt-oss-120b | 89 | 1 | 442 | 89 | 14.2696629213483 | 23221.5 |
| mini-swe-agent | openai_gpt-oss-20b | 89 | 1 | 443 | 89 | 3.37078651685393 | 15701 |

Additional quoted off-frontier configurations:

| scaffold | model_dir | task_count | submission_count | trajectory_count | total_tokens_task_count | task_balanced_pass_rate_pct | task_balanced_median_total_tokens |
|---|---|---|---|---|---|---|---|
| nexau | gpt-5.5 | 89 | 1 | 443 | NA | 84.7191011235955 | NA |
| gemini-cli | gemini-3.1-pro-preview | 89 | 2 | 434 | 89 | 60.8614232209738 | 575371.75 |
| claude-code | claude-opus-4-6 | 87 | 1 | 435 | 87 | 59.3103448275862 | 811188 |
| codex | gpt-5 | 88 | 1 | 409 | 88 | 51.780303030303 | 155115 |
| openhands | gpt-5 | 89 | 1 | 436 | 89 | 44.7752808988764 | 215506 |


### K. RQ2.1 current URL-balanced difficulty rates

Source: `data/processed_live/task_mining/difficulty/task_difficulty_outcome.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| difficulty | n_tasks | n_trajectories | n_submission_task_combinations | pass_count | fail_count | pass_rate | task_mean_pass_rate | trajectory_pooled_pass_rate | trajectory_pooled_task_mean_pass_rate |
|---|---|---|---|---|---|---|---|---|---|
| easy | 4 | 1419 | 219 | 1007 | 412 | 0.739152634700029 | 0.739152634700029 | 0.709654686398872 | 0.705294646334892 |
| medium | 55 | 19293 | 3006 | 8204 | 11089 | 0.464701063511044 | 0.464701063511044 | 0.425231949411704 | 0.424111931392058 |
| hard | 30 | 10391 | 1641 | 2008 | 8383 | 0.221117648374696 | 0.221117648374696 | 0.193244153594457 | 0.191121706131578 |


### L. RQ2.1 current URL-balanced category rates

Source: `data/processed_live/task_mining/category/task_domain_outcome.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| category | n_tasks | n_trajectories | n_submission_task_combinations | pass_count | fail_count | pass_rate | task_mean_pass_rate | trajectory_pooled_pass_rate | trajectory_pooled_task_mean_pass_rate |
|---|---|---|---|---|---|---|---|---|---|
| personal-assistant | 1 | 364 | 55 | 319 | 45 | 0.898656126482213 | 0.898656126482213 | 0.876373626373626 | 0.876373626373626 |
| data-querying | 1 | 357 | 55 | 108 | 249 | 0.362878787878788 | 0.362878787878788 | 0.302521008403361 | 0.302521008403361 |
| optimization | 1 | 357 | 55 | 283 | 74 | 0.836623376623377 | 0.836623376623377 | 0.792717086834734 | 0.792717086834734 |
| games | 1 | 356 | 55 | 34 | 322 | 0.134848484848485 | 0.134848484848485 | 0.095505617977528 | 0.095505617977528 |
| video-processing | 1 | 350 | 55 | 8 | 342 | 0.029090909090909 | 0.029090909090909 | 0.0228571428571428 | 0.0228571428571428 |
| machine-learning | 3 | 1071 | 164 | 335 | 736 | 0.348811263862943 | 0.348811263862943 | 0.312791783380019 | 0.310829218367519 |
| mathematics | 4 | 1430 | 220 | 335 | 1095 | 0.285876623376623 | 0.285876623376623 | 0.234265734265734 | 0.234045734893275 |
| data-processing | 4 | 1421 | 219 | 818 | 603 | 0.611149791566458 | 0.611149791566458 | 0.575650950035187 | 0.576054796428344 |
| model-training | 4 | 1332 | 211 | 428 | 904 | 0.370980836501317 | 0.370980836501317 | 0.321321321321321 | 0.328426482813486 |
| debugging | 5 | 1762 | 274 | 756 | 1006 | 0.48777262065317 | 0.48777262065317 | 0.42905788876277 | 0.427162909342621 |
| file-operations | 5 | 1758 | 272 | 362 | 1396 | 0.236581972285445 | 0.236581972285445 | 0.205915813424346 | 0.205154680479914 |
| security | 8 | 2828 | 439 | 1116 | 1712 | 0.442923887980706 | 0.442923887980706 | 0.394625176803395 | 0.394394256991734 |
| scientific-computing | 8 | 2802 | 438 | 813 | 1989 | 0.3166686210815 | 0.3166686210815 | 0.290149892933619 | 0.28734322620683 |
| data-science | 8 | 2765 | 437 | 811 | 1954 | 0.335500968574868 | 0.335500968574868 | 0.293309222423146 | 0.294401101801807 |
| system-administration | 9 | 3132 | 494 | 1422 | 1710 | 0.47625674660889 | 0.47625674660889 | 0.454022988505747 | 0.452135561440225 |
| software-engineering | 26 | 9018 | 1423 | 3271 | 5747 | 0.388434865214943 | 0.388434865214943 | 0.362719006431581 | 0.35632688921858 |


### M. RQ2.1 difficulty resource medians and support

Source: `data/processed_live/task_mining/difficulty/task_difficulty_effort_summary.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| difficulty | variable | n_trajectories | n_tasks | n_submission_task_combinations | median | trajectory_level_median |
|---|---|---|---|---|---|---|
| easy | cost_usd_positive | 1419 | 4 | 151 | 0.18828898125 | 0.105035 |
| medium | cost_usd_positive | 19293 | 55 | 2083 | 0.198100625 | 0.15580125 |
| hard | cost_usd_positive | 10391 | 30 | 1132 | 0.3695658125 | 0.2862162 |
| easy | duration_seconds | 1419 | 4 | 219 | 253.296 | 234.525 |
| medium | duration_seconds | 19293 | 55 | 3006 | 356.92 | 350.362 |
| hard | duration_seconds | 10391 | 30 | 1641 | 688.95625 | 613.183 |
| easy | shell_invocation_count | 1419 | 4 | 219 | 23.5 | 19 |
| medium | shell_invocation_count | 19293 | 55 | 3006 | 18 | 19 |
| hard | shell_invocation_count | 10391 | 30 | 1641 | 23.5 | 23 |
| easy | step_count | 1419 | 4 | 219 | 19 | 17 |
| medium | step_count | 19293 | 55 | 3006 | 19 | 20 |
| hard | step_count | 10391 | 30 | 1641 | 26 | 25 |
| easy | tool_call_count | 1419 | 4 | 219 | 27.25 | 21 |
| medium | tool_call_count | 19293 | 55 | 3006 | 21 | 22 |
| hard | tool_call_count | 10391 | 30 | 1641 | 30 | 27 |
| easy | total_tokens | 1419 | 4 | 215 | 151973.25 | 117730 |
| medium | total_tokens | 19293 | 55 | 2950 | 191015 | 174042.5 |
| hard | total_tokens | 10391 | 30 | 1609 | 407300.5 | 336171 |


### N. Quoted category resource medians

Source S6 `category/task_domain_effort_summary.csv`, column `median` (nested URL medians); `n_trajectories` is the category total, not metric-complete count. Zero token reports retained; cost positive only.

| category | variable | n_tasks | n_submission_task_combinations | median |
|---|---|---|---|---|
| mathematics | cost_usd_positive | 4 | 152 | 0.478124159375 |
| scientific-computing | cost_usd_positive | 8 | 302 | 0.42331265625 |
| machine-learning | cost_usd_positive | 3 | 113 | 0.2881399125 |
| model-training | cost_usd_positive | 4 | 151 | 0.24895896875 |
| data-processing | cost_usd_positive | 4 | 151 | 0.11765035625 |
| personal-assistant | cost_usd_positive | 1 | 38 | 0.1133407625 |
| mathematics | duration_seconds | 4 | 220 | 693.5125 |
| machine-learning | duration_seconds | 3 | 164 | 587.6485 |
| model-training | duration_seconds | 4 | 211 | 566.99675 |
| scientific-computing | duration_seconds | 8 | 438 | 523.79025 |
| data-processing | duration_seconds | 4 | 219 | 188.572 |
| personal-assistant | duration_seconds | 1 | 55 | 174.177 |
| machine-learning | shell_invocation_count | 3 | 164 | 27 |
| scientific-computing | shell_invocation_count | 8 | 438 | 20.875 |
| mathematics | shell_invocation_count | 4 | 220 | 20.5 |
| model-training | shell_invocation_count | 4 | 211 | 17.25 |
| data-processing | shell_invocation_count | 4 | 219 | 8.5 |
| personal-assistant | shell_invocation_count | 1 | 55 | 6 |
| machine-learning | step_count | 3 | 164 | 27 |
| mathematics | step_count | 4 | 220 | 26 |
| scientific-computing | step_count | 8 | 438 | 22.5 |
| model-training | step_count | 4 | 211 | 20.25 |
| data-processing | step_count | 4 | 219 | 10.5 |
| personal-assistant | step_count | 1 | 55 | 9.5 |
| machine-learning | tool_call_count | 3 | 164 | 36 |
| mathematics | tool_call_count | 4 | 220 | 25 |
| scientific-computing | tool_call_count | 8 | 438 | 23.625 |
| model-training | tool_call_count | 4 | 211 | 22.5 |
| data-processing | tool_call_count | 4 | 219 | 11 |
| personal-assistant | tool_call_count | 1 | 55 | 8 |
| mathematics | total_tokens | 4 | 216 | 409170 |
| scientific-computing | total_tokens | 8 | 429 | 352183.5 |
| machine-learning | total_tokens | 3 | 161 | 327565.75 |
| model-training | total_tokens | 4 | 207 | 242400.5 |
| data-processing | total_tokens | 4 | 215 | 69257.25 |
| personal-assistant | total_tokens | 1 | 54 | 61593.25 |


### O. Metric-complete trajectory counts behind quoted RQ2 resource groups

Read-only counts from S0 TB2 joined to retained task metadata; do not substitute `n_trajectories` from a saved group table for metric availability.

| Grouping | Group | All trajectories | Nonmissing tokens | Duration available | Positive cost |
|---|---|---|---|---|---|
| difficulty | easy | 1419 | 1397 | 1419 | 929 |
| difficulty | hard | 10391 | 10196 | 10391 | 6797 |
| difficulty | medium | 19293 | 18988 | 19293 | 12675 |
| category | data-processing | 1421 | 1399 | 1421 | 924 |
| category | machine-learning | 1071 | 1052 | 1071 | 711 |
| category | mathematics | 1430 | 1409 | 1430 | 933 |
| category | model-training | 1332 | 1313 | 1332 | 903 |
| category | personal-assistant | 364 | 359 | 364 | 235 |
| category | scientific-computing | 2802 | 2752 | 2802 | 1846 |


### P. RQ2.2 exploratory media comparison

Source: `data/processed_live/task_mining/rq2_2_media_exploratory.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| analysis_status | media_task_count | other_task_count | media_mean_task_pass_rate | other_mean_task_pass_rate | percentage_point_difference |
|---|---|---|---|---|---|
| post-hoc exploratory | 7 | 82 | 0.160368293929938 | 0.3838835945679 | -22.3515300637962 |


### Q. RQ2.2 human-time inference and success-only descriptions

Source: `data/processed_live/task_mining/rq2_2_time_significance.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| comparison | n_tasks | median_agent_duration_min | median_human_estimate_min | median_difference_min | cohens_dz | wilcoxon_statistic | p_value | nonzero_task_pairs | success_only_eligible_tasks | success_only_median_agent_duration_min | success_only_median_human_estimate_min | success_only_median_difference_min | success_only_median_agent_to_human_ratio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| expert | 88 | 7.02420833333333 | 60 | -46.9086 | -0.509414281456379 | 46 | 1.78328861568782e-15 | 88 | 86 | 7.2065875 | 60 | -46.592925 | 0.120696041666667 |
| junior | 88 | 7.02420833333333 | 240 | -235.344333333333 | -0.403009342834737 | 1 | 3.86257572623649e-16 | 88 | 86 | 7.2065875 | 240 | -235.598454166667 | 0.0223384259259259 |


### R. RQ2.3 exact nine-family estimates

Source: `data/processed_live/task_mining/tools/rq2_3_functional_behavior_inference.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| behavior | behavior_family | use_rate | eligible_tasks | mean_pass_rate_difference_pp | median_pass_rate_difference_pp | cohens_dz | wilcoxon_statistic | p_value | nonzero_task_pairs |
|---|---|---|---|---|---|---|---|---|---|
| Inspect/search | inspect_search | 0.884159084332701 | 89 | 9.45880518529176 | 7.41959064327485 | 0.778820841034282 | 434 | 3.75378279020056e-10 | 87 |
| Modify/write | modify_write | 0.77269073722792 | 89 | 5.69940287851562 | 3.9047619047619 | 0.509762368150349 | 856 | 7.53903690429346e-06 | 87 |
| Execute/run | execute_run | 0.61080924669646 | 89 | 7.68400808353825 | 5.63344701275735 | 0.520018018023822 | 762 | 1.08416266526348e-06 | 87 |
| Test/validate | test_validate | 0.119731215638363 | 82 | 7.5644015821082 | 6.66607221853572 | 0.487193226297958 | 730 | 1.9661936820094e-05 | 80 |
| Environment/dependencies | environment_dependencies | 0.373050831109539 | 80 | 2.34531755902264 | 2.18924377802882 | 0.120179250165995 | 1273 | 0.182744793221064 | 78 |
| Version control | version_control | 0.106484904993087 | 50 | -2.32280336447623 | -1.94044013527945 | -0.121237497910023 | 543 | 0.489353799814439 | 49 |
| Data query/transform | data_query_transform | 0.0403176542455711 | 13 | -3.74685000035107 | -2.9585798816568 | -0.182873001217972 | 38 | 0.635498046875 | 13 |
| Network/external | network_external | 0.101437160402534 | 48 | -2.40466146612518 | -3.00596116459373 | -0.100335294875725 | 450 | 0.227676364065947 | 47 |
| Media/specialized | media_specialized | 0.022280808925184 | 12 | 2.00270621895448 | 5.42634535091789 | 0.0983193069017182 | 32 | 0.6220703125 | 12 |


### S. Full-version pass rates

Source: `data/processed_live/longitudinal/rq3_1_version_performance_summary.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| benchmark_version | benchmark | trajectory_count | task_count | submission_count | scaffold_count | model_count | pooled_pass_rate | task_weighted_pass_rate | median_submission_pass_rate | mean_submission_pass_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| 2 | terminal_bench_2_0 | 31103 | 89 | 74 | 12 | 33 | 0.360704755168312 | 0.366303739461543 | 0.349625468164794 | 0.367850575011075 |
| 2.1 | terminal_bench_2_1 | 7501 | 89 | 17 | 6 | 12 | 0.751233168910812 | 0.750782110597048 | 0.761797752808989 | 0.750782110597048 |
| 3 | terminal_bench_3_0 | 4279 | 74 | 13 | 6 | 12 | 0.226454779154008 | 0.232845139095139 | 0.197260273972603 | 0.224720783025577 |
| 4 | terminal_bench_4_0 | 5902 | 66 | 18 | 4 | 14 | 0.361911216536767 | 0.361898395721925 | 0.398671328671329 | 0.361847319347319 |


### T. Paired shared-task pass-rate inference

Source: `data/processed_live/longitudinal/rq3_1_version_performance_inference.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| transition | shared_tasks | old_task_balanced_pass_rate | new_task_balanced_pass_rate | overall_change_pp | mean_task_change_pp | median_task_change_pp | cohens_dz | wilcoxon_statistic | p_value | nonzero_task_pairs |
|---|---|---|---|---|---|---|---|---|---|---|
| 2.0->2.1 | 89 | 0.366303739461543 | 0.750782110597048 | 38.4478371135505 | 38.4478371135505 | 36.7925278219396 | 1.80319632454581 | 1 | 2.63918889149538e-16 | 89 |
| 3.0->4.0 | 66 | 0.216088772338772 | 0.361898395721925 | 14.5809623383153 | 14.5809623383153 | 13.8034188034188 | 0.924091442153001 | 164 | 1.2224394185128e-08 | 62 |


### U. Instruction-group inference

Source: `data/processed_live/longitudinal/rq3_1_instruction_change_inference.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| transition | n_changed | n_unchanged | mean_improvement_changed_pp | mean_improvement_unchanged_pp | median_improvement_changed_pp | median_improvement_unchanged_pp | raw_difference_in_mean_improvement_pp | cliffs_delta | mann_whitney_u | p_value |
|---|---|---|---|---|---|---|---|---|---|---|
| 2.0->2.1 | 22 | 67 | 41.6956311486932 | 37.3813972811156 | 40.1344727080021 | 36.0427807486631 | 4.31423386757764 | 0.104477611940299 | 814 | 0.466869384158737 |
| 3.0->4.0 | 11 | 55 | 20.1233488733489 | 13.4724850313086 | 18.034188034188 | 12.7777777777778 | 6.65086384204031 | 0.208264462809917 | 365.5 | 0.282141395128863 |


### V. URL-grouped pass-rate sensitivity (not primary)

Source: `data/processed_live/longitudinal/rq3_1_version_performance_url_sensitivity.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| transition | shared_tasks | old_task_balanced_pass_rate | new_task_balanced_pass_rate | overall_change_pp | mean_task_change_pp | median_task_change_pp | cohens_dz | wilcoxon_statistic | p_value | nonzero_task_pairs |
|---|---|---|---|---|---|---|---|---|---|---|
| 2.0->2.1 | 89 | 0.39492919643987 | 0.750782110597048 | 35.5852914157178 | 35.5852914157178 | 33.6921846962887 | 1.70982480596861 | 0 | 2.55097295166325e-16 | 89 |
| 3.0->4.0 | 66 | 0.218470691766146 | 0.361898395721925 | 14.3427703955779 | 14.3427703955779 | 14.375 | 0.907871837011222 | 173.5 | 1.80142071234701e-08 | 62 |


### W. Difficulty-label validation: fixed panel

Source: `data/processed_live/longitudinal/tb2_difficulty_prompt_validation_summary.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| labeler | n_tasks | n_correct | accuracy | n_unanimous | n_majority | n_tie | n_easy | n_easy_correct | accuracy_easy | n_medium | n_medium_correct | accuracy_medium | n_hard | n_hard_correct | accuracy_hard |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| consensus | 22 | 14 | 0.636363636363636 | 11 | 11 | 0 | 2 | 0 | 0 | 10 | 7 | 0.7 | 10 | 7 | 0.7 |
| openai:gpt-4o-mini | 22 | 14 | 0.636363636363636 | NA | NA | NA | 2 | 0 | 0 | 10 | 7 | 0.7 | 10 | 7 | 0.7 |
| anthropic:claude-haiku-4-5-20251001 | 22 | 12 | 0.545454545454545 | NA | NA | NA | 2 | 1 | 0.5 | 10 | 3 | 0.3 | 10 | 8 | 0.8 |
| ollama:qwen2.5:7b-instruct | 22 | 15 | 0.681818181818182 | NA | NA | NA | 2 | 0 | 0 | 10 | 10 | 1 | 10 | 5 | 0.5 |


### X. Alternative historical Sonnet cache (protocol not established equivalent)

Source: `data/processed_live/longitudinal/tb2_difficulty_prompt_validation_sonnet5_summary.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| labeler | n_tasks | n_correct | accuracy | n_unanimous | n_majority | n_tie | n_easy | n_easy_correct | accuracy_easy | n_medium | n_medium_correct | accuracy_medium | n_hard | n_hard_correct | accuracy_hard |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| consensus | 22 | 17 | 0.772727272727273 | 14 | 7 | 1 | 2 | 0 | 0 | 10 | 9 | 0.9 | 10 | 8 | 0.8 |


### Y. Current difficulty-stratified version rates

Source: `data/processed_live/longitudinal/difficulty_over_versions/pass_rate_by_difficulty_over_versions.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| benchmark_version | task_weighting | submission_unit | version_label | difficulty_label | difficulty_order | n_tasks | n_trials | task_weighted_pass_rate | task_median_pass_rate | task_pass_rate_p25 | task_pass_rate_p75 | pooled_task_mean_pass_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | submission-balanced | effective | TB2.0 | easy | 0 | 4 | 1419 | 0.713000586202641 | 0.828603603603604 | 0.674881216833272 | 0.866722972972973 | 0.705294646334892 |
| 2 | submission-balanced | effective | TB2.0 | medium | 1 | 55 | 19293 | 0.43234341000686 | 0.42027027027027 | 0.251238738738739 | 0.630405405405405 | 0.424111931392058 |
| 2 | submission-balanced | effective | TB2.0 | hard | 2 | 30 | 10391 | 0.199004763896316 | 0.133108108108108 | 0.0533627377377377 | 0.320028076021227 | 0.191121706131578 |
| 2.1 | submission-balanced | effective | TB2.1 | easy | 0 | 4 | 337 | 0.926470588235294 | 0.976470588235294 | 0.902941176470588 | 1 | 0.924982282069454 |
| 2.1 | submission-balanced | effective | TB2.1 | medium | 1 | 55 | 4639 | 0.79554367201426 | 0.882352941176471 | 0.71764705882353 | 0.964705882352941 | 0.795616920344928 |
| 2.1 | submission-balanced | effective | TB2.1 | hard | 2 | 30 | 2525 | 0.645294117647059 | 0.691176470588235 | 0.422058823529412 | 0.908823529411765 | 0.645836785384042 |
| 3 | submission-balanced | effective | TB3.0 | medium | 1 | 2 | 107 | 0.548611111111111 | 0.548611111111111 | 0.489583333333333 | 0.607638888888889 | 0.497175141242938 |
| 3 | submission-balanced | effective | TB3.0 | hard | 2 | 72 | 4172 | 0.224073862094695 | 0.154166666666667 | 0.0471153846153846 | 0.339423076923077 | 0.227748706653574 |
| 4 | submission-balanced | effective | TB4.0 | medium | 1 | 1 | 84 | 0.485294117647059 | 0.485294117647059 | 0.485294117647059 | 0.485294117647059 | 0.488095238095238 |
| 4 | submission-balanced | effective | TB4.0 | hard | 2 | 65 | 5818 | 0.36 | 0.366666666666667 | 0.144444444444444 | 0.533333333333333 | 0.360116771420665 |


### Z. Stored broad-category composition

Source S13 `category_composition_by_version.csv`; it contains native-category subrows, so sum `n_tasks` and `task_share` within version/unified category. TB2 historical mapping has the R30 voting limitations.

| benchmark_version | unified_category | tasks | share |
|---|---|---|---|
| 2 | Hardware | 1 | 0.0112359550561797 |
| 2 | ML | 26 | 0.292134831460674 |
| 2 | Media | 4 | 0.0449438202247189 |
| 2 | Operations | 14 | 0.157303370786517 |
| 2 | Science | 8 | 0.0898876404494381 |
| 2 | Security | 11 | 0.123595505617977 |
| 2 | Software | 25 | 0.280898876404494 |
| 2.1 | Hardware | 1 | 0.0112359550561797 |
| 2.1 | ML | 26 | 0.292134831460674 |
| 2.1 | Media | 4 | 0.0449438202247189 |
| 2.1 | Operations | 14 | 0.157303370786517 |
| 2.1 | Science | 8 | 0.0898876404494381 |
| 2.1 | Security | 11 | 0.123595505617977 |
| 2.1 | Software | 25 | 0.280898876404494 |
| 3 | Hardware | 5 | 0.0675675675675675 |
| 3 | ML | 13 | 0.175675675675676 |
| 3 | Media | 4 | 0.054054054054054 |
| 3 | Operations | 10 | 0.135135135135135 |
| 3 | Science | 15 | 0.202702702702703 |
| 3 | Security | 7 | 0.0945945945945946 |
| 3 | Software | 20 | 0.27027027027027 |
| 4 | Hardware | 5 | 0.0757575757575757 |
| 4 | ML | 11 | 0.166666666666667 |
| 4 | Media | 4 | 0.0606060606060606 |
| 4 | Operations | 9 | 0.136363636363636 |
| 4 | Science | 14 | 0.212121212121212 |
| 4 | Security | 5 | 0.0757575757575757 |
| 4 | Software | 18 | 0.272727272727273 |


### AA. Task composition: expert/junior/timeouts/observed duration

Source: `data/processed_live/longitudinal/task_composition/version_task_composition_summary.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| benchmark_version | n_tasks | n_tasks_with_expert_estimate | n_tasks_with_junior_estimate | expert_estimate_min_mean | expert_estimate_min_median | junior_estimate_min_mean | junior_estimate_min_median | agent_timeout_min_median | observed_task_median_duration_min_n | observed_task_median_duration_min_median |
|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 89 | 88 | 88 | 206.704545454545 | 60 | 1425.39772727273 | 240 | 15 | 89 | 7.23053333333333 |
| 2.1 | 89 | 88 | 88 | 206.704545454545 | 60 | 1425.39772727273 | 240 | 15 | 89 | 6.29292003333333 |
| 3 | 74 | 74 | 0 | 417.405405405405 | 240 | NA | NA | 120 | 74 | 32.8711446041667 |
| 4 | 66 | 66 | 0 | 392.545454545455 | 240 | NA | NA | 135 | 66 | 24.617850425 |


### AB. TB2 pooled medians: positive tokens, complete text

Source: `data/processed_live/longitudinal/pooled_effort_summary_refreshed.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| key | column | early_value | late_value | early_valid_n | late_valid_n | relative_change_pct |
|---|---|---|---|---|---|---|
| steps | step_count | 21 | 18 | 31103 | 7501 | -14.2857142857143 |
| shell_invocations | shell_invocation_count | 20 | 15 | 31103 | 7501 | -25 |
| tool_calls | tool_call_count | 23 | 19 | 31103 | 7501 | -17.3913043478261 |
| duration | duration_seconds | 408.901 | 376.938479 | 31103 | 7501 | -7.81668936979857 |
| chars | logged_chars | 36828 | 46348 | 31103 | 7501 | 25.8498968176388 |
| prompt_tokens | prompt_tokens | 197388.5 | 266079 | 30126 | 7434 | 34.7996463826413 |
| completion_tokens | completion_tokens | 9012 | 13639.5 | 30126 | 7434 | 51.3482023968043 |
| total_tokens | total_tokens | 213974.5 | 282852 | 30126 | 7434 | 32.1895833382015 |


### AC. TB3/TB4 pooled medians: positive tokens, complete text

Source: `data/processed_live/longitudinal/tb3_tb4/pooled_effort_summary_refreshed.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| key | column | early_value | late_value | early_valid_n | late_valid_n | relative_change_pct |
|---|---|---|---|---|---|---|
| steps | step_count | 71 | 60 | 4337 | 5902 | -15.4929577464789 |
| shell_invocations | shell_invocation_count | 55 | 47 | 4337 | 5902 | -14.5454545454546 |
| tool_calls | tool_call_count | 75 | 63 | 4337 | 5902 | -16 |
| duration | duration_seconds | 1973.356668 | 1640.8997155 | 4337 | 5902 | -16.84728148191 |
| chars | logged_chars | 379444 | 305219.5 | 4337 | 5902 | -19.5613845521342 |
| prompt_tokens | prompt_tokens | 7912209 | 5209042.5 | 3921 | 5902 | -34.1644981824924 |
| completion_tokens | completion_tokens | 97567 | 84850 | 3921 | 5902 | -13.0341201430812 |
| total_tokens | total_tokens | 8064089 | 5299037 | 3921 | 5902 | -34.2884608540407 |


### AD. TB2 balanced descriptive medians and paired relative changes

Source: `data/processed_live/longitudinal/effort_figure_data_submission_balanced_effective.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| key | early_value | late_value | early_valid_n | late_valid_n | relative_change_pct | median_paired_change | median_paired_relative_change_pct |
|---|---|---|---|---|---|---|---|
| steps | 21 | 18 | 89 | 89 | -14.2857142857143 | -3.5 | -20 |
| shell_invocations | 20.5 | 16 | 89 | 89 | -21.9512195121951 | -4.5 | -25 |
| tool_calls | 23.75 | 19 | 89 | 89 | -20 | -5 | -21.9512195121951 |
| duration | 433.832 | 377.575202 | 89 | 89 | -12.9674154972432 | -57.802842 | -18.0924034798912 |
| chars | 39201.75 | 45775.5 | 89 | 89 | 16.769021791119 | 6746.5 | 15.9680500886219 |
| prompt_tokens | 220729.5 | 271920 | 89 | 89 | 23.1915081581755 | 59287 | 39.803558033882 |
| completion_tokens | 10147 | 13998 | 89 | 89 | 37.9521040701685 | 3120 | 29.5782541684181 |
| total_tokens | 242208 | 299868 | 89 | 89 | 23.8059849385652 | 60340 | 35.9714484205364 |


### AE. TB3/TB4 balanced descriptive medians and paired relative changes

Source: `data/processed_live/longitudinal/tb3_tb4/effort_figure_data_submission_balanced_effective.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| key | early_value | late_value | early_valid_n | late_valid_n | relative_change_pct | median_paired_change | median_paired_relative_change_pct |
|---|---|---|---|---|---|---|---|
| steps | 76.5 | 59.75 | 66 | 66 | -21.8954248366013 | -10.25 | -15.3010033444816 |
| shell_invocations | 57.25 | 49.25 | 66 | 66 | -13.9737991266376 | -4.75 | -11.7151767151767 |
| tool_calls | 78.5 | 63 | 66 | 66 | -19.7452229299363 | -10.25 | -17.3076923076923 |
| duration | 1996.628311 | 1477.0710255 | 66 | 66 | -26.0217328702398 | -414.03829225 | -21.5934216593125 |
| chars | 347138.75 | 296564 | 66 | 66 | -14.5690303949069 | -89000.5 | -25.9769017000113 |
| prompt_tokens | 8327654 | 5181714 | 66 | 66 | -37.7770257986223 | -1902173 | -29.0461232979309 |
| completion_tokens | 95933.75 | 86497.5 | 66 | 66 | -9.83621509635556 | -5903.375 | -9.05599924101725 |
| total_tokens | 8536325 | 5268329.75 | 66 | 66 | -38.2833977150589 | -1925222.5 | -27.9708902021548 |


### AF. All ten current RQ3.3 inference rows

Source: `data/processed_live/longitudinal/rq3_3_effort_inference.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| transition | metric | eligible_tasks | old_task_balanced_median | new_task_balanced_median | task_balanced_median_change_pct | mean_paired_task_difference | median_paired_task_difference | cohens_dz | wilcoxon_statistic | p_value | nonzero_task_pairs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2.0->2.1 | steps | 89 | 21 | 18 | -14.2857142857143 | -3.30898876404494 | -3.5 | -0.312894294590428 | 1129 | 0.0008894960251363 | 87 |
| 2.0->2.1 | shell_invocations | 89 | 20.5 | 16 | -21.9512195121951 | -5.7752808988764 | -4.5 | -0.523732786307623 | 766.5 | 1.17878798894363e-06 | 87 |
| 2.0->2.1 | tool_calls | 89 | 23.75 | 19 | -20 | -5.1938202247191 | -5 | -0.416884082869444 | 929 | 3.05129357974193e-05 | 87 |
| 2.0->2.1 | duration | 89 | 433.832 | 377.575202 | -12.9674154972432 | -38.9554535393259 | -57.802842 | -0.138539991859674 | 1312 | 0.0047272862787149 | 89 |
| 2.0->2.1 | total_tokens | 89 | 242208 | 299868 | 23.8059849385652 | 203421.168539326 | 60340 | 0.296637884270165 | 1080 | 0.0001604978226435 | 89 |
| 3.0->4.0 | steps | 66 | 76.5 | 59.75 | -21.8954248366013 | -9.90530303030303 | -10.25 | -0.360437750179541 | 416.5 | 1.07399284511201e-05 | 66 |
| 3.0->4.0 | shell_invocations | 66 | 57.25 | 49.25 | -13.9737991266376 | -2.89772727272727 | -4.75 | -0.133782953046193 | 658 | 0.0067471947016407 | 65 |
| 3.0->4.0 | tool_calls | 66 | 78.5 | 63 | -19.7452229299363 | -9.9280303030303 | -10.25 | -0.398661323780061 | 418.5 | 1.91774224839954e-05 | 65 |
| 3.0->4.0 | duration | 66 | 1996.628311 | 1477.0710255 | -26.0217328702398 | -510.615397943182 | -414.03829225 | -0.499867409459178 | 247 | 4.15420432053502e-08 | 66 |
| 3.0->4.0 | total_tokens | 66 | 8536325 | 5268329.75 | -38.2833977150589 | -2222156.62121212 | -1925222.5 | -0.510942476520215 | 374 | 2.97003238263667e-06 | 66 |


### AG. Current effective versus URL inference sensitivity

Source: `data/processed_live/longitudinal/rq3_3_submission_unit_sensitivity_inference.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| transition | metric | task_weighting | submission_unit | eligible_tasks | mean_paired_task_difference | median_paired_task_difference | cohens_dz | wilcoxon_statistic | p_value | nonzero_task_pairs |
|---|---|---|---|---|---|---|---|---|---|---|
| 2.0->2.1 | steps | submission-balanced | effective | 89 | -3.30898876404494 | -3.5 | -0.312894294590428 | 1129 | 0.0008894960251363 | 87 |
| 2.0->2.1 | shell_invocations | submission-balanced | effective | 89 | -5.7752808988764 | -4.5 | -0.523732786307623 | 766.5 | 1.17878798894363e-06 | 87 |
| 2.0->2.1 | tool_calls | submission-balanced | effective | 89 | -5.1938202247191 | -5 | -0.416884082869444 | 929 | 3.05129357974193e-05 | 87 |
| 2.0->2.1 | duration | submission-balanced | effective | 89 | -38.9554535393259 | -57.802842 | -0.138539991859674 | 1312 | 0.0047272862787149 | 89 |
| 2.0->2.1 | total_tokens | submission-balanced | effective | 89 | 203421.168539326 | 60340 | 0.296637884270165 | 1080 | 0.0001604978226435 | 89 |
| 2.0->2.1 | steps | submission-balanced | leaderboard-url | 89 | -3.01123595505618 | -3 | -0.292903446523287 | 1070.5 | 0.0009048161246406 | 85 |
| 2.0->2.1 | shell_invocations | submission-balanced | leaderboard-url | 89 | -4.84550561797753 | -4 | -0.482527686670474 | 829 | 4.3210027203806e-06 | 87 |
| 2.0->2.1 | tool_calls | submission-balanced | leaderboard-url | 89 | -5.14887640449438 | -5 | -0.413564447340968 | 885.5 | 3.64095723219045e-05 | 85 |
| 2.0->2.1 | duration | submission-balanced | leaderboard-url | 89 | -35.6186248876404 | -55.062643 | -0.12941962940836 | 1336 | 0.0063939967235828 | 89 |
| 2.0->2.1 | total_tokens | submission-balanced | leaderboard-url | 89 | 190180.632022472 | 43852 | 0.278974166185711 | 1254 | 0.0021960740615232 | 89 |
| 3.0->4.0 | steps | submission-balanced | effective | 66 | -9.90530303030303 | -10.25 | -0.360437750179541 | 416.5 | 1.07399284511201e-05 | 66 |
| 3.0->4.0 | shell_invocations | submission-balanced | effective | 66 | -2.89772727272727 | -4.75 | -0.133782953046193 | 658 | 0.0067471947016407 | 65 |
| 3.0->4.0 | tool_calls | submission-balanced | effective | 66 | -9.9280303030303 | -10.25 | -0.398661323780061 | 418.5 | 1.91774224839954e-05 | 65 |
| 3.0->4.0 | duration | submission-balanced | effective | 66 | -510.615397943182 | -414.03829225 | -0.499867409459178 | 247 | 4.15420432053502e-08 | 66 |
| 3.0->4.0 | total_tokens | submission-balanced | effective | 66 | -2222156.62121212 | -1925222.5 | -0.510942476520215 | 374 | 2.97003238263667e-06 | 66 |
| 3.0->4.0 | steps | submission-balanced | leaderboard-url | 66 | -9.48106060606061 | -11.25 | -0.364885490865144 | 430.5 | 1.61447499589834e-05 | 66 |
| 3.0->4.0 | shell_invocations | submission-balanced | leaderboard-url | 66 | -3.47727272727273 | -6 | -0.165547340051035 | 632.5 | 0.0025105150428279 | 66 |
| 3.0->4.0 | tool_calls | submission-balanced | leaderboard-url | 66 | -10.2954545454545 | -9.75 | -0.440711191442218 | 407 | 8.10535437650829e-06 | 66 |
| 3.0->4.0 | duration | submission-balanced | leaderboard-url | 66 | -589.360352526515 | -546.48412025 | -0.586386251783591 | 180 | 3.37631451690434e-09 | 66 |
| 3.0->4.0 | total_tokens | submission-balanced | leaderboard-url | 66 | -2538791.08333333 | -2167026.25 | -0.535722698817955 | 381 | 3.68920278891325e-06 | 66 |


### AH. All seven exact matched-configuration token comparisons

Source: `data/processed_live/longitudinal/rq3_3_shared_configuration_tokens_tb3_tb4.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| configuration | task_weighting | submission_unit | shared_tasks | old_median_tokens | new_median_tokens | percentage_change | direction |
|---|---|---|---|---|---|---|---|
| claude-code / claude-fable-5 | submission-balanced | effective | 66 | 5474905 | 5202921 | -4.96783049203593 | decrease |
| claude-code / claude-opus-4-8 | submission-balanced | effective | 66 | 9832830 | 12224736.5 | 24.3257180282787 | increase |
| claude-code / claude-sonnet-5 | submission-balanced | effective | 66 | 32988529.5 | 39208232.5 | 18.8541383755829 | increase |
| claude-code / glm-5.3 | submission-balanced | effective | 65 | 10022539 | 17812942 | 77.7288369743435 | increase |
| codex / gpt-5.6-luna | submission-balanced | effective | 66 | 9173579.5 | 11789155 | 28.5120491951915 | increase |
| codex / gpt-5.6-sol | submission-balanced | effective | 66 | 4731087.5 | 5002707.5 | 5.74117472991147 | increase |
| codex / gpt-5.6-terra | submission-balanced | effective | 66 | 6730560.5 | 7290233.5 | 8.31539958670604 | increase |


### AI. Input-prompt accumulation diagnostic

Source: `data/processed_live/longitudinal/token_accounting/input_context_growth_summary.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| group_type | group | eligible_trajectories | exact_sum_count | exact_sum_pct | last_gt_first_count | last_gt_first_pct | mostly_increasing_count | mostly_increasing_pct | median_final_first_ratio | q1_final_first_ratio | q3_final_first_ratio |
|---|---|---|---|---|---|---|---|---|---|---|---|
| overall | overall | 34463 | 33155 | 96.2046252502684 | 34139 | 99.0598613005252 | 33572 | 97.4146185764443 | 9.48056765037897 | 3.89268209364879 | 24.7278358588469 |
| scaffold | Codex | 890 | 890 | 100 | 890 | 100 | 890 | 100 | 4.23822218918457 | 2.26498925251883 | 8.04838357253871 |
| scaffold | Gemini CLI | 2056 | 2056 | 100 | 2056 | 100 | 2056 | 100 | 3.16410004846173 | 1.89576566022971 | 5.33181158819843 |
| scaffold | Claude Code | 4680 | 4680 | 100 | 4625 | 98.8247863247863 | 3939 | 84.1666666666667 | 22.0496769460157 | 3.0902794325724 | 58.116120364496 |
| scaffold | Terminus-2 | 14413 | 13367 | 92.7426628737945 | 14174 | 98.3417747866509 | 14266 | 98.9800874210782 | 14.6464771322621 | 6.74652406417112 | 29.7937743190661 |
| scaffold | mini-swe-agent | 5987 | 5765 | 96.2919659261734 | 5987 | 100 | 5987 | 100 | 11.1313131313131 | 4.92210437914952 | 25.1162416911845 |
| scaffold | OpenHands | 5149 | 5149 | 100 | 5119 | 99.4173625946786 | 5146 | 99.9417362594679 | 3.67617538298996 | 2.20297609095469 | 6.60606853256605 |
| scaffold | Terminus-3.3 | 678 | 649 | 95.7227138643068 | 678 | 100 | 678 | 100 | 12.3737946607039 | 6.87679335962905 | 21.1974124535762 |
| scaffold | Terminus Kira env bootstrap | 444 | 433 | 97.5225225225225 | 444 | 100 | 444 | 100 | 16.9891554373522 | 9.77233245442743 | 31.7477158599447 |
| scaffold | Judy | 166 | 166 | 100 | 166 | 100 | 166 | 100 | 5.27925174304679 | 4.01869113135988 | 7.13226292982866 |
| benchmark_version | Terminal-Bench 2.0 | 27927 | 26930 | 96.4299781573388 | 27616 | 98.8863823539943 | 27038 | 96.8167006839259 | 10.1263669501823 | 4.12610002966854 | 26.8536734329751 |
| benchmark_version | Terminal-Bench 2.1 | 6536 | 6225 | 95.2417380660955 | 6523 | 99.8011015911873 | 6534 | 99.969400244798 | 7.18904800981483 | 3.13376902776286 | 17.5061680283438 |


### AJ. Current model-progression token/text comparisons

Source: `data/processed_live/longitudinal/token_accounting/token_accounting_comparisons.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| comparison_id | scaffold | earlier_model | later_model | earlier_benchmark | later_benchmark | shared_task_count | prompt_tokens_earlier | prompt_tokens_later | prompt_tokens_change_pct | completion_tokens_earlier | completion_tokens_later | completion_tokens_change_pct | total_tokens_earlier | total_tokens_later | total_tokens_change_pct | logged_chars_earlier | logged_chars_later | logged_chars_change_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| codex_gpt5_to_gpt55 | codex | gpt-5 | gpt-5.5 | 2 | 2.1 | 88 | 149825.75 | 603113 | 302.542954064972 | 6567.5 | 11422.5 | 73.9246288542063 | 155115 | 614173 | 295.946878122683 | 13256.5 | 41343.5 | 211.873420586128 |
| codex_gpt5_to_gpt56_luna | codex | gpt-5 | gpt-5.6-luna | 2 | 2.1 | 88 | 149825.75 | 868182 | 479.46114069177 | 6567.5 | 16102 | 145.177007993909 | 155115 | 884360 | 470.131837668826 | 13256.5 | 56774 | 328.272922717158 |
| codex_gpt5_to_gpt56_terra | codex | gpt-5 | gpt-5.6-terra | 2 | 2.1 | 88 | 149825.75 | 502248.5 | 235.221749265397 | 6567.5 | 14936.5 | 127.43052912067 | 155115 | 522352.5 | 236.75176481965 | 13256.5 | 45988 | 246.909063478294 |
| gemini_cli_25pro_to_3pro | gemini-cli | gemini-2.5-pro | gemini-3-pro-preview | 2 | 2.1 | 88 | 267880.5 | 313656.5 | 17.0882165741814 | 13118 | 10531 | -19.7209940539716 | 287255.5 | 334748 | 16.5331908353365 | 28520.5 | 32901 | 15.3591276450273 |
| claude_code_opus46_to_opus47 | claude-code | claude-opus-4-6 | claude-opus-4-7 | 2 | 2.1 | 87 | 810971 | 580824 | -28.3791898847184 | 256 | 17667.5 | 6801.3671875 | 811188 | 595602 | -26.5765765765766 | 50841 | 37253 | -26.7264609272044 |
| claude_code_sonnet45_to_sonnet5 | claude-code | claude-sonnet-4-5-20250929 | claude-sonnet-5 | 2 | 2.1 | 88 | 1119538.5 | 363317.5 | -67.5475653584044 | 611.5 | 10941.5 | 1689.28863450532 | 1120107.5 | 379400 | -66.1282510830434 | 70311.5 | 87269.5 | 24.1183874615106 |
| terminus2_gpt52_to_gpt55 | terminus-2 | gpt-5.2 | gpt-5.5 | 2 | 2.1 | 89 | 51272 | 69804 | 36.1444843189265 | 18095 | 18445 | 1.93423597678917 | 74493 | 80734 | 8.37796839971541 | 35168 | 35237 | 0.196201091901726 |
| terminus2_gemini3_to_31 | terminus-2 | gemini-3-pro-preview | gemini-3.1-pro-preview | 2 | 2.1 | 89 | 67767 | 86891 | 28.2202251833488 | 16782 | 20042 | 19.4255750208557 | 80897 | 110892 | 37.0780127816854 | 30066 | 57848.5 | 92.4050422404044 |
| terminus2_opus46_to_opus47 | terminus-2 | claude-opus-4-6 | claude-opus-4-7 | 2 | 2.1 | 89 | 76442 | 165627 | 116.67015515031 | 9055 | 16464 | 81.8221976808393 | 81896 | 200839 | 145.236641594217 | 35873 | 35456 | -1.16243414266998 |


### AK. Monthly token/text diagnostic

Source: `data/processed_live/longitudinal/token_accounting/token_vs_logged_text_monthly.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| month | trajectory_n | benchmark_version_composition | tb20_trajectory_n | tb21_trajectory_n | prompt_tokens_n | median_prompt_tokens | completion_tokens_n | median_completion_tokens | total_tokens_n | median_total_tokens | logged_chars_n | median_logged_chars | reliable_month | indexed_prompt_tokens | indexed_completion_tokens | indexed_total_tokens | indexed_logged_chars |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-10 | 4390 | TB2.0: 4390 | 4390 | 0 | 4390 | 81908 | 4390 | 9169 | 4390 | 95931 | 4390 | 33453.5 | True | 100 | 100 | 100 | 100 |
| 2025-11 | 14108 | TB2.0: 14108 | 14108 | 0 | 14099 | 171943 | 14099 | 8993 | 14099 | 191701 | 14108 | 34423 | True | 209.922107730625 | 98.0804886029011 | 199.832171039601 | 102.898052520663 |
| 2025-12 | 1757 | TB2.0: 1757 | 1757 | 0 | 1757 | 373609 | 1757 | 9076 | 1757 | 389752 | 1757 | 50943 | True | 456.132490110856 | 98.9857127276693 | 406.283683063869 | 152.280030490083 |
| 2026-01 | 1747 | TB2.0: 1747 | 1747 | 0 | 1747 | 518627 | 1747 | 8630 | 1747 | 525918 | 1747 | 52348 | True | 633.182350930312 | 94.1214963463846 | 548.225286924977 | 156.479889996562 |
| 2026-02 | 6774 | TB2.0: 6774 | 6774 | 0 | 6704 | 170233 | 6704 | 7732 | 6704 | 183085 | 6774 | 41691.5 | True | 207.83439957025 | 84.3276256952776 | 190.850715618517 | 124.625226060054 |
| 2026-03 | 166 | TB2.0: 166 | 166 | 0 | 166 | 1136704 | 166 | 22725.5 | 166 | 1162406.5 | 166 | 162508.5 | True | 1387.78141329296 | 247.85145599302 | 1211.71102146334 | 485.774283707235 |
| 2026-04 | 409 | TB2.0: 409 | 409 | 0 | 409 | 149742 | 409 | 6480 | 409 | 155707 | 409 | 13490 | True | 182.817307222738 | 70.6729196204602 | 162.311453023527 | 40.3246297098958 |
| 2026-05 | 5694 | TB2.0: 1752; TB2.1: 3942 | 1752 | 3942 | 5251 | 306241 | 5251 | 14126 | 5251 | 323912 | 5694 | 36472.5 | True | 373.88411388387 | 154.062602246701 | 337.651020003961 | 109.024466797196 |
| 2026-06 | 890 | TB2.1: 890 | 0 | 890 | 890 | 93403 | 890 | 9682.5 | 890 | 105627.5 | 890 | 28861.5 | True | 114.034038189188 | 105.600392627331 | 110.10778580438 | 86.2734840898561 |
| 2026-07 | 2669 | TB2.1: 2669 | 0 | 2669 | 2629 | 367038 | 2629 | 12826 | 2629 | 381338 | 2669 | 62069 | True | 448.110074717976 | 139.884393063584 | 397.512795655211 | 185.538135023241 |


### AL. Every archived descriptive direction reversal checked against current cells

Historical source: `A/manuscript_direction_changes.csv`. Current sources: the row's adjacent-task column in S10 or `token_accounting_comparisons.csv` in S18. These are historical versus current differences, not causal effects. Duration columns are minutes or percent as named; pass-rate absolute changes here are **proportions**, multiply by 100 for pp.

| Row key | Column | Historical before | Current authoritative value | Matches archived after |
|---|---|---|---|---|
| ('3.0->4.0', 'fin-saccr-rwa') | observed_median_duration_min_change | -0.966931549999998 | 1.214270675 | True |
| ('3.0->4.0', 'gsea-proteomics') | observed_median_duration_min_change | 0.162388500000002 | -0.635615349999998 | True |
| ('3.0->4.0', 'kv-live-surgery') | observed_median_duration_min_change | -4.76336858333334 | 1.746881875 | True |
| ('3.0->4.0', 'photonic-waveguide-routing') | observed_median_duration_min_change | -0.546406900000001 | 3.54528146666666 | True |
| ('3.0->4.0', 'takens-embedding-lean') | observed_median_duration_min_change | -8.17344144166665 | 0.131080891666684 | True |
| ('3.0->4.0', 'uefi-bootkit') | observed_median_duration_min_change | 2.98870928333335 | -5.60526885833332 | True |
| ('3.0->4.0', 'vllm-deepseek-streaming') | observed_median_duration_min_change | -4.6136465 | 0.954535174999997 | True |
| ('3.0->4.0', 'fin-saccr-rwa') | observed_median_duration_min_relative_change_pct | -5.63935387786678 | 8.11410402859125 | True |
| ('3.0->4.0', 'gsea-proteomics') | observed_median_duration_min_relative_change_pct | 1.50002350418785 | -5.46825433335032 | True |
| ('3.0->4.0', 'kv-live-surgery') | observed_median_duration_min_relative_change_pct | -15.9549284956909 | 7.48292585628041 | True |
| ('3.0->4.0', 'photonic-waveguide-routing') | observed_median_duration_min_relative_change_pct | -1.12525667225396 | 7.97288458146024 | True |
| ('3.0->4.0', 'takens-embedding-lean') | observed_median_duration_min_relative_change_pct | -10.1333469366068 | 0.181165232108738 | True |
| ('3.0->4.0', 'uefi-bootkit') | observed_median_duration_min_relative_change_pct | 4.69161195069294 | -7.75308959056261 | True |
| ('3.0->4.0', 'vllm-deepseek-streaming') | observed_median_duration_min_relative_change_pct | -16.7202257273681 | 4.33386640801299 | True |
| ('3.0->4.0', 'glycan-ms2-elucidation') | observed_mean_duration_min_change | -1.12282889305555 | 0.0091257196581224 | True |
| ('3.0->4.0', 'ontology-kg-querying') | observed_mean_duration_min_change | -0.687514627314815 | 0.320978193091168 | True |
| ('3.0->4.0', 'session-window-debug') | observed_mean_duration_min_change | -0.285291220833335 | 0.616455522863248 | True |
| ('3.0->4.0', 'uefi-bootkit') | observed_mean_duration_min_change | 0.222227184259267 | -0.344380495655258 | True |
| ('3.0->4.0', 'vba-userform-port') | observed_mean_duration_min_change | -1.17299219074074 | 0.442036989387468 | True |
| ('3.0->4.0', 'vllm-deepseek-streaming') | observed_mean_duration_min_change | -0.504379578009257 | 0.403653901424502 | True |
| ('3.0->4.0', 'glycan-ms2-elucidation') | observed_mean_duration_min_relative_change_pct | -6.10335708447506 | 0.0528569077102636 | True |
| ('3.0->4.0', 'ontology-kg-querying') | observed_mean_duration_min_relative_change_pct | -3.21825716201317 | 1.57694312546388 | True |
| ('3.0->4.0', 'session-window-debug') | observed_mean_duration_min_relative_change_pct | -1.77206498993607 | 4.05626387914917 | True |
| ('3.0->4.0', 'uefi-bootkit') | observed_mean_duration_min_relative_change_pct | 0.315231414073835 | -0.484612056262101 | True |
| ('3.0->4.0', 'vba-userform-port') | observed_mean_duration_min_relative_change_pct | -3.25094591934715 | 1.28251061129097 | True |
| ('3.0->4.0', 'vllm-deepseek-streaming') | observed_mean_duration_min_relative_change_pct | -1.61023400529055 | 1.32713929523756 | True |
| ('3.0->4.0', 'biped-contact-dynamics') | task_weighted_pass_rate_change | -0.0041666666666666 | 0.0282051282051282 | True |
| ('3.0->4.0', 'vf2-speedup-networkx') | task_weighted_pass_rate_change | -0.0319444444444444 | 0.0029914529914529 | True |
| ('3.0->4.0', 'biped-contact-dynamics') | task_weighted_pass_rate_relative_change_pct | -0.990099009900991 | 7.26072607260726 | True |
| ('3.0->4.0', 'vf2-speedup-networkx') | task_weighted_pass_rate_relative_change_pct | -7.03363914373089 | 0.713557594291547 | True |
| terminus2_opus46_to_opus47 | logged_chars_change_pct | 4.58810607249334 | -1.16243414266998 | True |


### AM. Changed historical inferential rows

Source: `A/master_before_after.csv`. All 40 after-rows were compared by `(rq,analysis,comparison,metric)` to current S20 for n, raw effect, effect size, statistic, and p; they match to saved numerical tolerance. The following 20 changed rows are historical comparisons, not substitutes for today's outputs. No test was rerun.

| rq | comparison | metric | n_after | raw_effect_before | raw_effect_after | effect_size_before | effect_size_after | test_statistic_before | test_statistic_after | p_value_before | p_value_after |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RQ1.1 | success - failure | Shell invocations | 86 | 0.5 | 0.375 | -0.0064389266576731 | -0.0136526800336146 | 1481 | 1496 | 0.397965352897758 | 0.438556875143347 |
| RQ1.2 | H0: beta_2 = 0 | Shell invocations | 87 | -0.296089219401018 | -0.292799649614695 | -0.296089219401018 | -0.292799649614695 | -1.61648768263983 | -1.59840421323353 | 0.105988914374297 | 0.109953047575811 |
| RQ2.1 | ordinal difficulty | Task-balanced pass rate | 89 | -0.483290555366995 | -0.487792911583003 | -0.483290555366995 | -0.487792911583003 | -0.483290555366995 | -0.487792911583003 | 1.60881716556844e-06 | 1.24374181239545e-06 |
| RQ2.2 | agent - expert | Duration | 88 | -47.0802541666667 | -46.9086 | -0.509097069897989 | -0.509414281456379 | 47 | 46 | 1.84422704400097e-15 | 1.78328861568782e-15 |
| RQ2.2 | agent - junior | Duration | 88 | -235.26865 | -235.344333333333 | -0.402970679010402 | -0.403009342834737 | 1 | 1 | 3.86257572623649e-16 | 3.86257572623649e-16 |
| RQ2.3 | used - not used | Inspect/search | 89 | 9.50054304690501 | 9.45880518529176 | 0.783948799509946 | 0.778820841034282 | 428 | 434 | 3.18837238428385e-10 | 3.75378279020056e-10 |
| RQ2.3 | used - not used | Modify/write | 89 | 5.70370066671272 | 5.69940287851562 | 0.510227186715447 | 0.509762368150349 | 854 | 856 | 7.24577792216659e-06 | 7.53903690429346e-06 |
| RQ2.3 | used - not used | Execute/run | 89 | 7.70638506574502 | 7.68400808353825 | 0.520507935484814 | 0.520018018023822 | 769 | 762 | 1.25920922263824e-06 | 1.08416266526348e-06 |
| RQ2.3 | used - not used | Test/validate | 82 | 7.81182977417633 | 7.5644015821082 | 0.49805433594847 | 0.487193226297958 | 722 | 730 | 1.65434335876954e-05 | 1.9661936820094e-05 |
| RQ2.3 | used - not used | Version control | 50 | -2.30916824317333 | -2.32280336447623 | -0.120391967768798 | -0.121237497910023 | 543 | 543 | 0.489353799814439 | 0.489353799814439 |
| RQ2.3 | used - not used | Media/specialized | 12 | 2.05785358627614 | 2.00270621895448 | 0.101250717595226 | 0.0983193069017182 | 32 | 32 | 0.6220703125 | 0.6220703125 |
| RQ3.1 | 3.0->4.0 | Task-balanced pass rate | 66 | 14.3427703955779 | 14.5809623383153 | 0.907871837011222 | 0.924091442153001 | 173.5 | 164 | 1.80142071234701e-08 | 1.2224394185128e-08 |
| RQ3.1 | 3.0->4.0 | Task pass-rate improvement | 66 | 6.3492815859126 | 6.65086384204031 | 0.183471074380165 | 0.208264462809917 | 358 | 365.5 | 0.343889458855764 | 0.282141395128863 |
| RQ3.3 | 2.0->2.1 | Shell invocations | 89 | -4.5 | -4.5 | -0.522032174689398 | -0.523732786307623 | 750 | 766.5 | 1.38300701128735e-06 | 1.17878798894363e-06 |
| RQ3.3 | 2.0->2.1 | Total tokens | 89 | 63149 | 60340 | 0.311693614247545 | 0.296637884270165 | 1032 | 1080 | 7.16856699467081e-05 | 0.0001604978226435 |
| RQ3.3 | 3.0->4.0 | Steps | 66 | -11.25 | -10.25 | -0.364885490865144 | -0.360437750179541 | 430.5 | 416.5 | 1.61447499589834e-05 | 1.07399284511201e-05 |
| RQ3.3 | 3.0->4.0 | Shell invocations | 66 | -6 | -4.75 | -0.165547340051035 | -0.133782953046193 | 632.5 | 658 | 0.0025105150428279 | 0.0067471947016407 |
| RQ3.3 | 3.0->4.0 | Structured tool calls | 66 | -9.75 | -10.25 | -0.440711191442218 | -0.398661323780061 | 407 | 418.5 | 8.10535437650829e-06 | 1.91774224839954e-05 |
| RQ3.3 | 3.0->4.0 | Duration | 66 | -546.48412025 | -414.03829225 | -0.586386251783591 | -0.499867409459178 | 180 | 247 | 3.37631451690434e-09 | 4.15420432053502e-08 |
| RQ3.3 | 3.0->4.0 | Total tokens | 66 | -2167026.25 | -1925222.5 | -0.535722698817955 | -0.510942476520215 | 381 | 374 | 3.68920278891324e-06 | 2.97003238263667e-06 |


### AN. TB2 current descriptive weighting sensitivity

Source: each transition's `task_balanced_effort_summary{,_url_sensitivity,_trial_weighted_sensitivity}.csv`; task_set=`all_shared_tasks`. Ratios of medians are not these median paired relative changes. No additional trial-weighted test is inferred.

| estimator | metric | n_tasks_with_both_versions | median_paired_change | median_paired_relative_change_pct |
|---|---|---|---|---|
| effective | steps | 89 | -3.5 | -20 |
| effective | shell_invocations | 89 | -4.5 | -25 |
| effective | tool_calls | 89 | -5 | -21.9512195121951 |
| effective | duration | 89 | -57.802842 | -18.0924034798912 |
| effective | chars | 89 | 6746.5 | 15.9680500886219 |
| effective | prompt_tokens | 89 | 59287 | 39.803558033882 |
| effective | completion_tokens | 89 | 3120 | 29.5782541684181 |
| effective | total_tokens | 89 | 60340 | 35.9714484205364 |
| URL | steps | 89 | -3 | -17.6470588235294 |
| URL | shell_invocations | 89 | -4 | -23.0769230769231 |
| URL | tool_calls | 89 | -5 | -21.4285714285714 |
| URL | duration | 89 | -55.062643 | -19.1713312628422 |
| URL | chars | 89 | 6746 | 13.8565380501107 |
| URL | prompt_tokens | 89 | 44361 | 35.1131724382229 |
| URL | completion_tokens | 89 | 3425 | 39.7325868356109 |
| URL | total_tokens | 89 | 43852 | 31.8857418588852 |
| trial-weighted | steps | 89 | -3 | -16.6666666666667 |
| trial-weighted | shell_invocations | 89 | -4 | -25 |
| trial-weighted | tool_calls | 89 | -5 | -23.4042553191489 |
| trial-weighted | duration | 89 | -52.535047 | -14.4982915414497 |
| trial-weighted | chars | 89 | 7874 | 23.6087790837131 |
| trial-weighted | prompt_tokens | 89 | 75401 | 42.9109447992074 |
| trial-weighted | completion_tokens | 89 | 3240 | 34.7004186289901 |
| trial-weighted | total_tokens | 89 | 67057 | 41.9046761082188 |


### AN. TB3/TB4 current descriptive weighting sensitivity

Source: each transition's `task_balanced_effort_summary{,_url_sensitivity,_trial_weighted_sensitivity}.csv`; task_set=`all_shared_tasks`. Ratios of medians are not these median paired relative changes. No additional trial-weighted test is inferred.

| estimator | metric | n_tasks_with_both_versions | median_paired_change | median_paired_relative_change_pct |
|---|---|---|---|---|
| effective | steps | 66 | -10.25 | -15.3010033444816 |
| effective | shell_invocations | 66 | -4.75 | -11.7151767151767 |
| effective | tool_calls | 66 | -10.25 | -17.3076923076923 |
| effective | duration | 66 | -414.03829225 | -21.5934216593125 |
| effective | chars | 66 | -89000.5 | -25.9769017000113 |
| effective | prompt_tokens | 66 | -1902173 | -29.0461232979309 |
| effective | completion_tokens | 66 | -5903.375 | -9.05599924101725 |
| effective | total_tokens | 66 | -1925222.5 | -27.9708902021548 |
| URL | steps | 66 | -11.25 | -15.1517991004498 |
| URL | shell_invocations | 66 | -6 | -11.7151767151767 |
| URL | tool_calls | 66 | -9.75 | -16.1406953356958 |
| URL | duration | 66 | -546.48412025 | -24.4842038398588 |
| URL | chars | 66 | -94855.5 | -26.8340120480137 |
| URL | prompt_tokens | 66 | -2120917 | -30.2982382125899 |
| URL | completion_tokens | 66 | -10198.75 | -12.5475214918658 |
| URL | total_tokens | 66 | -2167026.25 | -29.2363393123446 |
| trial-weighted | steps | 66 | -11.5 | -16.2955632525153 |
| trial-weighted | shell_invocations | 66 | -6.5 | -15.0658561296859 |
| trial-weighted | tool_calls | 66 | -11.75 | -15.9592529711375 |
| trial-weighted | duration | 66 | -448.20881125 | -19.8049281797191 |
| trial-weighted | chars | 66 | -88938.75 | -26.3852189547735 |
| trial-weighted | prompt_tokens | 66 | -2362003.25 | -28.8745107284472 |
| trial-weighted | completion_tokens | 66 | -15824.5 | -15.5215844217303 |
| trial-weighted | total_tokens | 66 | -2391098.25 | -28.3444084871687 |


### AO. Current difficulty-provenance hashes

Source: `reports/longitudinal/difficulty_over_versions/provenance.json`, array `files`; compared with current bytes. Any mismatch is reported rather than repaired.

| Path | Current SHA-256 | Matches current recorded hash |
|---|---|---|
| data/processed_live/longitudinal/tb3_tb4_task_difficulty_llm_labels.csv | 7c0c49445c981d41cb0578d5077509c5f445e069deaccdb938dcd75d4b156f75 | True |
| data/processed_live/longitudinal/tb2_difficulty_prompt_validation.csv | d43a474571448f9c77ea5ea2a4d8be7538c52e1eb448e7477ee6ce93732d07f8 | True |
| data/processed_live/longitudinal/tb2_difficulty_prompt_validation_summary.csv | 12f57e68171ef8823777102f77587e1f009ed82d1e6df25bd4797ca776416383 | True |
| data/processed_live/longitudinal/tb2_difficulty_prompt_validation_confusion.csv | c9bce1de50614e2efc5d453585d23bdab3be74035ddb279c3171b541353c9216 | True |
| data/processed_live/longitudinal/trajectory_longitudinal.csv | 7507a5aa104c7534454ec9b8ae438ad0ee518eabbe74785b6f3760528efac8b2 | True |
| data/processed_live/longitudinal/tb3_tb4/trajectory_longitudinal.csv | ecad1ca7491bf0343bb3bb648d7853e7c0f9e31c1aaf3498c890534c989e1a4e | True |
| data/processed_live/longitudinal/difficulty_over_versions/difficulty_distribution_over_versions.csv | 9e69e0b02607d4c4257c2f6a6f6cd2cf97ee425ad91f81a3fc5d30c9179d2e80 | True |
| data/processed_live/longitudinal/difficulty_over_versions/pass_rate_by_difficulty_over_versions.csv | 104b688b9b54b35af84f27942cca1dbe109819e954dd88dcf02e935fecff4b91 | True |
| data/processed_live/longitudinal/difficulty_over_versions/pass_rate_change_by_difficulty_over_versions.csv | 603746b3fd55380ac45b5bd41af6d3a5f87effe6931606ffa029eb158f646bc8 | True |
| reports/longitudinal/difficulty_over_versions/difficulty_distribution_over_versions.png | e152c8938cc12af7224a75d5b6994f984ebe9b70a540cd140743f3e8fec478e2 | True |
| reports/longitudinal/difficulty_over_versions/pass_rate_by_difficulty_over_versions.png | 25c7917b13d20ee6378b4e83c6cd2b39a183457d5f4b2f7f7850b2df1b5ee04f | True |


### AP. Complete 40-row inferential reference

Source: `data/processed_live/statistical_analysis/master_inferential_results.csv`; producer and estimator in Section 2. Keys are the first identifying columns. Missing values shown as `NA`.

| rq | comparison | metric | n | raw_effect | raw_effect_unit | effect_size_type | effect_size | test | test_statistic | p_value | source_file | task_observation_function |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RQ1.1 | success - failure | Steps | 86 | 2 | steps | cohens_dz | 0.130583798033597 | two-sided Wilcoxon signed-rank | 1479.5 | 0.127194746755061 | terminal_bench_2_0/trajectory_summary.csv | task_medians |
| RQ1.1 | success - failure | Shell invocations | 86 | 0.375 | invocations | cohens_dz | -0.0136526800336146 | two-sided Wilcoxon signed-rank | 1496 | 0.438556875143347 | terminal_bench_2_0/trajectory_summary.csv | task_medians |
| RQ1.1 | success - failure | Structured tool calls | 86 | 1.125 | calls | cohens_dz | 0.104213606844877 | two-sided Wilcoxon signed-rank | 1398.5 | 0.11768846199576 | terminal_bench_2_0/trajectory_summary.csv | task_medians |
| RQ1.1 | success - failure | Input tokens | 85 | 21618 | tokens | cohens_dz | 0.254136593484926 | two-sided Wilcoxon signed-rank | 1274 | 0.015295497390481 | terminal_bench_2_0/trajectory_summary.csv | task_medians |
| RQ1.1 | success - failure | Output tokens | 85 | -29.5 | tokens | cohens_dz | 0.164443247924734 | two-sided Wilcoxon signed-rank | 1711 | 0.609718457481134 | terminal_bench_2_0/trajectory_summary.csv | task_medians |
| RQ1.1 | success - failure | Total tokens | 85 | 20272 | tokens | cohens_dz | 0.246160078290407 | two-sided Wilcoxon signed-rank | 1316 | 0.0250084783275188 | terminal_bench_2_0/trajectory_summary.csv | task_medians |
| RQ1.1 | success - failure | Duration | 86 | -44.88725 | seconds | cohens_dz | -0.274727436357776 | two-sided Wilcoxon signed-rank | 1190 | 0.0033871019599293 | terminal_bench_2_0/trajectory_summary.csv | task_medians |
| RQ1.1 | success - failure | Cost | 83 | 0.086210475 | USD | cohens_dz | 0.457220299604996 | two-sided Wilcoxon signed-rank | 385 | 7.02597366991317e-10 | terminal_bench_2_0/trajectory_summary.csv | task_medians |
| RQ1.2 | H0: beta_2 = 0 | Steps | 87 | -0.425470084515505 | standardized quadratic log-effort coefficient | beta_2 | -0.425470084515505 | two-sided Wald z test | -2.98551971248289 | 0.0028309689111176 | terminal_bench_2_0/trajectory_summary.csv | model_frame + fit_quadratic_conditional_logit |
| RQ1.2 | H0: beta_2 = 0 | Shell invocations | 87 | -0.292799649614695 | standardized quadratic log-effort coefficient | beta_2 | -0.292799649614695 | two-sided Wald z test | -1.59840421323353 | 0.109953047575811 | terminal_bench_2_0/trajectory_summary.csv | model_frame + fit_quadratic_conditional_logit |
| RQ1.2 | H0: beta_2 = 0 | Structured tool calls | 87 | -0.249856511875574 | standardized quadratic log-effort coefficient | beta_2 | -0.249856511875574 | two-sided Wald z test | -1.16891373270077 | 0.242438390046896 | terminal_bench_2_0/trajectory_summary.csv | model_frame + fit_quadratic_conditional_logit |
| RQ1.2 | H0: beta_2 = 0 | Total tokens | 87 | -0.341139582591246 | standardized quadratic log-effort coefficient | beta_2 | -0.341139582591246 | two-sided Wald z test | -2.56964971778068 | 0.0101801391870454 | terminal_bench_2_0/trajectory_summary.csv | model_frame + fit_quadratic_conditional_logit |
| RQ1.2 | H0: beta_2 = 0 | Duration | 87 | -0.486003629074745 | standardized quadratic log-effort coefficient | beta_2 | -0.486003629074745 | two-sided Wald z test | -3.09966764484345 | 0.0019373790337419 | terminal_bench_2_0/trajectory_summary.csv | model_frame + fit_quadratic_conditional_logit |
| RQ1.2 | H0: beta_2 = 0 | Cost | 86 | -0.288740205067501 | standardized quadratic log-effort coefficient | beta_2 | -0.288740205067501 | two-sided Wald z test | -2.23520038643706 | 0.0254041961388122 | terminal_bench_2_0/trajectory_summary.csv | model_frame + fit_quadratic_conditional_logit |
| RQ2.1 | ordinal difficulty | Task-balanced pass rate | 89 | -0.487792911583003 | rho | spearman_rho | -0.487792911583003 | two-sided Spearman rank correlation | -0.487792911583003 | 1.24374181239545e-06 | longitudinal/trajectory_longitudinal.csv + TB2 task metadata | submission_task_pass_rates |
| RQ2.2 | agent - expert | Duration | 88 | -46.9086 | minutes | cohens_dz | -0.509414281456379 | two-sided Wilcoxon signed-rank | 46 | 1.78328861568782e-15 | longitudinal/trajectory_longitudinal.csv + terminal_bench_2_task_toml_metadata.csv | build_task_average_duration_comparison |
| RQ2.2 | agent - junior | Duration | 88 | -235.344333333333 | minutes | cohens_dz | -0.403009342834737 | two-sided Wilcoxon signed-rank | 1 | 3.86257572623649e-16 | longitudinal/trajectory_longitudinal.csv + terminal_bench_2_task_toml_metadata.csv | build_task_average_duration_comparison |
| RQ2.3 | used - not used | Inspect/search | 89 | 9.45880518529176 | percentage points (mean task contrast) | cohens_dz | 0.778820841034282 | two-sided Wilcoxon signed-rank | 434 | 3.75378279020056e-10 | terminal_bench_2_0 trajectories + task metadata | build_task_functional_contrasts |
| RQ2.3 | used - not used | Modify/write | 89 | 5.69940287851562 | percentage points (mean task contrast) | cohens_dz | 0.509762368150349 | two-sided Wilcoxon signed-rank | 856 | 7.53903690429346e-06 | terminal_bench_2_0 trajectories + task metadata | build_task_functional_contrasts |
| RQ2.3 | used - not used | Execute/run | 89 | 7.68400808353825 | percentage points (mean task contrast) | cohens_dz | 0.520018018023822 | two-sided Wilcoxon signed-rank | 762 | 1.08416266526348e-06 | terminal_bench_2_0 trajectories + task metadata | build_task_functional_contrasts |
| RQ2.3 | used - not used | Test/validate | 82 | 7.5644015821082 | percentage points (mean task contrast) | cohens_dz | 0.487193226297958 | two-sided Wilcoxon signed-rank | 730 | 1.9661936820094e-05 | terminal_bench_2_0 trajectories + task metadata | build_task_functional_contrasts |
| RQ2.3 | used - not used | Environment/dependencies | 80 | 2.34531755902264 | percentage points (mean task contrast) | cohens_dz | 0.120179250165995 | two-sided Wilcoxon signed-rank | 1273 | 0.182744793221064 | terminal_bench_2_0 trajectories + task metadata | build_task_functional_contrasts |
| RQ2.3 | used - not used | Version control | 50 | -2.32280336447623 | percentage points (mean task contrast) | cohens_dz | -0.121237497910023 | two-sided Wilcoxon signed-rank | 543 | 0.489353799814439 | terminal_bench_2_0 trajectories + task metadata | build_task_functional_contrasts |
| RQ2.3 | used - not used | Data query/transform | 13 | -3.74685000035107 | percentage points (mean task contrast) | cohens_dz | -0.182873001217972 | two-sided Wilcoxon signed-rank | 38 | 0.635498046875 | terminal_bench_2_0 trajectories + task metadata | build_task_functional_contrasts |
| RQ2.3 | used - not used | Network/external | 48 | -2.40466146612518 | percentage points (mean task contrast) | cohens_dz | -0.100335294875725 | two-sided Wilcoxon signed-rank | 450 | 0.227676364065947 | terminal_bench_2_0 trajectories + task metadata | build_task_functional_contrasts |
| RQ2.3 | used - not used | Media/specialized | 12 | 2.00270621895448 | percentage points (mean task contrast) | cohens_dz | 0.0983193069017182 | two-sided Wilcoxon signed-rank | 32 | 0.6220703125 | terminal_bench_2_0 trajectories + task metadata | build_task_functional_contrasts |
| RQ3.1 | 2.0->2.1 | Task-balanced pass rate | 89 | 38.4478371135505 | percentage points | cohens_dz | 1.80319632454581 | two-sided Wilcoxon signed-rank | 1 | 2.63918889149538e-16 | longitudinal/task_composition/adjacent_version_task_changes.csv | build_observed_task_duration + build_adjacent_changes |
| RQ3.1 | 3.0->4.0 | Task-balanced pass rate | 66 | 14.5809623383153 | percentage points | cohens_dz | 0.924091442153001 | two-sided Wilcoxon signed-rank | 164 | 1.2224394185128e-08 | longitudinal/task_composition/adjacent_version_task_changes.csv | build_observed_task_duration + build_adjacent_changes |
| RQ3.1 | 2.0->2.1 | Task pass-rate improvement | 89 | 4.31423386757764 | percentage points | cliffs_delta | 0.104477611940299 | two-sided Mann-Whitney U | 814 | 0.466869384158737 | adjacent_version_task_changes.csv + task instruction audits | build_adjacent_changes; independent changed/unchanged task split |
| RQ3.1 | 3.0->4.0 | Task pass-rate improvement | 66 | 6.65086384204031 | percentage points | cliffs_delta | 0.208264462809917 | two-sided Mann-Whitney U | 365.5 | 0.282141395128863 | adjacent_version_task_changes.csv + task instruction audits | build_adjacent_changes; independent changed/unchanged task split |
| RQ3.3 | 2.0->2.1 | Steps | 89 | -3.5 | steps | cohens_dz | -0.312894294590428 | two-sided Wilcoxon signed-rank | 1129 | 0.0008894960251363 | longitudinal/trajectory_longitudinal.csv | task_metric_pairs (submission-task median -> task median) |
| RQ3.3 | 2.0->2.1 | Shell invocations | 89 | -4.5 | invocations | cohens_dz | -0.523732786307623 | two-sided Wilcoxon signed-rank | 766.5 | 1.17878798894363e-06 | longitudinal/trajectory_longitudinal.csv | task_metric_pairs (submission-task median -> task median) |
| RQ3.3 | 2.0->2.1 | Structured tool calls | 89 | -5 | calls | cohens_dz | -0.416884082869444 | two-sided Wilcoxon signed-rank | 929 | 3.05129357974193e-05 | longitudinal/trajectory_longitudinal.csv | task_metric_pairs (submission-task median -> task median) |
| RQ3.3 | 2.0->2.1 | Duration | 89 | -57.802842 | seconds | cohens_dz | -0.138539991859674 | two-sided Wilcoxon signed-rank | 1312 | 0.0047272862787149 | longitudinal/trajectory_longitudinal.csv | task_metric_pairs (submission-task median -> task median) |
| RQ3.3 | 2.0->2.1 | Total tokens | 89 | 60340 | tokens | cohens_dz | 0.296637884270165 | two-sided Wilcoxon signed-rank | 1080 | 0.0001604978226435 | longitudinal/trajectory_longitudinal.csv | task_metric_pairs (submission-task median -> task median) |
| RQ3.3 | 3.0->4.0 | Steps | 66 | -10.25 | steps | cohens_dz | -0.360437750179541 | two-sided Wilcoxon signed-rank | 416.5 | 1.07399284511201e-05 | longitudinal/tb3_tb4/trajectory_longitudinal.csv | task_metric_pairs (submission-task median -> task median) |
| RQ3.3 | 3.0->4.0 | Shell invocations | 66 | -4.75 | invocations | cohens_dz | -0.133782953046193 | two-sided Wilcoxon signed-rank | 658 | 0.0067471947016407 | longitudinal/tb3_tb4/trajectory_longitudinal.csv | task_metric_pairs (submission-task median -> task median) |
| RQ3.3 | 3.0->4.0 | Structured tool calls | 66 | -10.25 | calls | cohens_dz | -0.398661323780061 | two-sided Wilcoxon signed-rank | 418.5 | 1.91774224839954e-05 | longitudinal/tb3_tb4/trajectory_longitudinal.csv | task_metric_pairs (submission-task median -> task median) |
| RQ3.3 | 3.0->4.0 | Duration | 66 | -414.03829225 | seconds | cohens_dz | -0.499867409459178 | two-sided Wilcoxon signed-rank | 247 | 4.15420432053502e-08 | longitudinal/tb3_tb4/trajectory_longitudinal.csv | task_metric_pairs (submission-task median -> task median) |
| RQ3.3 | 3.0->4.0 | Total tokens | 66 | -1925222.5 | tokens | cohens_dz | -0.510942476520215 | two-sided Wilcoxon signed-rank | 374 | 2.97003238263667e-06 | longitudinal/tb3_tb4/trajectory_longitudinal.csv | task_metric_pairs (submission-task median -> task median) |


### AQ. Targeted reasoning-counter evidence (historical diagnostic definitions)

Source S19 `E_reasoning_thinking_token_evidence.csv`. Raw model identifiers and accounting denominators differ from the corrected manuscript claims. In particular the Gemini share exceeding 1 shows why this table cannot validate a completeness-adjusted fraction. These are not the 2,304 completeness-validated records claimed by the manuscript.

| benchmark_version | model | scaffold | submission_or_run_date_s | n_trajectories | token_field_name | number_with_field_populated | percentage_with_field_populated | number_with_value_gt_0 | percentage_with_value_gt_0 | median_reasoning_thinking_tokens_among_positive | median_output_completion_tokens | median_reasoning_thinking_share_of_output_completion_tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TB4.0 | claude-fable-5 | claude-code | 2026-06-09 | 290 | thinking_tokens | 290 | 100 | 290 | 100 | 114712 | 159222 | 0.695480790436721 |
| TB4.0 | claude-fable-5-1 | claude-code | 2026-09-01 | 318 | thinking_tokens | 318 | 100 | 318 | 100 | 109705 | 158585 | 0.67880665073698 |
| TB4.0 | claude-opus-4-8 | claude-code | 2026-05-28; 2026-06-09 | 331 | thinking_tokens | 331 | 100 | 331 | 100 | 182982 | 240419 | 0.771275429892203 |
| TB4.0 | claude-opus-5 | claude-code | 2026-06-09; 2026-07-24; 2026-09-01 | 381 | thinking_tokens | 381 | 100 | 381 | 100 | 111888 | 168750 | 0.652898481103318 |
| TB4.0 | claude-sonnet-5 | claude-code | 2026-06-30 | 329 | thinking_tokens | 329 | 100 | 329 | 100 | 243174 | 307281 | 0.780173689155588 |
| TB4.0 | gemini/gemini-3.8-flash | mini-swe-agent | 2026-09-02 | 330 | reasoning_tokens | 330 | 100 | 330 | 100 | 184018 | 155782.5 | 1.28669336192022 |
| TB4.0 | xai/grok-4.6 | grok-build | 2026-08-12 | 330 | total_reasoning_tokens | 330 | 100 | 330 | 100 | 45579 | 76385 | 0.608821172310565 |


### AR. Consolidated outdated-number ledger

This table collects the outdated numerical claims. R23 and R35 have complete cell-by-cell ledgers immediately below; source exactness and population qualifications remain those of the R-register. Rounded changes are computed before rounding endpoints.

| Revision | Claim / location | Manuscript number or wording | Authoritative replacement | Evidence key / exact selector |
|---|---|---|---|---|
| R07 | Shell paired row | +.50; dz-.006; p.398 | +.375; dz-.0136526800336146; p.4385568751433467; W1496; n86 | S2 shell_invocation_count |
| R09 | Shell fixed-bin peak | 39.69% | 39.68% | S3 shell_invocation_count,16-40 |
| R12 | RQ2 difficulty pass rates | 71.3/43.2/19.9% | 73.9/46.5/22.1% (URL units) | S6 difficulty pass_rate |
| R12 | Difficulty rho | -.48,p<.001 | -0.4877929115830032; display -.49,p<.001 | S6 rq2_1_difficulty_significance |
| R13 | Hard resource medians | 408813 tokens;719s;$.34 | 407300.5 tokens;688.95625s;$.3695658125 | S6 difficulty effort median |
| R13 | Easy resource medians | 167730 tokens;256s;$.16 | 151973.25 tokens;253.296s;$.18828898125 | S6 difficulty effort median |
| R14 | Category pass rates | data-proc58.1;sysadmin45.4;debug44.0;security40.4;math25.3;fileops21.3% | 61.1;47.6;48.8;44.3;28.6;23.7% | S6 category pass_rate |
| R15 | Single-task category pass rates | personal88.2;optimization79.7;games11.2% | 89.9;83.7;13.5% | S6 category pass_rate |
| R15 | Hard video-processing cell | .02 | .029090909...; display .03 | S6 category_difficulty |
| R16 | ML resource medians | 26steps;~363000tokens;482s | 27steps;327565.75tokens;587.6485s | S6 category effort |
| R16 | Mathematics resource medians | $.325;~315000tokens | $.478124159375;409170tokens | S6 category effort |
| R17 | Gemini model category rates | security77.6;math84.4;training74.6;scientific62.6% | 76.7;85.0;74.2;65.4% | S6 model_category_pass_rates |
| R20 | Agent time median | 7.11min | 7.02420833333333min; display7.02 | S8 median_agent_duration_min |
| R28 | TB3 paired performance test | dz.908;p1.80e-8 | .924091442153001;p1.2224394185128e-8;W164;n66 | S10 3.0->4.0 |
| R28 | TB3 instruction comparison | .183;p.344 | .208264462809917;p.282141395128863;U365.5;n11/55 | S11 3.0->4.0 |
| R29 | Alternative Sonnet validation | 13/22=59.1% | stored17/22=77.3%; equivalent neutralization unverified | S12 _sonnet5_summary |
| R30 | Broad-category labeling protocol | same complete3-LLM protocol | 2valid votes/task;89Anthropic failures;22recorded ties;historical final labels | S13 all89 category-cache vote arrays |
| R31 | Easy longitudinal pass rates/gain | 70.53->92.50%;+21.97pp | 71.30->92.65%;+21.35pp | S14 effective rates |
| R31 | Medium longitudinal pass rates/gain | 42.41->79.56%;+37.15pp | 43.23->79.55%;+36.32pp | S14 effective rates |
| R31 | Hard longitudinal pass rates/gain | 19.11->64.58%;+45.47pp | 19.90->64.53%;+44.63pp | S14 effective rates |
| R31 | Gap closure easy/medium/hard | 74.5/64.5/56.2% | 74.4/64.0/55.7% | (new-old)/(1-old) from S14 |
| R32 | ML category change | 31.1->88.6%;+57.5pp | 32.1->88.6%;+56.6pp | S10 category_old=machine-learning,3tasks |
| R32 | Data-science category change | 29.4->83.2%;+53.8pp | 30.5->83.3%;+52.8pp | S10 category_old=data-science,8tasks |
| R32 | Mathematics category change | 23.4->75.9%;+52.5pp | 25.3->75.9%;+50.6pp | S10 category_old=mathematics,4tasks |
| R32 | Media longitudinal change | 15.4->64.0% | 16.0->63.9% | S10 seven S7 media task IDs |
| R32 | Extract moves from video TB2.1 | 14.8% | 14.7058823529412%; display14.7% | S10 task extract-moves-from-video |
| R33 | TB3 full-task duration | 33.2min | 32.8711446041667min; display32.9 | S13 version summary,74tasks |
| R36 | TB3/TB4 pooled tokens | -34.4% | -34.2884608540407%; display-34.3% | S15 positive tokens |
| R37 | Matched token configuration count increasing | all7/every matched | 6of7;Fable5 decreases4.96783049%;GLM65shared tasks | S17 all7rows |
| R38 | Gemini/Terminus TB2.1 chars per token | .49 | .484715948460075; display.48 | S15 source TB2.1 rows;420positive-token records |
| R53 | Difficulty figure estimand | version difficulty pass rates | current filename is monthly submission plot; change caption or asset | Section5 figure map |

### AS. R23 complete behavior-table cell comparison

Source S9. Original manuscript columns use the displayed precision; current values are exact to the shown serialization.

| Behavior key | Old use% | Current use% | Old mean pp | Current mean pp | Old dz | Current dz | Old p | Current p | Tasks |
|---|---|---|---|---|---|---|---|---|---|
| inspect_search | 88.4 | 88.4159084332701 | 9.5 | 9.45880518529176 | 0.784 | 0.778820841034282 | 3.19e-10 | 3.75378279020056e-10 | 89 |
| modify_write | 77.2 | 77.269073722792 | 5.7 | 5.69940287851562 | 0.51 | 0.509762368150349 | 7.25e-6 | 7.53903690429346e-06 | 89 |
| execute_run | 61 | 61.080924669646 | 7.7 | 7.68400808353825 | 0.521 | 0.520018018023822 | 1.26e-6 | 1.08416266526348e-06 | 89 |
| test_validate | 12 | 11.9731215638363 | 7.8 | 7.5644015821082 | 0.498 | 0.487193226297958 | 1.65e-5 | 1.9661936820094e-05 | 82 |
| environment_dependencies | 37.3 | 37.3050831109539 | 2.3 | 2.34531755902264 | 0.12 | 0.120179250165995 | .183 | 0.182744793221064 | 80 |
| version_control | 10.6 | 10.6484904993087 | -2.3 | -2.32280336447623 | -0.12 | -0.121237497910023 | .489 | 0.489353799814439 | 50 |
| data_query_transform | 4 | 4.03176542455711 | -3.7 | -3.74685000035107 | -0.183 | -0.182873001217972 | .635 | 0.635498046875 | 13 |
| network_external | 10.1 | 10.1437160402534 | -2.4 | -2.40466146612518 | -0.1 | -0.100335294875725 | .228 | 0.227676364065947 | 48 |
| media_specialized | 2.2 | 2.2280808925184 | 2.1 | 2.00270621895448 | 0.101 | 0.0983193069017182 | .622 | 0.6220703125 | 12 |

### AT. R35 complete inferential-table cell comparison

Source S16; n refers to eligible shared task pairs, not trajectories. All ten unadjusted p-values remain below .05.

| Transition | Metric | Manuscript dz | Current dz | Manuscript p | Current p | Current W | Tasks |
|---|---|---|---|---|---|---|---|
| 2.0->2.1 | steps | -0.268 | -0.312894294590428 | 7.88e-4 | 0.0008894960251363 | 1129 | 89 |
| 2.0->2.1 | shell_invocations | -0.508 | -0.523732786307623 | 2.52e-6 | 1.17878798894363e-06 | 766.5 | 89 |
| 2.0->2.1 | tool_calls | -0.389 | -0.416884082869444 | 1.50e-5 | 3.05129357974193e-05 | 929 | 89 |
| 2.0->2.1 | duration | -0.111 | -0.138539991859674 | 1.96e-2 | 0.0047272862787149 | 1312 | 89 |
| 2.0->2.1 | total_tokens | 0.332 | 0.296637884270165 | 3.82e-5 | 0.0001604978226435 | 1080 | 89 |
| 3.0->4.0 | steps | -0.461 | -0.360437750179541 | 1.41e-6 | 1.07399284511201e-05 | 416.5 | 66 |
| 3.0->4.0 | shell_invocations | -0.269 | -0.133782953046193 | 5.32e-5 | 0.0067471947016407 | 658 | 66 |
| 3.0->4.0 | tool_calls | -0.516 | -0.398661323780061 | 2.57e-6 | 1.91774224839954e-05 | 418.5 | 66 |
| 3.0->4.0 | duration | -0.439 | -0.499867409459178 | 2.69e-8 | 4.15420432053502e-08 | 247 | 66 |
| 3.0->4.0 | total_tokens | -0.642 | -0.510942476520215 | 1.39e-7 | 2.97003238263667e-06 | 374 | 66 |

### AU. Complete unverified-number / provenance ledger

UNVERIFIED means insufficient evidence for the claim as stated, not evidence that every constituent number is false. No new analyses were run to fill these gaps.

| Revision | Current numbers or claim | Evidence limit | Safe replacement |
|---|---|---|---|
| R19 | Tag pass rates55.5/50.6/46.7%;requirement49.5/44.9/43.1% | No retained current outcome table; no numeric replacement | Use supported media-only table |
| R22 | Interface95.8/23.6/6.5/.5%;search raw+12.7pp | No retained pooled interface summary | Use qualitative interface paragraph |
| R24 | Inspection difficulty+17.2/+10.1/+7.3pp | Current figure supports whole-pp approximations only | Approximately+17/+10/+7pp;no subgroup significance |
| R26 | 22/67 as reproducible changed/unchanged instruction groups | Stored counts/hash equalities verified; original provenance incomplete | Retain as stored sensitivity partition with limitation |
| R39 | TB2 reasoning432/78.5%;434/70.9%;60/435;Muse56.1%,.20->.48 | Configuration Ns partly retained; comparable reasoning accounting not retained | No share replacement; use qualitative caveat |
| R40 | Tool elision5000ends;.170->.174;.053->.056;64.3% | No retained corpus adjustment/result definition | Omit exact elision corrections |
| R41 | Tokenizer30%;shares6.9/30.4%;divide1.3;2.%/6.6% | No retained mapping/sensitivity; cited entry not supplied | Do not guess missing digit in2.% |
| R42 | TB4 completeness2304/2309;Gemini64.3%;adjusted ratios.0103->.0104,.0407->.0431 | 2309across7groups and Sonnet78.0%/329supported; completeness/adjusted ratios not | Use scoped Sonnet example; no adjusted-ratio replacement |
| R43 | Collection June18/July21/September15 2026 | Source fields record submission dates, not collection events | Keep only with independent author provenance or omit dates |
| R44 | Completed manual one-per12scaffold common-task review | 24prepared records/12scaffolds; no completed review status | Describe prepared sample |
| R45 | Provider release dates/reasoning defaults;GPT5.5 tenth of submissions | Not established by submission timestamps/model names | Use recorded May-July population range only |
| R46 | Largest-to-date;prior-work200/300/3843/1794/64380/50tasks | External citation-dependent; bibliography not supplied | Own48843verified; omit priority or check citations |
| R54 | April2026 industry timing;millions of tokens anecdote | External citation-dependent, not repository evidence | Use generic accounting implications or verify bibliography |

### AV. Exact model/category marginal estimates and support

Source S6 `category/model_scaffold/model_category_pass_rates.csv`; `n_submission_task_combinations` uses URL units within the model group. These are model margins, not fixed joint configurations.

| model_dir | category | n_tasks | n_submission_task_combinations | n_trajectories | pass_count | fail_count | pass_rate | trajectory_pooled_pass_rate | trajectory_pooled_task_mean_pass_rate |
|---|---|---|---|---|---|---|---|---|---|
| claude-opus-4-6 | debugging | 5 | 20 | 88 | 84 | 4 | 0.96 | 0.954545454545455 | 0.955417956656347 |
| claude-opus-4-6 | mathematics | 4 | 16 | 70 | 44 | 26 | 0.65625 | 0.628571428571429 | 0.630659829721362 |
| claude-opus-4-6 | model-training | 4 | 15 | 65 | 33 | 32 | 0.538541666666667 | 0.507692307692308 | 0.533625730994152 |
| claude-opus-4-6 | scientific-computing | 8 | 32 | 142 | 74 | 68 | 0.521875 | 0.52112676056338 | 0.522702205882353 |
| claude-opus-4-6 | security | 8 | 32 | 144 | 111 | 33 | 0.7875 | 0.770833333333333 | 0.770424836601307 |
| claude-opus-4-6 | system-administration | 9 | 36 | 163 | 107 | 56 | 0.649537037037037 | 0.656441717791411 | 0.650422352176738 |
| gemini-3.1-pro-preview | debugging | 5 | 15 | 61 | 55 | 6 | 0.901111111111111 | 0.901639344262295 | 0.9 |
| gemini-3.1-pro-preview | mathematics | 4 | 12 | 47 | 38 | 9 | 0.85 | 0.808510638297872 | 0.795454545454545 |
| gemini-3.1-pro-preview | model-training | 4 | 11 | 45 | 33 | 12 | 0.741666666666667 | 0.733333333333333 | 0.745833333333333 |
| gemini-3.1-pro-preview | scientific-computing | 8 | 22 | 91 | 61 | 30 | 0.654166666666667 | 0.67032967032967 | 0.643181818181818 |
| gemini-3.1-pro-preview | security | 8 | 23 | 89 | 68 | 21 | 0.766666666666667 | 0.764044943820225 | 0.753685897435897 |
| gemini-3.1-pro-preview | system-administration | 9 | 26 | 106 | 74 | 32 | 0.685185185185185 | 0.69811320754717 | 0.681361231361231 |

Current hard-category examples (same S6 source family):

| category | difficulty | n_tasks | n_submission_task_combinations | n_trajectories | pass_count | fail_count | pass_rate | trajectory_pooled_pass_rate | trajectory_pooled_task_mean_pass_rate |
|---|---|---|---|---|---|---|---|---|---|
| file-operations | hard | 1 | 54 | 342 | 10 | 332 | 0.0432098765432098 | 0.0292397660818713 | 0.0292397660818713 |
| model-training | hard | 1 | 55 | 338 | 7 | 331 | 0.019090909090909 | 0.0207100591715976 | 0.0207100591715976 |
| video-processing | hard | 1 | 55 | 350 | 8 | 342 | 0.029090909090909 | 0.0228571428571428 | 0.0228571428571428 |

### AW. Exact longitudinal category means quoted in R32

Source S10 adjacent table, equal arithmetic means of the named category task rows for transition 2.0->2.1; descriptive, effective IDs.

| Category | Tasks | TB2.0% | TB2.1% | Change pp |
|---|---|---|---|---|
| machine-learning | 3 | 32.0752601916985 | 88.6274509803922 | 56.5521907886936 |
| data-science | 8 | 30.547301368149 | 83.3088235294118 | 52.7615221612628 |
| mathematics | 4 | 25.304054054054 | 75.8823529411765 | 50.5782988871224 |

### AX. Shared-task trajectory populations and historical source caveats

The 89 TB2 shared tasks cover 31,103/7,501 retained (binary) trajectories. The 66 TB3/TB4 shared tasks cover 3,879/5,902 retained trajectories, 3,873/5,902 binary trajectories, and 3,510/5,902 positive-token trajectories. The 6 shared fractional TB3 records are kv-live-surgery; the 52 erp-procurement-planning fractional records lie outside the shared task pool. These are processed-row counts, not new analysis outputs. Pairwise missingness is applied before inference.

S19 uses raw model_name and its older extraction: it reports 53 TB2 raw names rather than 33 normalized components, and its TB3pooled pass rate .22342633156559835 uses 969/4,337 retained records rather than 969/4,279 binary records (.22645477915400794). Its old pooled token medians are 206,147 (TB2.0), 281,590 (TB2.1), 8,028,088.5 (TB3.0), and 5,299,037 (TB4.0). These are valid provenance clues to a different diagnostic pipeline, not primary replacements for refreshed positive-token medians or binary pass rates.


### AY. Optional complete curvature table if the commented table is restored

This is not required by the active manuscript, which reports the four significant fits in prose. Source S4; the shell coefficient and p-value are refreshed. Model standard errors and sample sizes are in Appendix F.

```latex
\begin{table}[tb]
    \centering
    \caption{Quadratic coefficients ($\beta_2$) from task-stratified conditional logistic regression; two-sided cluster-robust Wald tests.}
    \label{tab:rq1-curvature}
    \begin{tabular}{lrr}
        \hline
        Metric & $\beta_2$ & $p$\\
        \hline
        Steps & $-0.425$ & $0.0028$ \\
        Shell invocations & $-0.293$ & $0.1100$ \\
        Tool calls & $-0.250$ & $0.2424$ \\
        Total tokens & $-0.341$ & $0.0102$ \\
        Duration & $-0.486$ & $0.0019$ \\
        Cost & $-0.289$ & $0.0254$ \\
        \hline
    \end{tabular}
\end{table}
```


Read-only source/filter checks also confirmed that the saved RQ1.2 total-token fixed-bin counts sum to 30,126, matching the positive-token filter in `01_plot_diminishing_returns.py::load_data`; reported zero totals are excluded from these bins. The raw RQ1.1 pooled token table remains a separate 30,581-record nonmissing summary.

## 10. Audit totals and completion summary

The register contains **102 claim groups**: **48 VERIFIED — correct**, **22 UPDATE REQUIRED — incorrect or outdated**, **19 WORDING CHANGE**, and **13 UNVERIFIED**. This is a transparent count of the 48 V-register entries and 54 R-register entries, not a count of independent tests, digits, or every repeated literal.

Interpretations requiring revision occur in the abstract/introduction, RQ1 measurement and aggregation wording, RQ2 category/rate/behavior discussion, RQ3 instruction and label provenance, RQ3 paired inference versus pooled descriptions, and the discussion, implications, threats, and conclusion. No primary inferential direction or significance classification reverses. The main narrative correction is six-of-seven matched token increases with composition sensitivity rather than a universal or causal claim.

Replace the four active numerical tables identified in Section 5 and clarify the metric-definition table. Refresh the RQ2 assets and pooled RQ3 assets listed there; correct the monthly difficulty caption or select its explicitly identified version-level alternative. Retain the current RQ1 token distribution, bin composite, and token Pareto assets with population qualifiers. Actual Overleaf image bytes were unavailable for hash comparison.

Unresolved evidence remains for the original TB2 instruction-audit construction, historical category tie resolution, comparable Sonnet-panel neutralization, unretained tag/interface and detailed reasoning/elision/tokenizer diagnostics, collection/manual-review provenance, and external citation-dependent claims. Authoritative replacements are supplied wherever current outputs support them; conservative text is supplied elsewhere. No missing value was filled by speculation.

**Report path:** `reports/manuscript_repository_consistency_20261019.md`

Final read-only validation checked 18 explicitly referenced PNGs for file integrity, balanced Markdown fences and LaTeX environment pairs, unchanged HEAD, and an empty tracked Git diff. Only this report appears as a new untracked file. These checks did not regenerate or modify any analysis artifact.

**Repository state:** requested commit retained; no tracked source/data/output/figure/README/manuscript changes, no regenerated analysis outputs, no commit, and no push. This report is the sole new repository file.
