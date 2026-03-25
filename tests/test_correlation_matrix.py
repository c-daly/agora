"""Tests for the correlation_matrix quant analysis module."""

from __future__ import annotations

import numpy as np
import pytest

from agora.analysis.quant.correlation_matrix import (
    compute_correlation_matrix,
    compute_rolling_correlation,
    detect_regime_change,
)


@pytest.fixture()
def two_symbol_returns():
    """Two symbols with 100 daily returns: AAPL and MSFT positively correlated."""
    rng = np.random.default_rng(42)
    common = rng.normal(0, 0.01, 100)
    noise_a = rng.normal(0, 0.005, 100)
    noise_b = rng.normal(0, 0.005, 100)
    return {
        "AAPL": (common + noise_a).tolist(),
        "MSFT": (common + noise_b).tolist(),
    }


@pytest.fixture()
def three_symbol_returns():
    """Three symbols with 120 daily returns for rolling tests."""
    rng = np.random.default_rng(123)
    common = rng.normal(0, 0.01, 120)
    return {
        "AAPL": (common + rng.normal(0, 0.003, 120)).tolist(),
        "GOOG": (common + rng.normal(0, 0.003, 120)).tolist(),
        "MSFT": (common + rng.normal(0, 0.003, 120)).tolist(),
    }


@pytest.fixture()
def regime_shift_returns():
    """Returns that shift from uncorrelated to highly correlated mid-series."""
    rng = np.random.default_rng(99)
    n_half = 40
    a_first = rng.normal(0, 0.01, n_half).tolist()
    b_first = rng.normal(0, 0.01, n_half).tolist()
    c_first = rng.normal(0, 0.01, n_half).tolist()
    common = rng.normal(0, 0.01, n_half)
    a_second = (common + rng.normal(0, 0.001, n_half)).tolist()
    b_second = (common + rng.normal(0, 0.001, n_half)).tolist()
    c_second = (common + rng.normal(0, 0.001, n_half)).tolist()
    return {
        "X": a_first + a_second,
        "Y": b_first + b_second,
        "Z": c_first + c_second,
    }


class TestComputeCorrelationMatrix:
    def test_empty_returns(self):
        result = compute_correlation_matrix({})
        assert result == {"symbols": [], "matrix": []}

    def test_single_symbol(self):
        result = compute_correlation_matrix({"AAPL": [0.01, -0.02, 0.03]})
        assert result["symbols"] == ["AAPL"]
        assert result["matrix"] == [[1.0]]

    def test_two_symbols_shape(self, two_symbol_returns):
        result = compute_correlation_matrix(two_symbol_returns)
        assert result["symbols"] == ["AAPL", "MSFT"]
        matrix = result["matrix"]
        assert len(matrix) == 2
        assert len(matrix[0]) == 2

    def test_diagonal_is_one(self, two_symbol_returns):
        result = compute_correlation_matrix(two_symbol_returns)
        matrix = result["matrix"]
        assert matrix[0][0] == pytest.approx(1.0)
        assert matrix[1][1] == pytest.approx(1.0)

    def test_symmetric(self, two_symbol_returns):
        result = compute_correlation_matrix(two_symbol_returns)
        matrix = result["matrix"]
        assert matrix[0][1] == pytest.approx(matrix[1][0])

    def test_positive_correlation(self, two_symbol_returns):
        """AAPL and MSFT share a common factor, so correlation should be positive."""
        result = compute_correlation_matrix(two_symbol_returns)
        assert result["matrix"][0][1] > 0.3

    def test_symbols_sorted(self):
        returns = {
            "ZZZ": [0.01, 0.02],
            "AAA": [0.03, 0.04],
            "MMM": [0.05, 0.06],
        }
        result = compute_correlation_matrix(returns)
        assert result["symbols"] == ["AAA", "MMM", "ZZZ"]

    def test_zero_variance_series(self):
        """A constant series should produce 0.0 correlation (NaN replaced)."""
        returns = {
            "FLAT": [0.0, 0.0, 0.0, 0.0, 0.0],
            "VARY": [0.01, -0.01, 0.02, -0.02, 0.03],
        }
        result = compute_correlation_matrix(returns)
        assert result["matrix"][0][1] == pytest.approx(0.0)


