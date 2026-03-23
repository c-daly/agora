"""Tests for the EDGAR insider-trading (Form 4) adapter.

All HTTP calls are mocked -- no live SEC traffic.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from agora.adapters.edgar_insider_adapter import (
    EDGAR_ARCHIVES_BASE,
    SEC_USER_AGENT,
    _extract_xml_urls,
    _parse_form4_xml_content,
    fetch_insider_trades,
)
from agora.schemas import Transaction


# ---------------------------------------------------------------------------
# Fixtures: realistic EFTS JSON and Form 4 XML
# ---------------------------------------------------------------------------

SAMPLE_EFTS_RESPONSE = {
    "hits": {
        "total": {"value": 2},
        "hits": [
            {"_id": "edgar/data/320193/0001234567-24-000001.txt"},
            {"_id": "edgar/data/320193/0001234567-24-000002.txt"},
        ],
    }
}

SAMPLE_FORM4_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ownershipDocument>
  <issuer>
    <issuerCik>0000320193</issuerCik>
    <issuerName>Apple Inc</issuerName>
    <issuerTradingSymbol>AAPL</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0009876543</rptOwnerCik>
      <rptOwnerName>Cook Timothy D</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isOfficer>1</isOfficer>
      <officerTitle>Chief Executive Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2024-06-15</value></transactionDate>
      <transactionCoding>
        <transactionCode>S</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>50000</value></transactionShares>
        <transactionPricePerShare><value>195.50</value></transactionPricePerShare>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>3361122</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2024-06-14</value></transactionDate>
      <transactionCoding>
        <transactionCode>P</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>10000</value></transactionShares>
        <transactionPricePerShare><value>194.00</value></transactionPricePerShare>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>3411122</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <derivativeTable>
    <derivativeTransaction>
      <securityTitle><value>Stock Option (Right to Buy)</value></securityTitle>
      <transactionDate><value>2024-06-13</value></transactionDate>
      <transactionCoding>
        <transactionCode>M</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>25000</value></transactionShares>
        <transactionPricePerShare><value>120.00</value></transactionPricePerShare>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>0</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
    </derivativeTransaction>
  </derivativeTable>
</ownershipDocument>
"""


def _make_mock_response(status_code: int = 200, json_data=None, content=b""):
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("No JSON")
    return resp


# ---------------------------------------------------------------------------
# 1. _extract_xml_urls unit tests
# ---------------------------------------------------------------------------


class TestExtractXmlUrls:
    def test_extracts_urls_from_hits(self):
        urls = _extract_xml_urls(SAMPLE_EFTS_RESPONSE)
        assert len(urls) == 2
        assert all(url.startswith(EDGAR_ARCHIVES_BASE) for url in urls)

    def test_returns_empty_for_no_hits(self):
        assert _extract_xml_urls({"hits": {"hits": []}}) == []

    def test_returns_empty_for_missing_hits_key(self):
        assert _extract_xml_urls({}) == []

    def test_skips_entries_without_id(self):
        data = {"hits": {"hits": [{"_id": ""}, {"_id": "edgar/data/123/doc.txt"}]}}
        urls = _extract_xml_urls(data)
        assert len(urls) == 1


# ---------------------------------------------------------------------------
# 2. _parse_form4_xml_content unit tests
# ---------------------------------------------------------------------------


