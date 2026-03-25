# Review: correlation_matrix
## Spec requirement
Rolling and static pairwise correlation matrices for any asset set. Detects regime changes via rolling window comparison.

## Implementation
Provides three public functions:
1. compute_correlation_matrix - static Pearson correlation via np.corrcoef; NaN (zero-variance series) replaced with 0.0.
2. compute_rolling_correlation - slides a configurable window over the return series, emits a correlation matrix at each step with a date_index cursor.
3. detect_regime_change - compares consecutive rolling matrices using the normalized Frobenius distance of the upper triangle; flags windows where the distance exceeds a threshold and labels the direction (increase / decrease in mean off-diagonal correlation).

## Functions
- compute_correlation_matrix(returns: dict[str, list[float]]) -> dict
- compute_rolling_correlation(returns: dict[str, list[float]], window: int = 60) -> list[dict]
- detect_regime_change(rolling_corrs: list[dict], threshold: float = 0.3) -> list[dict]

## Numerical correctness
Uses np.corrcoef (standard Pearson). Rolling window slices columns of a pre-built 2-D array, which is efficient. Regime-change distance uses the Frobenius norm divided by the number of unique off-diagonal pairs, a reasonable normalisation. Direction is based on the sign of the mean off-diagonal correlation change, which is correct and interpretable.

## Edge cases
- Empty returns dict returns empty structures - handled.
- Single-symbol case short-circuits to [[1.0]] - handled.
- Series shorter than window returns [] - handled.
- Zero-variance series: NaN replaced by 0.0 - handled (NumPy RuntimeWarning is expected and documented).
- Single-entry rolling list passed to detect_regime_change returns [] - handled.
- Single-symbol rolling matrices produce n_pairs == 0; the continue guard prevents divide-by-zero - handled.

## Verdict
PASS

## Issues
None.
