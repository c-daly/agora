"""Short squeeze candidate detection module.

Identifies stocks with elevated short squeeze potential by combining
short interest, price action, days-to-cover, volume trends, and FTD
persistence signals. Operates on already-fetched ShortData and Quote
objects. Does not fetch any data itself.
"""

from __future__ import annotations

from collections import defaultdict

from agora.schemas import Quote, ShortData

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_SI_THRESHOLD_PCT = 15.0  # short interest > 15% of float
_DTC_THRESHOLD = 5.0  # days-to-cover > 5
_FTD_PERSISTENCE_THRESHOLD = 0.5  # FTDs present on >50% of days
_PRICE_TREND_PERIODS = 5  # minimum data points for trend calc
_VOLUME_TREND_PERIODS = 5

# Weights for composite squeeze score
_WEIGHT_SI = 0.25
_WEIGHT_PRICE_TREND = 0.20
_WEIGHT_DTC = 0.20
_WEIGHT_VOLUME_TREND = 0.15
_WEIGHT_FTD = 0.20

# Confidence thresholds
_CONFIDENCE_THRESHOLDS: list[tuple[float, str]] = [
    (80.0, "very_high"),
    (60.0, "high"),
    (40.0, "moderate"),
    (20.0, "low"),
    (0.0, "very_low"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_trend(values: list[float]) -> float:
    """Return a simple linear slope over the values list.

    Uses least-squares fit of value vs index. Returns 0.0 for fewer than
    2 data points.
    """
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    numerator = 0.0
    denominator = 0.0
    for i, y in enumerate(values):
        dx = i - x_mean
        numerator += dx * (y - y_mean)
        denominator += dx * dx
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _classify_confidence(score: float) -> str:
    """Map a 0-100 squeeze score to a confidence label."""
    for threshold, label in _CONFIDENCE_THRESHOLDS:
        if score >= threshold:
            return label
    return "very_low"


def _group_by_symbol(
    short_data: list[ShortData],
) -> dict[str, dict[str, list[ShortData]]]:
    """Group ShortData by symbol, then by data_type."""
    result: dict[str, dict[str, list[ShortData]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for sd in short_data:
        result[sd.symbol][sd.data_type].append(sd)
    # Sort each group by date
    for symbol_groups in result.values():
        for data_type in symbol_groups:
            symbol_groups[data_type].sort(key=lambda sd: sd.date)
    return dict(result)


def _group_quotes_by_symbol(
    quotes: list[Quote],
) -> dict[str, list[Quote]]:
    """Group and sort quotes by symbol."""
    groups: dict[str, list[Quote]] = defaultdict(list)
    for q in quotes:
        groups[q.symbol].append(q)
    for symbol in groups:
        groups[symbol].sort(key=lambda q: q.date)
    return dict(groups)


# ---------------------------------------------------------------------------
# Criterion scorers (each returns 0-100)
# ---------------------------------------------------------------------------


def _score_short_interest(interest_data: list[ShortData]) -> tuple[float, bool]:
    """Score based on short interest as % of float.

    Returns (score, criterion_met). Criterion is met when latest SI > 15%.
    Piecewise linear:
      SI <=  5% -> score 0
      SI  5-15% -> score 0-50
      SI 15-30% -> score 50-90
      SI >= 30% -> score 100 (capped)
    """
    if not interest_data:
        return 0.0, False

    sorted_si = sorted(interest_data, key=lambda s: s.date)
    latest = sorted_si[-1].value

    if latest <= 5.0:
        score = 0.0
    elif latest <= 15.0:
        score = ((latest - 5.0) / 10.0) * 50.0
    elif latest <= 30.0:
        score = 50.0 + ((latest - 15.0) / 15.0) * 40.0
    else:
        score = 100.0

    # Trend bonus: increasing SI adds up to 10 points
    if len(sorted_si) >= 2:
        earliest = sorted_si[0].value
        if earliest > 0 and latest > earliest:
            pct_change = (latest - earliest) / earliest
            score = min(score + min(pct_change * 20.0, 10.0), 100.0)

    met = latest > _SI_THRESHOLD_PCT
    return round(score, 2), met


def _score_price_trend(quotes: list[Quote]) -> tuple[float, bool]:
    """Score based on rising price (positive for squeeze setup).

    Returns (score, criterion_met). Criterion is met when price slope > 0.
    A rising price against high short interest indicates squeeze pressure.
    """
    if len(quotes) < 2:
        return 0.0, False

    closes = [q.close for q in quotes]
    slope = _compute_trend(closes)

    # Normalize slope relative to average price
    avg_price = sum(closes) / len(closes)
    if avg_price <= 0:
        return 0.0, False

    # Relative slope: slope as fraction of average price per period
    rel_slope = slope / avg_price

    # Map relative slope to score:
    #   rel_slope <= 0     -> score 0
    #   rel_slope 0 - 0.02 -> score 0 - 50
    #   rel_slope 0.02 - 0.05 -> score 50 - 100
    #   rel_slope >= 0.05  -> score 100
    if rel_slope <= 0:
        score = 0.0
    elif rel_slope <= 0.02:
        score = (rel_slope / 0.02) * 50.0
    elif rel_slope <= 0.05:
        score = 50.0 + ((rel_slope - 0.02) / 0.03) * 50.0
    else:
        score = 100.0

    met = slope > 0
    return round(score, 2), met


def _score_days_to_cover(
    interest_data: list[ShortData], quotes: list[Quote]
) -> tuple[float, bool]:
    """Score based on days-to-cover ratio.

    DTC = short_interest_shares / avg_daily_volume. Higher DTC means shorts
    need more days to cover, increasing squeeze pressure.

    Returns (score, criterion_met). Criterion is met when DTC > 5.
    Piecewise linear:
      DTC <= 1  -> score 0
      DTC 1-5   -> score 0-50
      DTC 5-10  -> score 50-90
      DTC >= 10 -> score 100
    """
    if not interest_data or not quotes:
        return 0.0, False

    # Use latest SI value as short interest percentage
    sorted_si = sorted(interest_data, key=lambda s: s.date)
    latest_si_pct = sorted_si[-1].value

    # If total_for_ratio is available, use it as total shares for float
    total_for_ratio = sorted_si[-1].total_for_ratio

    # Average daily volume from quotes
    volumes = [q.volume for q in quotes if q.volume > 0]
    if not volumes:
        return 0.0, False
    avg_daily_volume = sum(volumes) / len(volumes)

    if avg_daily_volume <= 0:
        return 0.0, False

    # Estimate short shares from SI percentage and total shares
    if total_for_ratio is not None and total_for_ratio > 0:
        short_shares = (latest_si_pct / 100.0) * total_for_ratio
    else:
        # Fallback: use SI percentage as a proxy for DTC directly
        # This is an approximation when we lack float data
        short_shares = (latest_si_pct / 100.0) * avg_daily_volume * 5

    dtc = short_shares / avg_daily_volume

    if dtc <= 1.0:
        score = 0.0
    elif dtc <= 5.0:
        score = ((dtc - 1.0) / 4.0) * 50.0
    elif dtc <= 10.0:
        score = 50.0 + ((dtc - 5.0) / 5.0) * 40.0
    else:
        score = 100.0

    met = dtc > _DTC_THRESHOLD
    return round(score, 2), met


def _score_volume_trend(quotes: list[Quote]) -> tuple[float, bool]:
    """Score based on rising trading volume.

    Increasing volume alongside rising price and high SI amplifies
    squeeze potential.

    Returns (score, criterion_met). Criterion is met when volume slope > 0.
    """
    if len(quotes) < 2:
        return 0.0, False

    volumes = [float(q.volume) for q in quotes]
    slope = _compute_trend(volumes)

    avg_volume = sum(volumes) / len(volumes)
    if avg_volume <= 0:
        return 0.0, False

    rel_slope = slope / avg_volume

    # Map relative volume slope to score:
    #   rel_slope <= 0      -> score 0
    #   rel_slope 0 - 0.05  -> score 0 - 50
    #   rel_slope 0.05 - 0.15 -> score 50 - 100
    #   rel_slope >= 0.15   -> score 100
    if rel_slope <= 0:
        score = 0.0
    elif rel_slope <= 0.05:
        score = (rel_slope / 0.05) * 50.0
    elif rel_slope <= 0.15:
        score = 50.0 + ((rel_slope - 0.05) / 0.10) * 50.0
    else:
        score = 100.0

    met = slope > 0
    return round(score, 2), met


def _score_ftd_persistence(ftd_data: list[ShortData]) -> tuple[float, bool]:
    """Score based on FTD persistence and magnitude.

    Persistent FTDs indicate difficulty covering shorts, supporting
    squeeze thesis.

    Returns (score, criterion_met). Criterion is met when FTDs are present
    on >50% of observed days.
    """
    if not ftd_data:
        return 0.0, False

    total_days = len(ftd_data)
    days_with_ftds = sum(1 for f in ftd_data if f.value > 0)

    if total_days == 0:
        return 0.0, False

    persistence_ratio = days_with_ftds / total_days

    # Persistence score (0-60)
    persistence_score = persistence_ratio * 60.0

    # Magnitude score (0-40)
    avg_magnitude = sum(f.value for f in ftd_data) / total_days
    if avg_magnitude <= 0:
        magnitude_score = 0.0
    elif avg_magnitude <= 100_000:
        magnitude_score = (avg_magnitude / 100_000) * 20.0
    elif avg_magnitude <= 500_000:
        magnitude_score = 20.0 + ((avg_magnitude - 100_000) / 400_000) * 20.0
    else:
        magnitude_score = 40.0

    score = min(persistence_score + magnitude_score, 100.0)
    met = persistence_ratio > _FTD_PERSISTENCE_THRESHOLD
    return round(score, 2), met


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_squeeze_candidates(
    short_data: list[ShortData], quotes: list[Quote]
) -> list[dict]:
    """Detect short squeeze candidates from short data and price quotes.

    Evaluates each symbol across five criteria:
      1. High short interest (>15% of float)
      2. Rising price trend
      3. High days-to-cover (>5)
      4. Rising volume trend
      5. FTD persistence (>50% of days)

    Each criterion produces a 0-100 sub-score. The weighted composite
    determines overall squeeze potential. Results are ranked by score.

    Args:
        short_data: ShortData entries (any data_type: volume, interest,
            ftd, threshold).
        quotes: Quote entries with OHLCV data.

    Returns:
        List of dicts sorted by score descending, each containing:
          - symbol: str
          - score: float (0-100)
          - criteria_met: list[str] (names of criteria that passed)
          - confidence: str (very_high|high|moderate|low|very_low)
    """
    short_by_symbol = _group_by_symbol(short_data)
    quotes_by_symbol = _group_quotes_by_symbol(quotes)

    # Collect all symbols from both sources
    all_symbols = set(short_by_symbol.keys()) | set(quotes_by_symbol.keys())

    candidates: list[dict] = []

    for symbol in sorted(all_symbols):
        sym_short = short_by_symbol.get(symbol, {})
        sym_quotes = quotes_by_symbol.get(symbol, [])

        interest_data = sym_short.get("interest", [])
        ftd_data = sym_short.get("ftd", [])

        # Compute individual criterion scores
        si_score, si_met = _score_short_interest(interest_data)
        price_score, price_met = _score_price_trend(sym_quotes)
        dtc_score, dtc_met = _score_days_to_cover(interest_data, sym_quotes)
        vol_score, vol_met = _score_volume_trend(sym_quotes)
        ftd_score, ftd_met = _score_ftd_persistence(ftd_data)

        # Weighted composite
        composite = (
            _WEIGHT_SI * si_score
            + _WEIGHT_PRICE_TREND * price_score
            + _WEIGHT_DTC * dtc_score
            + _WEIGHT_VOLUME_TREND * vol_score
            + _WEIGHT_FTD * ftd_score
        )
        composite = round(composite, 2)

        criteria_met: list[str] = []
        if si_met:
            criteria_met.append("high_short_interest")
        if price_met:
            criteria_met.append("rising_price")
        if dtc_met:
            criteria_met.append("high_days_to_cover")
        if vol_met:
            criteria_met.append("rising_volume")
        if ftd_met:
            criteria_met.append("ftd_persistence")

        candidates.append(
            {
                "symbol": symbol,
                "score": composite,
                "criteria_met": criteria_met,
                "confidence": _classify_confidence(composite),
            }
        )

    # Sort by score descending, then symbol ascending for stability
    candidates.sort(key=lambda c: (-c["score"], c["symbol"]))
    return candidates
