"""FINRA short volume adapter for Agora.

Queries the FINRA RegSHO daily short volume API and returns data as
ShortData objects.  Each trading day’s short volume and total volume are
aggregated across all reporting facilities (NQTRF, NYTR, NCTRF) so that
the caller receives a single row per symbol per date.

FINRA API reference:
    POST https://api.finra.org/data/group/OTCMarket/name/regShoDaily
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import requests

from agora.schemas import ShortData

logger = logging.getLogger(__name__)

FINRA_API_URL = "https://api.finra.org/data/group/OTCMarket/name/regShoDaily"
REQUEST_TIMEOUT = 60
_MAX_LIMIT = 5000  # FINRA page size cap


def fetch_short_volume(
    symbol: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ShortData]:
    """Fetch FINRA daily short volume data for *symbol*.

    Parameters
    ----------
    symbol : str
        Ticker symbol (e.g. ``"AAPL"``).
    start_date : date | None
        Earliest trade-report date to include.  Defaults to 30 calendar
        days before *end_date* (or today).
    end_date : date | None
        Latest trade-report date to include.  Defaults to today.

    Returns
    -------
    list[ShortData]
        Records in chronological order with ``data_type="short_volume"``
        and ``source="FINRA"``.  ``value`` is the aggregate short volume
        and ``total_for_ratio`` is the aggregate total volume so that
        ``value / total_for_ratio`` gives the short-volume ratio.
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    raw_rows = _fetch_all_pages(symbol.upper(), start_date, end_date)
    aggregated = _aggregate_by_date(symbol.upper(), raw_rows)

    aggregated.sort(key=lambda r: r.date)
    return aggregated


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------


def _build_request_body(
    symbol: str,
    start_date: date,
    end_date: date,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    """Build the JSON body for the FINRA regShoDaily query."""
    return {
        "limit": limit,
        "offset": offset,
        "dateRangeFilters": [
            {
                "fieldName": "tradeReportDate",
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
            },
        ],
        "domainFilters": [
            {
                "fieldName": "securitiesInformationProcessorSymbolIdentifier",
                "values": [symbol],
            },
        ],
    }


def _fetch_page(
    symbol: str,
    start_date: date,
    end_date: date,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """Fetch a single page of results from the FINRA API."""
    body = _build_request_body(symbol, start_date, end_date, limit, offset)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    resp = requests.post(
        FINRA_API_URL,
        json=body,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    if resp.status_code == 204:
        return []
    if resp.status_code != 200:
        raise RuntimeError(
            f"FINRA API request failed (HTTP {resp.status_code}): {resp.text[:300]}"
        )

    data = resp.json()
    if not isinstance(data, list):
        logger.warning("Unexpected FINRA response type: %s", type(data))
        return []
    return data


def _fetch_all_pages(
    symbol: str,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """Paginate through the FINRA API until all rows are fetched."""
    all_rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        try:
            page = _fetch_page(symbol, start_date, end_date, _MAX_LIMIT, offset)
        except Exception:
            logger.warning(
                "FINRA API request failed for %s (%s to %s), offset=%d",
                symbol,
                start_date,
                end_date,
                offset,
                exc_info=True,
            )
            break

        if not page:
            break

        all_rows.extend(page)

        if len(page) < _MAX_LIMIT:
            break
        offset += _MAX_LIMIT

    return all_rows


def _aggregate_by_date(
    symbol: str,
    rows: list[dict[str, Any]],
) -> list[ShortData]:
    """Aggregate per-facility rows into one ShortData per date.

    The FINRA API returns separate rows for each reporting facility
    (NQTRF, NYTR, NCTRF).  We sum ``shortParQuantity`` and
    ``totalParQuantity`` across facilities for the same date.
    """
    date_totals: dict[date, dict[str, float]] = defaultdict(
        lambda: {"short": 0.0, "total": 0.0}
    )

    for row in rows:
        try:
            trade_date = date.fromisoformat(row["tradeReportDate"])
            short_qty = float(row["shortParQuantity"])
            total_qty = float(row["totalParQuantity"])
        except (KeyError, ValueError, TypeError) as exc:
            logger.debug("Skipping malformed FINRA row: %s | error: %s", row, exc)
            continue

        date_totals[trade_date]["short"] += short_qty
        date_totals[trade_date]["total"] += total_qty

    results: list[ShortData] = []
    for trade_date, totals in date_totals.items():
        results.append(
            ShortData(
                symbol=symbol,
                date=trade_date,
                data_type="short_volume",
                value=totals["short"],
                total_for_ratio=totals["total"],
                source="FINRA",
            )
        )

    return results
