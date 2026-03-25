"""Tests for agora.adapters.edgar_institutional_adapter."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch


from agora.adapters.edgar_institutional_adapter import (
    fetch_institutional_holdings,
)
from agora.schemas import Transaction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_transaction(
    d: str,
    entity: str = "Big Fund LLC",
    action: str = "Hold",
    amount: float = 1000.0,
    symbol: str = "AAPL",
) -> Transaction:
    """Create a Transaction for testing."""
    return Transaction(
        date=date.fromisoformat(d),
        entity=entity,
        action=action,
        amount=amount,
        context={"symbol": symbol, "value_usd": amount * 150.0},
    )


def _sample_transactions(symbol: str = "AAPL") -> list[Transaction]:
    """Return a small set of realistic mock transactions."""
    return [
        _make_transaction("2024-01-15", "Alpha Capital", "New", 5000.0, symbol),
        _make_transaction("2024-03-20", "Beta Advisors", "Increase", 8000.0, symbol),
        _make_transaction("2024-06-10", "Gamma Fund", "Hold", 3000.0, symbol),
        _make_transaction("2024-09-05", "Alpha Capital", "Decrease", 2000.0, symbol),
    ]


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


class TestReturnType:
    """fetch_institutional_holdings must return list[Transaction]."""

    @patch("agora.adapters.edgar_institutional_adapter._search_13f_filings", create=True)
    @patch("agora.adapters.edgar_institutional_adapter._parse_13f_filing", create=True)
    def test_returns_list_of_transactions(
        self, mock_parse, mock_search
    ) -> None:
        mock_search.return_value = [{"url": "http://example.com/filing"}]
        mock_parse.return_value = _sample_transactions()

        result = fetch_institutional_holdings("AAPL")

        assert isinstance(result, list)
        assert all(isinstance(t, Transaction) for t in result)

    @patch("agora.adapters.edgar_institutional_adapter._search_13f_filings", create=True)
    def test_empty_filings_returns_empty_list(self, mock_search) -> None:
        mock_search.return_value = []
        result = fetch_institutional_holdings("AAPL")
        assert result == []


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


class TestFieldMapping:
    """Verify Transaction fields are correctly populated."""

    @patch("agora.adapters.edgar_institutional_adapter._search_13f_filings", create=True)
    @patch("agora.adapters.edgar_institutional_adapter._parse_13f_filing", create=True)
    def test_transaction_fields(self, mock_parse, mock_search) -> None:
        txn = _make_transaction(
            "2024-03-20", "Beta Advisors", "Increase", 8000.0, "AAPL"
        )
        mock_search.return_value = [{"url": "http://example.com/filing"}]
        mock_parse.return_value = [txn]

        result = fetch_institutional_holdings("AAPL")

        assert len(result) == 1
        t = result[0]
        assert t.date == date(2024, 3, 20)
        assert t.entity == "Beta Advisors"
        assert t.action == "Increase"
        assert t.amount == 8000.0
        assert t.context["symbol"] == "AAPL"
        assert "value_usd" in t.context

    @patch("agora.adapters.edgar_institutional_adapter._search_13f_filings", create=True)
    @patch("agora.adapters.edgar_institutional_adapter._parse_13f_filing", create=True)
    def test_results_sorted_by_date(self, mock_parse, mock_search) -> None:
        """Results must come back in chronological order."""
        txns = [
            _make_transaction("2024-06-10"),
            _make_transaction("2024-01-15"),
            _make_transaction("2024-09-05"),
        ]
        mock_search.return_value = [{"url": "http://example.com/filing"}]
        mock_parse.return_value = txns

        result = fetch_institutional_holdings("AAPL")
        dates = [t.date for t in result]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """The adapter should gracefully handle parse failures."""

    @patch("agora.adapters.edgar_institutional_adapter._search_13f_filings", create=True)
    @patch("agora.adapters.edgar_institutional_adapter._parse_13f_filing", create=True)
    def test_parse_failure_skips_filing(self, mock_parse, mock_search) -> None:
        """If _parse_13f_filing raises, that filing is skipped."""
        good_txn = _make_transaction("2024-03-20", "Good Fund", "Hold", 100.0)
        mock_search.return_value = [
            {"url": "http://example.com/bad"},
            {"url": "http://example.com/good"},
        ]
        mock_parse.side_effect = [
            RuntimeError("XML parse error"),
            [good_txn],
        ]

        result = fetch_institutional_holdings("AAPL")

        assert len(result) == 1
        assert result[0].entity == "Good Fund"

    @patch("agora.adapters.edgar_institutional_adapter._search_13f_filings", create=True)
    @patch("agora.adapters.edgar_institutional_adapter._parse_13f_filing", create=True)
    def test_all_filings_fail_returns_empty(self, mock_parse, mock_search) -> None:
        mock_search.return_value = [
            {"url": "http://example.com/bad1"},
            {"url": "http://example.com/bad2"},
        ]
        mock_parse.side_effect = RuntimeError("XML parse error")

        result = fetch_institutional_holdings("AAPL")
        assert result == []


# ---------------------------------------------------------------------------
# Date filtering
# ---------------------------------------------------------------------------


class TestDateFiltering:
    """start_date and end_date parameters filter returned transactions."""

    @patch("agora.adapters.edgar_institutional_adapter._search_13f_filings", create=True)
    @patch("agora.adapters.edgar_institutional_adapter._parse_13f_filing", create=True)
    def test_start_date_filter(self, mock_parse, mock_search) -> None:
        mock_search.return_value = [{"url": "http://example.com/filing"}]
        mock_parse.return_value = _sample_transactions()

        result = fetch_institutional_holdings(
            "AAPL", start_date=date(2024, 4, 1)
        )
        assert all(t.date >= date(2024, 4, 1) for t in result)
        assert len(result) == 2  # June + September transactions

    @patch("agora.adapters.edgar_institutional_adapter._search_13f_filings", create=True)
    @patch("agora.adapters.edgar_institutional_adapter._parse_13f_filing", create=True)
    def test_end_date_filter(self, mock_parse, mock_search) -> None:
        mock_search.return_value = [{"url": "http://example.com/filing"}]
        mock_parse.return_value = _sample_transactions()

        result = fetch_institutional_holdings(
            "AAPL", end_date=date(2024, 3, 31)
        )
        assert all(t.date <= date(2024, 3, 31) for t in result)
        assert len(result) == 2  # January + March transactions

    @patch("agora.adapters.edgar_institutional_adapter._search_13f_filings", create=True)
    @patch("agora.adapters.edgar_institutional_adapter._parse_13f_filing", create=True)
    def test_both_date_filters(self, mock_parse, mock_search) -> None:
        mock_search.return_value = [{"url": "http://example.com/filing"}]
        mock_parse.return_value = _sample_transactions()

        result = fetch_institutional_holdings(
            "AAPL",
            start_date=date(2024, 2, 1),
            end_date=date(2024, 7, 1),
        )
        assert all(
            date(2024, 2, 1) <= t.date <= date(2024, 7, 1) for t in result
        )
        assert len(result) == 2  # March + June transactions

    @patch("agora.adapters.edgar_institutional_adapter._search_13f_filings", create=True)
    @patch("agora.adapters.edgar_institutional_adapter._parse_13f_filing", create=True)
    def test_no_results_in_range(self, mock_parse, mock_search) -> None:
        mock_search.return_value = [{"url": "http://example.com/filing"}]
        mock_parse.return_value = _sample_transactions()

        result = fetch_institutional_holdings(
            "AAPL",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
        )
        assert result == []

    @patch("agora.adapters.edgar_institutional_adapter._search_13f_filings", create=True)
    @patch("agora.adapters.edgar_institutional_adapter._parse_13f_filing", create=True)
    def test_dates_passed_to_search(self, mock_parse, mock_search) -> None:
        """Verify start_date/end_date are forwarded to the search function."""
        mock_search.return_value = []
        sd = date(2024, 1, 1)
        ed = date(2024, 12, 31)

        fetch_institutional_holdings("AAPL", start_date=sd, end_date=ed)

        mock_search.assert_called_once_with("AAPL", sd, ed)
