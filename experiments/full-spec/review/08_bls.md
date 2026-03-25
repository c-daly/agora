# Review: bls_adapter
## Spec requirement
Fetch employment, CPI detail, PPI, and productivity data from BLS REST API (free key, 500 daily requests). Returns TimeSeries objects. Handles errors gracefully, handles missing/malformed upstream data.

## Implementation
Uses BLS API v2 (POST to https://api.bls.gov/publicAPI/v2/timeseries/data/). Reads BLS_API_KEY from environment (optional; requests proceed without key at lower rate limit). Sends payload with seriesid, optional startyear/endyear, and optional registrationkey. Validates HTTP response (400 -> ValueError, 403 -> PermissionError, other non-200 -> RuntimeError). Validates BLS application-level status field (REQUEST_SUCCEEDED). Parses period codes: M01-M12 (monthly), Q01-Q05 (quarterly), A01 (annual); skips M13 annual averages. Returns list[TimeSeries] in chronological order (reverses the newest-first BLS ordering). Provides well-known series ID constants (SERIES_EMPLOYMENT, SERIES_CPI, SERIES_PPI).

## Functions
- `fetch_bls_series(series_id: str, *, start_year: int | None = None, end_year: int | None = None) -> list[TimeSeries]`

## Return types
Correct. Returns list[TimeSeries]. Each TimeSeries has: date (date), value (float), metadata (TimeSeriesMetadata with source=BLS, unit=None, frequency inferred from period code). Matches TimeSeries and TimeSeriesMetadata schemas exactly. Note: unit is not populated (BLS API does not return unit in v2 responses); this is acceptable given the schema marks unit as Optional.

## Verdict
PASS

## Issues
- LOW (bls_adapter.py): The module docstring is a one-liner ("BLS (Bureau of Labor Statistics) adapter for Agora.") with no description of usage, rate limits, or series ID conventions. Compare to the more thorough docstrings in other adapters.
- LOW (bls_adapter.py): Q05 in the quarterly period map resolves to month=1 (same as Q01), which appears to be a copy-paste artifact. BLS uses Q01-Q04 for quarters; Q05 likely never appears in practice but the mapping is incorrect if it does.
- LOW (bls_adapter.py): No retry logic or backoff. The BLS API is rate-limited to 500 requests/day without a key (25/day unauthenticated for v2); a single failed request raises immediately without retry.
- INFO: Tests present at tests/test_bls_adapter.py.
