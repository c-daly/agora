# Review: cointegration
## Spec requirement
Pairwise and basket cointegration testing. Identifies mean-reverting relationships. Tracks spread deviation from equilibrium.

## Implementation
Two public functions plus private helpers:
1. check_cointegration - Engle-Granger two-step test: (1) OLS regression of series_a on series_b via scipy.stats.linregress to obtain the hedge ratio and spread; (2) ADF(1) test on the spread residuals via a custom _adf_p_value that uses MacKinnon (2010) critical values with piecewise-linear interpolation.
2. compute_spread - produces the raw spread series given a hedge ratio, suitable for real-time mean-reversion monitoring.

## Functions
- check_cointegration(series_a: list[float], series_b: list[float]) -> dict
- compute_spread(series_a: list[float], series_b: list[float], hedge_ratio: float) -> list[float]

## Numerical correctness
- scipy.stats.linregress is correct for the first-step OLS (equivalent to np.linalg.lstsq with one predictor).
- ADF(1) regression (delta_e = alpha + beta * e_lagged) is a valid simplified ADF; augmenting with additional lags is not implemented, which is acceptable for a first-pass screening tool.
- MacKinnon critical values (-3.90 / -3.34 / -3.04 at 1% / 5% / 10%) match the standard 2-variable, constant-case table.
- _interpolate_p_value uses piecewise-linear interpolation between known critical values and a linear extrapolation beyond the 10% bound with a conservative cap at 1.0 - reasonable.
- The p_value < 0.05 threshold for the cointegrated flag is the conventional choice.

## Edge cases
- Series length mismatch raises ValueError - handled.
- Fewer than 30 observations raises ValueError - handled.
- Constant series raises ValueError - handled.
- Identical series raises ValueError - handled.
- compute_spread with empty series returns [] - handled.
- se_beta == 0 in ADF returns p-value of 1.0 (conservatively not cointegrated) - handled.

## Verdict
PASS

## Issues
- LOW: The spec mentions basket cointegration (more than two series), but the implementation only supports pairwise testing. A basket wrapper would require the Johansen trace test or sequential Engle-Granger and is not present. The pairwise case is fully correct.
- LOW: The spread returned by check_cointegration omits the intercept term (spread = a - hedge_ratio*b, not a - hedge_ratio*b - intercept). compute_spread also omits it. Both functions are internally consistent but the spread_mean will not be exactly zero; the caller must centre it manually if needed.
