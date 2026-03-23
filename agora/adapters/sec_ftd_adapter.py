"""SEC Fails-to-Deliver (FTD) adapter for Agora.

Downloads and parses SEC FTD flat files (pipe-delimited, published twice
monthly) and returns data as ShortData objects.

SEC FTD files are available at:
https://www.sec.gov/data/foiadata/failsdata/

File naming convention:
  cnsfails{YYYY}{MM}a.zip  ->  first half of month (days 1-15)
  cnsfails{YYYY}{MM}b.zip  ->  second half of month (days 16-end)
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from datetime import date
from typing import Iterator

import requests

from agora.schemas import ShortData

logger = logging.getLogger(__name__)

SEC_BASE_URL = "https://www.sec.gov/files/data/fails-deliver-data"
SEC_USER_AGENT = "Agora Financial Intelligence research@agora-finance.io"
REQUEST_TIMEOUT = 60


def fetch_ftd_data(
    *,
    symbol: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ShortData]:
    """Fetch SEC Fails-to-Deliver data.

    Parameters
    ----------
    symbol : str | None
        If provided, only return FTDs for this ticker symbol.
    start_date : date | None
        If provided, only return FTDs on or after this date.
    end_date : date | None
        If provided, only return FTDs on or before this date.

    Returns
    -------
    list[ShortData]
        FTD records in chronological order with data_type="ftd", source="SEC".
    """
    file_keys = _date_range_to_file_keys(start_date, end_date)

    results: list[ShortData] = []
    for year, month, half in file_keys:
        try:
            rows = _download_and_parse(year, month, half)
        except Exception:
            logger.warning(
                "Failed to download/parse FTD file for %04d-%02d%s, skipping",
                year,
                month,
                half,
                exc_info=True,
            )
            continue

        for row in rows:
            record = _row_to_short_data(row)
            if record is None:
                continue
            if symbol is not None and record.symbol.upper() != symbol.upper():
                continue
            if start_date is not None and record.date < start_date:
                continue
            if end_date is not None and record.date > end_date:
                continue
            results.append(record)

    results.sort(key=lambda r: r.date)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _date_range_to_file_keys(
    start_date: date | None,
    end_date: date | None,
) -> list[tuple[int, int, str]]:
    """Determine which SEC FTD half-month files to download.

    Returns a list of (year, month, half_letter) tuples.
    half_letter is 'a' for days 1-15 and 'b' for days 16-end.
    """
    if start_date is None and end_date is None:
        today = date.today()
        return [(today.year, today.month, "a"), (today.year, today.month, "b")]

    if start_date is None:
        start_date = date(end_date.year, end_date.month, 1)
    if end_date is None:
        end_date = start_date

    keys: list[tuple[int, int, str]] = []
    current = date(start_date.year, start_date.month, 1)
    end_boundary = date(end_date.year, end_date.month, 1)

    while current <= end_boundary:
        y, m = current.year, current.month

        # Determine if we need the 'a' half (days 1-15)
        need_a = True
        if (y, m) == (start_date.year, start_date.month) and start_date.day > 15:
            need_a = False

        # Determine if we need the 'b' half (days 16+)
        need_b = True
        if (y, m) == (end_date.year, end_date.month) and end_date.day <= 15:
            need_b = False

        if need_a:
            keys.append((y, m, "a"))
        if need_b:
            keys.append((y, m, "b"))

        # Advance to next month
        if m == 12:
            current = date(y + 1, 1, 1)
        else:
            current = date(y, m + 1, 1)

    return keys


def _build_url(year: int, month: int, half: str) -> str:
    """Build the download URL for a specific FTD half-month file."""
    filename = f"cnsfails{year:04d}{month:02d}{half}.zip"
    return f"{SEC_BASE_URL}/{filename}"


def _download_and_parse(year: int, month: int, half: str) -> list[dict[str, str]]:
    """Download a single FTD zip file and parse its pipe-delimited contents."""
    url = _build_url(year, month, half)
    logger.debug("Downloading FTD file: %s", url)

    session = requests.Session()
    session.headers.update({"User-Agent": SEC_USER_AGENT})

    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    if resp.status_code == 404:
        logger.debug("FTD file not found (404): %s", url)
        return []
    if resp.status_code != 200:
        raise RuntimeError(
            f"SEC FTD download failed (HTTP {resp.status_code}) for {url}"
        )

    return _parse_zip_content(resp.content)


def _parse_zip_content(zip_bytes: bytes) -> list[dict[str, str]]:
    """Extract and parse the pipe-delimited file inside a FTD zip archive."""
    rows: list[dict[str, str]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                with zf.open(name) as f:
                    raw = f.read()
                    # SEC files may use different encodings
                    for encoding in ("utf-8", "latin-1"):
                        try:
                            text = raw.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        text = raw.decode("utf-8", errors="replace")

                    rows.extend(_parse_pipe_delimited(text))
    except zipfile.BadZipFile:
        logger.warning("Bad zip file received from SEC, skipping")
        return []

    return rows


def _parse_pipe_delimited(text: str) -> Iterator[dict[str, str]]:
    """Parse pipe-delimited FTD text data into row dicts."""
    reader = csv.reader(io.StringIO(text), delimiter="|")
    header: list[str] | None = None

    for line_num, fields in enumerate(reader):
        if header is None:
            # Normalize header names
            header = [f.strip().upper() for f in fields]
            continue

        if len(fields) != len(header):
            logger.debug("Skipping malformed row %d: wrong number of fields", line_num)
            continue

        row = dict(zip(header, [f.strip() for f in fields]))
        yield row


def _row_to_short_data(row: dict[str, str]) -> ShortData | None:
    """Convert a parsed FTD row dict to a ShortData object.

    Returns None if the row is malformed or has missing required data.
    """
    try:
        # Parse settlement date (YYYYMMDD format)
        raw_date = row.get("SETTLEMENT DATE", "").strip()
        if not raw_date or len(raw_date) < 8:
            return None
        settlement_date = date(
            int(raw_date[:4]),
            int(raw_date[4:6]),
            int(raw_date[6:8]),
        )

        # Parse symbol
        symbol = row.get("SYMBOL", "").strip()
        if not symbol:
            return None

        # Parse quantity (fails)
        raw_qty = row.get("QUANTITY (FAILS)", "").strip()
        if not raw_qty:
            return None
        quantity = float(raw_qty)

        # Parse price (optional, used for total_for_ratio context)
        raw_price = row.get("PRICE", "").strip()
        price: float | None = None
        if raw_price:
            try:
                price = float(raw_price)
                if price <= 0:
                    price = None
            except (ValueError, TypeError):
                price = None

        return ShortData(
            symbol=symbol,
            date=settlement_date,
            data_type="ftd",
            value=quantity,
            total_for_ratio=price,
            source="SEC",
        )

    except (ValueError, TypeError, KeyError) as exc:
        logger.debug("Skipping malformed row: %s | error: %s", row, exc)
        return None
