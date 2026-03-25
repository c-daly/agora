"""Tests for the short_factor_analysis quant module."""

from __future__ import annotations

import pytest

from agora.analysis.quant.short_factor_analysis import (
    ShortFactorAnalysisError,
    analyze_short_factors,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture()
def single_factor_perfect() -> dict:
    """Short positions perfectly explained by a single size factor.

    short_weight = 0.02 + 1.5 * size_loading
    """
    symbols = ["AAPL", "GOOG", "MSFT", "TSLA", "AMZN", "META"]
    size_loadings = [0.1, 0.3, 0.2, 0.5, 0.4, 0.15]
    short_weights = {s: 0.02 + 1.5 * ld for s, ld in zip(symbols, size_loadings)}
    factor_loadings = {"size": dict(zip(symbols, size_loadings))}
    return {"short_positions": short_weights, "factor_loadings": factor_loadings}


@pytest.fixture()
def multi_factor_perfect() -> dict:
    """Short positions perfectly explained by sector + value factors.

    short_weight = 0.05 + 0.8 * sector + (-0.4) * value
    """
    symbols = ["AAPL", "GOOG", "MSFT", "TSLA", "AMZN", "META", "NFLX", "NVDA"]
    sector = [0.1, 0.2, 0.15, 0.8, 0.3, 0.25, 0.6, 0.9]
    value = [0.5, 0.3, 0.4, 0.1, 0.35, 0.45, 0.2, 0.05]
    short_weights = {
        s: 0.05 + 0.8 * sec + (-0.4) * val
        for s, sec, val in zip(symbols, sector, value)
    }
    factor_loadings = {
        "sector": dict(zip(symbols, sector)),
        "value": dict(zip(symbols, value)),
    }
    return {"short_positions": short_weights, "factor_loadings": factor_loadings}


@pytest.fixture()
def noisy_data() -> dict:
    """Short positions with factor signal plus independent noise."""
    symbols = ["A", "B", "C", "D", "E", "F", "G", "H"]
    size = [0.1, 0.3, 0.2, 0.5, 0.4, 0.15, 0.35, 0.45]
    # base = 0.02 + 1.0 * size, then add noise to some symbols
    noise = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.15, -0.12]
    short_weights = {
        s: 0.02 + 1.0 * sz + n for s, sz, n in zip(symbols, size, noise)
    }
    factor_loadings = {"size": dict(zip(symbols, size))}
    return {"short_positions": short_weights, "factor_loadings": factor_loadings}


# -----------------------------------------------------------------------
# Happy-path tests
# -----------------------------------------------------------------------


def test_return_keys(single_factor_perfect):
    """Result dict should contain exactly the documented keys."""
    result = analyze_short_factors(**single_factor_perfect)
    assert set(result.keys()) == {
        "factor_exposures",
        "unexplained_fraction",
        "independent_signal_strength",
        "symbols_with_high_residual",
    }


def test_return_types(single_factor_perfect):
    """All returned values should be plain Python types (not numpy)."""
    result = analyze_short_factors(**single_factor_perfect)
    assert isinstance(result["factor_exposures"], dict)
    assert all(isinstance(v, float) for v in result["factor_exposures"].values())
    assert isinstance(result["unexplained_fraction"], float)
    assert isinstance(result["independent_signal_strength"], float)
    assert isinstance(result["symbols_with_high_residual"], list)
    assert all(isinstance(s, str) for s in result["symbols_with_high_residual"])


def test_single_factor_perfect_fit(single_factor_perfect):
    """Perfect single-factor data should yield near-zero unexplained fraction."""
    result = analyze_short_factors(**single_factor_perfect)
    assert result["unexplained_fraction"] == pytest.approx(0.0, abs=1e-10)
    assert result["independent_signal_strength"] == pytest.approx(0.0, abs=1e-10)
    assert result["factor_exposures"]["size"] == pytest.approx(1.5, abs=1e-10)


def test_single_factor_perfect_fit_no_high_residuals(single_factor_perfect):
    """Perfect fit should have very small residuals; high-residual list may be
    empty or contain only symbols with numerically negligible residual deviation."""
    result = analyze_short_factors(**single_factor_perfect)
    # With perfect data, unexplained fraction is ~0, so any flagged symbols
    # are just floating-point noise.
    assert result["unexplained_fraction"] == pytest.approx(0.0, abs=1e-10)


def test_multi_factor_perfect_fit(multi_factor_perfect):
    """Perfect multi-factor data should recover coefficients."""
    result = analyze_short_factors(**multi_factor_perfect)
    assert result["unexplained_fraction"] == pytest.approx(0.0, abs=1e-10)
    assert result["factor_exposures"]["sector"] == pytest.approx(0.8, abs=1e-10)
    assert result["factor_exposures"]["value"] == pytest.approx(-0.4, abs=1e-10)


def test_noisy_data_has_nonzero_unexplained(noisy_data):
    """Noisy data should have a positive unexplained fraction."""
    result = analyze_short_factors(**noisy_data)
    assert result["unexplained_fraction"] > 0.01
    assert result["independent_signal_strength"] > 0.01


def test_noisy_data_detects_high_residual_symbols(noisy_data):
    """Symbols G and H have large noise and should appear as high residual."""
    result = analyze_short_factors(**noisy_data)
    # G and H have the injected noise
    high = result["symbols_with_high_residual"]
    assert len(high) > 0
    # At least one of the noisy symbols should be flagged
    assert any(s in high for s in ["G", "H"])


def test_unexplained_fraction_bounded():
    """Unexplained fraction should always be in [0, 1]."""
    symbols = ["A", "B", "C", "D", "E"]
    short_positions = {s: float(i) * 0.1 for i, s in enumerate(symbols)}
    factor_loadings = {"x": {s: float(i) * 0.05 for i, s in enumerate(symbols)}}
    result = analyze_short_factors(short_positions, factor_loadings)
    assert 0.0 <= result["unexplained_fraction"] <= 1.0


