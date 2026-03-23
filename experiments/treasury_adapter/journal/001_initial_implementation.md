# Journal 001: Initial Implementation

**Date**: 2026-03-23
**Status**: SUCCESS
**Metric**: test_pass_rate=1.0000 (21/21 passed)

## Hypothesis

Treasury.gov provides daily yield curve rate data via a public CSV endpoint at
`https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all`.
By fetching this CSV per-year, parsing with the `csv` module, and mapping column names
(e.g. "10 Yr") to maturity labels (e.g. "10yr"), we can build an adapter that returns
`TimeSeries` objects matching the Agora schema with no API key required.

## Changes Made

- Created `/agora/adapters/treasury_adapter.py` with a single public function `fetch_yields()`.
- Maturity label mapping: 13 CSV columns mapped to short labels (1mo, 2mo, 3mo, 4mo, 6mo, 1yr, 2yr, 3yr, 5yr, 7yr, 10yr, 20yr, 30yr).
- Year-range logic: determines which calendar years to fetch based on start_date/end_date.
- Defensive parsing: skips empty, "N/A", and non-numeric values silently.
- Invalid maturities raise `ValueError` with helpful message listing valid labels.
- Impossible date ranges (start > end) return empty list.
- Results sorted chronologically before return.

## Endpoint Discovery

Several Treasury.gov endpoints were investigated:
- `data.treasury.gov/feed.svc/DailyTreasuryYieldCurveRateData` -- old OData feed, now returns HTML redirect. **Dead endpoint.**
- `api.fiscaldata.treasury.gov/.../avg_interest_rates` -- returns monthly average rates by security type, not daily yield curve. **Wrong dataset.**
- `home.treasury.gov/sites/default/files/interest-rates/yield.xml` -- works but only has current month data. **Insufficient for historical queries.**
- `home.treasury.gov/.../daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&...` -- **Working endpoint.** Returns full-year CSV with daily rates for all maturities.

## Eval Results

```
21 passed in 3.05s
[METRIC] test_pass_rate=1.0000
```

All 10 test classes passed:
- TestReturnType (2): returns list of TimeSeries
- TestFieldsPopulated (3): date, value, metadata.source correct
- TestMetadataDetails (2): unit = maturity label, frequency set
- TestMaturityFiltering (3): single, multiple, all maturities
- TestDateFiltering (3): start only, end only, range
- TestValueValidity (2): finite and positive values
- TestChronologicalOrder (1): sorted by date
- TestErrorHandling (2): invalid maturity, impossible date range
- TestEmptyResults (1): weekend returns empty list
- TestMissingDataSkipped (2): no None values, maturity count differences OK

## Review

- `ruff check`: All checks passed
- No secrets in code
- No resp.text leaked in exceptions
- Defensive parsing throughout

## Diagnosis

No issues found. The implementation is clean and all constraints satisfied on the first attempt.
