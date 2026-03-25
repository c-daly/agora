"""Tests for the sector_short_sentiment analysis module."""

from __future__ import annotations

from datetime import date

import pytest

from agora.analysis.sector_short_sentiment import (
    _determine_trend,
    _short_volume_ratio,
    analyze_sector_sentiment,
)
from agora.schemas import ShortData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECTOR_MAP = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "JPM": "Financials",
    "BAC": "Financials",
    "XOM": "Energy",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tech_volume_data() -> list[ShortData]:
    """Volume data for two tech symbols across multiple days."""
    base = date(2026, 3, 10)
    entries: list[ShortData] = []
    for i in range(5):
        entries.append(
            ShortData(
                symbol="AAPL",
                date=date(base.year, base.month, base.day + i),
                data_type="volume",
                value=6_000_000 + i * 200_000,
                total_for_ratio=10_000_000,
                source="finra",
            )
        )
        entries.append(
            ShortData(
                symbol="MSFT",
                date=date(base.year, base.month, base.day + i),
                data_type="volume",
                value=4_000_000 + i * 100_000,
                total_for_ratio=10_000_000,
                source="finra",
            )
        )
    return entries


@pytest.fixture()
def financials_volume_data() -> list[ShortData]:
    """Volume data for two financial symbols."""
    return [
        ShortData(
            symbol="JPM",
            date=date(2026, 3, 10),
            data_type="volume",
            value=3_000_000,
            total_for_ratio=10_000_000,
            source="finra",
        ),
        ShortData(
            symbol="BAC",
            date=date(2026, 3, 10),
            data_type="volume",
            value=2_000_000,
            total_for_ratio=10_000_000,
            source="finra",
        ),
    ]


@pytest.fixture()
def interest_data() -> list[ShortData]:
    """Short interest data for multiple symbols."""
    return [
        ShortData(
            symbol="AAPL",
            date=date(2026, 3, 15),
            data_type="interest",
            value=5.0,
            source="exchange",
        ),
        ShortData(
            symbol="MSFT",
            date=date(2026, 3, 15),
            data_type="interest",
            value=3.0,
            source="exchange",
        ),
        ShortData(
            symbol="JPM",
            date=date(2026, 3, 15),
            data_type="interest",
            value=8.0,
            source="exchange",
        ),
    ]


@pytest.fixture()
def mixed_data(
    tech_volume_data: list[ShortData],
    financials_volume_data: list[ShortData],
    interest_data: list[ShortData],
) -> list[ShortData]:
    """Combined volume and interest data across sectors."""
    return tech_volume_data + financials_volume_data + interest_data


# ---------------------------------------------------------------------------
# _short_volume_ratio
# ---------------------------------------------------------------------------


class TestShortVolumeRatio:
    def test_valid_ratio(self):
        entry = ShortData(
            symbol="AAPL",
            date=date(2026, 3, 10),
            data_type="volume",
            value=6_000_000,
            total_for_ratio=10_000_000,
            source="finra",
        )
        assert _short_volume_ratio(entry) == pytest.approx(0.6)

    def test_none_total(self):
        entry = ShortData(
            symbol="AAPL",
            date=date(2026, 3, 10),
            data_type="volume",
            value=6_000_000,
            total_for_ratio=None,
            source="finra",
        )
        assert _short_volume_ratio(entry) is None

    def test_zero_total(self):
        entry = ShortData(
            symbol="AAPL",
            date=date(2026, 3, 10),
            data_type="volume",
            value=6_000_000,
            total_for_ratio=0,
            source="finra",
        )
        assert _short_volume_ratio(entry) is None


# ---------------------------------------------------------------------------
# _determine_trend
# ---------------------------------------------------------------------------


class TestDetermineTrend:
    def test_empty_list(self):
        assert _determine_trend([]) == "stable"

    def test_single_entry(self):
        assert _determine_trend([(date(2026, 3, 10), 0.5)]) == "stable"

    def test_increasing(self):
        data = [
            (date(2026, 3, 10), 0.30),
            (date(2026, 3, 11), 0.32),
            (date(2026, 3, 12), 0.50),
            (date(2026, 3, 13), 0.55),
        ]
        assert _determine_trend(data) == "increasing"

    def test_decreasing(self):
        data = [
            (date(2026, 3, 10), 0.60),
            (date(2026, 3, 11), 0.58),
            (date(2026, 3, 12), 0.40),
            (date(2026, 3, 13), 0.35),
        ]
        assert _determine_trend(data) == "decreasing"

    def test_stable(self):
        data = [
            (date(2026, 3, 10), 0.50),
            (date(2026, 3, 11), 0.51),
            (date(2026, 3, 12), 0.50),
            (date(2026, 3, 13), 0.51),
        ]
        assert _determine_trend(data) == "stable"

    def test_from_zero(self):
        data = [
            (date(2026, 3, 10), 0.0),
            (date(2026, 3, 11), 0.5),
        ]
        assert _determine_trend(data) == "increasing"

    def test_all_zero(self):
        data = [
            (date(2026, 3, 10), 0.0),
            (date(2026, 3, 11), 0.0),
        ]
        assert _determine_trend(data) == "stable"


# ---------------------------------------------------------------------------
# analyze_sector_sentiment
# ---------------------------------------------------------------------------