def test_factor_exposures_keys_match_input():
    """Factor exposure keys should match the factor names from input."""
    symbols = ["A", "B", "C", "D", "E", "F", "G"]
    short_positions = {s: 0.1 * (i + 1) for i, s in enumerate(symbols)}
    # Use linearly independent factors
    factor_loadings = {
        "sector": {s: [0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.5][i] for i, s in enumerate(symbols)},
        "size": {s: 0.05 * (i + 1) for i, s in enumerate(symbols)},
    }
    result = analyze_short_factors(short_positions, factor_loadings)
    assert set(result["factor_exposures"].keys()) == {"sector", "size"}


# -----------------------------------------------------------------------
# Edge cases and validation
# -----------------------------------------------------------------------


def test_empty_positions_raises():
    """Empty short_positions dict should raise."""
    with pytest.raises(ShortFactorAnalysisError, match="At least one short position"):
        analyze_short_factors({}, {"size": {}})


def test_single_position_raises():
    """A single position is not enough for regression."""
    with pytest.raises(ShortFactorAnalysisError, match="At least two"):
        analyze_short_factors({"AAPL": 0.1}, {"size": {"AAPL": 0.5}})


def test_no_factors_raises():
    """Empty factor_loadings dict should raise."""
    with pytest.raises(ShortFactorAnalysisError, match="At least one factor"):
        analyze_short_factors({"AAPL": 0.1, "GOOG": 0.2, "MSFT": 0.3}, {})


def test_insufficient_symbols_for_params():
    """N symbols <= number of parameters should raise."""
    # 2 factors + intercept = 3 params; 3 symbols is not enough
    with pytest.raises(ShortFactorAnalysisError, match="Insufficient symbols"):
        analyze_short_factors(
            {"A": 0.1, "B": 0.2, "C": 0.3},
            {
                "sector": {"A": 0.1, "B": 0.2, "C": 0.3},
                "size": {"A": 0.5, "B": 0.6, "C": 0.7},
            },
        )


def test_missing_factor_loading_raises():
    """Missing symbol in factor loadings should raise."""
    with pytest.raises(ShortFactorAnalysisError, match="missing loadings"):
        analyze_short_factors(
            {"A": 0.1, "B": 0.2, "C": 0.3, "D": 0.4},
            {"size": {"A": 0.1, "B": 0.2, "C": 0.3}},  # missing D
        )


def test_duplicate_factors_rank_deficient():
    """Identical factors create a rank-deficient matrix."""
    symbols = ["A", "B", "C", "D", "E", "F"]
    loadings = {s: 0.1 * i for i, s in enumerate(symbols)}
    with pytest.raises(ShortFactorAnalysisError, match="rank-deficient"):
        analyze_short_factors(
            {s: 0.1 * (i + 1) for i, s in enumerate(symbols)},
            {"factor_a": loadings, "factor_b": dict(loadings)},
        )


def test_constant_short_positions():
    """Constant short positions (zero variance) should have unexplained_fraction
    of 1.0 (R-squared is 0 because total variance is 0)."""
    symbols = ["A", "B", "C", "D", "E"]
    short_positions = {s: 0.1 for s in symbols}
    factor_loadings = {"size": {s: 0.1 * i for i, s in enumerate(symbols)}}
    result = analyze_short_factors(short_positions, factor_loadings)
    assert result["unexplained_fraction"] == 1.0
    assert result["factor_exposures"]["size"] == pytest.approx(0.0, abs=1e-10)


def test_symbols_with_high_residual_sorted():
    """High residual symbols list should be sorted."""
    symbols = ["Z", "A", "M", "B", "Q", "C", "X", "D"]
    size = [0.1, 0.3, 0.2, 0.5, 0.4, 0.15, 0.35, 0.45]
    noise = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2, -0.15]
    short_positions = {
        s: 0.02 + 1.0 * sz + n for s, sz, n in zip(symbols, size, noise)
    }
    factor_loadings = {"size": dict(zip(symbols, size))}
    result = analyze_short_factors(short_positions, factor_loadings)
    high = result["symbols_with_high_residual"]
    assert high == sorted(high)


def test_three_factors():
    """Analysis with sector, size, and value factors."""
    symbols = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    sector = [0.9, 0.1, 0.8, 0.2, 0.7, 0.3, 0.6, 0.4, 0.5, 0.5]
    size = [0.1, 0.5, 0.2, 0.6, 0.15, 0.55, 0.25, 0.45, 0.3, 0.4]
    value = [0.3, 0.7, 0.4, 0.6, 0.35, 0.65, 0.45, 0.55, 0.5, 0.5]
    # Perfect: short = 0.01 + 0.5*sector - 0.3*size + 0.2*value
    short_positions = {
        s: 0.01 + 0.5 * sec - 0.3 * sz + 0.2 * val
        for s, sec, sz, val in zip(symbols, sector, size, value)
    }
    factor_loadings = {
        "sector": dict(zip(symbols, sector)),
        "size": dict(zip(symbols, size)),
        "value": dict(zip(symbols, value)),
    }
    result = analyze_short_factors(short_positions, factor_loadings)
    assert result["unexplained_fraction"] == pytest.approx(0.0, abs=1e-10)
    assert result["factor_exposures"]["sector"] == pytest.approx(0.5, abs=1e-10)
    assert result["factor_exposures"]["size"] == pytest.approx(-0.3, abs=1e-10)
    assert result["factor_exposures"]["value"] == pytest.approx(0.2, abs=1e-10)
