"""EDGAR activist-position (13D/13G) adapter for Agora.

Fetches SEC Schedule 13D and 13G filings via the EDGAR full-text search
(EFTS) API, downloads the underlying filing documents, and parses
activist position details into agora.schemas.Transaction objects.

Schedule 13D: filed when an investor acquires >5% of a public company
               with intent to influence management.
Schedule 13G: filed by passive investors who acquire >5%.

SEC EDGAR EFTS endpoint:
  https://efts.sec.gov/LATEST/search-index?forms=SC 13D,SC 13G&q=...

SEC requires:
  - A descriptive User-Agent header
  - Rate limiting to 10 requests per second
"""

from __future__ import annotations

import logging
import re
import time
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

# Forms we search for (both initial and amendment variants).
_ACTIVIST_FORMS = "SC 13D,SC 13D/A,SC 13G,SC 13G/A"


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def fetch_activist_positions(
    symbol: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Transaction]:
    """Fetch activist positions (13D/13G) from SEC EDGAR for *symbol*.

    Parameters
    ----------
    symbol : str
        Ticker symbol (e.g. ``\"AAPL\"``).
    start_date : date | None
        If provided, only return filings on or after this date.
    end_date : date | None
        If provided, only return filings on or before this date.

    Returns
    -------
    list[Transaction]
        Activist position transactions in chronological order.  Each
        Transaction has:
        - date: filing date
        - entity: activist / filer name
        - action: ``\"Acquire\"``, ``\"Increase\"``, or ``\"Decrease\"``
        - amount: number of shares
        - context: dict with keys such as ``percent_owned``,
          ``filing_type``, ``form_url``, ``symbol``.
    """
    filings = _search_activist_filings(symbol, start_date, end_date)

    results: list[Transaction] = []
    for filing_meta in filings:
        try:
            txn = _parse_activist_filing(filing_meta, symbol)
        except Exception:
            logger.warning(
                "Failed to parse activist filing at %s, skipping",
                filing_meta.get("url", "unknown"),
                exc_info=True,
            )
            continue

        if txn is None:
            continue
        if start_date is not None and txn.date < start_date:
            continue
        if end_date is not None and txn.date > end_date:
            continue
        results.append(txn)

    results.sort(key=lambda t: t.date)
    return results


# -----------------------------------------------------------------------
# Filing discovery via EDGAR EFTS
# -----------------------------------------------------------------------


def _search_activist_filings(
    symbol: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict[str, Any]]:
    """Return metadata dicts for 13D/13G filings matching *symbol*."""
    params: dict[str, str] = {
        "q": '"' + symbol.upper() + '"',
        "forms": _ACTIVIST_FORMS,
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
            "EFTS search returned HTTP %d for symbol=%s",
            resp.status_code,
            symbol,
        )
        return []

    try:
        data_ = resp.json()
    except Exception:
        logger.warning("EFTS returned non-JSON response for symbol=%s", symbol)
        return []

    return _extract_filing_metadata(data_)


