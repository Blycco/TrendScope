"""Tests for semantic_clusterer module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.processor.shared.semantic_clusterer import (
    Cluster,
    ClusterItem,
    cluster_items,
    compute_cosine_similarity,
    compute_jaccard,
    compute_similarity,
    compute_source_similarity,
    compute_temporal_similarity,
)


class TestJaccard:
    """Tests for Jaccard similarity."""

    def test_identical_sets(self) -> None:
        assert compute_jaccard({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint_sets(self) -> None:
        assert compute_jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self) -> None:
        sim = compute_jaccard({"a", "b", "c"}, {"b", "c", "d"})
        assert sim == 2.0 / 4.0  # 2 intersection, 4 union

    def test_empty_sets(self) -> None:
        assert compute_jaccard(set(), set()) == 0.0

    def test_one_empty(self) -> None:
        assert compute_jaccard({"a"}, set()) == 0.0


class TestCosineSimilarity:
    """Tests for cosine similarity."""

    def test_identical_vectors(self) -> None:
        vec = [1.0, 2.0, 3.0]
        assert compute_cosine_similarity(vec, vec) > 0.99

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(compute_cosine_similarity(a, b)) < 0.01

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert compute_cosine_similarity(a, b) < -0.99

    def test_empty_vectors(self) -> None:
        assert compute_cosine_similarity([], []) == 0.0

    def test_zero_vector(self) -> None:
        assert compute_cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_different_lengths(self) -> None:
        assert compute_cosine_similarity([1.0], [1.0, 2.0]) == 0.0


class TestTemporalSimilarity:
    """Tests for temporal similarity."""

    def test_same_time(self) -> None:
        now = datetime.now(timezone.utc)
        assert compute_temporal_similarity(now, now) == 1.0

    def test_far_apart(self) -> None:
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=7)
        sim = compute_temporal_similarity(now, past)
        assert sim < 0.1

    def test_none_timestamps(self) -> None:
        now = datetime.now(timezone.utc)
        assert compute_temporal_similarity(None, now) == 0.5
        assert compute_temporal_similarity(now, None) == 0.5
        assert compute_temporal_similarity(None, None) == 0.5


class TestSourceSimilarity:
    """Tests for source similarity."""

    def test_same_source(self) -> None:
        assert compute_source_similarity("news", "news") == 1.0

    def test_different_source(self) -> None:
        assert compute_source_similarity("news", "sns") == 0.0

    def test_empty_source(self) -> None:
        assert compute_source_similarity("", "news") == 0.5


class TestComputeSimilarity:
    """Tests for composite similarity."""

    def test_identical_items(self) -> None:
        now = datetime.now(timezone.utc)
        embedding = [1.0, 0.0, 0.0]
        a = ClusterItem(
            item_id="1",
            text="test",
            keywords={"a", "b"},
            published_at=now,
            source_type="news",
            embedding=embedding,
        )
        b = ClusterItem(
            item_id="2",
            text="test",
            keywords={"a", "b"},
            published_at=now,
            source_type="news",
            embedding=embedding,
        )
        sim = compute_similarity(a, b)
        assert sim > 0.9

    def test_completely_different_items(self) -> None:
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=30)
        a = ClusterItem(
            item_id="1",
            text="sports",
            keywords={"football", "goal"},
            published_at=now,
            source_type="news",
            embedding=[1.0, 0.0, 0.0],
        )
        b = ClusterItem(
            item_id="2",
            text="politics",
            keywords={"election", "vote"},
            published_at=past,
            source_type="blog",
            embedding=[0.0, 0.0, 1.0],
        )
        sim = compute_similarity(a, b)
        assert sim < 0.3


class TestClusterItems:
    """Tests for cluster_items function."""

    def test_empty_input(self) -> None:
        assert cluster_items([]) == []

    def test_single_item(self) -> None:
        items = [ClusterItem(item_id="1", text="test")]
        clusters = cluster_items(items)
        assert len(clusters) == 1
        assert clusters[0].size == 1

    def test_similar_items_clustered(self) -> None:
        now = datetime.now(timezone.utc)
        emb = [1.0, 0.0, 0.0]
        items = [
            ClusterItem(
                item_id="1",
                text="news A",
                keywords={"economy", "growth"},
                published_at=now,
                source_type="news",
                embedding=emb,
            ),
            ClusterItem(
                item_id="2",
                text="news B",
                keywords={"economy", "growth", "gdp"},
                published_at=now,
                source_type="news",
                embedding=emb,
            ),
        ]
        clusters = cluster_items(items, threshold=0.3)
        assert len(clusters) == 1
        assert clusters[0].size == 2

    def test_dissimilar_items_separate(self) -> None:
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=30)
        items = [
            ClusterItem(
                item_id="1",
                text="sports",
                keywords={"football"},
                published_at=now,
                source_type="news",
                embedding=[1.0, 0.0, 0.0],
            ),
            ClusterItem(
                item_id="2",
                text="politics",
                keywords={"election"},
                published_at=past,
                source_type="blog",
                embedding=[0.0, 0.0, 1.0],
            ),
        ]
        clusters = cluster_items(items, threshold=0.8)
        assert len(clusters) == 2

    def test_cluster_structure(self) -> None:
        items = [ClusterItem(item_id="1", text="test")]
        clusters = cluster_items(items)
        cluster = clusters[0]
        assert isinstance(cluster, Cluster)
        assert cluster.cluster_id == "cluster_0"
        assert cluster.representative.item_id == "1"
