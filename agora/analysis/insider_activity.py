"""Insider-activity analysis module.

Aggregates statistics and detects unusual trading clusters from corporate
insider transactions.  Operates on already-fetched Transaction objects.
Does not fetch any data itself.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any

from agora.schemas import Transaction


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_insider_activity(
    trades: list[Transaction],
    sector_map: dict[str, str] | None = None,
) -> dict:
    """Aggregate statistics from a list of insider trades.

    Parameters
    ----------
    trades : list[Transaction]
        Insider transactions to analyse.  Each transaction is expected to
        carry a ``symbol`` key in its ``context`` dict identifying the
        company ticker.
    sector_map : dict[str, str] | None
        Optional mapping of ticker symbol to sector name.  When provided,
        the result includes a ``by_sector`` breakdown.

    Returns
    -------
    dict
        Keys:

        - ``total_trades``      -- int
        - ``buy_sell_ratio``    -- float | None (None when no sells)
        - ``top_insiders``      -- list of {entity, trade_count, total_amount}
                                   sorted by trade_count desc (top 10)
        - ``by_company``        -- dict mapping symbol to
                                   {buys, sells, net}
        - ``by_sector``         -- dict mapping sector to
                                   {buys, sells, net}  (only when *sector_map*
                                   is provided, otherwise omitted)
        - ``unusual_clusters``  -- list of {date, trade_count, avg_daily}
                                   for days whose trade count exceeds 3x the
                                   average daily volume
    """
    if not trades:
        return _empty_result(include_sector=sector_map is not None)

    buy_count = 0
    sell_count = 0

    insider_counts: Counter[str] = Counter()
    insider_amounts: defaultdict[str, float] = defaultdict(float)

    company_stats: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"buys": 0, "sells": 0, "net": 0.0},
    )

    trades_by_date: defaultdict[date, int] = defaultdict(int)

    for t in trades:
        action = t.action.lower()

        if action == "buy":
            buy_count += 1
        elif action == "sell":
            sell_count += 1

        # Per-insider stats
        insider_counts[t.entity] += 1
        insider_amounts[t.entity] += t.amount

        # Per-company stats
        symbol = t.context.get("symbol")
        if symbol:
            cs = company_stats[symbol]
            if action == "buy":
                cs["buys"] += 1
                cs["net"] += t.amount
            elif action == "sell":
                cs["sells"] += 1
                cs["net"] -= t.amount

        # Daily volume tracking
        trades_by_date[t.date] += 1

    buy_sell_ratio: float | None = None
    if sell_count > 0:
        buy_sell_ratio = round(buy_count / sell_count, 4)

    top_insiders = [
        {
            "entity": entity,
            "trade_count": count,
            "total_amount": round(insider_amounts[entity], 2),
        }
        for entity, count in insider_counts.most_common(10)
    ]

    by_company: dict[str, dict[str, Any]] = {
        sym: {
            "buys": stats["buys"],
            "sells": stats["sells"],
            "net": round(stats["net"], 2),
        }
        for sym, stats in sorted(company_stats.items())
    }

    unusual_clusters = _detect_unusual_clusters(trades_by_date)

    result: dict[str, Any] = {
        "total_trades": len(trades),
        "buy_sell_ratio": buy_sell_ratio,
        "top_insiders": top_insiders,
        "by_company": by_company,
        "unusual_clusters": unusual_clusters,
    }

    if sector_map is not None:
        result["by_sector"] = _build_sector_breakdown(trades, sector_map)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _empty_result(*, include_sector: bool) -> dict:
    result: dict[str, Any] = {
        "total_trades": 0,
        "buy_sell_ratio": None,
        "top_insiders": [],
        "by_company": {},
        "unusual_clusters": [],
    }
    if include_sector:
        result["by_sector"] = {}
    return result


def _detect_unusual_clusters(
    trades_by_date: defaultdict[date, int],
) -> list[dict]:
    """Return days whose trade count exceeds 3x the average daily volume."""
    if not trades_by_date:
        return []

    total_days = len(trades_by_date)
    total_trades = sum(trades_by_date.values())
    avg_daily = total_trades / total_days

    clusters: list[dict] = []
    for trade_date in sorted(trades_by_date):
        count = trades_by_date[trade_date]
        if count > 3 * avg_daily:
            clusters.append(
                {
                    "date": trade_date.isoformat(),
                    "trade_count": count,
                    "avg_daily": round(avg_daily, 4),
                }
            )
    return clusters


def _build_sector_breakdown(
    trades: list[Transaction],
    sector_map: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Aggregate buy/sell/net by sector using the provided mapping."""
    sector_stats: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"buys": 0, "sells": 0, "net": 0.0},
    )

    for t in trades:
        symbol = t.context.get("symbol")
        if not symbol:
            continue
        sector = sector_map.get(symbol)
        if not sector:
            continue

        action = t.action.lower()
        ss = sector_stats[sector]
        if action == "buy":
            ss["buys"] += 1
            ss["net"] += t.amount
        elif action == "sell":
            ss["sells"] += 1
            ss["net"] -= t.amount

    return {
        sector: {
            "buys": stats["buys"],
            "sells": stats["sells"],
            "net": round(stats["net"], 2),
        }
        for sector, stats in sorted(sector_stats.items())
    }
