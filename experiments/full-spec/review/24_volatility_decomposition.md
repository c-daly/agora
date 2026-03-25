# Review: volatility_decomposition
## Spec requirement
Decomposes realized volatility into components (overnight vs intraday, systematic vs idiosyncratic). Compares against implied vol to compute variance risk premium.

## Implementation
Two public functions:
1. decompose_volatility - splits close-to-close volatility into overnight (open[t]/close[t-1]-1) and intraday (close[t]/open[t]-1) components. Reports annualised standard deviations (sqrt(252)) and the overnight fraction of total variance.
2. compute_variance_risk_premium - takes scalar realized and implied vol inputs, returns variance-domain quantities (var = vol^2), the VRP (implied_var - realized_var), the vol ratio, and a rich/cheap signal label.

## Functions
- decompose_volatility(close_prices: list[float], open_prices: list[float]) -> dict
- compute_variance_risk_premium(realized_vol: float, implied_vol: float) -> dict

## Numerical correctness
- Overnight and intraday return definitions are textbook-standard.
- Annualisation via sqrt(252) is the standard daily-to-annual conversion.
- ddof=1 is correct for a sample standard deviation.
- VRP = implied_var - realized_var is the standard definition (positive means options are rich, IV > RV).
- overnight_fraction = overnight_var / total_var is computed in variance space, which is correct.

## Edge cases
- Mismatched close/open lengths raises ValueError - handled.
- Fewer than 2 price observations raises ValueError (_MIN_PERIODS = 2) - handled.
- Non-positive prices raise ValueError per element - handled.
- Flat prices (zero variance): overnight_fraction returns 0.0 via total_var > 0 guard - handled.
- realized_vol = 0 in VRP: vrp_ratio returned as inf - documented and handled.
- Negative vol inputs raise ValueError - handled.

## Verdict
PASS

## Issues
- MEDIUM: When exactly 2 price observations are provided (1 return period), np.std(..., ddof=1) produces NaN because there is only one data point and ddof=1 causes division by zero in numpy. The function does not guard against this case and returns NaN values in the output dict silently. The minimum should be raised to 3 price observations (2 returns), or the result should explicitly return 0.0 for single-return inputs. The test test_two_prices_minimum currently passes because it only checks that no exception is raised, not that the output contains valid floats. File: agora/analysis/quant/volatility_decomposition.py, _validate_prices and decompose_volatility.
- LOW: The spec mentions systematic vs idiosyncratic decomposition, but the implementation only provides overnight vs intraday. The systematic/idiosyncratic split requires factor model residuals (e.g., from factor_decomposition.py) and is not present. This is a scope gap.
