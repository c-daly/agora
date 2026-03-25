# Review: earnings_context
## Spec requirement: upcoming earnings with historical surprise data.
## Implementation: get_earnings_context takes symbol, a list of earnings dates, and a list of historical surprise dicts (each requiring surprise_pct key). Returns: next_earnings (nearest date >= today as ISO string or None), avg_surprise_pct (mean surprise %), beat_rate (fraction where surprise_pct > 0), streak (signed consecutive beat/miss count walking backwards from most recent), and historical (the raw input list passed through). Pure functions with no I/O or external dependencies.
## Functions:
- get_earnings_context(symbol: str, earnings_dates: list[date], historical_surprises: list[dict]) -> dict
## Return types: Returns dict with keys: symbol (str), next_earnings (str|None), avg_surprise_pct (float), beat_rate (float), streak (int), historical (list[dict]). Correct.
## Verdict: PASS
## Issues: None material. The implementation fully satisfies the spec. beat_rate and streak are additive analytical outputs not explicitly listed in the spec but consistent with the intent of historical surprise data analysis. The historical field exposes raw caller data, which is informative but adds no risk since the module performs no I/O.
