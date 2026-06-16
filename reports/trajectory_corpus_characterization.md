# TerminalBench Trajectory Corpus Characterization

Generated on 2026-06-14 from the current local leaderboard trajectory corpus. This report characterizes the available trajectory data for phase-taxonomy, stratified sampling, and annotation-methodology design. It does not propose a final phase taxonomy.

## Data Sources

The current trajectory corpus is stored under:

```text
data/trajectories/current_leaderboard/
```

Trajectory files are nested by scaffold and model:

```text
data/trajectories/current_leaderboard/{scaffold}/{model}/{task_checksum}_{trial_id}.json
```

The current leaderboard and reward index are:

```text
data/raw/leaderboard_submissions_current.json
data/indexes/trajectory_trials_current.json
```

The summary tables used for this report are the current `processed_live` outputs:

```text
data/processed_live/trajectory_summary.csv
data/processed_live/trajectory_outcome_by_scaffold_model.csv
data/processed_live/trajectory_features_by_outcome.csv
data/processed_live/command_patterns.csv
data/processed_live/corpus_stats.json
```

## Dataset Overview

- Trajectories: 31,103.
- Unique task checksums in the local trajectory corpus: 89.
- Current leaderboard submissions: 142.
- Leaderboard scaffold/model/task cells: 12,638.
- Scaffold/model trajectory groups: 73.
- Scaffolds represented in local trajectories: 12.

The corpus is now much broader than the earlier balanced 12-submission sample. It includes current leaderboard trajectories from `terminus-2`, `mini-swe-agent`, `openhands`, `claude-code`, `codex`, `gemini-cli`, `terminus-3-3`, `terminus-kira-env-bootstrap`, `nexau`, `hookele`, `deepagent-harbor`, and `judy`.

## Trajectory Schema

All trajectories are JSON files. The common normalized envelope is ATIF-like:

```json
{
  "schema_version": "ATIF-v1.2",
  "session_id": "...",
  "agent": {
    "name": "...",
    "version": "...",
    "model_name": "...",
    "extra": {}
  },
  "steps": [],
  "final_metrics": {}
}
```

Observed top-level fields:

| Field | Files |
|---|---:|
| `schema_version` | 31,103 |
| `session_id` | 31,103 |
| `agent` | 31,103 |
| `steps` | 31,103 |
| `final_metrics` | 31,094 |
| `notes` | 5,610 |

Common step fields remain scaffold-dependent:

- `steps[].step_id`
- `steps[].timestamp`
- `steps[].source`
- `steps[].message`
- `steps[].reasoning_content` in some scaffolds/models.
- `steps[].tool_calls` in agent/tool steps.
- `steps[].observation.results[].content` for stdout, stderr, or tool output.
- `steps[].metrics` with token/cost data in many steps.

Scaffold-specific tool payload variation matters for annotation:

- `mini-swe-agent` often stores shell actions as fenced bash or `bash_command` calls and accounts for the `notes` top-level field.
- `terminus-2` and `terminus-3-3` use terminal-like command streams, sometimes including keystroke/control events such as `C-c`.
- `openhands` heavily uses editor-like operations such as `view`, `str_replace`, and `create`.
- `claude-code`, `codex`, and `gemini-cli` more often expose shell commands and file-edit tool calls.
- `hookele`, `nexau`, `judy`, and `deepagent-harbor` are smaller but high-performing trajectory subsets with distinct orchestration patterns.

## Key Statistics

Scaffold coverage:

| Scaffold | Trajectories |
|---|---:|
| `terminus-2` | 12,739 |
| `mini-swe-agent` | 5,610 |
| `openhands` | 5,190 |
| `claude-code` | 2,522 |
| `codex` | 1,242 |
| `gemini-cli` | 1,221 |
| `terminus-3-3` | 678 |
| `terminus-kira-env-bootstrap` | 444 |
| `nexau` | 443 |
| `hookele` | 431 |
| `deepagent-harbor` | 417 |
| `judy` | 166 |

Largest scaffold/model directories:

