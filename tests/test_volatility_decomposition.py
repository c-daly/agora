"""Tests for agora.analysis.quant.volatility_decomposition."""

from __future__ import annotations

import math

import numpy as np
import pytest

from agora.analysis.quant.volatility_decomposition import (
    compute_variance_risk_premium,
    decompose_volatility,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_prices():
    """Five days of close/open data with known behaviour."""
    close = [100.0, 102.0, 101.0, 103.0, 104.0]
    opn = [100.5, 101.5, 101.0, 102.5, 103.5]
    return close, opn


@pytest.fixture()
def flat_prices():
    """Constant prices -- zero volatility."""
    close = [100.0, 100.0, 100.0, 100.0]
    opn = [100.0, 100.0, 100.0, 100.0]
    return close, opn


@pytest.fixture()
def trending_prices():
    """Steadily increasing prices over 20 days."""
    np.random.seed(42)
    n = 20
    close = [100.0]
    opn = [100.0]
    for _ in range(n - 1):
        gap = np.random.uniform(0.001, 0.005)
        new_open = close[-1] * (1 + gap)
        intraday = np.random.uniform(-0.002, 0.01)
        new_close = new_open * (1 + intraday)
        opn.append(round(new_open, 4))
        close.append(round(new_close, 4))
    return close, opn


# ---------------------------------------------------------------------------
# decompose_volatility -- happy path
# ---------------------------------------------------------------------------


class TestDecomposeVolatility:
    def test_returns_expected_keys(self, simple_prices):
        close, opn = simple_prices
        result = decompose_volatility(close, opn)
        expected_keys = {
            "total_vol",
            "overnight_vol",
            "intraday_vol",
            "overnight_fraction",
            "n_periods",
        }
        assert set(result.keys()) == expected_keys

    def test_n_periods(self, simple_prices):
        close, opn = simple_prices
        result = decompose_volatility(close, opn)
        assert result["n_periods"] == len(close) - 1

    def test_volatilities_are_non_negative(self, simple_prices):
        close, opn = simple_prices
        result = decompose_volatility(close, opn)
        assert result["total_vol"] >= 0
        assert result["overnight_vol"] >= 0
        assert result["intraday_vol"] >= 0

    def test_overnight_fraction_between_zero_and_one(self, trending_prices):
        close, opn = trending_prices
        result = decompose_volatility(close, opn)
        assert 0.0 <= result["overnight_fraction"] <= 1.0

    def test_flat_prices_give_zero_vol(self, flat_prices):
        close, opn = flat_prices
        result = decompose_volatility(close, opn)
        assert result["total_vol"] == 0.0
        assert result["overnight_vol"] == 0.0
        assert result["intraday_vol"] == 0.0
        assert result["overnight_fraction"] == 0.0

    def test_two_prices_minimum(self):
        """Exactly 2 observations should work (1 return)."""
        close = [100.0, 102.0]
        opn = [100.0, 101.0]
        result = decompose_volatility(close, opn)
        assert result["n_periods"] == 1
        # With a single return, std with ddof=1 is NaN; we should still get a dict
        # but the vol values will be NaN since std of a single value with ddof=1 is undefined

    def test_annualization_factor(self, trending_prices):
        """Verify annualized vol is roughly sqrt(252) times daily vol."""
        close, opn = trending_prices
        result = decompose_volatility(close, opn)

        # Manually compute daily total std
        c = np.array(close, dtype=np.float64)
        daily_returns = c[1:] / c[:-1] - 1.0
        daily_std = float(np.std(daily_returns, ddof=1))
        expected_annual = daily_std * math.sqrt(252)

        assert abs(result["total_vol"] - expected_annual) < 1e-6


# ---------------------------------------------------------------------------
# decompose_volatility -- edge cases / errors
# ---------------------------------------------------------------------------


class TestDecomposeVolatilityEdgeCases:
    def test_mismatched_lengths(self):
        with pytest.raises(ValueError, match="same length"):
            decompose_volatility([100.0, 101.0], [100.0])

    def test_too_few_observations_empty(self):
        with pytest.raises(ValueError, match="at least 2"):
            decompose_volatility([], [])

    def test_too_few_observations_single(self):
        with pytest.raises(ValueError, match="at least 2"):
            decompose_volatility([100.0], [100.0])

    def test_zero_close_price(self):
        with pytest.raises(ValueError, match="close_prices.*positive"):
            decompose_volatility([0.0, 100.0], [100.0, 100.0])

    def test_negative_open_price(self):
        with pytest.raises(ValueError, match="open_prices.*positive"):
            decompose_volatility([100.0, 101.0], [100.0, -1.0])

    def test_zero_open_price(self):
        with pytest.raises(ValueError, match="open_prices.*positive"):
            decompose_volatility([100.0, 101.0], [100.0, 0.0])

    def test_negative_close_price(self):
        with pytest.raises(ValueError, match="close_prices.*positive"):
            decompose_volatility([100.0, -50.0], [100.0, 100.0])


# ---------------------------------------------------------------------------
# compute_variance_risk_premium -- happy path
# ---------------------------------------------------------------------------


class TestVarianceRiskPremium:
    def test_returns_expected_keys(self):
        result = compute_variance_risk_premium(0.20, 0.25)
        expected_keys = {
            "realized_vol",
            "implied_vol",
            "realized_var",
            "implied_var",
            "vrp",
            "vrp_ratio",
            "signal",
        }
        assert set(result.keys()) == expected_keys

    def test_rich_signal(self):
        """Implied > realized => positive VRP => rich."""
        result = compute_variance_risk_premium(0.15, 0.25)
        assert result["vrp"] > 0
        assert result["signal"] == "rich"

    def test_cheap_signal(self):
        """Implied < realized => negative VRP => cheap."""
        result = compute_variance_risk_premium(0.30, 0.20)
        assert result["vrp"] < 0
        assert result["signal"] == "cheap"

    def test_equal_vols(self):
        """Same vol => VRP = 0 => cheap (not positive)."""
        result = compute_variance_risk_premium(0.20, 0.20)
        assert result["vrp"] == 0.0
        assert result["signal"] == "cheap"

    def test_vrp_arithmetic(self):
        """Verify VRP = implied_var - realized_var."""
        result = compute_variance_risk_premium(0.15, 0.25)
        expected_vrp = 0.25**2 - 0.15**2
        assert abs(result["vrp"] - expected_vrp) < 1e-8

    def test_vrp_ratio(self):
        result = compute_variance_risk_premium(0.20, 0.30)
        assert abs(result["vrp_ratio"] - 1.5) < 1e-8

    def test_zero_realized_vol(self):
        """Zero realized vol should give infinite ratio."""
        result = compute_variance_risk_premium(0.0, 0.25)
        assert result["vrp_ratio"] == float("inf")
        assert result["vrp"] > 0
        assert result["signal"] == "rich"

    def test_both_zero(self):
        result = compute_variance_risk_premium(0.0, 0.0)
        assert result["vrp"] == 0.0
        assert result["signal"] == "cheap"


# ---------------------------------------------------------------------------
# compute_variance_risk_premium -- edge cases / errors
# ---------------------------------------------------------------------------


class TestVarianceRiskPremiumEdgeCases:
    def test_negative_realized_vol(self):
        with pytest.raises(ValueError, match="realized_vol must be non-negative"):
            compute_variance_risk_premium(-0.1, 0.2)

    def test_negative_implied_vol(self):
        with pytest.raises(ValueError, match="implied_vol must be non-negative"):
            compute_variance_risk_premium(0.2, -0.1)

    def test_both_negative(self):
        with pytest.raises(ValueError, match="realized_vol must be non-negative"):
            compute_variance_risk_premium(-0.1, -0.2)
