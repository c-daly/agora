"""Yield curve analysis module.

Operates on already-fetched TimeSeries data to compute yield curves,
spreads, and detect inversions. Does not fetch any data itself.
"""

from __future__ import annotations

from collections import defaultdict

from agora.schemas import TimeSeries, TimeSeriesMetadata

# Maturity ordering from shortest to longest
MATURITY_ORDER: list[str] = [
    "1-Month",
    "2-Month",
    "3-Month",
    "4-Month",
    "6-Month",
    "1-Year",
    "2-Year",
    "3-Year",
    "5-Year",
    "7-Year",
    "10-Year",
    "20-Year",
    "30-Year",
]

_MATURITY_RANK: dict[str, int] = {m: i for i, m in enumerate(MATURITY_ORDER)}


def current_curve(series: list[TimeSeries]) -> dict[str, float]:
    """Return latest yield per maturity as {maturity_label: yield_value}.

    When multiple dates are present, only the latest date's values are used.
    """
    if not series:
        return {}

    # Find the latest date across all entries
    latest_date = max(ts.date for ts in series)

    # Extract yields for the latest date, keyed by maturity label
    curve: dict[str, float] = {}
    for ts in series:
        if ts.date == latest_date:
            maturity = ts.metadata.unit
            curve[maturity] = ts.value

    return curve


def compute_spread(
    series: list[TimeSeries],
    long_maturity: str,
    short_maturity: str,
) -> list[TimeSeries]:
    """Compute spread (long - short) for each date, return as TimeSeries list.

    Only dates where both maturities have data are included.
    Results are sorted by date.
    """
    if not series:
        return []

    # Group values by (date, maturity)
    by_date: dict[object, dict[str, TimeSeries]] = defaultdict(dict)
    for ts in series:
        maturity = ts.metadata.unit
        if maturity in (long_maturity, short_maturity):
            by_date[ts.date][maturity] = ts

    # Compute spread for dates where both maturities exist
    result: list[TimeSeries] = []
    for d in sorted(by_date.keys()):
        bucket = by_date[d]
        if long_maturity in bucket and short_maturity in bucket:
            spread_value = bucket[long_maturity].value - bucket[short_maturity].value
            result.append(
                TimeSeries(
                    date=d,
                    value=spread_value,
                    metadata=TimeSeriesMetadata(
                        source=bucket[long_maturity].metadata.source,
                        unit=f"{long_maturity}/{short_maturity} Spread",
                        frequency=bucket[long_maturity].metadata.frequency,
                    ),
                )
            )

    return result


def detect_inversions(series: list[TimeSeries]) -> list[dict]:
    """Find maturity pairs where shorter-term yield > longer-term yield.

    Uses the latest date's values. Returns a list of dicts, each containing
    at least: short_maturity, long_maturity, spread (short - long, positive
    when inverted).

    Only considers maturities present in the MATURITY_ORDER list.
    Checks all pairs, not just adjacent ones.
    """
    if not series:
        return []

    # Get the current curve (latest date values)
    curve = current_curve(series)

    if len(curve) < 2:
        return []

    # Filter to known maturities and sort by maturity order
    known_maturities = [
        m for m in MATURITY_ORDER if m in curve
    ]

    # Check all pairs where shorter maturity has higher yield than longer
    inversions: list[dict] = []
    for i in range(len(known_maturities)):
        for j in range(i + 1, len(known_maturities)):
            short_mat = known_maturities[i]
            long_mat = known_maturities[j]
            short_yield = curve[short_mat]
            long_yield = curve[long_mat]

            if short_yield > long_yield:
                inversions.append(
                    {
                        "short_maturity": short_mat,
                        "long_maturity": long_mat,
                        "spread": round(short_yield - long_yield, 10),
                    }
                )

    return inversions
