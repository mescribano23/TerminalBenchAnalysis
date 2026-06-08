# Superficial Terminal-Bench Leaderboard Analysis

This report uses `data/processed/leaderboard_submission_summary.csv` and stays at submission-row level. Accuracy and +/- use scraped official leaderboard fields; task-rate variance remains a computed diagnostic from per-task resolution rates. Passed task-trials are represented by computed aggregate counts (`computed_submission_success_count`). Trajectory-level pass/fail analysis now lives in the trajectory characterization outputs via the validated reward index.

## Overall Submission-Level Picture

- Submission rows: 144.
- Rows with local trajectories: 76.
- Unique scaffolds: 45.
- Unique exact model labels: 62.
- Total passed task-trials: 29734 / 62937 (47.2%).
- Leaderboard accuracy: mean 46.7%, median 44.7%, range 3.1%-90.2%.
- Within-submission task-rate variance: mean 0.1416, median 0.1523.
- Leaderboard +/- estimate: mean 2.6%, median 2.7%.

## Preliminary Reading

- Same-scaffold comparisons are available for 22 scaffolds. The largest accuracy ranges are `codex` (70.8%), `terminus-2` (61.6%), and `spoox-m` (49.7%).
- Same-model comparisons are available for 30 exact model labels. The largest exact-model ranges are `gpt-5.1-codex` (20.9%), `gemini-3.1-pro-preview` (20.9%), and `gpt-5.5` (18.7%).
- After splitting comma-separated model labels, 31 model components appear with more than one scaffold. This view is useful for spotting mixed-model or ensemble rows that would otherwise hide under a combined label.
- The eta-squared values below are descriptive only. They are inflated when many groups have one or two rows, so they should guide where to inspect next rather than settle the scaffold-vs-model question.

## Top Rows by Accuracy

| Rank | Scaffold | Model | Passed | Trials | Accuracy | Task-rate variance | +/- | Has trajectories |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | vix | claude-opus-4-7 | 400 | 442 | 90.2% | 0.0493 | 2.1% | True |
| 2 | jj-agent-harness | multiple | 775 | 890 | 87.1% | 0.0769 | 1.3% | True |
| 3 | nexau | gpt-5.5 | 376 | 443 | 84.7% | 0.0900 | 2.1% | True |
| 4 | Lemoncode-agent | gemini-3.1-pro-preview,gpt-5.3-codex | 376 | 445 | 84.5% | 0.0707 | 2.6% | False |
| 5 | capy-build | gpt-5.5 | 370 | 445 | 83.1% | 0.0999 | 2.1% | False |
| 6 | codex | gpt-5.5 | 366 | 445 | 82.2% | 0.1013 | 2.2% | False |
| 7 | polaris | claude-opus-4-7,gemini-3.1-pro-preview,gpt-5.5 | 365 | 444 | 82.2% | 0.0759 | 2.8% | False |
| 8 | judy | gemini-3.1-pro-preview | 357 | 445 | 80.2% | 0.0959 | 2.6% | True |
| 9 | claude-wozcode-plugin | claude-opus-4-7 | 357 | 445 | 80.2% | 0.1186 | 2.1% | False |
| 10 | Lemoncode-agent | gemini-3.1-pro-preview,gpt-3.5-codex | 349 | 437 | 79.9% | 0.0788 | 3.0% | False |
| 11 | sage | gpt-5.3-codex | 349 | 445 | 78.4% | 0.1257 | 2.2% | False |
| 12 | Factory Droid | gpt-5.3-codex | 344 | 445 | 77.3% | 0.1338 | 2.2% | False |
| 13 | terminus-kira-env-bootstrap | claude-opus-4-6 | 340 | 445 | 76.4% | 0.1269 | 2.4% | True |
| 14 | ruley | gpt-5.3-codex | 675 | 890 | 75.8% | 0.0984 | 2.0% | False |
| 15 | codelia | gpt-5.3-codex | 337 | 445 | 75.7% | 0.1422 | 2.2% | False |

## Same Scaffold, Different Models

