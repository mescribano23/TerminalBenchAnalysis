"""Small, shared helpers for the thesis' task-level statistical inference."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, wilcoxon


def numeric_values(values: pd.Series | np.ndarray | list[float]) -> np.ndarray:
    """Return finite numeric values as a one-dimensional float array."""
    series = pd.to_numeric(pd.Series(values), errors="coerce")
    return series[np.isfinite(series)].to_numpy(dtype=float)


def paired_cohens_dz(differences: pd.Series | np.ndarray | list[float]) -> float:
    """Cohen's dz = mean(D) / sample SD(D) for paired differences."""
    values = numeric_values(differences)
    if values.size < 2:
        return np.nan
    sample_sd = float(np.std(values, ddof=1))
    mean_difference = float(np.mean(values))
    if np.isclose(sample_sd, 0.0):
        if np.isclose(mean_difference, 0.0):
            return 0.0
        return float(np.copysign(np.inf, mean_difference))
    return mean_difference / sample_sd


def two_sided_signed_rank(
    differences: pd.Series | np.ndarray | list[float],
) -> tuple[float, float, int]:
    """Two-sided Wilcoxon signed-rank test with Wilcox zero handling.

    Returns the statistic, p-value, and number of nonzero pairs. An all-zero
    contrast is represented explicitly as W=0 and p=1.
    """
    values = numeric_values(differences)
    nonzero_n = int(np.count_nonzero(values))
    if values.size == 0:
        return np.nan, np.nan, 0
    if nonzero_n == 0:
        return 0.0, 1.0, 0
    result = wilcoxon(
        values,
        alternative="two-sided",
        zero_method="wilcox",
        method="auto",
    )
    return float(result.statistic), float(result.pvalue), nonzero_n


def cliffs_delta(
    x: pd.Series | np.ndarray | list[float],
    y: pd.Series | np.ndarray | list[float],
) -> float:
    """Cliff's delta, positive when values in x tend to exceed values in y."""
    x_values = numeric_values(x)
    y_values = numeric_values(y)
    if x_values.size == 0 or y_values.size == 0:
        return np.nan
    comparisons = x_values[:, None] - y_values[None, :]
    return float((np.count_nonzero(comparisons > 0) - np.count_nonzero(comparisons < 0)) /
                 comparisons.size)


def two_sided_mann_whitney(
    x: pd.Series | np.ndarray | list[float],
    y: pd.Series | np.ndarray | list[float],
) -> tuple[float, float]:
    """Two-sided Mann--Whitney U test for two independent task groups."""
    x_values = numeric_values(x)
    y_values = numeric_values(y)
    if x_values.size == 0 or y_values.size == 0:
        return np.nan, np.nan
    result = mannwhitneyu(x_values, y_values, alternative="two-sided", method="auto")
    return float(result.statistic), float(result.pvalue)
