"""BLS (Bureau of Labor Statistics) adapter for Agora."""

from __future__ import annotations

import os
from datetime import date

import requests

from agora.schemas import TimeSeries, TimeSeriesMetadata

BLS_BASE_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# Well-known series IDs for convenience.
SERIES_EMPLOYMENT = "CES0000000001"  # Total Nonfarm Employment
SERIES_CPI = "CUUR0000SA0"  # CPI - All Urban Consumers
SERIES_PPI = "WPUFD49104"  # PPI - Final Demand


def fetch_bls_series(
    series_id: str,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[TimeSeries]:
    """Fetch a BLS time series by series ID.

    Uses BLS API v2 (POST with JSON body).  If the BLS_API_KEY
    environment variable is set it will be included in the request for
    higher rate-limits; otherwise the request proceeds without a key.

    Returns a list of TimeSeries objects in chronological order.
    """
    payload: dict = {"seriesid": [series_id]}

    api_key = os.environ.get("BLS_API_KEY")
    if api_key:
        payload["registrationkey"] = api_key

    if start_year is not None:
        payload["startyear"] = str(start_year)
    if end_year is not None:
        payload["endyear"] = str(end_year)

    resp = requests.post(BLS_BASE_URL, json=payload, timeout=30)
    _check_response(resp, series_id)

    data = resp.json()
    if data.get("status") != "REQUEST_SUCCEEDED":
        msg = "; ".join(data.get("message", []))
        raise RuntimeError(
            f"BLS API error for series '{series_id}': {msg or 'unknown error'}"
        )

    series_list = data.get("Results", {}).get("series", [])
    if not series_list:
        raise ValueError(f"No series found for ID '{series_id}'")

    raw_data = series_list[0].get("data", [])
    return _parse_observations(raw_data)


def _parse_observations(raw_data: list[dict]) -> list[TimeSeries]:
    """Convert raw BLS observations into TimeSeries objects.

    BLS returns observations newest-first; we reverse to chronological order.
    """
    results: list[TimeSeries] = []
    for obs in raw_data:
        period = obs.get("period", "")
        year_str = obs.get("year", "")
        value_str = obs.get("value", "")

        obs_date = _period_to_date(year_str, period)
        if obs_date is None:
            continue

        try:
            value = float(value_str)
        except (ValueError, TypeError):
            continue

        frequency = _infer_frequency(period)

        results.append(
            TimeSeries(
                date=obs_date,
                value=value,
                metadata=TimeSeriesMetadata(
                    source="BLS",
                    frequency=frequency,
                ),
            )
        )

    # BLS returns newest first; reverse to chronological order.
    results.reverse()
    return results


def _period_to_date(year_str: str, period: str) -> date | None:
    """Convert a BLS year + period code to a date.

    Monthly periods are M01 through M12.  M13 is an annual average and is
    skipped.  Quarterly (Q01-Q05) and annual (A01) periods are also handled.
    """
    try:
        year = int(year_str)
    except (ValueError, TypeError):
        return None

    if period.startswith("M"):
        month_num = int(period[1:])
        if month_num < 1 or month_num > 12:
            return None  # skip M13 annual averages
        return date(year, month_num, 1)

    if period.startswith("Q"):
        quarter = int(period[1:])
        month = {1: 1, 2: 4, 3: 7, 4: 10, 5: 1}.get(quarter)
        if month is None:
            return None
        return date(year, month, 1)

    if period.startswith("A"):
        return date(year, 1, 1)

    return None


def _infer_frequency(period: str) -> str:
    """Infer human-readable frequency from a BLS period code."""
    if period.startswith("M"):
        return "Monthly"
    if period.startswith("Q"):
        return "Quarterly"
    if period.startswith("A"):
        return "Annual"
    return "Unknown"


def _check_response(resp: requests.Response, series_id: str) -> None:
    """Raise descriptive exceptions for HTTP-level BLS API errors."""
    if resp.status_code == 400:
        raise ValueError(
            f"BLS API error for series '{series_id}': bad request"
        )
    if resp.status_code == 403:
        raise PermissionError("Invalid or unauthorized BLS API key")
    if resp.status_code != 200:
        raise RuntimeError(
            f"BLS API request failed (HTTP {resp.status_code}) for series "
            f"'{series_id}': unexpected error"
        )
