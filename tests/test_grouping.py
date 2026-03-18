"""Tests for backend/processor/algorithms/grouping.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.processor.algorithms.grouping import _build_louvain_clusters, louvain_cluster
from backend.processor.shared.semantic_clusterer import Cluster, ClusterItem


def _item(item_id: str, keywords: set[str]) -> ClusterItem:
    return ClusterItem(item_id=item_id, text=item_id, keywords=keywords)


def _mock_nx_and_community(partition: dict[int, int]) -> tuple[MagicMock, MagicMock]:
    mock_nx = MagicMock()
    mock_nx.Graph.return_value = MagicMock()
    mock_community = MagicMock()
    mock_community.best_partition.return_value = partition
    return mock_nx, mock_community


class TestLouvainCluster:
    def test_empty_items_returns_empty_list(self) -> None:
        result = louvain_cluster([])
        assert result == []

    def test_networkx_importerror_falls_back(self) -> None:
        items = [_item("a", {"ai"}), _item("b", {"tech"})]
        with patch.dict("sys.modules", {"networkx": None, "community": None}):
            result = louvain_cluster(items)
        assert isinstance(result, list)

    def test_community_importerror_falls_back(self) -> None:
        items = [_item("a", {"ai"}), _item("b", {"tech"})]
        # networkx present but community absent
        mock_nx = MagicMock()
        mock_nx.Graph.return_value = MagicMock()
        with patch.dict("sys.modules", {"networkx": mock_nx, "community": None}):
            result = louvain_cluster(items)
        assert isinstance(result, list)

    def test_runtime_exception_falls_back(self) -> None:
        items = [_item("a", {"ai"}), _item("b", {"tech"})]
        mock_nx = MagicMock()
        mock_nx.Graph.return_value = MagicMock()
        mock_community = MagicMock()
        mock_community.best_partition.side_effect = RuntimeError("clustering failed")
        with patch.dict("sys.modules", {"networkx": mock_nx, "community": mock_community}):
            result = louvain_cluster(items)
        assert isinstance(result, list)

    def test_high_similarity_items_grouped(self) -> None:
        items = [
            _item("a", {"ai", "tech", "ml"}),
            _item("b", {"ai", "tech", "ml"}),
        ]
        # Both in same community (0)
        mock_nx, mock_community = _mock_nx_and_community({0: 0, 1: 0})
        with patch.dict("sys.modules", {"networkx": mock_nx, "community": mock_community}):
            result = louvain_cluster(items)
        assert len(result) == 1
        assert isinstance(result[0], Cluster)

    def test_low_similarity_items_separate(self) -> None:
        items = [_item("a", {"ai"}), _item("b", {"fashion"})]
        # Different communities (0, 1)
        mock_nx, mock_community = _mock_nx_and_community({0: 0, 1: 1})
        with patch.dict("sys.modules", {"networkx": mock_nx, "community": mock_community}):
            result = louvain_cluster(items)
        assert len(result) == 2

    def test_default_threshold_0_55(self) -> None:
        items = [_item("a", {"ai"})]
        mock_nx, mock_community = _mock_nx_and_community({0: 0})
        with patch.dict("sys.modules", {"networkx": mock_nx, "community": mock_community}):
            result = louvain_cluster(items)  # uses default threshold=0.55
        assert isinstance(result, list)

    def test_custom_threshold_respected(self) -> None:
        items = [_item("a", {"ai", "ml"}), _item("b", {"ai", "tech"})]
        mock_nx, mock_community = _mock_nx_and_community({0: 0, 1: 0})
        with patch.dict("sys.modules", {"networkx": mock_nx, "community": mock_community}):
            result = louvain_cluster(items, threshold=0.1)
        assert isinstance(result, list)

    def test_returns_cluster_objects(self) -> None:
        items = [_item("x", {"python", "ml"})]
        mock_nx, mock_community = _mock_nx_and_community({0: 0})
        with patch.dict("sys.modules", {"networkx": mock_nx, "community": mock_community}):
            result = louvain_cluster(items)
        for cluster in result:
            assert isinstance(cluster, Cluster)

    def test_single_item_one_cluster(self) -> None:
        items = [_item("a", {"ai", "tech"})]
        mock_nx, mock_community = _mock_nx_and_community({0: 0})
        with patch.dict("sys.modules", {"networkx": mock_nx, "community": mock_community}):
            result = louvain_cluster(items)
        assert len(result) == 1


class TestBuildLouvainClusters:
    def test_representative_is_first_item(self) -> None:
        items = [_item("a", {"x"}), _item("b", {"y"})]
        partition = {0: 0, 1: 0}
        result = _build_louvain_clusters(items, partition)
        assert len(result) == 1
        assert result[0].representative.item_id == "a"

    def test_cluster_items_all_included(self) -> None:
        items = [_item("a", {"x"}), _item("b", {"y"}), _item("c", {"z"})]
        # All in same community
        partition = {0: 0, 1: 0, 2: 0}
        result = _build_louvain_clusters(items, partition)
        assert len(result) == 1
        # representative + members = 3 items total
        total = 1 + len(result[0].members)
        assert total == 3

    def test_two_communities_two_clusters(self) -> None:
        items = [_item("a", {"x"}), _item("b", {"y"})]
        partition = {0: 0, 1: 1}
        result = _build_louvain_clusters(items, partition)
        assert len(result) == 2

    def test_empty_partition_returns_empty(self) -> None:
        result = _build_louvain_clusters([], {})
        assert result == []
