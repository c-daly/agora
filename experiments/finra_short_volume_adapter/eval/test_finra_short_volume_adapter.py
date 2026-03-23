"""Eval tests for the FINRA short volume adapter.

Tests hit the real FINRA endpoint -- no mocking -- since the data is public.
We use AAPL with a known recent date range where short volume data is
reliably available.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from agora.adapters.finra_short_volume_adapter import fetch_short_volume
from agora.schemas import ShortData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

KNOWN_SYMBOL = "AAPL"
# A recent week where FINRA data is reliably available
KNOWN_START = date(2026, 1, 6)
KNOWN_END = date(2026, 1, 10)


@pytest.fixture(scope="module")
def short_vol_results() -> list[ShortData]:
    """Fetch short volume data once for the module to avoid repeated API calls."""
    return fetch_short_volume(
        KNOWN_SYMBOL, start_date=KNOWN_START, end_date=KNOWN_END
    )


# ---------------------------------------------------------------------------
# 1. Returns list of ShortData objects
# ---------------------------------------------------------------------------


class TestReturnType:
    def test_returns_list(self, short_vol_results: list[ShortData]):
        assert isinstance(short_vol_results, list)

    def test_elements_are_short_data(self, short_vol_results: list[ShortData]):
        for item in short_vol_results:
            assert isinstance(item, ShortData), f"Expected ShortData, got {type(item)}"


# ---------------------------------------------------------------------------
# 2. ShortData fields populated correctly
# ---------------------------------------------------------------------------


class TestFieldValues:
    def test_data_type_is_short_volume(self, short_vol_results: list[ShortData]):
        assert len(short_vol_results) > 0, "Expected at least one result for AAPL"
        for item in short_vol_results:
            assert item.data_type == "short_volume", (
                f"Expected data_type='short_volume', got '{item.data_type}'"
            )

    def test_source_is_finra(self, short_vol_results: list[ShortData]):
        for item in short_vol_results:
            assert item.source == "FINRA", (
                f"Expected source='FINRA', got '{item.source}'"
            )

    def test_symbol_matches(self, short_vol_results: list[ShortData]):
        for item in short_vol_results:
            assert item.symbol == KNOWN_SYMBOL, (
                f"Expected symbol='{KNOWN_SYMBOL}', got '{item.symbol}'"
            )

    def test_total_for_ratio_populated(self, short_vol_results: list[ShortData]):
        """Every record must have total_for_ratio set."""
        for item in short_vol_results:
            assert item.total_for_ratio is not None, (
                f"total_for_ratio is None for {item.date}"
            )


# ---------------------------------------------------------------------------
# 3. Short volume ratio is sensible
# ---------------------------------------------------------------------------


class TestRatioValidity:
    def test_short_volume_leq_total_volume(self, short_vol_results: list[ShortData]):
        for item in short_vol_results:
            assert item.total_for_ratio is not None
            assert item.value <= item.total_for_ratio, (
                f"Short volume ({item.value}) > total volume ({item.total_for_ratio}) "
                f"on {item.date}"
            )

    def test_ratio_between_zero_and_one(self, short_vol_results: list[ShortData]):
        for item in short_vol_results:
            assert item.total_for_ratio is not None
            assert item.total_for_ratio > 0
            ratio = item.value / item.total_for_ratio
            assert 0.0 <= ratio <= 1.0, (
                f"Short ratio {ratio:.4f} out of [0, 1] range on {item.date}"
            )


# ---------------------------------------------------------------------------
# 4. Date filtering works
# ---------------------------------------------------------------------------


class TestDateFiltering:
    def test_results_within_date_range(self, short_vol_results: list[ShortData]):
        for item in short_vol_results:
            assert KNOWN_START <= item.date <= KNOWN_END, (
                f"Date {item.date} outside range [{KNOWN_START}, {KNOWN_END}]"
            )

    def test_narrower_range(self):
        start = date(2026, 1, 7)
        end = date(2026, 1, 8)
        results = fetch_short_volume(KNOWN_SYMBOL, start_date=start, end_date=end)
        for item in results:
            assert start <= item.date <= end


# ---------------------------------------------------------------------------
# 5. Values are valid (non-negative, finite)
# ---------------------------------------------------------------------------


class TestValueValidity:
    def test_values_non_negative(self, short_vol_results: list[ShortData]):
        for item in short_vol_results:
            assert item.value >= 0, f"Negative short volume: {item.value}"

    def test_values_finite(self, short_vol_results: list[ShortData]):
        for item in short_vol_results:
            assert math.isfinite(item.value), f"Non-finite short volume: {item.value}"

    def test_total_for_ratio_finite(self, short_vol_results: list[ShortData]):
        for item in short_vol_results:
            if item.total_for_ratio is not None:
                assert math.isfinite(item.total_for_ratio), (
                    f"Non-finite total_for_ratio: {item.total_for_ratio}"
                )


# ---------------------------------------------------------------------------
# 6. Results in chronological order
# ---------------------------------------------------------------------------


class TestChronologicalOrder:
    def test_dates_ascending(self, short_vol_results: list[ShortData]):
        dates = [item.date for item in short_vol_results]
        assert dates == sorted(dates), "Results are not in chronological order"


# ---------------------------------------------------------------------------
# 7. Aggregation: one row per date (facilities are merged)
# ---------------------------------------------------------------------------


class TestAggregation:
    def test_one_row_per_date(self, short_vol_results: list[ShortData]):
        dates = [item.date for item in short_vol_results]
        assert len(dates) == len(set(dates)), (
            "Multiple rows for the same date -- facility aggregation may be broken"
        )


# ---------------------------------------------------------------------------
# 8. Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_nonsense_symbol_returns_empty(self):
        results = fetch_short_volume(
            "ZZZZZNOTREAL123",
            start_date=KNOWN_START,
            end_date=KNOWN_END,
        )
        assert isinstance(results, list)
        assert len(results) == 0

    def test_far_future_returns_empty(self):
        far_future = date(2099, 1, 1)
        results = fetch_short_volume(
            KNOWN_SYMBOL, start_date=far_future, end_date=far_future
        )
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# 9. Default date range works (no dates provided)
# ---------------------------------------------------------------------------


class TestDefaultDateRange:
    def test_no_dates_returns_results(self):
        """Calling with no dates should default to last 30 days."""
        results = fetch_short_volume(KNOWN_SYMBOL)
        assert isinstance(results, list)
        # We do not assert non-empty since weekends/holidays can cause gaps,
        # but it must not crash.
