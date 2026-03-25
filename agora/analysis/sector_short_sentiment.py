"""Sector-level short sentiment analysis module.

Aggregates short-selling metrics by sector. Operates on already-fetched
ShortData objects and a symbol-to-sector mapping. Does not fetch any data
itself.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean

from agora.schemas import ShortData


def _short_volume_ratio(entry: ShortData) -> float | None:
    """Return the short volume ratio for a single entry, or None if unavailable."""
    if entry.total_for_ratio is not None and entry.total_for_ratio > 0:
        return entry.value / entry.total_for_ratio
    return None


def _determine_trend(
    ratios_by_date: list[tuple],
) -> str:
    """Classify the trend in short volume ratios over time.

    Compares the average of the first half to the average of the second half.
    Returns "increasing", "decreasing", or "stable".
    """
    if len(ratios_by_date) < 2:
        return "stable"

    sorted_ratios = sorted(ratios_by_date, key=lambda x: x[0])
    values = [v for _, v in sorted_ratios]

    mid = len(values) // 2
    first_half_avg = mean(values[:mid]) if values[:mid] else 0.0
    second_half_avg = mean(values[mid:]) if values[mid:] else 0.0

    if first_half_avg == 0.0:
        if second_half_avg > 0.0:
            return "increasing"
        return "stable"

    pct_change = (second_half_avg - first_half_avg) / first_half_avg
    if pct_change > 0.05:
        return "increasing"
    if pct_change < -0.05:
        return "decreasing"
    return "stable"


def analyze_sector_sentiment(
    short_data: list[ShortData],
    sector_map: dict[str, str],
) -> list[dict]:
    """Compute aggregate short metrics grouped by sector.

    Groups *short_data* entries according to *sector_map* (symbol -> sector
    name). Symbols not present in *sector_map* are silently skipped.

    Args:
        short_data: ShortData entries of any data_type (volume, interest, etc.).
        sector_map: Mapping from symbol to sector name.

    Returns:
        A list of dicts, one per sector, sorted by sector name. Each dict
        contains:
            - sector: str
            - avg_short_volume_ratio: float
            - avg_short_interest: float
            - symbol_count: int
            - trend: str  ("increasing" | "decreasing" | "stable")
    """
    volume_ratios: dict[str, list[tuple]] = defaultdict(list)
    interest_values: dict[str, list[float]] = defaultdict(list)
    symbols_per_sector: dict[str, set[str]] = defaultdict(set)

    for entry in short_data:
        sector = sector_map.get(entry.symbol)
        if sector is None:
            continue

        symbols_per_sector[sector].add(entry.symbol)

        if entry.data_type == "volume":
            ratio = _short_volume_ratio(entry)
            if ratio is not None:
                volume_ratios[sector].append((entry.date, ratio))

        elif entry.data_type == "interest":
            interest_values[sector].append(entry.value)

    all_sectors = sorted(symbols_per_sector.keys())

    results: list[dict] = []
    for sector in all_sectors:
        ratios = volume_ratios.get(sector, [])
        interests = interest_values.get(sector, [])

        avg_ratio = round(mean(v for _, v in ratios), 6) if ratios else 0.0
        avg_interest = round(mean(interests), 6) if interests else 0.0
        trend = _determine_trend(ratios)

        results.append(
            {
                "sector": sector,
                "avg_short_volume_ratio": avg_ratio,
                "avg_short_interest": avg_interest,
                "symbol_count": len(symbols_per_sector[sector]),
                "trend": trend,
            }
        )

    return results
