"""Options sentiment adapter for Agora.

Derives sentiment metrics from OptionsSnapshot data:
- Put/call volume ratio
- Put/call open interest ratio
- IV skew (put IV minus call IV at the same strike)

Pure computation: takes a list of OptionsSnapshot, returns a list of ShortData.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date

from agora.schemas import OptionsSnapshot, ShortData

logger = logging.getLogger(__name__)

# Metric keys emitted in data_type
PC_VOLUME_RATIO = "options_sentiment_pc_volume_ratio"
PC_OI_RATIO = "options_sentiment_pc_oi_ratio"
IV_SKEW = "options_sentiment_iv_skew"


def compute_options_sentiment(
    options: list[OptionsSnapshot],
) -> list[ShortData]:
    """Derive sentiment indicators from options chain snapshots.

    Parameters
    ----------
    options : list[OptionsSnapshot]
        Raw options chain entries (puts and calls).

    Returns
    -------
    list[ShortData]
        Three entries per (symbol, date) group:
        - ``options_sentiment_pc_volume_ratio`` -- put volume / call volume
        - ``options_sentiment_pc_oi_ratio`` -- put OI / call OI
        - ``options_sentiment_iv_skew`` -- mean(put IV - call IV) at matched strikes
    """
    if not options:
        return []

    # Group by (symbol, date)
    groups: dict[tuple[str, date], list[OptionsSnapshot]] = defaultdict(list)
    for snap in options:
        groups[(snap.symbol, snap.date)].append(snap)

    results: list[ShortData] = []

    for (symbol, snap_date), snaps in sorted(groups.items()):
        put_volume = 0
        call_volume = 0
        put_oi = 0
        call_oi = 0

        # For IV skew: collect IV by (expiry, strike) for puts and calls
        put_iv: dict[tuple[date, float], list[float]] = defaultdict(list)
        call_iv: dict[tuple[date, float], list[float]] = defaultdict(list)

        for snap in snaps:
            if snap.type == "put":
                put_volume += snap.volume
                put_oi += snap.open_interest
                if snap.implied_vol is not None:
                    put_iv[(snap.expiry, snap.strike)].append(snap.implied_vol)
            elif snap.type == "call":
                call_volume += snap.volume
                call_oi += snap.open_interest
                if snap.implied_vol is not None:
                    call_iv[(snap.expiry, snap.strike)].append(snap.implied_vol)

        # -- Put/Call volume ratio --
        total_volume = put_volume + call_volume
        if call_volume > 0:
            pc_vol_ratio = put_volume / call_volume
        else:
            pc_vol_ratio = 0.0

        results.append(
            ShortData(
                symbol=symbol,
                date=snap_date,
                data_type=PC_VOLUME_RATIO,
                value=round(pc_vol_ratio, 6),
                total_for_ratio=float(total_volume) if total_volume else None,
                source="Derived",
            )
        )

        # -- Put/Call open interest ratio --
        total_oi = put_oi + call_oi
        if call_oi > 0:
            pc_oi_ratio = put_oi / call_oi
        else:
            pc_oi_ratio = 0.0

        results.append(
            ShortData(
                symbol=symbol,
                date=snap_date,
                data_type=PC_OI_RATIO,
                value=round(pc_oi_ratio, 6),
                total_for_ratio=float(total_oi) if total_oi else None,
                source="Derived",
            )
        )

        # -- IV skew (put IV - call IV at same strike) --
        matched_keys = set(put_iv.keys()) & set(call_iv.keys())
        if matched_keys:
            skew_values: list[float] = []
            for key in sorted(matched_keys):
                mean_put = sum(put_iv[key]) / len(put_iv[key])
                mean_call = sum(call_iv[key]) / len(call_iv[key])
                skew_values.append(mean_put - mean_call)
            iv_skew = sum(skew_values) / len(skew_values)
        else:
            iv_skew = 0.0

        results.append(
            ShortData(
                symbol=symbol,
                date=snap_date,
                data_type=IV_SKEW,
                value=round(iv_skew, 6),
                total_for_ratio=float(len(matched_keys)) if matched_keys else None,
                source="Derived",
            )
        )

    return results
