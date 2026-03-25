# Review: insider_activity
## Spec requirement: aggregate insider buy/sell ratios by sector/company
## Implementation: Aggregates statistics from a list of Transaction objects. Computes total_trades, buy_sell_ratio, top_insiders (by trade count, top 10), by_company (buys/sells/net per symbol), optional by_sector (buys/sells/net per sector when sector_map is provided), and unusual_clusters (days exceeding 3x average daily trade count). All data is pre-fetched; no I/O is performed.
## Functions:
- `analyze_insider_activity(trades: list[Transaction], sector_map: dict[str, str] | None = None) -> dict`
## Return types: Returns dict with keys: total_trades (int), buy_sell_ratio (float|None), top_insiders (list[dict]), by_company (dict[str, dict]), by_sector (dict[str, dict], conditional), unusual_clusters (list[dict]). Types are correct and well-documented.
## Verdict: PASS
## Issues: None. Implementation cleanly covers buy/sell ratios at both company and sector level. Cluster detection (3x average) is a reasonable heuristic not spelled out in the spec but is additive. by_sector is only included when sector_map is provided, which is appropriate. buy_sell_ratio is None when there are no sells (avoids ZeroDivisionError).
