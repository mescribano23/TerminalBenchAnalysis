# Statistical results

## Analysis methods

Primary RQ3.1, RQ3.2 and RQ3.3 aggregation uses resolved source_submission_id values, consistently with RQ1. RQ3.3 takes medians within source submission-task pairs, medians across submissions within tasks, then compares paired shared tasks. Leaderboard-URL grouping is retained as an explicit sensitivity analysis. RQ2.1 and RQ2.2 now use the same actual source submission unit; RQ2.3 retains trajectory use/non-use cells with at least three trajectories per cell. Configuration fingerprints are separate from source submission identity. Historical scraped dates are preserved; their submission/publication semantics remain unverified. Only source-submission-balanced RQ3.3 effort figures are retained; pooled trajectory medians remain descriptive diagnostics in CSV tables.

RQ1.3 remains a descriptive Pareto analysis. RQ2.2 agent durations and human completion-time estimates measure different constructs and are compared descriptively, without hypothesis tests or standardized effect sizes. The media comparison is post-hoc exploratory. RQ3.2 composition analyses and exact shared-configuration token comparisons remain descriptive. Cost is not a current longitudinal headline metric and its incomplete, configuration-dependent coverage does not support adding a primary RQ3.3 test. No confidence intervals, multiplicity correction, or extra subgroup tests were added.

Effect-size signs follow the original task contrasts: success minus failure for RQ1.1, used minus not used for RQ2.3, and newer minus older version for RQ3.1 performance and RQ3.3 effort. Positive r_rb means a greater positive than negative signed-rank sum. For RQ1.1 output tokens, the median difference remains -29.5 tokens while r_rb is +0.063748290; a median and a signed-rank balance can have different signs. Shell invocations have median difference +0.375 and r_rb +0.099066546. Neither contrast is statistically significant. Effect-size magnitude labels from standardized mean differences are not applied to r_rb.

## Formulas and implementation

For paired task differences D, matched-pairs rank-biserial correlation is r_rb = (R+ - R-) / (R+ + R-), where R+ and R- sum the average ranks of absolute nonzero differences with positive and negative signs. The effect and Wilcoxon test share finite-value/missing-value filtering and exact-zero exclusion (`zero_method='wilcox'`); ties receive average ranks without rounding D. Empty or all-zero contrasts have undefined r_rb (NaN). The unchanged two-sided Wilcoxon test reports W=min(R+,R-) and represents an all-zero contrast as W=0, p=1. Cliff's delta is (# changed>unchanged - # changed<unchanged)/(n_changed*n_unchanged), paired with a two-sided Mann-Whitney U test. The RQ1.2 test is H0: beta2=0 versus H1: beta2!=0.

## Thesis-ready results

### RQ1.1

- Steps: median delta = 2.000, r_rb = 0.190424077, W = 1479.5, p = 0.127 (not significant; n = 86).
- Shell invocations: median delta = 0.375, r_rb = 0.099066546, W = 1496.0, p = 0.439 (not significant; n = 86).
- Structured tool calls: median delta = 1.125, r_rb = 0.197647734, W = 1398.5, p = 0.118 (not significant; n = 86).
- Input tokens: median delta = 21618.000, r_rb = 0.302872777, W = 1274.0, p = 0.0153 (significant; n = 85).
- Output tokens: median delta = -29.500, r_rb = 0.063748290, W = 1711.0, p = 0.61 (not significant; n = 85).
- Total tokens: median delta = 20272.000, r_rb = 0.279890561, W = 1316.0, p = 0.025 (significant; n = 85).
- Duration: median delta = -44.887, r_rb = -0.363806469, W = 1190.0, p = 0.00339 (significant; n = 86).
- Cost: median delta = 0.086, r_rb = 0.779116466, W = 385.0, p = 7.03e-10 (significant; n = 83).

### RQ1.2

Each regression fits binary trajectory success using z = (log(1+x) - mu) / sigma, with mu and population SD sigma calculated from that model's eligible trajectories. The predictors are z and z squared. Task-specific intercepts are conditioned out of the conditional logistic likelihood; no common beta0 is estimated. These regressions use individual trajectories, without binning or equal-task weighting, and source-submission-clustered standard errors.

The estimated vertex is z_peak = -beta1 / (2*beta2), with original-scale location x_peak = exp(mu + sigma*z_peak) - 1. An interior vertex with beta2 < 0 gives an estimated increase-then-decline relationship. Strict interior support and statistically significant negative curvature are reported separately below.

