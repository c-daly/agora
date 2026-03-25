"""Random Matrix Theory filtering for correlation matrices.

Applies the Marchenko-Pastur distribution to separate signal eigenvalues
from noise in empirical correlation matrices. Eigenvalues exceeding the
theoretical upper bound represent real structure; those within the bounds
are consistent with random noise.
"""

from __future__ import annotations

import numpy as np


def marchenko_pastur_bounds(n_assets: int, n_observations: int) -> dict:
    """Compute theoretical Marchenko-Pastur noise bounds.

    The Marchenko-Pastur law describes the distribution of eigenvalues
    for large random matrices. For a correlation matrix built from
    *n_observations* observations of *n_assets* variables, the noise
    eigenvalues are bounded by lambda_min and lambda_max.

    Parameters
    ----------
    n_assets:
        Number of assets (matrix dimension).
    n_observations:
        Number of time-series observations.

    Returns
    -------
    dict with keys:
        - ``lambda_min``: lower bound of noise eigenvalue range
        - ``lambda_max``: upper bound of noise eigenvalue range
        - ``q_ratio``: ratio n_assets / n_observations

    Raises
    ------
    ValueError
        If *n_assets* or *n_observations* is less than 1.
    """
    if n_assets < 1 or n_observations < 1:
        raise ValueError(
            f"n_assets ({n_assets}) and n_observations ({n_observations}) must be >= 1"
        )

    q = n_assets / n_observations

    # When q > 1 the standard formula still holds but lambda_min becomes 0
    # because (1 - sqrt(q))^2 can go negative in the intermediate calc
    # for q > 1. The correct lower bound is max(0, (1 - sqrt(q))^2).
    lambda_max = (1.0 + np.sqrt(q)) ** 2
    lambda_min = max(0.0, (1.0 - np.sqrt(q)) ** 2)

    return {
        "lambda_min": float(lambda_min),
        "lambda_max": float(lambda_max),
        "q_ratio": float(q),
    }


def filter_correlation_matrix(
    correlation_matrix: list[list[float]],
    n_observations: int,
) -> dict:
    """Separate signal eigenvalues from noise using the Marchenko-Pastur law.

    Eigenvalues exceeding the theoretical upper bound are classified as
    *signal*; the remainder are classified as *noise*. A filtered
    correlation matrix is reconstructed using only the signal eigenvalues.

    For a 1x1 matrix the single eigenvalue is always classified as signal.

    Parameters
    ----------
    correlation_matrix:
        Square correlation matrix as a list of lists.
    n_observations:
        Number of observations used to estimate the correlation matrix.

    Returns
    -------
    dict with keys:
        - ``signal_eigenvalues``: eigenvalues above the MP upper bound
        - ``noise_eigenvalues``: eigenvalues within the MP noise band
        - ``filtered_matrix``: reconstructed matrix from signal components
        - ``n_signal``: count of signal eigenvalues

    Raises
    ------
    ValueError
        If the matrix is not square, or *n_observations* < 1.
    """
    mat = np.array(correlation_matrix, dtype=float)

    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError(
            f"correlation_matrix must be square, got shape {mat.shape}"
        )

    n_assets = mat.shape[0]

    if n_assets == 0:
        return {
            "signal_eigenvalues": [],
            "noise_eigenvalues": [],
            "filtered_matrix": [],
            "n_signal": 0,
        }

    if n_observations < 1:
        raise ValueError(f"n_observations ({n_observations}) must be >= 1")

    # Force symmetry to avoid complex eigenvalues from floating-point noise
    mat = (mat + mat.T) / 2.0

    eigenvalues, eigenvectors = np.linalg.eigh(mat)

    # eigh returns eigenvalues in ascending order; work with descending
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    bounds = marchenko_pastur_bounds(n_assets, n_observations)
    lambda_max = bounds["lambda_max"]

    # For a 1x1 matrix the single eigenvalue is always signal
    if n_assets == 1:
        signal_mask = np.array([True])
    else:
        signal_mask = eigenvalues > lambda_max

    signal_eigenvalues = eigenvalues[signal_mask]
    noise_eigenvalues = eigenvalues[~signal_mask]

    # Reconstruct filtered matrix from signal eigenvectors/eigenvalues
    if signal_mask.any():
        signal_vecs = eigenvectors[:, signal_mask]
        filtered = signal_vecs @ np.diag(signal_eigenvalues) @ signal_vecs.T

        # Re-normalize diagonal to 1.0 so it remains a correlation matrix
        diag_sqrt = np.sqrt(np.diag(filtered))
        # Guard against zero diagonal entries
        diag_sqrt = np.where(diag_sqrt > 0, diag_sqrt, 1.0)
        outer = np.outer(diag_sqrt, diag_sqrt)
        filtered = filtered / outer
    else:
        # No signal found -- return identity as the "no structure" baseline
        filtered = np.eye(n_assets)

    return {
        "signal_eigenvalues": signal_eigenvalues.tolist(),
        "noise_eigenvalues": noise_eigenvalues.tolist(),
        "filtered_matrix": filtered.tolist(),
        "n_signal": int(signal_mask.sum()),
    }
