"""Tests for the edgar_filings_adapter module."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from agora.adapters.edgar_filings_adapter import (
    EDGAR_FILING_BASE,
    EFTS_SEARCH_URL,
    _hit_to_filing,
    fetch_filings,
)
from agora.schemas import Filing


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

SYMBOL = "AAPL"


def _make_hit(
    accession="0001193125-23-012345",
    filename="filing.htm",
    cik="320193",
    display_name="Apple Inc.",
    form_type="10-K",
    file_date="2025-11-01",
):
    """Build a synthetic EFTS hit dict."""
    return {
        "_id": f"{accession}:{filename}",
        "_source": {
            "ciks": [cik],
            "display_names": [display_name],
            "forms": [form_type],
            "file_date": file_date,
        },
    }


def _efts_response(*hits):
    """Wrap hits in the EFTS response envelope."""
    return {"hits": {"hits": list(hits)}}


@pytest.fixture()
def mock_efts_response():
    """A typical multi-filing EFTS response."""
    return _efts_response(
        _make_hit(
            accession="0001193125-25-000111",
            filename="aapl-20251101.htm",
            cik="320193",
            display_name="Apple Inc.",
            form_type="10-K",
            file_date="2025-11-01",
        ),
        _make_hit(
            accession="0001193125-25-000222",
            filename="aapl-20250801.htm",
            cik="320193",
            display_name="Apple Inc.",
            form_type="10-Q",
            file_date="2025-08-01",
        ),
        _make_hit(
            accession="0001193125-25-000333",
            filename="aapl-8k-20250615.htm",
            cik="320193",
            display_name="Apple Inc.",
            form_type="8-K",
            file_date="2025-06-15",
        ),
    )


# -----------------------------------------------------------------------
# _hit_to_filing unit tests
# -----------------------------------------------------------------------


class TestHitToFiling:
    """Low-level conversion of a single EFTS hit to Filing."""

    def test_valid_hit(self):
        hit = _make_hit()
        filing = _hit_to_filing(hit)
        assert filing is not None
        assert isinstance(filing, Filing)
        assert filing.entity == "Apple Inc."
        assert filing.type == "10-K"
        assert filing.date == date(2025, 11, 1)
        assert "320193" in filing.url
        assert filing.extracted_fields["accession_number"] == "0001193125-23-012345"
        assert filing.extracted_fields["cik"] == "320193"

    def test_missing_id_separator(self):
        hit = {"_id": "no-separator", "_source": {"ciks": ["1"]}}
        assert _hit_to_filing(hit) is None

    def test_missing_ciks(self):
        hit = {"_id": "acc:file.htm", "_source": {"ciks": []}}
        assert _hit_to_filing(hit) is None

    def test_missing_file_date(self):
        hit = _make_hit(file_date="")
        assert _hit_to_filing(hit) is None

    def test_invalid_date_format(self):
        hit = _make_hit(file_date="not-a-date")
        assert _hit_to_filing(hit) is None

    def test_url_construction(self):
        hit = _make_hit(
            accession="0001193125-23-012345",
            filename="doc.htm",
            cik="320193",
        )
        filing = _hit_to_filing(hit)
        assert filing is not None
        expected_url = f"{EDGAR_FILING_BASE}/320193/000119312523012345/doc.htm"
        assert filing.url == expected_url

    def test_fallback_entity_name(self):
        hit = _make_hit()
        hit["_source"]["display_names"] = []
        hit["_source"]["entity_name"] = "Fallback Corp"
        filing = _hit_to_filing(hit)
        assert filing is not None
        assert filing.entity == "Fallback Corp"

    def test_fallback_form_type(self):
        hit = _make_hit()
        hit["_source"]["forms"] = []
        hit["_source"]["form_type"] = "10-Q"
        filing = _hit_to_filing(hit)
        assert filing is not None
        assert filing.type == "10-Q"


# -----------------------------------------------------------------------
# fetch_filings integration tests (mocked HTTP)
# -----------------------------------------------------------------------


class TestFetchFilings:
    """Public API tests with mocked EFTS responses."""

    @patch("agora.adapters.edgar_filings_adapter._get")
    @patch("agora.adapters.edgar_filings_adapter._throttle")
    def test_returns_filings_sorted_by_date(self, _mock_throttle, mock_get, mock_efts_response):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = mock_efts_response
        mock_get.return_value = resp

        filings = fetch_filings(SYMBOL)

        assert len(filings) == 3
        assert filings[0].date <= filings[1].date <= filings[2].date
        assert filings[0].type == "8-K"  # 2025-06-15 is earliest

    @patch("agora.adapters.edgar_filings_adapter._get")
    @patch("agora.adapters.edgar_filings_adapter._throttle")
    def test_filing_type_filter(self, _mock_throttle, mock_get, mock_efts_response):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = mock_efts_response
        mock_get.return_value = resp

        fetch_filings(SYMBOL, filing_type="10-K")

        call_kwargs = mock_get.call_args
        assert "10-K" in call_kwargs.kwargs.get("params", {}).get("forms", "")

    @patch("agora.adapters.edgar_filings_adapter._get")
    @patch("agora.adapters.edgar_filings_adapter._throttle")
    def test_date_range_filter(self, _mock_throttle, mock_get, mock_efts_response):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = mock_efts_response
        mock_get.return_value = resp

        filings = fetch_filings(
            SYMBOL,
            start_date=date(2025, 7, 1),
            end_date=date(2025, 9, 30),
        )

        # Only the 10-Q (2025-08-01) falls in range
        assert len(filings) == 1
        assert filings[0].type == "10-Q"

    @patch("agora.adapters.edgar_filings_adapter._get")
    @patch("agora.adapters.edgar_filings_adapter._throttle")
    def test_http_error_returns_empty(self, _mock_throttle, mock_get):
        resp = MagicMock()
        resp.status_code = 503
        mock_get.return_value = resp

        filings = fetch_filings(SYMBOL)
        assert filings == []

    @patch("agora.adapters.edgar_filings_adapter._get")
    @patch("agora.adapters.edgar_filings_adapter._throttle")
    def test_non_json_response_returns_empty(self, _mock_throttle, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("No JSON")
        mock_get.return_value = resp

        filings = fetch_filings(SYMBOL)
        assert filings == []

    def test_unsupported_filing_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported filing_type"):
            fetch_filings(SYMBOL, filing_type="13-F")

    @patch("agora.adapters.edgar_filings_adapter._get")
    @patch("agora.adapters.edgar_filings_adapter._throttle")
    def test_efts_params_include_symbol_and_dates(self, _mock_throttle, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _efts_response()
        mock_get.return_value = resp

        fetch_filings(
            "MSFT",
            filing_type="10-Q",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        call_args = mock_get.call_args
        params = call_args.kwargs.get("params", {})
        assert '"MSFT"' in params["q"]
        assert params["forms"] == "10-Q"
        assert params["startdt"] == "2024-01-01"
        assert params["enddt"] == "2024-12-31"

    @patch("agora.adapters.edgar_filings_adapter._get")
    @patch("agora.adapters.edgar_filings_adapter._throttle")
    def test_all_forms_when_no_type_filter(self, _mock_throttle, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _efts_response()
        mock_get.return_value = resp

        fetch_filings("TSLA")

        call_args = mock_get.call_args
        params = call_args.kwargs.get("params", {})
        forms = params["forms"]
        assert "10-K" in forms
        assert "10-Q" in forms
        assert "8-K" in forms

    @patch("agora.adapters.edgar_filings_adapter._get")
    @patch("agora.adapters.edgar_filings_adapter._throttle")
    def test_efts_url_used(self, _mock_throttle, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _efts_response()
        mock_get.return_value = resp

        fetch_filings(SYMBOL)

        assert mock_get.called
        assert EFTS_SEARCH_URL in str(mock_get.call_args)

    @patch("agora.adapters.edgar_filings_adapter._get")
    @patch("agora.adapters.edgar_filings_adapter._throttle")
    def test_malformed_hits_skipped(self, _mock_throttle, mock_get):
        bad_response = _efts_response(
            {"_id": "no-separator", "_source": {}},
            _make_hit(),  # one valid hit
        )
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = bad_response
        mock_get.return_value = resp

        filings = fetch_filings(SYMBOL)
        assert len(filings) == 1
