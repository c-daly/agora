"""Tests for the FINRA short interest adapter (mocked)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch


from agora.adapters.finra_short_interest_adapter import (
    _build_request_body,
    _parse_rows,
    fetch_short_interest,
)
from agora.schemas import ShortData


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

SAMPLE_ROWS = [
    {
        "settlementDate": "2026-01-15",
        "currentShortPositionQuantity": 15000000,
        "sharesOutstandingQuantity": 300000000,
        "symbolCode": "AAPL",
    },
    {
        "settlementDate": "2026-01-31",
        "currentShortPositionQuantity": 18000000,
        "sharesOutstandingQuantity": 300000000,
        "symbolCode": "AAPL",
    },
    {
        "settlementDate": "2026-02-15",
        "currentShortPositionQuantity": 16500000,
        "sharesOutstandingQuantity": 300000000,
        "symbolCode": "AAPL",
    },
]


# ---------------------------------------------------------------------
# Unit tests: _build_request_body
# ---------------------------------------------------------------------


def test_build_request_body_structure():
    """The request body should contain expected filters and pagination."""
    body = _build_request_body(
        "AAPL", date(2026, 1, 1), date(2026, 3, 1), limit=5000, offset=0
    )

    assert body["limit"] == 5000
    assert body["offset"] == 0

    # Date range filter
    drf = body["dateRangeFilters"]
    assert len(drf) == 1
    assert drf[0]["fieldName"] == "settlementDate"
    assert drf[0]["startDate"] == "2026-01-01"
    assert drf[0]["endDate"] == "2026-03-01"

    # Domain filter
    df = body["domainFilters"]
    assert len(df) == 1
    assert df[0]["fieldName"] == "symbolCode"
    assert df[0]["values"] == ["AAPL"]

    # Sort fields
    sf = body["sortFields"]
    assert len(sf) == 1
    assert sf[0]["fieldName"] == "settlementDate"


# ---------------------------------------------------------------------
# Unit tests: _parse_rows
# ---------------------------------------------------------------------


def test_parse_rows_basic():
    """_parse_rows should convert raw dicts to ShortData."""
    results = _parse_rows("AAPL", SAMPLE_ROWS)

    assert len(results) == 3
    for r in results:
        assert isinstance(r, ShortData)
        assert r.symbol == "AAPL"
        assert r.data_type == "short_interest"
        assert r.source == "FINRA"


def test_parse_rows_values():
    """Parsed values should match raw data."""
    results = _parse_rows("AAPL", SAMPLE_ROWS)

    assert results[0].date == date(2026, 1, 15)
    assert results[0].value == 15_000_000.0
    assert results[0].total_for_ratio == 300_000_000.0

    assert results[1].date == date(2026, 1, 31)
    assert results[1].value == 18_000_000.0


def test_parse_rows_missing_shares_outstanding():
    """Rows without sharesOutstandingQuantity should have None total_for_ratio."""
    rows = [
        {
            "settlementDate": "2026-03-15",
            "currentShortPositionQuantity": 5000000,
            "symbolCode": "GME",
        },
    ]
    results = _parse_rows("GME", rows)

    assert len(results) == 1
    assert results[0].value == 5_000_000.0
    assert results[0].total_for_ratio is None


def test_parse_rows_null_shares_outstanding():
    """Rows with null sharesOutstandingQuantity should have None total_for_ratio."""
    rows = [
        {
            "settlementDate": "2026-03-15",
            "currentShortPositionQuantity": 5000000,
            "sharesOutstandingQuantity": None,
            "symbolCode": "GME",
        },
    ]
    results = _parse_rows("GME", rows)

    assert len(results) == 1
    assert results[0].total_for_ratio is None


def test_parse_rows_skips_malformed():
    """Malformed rows should be skipped without raising."""
    rows = [
        {"bad": "data"},  # missing required keys
        {"settlementDate": "not-a-date", "currentShortPositionQuantity": 100},
        SAMPLE_ROWS[0],  # valid
    ]
    results = _parse_rows("AAPL", rows)

    assert len(results) == 1
    assert results[0].date == date(2026, 1, 15)


def test_parse_rows_empty():
    """Empty input should return empty list."""
    assert _parse_rows("AAPL", []) == []


# ---------------------------------------------------------------------
# Integration tests: fetch_short_interest (mocked HTTP)
# ---------------------------------------------------------------------


@patch("agora.adapters.finra_short_interest_adapter.requests.post")
def test_fetch_short_interest_basic(mock_post: MagicMock):
    """fetch_short_interest returns sorted ShortData from mocked API."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_ROWS
    mock_post.return_value = mock_resp

    results = fetch_short_interest(
        "aapl",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 1),
    )

    assert len(results) == 3
    # Should be chronologically sorted
    assert results[0].date < results[1].date < results[2].date
    # Symbol should be uppercased
    assert all(r.symbol == "AAPL" for r in results)
    # Correct data_type and source
    assert all(r.data_type == "short_interest" for r in results)
    assert all(r.source == "FINRA" for r in results)