class TestComputeRollingCorrelation:
    def test_empty_returns(self):
        assert compute_rolling_correlation({}) == []

    def test_insufficient_data(self):
        returns = {"A": [0.01] * 30, "B": [0.02] * 30}
        assert compute_rolling_correlation(returns, window=60) == []

    def test_result_count(self, three_symbol_returns):
        """With 120 observations and window=60, expect 61 results."""
        results = compute_rolling_correlation(three_symbol_returns, window=60)
        assert len(results) == 61

    def test_date_indices(self, three_symbol_returns):
        results = compute_rolling_correlation(three_symbol_returns, window=60)
        assert results[0]["date_index"] == 59
        assert results[-1]["date_index"] == 119

    def test_matrix_shape(self, three_symbol_returns):
        results = compute_rolling_correlation(three_symbol_returns, window=60)
        for r in results:
            assert len(r["matrix"]) == 3
            for row in r["matrix"]:
                assert len(row) == 3

    def test_small_window(self):
        """Window=3 on 5 data points should produce 3 results."""
        rng = np.random.default_rng(7)
        returns = {
            "A": rng.normal(0, 0.01, 5).tolist(),
            "B": rng.normal(0, 0.01, 5).tolist(),
        }
        results = compute_rolling_correlation(returns, window=3)
        assert len(results) == 3
        assert results[0]["date_index"] == 2
        assert results[-1]["date_index"] == 4


class TestDetectRegimeChange:
    def test_empty_input(self):
        assert detect_regime_change([]) == []

    def test_single_entry(self):
        assert detect_regime_change([{"date_index": 0, "matrix": [[1.0]]}]) == []

    def test_no_change_below_threshold(self):
        """Two identical matrices should produce no regime change."""
        m = [[1.0, 0.5], [0.5, 1.0]]
        rolling = [
            {"date_index": 59, "matrix": m},
            {"date_index": 60, "matrix": m},
        ]
        assert detect_regime_change(rolling, threshold=0.3) == []

    def test_detects_large_shift(self):
        """A large jump in off-diagonal correlation should be detected."""
        m_low = [[1.0, 0.1, 0.1], [0.1, 1.0, 0.1], [0.1, 0.1, 1.0]]
        m_high = [[1.0, 0.9, 0.9], [0.9, 1.0, 0.9], [0.9, 0.9, 1.0]]
        rolling = [
            {"date_index": 59, "matrix": m_low},
            {"date_index": 60, "matrix": m_high},
        ]
        changes = detect_regime_change(rolling, threshold=0.3)
        assert len(changes) == 1
        assert changes[0]["date_index"] == 60
        assert changes[0]["direction"] == "increase"
        assert changes[0]["distance"] > 0.3

    def test_detects_decrease(self):
        """A drop in correlation should be flagged with direction=decrease."""
        m_high = [[1.0, 0.8], [0.8, 1.0]]
        m_low = [[1.0, 0.0], [0.0, 1.0]]
        rolling = [
            {"date_index": 59, "matrix": m_high},
            {"date_index": 60, "matrix": m_low},
        ]
        changes = detect_regime_change(rolling, threshold=0.3)
        assert len(changes) == 1
        assert changes[0]["direction"] == "decrease"

    def test_regime_shift_end_to_end(self, regime_shift_returns):
        """Full pipeline: rolling correlation then regime detection."""
        rolling = compute_rolling_correlation(regime_shift_returns, window=20)
        assert len(rolling) > 0
        changes = detect_regime_change(rolling, threshold=0.15)
        assert len(changes) >= 1
        mid_changes = [c for c in changes if 30 <= c["date_index"] <= 55]
        assert len(mid_changes) >= 1

    def test_distance_is_positive(self):
        """Distance should always be non-negative."""
        m1 = [[1.0, 0.2, 0.3], [0.2, 1.0, 0.1], [0.3, 0.1, 1.0]]
        m2 = [[1.0, 0.8, 0.7], [0.8, 1.0, 0.9], [0.7, 0.9, 1.0]]
        rolling = [
            {"date_index": 59, "matrix": m1},
            {"date_index": 60, "matrix": m2},
        ]
        changes = detect_regime_change(rolling, threshold=0.0)
        for c in changes:
            assert c["distance"] >= 0
