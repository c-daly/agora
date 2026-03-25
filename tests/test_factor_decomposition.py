"""Tests for the factor_decomposition quant module."""

from __future__ import annotations

import pytest

from agora.analysis.quant.factor_decomposition import (
    FactorDecompositionError,
    decompose_returns,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture()
def single_factor_data() -> dict:
    """Asset that is exactly 2.x market + 0.01 alpha (no noise)."""
    market = [0.01, -0.02, 0.03, 0.00, -0.01, 0.02, 0.04, -0.03, 0.01, 0.02]
    # asset = 0.01 + 2.0 * market
    asset = [0.01 + 2.0 * m for m in market]
    return {
        "asset_returns": asset,
        "factor_returns": {"market": market},
    }


@pytest.fixture()
def multi_factor_data() -> dict:
    """Fama-French 3-factor style data (exact, no noise).

    asset = 0.005 + 1.2*market + 0.5*smb - 0.3*hml
    """
    market = [0.01, -0.02, 0.03, 0.00, -0.01, 0.02, 0.04, -0.03, 0.01, 0.02]
    smb = [0.005, 0.010, -0.005, 0.003, -0.007, 0.002, 0.008, -0.004, 0.001, 0.006]
    hml = [-0.003, 0.007, 0.002, -0.001, 0.004, -0.006, 0.003, 0.005, -0.002, 0.001]
    asset = [
        0.005 + 1.2 * m + 0.5 * s - 0.3 * h
        for m, s, h in zip(market, smb, hml)
    ]
    return {
        "asset_returns": asset,
        "factor_returns": {"market": market, "smb": smb, "hml": hml},
    }


# -----------------------------------------------------------------------
# Happy-path tests
# -----------------------------------------------------------------------


def test_single_factor_recovers_alpha_and_beta(single_factor_data):
    """With no-noise data, alpha and beta should match exactly."""
    result = decompose_returns(**single_factor_data)

    assert result["alpha"] == pytest.approx(0.01, abs=1e-10)
    assert result["betas"]["market"] == pytest.approx(2.0, abs=1e-10)


def test_single_factor_perfect_r_squared(single_factor_data):
    """No-noise data should yield R-squared ~ 1.0."""
    result = decompose_returns(**single_factor_data)
    assert result["r_squared"] == pytest.approx(1.0, abs=1e-10)


def test_single_factor_residuals_near_zero(single_factor_data):
    """Residuals should be essentially zero for perfect fit."""
    result = decompose_returns(**single_factor_data)
    for r in result["residuals"]:
        assert r == pytest.approx(0.0, abs=1e-10)


def test_single_factor_residuals_length(single_factor_data):
    """Residuals list should have same length as input."""
    result = decompose_returns(**single_factor_data)
    assert len(result["residuals"]) == len(single_factor_data["asset_returns"])


def test_multi_factor_recovers_all_params(multi_factor_data):
    """3-factor decomposition should recover alpha and all betas."""
    result = decompose_returns(**multi_factor_data)

    assert result["alpha"] == pytest.approx(0.005, abs=1e-10)
    assert result["betas"]["market"] == pytest.approx(1.2, abs=1e-10)
    assert result["betas"]["smb"] == pytest.approx(0.5, abs=1e-10)
    assert result["betas"]["hml"] == pytest.approx(-0.3, abs=1e-10)


def test_multi_factor_perfect_fit(multi_factor_data):
    """No-noise 3-factor data should yield R-squared ~ 1.0."""
    result = decompose_returns(**multi_factor_data)
    assert result["r_squared"] == pytest.approx(1.0, abs=1e-10)


def test_return_keys(single_factor_data):
    """Result dict should contain exactly the documented keys."""
    result = decompose_returns(**single_factor_data)
    assert set(result.keys()) == {"alpha", "betas", "r_squared", "residuals"}


def test_return_types(single_factor_data):
    """All returned values should be plain Python types (not numpy)."""
    result = decompose_returns(**single_factor_data)
    assert isinstance(result["alpha"], float)
    assert isinstance(result["r_squared"], float)
    assert isinstance(result["residuals"], list)
    assert all(isinstance(r, float) for r in result["residuals"])
    assert isinstance(result["betas"], dict)
    assert all(isinstance(v, float) for v in result["betas"].values())


# -----------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------


def test_no_factors_raises():
    """Empty factor dict should raise."""
    with pytest.raises(FactorDecompositionError, match="At least one factor"):
        decompose_returns([0.01, 0.02, 0.03], {})


def test_insufficient_data_too_few_obs():
    """Fewer than _MIN_OBSERVATIONS should raise."""
    with pytest.raises(FactorDecompositionError, match="Insufficient data"):
        decompose_returns([0.01, 0.02], {"mkt": [0.01, 0.02]})


def test_insufficient_data_for_params():
    """N obs <= number of parameters should raise."""
    # 3 factors + intercept = 4 params; 3 obs is not enough
    with pytest.raises(FactorDecompositionError, match="Insufficient data"):
        decompose_returns(
            [0.01, 0.02, 0.03],
            {"a": [0.01, 0.02, 0.03], "b": [0.01, 0.02, 0.03], "c": [0.01, 0.02, 0.03]},
        )


def test_mismatched_lengths_raises():
    """Factor series with different length than asset returns should raise."""
    with pytest.raises(FactorDecompositionError, match="observations"):
        decompose_returns(
            [0.01, 0.02, 0.03, 0.04],
            {"mkt": [0.01, 0.02, 0.03]},  # one too few
        )


def test_singular_matrix_duplicate_factors():
    """Identical factors create a rank-deficient matrix."""
    mkt = [0.01, -0.02, 0.03, 0.00, -0.01, 0.02, 0.04, -0.03, 0.01, 0.02]
    asset = [0.01 + m for m in mkt]
    with pytest.raises(FactorDecompositionError, match="rank-deficient"):
        decompose_returns(asset, {"a": mkt, "b": mkt})


def test_constant_asset_returns():
    """Constant asset returns (ss total = 0) should return r_squared = 0."""
    asset = [0.05] * 10
    market = [0.01, -0.02, 0.03, 0.00, -0.01, 0.02, 0.04, -0.03, 0.01, 0.02]
    result = decompose_returns(asset, {"market": market})
    assert result["r_squared"] == 0.0
    assert result["betas"]["market"] == pytest.approx(0.0, abs=1e-10)
    assert result["alpha"] == pytest.approx(0.05, abs=1e-10)


def test_minimal_valid_data():
    """3 obs with 1 factor (2 params) is the minimum valid case."""
    asset = [0.03, 0.01, 0.05]
    market = [0.01, 0.00, 0.02]
    result = decompose_returns(asset, {"market": market})
    assert "alpha" in result
    assert "market" in result["betas"]
    assert len(result["residuals"]) == 3
