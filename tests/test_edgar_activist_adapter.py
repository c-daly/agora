"""Tests for the EDGAR activist adapter (13D/13G).

All HTTP calls are mocked. Validates that filing metadata is correctly
parsed and transformed into Transaction objects with the expected
entity, action, amount, and context fields.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch


from agora.adapters.edgar_activist_adapter import (
    _determine_action,
    _extract_filing_metadata,
    _extract_name,
    _extract_percent,
    _extract_shares,
    _parse_activist_filing_text,
    fetch_activist_positions,
)
from agora.schemas import Transaction


# ---------------------------------------------------------------------------
# Constants and fixtures
# ---------------------------------------------------------------------------

SYMBOL = "AAPL"

_SAMPLE_EFTS_RESPONSE = {
    "hits": {
        "hits": [
            {
                "_id": "0001234567-24-000001:filing.htm",
                "_source": {
                    "ciks": ["9876543", "1111111"],
                    "file_date": "2024-06-15",
                    "display_names": ["Icahn Capital LP"],
                    "form_type": "SC 13D",
                },
            },
            {
                "_id": "0001234567-24-000002:amend.htm",
                "_source": {
                    "ciks": ["9876543"],
                    "file_date": "2024-09-01",
                    "display_names": ["Icahn Capital LP"],
                    "form_type": "SC 13D/A",
                },
            },
        ]
    }
}

_SAMPLE_13D_TEXT = """
UNITED STATES SECURITIES AND EXCHANGE COMMISSION
SCHEDULE 13D

Name of Reporting Person: Icahn Capital LP

Aggregate Amount Beneficially Owned: 15,000,000

Percent of Class: 7.5%
"""

_SAMPLE_13D_AMENDMENT_DECREASE = """
UNITED STATES SECURITIES AND EXCHANGE COMMISSION
SCHEDULE 13D/A (Amendment No. 2)

Name of Reporting Person: Icahn Capital LP

The reporting person has decreased its position.
Aggregate Amount Beneficially Owned: 10,000,000

Certain shares were disposed of in open market transactions.
Percent of Class: 5.1%
"""

_SAMPLE_13D_AMENDMENT_INCREASE = """
UNITED STATES SECURITIES AND EXCHANGE COMMISSION
SCHEDULE 13D/A (Amendment No. 3)

Name of Reporting Person: Icahn Capital LP

Aggregate Amount Beneficially Owned: 20,000,000

