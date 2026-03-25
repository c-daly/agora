"""Tests for the earnings_context analysis module."""

from __future__ import annotations

from datetime import date

import pytest

from agora.analysis.earnings_context import (
    _avg_surprise_pct,
    _beat_rate,
    _next_earnings,
    _streak,
    get_earnings_context,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SYMBOL = "AAPL"


def _surprise(pct: float, quarter: str = "Q1") -> dict:
    """Shorthand helper to build a single historical surprise dict."""
    return {"quarter": quarter, "surprise_pct": pct}


@pytest.fixture()
def surprises_all_beats() -> list[dict]:
    """Four consecutive beats."""
    return [
        _surprise(5.0, "Q1"),
        _surprise(3.2, "Q2"),
        _surprise(1.1, "Q3"),
        _surprise(7.5, "Q4"),
    ]


@pytest.fixture()
def surprises_all_misses() -> list[dict]:
    """Four consecutive misses."""
    return [
        _surprise(-2.0, "Q1"),
        _surprise(-4.5, "Q2"),
        _surprise(-1.0, "Q3"),
        _surprise(-3.3, "Q4"),
    ]


@pytest.fixture()
def surprises_mixed() -> list[dict]:
    """Mix of beats and misses: beat, miss, beat, beat."""
    return [
        _surprise(5.0, "Q1"),
        _surprise(-2.0, "Q2"),
        _surprise(3.0, "Q3"),
        _surprise(1.0, "Q4"),
    ]


@pytest.fixture()
def surprises_with_zero() -> list[dict]:
    """Streak interrupted by an exact-inline quarter."""
    return [
        _surprise(5.0, "Q1"),
        _surprise(0.0, "Q2"),
        _surprise(2.0, "Q3"),
        _surprise(3.0, "Q4"),
    ]


@pytest.fixture()
def future_dates() -> list[date]:
    """Earnings dates: two in the future, one in the past."""
    return [
        date(2025, 1, 15),
        date(2026, 7, 20),
        date(2026, 10, 25),
    ]


# ---------------------------------------------------------------------------
# _next_earnings
# ---------------------------------------------------------------------------


class TestNextEarnings:
    def test_empty(self):
        assert _next_earnings([]) is None

    def test_all_past(self):
        dates = [date(2020, 1, 1), date(2021, 6, 15)]
        assert _next_earnings(dates, reference=date(2026, 3, 25)) is None

    def test_picks_nearest_future(self, future_dates: list[date]):
        result = _next_earnings(future_dates, reference=date(2026, 3, 25))
        assert result == "2026-07-20"

    def test_same_day_included(self):
        dates = [date(2026, 3, 25)]
        result = _next_earnings(dates, reference=date(2026, 3, 25))
        assert result == "2026-03-25"

    def test_unsorted_input(self):
        dates = [date(2026, 12, 1), date(2026, 6, 1), date(2026, 9, 1)]
        result = _next_earnings(dates, reference=date(2026, 3, 25))
        assert result == "2026-06-01"

    def test_single_future_date(self):
        dates = [date(2027, 1, 1)]
        result = _next_earnings(dates, reference=date(2026, 3, 25))
        assert result == "2027-01-01"


# ---------------------------------------------------------------------------
# _avg_surprise_pct
# ---------------------------------------------------------------------------


class TestAvgSurprisePct:
    def test_empty(self):
        assert _avg_surprise_pct([]) == 0.0

    def test_all_beats(self, surprises_all_beats: list[dict]):
        # (5.0 + 3.2 + 1.1 + 7.5) / 4 = 4.2
        assert _avg_surprise_pct(surprises_all_beats) == 4.2

    def test_all_misses(self, surprises_all_misses: list[dict]):
        # (-2.0 + -4.5 + -1.0 + -3.3) / 4 = -2.7
        assert _avg_surprise_pct(surprises_all_misses) == -2.7

    def test_mixed(self, surprises_mixed: list[dict]):
        # (5.0 + -2.0 + 3.0 + 1.0) / 4 = 1.75
        assert _avg_surprise_pct(surprises_mixed) == 1.75

    def test_single_entry(self):
        assert _avg_surprise_pct([_surprise(10.0)]) == 10.0

    def test_zeros(self):
        data = [_surprise(0.0), _surprise(0.0)]
        assert _avg_surprise_pct(data) == 0.0


# ---------------------------------------------------------------------------
# _beat_rate
# ---------------------------------------------------------------------------


class TestBeatRate:
    def test_empty(self):
        assert _beat_rate([]) == 0.0

    def test_all_beats(self, surprises_all_beats: list[dict]):
        assert _beat_rate(surprises_all_beats) == 1.0

    def test_all_misses(self, surprises_all_misses: list[dict]):
        assert _beat_rate(surprises_all_misses) == 0.0

    def test_mixed(self, surprises_mixed: list[dict]):
        # 3 beats out of 4
        assert _beat_rate(surprises_mixed) == 0.75

    def test_zero_is_not_a_beat(self):
        data = [_surprise(0.0), _surprise(5.0)]
        assert _beat_rate(data) == 0.5

    def test_single_beat(self):
        assert _beat_rate([_surprise(0.1)]) == 1.0

    def test_single_miss(self):
        assert _beat_rate([_surprise(-0.1)]) == 0.0


# ---------------------------------------------------------------------------
# _streak
# ---------------------------------------------------------------------------


class TestStreak:
    def test_empty(self):
        assert _streak([]) == 0

    def test_all_beats(self, surprises_all_beats: list[dict]):
        assert _streak(surprises_all_beats) == 4

    def test_all_misses(self, surprises_all_misses: list[dict]):
        assert _streak(surprises_all_misses) == -4

    def test_mixed_ends_with_beat_streak(self, surprises_mixed: list[dict]):
        # beat, miss, beat, beat -> streak of 2 beats
        assert _streak(surprises_mixed) == 2

    def test_zero_breaks_streak(self, surprises_with_zero: list[dict]):
        # beat, zero, beat, beat -> streak of 2 (zero breaks it)
        assert _streak(surprises_with_zero) == 2

    def test_single_beat(self):
        assert _streak([_surprise(1.0)]) == 1

    def test_single_miss(self):
        assert _streak([_surprise(-1.0)]) == -1

    def test_single_zero(self):
        assert _streak([_surprise(0.0)]) == 0

    def test_ends_with_miss(self):
        data = [_surprise(5.0), _surprise(3.0), _surprise(-1.0), _surprise(-2.0)]
        assert _streak(data) == -2

    def test_alternating(self):
        data = [_surprise(1.0), _surprise(-1.0), _surprise(1.0), _surprise(-1.0)]
        assert _streak(data) == -1


# ---------------------------------------------------------------------------
# get_earnings_context (integration)
# ---------------------------------------------------------------------------


class TestGetEarningsContext:
    def test_empty_inputs(self):
        result = get_earnings_context(SYMBOL, [], [])
        assert result["symbol"] == SYMBOL
        assert result["next_earnings"] is None
        assert result["avg_surprise_pct"] == 0.0
        assert result["beat_rate"] == 0.0
        assert result["streak"] == 0
        assert result["historical"] == []

    def test_all_keys_present(self, surprises_mixed: list[dict]):
        result = get_earnings_context(SYMBOL, [], surprises_mixed)
        expected_keys = {
            "symbol",
            "next_earnings",
            "avg_surprise_pct",
            "beat_rate",
            "streak",
            "historical",
        }
        assert set(result.keys()) == expected_keys

    def test_full_context(
        self,
        future_dates: list[date],
        surprises_all_beats: list[dict],
    ):
        result = get_earnings_context(SYMBOL, future_dates, surprises_all_beats)
        assert result["symbol"] == SYMBOL
        # next_earnings depends on today; use a known reference via internals
        # But we can at least check it is a string (not None) since future_dates has 2026 dates
        assert result["next_earnings"] is not None
        assert result["avg_surprise_pct"] == 4.2
        assert result["beat_rate"] == 1.0
        assert result["streak"] == 4
        assert result["historical"] is surprises_all_beats

    def test_historical_passed_through(self, surprises_mixed: list[dict]):
        result = get_earnings_context(SYMBOL, [], surprises_mixed)
        assert result["historical"] is surprises_mixed

    def test_no_future_dates(self, surprises_mixed: list[dict]):
        past_dates = [date(2020, 1, 1)]
        result = get_earnings_context(SYMBOL, past_dates, surprises_mixed)
        assert result["next_earnings"] is None

    def test_different_symbol(self):
        result = get_earnings_context("MSFT", [], [])
        assert result["symbol"] == "MSFT"
