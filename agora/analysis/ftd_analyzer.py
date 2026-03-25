"""FTD (Failure to Deliver) analysis module.

Computes persistence, spike detection, trend direction, and summary
statistics from FTD data. Operates on already-fetched ShortData objects
with data_type="ftd". Does not fetch any data itself.
"""

from __future__ import annotations

from agora.schemas import ShortData

# Spike threshold: a day counts as a spike when its FTD value
# exceeds this multiple of the overall average.
_SPIKE_MULTIPLIER = 2.0


def _persistence(ftd_data: list[ShortData]) -> float:
    """Fraction of days that have non-zero FTDs.

    Returns a float in [0.0, 1.0].
    """
    total_days = len(ftd_data)
    if total_days == 0:
        return 0.0
    days_with_ftds = sum(1 for f in ftd_data if f.value > 0)
    return round(days_with_ftds / total_days, 6)


def _spike_days(ftd_data: list[ShortData], avg_ftd: float) -> list[dict]:
    """Identify days where FTD value exceeds 2x the average.

    Returns a list of dicts with date and value for each spike day.
    """
    if avg_ftd <= 0:
        return []
    threshold = _SPIKE_MULTIPLIER * avg_ftd
    return [
        {"date": f.date.isoformat(), "value": f.value}
        for f in ftd_data
        if f.value > threshold
    ]


def _trend(ftd_data: list[ShortData]) -> str:
    """Determine whether FTDs are rising or falling over the period.

    Compares the average of the first half to the average of the second
    half. Returns "rising", "falling", or "flat".
    """
    if len(ftd_data) < 2:
        return "flat"

    sorted_data = sorted(ftd_data, key=lambda f: f.date)
    mid = len(sorted_data) // 2
    first_half = sorted_data[:mid]
    second_half = sorted_data[mid:]

    avg_first = sum(f.value for f in first_half) / len(first_half)
    avg_second = sum(f.value for f in second_half) / len(second_half)

    # Use a 5% tolerance band to avoid labeling noise as a trend
    if avg_first == 0 and avg_second == 0:
        return "flat"
    if avg_first == 0:
        return "rising"
    ratio = (avg_second - avg_first) / avg_first
    if ratio > 0.05:
        return "rising"
    if ratio < -0.05:
        return "falling"
    return "flat"


def analyze_ftd(ftd_data: list[ShortData]) -> dict:
    """Analyse FTD data for a single symbol.

    Args:
        ftd_data: ShortData entries with data_type="ftd".

    Returns:
        Dict with persistence, spike_days, trend, max_ftd, and avg_ftd.
    """
    if not ftd_data:
        return {
            "symbol": "UNKNOWN",
            "persistence": 0.0,
            "spike_days": [],
            "trend": "flat",
            "max_ftd": 0.0,
            "avg_ftd": 0.0,
        }

    symbol = ftd_data[0].symbol
    values = [f.value for f in ftd_data]
    total_days = len(values)

    max_ftd = max(values)
    avg_ftd = round(sum(values) / total_days, 6)

    return {
        "symbol": symbol,
        "persistence": _persistence(ftd_data),
        "spike_days": _spike_days(ftd_data, avg_ftd),
        "trend": _trend(ftd_data),
        "max_ftd": max_ftd,
        "avg_ftd": avg_ftd,
    }
