"""Tests for semantic_clusterer module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend.processor.shared.semantic_clusterer import (
    Cluster,
    ClusterItem,
    _cluster_greedy,
    cluster_items,
    compute_cosine_similarity,
    compute_jaccard,
    compute_similarity,
    compute_source_similarity,
    compute_temporal_similarity,
    refine_clusters,
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
        assert compute_temporal_similarity(None, now) == 0.0
        assert compute_temporal_similarity(now, None) == 0.0
        assert compute_temporal_similarity(None, None) == 0.0


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
        assert cluster.representative.item_id == "1"


class TestHdbscanClustering:
    """Tests for HDBSCAN-based clustering."""

    def test_hdbscan_clusters_similar_items(self) -> None:
        """Items with identical embeddings should cluster together."""
        now = datetime.now(timezone.utc)
        emb_a = [1.0, 0.0, 0.0]
        emb_b = [0.0, 0.0, 1.0]
        items = [
            ClusterItem(
                item_id="a1",
                text="economy",
                keywords={"경제", "성장"},
                published_at=now,
                source_type="news",
                embedding=emb_a,
            ),
            ClusterItem(
                item_id="a2",
                text="economy",
                keywords={"경제", "성장"},
                published_at=now,
                source_type="news",
                embedding=emb_a,
            ),
            ClusterItem(
                item_id="a3",
                text="economy",
                keywords={"경제", "성장"},
                published_at=now,
                source_type="news",
                embedding=emb_a,
            ),
            ClusterItem(
                item_id="b1",
                text="sports",
                keywords={"스포츠", "축구"},
                published_at=now,
                source_type="news",
                embedding=emb_b,
            ),
            ClusterItem(
                item_id="b2",
                text="sports",
                keywords={"스포츠", "축구"},
                published_at=now,
                source_type="news",
                embedding=emb_b,
            ),
            ClusterItem(
                item_id="b3",
                text="sports",
                keywords={"스포츠", "축구"},
                published_at=now,
                source_type="news",
                embedding=emb_b,
            ),
        ]
        clusters = cluster_items(items)
        # Should produce at least 2 clusters (economy vs sports)
        assert len(clusters) >= 2
        # All items should be accounted for
        total = sum(c.size for c in clusters)
        assert total == 6

    def test_hdbscan_separates_dissimilar(self) -> None:
        """Very different items should not cluster together."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=30)
        items = [
            ClusterItem(
                item_id="1",
                text="경제 성장률이 올해 들어 크게 개선됨",
                keywords={"경제", "성장률", "개선"},
                published_at=now,
                source_type="news",
                embedding=[1.0, 0.0, 0.0],
            ),
            ClusterItem(
                item_id="2",
                text="프로야구 시즌 개막 관중 기록 경신 소식",
                keywords={"스포츠", "프로야구", "관중"},
                published_at=past,
                source_type="blog",
                embedding=[0.0, 1.0, 0.0],
            ),
            ClusterItem(
                item_id="3",
                text="국회 본회의에서 예산안 통과 논란 확산",
                keywords={"정치", "국회", "예산안"},
                published_at=past,
                source_type="sns",
                embedding=[0.0, 0.0, 1.0],
            ),
        ]
        clusters = cluster_items(items)
        # All items are dissimilar → likely separate or noise
        assert len(clusters) >= 2

    def test_hdbscan_all_items_preserved(self) -> None:
        """Quality noise items should be preserved during clustering."""
        now = datetime.now(timezone.utc)
        items = [
            ClusterItem(
                item_id=f"item_{i}",
                text=f"이것은 충분히 긴 테스트 텍스트 아이템 번호 {i}",
                keywords={f"키워드{i}", f"주제{i}", f"태그{i}"},
                published_at=now,
                embedding=[float(i), 0.0, 0.0],
            )
            for i in range(5)
        ]
        clusters = cluster_items(items)
        all_ids = set()
        for c in clusters:
            all_ids.add(c.representative.item_id)
            for m in c.members:
                all_ids.add(m.item_id)
        assert all_ids == {f"item_{i}" for i in range(5)}

    def test_hdbscan_fallback_few_items(self) -> None:
        """With < 3 items, falls back to greedy."""
        now = datetime.now(timezone.utc)
        emb = [1.0, 0.0, 0.0]
        items = [
            ClusterItem(
                item_id="1",
                text="a",
                keywords={"경제"},
                published_at=now,
                source_type="news",
                embedding=emb,
            ),
            ClusterItem(
                item_id="2",
                text="b",
                keywords={"경제"},
                published_at=now,
                source_type="news",
                embedding=emb,
            ),
        ]
        clusters = cluster_items(items)
        assert len(clusters) >= 1
        total = sum(c.size for c in clusters)
        assert total == 2

    def test_greedy_fallback_on_import_error(self) -> None:
        """When HDBSCAN is unavailable, greedy fallback is used."""
        now = datetime.now(timezone.utc)
        emb = [1.0, 0.0, 0.0]
        items = [
            ClusterItem(
                item_id=str(i),
                text="a",
                keywords={"경제"},
                published_at=now,
                source_type="news",
                embedding=emb,
            )
            for i in range(4)
        ]
        with patch(
            "backend.processor.shared.semantic_clusterer._cluster_hdbscan",
            return_value=None,
        ):
            clusters = cluster_items(items)
            assert len(clusters) >= 1
            total = sum(c.size for c in clusters)
            assert total == 4


