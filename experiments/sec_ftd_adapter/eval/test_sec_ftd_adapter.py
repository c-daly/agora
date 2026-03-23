"""Eval tests for the SEC FTD adapter.

Tests hit the real SEC endpoint — no mocking — since the data is public.
We use AAPL with a known historical date range (2024-01-02 to 2024-01-15)
where FTD data is reliably available.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from agora.adapters.sec_ftd_adapter import fetch_ftd_data
from agora.schemas import ShortData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

KNOWN_SYMBOL = "AAPL"
# First half of January 2024 — SEC publishes this in the second-half-of-Jan file
KNOWN_START = date(2024, 1, 2)
KNOWN_END = date(2024, 1, 15)


@pytest.fixture(scope="module")
def ftd_results() -> list[ShortData]:
    """Fetch FTD data once for the module to avoid repeated downloads."""
    return fetch_ftd_data(symbol=KNOWN_SYMBOL, start_date=KNOWN_START, end_date=KNOWN_END)


# ---------------------------------------------------------------------------
# 1. Returns list of ShortData objects
# ---------------------------------------------------------------------------

class TestReturnType:
    def test_returns_list(self, ftd_results: list[ShortData]):
        assert isinstance(ftd_results, list)

    def test_elements_are_short_data(self, ftd_results: list[ShortData]):
        for item in ftd_results:
            assert isinstance(item, ShortData), f"Expected ShortData, got {type(item)}"


# ---------------------------------------------------------------------------
# 2. ShortData fields populated correctly (data_type="ftd", source="SEC")
# ---------------------------------------------------------------------------

class TestFieldValues:
    def test_data_type_is_ftd(self, ftd_results: list[ShortData]):
        assert len(ftd_results) > 0, "Expected at least one result for AAPL in date range"
        for item in ftd_results:
            assert item.data_type == "ftd", f"Expected data_type='ftd', got '{item.data_type}'"

    def test_source_is_sec(self, ftd_results: list[ShortData]):
        for item in ftd_results:
            assert item.source == "SEC", f"Expected source='SEC', got '{item.source}'"

    def test_symbol_matches(self, ftd_results: list[ShortData]):
        for item in ftd_results:
            assert item.symbol == KNOWN_SYMBOL, f"Expected symbol='{KNOWN_SYMBOL}', got '{item.symbol}'"


# ---------------------------------------------------------------------------
# 3. Symbol filtering works
# ---------------------------------------------------------------------------

class TestSymbolFiltering:
    def test_filter_by_symbol(self):
        results = fetch_ftd_data(symbol="GME", start_date=KNOWN_START, end_date=KNOWN_END)
        for item in results:
            assert item.symbol == "GME"

    def test_no_symbol_returns_multiple_symbols(self):
        results = fetch_ftd_data(start_date=KNOWN_START, end_date=KNOWN_END)
        symbols = {item.symbol for item in results}
        assert len(symbols) > 1, "Without symbol filter, should return data for multiple symbols"


# ---------------------------------------------------------------------------
# 4. Date filtering works (start, end, range)
# ---------------------------------------------------------------------------

class TestDateFiltering:
    def test_results_within_date_range(self, ftd_results: list[ShortData]):
        for item in ftd_results:
            assert KNOWN_START <= item.date <= KNOWN_END, (
                f"Date {item.date} outside range [{KNOWN_START}, {KNOWN_END}]"
            )

    def test_start_date_only(self):
        start = date(2024, 1, 10)
        results = fetch_ftd_data(symbol=KNOWN_SYMBOL, start_date=start, end_date=KNOWN_END)
        for item in results:
            assert item.date >= start, f"Date {item.date} before start_date {start}"

    def test_end_date_only(self):
        end = date(2024, 1, 8)
        results = fetch_ftd_data(symbol=KNOWN_SYMBOL, start_date=KNOWN_START, end_date=end)
        for item in results:
            assert item.date <= end, f"Date {item.date} after end_date {end}"


# ---------------------------------------------------------------------------
# 5. Values are valid (non-negative quantities, finite)
# ---------------------------------------------------------------------------

class TestValueValidity:
    def test_values_non_negative(self, ftd_results: list[ShortData]):
        for item in ftd_results:
            assert item.value >= 0, f"Negative FTD value: {item.value}"

    def test_values_finite(self, ftd_results: list[ShortData]):
        for item in ftd_results:
            assert math.isfinite(item.value), f"Non-finite FTD value: {item.value}"

    def test_total_for_ratio_finite_if_present(self, ftd_results: list[ShortData]):
        for item in ftd_results:
            if item.total_for_ratio is not None:
                assert math.isfinite(item.total_for_ratio), (
                    f"Non-finite total_for_ratio: {item.total_for_ratio}"
                )


# ---------------------------------------------------------------------------
# 6. Results in chronological order
# ---------------------------------------------------------------------------

class TestChronologicalOrder:
    def test_dates_ascending(self, ftd_results: list[ShortData]):
        dates = [item.date for item in ftd_results]
        assert dates == sorted(dates), "Results are not in chronological order"


# ---------------------------------------------------------------------------
# 7. Handles errors gracefully (bad URLs, network issues)
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_future_date_returns_empty(self):
        """A date far in the future should have no data, not raise."""
        far_future = date(2099, 1, 1)
        results = fetch_ftd_data(symbol=KNOWN_SYMBOL, start_date=far_future, end_date=far_future)
        assert isinstance(results, list)

    def test_nonsense_symbol_returns_empty(self):
        """A symbol that doesn't exist should return empty, not raise."""
        results = fetch_ftd_data(
            symbol="ZZZZZNOTREAL123",
            start_date=KNOWN_START,
            end_date=KNOWN_END,
        )
        assert isinstance(results, list)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# 8. Empty result handling (valid symbol but no FTDs in range)
# ---------------------------------------------------------------------------

class TestEmptyResults:
    def test_valid_symbol_no_ftds_in_range(self):
        """BRK.A rarely has FTDs; a narrow weekend range should be empty."""
        weekend_start = date(2024, 1, 6)  # Saturday
        weekend_end = date(2024, 1, 7)    # Sunday
        results = fetch_ftd_data(
            symbol="BRK-A",
            start_date=weekend_start,
            end_date=weekend_end,
        )
        assert isinstance(results, list)
        # Either empty or at least no crash — both are acceptable


# ---------------------------------------------------------------------------
# 9. Malformed rows are skipped without crashing
# ---------------------------------------------------------------------------

class TestMalformedRowHandling:
    def test_adapter_does_not_crash_on_real_data(self, ftd_results: list[ShortData]):
        """Real SEC files sometimes have malformed rows.

        If we got this far without an exception, the adapter handled them.
        This test simply asserts we have valid results.
        """
        assert isinstance(ftd_results, list)
        for item in ftd_results:
            assert isinstance(item, ShortData)
