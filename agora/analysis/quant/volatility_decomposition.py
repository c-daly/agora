"""Volatility decomposition analysis module.

Separates total price volatility into overnight and intraday components, and
computes the variance risk premium by comparing realized vs implied volatility.
Operates on pre-computed price data. Does not fetch any data itself.
"""

from __future__ import annotations

import numpy as np

_MIN_PERIODS = 2


def decompose_volatility(
    close_prices: list[float],
    open_prices: list[float],
) -> dict:
    """Separate total volatility into overnight and intraday components.

    Overnight return for day *t* is defined as ``open[t] / close[t-1] - 1``.
    Intraday return for day *t* is defined as ``close[t] / open[t] - 1``.
    Total close-to-close return is the combination of both.

    Volatility is reported as annualized standard deviation (assuming 252
    trading days per year).

    Parameters
    ----------
    close_prices:
        List of daily closing prices in chronological order. Must contain at
        least 2 elements.
    open_prices:
        List of daily opening prices in chronological order. Must be the same
        length as *close_prices*.

    Returns
    -------
    dict with keys:
        - total_vol: float  annualized close-to-close volatility
        - overnight_vol: float  annualized overnight volatility
        - intraday_vol: float  annualized intraday volatility
        - overnight_fraction: float  share of total variance from overnight
        - n_periods: int  number of return observations used

    Raises
    ------
    ValueError
        If inputs are invalid (mismatched lengths, too few observations,
        non-positive prices).
    """
    _validate_prices(close_prices, open_prices)

    close = np.array(close_prices, dtype=np.float64)
    opn = np.array(open_prices, dtype=np.float64)

    # Overnight returns: open[t] / close[t-1] - 1  (for t = 1..N-1)
    overnight_returns = opn[1:] / close[:-1] - 1.0

    # Intraday returns: close[t] / open[t] - 1  (for t = 1..N-1)
    intraday_returns = close[1:] / opn[1:] - 1.0

    # Close-to-close returns: close[t] / close[t-1] - 1
    total_returns = close[1:] / close[:-1] - 1.0

    annualization = np.sqrt(252.0)

    overnight_std = float(np.std(overnight_returns, ddof=1))
    intraday_std = float(np.std(intraday_returns, ddof=1))
    total_std = float(np.std(total_returns, ddof=1))

    overnight_var = overnight_std**2
    total_var = total_std**2

    overnight_fraction = overnight_var / total_var if total_var > 0 else 0.0

    return {
        "total_vol": round(total_std * annualization, 8),
        "overnight_vol": round(overnight_std * annualization, 8),
        "intraday_vol": round(intraday_std * annualization, 8),
        "overnight_fraction": round(overnight_fraction, 8),
        "n_periods": len(total_returns),
    }


def compute_variance_risk_premium(
    realized_vol: float,
    implied_vol: float,
) -> dict:
    """Compute the variance risk premium from realized and implied volatility.

    The variance risk premium (VRP) is the difference between implied and
    realized variance.  A positive VRP indicates that options are priced above
    realized risk, which is typical because investors pay a premium for
    downside protection.

    Parameters
    ----------
    realized_vol:
        Annualized realized volatility (standard deviation), expressed as a
        decimal (e.g. 0.20 for 20%).
    implied_vol:
        Annualized implied volatility from options markets, expressed as a
        decimal.

    Returns
    -------
    dict with keys:
        - realized_vol: float  the input realized volatility
        - implied_vol: float  the input implied volatility
        - realized_var: float  realized variance (vol squared)
        - implied_var: float  implied variance (vol squared)
        - vrp: float  variance risk premium (implied_var - realized_var)
        - vrp_ratio: float  ratio of implied_vol to realized_vol
        - signal: str  "rich" if VRP > 0 else "cheap"

    Raises
    ------
    ValueError
        If either volatility is negative.
    """
    if realized_vol < 0:
        msg = f"realized_vol must be non-negative, got {realized_vol}"
        raise ValueError(msg)
    if implied_vol < 0:
        msg = f"implied_vol must be non-negative, got {implied_vol}"
        raise ValueError(msg)

    realized_var = realized_vol**2
    implied_var = implied_vol**2
    vrp = implied_var - realized_var

    vrp_ratio = implied_vol / realized_vol if realized_vol > 0 else float("inf")

    return {
        "realized_vol": round(realized_vol, 8),
        "implied_vol": round(implied_vol, 8),
        "realized_var": round(realized_var, 8),
        "implied_var": round(implied_var, 8),
        "vrp": round(vrp, 8),
        "vrp_ratio": round(vrp_ratio, 8) if vrp_ratio != float("inf") else float("inf"),
        "signal": "rich" if vrp > 0 else "cheap",
    }


def _validate_prices(
    close_prices: list[float],
    open_prices: list[float],
) -> None:
    """Validate price inputs for decompose_volatility."""
    if len(close_prices) != len(open_prices):
        msg = (
            f"close_prices and open_prices must have the same length, "
            f"got {len(close_prices)} and {len(open_prices)}"
        )
        raise ValueError(msg)

    if len(close_prices) < _MIN_PERIODS:
        msg = (
            f"Need at least {_MIN_PERIODS} price observations, "
            f"got {len(close_prices)}"
        )
        raise ValueError(msg)

    for i, (c, o) in enumerate(zip(close_prices, open_prices)):
        if c <= 0:
            msg = f"close_prices[{i}] must be positive, got {c}"
            raise ValueError(msg)
        if o <= 0:
            msg = f"open_prices[{i}] must be positive, got {o}"
            raise ValueError(msg)
