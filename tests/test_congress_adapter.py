"""Tests for the congressional stock-trading adapter.

Tests use mocked HTTP responses (no real network calls).  Validates
normalisation, date filtering, pagination, and graceful error handling.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import requests

from agora.adapters.congress_adapter import (
    _estimate_amount,
    _normalize_action,
    _normalize_trades,
    _parse_date,
    fetch_congress_trades,
)
from agora.schemas import Transaction


# -----------------------------------------------------------------------
# Fake API response builders
# -----------------------------------------------------------------------


def _make_api_response(trades: list, total: int | None = None) -> dict:
    """Build a fake Capitol Trades API JSON response."""
    if total is None:
        total = len(trades)
    return {
        "data": trades,
        "meta": {
            "paging": {
                "totalItems": total,
                "pageSize": 100,
                "currentPage": 1,
            }
        },
    }


def _make_trade(
    *,
    first="Pelosi",
    last="Nancy",
    party="Democrat",
    state="CA",
    chamber="house",
    committees=None,
    tx_date="2024-03-18T00:00:00",
    tx_type="buy",
    amount="$1,001 - $15,000",
    ticker="AAPL",
    asset_name="Apple Inc",
) -> dict:
    """Build a single fake trade dict mirroring Capitol Trades shape."""
    trade: dict = {
        "txDate": tx_date,
        "txType": tx_type,
        "amount": amount,
        "ticker": ticker,
        "assetName": asset_name,
        "politician": {
            "firstName": first,
            "lastName": last,
            "party": party,
            "state": state,
            "chamber": chamber,
        },
    }
    if committees is not None:
        trade["politician"]["committees"] = committees
    return trade


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    if status_code >= 400:
        mock.raise_for_status.side_effect = requests.HTTPError()
    else:
        mock.raise_for_status.return_value = None
    return mock


# -----------------------------------------------------------------------
# Unit tests: helper functions
# -----------------------------------------------------------------------


class TestParseDate:
    def test_iso_date(self):
        assert _parse_date("2024-03-18") == date(2024, 3, 18)

    def test_iso_datetime(self):
        assert _parse_date("2024-03-18T00:00:00") == date(2024, 3, 18)

    def test_none(self):
        assert _parse_date(None) is None

    def test_empty_string(self):
        assert _parse_date("") is None

    def test_invalid(self):
        assert _parse_date("not-a-date") is None


class TestEstimateAmount:
    def test_known_range(self):
        assert _estimate_amount("$1,001 - $15,000") == 8_000.0

    def test_large_range(self):
        assert _estimate_amount("$1,000,001 - $5,000,000") == 3_000_000.0

    def test_over50m(self):
        assert _estimate_amount("Over $50,000,000") == 50_000_000.0

    def test_none(self):
        assert _estimate_amount(None) == 0.0

    def test_unknown_range(self):
        assert _estimate_amount("$999 - $1,000") == 0.0


class TestNormalizeAction:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("buy", "Buy"),
            ("Buy", "Buy"),
            ("purchase", "Buy"),
            ("sell", "Sell"),
            ("Sell", "Sell"),
            ("sale", "Sell"),
            ("sale (full)", "Sell"),
            ("sale (partial)", "Sell"),
            ("exchange", "Exchange"),
        ],
    )
    def test_action_mapping(self, raw, expected):
        assert _normalize_action(raw) == expected

    def test_none(self):
        assert _normalize_action(None) == "Unknown"


# -----------------------------------------------------------------------
# Unit tests: normalisation
# -----------------------------------------------------------------------


class TestNormalizeTrades:
    def test_single_trade(self):
        raw = [_make_trade()]
        result = _normalize_trades(raw)
        assert len(result) == 1
        txn = result[0]
        assert isinstance(txn, Transaction)
        assert txn.date == date(2024, 3, 18)
        assert txn.entity == "Pelosi Nancy"
        assert txn.action == "Buy"
        assert txn.amount == 8_000.0
        assert txn.context["party"] == "Democrat"
        assert txn.context["state"] == "CA"
        assert txn.context["chamber"] == "house"
        assert txn.context["symbol"] == "AAPL"
        assert txn.context["asset_name"] == "Apple Inc"
        assert txn.context["disclosed_range"] == "$1,001 - $15,000"

    def test_sell_trade(self):
        raw = [_make_trade(tx_type="sale (full)")]
        result = _normalize_trades(raw)
        assert result[0].action == "Sell"

    def test_missing_date_skipped(self):
        raw = [_make_trade(tx_date=None)]
        result = _normalize_trades(raw)
        assert len(result) == 0

    def test_invalid_date_skipped(self):
        raw = [_make_trade(tx_date="not-a-date")]
        result = _normalize_trades(raw)
        assert len(result) == 0

    def test_date_filtering(self):
        raw = [
            _make_trade(tx_date="2024-01-10"),
            _make_trade(tx_date="2024-03-18"),
            _make_trade(tx_date="2024-06-20"),
        ]
        result = _normalize_trades(
            raw,
            start_date=date(2024, 2, 1),
            end_date=date(2024, 5, 1),
        )
        assert len(result) == 1
        assert result[0].date == date(2024, 3, 18)

    def test_missing_politician(self):
        """Trade with no politician data gets entity='Unknown'."""
        raw = [{"txDate": "2024-03-18", "txType": "buy", "amount": None}]
        result = _normalize_trades(raw)
        assert len(result) == 1
        assert result[0].entity == "Unknown"

    def test_committees_in_context(self):
        raw = [_make_trade(committees=["Finance", "Armed Services"])]
        result = _normalize_trades(raw)
        assert result[0].context["committee"] == ["Finance", "Armed Services"]


# -----------------------------------------------------------------------
# Integration tests: fetch_congress_trades (mocked HTTP)
# -----------------------------------------------------------------------


class TestFetchCongressTrades:
    @patch("requests.get")
    def test_basic_fetch(self, mock_get):
        """Single-page response with one trade."""
        trades = [_make_trade()]
        mock_get.return_value = _mock_response(_make_api_response(trades))

        result = fetch_congress_trades(symbol="AAPL")
        assert len(result) == 1
        assert result[0].entity == "Pelosi Nancy"
        assert result[0].action == "Buy"
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_pagination(self, mock_get):
        """Two-page response triggers a second HTTP call."""
        page1_trades = [_make_trade(tx_date="2024-01-01")]
        page2_trades = [_make_trade(tx_date="2024-02-01")]

        resp1 = _mock_response(_make_api_response(page1_trades, total=2))
        resp2 = _mock_response(_make_api_response(page2_trades, total=2))
        mock_get.side_effect = [resp1, resp2]

        result = fetch_congress_trades()
        assert len(result) == 2
        assert mock_get.call_count == 2
        # Should be sorted chronologically
        assert result[0].date < result[1].date

    @patch("requests.get")
    def test_api_error_returns_empty(self, mock_get):
        """HTTP errors return empty list instead of raising."""
        mock_get.side_effect = requests.ConnectionError("Connection refused")
        result = fetch_congress_trades(symbol="AAPL")
        assert result == []

    @patch("requests.get")
    def test_http_500_returns_empty(self, mock_get):
        """5xx server errors degrade gracefully."""
        mock_get.return_value = _mock_response({}, status_code=500)
        result = fetch_congress_trades()
        assert result == []

    @patch("requests.get")
    def test_date_filters_passed_to_params(self, mock_get):
        """Start/end dates are forwarded as query parameters."""
        mock_get.return_value = _mock_response(_make_api_response([]))

        fetch_congress_trades(
            symbol="MSFT",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        _, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert params["ticker"] == "MSFT"
        assert params["txDate.gte"] == "2024-01-01"
        assert params["txDate.lte"] == "2024-12-31"

    @patch("requests.get")
    def test_no_symbol_omits_ticker_param(self, mock_get):
        """When symbol is None, ticker should not be in params."""
        mock_get.return_value = _mock_response(_make_api_response([]))

        fetch_congress_trades()

        _, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert "ticker" not in params

    @patch("requests.get")
    def test_symbol_uppercased(self, mock_get):
        """Lowercase symbol is uppercased in the request."""
        mock_get.return_value = _mock_response(_make_api_response([]))

        fetch_congress_trades(symbol="aapl")

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["ticker"] == "AAPL"

    @patch("requests.get")
    def test_empty_response(self, mock_get):
        """API returning zero trades produces an empty list."""
        mock_get.return_value = _mock_response(_make_api_response([]))
        result = fetch_congress_trades(symbol="XYZ")
        assert result == []
