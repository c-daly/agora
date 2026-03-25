# Review: sector_short_sentiment
## Spec requirement: aggregate short metrics by sector. Which sectors are seeing increasing/decreasing short pressure.
## Implementation: Groups ShortData entries by sector using a caller-supplied sector_map (symbol -> sector name). Symbols absent from the map are silently skipped. For each sector computes: avg_short_volume_ratio (from data_type=volume entries that have total_for_ratio), avg_short_interest (from data_type=interest entries), symbol_count, and trend (increasing/decreasing/stable) by comparing first-half vs second-half average volume ratios with a 5% threshold. Results sorted alphabetically by sector name.
## Functions:
- analyze_sector_sentiment(short_data: list[ShortData], sector_map: dict[str, str]) -> list[dict]
## Return types: Returns list[dict], each with: sector (str), avg_short_volume_ratio (float), avg_short_interest (float), symbol_count (int), trend (str). Correct.
## Verdict: PASS
## Issues: Sectors that have interest data but no volume data will show trend=stable regardless of interest trend, since trend is computed solely from volume ratios. This edge case is silently handled but could yield a misleading stable label. Not a spec violation but worth documenting.
