"""Eval tests for the treasury_adapter experiment.

Tests hit the real Treasury.gov endpoint (no API key required).
Uses a known date range (2023-01-01 to 2023-03-31) that has data.
"""

import math
from datetime import date

import pytest

from agora.adapters.treasury_adapter import fetch_yields
from agora.schemas import TimeSeries, TimeSeriesMetadata

# ---------------------------------------------------------------------------
# Known good parameters
# ---------------------------------------------------------------------------
START = date(2023, 1, 1)
END = date(2023, 3, 31)
KNOWN_MATURITIES = ["1mo", "3mo", "6mo", "1yr", "2yr", "3yr", "5yr", "7yr", "10yr", "20yr", "30yr"]


# ---------------------------------------------------------------------------
# 1. Returns list of TimeSeries objects
# ---------------------------------------------------------------------------
class TestReturnType:
    def test_returns_list(self):
        results = fetch_yields(start_date=START, end_date=END)
        assert isinstance(results, list), "fetch_yields must return a list"

    def test_elements_are_timeseries(self):
        results = fetch_yields(start_date=START, end_date=END)
        assert len(results) > 0, "Expected non-empty results for known date range"
        for ts in results:
            assert isinstance(ts, TimeSeries), (
                f"Each element must be a TimeSeries, got {type(ts)}"
            )


# ---------------------------------------------------------------------------
# 2. TimeSeries fields populated correctly
# ---------------------------------------------------------------------------
class TestFieldsPopulated:
    def test_date_field(self):
        results = fetch_yields(start_date=START, end_date=END)
        for ts in results:
            assert isinstance(ts.date, date), "date field must be a date"

    def test_value_field(self):
        results = fetch_yields(start_date=START, end_date=END)
        for ts in results:
            assert isinstance(ts.value, float), "value field must be a float"

    def test_metadata_source(self):
        results = fetch_yields(start_date=START, end_date=END)
        for ts in results:
            assert isinstance(ts.metadata, TimeSeriesMetadata)
            assert ts.metadata.source == "TREASURY", (
                f"metadata.source must be 'TREASURY', got '{ts.metadata.source}'"
            )


# ---------------------------------------------------------------------------
# 3. Metadata includes unit (maturity label) and frequency
# ---------------------------------------------------------------------------
class TestMetadataDetails:
    def test_unit_is_maturity_label(self):
        results = fetch_yields(
            maturities=["10yr"], start_date=START, end_date=END
        )
        assert len(results) > 0
        for ts in results:
            assert ts.metadata.unit is not None, "metadata.unit must not be None"
            assert ts.metadata.unit == "10yr", (
                f"metadata.unit should be the maturity label, got '{ts.metadata.unit}'"
            )

    def test_frequency_set(self):
        results = fetch_yields(start_date=START, end_date=END)
        assert len(results) > 0
        for ts in results:
            assert ts.metadata.frequency is not None, (
                "metadata.frequency must not be None"
            )


# ---------------------------------------------------------------------------
# 4. Maturity filtering works (request specific maturities)
# ---------------------------------------------------------------------------
class TestMaturityFiltering:
    def test_single_maturity(self):
        results = fetch_yields(
            maturities=["5yr"], start_date=START, end_date=END
        )
        assert len(results) > 0
        units = {ts.metadata.unit for ts in results}
        assert units == {"5yr"}, f"Expected only '5yr', got {units}"

    def test_multiple_maturities(self):
        requested = ["2yr", "10yr"]
        results = fetch_yields(
            maturities=requested, start_date=START, end_date=END
        )
        assert len(results) > 0
        units = {ts.metadata.unit for ts in results}
        assert units == set(requested), (
            f"Expected {set(requested)}, got {units}"
        )

    def test_all_maturities_when_none(self):
        """When maturities=None, should return data for multiple maturities."""
        results = fetch_yields(start_date=START, end_date=END)
        units = {ts.metadata.unit for ts in results}
        assert len(units) > 1, (
            "With no maturity filter, should return multiple maturities"
        )


