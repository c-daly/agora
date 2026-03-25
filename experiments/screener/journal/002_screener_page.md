# Journal Entry 002 — Screener Page + Fixes

**Date:** 2026-03-25

## Screener API (task 1)
- Built by registered implementer agent via mcp-call
- 16 tests passing, ruff clean
- Review found 2 major issues: str(exc) leak, silent adapter swallowing
- Fixed, re-reviewed, APPROVED

## Screener Page (task 2)  
- Built by registered implementer agent
- 10 vitest tests passing
- Visual verification: renders real data, sortable table, signal badges

## Bug fixes during verification
- FTD scores were 0 — screener/short_intel had no date range default, now 30-day lookback
- Screener page crashed on render — signal field mismatch (API returns `signal`, component expected `signal_label`)
- 12 broken tests from earlier sessions — FtdHeatmap, MacroGrid, SymbolDeepDive test mocks didn't match refactored components. Fixed all, 42/42 vitest passing.

## Enforcement system tested
- bypassPermissions hook: BLOCKS
- Fake agent ID hook: BLOCKS (verified with daemon)
- Completion claim hook: BLOCKS when workflow not in done phase
- Workflow transitions: eval cannot skip to journal, must go through review
- Daemon needed restart to pick up config changes

## Known issues
- SI score pegged at 100 for all tickers (algorithm treats raw share counts as percentages)
- Screener takes ~30s for 8 tickers (no caching, sequential adapter calls)
- Insider trades endpoint slow (~30s, multiple EDGAR API calls per filing)
