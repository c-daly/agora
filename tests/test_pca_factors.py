"""Tests for agora.analysis.quant.pca_factors."""
import math
import pytest
from agora.analysis.quant.pca_factors import extract_factors, variance_concentration


class TestExtractFactors:
    def test_basic_two_assets(self):
        returns = {"A": [0.01, 0.02, -0.01, 0.03, 0.00], "B": [0.02, 0.01, -0.02, 0.04, 0.01]}
        result = extract_factors(returns)
        assert result["n_components"] == 2
        assert result["eigenvalues"][0] >= result["eigenvalues"][1]
        assert math.isclose(sum(result["explained_variance_ratio"]), 1.0, abs_tol=1e-10)
        assert set(result["loadings"].keys()) == {"A", "B"}

    def test_single_asset(self):
        result = extract_factors({"X": [0.01, 0.02, 0.03]})
        assert result["n_components"] == 1
        assert math.isclose(result["explained_variance_ratio"][0], 1.0, abs_tol=1e-10)

    def test_n_components_limits(self):
        returns = {"A": [0.01, 0.02, -0.01], "B": [0.02, 0.01, -0.02], "C": [0.00, 0.03, 0.01]}
        result = extract_factors(returns, n_components=2)
        assert result["n_components"] == 2
        assert len(result["eigenvalues"]) == 2

    def test_n_components_exceeds_assets(self):
        result = extract_factors({"A": [0.01, 0.02], "B": [0.03, 0.04]}, n_components=10)
        assert result["n_components"] == 2

    def test_empty_returns_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            extract_factors({})

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="same length"):
            extract_factors({"A": [0.01, 0.02], "B": [0.01]})

    def test_n_components_zero_raises(self):
        with pytest.raises(ValueError, match="n_components must be >= 1"):
            extract_factors({"A": [0.01, 0.02]}, n_components=0)

    def test_constant_returns(self):
        result = extract_factors({"A": [0.0, 0.0, 0.0], "B": [0.0, 0.0, 0.0]})
        for ev in result["eigenvalues"]:
            assert math.isclose(ev, 0.0, abs_tol=1e-15)


class TestVarianceConcentration:
    def test_basic(self):
        result = variance_concentration([5.0, 3.0, 1.0, 0.5, 0.5])
        assert math.isclose(result["top_1"], 0.5)
        assert math.isclose(result["top_3"], 0.9)
        assert math.isclose(result["top_5"], 1.0)

    def test_fewer_than_five(self):
        result = variance_concentration([3.0, 1.0])
        assert math.isclose(result["top_1"], 0.75)
        assert math.isclose(result["top_5"], 1.0)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            variance_concentration([])

    def test_integration(self):
        factors = extract_factors({"A": [0.01, 0.02, -0.01, 0.03], "B": [0.02, 0.01, -0.02, 0.04], "C": [0.00, 0.03, 0.01, -0.01]})
        conc = variance_concentration(factors["eigenvalues"])
        assert 0.0 <= conc["top_1"] <= 1.0
        assert conc["top_1"] <= conc["top_3"] <= conc["top_5"]
