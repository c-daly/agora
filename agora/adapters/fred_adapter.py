"""FRED (Federal Reserve Economic Data) adapter for Agora."""

from __future__ import annotations

from datetime import date

import requests

from agora.schemas import TimeSeries, TimeSeriesMetadata

FRED_BASE_URL = "https://api.stlouisfed.org/fred"


def fetch_series(
    series_id: str,
    api_key: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[TimeSeries]:
    """Fetch a FRED time series by series ID.

    Returns a list of TimeSeries objects in chronological order.
    Missing observations are skipped.
    """
    metadata = _fetch_series_metadata(series_id, api_key)
    observations = _fetch_observations(series_id, api_key, start_date, end_date)

    results: list[TimeSeries] = []
    for obs in observations:
        if obs["value"] == ".":
            continue
        try:
            value = float(obs["value"])
            obs_date = date.fromisoformat(obs["date"])
        except (ValueError, TypeError):
            continue
        results.append(
            TimeSeries(
                date=obs_date,
                value=value,
                metadata=TimeSeriesMetadata(
                    source="FRED",
                    unit=metadata.get("units"),
                    frequency=metadata.get("frequency"),
                ),
            )
        )
    return results


def _fetch_series_metadata(series_id: str, api_key: str) -> dict:
    """Fetch series metadata (units, frequency) from FRED."""
    resp = requests.get(
        f"{FRED_BASE_URL}/series",
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
        },
        timeout=30,
    )
    _check_response(resp, series_id)
    data = resp.json()
    seriess = data.get("seriess", [])
    if not seriess:
        raise ValueError(f"No series found for ID '{series_id}'")
    series = seriess[0]
    return {
        "units": series.get("units"),
        "frequency": series.get("frequency"),
    }


def _fetch_observations(
    series_id: str,
    api_key: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict]:
    """Fetch observations for a FRED series."""
    params: dict = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "asc",
    }
    if start_date is not None:
        params["observation_start"] = start_date.isoformat()
    if end_date is not None:
        params["observation_end"] = end_date.isoformat()

    resp = requests.get(
        f"{FRED_BASE_URL}/series/observations",
        params=params,
        timeout=30,
    )
    _check_response(resp, series_id)
    return resp.json().get("observations", [])


def _check_response(resp: requests.Response, series_id: str) -> None:
    """Raise descriptive exceptions for FRED API errors."""
    if resp.status_code == 400:
        error_msg = ""
        try:
            error_msg = resp.json().get("error_message", "")
        except Exception:
            pass
        raise ValueError(
            f"FRED API error for series '{series_id}': {error_msg or 'bad request'}"
        )
    if resp.status_code == 403:
        raise PermissionError("Invalid or unauthorized FRED API key")
    if resp.status_code != 200:
        error_msg = ""
        try:
            error_msg = resp.json().get("error_message", "")
        except Exception:
            pass
        raise RuntimeError(
            f"FRED API request failed (HTTP {resp.status_code}) for series "
            f"'{series_id}': {error_msg or 'unexpected error'}"
        )
