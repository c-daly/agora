"""SEC EDGAR 13F institutional holdings adapter for Agora.

Fetches institutional holdings from 13F-HR filings via EDGAR EFTS search API.
"""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

import requests

from agora.schemas import Transaction

logger = logging.getLogger(__name__)

EFTS_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
SEC_USER_AGENT = "Agora Financial Intelligence research@agora-finance.io"
REQUEST_TIMEOUT = 30
_THROTTLE_SECONDS = 0.11
_last_request_time = 0.0


def fetch_institutional_holdings(
    symbol: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Transaction]:
    """Fetch institutional holdings from 13F filings for a symbol."""
    filings = _search_13f_filings(symbol, start_date, end_date)
    results: list[Transaction] = []

    for filing in filings:
        try:
            holdings = _parse_13f_filing(filing)
            results.extend(holdings)
        except Exception:
            logger.warning("Failed to parse 13F filing: %s", filing.get("url", "?"), exc_info=True)
            continue

    if start_date:
        results = [r for r in results if r.date >= start_date]
    if end_date:
        results = [r for r in results if r.date <= end_date]

    results.sort(key=lambda r: r.date)
    return results


def _throttle() -> None:
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _THROTTLE_SECONDS:
        time.sleep(_THROTTLE_SECONDS - elapsed)
    _last_request_time = time.time()


def _get(url: str, **kwargs: Any) -> requests.Response:
    _throttle()
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", SEC_USER_AGENT)
    return requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)


def _search_13f_filings(
    symbol: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict]:
    """Search EDGAR EFTS for 13F-HR filings mentioning the symbol."""
    params: dict[str, str] = {
        "q": f'"{symbol.upper()}"',
        "forms": "13F-HR",
        "dateRange": "custom",
        "startdt": (start_date or date(2020, 1, 1)).isoformat(),
        "enddt": (end_date or date.today()).isoformat(),
    }

    resp = _get(EFTS_SEARCH_URL, params=params)
    if resp.status_code != 200:
        logger.warning("EFTS search returned HTTP %d for %s", resp.status_code, symbol)
        return []

    try:
        data = resp.json()
    except Exception:
        return []

    filings = []
    for hit in data.get("hits", {}).get("hits", []):
        _id = hit.get("_id", "")
        source = hit.get("_source", {})
        if ":" not in _id:
            continue
        accession, filename = _id.split(":", 1)
        ciks = source.get("ciks", [])
        if not ciks:
            continue
        cik = ciks[-1] if len(ciks) > 1 else ciks[0]
        accession_nodash = accession.replace("-", "")

        display_names = source.get("display_names", [])
        filer_name = display_names[0].split("(")[0].strip() if display_names else "Unknown"

        filings.append({
            "url": f"{EDGAR_ARCHIVES_BASE}/{cik}/{accession_nodash}/{filename}",
            "filer_name": filer_name,
            "file_date": source.get("file_date", ""),
            "accession": accession,
        })

    return filings


def _parse_13f_filing(filing: dict) -> list[Transaction]:
    """Parse a 13F filing to extract holdings."""
    url = filing.get("url", "")
    resp = _get(url)
    if resp.status_code != 200:
        logger.debug("13F download failed (HTTP %d): %s", resp.status_code, url)
        return []

    try:
        file_date = date.fromisoformat(filing.get("file_date", "")[:10])
    except (ValueError, TypeError):
        file_date = date.today()

    filer_name = filing.get("filer_name", "Unknown")
    results = []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        logger.debug("XML parse failed for %s", url)
        return []

    # 13F XML uses namespaces — try common patterns
    ns = {"": ""}
    for elem in root.iter():
        if "infoTable" in elem.tag:
            tag_ns = elem.tag.split("}")[0] + "}" if "}" in elem.tag else ""
            ns[""] = tag_ns
            break

    prefix = ns.get("", "")

    for entry in root.iter(f"{prefix}infoTable"):
        issuer = ""
        shares = 0.0
        value_usd = 0.0

        for child in entry:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            text = (child.text or "").strip()
            if tag == "nameOfIssuer":
                issuer = text
            elif tag == "sshPrnamt":
                try:
                    shares = float(text)
                except (ValueError, TypeError):
                    pass
            elif tag == "value":
                try:
                    value_usd = float(text) * 1000  # 13F reports in thousands
                except (ValueError, TypeError):
                    pass

        if issuer and shares > 0:
            results.append(Transaction(
                date=file_date,
                entity=filer_name,
                action="Hold",
                amount=shares,
                context={
                    "issuer": issuer,
                    "value_usd": value_usd,
                    "form_url": filing.get("url", ""),
                    "symbol": issuer,
                },
            ))

    return results
