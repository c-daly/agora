"""Correlation network analysis module.

Builds graph representations from correlation matrices, computes minimum
spanning trees, and calculates centrality metrics.  Operates on pre-computed
correlation data.  Does not fetch any data itself.
"""

from __future__ import annotations

import numpy as np


def build_network(
    symbols: list[str],
    correlation_matrix: list[list[float]],
    threshold: float = 0.5,
) -> dict:
    """Build an undirected graph from a correlation matrix.

    An edge is added between two symbols when the absolute value of their
    pairwise correlation meets or exceeds *threshold*.

    Parameters
    ----------
    symbols:
        Ordered list of symbol labels.  Length must match the dimensions of
        *correlation_matrix*.
    correlation_matrix:
        Square symmetric matrix of pairwise correlations (row-major).
    threshold:
        Minimum absolute correlation required to create an edge.

    Returns
    -------
    dict with keys:
        - nodes: list[str] -- symbol labels
        - edges: list[dict] -- each dict has keys *source*, *target*, *weight*
        - threshold: float -- the threshold used
    """
    n = len(symbols)
    if n == 0:
        return {"nodes": [], "edges": [], "threshold": threshold}

    corr = np.array(correlation_matrix, dtype=np.float64)

    edges: list[dict] = []
    for i in range(n):
        for j in range(i + 1, n):
            weight = float(corr[i, j])
            if abs(weight) >= threshold:
                edges.append(
                    {"source": symbols[i], "target": symbols[j], "weight": weight}
                )

    return {"nodes": list(symbols), "edges": edges, "threshold": threshold}


def minimum_spanning_tree(
    symbols: list[str],
    correlation_matrix: list[list[float]],
) -> dict:
    """Compute the minimum spanning tree using distance = 1 - abs(correlation).

    Uses Kruskals algorithm.  For disconnected graphs the result is a minimum
    spanning *forest* (one tree per connected component).

    Parameters
    ----------
    symbols:
        Ordered list of symbol labels.
    correlation_matrix:
        Square symmetric matrix of pairwise correlations (row-major).

    Returns
    -------
    dict with keys:
        - nodes: list[str] -- symbol labels
        - edges: list[dict] -- MST edges with keys *source*, *target*, *weight*
          where *weight* is the distance (1 - abs(corr))
        - total_weight: float -- sum of edge weights in the MST
    """
    n = len(symbols)
    if n == 0:
        return {"nodes": [], "edges": [], "total_weight": 0.0}
    if n == 1:
        return {"nodes": list(symbols), "edges": [], "total_weight": 0.0}

    corr = np.array(correlation_matrix, dtype=np.float64)

    # Build all candidate edges with distance = 1 - |corr|
    candidate_edges: list[tuple[float, int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            dist = 1.0 - abs(float(corr[i, j]))
            candidate_edges.append((dist, i, j))

    # Sort by distance ascending
    candidate_edges.sort()

    # Union-Find for Kruskals algorithm
    parent = list(range(n))
    rank = [0] * n

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> bool:
        rx, ry = find(x), find(y)
        if rx == ry:
            return False
        if rank[rx] < rank[ry]:
            rx, ry = ry, rx
        parent[ry] = rx
        if rank[rx] == rank[ry]:
            rank[rx] += 1
        return True

    mst_edges: list[dict] = []
    total_weight = 0.0
    for dist, i, j in candidate_edges:
        if union(i, j):
            mst_edges.append(
                {"source": symbols[i], "target": symbols[j], "weight": dist}
            )
            total_weight += dist
            if len(mst_edges) == n - 1:
                break

    return {
        "nodes": list(symbols),
        "edges": mst_edges,
        "total_weight": total_weight,
    }


def compute_centrality(network: dict) -> dict[str, float]:
    """Compute degree centrality for each node in the network.

    Degree centrality is the fraction of other nodes a given node is connected
    to: degree(v) / (n - 1) for graphs with n >= 2 nodes.

    Parameters
    ----------
    network:
        A network dict as returned by build_network or
        minimum_spanning_tree.  Must contain *nodes* and *edges* keys.

    Returns
    -------
    dict mapping each symbol to its degree centrality (float in [0, 1]).
    """
    nodes: list[str] = network.get("nodes", [])
    edges: list[dict] = network.get("edges", [])

    n = len(nodes)
    if n == 0:
        return {}
    if n == 1:
        return {nodes[0]: 0.0}

    degree: dict[str, int] = {node: 0 for node in nodes}
    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        if src in degree:
            degree[src] += 1
        if tgt in degree:
            degree[tgt] += 1

    return {node: degree[node] / (n - 1) for node in nodes}
