"""Short composite analysis module.

Computes a composite short-selling pressure score from short volume,
short interest, and FTD data. Operates on already-fetched ShortData
objects. Does not fetch any data itself.
"""

from __future__ import annotations

from agora.schemas import ShortData

# Weights for composite score
_WEIGHT_VOLUME = 0.40
_WEIGHT_INTEREST = 0.30
_WEIGHT_FTD = 0.30

# Signal thresholds
_SIGNAL_THRESHOLDS: list[tuple[float, str]] = [
    (75.0, "extreme"),
    (50.0, "high"),
    (25.0, "moderate"),
    (0.0, "low"),
]


def _classify_signal(score: float) -> str:
    """Map a 0-100 composite score to a signal label."""
    for threshold, label in _SIGNAL_THRESHOLDS:
        if score >= threshold:
            return label
    return "low"


def _compute_short_volume_score(
    short_volume: list[ShortData],
) -> tuple[float, float]:
    """Score based on average short volume ratio.

    Returns (score, avg_ratio). The ratio is short_volume / total_volume
    for each day. A ratio above 50% maps toward high scores.
    """
    ratios: list[float] = []
    for sv in short_volume:
        if sv.total_for_ratio is not None and sv.total_for_ratio > 0:
            ratios.append(sv.value / sv.total_for_ratio)

    if not ratios:
        return 0.0, 0.0

    avg_ratio = sum(ratios) / len(ratios)

    # Score: piecewise linear mapping
    #   ratio <= 0.20 -> score 0
    #   ratio 0.20 - 0.50 -> score 0 - 50 (linear)
    #   ratio 0.50 - 0.70 -> score 50 - 100 (linear)
    #   ratio >= 0.70 -> score 100
    if avg_ratio <= 0.20:
        score = 0.0
    elif avg_ratio <= 0.50:
        score = ((avg_ratio - 0.20) / 0.30) * 50.0
    elif avg_ratio <= 0.70:
        score = 50.0 + ((avg_ratio - 0.50) / 0.20) * 50.0
    else:
        score = 100.0

    return round(score, 2), round(avg_ratio, 6)


def _compute_short_interest_score(
    short_interest: list[ShortData],
) -> tuple[float, float]:
    """Score based on short interest level and change over time.

    Returns (score, latest_si_pct). Uses value directly as the short
    interest percentage. Also rewards increasing trend.
    """
    if not short_interest:
        return 0.0, 0.0

    sorted_si = sorted(short_interest, key=lambda s: s.date)
    latest_value = sorted_si[-1].value

    # Base score from the absolute SI level
    if latest_value <= 5.0:
        base_score = (latest_value / 5.0) * 25.0
    elif latest_value <= 10.0:
        base_score = 25.0 + ((latest_value - 5.0) / 5.0) * 25.0
    elif latest_value <= 20.0:
        base_score = 50.0 + ((latest_value - 10.0) / 10.0) * 25.0
    else:
        base_score = 75.0 + min((latest_value - 20.0) / 10.0, 1.0) * 25.0

    # Trend bonus: if SI is increasing, add up to 10 points
    trend_bonus = 0.0
    if len(sorted_si) >= 2:
        earliest_value = sorted_si[0].value
        if earliest_value > 0 and latest_value > earliest_value:
            pct_change = (latest_value - earliest_value) / earliest_value
            trend_bonus = min(pct_change * 20.0, 10.0)

    score = min(base_score + trend_bonus, 100.0)
    return round(score, 2), round(latest_value, 6)


def _compute_ftd_score(
    ftd_data: list[ShortData],
) -> tuple[float, int]:
    """Score based on FTD persistence and magnitude.

    Returns (score, days_with_ftds). Persistence (number of days with
    non-zero FTDs) and average magnitude both contribute.
    """
    if not ftd_data:
        return 0.0, 0

    days_with_ftds = sum(1 for f in ftd_data if f.value > 0)
    total_days = len(ftd_data)

    if total_days == 0:
        return 0.0, 0

    persistence_ratio = days_with_ftds / total_days
    avg_magnitude = sum(f.value for f in ftd_data) / total_days

    # Persistence score (0-60)
    persistence_score = persistence_ratio * 60.0

    # Magnitude score (0-40)
    if avg_magnitude <= 0:
        magnitude_score = 0.0
    elif avg_magnitude <= 100_000:
        magnitude_score = (avg_magnitude / 100_000) * 20.0
    elif avg_magnitude <= 500_000:
        magnitude_score = 20.0 + ((avg_magnitude - 100_000) / 400_000) * 20.0
    else:
        magnitude_score = 40.0

    score = min(persistence_score + magnitude_score, 100.0)
    return round(score, 2), days_with_ftds


def compute_short_composite(
    short_volume: list[ShortData],
    short_interest: list[ShortData],
    ftd_data: list[ShortData],
) -> dict:
    """Compute a composite short-selling pressure score.

    Combines short volume, short interest, and FTD data into a single
    0-100 score with component breakdowns. Handles missing data sources
    gracefully by re-weighting available components.

    Args:
        short_volume: ShortData entries with data_type="volume".
        short_interest: ShortData entries with data_type="interest".
        ftd_data: ShortData entries with data_type="ftd".

    Returns:
        Dict with composite_score, components, signal, and details.
    """
    # Determine symbol from first available data point
    symbol = "UNKNOWN"
    for source_list in (short_volume, short_interest, ftd_data):
        if source_list:
            symbol = source_list[0].symbol
            break

    # Compute individual component scores
    vol_score, vol_ratio_avg = _compute_short_volume_score(short_volume)
    si_score, si_pct = _compute_short_interest_score(short_interest)
    ftd_score_val, ftd_persistence = _compute_ftd_score(ftd_data)

    # Build weighted composite, handling missing sources
    components = []
    missing: list[str] = []
    if short_volume:
        components.append((_WEIGHT_VOLUME, vol_score))
    else:
        missing.append("short_volume")
    if short_interest:
        components.append((_WEIGHT_INTEREST, si_score))
    else:
        missing.append("short_interest")
    if ftd_data:
        components.append((_WEIGHT_FTD, ftd_score_val))
    else:
        missing.append("ftd_data")

    if components:
        total_weight = sum(w for w, _ in components)
        composite_score = sum(w * s for w, s in components) / total_weight
    else:
        composite_score = 0.0

    composite_score = round(composite_score, 2)

    result: dict = {
        "symbol": symbol,
        "composite_score": composite_score,
        "components": {
            "short_volume_score": vol_score,
            "short_interest_score": si_score,
            "ftd_score": ftd_score_val,
        },
        "signal": _classify_signal(composite_score),
        "details": {
            "short_volume_ratio_avg": vol_ratio_avg,
            "short_interest_pct": si_pct,
            "ftd_persistence": ftd_persistence,
        },
    }

    if missing:
        result["missing_sources"] = missing

    return result