These groups show how much leaderboard accuracy moves when the scaffold label is fixed and the model label changes. Large ranges suggest model choice matters within that scaffold, although scaffold versions are not collapsed here.

| Scaffold | Rows | Models | Mean acc. | Range | Std. | Best | Worst |
| --- | --- | --- | --- | --- | --- | --- | --- |
| codex | 9 | 9 | 49.3% | 70.8% | 20.2% | 82.2% | 11.5% |
| terminus-2 | 33 | 33 | 35.1% | 61.6% | 15.6% | 64.7% | 3.1% |
| spoox-m | 3 | 3 | 42.7% | 49.7% | 25.7% | 71.5% | 21.8% |
| gemini-cli | 5 | 4 | 40.6% | 46.0% | 21.8% | 61.4% | 15.4% |
| openhands | 12 | 12 | 28.4% | 42.0% | 13.2% | 51.9% | 9.9% |
| mini-swe-agent | 13 | 13 | 24.9% | 39.2% | 12.1% | 42.5% | 3.4% |
| claude-code | 7 | 7 | 40.3% | 30.4% | 10.9% | 58.0% | 27.5% |
| final | 2 | 2 | 57.4% | 29.4% | 20.8% | 72.1% | 42.7% |
| IndusAGICodingAgent | 2 | 2 | 57.1% | 24.1% | 17.0% | 69.1% | 45.1% |
| goose | 3 | 3 | 44.3% | 18.8% | 9.5% | 54.3% | 35.5% |
| Factory Droid | 5 | 5 | 67.3% | 16.2% | 6.5% | 77.3% | 61.1% |
| mux | 4 | 4 | 65.1% | 16.2% | 7.2% | 74.6% | 58.4% |
| little-coder | 3 | 2 | 19.0% | 15.4% | 8.5% | 24.6% | 9.2% |
| ruley | 2 | 2 | 69.0% | 13.6% | 9.6% | 75.8% | 62.2% |
| sage | 2 | 2 | 71.8% | 13.3% | 9.4% | 78.4% | 65.2% |
| warp | 3 | 3 | 56.8% | 11.1% | 5.9% | 61.2% | 50.1% |
| judy | 2 | 2 | 76.1% | 8.3% | 5.9% | 80.2% | 71.9% |
| capy-build | 2 | 2 | 79.2% | 7.9% | 5.6% | 83.1% | 75.3% |
| Junie | 2 | 2 | 67.6% | 6.7% | 4.8% | 71.0% | 64.3% |
| letta-code | 3 | 3 | 56.2% | 5.6% | 2.8% | 59.1% | 53.5% |

## Same Model, Different Scaffolds

These groups show how much leaderboard accuracy moves when the exact model label is fixed and the scaffold changes. Large ranges suggest scaffold choice matters for that model.

| Model | Rows | Scaffolds | Mean acc. | Range | Std. | Best | Worst |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-5.1-codex | 3 | 3 | 49.4% | 20.9% | 11.0% | 57.8% | 36.9% |
| gemini-3.1-pro-preview | 4 | 3 | 69.0% | 20.9% | 10.2% | 80.2% | 59.4% |
| gpt-5.5 | 4 | 4 | 79.0% | 18.7% | 8.7% | 84.7% | 66.1% |
| gpt-5.1-codex-mini | 2 | 2 | 52.4% | 18.4% | 13.0% | 61.6% | 43.1% |
| claude-opus-4-6 | 8 | 8 | 68.8% | 18.4% | 6.5% | 76.4% | 58.0% |
| gemini-3-flash-preview | 3 | 3 | 54.5% | 16.9% | 8.8% | 64.3% | 47.4% |
| gemini-2.5-pro | 4 | 4 | 23.7% | 16.2% | 7.2% | 32.6% | 16.4% |
| claude-haiku-4-5-20251001 | 4 | 4 | 24.9% | 15.9% | 7.4% | 29.8% | 13.9% |
| gpt-5 | 4 | 4 | 40.6% | 15.7% | 7.4% | 49.6% | 33.9% |
| gpt-5-nano | 5 | 5 | 11.6% | 14.8% | 6.0% | 21.8% | 7.0% |
| gpt-5.3-codex | 9 | 9 | 73.6% | 13.7% | 4.4% | 78.4% | 64.7% |
| gemini-3-pro-preview | 7 | 7 | 61.8% | 13.5% | 4.6% | 69.4% | 56.0% |
| gpt-5-mini | 5 | 5 | 28.4% | 12.6% | 5.3% | 34.8% | 22.2% |
| grok-code-fast-1 | 2 | 2 | 20.0% | 11.7% | 8.3% | 25.8% | 14.2% |
| claude-opus-4-5-20251101 | 4 | 4 | 56.2% | 11.2% | 5.3% | 63.1% | 51.9% |
| gpt-5.2 | 4 | 4 | 60.6% | 10.9% | 4.7% | 64.9% | 54.0% |
| claude-opus-4-7 | 2 | 2 | 85.2% | 9.9% | 7.0% | 90.2% | 80.2% |
| minimax-m2.1 | 2 | 2 | 32.9% | 7.4% | 5.2% | 36.6% | 29.2% |
| claude-opus-4-5 | 4 | 4 | 55.9% | 7.4% | 3.5% | 59.1% | 51.7% |
| openai/gpt-oss-120b | 2 | 2 | 16.4% | 4.5% | 3.2% | 18.7% | 14.2% |

