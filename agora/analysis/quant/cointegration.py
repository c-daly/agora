"""Cointegration analysis for pairs trading.

Implements the Engle-Granger two-step cointegration test and spread
computation for mean-reversion monitoring.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy import stats

# Minimum observations required for a meaningful ADF regression.
_MIN_OBSERVATIONS = 30


def _validate_inputs(
    series_a: list[float], series_b: list[float]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Validate and convert input series to numpy arrays.

    Raises
    ------
    ValueError
        If the series are too short, mismatched in length, or degenerate
        (constant / identical).
    """
    if len(series_a) != len(series_b):
        raise ValueError(
            f"Series length mismatch: {len(series_a)} vs {len(series_b)}"
        )
    if len(series_a) < _MIN_OBSERVATIONS:
        raise ValueError(
            f"Insufficient data: need >= {_MIN_OBSERVATIONS} observations, got {len(series_a)}"
        )

    a = np.asarray(series_a, dtype=np.float64)
    b = np.asarray(series_b, dtype=np.float64)

    if np.std(a) == 0.0:
        raise ValueError("series_a is constant")
    if np.std(b) == 0.0:
        raise ValueError("series_b is constant")
    if np.array_equal(a, b):
        raise ValueError("series_a and series_b are identical")

    return a, b


# MacKinnon (2010) critical values for the Engle-Granger cointegration
# test with 2 variables ("c" case -- constant, no trend).  The table maps
# significance level -> tau critical value.
_EG_CRITICAL_VALUES: list[tuple[float, float]] = [
    (0.01, -3.90),
    (0.05, -3.34),
    (0.10, -3.04),
]


def _interpolate_p_value(t_stat: float) -> float:
    """Approximate the p-value from the ADF t-statistic using MacKinnon critical values.

    Performs piecewise-linear interpolation between known critical values.
    Returns conservative bounds outside the table range.
    """
    # Sorted from most significant (smallest p) to least
    # If t_stat is more negative than the 1% critical value -> p < 0.01
    if t_stat <= _EG_CRITICAL_VALUES[0][1]:
        return _EG_CRITICAL_VALUES[0][0] / 2.0  # 0.005

    # If t_stat is less negative than the 10% critical value -> p > 0.10
    if t_stat >= _EG_CRITICAL_VALUES[-1][1]:
        # Use a rough linear extrapolation toward 1.0
        return min(1.0, 0.10 + 0.30 * (t_stat - _EG_CRITICAL_VALUES[-1][1]))

    # Interpolate between adjacent critical values
    for i in range(len(_EG_CRITICAL_VALUES) - 1):
        p_lo, cv_lo = _EG_CRITICAL_VALUES[i]      # e.g. (0.01, -3.90)
        p_hi, cv_hi = _EG_CRITICAL_VALUES[i + 1]  # e.g. (0.05, -3.34)
        if cv_lo <= t_stat <= cv_hi:
            frac = (t_stat - cv_lo) / (cv_hi - cv_lo)
            return p_lo + frac * (p_hi - p_lo)

    return 1.0  # pragma: no cover


def _adf_p_value(residuals: NDArray[np.float64]) -> float:
    """Compute the Augmented Dickey-Fuller p-value for residuals.

    Uses a simple ADF(1) regression:
        delta_e(t) = alpha + beta * e(t-1) + error

    The t-statistic for beta is compared against MacKinnon (2010)
    critical values for the Engle-Granger 2-variable case.

    For the Engle-Granger test the null is 'no cointegration' (unit root
    in the residuals), so a small p-value rejects the null and indicates
    cointegration.
    """
    e = residuals
    delta_e = np.diff(e)
    e_lagged = e[:-1]

    # OLS: delta_e = alpha + beta * e_lagged
    x = np.column_stack([np.ones(len(e_lagged)), e_lagged])
    result = np.linalg.lstsq(x, delta_e, rcond=None)
    coeffs = result[0]
    beta = coeffs[1]

    # Residuals of the ADF regression
    fitted = x @ coeffs
    adf_resid = delta_e - fitted
    mse = float(np.sum(adf_resid**2) / (len(adf_resid) - 2))

    # Standard error of beta
    xtx_inv = np.linalg.inv(x.T @ x)
    se_beta = float(np.sqrt(mse * xtx_inv[1, 1]))

    if se_beta == 0.0:
        return 1.0

    t_stat = beta / se_beta
    return _interpolate_p_value(t_stat)


def check_cointegration(
    series_a: list[float], series_b: list[float]
) -> dict:
    """Run the Engle-Granger two-step cointegration test.

    Parameters
    ----------
    series_a, series_b
        Price series of equal length (>= 30 observations).

    Returns
    -------
    dict
        Keys: cointegrated (bool), p_value (float), hedge_ratio (float),
        spread_mean (float), spread_std (float).
    """
    a, b = _validate_inputs(series_a, series_b)

    # Step 1 -- OLS regression: a = hedge_ratio * b + intercept + residuals
    slope, intercept, _, _, _ = stats.linregress(b, a)
    hedge_ratio = float(slope)

    # Spread (residuals of the cointegrating regression)
    spread = a - (hedge_ratio * b + intercept)
    spread_mean = float(np.mean(spread))
    spread_std = float(np.std(spread, ddof=1))

    # Step 2 -- ADF test on the residuals
    p_value = _adf_p_value(spread)

    return {
        "cointegrated": bool(p_value < 0.05),
        "p_value": round(p_value, 6),
        "hedge_ratio": round(hedge_ratio, 6),
        "spread_mean": round(spread_mean, 6),
        "spread_std": round(spread_std, 6),
    }


def compute_spread(
    series_a: list[float],
    series_b: list[float],
    hedge_ratio: float,
) -> list[float]:
    """Compute the spread between two price series for mean-reversion monitoring.

    Parameters
    ----------
    series_a, series_b
        Price series of equal length.
    hedge_ratio
        The coefficient from the cointegrating regression.

    Returns
    -------
    list[float]
        The spread series: series_a - hedge_ratio * series_b.
    """
    if len(series_a) != len(series_b):
        raise ValueError(
            f"Series length mismatch: {len(series_a)} vs {len(series_b)}"
        )
    if len(series_a) == 0:
        return []

    a = np.asarray(series_a, dtype=np.float64)
    b = np.asarray(series_b, dtype=np.float64)
    spread = a - hedge_ratio * b
    return [round(float(v), 6) for v in spread]