class TestParseForm4XmlContent:
    def test_parses_non_derivative_transactions(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML, "http://example.com/form4.xml")
        non_deriv = [t for t in txns if t.action in ("Buy", "Sell")]
        assert len(non_deriv) == 2

    def test_parses_derivative_transactions(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML, "http://example.com/form4.xml")
        exercises = [t for t in txns if t.action == "Exercise"]
        assert len(exercises) == 1

    def test_total_transaction_count(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML)
        assert len(txns) == 3

    def test_entity_is_insider_name(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML)
        for t in txns:
            assert t.entity == "Cook Timothy D"

    def test_sell_action(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML)
        sell = [t for t in txns if t.action == "Sell"][0]
        assert sell.amount == 50000.0
        assert sell.date == date(2024, 6, 15)

    def test_buy_action(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML)
        buy = [t for t in txns if t.action == "Buy"][0]
        assert buy.amount == 10000.0
        assert buy.date == date(2024, 6, 14)

    def test_exercise_action(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML)
        ex = [t for t in txns if t.action == "Exercise"][0]
        assert ex.amount == 25000.0
        assert ex.date == date(2024, 6, 13)

    def test_context_has_title(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML)
        for t in txns:
            assert t.context["title"] == "Chief Executive Officer"

    def test_context_has_price(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML)
        sell = [t for t in txns if t.action == "Sell"][0]
        assert sell.context["price"] == 195.50

    def test_context_has_shares_owned_after(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML)
        sell = [t for t in txns if t.action == "Sell"][0]
        assert sell.context["shares_owned_after"] == 3361122.0

    def test_context_has_symbol(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML)
        for t in txns:
            assert t.context["symbol"] == "AAPL"

    def test_context_has_form_url(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML, "http://example.com/form4.xml")
        for t in txns:
            assert t.context["form_url"] == "http://example.com/form4.xml"

    def test_returns_transaction_objects(self):
        txns = _parse_form4_xml_content(SAMPLE_FORM4_XML)
        for t in txns:
            assert isinstance(t, Transaction)

    def test_invalid_xml_returns_empty(self):
        txns = _parse_form4_xml_content(b"<not valid xml")
        assert txns == []

    def test_missing_date_skips_transaction(self):
        xml = b"""<?xml version="1.0"?>
        <ownershipDocument>
          <reportingOwner>
            <reportingOwnerId><rptOwnerName>Test</rptOwnerName></reportingOwnerId>
          </reportingOwner>
          <issuer><issuerTradingSymbol>TST</issuerTradingSymbol></issuer>
          <nonDerivativeTable>
            <nonDerivativeTransaction>
              <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
              <transactionAmounts>
                <transactionShares><value>100</value></transactionShares>
              </transactionAmounts>
            </nonDerivativeTransaction>
          </nonDerivativeTable>
        </ownershipDocument>"""
        txns = _parse_form4_xml_content(xml)
        assert txns == []


