"""Tests for the short_squeeze_detector analysis module."""

from __future__ import annotations

from datetime import date

import pytest

from agora.analysis.short_squeeze_detector import (
    _classify_confidence,
    _compute_trend,
    _group_by_symbol,
    _group_quotes_by_symbol,
    _score_days_to_cover,
    _score_ftd_persistence,
    _score_price_trend,
    _score_short_interest,
    _score_volume_trend,
    detect_squeeze_candidates,
)
from agora.schemas import Quote, ShortData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SYMBOL = "GME"


@pytest.fixture()
def high_si_data() -> list[ShortData]:
    """Short interest data with SI at 20% (above 15% threshold)."""
    return [
        ShortData(
            symbol=SYMBOL,
            date=date(2026, 2, 15),
            data_type="interest",
            value=12.0,
            source="exchange",
        ),
        ShortData(
            symbol=SYMBOL,
            date=date(2026, 3, 15),
            data_type="interest",
            value=20.0,
            total_for_ratio=50_000_000.0,
            source="exchange",
        ),
    ]


@pytest.fixture()
def low_si_data() -> list[ShortData]:
    """Short interest data with SI at 5% (below threshold)."""
    return [
        ShortData(
            symbol=SYMBOL,
            date=date(2026, 3, 15),
            data_type="interest",
            value=5.0,
            source="exchange",
        ),
    ]


@pytest.fixture()
def rising_price_quotes() -> list[Quote]:
    """Quotes with clearly rising prices and rising volume."""
    base = date(2026, 3, 16)
    entries = []
    for i in range(10):
        entries.append(
            Quote(
                symbol=SYMBOL,
                date=date(base.year, base.month, base.day + i),
                open=100.0 + i * 3.0,
                high=105.0 + i * 3.0,
                low=98.0 + i * 3.0,
                close=103.0 + i * 3.0,
                volume=1_000_000 + i * 100_000,
            )
        )
    return entries


@pytest.fixture()
def flat_price_quotes() -> list[Quote]:
    """Quotes with flat prices and flat volume."""
    base = date(2026, 3, 16)
    entries = []
    for i in range(10):
        entries.append(
            Quote(
                symbol=SYMBOL,
                date=date(base.year, base.month, base.day + i),
                open=100.0,
                high=102.0,
                low=99.0,
                close=100.0,
                volume=1_000_000,
            )
        )
    return entries


@pytest.fixture()
def declining_price_quotes() -> list[Quote]:
    """Quotes with declining prices."""
    base = date(2026, 3, 16)
    entries = []
    for i in range(10):
        entries.append(
            Quote(
                symbol=SYMBOL,
                date=date(base.year, base.month, base.day + i),
                open=130.0 - i * 3.0,
                high=135.0 - i * 3.0,
                low=128.0 - i * 3.0,
                close=130.0 - i * 3.0,
                volume=1_000_000,
            )
        )
    return entries


@pytest.fixture()
def persistent_ftd_data() -> list[ShortData]:
    """FTD data with high persistence (8/10 days)."""
    base = date(2026, 3, 10)
    values = [
        200_000, 300_000, 150_000, 0, 250_000,
        400_000, 350_000, 0, 200_000, 500_000,
    ]
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
def no_ftd_data() -> list[ShortData]:
    """FTD data with zero FTDs."""
    base = date(2026, 3, 10)
    return [
        ShortData(
            symbol=SYMBOL,
            date=date(base.year, base.month, base.day + i),
            data_type="ftd",
            value=0,
            source="sec",
        )
        for i in range(5)
    ]


# ---------------------------------------------------------------------------
# _compute_trend
# ---------------------------------------------------------------------------


class TestComputeTrend:
    def test_empty(self):
        assert _compute_trend([]) == 0.0

    def test_single_value(self):
        assert _compute_trend([5.0]) == 0.0

    def test_rising(self):
        slope = _compute_trend([1.0, 2.0, 3.0, 4.0, 5.0])
        assert slope == pytest.approx(1.0)

    def test_falling(self):
        slope = _compute_trend([5.0, 4.0, 3.0, 2.0, 1.0])
        assert slope == pytest.approx(-1.0)

    def test_flat(self):
        slope = _compute_trend([3.0, 3.0, 3.0])
        assert slope == 0.0


# ---------------------------------------------------------------------------
# _classify_confidence
# ---------------------------------------------------------------------------


