# Journal Entry 001: Initial Implementation

## Date
2026-03-23

## Hypothesis
SEC FTD data can be downloaded as zip archives from a predictable URL pattern
(`cnsfails{YYYY}{MM}{a|b}.zip`), parsed as pipe-delimited text, and mapped
directly to the ShortData schema. The two-file-per-month structure (a = days
1-15, b = days 16-end) means we need to compute which half-month files cover
the requested date range.

## Changes Made
Created `/Users/cdaly/projects/agora/agora/adapters/sec_ftd_adapter.py` with:

1. **`fetch_ftd_data()`** - Public interface matching the contract:
   `(*, symbol: str | None, start_date: date | None, end_date: date | None) -> list[ShortData]`

2. **`_date_range_to_file_keys()`** - Computes which (year, month, half) tuples
   to download based on the date range. Optimizes by skipping the 'a' half when
   start_date is in the second half of its month, and vice versa for 'b'.

3. **`_download_and_parse()`** - Downloads a single FTD zip from SEC using
   requests with a proper User-Agent header. Returns empty list on 404 (file
   not yet published). Raises RuntimeError on other HTTP errors.

4. **`_parse_zip_content()`** - Extracts files from zip, tries utf-8 then
   latin-1 encoding, parses pipe-delimited content.

5. **`_parse_pipe_delimited()`** - Uses csv.reader with `|` delimiter.
   Normalizes headers to uppercase. Skips rows with wrong field count.

6. **`_row_to_short_data()`** - Converts row dict to ShortData. Parses
   YYYYMMDD dates, float quantities, optional price. Returns None on any
   parsing failure.

Key design decisions:
- `data_type="ftd"`, `source="SEC"` as required
- `value` = quantity of fails
- `total_for_ratio` = price (optional; useful for computing dollar value of fails)
- Results sorted chronologically before returning
- All malformed rows silently skipped with debug logging
- Network failures for individual files logged as warnings, not raised

## Eval Results
```
18 passed in 5.56s
[METRIC] test_pass_rate=1.0000
```

All 18 tests passed on the first attempt:
- TestReturnType (2 tests): Returns list of ShortData objects
- TestFieldValues (3 tests): data_type, source, symbol all correct
- TestSymbolFiltering (2 tests): Single symbol and multi-symbol queries work
- TestDateFiltering (3 tests): Date range, start-only, end-only all filter correctly
- TestValueValidity (3 tests): Non-negative, finite values and ratios
- TestChronologicalOrder (1 test): Results sorted by date
- TestErrorHandling (2 tests): Future dates and nonsense symbols return empty lists
- TestEmptyResults (1 test): Weekend date range for rare ticker handled gracefully
- TestMalformedRowHandling (1 test): Real SEC data parsed without crashes

## Code Quality
- `ruff check`: All checks passed
- No secrets or credentials in code
- No response body text leaked in exceptions
- Defensive date parsing with length check and try/except

## Diagnosis
The implementation worked on the first iteration. The SEC FTD URL pattern
`https://www.sec.gov/files/data/fails-deliver-data/cnsfails{YYYY}{MM}{a|b}.zip`
is stable and well-documented. The pipe-delimited format is straightforward to
parse with Python's csv module. The main complexity was in the date-range-to-file
mapping logic, which needed to handle the half-month boundary correctly.
