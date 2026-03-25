"""Short factor analysis module for decomposing short interest signals.

Determines whether short interest across a set of positions loads on
known risk factors (sector, size, value) or represents an independent
alpha signal, using OLS regression via numpy.
"""

from __future__ import annotations

import numpy as np


_RESIDUAL_THRESHOLD = 0.5


class ShortFactorAnalysisError(Exception):
    """Raised when short factor analysis cannot be performed."""


def analyze_short_factors(
    short_positions: dict[str, float],
    factor_loadings: dict[str, dict[str, float]],
) -> dict:
    """Analyze whether short interest loads on known factors or is independent.

    Regresses the vector of short-position weights on factor-loading columns
    to determine how much of the short interest pattern is explained by
    known factors versus representing an independent signal.

    Parameters
    ----------
    short_positions:
        Mapping of symbol to short-interest weight (e.g. fraction of
        portfolio or percentage of float).  Must contain at least two
        symbols.
    factor_loadings:
        Mapping of factor name (e.g. ``"sector"``, ``"size"``, ``"value"``)
        to a dict mapping symbol to that factor loading for the symbol.
        Every symbol in *short_positions* must appear in every factor
        loading dict.  At least one factor must be provided.

    Returns
    -------
    dict with keys:
        factor_exposures          -- dict[str, float] mapping factor name
                                     to its regression coefficient on the
                                     short-interest vector.
        unexplained_fraction      -- float in [0, 1]; fraction of short
                                     interest variance not explained by
                                     the factors (1 - R-squared).
        independent_signal_strength -- float in [0, 1]; strength of the
                                       independent (non-factor) component.
                                       Equals unexplained_fraction when
                                       there is residual variance, 0.0 when
                                       factors explain everything.
        symbols_with_high_residual -- list[str]; symbols whose absolute
                                      residual exceeds the median absolute
                                      residual by more than
                                      ``_RESIDUAL_THRESHOLD`` standard
                                      deviations of the residuals.

    Raises
    ------
    ShortFactorAnalysisError
        If the inputs are invalid or the regression cannot be performed.
    """
    _validate_inputs(short_positions, factor_loadings)

    symbols = sorted(short_positions.keys())
    factor_names = sorted(factor_loadings.keys())

    # ---- build response vector and design matrix -------------------------
    y = np.array([short_positions[s] for s in symbols], dtype=np.float64)
    X = _build_design_matrix(symbols, factor_names, factor_loadings)

    # ---- OLS via numpy.linalg.lstsq -------------------------------------
    try:
        coeffs, _, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    except np.linalg.LinAlgError as exc:
        raise ShortFactorAnalysisError(
            f"OLS regression failed: {exc}"
        ) from exc

    n_params = len(factor_names) + 1  # intercept + factors
    if rank < n_params:
        raise ShortFactorAnalysisError(
            f"Design matrix is rank-deficient (rank {rank}, expected {n_params}). "
            "Check for linearly dependent factors."
        )

    # ---- unpack results --------------------------------------------------
    # coeffs[0] is intercept; coeffs[1:] are factor betas
    factor_exposures = {
        name: float(coeffs[i + 1]) for i, name in enumerate(factor_names)
    }

    residuals = y - X @ coeffs
    r_squared = _compute_r_squared(y, residuals)
    unexplained_fraction = round(1.0 - r_squared, 12)
    # Clamp to [0, 1] to avoid floating-point artifacts
    unexplained_fraction = max(0.0, min(1.0, unexplained_fraction))

    independent_signal_strength = unexplained_fraction

    high_residual_symbols = _find_high_residual_symbols(symbols, residuals)

    return {
        "factor_exposures": factor_exposures,
        "unexplained_fraction": unexplained_fraction,
        "independent_signal_strength": independent_signal_strength,
        "symbols_with_high_residual": high_residual_symbols,
    }


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------


def _validate_inputs(
    short_positions: dict[str, float],
    factor_loadings: dict[str, dict[str, float]],
) -> None:
    """Raise *ShortFactorAnalysisError* for malformed inputs."""
    if not short_positions:
        raise ShortFactorAnalysisError("At least one short position must be provided.")

    if len(short_positions) < 2:
        raise ShortFactorAnalysisError(
            "At least two short positions are required for regression."
        )

    if not factor_loadings:
        raise ShortFactorAnalysisError("At least one factor must be provided.")

    symbols = set(short_positions.keys())
    n_params = len(factor_loadings) + 1  # intercept + factors
    if len(symbols) <= n_params:
        raise ShortFactorAnalysisError(
            f"Insufficient symbols: {len(symbols)} symbols for {n_params} parameters "
            f"(need at least {n_params + 1})."
        )

    for factor_name, loadings in factor_loadings.items():
        missing = symbols - set(loadings.keys())
        if missing:
            raise ShortFactorAnalysisError(
                f"Factor {factor_name!r} is missing loadings for symbols: "
                f"{sorted(missing)}"
            )


def _build_design_matrix(
    symbols: list[str],
    factor_names: list[str],
    factor_loadings: dict[str, dict[str, float]],
) -> np.ndarray:
    """Return an (n_symbols, 1 + n_factors) design matrix with intercept."""
    n = len(symbols)
    ones = np.ones((n, 1), dtype=np.float64)
    factor_cols = np.column_stack(
        [
            np.array([factor_loadings[f][s] for s in symbols], dtype=np.float64)
            for f in factor_names
        ]
    )
    return np.hstack([ones, factor_cols])


def _compute_r_squared(y: np.ndarray, residuals: np.ndarray) -> float:
    """Compute the coefficient of determination (R-squared).

    Returns 0.0 when total variance is zero (constant short positions).
    """
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    if ss_tot == 0.0:
        return 0.0
    return 1.0 - ss_res / ss_tot


def _find_high_residual_symbols(
    symbols: list[str],
    residuals: np.ndarray,
) -> list[str]:
    """Return symbols whose residual magnitude exceeds threshold.

    A symbol is flagged when its absolute residual exceeds the median
    absolute residual by more than ``_RESIDUAL_THRESHOLD`` standard
    deviations of the absolute residuals.
    """
    abs_resid = np.abs(residuals)
    median_abs = float(np.median(abs_resid))
    std_abs = float(np.std(abs_resid))

    if std_abs == 0.0:
        return []

    high = []
    for sym, ar in zip(symbols, abs_resid):
        if float(ar) - median_abs > _RESIDUAL_THRESHOLD * std_abs:
            high.append(sym)
    return sorted(high)
