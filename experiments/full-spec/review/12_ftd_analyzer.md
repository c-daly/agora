# Review: ftd_analyzer
## Spec requirement: FTD trend analysis per security. Persistent FTDs, spikes, threshold list correlation.
## Implementation: For a single symbol, computes: persistence (fraction of days with non-zero FTDs, float 0-1), spike_days (days where value > 2x average, list of {date, value}), trend (rising/falling/flat by comparing first-half vs second-half averages with 5% tolerance), max_ftd, avg_ftd. Operates on list[ShortData] with data_type=ftd. Returns an empty-like result dict with symbol=UNKNOWN when input is empty.
## Functions:
- analyze_ftd(ftd_data: list[ShortData]) -> dict
## Return types: Returns dict with keys: symbol (str), persistence (float), spike_days (list[dict]), trend (str), max_ftd (float), avg_ftd (float). Correct.
## Verdict: FAIL
## Issues:
1. MISSING FEATURE (HIGH): The spec explicitly requires threshold list correlation but the implementation contains no threshold list logic. There is no parameter to accept threshold list membership data and no output field for it. This is a material omission.
2. DESIGN (LOW): analyze_ftd operates on a single symbol at a time rather than a multi-symbol batch, requiring external looping by callers. Not prohibited by spec but worth noting.
