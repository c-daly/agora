# Review: random_matrix_filter
## Spec requirement
Marchenko-Pastur filtering to separate signal from noise in correlation matrices. Eigenvalues exceeding the theoretical noise bound represent real structure.

## Implementation
Two public functions:
1. marchenko_pastur_bounds - computes the MP upper and lower eigenvalue bounds for a given (n_assets, n_observations) pair. Correctly handles q > 1 by clamping lambda_min to 0.
2. filter_correlation_matrix - symmetrises the input matrix, runs np.linalg.eigh, classifies eigenvalues against the MP upper bound, reconstructs a filtered matrix from signal eigenvectors, and re-normalises the diagonal back to 1.0. Falls back to an identity matrix when no signal is found.

## Functions
- marchenko_pastur_bounds(n_assets: int, n_observations: int) -> dict
- filter_correlation_matrix(correlation_matrix: list[list[float]], n_observations: int) -> dict

## Numerical correctness
- The Marchenko-Pastur formula lambda_max = (1 + sqrt(q))^2 is correct for a standardised correlation matrix (variance = 1).
- Using eigh (symmetric eigensolver) avoids spurious complex eigenvalues from floating-point asymmetry; the pre-symmetrisation step is best practice.
- Re-normalisation of the filtered matrix diagonal to 1.0 restores the correlation matrix property after rank-reduction.
- The 1x1 special case (always signal) is correct: any real signal has only one eigenvalue and trivially exceeds noise.
- Identity fallback when all eigenvalues are noise is a sensible conservative baseline.

## Edge cases
- n_assets < 1 or n_observations < 1 raises ValueError - handled.
- Empty (0x0) correlation matrix returns empty lists and n_signal=0 - handled.
- Non-square matrix raises ValueError - handled.
- q > 1 (more assets than observations): lambda_min clamped to 0.0 - handled.
- Zero diagonal after filtered reconstruction: diag_sqrt replaced with 1.0 to prevent division by zero - handled.

## Verdict
PASS

## Issues
None.