class TestClassifyConfidence:
    def test_very_high(self):
        assert _classify_confidence(90.0) == "very_high"

    def test_high(self):
        assert _classify_confidence(65.0) == "high"

    def test_moderate(self):
        assert _classify_confidence(45.0) == "moderate"

    def test_low(self):
        assert _classify_confidence(25.0) == "low"

    def test_very_low(self):
        assert _classify_confidence(10.0) == "very_low"

    def test_zero(self):
        assert _classify_confidence(0.0) == "very_low"

    def test_boundary_80(self):
        assert _classify_confidence(80.0) == "very_high"

    def test_boundary_60(self):
        assert _classify_confidence(60.0) == "high"

    def test_boundary_40(self):
        assert _classify_confidence(40.0) == "moderate"

    def test_boundary_20(self):
        assert _classify_confidence(20.0) == "low"


# ---------------------------------------------------------------------------
# _group_by_symbol
# ---------------------------------------------------------------------------


class TestGroupBySymbol:
    def test_empty(self):
        assert _group_by_symbol([]) == {}

    def test_single_symbol(self, high_si_data: list[ShortData]):
        grouped = _group_by_symbol(high_si_data)
        assert SYMBOL in grouped
        assert "interest" in grouped[SYMBOL]
        assert len(grouped[SYMBOL]["interest"]) == 2

    def test_multiple_types(self, high_si_data, persistent_ftd_data):
        combined = high_si_data + persistent_ftd_data
        grouped = _group_by_symbol(combined)
        assert "interest" in grouped[SYMBOL]
        assert "ftd" in grouped[SYMBOL]

    def test_sorted_by_date(self):
        data = [
            ShortData(
                symbol="A",
                date=date(2026, 3, 20),
                data_type="interest",
                value=10.0,
                source="x",
            ),
            ShortData(
                symbol="A",
                date=date(2026, 3, 10),
                data_type="interest",
                value=8.0,
                source="x",
            ),
        ]
        grouped = _group_by_symbol(data)
        dates = [sd.date for sd in grouped["A"]["interest"]]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# _group_quotes_by_symbol
# ---------------------------------------------------------------------------


class TestGroupQuotesBySymbol:
    def test_empty(self):
        assert _group_quotes_by_symbol([]) == {}

    def test_sorted_by_date(self):
        quotes = [
            Quote(
                symbol="A",
                date=date(2026, 3, 20),
                open=10, high=11, low=9, close=10, volume=100,
            ),
            Quote(
                symbol="A",
                date=date(2026, 3, 10),
                open=10, high=11, low=9, close=10, volume=100,
            ),
        ]
        grouped = _group_quotes_by_symbol(quotes)
        dates = [q.date for q in grouped["A"]]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# _score_short_interest
# ---------------------------------------------------------------------------


class TestScoreShortInterest:
    def test_empty(self):
        score, met = _score_short_interest([])
        assert score == 0.0
        assert met is False

    def test_high_si(self, high_si_data):
        score, met = _score_short_interest(high_si_data)
        # SI at 20% with increasing trend: should be well above 50
        assert score > 50.0
        assert met is True

    def test_low_si(self, low_si_data):
        score, met = _score_short_interest(low_si_data)
        # SI at 5%: at boundary, score = 0
        assert score == 0.0
        assert met is False

    def test_extreme_si(self):
        data = [
            ShortData(
                symbol=SYMBOL,
                date=date(2026, 3, 15),
                data_type="interest",
                value=35.0,
                source="exchange",
            ),
        ]
        score, met = _score_short_interest(data)
        assert score == 100.0
        assert met is True

    def test_moderate_si(self):
        data = [
            ShortData(
                symbol=SYMBOL,
                date=date(2026, 3, 15),
                data_type="interest",
                value=10.0,
                source="exchange",
            ),
        ]
        score, met = _score_short_interest(data)
        # (10-5)/10 * 50 = 25.0
        assert score == 25.0
        assert met is False

    def test_trend_bonus(self):
        """Increasing SI should add a trend bonus."""
        single = [
            ShortData(
                symbol=SYMBOL,
                date=date(2026, 3, 15),
                data_type="interest",
                value=20.0,
                source="exchange",
            ),
        ]
        multi = [
            ShortData(
                symbol=SYMBOL,
                date=date(2026, 2, 15),
                data_type="interest",
                value=10.0,
                source="exchange",
            ),
            ShortData(
                symbol=SYMBOL,
                date=date(2026, 3, 15),
                data_type="interest",
                value=20.0,
                source="exchange",
            ),
        ]
        score_single, _ = _score_short_interest(single)
        score_multi, _ = _score_short_interest(multi)
        assert score_multi > score_single