## Same Model Component, Different Scaffolds

Some leaderboard rows list model ensembles or multiple model names. This exploded view splits comma-separated model labels before grouping, so mixed-model rows can still contribute to model-level pattern finding.

| Model component | Rows | Scaffolds | Mean acc. | Range | Std. | Best | Worst |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-5-nano | 7 | 6 | 23.9% | 52.1% | 21.7% | 59.1% | 7.0% |
| claude-haiku-4-5-20251001 | 6 | 5 | 34.8% | 45.2% | 16.6% | 59.1% | 13.9% |
| claude-haiku-4-5 | 3 | 3 | 51.7% | 25.7% | 14.1% | 61.2% | 35.5% |
| gemini-3.1-pro-preview | 8 | 6 | 74.2% | 25.1% | 9.5% | 84.5% | 59.4% |
| gemini-3-flash-preview | 4 | 3 | 58.6% | 23.6% | 10.9% | 71.0% | 47.4% |
| gpt-5.1-codex | 3 | 3 | 49.4% | 20.9% | 11.0% | 57.8% | 36.9% |
| gpt-5.3-codex | 11 | 11 | 74.3% | 19.8% | 5.2% | 84.5% | 64.7% |
| gpt-5.5 | 5 | 5 | 79.7% | 18.7% | 7.7% | 84.7% | 66.1% |
| gpt-5.1-codex-mini | 2 | 2 | 52.4% | 18.4% | 13.0% | 61.6% | 43.1% |
| claude-opus-4-6 | 9 | 9 | 69.1% | 18.4% | 6.1% | 76.4% | 58.0% |
| gemini-2.5-pro | 4 | 4 | 23.7% | 16.2% | 7.2% | 32.6% | 16.4% |
| gpt-5 | 4 | 4 | 40.6% | 15.7% | 7.4% | 49.6% | 33.9% |
| gemini-3-pro-preview | 9 | 9 | 61.1% | 13.5% | 4.2% | 69.4% | 56.0% |
| gpt-5-mini | 5 | 5 | 28.4% | 12.6% | 5.3% | 34.8% | 22.2% |
| grok-code-fast-1 | 2 | 2 | 20.0% | 11.7% | 8.3% | 25.8% | 14.2% |
| claude-opus-4-5-20251101 | 4 | 4 | 56.2% | 11.2% | 5.3% | 63.1% | 51.9% |
| gpt-5.2 | 5 | 5 | 60.8% | 10.9% | 4.1% | 64.9% | 54.0% |
| claude-sonnet-4-5-20250929 | 5 | 5 | 43.6% | 10.1% | 3.8% | 50.1% | 40.1% |
| claude-opus-4-7 | 3 | 3 | 84.2% | 9.9% | 5.3% | 90.2% | 80.2% |
| minimax-m2.1 | 2 | 2 | 32.9% | 7.4% | 5.2% | 36.6% | 29.2% |

