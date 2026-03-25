"""Tests for the correlation_network quant analysis module."""

from __future__ import annotations

import pytest

from agora.analysis.quant.correlation_network import (
    build_network,
    compute_centrality,
    minimum_spanning_tree,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def identity_3x3():
    """Three symbols with an identity correlation matrix (uncorrelated)."""
    symbols = ["A", "B", "C"]
    matrix = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    return symbols, matrix


@pytest.fixture()
def strong_corr_3x3():
    """Three symbols, all strongly correlated."""
    symbols = ["A", "B", "C"]
    matrix = [
        [1.0, 0.9, 0.8],
        [0.9, 1.0, 0.7],
        [0.8, 0.7, 1.0],
    ]
    return symbols, matrix


@pytest.fixture()
def negative_corr_2x2():
    """Two symbols with strong negative correlation."""
    symbols = ["X", "Y"]
    matrix = [
        [1.0, -0.85],
        [-0.85, 1.0],
    ]
    return symbols, matrix


@pytest.fixture()
def mixed_4x4():
    """Four symbols with a mix of strong and weak correlations."""
    symbols = ["A", "B", "C", "D"]
    matrix = [
        [1.0, 0.9, 0.1, 0.2],
        [0.9, 1.0, 0.15, 0.3],
        [0.1, 0.15, 1.0, 0.85],
        [0.2, 0.3, 0.85, 1.0],
    ]
    return symbols, matrix


# ---------------------------------------------------------------------------
# build_network
# ---------------------------------------------------------------------------


class TestBuildNetwork:
    def test_empty_symbols(self):
        result = build_network([], [], threshold=0.5)
        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["threshold"] == 0.5

    def test_single_symbol(self):
        result = build_network(["AAPL"], [[1.0]], threshold=0.5)
        assert result["nodes"] == ["AAPL"]
        assert result["edges"] == []

    def test_identity_no_edges(self, identity_3x3):
        """Uncorrelated symbols should produce no edges at default threshold."""
        symbols, matrix = identity_3x3
        result = build_network(symbols, matrix, threshold=0.5)
        assert len(result["nodes"]) == 3
        assert result["edges"] == []

    def test_strong_correlation_all_edges(self, strong_corr_3x3):
        """All pairwise correlations exceed 0.5 so all edges should appear."""
        symbols, matrix = strong_corr_3x3
        result = build_network(symbols, matrix, threshold=0.5)
        assert len(result["edges"]) == 3
        weights = {(e["source"], e["target"]): e["weight"] for e in result["edges"]}
        assert weights[("A", "B")] == pytest.approx(0.9)
        assert weights[("A", "C")] == pytest.approx(0.8)
        assert weights[("B", "C")] == pytest.approx(0.7)

    def test_negative_correlation_included(self, negative_corr_2x2):
        """Negative correlations with abs value >= threshold should be edges."""
        symbols, matrix = negative_corr_2x2
        result = build_network(symbols, matrix, threshold=0.5)
        assert len(result["edges"]) == 1
        assert result["edges"][0]["weight"] == pytest.approx(-0.85)

    def test_threshold_filters_weak(self, mixed_4x4):
        """Only edges with |corr| >= 0.5 should survive."""
        symbols, matrix = mixed_4x4
        result = build_network(symbols, matrix, threshold=0.5)
        edge_pairs = {(e["source"], e["target"]) for e in result["edges"]}
        assert ("A", "B") in edge_pairs
        assert ("C", "D") in edge_pairs
        assert len(result["edges"]) == 2

    def test_zero_threshold_all_nonzero_edges(self, mixed_4x4):
        """With threshold=0, all pairs with nonzero correlation are edges."""
        symbols, matrix = mixed_4x4
        result = build_network(symbols, matrix, threshold=0.0)
        # 4 symbols -> 6 possible edges; all off-diagonal values are nonzero
        assert len(result["edges"]) == 6

    def test_high_threshold_removes_all(self, strong_corr_3x3):
        """Threshold above all correlations yields no edges."""
        symbols, matrix = strong_corr_3x3
        result = build_network(symbols, matrix, threshold=0.95)
        assert result["edges"] == []


# ---------------------------------------------------------------------------
# minimum_spanning_tree
# ---------------------------------------------------------------------------


class TestMinimumSpanningTree:
    def test_empty_symbols(self):
        result = minimum_spanning_tree([], [])
        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["total_weight"] == 0.0

    def test_single_symbol(self):
        result = minimum_spanning_tree(["AAPL"], [[1.0]])
        assert result["nodes"] == ["AAPL"]
        assert result["edges"] == []
        assert result["total_weight"] == 0.0

    def test_two_symbols(self, negative_corr_2x2):
        symbols, matrix = negative_corr_2x2
        result = minimum_spanning_tree(symbols, matrix)
        assert len(result["edges"]) == 1
        assert result["edges"][0]["weight"] == pytest.approx(1.0 - 0.85)
        assert result["total_weight"] == pytest.approx(0.15)

    def test_three_symbols_edge_count(self, strong_corr_3x3):
        """MST on 3 nodes always has exactly 2 edges."""
        symbols, matrix = strong_corr_3x3
        result = minimum_spanning_tree(symbols, matrix)
        assert len(result["edges"]) == 2

    def test_three_symbols_picks_shortest_distances(self, strong_corr_3x3):
        """The MST should pick the two smallest distances.

        Distances: A-B=0.1, A-C=0.2, B-C=0.3.
        MST should pick A-B (0.1) and A-C (0.2).
        """
        symbols, matrix = strong_corr_3x3
        result = minimum_spanning_tree(symbols, matrix)
        total = result["total_weight"]
        assert total == pytest.approx(0.1 + 0.2)

    def test_four_symbols_mst(self, mixed_4x4):
        """MST on 4 nodes has 3 edges."""
        symbols, matrix = mixed_4x4
        result = minimum_spanning_tree(symbols, matrix)
        assert len(result["edges"]) == 3
        # total weight should be sum of 3 smallest distances spanning all nodes
        assert result["total_weight"] > 0.0

    def test_identity_mst_weights(self, identity_3x3):
        """Uncorrelated symbols: all distances are 1.0."""
        symbols, matrix = identity_3x3
        result = minimum_spanning_tree(symbols, matrix)
        assert len(result["edges"]) == 2
        assert result["total_weight"] == pytest.approx(2.0)

    def test_negative_correlation_distance(self):
        """Distance uses abs(corr), so -0.9 should give distance 0.1."""
        symbols = ["A", "B"]
        matrix = [[1.0, -0.9], [-0.9, 1.0]]
        result = minimum_spanning_tree(symbols, matrix)
        assert result["edges"][0]["weight"] == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# compute_centrality
# ---------------------------------------------------------------------------


class TestComputeCentrality:
    def test_empty_network(self):
        result = compute_centrality({"nodes": [], "edges": []})
        assert result == {}

    def test_single_node(self):
        result = compute_centrality({"nodes": ["A"], "edges": []})
        assert result == {"A": 0.0}

    def test_fully_connected_three(self, strong_corr_3x3):
        """In a fully connected 3-node graph, every node has centrality 1.0."""
        symbols, matrix = strong_corr_3x3
        network = build_network(symbols, matrix, threshold=0.5)
        centrality = compute_centrality(network)
        for node in symbols:
            assert centrality[node] == pytest.approx(1.0)

    def test_star_topology(self):
        """Star graph: center has centrality 1.0, leaves have 1/(n-1)."""
        network = {
            "nodes": ["hub", "leaf1", "leaf2", "leaf3"],
            "edges": [
                {"source": "hub", "target": "leaf1", "weight": 0.1},
                {"source": "hub", "target": "leaf2", "weight": 0.1},
                {"source": "hub", "target": "leaf3", "weight": 0.1},
            ],
        }
        centrality = compute_centrality(network)
        assert centrality["hub"] == pytest.approx(1.0)
        for leaf in ["leaf1", "leaf2", "leaf3"]:
            assert centrality[leaf] == pytest.approx(1.0 / 3.0)

    def test_disconnected_node(self, mixed_4x4):
        """Nodes with no edges should have centrality 0.0."""
        # Build a network where threshold is very high
        symbols, matrix = mixed_4x4
        network = build_network(symbols, matrix, threshold=0.95)
        centrality = compute_centrality(network)
        for node in symbols:
            assert centrality[node] == 0.0

    def test_mst_centrality(self, strong_corr_3x3):
        """Centrality computed on MST should be well-defined."""
        symbols, matrix = strong_corr_3x3
        mst = minimum_spanning_tree(symbols, matrix)
        centrality = compute_centrality(mst)
        assert len(centrality) == 3
        # All centrality values should be in [0, 1]
        for v in centrality.values():
            assert 0.0 <= v <= 1.0

    def test_two_node_line(self):
        """Two connected nodes each have centrality 1.0."""
        network = {
            "nodes": ["A", "B"],
            "edges": [{"source": "A", "target": "B", "weight": 0.5}],
        }
        centrality = compute_centrality(network)
        assert centrality["A"] == pytest.approx(1.0)
        assert centrality["B"] == pytest.approx(1.0)
