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



def _threshold_correlation(
    ftd_data: list[ShortData],
    threshold_data: list[ShortData],
) -> tuple[bool, int]:
    """Compute threshold list correlation with FTD data.

    Returns a tuple of (on_threshold_list, threshold_overlap_days):
    - on_threshold_list: True if the symbol appeared on a threshold list
      during the FTD analysis period.
    - threshold_overlap_days: number of FTD data days that overlap with
      threshold list presence.
    """
    if not threshold_data:
        return False, 0

    ftd_dates = {f.date for f in ftd_data}
    threshold_dates = {t.date for t in threshold_data if t.value > 0}

    if not threshold_dates:
        return False, 0

    # Check if any threshold dates fall within the FTD analysis period
    if not ftd_dates:
        return False, 0

    ftd_start = min(ftd_dates)
    ftd_end = max(ftd_dates)
    threshold_in_period = {
        d for d in threshold_dates if ftd_start <= d <= ftd_end
    }
    on_threshold = len(threshold_in_period) > 0
    overlap_days = len(ftd_dates & threshold_dates)

    return on_threshold, overlap_days

def analyze_ftd(
    ftd_data: list[ShortData],
    *,
    threshold_data: list[ShortData] | None = None,
) -> dict:
    """Analyse FTD data for a single symbol.

    Args:
        ftd_data: ShortData entries with data_type="ftd".
        threshold_data: Optional ShortData entries with data_type="threshold".
            When provided, threshold list correlation fields are added to the
            result.

    Returns:
        Dict with persistence, spike_days, trend, max_ftd, avg_ftd, and
        optionally on_threshold_list and threshold_overlap_days.
    """
    if not ftd_data:
        result = {
            "symbol": "UNKNOWN",
            "persistence": 0.0,
            "spike_days": [],
            "trend": "flat",
            "max_ftd": 0.0,
            "avg_ftd": 0.0,
        }
        if threshold_data is not None:
            result["on_threshold_list"] = False
            result["threshold_overlap_days"] = 0
        return result

    symbol = ftd_data[0].symbol
    values = [f.value for f in ftd_data]
    total_days = len(values)

    max_ftd = max(values)
    avg_ftd = round(sum(values) / total_days, 6)

    result = {
        "symbol": symbol,
        "persistence": _persistence(ftd_data),
        "spike_days": _spike_days(ftd_data, avg_ftd),
        "trend": _trend(ftd_data),
        "max_ftd": max_ftd,
        "avg_ftd": avg_ftd,
    }

    if threshold_data is not None:
        on_threshold, overlap_days = _threshold_correlation(
            ftd_data, threshold_data,
        )
        result["on_threshold_list"] = on_threshold
        result["threshold_overlap_days"] = overlap_days

    return result
