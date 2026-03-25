"""EDGAR institutional-holdings (13F) adapter for Agora.

Fetches SEC Form 13F-HR filings via the EDGAR full-text search (EFTS)
API, downloads the underlying XML information tables, and parses
institutional holding details into agora.schemas.Transaction objects.

Form 13F-HR: filed quarterly by institutional investment managers with
             >=USD 100M in qualifying assets under management.

SEC EDGAR EFTS endpoint:
  https://efts.sec.gov/LATEST/search-index?forms=13F-HR&q=...

SEC requires:
  - A descriptive User-Agent header
  - Rate limiting to 10 requests per second
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Any

import requests

from agora.schemas import Transaction

logger = logging.getLogger(__name__)

EFTS_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
SEC_USER_AGENT = "Agora Financial Intelligence research@agora-finance.io"
REQUEST_TIMEOUT = 30

# SEC rate limit: 10 requests/second.  We enforce a floor of 0.11s between
# requests to stay comfortably under the limit.
_MIN_REQUEST_INTERVAL = 0.11
_last_request_time: float = 0.0

# Forms we search for (initial and amendment variants).
_13F_FORMS = "13F-HR,13F-HR/A"

# XML namespace used in 13F information tables.
_NS = {"ns": "http://www.sec.gov/edgar/document/thirteenf/informationtable"}


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def fetch_institutional_holdings(
    symbol: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Transaction]:
    """Fetch institutional holdings (13F) from SEC EDGAR for *symbol*.

    Parameters
    ----------
    symbol : str
        Ticker symbol (e.g. ``"AAPL"``).
    start_date : date | None
        If provided, only return filings on or after this date.
    end_date : date | None
        If provided, only return filings on or before this date.

    Returns
    -------
    list[Transaction]
        Institutional holding transactions in chronological order.  Each
        Transaction has:
        - date: filing date
        - entity: institution name
        - action: ``"Hold"``, ``"Increase"``, ``"Decrease"``, ``"New"``,
          or ``"Exit"``
        - amount: number of shares
        - context: dict with keys such as ``value_usd``,
          ``filing_type``, ``form_url``, ``symbol``.
    """
    filings = _search_13f_filings(symbol, start_date, end_date)

    results: list[Transaction] = []
    for filing_meta in filings:
        try:
            txns = _parse_13f_filing(filing_meta, symbol)
        except Exception:
            logger.warning(
                "Failed to parse 13F filing at %s, skipping",
                filing_meta.get("url", "unknown"),
                exc_info=True,
            )
            continue

        for txn in txns:
            if start_date is not None and txn.date < start_date:
                continue
            if end_date is not None and txn.date > end_date:
                continue
            results.append(txn)

    results.sort(key=lambda t: t.date)
    return results
