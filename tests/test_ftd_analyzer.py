"""Tests for the ftd_analyzer analysis module."""

from __future__ import annotations

from datetime import date

import pytest

from agora.analysis.ftd_analyzer import (
    _persistence,
    _spike_days,
    _threshold_correlation,
    _trend,
    analyze_ftd,
)
from agora.schemas import ShortData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SYMBOL = "GME"


def _ftd(day: int, value: float, month: int = 3, year: int = 2026) -> ShortData:
    """Shorthand helper to build a single FTD ShortData entry."""
    return ShortData(
        symbol=SYMBOL,
        date=date(year, month, day),
        data_type="ftd",
        value=value,
        source="sec",
    )


@pytest.fixture()
def ftd_data_rising() -> list[ShortData]:
    """Ten days of FTD data with a rising trend (low first half, high second)."""
    # First half avg: (100+200+0+150+100) / 5 = 110
    # Second half avg: (300+400+500+350+450) / 5 = 400
    values = [100, 200, 0, 150, 100, 300, 400, 500, 350, 450]
    return [_ftd(day=1 + i, value=v) for i, v in enumerate(values)]


@pytest.fixture()
def ftd_data_falling() -> list[ShortData]:
    """Ten days of FTD data with a falling trend."""
    values = [500, 400, 450, 350, 300, 100, 50, 80, 0, 60]
    return [_ftd(day=1 + i, value=v) for i, v in enumerate(values)]


@pytest.fixture()
def ftd_data_flat() -> list[ShortData]:
    """Six days of FTD data that is roughly flat."""
    values = [100, 102, 98, 101, 99, 100]
    return [_ftd(day=1 + i, value=v) for i, v in enumerate(values)]


@pytest.fixture()
def ftd_data_with_spikes() -> list[ShortData]:
    """Data containing clear spikes (values >> 2x average)."""
    # avg = (100+100+100+100+100+100+100+100+900+100) / 10 = 180
    # threshold = 2 * 180 = 360 -> only day with 900 is a spike
    values = [100, 100, 100, 100, 100, 100, 100, 100, 900, 100]
    return [_ftd(day=1 + i, value=v) for i, v in enumerate(values)]


@pytest.fixture()
def ftd_data_all_zero() -> list[ShortData]:
    """Five days with zero FTDs."""
    return [_ftd(day=1 + i, value=0) for i in range(5)]


# ---------------------------------------------------------------------------
# _persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_empty(self):
        assert _persistence([]) == 0.0

    def test_all_nonzero(self):
        data = [_ftd(day=1 + i, value=100) for i in range(5)]
        assert _persistence(data) == 1.0

    def test_all_zero(self, ftd_data_all_zero: list[ShortData]):
        assert _persistence(ftd_data_all_zero) == 0.0

    def test_mixed(self, ftd_data_rising: list[ShortData]):
        # 9 out of 10 are nonzero (one zero at index 2)
        assert _persistence(ftd_data_rising) == 0.9

    def test_single_nonzero(self):
        data = [_ftd(day=1, value=500)]
        assert _persistence(data) == 1.0

    def test_single_zero(self):
        data = [_ftd(day=1, value=0)]
        assert _persistence(data) == 0.0


# ---------------------------------------------------------------------------
# _spike_days
# ---------------------------------------------------------------------------


class TestSpikeDays:
    def test_no_spikes_when_avg_zero(self):
        data = [_ftd(day=1, value=0)]
        assert _spike_days(data, 0.0) == []

    def test_detects_spike(self, ftd_data_with_spikes: list[ShortData]):
        avg = 180.0
        spikes = _spike_days(ftd_data_with_spikes, avg)
        assert len(spikes) == 1
        assert spikes[0]["value"] == 900
        assert spikes[0]["date"] == "2026-03-09"

    def test_no_spikes_when_uniform(self):
        data = [_ftd(day=1 + i, value=100) for i in range(5)]
        avg = 100.0
        spikes = _spike_days(data, avg)
        assert spikes == []

    def test_boundary_not_spike(self):
        """Value exactly at 2x avg is NOT a spike (must exceed, not equal)."""
        data = [_ftd(day=1, value=200)]
        spikes = _spike_days(data, 100.0)
        assert spikes == []

    def test_multiple_spikes(self):
        data = [_ftd(day=1 + i, value=v) for i, v in enumerate([50, 300, 50, 400])]
        avg = 200.0
        spikes = _spike_days(data, avg)
        assert len(spikes) == 0  # threshold is 400, so 300 and 400 are not > 400

    def test_multiple_spikes_lower_avg(self):
        data = [_ftd(day=1 + i, value=v) for i, v in enumerate([50, 300, 50, 500])]
        avg = 100.0  # threshold = 200
        spikes = _spike_days(data, avg)
        assert len(spikes) == 2


