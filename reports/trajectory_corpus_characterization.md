# TerminalBench Trajectory Corpus Characterization

Generated on 2026-06-04 from the local workspace. This report characterizes the available trajectory corpus to support later phase-taxonomy and annotation-methodology design. It does not propose a final phase taxonomy.

## Dataset Overview

The primary trajectory corpus is stored under:

```text
data/trajectories/balanced_12/
```

The corpus contains JSON files nested by scaffold and model:

```text
data/trajectories/balanced_12/{scaffold}/{model}/{task_checksum}_{run_uuid}.json
```

Example active-file path:

```text
data/trajectories/balanced_12/mini-swe-agent/gemini-2.5-pro/0ddf1db011f2f37709b0fc536f67a3f4261ce5cae69613969f017f365c25ac94_3bd68e39-3bd5-4c21-8cd1-fc82865879f2.json
```

A nearby metadata file exists:

```text
data/raw/leaderboard_v2.json
```

This leaderboard file provides aggregate task/scaffold/model fields such as `taskName`, `taskChecksum`, `nTrials`, `avgResolutionRate`, and `successCount`. The trajectory JSON files themselves do not expose per-run pass/fail fields, but the companion index `data/indexes/trajectory_index_balanced_12.json` provides validated per-run `reward` labels for the local balanced sample.

Reproduction command:

```powershell
python scripts/characterize_trajectories.py
```

Generated artifacts:

- `data/processed/corpus_stats.json`
- `data/processed/trajectory_summary.csv`
- `data/processed/trajectory_outcome_by_scaffold_model.csv`
- `data/processed/trajectory_features_by_outcome.csv`
- `data/processed/command_patterns.csv`
- `data/processed/representative_snippets.jsonl`

## Trajectory Schema

All 5,265 trajectories are JSON. The common normalized envelope is ATIF-like:

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

- `schema_version`: present in 5,265 files.
- `session_id`: present in 5,265 files.
- `agent`: present in 5,265 files.
- `steps`: present in 5,265 files.
- `final_metrics`: present in 5,265 files.
- `notes`: present in 1,288 files, mostly converted `mini-swe-agent` trajectories.

Common step fields:

- `steps[].step_id`
- `steps[].timestamp`
- `steps[].source`
- `steps[].message`
- `steps[].reasoning_content` in some scaffolds/models.
- `steps[].tool_calls` in agent/tool steps.
- `steps[].observation.results[].content` for stdout/stderr/tool output.
- `steps[].metrics` with token/cost data in many steps.

Common metric fields:

- `final_metrics.total_prompt_tokens`: 5,265 trajectories.
- `final_metrics.total_completion_tokens`: 5,265 trajectories.
- `final_metrics.total_cached_tokens`: 4,686 trajectories.
- `final_metrics.total_cost_usd`: 3,065 trajectories.
- `final_metrics.total_steps`: 1,747 trajectories.
- `final_metrics.extra.total_reasoning_tokens`: 869 trajectories.

Scaffold-specific tool payload variation matters for annotation:

- `mini-swe-agent` often has `function_name: "bash_command"` with `arguments.command` and agent messages containing `THOUGHT` plus fenced bash.
- `terminus-2` uses `function_name: "bash_command"` with `arguments.keystrokes`, reflecting terminal keystroke batches.
- `vix` uses tool names such as `bash` and `read_file`, with `arguments.command`, `arguments.path`, and `arguments.reason`.
- `openhands` uses `str_replace_editor` and commands such as `view`, `str_replace`, and `create`.
- `claude-code` includes Bash tool calls and editor-like tool calls, with observations containing tool-use IDs and stdout/stderr-like content.

## Key Statistics

Corpus size:

- Trajectories: 5,265.
- Unique task IDs inferred from filenames and metadata: 218.
- Leaderboard task checksums available: 89.
- Leaderboard scaffold/model/task cells: 12,104.

Scaffolds:

| Scaffold | Trajectories |
|---|---:|
| `terminus-2` | 1,362 |
| `mini-swe-agent` | 1,288 |
| `claude-code` | 876 |
| `openhands` | 868 |
| `vix` | 440 |
| `hookele` | 431 |

Scaffold/model combinations:

| Scaffold/model directory | Trajectories |
|---|---:|
| `terminus-2/openai_gpt-oss-20b` | 466 |
| `terminus-2/accounts_fireworks_models_minimax-m2` | 451 |
| `terminus-2/grok-code-fast-1` | 445 |
| `claude-code/minimax-m2.1` | 440 |
| `vix/claude-opus-4-7` | 440 |
| `openhands/claude-sonnet-4-5-20250929` | 438 |
| `claude-code/claude-opus-4-5-20251101` | 436 |
| `mini-swe-agent/gemini-2.5-pro` | 435 |
| `mini-swe-agent/gpt-5-mini` | 434 |
| `hookele/gpt-5.1-codex-mini` | 431 |
| `openhands/moonshotai_Kimi-K2-Instruct-0905` | 430 |
| `mini-swe-agent/claude-sonnet-4-5-20250929` | 419 |

Trajectory-level pass/fail:

- Explicit per-trajectory pass/fail field in trajectory JSON: not found; `trajectory_json_outcome` remains `missing` for 5,265/5,265 after conservative parsing.
- Per-run outcome is now joined from `data/indexes/trajectory_index_balanced_12.json`: `reward == 1.0` is pass and `reward == 0.0` is fail.
- Index reward distribution: 1,992 passes and 3,273 failures across 5,265 trajectories, for a local success rate of 37.8%.
- No reward values are missing, and all rewards are binary (`0.0` or `1.0`).
- Validation against leaderboard task aggregates: all 1,007 complete local `(task, scaffold, model)` groups match leaderboard `avgResolutionRate` exactly. The 59 partial groups remain success-count consistent; their reward means can differ because fewer than all leaderboard trials were downloaded.

Trajectory-level outcome by sampled scaffold/model:

| Scaffold/model directory | Passes | Failures | Success rate |
|---|---:|---:|---:|
| `vix/claude-opus-4-7` | 400 | 40 | 90.9% |
| `hookele/gpt-5.1-codex-mini` | 272 | 159 | 63.1% |
| `claude-code/claude-opus-4-5-20251101` | 232 | 204 | 53.2% |
| `mini-swe-agent/claude-sonnet-4-5-20250929` | 188 | 231 | 44.9% |
| `openhands/claude-sonnet-4-5-20250929` | 188 | 250 | 42.9% |
| `claude-code/minimax-m2.1` | 163 | 277 | 37.0% |
| `terminus-2/accounts_fireworks_models_minimax-m2` | 138 | 313 | 30.6% |
| `openhands/moonshotai_Kimi-K2-Instruct-0905` | 119 | 311 | 27.7% |
| `mini-swe-agent/gemini-2.5-pro` | 116 | 319 | 26.7% |
| `mini-swe-agent/gpt-5-mini` | 99 | 335 | 22.8% |
| `terminus-2/grok-code-fast-1` | 63 | 382 | 14.2% |
| `terminus-2/openai_gpt-oss-20b` | 14 | 452 | 3.0% |

Passed trajectories are generally shorter than failed trajectories in this sample: median `step_count` is 29 for passes vs 28 for failures, but the mean is 41.3 vs 57.0 because long repair loops are concentrated in failures. Median command count is 9.5 for passes vs 6 for failures; the failed mean is higher, 30.6 vs 20.6.

Length and resource distributions:

| Measure | Min | P25 | Median | Mean | P75 | P90 | P95 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `step_count` | 2 | 11 | 29 | 51.1 | 66 | 126 | 183 | 796 |
| extracted command/tool-command count | 0 | 0 | 8 | 26.8 | 32 | 78 | 118 | 792 |
| `tool_call_count` | 0 | 6 | 19 | 37.4 | 48 | 95 | 139 | 792 |
| `total_tokens` | 0 | 41,112 | 251,316 | 1,287,434 | 1,037,262 | 3,235,753 | 5,343,807 | 180,963,993 |
| `cost_usd` where present | 0.0 | 0.0 | 0.008649 | 0.248 | 0.127 | 0.691 | 1.317 | 83.798 |
| duration from timestamps, seconds | 0.00004 | 12.64 | 130.0 | 353.0 | 440.0 | 898.1 | 1505.3 | 6366.3 |

