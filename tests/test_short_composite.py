"""Tests for the short_composite analysis module."""

from __future__ import annotations

from datetime import date

import pytest

from agora.analysis.short_composite import (
    _classify_signal,
    _compute_ftd_score,
    _compute_short_interest_score,
    _compute_short_volume_score,
    compute_short_composite,
)
from agora.schemas import ShortData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SYMBOL = "GME"


@pytest.fixture()
def short_volume_data() -> list[ShortData]:
    """Five days of short volume data with ~55% short ratio."""
    base = date(2026, 3, 16)
    entries = []
    for i in range(5):
        entries.append(
            ShortData(
                symbol=SYMBOL,
                date=date(base.year, base.month, base.day + i),
                data_type="volume",
                value=5_500_000 + i * 100_000,
                total_for_ratio=10_000_000,
                source="finra",
            )
        )
    return entries


@pytest.fixture()
def short_interest_data() -> list[ShortData]:
    """Two reporting periods with increasing SI (8% -> 12%)."""
    return [
        ShortData(
            symbol=SYMBOL,
            date=date(2026, 2, 15),
            data_type="interest",
            value=8.0,
            source="exchange",
        ),
        ShortData(
            symbol=SYMBOL,
            date=date(2026, 3, 15),
            data_type="interest",
            value=12.0,
            source="exchange",
        ),
    ]


@pytest.fixture()
def ftd_data() -> list[ShortData]:
    """Ten days of FTD data: 7 days with FTDs, avg magnitude ~200k."""
    base = date(2026, 3, 10)
    values = [150_000, 250_000, 0, 300_000, 200_000, 0, 180_000, 220_000, 0, 250_000]
    return [
        ShortData(
            symbol=SYMBOL,
            date=date(base.year, base.month, base.day + i),
            data_type="ftd",
            value=v,
            source="sec",
        )
        for i, v in enumerate(values)
    ]


@pytest.fixture()
def low_short_volume_data() -> list[ShortData]:
    """Low short volume ratio (~15%)."""
    return [
        ShortData(
            symbol=SYMBOL,
            date=date(2026, 3, 16),
            data_type="volume",
            value=1_500_000,
            total_for_ratio=10_000_000,
            source="finra",
        ),
    ]


# ---------------------------------------------------------------------------
# Signal classification
# ---------------------------------------------------------------------------


class TestClassifySignal:
    def test_extreme(self):
        assert _classify_signal(85.0) == "extreme"

    def test_high(self):
        assert _classify_signal(60.0) == "high"

    def test_moderate(self):
        assert _classify_signal(30.0) == "moderate"

    def test_low(self):
        assert _classify_signal(10.0) == "low"

    def test_zero(self):
        assert _classify_signal(0.0) == "low"

    def test_boundary_75(self):
        assert _classify_signal(75.0) == "extreme"

    def test_boundary_50(self):
        assert _classify_signal(50.0) == "high"

    def test_boundary_25(self):
        assert _classify_signal(25.0) == "moderate"


# ---------------------------------------------------------------------------
# Short volume score
# ---------------------------------------------------------------------------


class TestShortVolumeScore:
    def test_empty_input(self):
        score, ratio = _compute_short_volume_score([])
        assert score == 0.0
        assert ratio == 0.0

    def test_high_ratio(self, short_volume_data: list[ShortData]):
        score, ratio = _compute_short_volume_score(short_volume_data)
        # avg ratio around 0.57, should be in the 50-100 range
        assert 50.0 <= score <= 100.0
        assert 0.50 < ratio < 0.65

    def test_low_ratio(self, low_short_volume_data: list[ShortData]):
        score, ratio = _compute_short_volume_score(low_short_volume_data)
        assert score == 0.0
        assert ratio == 0.15

    def test_missing_total_for_ratio(self):
        """Records without total_for_ratio are skipped."""
        data = [
            ShortData(
                symbol=SYMBOL,
                date=date(2026, 3, 16),
                data_type="volume",
                value=5_000_000,
                total_for_ratio=None,
                source="finra",
            ),
        ]
        score, ratio = _compute_short_volume_score(data)
        assert score == 0.0
        assert ratio == 0.0

    def test_extreme_ratio(self):
        """75% ratio should score 100."""
        data = [
            ShortData(
                symbol=SYMBOL,
                date=date(2026, 3, 16),
                data_type="volume",
                value=7_500_000,
                total_for_ratio=10_000_000,
                source="finra",
            ),
        ]
        score, ratio = _compute_short_volume_score(data)
        assert score == 100.0


# ---------------------------------------------------------------------------
# Short interest score
# ---------------------------------------------------------------------------