class TestClusterGreedy:
    """Tests for greedy fallback directly."""

    def test_greedy_similar_items(self) -> None:
        now = datetime.now(timezone.utc)
        emb = [1.0, 0.0, 0.0]
        items = [
            ClusterItem(
                item_id="1",
                text="a",
                keywords={"경제", "성장"},
                published_at=now,
                source_type="news",
                embedding=emb,
            ),
            ClusterItem(
                item_id="2",
                text="b",
                keywords={"경제", "성장", "gdp"},
                published_at=now,
                source_type="news",
                embedding=emb,
            ),
        ]
        clusters = _cluster_greedy(items, threshold=0.3)
        assert len(clusters) == 1
        assert clusters[0].size == 2


class TestRefineClusters:
    """Tests for refine_clusters outlier removal."""

    def test_refine_removes_outlier(self) -> None:
        """Outlier with very different embedding is separated."""
        good_emb = [1.0, 0.0, 0.0]
        outlier_emb = [0.0, 0.0, 1.0]  # orthogonal → low cosine
        cluster = Cluster(
            cluster_id="c0",
            representative=ClusterItem(
                item_id="1",
                text="a",
                keywords={"경제"},
                embedding=good_emb,
            ),
            members=[
                ClusterItem(item_id="2", text="b", keywords={"경제"}, embedding=good_emb),
                ClusterItem(item_id="3", text="c", keywords={"경제"}, embedding=good_emb),
                ClusterItem(
                    item_id="outlier",
                    text="d",
                    keywords={"스포츠"},
                    embedding=outlier_emb,
                ),
            ],
        )
        result = refine_clusters([cluster])
        # outlier should be separated
        all_ids = set()
        for c in result:
            all_ids.add(c.representative.item_id)
            for m in c.members:
                all_ids.add(m.item_id)
        assert "outlier" in all_ids  # not lost, just separated
        assert len(result) >= 2  # at least original + outlier singleton

    def test_refine_keeps_good_members(self) -> None:
        """All similar members stay together."""
        emb = [1.0, 0.0, 0.0]
        cluster = Cluster(
            cluster_id="c0",
            representative=ClusterItem(
                item_id="1",
                text="a",
                keywords={"경제"},
                embedding=emb,
            ),
            members=[
                ClusterItem(item_id="2", text="b", keywords={"경제"}, embedding=emb),
                ClusterItem(item_id="3", text="c", keywords={"경제"}, embedding=emb),
            ],
        )
        result = refine_clusters([cluster])
        assert len(result) == 1
        assert result[0].size == 3

    def test_refine_single_item_cluster(self) -> None:
        """Singleton clusters are unchanged."""
        cluster = Cluster(
            cluster_id="c0",
            representative=ClusterItem(item_id="1", text="a"),
        )
        result = refine_clusters([cluster])
        assert len(result) == 1
        assert result[0].size == 1

    def test_refine_no_embeddings_fallback(self) -> None:
        """Without embeddings, Jaccard is used as fallback."""
        shared_kw = {"경제", "성장", "투자"}
        outlier_kw = {"스포츠", "야구", "축구"}
        cluster = Cluster(
            cluster_id="c0",
            representative=ClusterItem(
                item_id="1",
                text="a",
                keywords=shared_kw,
            ),
            members=[
                ClusterItem(item_id="2", text="b", keywords=shared_kw),
                ClusterItem(item_id="3", text="c", keywords=shared_kw),
                ClusterItem(item_id="outlier", text="d", keywords=outlier_kw),
            ],
        )
        result = refine_clusters([cluster])
        # outlier has zero keyword overlap → should be separated
        singleton_ids = {c.representative.item_id for c in result if c.size == 1}
        assert "outlier" in singleton_ids


class TestClusterConfigAndTemporalFix:
    """T-05: ClusterConfig 전달 + temporal None=0.0 수정 검증."""

    def test_temporal_similarity_none_returns_zero(self) -> None:
        """None 타임스탬프 → 0.0 반환 (기존 0.5에서 변경)."""
        from backend.processor.shared.semantic_clusterer import compute_temporal_similarity

        assert compute_temporal_similarity(None, None) == 0.0
        assert compute_temporal_similarity(None, datetime.now(timezone.utc)) == 0.0

    def test_cluster_config_defaults(self) -> None:
        """ClusterConfig 기본값 확인."""
        from backend.processor.shared.semantic_clusterer import ClusterConfig

        cfg = ClusterConfig()
        assert cfg.cosine_weight == 0.50
        assert cfg.jaccard_weight == 0.25
        assert cfg.threshold == 0.55
        assert cfg.outlier_sigma == 1.0

    def test_compute_similarity_with_config(self) -> None:
        """config 파라미터 없이도 기본 동작 유지."""
        from backend.processor.shared.semantic_clusterer import (
            ClusterConfig,
            ClusterItem,
            compute_similarity,
        )

        a = ClusterItem(item_id="a", text="축구 경기 리그", keywords={"축구", "경기"})
        b = ClusterItem(item_id="b", text="축구 월드컵 선수", keywords={"축구", "월드컵"})
        sim_default = compute_similarity(a, b)
        sim_config = compute_similarity(a, b, ClusterConfig())
        # Jaccard("축구") overlap → sim > 0
        assert sim_default > 0.0
        assert abs(sim_default - sim_config) < 1e-9

    def test_different_topic_low_jaccard(self) -> None:
        """다른 주제 기사 → Jaccard < 0.25."""
        from backend.processor.shared.semantic_clusterer import compute_jaccard

        kws_a = {"12월", "실적", "매출", "영업이익", "기업"}
        kws_b = {"12월", "날씨", "기온", "한파", "겨울"}
        # 공통 키워드 "12월" 1개, 합집합 9개 → Jaccard ≈ 0.11
        assert compute_jaccard(kws_a, kws_b) < 0.25