@patch("agora.adapters.finra_short_interest_adapter.requests.post")
def test_fetch_short_interest_empty_204(mock_post: MagicMock):
    """HTTP 204 (no content) should return an empty list."""
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_post.return_value = mock_resp

    results = fetch_short_interest(
        "AAPL",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 1),
    )

    assert results == []


@patch("agora.adapters.finra_short_interest_adapter.requests.post")
def test_fetch_short_interest_api_error_returns_empty(mock_post: MagicMock):
    """API errors should be caught and return an empty list."""
    mock_post.side_effect = Exception("Connection error")

    results = fetch_short_interest(
        "AAPL",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 1),
    )

    assert results == []


@patch("agora.adapters.finra_short_interest_adapter.requests.post")
def test_fetch_short_interest_default_dates(mock_post: MagicMock):
    """When no dates provided, defaults should be applied."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    mock_post.return_value = mock_resp

    fetch_short_interest("AAPL")

    # Should have been called at least once
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    body = call_kwargs.kwargs["json"]
    # Verify date range filter exists
    assert len(body["dateRangeFilters"]) == 1


@patch("agora.adapters.finra_short_interest_adapter.requests.post")
def test_fetch_short_interest_pagination(mock_post: MagicMock):
    """When first page is full, a second page should be fetched."""
    # First page: exactly 5000 rows (triggers pagination)
    page_1 = [
        {
            "settlementDate": f"2026-01-{i:14}",
            "currentShortPositionQuantity": 1000 + i,
            "symbolCode": "AAPL",
        }
        for i in range(5000)
    ]
    # Second page: 2 rows (ends pagination)
    page_2 = [
        {
            "settlementDate": "2026-02-15",
            "currentShortPositionQuantity": 9999,
            "symbolCode": "AAPL",
        },
        {
            "settlementDate": "2026-02-28",
            "currentShortPositionQuantity": 8888,
            "symbolCode": "AAPL",
        },
    ]

    mock_resp_1 = MagicMock()
    mock_resp_1.status_code = 200
    mock_resp_1.json.return_value = page_1

    mock_resp_2 = MagicMock()
    mock_resp_2.status_code = 200
    mock_resp_2.json.return_value = page_2

    mock_post.side_effect = [mock_resp_1, mock_resp_2]

    results = fetch_short_interest(
        "AAPL",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 1),
   )

    assert mock_post.call_count == 2
    # Total results should be from both pages
    # (page_1 dates are mostly invalid but some may parse, plus 2 from page_2)
    assert len(results) >= 2


@patch("agora.adapters.finra_short_interest_adapter.requests.post")
def test_fetch_short_interest_non_list_response(mock_post: MagicMock):
    """Non-list JSON response should return empty."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"error": "something"}
    mock_post.return_value = mock_resp

    results = fetch_short_interest(
        "AAPL",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 1),
    )

    assert results == []
