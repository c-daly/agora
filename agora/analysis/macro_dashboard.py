"""Macro dashboard analysis module.

Operates on already-fetched TimeSeries data to produce a summary dashboard
of macro indicators: current values, trend directions, and regime-shift
signals. Does not fetch any data itself.
"""

from __future__ import annotations

from statistics import mean

from agora.schemas import TimeSeries

# Minimum absolute percentage change to call a trend "rising" or "falling".
# Below this threshold the trend is "flat".
FLAT_THRESHOLD: float = 0.01

# Fraction of indicators that must shift direction simultaneously to
# trigger a regime signal (>= this proportion).
REGIME_SHIFT_RATIO: float = 0.5


def _latest_value(series: list[TimeSeries]) -> float | None:
    """Return the value from the most recent date, or None if empty."""
    if not series:
        return None
    latest = max(series, key=lambda ts: ts.date)
    return latest.value


def _classify_trend(
    series: list[TimeSeries],
    *,
    threshold: float = FLAT_THRESHOLD,
) -> str:
    """Classify a single indicator series as rising / falling / flat.

    Strategy: split the date-sorted values into two equal halves (prior and
    recent), compare their means.  If the percentage change exceeds
    threshold the trend is directional; otherwise it is flat.

    Returns "rising", "falling", or "flat".
    If the series has fewer than 2 points, returns "flat".
    """
    if len(series) < 2:
        return "flat"

    sorted_series = sorted(series, key=lambda ts: ts.date)
    mid = len(sorted_series) // 2

    prior_mean = mean(ts.value for ts in sorted_series[:mid])
    recent_mean = mean(ts.value for ts in sorted_series[mid:])

    if prior_mean == 0:
        # Avoid division by zero; use absolute difference instead
        diff = recent_mean - prior_mean
        if diff > threshold:
            return "rising"
        if diff < -threshold:
            return "falling"
        return "flat"

    pct_change = (recent_mean - prior_mean) / abs(prior_mean)

    if pct_change > threshold:
        return "rising"
    if pct_change < -threshold:
        return "falling"
    return "flat"


def _detect_regime_signals(
    trends: dict[str, str],
    prior_trends: dict[str, str],
    *,
    ratio: float = REGIME_SHIFT_RATIO,
) -> list[dict]:
    """Flag when multiple indicators shift direction simultaneously.

    Compares trends (current period) against prior_trends (previous
    period).  A direction shift is counted when an indicator changes between
    rising, falling, or flat.

    Returns a (possibly empty) list of signal dicts.
    """
    if not trends or not prior_trends:
        return []

    common = set(trends) & set(prior_trends)
    if not common:
        return []

    shifted: list[str] = []
    for name in sorted(common):
        if trends[name] != prior_trends[name]:
            shifted.append(name)

    if not shifted:
        return []

    shift_fraction = len(shifted) / len(common)
    if shift_fraction >= ratio:
        return [
            {
                "signal": "regime_shift",
                "shifted_indicators": shifted,
                "shift_fraction": round(shift_fraction, 4),
            }
        ]
    return []


def _compute_prior_trends(
    indicators: dict[str, list[TimeSeries]],
    *,
    threshold: float = FLAT_THRESHOLD,
) -> dict[str, str]:
    """Compute trends using only the first half of each series.

    This provides the "prior period" baseline for regime-shift detection.
    """
    prior: dict[str, str] = {}
    for name, series in indicators.items():
        if len(series) < 4:
            # Not enough data to split into two meaningful halves twice
            prior[name] = "flat"
            continue
        sorted_series = sorted(series, key=lambda ts: ts.date)
        first_half = sorted_series[: len(sorted_series) // 2]
        prior[name] = _classify_trend(first_half, threshold=threshold)
    return prior


def build_dashboard(indicators: dict[str, list[TimeSeries]]) -> dict:
    """Build a macro dashboard from pre-fetched indicator data.

    Parameters
    ----------
    indicators:
        Mapping of indicator names to their TimeSeries histories.
        Example: {"GDP": [...], "CPI": [...], "unemployment": [...]}

    Returns
    -------
    dict with keys:
        - current_values: latest value per indicator
        - trends: "rising" / "falling" / "flat" per indicator
        - regime_signals: list of dicts flagging simultaneous shifts
    """
    current_values: dict[str, float | None] = {}
    trends: dict[str, str] = {}

    for name, series in indicators.items():
        current_values[name] = _latest_value(series)
        trends[name] = _classify_trend(series)

    prior_trends = _compute_prior_trends(indicators)
    regime_signals = _detect_regime_signals(trends, prior_trends)

    return {
        "current_values": current_values,
        "trends": trends,
        "regime_signals": regime_signals,
    }
