"""Reg SHO threshold list adapter for Agora.

Fetches Regulation SHO threshold security lists from NYSE, NASDAQ, and CBOE.
A security lands on the threshold list when it has sustained high
fails-to-deliver (FTDs): >=10,000 shares, >=0.5% of outstanding shares,
for 5 consecutive settlement days.

Data sources:
    NYSE:   https://www.nyse.com/regulation/threshold-securities
    NASDAQ: https://www.nasdaqtrader.com/dynamic/symdir/regsho/nasdaqth{YYYYMMDD}.txt
    CBOE:   https://www.cboe.com/us/equities/market_statistics/threshold_securities/
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date
from typing import Any

import requests

from agora.schemas import ShortData

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 60

# -----------------------------------------------------------------------
# Public URLs
# -----------------------------------------------------------------------

NASDAQ_URL_TEMPLATE = (
    "https://www.nasdaqtrader.com/dynamic/symdir/regsho/nasdaqth{date_str}.txt"
)
NYSE_URL_TEMPLATE = (
    "https://www.nyse.com/api/regulatory/threshold-securities/download"
)
CBOE_URL_TEMPLATE = (
    "https://www.cboe.com/us/equities/market_statistics/threshold_securities/"
    "?mkt=edgx&dt={iso_date}"
)

# Exchanges we aggregate across
EXCHANGES = ("NYSE", "NASDAQ", "CBOE")


def fetch_threshold_list(
    *,
    symbol: str | None = None,
    date: date | None = None,
) -> list[ShortData]:
    """Fetch Reg SHO threshold securities aggregated across exchanges.

    Parameters
    ----------
    symbol : str | None
        If provided, only return records matching this ticker.
    date : date | None
        The settlement date to query.  Defaults to today.

    Returns
    -------
    list[ShortData]
        One record per unique symbol-date pair with
        ``data_type="threshold"`` and ``source="RegSHO"``.
        ``value`` is the number of exchanges listing the security
        on their threshold list (1-3).
    """
    from datetime import date as _date_type

    query_date: _date_type = date if date is not None else _date_type.today()

    raw_entries: list[dict[str, Any]] = []

    for exchange in EXCHANGES:
        try:
            entries = _fetch_exchange(exchange, query_date)
            raw_entries.extend(entries)
        except Exception:
            logger.warning(
                "Failed to fetch threshold list from %s for %s, skipping",
                exchange,
                query_date,
                exc_info=True,
            )

    aggregated = _aggregate_entries(raw_entries, query_date)

    if symbol is not None:
        aggregated = [r for r in aggregated if r.symbol.upper() == symbol.upper()]

    aggregated.sort(key=lambda r: r.symbol)
    return aggregated


# -----------------------------------------------------------------------
# Per-exchange fetch helpers
# -----------------------------------------------------------------------


def _fetch_exchange(exchange: str, query_date: date) -> list[dict[str, Any]]:
    """Dispatch to the correct exchange-specific fetcher."""
    fetchers = {
        "NYSE": _fetch_nyse,
        "NASDAQ": _fetch_nasdaq,
        "CBOE": _fetch_cboe,
    }
    fetcher = fetchers.get(exchange)
    if fetcher is None:
        raise ValueError(f"Unknown exchange: {exchange}")
    return fetcher(query_date)


def _fetch_nyse(query_date: date) -> list[dict[str, Any]]:
    """Fetch NYSE threshold list for a given date."""
    params = {"selectedDate": query_date.isoformat()}
    resp = requests.get(
        NYSE_URL_TEMPLATE,
        params=params,
        timeout=REQUEST_TIMEOUT,
        headers={"Accept": "application/json"},
    )

    if resp.status_code == 404:
        return []
    if resp.status_code != 200:
        raise RuntimeError(
            f"NYSE threshold list request failed (HTTP {resp.status_code})"
        )

    data = resp.json()
    if not isinstance(data, list):
        return []

    entries: list[dict[str, Any]] = []
    for item in data:
        sym = item.get("symbol", "").strip()
        if sym:
            entries.append({"symbol": sym.upper(), "exchange": "NYSE"})
    return entries


def _fetch_nasdaq(query_date: date) -> list[dict[str, Any]]:
    """Fetch NASDAQ threshold list for a given date."""
    date_str = query_date.strftime("%Y%m%d")
    url = NASDAQ_URL_TEMPLATE.format(date_str=date_str)

    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    if resp.status_code == 404:
        return []
    if resp.status_code != 200:
        raise RuntimeError(
            f"NASDAQ threshold list request failed (HTTP {resp.status_code})"
        )

    return _parse_nasdaq_text(resp.text)


def _parse_nasdaq_text(text: str) -> list[dict[str, Any]]:
    """Parse NASDAQ pipe-delimited threshold list text."""
    entries: list[dict[str, Any]] = []
    reader = csv.reader(io.StringIO(text), delimiter="|")

    header: list[str] | None = None
    for fields in reader:
        if not fields or not fields[0].strip():
            continue

        if header is None:
            header = [f.strip().upper() for f in fields]
            continue

        # Skip trailer lines
        if len(fields) < 2:
            continue

        row = dict(zip(header, [f.strip() for f in fields]))
        sym = row.get("SYMBOL", "").strip()
        if sym and not sym.startswith("File"):
            entries.append({"symbol": sym.upper(), "exchange": "NASDAQ"})

    return entries


def _fetch_cboe(query_date: date) -> list[dict[str, Any]]:
    """Fetch CBOE (EDGX) threshold list for a given date."""
    url = CBOE_URL_TEMPLATE.format(iso_date=query_date.isoformat())

    resp = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"Accept": "application/json"},
    )

    if resp.status_code == 404:
        return []
    if resp.status_code != 200:
        raise RuntimeError(
            f"CBOE threshold list request failed (HTTP {resp.status_code})"
        )

    data = resp.json()
    records = data if isinstance(data, list) else data.get("data", [])

    entries: list[dict[str, Any]] = []
    for item in records:
        sym = ""
        if isinstance(item, dict):
            sym = item.get("symbol", item.get("Symbol", "")).strip()
        if sym:
            entries.append({"symbol": sym.upper(), "exchange": "CBOE"})
    return entries


# -----------------------------------------------------------------------
# Aggregation
# -----------------------------------------------------------------------


def _aggregate_entries(
    raw_entries: list[dict[str, Any]],
    query_date: date,
) -> list[ShortData]:
    """Aggregate threshold entries across exchanges.

    For each unique symbol, count how many exchanges list it.  The ``value``
    field holds the exchange count (1-3), and ``total_for_ratio`` is set to
    the total number of exchanges queried (3) so that
    ``value / total_for_ratio`` gives the fraction of exchanges.
    """
    exchange_counts: dict[str, set[str]] = {}
    for entry in raw_entries:
        sym = entry["symbol"]
        exchange = entry["exchange"]
        if sym not in exchange_counts:
            exchange_counts[sym] = set()
        exchange_counts[sym].add(exchange)

    results: list[ShortData] = []
    for sym, exchanges in exchange_counts.items():
        results.append(
            ShortData(
                symbol=sym,
                date=query_date,
                data_type="threshold",
                value=float(len(exchanges)),
                total_for_ratio=float(len(EXCHANGES)),
                source="RegSHO",
            )
        )

    return results
