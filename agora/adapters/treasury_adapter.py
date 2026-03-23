"""Treasury.gov yield curve adapter for Agora.

Fetches daily Treasury yield curve rates from the Treasury.gov CSV endpoint.
No API key required.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime

import requests

from agora.schemas import TimeSeries, TimeSeriesMetadata

# ---------------------------------------------------------------------------
# Column name in CSV -> our maturity label
# ---------------------------------------------------------------------------
_CSV_COL_TO_MATURITY: dict[str, str] = {
    "1 Mo": "1mo",
    "2 Mo": "2mo",
    "3 Mo": "3mo",
    "4 Mo": "4mo",
    "6 Mo": "6mo",
    "1 Yr": "1yr",
    "2 Yr": "2yr",
    "3 Yr": "3yr",
    "5 Yr": "5yr",
    "7 Yr": "7yr",
    "10 Yr": "10yr",
    "20 Yr": "20yr",
    "30 Yr": "30yr",
}

_MATURITY_TO_CSV_COL: dict[str, str] = {v: k for k, v in _CSV_COL_TO_MATURITY.items()}

_ALL_MATURITIES: list[str] = list(_MATURITY_TO_CSV_COL.keys())

_BASE_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/"
    "interest-rates/daily-treasury-rates.csv/{year}/all"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_yields(
    *,
    maturities: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[TimeSeries]:
    """Fetch daily Treasury yield curve rates.

    Parameters
    ----------
    maturities:
        List of maturity labels to fetch (e.g. ``["2yr", "10yr"]``).
        ``None`` fetches all available maturities.
    start_date:
        Earliest date to include (inclusive).
    end_date:
        Latest date to include (inclusive).

    Returns
    -------
    list[TimeSeries]
        One entry per (date, maturity) pair, in chronological order.
        Missing data points are silently skipped.
    """
    # Validate impossible date range early
    if start_date is not None and end_date is not None and start_date > end_date:
        return []

    # Resolve which maturities to fetch
    requested = _resolve_maturities(maturities)
    if not requested:
        return []

    # Determine which years we need to fetch
    years = _years_to_fetch(start_date, end_date)

    # Fetch and parse CSV data for each year
    results: list[TimeSeries] = []
    for year in years:
        rows = _fetch_csv_for_year(year)
        for row_date, col_values in rows:
            # Apply date filters
            if start_date is not None and row_date < start_date:
                continue
            if end_date is not None and row_date > end_date:
                continue

            for maturity in requested:
                csv_col = _MATURITY_TO_CSV_COL[maturity]
                raw_value = col_values.get(csv_col)
                if raw_value is None or raw_value.strip() == "" or raw_value.strip() == "N/A":
                    continue
                try:
                    value = float(raw_value)
                except (ValueError, TypeError):
                    continue

                results.append(
                    TimeSeries(
                        date=row_date,
                        value=value,
                        metadata=TimeSeriesMetadata(
                            source="TREASURY",
                            unit=maturity,
                            frequency="Daily",
                        ),
                    )
                )

    # Sort chronologically
    results.sort(key=lambda ts: ts.date)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_maturities(maturities: list[str] | None) -> list[str]:
    """Validate and return the list of maturity labels to fetch."""
    if maturities is None:
        return list(_ALL_MATURITIES)

    valid: list[str] = []
    for m in maturities:
        if m in _MATURITY_TO_CSV_COL:
            valid.append(m)
        else:
            raise ValueError(
                f"Unknown maturity label '{m}'. "
                f"Valid labels: {', '.join(_ALL_MATURITIES)}"
            )
    return valid


def _years_to_fetch(
    start_date: date | None,
    end_date: date | None,
) -> list[int]:
    """Return the list of calendar years we need CSV data for."""
    today = date.today()

    if start_date is not None and end_date is not None:
        return list(range(start_date.year, end_date.year + 1))

    if start_date is not None:
        # No end_date: fetch from start year through current year
        return list(range(start_date.year, today.year + 1))

    if end_date is not None:
        # No start_date: fetch just the end_date's year
        return [end_date.year]

    # Neither specified: fetch current year
    return [today.year]


def _fetch_csv_for_year(year: int) -> list[tuple[date, dict[str, str]]]:
    """Fetch the Treasury yield curve CSV for a given year.

    Returns a list of ``(date, {column_name: value_str})`` tuples.
    """
    url = _BASE_URL.format(year=year)
    params = {
        "type": "daily_treasury_yield_curve",
        "field_tdr_date_value": str(year),
        "page": "",
        "_format": "csv",
    }

    try:
        resp = requests.get(
            url,
            params=params,
            headers={"User-Agent": "agora/treasury-adapter", "Accept": "text/csv"},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Failed to connect to Treasury.gov for year {year}: {exc}"
        ) from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"Treasury.gov returned HTTP {resp.status_code} for year {year}"
        )

    text = resp.text
    if not text.strip():
        return []

    reader = csv.DictReader(io.StringIO(text))
    rows: list[tuple[date, dict[str, str]]] = []

    for record in reader:
        raw_date = record.get("Date", "").strip()
        if not raw_date:
            continue
        try:
            row_date = datetime.strptime(raw_date, "%m/%d/%Y").date()
        except ValueError:
            continue
        rows.append((row_date, record))

    return rows
