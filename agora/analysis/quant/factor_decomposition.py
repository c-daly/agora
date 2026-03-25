"""Factor decomposition module for Fama-French style return analysis.

Decomposes asset returns into factor exposures (betas) and alpha
using ordinary least squares regression via numpy.
"""

from __future__ import annotations

import numpy as np


_MIN_OBSERVATIONS = 3


class FactorDecompositionError(Exception):
    """Raised when factor decomposition cannot be performed."""


def decompose_returns(
    asset_returns: list[float],
    factor_returns: dict[str, list[float]],
) -> dict:
    """Decompose asset returns into factor exposures (betas) and alpha.

    Performs an OLS regression of *asset_returns* on one or more return
    series supplied in *factor_returns*.  The regression includes an
    intercept term that represents alpha.

    Parameters
    ----------
    asset_returns:
        T-length sequence of asset period returns.
    factor_returns:
        Mapping of factor names to T-length sequences of factor period
        returns.  At least one factor must be provided.

    Returns
    -------
    dict with keys:
        alpha      -- regression intercept (float)
        betas      -- dict mapping factor_name to beta (dict[str, float])
        r_squared  -- coefficient of determination (float)
        residuals  -- list of regression residuals (list[float])

    Raises
    ------
    FactorDecompositionError
        If the inputs are invalid or the regression is infeasible.
    """
    # ---- input validation ------------------------------------------------
    _validate_inputs(asset_returns, factor_returns)

    factor_names = list(factor_returns.keys())
    n_obs = len(asset_returns)

    # ---- build design matrix (with intercept column) ---------------------
    y = np.asarray(asset_returns, dtype=np.float64)
    X = _build_design_matrix(factor_returns, factor_names, n_obs)

    # ---- OLS via numpy.linalg.lstsq ---------------------------------------
    try:
        coeffs, _, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    except np.linalg.LinAlgError as exc:
        raise FactorDecompositionError(
            f"OLS regression failed: {exc}"
        ) from exc

    n_params = len(factor_names) + 1  # factors + intercept
    if rank < n_params:
        raise FactorDecompositionError(
            f"Design matrix is rank-deficient (rank {rank}, expected {n_params}). "
            "Check for linearly dependent factors."
        )

    # ---- unpack results --------------------------------------------------
    alpha = float(coeffs[0])
    betas = {name: float(coeffs[i + 1]) for i, name in enumerate(factor_names)}

    residuals_arr = y - X @ coeffs
    residuals = residuals_arr.tolist()
    r_squared = _compute_r_squared(y, residuals_arr)

    return {
        "alpha": alpha,
        "betas": betas,
        "r_squared": r_squared,
        "residuals": residuals,
    }


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------


def _validate_inputs(
    asset_returns: list[float],
    factor_returns: dict[str, list[float]],
) -> None:
    """Raise *FactorDecompositionError* for malformed inputs."""
    if not factor_returns:
        raise FactorDecompositionError("At least one factor must be provided.")

    n_obs = len(asset_returns)

    if n_obs < _MIN_OBSERVATIONS:
        raise FactorDecompositionError(
            f"Insufficient data: {n_obs} observations "
            f"(minimum {_MIN_OBSERVATIONS} required)."
        )

    n_params = len(factor_returns) + 1  # factors + intercept
    if n_obs <= n_params:
        raise FactorDecompositionError(
            f"Insufficient data: {n_obs} observations for {n_params} parameters "
            f"(need at least {n_params + 1})."
        )

    for name, values in factor_returns.items():
        if len(values) != n_obs:
            raise FactorDecompositionError(
                f"Factor {name!r} has {len(values)} observations, "
                f"expected {n_obs}."
            )


def _build_design_matrix(
    factor_returns: dict[str, list[float]],
    factor_names: list[str],
    n_obs: int,
) -> np.ndarray:
    """Return an (n_obs, 1 + n_factors) design matrix with intercept column."""
    ones = np.ones((n_obs, 1), dtype=np.float64)
    factor_cols = np.column_stack(
        [np.asarray(factor_returns[name], dtype=np.float64) for name in factor_names]
    )
    return np.hstack([ones, factor_cols])


def _compute_r_squared(y: np.ndarray, residuals: np.ndarray) -> float:
    """Compute the coefficient of determination (R-squared).

    Returns 0.0 when total variance is zero (constant asset returns).
    """
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    if ss_tot == 0.0:
        return 0.0
    return 1.0 - ss_res / ss_tot
