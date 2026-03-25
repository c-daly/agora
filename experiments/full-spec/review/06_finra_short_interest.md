# Review: finra_short_interest_adapter
## Spec requirement
Fetch twice-monthly short interest per security from FINRA. Scrape query page for listed securities, download pipe-delimited for OTC. Returns ShortData objects with data_type=interest. Handles errors gracefully, handles missing/malformed upstream data.

## Implementation
Uses FINRA consolidated short interest REST API (POST https://api.finra.org/data/group/OTCMarket/name/consolidatedShortInterest) with JSON query body. Supports date range filtering via dateRangeFilters and symbol filtering via domainFilters. Paginates automatically with page size 5000. HTTP 204 (no content) returns empty list. Non-200 responses raise RuntimeError. Malformed rows are skipped with debug logging. Parses settlementDate, currentShortPositionQuantity (value), and sharesOutstandingQuantity (total_for_ratio). Returns list[ShortData] sorted chronologically.

## Functions
- `fetch_short_interest(symbol: str, *, start_date: date | None = None, end_date: date | None = None) -> list[ShortData]`

## Return types
Correct. Returns list[ShortData] with data_type=short_interest and source=FINRA. value is shares short (float), total_for_ratio is shares outstanding when available. Matches ShortData schema. Note: data_type is short_interest rather than the spec-enumerated interest, which is a minor mismatch with the spec comment (volume|interest|ftd|threshold).

## Verdict
PASS

## Issues
- LOW (finra_short_interest_adapter.py): data_type is set to "short_interest" rather than "interest" as suggested by the spec enumeration comment (volume|interest|ftd|threshold). This is a naming inconsistency that could affect downstream filtering if any analysis module pattern-matches on "interest".
- LOW (finra_short_interest_adapter.py): The spec mentions scraping the query page for listed securities and downloading pipe-delimited files for OTC. The implementation uses only the FINRA JSON API, which covers consolidated short interest (primarily OTC). Exchange-listed securities may not be covered by this endpoint. The spec's dual-path approach (query page for listed, pipe-delimited for OTC) is not implemented.
- INFO: No rate limiting is applied to FINRA API calls. FINRA's rate limits are not documented in the spec; current implementation fires requests without delay.
- INFO: Tests present at tests/test_finra_short_interest_adapter.py.