| Metric | beta1 | beta2 | p(beta2) | z_peak | Peak (original units) | Observed z-range | Vertex strictly inside? | Trajectories / tasks | Negative curvature (p<0.05) |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | --- |
| Steps | 0.180935 | -0.425470 | 0.00283 | 0.212629 | 28.456810 steps | [-2.409157, 4.721472] | yes | 30,392 / 87 | significant |
| Shell invocations | -0.092329 | -0.292800 | 0.11 | -0.157666 | 15.049932 invocations | [-2.467510, 3.666785] | yes | 30,392 / 87 | not significant |
| Structured tool calls | -0.017843 | -0.249857 | 0.242 | -0.035706 | 20.743823 calls | [-2.717279, 3.736927] | yes | 30,392 / 87 | not significant |
| Total tokens | 0.207426 | -0.341140 | 0.0102 | 0.304019 | 365249.726251 tokens | [-3.260384, 3.896778] | yes | 29,441 / 87 | significant |
| Duration | -0.252262 | -0.486004 | 0.00194 | -0.259526 | 319.280740 seconds | [-2.891639, 4.222642] | yes | 30,392 / 87 | significant |
| Positive reported cost | 0.851828 | -0.288740 | 0.0254 | 1.475078 | 1.967466 USD | [-0.719122, 8.240256] | yes | 19,705 / 86 | significant |

Peak locations are point estimates without confidence intervals; they do not establish causal effects or optimal effort budgets. The descriptive effort-bin figures summarize observed pass rates separately from these fitted regressions, so their increase-then-decline patterns do not imply statistically significant curvature for every metric.

### RQ2.1

- Difficulty and task pass rate: Spearman rho = -0.483, p = 1.61e-06, n = 89 tasks.

### RQ2.2

- Post-hoc exploratory media finding: 7 media tasks averaged 16.0% versus 38.4% for 82 other tasks (delta = -22.4 pp); no confirmatory test or Cliff's delta is reported.
- Observed agent duration vs expert estimate (descriptive only): median agent duration = 7.11 min, median estimate = 60.00 min, median paired delta = -47.08 min (n = 88). Success-only median = 7.25 min; median paired delta = -46.06 min and median agent/estimate ratio = 0.124 (n = 86).
- Observed agent duration vs junior estimate (descriptive only): median agent duration = 7.11 min, median estimate = 240.00 min, median paired delta = -235.27 min (n = 88). Success-only median = 7.25 min; median paired delta = -235.46 min and median agent/estimate ratio = 0.022 (n = 86).

### RQ2.3

- Inspect/search: use rate = 88.4%, mean/median delta = 9.46/7.42 pp, r_rb = 0.773249739, W = 434.0, p = 3.75e-10 (significant; n = 89).
- Modify/write: use rate = 77.3%, mean/median delta = 5.70/3.90 pp, r_rb = 0.552769070, W = 856.0, p = 7.54e-06 (significant; n = 89).
- Execute/run: use rate = 61.1%, mean/median delta = 7.68/5.63 pp, r_rb = 0.601880878, W = 762.0, p = 1.08e-06 (significant; n = 89).
- Test/validate: use rate = 12.0%, mean/median delta = 7.56/6.67 pp, r_rb = 0.549382716, W = 730.0, p = 1.97e-05 (significant; n = 82).
- Environment/dependencies: use rate = 37.3%, mean/median delta = 2.35/2.19 pp, r_rb = 0.173644920, W = 1273.0, p = 0.183 (not significant; n = 80).
- Version control: use rate = 10.6%, mean/median delta = -2.32/-1.94 pp, r_rb = -0.113469388, W = 543.0, p = 0.489 (not significant; n = 50).
- Data query/transform: use rate = 4.0%, mean/median delta = -3.75/-2.96 pp, r_rb = -0.164835165, W = 38.0, p = 0.635 (not significant; n = 13).
- Network/external: use rate = 10.1%, mean/median delta = -2.40/-3.01 pp, r_rb = -0.202127660, W = 450.0, p = 0.228 (not significant; n = 48).
- Media/specialized: use rate = 2.2%, mean/median delta = 2.00/5.43 pp, r_rb = 0.179487179, W = 32.0, p = 0.622 (not significant; n = 12).

### RQ3.1

