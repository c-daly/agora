# Review: edgar_filings_adapter
## Spec requirement
Fetch 10-K, 10-Q, and 8-K company filings from SEC EDGAR. Adapters must return correctly shaped data matching the relevant schema, handle API errors gracefully, respect rate limits (10 req/sec for SEC), and handle missing/malformed upstream data.

## Implementation
Uses the EDGAR full-text search (EFTS) API at https://efts.sec.gov/LATEST/search-index to search for filings by ticker symbol. Enforces SEC rate limiting via a monotonic-clock throttle (_MIN_REQUEST_INTERVAL = 0.11s between requests). Parses EFTS hit dicts into Filing objects. Supports optional date range filtering and filing-type restriction (10-K, 10-Q, 8-K). Returns results sorted chronologically. Non-200 responses and non-JSON payloads are logged as warnings and return empty list. Invalid hits (missing CIK, unparseable date) are silently skipped.

## Functions
- `fetch_filings(symbol: str, *, filing_type: str | None = None, start_date: date | None = None, end_date: date | None = None) -> list[Filing]`

## Return types
Correct. Returns list[Filing]. Each Filing carries: date, entity, type, url, extracted_fields (dict with accession_number and cik). Matches the Filing schema exactly.

## Verdict
PASS

## Issues
- LOW (edgar_filings_adapter.py): EFTS full-text search on ticker string (q="SYMBOL") is imprecise; filings from unrelated issuers whose documents mention the ticker can appear in results. Resolving the ticker to a CIK first via the EDGAR company search API would be more accurate, but this is a known EFTS limitation rather than a schema defect.
- LOW (edgar_filings_adapter.py): Date range is filtered twice: once via EFTS query params and once in Python. Benign but redundant.
- INFO: Tests present at tests/test_edgar_filings_adapter.py.