| Scaffold/model directory | Trajectories |
|---|---:|
| `terminus-2/openai_gpt-oss-20b` | 466 |
| `terminus-2/Qwen_Qwen3-Coder-480B-A35B-Instruct-FP8` | 464 |
| `terminus-2/moonshotai_Kimi-K2-Instruct-0905` | 462 |
| `terminus-2/openai_gpt-oss-120b` | 462 |
| `terminus-2/accounts_fireworks_models_glm-4p6` | 452 |
| `terminus-2/accounts_fireworks_models_minimax-m2` | 451 |
| `terminus-2/moonshotai_Kimi-K2-Thinking` | 446 |
| `terminus-2/claude-opus-4-5-20251101` | 445 |
| `terminus-2/claude-opus-4-6` | 445 |
| `terminus-2/gemini-3-pro-preview` | 445 |
| `terminus-2/gpt-5.1` | 445 |
| `terminus-2/gpt-5.1-codex` | 445 |
| `terminus-2/grok-code-fast-1` | 445 |
| `terminus-2/gemini-3-flash-preview` | 444 |
| `terminus-kira-env-bootstrap/claude-opus-4-6` | 444 |

Trajectory-level reward labels for stratification:

- Per-run outcome is joined from `data/indexes/trajectory_trials_current.json`.
- `reward == 1.0` is treated as pass; `reward == 0.0` is treated as fail for trajectory-level stratification.
- The current index contains 31,103 matched trajectory rewards.
- Passes: 11,219.
- Failures: 19,884.
- Missing reward values: 0.

Reward-label coverage by scaffold:

These counts describe the local downloaded trajectory corpus. They are not leaderboard accuracies and should not be used to rank scaffolds.

| Scaffold | Local trajectories | Reward pass | Reward fail |
|---|---:|---:|---:|
| `terminus-2` | 12,739 | 4,424 | 8,315 |
| `mini-swe-agent` | 5,610 | 1,439 | 4,171 |
| `openhands` | 5,190 | 1,513 | 3,677 |
| `claude-code` | 2,522 | 1,099 | 1,423 |
| `codex` | 1,242 | 406 | 836 |
| `gemini-cli` | 1,221 | 418 | 803 |
| `terminus-3-3` | 678 | 506 | 172 |
| `terminus-kira-env-bootstrap` | 444 | 340 | 104 |
| `nexau` | 443 | 376 | 67 |
| `hookele` | 431 | 272 | 159 |
| `deepagent-harbor` | 417 | 284 | 133 |
| `judy` | 166 | 142 | 24 |

Official top local scaffold/model groups with reward-label coverage:

This table is ordered by scraped official leaderboard rank and accuracy. Reward counts are shown only to describe the local trajectory subset available for qualitative inspection.

| Official rank | Scaffold/model directory | Official accuracy | Local trajectories | Reward pass | Reward fail |
|---:|---|---:|---:|---:|---:|
| 1 | `nexau/gpt-5.5` | 84.7% | 443 | 376 | 67 |
| 7 | `judy/gemini-3.1-pro-preview` | 80.2% | 166 | 142 | 24 |
| 11 | `terminus-kira-env-bootstrap/claude-opus-4-6` | 76.4% | 444 | 340 | 104 |
| 16 | `terminus-3-3/gemini-3.1-pro-preview` | 74.8% | 431 | 320 | 111 |
| 17 | `terminus-3-3/claude-opus-4-6` | 74.7% | 247 | 186 | 61 |
| 27 | `deepagent-harbor/gpt-5.2-codex` | 66.5% | 417 | 284 | 133 |
| 36 | `terminus-2/claude-opus-4-6` | 62.9% | 445 | 280 | 165 |
| 39 | `hookele/gpt-5.1-codex-mini` | 61.6% | 431 | 272 | 159 |
| 40 | `gemini-cli/gemini-3.1-pro-preview` | 61.4% | 434 | 265 | 169 |
| 50 | `claude-code/claude-opus-4-6` | 58.0% | 435 | 258 | 177 |
| 52 | `terminus-2/claude-opus-4-5-20251101` | 57.8% | 445 | 257 | 188 |
| 54 | `terminus-2/gemini-3-pro-preview` | 56.9% | 445 | 253 | 192 |
| 57 | `terminus-2/gpt-5.2` | 54.0% | 443 | 239 | 204 |
| 60 | `terminus-2/glm-5` | 52.4% | 376 | 211 | 165 |