# ---------------------------------------------------------------------------
# _trend
# ---------------------------------------------------------------------------


class TestTrend:
    def test_empty(self):
        assert _trend([]) == "flat"

    def test_single_element(self):
        assert _trend([_ftd(day=1, value=100)]) == "flat"

    def test_rising(self, ftd_data_rising: list[ShortData]):
        assert _trend(ftd_data_rising) == "rising"

    def test_falling(self, ftd_data_falling: list[ShortData]):
        assert _trend(ftd_data_falling) == "falling"

    def test_flat(self, ftd_data_flat: list[ShortData]):
        assert _trend(ftd_data_flat) == "flat"

    def test_all_zero(self, ftd_data_all_zero: list[ShortData]):
        assert _trend(ftd_data_all_zero) == "flat"

    def test_zero_to_nonzero(self):
        """First half all zeros, second half nonzero -> rising."""
        data = [_ftd(day=1 + i, value=v) for i, v in enumerate([0, 0, 100, 200])]
        assert _trend(data) == "rising"


# ---------------------------------------------------------------------------
# analyze_ftd (integration)
# ---------------------------------------------------------------------------


class TestAnalyzeFtd:
    def test_empty_input(self):
        result = analyze_ftd([])
        assert result["symbol"] == "UNKNOWN"
        assert result["persistence"] == 0.0
        assert result["spike_days"] == []
        assert result["trend"] == "flat"
        assert result["max_ftd"] == 0.0
        assert result["avg_ftd"] == 0.0

    def test_rising_data(self, ftd_data_rising: list[ShortData]):
        result = analyze_ftd(ftd_data_rising)
        assert result["symbol"] == SYMBOL
        assert result["trend"] == "rising"
        assert result["persistence"] == 0.9
        assert result["max_ftd"] == 500
        assert result["avg_ftd"] == 255.0

    def test_falling_data(self, ftd_data_falling: list[ShortData]):
        result = analyze_ftd(ftd_data_falling)
        assert result["symbol"] == SYMBOL
        assert result["trend"] == "falling"

    def test_flat_data(self, ftd_data_flat: list[ShortData]):
        result = analyze_ftd(ftd_data_flat)
        assert result["trend"] == "flat"

    def test_spike_detection_integration(self, ftd_data_with_spikes: list[ShortData]):
        result = analyze_ftd(ftd_data_with_spikes)
        assert len(result["spike_days"]) == 1
        assert result["spike_days"][0]["value"] == 900

    def test_all_zero_data(self, ftd_data_all_zero: list[ShortData]):
        result = analyze_ftd(ftd_data_all_zero)
        assert result["persistence"] == 0.0
        assert result["max_ftd"] == 0.0
        assert result["avg_ftd"] == 0.0
        assert result["spike_days"] == []
        assert result["trend"] == "flat"

    def test_all_keys_present(self, ftd_data_rising: list[ShortData]):
        result = analyze_ftd(ftd_data_rising)
        expected_keys = {"symbol", "persistence", "spike_days", "trend", "max_ftd", "avg_ftd"}
        assert set(result.keys()) == expected_keys

    def test_single_entry(self):
        data = [_ftd(day=15, value=42000)]
        result = analyze_ftd(data)
        assert result["symbol"] == SYMBOL
        assert result["persistence"] == 1.0
        assert result["max_ftd"] == 42000
        assert result["avg_ftd"] == 42000.0
        assert result["trend"] == "flat"
        assert result["spike_days"] == []
