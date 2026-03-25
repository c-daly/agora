"""Tests for agora.analysis.quant.random_matrix_filter."""

from __future__ import annotations

import numpy as np
import pytest

from agora.analysis.quant.random_matrix_filter import (
    filter_correlation_matrix,
    marchenko_pastur_bounds,
)


# ---------------------------------------------------------------------------
# marchenko_pastur_bounds
# ---------------------------------------------------------------------------


class TestMarchenkoPasturBounds:
    """Tests for the marchenko_pastur_bounds function."""

    def test_basic_computation(self):
        """Verify known MP bounds for q = 0.5 (100 assets, 200 obs)."""
        result = marchenko_pastur_bounds(100, 200)
        q = 0.5
        expected_max = (1 + np.sqrt(q)) ** 2
        expected_min = (1 - np.sqrt(q)) ** 2

        assert result["q_ratio"] == pytest.approx(q)
        assert result["lambda_max"] == pytest.approx(expected_max)
        assert result["lambda_min"] == pytest.approx(expected_min)

    def test_q_equals_one(self):
        """When n_assets == n_observations, q = 1."""
        result = marchenko_pastur_bounds(50, 50)
        assert result["q_ratio"] == pytest.approx(1.0)
        assert result["lambda_min"] == pytest.approx(0.0)
        assert result["lambda_max"] == pytest.approx(4.0)

    def test_q_greater_than_one(self):
        """When q > 1, lambda_min is max(0, (1-sqrt(q))^2)."""
        result = marchenko_pastur_bounds(200, 100)
        assert result["q_ratio"] == pytest.approx(2.0)
        expected_min = max(0.0, (1.0 - np.sqrt(2.0)) ** 2)
        assert result["lambda_min"] == pytest.approx(expected_min)
        assert result["lambda_max"] > 4.0

    def test_small_q(self):
        """Very small q (few assets, many observations)."""
        result = marchenko_pastur_bounds(2, 1000)
        assert result["q_ratio"] == pytest.approx(0.002)
        # Bounds should be close to 1
        assert result["lambda_min"] < 1.0
        assert result["lambda_max"] > 1.0

    def test_single_asset_single_obs(self):
        """Edge case: 1 asset, 1 observation."""
        result = marchenko_pastur_bounds(1, 1)
        assert result["q_ratio"] == pytest.approx(1.0)
        assert result["lambda_min"] == pytest.approx(0.0)
        assert result["lambda_max"] == pytest.approx(4.0)

    def test_invalid_n_assets_zero(self):
        with pytest.raises(ValueError, match="n_assets"):
            marchenko_pastur_bounds(0, 100)

    def test_invalid_n_observations_zero(self):
        with pytest.raises(ValueError, match="n_observations"):
            marchenko_pastur_bounds(10, 0)

    def test_invalid_negative(self):
        with pytest.raises(ValueError):
            marchenko_pastur_bounds(-1, 10)


# ---------------------------------------------------------------------------
# filter_correlation_matrix
# ---------------------------------------------------------------------------


