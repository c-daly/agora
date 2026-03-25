"""Mocked tests for agora.adapters.bls_adapter."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from agora.adapters.bls_adapter import (
    BLS_BASE_URL,
    _check_response,
    _infer_frequency,
    _parse_observations,
    _period_to_date,
    fetch_bls_series,
)
from agora.schemas import TimeSeries


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_bls_response(series_id: str, data: list[dict]) -> dict:
    """Build a minimal BLS API v2 JSON response."""
    return {
        "status": "REQUEST_SUCCEEDED",
        "responseTime": 42,
        "message": [],
        "Results": {
            "series": [
                {
                    "seriesID": series_id,
                    "data": data,
                }
            ]
        },
    }


SAMPLE_MONTHLY_OBS = [
    {"year": "2024", "period": "M03", "value": "300.0", "footnotes": []},
    {"year": "2024", "period": "M02", "value": "200.0", "footnotes": []},
    {"year": "2024", "period": "M01", "value": "100.0", "footnotes": []},
]


# ---------------------------------------------------------------------------
# _period_to_date
# ---------------------------------------------------------------------------


class TestPeriodToDate:
    def test_monthly(self):
        assert _period_to_date("2024", "M01") == date(2024, 1, 1)
        assert _period_to_date("2024", "M12") == date(2024, 12, 1)

    def test_monthly_m13_skipped(self):
        assert _period_to_date("2024", "M13") is None

    def test_quarterly(self):
        assert _period_to_date("2024", "Q01") == date(2024, 1, 1)
        assert _period_to_date("2024", "Q02") == date(2024, 4, 1)
        assert _period_to_date("2024", "Q03") == date(2024, 7, 1)
        assert _period_to_date("2024", "Q04") == date(2024, 10, 1)

    def test_annual(self):
        assert _period_to_date("2024", "A01") == date(2024, 1, 1)

    def test_bad_year(self):
        assert _period_to_date("abc", "M01") is None

    def test_unknown_period(self):
        assert _period_to_date("2024", "X99") is None


# ---------------------------------------------------------------------------
# _infer_frequency
# ---------------------------------------------------------------------------


class TestInferFrequency:
    def test_monthly(self):
        assert _infer_frequency("M01") == "Monthly"

    def test_quarterly(self):
        assert _infer_frequency("Q03") == "Quarterly"

    def test_annual(self):
        assert _infer_frequency("A01") == "Annual"

    def test_unknown(self):
        assert _infer_frequency("Z99") == "Unknown"


# ---------------------------------------------------------------------------
# _parse_observations
# ---------------------------------------------------------------------------


class TestParseObservations:
    def test_returns_chronological_order(self):
        result = _parse_observations(SAMPLE_MONTHLY_OBS)
        assert len(result) == 3
        assert result[0].date == date(2024, 1, 1)
        assert result[1].date == date(2024, 2, 1)
        assert result[2].date == date(2024, 3, 1)

    def test_values_parsed(self):
        result = _parse_observations(SAMPLE_MONTHLY_OBS)
        assert result[0].value == 100.0
        assert result[2].value == 300.0

    def test_metadata_source_is_bls(self):
        result = _parse_observations(SAMPLE_MONTHLY_OBS)
        for ts in result:
            assert ts.metadata.source == "BLS"
            assert ts.metadata.frequency == "Monthly"

    def test_skips_bad_values(self):
        bad_obs = [{"year": "2024", "period": "M01", "value": "N/A", "footnotes": []}]
        result = _parse_observations(bad_obs)
        assert result == []

    def test_skips_m13_annual_average(self):
        obs = [{"year": "2024", "period": "M13", "value": "150.0", "footnotes": []}]
        result = _parse_observations(obs)
        assert result == []


# ---------------------------------------------------------------------------
# _check_response
# ---------------------------------------------------------------------------


class TestCheckResponse:
    def test_200_passes(self):
        resp = MagicMock(status_code=200)
        _check_response(resp, "TEST")  # should not raise

    def test_400_raises_value_error(self):
        resp = MagicMock(status_code=400)
        with pytest.raises(ValueError, match="bad request"):
            _check_response(resp, "TEST")

    def test_403_raises_permission_error(self):
        resp = MagicMock(status_code=403)
        with pytest.raises(PermissionError, match="unauthorized"):
            _check_response(resp, "TEST")

    def test_500_raises_runtime_error(self):
        resp = MagicMock(status_code=500)
        with pytest.raises(RuntimeError, match="500"):
            _check_response(resp, "TEST")


# ---------------------------------------------------------------------------
# fetch_bls_series (mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchBlsSeries:
    @patch("agora.adapters.bls_adapter.requests.post")
    def test_basic_fetch(self, mock_post):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = _make_bls_response("CES0000000001", SAMPLE_MONTHLY_OBS)
        mock_post.return_value = mock_resp

        result = fetch_bls_series("CES0000000001")

        assert len(result) == 3
        assert all(isinstance(r, TimeSeries) for r in result)
        assert result[0].date < result[-1].date
        mock_post.assert_called_once()

    @patch("agora.adapters.bls_adapter.requests.post")
    def test_payload_includes_years_when_given(self, mock_post):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = _make_bls_response("CES0000000001", [])
        mock_post.return_value = mock_resp

        fetch_bls_series("CES0000000001", start_year=2020, end_year=2024)

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1]["json"]
        assert payload["startyear"] == "2020"
        assert payload["endyear"] == "2024"

    @patch.dict("os.environ", {"BLS_API_KEY": "test-key-123"})
    @patch("agora.adapters.bls_adapter.requests.post")
    def test_api_key_included_when_set(self, mock_post):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = _make_bls_response("CUUR0000SA0", [])
        mock_post.return_value = mock_resp

        fetch_bls_series("CUUR0000SA0")

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1]["json"]
        assert payload["registrationkey"] == "test-key-123"

    @patch.dict("os.environ", {}, clear=True)
    @patch("agora.adapters.bls_adapter.requests.post")
    def test_no_api_key_when_unset(self, mock_post):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = _make_bls_response("CUUR0000SA0", [])
        mock_post.return_value = mock_resp

        fetch_bls_series("CUUR0000SA0")

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1]["json"]
        assert "registrationkey" not in payload

    @patch("agora.adapters.bls_adapter.requests.post")
    def test_api_error_status(self, mock_post):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "status": "REQUEST_NOT_PROCESSED",
            "responseTime": 10,
            "message": ["Invalid Series"],
            "Results": {},
        }
        mock_post.return_value = mock_resp

        with pytest.raises(RuntimeError, match="Invalid Series"):
            fetch_bls_series("INVALID")

    @patch("agora.adapters.bls_adapter.requests.post")
    def test_no_series_in_results(self, mock_post):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "status": "REQUEST_SUCCEEDED",
            "responseTime": 10,
            "message": [],
            "Results": {"series": []},
        }
        mock_post.return_value = mock_resp

        with pytest.raises(ValueError, match="No series found"):
            fetch_bls_series("NOPE")

    @patch("agora.adapters.bls_adapter.requests.post")
    def test_posts_to_bls_url(self, mock_post):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = _make_bls_response("X", [])
        mock_post.return_value = mock_resp

        fetch_bls_series("X")

        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == BLS_BASE_URL
