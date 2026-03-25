# Review: edgar_institutional_adapter
## Spec requirement
Fetch 13F institutional holdings from SEC EDGAR. Returns data shaped to common schema. Handles errors gracefully, respects SEC rate limit (10 req/sec). Handles missing/malformed upstream data.

## Implementation
Module-level docstring correctly describes the intent: fetch 13F-HR filings via EFTS, download XML information tables, parse into Transaction objects. However the implementation is INCOMPLETE: the public function fetch_institutional_holdings() calls two private helpers (_search_13f_filings and _parse_13f_filing) that are never defined anywhere in the file. All five non-schema imports (time, xml.etree.ElementTree, datetime, typing.Any, requests) are unused, consistent with stub/placeholder status. The function body after the helper calls is present but the helpers themselves are missing stubs or full implementations.

## Functions
- `fetch_institutional_holdings(symbol: str, *, start_date: date | None = None, end_date: date | None = None) -> list[Transaction]`

## Return types
Declared return type list[Transaction] is correct per spec. However the implementation cannot be called successfully because the referenced private helpers do not exist, making the return type declaration unreachable.

## Verdict
FAIL

## Issues
- CRITICAL (agora/adapters/edgar_institutional_adapter.py:84): F821 Undefined name `_search_13f_filings` - private helper called but never defined. Calling fetch_institutional_holdings() will raise NameError at runtime.
- CRITICAL (agora/adapters/edgar_institutional_adapter.py:89): F821 Undefined name `_parse_13f_filing` - private helper called but never defined. Same NameError at runtime.
- HIGH (agora/adapters/edgar_institutional_adapter.py:21-26): F401 Five unused imports: time, xml.etree.ElementTree, datetime, typing.Any, requests. Indicates implementation body is missing entirely.
- INFO: Tests present at tests/test_edgar_institutional_adapter.py (tests presumably mock the missing helpers or test only the partial logic).