# ---------------------------------------------------------------------------
# _score_price_trend
# ---------------------------------------------------------------------------


class TestScorePriceTrend:
    def test_empty(self):
        score, met = _score_price_trend([])
        assert score == 0.0
        assert met is False

    def test_single_quote(self):
        q = Quote(
            symbol=SYMBOL, date=date(2026, 3, 16),
            open=100, high=105, low=98, close=103, volume=1_000_000,
        )
        score, met = _score_price_trend([q])
        assert score == 0.0
        assert met is False

    def test_rising(self, rising_price_quotes):
        score, met = _score_price_trend(rising_price_quotes)
        assert score > 0.0
        assert met is True

    def test_flat(self, flat_price_quotes):
        score, met = _score_price_trend(flat_price_quotes)
        assert score == 0.0
        assert met is False

    def test_declining(self, declining_price_quotes):
        score, met = _score_price_trend(declining_price_quotes)
        assert score == 0.0
        assert met is False


# ---------------------------------------------------------------------------
# _score_days_to_cover
# ---------------------------------------------------------------------------


class TestScoreDaysToCover:
    def test_empty_interest(self, rising_price_quotes):
        score, met = _score_days_to_cover([], rising_price_quotes)
        assert score == 0.0
        assert met is False

    def test_empty_quotes(self, high_si_data):
        score, met = _score_days_to_cover(high_si_data, [])
        assert score == 0.0
        assert met is False

    def test_high_dtc(self, high_si_data, rising_price_quotes):
        """With 20% SI on 50M float and ~1.45M avg volume, DTC ~6.9."""
        score, met = _score_days_to_cover(high_si_data, rising_price_quotes)
        # DTC should be above 5
        assert score > 50.0
        assert met is True

    def test_low_dtc_without_float(self):
        """Without total_for_ratio, fallback estimate yields low DTC."""
        si_data = [
            ShortData(
                symbol=SYMBOL,
                date=date(2026, 3, 15),
                data_type="interest",
                value=5.0,
                source="exchange",
            ),
        ]
        quotes = [
            Quote(
                symbol=SYMBOL,
                date=date(2026, 3, 16),
                open=100, high=105, low=98, close=103,
                volume=10_000_000,
            ),
        ]
        score, met = _score_days_to_cover(si_data, quotes)
        # Fallback: short_shares = 0.05 * 10M * 5 = 2.5M, DTC = 2.5M/10M = 0.25
        assert score == 0.0
        assert met is False


# ---------------------------------------------------------------------------
# _score_volume_trend
# ---------------------------------------------------------------------------


class TestScoreVolumeTrend:
    def test_empty(self):
        score, met = _score_volume_trend([])
        assert score == 0.0
        assert met is False

    def test_rising(self, rising_price_quotes):
        score, met = _score_volume_trend(rising_price_quotes)
        assert score > 0.0
        assert met is True

    def test_flat(self, flat_price_quotes):
        score, met = _score_volume_trend(flat_price_quotes)
        assert score == 0.0
        assert met is False


# ---------------------------------------------------------------------------
# _score_ftd_persistence
# ---------------------------------------------------------------------------


class TestScoreFtdPersistence:
    def test_empty(self):
        score, met = _score_ftd_persistence([])
        assert score == 0.0
        assert met is False

    def test_persistent(self, persistent_ftd_data):
        score, met = _score_ftd_persistence(persistent_ftd_data)
        # 8/10 persistence = 80% -> well above 50% threshold
        assert score > 40.0
        assert met is True

    def test_no_ftds(self, no_ftd_data):
        score, met = _score_ftd_persistence(no_ftd_data)
        assert score == 0.0
        assert met is False

    def test_low_persistence(self):
        """Only 1/5 days with FTDs: below 50% threshold."""
        base = date(2026, 3, 10)
        data = [
            ShortData(
                symbol=SYMBOL,
                date=date(base.year, base.month, base.day + i),
                data_type="ftd",
                value=100_000 if i == 0 else 0,
                source="sec",
            )
            for i in range(5)
        ]
        score, met = _score_ftd_persistence(data)
        assert met is False


# ---------------------------------------------------------------------------
# detect_squeeze_candidates (integration)
# ---------------------------------------------------------------------------