# ---------------------------------------------------------------------------
# 5. Date filtering works (start, end, range)
# ---------------------------------------------------------------------------
class TestDateFiltering:
    def test_start_date_only(self):
        start = date(2023, 3, 1)
        results = fetch_yields(maturities=["10yr"], start_date=start)
        assert len(results) > 0
        for ts in results:
            assert ts.date >= start, (
                f"All dates must be >= start_date, got {ts.date}"
            )

    def test_end_date_only(self):
        end = date(2023, 1, 31)
        results = fetch_yields(maturities=["10yr"], end_date=end)
        assert len(results) > 0
        for ts in results:
            assert ts.date <= end, (
                f"All dates must be <= end_date, got {ts.date}"
            )

    def test_date_range(self):
        results = fetch_yields(
            maturities=["10yr"], start_date=START, end_date=END
        )
        assert len(results) > 0
        for ts in results:
            assert START <= ts.date <= END, (
                f"Date {ts.date} outside range [{START}, {END}]"
            )


# ---------------------------------------------------------------------------
# 6. Values are valid (finite, positive yields — yields can be very small)
# ---------------------------------------------------------------------------
class TestValueValidity:
    def test_values_are_finite(self):
        results = fetch_yields(
            maturities=["10yr"], start_date=START, end_date=END
        )
        for ts in results:
            assert math.isfinite(ts.value), f"Value must be finite, got {ts.value}"

    def test_values_are_positive(self):
        """Treasury yields in 2023 were all positive."""
        results = fetch_yields(
            maturities=["10yr"], start_date=START, end_date=END
        )
        for ts in results:
            assert ts.value > 0, f"Expected positive yield, got {ts.value}"


# ---------------------------------------------------------------------------
# 7. Results in chronological order
# ---------------------------------------------------------------------------
class TestChronologicalOrder:
    def test_sorted_by_date(self):
        results = fetch_yields(
            maturities=["10yr"], start_date=START, end_date=END
        )
        assert len(results) > 1, "Need multiple results to test ordering"
        dates = [ts.date for ts in results]
        assert dates == sorted(dates), "Results must be in chronological order"


# ---------------------------------------------------------------------------
# 8. Handles errors gracefully
# ---------------------------------------------------------------------------
class TestErrorHandling:
    def test_invalid_maturity_does_not_crash(self):
        """An unrecognised maturity label should not raise an unhandled exception.
        It may return an empty list or raise a clear ValueError."""
        try:
            results = fetch_yields(
                maturities=["999yr"], start_date=START, end_date=END
            )
            # Returning an empty list is acceptable
            assert isinstance(results, list)
        except (ValueError, KeyError):
            # A clear domain error is also acceptable
            pass

    def test_impossible_date_range(self):
        """start > end should return empty or raise ValueError, not crash."""
        try:
            results = fetch_yields(
                start_date=date(2023, 12, 31), end_date=date(2023, 1, 1)
            )
            assert isinstance(results, list)
            assert len(results) == 0
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# 9. Empty result handling (valid maturity but no data in range)
# ---------------------------------------------------------------------------
class TestEmptyResults:
    def test_weekend_returns_empty_or_skips(self):
        """Treasury markets are closed on weekends; a Sat-Sun range should
        return an empty list (not an error)."""
        # 2023-01-07 is a Saturday, 2023-01-08 is a Sunday
        results = fetch_yields(
            maturities=["10yr"],
            start_date=date(2023, 1, 7),
            end_date=date(2023, 1, 8),
        )
        assert isinstance(results, list)
        assert len(results) == 0, (
            "Expected empty list for weekend-only date range"
        )


# ---------------------------------------------------------------------------
# 10. Missing data points are skipped (some maturities have gaps)
# ---------------------------------------------------------------------------
class TestMissingDataSkipped:
    def test_no_none_values(self):
        """Even when requesting all maturities, no TimeSeries should have
        None as its value — missing data points should be skipped entirely."""
        results = fetch_yields(start_date=START, end_date=END)
        for ts in results:
            assert ts.value is not None, "Skipped data should be omitted, not None"

    def test_multiple_maturities_may_differ_in_count(self):
        """Different maturities may have different numbers of data points
        due to gaps. This is expected and should not cause errors."""
        all_results = fetch_yields(start_date=START, end_date=END)
        by_maturity: dict[str, int] = {}
        for ts in all_results:
            by_maturity[ts.metadata.unit] = by_maturity.get(ts.metadata.unit, 0) + 1
        # We just verify we got data and no crashes — count differences are fine
        assert len(by_maturity) > 0, "Should have data for at least one maturity"
