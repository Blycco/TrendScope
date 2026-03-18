"""Topic grouping via Louvain community detection with fallback to greedy clustering.

RULE 17: Reuses ClusterItem, Cluster from semantic_clusterer.py.
"""

from __future__ import annotations

import structlog

from backend.processor.shared.semantic_clusterer import (
    Cluster,
    ClusterItem,
    cluster_items,
    compute_jaccard,
)

logger = structlog.get_logger(__name__)


def _build_louvain_clusters(
    items: list[ClusterItem],
    partition: dict[int, int],
) -> list[Cluster]:
    """Map Louvain partition result back to Cluster objects.

    Args:
        items: Original items in index order matching graph node IDs.
        partition: Mapping of node_id -> community_id from community_louvain.

    Returns:
        List of Cluster objects, one per detected community.
    """
    community_map: dict[int, list[ClusterItem]] = {}
    for node_id, community_id in partition.items():
        community_map.setdefault(community_id, []).append(items[node_id])

    clusters: list[Cluster] = []
    for community_id, members in community_map.items():
        representative = members[0]
        rest = members[1:]
        cluster = Cluster(
            cluster_id=str(community_id),
            representative=representative,
            members=rest,
        )
        clusters.append(cluster)

    return clusters


def louvain_cluster(
    items: list[ClusterItem],
    threshold: float = 0.55,
) -> list[Cluster]:
    """Cluster items using Louvain community detection on a keyword similarity graph.

    Builds an undirected graph where edges connect item pairs whose Jaccard
    keyword similarity meets or exceeds `threshold`. Applies Louvain community
    detection to find topic groups.

    Falls back to `cluster_items` from semantic_clusterer when python-louvain
    or networkx is unavailable, or on any unexpected error.

    Args:
        items: Items to cluster.
        threshold: Minimum Jaccard similarity to add an edge. Defaults to 0.55.

    Returns:
        List of Cluster objects.
    """
    if not items:
        return []

    try:
        import community as community_louvain  # type: ignore[import-untyped]
        import networkx as nx  # type: ignore[import-untyped]
    except ImportError as exc:
        logger.warning(
            "louvain_not_available",
            reason=str(exc),
            fallback="cluster_items",
        )
        return cluster_items(items, threshold=threshold)

    try:
        graph: nx.Graph = nx.Graph()

        # Add one node per item (indexed by position)
        for idx in range(len(items)):
            graph.add_node(idx)

        # Add edges where Jaccard similarity >= threshold
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                jaccard = compute_jaccard(items[i].keywords, items[j].keywords)
                if jaccard >= threshold:
                    graph.add_edge(i, j, weight=jaccard)

        partition: dict[int, int] = community_louvain.best_partition(graph)

        clusters = _build_louvain_clusters(items, partition)

        logger.info(
            "louvain_clustering_complete",
            input_count=len(items),
            cluster_count=len(clusters),
        )
        return clusters

    except Exception as exc:
        logger.warning(
            "louvain_clustering_failed",
            error=str(exc),
            fallback="cluster_items",
        )
        return cluster_items(items, threshold=threshold)