class TestDetectSqueezeCandidates:
    def test_empty_inputs(self):
        result = detect_squeeze_candidates([], [])
        assert result == []

    def test_single_strong_candidate(
        self,
        high_si_data,
        rising_price_quotes,
        persistent_ftd_data,
    ):
        short_data = high_si_data + persistent_ftd_data
        result = detect_squeeze_candidates(short_data, rising_price_quotes)
        assert len(result) == 1
        candidate = result[0]
        assert candidate["symbol"] == SYMBOL
        assert candidate["score"] > 0
        assert isinstance(candidate["criteria_met"], list)
        assert candidate["confidence"] in (
            "very_high", "high", "moderate", "low", "very_low"
        )
        # With high SI, rising price, rising volume, persistent FTDs
        assert "high_short_interest" in candidate["criteria_met"]
        assert "rising_price" in candidate["criteria_met"]
        assert "ftd_persistence" in candidate["criteria_met"]

    def test_weak_candidate(self, low_si_data, flat_price_quotes, no_ftd_data):
        short_data = low_si_data + no_ftd_data
        result = detect_squeeze_candidates(short_data, flat_price_quotes)
        assert len(result) == 1
        candidate = result[0]
        assert candidate["score"] < 20.0
        assert len(candidate["criteria_met"]) == 0

    def test_multiple_symbols_ranked(self):
        """Two symbols: strong squeeze and weak squeeze, ordered by score."""
        strong_short = [
            ShortData(
                symbol="SQZZ",
                date=date(2026, 2, 15),
                data_type="interest",
                value=10.0,
                source="exchange",
            ),
            ShortData(
                symbol="SQZZ",
                date=date(2026, 3, 15),
                data_type="interest",
                value=25.0,
                total_for_ratio=20_000_000.0,
                source="exchange",
            ),
        ]
        weak_short = [
            ShortData(
                symbol="BORING",
                date=date(2026, 3, 15),
                data_type="interest",
                value=3.0,
                source="exchange",
            ),
        ]
        strong_quotes = [
            Quote(
                symbol="SQZZ",
                date=date(2026, 3, 16 + i),
                open=50.0 + i * 2.0,
                high=55.0 + i * 2.0,
                low=48.0 + i * 2.0,
                close=52.0 + i * 2.0,
                volume=500_000 + i * 50_000,
            )
            for i in range(10)
        ]
        weak_quotes = [
            Quote(
                symbol="BORING",
                date=date(2026, 3, 16 + i),
                open=200.0,
                high=202.0,
                low=199.0,
                close=200.0,
                volume=5_000_000,
            )
            for i in range(10)
        ]

        result = detect_squeeze_candidates(
            strong_short + weak_short,
            strong_quotes + weak_quotes,
        )
        assert len(result) == 2
        assert result[0]["symbol"] == "SQZZ"
        assert result[1]["symbol"] == "BORING"
        assert result[0]["score"] > result[1]["score"]

    def test_only_quotes_no_short_data(self, rising_price_quotes):
        result = detect_squeeze_candidates([], rising_price_quotes)
        assert len(result) == 1
        candidate = result[0]
        # No SI data means no SI or DTC criteria met
        assert "high_short_interest" not in candidate["criteria_met"]
        assert "high_days_to_cover" not in candidate["criteria_met"]
        # But price/volume criteria can still be met
        assert "rising_price" in candidate["criteria_met"]

    def test_only_short_data_no_quotes(self, high_si_data):
        result = detect_squeeze_candidates(high_si_data, [])
        assert len(result) == 1
        candidate = result[0]
        assert "high_short_interest" in candidate["criteria_met"]
        # No quotes means no price/volume/DTC criteria
        assert "rising_price" not in candidate["criteria_met"]
        assert "rising_volume" not in candidate["criteria_met"]
        assert "high_days_to_cover" not in candidate["criteria_met"]

    def test_return_shape(self, high_si_data, rising_price_quotes):
        result = detect_squeeze_candidates(high_si_data, rising_price_quotes)
        assert len(result) >= 1
        for candidate in result:
            assert "symbol" in candidate
            assert "score" in candidate
            assert "criteria_met" in candidate
            assert "confidence" in candidate
            assert isinstance(candidate["symbol"], str)
            assert isinstance(candidate["score"], float)
            assert isinstance(candidate["criteria_met"], list)
            assert isinstance(candidate["confidence"], str)

    def test_score_range(self, high_si_data, rising_price_quotes):
        """All scores should be in 0-100 range."""
        result = detect_squeeze_candidates(high_si_data, rising_price_quotes)
        for candidate in result:
            assert 0.0 <= candidate["score"] <= 100.0
