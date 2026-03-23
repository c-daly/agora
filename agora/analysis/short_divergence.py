"""Short divergence analysis module.

Detects divergences between short-selling signals (short volume, short interest,
FTDs) and insider trading activity. Operates on already-fetched ShortData and
Transaction data. Does not fetch any data itself.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from agora.schemas import ShortData, Transaction


def _group_short_data_by_type(
    short_data: list[ShortData],
) -> dict[str, list[ShortData]]:
    """Partition short data records by their data_type field."""
    groups: dict[str, list[ShortData]] = defaultdict(list)
    for sd in short_data:
        groups[sd.data_type].append(sd)
    # Sort each group by date for chronological analysis
    for key in groups:
        groups[key].sort(key=lambda sd: sd.date)
    return groups


def _compute_trend(values: list[float]) -> float:
    """Return a simple linear slope over the values list.

    Uses least-squares fit of value vs index. Returns 0.0 for fewer than
    2 data points.
    """
    n = len(values)
    if n < 2:
        return 0.0
    # Simple OLS slope: sum((x - x_mean)(y - y_mean)) / sum((x - x_mean)^2)
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


def _date_range(dates: list[date]) -> dict[str, date]:
    """Return {"start": min_date, "end": max_date} from a list of dates."""
    return {"start": min(dates), "end": max(dates)}


def _net_insider_direction(trades: list[Transaction]) -> tuple[float, int, int]:
    """Compute net insider direction from transactions.

    Returns (net_amount, buy_count, sell_count).
    Buys are actions containing "buy" or "purchase" (case-insensitive).
    Sells are actions containing "sell" or "sale" or "disposition" (case-insensitive).
    """
    net = 0.0
    buys = 0
    sells = 0
    for t in trades:
        action_lower = t.action.lower()
        if any(kw in action_lower for kw in ("buy", "purchase")):
            net += t.amount
            buys += 1
        elif any(kw in action_lower for kw in ("sell", "sale", "disposition")):
            net -= t.amount
            sells += 1
    return net, buys, sells


def _severity_from_slope(slope: float) -> str:
    """Map an absolute slope magnitude to a severity level."""
    abs_slope = abs(slope)
    if abs_slope >= 1000:
        return "high"
    if abs_slope >= 100:
        return "medium"
    return "low"


def _detect_shorts_rising_insiders_buying(
    short_groups: dict[str, list[ShortData]],
    insider_trades: list[Transaction],
) -> list[dict]:
    """Detect when short volume or interest is rising while insiders are net buying."""
    if not insider_trades:
        return []

    net_amount, buy_count, sell_count = _net_insider_direction(insider_trades)
    if net_amount <= 0:
        return []

    results: list[dict] = []

    for data_type in ("short_volume", "short_interest"):
        records = short_groups.get(data_type, [])
        if len(records) < 2:
            continue

        values = [r.value for r in records]
        slope = _compute_trend(values)

        if slope > 0:
            all_dates = [r.date for r in records] + [t.date for t in insider_trades]
            results.append({
                "divergence_type": "shorts_rising_insiders_buying",
                "description": (
                    f"{data_type} trending up (slope={slope:.2f}) while insiders are "
                    f"net buyers ({buy_count} buys, {sell_count} sells, "
                    f"net={net_amount:.0f} shares)"
                ),
                "severity": _severity_from_slope(slope),
                "date_range": _date_range(all_dates),
                "details": {
                    "short_data_type": data_type,
                    "short_slope": round(slope, 4),
                    "insider_net_amount": round(net_amount, 2),
                    "insider_buy_count": buy_count,
                    "insider_sell_count": sell_count,
                },
            })

    return results


def _detect_shorts_rising_ftd_declining(
    short_groups: dict[str, list[ShortData]],
) -> list[dict]:
    """Detect when shorts are up but FTDs are going down (potential covering)."""
    ftd_records = short_groups.get("ftd", [])
    if len(ftd_records) < 2:
        return []

    ftd_slope = _compute_trend([r.value for r in ftd_records])
    if ftd_slope >= 0:
        return []

    results: list[dict] = []

    for data_type in ("short_volume", "short_interest"):
        records = short_groups.get(data_type, [])
        if len(records) < 2:
            continue

        short_slope = _compute_trend([r.value for r in records])
        if short_slope <= 0:
            continue

        all_dates = [r.date for r in records] + [r.date for r in ftd_records]
        severity = _severity_from_slope(short_slope)

        results.append({
            "divergence_type": "shorts_rising_ftd_declining",
            "description": (
                f"{data_type} trending up (slope={short_slope:.2f}) while FTDs "
                f"are declining (slope={ftd_slope:.2f}), suggesting potential covering"
            ),
            "severity": severity,
            "date_range": _date_range(all_dates),
            "details": {
                "short_data_type": data_type,
                "short_slope": round(short_slope, 4),
                "ftd_slope": round(ftd_slope, 4),
            },
        })

    return results


def _detect_short_interest_dropping_volume_high(
    short_groups: dict[str, list[ShortData]],
) -> list[dict]:
    """Detect when reported short interest declines but daily short volume stays elevated."""
    si_records = short_groups.get("short_interest", [])
    sv_records = short_groups.get("short_volume", [])

    if len(si_records) < 2 or len(sv_records) < 2:
        return []

    si_slope = _compute_trend([r.value for r in si_records])
    sv_slope = _compute_trend([r.value for r in sv_records])

    # Short interest must be declining
    if si_slope >= 0:
        return []

    # Short volume must be flat or rising (not declining at same rate)
    # We consider it divergent if sv_slope >= 0 (flat or rising)
    if sv_slope < 0:
        return []

    all_dates = [r.date for r in si_records] + [r.date for r in sv_records]
    severity = _severity_from_slope(si_slope)

    return [{
        "divergence_type": "short_interest_dropping_volume_high",
        "description": (
            f"Short interest declining (slope={si_slope:.2f}) while short volume "
            f"remains elevated (slope={sv_slope:.2f}), possible hidden shorts"
        ),
        "severity": severity,
        "date_range": _date_range(all_dates),
        "details": {
            "short_interest_slope": round(si_slope, 4),
            "short_volume_slope": round(sv_slope, 4),
        },
    }]


def detect_divergences(
    short_data: list[ShortData],
    insider_trades: list[Transaction],
) -> list[dict]:
    """Detect divergences between short-selling signals and insider trades.

    Accepts ShortData with mixed data_types (short_volume, short_interest, ftd).
    Separates by data_type to analyze each signal independently.

    Returns a list of divergence dicts, each containing:
        - divergence_type: str identifying the divergence
        - description: human-readable explanation
        - severity: "low", "medium", or "high"
        - date_range: {"start": date, "end": date}
        - details: dict with supporting numerical data

    Returns an empty list when data is insufficient for any detection.
    """
    if not short_data:
        return []

    short_groups = _group_short_data_by_type(short_data)

    divergences: list[dict] = []
    divergences.extend(
        _detect_shorts_rising_insiders_buying(short_groups, insider_trades)
    )
    divergences.extend(
        _detect_shorts_rising_ftd_declining(short_groups)
    )
    divergences.extend(
        _detect_short_interest_dropping_volume_high(short_groups)
    )

    return divergences
