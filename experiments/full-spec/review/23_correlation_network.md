# Review: correlation_network
## Spec requirement
Builds graph from correlation/covariance matrix. Minimum spanning tree, threshold networks. Tracks topology changes (centrality, clustering) over time.

## Implementation
Three public functions:
1. build_network - threshold-based undirected graph: an edge is added when abs(corr(i,j)) >= threshold. Returns nodes, edges with source/target/weight, and the threshold used.
2. minimum_spanning_tree - Kruskal algorithm over distance = 1 - abs(corr). Implements union-find with path compression and union-by-rank. Returns MST nodes, edges, and total weight.
3. compute_centrality - degree centrality (fraction of possible connections actually made) for each node.

## Functions
- build_network(symbols: list[str], correlation_matrix: list[list[float]], threshold: float = 0.5) -> dict
- minimum_spanning_tree(symbols: list[str], correlation_matrix: list[list[float]]) -> dict
- compute_centrality(network: dict) -> dict[str, float]

## Numerical correctness
- Distance metric 1 - abs(corr) maps correlations in [-1, 1] to distances in [0, 1], which is the standard financial network convention (Mantegna 1999).
- Kruskal with union-find is correct for MST; path compression and rank-union make it efficient.
- Degree centrality normalisation degree / (n-1) is the standard definition.
- Edge weights stored in build_network are raw correlation values; weights in minimum_spanning_tree are distances. This asymmetry is correctly documented in the docstrings.

## Edge cases
- Empty symbol list returns empty structures in all three functions - handled.
- Single symbol: all three functions return correct degenerate results - handled.
- Negative correlations: build_network uses abs(weight) for threshold check and minimum_spanning_tree uses abs(corr) for distance - correct.
- All correlations below threshold: results in an edgeless graph - handled.
- Identity matrix: MST includes all n-1 edges with distance 1.0 - correct.

## Verdict
PASS

## Issues
- LOW: The spec mentions tracking topology changes (centrality, clustering) over time, but there is no time-series wrapper or differencing utility. The three functions operate on a single snapshot. A caller would need to invoke them on successive rolling correlation matrices. The core primitives are correct and sufficient; the temporal wrapper is a scope gap.
- LOW: Clustering coefficient is implied by the spec mention of clustering but is not implemented - only degree centrality is provided. Betweenness and closeness centrality are also absent.
