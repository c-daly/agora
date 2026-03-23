"""Eval tests for the Yahoo Finance quotes adapter."""

import math
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agora.adapters.yahoo_quotes_adapter import fetch_quotes
from agora.schemas import Quote


def _make_mock_df(rows: list[dict], dates: list[str]) -> pd.DataFrame:
    """Build a DataFrame that mimics yfinance history() output."""
    index = pd.to_datetime(dates)
    return pd.DataFrame(rows, index=index)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_ROWS = [
    {"Open": 150.0, "High": 155.0, "Low": 149.0, "Close": 154.0, "Volume": 1000000,
     "Dividends": 0.0, "Stock Splits": 0.0},
    {"Open": 154.0, "High": 158.0, "Low": 153.0, "Close": 157.0, "Volume": 1200000,
     "Dividends": 0.0, "Stock Splits": 0.0},
    {"Open": 157.0, "High": 160.0, "Low": 156.0, "Close": 159.0, "Volume": 900000,
     "Dividends": 0.0, "Stock Splits": 0.0},
]
_SAMPLE_DATES = ["2025-01-02", "2025-01-03", "2025-01-06"]


@pytest.fixture()
def mock_history():
    """Patch yfinance.Ticker.history to return canned data."""
    df = _make_mock_df(_SAMPLE_ROWS, _SAMPLE_DATES)
    with patch("agora.adapters.yahoo_quotes_adapter.yf.Ticker") as mock_cls:
        instance = MagicMock()
        instance.history.return_value = df
        mock_cls.return_value = instance
        yield instance


@pytest.fixture()
def mock_empty_history():
    """Patch yfinance.Ticker.history to return an empty DataFrame."""
    with patch("agora.adapters.yahoo_quotes_adapter.yf.Ticker") as mock_cls:
        instance = MagicMock()
        instance.history.return_value = pd.DataFrame()
        mock_cls.return_value = instance
        yield instance


# ---------------------------------------------------------------------------
# Schema compliance
# ---------------------------------------------------------------------------

class TestSchemaCompliance:
    """Returns correctly shaped Quote objects."""

    def test_returns_list_of_quotes(self, mock_history):
        result = fetch_quotes("AAPL")
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, Quote)

    def test_quote_fields(self, mock_history):
        result = fetch_quotes("AAPL")
        item = result[0]
        assert isinstance(item.symbol, str)
        assert isinstance(item.date, date)
        assert isinstance(item.open, float)
        assert isinstance(item.high, float)
        assert isinstance(item.low, float)
        assert isinstance(item.close, float)
        assert isinstance(item.volume, int)

    def test_symbol_is_uppercased(self, mock_history):
        result = fetch_quotes("aapl")
        for item in result:
            assert item.symbol == "AAPL"

    def test_values_are_finite(self, mock_history):
        result = fetch_quotes("AAPL")
        for item in result:
            assert math.isfinite(item.open)
            assert math.isfinite(item.high)
            assert math.isfinite(item.low)
            assert math.isfinite(item.close)
            assert math.isfinite(item.volume)

    def test_results_in_chronological_order(self, mock_history):
        result = fetch_quotes("AAPL")
        dates = [item.date for item in result]
        assert dates == sorted(dates)

    def test_expected_values(self, mock_history):
        result = fetch_quotes("AAPL")
        assert len(result) == 3
        assert result[0].open == 150.0
        assert result[0].close == 154.0
        assert result[0].volume == 1000000
        assert result[0].date == date(2025, 1, 2)


# ---------------------------------------------------------------------------
# Date filtering
# ---------------------------------------------------------------------------

class TestDateFiltering:
    """Date range parameters are forwarded to yfinance."""

    def test_start_date_passed(self, mock_history):
        start = date(2025, 1, 1)
        fetch_quotes("AAPL", start_date=start)
        call_kwargs = mock_history.history.call_args
        assert call_kwargs.kwargs.get("start") == "2025-01-01" or \
            call_kwargs[1].get("start") == "2025-01-01"

    def test_end_date_passed(self, mock_history):
        end = date(2025, 6, 30)
        fetch_quotes("AAPL", end_date=end)
        call_kwargs = mock_history.history.call_args
        assert call_kwargs.kwargs.get("end") == "2025-06-30" or \
            call_kwargs[1].get("end") == "2025-06-30"

    def test_default_period_when_no_dates(self, mock_history):
        fetch_quotes("AAPL")
        call_kwargs = mock_history.history.call_args
        assert "period" in (call_kwargs.kwargs or call_kwargs[1])

    def test_no_period_when_dates_given(self, mock_history):
        fetch_quotes("AAPL", start_date=date(2025, 1, 1), end_date=date(2025, 6, 30))
        call_kwargs = mock_history.history.call_args
        combined = {**call_kwargs.kwargs, **(call_kwargs[1] if call_kwargs[1] else {})}
        assert "period" not in combined


# ---------------------------------------------------------------------------
# Empty / missing data
# ---------------------------------------------------------------------------

class TestEmptyData:
    """Graceful handling of empty results."""

    def test_empty_dataframe_returns_empty_list(self, mock_empty_history):
        result = fetch_quotes("AAPL")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_none_dataframe_returns_empty_list(self):
        with patch("agora.adapters.yahoo_quotes_adapter.yf.Ticker") as mock_cls:
            instance = MagicMock()
            instance.history.return_value = None
            mock_cls.return_value = instance
            result = fetch_quotes("AAPL")
            assert isinstance(result, list)
            assert len(result) == 0


# ---------------------------------------------------------------------------
# Integration smoke test (hits real Yahoo Finance)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIntegration:
    """Live integration tests -- skipped by default (use -m integration)."""

    def test_real_fetch(self):
        result = fetch_quotes("AAPL", start_date=date(2025, 1, 2), end_date=date(2025, 1, 10))
        assert len(result) > 0
        for item in result:
            assert isinstance(item, Quote)
            assert item.symbol == "AAPL"
            assert item.open > 0
            assert item.volume >= 0
