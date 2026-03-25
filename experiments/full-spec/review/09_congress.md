# Review: congress_adapter
## Spec requirement
Fetch congressional trading disclosures. Source is Quiver Quant API or scrape. Returns Transaction objects for congress member stock transactions. Handles unavailability gracefully.

## Implementation
Uses Capitol Trades public JSON API (https://bff.capitoltrades.com/trades) rather than Quiver Quant. No API key required. Paginates via page/pageSize params with sortBy=txDate. Maps disclosed dollar amount ranges to midpoint estimates using a hardcoded lookup table (_AMOUNT_MIDPOINTS). Normalises action strings (buy/purchase -> Buy, sell/sale/sale (full)/sale (partial) -> Sell, others title-cased). Parses politician name from nested politician object. Populates context with party, state, chamber, committee, symbol, asset_name, and disclosed_range. On any HTTP or parse error returns empty list with warning log. Date filter applied both as API query param and in Python. Returns list[Transaction] sorted chronologically.

## Functions
- `fetch_congress_trades(*, symbol: str | None = None, start_date: date | None = None, end_date: date | None = None) -> list[Transaction]`

## Return types
Correct. Returns list[Transaction]. Each Transaction has: date (txDate), entity (politician full name), action (Buy/Sell/other), amount (dollar midpoint estimate as float), context (dict with party, state, chamber, committee, symbol, asset_name, disclosed_range). Matches Transaction schema exactly.

## Verdict
PASS

## Issues
- LOW (congress_adapter.py): Uses Capitol Trades API (bff.capitoltrades.com) rather than the Quiver Quant API mentioned in the spec. Capitol Trades is a reasonable alternative (aggregates the same House/Senate disclosures), but deviates from spec. The adapter docstring acknowledges this choice.
- LOW (congress_adapter.py): _AMOUNT_MIDPOINTS does not cover all possible disclosure ranges. Unrecognised ranges fall back to 0.0 amount, which is silently incorrect. If Capitol Trades adds new range strings, the fallback produces misleading zero amounts with no warning.
- LOW (congress_adapter.py): Date range is filtered twice (API params and Python-side), same pattern as edgar_filings_adapter. Benign but redundant.
- LOW (congress_adapter.py): No rate limiting applied. The Capitol Trades API rate limits are undocumented; bulk fetches could trigger throttling.
- INFO: Tests present at tests/test_congress_adapter.py.