class TestAnalyzeSectorSentiment:
    def test_empty_data(self):
        result = analyze_sector_sentiment([], SECTOR_MAP)
        assert result == []

    def test_empty_sector_map(self, mixed_data: list[ShortData]):
        result = analyze_sector_sentiment(mixed_data, {})
        assert result == []

    def test_unmapped_symbols_skipped(self):
        data = [
            ShortData(
                symbol="UNKNOWN",
                date=date(2026, 3, 10),
                data_type="volume",
                value=5_000_000,
                total_for_ratio=10_000_000,
                source="finra",
            ),
        ]
        result = analyze_sector_sentiment(data, SECTOR_MAP)
        assert result == []

    def test_results_sorted_by_sector(self, mixed_data: list[ShortData]):
        result = analyze_sector_sentiment(mixed_data, SECTOR_MAP)
        sectors = [r["sector"] for r in result]
        assert sectors == sorted(sectors)

    def test_required_keys(self, mixed_data: list[ShortData]):
        result = analyze_sector_sentiment(mixed_data, SECTOR_MAP)
        for row in result:
            assert "sector" in row
            assert "avg_short_volume_ratio" in row
            assert "avg_short_interest" in row
            assert "symbol_count" in row
            assert "trend" in row

    def test_symbol_count(self, mixed_data: list[ShortData]):
        result = analyze_sector_sentiment(mixed_data, SECTOR_MAP)
        by_sector = {r["sector"]: r for r in result}
        assert by_sector["Technology"]["symbol_count"] == 2
        assert by_sector["Financials"]["symbol_count"] == 2

    def test_avg_short_volume_ratio_tech(
        self, tech_volume_data: list[ShortData]
    ):
        result = analyze_sector_sentiment(tech_volume_data, SECTOR_MAP)
        assert len(result) == 1
        tech = result[0]
        assert tech["sector"] == "Technology"
        # AAPL ratios: 0.6, 0.62, 0.64, 0.66, 0.68
        # MSFT ratios: 0.4, 0.41, 0.42, 0.43, 0.44
        # combined avg = 0.53
        assert tech["avg_short_volume_ratio"] == pytest.approx(0.53, abs=0.01)

    def test_avg_short_interest(self, interest_data: list[ShortData]):
        result = analyze_sector_sentiment(interest_data, SECTOR_MAP)
        by_sector = {r["sector"]: r for r in result}
        # Tech: (5.0 + 3.0) / 2 = 4.0
        assert by_sector["Technology"]["avg_short_interest"] == pytest.approx(4.0)
        # Financials: 8.0 / 1 = 8.0
        assert by_sector["Financials"]["avg_short_interest"] == pytest.approx(8.0)

    def test_no_volume_gives_zero_ratio(self, interest_data: list[ShortData]):
        result = analyze_sector_sentiment(interest_data, SECTOR_MAP)
        for row in result:
            assert row["avg_short_volume_ratio"] == 0.0

    def test_no_interest_gives_zero(
        self, tech_volume_data: list[ShortData]
    ):
        result = analyze_sector_sentiment(tech_volume_data, SECTOR_MAP)
        assert result[0]["avg_short_interest"] == 0.0

    def test_trend_increasing(self):
        """Short volume ratio increases over time -> increasing trend."""
        data = [
            ShortData(
                symbol="AAPL",
                date=date(2026, 3, 10),
                data_type="volume",
                value=3_000_000,
                total_for_ratio=10_000_000,
                source="finra",
            ),
            ShortData(
                symbol="AAPL",
                date=date(2026, 3, 11),
                data_type="volume",
                value=3_200_000,
                total_for_ratio=10_000_000,
                source="finra",
            ),
            ShortData(
                symbol="AAPL",
                date=date(2026, 3, 12),
                data_type="volume",
                value=5_000_000,
                total_for_ratio=10_000_000,
                source="finra",
            ),
            ShortData(
                symbol="AAPL",
                date=date(2026, 3, 13),
                data_type="volume",
                value=5_500_000,
                total_for_ratio=10_000_000,
                source="finra",
            ),
        ]
        result = analyze_sector_sentiment(data, SECTOR_MAP)
        assert result[0]["trend"] == "increasing"

    def test_trend_stable_no_volume(self, interest_data: list[ShortData]):
        """No volume data -> stable trend."""
        result = analyze_sector_sentiment(interest_data, SECTOR_MAP)
        for row in result:
            assert row["trend"] == "stable"

    def test_multiple_sectors(self, mixed_data: list[ShortData]):
        result = analyze_sector_sentiment(mixed_data, SECTOR_MAP)
        sectors = {r["sector"] for r in result}
        assert "Technology" in sectors
        assert "Financials" in sectors

    def test_volume_missing_total_for_ratio_skipped(self):
        """Volume entries without total_for_ratio should not affect avg ratio."""
        data = [
            ShortData(
                symbol="AAPL",
                date=date(2026, 3, 10),
                data_type="volume",
                value=5_000_000,
                total_for_ratio=None,
                source="finra",
            ),
            ShortData(
                symbol="AAPL",
                date=date(2026, 3, 11),
                data_type="volume",
                value=6_000_000,
                total_for_ratio=10_000_000,
                source="finra",
            ),
        ]
        result = analyze_sector_sentiment(data, SECTOR_MAP)
        assert len(result) == 1
        # Only the second entry contributes: 0.6
        assert result[0]["avg_short_volume_ratio"] == pytest.approx(0.6)
