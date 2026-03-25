# Review: sector_analysis
## Spec requirement: sector performance, rotation, correlation.
## Implementation: Two public functions. compute_sector_performance takes a dict of sector -> list[Quote], groups by symbol, sorts by date, computes avg_return (mean of per-symbol period returns), total_volume, symbol_count, best_symbol/return, worst_symbol/return; sorted by avg_return descending. compute_sector_rotation splits each symbol quotelist into periods, computes prior vs recent sub-period returns, derives momentum_change and rotation_signal (gaining/losing/stable with a 1% threshold); sorted by momentum_change descending.
## Functions:
- compute_sector_performance(quotes_by_sector: dict[str, list[Quote]]) -> list[dict]
- compute_sector_rotation(quotes_by_sector: dict[str, list[Quote]], periods: int = 2) -> list[dict]
## Return types: Both return list[dict] with documented keys. Correct.
## Verdict: FAIL
## Issues:
1. MISSING FEATURE (HIGH): The spec requires correlation as part of sector analysis. Neither public function computes any correlation metric. There is no pairwise sector correlation, intra-sector stock correlation, or cross-sector correlation computation anywhere in the module. This is a material omission against the spec.
