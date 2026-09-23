# Longitudinal model-population audit notes

Sources used:
- `data/processed_live/{terminal_bench_*}/trajectory_summary.csv`: trajectory rows, scaffold, `model_name`, task, reward, step/tool/shell counts, chars, tokens, cost, duration, leaderboard date, source URL, source scaffold version.
- `data/raw/{terminal_bench_*}/leaderboard_submissions.json` and TB2.0 `leaderboard_submissions_historical.json`: source leaderboard submission metadata that had already been merged into `trajectory_summary.csv`.
- `data/raw/{terminal_bench_2_1,terminal_bench_3_0,terminal_bench_4_0}/leaderboard_trials.json`: Harbor trial `started_at`, `finished_at`, trial status/job metadata, and raw trial token/cost fields.
- Targeted raw trajectory searches using `rg -o`: TB4.0 `mini-swe-agent/gemini-3.8-flash` for `reasoning_tokens`, TB4.0 `grok-build/grok-4.6` for `total_reasoning_tokens`, and TB4.0 `claude-code` for `thinking_tokens`.

Column choices:
- Model population/configuration tables use exact `model_name` from the processed trajectory summary as `model`; `model_dir` and `leaderboard_model` are retained as provenance because they can differ.
- `median_logged_readable_chars` is `message_chars + reasoning_chars + observation_chars`, matching the existing longitudinal analysis scripts.
- Primary `submission_date`/`audit_date` is `leaderboard_date` when present, then Harbor `trial_started_at`, then first trajectory step timestamp. In these processed files, all four versions had `leaderboard_date` for all trajectory rows.
- `median_cost_usd_positive` is computed only over positive costs; `n_with_cost` counts non-missing `cost_usd` values.

Data-quality cautions:
- The raw trajectory corpus is about 34.9 GB. The full raw corpus was not decoded trajectory-by-trajectory in Python; direct reasoning/thinking-token evidence was extracted with targeted `rg` searches where such fields were observed.
- Token fields differ across schemas/scaffolds. Harbor trial `cache_tokens` exists for TB2.1, TB3.0, and TB4.0 trial rows; raw ATIF trajectories also contain provider/scaffold-specific cache fields.
- Explicit reasoning/thinking token metadata was observed in TB4.0 only in this targeted audit: `thinking_tokens`, `reasoning_tokens`, and `total_reasoning_tokens`.
- Absence of an explicit reasoning/thinking token field should not be interpreted as evidence about model capability.
- Leaderboard dates, Harbor trial run timestamps, and trajectory step timestamps are different concepts. The primary date in the tables is the processed `leaderboard_date`; trial start/finish timestamps are retained where available.
- Trajectory weighting is uneven across versions, models, and configurations, so version-level medians are composition-weighted by the available trajectory population.
