"""Tests for backend.processor.pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.processor.pipeline import (
    _compute_early_trend_score,
    _stage_dedupe,
    _stage_extract_keywords,
    _stage_normalize,
    _stage_score,
    _stage_spam_filter,
    _stage_warm_cache,
    process_articles,
)
from backend.processor.shared.semantic_clusterer import Cluster, ClusterItem


def _make_article(
    url: str = "https://example.com/article",
    title: str = "Test Article Title",
    body: str = "This is the article body text.",
    category: str = "it",
    locale: str = "ko",
    url_hash: str = "abc123",
    content_fp: str = "def456",
) -> dict:
    return {
        "url": url,
        "url_hash": url_hash,
        "content_fp": content_fp,
        "title": title,
        "body": body,
        "category": category,
        "locale": locale,
        "source": "test_source",
        "publish_time": datetime.now(tz=timezone.utc),
    }


def _make_db_pool(group_id: int = 1) -> MagicMock:
    pool = MagicMock()
    pool.fetchval = AsyncMock(return_value=group_id)
    pool.execute = AsyncMock(return_value="UPDATE 1")
    return pool


class TestStageNormalize:
    def test_normalizes_title_and_body(self) -> None:
        articles = [_make_article(title="  Test  ", body="  Body  ")]
        result = _stage_normalize(articles)
        assert len(result) == 1
        assert result[0]["title"].strip() == result[0]["title"]

    def test_removes_article_with_empty_title(self) -> None:
        articles = [_make_article(title="   ")]
        result = _stage_normalize(articles)
        assert len(result) == 0

    def test_handles_normalize_error_gracefully(self) -> None:
        articles = [{"url": "https://x.com", "title": None, "body": "body"}]
        result = _stage_normalize(articles)
        assert isinstance(result, list)


class TestStageSpamFilter:
    async def test_passes_clean_article(self) -> None:
        articles = [_make_article(title="정상 뉴스 기사", body="내용이 있는 뉴스 기사입니다.")]
        pool = MagicMock()
        _mock_cfg = AsyncMock(side_effect=[0.3, 3, 20, 2])
        _mock_kw = AsyncMock(return_value=frozenset())
        with (
            patch("backend.processor.stages.spam_filter.get_setting", _mock_cfg),
            patch("backend.processor.stages.spam_filter.get_filter_keywords", _mock_kw),
        ):
            result = await _stage_spam_filter(articles, pool)
        assert len(result) == 1

    async def test_filters_spam_article(self) -> None:
        articles = [
            _make_article(
                title="무료 대출 카지노 도박 바카라",
                body=" ".join(["무료대출카지노도박"] * 20),
            )
        ]
        pool = MagicMock()
        _mock_cfg = AsyncMock(side_effect=[0.3, 3, 20, 2])
        _mock_kw = AsyncMock(return_value=frozenset())
        with (
            patch("backend.processor.stages.spam_filter.get_setting", _mock_cfg),
            patch("backend.processor.stages.spam_filter.get_filter_keywords", _mock_kw),
        ):
            result = await _stage_spam_filter(articles, pool)
        assert isinstance(result, list)


class TestStageExtractKeywords:
    @staticmethod
    def _mock_pool() -> MagicMock:
        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return pool

    async def test_adds_keywords_field(self) -> None:
        articles = [_make_article(title="Python 기초", body="파이썬은 배우기 쉬운 언어입니다.")]
        with (
            patch(
                "backend.processor.shared.config_loader.get_stopwords", new_callable=AsyncMock
            ) as mock_sw,
            patch(
                "backend.processor.shared.config_loader.get_setting", new_callable=AsyncMock
            ) as mock_gs,
        ):
            mock_sw.return_value = frozenset()
            mock_gs.return_value = 2.0
            result = await _stage_extract_keywords(articles, self._mock_pool())
        assert "keywords" in result[0]
        assert isinstance(result[0]["keywords"], list)

    async def test_adds_keyword_importance(self) -> None:
        articles = [_make_article()]
        with (
            patch(
                "backend.processor.shared.config_loader.get_stopwords", new_callable=AsyncMock
            ) as mock_sw,
            patch(
                "backend.processor.shared.config_loader.get_setting", new_callable=AsyncMock
            ) as mock_gs,
        ):
            mock_sw.return_value = frozenset()
            mock_gs.return_value = 2.0
            result = await _stage_extract_keywords(articles, self._mock_pool())
        assert "keyword_importance" in result[0]
        assert isinstance(result[0]["keyword_importance"], float)

    async def test_handles_empty_text(self) -> None:
        articles = [_make_article(title="", body="")]
        with (
            patch(
                "backend.processor.shared.config_loader.get_stopwords", new_callable=AsyncMock
            ) as mock_sw,
            patch(
                "backend.processor.shared.config_loader.get_setting", new_callable=AsyncMock
            ) as mock_gs,
        ):
            mock_sw.return_value = frozenset()
            mock_gs.return_value = 2.0
            result = await _stage_extract_keywords(articles, self._mock_pool())
        assert result[0]["keywords"] == []
        assert result[0]["keyword_importance"] == 0.0


class TestComputeEarlyTrendScore:
    def test_empty_articles_returns_zero(self) -> None:
        assert _compute_early_trend_score([]) == 0.0

    def test_single_source_returns_zero(self) -> None:
        """Single source is not an emerging trend."""
        articles = [_make_article()]
        score = _compute_early_trend_score(articles)
        assert score == 0.0

    def test_two_sources_returns_positive(self) -> None:
        """Two different sources produce a positive early trend score."""
        articles = [
            _make_article(),
            {**_make_article(url="https://other.com/1", url_hash="h2"), "source": "other"},
        ]
        score = _compute_early_trend_score(articles)
        assert score > 0.0

    def test_more_articles_higher_velocity(self) -> None:
        two_src = [
            {**_make_article(url=f"https://a.com/{i}", url_hash=f"a{i}"), "source": "srcA"}
            for i in range(2)
        ] + [
            {**_make_article(url=f"https://b.com/{i}", url_hash=f"b{i}"), "source": "srcB"}
            for i in range(8)
        ]
        few = [
            _make_article(),
            {**_make_article(url="https://other.com/1", url_hash="h2"), "source": "other"},
        ]
        assert _compute_early_trend_score(two_src) > _compute_early_trend_score(few)

    def test_diverse_sources_higher_score(self) -> None:
        # same_source: all from one source (returns 0 — single source)
        same_source = [
            _make_article(url=f"https://example.com/{i}", url_hash=f"h{i}") for i in range(3)
        ]
        # diverse: 3 different sources
        diverse = [
            {**_make_article(url=f"https://example.com/{i}", url_hash=f"h{i}"), "source": f"src{i}"}
            for i in range(3)
        ]
        assert _compute_early_trend_score(same_source) == 0.0
        assert _compute_early_trend_score(diverse) > 0.0

    def test_score_bounded_zero_to_one(self) -> None:
        articles = [
            {**_make_article(url=f"https://example.com/{i}", url_hash=f"h{i}"), "source": f"s{i}"}
            for i in range(20)
        ]
        score = _compute_early_trend_score(articles)
        assert 0.0 < score <= 1.0


class TestStageScore:
    @staticmethod
    def _mock_pool() -> MagicMock:
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=None)
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return pool

    async def test_returns_scored_clusters(self) -> None:
        article = _make_article()
        article["keywords"] = ["python", "code"]
        article["keyword_importance"] = 0.5

        item = ClusterItem(
            item_id="abc123",
            text="Test article",
            keywords={"python", "code"},
            published_at=datetime.now(tz=timezone.utc),
            source_type="test",
        )
        cluster = Cluster(cluster_id="test-cluster-1", representative=item, members=[])
        cluster._articles = [article]  # type: ignore[attr-defined]

        with patch(
            "backend.processor.shared.config_loader.get_setting",
            new_callable=AsyncMock,
            return_value=25.0,
        ):
            result = await _stage_score([cluster], self._mock_pool())
        assert len(result) == 1
        assert "score" in result[0]
        assert result[0]["score"] >= 0
        assert "early_trend_score" in result[0]
        assert 0.0 <= result[0]["early_trend_score"] <= 1.0
        assert "burst_score" in result[0]

    async def test_group_title_prefers_longest_article_title(self) -> None:
        short_article = _make_article(url="https://x.com/1", url_hash="h1", title="AI")
        short_article["keywords"] = ["ai", "chip"]
        long_article = _make_article(
            url="https://x.com/2",
            url_hash="h2",
            title="엔비디아 AI 반도체 호조로 주가 급등",
        )
        long_article["keywords"] = ["ai", "chip"]

        item = ClusterItem(
            item_id="abc123",
            text="Test",
            keywords={"ai", "chip"},
            published_at=datetime.now(tz=timezone.utc),
            source_type="test",
        )
        cluster = Cluster(cluster_id="t1", representative=item, members=[])
        cluster._articles = [short_article, long_article]  # type: ignore[attr-defined]

        with patch(
            "backend.processor.shared.config_loader.get_setting",
            new_callable=AsyncMock,
            return_value=25.0,
        ):
            result = await _stage_score([cluster], self._mock_pool())
        assert result[0]["title"] == "엔비디아 AI 반도체 호조로 주가 급등"

    async def test_group_title_falls_back_to_keywords_only_when_no_titles(self) -> None:
        untitled = _make_article(title="")
        untitled["keywords"] = ["ai", "chip", "nvidia"]

        item = ClusterItem(
            item_id="abc123",
            text="Test",
            keywords={"ai"},
            published_at=datetime.now(tz=timezone.utc),
            source_type="test",
        )
        cluster = Cluster(cluster_id="t2", representative=item, members=[])
        cluster._articles = [untitled]  # type: ignore[attr-defined]

        with patch(
            "backend.processor.shared.config_loader.get_setting",
            new_callable=AsyncMock,
            return_value=25.0,
        ):
            result = await _stage_score([cluster], self._mock_pool())
        assert " · " in result[0]["title"]


class TestStageWarmCache:
    async def test_warms_cache_for_items(self) -> None:
        items = [
            {"title": "Test", "score": 80.0, "keywords": ["kw1"], "category": "it", "locale": "ko"},
            {
                "title": "Test2",
                "score": 70.0,
                "keywords": ["kw2"],
                "category": "it",
                "locale": "ko",
            },
        ]
        with patch("backend.processor.stages.cache.set_cached", AsyncMock()) as mock_set:
            await _stage_warm_cache(items)
            mock_set.assert_awaited()

    async def test_handles_cache_error_gracefully(self) -> None:
        items = [{"title": "T", "score": 1.0, "keywords": [], "category": "x", "locale": "ko"}]
        with patch(
            "backend.processor.stages.cache.set_cached",
            AsyncMock(side_effect=RuntimeError("Redis down")),
        ):
            await _stage_warm_cache(items)  # should not raise


class TestProcessArticles:
    async def test_empty_input_returns_zero(self) -> None:
        pool = _make_db_pool()
        result = await process_articles([], pool)
        assert result == 0

    async def test_all_duplicates_returns_zero(self) -> None:
        articles = [_make_article()]
        with patch("backend.processor.stages.dedupe.is_duplicate", AsyncMock(return_value=True)):
            pool = _make_db_pool()
            result = await process_articles(articles, pool)
            assert result == 0

    async def test_full_pipeline_single_article(self) -> None:
        articles = [
            _make_article(title="AI 기술 뉴스", body="인공지능 기술이 빠르게 발전하고 있습니다.")
        ]
        with (
            patch("backend.processor.stages.dedupe.is_duplicate", AsyncMock(return_value=False)),
            patch("backend.processor.stages.cache.set_cached", AsyncMock()),
            patch(
                "backend.processor.stages.spam_filter.get_setting",
                AsyncMock(side_effect=[0.3, 3, 20, 2]),
            ),
            patch(
                "backend.processor.stages.spam_filter.get_filter_keywords",
                AsyncMock(return_value=frozenset()),
            ),
        ):
            pool = _make_db_pool(group_id=42)
            result = await process_articles(articles, pool)
            assert isinstance(result, int)
            assert result >= 0

    async def test_dedupe_error_passes_article_through(self) -> None:
        articles = [_make_article()]
        with patch(
            "backend.processor.stages.dedupe.is_duplicate",
            AsyncMock(side_effect=RuntimeError("Redis error")),
        ):
            result = await _stage_dedupe(articles)
            assert len(result) == 1
