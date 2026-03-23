"""Tests for the short_intel API routes.

Tests use mocked adapters (no real HTTP calls). Validates response
status codes and JSON body shapes for all short intel endpoints.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agora.schemas import Quote, ShortData, Transaction


# ---------------------------------------------------------------------------
# Fake data builders
# ---------------------------------------------------------------------------

SYMBOL = "GME"


def _make_quotes() -> list[Quote]:
    """Return fake quote data."""
    return [
        Quote(
            symbol=SYMBOL,
            date=date(2024, 3, 18),
            open=25.0,
            high=27.0,
            low=24.5,
            close=26.5,
            volume=10_000_000,
        ),
        Quote(
            symbol=SYMBOL,
            date=date(2024, 3, 19),
            open=26.5,
            high=28.0,
            low=26.0,
            close=27.0,
            volume=12_000_000,
        ),
    ]


def _make_short_volume() -> list[ShortData]:
    """Return fake FINRA short volume data."""
    return [
        ShortData(
            symbol=SYMBOL,
            date=date(2024, 3, 18),
            data_type="short_volume",
            value=5500000,
            total_for_ratio=10000000,
            source="FINRA",
        ),
        ShortData(
            symbol=SYMBOL,
            date=date(2024, 3, 19),
            data_type="short_volume",
            value=6000000,
            total_for_ratio=12000000,
            source="FINRA",
        ),
    ]


def _make_short_interest() -> list[ShortData]:
    """Return fake Yahoo short interest data."""
    return [
        ShortData(
            symbol=SYMBOL,
            date=date(2024, 3, 15),
            data_type="short_interest",
            value=15000000,
            source="Yahoo Finance",
        ),
        ShortData(
            symbol=SYMBOL,
            date=date(2024, 3, 15),
            data_type="short_ratio",
            value=2.5,
            source="Yahoo Finance",
        ),
    ]


def _make_ftd() -> list[ShortData]:
    """Return fake SEC FTD data."""
    return [
        ShortData(
            symbol=SYMBOL,
            date=date(2024, 3, 18),
            data_type="ftd",
            value=150000,
            total_for_ratio=25.0,
            source="SEC",
        ),
        ShortData(
            symbol=SYMBOL,
            date=date(2024, 3, 19),
            data_type="ftd",
            value=200000,
            total_for_ratio=26.0,
            source="SEC",
        ),
    ]


def _make_insider_trades() -> list[Transaction]:
    """Return fake insider trade data."""
    return [
        Transaction(
            date=date(2024, 3, 15),
            entity="John Doe",
            action="Buy",
            amount=10_000,
            context={"symbol": SYMBOL, "title": "CEO", "price": 24.0},
        ),
        Transaction(
            date=date(2024, 3, 18),
            entity="Jane Smith",
            action="Sell",
            amount=5_000,
            context={"symbol": SYMBOL, "title": "CFO", "price": 26.5},
        ),
    ]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_short_adapters():
    """Patch all short intel adapter calls so tests never hit real APIs."""
    with (
        patch(
            "agora.adapters.yahoo_quotes_adapter.fetch_quotes",
            return_value=_make_quotes(),
        ) as mock_quotes,
        patch(
            "agora.adapters.finra_short_volume_adapter.fetch_short_volume",
            return_value=_make_short_volume(),
        ) as mock_sv,
        patch(
            "agora.adapters.yahoo_short_adapter.fetch_short_interest",
            return_value=_make_short_interest(),
        ) as mock_si,
        patch(
            "agora.adapters.sec_ftd_adapter.fetch_ftd_data",
            return_value=_make_ftd(),
        ) as mock_ftd,
        patch(
            "agora.adapters.edgar_insider_adapter.fetch_insider_trades",
            return_value=_make_insider_trades(),
        ) as mock_insider,
    ):
        yield {
            "quotes": mock_quotes,
            "short_volume": mock_sv,
            "short_interest": mock_si,
            "ftd": mock_ftd,
            "insider": mock_insider,
        }


@pytest.fixture()
def client(mock_short_adapters):
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

# ======================================================================
# GET /api/symbol/{ticker}/quote
# ======================================================================


class TestQuote:
    """GET /api/symbol/{ticker}/quote"""

    def test_returns_200(self, client):
        resp = client.get("/api/symbol/GME/quote")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        body = client.get("/api/symbol/GME/quote").json()
        assert "data" in body
        assert "count" in body
        assert isinstance(body["data"], list)
        assert body["count"] == len(body["data"])

    def test_item_shape(self, client):
        body = client.get("/api/symbol/GME/quote").json()
        assert len(body["data"]) > 0
        item = body["data"][0]
        for key in ("symbol", "date", "open", "high", "low", "close", "volume"):
            assert key in item

    def test_invalid_date_returns_400(self, client):
        resp = client.get(
            "/api/symbol/GME/quote",
            params={"start_date": "bad"},
        )
        assert resp.status_code == 400

    def test_adapter_error_returns_502(self, client, mock_short_adapters):
        mock_short_adapters["quotes"].side_effect = RuntimeError("upstream")
        resp = client.get("/api/symbol/GME/quote")
        assert resp.status_code == 502

# =======================================================================
# GET /api/symbol/{ticker}/short-volume
# =======================================================================


class TestShortVolume:
    """GET /api/symbol/{ticker}/short-volume"""

    def test_returns_200(self, client):
        resp = client.get("/api/symbol/GME/short-volume")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        body = client.get("/api/symbol/GME/short-volume").json()
        assert "data" in body
        assert "count" in body
        assert body["count"] == len(body["data"])

    def test_item_shape(self, client):
        body = client.get("/api/symbol/GME/short-volume").json()
        assert len(body["data"]) > 0
        item = body["data"][0]
        for key in ("symbol", "date", "data_type", "value", "source"):
            assert key in item

    def test_adapter_error_returns_502(self, client, mock_short_adapters):
        mock_short_adapters["short_volume"].side_effect = RuntimeError("fail")
        resp = client.get("/api/symbol/GME/short-volume")
        assert resp.status_code == 502


# =======================================================================
# GET /api/symbol/{ticker}/short-interest
# =======================================================================


class TestShortInterest:
    """GET /api/symbol/{ticker}/short-interest"""

    def test_returns_200(self, client):
        resp = client.get("/api/symbol/GME/short-interest")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        body = client.get("/api/symbol/GME/short-interest").json()
        assert "data" in body
        assert "count" in body
        assert body["count"] == len(body["data"])

    def test_item_shape(self, client):
        body = client.get("/api/symbol/GME/short-interest").json()
        assert len(body["data"]) > 0
        item = body["data"][0]
        for key in ("symbol", "date", "data_type", "value", "source"):
            assert key in item

    def test_adapter_error_returns_502(self, client, mock_short_adapters):
        mock_short_adapters["short_interest"].side_effect = RuntimeError("fail")
        resp = client.get("/api/symbol/GME/short-interest")
        assert resp.status_code == 502


# =======================================================================
# GET /api/symbol/{ticker}/ftd
# =======================================================================


class TestFtd:
    """GET /api/symbol/{ticker}/ftd"""

    def test_returns_200(self, client):
        resp = client.get("/api/symbol/GME/ftd")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        body = client.get("/api/symbol/GME/ftd").json()
        assert "data" in body
        assert "count" in body
        assert body["count"] == len(body["data"])

    def test_item_shape(self, client):
        body = client.get("/api/symbol/GME/ftd").json()
        assert len(body["data"]) > 0
        item = body["data"][0]
        for key in ("symbol", "date", "data_type", "value", "source"):
            assert key in item

    def test_adapter_error_returns_502(self, client, mock_short_adapters):
        mock_short_adapters["ftd"].side_effect = RuntimeError("fail")
        resp = client.get("/api/symbol/GME/ftd")
        assert resp.status_code == 502


# =======================================================================
# GET /api/symbol/{ticker}/insider-trades
# =======================================================================


class TestInsiderTrades:
    """GET /api/symbol/{ticker}/insider-trades"""

    def test_returns_200(self, client):
        resp = client.get("/api/symbol/GME/insider-trades")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        body = client.get("/api/symbol/GME/insider-trades").json()
        assert "data" in body
        assert "count" in body
        assert body["count"] == len(body["data"])

    def test_item_shape(self, client):
        body = client.get("/api/symbol/GME/insider-trades").json()
        assert len(body["data"]) > 0
        item = body["data"][0]
        for key in ("date", "entity", "action", "amount", "context"):
            assert key in item

    def test_adapter_error_returns_502(self, client, mock_short_adapters):
        mock_short_adapters["insider"].side_effect = RuntimeError("fail")
        resp = client.get("/api/symbol/GME/insider-trades")
        assert resp.status_code == 502


# =======================================================================
# GET /api/symbol/{ticker}/short-composite
# =======================================================================


class TestShortComposite:
    """GET /api/symbol/{ticker}/short-composite"""

    def test_returns_200(self, client):
        resp = client.get("/api/symbol/GME/short-composite")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        body = client.get("/api/symbol/GME/short-composite").json()
        assert "composite_score" in body
        assert "signal" in body
        assert "components" in body
        assert 0 <= body["composite_score"] <= 100
        assert body["signal"] in ("low", "moderate", "high", "extreme")

    def test_tolerates_adapter_failures(self, client, mock_short_adapters):
        """Composite endpoint should still work even if some adapters fail."""
        mock_short_adapters["short_volume"].side_effect = RuntimeError("fail")
        mock_short_adapters["short_interest"].side_effect = RuntimeError("fail")
        resp = client.get("/api/symbol/GME/short-composite")
        assert resp.status_code == 200
        body = resp.json()
        assert "composite_score" in body


# =======================================================================
# GET /api/symbol/{ticker}/divergences
# =======================================================================


class TestDivergences:
    """GET /api/symbol/{ticker}/divergences"""

    def test_returns_200(self, client):
        resp = client.get("/api/symbol/GME/divergences")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        body = client.get("/api/symbol/GME/divergences").json()
        assert "data" in body
        assert "count" in body
        assert isinstance(body["data"], list)
        assert body["count"] == len(body["data"])

    def test_tolerates_adapter_failures(self, client, mock_short_adapters):
        mock_short_adapters["short_volume"].side_effect = RuntimeError("fail")
        resp = client.get("/api/symbol/GME/divergences")
        assert resp.status_code == 200


# =======================================================================
# GET /api/symbol/{ticker}/summary
# =======================================================================


class TestSummary:
    """GET /api/symbol/{ticker}/summary"""

    def test_returns_200(self, client):
        resp = client.get("/api/symbol/GME/summary")
        assert resp.status_code == 200

    def test_response_has_all_sections(self, client):
        body = client.get("/api/symbol/GME/summary").json()
        assert body["symbol"] == "GME"
        for key in (
            "quote",
            "short_volume",
            "short_interest",
            "ftd",
            "insider_trades",
            "composite",
            "divergences",
        ):
            assert key in body

    def test_quote_section_populated(self, client):
        body = client.get("/api/symbol/GME/summary").json()
        assert len(body["quote"]) > 0

    def test_composite_section_shape(self, client):
        body = client.get("/api/symbol/GME/summary").json()
        composite = body["composite"]
        assert "composite_score" in composite
        assert "signal" in composite

    def test_tolerates_all_adapter_failures(self, client, mock_short_adapters):
        """Summary should still return 200 even if all adapters fail."""
        for mock in mock_short_adapters.values():
            mock.side_effect = RuntimeError("fail")
        resp = client.get("/api/symbol/GME/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "GME"
        assert body["quote"] == []
        assert body["short_volume"] == []


# =======================================================================
# Cross-cutting -- JSON content type
# =======================================================================


class TestContentType:
    """All short intel routes should return application/json."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/symbol/GME/quote",
            "/api/symbol/GME/short-volume",
            "/api/symbol/GME/short-interest",
            "/api/symbol/GME/ftd",
            "/api/symbol/GME/insider-trades",
            "/api/symbol/GME/short-composite",
            "/api/symbol/GME/divergences",
            "/api/symbol/GME/summary",
        ],
    )
    def test_json_content_type(self, client, path):
        resp = client.get(path)
        assert "application/json" in resp.headers.get("content-type", "")