Length and resource distributions:

| Measure | Count | Min | P25 | Median | Mean | P75 | P90 | P95 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `step_count` | 31,103 | 1 | 10 | 21 | 47.1 | 46 | 90 | 137 | 3,006 |
| extracted command/tool-command count | 31,103 | 0 | 0 | 2 | 18.1 | 19 | 52 | 84 | 1,000 |
| `tool_call_count` | 31,103 | 0 | 10 | 23 | 40.4 | 49 | 91 | 129 | 1,654 |
| `total_tokens` | 30,581 | 0 | 52,289 | 206,147 | 1,059,878 | 746,842 | 2,224,359 | 4,259,402 | 244,237,325 |
| `cost_usd` where present | 28,944 | 0.0 | 0.0 | 0.0533 | 0.543 | 0.366 | 1.166 | 2.217 | 83.798 |
| duration from timestamps, seconds | 31,084 | 0.000015 | 50.39 | 211.76 | 441.92 | 617.65 | 1079.38 | 1732.06 | 11998.16 |

Passed trajectories are generally shorter than failed trajectories in this corpus. Median `step_count` is 19 for passes and 22 for failures, while the means are 30.9 and 56.3 respectively. The same pattern appears in commands, tool calls, tokens, cost, and duration: failures contain a long tail of repair or retry loops.

Outcome feature summary:

| Outcome | Trajectories | Median steps | Mean steps | Median commands | Mean commands | Median tool calls | Mean tool calls | Median tokens | Mean tokens | Median sec. | Mean sec. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pass | 11,219 | 19 | 30.9 | 2 | 13.3 | 22 | 31.1 | 166,391 | 571,946 | 188.8 | 318.0 |
| fail | 19,884 | 22 | 56.3 | 2 | 20.9 | 25 | 45.6 | 239,455 | 1,327,654 | 238.1 | 511.9 |

## Command And Tool Pattern Candidates

The command/tool extraction intentionally treats these as candidates for later annotation, not final labels. Editor commands and scaffold control actions dominate the raw command-head counts.

Most common command heads or tool-command names:

| Rank | Count | Head/tool | Candidate purpose | Example |
|---:|---:|---|---|---|
| 1 | 37,174 | `str_replace` | other/editor operation | `str_replace` |
| 2 | 26,462 | `view` | other/editor operation | `view` |
| 3 | 15,438 | `create` | other/editor operation | `create` |
| 4 | 13,954 | `plan` | other/orchestration | `plan` |
| 5 | 6,728 | `C-c` | other/control event | `C-c` |
| 6 | 4,639 | `echo` | final verification | `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` |
| 7 | 3,830 | `python3` | running scripts/tests | `python3 << 'EOF'` |
| 8 | 3,760 | `python3` | running scripts/tests | `python3 -c ...` |
| 9 | 3,692 | `python3` | editing/writing files | `python3 - <<'PY'` |
| 10 | 2,907 | `python3` | editing/writing files | `python3 - << 'PY'` |
| 12 | 1,830 | `cat` | editing/writing files | `cat <<'EOF' > my_warrior.red` |
| 17 | 1,349 | `ls` | environment inspection | `ls -la /app` |
| 21 | 1,128 | `python3` | running scripts/tests | `python3 /app/eval.py` |
| 24 | 880 | `pwd` | environment inspection | `pwd && ls -la` |
| 31 | 739 | `pdflatex` | other/domain command | `pdflatex main.tex` |

Purpose counts from heuristic grouping:

| Candidate purpose | Count |
|---|---:|
| `other` | 201,296 |
| `editing_writing_files` | 86,731 |
| `reading_files` | 71,740 |
| `running_scripts_tests` | 43,445 |
| `environment_inspection` | 38,715 |
| `file_content_search` | 36,212 |
| `debugging_diagnostics` | 29,930 |
| `final_verification` | 28,581 |
| `dependency_setup` | 26,814 |
| `unknown` | 168 |

## Likely Task Families

The following families are heuristic and should seed stratification, not serve as definitive task-type labels.

