"""Tests for the threshold_list_adapter module."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch


from agora.adapters.threshold_list_adapter import (
    _aggregate_entries,
    _parse_nasdaq_text,
    fetch_threshold_list,
)
from agora.schemas import ShortData

QUERY_DATE = date(2026, 3, 20)


# ---------------------------------------------------------------------------
# Unit tests: _parse_nasdaq_text
# ---------------------------------------------------------------------------


class TestParseNasdaqText:
    """Tests for _parse_nasdaq_text."""

    def test_parses_valid_pipe_delimited(self):
        text = (
            "Symbol|Security Name|Market|Reg SHO Threshold Flag\n"
            "AAPL|Apple Inc|Q|Y\n"
            "GME|GameStop Corp|N|Y\n"
        )
        result = _parse_nasdaq_text(text)
        assert len(result) == 2
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["exchange"] == "NASDAQ"
        assert result[1]["symbol"] == "GME"

    def test_skips_trailer_line(self):
        text = (
            "Symbol|Security Name|Market\n"
            "AAPL|Apple Inc|Q\n"
            "File Creation Time: 1234\n"
        )
        result = _parse_nasdaq_text(text)
        assert len(result) == 1
        assert result[0]["symbol"] == "AAPL"

    def test_empty_text(self):
        assert _parse_nasdaq_text("") == []

    def test_header_only(self):
        text = "Symbol|Security Name|Market\n"
        assert _parse_nasdaq_text(text) == []


# ---------------------------------------------------------------------------
# Unit tests: _aggregate_entries
# ---------------------------------------------------------------------------


class TestAggregateEntries:
    """Tests for _aggregate_entries."""

    def test_single_exchange(self):
        entries = [{"symbol": "GME", "exchange": "NYSE"}]
        result = _aggregate_entries(entries, QUERY_DATE)
        assert len(result) == 1
        assert result[0].symbol == "GME"
        assert result[0].value == 1.0
        assert result[0].total_for_ratio == 3.0
        assert result[0].data_type == "threshold"
        assert result[0].source == "RegSHO"

    def test_multiple_exchanges_same_symbol(self):
        entries = [
            {"symbol": "GME", "exchange": "NYSE"},
            {"symbol": "GME", "exchange": "NASDAQ"},
            {"symbol": "GME", "exchange": "CBOE"},
        ]
        result = _aggregate_entries(entries, QUERY_DATE)
        assert len(result) == 1
        assert result[0].value == 3.0

    def test_duplicate_exchange_not_double_counted(self):
        entries = [
            {"symbol": "GME", "exchange": "NYSE"},
            {"symbol": "GME", "exchange": "NYSE"},
        ]
        result = _aggregate_entries(entries, QUERY_DATE)
        assert len(result) == 1
        assert result[0].value == 1.0

    def test_multiple_symbols(self):
        entries = [
            {"symbol": "GME", "exchange": "NYSE"},
            {"symbol": "AMC", "exchange": "NASDAQ"},
            {"symbol": "GME", "exchange": "NASDAQ"},
        ]
        result = _aggregate_entries(entries, QUERY_DATE)
        assert len(result) == 2
        by_sym = {r.symbol: r for r in result}
        assert by_sym["GME"].value == 2.0
        assert by_sym["AMC"].value == 1.0

    def test_empty_entries(self):
        assert _aggregate_entries([], QUERY_DATE) == []

    def test_output_is_short_data(self):
        entries = [{"symbol": "AAPL", "exchange": "CBOE"}]
        result = _aggregate_entries(entries, QUERY_DATE)
        assert len(result) == 1
        record = result[0]
        assert isinstance(record, ShortData)
        assert record.date == QUERY_DATE
        assert record.data_type == "threshold"
        assert record.source == "RegSHO"


# ---------------------------------------------------------------------------
# Integration tests: fetch_threshold_list (mocked HTTP)
# ---------------------------------------------------------------------------


def _make_response(status_code, json_data=None, text=None):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    if text is not None:
        resp.text = text
    return resp


class TestFetchThresholdList:
    """Integration tests for fetch_threshold_list with mocked HTTP."""

    @patch("agora.adapters.threshold_list_adapter.requests.get")
    def test_all_exchanges_return_data(self, mock_get):
        """All three exchanges return the same symbol."""
        nyse_resp = _make_response(200, json_data=[{"symbol": "GME"}])
        nasdaq_resp = _make_response(
            200,
            text="Symbol|Name|Market\nGME|GameStop|Q\n",
        )
        cboe_resp = _make_response(200, json_data=[{"symbol": "GME"}])

        mock_get.side_effect = [nyse_resp, nasdaq_resp, cboe_resp]

        result = fetch_threshold_list(date=QUERY_DATE)

        assert len(result) == 1
        assert result[0].symbol == "GME"
        assert result[0].value == 3.0
        assert result[0].data_type == "threshold"
        assert result[0].source == "RegSHO"
        assert mock_get.call_count == 3

    @patch("agora.adapters.threshold_list_adapter.requests.get")
    def test_symbol_filter(self, mock_get):
        """Only the requested symbol is returned."""
        nyse_resp = _make_response(
            200, json_data=[{"symbol": "GME"}, {"symbol": "AMC"}]
        )
        nasdaq_resp = _make_response(404)
        cboe_resp = _make_response(404)

        mock_get.side_effect = [nyse_resp, nasdaq_resp, cboe_resp]

        result = fetch_threshold_list(symbol="AMC", date=QUERY_DATE)

        assert len(result) == 1
        assert result[0].symbol == "AMC"

    @patch("agora.adapters.threshold_list_adapter.requests.get")
    def test_exchange_failure_graceful(self, mock_get):
        """If one exchange fails, others still return data."""
        nyse_resp = _make_response(200, json_data=[{"symbol": "GME"}])
        nasdaq_error = Exception("Connection timeout")
        cboe_resp = _make_response(200, json_data=[{"symbol": "GME"}])

        mock_get.side_effect = [nyse_resp, nasdaq_error, cboe_resp]

        result = fetch_threshold_list(date=QUERY_DATE)

        assert len(result) == 1
        assert result[0].symbol == "GME"
        assert result[0].value == 2.0  # Only NYSE + CBOE

    @patch("agora.adapters.threshold_list_adapter.requests.get")
    def test_all_exchanges_fail(self, mock_get):
        """If all exchanges fail, return empty list."""
        mock_get.side_effect = Exception("Network error")

        result = fetch_threshold_list(date=QUERY_DATE)

        assert result == []

    @patch("agora.adapters.threshold_list_adapter.requests.get")
    def test_all_exchanges_404(self, mock_get):
        """If all exchanges return 404, return empty list."""
        mock_get.return_value = _make_response(404)

        result = fetch_threshold_list(date=QUERY_DATE)

        assert result == []

    @patch("agora.adapters.threshold_list_adapter.requests.get")
    def test_results_sorted_by_symbol(self, mock_get):
        """Results are returned sorted alphabetically by symbol."""
        nyse_resp = _make_response(
            200, json_data=[{"symbol": "ZZZ"}, {"symbol": "AAA"}]
        )
        nasdaq_resp = _make_response(404)
        cboe_resp = _make_response(404)

        mock_get.side_effect = [nyse_resp, nasdaq_resp, cboe_resp]

        result = fetch_threshold_list(date=QUERY_DATE)

        assert len(result) == 2
        assert result[0].symbol == "AAA"
        assert result[1].symbol == "ZZZ"

    @patch("agora.adapters.threshold_list_adapter.requests.get")
    def test_symbol_filter_case_insensitive(self, mock_get):
        """Symbol filtering is case-insensitive."""
        nyse_resp = _make_response(200, json_data=[{"symbol": "GME"}])
        nasdaq_resp = _make_response(404)
        cboe_resp = _make_response(404)

        mock_get.side_effect = [nyse_resp, nasdaq_resp, cboe_resp]

        result = fetch_threshold_list(symbol="gme", date=QUERY_DATE)

        assert len(result) == 1
        assert result[0].symbol == "GME"

    @patch("agora.adapters.threshold_list_adapter.requests.get")
    def test_cboe_nested_data_format(self, mock_get):
        """CBOE may return data nested under a 'data' key."""
        nyse_resp = _make_response(404)
        nasdaq_resp = _make_response(404)
        cboe_resp = _make_response(
            200, json_data={"data": [{"Symbol": "AMC"}]}
        )

        mock_get.side_effect = [nyse_resp, nasdaq_resp, cboe_resp]

        result = fetch_threshold_list(date=QUERY_DATE)

        assert len(result) == 1
        assert result[0].symbol == "AMC"
        assert result[0].value == 1.0
