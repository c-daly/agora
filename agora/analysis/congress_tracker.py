"""Congressional trading analysis module.

Aggregates statistics and detects timing anomalies from congressional
stock-trade disclosures.  Operates on already-fetched Transaction objects
produced by the congress_adapter.  Does not fetch any data itself.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from agora.schemas import Transaction


# ---------------------------------------------------------------------------
# Configurable thresholds
# ---------------------------------------------------------------------------

# A cluster is flagged when at least this many trades land in the window.
_CLUSTER_MIN_TRADES = 3

# Window (in calendar days) before a market event to scan for clusters.
_PRE_EVENT_WINDOW_DAYS = 7


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_congress_trades(trades: list[Transaction]) -> dict:
    """Aggregate statistics from a list of congressional trades.

    Returns a dict with the following keys:

    - ``total_trades``    -- int, number of trades analysed
    - ``total_volume``    -- float, sum of estimated dollar amounts
    - ``buy_sell_ratio``  -- float | None, buys / sells (None when no sells)
    - ``top_traders``     -- list of ``{entity, trade_count, total_amount}``
                             dicts, sorted by trade_count desc (top 10)
    - ``most_traded_symbols`` -- list of ``{symbol, trade_count, total_amount}``
                                  dicts, sorted by trade_count desc (top 10)
    - ``party_breakdown`` -- dict mapping party string to
                             ``{trade_count, total_amount, buy_count, sell_count}``
    """
    if not trades:
        return _empty_stats()

    buy_count = 0
    sell_count = 0
    total_volume = 0.0

    trader_counts: Counter[str] = Counter()
    trader_amounts: defaultdict[str, float] = defaultdict(float)

    symbol_counts: Counter[str] = Counter()
    symbol_amounts: defaultdict[str, float] = defaultdict(float)

    party_stats: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"trade_count": 0, "total_amount": 0.0, "buy_count": 0, "sell_count": 0}
    )

    for t in trades:
        total_volume += t.amount

        # Buy / sell tallies
        action = t.action.lower()
        if action == "buy":
            buy_count += 1
        elif action == "sell":
            sell_count += 1

        # Per-trader stats
        trader_counts[t.entity] += 1
        trader_amounts[t.entity] += t.amount

        # Per-symbol stats
        symbol = t.context.get("symbol")
        if symbol:
            symbol_counts[symbol] += 1
            symbol_amounts[symbol] += t.amount

        # Per-party stats
        party = t.context.get("party", "Unknown")
        ps = party_stats[party]
        ps["trade_count"] += 1
        ps["total_amount"] += t.amount
        if action == "buy":
            ps["buy_count"] += 1
        elif action == "sell":
            ps["sell_count"] += 1

    buy_sell_ratio: float | None = None
    if sell_count > 0:
        buy_sell_ratio = round(buy_count / sell_count, 4)

    top_traders = [
        {"entity": entity, "trade_count": count, "total_amount": trader_amounts[entity]}
        for entity, count in trader_counts.most_common(10)
    ]

    most_traded_symbols = [
        {"symbol": sym, "trade_count": count, "total_amount": symbol_amounts[sym]}
        for sym, count in symbol_counts.most_common(10)
    ]

    return {
        "total_trades": len(trades),
        "total_volume": round(total_volume, 2),
        "buy_sell_ratio": buy_sell_ratio,
        "top_traders": top_traders,
        "most_traded_symbols": most_traded_symbols,
        "party_breakdown": dict(party_stats),
    }


def detect_timing_anomalies(
    trades: list[Transaction],
    market_events: list[dict] | None = None,
) -> list[dict]:
    """Identify trades that cluster suspiciously before significant dates.

    Parameters
    ----------
    trades : list[Transaction]
        Congressional trades to examine.
    market_events : list[dict] | None
        Optional list of market events, each having at least ``date``
        (ISO string or ``datetime.date``) and ``description`` keys.
        When *None*, the function falls back to detecting dense clusters
        in the trade data itself (any day with >= ``_CLUSTER_MIN_TRADES``
        trades).

    Returns
    -------
    list[dict]
        Each dict describes one anomaly with keys:
        ``event_date``, ``description``, ``trades_in_window``,
        ``window_start``, ``window_end``, ``traders``.
    """
    if not trades:
        return []

    if market_events is not None:
        return _event_based_anomalies(trades, market_events)
    return _cluster_based_anomalies(trades)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _empty_stats() -> dict:
    return {
        "total_trades": 0,
        "total_volume": 0.0,
        "buy_sell_ratio": None,
        "top_traders": [],
        "most_traded_symbols": [],
        "party_breakdown": {},
    }


def _coerce_date(value: str | date) -> date:
    """Accept an ISO string or a date object and return a date."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _event_based_anomalies(
    trades: list[Transaction],
    market_events: list[dict],
) -> list[dict]:
    """Flag trade clusters that appear in the window before known events."""
    anomalies: list[dict] = []

    for event in market_events:
        event_date = _coerce_date(event["date"])
        window_start = event_date - timedelta(days=_PRE_EVENT_WINDOW_DAYS)
        window_end = event_date - timedelta(days=1)

        window_trades = [
            t for t in trades if window_start <= t.date <= window_end
        ]

        if len(window_trades) >= _CLUSTER_MIN_TRADES:
            traders = sorted({t.entity for t in window_trades})
            anomalies.append({
                "event_date": event_date.isoformat(),
                "description": event.get("description", ""),
                "trades_in_window": len(window_trades),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "traders": traders,
            })

    return anomalies


def _cluster_based_anomalies(trades: list[Transaction]) -> list[dict]:
    """Detect days with unusually high trade counts (no event context)."""
    by_date: defaultdict[date, list[Transaction]] = defaultdict(list)
    for t in trades:
        by_date[t.date].append(t)

    anomalies: list[dict] = []
    for trade_date in sorted(by_date):
        day_trades = by_date[trade_date]
        if len(day_trades) >= _CLUSTER_MIN_TRADES:
            traders = sorted({t.entity for t in day_trades})
            anomalies.append({
                "event_date": trade_date.isoformat(),
                "description": "high-volume trading day (no event context)",
                "trades_in_window": len(day_trades),
                "window_start": trade_date.isoformat(),
                "window_end": trade_date.isoformat(),
                "traders": traders,
            })

    return anomalies
