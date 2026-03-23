"""Eval tests for the FRED adapter.

These tests hit the real FRED API. Requires FRED_API_KEY env var.
"""

import math
from datetime import date

import pytest

from agora.adapters.fred_adapter import fetch_series
from agora.schemas import TimeSeries, TimeSeriesMetadata


class TestFetchSeries:
    """Core functionality: fetch a known series and verify shape."""

    def test_returns_list_of_timeseries(self, fred_api_key):
        """Fetching a known series returns a non-empty list of TimeSeries."""
        result = fetch_series("GDP", fred_api_key)
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, TimeSeries)

    def test_timeseries_fields(self, fred_api_key):
        """Each TimeSeries has date, value, and metadata with correct types."""
        result = fetch_series("GDP", fred_api_key)
        item = result[0]
        assert isinstance(item.date, date)
        assert isinstance(item.value, float)
        assert isinstance(item.metadata, TimeSeriesMetadata)

    def test_metadata_source_is_fred(self, fred_api_key):
        """Metadata source must be 'FRED'."""
        result = fetch_series("GDP", fred_api_key)
        for item in result:
            assert item.metadata.source == "FRED"

    def test_values_are_finite(self, fred_api_key):
        """All returned values must be finite numbers (no NaN, no inf)."""
        result = fetch_series("GDP", fred_api_key)
        for item in result:
            assert math.isfinite(item.value)


class TestDateFiltering:
    """Date range filtering."""

    def test_start_date_filter(self, fred_api_key):
        """start_date parameter limits results."""
        start = date(2020, 1, 1)
        result = fetch_series("GDP", fred_api_key, start_date=start)
        assert len(result) > 0
        for item in result:
            assert item.date >= start

    def test_end_date_filter(self, fred_api_key):
        """end_date parameter limits results."""
        end = date(2020, 12, 31)
        result = fetch_series("GDP", fred_api_key, end_date=end)
        assert len(result) > 0
        for item in result:
            assert item.date <= end

    def test_date_range(self, fred_api_key):
        """Both start and end date together."""
        start = date(2019, 1, 1)
        end = date(2020, 12, 31)
        result = fetch_series("GDP", fred_api_key, start_date=start, end_date=end)
        assert len(result) > 0
        for item in result:
            assert start <= item.date <= end


class TestErrorHandling:
    """Graceful handling of bad inputs and API errors."""

    def test_invalid_series_id(self, fred_api_key):
        """Non-existent series raises a descriptive exception, not a crash."""
        with pytest.raises(Exception) as exc_info:
            fetch_series("DEFINITELY_NOT_A_REAL_SERIES_XYZ123", fred_api_key)
        # Should have a meaningful message, not a raw HTTP error
        assert len(str(exc_info.value)) > 0

    def test_invalid_api_key(self):
        """Bad API key raises a descriptive exception."""
        with pytest.raises(Exception) as exc_info:
            fetch_series("GDP", "not_a_valid_key")
        assert len(str(exc_info.value)) > 0


class TestMissingValues:
    """FRED returns '.' for missing observations. Adapter must skip them."""

    def test_no_missing_values_in_output(self, fred_api_key):
        """Returned list should not contain entries for missing observations."""
        # DFF (federal funds rate) is daily and sometimes has gaps
        result = fetch_series(
            "DFF", fred_api_key, start_date=date(2020, 1, 1), end_date=date(2020, 3, 31)
        )
        for item in result:
            assert isinstance(item.value, float)
            assert math.isfinite(item.value)
