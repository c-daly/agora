# Review: options_sentiment_adapter
## Spec requirement
Compute put/call ratios and IV skew from Yahoo Finance options chains. This is listed under the Adapters - Short Selling & Sentiment section. Derives bearish-sentiment signals from OptionsSnapshot data. Returns ShortData objects.

## Implementation
Pure computation module (no HTTP calls). Takes list[OptionsSnapshot] as input. Groups snapshots by (symbol, date). For each group computes: (1) put/call volume ratio (put_volume / call_volume, 0.0 if call_volume is zero), (2) put/call open interest ratio (put_oi / call_oi, 0.0 if call_oi is zero), (3) IV skew = mean(put_iv - call_iv) at matched (expiry, strike) pairs (0.0 if no matched pairs). Emits three ShortData records per (symbol, date) group with data_type keys: options_sentiment_pc_volume_ratio, options_sentiment_pc_oi_ratio, options_sentiment_iv_skew. source is set to Derived.

## Functions
- `compute_options_sentiment(options: list[OptionsSnapshot]) -> list[ShortData]`

## Return types
Correct. Returns list[ShortData]. Each ShortData has: symbol, date, data_type (one of the three sentinel keys), value (float), total_for_ratio (total volume/OI or matched-pair count), source (Derived). Matches ShortData schema. The data_type values are not in the spec-enumerated set (volume|interest|ftd|threshold) but the spec comment notes that field as extensible; Derived sentiment metrics are a reasonable extension.

## Verdict
PASS

## Issues
- LOW (options_sentiment_adapter.py): When call_volume or call_oi is zero the ratio is set to 0.0 rather than a sentinel like None or infinity. A zero call volume producing a 0.0 put/call ratio is misleading; it should arguably be None or the record should be omitted. This is a design choice but could mislead downstream analysis.
- LOW (options_sentiment_adapter.py): The data_type strings (options_sentiment_pc_volume_ratio, etc.) are not part of the spec-defined enumeration (volume|interest|ftd|threshold). While the schema field is a plain str so this is technically valid, any downstream component that filters by data_type will need to know these extended keys. They are well-documented as module-level constants.
- INFO: Tests present at tests/test_options_sentiment_adapter.py.
