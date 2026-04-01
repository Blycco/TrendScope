"""Tests for backend.crawler.sources.news_crawler."""

from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from backend.crawler.sources.news_crawler import (
    _content_fp,
    _parse_published,
    _url_hash,
    crawl_all,
    crawl_feed,
)


def _make_db_pool() -> MagicMock:
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="INSERT 0 1")
    return pool


def _make_feed_source(
    url: str = "https://example.com/rss",
    name: str = "Test Feed",
    category: str = "it",
    locale: str = "ko",
) -> dict:
    return {"url": url, "name": name, "category": category, "locale": locale}


class TestUrlHash:
    def test_returns_16_char_hex(self) -> None:
        result = _url_hash("https://example.com")
        assert len(result) == 16

    def test_consistent(self) -> None:
        assert _url_hash("https://a.com") == _url_hash("https://a.com")

    def test_unique_per_url(self) -> None:
        assert _url_hash("https://a.com") != _url_hash("https://b.com")


class TestContentFp:
    def test_returns_16_char_hex(self) -> None:
        result = _content_fp("title", "body content here")
        assert len(result) == 16

    def test_uses_title_and_body(self) -> None:
        assert _content_fp("title A", "same body") != _content_fp("title B", "same body")

    def test_truncates_body_to_200(self) -> None:
        long_body = "x" * 500
        assert _content_fp("t", long_body) == _content_fp("t", long_body[:200])


class TestParsePublished:
    def test_returns_now_when_no_parsed(self) -> None:
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = None
        result = _parse_published(entry)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_uses_published_parsed(self) -> None:
        entry = MagicMock()
        entry.published_parsed = time.localtime()
        entry.updated_parsed = None
        result = _parse_published(entry)
        assert isinstance(result, datetime)

    def test_falls_back_to_updated(self) -> None:
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = time.localtime()
        result = _parse_published(entry)
        assert isinstance(result, datetime)


class TestCrawlFeed:
    async def test_returns_empty_when_quota_exceeded(self) -> None:
        pool = _make_db_pool()
        feed = _make_feed_source()
        with patch(
            "backend.crawler.sources.news_crawler.check_quota",
            AsyncMock(return_value=False),
        ):
            result = await crawl_feed(feed, pool)
            assert result == []

    async def test_returns_empty_on_304_response(self) -> None:
        pool = _make_db_pool()
        feed = _make_feed_source()
        with (
            patch(
                "backend.crawler.sources.news_crawler.check_quota",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.crawler.sources.news_crawler.get_cached",
                AsyncMock(return_value=None),
            ),
            patch("httpx.AsyncClient") as mock_cls,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 304
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await crawl_feed(feed, pool)
            assert result == []

    async def test_returns_empty_on_http_error(self) -> None:
        pool = _make_db_pool()
        feed = _make_feed_source()
        with (
            patch(
                "backend.crawler.sources.news_crawler.check_quota",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.crawler.sources.news_crawler.get_cached",
                AsyncMock(return_value=None),
            ),
            patch("httpx.AsyncClient") as mock_cls,
        ):
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=RuntimeError("network error"))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await crawl_feed(feed, pool)
            assert result == []

    async def test_processes_feed_entries(self) -> None:
        pool = _make_db_pool()
        feed = _make_feed_source()

        entry = MagicMock()
        entry.get = MagicMock(
            side_effect=lambda k, d="": {
                "link": "https://example.com/article/1",
                "title": "Test Article Title",
                "author": "John Doe",
            }.get(k, d)
        )
        entry.published_parsed = None
        entry.updated_parsed = None

        mock_parsed = MagicMock()
        mock_parsed.entries = [entry]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<rss>...</rss>"
        mock_resp.headers = {}

        with (
            patch(
                "backend.crawler.sources.news_crawler.check_quota",
                AsyncMock(return_value=True),
            ),
            patch("backend.crawler.sources.news_crawler.increment_quota", AsyncMock()),
            patch(
                "backend.crawler.sources.news_crawler.get_cached",
                AsyncMock(return_value=None),
            ),
            patch("backend.crawler.sources.news_crawler.set_cached", AsyncMock()),
            patch(
                "backend.crawler.sources.news_crawler.extract_body",
                AsyncMock(return_value="Article body text"),
            ),
            patch(
                "backend.crawler.sources.news_crawler.feedparser.parse",
                return_value=mock_parsed,
            ),
            patch("httpx.AsyncClient") as mock_cls,
        ):
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await crawl_feed(feed, pool, extract_bodies=True)
            assert isinstance(result, list)


def _make_feed_row(
    feed_id: str = "feed-1",
    url: str = "https://example.com/rss",
    name: str = "Test Feed",
    category: str = "it",
    locale: str = "ko",
) -> MagicMock:
    row = MagicMock()
    data = {
        "id": feed_id,
        "url": url,
        "name": name,
        "category": category,
        "locale": locale,
        "config": {},
    }
    row.__getitem__ = lambda self, key: data[key]
    return row


class TestCrawlAll:
    async def test_returns_list(self) -> None:
        pool = _make_db_pool()
        feed_row = _make_feed_row()
        with (
            patch(
                "backend.crawler.sources.news_crawler.get_feed_sources_for_crawl",
                AsyncMock(return_value=[feed_row]),
            ),
            patch(
                "backend.crawler.sources.news_crawler.crawl_feed",
                AsyncMock(return_value=[{"title": "article"}]),
            ),
            patch(
                "backend.crawler.sources.news_crawler.update_feed_health",
                AsyncMock(),
            ),
        ):
            result = await crawl_all(pool)
            assert isinstance(result, list)
            assert len(result) > 0

    async def test_returns_empty_on_all_failures(self) -> None:
        pool = _make_db_pool()
        with patch(
            "backend.crawler.sources.news_crawler.get_feed_sources_for_crawl",
            AsyncMock(return_value=[]),
        ):
            result = await crawl_all(pool)
            assert result == []

    async def test_updates_health_on_success(self) -> None:
        pool = _make_db_pool()
        feed_row = _make_feed_row()
        mock_health = AsyncMock()
        with (
            patch(
                "backend.crawler.sources.news_crawler.get_feed_sources_for_crawl",
                AsyncMock(return_value=[feed_row]),
            ),
            patch(
                "backend.crawler.sources.news_crawler.crawl_feed",
                AsyncMock(return_value=[]),
            ),
            patch(
                "backend.crawler.sources.news_crawler.update_feed_health",
                mock_health,
            ),
        ):
            await crawl_all(pool)
            mock_health.assert_awaited_once()
            call_kwargs = mock_health.call_args.kwargs
            assert call_kwargs["success"] is True

    async def test_updates_health_on_failure(self) -> None:
        pool = _make_db_pool()
        feed_row = _make_feed_row()
        mock_health = AsyncMock()
        with (
            patch(
                "backend.crawler.sources.news_crawler.get_feed_sources_for_crawl",
                AsyncMock(return_value=[feed_row]),
            ),
            patch(
                "backend.crawler.sources.news_crawler.crawl_feed",
                AsyncMock(side_effect=RuntimeError("timeout")),
            ),
            patch(
                "backend.crawler.sources.news_crawler.update_feed_health",
                mock_health,
            ),
        ):
            await crawl_all(pool)
            mock_health.assert_awaited_once()
            call_kwargs = mock_health.call_args.kwargs
            assert call_kwargs["success"] is False
            assert "timeout" in call_kwargs["error"]
