"""Tests for the screener API route.

Tests use mocked adapters (no real HTTP calls). Validates response
status codes, JSON body shapes, sorting, and graceful error handling.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agora.schemas import ShortData


# -----------------------------------------------------------------------
# Fake data builders
# -----------------------------------------------------------------------


def _make_short_volume(symbol: str, ratio: float = 0.55) -> list[ShortData]:
    """Return fake FINRA short volume data with a configurable ratio."""
    total = 10_000_000
    short = int(total * ratio)
    return [
        ShortData(
            symbol=symbol,
            date=date(2024, 3, 18),
            data_type="short_volume",
            value=short,
            total_for_ratio=total,
            source="FINRA",
        ),
        ShortData(
            symbol=symbol,
            date=date(2024, 3, 19),
            data_type="short_volume",
            value=short,
            total_for_ratio=total,
            source="FINRA",
        ),
    ]


def _make_short_interest(symbol: str, value: float = 15.0) -> list[ShortData]:
    """Return fake Yahoo short interest data."""
    return [
        ShortData(
            symbol=symbol,
            date=date(2024, 3, 15),
            data_type="short_interest",
            value=value,
            source="Yahoo Finance",
        ),
    ]


def _make_ftd(symbol: str, magnitude: int = 150_000) -> list[ShortData]:
    """Return fake SEC FTD data."""
    return [
        ShortData(
            symbol=symbol,
            date=date(2024, 3, 18),
            data_type="ftd",
            value=magnitude,
            total_for_ratio=25.0,
            source="SEC",
        ),
        ShortData(
            symbol=symbol,
            date=date(2024, 3, 19),
            data_type="ftd",
            value=magnitude,
            total_for_ratio=26.0,
            source="SEC",
        ),
    ]


# -----------------------------------------------------------------------
# Per-symbol adapter side-effect helpers
# -----------------------------------------------------------------------

# GME: high short pressure
# AAPL: low short pressure
_SV_DATA = {
    "GME": _make_short_volume("GME", ratio=0.65),
    "AAPL": _make_short_volume("AAPL", ratio=0.25),
    "AMC": _make_short_volume("AMC", ratio=0.55),
}

_SI_DATA = {
    "GME": _make_short_interest("GME", value=25.0),
    "AAPL": _make_short_interest("AAPL", value=3.0),
    "AMC": _make_short_interest("AMC", value=12.0),
}

_FTD_DATA = {
    "GME": _make_ftd("GME", magnitude=400_000),
    "AAPL": _make_ftd("AAPL", magnitude=10_000),
    "AMC": _make_ftd("AMC", magnitude=150_000),
}


def _sv_side_effect(symbol, **kwargs):
    return _SV_DATA.get(symbol, [])


def _si_side_effect(symbol):
    return _SI_DATA.get(symbol, [])


def _ftd_side_effect(*, symbol=None, **kwargs):
    return _FTD_DATA.get(symbol, [])


def _original_score_ticker_via_mock(ticker: str) -> dict:
    """Helper: call the real _score_ticker logic with mocked adapters."""
    from agora.analysis import short_composite

    sv = _SV_DATA.get(ticker, [])
    si = _SI_DATA.get(ticker, [])
    ftd = _FTD_DATA.get(ticker, [])
    return short_composite.compute_short_composite(sv, si, ftd)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture()
def mock_screener_adapters():
    """Patch all screener adapter calls so tests never hit real APIs."""
    with (
        patch(
            "agora.adapters.finra_short_volume_adapter.fetch_short_volume",
            side_effect=_sv_side_effect,
        ) as mock_sv,
        patch(
            "agora.adapters.yahoo_short_adapter.fetch_short_interest",
            side_effect=_si_side_effect,
        ) as mock_si,
        patch(
            "agora.adapters.sec_ftd_adapter.fetch_ftd_data",
            side_effect=_ftd_side_effect,
        ) as mock_ftd,
    ):
        yield {
            "short_volume": mock_sv,
            "short_interest": mock_si,
            "ftd": mock_ftd,
        }


@pytest.fixture()
def client(mock_screener_adapters):
    """Create a TestClient with all adapters mocked."""
    with (
        patch(
            "agora.adapters.treasury_adapter.fetch_yields",
            return_value=[],
        ),
        patch(
            "agora.adapters.fred_adapter.fetch_series",
            return_value=[],
        ),
    ):
        from agora.api.routes import create_app

        app = create_app()
        with TestClient(app) as tc:
            yield tc


# =====================================================================
# GET /api/screener -- basic happy path
# =====================================================================


class TestScreenerBasic:
    """GET /api/screener happy path."""

    def test_returns_200(self, client):
        resp = client.get("/api/screener", params={"tickers": "GME,AAPL"})
        assert resp.status_code == 200

    def test_response_shape(self, client):
        body = client.get(
            "/api/screener", params={"tickers": "GME,AAPL"}
        ).json()
        assert "data" in body
        assert "errors" in body
        assert "count" in body
        assert isinstance(body["data"], list)
        assert isinstance(body["errors"], list)
        assert body["count"] == len(body["data"])

    def test_item_shape(self, client):
        body = client.get(
            "/api/screener", params={"tickers": "GME"}
        ).json()
        assert len(body["data"]) == 1
        item = body["data"][0]
        for key in ("symbol", "composite_score", "signal", "components"):
            assert key in item

    def test_json_content_type(self, client):
        resp = client.get("/api/screener", params={"tickers": "GME"})
        assert "application/json" in resp.headers.get("content-type", "")


# =====================================================================
# GET /api/screener -- sorting
# =====================================================================


class TestScreenerSorting:
    """Results should be sorted by composite_score descending."""

    def test_sorted_descending(self, client):
        body = client.get(
            "/api/screener", params={"tickers": "AAPL,GME,AMC"}
        ).json()
        scores = [item["composite_score"] for item in body["data"]]
        assert scores == sorted(scores, reverse=True)

    def test_gme_ranks_above_aapl(self, client):
        body = client.get(
            "/api/screener", params={"tickers": "AAPL,GME"}
        ).json()
        symbols = [item["symbol"] for item in body["data"]]
        assert symbols[0] == "GME"
        assert symbols[1] == "AAPL"


# =====================================================================
# GET /api/screener -- per-ticker error handling
# =====================================================================


class TestScreenerErrorHandling:
    """Per-ticker failures should not abort the request."""

    def test_partial_failure(self, client, mock_screener_adapters):
        """If _score_ticker raises for one symbol, others still return."""
        def _mock_score(t):
            if t == "BADTK":
                raise RuntimeError("boom")
            return _original_score_ticker_via_mock(t)

        with patch("agora.api.screener._score_ticker", side_effect=_mock_score):
            resp = client.get(
                "/api/screener", params={"tickers": "GME,BADTK"}
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert len(body["errors"]) == 1
        assert body["errors"][0]["symbol"] == "BADTK"

    def test_all_tickers_fail(self, client):
        """If every ticker fails, return 200 with empty data."""
        with patch(
            "agora.api.screener._score_ticker",
            side_effect=RuntimeError("total failure"),
        ):
            resp = client.get(
                "/api/screener", params={"tickers": "X,Y,Z"}
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert len(body["errors"]) == 3


# =====================================================================
# GET /api/screener -- validation
# =====================================================================


class TestScreenerValidation:
    """Input validation edge cases."""

    def test_missing_tickers_param_returns_422(self, client):
        resp = client.get("/api/screener")
        assert resp.status_code == 422

    def test_empty_tickers_returns_400(self, client):
        resp = client.get("/api/screener", params={"tickers": "  ,  , "})
        assert resp.status_code == 400

    def test_too_many_tickers_returns_400(self, client):
        symbols = ",".join(f"T{i}" for i in range(25))
        resp = client.get("/api/screener", params={"tickers": symbols})
        assert resp.status_code == 400

    def test_single_ticker(self, client):
        body = client.get(
            "/api/screener", params={"tickers": "GME"}
        ).json()
        assert body["count"] == 1
        assert body["data"][0]["symbol"] == "GME"

    def test_tickers_uppercased(self, client):
        body = client.get(
            "/api/screener", params={"tickers": "gme,aapl"}
        ).json()
        symbols = {item["symbol"] for item in body["data"]}
        assert symbols == {"GME", "AAPL"}

    def test_whitespace_trimmed(self, client):
        body = client.get(
            "/api/screener", params={"tickers": " GME , AAPL "}
        ).json()
        assert body["count"] == 2


# =====================================================================
# GET /api/screener -- adapter-level fault tolerance
# =====================================================================


class TestScreenerAdapterFaultTolerance:
    """Individual adapter failures should not prevent composite scoring."""

    def test_short_volume_adapter_fails(self, client, mock_screener_adapters):
        """Composite should still compute with SI + FTD when SV fails."""
        mock_screener_adapters["short_volume"].side_effect = RuntimeError("sv fail")
        resp = client.get("/api/screener", params={"tickers": "GME"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert "composite_score" in body["data"][0]

    def test_all_adapters_fail_produces_zero_score(
        self, client, mock_screener_adapters
    ):
        """All adapters failing yields score 0 but no error entry."""
        for mock in mock_screener_adapters.values():
            mock.side_effect = RuntimeError("fail")
        resp = client.get("/api/screener", params={"tickers": "GME"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["data"][0]["composite_score"] == 0.0
        assert len(body["errors"]) == 0
