# Review: pca_factors
## Spec requirement
Principal component analysis on returns covariance matrix. Extracts latent market factors, tracks variance concentration over time.

## Implementation
Two public functions:
1. extract_factors - builds the sample covariance matrix (ddof=1), calls np.linalg.eigh, re-sorts eigenvalues descending, returns eigenvalues, explained-variance ratios, per-asset loadings, and the effective component count.
2. variance_concentration - given a list of (already-sorted) eigenvalues, reports cumulative explained variance for top-1, top-3, and top-5 components, enabling time-series tracking of market factor dominance.

## Functions
- extract_factors(returns: dict[str, list[float]], n_components: int | None = None) -> dict
- variance_concentration(eigenvalues: list[float]) -> dict

## Numerical correctness
np.linalg.eigh is the correct algorithm for real symmetric matrices (guaranteed real eigenvalues, faster than eig). Descending sort is applied manually after the call. Explained variance ratio sums over the full pre-slice eigenvalue vector, which is correct. ddof=1 is appropriate for a sample covariance matrix.

## Edge cases
- Empty returns raises ValueError - handled.
- Mismatched-length series raises ValueError - handled.
- Zero-length series raises ValueError - handled.
- n_components=0 raises ValueError (clamped then checked) - handled.
- n_components exceeding number of assets is silently clamped to n_assets - handled.
- Single observation: ddof falls back to 0, covariance still computable - handled.
- All-zero returns (constant): total_var == 0.0 returns [0.0] * n_components - handled.
- variance_concentration with empty list raises ValueError - handled.
- variance_concentration with all-zero eigenvalues returns zeros - handled.

## Verdict
PASS

## Issues
Minor: the docstring for extract_factors is a single-line stub with no Parameters / Returns section, unlike all other functions in the codebase. Not a correctness issue but inconsistent with module style.