class TestFilterCorrelationMatrix:
    """Tests for the filter_correlation_matrix function."""

    def test_identity_matrix_no_signal(self):
        """An identity matrix has all eigenvalues = 1, within MP noise bounds."""
        n = 10
        identity = np.eye(n).tolist()
        result = filter_correlation_matrix(identity, n_observations=1000)
        # With many observations, MP upper bound is close to 1, so
        # eigenvalues of 1.0 should be at or below the bound.
        # n_signal may be 0 or small depending on exact bound.
        assert result["n_signal"] + len(result["noise_eigenvalues"]) == n
        assert len(result["filtered_matrix"]) == n
        assert len(result["filtered_matrix"][0]) == n

    def test_strong_signal_detected(self):
        """A matrix with a dominant factor should produce at least one signal eigenvalue."""
        np.random.seed(42)
        n = 20
        # Create a correlation matrix with one strong factor
        factor = np.random.randn(n, 1)
        cov = factor @ factor.T + np.eye(n) * 0.5
        # Normalize to correlation
        d = np.sqrt(np.diag(cov))
        corr = cov / np.outer(d, d)
        corr_list = corr.tolist()

        result = filter_correlation_matrix(corr_list, n_observations=500)
        assert result["n_signal"] >= 1
        assert len(result["signal_eigenvalues"]) == result["n_signal"]

    def test_filtered_matrix_has_unit_diagonal(self):
        """The filtered matrix should have 1s on the diagonal."""
        np.random.seed(123)
        n = 10
        factor = np.random.randn(n, 2)
        cov = factor @ factor.T + np.eye(n)
        d = np.sqrt(np.diag(cov))
        corr = cov / np.outer(d, d)

        result = filter_correlation_matrix(corr.tolist(), n_observations=200)
        filtered = np.array(result["filtered_matrix"])
        np.testing.assert_allclose(np.diag(filtered), 1.0, atol=1e-10)

    def test_eigenvalue_counts_add_up(self):
        """signal + noise eigenvalue count must equal matrix dimension."""
        n = 5
        mat = np.eye(n).tolist()
        result = filter_correlation_matrix(mat, n_observations=100)
        total = len(result["signal_eigenvalues"]) + len(result["noise_eigenvalues"])
        assert total == n

    def test_1x1_matrix(self):
        """A 1x1 matrix should have exactly one signal eigenvalue."""
        result = filter_correlation_matrix([[1.0]], n_observations=50)
        assert result["n_signal"] == 1
        assert result["signal_eigenvalues"] == pytest.approx([1.0])
        assert result["noise_eigenvalues"] == []
        np.testing.assert_allclose(result["filtered_matrix"], [[1.0]])

    def test_2x2_perfect_correlation(self):
        """A 2x2 matrix of all ones has eigenvalues [2, 0]."""
        mat = [[1.0, 1.0], [1.0, 1.0]]
        result = filter_correlation_matrix(mat, n_observations=100)
        # The large eigenvalue (2.0) should be signal
        assert result["n_signal"] >= 1
        assert max(result["signal_eigenvalues"]) == pytest.approx(2.0)

    def test_empty_matrix(self):
        """An empty list is not a valid square matrix and should raise."""
        with pytest.raises(ValueError, match="square"):
            filter_correlation_matrix([], n_observations=100)

    def test_non_square_raises(self):
        with pytest.raises(ValueError, match="square"):
            filter_correlation_matrix([[1.0, 2.0]], n_observations=100)

    def test_invalid_n_observations(self):
        with pytest.raises(ValueError, match="n_observations"):
            filter_correlation_matrix([[1.0]], n_observations=0)

    def test_q_greater_than_one_scenario(self):
        """More assets than observations: q > 1."""
        np.random.seed(7)
        n_assets = 20
        n_obs = 10
        # Random data to create a sample correlation
        data = np.random.randn(n_obs, n_assets)
        corr = np.corrcoef(data, rowvar=False)
        result = filter_correlation_matrix(corr.tolist(), n_observations=n_obs)
        total = len(result["signal_eigenvalues"]) + len(result["noise_eigenvalues"])
        assert total == n_assets
        assert result["n_signal"] >= 0
        filtered = np.array(result["filtered_matrix"])
        assert filtered.shape == (n_assets, n_assets)

    def test_filtered_matrix_is_symmetric(self):
        """The filtered matrix should be symmetric."""
        np.random.seed(99)
        n = 8
        factor = np.random.randn(n, 2)
        cov = factor @ factor.T + np.eye(n)
        d = np.sqrt(np.diag(cov))
        corr = cov / np.outer(d, d)

        result = filter_correlation_matrix(corr.tolist(), n_observations=200)
        filtered = np.array(result["filtered_matrix"])
        np.testing.assert_allclose(filtered, filtered.T, atol=1e-10)

    def test_signal_eigenvalues_sorted_descending(self):
        """Signal eigenvalues should be in descending order."""
        np.random.seed(42)
        n = 15
        factor = np.random.randn(n, 3)
        cov = factor @ factor.T + np.eye(n) * 0.3
        d = np.sqrt(np.diag(cov))
        corr = cov / np.outer(d, d)

        result = filter_correlation_matrix(corr.tolist(), n_observations=500)
        sig = result["signal_eigenvalues"]
        if len(sig) > 1:
            for i in range(len(sig) - 1):
                assert sig[i] >= sig[i + 1]
