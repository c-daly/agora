# Review: short_factor_analysis
## Spec requirement
PCA/factor analysis on short positioning data across securities. Identifies whether short interest is loading on known factors (sector, size) or represents independent signal.

## Implementation
One public function (analyze_short_factors) plus private helpers. Regresses the vector of per-symbol short-interest weights against user-supplied factor loading columns using OLS (np.linalg.lstsq). Returns factor exposures (betas), unexplained fraction (1 - R^2), independent signal strength (= unexplained fraction), and symbols with abnormally large residuals.

## Functions
- analyze_short_factors(short_positions: dict[str, float], factor_loadings: dict[str, dict[str, float]]) -> dict

Private helpers (not public API):
- _validate_inputs, _build_design_matrix, _compute_r_squared, _find_high_residual_symbols

## Numerical correctness
- OLS via np.linalg.lstsq with rcond=None is numerically stable.
- Intercept column is included in the design matrix, consistent with factor_decomposition.py.
- unexplained_fraction is clamped to [0, 1] with max/min to guard against floating-point artifacts near the boundary.
- Residual outlier detection uses (abs(resid) - median(abs(resid))) > threshold * std(abs(resid)), a robust z-score relative to the median. The threshold constant _RESIDUAL_THRESHOLD = 0.5 is conservative and will flag a moderate portion of outliers.
- _compute_r_squared returns 0.0 for constant short positions (SS_tot == 0), preventing division by zero.

## Edge cases
- Empty short_positions raises ShortFactorAnalysisError - handled.
- Fewer than 2 symbols raises - handled.
- No factors provided raises - handled.
- Symbol count <= number of parameters (underdetermined) raises - handled.
- Factor missing loadings for some symbols raises - handled.
- Rank-deficient design matrix (duplicate factors) raises - handled.
- Constant short positions: R-squared returns 0.0 without division by zero - handled.
- std_abs == 0 in _find_high_residual_symbols returns [] - handled.

## Verdict
PASS

## Issues
- LOW: The spec says PCA/factor analysis, but the implementation uses only OLS regression. It does not include a PCA-on-short-positions path (eigendecomposition of the short-interest covariance matrix across time). For the described cross-sectional use case OLS is appropriate and sufficient, but the PCA mode mentioned in the spec is absent.
- LOW: independent_signal_strength is set equal to unexplained_fraction with no additional scaling or normalisation, making it a redundant field. The docstring accurately describes this equivalence, but a caller may expect a distinct measure.
