# Diminishing Returns Analysis

## Research Question

How does the probability of Terminal-Bench success vary with observed trajectory effort?

## Data Summary

- Trajectories analyzed: 5,265
- Passes: 1,992
- Failures: 3,273
- Overall success rate: 37.8%
- Rows excluded because `reward` was not binary 0/1: 0
- Cost coverage caveat: `cost_usd_positive` is defined only where reported cost is positive (3,065 trajectories, 58.2%). Zero-cost rows are not interpreted as free execution.
- Scaffold-normalized step caveat: `step_count_scaffold_ratio` divides each trajectory's step count by the median step count for its scaffold (5,265 complete cases). This helps compare scaffolds, but it remains a post-hoc normalization.

## Method

This analysis groups completed trajectories into effort bins and computes the empirical success rate in each bin. Success rates are reported with Wilson 95% confidence intervals to show uncertainty around bin-level estimates.

This analysis is post-hoc: it uses completed trajectories and final effort values. It can identify low-return regions in completed runs, but it does not prove that an online agent should have stopped earlier.

## Main Step-Count Bin Table

| Bin | n | Passes | Success rate | Wilson CI low | Wilson CI high |
| --- | --- | --- | --- | --- | --- |
| 0-10 | 1,284 | 351 | 27.3% | 25.0% | 29.8% |
| 11-25 | 1,187 | 567 | 47.8% | 44.9% | 50.6% |
| 26-50 | 1,078 | 519 | 48.1% | 45.2% | 51.1% |
| 51-100 | 950 | 398 | 41.9% | 38.8% | 45.1% |
| 101-200 | 548 | 135 | 24.6% | 21.2% | 28.4% |
| >200 | 218 | 22 | 10.1% | 6.8% | 14.8% |

## High-Effort Summary

| Effort variable | High-effort bin | n | Success rate | Wilson CI low | Wilson CI high | Low support |
| --- | --- | --- | --- | --- | --- | --- |
| Command count | >40 | 1,113 | 27.5% | 25.0% | 30.2% | False |
| Positive cost USD | >$1 | 373 | 10.2% | 7.5% | 13.7% | False |
| Duration seconds | >60m | 5 | 0.0% | 0.0% | 43.4% | True |
| Step count | >200 | 218 | 10.1% | 6.8% | 14.8% | False |
| Step count / scaffold median | >4x | 462 | 11.5% | 8.9% | 14.7% | False |
| Tool call count | >150 | 227 | 13.2% | 9.4% | 18.2% | False |
| Total tokens | >10M | 90 | 11.1% | 6.1% | 19.3% | False |

## Interpretation

Success generally peaks at moderate observed effort rather than at the longest trajectories. Very high-effort bins have lower success rates for the main effort measures, consistent with a diminishing-returns pattern.

## Generated Files

- `data/processed/diminishing_returns_effort_bins.csv`
- `data/processed/diminishing_returns_variable_coverage.csv`
- `reports/diminishing_returns_analysis.md`
- `reports/figures/diminishing_returns_step_count.png`
- `reports/figures/diminishing_returns_step_count_scaffold_ratio.png`
- `reports/figures/diminishing_returns_command_count.png`
- `reports/figures/diminishing_returns_tool_call_count.png`
- `reports/figures/diminishing_returns_total_tokens.png`
- `reports/figures/diminishing_returns_duration_seconds_from_timestamps.png`
- `reports/figures/diminishing_returns_cost_usd_positive.png`