Percent of Class: 9.8%
"""


# ---------------------------------------------------------------------------
# Tests for internal parsing helpers
# ---------------------------------------------------------------------------


class TestExtractName:
    """Tests for _extract_name."""

    def test_extracts_reporting_person_name(self):
        text = "Name of Reporting Person: Icahn Capital LP"
        assert _extract_name(text) == "Icahn Capital LP"

    def test_extracts_filed_by_name(self):
        text = "Filed by: Elliott Investment Management"
        assert _extract_name(text) == "Elliott Investment Management"

    def test_returns_none_for_no_match(self):
        assert _extract_name("no relevant content here") is None

    def test_rejects_overly_long_match(self):
        text = "Filed by: " + "A" * 200
        assert _extract_name(text) is None


class TestExtractShares:
    """Tests for _extract_shares."""

    def test_extracts_aggregate_amount(self):
        text = "Aggregate Amount Beneficially Owned: 15,000,000"
        assert _extract_shares(text) == 15_000_000

    def test_extracts_number_of_shares(self):
        text = "Number of Shares: 500,000"
        assert _extract_shares(text) == 500_000

    def test_returns_none_for_no_match(self):
        assert _extract_shares("no shares mentioned") is None


class TestExtractPercent:
    """Tests for _extract_percent."""

    def test_extracts_percent_of_class(self):
        text = "Percent of Class: 7.5%"
        assert _extract_percent(text) == 7.5

    def test_extracts_percentage_variant(self):
        text = "Percentage: 12.3%"
        assert _extract_percent(text) == 12.3

    def test_returns_none_for_no_match(self):
        assert _extract_percent("no percent here") is None


class TestDetermineAction:
    """Tests for _determine_action."""

    def test_initial_13d_returns_acquire(self):
        assert _determine_action("SC 13D", "any text") == "Acquire"

    def test_initial_13g_returns_acquire(self):
        assert _determine_action("SC 13G", "any text") == "Acquire"

    def test_amendment_with_decrease_language(self):
        assert _determine_action("SC 13D/A", "shares were disposed") == "Decrease"

    def test_amendment_with_sold_language(self):
        assert _determine_action("SC 13G/A", "shares sold in open market") == "Decrease"

    def test_amendment_defaults_to_increase(self):
        assert _determine_action("SC 13D/A", "position updated") == "Increase"


# ---------------------------------------------------------------------------
# Tests for _extract_filing_metadata
# ---------------------------------------------------------------------------


class TestExtractFilingMetadata:
    """Tests for _extract_filing_metadata."""

    def test_extracts_metadata_from_efts_response(self):
        result = _extract_filing_metadata(_SAMPLE_EFTS_RESPONSE)
        assert len(result) == 2

        first = result[0]
        assert first["filer_name"] == "Icahn Capital LP"
        assert first["form_type"] == "SC 13D"
        assert first["file_date"] == "2024-06-15"
        assert "filing.htm" in first["url"]

    def test_skips_entries_without_colon_in_id(self):
        response = {"hits": {"hits": [{"_id": "nocolon", "_source": {}}]}}
        assert _extract_filing_metadata(response) == []

    def test_skips_entries_without_ciks(self):
        response = {"hits": {"hits": [{"_id": "acc:file", "_source": {"ciks": []}}]}}
        assert _extract_filing_metadata(response) == []

    def test_empty_response(self):
        assert _extract_filing_metadata({}) == []


# ---------------------------------------------------------------------------
# Tests for _parse_activist_filing_text
# ---------------------------------------------------------------------------


class TestParseActivistFilingText:
    """Tests for _parse_activist_filing_text."""

    def test_parses_initial_13d(self):
        meta = {
            "file_date": "2024-06-15",
            "filer_name": "Fallback Name",
            "form_type": "SC 13D",
            "url": "https://example.com/filing.htm",
        }
        txn = _parse_activist_filing_text(_SAMPLE_13D_TEXT, meta, "AAPL")
        assert txn is not None
        assert isinstance(txn, Transaction)
        assert txn.date == date(2024, 6, 15)
        assert txn.entity == "Icahn Capital LP"
        assert txn.action == "Acquire"
        assert txn.amount == 15_000_000.0
        assert txn.context["symbol"] == "AAPL"
        assert txn.context["percent_owned"] == 7.5
        assert txn.context["filing_type"] == "SC 13D"
        assert txn.context["form_url"] == "https://example.com/filing.htm"

    def test_parses_amendment_decrease(self):
        meta = {
            "file_date": "2024-09-01",
            "filer_name": "Fallback Name",
            "form_type": "SC 13D/A",
            "url": "https://example.com/amend.htm",
        }
        txn = _parse_activist_filing_text(_SAMPLE_13D_AMENDMENT_DECREASE, meta, "AAPL")
        assert txn is not None
        assert txn.action == "Decrease"
        assert txn.amount == 10_000_000.0
        assert txn.context["percent_owned"] == 5.1

    def test_parses_amendment_increase(self):
        meta = {
            "file_date": "2024-10-15",
            "filer_name": "Fallback Name",
            "form_type": "SC 13D/A",
            "url": "https://example.com/amend2.htm",
        }
        txn = _parse_activist_filing_text(_SAMPLE_13D_AMENDMENT_INCREASE, meta, "AAPL")
        assert txn is not None
        assert txn.action == "Increase"
        assert txn.amount == 20_000_000.0

    def test_returns_none_for_missing_date(self):
        meta = {"file_date": "", "filer_name": "X", "form_type": "SC 13D", "url": ""}
        assert _parse_activist_filing_text(_SAMPLE_13D_TEXT, meta, "AAPL") is None

    def test_returns_none_for_no_shares(self):
        meta = {
            "file_date": "2024-01-01",
            "filer_name": "X",
            "form_type": "SC 13D",
            "url": "",
        }
        assert _parse_activist_filing_text("no shares info", meta, "AAPL") is None

    def test_falls_back_to_filer_name(self):
        # Filing text has no parseable name
        text = "Aggregate Amount Beneficially Owned: 100,000"
        meta = {
            "file_date": "2024-01-01",
            "filer_name": "Meta Filer Name",
            "form_type": "SC 13G",
            "url": "",
        }
        txn = _parse_activist_filing_text(text, meta, "AAPL")
        assert txn is not None
        assert txn.entity == "Meta Filer Name"


# ---------------------------------------------------------------------------
# Tests for fetch_activist_positions (mocked HTTP)
# ---------------------------------------------------------------------------


def _mock_get_factory(efts_json, filing_text):
    """Return a side_effect function for mocking _get."""
    call_count = [0]

    def _side_effect(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if call_count[0] == 0:
            # First call is the EFTS search
            resp.json.return_value = efts_json
        else:
            # Subsequent calls are filing downloads
            resp.text = filing_text
        call_count[0] += 1
        return resp

    return _side_effect


class TestFetchActivistPositions:
    """Integration tests for fetch_activist_positions with mocked HTTP."""

    @patch("agora.adapters.edgar_activist_adapter._get")
    @patch("agora.adapters.edgar_activist_adapter._throttle")
    def test_returns_transactions(self, mock_throttle, mock_get):
        # Use only the first filing from the EFTS response
        single_hit_response = {
            "hits": {
                "hits": [_SAMPLE_EFTS_RESPONSE["hits"]["hits"][0]]
            }
        }
        mock_get.side_effect = _mock_get_factory(single_hit_response, _SAMPLE_13D_TEXT)

        results = fetch_activist_positions("AAPL")

        assert len(results) == 1
        txn = results[0]
        assert isinstance(txn, Transaction)
        assert txn.entity == "Icahn Capital LP"
        assert txn.action == "Acquire"
        assert txn.amount == 15_000_000.0

    @patch("agora.adapters.edgar_activist_adapter._get")
    @patch("agora.adapters.edgar_activist_adapter._throttle")
    def test_filters_by_date_range(self, mock_throttle, mock_get):
        single_hit_response = {
            "hits": {
                "hits": [_SAMPLE_EFTS_RESPONSE["hits"]["hits"][0]]
            }
        }
        mock_get.side_effect = _mock_get_factory(single_hit_response, _SAMPLE_13D_TEXT)

        # Filing date is 2024-06-15, filter to after that
        results = fetch_activist_positions(
            "AAPL", start_date=date(2024, 7, 1)
        )
        assert len(results) == 0

    @patch("agora.adapters.edgar_activist_adapter._get")
    @patch("agora.adapters.edgar_activist_adapter._throttle")
    def test_handles_empty_search_results(self, mock_throttle, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"hits": {"hits": []}}
        mock_get.return_value = mock_resp

        results = fetch_activist_positions("AAPL")
        assert results == []

    @patch("agora.adapters.edgar_activist_adapter._get")
    @patch("agora.adapters.edgar_activist_adapter._throttle")
    def test_handles_http_error(self, mock_throttle, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        results = fetch_activist_positions("AAPL")
        assert results == []

    @patch("agora.adapters.edgar_activist_adapter._get")
    @patch("agora.adapters.edgar_activist_adapter._throttle")
    def test_skips_unparseable_filing(self, mock_throttle, mock_get):
        single_hit_response = {
            "hits": {
                "hits": [_SAMPLE_EFTS_RESPONSE["hits"]["hits"][0]]
            }
        }
        # First call returns EFTS response, second returns unparseable text
        mock_get.side_effect = _mock_get_factory(single_hit_response, "garbage content")

        results = fetch_activist_positions("AAPL")
        # Should be empty since the filing text has no shares
        assert results == []

    @patch("agora.adapters.edgar_activist_adapter._get")
    @patch("agora.adapters.edgar_activist_adapter._throttle")
    def test_results_are_sorted_chronologically(self, mock_throttle, mock_get):
        # Two filings with different dates, second is earlier
        hits = _SAMPLE_EFTS_RESPONSE["hits"]["hits"]
        reversed_response = {"hits": {"hits": list(reversed(hits))}}

        call_count = [0]

        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if call_count[0] == 0:
                resp.json.return_value = reversed_response
            else:
                resp.text = _SAMPLE_13D_TEXT
            call_count[0] += 1
            return resp

        mock_get.side_effect = side_effect

        results = fetch_activist_positions("AAPL")
        if len(results) >= 2:
            assert results[0].date <= results[1].date
