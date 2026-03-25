# Review: threshold_list_adapter
## Spec requirement
Fetch Reg SHO threshold lists from NYSE, NASDAQ, and CBOE. Aggregate across exchanges. A security is on the list when it has sustained high FTDs (>=10k shares, >=0.5% outstanding, 5 consecutive days). Returns ShortData objects with data_type=threshold.

## Implementation
Complete implementation. Fetches from all three exchanges for a given date: NASDAQ via pipe-delimited text file (nasdaqth{YYYYMMDD}.txt), NYSE via JSON API endpoint, CBOE via JSON API endpoint. HTTP 404 responses return empty list (no data for that date). Other non-200 responses raise RuntimeError (caught per-exchange and logged as warning). Aggregates results: for each unique symbol counts how many exchanges list it. value = exchange count (1-3), total_for_ratio = 3 (total exchanges queried), source = RegSHO, data_type = threshold. Supports optional symbol filter and date parameter (defaults to today).

## Functions
- `fetch_threshold_list(*, symbol: str | None = None, date: date | None = None) -> list[ShortData]`

## Return types
Correct. Returns list[ShortData] with data_type=threshold and source=RegSHO. value is exchange count (1.0-3.0), total_for_ratio is 3.0. Matches ShortData schema exactly and uses the spec-enumerated data_type value.

## Verdict
PASS

## Issues
- LOW (threshold_list_adapter.py): The parameter named `date` shadows the built-in `date` type imported from the datetime module. The function uses `from datetime import date as _date_type` inside the function body to work around this. This is functional but fragile; renaming the parameter to `query_date` would be cleaner.
- LOW (threshold_list_adapter.py): The NYSE endpoint uses a JSON API (nyse.com/api/regulatory/threshold-securities/download) whose schema and availability are not documented. If NYSE changes their API format, _fetch_nyse silently returns empty list on schema mismatch.
- LOW (threshold_list_adapter.py): The CBOE URL uses the EDGX market (?mkt=edgx). The spec says "Separate lists from NYSE, NASDAQ, CBOE" but CBOE operates multiple equity markets (EDGX, EDGA, BZX, BYX). Only EDGX is queried.
- INFO: Tests present at tests/test_threshold_list_adapter.py.