class TestShortInterestScore:
    def test_empty_input(self):
        score, pct = _compute_short_interest_score([])
        assert score == 0.0
        assert pct == 0.0

    def test_moderate_si(self, short_interest_data: list[ShortData]):
        score, pct = _compute_short_interest_score(short_interest_data)
        # SI at 12% with an increasing trend
        assert 50.0 <= score <= 75.0
        assert pct == 12.0

    def test_low_si(self):
        data = [
            ShortData(
                symbol=SYMBOL,
                date=date(2026, 3, 15),
                data_type="interest",
                value=2.0,
                source="exchange",
            ),
        ]
        score, pct = _compute_short_interest_score(data)
        assert score == 10.0  # (2/5)*25 = 10
        assert pct == 2.0

    def test_extreme_si(self):
        data = [
            ShortData(
                symbol=SYMBOL,
                date=date(2026, 3, 15),
                data_type="interest",
                value=30.0,
                source="exchange",
            ),
        ]
        score, pct = _compute_short_interest_score(data)
        assert score == 100.0


# ---------------------------------------------------------------------------
# FTD score
# ---------------------------------------------------------------------------


class TestFtdScore:
    def test_empty_input(self):
        score, days = _compute_ftd_score([])
        assert score == 0.0
        assert days == 0

    def test_moderate_ftds(self, ftd_data: list[ShortData]):
        score, days = _compute_ftd_score(ftd_data)
        assert days == 7
        # persistence 7/10 = 0.7 -> 42pts, magnitude avg 155k -> ~31pts
        assert 40.0 <= score <= 80.0

    def test_zero_ftds(self):
        data = [
            ShortData(
                symbol=SYMBOL,
                date=date(2026, 3, 16),
                data_type="ftd",
                value=0,
                source="sec",
            ),
        ]
        score, days = _compute_ftd_score(data)
        assert score == 0.0
        assert days == 0


# ---------------------------------------------------------------------------
# Composite function
# ---------------------------------------------------------------------------


class TestComputeShortComposite:
    def test_full_data(
        self,
        short_volume_data: list[ShortData],
        short_interest_data: list[ShortData],
        ftd_data: list[ShortData],
    ):
        result = compute_short_composite(
            short_volume_data, short_interest_data, ftd_data
        )
        assert result["symbol"] == SYMBOL
        assert 0 <= result["composite_score"] <= 100
        assert result["signal"] in ("low", "moderate", "high", "extreme")
        assert "missing_sources" not in result

        # Verify all keys present
        assert "components" in result
        assert "short_volume_score" in result["components"]
        assert "short_interest_score" in result["components"]
        assert "ftd_score" in result["components"]

        assert "details" in result
        assert "short_volume_ratio_avg" in result["details"]
        assert "short_interest_pct" in result["details"]
        assert "ftd_persistence" in result["details"]

    def test_missing_volume(
        self,
        short_interest_data: list[ShortData],
        ftd_data: list[ShortData],
    ):
        result = compute_short_composite([], short_interest_data, ftd_data)
        assert "missing_sources" in result
        assert "short_volume" in result["missing_sources"]
        assert result["components"]["short_volume_score"] == 0.0
        # Composite should still be computed from available sources
        assert result["composite_score"] > 0

    def test_missing_interest(
        self,
        short_volume_data: list[ShortData],
        ftd_data: list[ShortData],
    ):
        result = compute_short_composite(short_volume_data, [], ftd_data)
        assert "missing_sources" in result
        assert "short_interest" in result["missing_sources"]

    def test_missing_ftd(
        self,
        short_volume_data: list[ShortData],
        short_interest_data: list[ShortData],
    ):
        result = compute_short_composite(short_volume_data, short_interest_data, [])
        assert "missing_sources" in result
        assert "ftd_data" in result["missing_sources"]

    def test_all_empty(self):
        result = compute_short_composite([], [], [])
        assert result["symbol"] == "UNKNOWN"
        assert result["composite_score"] == 0.0
        assert result["signal"] == "low"
        assert len(result["missing_sources"]) == 3

    def test_composite_weighted_correctly(
        self,
        short_volume_data: list[ShortData],
        short_interest_data: list[ShortData],
        ftd_data: list[ShortData],
    ):
        result = compute_short_composite(
            short_volume_data, short_interest_data, ftd_data
        )
        vol = result["components"]["short_volume_score"]
        si = result["components"]["short_interest_score"]
        ftd = result["components"]["ftd_score"]
        expected = round(0.40 * vol + 0.30 * si + 0.30 * ftd, 2)
        assert result["composite_score"] == expected

    def test_reweighting_with_one_source(
        self,
        short_volume_data: list[ShortData],
    ):
        """With only volume data, composite should equal volume score."""
        result = compute_short_composite(short_volume_data, [], [])
        assert result["composite_score"] == result["components"]["short_volume_score"]
