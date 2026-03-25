# Review: factor_decomposition
## Spec requirement
Fama-French style regression. Decomposes returns into market, size, value, momentum factors. Residual alpha relative to factor model.

## Implementation
One public function (decompose_returns) plus private helpers. Regresses asset returns onto a user-supplied set of named factor return series using OLS via np.linalg.lstsq. Returns alpha (intercept), per-factor betas, R-squared, and raw residuals. Uses FactorDecompositionError as a domain-specific exception.

## Functions
- decompose_returns(asset_returns: list[float], factor_returns: dict[str, list[float]]) -> dict

Private helpers (not public API):
- _validate_inputs, _build_design_matrix, _compute_r_squared

## Numerical correctness
- np.linalg.lstsq with rcond=None is the correct numerically-stable OLS solver.
- Design matrix has a leading ones column for the intercept, so alpha is directly extracted as coeffs[0].
- R-squared computed as 1 - SS_res / SS_tot; correctly returns 0.0 when the asset return is constant (SS_tot == 0).
- Rank check after lstsq detects linearly-dependent factors and raises a meaningful error.

## Edge cases
- No factors provided raises FactorDecompositionError - handled.
- Fewer than 3 observations raises - handled.
- Observations <= number of parameters (underdetermined) raises - handled.
- Mismatched factor-series length raises - handled.
- Rank-deficient design matrix (duplicate factors) raises - handled.
- Constant asset returns: R-squared returns 0.0 without division by zero - handled.

## Verdict
PASS

## Issues
None. The module deliberately does not hard-code Fama-French factor names; the caller supplies market, size, value, momentum series. This is good separation of concerns consistent with the data-agnostic design of the analysis layer.