- 2.0->2.1: 36.6% -> 75.1% (delta = 38.45 pp; mean/median task delta = 38.45/36.79 pp), r_rb = 0.999500624, W = 1.0, p = 2.64e-16 (n = 89).
- 3.0->4.0: 21.8% -> 36.2% (delta = 14.34 pp; mean/median task delta = 14.34/14.38 pp), r_rb = 0.822324629, W = 173.5, p = 1.8e-08 (n = 66).
- Official release-fix comparison, 2.0->2.1: release-fixed tasks improved by 40.82 pp on average (median 37.52) versus 37.36 pp (median 36.44) for tasks not listed as fixed; between-group mean difference = 3.46 pp, Cliff's delta = 0.055, U = 901.0, p = 0.681 (n = 28/61).
- Official release-fix comparison, 3.0->4.0: release-fixed tasks improved by 22.30 pp on average (median 18.19) versus 11.13 pp (median 9.29) for tasks not listed as fixed; between-group mean difference = 11.17 pp, Cliff's delta = 0.357, U = 606.0, p = 0.0243 (n = 19/47).

### RQ3.3

- 2.0->2.1, Steps: source-submission-balanced shared-task medians 21 -> 18 (-14.3% ratio of cross-task medians); mean/median paired task delta = -3.31/-3.5, r_rb = -0.410135841, W = 1129.0, p = 0.000889 (n = 89). Refreshed pooled trajectory medians are descriptive only: 21 -> 18 (-14.3%).
- 2.0->2.1, Shell invocations: source-submission-balanced shared-task medians 20.5 -> 16 (-22.0% ratio of cross-task medians); mean/median paired task delta = -5.78/-4.5, r_rb = -0.599529781, W = 766.5, p = 1.18e-06 (n = 89). Refreshed pooled trajectory medians are descriptive only: 20 -> 15 (-25.0%).
- 2.0->2.1, Structured tool calls: source-submission-balanced shared-task medians 23.8 -> 19 (-20.0% ratio of cross-task medians); mean/median paired task delta = -5.19/-5, r_rb = -0.514629049, W = 929.0, p = 3.05e-05 (n = 89). Refreshed pooled trajectory medians are descriptive only: 23 -> 19 (-17.4%).
- 2.0->2.1, Duration: source-submission-balanced shared-task medians 434 -> 378 (-13.0% ratio of cross-task medians); mean/median paired task delta = -39/-57.8, r_rb = -0.344818976, W = 1312.0, p = 0.00473 (n = 89). Refreshed pooled trajectory medians are descriptive only: 409 -> 377 (-7.8%).
- 2.0->2.1, Total tokens: source-submission-balanced shared-task medians 2.42e+05 -> 3e+05 (+23.8% ratio of cross-task medians); mean/median paired task delta = 2.03e+05/6.03e+04, r_rb = 0.460674157, W = 1080.0, p = 0.00016 (n = 89). Refreshed pooled trajectory medians are descriptive only: 2.14e+05 -> 2.83e+05 (+32.2%).
- 3.0->4.0, Steps: source-submission-balanced shared-task medians 76.5 -> 59.8 (-21.9% ratio of cross-task medians); mean/median paired task delta = -9.48/-11.2, r_rb = -0.610583446, W = 430.5, p = 1.61e-05 (n = 66). Refreshed pooled trajectory medians are descriptive only: 71 -> 60 (-15.5%).
- 3.0->4.0, Shell invocations: source-submission-balanced shared-task medians 59.9 -> 49.2 (-17.7% ratio of cross-task medians); mean/median paired task delta = -3.48/-6, r_rb = -0.427860697, W = 632.5, p = 0.00251 (n = 66). Refreshed pooled trajectory medians are descriptive only: 55 -> 47 (-14.5%).
- 3.0->4.0, Structured tool calls: source-submission-balanced shared-task medians 82.2 -> 63 (-23.4% ratio of cross-task medians); mean/median paired task delta = -10.3/-9.75, r_rb = -0.631840796, W = 407.0, p = 8.11e-06 (n = 66). Refreshed pooled trajectory medians are descriptive only: 75 -> 63 (-16.0%).
- 3.0->4.0, Duration: source-submission-balanced shared-task medians 2.14e+03 -> 1.48e+03 (-31.0% ratio of cross-task medians); mean/median paired task delta = -589/-546, r_rb = -0.837177748, W = 180.0, p = 3.38e-09 (n = 66). Refreshed pooled trajectory medians are descriptive only: 1.97e+03 -> 1.64e+03 (-16.8%).
- 3.0->4.0, Total tokens: source-submission-balanced shared-task medians 8.39e+06 -> 5.27e+06 (-37.2% ratio of cross-task medians); mean/median paired task delta = -2.54e+06/-2.17e+06, r_rb = -0.655359566, W = 381.0, p = 3.69e-06 (n = 66). Refreshed pooled trajectory medians are descriptive only: 8.06e+06 -> 5.3e+06 (-34.3%).

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

