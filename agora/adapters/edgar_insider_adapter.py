"""EDGAR insider-trading (Form 4) adapter for Agora.

Fetches SEC Form 4 filings via the EDGAR full-text search (EFTS) API,
downloads the underlying XML for each filing, and parses insider
transaction details into agora.schemas.Transaction objects.

SEC EDGAR EFTS endpoint:
  https://efts.sec.gov/LATEST/search-index?forms=4&q=...

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
EDGAR_ARCHIVES_BASE = "https://www.sec.gov/Archives"
SEC_USER_AGENT = "Agora Financial Intelligence research@agora-finance.io"
REQUEST_TIMEOUT = 30

# SEC rate limit: 10 requests/second.  We enforce a floor of 0.11s between
# requests to stay comfortably under the limit.
_MIN_REQUEST_INTERVAL = 0.11
_last_request_time: float = 0.0


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def fetch_insider_trades(
    symbol: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Transaction]:
    """Fetch insider trades (Form 4) from SEC EDGAR for *symbol*.

    Parameters
    ----------
    symbol : str
        Ticker symbol (e.g. ``"AAPL"``).
    start_date : date | None
        If provided, only return trades on or after this date.
    end_date : date | None
        If provided, only return trades on or before this date.

    Returns
    -------
    list[Transaction]
        Insider transactions in chronological order.  Each Transaction has:
        - date: transaction date
        - entity: insider name
        - action: "Buy", "Sell", or "Exercise"
        - amount: number of shares
        - context: dict with keys such as ``title``, ``price``,
          ``shares_owned_after``, ``form_url``, ``symbol``.
    """
    filing_urls = _search_form4_filings(symbol, start_date, end_date)

    results: list[Transaction] = []
    for url in filing_urls:
        try:
            transactions = _parse_form4_xml(url)
        except Exception:
            logger.warning("Failed to parse Form 4 at %s, skipping", url, exc_info=True)
            continue

        for txn in transactions:
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


def _search_form4_filings(
    symbol: str,
    start_date: date | None,
    end_date: date | None,
) -> list[str]:
    """Return a list of Form 4 XML document URLs for *symbol*."""
    params: dict[str, str] = {
        "q": f'"issuerTradingSymbol" AND "{symbol.upper()}"',
        "forms": "4",
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

    return _extract_xml_urls(data_)


def _extract_xml_urls(efts_response: dict[str, Any]) -> list[str]:
    """Pull filing document URLs out of the EFTS JSON response."""
    urls: list[str] = []
    hits = efts_response.get("hits", {}).get("hits", [])
    for hit in hits:
        file_path = hit.get("_id", "")
        if file_path:
            url = f"{EDGAR_ARCHIVES_BASE}/{file_path}"
            urls.append(url)
    return urls


# -----------------------------------------------------------------------
# Form 4 XML parsing
# -----------------------------------------------------------------------

_TRANSACTION_CODES: dict[str, str] = {
    "P": "Buy",
    "S": "Sell",
    "M": "Exercise",
    "C": "Exercise",
    "A": "Buy",
    "D": "Sell",
    "F": "Sell",
    "G": "Buy",
    "J": "Buy",
    "X": "Exercise",
}


def _parse_form4_xml(url: str) -> list[Transaction]:
    """Download and parse a single Form 4 XML filing into Transactions."""
    _throttle()
    resp = _get(url)
    if resp.status_code != 200:
        logger.debug("Form 4 download failed (HTTP %d): %s", resp.status_code, url)
        return []

    return _parse_form4_xml_content(resp.content, url)


def _parse_form4_xml_content(xml_bytes: bytes, source_url: str = "") -> list[Transaction]:
    """Parse Form 4 XML bytes into Transaction objects."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        logger.debug("XML parse error for %s", source_url)
        return []

    insider_name = _text(root, ".//rptOwnerName") or "Unknown"
    insider_title = (
        _text(root, ".//officerTitle")
        or _text(root, ".//rptOwnerRelationship/officerTitle")
        or ""
    )
    issuer_symbol = _text(root, ".//issuerTradingSymbol") or ""

    transactions: list[Transaction] = []

    for txn_el in root.findall(".//nonDerivativeTransaction"):
        parsed = _parse_transaction_element(
            txn_el, insider_name, insider_title, issuer_symbol, source_url,
        )
        if parsed is not None:
            transactions.append(parsed)

    for txn_el in root.findall(".//derivativeTransaction"):
        parsed = _parse_transaction_element(
            txn_el, insider_name, insider_title, issuer_symbol, source_url,
        )
        if parsed is not None:
            transactions.append(parsed)

    return transactions


def _parse_transaction_element(
    el: ET.Element,
    insider_name: str,
    insider_title: str,
    issuer_symbol: str,
    source_url: str,
) -> Transaction | None:
    """Extract a single Transaction from a (non)derivativeTransaction element."""
    date_str = _text(el, ".//transactionDate/value")
    if not date_str:
        return None
    try:
        txn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

    code = _text(el, ".//transactionCoding/transactionCode") or ""
    action = _TRANSACTION_CODES.get(code.upper(), code.upper() or "Unknown")

    shares_str = (
        _text(el, ".//transactionAmounts/transactionShares/value")
        or _text(el, ".//transactionShares/value")
        or "0"
    )
    try:
        shares = float(shares_str)
    except (ValueError, TypeError):
        shares = 0.0

    price_str = (
        _text(el, ".//transactionAmounts/transactionPricePerShare/value")
        or _text(el, ".//transactionPricePerShare/value")
        or ""
    )
    price: float | None = None
    if price_str:
        try:
            price = float(price_str)
        except (ValueError, TypeError):
            price = None

    owned_after_str = (
        _text(el, ".//postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        or ""
    )
    owned_after: float | None = None
    if owned_after_str:
        try:
            owned_after = float(owned_after_str)
        except (ValueError, TypeError):
            owned_after = None

    context: dict[str, Any] = {"symbol": issuer_symbol}
    if insider_title:
        context["title"] = insider_title
    if price is not None:
        context["price"] = price
    if owned_after is not None:
        context["shares_owned_after"] = owned_after
    if source_url:
        context["form_url"] = source_url

    return Transaction(
        date=txn_date,
        entity=insider_name,
        action=action,
        amount=shares,
        context=context,
    )


# -----------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------


def _text(el: ET.Element, xpath: str) -> str | None:
    """Return stripped text of the first matching child, or None."""
    child = el.find(xpath)
    if child is not None and child.text:
        return child.text.strip()
    return None


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
