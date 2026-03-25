# Review: short_squeeze_detector
## Spec requirement: identifies candidates: high short interest + rising price + high days-to-cover + decreasing shares available (via FTD proxy) + rising volume.
## Implementation: Evaluates each symbol across five criteria using weighted sub-scores (0-100 each): (1) short interest >15% of float (_WEIGHT_SI=0.25), (2) rising price trend (_WEIGHT_PRICE_TREND=0.20), (3) high days-to-cover >5 (_WEIGHT_DTC=0.20), (4) rising volume trend (_WEIGHT_VOLUME_TREND=0.15), (5) FTD persistence >50% of days (_WEIGHT_FTD=0.20). Produces a composite score 0-100 and confidence label (very_high/high/moderate/low/very_low). Results sorted by score descending.
## Functions:
- detect_squeeze_candidates(short_data: list[ShortData], quotes: list[Quote]) -> list[dict]
## Return types: Returns list[dict], each with: symbol (str), score (float), criteria_met (list[str]), confidence (str). Correct.
## Verdict: PASS
## Issues: Minor spec interpretation gap: the spec says decreasing shares available (via FTD proxy) but the implementation uses FTD persistence (fraction of days with non-zero FTDs) rather than a directional decreasing-trend. This is a reasonable proxy. Weights sum to exactly 1.00. DTC uses a rough approximation fallback when total_for_ratio is unavailable; this is acceptable but undocumented.
