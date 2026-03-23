"""Eval tests for agora.api.routes — FastAPI API layer.

Tests use mocked adapters (no real HTTP calls). Every test validates
response status codes and JSON body shapes per constraints.yaml.
"""

from datetime import date

import pytest


# ======================================================================
# GET /api/yields
# ======================================================================

class TestYields:
    """GET /api/yields — treasury yield time-series data."""

    def test_yields_returns_200(self, client):
        resp = client.get("/api/yields")
        assert resp.status_code == 200

    def test_yields_response_has_data_and_count(self, client):
        body = client.get("/api/yields").json()
        assert "data" in body
        assert "count" in body
        assert isinstance(body["data"], list)
        assert isinstance(body["count"], int)
        assert body["count"] == len(body["data"])

    def test_yields_item_shape(self, client):
        body = client.get("/api/yields").json()
        assert len(body["data"]) > 0
        item = body["data"][0]
        for key in ("date", "value", "maturity", "source"):
            assert key in item, f"Missing key '{key}' in yield item"

    def test_yields_with_maturities_filter(self, client):
        resp = client.get("/api/yields", params={"maturities": "10yr"})
        assert resp.status_code == 200
        body = resp.json()
        for item in body["data"]:
            assert item["maturity"] == "10yr"

    def test_yields_with_date_range(self, client):
        resp = client.get(
            "/api/yields",
            params={"start_date": "2024-01-02", "end_date": "2024-01-02"},
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["data"]:
            assert item["date"] == "2024-01-02"

    def test_yields_invalid_date_returns_400(self, client):
        resp = client.get("/api/yields", params={"start_date": "not-a-date"})
        assert resp.status_code == 400
        body = resp.json()
        assert "detail" in body

    def test_yields_invalid_maturity_returns_400(self, client):
        resp = client.get("/api/yields", params={"maturities": "99yr"})
        assert resp.status_code == 400
        body = resp.json()
        assert "detail" in body


# ======================================================================
# GET /api/yields/curve
# ======================================================================

class TestYieldsCurve:
    """GET /api/yields/curve — latest yield curve snapshot."""

    def test_curve_returns_200(self, client):
        resp = client.get("/api/yields/curve")
        assert resp.status_code == 200

    def test_curve_response_shape(self, client):
        body = client.get("/api/yields/curve").json()
        assert "data" in body
        assert "as_of" in body
        assert isinstance(body["data"], dict)
        # as_of should be an ISO date string
        date.fromisoformat(body["as_of"])

    def test_curve_data_contains_maturities(self, client):
        body = client.get("/api/yields/curve").json()
        # Our mock has 2yr and 10yr
        assert len(body["data"]) > 0
        for key, val in body["data"].items():
            assert isinstance(key, str)
            assert isinstance(val, (int, float))


# ======================================================================
# GET /api/yields/spread
# ======================================================================

class TestYieldsSpread:
    """GET /api/yields/spread — spread between two maturities."""

    def test_spread_returns_200(self, client):
        resp = client.get(
            "/api/yields/spread", params={"long": "10yr", "short": "2yr"}
        )
        assert resp.status_code == 200

    def test_spread_response_shape(self, client):
        body = client.get(
            "/api/yields/spread", params={"long": "10yr", "short": "2yr"}
        ).json()
        assert "data" in body
        assert "long" in body
        assert "short" in body
        assert "count" in body
        assert isinstance(body["data"], list)
        assert body["long"] == "10yr"
        assert body["short"] == "2yr"
        assert body["count"] == len(body["data"])

    def test_spread_item_shape(self, client):
        body = client.get(
            "/api/yields/spread", params={"long": "10yr", "short": "2yr"}
        ).json()
        if body["data"]:
            item = body["data"][0]
            assert "date" in item
            assert "spread" in item

    def test_spread_missing_long_returns_400(self, client):
        resp = client.get("/api/yields/spread", params={"short": "2yr"})
        assert resp.status_code in (400, 422)

    def test_spread_missing_short_returns_400(self, client):
        resp = client.get("/api/yields/spread", params={"long": "10yr"})
        assert resp.status_code in (400, 422)

    def test_spread_missing_both_returns_400(self, client):
        resp = client.get("/api/yields/spread")
        assert resp.status_code in (400, 422)


# ======================================================================
# GET /api/yields/inversions
# ======================================================================

class TestYieldsInversions:
    """GET /api/yields/inversions — detected yield curve inversions."""

    def test_inversions_returns_200(self, client):
        resp = client.get("/api/yields/inversions")
        assert resp.status_code == 200

    def test_inversions_response_shape(self, client):
        body = client.get("/api/yields/inversions").json()
        assert "data" in body
        assert "count" in body
        assert isinstance(body["data"], list)
        assert body["count"] == len(body["data"])

    def test_inversions_item_shape_if_present(self, client):
        """If inversions exist, each item must have the required fields."""
        body = client.get("/api/yields/inversions").json()
        for item in body["data"]:
            assert "short_maturity" in item
            assert "long_maturity" in item
            assert "spread" in item


# ======================================================================
# GET /api/ftd
# ======================================================================

class TestFtd:
    """GET /api/ftd — SEC fails-to-deliver data."""

    def test_ftd_returns_200(self, client):
        resp = client.get("/api/ftd")
        assert resp.status_code == 200

    def test_ftd_response_has_data_and_count(self, client):
        body = client.get("/api/ftd").json()
        assert "data" in body
        assert "count" in body
        assert isinstance(body["data"], list)
        assert body["count"] == len(body["data"])

    def test_ftd_item_shape(self, client):
        body = client.get("/api/ftd").json()
        assert len(body["data"]) > 0
        item = body["data"][0]
        for key in ("symbol", "date", "value", "data_type", "source"):
            assert key in item, f"Missing key '{key}' in FTD item"

    def test_ftd_with_symbol_filter(self, client):
        resp = client.get("/api/ftd", params={"symbol": "GME"})
        assert resp.status_code == 200
        body = resp.json()
        for item in body["data"]:
            assert item["symbol"].upper() == "GME"

    def test_ftd_with_date_range(self, client):
        resp = client.get(
            "/api/ftd",
            params={"start_date": "2024-01-02", "end_date": "2024-01-02"},
        )
        assert resp.status_code == 200

    def test_ftd_invalid_date_returns_400(self, client):
        resp = client.get("/api/ftd", params={"start_date": "bad"})
        assert resp.status_code == 400
        body = resp.json()
        assert "detail" in body


# ======================================================================
# GET /api/fred
# ======================================================================

class TestFred:
    """GET /api/fred — FRED economic data series."""

    def test_fred_returns_200(self, client):
        resp = client.get("/api/fred", params={"series_id": "GDP"})
        assert resp.status_code == 200

    def test_fred_response_shape(self, client):
        body = client.get("/api/fred", params={"series_id": "GDP"}).json()
        assert "data" in body
        assert "series_id" in body
        assert "count" in body
        assert body["series_id"] == "GDP"
        assert isinstance(body["data"], list)
        assert body["count"] == len(body["data"])

    def test_fred_item_shape(self, client):
        body = client.get("/api/fred", params={"series_id": "GDP"}).json()
        assert len(body["data"]) > 0
        item = body["data"][0]
        for key in ("date", "value", "source"):
            assert key in item, f"Missing key '{key}' in FRED item"

    def test_fred_missing_series_id_returns_400_or_422(self, client):
        resp = client.get("/api/fred")
        assert resp.status_code in (400, 422)

    def test_fred_with_date_range(self, client):
        resp = client.get(
            "/api/fred",
            params={
                "series_id": "GDP",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
        )
        assert resp.status_code == 200

    def test_fred_invalid_date_returns_400(self, client):
        resp = client.get(
            "/api/fred",
            params={"series_id": "GDP", "start_date": "nope"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "detail" in body


# ======================================================================
# GET /api/glossary
# ======================================================================

class TestGlossary:
    """GET /api/glossary — full term listing."""

    def test_glossary_returns_200(self, client):
        resp = client.get("/api/glossary")
        assert resp.status_code == 200

    def test_glossary_response_shape(self, client):
        body = client.get("/api/glossary").json()
        assert "data" in body
        assert "count" in body
        assert isinstance(body["data"], list)
        assert body["count"] == len(body["data"])

    def test_glossary_item_has_term_and_description(self, client):
        body = client.get("/api/glossary").json()
        assert len(body["data"]) > 0
        for item in body["data"]:
            assert "term" in item
            assert "description" in item


# ======================================================================
# GET /api/glossary/{term}
# ======================================================================

class TestGlossaryTerm:
    """GET /api/glossary/{term} — single term lookup."""

    def test_term_lookup_returns_200(self, client):
        resp = client.get("/api/glossary/yield_curve")
        assert resp.status_code == 200

    def test_term_lookup_response_shape(self, client):
        body = client.get("/api/glossary/yield_curve").json()
        assert "term" in body
        assert "description" in body

    def test_term_lookup_not_found_returns_404(self, client):
        resp = client.get("/api/glossary/nonexistent_term_xyz")
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body

    def test_term_lookup_values_match(self, client, mock_glossary):
        _, glossary_data = mock_glossary
        body = client.get("/api/glossary/ftd").json()
        assert body["term"] == glossary_data["ftd"]["term"]
        assert body["description"] == glossary_data["ftd"]["description"]


# ======================================================================
# Error handling — adapter failures
# ======================================================================

class TestAdapterErrorHandling:
    """Routes must catch adapter exceptions and return structured errors."""

    def test_yields_adapter_error_returns_500_or_502(self, client, mock_adapters):
        mock_adapters["treasury"].side_effect = RuntimeError("upstream failure")
        resp = client.get("/api/yields")
        assert resp.status_code in (500, 502)
        body = resp.json()
        assert "detail" in body

    def test_fred_adapter_error_returns_500_or_502(self, client, mock_adapters):
        mock_adapters["fred"].side_effect = RuntimeError("upstream failure")
        resp = client.get("/api/fred", params={"series_id": "GDP"})
        assert resp.status_code in (500, 502)
        body = resp.json()
        assert "detail" in body

    def test_ftd_adapter_error_returns_500_or_502(self, client, mock_adapters):
        mock_adapters["ftd"].side_effect = RuntimeError("upstream failure")
        resp = client.get("/api/ftd")
        assert resp.status_code in (500, 502)
        body = resp.json()
        assert "detail" in body


# ======================================================================
# Cross-cutting — JSON content type
# ======================================================================

class TestContentType:
    """All responses should return application/json."""

    @pytest.mark.parametrize(
        "path,params",
        [
            ("/api/yields", {}),
            ("/api/yields/curve", {}),
            ("/api/yields/spread", {"long": "10yr", "short": "2yr"}),
            ("/api/yields/inversions", {}),
            ("/api/ftd", {}),
            ("/api/fred", {"series_id": "GDP"}),
            ("/api/glossary", {}),
            ("/api/glossary/yield_curve", {}),
        ],
    )
    def test_json_content_type(self, client, path, params):
        resp = client.get(path, params=params)
        assert "application/json" in resp.headers.get("content-type", "")