## Coarse Variance Attribution

This is a one-way ANOVA-style eta-squared diagnostic on submission accuracy, not a causal estimate. It asks how much row-level accuracy variance is associated with grouping by one label at a time.

- Scaffold label eta-squared: 0.695 across 45 scaffold groups.
- Exact model label eta-squared: 0.958 across 62 model groups.
- Exploded model component eta-squared: 0.894 across 55 model-component groups.

## Trajectory Resource Efficiency

The companion efficiency files use local trajectory rows from `data/processed/trajectory_summary.csv`, not the full leaderboard. Coverage columns report how many local trajectories support token, duration, and cost estimates.

For model components, multi-model rows are duplicated across components and are not credit-apportioned. Component-level token, duration, and cost metrics should be read as association or presence metrics: submissions involving this model component had this resource profile.

Top sampled scaffolds by trajectory success rate:

| Scaffold | Trajectories | Passes | Failures | Success rate | Median tokens | Median sec. | Median cost | Tokens/pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vix | 440 | 400 | 40 | 90.9% | 8619.50 | 153.64 | 0.00 | 21077.67 |
| hookele | 431 | 272 | 159 | 63.1% | 304446.00 | 224.00 | 0.03 | 1186740.28 |
| claude-code | 876 | 395 | 481 | 45.1% | 1037771.50 | 298.96 | 0.00 | 7555890.90 |
| openhands | 868 | 307 | 561 | 35.4% | 805434.50 | 320.61 | 0.08 | 4230109.25 |
| mini-swe-agent | 1288 | 403 | 885 | 31.3% | 151220.50 | 0.00 | 0.16 | 3071282.20 |
| terminus-2 | 1362 | 215 | 1147 | 15.8% | 65272.50 | 171.19 | 0.00 | 4307768.45 |

Top sampled model components by trajectory success rate:

| Model component | Trajectories | Passes | Failures | Success rate | Median tokens | Median sec. | Median cost | Tokens/pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-opus-4-7 | 440 | 400 | 40 | 90.9% | 8619.50 | 153.64 | 0.00 | 21077.67 |
| gpt-5.1-codex-mini | 431 | 272 | 159 | 63.1% | 304446.00 | 224.00 | 0.03 | 1186740.28 |
| claude-opus-4-5-20251101 | 436 | 232 | 204 | 53.2% | 908130.00 | 230.95 | 0.00 | 5362608.63 |
| claude-sonnet-4-5-20250929 | 857 | 376 | 481 | 43.9% | 595962.00 | 61.24 | 0.43 | 3043235.81 |
| minimax-m2.1 | 440 | 163 | 277 | 37.0% | 1294444.50 | 416.21 | 0.00 | 10677617.80 |
| accounts_fireworks_models_minimax-m2 | 451 | 138 | 313 | 30.6% | 257672.00 | 459.19 | 0.00 | 3321541.36 |
| moonshotai_Kimi-K2-Instruct-0905 | 430 | 119 | 311 | 27.7% | 759048.50 | 291.29 | 0.00 | 5301285.50 |
| gemini-2.5-pro | 435 | 116 | 319 | 26.7% | 151281.00 | 0.00 | 0.31 | 5759265.71 |
| gpt-5-mini | 434 | 99 | 335 | 22.8% | 38932.50 | 0.00 | 0.03 | 941270.73 |
| grok-code-fast-1 | 445 | 63 | 382 | 14.2% | 43061.00 | 138.10 | 0.02 | 1023776.87 |
| openai_gpt-oss-20b | 466 | 14 | 452 | 3.0% | 17170.00 | 66.83 | 0.01 | 28807111.86 |

## Generated Artifacts

- `data/processed/leaderboard_scaffold_variance.csv`
- `data/processed/leaderboard_model_variance.csv`
- `data/processed/leaderboard_model_component_variance.csv`
- `data/processed/trajectory_scaffold_efficiency.csv`
- `data/processed/trajectory_model_component_efficiency.csv`
