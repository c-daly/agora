# Review: macro_dashboard
## Spec requirement: key indicator summary with trend detection.
## Implementation: build_dashboard accepts a dict of indicator names to list[TimeSeries]. For each indicator it computes: current value (value from the latest date entry) and trend classification (rising/falling/flat) by splitting the date-sorted series into two halves and comparing means with a 1% threshold (FLAT_THRESHOLD=0.01). Additionally detects regime_signals: when >=50% of tracked indicators simultaneously change trend direction compared to their prior-period trends (REGIME_SHIFT_RATIO=0.5). Division-by-zero is handled for zero-mean prior series.
## Functions:
- build_dashboard(indicators: dict[str, list[TimeSeries]]) -> dict
## Return types: Returns dict with keys: current_values (dict[str, float|None]), trends (dict[str, str]), regime_signals (list[dict]). Correct.
## Verdict: PASS
## Issues: None material. Regime shift detection is an additive feature not required by the spec but directly relevant to macro analysis. The 1% flat threshold is reasonable for most macro series but could produce spurious directional labels for near-zero rate environments; this is a heuristic limitation, not a bug.