Statistical inference used tasks as the unit of analysis after task-balanced aggregation: where submission identifiers were available, trajectories were first summarized within submission-task pairs and then across submissions. Inferential paired task comparisons used two-sided Wilcoxon signed-rank tests with matched-pairs rank-biserial correlation, while comparisons of independent task groups used two-sided Mann-Whitney U tests with Cliff's delta. Ordinal difficulty associations used Spearman's rho, and RQ1.2 retained the quadratic conditional-logistic coefficient beta2 and its two-sided test of H0: beta2=0. Agent-duration versus human-estimate comparisons remained descriptive because they measure different constructs. Post-hoc media, Pareto, composition, subgroup, diagnostic token, and sparse shared-configuration analyses remained descriptive.

## Thesis wording changes

No thesis manuscript or Results-section source file is present in the repository, so exact sentence-level edits could not be marked in place. Apply these claim-level replacements:

- RQ1.1: reserve 'statistically significant' for metrics with p<0.05 in the table above, and always pair it with the signed median difference and r_rb. Do not infer the task-level direction from pooled success/failure medians where the repository flags a reversal.
- RQ2.3: use 'was associated with' rather than causal language. State that support means three use and three non-use trajectories per task, not three distinct submissions, and do not claim subgroup significance from category/difficulty figures.
- RQ3.1: state improvement using the paired shared-task results. Use official release-fixed versus not-listed-as-fixed task groups and the between-group Mann-Whitney/Cliff comparison. TB2.1 uses the 28 enumerated release IDs; the README/PR count of 26 differs by crack-7z-hash and gpt2-codegolf. TB4.0 calibrates resources for all retained tasks, so the 47 tasks not listed as fixed are not wholly unchanged. Separate within-group p-values do not test the between-group contrast.
- RQ3.3: use source-submission-balanced shared-task medians for the main figures and text. Distinguish ratios of cross-task medians from the paired absolute differences used for inference. Describe increases/decreases as statistically supported only where the paired Wilcoxon p-value is below 0.05, and include r_rb.
- Cost: do not add a longitudinal cost test. Cost is not a current headline RQ3.3 metric; positive-cost coverage is 25,840/38,604 (66.9%) for TB2.0/TB2.1 and 7,362/10,239 (71.9%) for TB3.0/TB4.0, and coverage is configuration-dependent, so comparability is inadequate for the requested primary analysis.

## Master inferential table

The machine-readable table contains 38 inferential rows. Descriptive-only analyses are deliberately excluded.

