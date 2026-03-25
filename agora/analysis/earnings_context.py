"""Earnings context analysis module.

Computes earnings context from upcoming dates and historical surprise data.
Operates on pre-fetched earnings dates and surprise records. Does not fetch
any data itself.
"""

from __future__ import annotations

from datetime import date


def _next_earnings(earnings_dates: list[date], reference: date | None = None) -> str | None:
    """Return the nearest future earnings date as an ISO string.

    If *reference* is ``None``, today is used. Returns ``None`` when no
    future date is found.
    """
    ref = reference if reference is not None else date.today()
    future = sorted(d for d in earnings_dates if d >= ref)
    if not future:
        return None
    return future[0].isoformat()


def _avg_surprise_pct(historical_surprises: list[dict]) -> float:
    """Mean surprise percentage across all historical records.

    Each dict is expected to contain a ``surprise_pct`` key.
    Returns 0.0 when the list is empty.
    """
    if not historical_surprises:
        return 0.0
    total = sum(h["surprise_pct"] for h in historical_surprises)
    return round(total / len(historical_surprises), 6)


def _beat_rate(historical_surprises: list[dict]) -> float:
    """Fraction of quarters where the company beat estimates.

    A beat is defined as ``surprise_pct > 0``. Returns 0.0 when
    the list is empty.
    """
    if not historical_surprises:
        return 0.0
    beats = sum(1 for h in historical_surprises if h["surprise_pct"] > 0)
    return round(beats / len(historical_surprises), 6)


def _streak(historical_surprises: list[dict]) -> int:
    """Length of the current consecutive beat or miss streak.

    Positive value = consecutive beats, negative = consecutive misses.
    Entries are expected in chronological order (oldest first).
    Returns 0 when the list is empty or the most recent surprise is zero.
    """
    if not historical_surprises:
        return 0

    # Walk backwards from the most recent quarter
    count = 0
    direction: int | None = None
    for h in reversed(historical_surprises):
        pct = h["surprise_pct"]
        if pct == 0:
            break
        current_dir = 1 if pct > 0 else -1
        if direction is None:
            direction = current_dir
        if current_dir != direction:
            break
        count += 1

    if direction is None:
        return 0
    return direction * count


def get_earnings_context(
    symbol: str,
    earnings_dates: list[date],
    historical_surprises: list[dict],
) -> dict:
    """Build an earnings-context summary for a symbol.

    Args:
        symbol: Ticker symbol (e.g. ``"AAPL"``).
        earnings_dates: Known/upcoming earnings dates.
        historical_surprises: List of dicts, each with at least a
            ``surprise_pct`` key (float). Expected in chronological
            order (oldest first).

    Returns:
        Dict with keys: symbol, next_earnings, avg_surprise_pct,
        beat_rate, streak, historical.
    """
    return {
        "symbol": symbol,
        "next_earnings": _next_earnings(earnings_dates),
        "avg_surprise_pct": _avg_surprise_pct(historical_surprises),
        "beat_rate": _beat_rate(historical_surprises),
        "streak": _streak(historical_surprises),
        "historical": historical_surprises,
    }