Missing or inconsistent fields:

- `agent.model_name` is present as a JSON field in 4,373 trajectories; the script falls back to the model directory where missing.
- `final_metrics.total_cost_usd` is absent in 2,200 trajectories.
- Some trajectories have command count `0` because their actions are stored as high-level tool/editor commands or final answer text rather than shell commands.
- Text fields occasionally contain mojibake from encoding conversion, for example `â€˜` in one `mini-swe-agent` trajectory.
- `schema_version` varies at least between `ATIF-v1.2` and `ATIF-v1.6`.

## Command And Tool Pattern Candidates

The command/tool extraction intentionally treats these as candidates for later annotation, not final labels.

Most common command heads or tool-command names:

| Rank | Count | Head/tool | Candidate purpose | Example |
|---:|---:|---|---|---|
| 1 | 9,589 | `str_replace` | other/editor operation | `str_replace` |
| 2 | 6,960 | `view` | other/editor operation | `view` |
| 3 | 4,595 | `create` | other/editor operation | `create` |
| 4 | 4,031 | `plan` | other/orchestration | `plan` |
| 5 | 1,803 | `python3` | running scripts/tests | `python3 -c ...` |
| 6 | 1,412 | `python3` | running scripts/tests | `python3 << 'EOF'` |
| 7 | 1,121 | `echo` | final verification | `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` |
| 10 | 761 | `cat` | editing/writing files | `cat <<'EOF' > my_warrior.red` |
| 13 | 344 | `ls` | environment inspection | `ls -la /app/` |
| 25 | 189 | `sed` | editing/writing files | `sed -i ...` |

Purpose counts from heuristic grouping:

| Candidate purpose | Count |
|---|---:|
| `other` | 52,423 |
| `reading_files` | 18,136 |
| `editing_writing_files` | 18,097 |
| `running_scripts_tests` | 10,034 |
| `environment_inspection` | 9,961 |
| `file_content_search` | 9,573 |
| `debugging_diagnostics` | 9,488 |
| `final_verification` | 8,513 |
| `dependency_setup` | 4,917 |
| `unknown` | 10 |

Interpretation notes:

- `other` is large because tool-native actions such as `str_replace`, `view`, `create`, `plan`, `C-c`, and domain commands such as `pmars` do not map cleanly to generic shell-purpose labels.
- `cd /app && ...` commands often hide the real purpose in the second segment; downstream extraction should normalize chained commands.
- `cat` is ambiguous: `cat file` is reading, but `cat <<EOF > file` is writing.
- `python -c` can be inspection, debugging, implementation, or validation depending on local context and observation.

## Representative Phase-Like Snippets

These are examples to inform phase-design. They are not labels to be frozen into the final taxonomy.

| Candidate phase | Path and step | Evidence |
|---|---|---|
| Task understanding | `terminus-2/.../0014600..._40681775....json`, step 3 | Agent message: "I need to explore the /app directory..." then `ls -la /app`. |
| Environment exploration | `terminus-2/.../0014600..._40681775....json`, step 3 | `keystrokes: "ls -la /app\n"` with observation listing `eval.py` and `model_ref.xml`. |
| Problem localization | `terminus-2/.../0014600..._40681775....json`, step 4 | `cat /app/eval.py` to understand correctness and speed assertions. |
| Problem localization | `vix/.../0014600..._15abf288....json`, step 3 | `read_file` on `/app/model_ref.xml` with reason "Examine the reference model". |
| Planning | `claude-code/.../0014600..._1bac6418....json`, step 19 | Runs a custom `python3 -c` script to inspect MuJoCo constraint/contact dynamics; this is exploratory planning despite using an executable command. |
| Implementation/intervention | `mini-swe-agent/.../0ddf1db..._3bd68e39....json`, step 9 | Writes `/app/polyglot/main.rs` using `cat <<'EOF' > /app/polyglot/main.rs`. |
| Execution/testing | `claude-code/.../0014600..._1bac6418....json`, step 10 | `python eval.py 2>&1`, observation has assertion failure for speed. |
| Feedback interpretation | `claude-code/.../0014600..._1bac6418....json`, step 13 | Observation shows `AssertionError` from `test_correctness`; next actions depend on interpreting that failure. |
| Iterative repair | `mini-swe-agent/.../0ddf1db..._3bd68e39....json`, step 9 | Reasoning says previous attempt failed with C++ compilation error, then overwrites the whole file and reruns edge-case tests. |
| Verification/finalization | `mini-swe-agent/.../0ddf1db..._3bd68e39....json`, step 10 | Reasoning says both `rustc` and `g++` tests passed, then `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`. |
| Orchestration/bookkeeping | `openhands/.../0014600..._18ab3eae....json`, early system steps | System adds workspace context and includes task-management/process-management policy before agent actions. |
| Final-answer/output | `claude-code/.../0014600..._34d1417b....json`, final message snippet | Summarizes changed solver and says correctness and speed tests pass, but trajectory outcome field remains missing. |

