# Journal Entry 001: Initial Implementation

**Date**: 2026-03-23
**Phase**: Initial implementation of yield_curve analysis module

## Hypothesis

A pure-computation analysis module can be built on top of the existing TimeSeries
schema to extract yield curves, compute spreads, and detect inversions without
any data-fetching logic. The maturity label stored in `TimeSeries.metadata.unit`
provides sufficient information for ordering and identification.

## Changes Made

Created `/Users/cdaly/projects/agora/agora/analysis/yield_curve.py` with three functions:

1. **`current_curve(series)`** -- Finds the maximum date across all input
   TimeSeries, filters to that date, and returns a `{maturity_label: yield_value}`
   dictionary.

2. **`compute_spread(series, long_maturity, short_maturity)`** -- Groups input by
   date, computes `long - short` for each date where both maturities are present,
   returns a sorted list of TimeSeries with spread metadata.

3. **`detect_inversions(series)`** -- Derives the current curve, then checks all
   ordered maturity pairs (using a 13-element `MATURITY_ORDER` list) to find cases
   where a shorter-term yield exceeds a longer-term yield. Returns list of dicts
   with `short_maturity`, `long_maturity`, and `spread` fields.

Key design decisions:
- `detect_inversions` checks ALL pairs, not just adjacent maturities
- `compute_spread` only includes dates where both requested maturities have data
- All functions return empty containers for empty input (no exceptions)
- `_MATURITY_RANK` lookup dict is pre-computed at module level for efficiency

## Eval Results

```
17 passed in 0.06s
[METRIC] test_pass_rate=1.0000
```

All 17 tests passed on the first attempt:
- TestCurrentCurve: 5/5
- TestComputeSpread: 4/4
- TestDetectInversions: 5/5
- TestDeterminism: 3/3

## Review

- `ruff check`: All checks passed
- No adapter imports present
- Pure computation, no side effects
- Edge cases (empty, single maturity, single date) all handled
- Deterministic output confirmed by tests

## Diagnosis

No issues found. The implementation matched test expectations on the first iteration.
The main insight was that `detect_inversions` needed to check all pairwise
combinations rather than just adjacent maturities, since the inverted_yields
fixture has non-adjacent inversions (e.g., 2-Year > 10-Year).