# ---------------------------------------------------------------------------
# 3. fetch_insider_trades integration tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchInsiderTrades:
    @patch("agora.adapters.edgar_insider_adapter._get")
    def test_returns_list_of_transactions(self, mock_get):
        # First call: EFTS search; subsequent calls: Form 4 XML downloads
        search_resp = _make_mock_response(json_data=SAMPLE_EFTS_RESPONSE)
        xml_resp = _make_mock_response(content=SAMPLE_FORM4_XML)
        mock_get.side_effect = [search_resp, xml_resp, xml_resp]

        result = fetch_insider_trades("AAPL")
        assert isinstance(result, list)
        assert all(isinstance(t, Transaction) for t in result)

    @patch("agora.adapters.edgar_insider_adapter._get")
    def test_results_sorted_chronologically(self, mock_get):
        search_resp = _make_mock_response(json_data=SAMPLE_EFTS_RESPONSE)
        xml_resp = _make_mock_response(content=SAMPLE_FORM4_XML)
        mock_get.side_effect = [search_resp, xml_resp, xml_resp]

        result = fetch_insider_trades("AAPL")
        dates = [t.date for t in result]
        assert dates == sorted(dates)

    @patch("agora.adapters.edgar_insider_adapter._get")
    def test_start_date_filter(self, mock_get):
        search_resp = _make_mock_response(json_data=SAMPLE_EFTS_RESPONSE)
        xml_resp = _make_mock_response(content=SAMPLE_FORM4_XML)
        mock_get.side_effect = [search_resp, xml_resp, xml_resp]

        result = fetch_insider_trades(
            "AAPL", start_date=date(2024, 6, 15),
        )
        assert len(result) > 0
        for t in result:
            assert t.date >= date(2024, 6, 15)

    @patch("agora.adapters.edgar_insider_adapter._get")
    def test_end_date_filter(self, mock_get):
        search_resp = _make_mock_response(json_data=SAMPLE_EFTS_RESPONSE)
        xml_resp = _make_mock_response(content=SAMPLE_FORM4_XML)
        mock_get.side_effect = [search_resp, xml_resp, xml_resp]

        result = fetch_insider_trades(
            "AAPL", end_date=date(2024, 6, 13),
        )
        assert len(result) > 0
        for t in result:
            assert t.date <= date(2024, 6, 13)

    @patch("agora.adapters.edgar_insider_adapter._get")
    def test_date_range_filter(self, mock_get):
        search_resp = _make_mock_response(json_data=SAMPLE_EFTS_RESPONSE)
        xml_resp = _make_mock_response(content=SAMPLE_FORM4_XML)
        mock_get.side_effect = [search_resp, xml_resp, xml_resp]

        result = fetch_insider_trades(
            "AAPL",
            start_date=date(2024, 6, 14),
            end_date=date(2024, 6, 14),
        )
        assert len(result) == 2  # Buy on 6/14 from both filings
        for t in result:
            assert t.date == date(2024, 6, 14)

    @patch("agora.adapters.edgar_insider_adapter._get")
    def test_efts_search_failure_returns_empty(self, mock_get):
        mock_get.return_value = _make_mock_response(status_code=500)
        result = fetch_insider_trades("AAPL")
        assert result == []

    @patch("agora.adapters.edgar_insider_adapter._get")
    def test_efts_non_json_returns_empty(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("not json")
        mock_get.return_value = resp
        result = fetch_insider_trades("AAPL")
        assert result == []

    @patch("agora.adapters.edgar_insider_adapter._get")
    def test_xml_download_failure_skipped(self, mock_get):
        search_resp = _make_mock_response(json_data=SAMPLE_EFTS_RESPONSE)
        bad_xml = _make_mock_response(status_code=404)
        mock_get.side_effect = [search_resp, bad_xml, bad_xml]

        result = fetch_insider_trades("AAPL")
        assert result == []

    @patch("agora.adapters.edgar_insider_adapter._get")
    def test_user_agent_sent(self, mock_get):
        """Verify _get is called (which adds User-Agent internally)."""
        search_resp = _make_mock_response(json_data={"hits": {"hits": []}})
        mock_get.return_value = search_resp

        fetch_insider_trades("AAPL")
        assert mock_get.called

    @patch("agora.adapters.edgar_insider_adapter._get")
    def test_empty_search_results(self, mock_get):
        search_resp = _make_mock_response(json_data={"hits": {"hits": []}})
        mock_get.return_value = search_resp

        result = fetch_insider_trades("ZZZZ")
        assert result == []
        # Only one call (the search), no XML downloads
        assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# 4. User-Agent and rate limiting
# ---------------------------------------------------------------------------


class TestUserAgentAndRateLimit:
    def test_sec_user_agent_is_descriptive(self):
        """SEC requires a descriptive User-Agent with contact info."""
        assert "@" in SEC_USER_AGENT
        assert len(SEC_USER_AGENT) > 10

    @patch("agora.adapters.edgar_insider_adapter.requests.get")
    def test_get_sends_user_agent_header(self, mock_requests_get):
        """The _get helper should set User-Agent on every request."""
        from agora.adapters.edgar_insider_adapter import _get

        mock_requests_get.return_value = MagicMock(status_code=200)
        _get("http://example.com")
        _, kwargs = mock_requests_get.call_args
        assert kwargs["headers"]["User-Agent"] == SEC_USER_AGENT


# ---------------------------------------------------------------------------
# 5. Transaction code mapping
# ---------------------------------------------------------------------------


class TestTransactionCodeMapping:
    """Verify all documented SEC transaction codes map correctly."""

    @pytest.mark.parametrize(
        "code,expected_action",
        [
            ("P", "Buy"),
            ("S", "Sell"),
            ("M", "Exercise"),
            ("C", "Exercise"),
            ("A", "Buy"),
            ("D", "Sell"),
            ("F", "Sell"),
            ("G", "Buy"),
            ("J", "Buy"),
            ("X", "Exercise"),
        ],
    )
    def test_code_to_action(self, code, expected_action):
        xml_template = f"""<?xml version="1.0"?>
        <ownershipDocument>
          <reportingOwner>
            <reportingOwnerId><rptOwnerName>Jane Doe</rptOwnerName></reportingOwnerId>
          </reportingOwner>
          <issuer><issuerTradingSymbol>TST</issuerTradingSymbol></issuer>
          <nonDerivativeTable>
            <nonDerivativeTransaction>
              <transactionDate><value>2024-01-01</value></transactionDate>
              <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
              <transactionAmounts>
                <transactionShares><value>100</value></transactionShares>
                <transactionPricePerShare><value>50.00</value></transactionPricePerShare>
              </transactionAmounts>
            </nonDerivativeTransaction>
          </nonDerivativeTable>
        </ownershipDocument>"""
        txns = _parse_form4_xml_content(xml_template.encode())
        assert len(txns) == 1
        assert txns[0].action == expected_action
