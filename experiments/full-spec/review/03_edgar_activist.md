# Review: edgar_activist_adapter
## Spec requirement
Fetch 13D/13G activist position disclosures from SEC EDGAR. Returns data shaped to common schema. Handles errors gracefully, respects SEC rate limit (10 req/sec). Handles missing/malformed upstream data.

## Implementation
Complete implementation. Uses EFTS to search for SC 13D, SC 13D/A, SC 13G, SC 13G/A filings. Enforces SEC rate limiting. Downloads the raw filing documents (HTML or plain text) and parses them using regex patterns to extract: aggregate shares beneficially owned (_RE_SHARES), percent of class (_RE_PERCENT), and reporting person name (_RE_NAME_COVER). Determines action from form type: initial filings map to Acquire; amendments heuristically detect Increase vs Decrease from filing text keywords. Returns list[Transaction] sorted chronologically. Errors during individual filing parse are logged and skipped rather than propagating.

## Functions
- `fetch_activist_positions(symbol: str, *, start_date: date | None = None, end_date: date | None = None) -> list[Transaction]`

## Return types
Correct. Returns list[Transaction]. Each Transaction carries: date (filing date), entity (activist name), action (Acquire/Increase/Decrease), amount (shares as float), context (dict with symbol, percent_owned, filing_type, form_url). Matches Transaction schema.

## Verdict
PASS

## Issues
- MEDIUM (edgar_activist_adapter.py): Regex-based text extraction from 13D/13G documents is fragile. EDGAR filings are often HTML with varying structure; the share-count regex may match the wrong number or fail on non-standard formatting, resulting in None returns (filing silently dropped). No fallback for when shares cannot be parsed.
- MEDIUM (edgar_activist_adapter.py): The EFTS search uses a full-text q= query on the ticker symbol, which can match filings where the ticker appears incidentally (e.g., in a portfolio list) rather than as the subject of the 13D/13G. This can produce false-positive results.
- LOW (edgar_activist_adapter.py): _determine_action uses keyword matching on lowercased filing text to detect Decrease. The keyword list is incomplete (e.g., does not include transferred, distributed, forfeited), so some reduction filings may be misclassified as Increase.
- INFO: Tests present at tests/test_edgar_activist_adapter.py.
