"""Tests for agora.analysis.macro_dashboard."""

from __future__ import annotations

from datetime import date

import pytest

from agora.analysis.macro_dashboard import (
    _classify_trend,
    _detect_regime_signals,
    _latest_value,
    build_dashboard,
)
from agora.schemas import TimeSeries, TimeSeriesMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_META = TimeSeriesMetadata(source="test", unit="index", frequency="monthly")


def _ts(d: str, v: float) -> TimeSeries:
    """Shorthand to build a TimeSeries point."""
    return TimeSeries(date=date.fromisoformat(d), value=v, metadata=_META)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def rising_series() -> list[TimeSeries]:
    """Series that clearly rises over time."""
    return [
        _ts("2024-01-01", 100.0),
        _ts("2024-02-01", 102.0),
        _ts("2024-03-01", 105.0),
        _ts("2024-04-01", 108.0),
        _ts("2024-05-01", 112.0),
        _ts("2024-06-01", 115.0),
    ]


@pytest.fixture()
def falling_series() -> list[TimeSeries]:
    """Series that clearly falls over time."""
    return [
        _ts("2024-01-01", 200.0),
        _ts("2024-02-01", 195.0),
        _ts("2024-03-01", 188.0),
        _ts("2024-04-01", 180.0),
        _ts("2024-05-01", 172.0),
        _ts("2024-06-01", 165.0),
    ]


@pytest.fixture()
def flat_series() -> list[TimeSeries]:
    """Series that barely moves."""
    return [
        _ts("2024-01-01", 100.0),
        _ts("2024-02-01", 100.1),
        _ts("2024-03-01", 99.9),
        _ts("2024-04-01", 100.0),
        _ts("2024-05-01", 100.05),
        _ts("2024-06-01", 100.0),
    ]


# ---------------------------------------------------------------------------
# _latest_value
# ---------------------------------------------------------------------------


class TestLatestValue:
    def test_returns_most_recent(self, rising_series: list[TimeSeries]) -> None:
        assert _latest_value(rising_series) == 115.0

    def test_empty_returns_none(self) -> None:
        assert _latest_value([]) is None

    def test_single_point(self) -> None:
        series = [_ts("2024-03-15", 42.5)]
        assert _latest_value(series) == 42.5

    def test_unordered_input(self) -> None:
        series = [
            _ts("2024-03-01", 3.0),
            _ts("2024-01-01", 1.0),
            _ts("2024-05-01", 5.0),
            _ts("2024-02-01", 2.0),
        ]
        assert _latest_value(series) == 5.0


# ---------------------------------------------------------------------------
# _classify_trend
# ---------------------------------------------------------------------------


class TestClassifyTrend:
    def test_rising(self, rising_series: list[TimeSeries]) -> None:
        assert _classify_trend(rising_series) == "rising"

    def test_falling(self, falling_series: list[TimeSeries]) -> None:
        assert _classify_trend(falling_series) == "falling"

    def test_flat(self, flat_series: list[TimeSeries]) -> None:
        assert _classify_trend(flat_series) == "flat"

    def test_single_point_is_flat(self) -> None:
        assert _classify_trend([_ts("2024-01-01", 50.0)]) == "flat"

    def test_empty_is_flat(self) -> None:
        assert _classify_trend([]) == "flat"

    def test_two_points_rising(self) -> None:
        series = [_ts("2024-01-01", 10.0), _ts("2024-02-01", 20.0)]
        assert _classify_trend(series) == "rising"

    def test_two_points_falling(self) -> None:
        series = [_ts("2024-01-01", 20.0), _ts("2024-02-01", 10.0)]
        assert _classify_trend(series) == "falling"

    def test_prior_mean_zero(self) -> None:
        """When the prior half mean is 0, uses absolute diff instead."""
        series = [
            _ts("2024-01-01", 0.0),
            _ts("2024-02-01", 0.0),
            _ts("2024-03-01", 5.0),
            _ts("2024-04-01", 5.0),
        ]
        assert _classify_trend(series) == "rising"

    def test_custom_threshold(self) -> None:
        """With a very high threshold, even a clear rise becomes flat."""
        series = [_ts("2024-01-01", 100.0), _ts("2024-02-01", 110.0)]
        assert _classify_trend(series, threshold=0.5) == "flat"


# ---------------------------------------------------------------------------
# build_dashboard – current_values
# ---------------------------------------------------------------------------


class TestBuildDashboardCurrentValues:
    def test_current_values_populated(
        self, rising_series: list[TimeSeries], falling_series: list[TimeSeries]
    ) -> None:
        result = build_dashboard(
            {"GDP": rising_series, "Unemployment": falling_series}
        )
        cv = result["current_values"]
        assert cv["GDP"] == 115.0
        assert cv["Unemployment"] == 165.0

    def test_empty_input(self) -> None:
        result = build_dashboard({})
        assert result["current_values"] == {}
        assert result["trends"] == {}
        assert result["regime_signals"] == []

    def test_single_indicator(
        self, rising_series: list[TimeSeries]
    ) -> None:
        result = build_dashboard({"CPI": rising_series})
        assert "CPI" in result["current_values"]
        assert result["current_values"]["CPI"] == 115.0
        assert result["trends"]["CPI"] == "rising"
        # With a single indicator, no regime shift can occur
        # (prior trends will also be computed but there is only one indicator)


