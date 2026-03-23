"""Tests for the Yahoo Finance short-interest adapter.

All tests mock yfinance so they run offline and deterministically.
"""

from __future__ import annotations

import math
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from agora.adapters.yahoo_short_adapter import fetch_short_interest
from agora.schemas import ShortData

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

# Realistic info dict returned by yfinance for AAPL
_AAPL_INFO: dict = {
    "shortInterest": 120_000_000,
    "shortRatio": 1.5,
    "shortPercentOfFloat": 0.008,
    "sharesShort": 120_000_000,
    "sharesShortPriorMonth": 115_000_000,
    "dateShortInterest": 1_700_006_400,  # 2023-11-15 00:00:00 UTC
    "floatShares": 15_000_000_000,
    "sharesOutstanding": 15_500_000_000,
}


def _mock_ticker(info: dict | None = None) -> MagicMock:
    """Return a MagicMock that behaves like yfinance.Ticker."""
    mock = MagicMock()
    mock.info = info if info is not None else {}
    return mock


@pytest.fixture()
def aapl_results() -> list[ShortData]:
    """Fetch short interest for AAPL with mocked yfinance."""
    with patch(
        "agora.adapters.yahoo_short_adapter.yf", create=True
    ) as mock_yf:
        mock_yf.Ticker.return_value = _mock_ticker(_AAPL_INFO)
        # Need to also patch the lazy import inside the function
        with patch.dict(
            "sys.modules", {"yfinance": mock_yf}
        ):
            return fetch_short_interest("AAPL")


# ---------------------------------------------------------------------------
# 1. Returns list of ShortData objects
# ---------------------------------------------------------------------------


class TestReturnType:
    def test_returns_list(self, aapl_results: list[ShortData]):
        assert isinstance(aapl_results, list)

    def test_elements_are_short_data(self, aapl_results: list[ShortData]):
        for item in aapl_results:
            assert isinstance(item, ShortData), f"Expected ShortData, got {type(item)}"

    def test_expected_count(self, aapl_results: list[ShortData]):
        """With all 5 metrics present we expect 5 ShortData entries."""
        assert len(aapl_results) == 5


# ---------------------------------------------------------------------------
# 2. ShortData fields populated correctly
# ---------------------------------------------------------------------------


class TestFieldValues:
    def test_source_is_yahoo_finance(self, aapl_results: list[ShortData]):
        for item in aapl_results:
            assert item.source == "Yahoo Finance"

    def test_symbol_matches(self, aapl_results: list[ShortData]):
        for item in aapl_results:
            assert item.symbol == "AAPL"

    def test_data_types_present(self, aapl_results: list[ShortData]):
        data_types = {item.data_type for item in aapl_results}
        expected = {
            "short_interest",
            "short_ratio",
            "short_percent_of_float",
            "shares_short",
            "shares_short_prior_month",
        }
        assert data_types == expected

    def test_date_parsed_from_epoch(self, aapl_results: list[ShortData]):
        """dateShortInterest=1700006400 -> 2023-11-15."""
        for item in aapl_results:
            assert item.date == date(2023, 11, 15)


# ---------------------------------------------------------------------------
# 3. Values are valid
# ---------------------------------------------------------------------------


class TestValueValidity:
    def test_values_finite(self, aapl_results: list[ShortData]):
        for item in aapl_results:
            assert math.isfinite(item.value), f"Non-finite value: {item.value}"

    def test_total_for_ratio_where_expected(self, aapl_results: list[ShortData]):
        """shares_short and shares_short_prior_month should have total_for_ratio."""
        by_type = {item.data_type: item for item in aapl_results}
        assert by_type["shares_short"].total_for_ratio == 15_500_000_000
        assert by_type["shares_short_prior_month"].total_for_ratio == 15_500_000_000
        assert by_type["short_percent_of_float"].total_for_ratio == 15_000_000_000

    def test_short_interest_no_total_for_ratio(self, aapl_results: list[ShortData]):
        by_type = {item.data_type: item for item in aapl_results}
        assert by_type["short_interest"].total_for_ratio is None
        assert by_type["short_ratio"].total_for_ratio is None


# ---------------------------------------------------------------------------
# 4. Graceful handling of missing data
# ---------------------------------------------------------------------------


