"""Tests for the sector_analysis module."""

from __future__ import annotations

from datetime import date

import pytest

from agora.analysis.sector_analysis import (
    _average_volume,
    _period_return,
    _split_into_periods,
    compute_sector_performance,
    compute_sector_rotation,
)
from agora.schemas import Quote


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _q(symbol: str, day: int, close: float, *, volume: int = 1_000_000) -> Quote:
    """Shorthand Quote constructor with sensible defaults."""
    return Quote(
        symbol=symbol,
        date=date(2026, 3, day),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tech_quotes() -> list[Quote]:
    """Technology sector: AAPL rising, MSFT flat."""
    return [
        _q("AAPL", 1, 100.0),
        _q("AAPL", 2, 105.0),
        _q("AAPL", 3, 110.0),
        _q("AAPL", 4, 120.0),
        _q("MSFT", 1, 200.0),
        _q("MSFT", 2, 200.0),
        _q("MSFT", 3, 200.0),
        _q("MSFT", 4, 200.0),
    ]


@pytest.fixture()
def energy_quotes() -> list[Quote]:
    """Energy sector: XOM declining."""
    return [
        _q("XOM", 1, 80.0, volume=2_000_000),
        _q("XOM", 2, 75.0, volume=2_000_000),
        _q("XOM", 3, 70.0, volume=2_000_000),
        _q("XOM", 4, 60.0, volume=2_000_000),
    ]


@pytest.fixture()
def quotes_by_sector(
    tech_quotes: list[Quote],
    energy_quotes: list[Quote],
) -> dict[str, list[Quote]]:
    return {"Technology": tech_quotes, "Energy": energy_quotes}


@pytest.fixture()
def rotation_tech_quotes() -> list[Quote]:
    """Tech quotes designed for rotation: slow first half, fast second half."""
    return [
        # Period 1: slow growth
        _q("AAPL", 1, 100.0),
        _q("AAPL", 2, 101.0),
        _q("AAPL", 3, 102.0),
        # Period 2: fast growth
        _q("AAPL", 4, 110.0),
        _q("AAPL", 5, 115.0),
        _q("AAPL", 6, 125.0),
    ]


@pytest.fixture()
def rotation_energy_quotes() -> list[Quote]:
    """Energy quotes: strong first half, declining second half."""
    return [
        # Period 1: strong growth
        _q("XOM", 1, 50.0),
        _q("XOM", 2, 55.0),
        _q("XOM", 3, 60.0),
        # Period 2: decline
        _q("XOM", 4, 58.0),
        _q("XOM", 5, 55.0),
        _q("XOM", 6, 50.0),
    ]


# ---------------------------------------------------------------------------
# _period_return
# ---------------------------------------------------------------------------


class TestPeriodReturn:
    def test_positive_return(self):
        quotes = [_q("AAPL", 1, 100.0), _q("AAPL", 2, 120.0)]
        assert _period_return(quotes) == pytest.approx(0.2)

    def test_negative_return(self):
        quotes = [_q("AAPL", 1, 100.0), _q("AAPL", 2, 80.0)]
        assert _period_return(quotes) == pytest.approx(-0.2)

    def test_zero_return(self):
        quotes = [_q("AAPL", 1, 100.0), _q("AAPL", 2, 100.0)]
        assert _period_return(quotes) == pytest.approx(0.0)

    def test_single_quote(self):
        quotes = [_q("AAPL", 1, 100.0)]
        assert _period_return(quotes) == 0.0

    def test_empty_list(self):
        assert _period_return([]) == 0.0

    def test_zero_initial_close(self):
        quotes = [_q("AAPL", 1, 0.0), _q("AAPL", 2, 100.0)]
        assert _period_return(quotes) == 0.0


# ---------------------------------------------------------------------------
# _average_volume
# ---------------------------------------------------------------------------


class TestAverageVolume:
    def test_basic(self):
        quotes = [
            _q("AAPL", 1, 100.0, volume=1_000_000),
            _q("AAPL", 2, 110.0, volume=3_000_000),
        ]
        assert _average_volume(quotes) == pytest.approx(2_000_000.0)

    def test_empty(self):
        assert _average_volume([]) == 0.0


# ---------------------------------------------------------------------------
# _split_into_periods
# ---------------------------------------------------------------------------


class TestSplitIntoPeriods:
    def test_even_split(self):
        quotes = [_q("A", d, 100.0) for d in range(1, 7)]
        chunks = _split_into_periods(quotes, 2)
        assert len(chunks) == 2
        assert len(chunks[0]) == 3
        assert len(chunks[1]) == 3

    def test_uneven_split_merges_remainder(self):
        quotes = [_q("A", d, 100.0) for d in range(1, 8)]  # 7 items, 2 periods
        chunks = _split_into_periods(quotes, 2)
        assert len(chunks) == 2
        # chunk_size=3, so first chunk has 3, second has 3+1=4
        assert len(chunks[0]) == 3
        assert len(chunks[1]) == 4

    def test_three_periods(self):
        quotes = [_q("A", d, 100.0) for d in range(1, 10)]  # 9 items
        chunks = _split_into_periods(quotes, 3)
        assert len(chunks) == 3
        for chunk in chunks:
            assert len(chunk) == 3

    def test_empty_list(self):
        assert _split_into_periods([], 2) == []

    def test_zero_periods(self):
        quotes = [_q("A", 1, 100.0)]
        assert _split_into_periods(quotes, 0) == []

    def test_single_quote_two_periods(self):
        quotes = [_q("A", 1, 100.0)]
        chunks = _split_into_periods(quotes, 2)
        # Only 1 item, chunk_size=1, produces 1 chunk
        assert len(chunks) == 1


# ---------------------------------------------------------------------------
# compute_sector_performance
# ---------------------------------------------------------------------------


class TestComputeSectorPerformance:
    def test_empty_input(self):
        assert compute_sector_performance({}) == []

    def test_empty_quotes_in_sector(self):
        assert compute_sector_performance({"Tech": []}) == []

    def test_sorted_by_avg_return_descending(
        self, quotes_by_sector: dict[str, list[Quote]]
    ):
        result = compute_sector_performance(quotes_by_sector)
        returns = [r["avg_return"] for r in result]
        assert returns == sorted(returns, reverse=True)

    def test_tech_beats_energy(
        self, quotes_by_sector: dict[str, list[Quote]]
    ):
        result = compute_sector_performance(quotes_by_sector)
        assert result[0]["sector"] == "Technology"
        assert result[1]["sector"] == "Energy"

    def test_required_keys(
        self, quotes_by_sector: dict[str, list[Quote]]
    ):
        result = compute_sector_performance(quotes_by_sector)
        expected_keys = {
            "sector",
            "avg_return",
            "total_volume",
            "symbol_count",
            "best_symbol",
            "best_return",
            "worst_symbol",
            "worst_return",
        }
        for row in result:
            assert set(row.keys()) == expected_keys

    def test_symbol_count(
        self, quotes_by_sector: dict[str, list[Quote]]
    ):
        result = compute_sector_performance(quotes_by_sector)
        by_sector = {r["sector"]: r for r in result}
        assert by_sector["Technology"]["symbol_count"] == 2
        assert by_sector["Energy"]["symbol_count"] == 1

    def test_tech_avg_return(
        self, quotes_by_sector: dict[str, list[Quote]]
    ):
        result = compute_sector_performance(quotes_by_sector)
        tech = next(r for r in result if r["sector"] == "Technology")
        # AAPL: (120 - 100) / 100 = 0.2
        # MSFT: (200 - 200) / 200 = 0.0
        # avg = 0.1
        assert tech["avg_return"] == pytest.approx(0.1)

    def test_energy_return(
        self, quotes_by_sector: dict[str, list[Quote]]
    ):
        result = compute_sector_performance(quotes_by_sector)
        energy = next(r for r in result if r["sector"] == "Energy")
        # XOM: (60 - 80) / 80 = -0.25
        assert energy["avg_return"] == pytest.approx(-0.25)

    def test_best_worst_symbol(
        self, quotes_by_sector: dict[str, list[Quote]]
    ):
        result = compute_sector_performance(quotes_by_sector)
        tech = next(r for r in result if r["sector"] == "Technology")
        assert tech["best_symbol"] == "AAPL"
        assert tech["worst_symbol"] == "MSFT"

    def test_total_volume(
        self, quotes_by_sector: dict[str, list[Quote]]
    ):
        result = compute_sector_performance(quotes_by_sector)
        tech = next(r for r in result if r["sector"] == "Technology")
        # 8 quotes * 1_000_000 each
        assert tech["total_volume"] == 8_000_000
        energy = next(r for r in result if r["sector"] == "Energy")
        # 4 quotes * 2_000_000 each
        assert energy["total_volume"] == 8_000_000

    def test_single_quote_per_symbol(self):
        """A single quote per symbol gives zero return."""
        data = {"Sector": [_q("AAA", 1, 50.0)]}
        result = compute_sector_performance(data)
        assert len(result) == 1
        assert result[0]["avg_return"] == 0.0


# ---------------------------------------------------------------------------
# compute_sector_rotation
# ---------------------------------------------------------------------------


class TestComputeSectorRotation:
    def test_empty_input(self):
        assert compute_sector_rotation({}) == []

    def test_empty_quotes(self):
        assert compute_sector_rotation({"Tech": []}) == []

    def test_periods_less_than_two(self, tech_quotes: list[Quote]):
        assert compute_sector_rotation({"Tech": tech_quotes}, periods=1) == []
        assert compute_sector_rotation({"Tech": tech_quotes}, periods=0) == []

    def test_required_keys(
        self,
        rotation_tech_quotes: list[Quote],
    ):
        result = compute_sector_rotation({"Tech": rotation_tech_quotes})
        expected_keys = {
            "sector",
            "prior_return",
            "recent_return",
            "momentum_change",
            "rotation_signal",
        }
        for row in result:
            assert set(row.keys()) == expected_keys

    def test_gaining_signal(
        self,
        rotation_tech_quotes: list[Quote],
    ):
        """Tech accelerating -> gaining signal."""
        result = compute_sector_rotation({"Tech": rotation_tech_quotes})
        assert len(result) == 1
        assert result[0]["rotation_signal"] == "gaining"
        assert result[0]["momentum_change"] > 0

    def test_losing_signal(
        self,
        rotation_energy_quotes: list[Quote],
    ):
        """Energy decelerating -> losing signal."""
        result = compute_sector_rotation({"Energy": rotation_energy_quotes})
        assert len(result) == 1
        assert result[0]["rotation_signal"] == "losing"
        assert result[0]["momentum_change"] < 0

    def test_stable_signal(self):
        """Flat performance across both periods -> stable."""
        quotes = [
            _q("FLAT", 1, 100.0),
            _q("FLAT", 2, 100.5),
            _q("FLAT", 3, 101.0),
            _q("FLAT", 4, 101.5),
            _q("FLAT", 5, 101.0),
            _q("FLAT", 6, 101.5),
        ]
        result = compute_sector_rotation({"Flat": quotes})
        assert len(result) == 1
        assert result[0]["rotation_signal"] == "stable"

    def test_sorted_by_momentum_descending(
        self,
        rotation_tech_quotes: list[Quote],
        rotation_energy_quotes: list[Quote],
    ):
        data = {
            "Technology": rotation_tech_quotes,
            "Energy": rotation_energy_quotes,
        }
        result = compute_sector_rotation(data)
        changes = [r["momentum_change"] for r in result]
        assert changes == sorted(changes, reverse=True)
        # Tech gaining should come before Energy losing
        assert result[0]["sector"] == "Technology"
        assert result[1]["sector"] == "Energy"

    def test_too_few_quotes_for_periods(self):
        """Symbols with too few quotes to split are skipped."""
        quotes = [_q("A", 1, 100.0)]  # Only 1 quote, cannot split into 2
        result = compute_sector_rotation({"S": quotes})
        assert result == []

    def test_multiple_symbols_averaged(
        self,
    ):
        """Rotation averages returns across symbols in a sector."""
        # Both symbols accelerate in period 2
        quotes = [
            _q("A", 1, 100.0),
            _q("A", 2, 102.0),
            _q("A", 3, 110.0),
            _q("A", 4, 125.0),
            _q("B", 1, 50.0),
            _q("B", 2, 51.0),
            _q("B", 3, 55.0),
            _q("B", 4, 65.0),
        ]
        result = compute_sector_rotation({"Mixed": quotes})
        assert len(result) == 1
        assert result[0]["rotation_signal"] == "gaining"

    def test_three_periods(
        self,
    ):
        """With periods=3, the last two chunks are compared."""
        quotes = [
            _q("X", 1, 100.0),
            _q("X", 2, 105.0),
            _q("X", 3, 110.0),
            _q("X", 4, 108.0),
            _q("X", 5, 106.0),
            _q("X", 6, 104.0),
            _q("X", 7, 120.0),
            _q("X", 8, 130.0),
            _q("X", 9, 150.0),
        ]
        result = compute_sector_rotation({"S": quotes}, periods=3)
        assert len(result) == 1
        # Period 2 (days 4-6): decline; Period 3 (days 7-9): strong rise
        assert result[0]["rotation_signal"] == "gaining"
