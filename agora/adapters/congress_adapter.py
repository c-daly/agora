"""Congressional stock-trading adapter for Agora.

Fetches congressional financial disclosures from the Capitol Trades API
(https://www.capitoltrades.com) and normalises them into
agora.schemas.Transaction objects.

Capitol Trades aggregates House and Senate financial disclosures from
disclosures.house.gov and efdsearch.senate.gov into a single searchable
API.  The adapter hits their public JSON endpoint (no API key required)
and parses the resulting trades.

If the Capitol Trades API becomes unavailable the adapter logs a warning
and returns an empty list rather than raising, keeping downstream
consumers resilient.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import requests

from agora.schemas import Transaction

logger = logging.getLogger(__name__)

CAPITOL_TRADES_API_URL = "https://bff.capitoltrades.com/trades"
REQUEST_TIMEOUT = 30
USER_AGENT = "Agora Financial Intelligence research@agora-finance.io"

# Capitol Trades uses page-based pagination with a configurable page size.
_PAGE_SIZE = 100


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def fetch_congress_trades(
    *,
    symbol: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Transaction]:
    """Fetch congressional stock trades from Capitol Trades.

    Parameters
    ----------
    symbol : str | None
        If provided, only return trades for this ticker (e.g. ``"AAPL"``).
    start_date : date | None
        If provided, only return trades on or after this date.
    end_date : date | None
        If provided, only return trades on or before this date.

    Returns
    -------
    list[Transaction]
        Congressional trades in chronological order.  Each Transaction has:

        - date: trade publication / transaction date
        - entity: congress member name
        - action: ``"Buy"`` or ``"Sell"``
        - amount: estimated dollar value (midpoint of the disclosed range)
        - context: dict with keys ``party``, ``state``, ``committee``
    """
    raw_trades = _fetch_all_pages(symbol=symbol, start_date=start_date, end_date=end_date)
    transactions = _normalize_trades(raw_trades, start_date=start_date, end_date=end_date)
    transactions.sort(key=lambda t: t.date)
    return transactions


# -----------------------------------------------------------------------
# Pagination / HTTP layer
# -----------------------------------------------------------------------

# Disclosed amount ranges and their midpoints used by Capitol Trades.
_AMOUNT_MIDPOINTS: dict[str, float] = {
    "$1,001 - $15,000": 8_000.0,
    "$15,001 - $50,000": 32_500.0,
    "$50,001 - $100,000": 75_000.0,
    "$100,001 - $250,000": 175_000.0,
    "$250,001 - $500,000": 375_000.0,
    "$500,001 - $1,000,000": 750_000.0,
    "$1,000,001 - $5,000,000": 3_000_000.0,
    "$5,000,001 - $25,000,000": 15_000_000.0,
    "$25,000,001 - $50,000,000": 37_500_000.0,
    "Over $50,000,000": 50_000_000.0,
}


def _build_params(
    *,
    symbol: str | None,
    start_date: date | None,
    end_date: date | None,
    page: int,
) -> dict[str, str | int]:
    """Build query-string parameters for the Capitol Trades API."""
    params: dict[str, str | int] = {
        "page": page,
        "pageSize": _PAGE_SIZE,
        "sortBy": "txDate",
        "sortOrder": "asc",
    }
    if symbol is not None:
        params["ticker"] = symbol.upper()
    if start_date is not None:
        params["txDate.gte"] = start_date.isoformat()
    if end_date is not None:
        params["txDate.lte"] = end_date.isoformat()
    return params


def _fetch_page(
    *,
    symbol: str | None,
    start_date: date | None,
    end_date: date | None,
    page: int,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch a single page and return ``(trades, total_count)``.

    Returns ``([], 0)`` on any HTTP or parse error so the caller can
    gracefully degrade.
    """
    params = _build_params(symbol=symbol, start_date=start_date, end_date=end_date, page=page)
    try:
        resp = requests.get(
            CAPITOL_TRADES_API_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Capitol Trades API request failed (page=%d): %s", page, exc)
        return [], 0

    data = body.get("data", [])
    meta = body.get("meta", {})
    total = int(meta.get("paging", {}).get("totalItems", 0))
    return data, total


def _fetch_all_pages(
    *,
    symbol: str | None,
    start_date: date | None,
    end_date: date | None,
) -> list[dict[str, Any]]:
    """Iterate through all pages and return the combined raw trade list."""
    page = 1
    all_trades: list[dict[str, Any]] = []

    data, total = _fetch_page(symbol=symbol, start_date=start_date, end_date=end_date, page=page)
    all_trades.extend(data)

    while len(all_trades) < total:
        page += 1
        data, _ = _fetch_page(
            symbol=symbol, start_date=start_date, end_date=end_date, page=page,
        )
        if not data:
            break
        all_trades.extend(data)

    return all_trades


# -----------------------------------------------------------------------
# Normalisation
# -----------------------------------------------------------------------


def _parse_date(raw: str | None) -> date | None:
    """Best-effort ISO date parse (``2024-03-18T00:00:00`` or ``2024-03-18``)."""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except (ValueError, TypeError):
        return None


def _estimate_amount(raw_range: str | None) -> float:
    """Map a disclosure amount range to its midpoint estimate.

    Falls back to 0.0 for any unrecognised value.
    """
    if not raw_range:
        return 0.0
    return _AMOUNT_MIDPOINTS.get(raw_range, 0.0)


def _normalize_action(raw: str | None) -> str:
    """Normalise Capitol Trades action strings to ``Buy`` / ``Sell``."""
    if not raw:
        return "Unknown"
    lower = raw.strip().lower()
    if lower in {"buy", "purchase"}:
        return "Buy"
    if lower in {"sell", "sale", "sale (full)", "sale (partial)"}:
        return "Sell"
    return raw.strip().title()


def _normalize_trades(
    raw_trades: list[dict[str, Any]],
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Transaction]:
    """Convert raw Capitol Trades JSON dicts into Transaction objects."""
    results: list[Transaction] = []
    for trade in raw_trades:
        tx_date = _parse_date(trade.get("txDate"))
        if tx_date is None:
            logger.debug("Skipping trade with missing/invalid txDate: %s", trade)
            continue

        if start_date is not None and tx_date < start_date:
            continue
        if end_date is not None and tx_date > end_date:
            continue

        politician = trade.get("politician", {}) or {}
        first = (politician.get("firstName") or "").strip()
        last = (politician.get("lastName") or "").strip()
        entity = f"{first} {last}".strip() or "Unknown"

        action = _normalize_action(trade.get("txType"))
        amount = _estimate_amount(trade.get("amount"))

        context: dict[str, Any] = {}
        party = politician.get("party")
        if party:
            context["party"] = party
        state = politician.get("state")
        if state:
            context["state"] = state
        chamber = politician.get("chamber")
        if chamber:
            context["chamber"] = chamber
        committees = politician.get("committees")
        if committees:
            context["committee"] = committees

        ticker = trade.get("ticker")
        if ticker:
            context["symbol"] = ticker

        asset_name = trade.get("assetName")
        if asset_name:
            context["asset_name"] = asset_name

        amount_range = trade.get("amount")
        if amount_range:
            context["disclosed_range"] = amount_range

        results.append(
            Transaction(
                date=tx_date,
                entity=entity,
                action=action,
                amount=amount,
                context=context,
            )
        )
    return results
