"""Correlation matrix analysis module.

Computes static and rolling pairwise correlation matrices from return series,
and detects regime changes in correlation structure. Operates on pre-computed
return data. Does not fetch any data itself.
"""

from __future__ import annotations

import numpy as np


def compute_correlation_matrix(returns: dict[str, list[float]]) -> dict:
    """Compute a static pairwise Pearson correlation matrix from daily returns.

    Parameters
    ----------
    returns:
        Mapping of symbol to list of daily returns. All lists must have the
        same length.

    Returns
    -------
    dict with keys:
        - symbols: list[str] ordered symbol labels
        - matrix: list[list[float]] correlation matrix (row-major)
    """
    if not returns:
        return {"symbols": [], "matrix": []}

    symbols = sorted(returns.keys())
    n_symbols = len(symbols)

    if n_symbols == 1:
        return {"symbols": symbols, "matrix": [[1.0]]}

    # Build 2-D array: each row is one symbol's return series
    data = np.array([returns[s] for s in symbols], dtype=np.float64)

    # np.corrcoef returns the full correlation matrix
    corr = np.corrcoef(data)

    # Replace any NaN (e.g. zero-variance series) with 0.0
    corr = np.where(np.isnan(corr), 0.0, corr)

    return {
        "symbols": symbols,
        "matrix": corr.tolist(),
    }


def compute_rolling_correlation(
    returns: dict[str, list[float]],
    window: int = 60,
) -> list[dict]:
    """Compute rolling-window pairwise correlation matrices.

    Slides a window across the return series and computes a correlation matrix
    at each step. Useful for detecting shifts in correlation regime over time.

    Parameters
    ----------
    returns:
        Mapping of symbol to list of daily returns. All lists must have the
        same length and be at least *window* elements long.
    window:
        Number of observations in each rolling window.

    Returns
    -------
    List of dicts, each with:
        - date_index: int  (the ending index of the window, 0-based)
        - matrix: list[list[float]]  correlation matrix for that window
    """
    if not returns:
        return []

    symbols = sorted(returns.keys())
    data = np.array([returns[s] for s in symbols], dtype=np.float64)
    n_obs = data.shape[1]

    if n_obs < window:
        return []

    results: list[dict] = []
    for end in range(window, n_obs + 1):
        window_data = data[:, end - window : end]
        corr = np.corrcoef(window_data)
        corr = np.where(np.isnan(corr), 0.0, corr)
        results.append({
            "date_index": end - 1,
            "matrix": corr.tolist(),
        })

    return results


def detect_regime_change(
    rolling_corrs: list[dict],
    threshold: float = 0.3,
) -> list[dict]:
    """Identify periods where the correlation structure shifts significantly.

    Compares consecutive correlation matrices using the Frobenius norm of their
    difference, normalized by the number of unique pairs. When the normalized
    distance exceeds *threshold*, a regime change is flagged.

    Parameters
    ----------
    rolling_corrs:
        Output of :func:`compute_rolling_correlation`.
    threshold:
        Minimum normalized Frobenius distance to flag a regime change.

    Returns
    -------
    List of dicts, each with:
        - date_index: int  (the date_index where the change was detected)
        - distance: float  (the normalized Frobenius distance)
        - direction: str   ("increase" or "decrease" in avg correlation)
    """
    if len(rolling_corrs) < 2:
        return []

    changes: list[dict] = []

    for i in range(1, len(rolling_corrs)):
        prev = np.array(rolling_corrs[i - 1]["matrix"], dtype=np.float64)
        curr = np.array(rolling_corrs[i]["matrix"], dtype=np.float64)

        diff = curr - prev
        n = prev.shape[0]

        # Number of unique off-diagonal pairs
        n_pairs = n * (n - 1) / 2
        if n_pairs == 0:
            continue

        # Extract upper-triangle (off-diagonal) of diff for normalized distance
        upper_idx = np.triu_indices(n, k=1)
        upper_diff = diff[upper_idx]
        distance = float(np.sqrt(np.sum(upper_diff**2) / n_pairs))

        if distance >= threshold:
            # Direction: compare mean off-diagonal correlation
            prev_mean = float(np.mean(prev[upper_idx]))
            curr_mean = float(np.mean(curr[upper_idx]))
            direction = "increase" if curr_mean > prev_mean else "decrease"

            changes.append({
                "date_index": rolling_corrs[i]["date_index"],
                "distance": round(distance, 6),
                "direction": direction,
            })

    return changes
