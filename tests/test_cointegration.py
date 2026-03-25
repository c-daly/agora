"""Tests for agora.analysis.quant.cointegration module."""

from __future__ import annotations

import numpy as np
import pytest

from agora.analysis.quant.cointegration import (
    compute_spread,
    check_cointegration,
)

# ------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------


@pytest.fixture()
def cointegrated_pair() -> tuple[list[float], list[float]]:
    """Generate a cointegrated pair.

    series_a = 2 * series_b + noise  (where series_b is a random walk).
    The residuals are stationary by construction.
    """
    rng = np.random.default_rng(seed=42)
    n = 200
    # Random walk for series_b
    b = np.cumsum(rng.normal(0.0, 1.0, n)) + 100.0
    # Cointegrated series: a = 2*b + 5 + stationary noise
    noise = rng.normal(0.0, 0.5, n)
    a = 2.0 * b + 5.0 + noise
    return a.tolist(), b.tolist()


@pytest.fixture()
def non_cointegrated_pair() -> tuple[list[float], list[float]]:
    """Generate two independent random walks (no cointegration)."""
    rng = np.random.default_rng(seed=99)
    n = 200
    a = np.cumsum(rng.normal(0.0, 1.0, n)) + 100.0
    b = np.cumsum(rng.normal(0.0, 1.0, n)) + 100.0
    return a.tolist(), b.tolist()


# ------------------------------------------------------------
# check_cointegration
# ------------------------------------------------------------


class TestCointegrationResult:
    """Tests for check_cointegration return values."""

    def test_cointegrated_pair_detected(self, cointegrated_pair):
        a, b = cointegrated_pair
        result = check_cointegration(a, b)
        assert result["cointegrated"] is True
        assert result["p_value"] < 0.05

    def test_cointegrated_hedge_ratio_near_two(self, cointegrated_pair):
        """The generating process uses hedge_ratio=2.0."""
        a, b = cointegrated_pair
        result = check_cointegration(a, b)
        assert abs(result["hedge_ratio"] - 2.0) < 0.1

    def test_non_cointegrated_pair_not_detected(self, non_cointegrated_pair):
        a, b = non_cointegrated_pair
        result = check_cointegration(a, b)
        assert result["cointegrated"] is False
        assert result["p_value"] >= 0.05

    def test_result_keys(self, cointegrated_pair):
        a, b = cointegrated_pair
        result = check_cointegration(a, b)
        expected_keys = {"cointegrated", "p_value", "hedge_ratio", "spread_mean", "spread_std"}
        assert set(result.keys()) == expected_keys

    def test_spread_mean_near_zero(self, cointegrated_pair):
        """OLS residuals should have mean ~= 0."""
        a, b = cointegrated_pair
        result = check_cointegration(a, b)
        assert abs(result["spread_mean"]) < 1.0

    def test_spread_std_positive(self, cointegrated_pair):
        a, b = cointegrated_pair
        result = check_cointegration(a, b)
        assert result["spread_std"] > 0.0


# ------------------------------------------------------------
# compute_spread
# ------------------------------------------------------------


class TestComputeSpread:
    """Tests for compute_spread."""

    def test_basic_spread(self):
        a = [10.0, 20.0, 30.0]
        b = [5.0, 10.0, 15.0]
        result = compute_spread(a, b, hedge_ratio=2.0)
        assert result == [0.0, 0.0, 0.0]

    def test_spread_length_matches_input(self, cointegrated_pair):
        a, b = cointegrated_pair
        result = check_cointegration(a, b)
        spread = compute_spread(a, b, result["hedge_ratio"])
        assert len(spread) == len(a)

    def test_empty_series(self):
        assert compute_spread([], [], 1.0) == []

    def test_hedge_ratio_one(self):
        a = [5.0, 10.0, 15.0]
        b = [3.0, 8.0, 12.0]
        result = compute_spread(a, b, hedge_ratio=1.0)
        assert result == [2.0, 2.0, 3.0]

    def test_length_mismatch(self):
        with pytest.raises(ValueError, match="length mismatch"):
            compute_spread([1.0, 2.0], [1.0], 1.0)


# ------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------


class TestEdgeCases:
    """Validation edge cases for check_cointegration."""

    def test_insufficient_data(self):
        with pytest.raises(ValueError, match="Insufficient data"):
            check_cointegration(list(range(10)), list(range(10)))

    def test_length_mismatch(self):
        with pytest.raises(ValueError, match="length mismatch"):
            check_cointegration(list(range(50)), list(range(40)))

    def test_constant_series_a(self):
        with pytest.raises(ValueError, match="series_a is constant"):
            check_cointegration([5.0] * 50, list(range(50)))

    def test_constant_series_b(self):
        with pytest.raises(ValueError, match="series_b is constant"):
            check_cointegration(list(range(50)), [5.0] * 50)

    def test_identical_series(self):
        s = list(range(50))
        with pytest.raises(ValueError, match="identical"):
            check_cointegration(s, s.copy())

    def test_exactly_30_observations(self):
        """30 observations is the minimum -- should not raise."""
        rng = np.random.default_rng(seed=77)
        b = np.cumsum(rng.normal(0.0, 1.0, 30)) + 100.0
        a = 2.0 * b + rng.normal(0.0, 0.5, 30)
        result = check_cointegration(a.tolist(), b.tolist())
        assert "cointegrated" in result