| RQ | Analysis | Comparison | Metric | n | Raw effect | Effect size | Test statistic | p | Direction |
| --- | --- | --- | --- | --: | --: | ---: | --: | --: | --- |
| RQ1.1 | successful vs failed trajectories | success - failure | Steps | 86 | 2 steps | rank_biserial=0.1904 | 1480 | 0.1272 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Shell invocations | 86 | 0.375 invocations | rank_biserial=0.09907 | 1496 | 0.4386 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Structured tool calls | 86 | 1.125 calls | rank_biserial=0.1976 | 1398 | 0.1177 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Input tokens | 85 | 2.162e+04 tokens | rank_biserial=0.3029 | 1274 | 0.0153 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Output tokens | 85 | -29.5 tokens | rank_biserial=0.06375 | 1711 | 0.6097 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Total tokens | 85 | 2.027e+04 tokens | rank_biserial=0.2799 | 1316 | 0.02501 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Duration | 86 | -44.89 seconds | rank_biserial=-0.3638 | 1190 | 0.003387 | positive = higher for successful trajectories |
| RQ1.1 | successful vs failed trajectories | success - failure | Cost | 83 | 0.08621 USD | rank_biserial=0.7791 | 385 | 7.026e-10 | positive = higher for successful trajectories |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Steps | 87 | -0.4255 standardized quadratic log-effort coefficient | beta_2=-0.4255 | -2.986 | 0.002831 | negative = concave-down conditional relationship |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Shell invocations | 87 | -0.2928 standardized quadratic log-effort coefficient | beta_2=-0.2928 | -1.598 | 0.11 | negative = concave-down conditional relationship |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Structured tool calls | 87 | -0.2499 standardized quadratic log-effort coefficient | beta_2=-0.2499 | -1.169 | 0.2424 | negative = concave-down conditional relationship |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Total tokens | 87 | -0.3411 standardized quadratic log-effort coefficient | beta_2=-0.3411 | -2.57 | 0.01018 | negative = concave-down conditional relationship |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Duration | 87 | -0.486 standardized quadratic log-effort coefficient | beta_2=-0.486 | -3.1 | 0.001937 | negative = concave-down conditional relationship |
| RQ1.2 | quadratic conditional logistic regression | H0: beta_2 = 0 | Cost | 86 | -0.2887 standardized quadratic log-effort coefficient | beta_2=-0.2887 | -2.235 | 0.0254 | negative = concave-down conditional relationship |
| RQ2.1 | difficulty vs task pass rate | ordinal difficulty | Task-balanced pass rate | 89 | -0.4833 rho | spearman_rho=-0.4833 | -0.4833 | 1.609e-06 | negative = lower pass rate at greater difficulty |
| RQ2.3 | functional behavior use vs success | used - not used | Inspect/search | 89 | 9.459 percentage points (mean task contrast) | rank_biserial=0.7732 | 434 | 3.754e-10 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Modify/write | 89 | 5.699 percentage points (mean task contrast) | rank_biserial=0.5528 | 856 | 7.539e-06 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Execute/run | 89 | 7.684 percentage points (mean task contrast) | rank_biserial=0.6019 | 762 | 1.084e-06 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Test/validate | 82 | 7.564 percentage points (mean task contrast) | rank_biserial=0.5494 | 730 | 1.966e-05 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Environment/dependencies | 80 | 2.345 percentage points (mean task contrast) | rank_biserial=0.1736 | 1273 | 0.1827 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Version control | 50 | -2.323 percentage points (mean task contrast) | rank_biserial=-0.1135 | 543 | 0.4894 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Data query/transform | 13 | -3.747 percentage points (mean task contrast) | rank_biserial=-0.1648 | 38 | 0.6355 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Network/external | 48 | -2.405 percentage points (mean task contrast) | rank_biserial=-0.2021 | 450 | 0.2277 | positive = behavior use associated with higher success |
| RQ2.3 | functional behavior use vs success | used - not used | Media/specialized | 12 | 2.003 percentage points (mean task contrast) | rank_biserial=0.1795 | 32 | 0.6221 | positive = behavior use associated with higher success |
| RQ3.1 | benchmark-version performance | 2.0->2.1 | Task-balanced pass rate | 89 | 38.45 percentage points | rank_biserial=0.9995 | 1 | 2.639e-16 | positive = higher performance in the newer version |
| RQ3.1 | benchmark-version performance | 3.0->4.0 | Task-balanced pass rate | 66 | 14.34 percentage points | rank_biserial=0.8223 | 173.5 | 1.801e-08 | positive = higher performance in the newer version |
| RQ3.1 | official release-fix comparison | 2.0->2.1 | Task pass-rate improvement | 89 | 3.456 percentage points | cliffs_delta=0.05504 | 901 | 0.6812 | positive = release-fixed tasks tended to improve more |
| RQ3.1 | official release-fix comparison | 3.0->4.0 | Task pass-rate improvement | 66 | 11.17 percentage points | cliffs_delta=0.3572 | 606 | 0.02431 | positive = release-fixed tasks tended to improve more |
| RQ3.3 | benchmark-version interaction/resource change | 2.0->2.1 | Steps | 89 | -3.5 steps | rank_biserial=-0.4101 | 1129 | 0.0008895 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 2.0->2.1 | Shell invocations | 89 | -4.5 invocations | rank_biserial=-0.5995 | 766.5 | 1.179e-06 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 2.0->2.1 | Structured tool calls | 89 | -5 calls | rank_biserial=-0.5146 | 929 | 3.051e-05 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 2.0->2.1 | Duration | 89 | -57.8 seconds | rank_biserial=-0.3448 | 1312 | 0.004727 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 2.0->2.1 | Total tokens | 89 | 6.034e+04 tokens | rank_biserial=0.4607 | 1080 | 0.0001605 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 3.0->4.0 | Steps | 66 | -11.25 steps | rank_biserial=-0.6106 | 430.5 | 1.614e-05 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 3.0->4.0 | Shell invocations | 66 | -6 invocations | rank_biserial=-0.4279 | 632.5 | 0.002511 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 3.0->4.0 | Structured tool calls | 66 | -9.75 calls | rank_biserial=-0.6318 | 407 | 8.105e-06 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 3.0->4.0 | Duration | 66 | -546.5 seconds | rank_biserial=-0.8372 | 180 | 3.376e-09 | positive = metric increased in the newer version |
| RQ3.3 | benchmark-version interaction/resource change | 3.0->4.0 | Total tokens | 66 | -2.167e+06 tokens | rank_biserial=-0.6554 | 381 | 3.689e-06 | positive = metric increased in the newer version |
