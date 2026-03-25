"""FINRA short interest adapter for Agora.

Queries the FINRA consolidated short interest API and returns data as
ShortData objects.  Short interest is reported twice monthly (mid-month
and end-of-month settlement dates).

FINRA API reference:
    POST https://api.finra.org/data/group/OTCMarket/name/consolidatedShortInterest
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import requests

from agora.schemas import ShortData

logger = logging.getLogger(__name__)

FINRA_API_URL = (
    "https://api.finra.org/data/group/OTCMarket/name/consolidatedShortInterest"
)
REQUEST_TIMEOUT = 60
_MAX_LIMIT = 5000  # FINRA page size cap


def fetch_short_interest(
    symbol: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ShortData]:
    """Fetch FINRA twice-monthly short interest data for *symbol*.

    Parameters
    ----------
    symbol : str
        Ticker symbol (e.g. ``"AAPL"``).
    start_date : date | None
        Earliest settlement date to include.  Defaults to 90 calendar
        days before *end_date* (or today).
    end_date : date | None
        Latest settlement date to include.  Defaults to today.

    Returns
    -------
    list[ShortData]
        Records in chronological order with ``data_type="short_interest"``
        and ``source="FINRA"``.  ``value`` is the current short interest
        (shares short) and ``total_for_ratio`` is shares outstanding when
        available, enabling short-interest-as-percent-of-float calculation.
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=90)

    raw_rows = _fetch_all_pages(symbol.upper(), start_date, end_date)
    results = _parse_rows(symbol.upper(), raw_rows)

    results.sort(key=lambda r: r.date)
    return results


# ---------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------


def _build_request_body(
    symbol: str,
    start_date: date,
    end_date: date,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    """Build the JSON body for the FINRA consolidatedShortInterest query."""
    return {
        "limit": limit,
        "offset": offset,
        "dateRangeFilters": [
            {
                "fieldName": "settlementDate",
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
            },
        ],
        "domainFilters": [
            {
                "fieldName": "symbolCode",
                "values": [symbol],
            },
        ],
        "sortFields": [
            {
                "fieldName": "settlementDate",
                "order": "desc",
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


def _parse_rows(
    symbol: str,
    rows: list[dict[str, Any]],
) -> list[ShortData]:
    """Convert raw FINRA JSON rows into ShortData objects.

    Each row from the FINRA consolidated short interest endpoint contains
    ``currentShortPositionQuantity`` (shares short) and, when available,
    ``sharesOutstandingQuantity`` (total shares outstanding).
    """
    results: list[ShortData] = []

    for row in rows:
        try:
            settlement_date = date.fromisoformat(row["settlementDate"])
            short_interest = float(row["currentShortPositionQuantity"])
        except (KeyError, ValueError, TypeError) as exc:
            logger.debug("Skipping malformed FINRA row: %s | error: %s", row, exc)
            continue

        # sharesOutstandingQuantity may be absent or null
        shares_outstanding: float | None = None
        raw_outstanding = row.get("sharesOutstandingQuantity")
        if raw_outstanding is not None:
            try:
                shares_outstanding = float(raw_outstanding)
            except (ValueError, TypeError):
                pass

        results.append(
            ShortData(
                symbol=symbol,
                date=settlement_date,
                data_type="short_interest",
                value=short_interest,
                total_for_ratio=shares_outstanding,
                source="FINRA",
            )
        )

    return results
