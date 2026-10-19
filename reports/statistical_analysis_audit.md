# Statistical analysis audit

## Audit summary

The reconciliation refresh updates affected existing tests and effect sizes from the restored caches. Only the shell-invocation curvature model was refitted; five unaffected curvature models were retained. The validated difficulty labels were not regenerated. Historical outputs are preserved separately.

Primary RQ3.1, RQ3.2 and RQ3.3 aggregation uses the repository's existing effective submission IDs, consistently with RQ1. RQ3.3 takes medians within effective submission-task pairs, medians across submissions within tasks, then compares paired shared tasks. Leaderboard-URL grouping is retained as an explicit sensitivity analysis. RQ2.1 and RQ2.2 retain their existing URL-grouped definitions; RQ2.3 retains trajectory use/non-use cells with at least three trajectories per cell. No new identifier was introduced. Refreshed and historical pooled trajectory figures remain descriptive and are not submission-balanced estimates.

RQ1.3 remains a descriptive Pareto analysis. The media comparison is post-hoc exploratory. RQ3.2 composition analyses and exact shared-configuration token comparisons remain descriptive. Cost is not a current longitudinal headline metric and its incomplete, configuration-dependent coverage does not support adding a primary RQ3.3 test. No confidence intervals, multiplicity correction, or extra subgroup tests were added.

For RQ1.1 shell invocations and output tokens, the median task difference and dz have opposite signs. This is not a coding discrepancy: dz follows the mean paired difference by definition, while the requested raw effect is the median paired difference; skewed task differences can make their signs differ.

## Formulas and implementation