## Ambiguity Cases

Simple command-based labelling will fail in several recurrent situations:

- Reading for exploration vs verification: `cat /app/recovered.json` late in `claude-code/.../01f470..._292e7e9c....json` can be evidence gathering, output verification, or final answer preparation depending on preceding context.
- Running a script for diagnosis vs validation: `python eval.py 2>&1` appears early with failing assertions and late with passing speed/correctness output in `claude-code/.../0014600..._34d1417b....json`.
- Python one-liners are multi-purpose: `python3 -c "import mujoco; print(dir(...))"` is environment/API inspection, not testing, even though it executes Python.
- Installing dependencies can be setup or repair: commands matching `pip`, `apt-get`, `npm`, or similar require nearby observations; missing-package errors convert the same command family from setup to reactive repair.
- Repeated commands may be useful confirmation or blind retry: some trajectories repeat `python3 eval.py` many times after similar failures, while others repeat tests after successive edits.
- Chained commands compress phases: `sed -i ... && cd ocaml && make clean && make -j4 && make -C testsuite one ... && echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` contains implementation, build, test, and finalization in one tool call.
- Tool-native editor actions are semantically underspecified: `view`, `str_replace`, and `create` need `arguments.path`, surrounding message text, and subsequent observation to distinguish localization from implementation.
- `cd /app && python3 ...` should not be labelled as environment inspection just because it starts with `cd`.
- Observations with empty content occur in some late commands, so absence of stdout is not reliable evidence of success.

## Likely Task Families

The following families are heuristic, based on available task names from `data/raw/leaderboard_v2.json`, filename-linked checksums, final snippets, and command contents. They should seed stratification, not serve as definitive task-type labels.

| Heuristic family | Matched trajectories |
|---|---:|
| `shell/filesystem` | 2,076 |
| `unclassified_from_available_text` | 1,967 |
| `python/data` | 1,048 |
| `build/test` | 663 |
| `ml/math` | 505 |
| `web/api` | 468 |
| `database` | 242 |
| `polyglot/compiler` | 233 |
| `security/crypto` | 218 |

Concrete task-name examples observed through leaderboard matching include `tune-mjcf`, `build-pmars`, `build-cython-ext`, `caffe-cifar-10`, `cancel-async-tasks`, `break-filter-js-from-html`, and `chess-best-move`.

## Recommended Pilot Sampling Strategy

Use a stratified pilot of roughly 120 trajectories. If annotation time is tight, start with 72 and preserve the same proportions.

Recommended strata:

- Scaffold/model: sample each scaffold, with at least 10 trajectories per scaffold; oversample `openhands` and `terminus-2` because their tool representations differ strongly from shell-only trajectories.
- Outcome: stratify directly by `reward_outcome` (`pass`/`fail`) from the trajectory index, while retaining `leaderboard_avg_resolution_rate` as a task/scaffold/model difficulty covariate.
- Length: sample short (`step_count <= 11`), medium (`12-66`), long (`67-183`), and extreme (`>183`) trajectories.
- Tool density: include command/tool-call count bins `0`, `1-8`, `9-32`, `33-118`, and `>118`.
- Command pattern: deliberately include trajectories dominated by editor tools (`view`/`str_replace`/`create`), shell exploration (`ls`/`find`/`grep`), heavy testing (`python eval.py`, `pytest`, `make`, compilers), dependency setup (`pip`, `apt-get`, `npm`), and domain tools (`pmars`, MuJoCo scripts, compilers).
- Task family: include at least five examples from each high-confidence family and a separate batch of unclassified tasks.

