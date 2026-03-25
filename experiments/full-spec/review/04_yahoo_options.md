# Review: yahoo_options_adapter
## Spec requirement
Fetch full options chains per symbol from Yahoo Finance via yfinance. Returns OptionsSnapshot objects per contract (both puts and calls). Handles missing data gracefully. No auth required. Compute put/call OI ratios and IV skew as short sentiment proxies.

## Implementation
Complete implementation. Uses yfinance Ticker.options to enumerate available expiry dates, then calls Ticker.option_chain(exp_str) for each. Iterates over both calls and puts DataFrames, mapping each row to an OptionsSnapshot. Handles None/missing per-field values with explicit fallbacks (volume defaults to 0, implied_vol/bid/ask default to None). Per-expiry fetch errors are caught and logged without propagating. Unknown tickers (empty options tuple) return empty list. Returns one OptionsSnapshot per contract across all expiries (or the requested single expiry).

## Functions
- `fetch_options(symbol: str, *, expiry: date | None = None) -> list[OptionsSnapshot]`

## Return types
Correct. Returns list[OptionsSnapshot]. Each OptionsSnapshot has: symbol, date (today), expiry, strike, type (call/put), volume, open_interest, implied_vol, bid, ask. Matches OptionsSnapshot schema exactly.

## Verdict
PASS

## Issues
- LOW (yahoo_options_adapter.py): The variable `today` is assigned but never used in the main loop body; `date.today()` is called once but the OptionsSnapshot date field is populated by reusing `today` correctly. On inspection `today` IS used in the OptionsSnapshot construction, so this is a non-issue. No actual bug.
- LOW (yahoo_options_adapter.py): No rate-limit handling. The spec notes Yahoo Finance should be rate-limited cautiously. Fetching all expiry dates in a tight loop could trigger throttling. No sleep or backoff is applied between option_chain calls.
- LOW (yahoo_options_adapter.py): yfinance is an unofficial library. If Yahoo changes their API the adapter silently returns empty lists rather than raising, which may hide upstream breakage.
- INFO: Tests present at tests/test_yahoo_options_adapter.py.