For paired task differences D, Cohen's dz is mean(D) / sd(D) with sample SD (ddof=1). The two-sided Wilcoxon test uses the same D values, `zero_method='wilcox'`, and reports W=0, p=1 for an all-zero contrast. Cliff's delta is (# changed>unchanged - # changed<unchanged)/(n_changed*n_unchanged), paired with a two-sided Mann-Whitney U test. The RQ1.2 test is H0: beta2=0 versus H1: beta2!=0.

## Thesis-ready results

### RQ1.1

- Steps: median delta = 2.000, dz = 0.131, W = 1479.5, p = 0.127 (not significant; n = 86).
- Shell invocations: median delta = 0.375, dz = -0.014, W = 1496.0, p = 0.439 (not significant; n = 86).
- Structured tool calls: median delta = 1.125, dz = 0.104, W = 1398.5, p = 0.118 (not significant; n = 86).
- Input tokens: median delta = 21618.000, dz = 0.254, W = 1274.0, p = 0.0153 (significant; n = 85).
- Output tokens: median delta = -29.500, dz = 0.164, W = 1711.0, p = 0.61 (not significant; n = 85).
- Total tokens: median delta = 20272.000, dz = 0.246, W = 1316.0, p = 0.025 (significant; n = 85).
- Duration: median delta = -44.887, dz = -0.275, W = 1190.0, p = 0.00339 (significant; n = 86).
- Cost: median delta = 0.086, dz = 0.457, W = 385.0, p = 7.03e-10 (significant; n = 83).

### RQ1.2

- Steps: beta1 = 0.181, beta2 = -0.425, p(beta2) = 0.00283.
- Shell invocations: beta1 = -0.092, beta2 = -0.293, p(beta2) = 0.11.
- Structured tool calls: beta1 = -0.018, beta2 = -0.250, p(beta2) = 0.242.
- Total tokens: beta1 = 0.207, beta2 = -0.341, p(beta2) = 0.0102.
- Duration: beta1 = -0.252, beta2 = -0.486, p(beta2) = 0.00194.
- Cost: beta1 = 0.852, beta2 = -0.289, p(beta2) = 0.0254.

### RQ2.1

- Difficulty and task pass rate: Spearman rho = -0.488, p = 1.24e-06, n = 89 tasks.

### RQ2.2

- Post-hoc exploratory media finding: 7 media tasks averaged 16.0% versus 38.4% for 82 other tasks (delta = -22.4 pp); no confirmatory test or Cliff's delta is reported.
- Agent vs expert: median agent duration = 7.02 min, median estimate = 60.00 min, median paired delta = -46.91 min, dz = -0.509, W = 46.0, p = 1.78e-15 (n = 88). Success-only median = 7.21 min; median paired delta = -46.59 min and median agent/estimate ratio = 0.121 (descriptive only).
- Agent vs junior: median agent duration = 7.02 min, median estimate = 240.00 min, median paired delta = -235.34 min, dz = -0.403, W = 1.0, p = 3.86e-16 (n = 88). Success-only median = 7.21 min; median paired delta = -235.60 min and median agent/estimate ratio = 0.022 (descriptive only).

### RQ2.3

- Inspect/search: use rate = 88.4%, mean/median delta = 9.46/7.42 pp, dz = 0.779, W = 434.0, p = 3.75e-10 (significant; n = 89).
- Modify/write: use rate = 77.3%, mean/median delta = 5.70/3.90 pp, dz = 0.510, W = 856.0, p = 7.54e-06 (significant; n = 89).
- Execute/run: use rate = 61.1%, mean/median delta = 7.68/5.63 pp, dz = 0.520, W = 762.0, p = 1.08e-06 (significant; n = 89).
- Test/validate: use rate = 12.0%, mean/median delta = 7.56/6.67 pp, dz = 0.487, W = 730.0, p = 1.97e-05 (significant; n = 82).
- Environment/dependencies: use rate = 37.3%, mean/median delta = 2.35/2.19 pp, dz = 0.120, W = 1273.0, p = 0.183 (not significant; n = 80).
- Version control: use rate = 10.6%, mean/median delta = -2.32/-1.94 pp, dz = -0.121, W = 543.0, p = 0.489 (not significant; n = 50).
- Data query/transform: use rate = 4.0%, mean/median delta = -3.75/-2.96 pp, dz = -0.183, W = 38.0, p = 0.635 (not significant; n = 13).
- Network/external: use rate = 10.1%, mean/median delta = -2.40/-3.01 pp, dz = -0.100, W = 450.0, p = 0.228 (not significant; n = 48).
- Media/specialized: use rate = 2.2%, mean/median delta = 2.00/5.43 pp, dz = 0.098, W = 32.0, p = 0.622 (not significant; n = 12).

### RQ3.1

- 2.0->2.1: 36.6% -> 75.1% (delta = 38.45 pp; mean/median task delta = 38.45/36.79 pp), dz = 1.803, W = 1.0, p = 2.64e-16 (n = 89).
- 3.0->4.0: 21.6% -> 36.2% (delta = 14.58 pp; mean/median task delta = 14.58/13.80 pp), dz = 0.924, W = 164.0, p = 1.22e-08 (n = 66).
- Instruction-change comparison, 2.0->2.1: changed tasks improved by 41.70 pp on average (median 40.13) versus 37.38 pp (median 36.04) for unchanged tasks; between-group mean difference = 4.31 pp, Cliff's delta = 0.104, U = 814.0, p = 0.467 (n = 22/67).
- Instruction-change comparison, 3.0->4.0: changed tasks improved by 20.12 pp on average (median 18.03) versus 13.47 pp (median 12.78) for unchanged tasks; between-group mean difference = 6.65 pp, Cliff's delta = 0.208, U = 365.5, p = 0.282 (n = 11/55).

### RQ3.3

- 2.0->2.1, Steps: effective-submission-balanced shared-task medians 21 -> 18 (-14.3% ratio of cross-task medians); mean/median paired task delta = -3.31/-3.5, dz = -0.313, W = 1129.0, p = 0.000889 (n = 89). Refreshed pooled trajectory medians are descriptive only: 21 -> 18 (-14.3%).
- 2.0->2.1, Shell invocations: effective-submission-balanced shared-task medians 20.5 -> 16 (-22.0% ratio of cross-task medians); mean/median paired task delta = -5.78/-4.5, dz = -0.524, W = 766.5, p = 1.18e-06 (n = 89). Refreshed pooled trajectory medians are descriptive only: 20 -> 15 (-25.0%).
- 2.0->2.1, Structured tool calls: effective-submission-balanced shared-task medians 23.8 -> 19 (-20.0% ratio of cross-task medians); mean/median paired task delta = -5.19/-5, dz = -0.417, W = 929.0, p = 3.05e-05 (n = 89). Refreshed pooled trajectory medians are descriptive only: 23 -> 19 (-17.4%).
- 2.0->2.1, Duration: effective-submission-balanced shared-task medians 434 -> 378 (-13.0% ratio of cross-task medians); mean/median paired task delta = -39/-57.8, dz = -0.139, W = 1312.0, p = 0.00473 (n = 89). Refreshed pooled trajectory medians are descriptive only: 409 -> 377 (-7.8%).
- 2.0->2.1, Total tokens: effective-submission-balanced shared-task medians 2.42e+05 -> 3e+05 (+23.8% ratio of cross-task medians); mean/median paired task delta = 2.03e+05/6.03e+04, dz = 0.297, W = 1080.0, p = 0.00016 (n = 89). Refreshed pooled trajectory medians are descriptive only: 2.14e+05 -> 2.83e+05 (+32.2%).
- 3.0->4.0, Steps: effective-submission-balanced shared-task medians 76.5 -> 59.8 (-21.9% ratio of cross-task medians); mean/median paired task delta = -9.91/-10.2, dz = -0.360, W = 416.5, p = 1.07e-05 (n = 66). Refreshed pooled trajectory medians are descriptive only: 71 -> 60 (-15.5%).
- 3.0->4.0, Shell invocations: effective-submission-balanced shared-task medians 57.2 -> 49.2 (-14.0% ratio of cross-task medians); mean/median paired task delta = -2.9/-4.75, dz = -0.134, W = 658.0, p = 0.00675 (n = 66). Refreshed pooled trajectory medians are descriptive only: 55 -> 47 (-14.5%).
- 3.0->4.0, Structured tool calls: effective-submission-balanced shared-task medians 78.5 -> 63 (-19.7% ratio of cross-task medians); mean/median paired task delta = -9.93/-10.2, dz = -0.399, W = 418.5, p = 1.92e-05 (n = 66). Refreshed pooled trajectory medians are descriptive only: 75 -> 63 (-16.0%).
- 3.0->4.0, Duration: effective-submission-balanced shared-task medians 2e+03 -> 1.48e+03 (-26.0% ratio of cross-task medians); mean/median paired task delta = -511/-414, dz = -0.500, W = 247.0, p = 4.15e-08 (n = 66). Refreshed pooled trajectory medians are descriptive only: 1.97e+03 -> 1.64e+03 (-16.8%).
- 3.0->4.0, Total tokens: effective-submission-balanced shared-task medians 8.54e+06 -> 5.27e+06 (-38.3% ratio of cross-task medians); mean/median paired task delta = -2.22e+06/-1.93e+06, dz = -0.511, W = 374.0, p = 2.97e-06 (n = 66). Refreshed pooled trajectory medians are descriptive only: 8.06e+06 -> 5.3e+06 (-34.3%).

### Shared TB3.0/TB4.0 configurations (descriptive)

- claude-code / claude-fable-5: 5,474,905 -> 5,202,921 tokens (-5.0%, decrease; 66 shared tasks).
- claude-code / claude-opus-4-8: 9,832,830 -> 12,224,736 tokens (+24.3%, increase; 66 shared tasks).
- claude-code / claude-sonnet-5: 32,988,530 -> 39,208,232 tokens (+18.9%, increase; 66 shared tasks).
- claude-code / glm-5.3: 10,022,539 -> 17,812,942 tokens (+77.7%, increase; 65 shared tasks).
- codex / gpt-5.6-luna: 9,173,580 -> 11,789,155 tokens (+28.5%, increase; 66 shared tasks).
- codex / gpt-5.6-sol: 4,731,088 -> 5,002,708 tokens (+5.7%, increase; 66 shared tasks).
- codex / gpt-5.6-terra: 6,730,560 -> 7,290,234 tokens (+8.3%, increase; 66 shared tasks).
- Summary: 6/7 increased; median change +18.9%, range -5.0% to +77.7%; no significance test.

## Suggested methodology wording

Statistical inference used tasks as the unit of analysis after task-balanced aggregation: where submission identifiers were available, trajectories were first summarized within submission-task pairs and then across submissions. Paired task comparisons used two-sided Wilcoxon signed-rank tests with paired Cohen's dz, while comparisons of independent task groups used two-sided Mann-Whitney U tests with Cliff's delta. Ordinal difficulty associations used Spearman's rho, and RQ1.2 retained the quadratic conditional-logistic coefficient beta2 and its two-sided test of H0: beta2=0. Post-hoc media, Pareto, composition, subgroup, diagnostic token, and sparse shared-configuration analyses remained descriptive.

## Thesis wording changes

No thesis manuscript or Results-section source file is present in the repository, so exact sentence-level edits could not be marked in place. Apply these claim-level replacements:

- RQ1.1: reserve 'statistically significant' for metrics with p<0.05 in the table above, and always pair it with the signed median difference and dz. Do not infer the task-level direction from pooled success/failure medians where the repository flags a reversal.
- RQ2.3: use 'was associated with' rather than causal language. State that support means three use and three non-use trajectories per task, not three distinct submissions, and do not claim subgroup significance from category/difficulty figures.
- RQ3.1: state improvement using the paired shared-task results. The instruction conclusion must be based on the changed-versus-unchanged Mann-Whitney/Cliff comparison, not separate within-group p-values.
- RQ3.3: distinguish pooled headline percentage changes from paired task-level inference. Describe increases/decreases as statistically supported only where the paired Wilcoxon p-value is below 0.05, and include dz.
- Cost: do not add a longitudinal cost test. Cost is not a current headline RQ3.3 metric; positive-cost coverage is 25,840/38,604 (66.9%) for TB2.0/TB2.1 and 7,362/10,239 (71.9%) for TB3.0/TB4.0, and coverage is configuration-dependent, so comparability is inadequate for the requested primary analysis.

## Master inferential table

The machine-readable table contains 40 inferential rows. Descriptive-only analyses are deliberately excluded.

| RQ | Analysis | Comparison | Metric | n | Raw effect | Effect size | Test statistic | p | Direction |
| --- | --- | --- | --- | --: | --: | ---: | --: | --: | --- |
| RQ1.1 | successful vs failed trajectories | success - failure | Steps | 86 | 2 steps | cohens_dz=0.1306 | 1480 | 0.1272 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Shell invocations | 86 | 0.375 invocations | cohens_dz=-0.01365 | 1496 | 0.4386 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Structured tool calls | 86 | 1.125 calls | cohens_dz=0.1042 | 1398 | 0.1177 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Input tokens | 85 | 2.162e+04 tokens | cohens_dz=0.2541 | 1274 | 0.0153 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Output tokens | 85 | -29.5 tokens | cohens_dz=0.1644 | 1711 | 0.6097 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Total tokens | 85 | 2.027e+04 tokens | cohens_dz=0.2462 | 1316 | 0.02501 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Duration | 86 | -44.89 seconds | cohens_dz=-0.2747 | 1190 | 0.003387 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Cost | 83 | 0.08621 USD | cohens_dz=0.4572 | 385 | 7.026e-10 | positive = higher for successful trajectories |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Steps | 87 | -0.4255 standardized quadratic log-effort coefficient | beta_2=-0.4255 | -2.986 | 0.002831 | negative = concave-down conditional relationship |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Shell invocations | 87 | -0.2928 standardized quadratic log-effort coefficient | beta_2=-0.2928 | -1.598 | 0.11 | negative = concave-down conditional relationship |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Structured tool calls | 87 | -0.2499 standardized quadratic log-effort coefficient | beta_2=-0.2499 | -1.169 | 0.2424 | negative = concave-down conditional relationship |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Total tokens | 87 | -0.3411 standardized quadratic log-effort coefficient | beta_2=-0.3411 | -2.57 | 0.01018 | negative = concave-down conditional relationship |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Duration | 87 | -0.486 standardized quadratic log-effort coefficient | beta_2=-0.486 | -3.1 | 0.001937 | negative = concave-down conditional relationship |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Cost | 86 | -0.2887 standardized quadratic log-effort coefficient | beta_2=-0.2887 | -2.235 | 0.0254 | negative = concave-down conditional relationship |
| RQ2.1 | difficulty vs task pass rate | ordinal difficulty | Task-balanced pass rate | 89 | -0.4878 rho | spearman_rho=-0.4878 | -0.4878 | 1.244e-06 | negative = lower pass rate at greater difficulty |
| RQ2.2 | agent duration vs human estimate | agent - expert | Duration | 88 | -46.91 minutes | cohens_dz=-0.5094 | 46 | 1.783e-15 | negative = agent duration is shorter |
| RQ2.2 | agent duration vs human estimate | agent - junior | Duration | 88 | -235.3 minutes | cohens_dz=-0.403 | 1 | 3.863e-16 | negative = agent duration is shorter |
| RQ2.3 | functional behavior use vs success | used - not used | Inspect/search | 89 | 9.459 percentage points (mean task contrast) | cohens_dz=0.7788 | 434 | 3.754e-10 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Modify/write | 89 | 5.699 percentage points (mean task contrast) | cohens_dz=0.5098 | 856 | 7.539e-06 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Execute/run | 89 | 7.684 percentage points (mean task contrast) | cohens_dz=0.52 | 762 | 1.084e-06 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Test/validate | 82 | 7.564 percentage points (mean task contrast) | cohens_dz=0.4872 | 730 | 1.966e-05 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Environment/dependencies | 80 | 2.345 percentage points (mean task contrast) | cohens_dz=0.1202 | 1273 | 0.1827 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Version control | 50 | -2.323 percentage points (mean task contrast) | cohens_dz=-0.1212 | 543 | 0.4894 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Data query/transform | 13 | -3.747 percentage points (mean task contrast) | cohens_dz=-0.1829 | 38 | 0.6355 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Network/external | 48 | -2.405 percentage points (mean task contrast) | cohens_dz=-0.1003 | 450 | 0.2277 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Media/specialized | 12 | 2.003 percentage points (mean task contrast) | cohens_dz=0.09832 | 32 | 0.6221 | positive = behavior use associated with higher success |
| RQ3.1 | benchmark-version performance | 2.0->2.1 | Task-balanced pass rate | 89 | 38.45 percentage points | cohens_dz=1.803 | 1 | 2.639e-16 | positive = higher performance in the newer version |
| RQ3.1 | benchmark-version performance | 3.0->4.0 | Task-balanced pass rate | 66 | 14.58 percentage points | cohens_dz=0.9241 | 164 | 1.222e-08 | positive = higher performance in the newer version |
| RQ3.1 | instruction-change robustness | 2.0->2.1 | Task pass-rate improvement | 89 | 4.314 percentage points | cliffs_delta=0.1045 | 814 | 0.4669 | positive = changed tasks tended to improve more |
| RQ3.1 | instruction-change robustness | 3.0->4.0 | Task pass-rate improvement | 66 | 6.651 percentage points | cliffs_delta=0.2083 | 365.5 | 0.2821 | positive = changed tasks tended to improve more |
| RQ3.3 | benchmark-version interaction/resource change | 2.0->2.1 | Steps | 89 | -3.5 steps | cohens_dz=-0.3129 | 1129 | 0.0008895 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 2.0->2.1 | Shell invocations | 89 | -4.5 invocations | cohens_dz=-0.5237 | 766.5 | 1.179e-06 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 2.0->2.1 | Structured tool calls | 89 | -5 calls | cohens_dz=-0.4169 | 929 | 3.051e-05 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 2.0->2.1 | Duration | 89 | -57.8 seconds | cohens_dz=-0.1385 | 1312 | 0.004727 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 2.0->2.1 | Total tokens | 89 | 6.034e+04 tokens | cohens_dz=0.2966 | 1080 | 0.0001605 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 3.0->4.0 | Steps | 66 | -10.25 steps | cohens_dz=-0.3604 | 416.5 | 1.074e-05 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 3.0->4.0 | Shell invocations | 66 | -4.75 invocations | cohens_dz=-0.1338 | 658 | 0.006747 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 3.0->4.0 | Structured tool calls | 66 | -10.25 calls | cohens_dz=-0.3987 | 418.5 | 1.918e-05 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 3.0->4.0 | Duration | 66 | -414 seconds | cohens_dz=-0.4999 | 247 | 4.154e-08 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 3.0->4.0 | Total tokens | 66 | -1.925e+06 tokens | cohens_dz=-0.5109 | 374 | 2.97e-06 | positive = metric increased in the newer version |
