"""EDGAR company-filings adapter for Agora.

Fetches SEC company filings (10-K, 10-Q, 8-K) via the EDGAR full-text
search (EFTS) API and returns normalised Filing objects.

EDGAR EFTS endpoint:
  https://efts.sec.gov/LATEST/search-index?forms=10-K&q=...

SEC requires:
  - A descriptive User-Agent header
  - Rate limiting to 10 requests per second
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import requests

from agora.schemas import Filing

logger = logging.getLogger(__name__)

EFTS_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_FILING_BASE = "https://www.sec.gov/Archives/edgar/data"
SEC_USER_AGENT = "Agora Financial Intelligence research@agora-finance.io"
REQUEST_TIMEOUT = 30

_SUPPORTED_FILING_TYPES = {"10-K", "10-Q", "8-K"}

# SEC rate limit: 10 requests/second.  We enforce a floor of 0.11s between
# requests to stay comfortably under the limit.
_MIN_REQUEST_INTERVAL = 0.11
_last_request_time: float = 0.0


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def fetch_filings(
    symbol: str,
    *,
    filing_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Filing]:
    """Fetch company filings from SEC EDGAR for *symbol*.

    Parameters
    ----------
    symbol : str
        Ticker symbol (e.g. ``"AAPL"``).
    filing_type : str | None
        If provided, restrict to this filing type (``"10-K"``, ``"10-Q"``,
        or ``"8-K"``).  When *None*, all three types are returned.
    start_date : date | None
        If provided, only return filings on or after this date.
    end_date : date | None
        If provided, only return filings on or before this date.

    Returns
    -------
    list[Filing]
        Filings in chronological order.  Each Filing has:
        - date: filing date
        - entity: company name
        - type: filing type (e.g. "10-K")
        - url: EDGAR filing URL
        - extracted_fields: dict with ``accession_number`` and ``cik``
    """
    if filing_type is not None and filing_type not in _SUPPORTED_FILING_TYPES:
        raise ValueError(
            f"Unsupported filing_type {filing_type!r}; "
            f"must be one of {sorted(_SUPPORTED_FILING_TYPES)}"
        )

    forms = filing_type if filing_type is not None else ",".join(sorted(_SUPPORTED_FILING_TYPES))
    raw_hits = _search_filings(symbol, forms=forms, start_date=start_date, end_date=end_date)

    results: list[Filing] = []
    for hit in raw_hits:
        filing = _hit_to_filing(hit)
        if filing is None:
            continue
        if start_date is not None and filing.date < start_date:
            continue
        if end_date is not None and filing.date > end_date:
            continue
        results.append(filing)

    results.sort(key=lambda f: f.date)
    return results


# -----------------------------------------------------------------------
# Filing discovery via EDGAR EFTS
# -----------------------------------------------------------------------


def _search_filings(
    symbol: str,
    *,
    forms: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict[str, Any]]:
    """Return raw EFTS hit dicts for *symbol* and *forms*."""
    params: dict[str, str] = {
        "q": f'"{symbol.upper()}"',
        "forms": forms,
        "dateRange": "custom",
    }
    if start_date is not None:
        params["startdt"] = start_date.isoformat()
    else:
        params["startdt"] = "2000-01-01"
    if end_date is not None:
        params["enddt"] = end_date.isoformat()
    else:
        params["enddt"] = date.today().isoformat()

    _throttle()
    resp = _get(EFTS_SEARCH_URL, params=params)

    if resp.status_code != 200:
        logger.warning(
            "EFTS search returned HTTP %d for symbol=%s, forms=%s",
            resp.status_code,
            symbol,
            forms,
        )
        return []

    try:
        data = resp.json()
    except Exception:
        logger.warning("EFTS returned non-JSON response for symbol=%s", symbol)
        return []

    return data.get("hits", {}).get("hits", [])


def _hit_to_filing(hit: dict[str, Any]) -> Filing | None:
    """Convert a single EFTS hit dict into a Filing, or *None* on failure."""
    _id = hit.get("_id", "")
    source = hit.get("_source", {})

    if ":" not in _id:
        return None

    accession, filename = _id.split(":", 1)

    ciks = source.get("ciks", [])
    if not ciks:
        return None
    cik = ciks[0]

    entity_name = source.get("display_names", [""])[0] if source.get("display_names") else ""
    if not entity_name:
        entity_name = source.get("entity_name", "Unknown")

    form_type = source.get("forms", [""])[0] if source.get("forms") else ""
    if not form_type:
        form_type = source.get("form_type", "Unknown")

    file_date_str = source.get("file_date", "") or source.get("period_of_report", "")
    if not file_date_str:
        return None
    try:
        file_date = date.fromisoformat(file_date_str)
    except ValueError:
        return None

    accession_nodash = accession.replace("-", "")
    url = f"{EDGAR_FILING_BASE}/{cik}/{accession_nodash}/{filename}"

    return Filing(
        date=file_date,
        entity=entity_name,
        type=form_type,
        url=url,
        extracted_fields={
            "accession_number": accession,
            "cik": str(cik),
        },
    )


# -----------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------


def _throttle() -> None:
    """Enforce SEC rate limit of 10 req/sec."""
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


def _get(url: str, **kwargs: Any) -> requests.Response:
    """GET with the required SEC User-Agent header."""
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", SEC_USER_AGENT)
    return requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