def _extract_filing_metadata(efts_response: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull filing metadata out of the EFTS JSON response."""
    filings: list[dict[str, Any]] = []
    hits = efts_response.get("hits", {}).get("hits", [])
    for hit in hits:
        _id = hit.get("_id", "")
        source = hit.get("_source", {})
        if ":" not in _id:
            continue
        accession, filename = _id.split(":", 1)
        ciks = source.get("ciks", [])
        if not ciks:
            continue
        # The filer (activist) CIK is typically first
        cik = ciks[0]
        accession_nodash = accession.replace("-", "")
        url = f"{EDGAR_ARCHIVES_BASE}/{cik}/{accession_nodash}/{filename}"

        file_date_str = source.get("file_date", "")
        display_names = source.get("display_names", [])
        form_type = source.get("form_type", "")
        filer_name = display_names[0] if display_names else ""

        filings.append({
            "url": url,
            "file_date": file_date_str,
            "filer_name": filer_name,
            "form_type": form_type,
            "accession": accession,
        })
    return filings


# -----------------------------------------------------------------------
# Filing text parsing
# -----------------------------------------------------------------------

# Regex patterns for extracting position data from 13D/13G text.
# These filings are typically HTML or plain-text (not structured XML).
_RE_SHARES = re.compile(
    r"(?:aggregate\s+amount|number\s+of\s+shares)\s*(?:beneficially\s+owned)?"
    r"\s*[:\-]?\s*([\d,]+)",
    re.IGNORECASE,
)
_RE_PERCENT = re.compile(
    r"(?:percent\s+of\s+class|percentage)\s*[:\-]?\s*([\d.]+)\s*%",
    re.IGNORECASE,
)
_RE_NAME_COVER = re.compile(
    r"(?:names?\s+of\s+reporting\s+persons?|filed\s+by)\s*[:\-]?\s*"
    r"([A-Z][\w \t,.&'()-]+)",
    re.IGNORECASE,
)


def _parse_activist_filing(
    filing_meta: dict[str, Any],
    symbol: str,
) -> Transaction | None:
    """Download and parse a single 13D/13G filing into a Transaction."""
    url = filing_meta.get("url", "")
    if not url:
        return None

    _throttle()
    resp = _get(url)
    if resp.status_code != 200:
        logger.debug(
            "Activist filing download failed (HTTP %d): %s", resp.status_code, url,
        )
        return None

    return _parse_activist_filing_text(
        resp.text, filing_meta, symbol,
    )


def _parse_activist_filing_text(
    text: str,
    filing_meta: dict[str, Any],
    symbol: str,
) -> Transaction | None:
    """Parse activist filing text and filing metadata into a Transaction."""
    # -- Filing date --
    file_date_str = filing_meta.get("file_date", "")
    if not file_date_str:
        return None
    try:
        filing_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

    # -- Activist name: prefer parsed from cover page, fall back to EFTS metadata --
    activist_name = _extract_name(text) or filing_meta.get("filer_name", "Unknown")

    # -- Shares --
    shares = _extract_shares(text)
    if shares is None:
        return None

    # -- Percent owned --
    percent_owned = _extract_percent(text)

    # -- Action: determine from form type and filing context --
    form_type = filing_meta.get("form_type", "")
    action = _determine_action(form_type, text)

    context: dict[str, Any] = {"symbol": symbol.upper()}
    if percent_owned is not None:
        context["percent_owned"] = percent_owned
    if form_type:
        context["filing_type"] = form_type
    filing_url = filing_meta.get("url", "")
    if filing_url:
        context["form_url"] = filing_url

    return Transaction(
        date=filing_date,
        entity=activist_name,
        action=action,
        amount=float(shares),
        context=context,
    )


def _extract_name(text: str) -> str | None:
    """Try to extract the activist / reporting person name from filing text."""
    match = _RE_NAME_COVER.search(text)
    if match:
        name = match.group(1).strip().rstrip(".")
        # Reject overly long matches (likely captured a paragraph)
        if len(name) <= 120:
            return name
    return None


def _extract_shares(text: str) -> int | None:
    """Extract the aggregate number of shares beneficially owned."""
    match = _RE_SHARES.search(text)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _extract_percent(text: str) -> float | None:
    """Extract the percentage of class owned."""
    match = _RE_PERCENT.search(text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _determine_action(form_type: str, text: str) -> str:
    """Determine the action based on form type and filing content.

    - 13D (initial) or 13G (initial) -> \"Acquire\"
    - 13D/A or 13G/A (amendment) -> \"Increase\" or \"Decrease\"
      depending on language in the filing text.
    """
    is_amendment = "/A" in form_type

    if not is_amendment:
        return "Acquire"

    # For amendments, look for language indicating direction
    text_lower = text.lower()
    decrease_signals = [
        "decreased",
        "reduced",
        "disposed",
        "sold",
        "no longer beneficially own",
    ]
    for signal in decrease_signals:
        if signal in text_lower:
            return "Decrease"

    # Default for amendments is increase (most common reason to amend)
    return "Increase"


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