Suggested allocation for 120:

- 60 balanced by scaffold/model and reward outcome, with leaderboard-resolution bins used to preserve task difficulty spread.
- 24 long/extreme trajectories because phase boundaries and repair loops are more visible there.
- 18 short trajectories because they stress whether the taxonomy handles compressed behavior.
- 18 ambiguity-enriched trajectories selected from `data/processed/representative_snippets.jsonl` and repeated-command cases.

Do not use `leaderboard_avg_resolution_rate` as a trajectory pass/fail label. Use `reward_outcome` for per-run success/failure and treat leaderboard resolution rate as an aggregate covariate.

## Annotation Export Metadata

Recommended CSV/JSONL row fields for downstream annotation:

- Identifiers: `rel_path`, `session_id`, `schema_version`, `file_task_id`, `file_run_id`, `task_id`, `task_name`, `leaderboard_task_name`.
- Agent metadata: `scaffold`, `model_dir`, `agent_name`, `agent_version`, `model_name`, `original_format`.
- Per-run outcome: `reward`, `reward_outcome`, `trajectory_json_outcome`.
- Aggregate task/submission metadata: `leaderboard_avg_resolution_rate`, `leaderboard_success_count`, `leaderboard_n_trials`, `leaderboard_model`.
- Length/resource metadata: `file_size_bytes`, `step_count`, `agent_step_count`, `tool_call_count`, `command_count`, `message_chars`, `reasoning_chars`, `observation_chars`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `duration_seconds_from_timestamps`.
- Finalization markers: `has_final_marker`, `final_message_snippet`.
- Step-level annotation export should additionally include `step_id`, `step_index`, `source`, `message`, `reasoning_content`, normalized `tool_name`, normalized `command`, `arguments.path`, `observation_text`, `returncode` when recoverable, and previous/next step references.

The generated `data/processed/trajectory_summary.csv` already contains a trajectory-level subset of these fields. A later step-level export should be produced before manual annotation.

## Reproducible Commands

Count trajectory JSON files:

```powershell
Get-ChildItem data\trajectories\balanced_12 -Recurse -File -Filter *.json | Measure-Object
```

List scaffold directories:

```powershell
Get-ChildItem data\trajectories\balanced_12 -Directory | Select-Object Name
```

Run full characterization:

```powershell
python scripts\characterize_trajectories.py
```

Inspect generated trajectory summary:

```powershell
Get-Content data\processed\trajectory_summary.csv -TotalCount 6
```

Inspect common command patterns:

```powershell
Get-Content data\processed\command_patterns.csv -TotalCount 40
```

## Risks For Annotation Validity

- No per-run pass/fail labels are present inside the trajectory JSON files themselves; the labels come from the companion index. Keep `reward_outcome` provenance explicit when annotating or modeling.
- The reward index was validated against leaderboard aggregates for complete local task groups, but 59 task groups are partial downloads. Their local reward means need not equal leaderboard `avgResolutionRate`.
- The same behavioral phase can be encoded differently by scaffold: shell command, editor tool, JSON keystroke, final-answer text, or empty message plus tool call.
- Command-only labelling will overfit to surface syntax and miss intent; annotators need message, tool arguments, observation, and local sequence context.
- Very long trajectories can dominate phase-frequency counts unless sampling or weighting accounts for trajectory length.
- Token and cost fields are not uniformly available; `total_cost_usd` is missing in many trajectories and zero in some apparently completed runs.
- Some observations include terminal prompts, warnings from parser wrappers, or tool IDs, which can confuse text-based classifiers.
- Some scaffolds embed extensive system instructions, workflow recommendations, and examples; these must be excluded from behavioral phase annotation.
- Task-family labels inferred from names/commands are incomplete; nearly 2,000 trajectories were unclassified by the simple heuristic.
- Timestamps are usable for duration estimates, but many steps in converted trajectories have near-identical timestamps; duration should be treated as approximate.
- The corpus is "balanced_12" by directory name, but the balancing criterion is not documented in the trajectory files; avoid assuming it is representative of all TerminalBench runs.
