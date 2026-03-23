"""Eval tests for the FRED adapter."""

import math
from datetime import date

import pytest

from agora.adapters.fred_adapter import fetch_series
from agora.schemas import TimeSeries, TimeSeriesMetadata


class TestSchemaCompliance:
    """Returns correctly shaped TimeSeries objects."""

    def test_returns_list_of_timeseries(self, fred_api_key):
        result = fetch_series("GDP", fred_api_key)
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, TimeSeries)

    def test_timeseries_fields(self, fred_api_key):
        result = fetch_series("GDP", fred_api_key)
        item = result[0]
        assert isinstance(item.date, date)
        assert isinstance(item.value, float)
        assert isinstance(item.metadata, TimeSeriesMetadata)

    def test_metadata_source_is_fred(self, fred_api_key):
        result = fetch_series("GDP", fred_api_key)
        for item in result:
            assert item.metadata.source == "FRED"

    def test_metadata_fields_populated(self, fred_api_key):
        """Metadata should include unit and frequency when available."""
        result = fetch_series("GDP", fred_api_key)
        item = result[0]
        assert item.metadata.unit is not None or item.metadata.frequency is not None

    def test_values_are_finite(self, fred_api_key):
        result = fetch_series("GDP", fred_api_key)
        for item in result:
            assert math.isfinite(item.value)

    def test_results_in_chronological_order(self, fred_api_key):
        result = fetch_series("GDP", fred_api_key)
        dates = [item.date for item in result]
        assert dates == sorted(dates)


class TestDateFiltering:
    """Date range filtering."""

    def test_start_date_filter(self, fred_api_key):
        start = date(2020, 1, 1)
        result = fetch_series("GDP", fred_api_key, start_date=start)
        assert len(result) > 0
        for item in result:
            assert item.date >= start

    def test_end_date_filter(self, fred_api_key):
        end = date(2020, 12, 31)
        result = fetch_series("GDP", fred_api_key, end_date=end)
        assert len(result) > 0
        for item in result:
            assert item.date <= end

    def test_date_range(self, fred_api_key):
        start = date(2019, 1, 1)
        end = date(2020, 12, 31)
        result = fetch_series("GDP", fred_api_key, start_date=start, end_date=end)
        assert len(result) > 0
        for item in result:
            assert start <= item.date <= end

    def test_empty_date_range(self, fred_api_key):
        """Valid series but no data in range — should return empty list, not error."""
        result = fetch_series(
            "GDP", fred_api_key, start_date=date(1800, 1, 1), end_date=date(1800, 12, 31)
        )
        assert isinstance(result, list)
        assert len(result) == 0


class TestErrorHandling:
    """Graceful handling of bad inputs."""

    def test_invalid_series_raises_with_message(self, fred_api_key):
        with pytest.raises(Exception, match=r".+"):
            fetch_series("DEFINITELY_NOT_A_REAL_SERIES_XYZ123", fred_api_key)

    def test_invalid_api_key_raises_with_message(self):
        with pytest.raises(Exception, match=r".+"):
            fetch_series("GDP", "not_a_valid_key")


class TestMissingValues:
    """FRED missing observations must be skipped."""

    def test_no_missing_values_in_output(self, fred_api_key):
        result = fetch_series(
            "DFF", fred_api_key, start_date=date(2020, 1, 1), end_date=date(2020, 3, 31)
        )
        for item in result:
            assert isinstance(item.value, float)
            assert math.isfinite(item.value)