| Task-family hint | Trajectories |
|---|---:|
| `shell/filesystem` | 13,609 |
| `unclassified_from_available_text` | 9,846 |
| `python/data` | 6,382 |
| `build/test` | 4,004 |
| `ml/math` | 3,213 |
| `web/api` | 2,694 |
| `database` | 1,420 |
| `polyglot/compiler` | 1,338 |
| `security/crypto` | 1,247 |

## Annotation Implications

The current corpus is large enough to support both broad quantitative summaries and targeted qualitative annotation. The old balanced 12-submission sample is still useful as a pilot design, but it no longer represents the current local corpus.

Recommended pilot sampling strategy:

- Use a stratified pilot of roughly 120 trajectories, or 72 if annotation time is tight.
- Stratify by scaffold, reward outcome, and coarse task-family hint.
- Oversample smaller high-performing scaffolds such as `judy`, `nexau`, `terminus-kira-env-bootstrap`, `terminus-3-3`, `deepagent-harbor`, and `hookele` so their workflows are not drowned out by `terminus-2`, `mini-swe-agent`, and `openhands`.
- Include long-tail failures from the upper step/token/duration quantiles because they likely contain the richest recovery, debugging, and loop-collapse behavior.
- Include a separate ambiguity-enriched slice from `data/processed_live/representative_snippets.jsonl` and repeated-command cases.

Do not use leaderboard aggregate accuracy as a trajectory pass/fail label. Use `reward_outcome` from `data/indexes/trajectory_trials_current.json` for per-run success/failure and treat leaderboard accuracy or task resolution rate as aggregate covariates.

## Annotation Export Metadata

A step-level annotation export should include at least:

- Identifiers: `rel_path`, `session_id`, `schema_version`, `file_task_id`, `file_run_id`, `task_id`, and task name fields where available.
- Agent context: `scaffold`, `model_dir`, `agent.name`, `agent.version`, `agent.model_name`, and leaderboard display/model labels.
- Outcome: `reward`, `reward_outcome`, and any validation notes.
- Step structure: `step_id`, timestamp, source/role, message text, reasoning text if present, tool-call names and arguments, observations, and per-step metrics.
- Derived features: step index, command head, command purpose candidate, character counts, token/cost fields, duration deltas, and repeated-action flags.
- Aggregate covariates: scraped leaderboard accuracy, task-level resolution rate, task family hint, and local trajectory coverage bin.

The current `data/processed_live/trajectory_summary.csv` already contains a trajectory-level subset of these fields. A later step-level export should be produced before manual annotation.

## Reproducible Commands

From the repository root:

```powershell
cd TerminalBenchAnalysis
```

Refresh the current corpus summary tables:

```powershell
python -m scripts.analysis.characterize_trajectories `
  --root data\trajectories\current_leaderboard `
  --leaderboard data\raw\leaderboard_submissions_current.json `
  --trajectory-index data\indexes\trajectory_trials_current.json `
  --out data\processed_live
```

Regenerate the current leaderboard-level report:

```powershell
python -m scripts.analysis.analyze_leaderboard_superficial `
  --input data\processed_live\leaderboard_submission_summary.csv `
  --trajectory-summary data\processed_live\trajectory_summary.csv `
  --out data\processed_live `
  --report reports\leaderboard_superficial_analysis.md
```

Inspect generated trajectory summary:

```powershell
Get-Content data\processed_live\trajectory_summary.csv -TotalCount 6
```

Inspect command-pattern candidates:

```powershell
Get-Content data\processed_live\command_patterns.csv -TotalCount 40
```

## Risks For Annotation Validity

- Scaffold/action schemas differ strongly; phase labels must be defined at a behavioral level rather than as exact tool names.
- `other` is a large heuristic bucket because editor operations, orchestration steps, domain tools, and terminal-control events are not yet separated cleanly.
- Current local coverage is not a randomized leaderboard sample. Large scaffolds such as `terminus-2`, `mini-swe-agent`, and `openhands` dominate the trajectory count.
- Some high-performing scaffolds have only a few hundred local trajectories, so they require deliberate oversampling for qualitative work.
- Resource metrics are unevenly available: total tokens are present for 30,581 trajectories, timestamp-derived duration for 31,084, and cost for 28,944.
- Very large token and step outliers can dominate means; medians and quantile bins are safer descriptive summaries.
- Task-family hints are incomplete and should be treated as weak labels until validated manually.
