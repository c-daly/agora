"""PCA factor extraction for return series.

Performs principal component analysis via eigendecomposition of the
covariance matrix, identifying latent factors that drive asset returns.
"""

from __future__ import annotations

import numpy as np


def extract_factors(
    returns: dict[str, list[float]],
    n_components: int | None = None,
) -> dict:
    """Extract principal components from asset return series."""
    if not returns:
        raise ValueError("returns must be non-empty")

    assets = list(returns.keys())
    n_assets = len(assets)

    series_lengths = {len(v) for v in returns.values()}
    if len(series_lengths) != 1:
        raise ValueError(
            f"All return series must have the same length, got lengths {sorted(series_lengths)}"
        )

    n_obs = series_lengths.pop()
    if n_obs == 0:
        raise ValueError("Return series must not be empty")

    matrix = np.column_stack([np.array(returns[a], dtype=float) for a in assets])

    ddof = 1 if n_obs > 1 else 0
    cov = np.cov(matrix, rowvar=False, ddof=ddof)
    cov = np.atleast_2d(cov)

    raw_eigenvalues, raw_eigenvectors = np.linalg.eigh(cov)

    idx = np.argsort(raw_eigenvalues)[::-1]
    eigenvalues = raw_eigenvalues[idx]
    eigenvectors = raw_eigenvectors[:, idx]

    max_components = n_assets
    if n_components is None:
        n_components = max_components
    else:
        n_components = min(n_components, max_components)
        if n_components < 1:
            raise ValueError("n_components must be >= 1")

    eigenvalues = eigenvalues[:n_components]
    eigenvectors = eigenvectors[:, :n_components]

    total_var = float(np.sum(raw_eigenvalues[idx]))
    if total_var == 0.0:
        explained_variance_ratio = [0.0] * n_components
    else:
        explained_variance_ratio = (eigenvalues / total_var).tolist()

    loadings = {
        asset: eigenvectors[i, :].tolist() for i, asset in enumerate(assets)
    }

    return {
        "eigenvalues": eigenvalues.tolist(),
        "explained_variance_ratio": explained_variance_ratio,
        "loadings": loadings,
        "n_components": n_components,
    }


def variance_concentration(eigenvalues: list[float]) -> dict:
    """Measure how much variance is concentrated in the top factors."""
    if not eigenvalues:
        raise ValueError("eigenvalues must be non-empty")

    vals = np.array(eigenvalues, dtype=float)
    total = float(np.sum(vals))

    if total == 0.0:
        return {"top_1": 0.0, "top_3": 0.0, "top_5": 0.0}

    return {
        "top_1": float(np.sum(vals[:1]) / total),
        "top_3": float(np.sum(vals[:3]) / total),
        "top_5": float(np.sum(vals[:5]) / total),
    }