class TestGracefulHandling:
    def test_empty_info_returns_empty(self):
        """Ticker with no info returns empty list."""
        with patch.dict("sys.modules", {"yfinance": MagicMock()}) as _:
            import sys

            mock_yf = sys.modules["yfinance"]
            mock_yf.Ticker.return_value = _mock_ticker({})
            result = fetch_short_interest("ZZZNOTREAL")
        assert result == []

    def test_none_info_returns_empty(self):
        """Ticker whose .info is None returns empty list."""
        with patch.dict("sys.modules", {"yfinance": MagicMock()}) as _:
            import sys

            mock_yf = sys.modules["yfinance"]
            mock_ticker = MagicMock()
            mock_ticker.info = None
            mock_yf.Ticker.return_value = mock_ticker
            result = fetch_short_interest("ZZZNOTREAL")
        assert result == []

    def test_partial_metrics(self):
        """If only some metrics are present, only those are returned."""
        partial_info = {
            "shortInterest": 5_000_000,
            "dateShortInterest": 1_700_006_400,
        }
        with patch.dict("sys.modules", {"yfinance": MagicMock()}) as _:
            import sys

            mock_yf = sys.modules["yfinance"]
            mock_yf.Ticker.return_value = _mock_ticker(partial_info)
            result = fetch_short_interest("GME")
        assert len(result) == 1
        assert result[0].data_type == "short_interest"
        assert result[0].value == 5_000_000

    def test_exception_in_ticker_returns_empty(self):
        """If yfinance raises, we get an empty list, not an exception."""
        with patch.dict("sys.modules", {"yfinance": MagicMock()}) as _:
            import sys

            mock_yf = sys.modules["yfinance"]
            mock_yf.Ticker.side_effect = RuntimeError("network error")
            result = fetch_short_interest("AAPL")
        assert result == []


# ---------------------------------------------------------------------------
# 5. Symbol is uppercased
# ---------------------------------------------------------------------------


class TestSymbolNormalization:
    def test_lowercase_symbol_uppercased(self):
        with patch.dict("sys.modules", {"yfinance": MagicMock()}) as _:
            import sys

            mock_yf = sys.modules["yfinance"]
            mock_yf.Ticker.return_value = _mock_ticker(_AAPL_INFO)
            result = fetch_short_interest("aapl")
        for item in result:
            assert item.symbol == "AAPL"


# ---------------------------------------------------------------------------
# 6. Date fallback when dateShortInterest is absent
# ---------------------------------------------------------------------------


class TestDateFallback:
    def test_missing_date_uses_today(self):
        info_no_date = {"shortInterest": 100_000}
        with patch.dict("sys.modules", {"yfinance": MagicMock()}) as _:
            import sys

            mock_yf = sys.modules["yfinance"]
            mock_yf.Ticker.return_value = _mock_ticker(info_no_date)
            result = fetch_short_interest("TEST")
        assert len(result) == 1
        assert result[0].date == date.today()

    def test_invalid_date_epoch_uses_today(self):
        info_bad_date = {
            "shortInterest": 100_000,
            "dateShortInterest": "not_a_number",
        }
        with patch.dict("sys.modules", {"yfinance": MagicMock()}) as _:
            import sys

            mock_yf = sys.modules["yfinance"]
            mock_yf.Ticker.return_value = _mock_ticker(info_bad_date)
            result = fetch_short_interest("TEST")
        assert len(result) == 1
        assert result[0].date == date.today()


# ---------------------------------------------------------------------------
# 7. Non-numeric metric values are skipped
# ---------------------------------------------------------------------------


class TestNonNumericSkipping:
    def test_non_numeric_value_skipped(self):
        info_bad_value = {
            "shortInterest": "N/A",
            "shortRatio": 2.0,
            "dateShortInterest": 1_700_006_400,
        }
        with patch.dict("sys.modules", {"yfinance": MagicMock()}) as _:
            import sys

            mock_yf = sys.modules["yfinance"]
            mock_yf.Ticker.return_value = _mock_ticker(info_bad_value)
            result = fetch_short_interest("TEST")
        assert len(result) == 1
        assert result[0].data_type == "short_ratio"