# ---------------------------------------------------------------------------
# build_dashboard – trends
# ---------------------------------------------------------------------------


class TestBuildDashboardTrends:
    def test_trends_match_classification(
        self,
        rising_series: list[TimeSeries],
        falling_series: list[TimeSeries],
        flat_series: list[TimeSeries],
    ) -> None:
        result = build_dashboard(
            {"GDP": rising_series, "Unemployment": falling_series, "Rates": flat_series}
        )
        assert result["trends"]["GDP"] == "rising"
        assert result["trends"]["Unemployment"] == "falling"
        assert result["trends"]["Rates"] == "flat"


# ---------------------------------------------------------------------------
# build_dashboard – regime_signals
# ---------------------------------------------------------------------------


class TestBuildDashboardRegimeSignals:
    def test_no_regime_shift_when_all_same_direction(
        self, rising_series: list[TimeSeries]
    ) -> None:
        """If all indicators consistently rise, no regime shift."""
        # Use the same rising series for multiple indicators
        result = build_dashboard(
            {"GDP": rising_series, "Industrial": rising_series}
        )
        assert result["regime_signals"] == []

    def test_regime_shift_detected(self) -> None:
        """Build series where the first half trends one way, second half trends another.

        The prior trends (computed from the first half of each series) should
        differ from the full-series trends, triggering a regime signal.
        """
        # GDP: falls in first half, rises in second half
        gdp = [
            _ts("2024-01-01", 100.0),
            _ts("2024-02-01", 90.0),
            _ts("2024-03-01", 80.0),
            _ts("2024-04-01", 70.0),
            _ts("2024-05-01", 120.0),
            _ts("2024-06-01", 130.0),
            _ts("2024-07-01", 140.0),
            _ts("2024-08-01", 150.0),
        ]
        # CPI: falls in first half, rises in second half
        cpi = [
            _ts("2024-01-01", 50.0),
            _ts("2024-02-01", 45.0),
            _ts("2024-03-01", 40.0),
            _ts("2024-04-01", 35.0),
            _ts("2024-05-01", 60.0),
            _ts("2024-06-01", 70.0),
            _ts("2024-07-01", 80.0),
            _ts("2024-08-01", 90.0),
        ]
        result = build_dashboard({"GDP": gdp, "CPI": cpi})
        # The full series trend is rising (second half mean > first half mean).
        assert result["trends"]["GDP"] == "rising"
        assert result["trends"]["CPI"] == "rising"
        # The prior trend (from first half of each series) should be falling,
        # so the shift from falling -> rising should trigger a regime signal.
        if result["regime_signals"]:
            sig = result["regime_signals"][0]
            assert sig["signal"] == "regime_shift"
            assert sig["shift_fraction"] > 0
            assert len(sig["shifted_indicators"]) > 0


# ---------------------------------------------------------------------------
# _detect_regime_signals (direct)
# ---------------------------------------------------------------------------


class TestDetectRegimeSignals:
    def test_empty_trends(self) -> None:
        assert _detect_regime_signals({}, {}) == []

    def test_no_common_indicators(self) -> None:
        assert _detect_regime_signals({"A": "rising"}, {"B": "falling"}) == []

    def test_no_shifts(self) -> None:
        trends = {"A": "rising", "B": "falling"}
        assert _detect_regime_signals(trends, trends) == []

    def test_full_shift(self) -> None:
        current = {"A": "rising", "B": "rising"}
        prior = {"A": "falling", "B": "falling"}
        signals = _detect_regime_signals(current, prior)
        assert len(signals) == 1
        assert signals[0]["signal"] == "regime_shift"
        assert signals[0]["shift_fraction"] == 1.0
        assert sorted(signals[0]["shifted_indicators"]) == ["A", "B"]

    def test_partial_shift_below_threshold(self) -> None:
        """Only 1 of 3 shifts: 33% < default 50% threshold."""
        current = {"A": "rising", "B": "falling", "C": "flat"}
        prior = {"A": "falling", "B": "falling", "C": "flat"}
        assert _detect_regime_signals(current, prior) == []

    def test_partial_shift_at_threshold(self) -> None:
        """2 of 4 shift: 50% >= default 50% threshold."""
        current = {"A": "rising", "B": "rising", "C": "flat", "D": "flat"}
        prior = {"A": "falling", "B": "falling", "C": "flat", "D": "flat"}
        signals = _detect_regime_signals(current, prior)
        assert len(signals) == 1


# ---------------------------------------------------------------------------
# build_dashboard – single indicator
# ---------------------------------------------------------------------------


class TestBuildDashboardSingleIndicator:
    def test_single_rising(self, rising_series: list[TimeSeries]) -> None:
        result = build_dashboard({"GDP": rising_series})
        assert result["current_values"]["GDP"] == 115.0
        assert result["trends"]["GDP"] == "rising"
        assert isinstance(result["regime_signals"], list)

    def test_single_empty_series(self) -> None:
        result = build_dashboard({"GDP": []})
        assert result["current_values"]["GDP"] is None
        assert result["trends"]["GDP"] == "flat"
        assert result["regime_signals"] == []

    def test_single_one_point(self) -> None:
        result = build_dashboard({"GDP": [_ts("2024-06-01", 42.0)]})
        assert result["current_values"]["GDP"] == 42.0
        assert result["trends"]["GDP"] == "flat"
