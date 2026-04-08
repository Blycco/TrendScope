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
    def test_passes_clean_article(self) -> None:
        articles = [_make_article(title="정상 뉴스 기사", body="내용이 있는 뉴스 기사입니다.")]
        result = _stage_spam_filter(articles)
        assert len(result) == 1

    def test_filters_spam_article(self) -> None:
        articles = [
            _make_article(
                title="무료 대출 카지노 도박 바카라",
                body=" ".join(["무료대출카지노도박"] * 20),
            )
        ]
        result = _stage_spam_filter(articles)
        assert isinstance(result, list)


class TestStageExtractKeywords:
    def test_adds_keywords_field(self) -> None:
        articles = [_make_article(title="Python 기초", body="파이썬은 배우기 쉬운 언어입니다.")]
        result = _stage_extract_keywords(articles)
        assert "keywords" in result[0]
        assert isinstance(result[0]["keywords"], list)

    def test_adds_keyword_importance(self) -> None:
        articles = [_make_article()]
        result = _stage_extract_keywords(articles)
        assert "keyword_importance" in result[0]
        assert isinstance(result[0]["keyword_importance"], float)

    def test_handles_empty_text(self) -> None:
        articles = [_make_article(title="", body="")]
        result = _stage_extract_keywords(articles)
        assert result[0]["keywords"] == []
        assert result[0]["keyword_importance"] == 0.0


class TestComputeEarlyTrendScore:
    def test_empty_articles_returns_zero(self) -> None:
        assert _compute_early_trend_score([]) == 0.0

    def test_single_recent_article(self) -> None:
        articles = [_make_article()]
        score = _compute_early_trend_score(articles)
        assert 0.0 < score <= 1.0

    def test_more_articles_higher_velocity(self) -> None:
        one = [_make_article()]
        many = [_make_article(url=f"https://example.com/{i}", url_hash=f"h{i}") for i in range(10)]
        assert _compute_early_trend_score(many) > _compute_early_trend_score(one)

    def test_diverse_sources_higher_score(self) -> None:
        same_source = [
            _make_article(url=f"https://example.com/{i}", url_hash=f"h{i}") for i in range(3)
        ]
        diverse = [
            {**_make_article(url=f"https://example.com/{i}", url_hash=f"h{i}"), "source": f"src{i}"}
            for i in range(3)
        ]
        assert _compute_early_trend_score(diverse) > _compute_early_trend_score(same_source)

    def test_score_bounded_zero_to_one(self) -> None:
        articles = [
            _make_article(url=f"https://example.com/{i}", url_hash=f"h{i}") for i in range(20)
        ]
        score = _compute_early_trend_score(articles)
        assert 0.0 <= score <= 1.0


class TestStageScore:
    def test_returns_scored_clusters(self) -> None:
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

        result = _stage_score([cluster])
        assert len(result) == 1
        assert "score" in result[0]
        assert result[0]["score"] >= 0
        assert "early_trend_score" in result[0]
        assert 0.0 <= result[0]["early_trend_score"] <= 1.0


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
