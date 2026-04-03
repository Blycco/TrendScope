"""Tests for backend.crawler.sources.burst_crawler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.crawler.sources.burst_crawler import (
    run_burst_crawl,
    search_google_news_rss,
    search_reddit,
)


def _make_pool(existing_hashes: set[str] | None = None) -> MagicMock:
    """Create a mock asyncpg pool."""
    pool = MagicMock()
    hashes = existing_hashes or set()

    async def mock_fetchval(query: str, *args: object) -> object:
        if "url_hash" in query:
            return 1 if args[0] in hashes else None
        return None

    pool.fetchval = AsyncMock(side_effect=mock_fetchval)
    pool.execute = AsyncMock()
    return pool


def _mock_http_client(response: MagicMock) -> MagicMock:
    """Create a mock httpx.AsyncClient context manager."""
    mock_client_inst = MagicMock()
    mock_client_inst.get = AsyncMock(return_value=response)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client_inst)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


_GNEWS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>AI 기술 혁신 발표</title>
      <link>https://example.com/news/1</link>
      <description>AI 관련 뉴스 요약</description>
      <pubDate>Thu, 03 Apr 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>글로벌 AI 트렌드</title>
      <link>https://example.com/news/2</link>
      <description>글로벌 AI 트렌드 요약</description>
    </item>
  </channel>
</rss>"""

_REDDIT_JSON = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "AI breakthrough discussion",
                    "permalink": "/r/technology/comments/abc123/ai_breakthrough/",
                    "selftext": "This is a discussion about AI",
                    "created_utc": 1743674400.0,
                    "subreddit": "technology",
                }
            },
            {
                "data": {
                    "title": "New ML paper released",
                    "permalink": "/r/MachineLearning/comments/def456/new_ml_paper/",
                    "selftext": "",
                    "created_utc": 1743674400.0,
                    "subreddit": "MachineLearning",
                }
            },
        ]
    }
}


class TestSearchGoogleNewsRss:
    @pytest.mark.asyncio
    async def test_parses_rss_results(self) -> None:
        pool = _make_pool()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = _GNEWS_RSS

        with patch(
            "backend.crawler.sources.burst_crawler.httpx.AsyncClient",
        ) as mock_client:
            mock_client.return_value = _mock_http_client(mock_resp)
            result = await search_google_news_rss(["AI", "기술"], "ko", pool)

        assert len(result) == 2
        assert result[0]["title"] == "AI 기술 혁신 발표"

    @pytest.mark.asyncio
    async def test_deduplicates_existing_articles(self) -> None:
        from backend.crawler.sources.news_crawler import _url_hash

        existing = {_url_hash("https://example.com/news/1")}
        pool = _make_pool(existing_hashes=existing)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = _GNEWS_RSS

        with patch(
            "backend.crawler.sources.burst_crawler.httpx.AsyncClient",
        ) as mock_client:
            mock_client.return_value = _mock_http_client(mock_resp)
            result = await search_google_news_rss(["AI"], "ko", pool)

        assert len(result) == 1
        assert result[0]["title"] == "글로벌 AI 트렌드"

    @pytest.mark.asyncio
    async def test_returns_empty_on_http_error(self) -> None:
        pool = _make_pool()
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch(
            "backend.crawler.sources.burst_crawler.httpx.AsyncClient",
        ) as mock_client:
            mock_client.return_value = _mock_http_client(mock_resp)
            result = await search_google_news_rss(["AI"], "ko", pool)

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_network_error(self) -> None:
        pool = _make_pool()
        err_client = MagicMock()
        err_client.get = AsyncMock(side_effect=ConnectionError("timeout"))
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=err_client)
        ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "backend.crawler.sources.burst_crawler.httpx.AsyncClient",
        ) as mock_client:
            mock_client.return_value = ctx
            result = await search_google_news_rss(["AI"], "ko", pool)

        assert result == []


class TestSearchReddit:
    @pytest.mark.asyncio
    async def test_parses_search_results(self) -> None:
        pool = _make_pool()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _REDDIT_JSON

        with patch(
            "backend.crawler.sources.burst_crawler.httpx.AsyncClient",
        ) as mock_client:
            mock_client.return_value = _mock_http_client(mock_resp)
            result = await search_reddit(["AI"], pool)

        assert len(result) == 2
        assert result[0]["title"] == "AI breakthrough discussion"

    @pytest.mark.asyncio
    async def test_returns_empty_on_http_error(self) -> None:
        pool = _make_pool()
        mock_resp = MagicMock()
        mock_resp.status_code = 429

        with patch(
            "backend.crawler.sources.burst_crawler.httpx.AsyncClient",
        ) as mock_client:
            mock_client.return_value = _mock_http_client(mock_resp)
            result = await search_reddit(["AI"], pool)

        assert result == []


class TestRunBurstCrawl:
    @pytest.mark.asyncio
    async def test_aggregates_all_sources(self) -> None:
        pool = _make_pool()

        with (
            patch(
                "backend.crawler.sources.burst_crawler.search_google_news_rss",
                new_callable=AsyncMock,
                return_value=[{"url": "a", "title": "a"}],
            ),
            patch(
                "backend.crawler.sources.burst_crawler.search_reddit",
                new_callable=AsyncMock,
                return_value=[{"url": "b", "title": "b"}, {"url": "c", "title": "c"}],
            ),
        ):
            total = await run_burst_crawl(["AI"], "ko", pool)

        assert total == 3

    @pytest.mark.asyncio
    async def test_handles_partial_failure(self) -> None:
        pool = _make_pool()

        with (
            patch(
                "backend.crawler.sources.burst_crawler.search_google_news_rss",
                new_callable=AsyncMock,
                side_effect=RuntimeError("gnews down"),
            ),
            patch(
                "backend.crawler.sources.burst_crawler.search_reddit",
                new_callable=AsyncMock,
                return_value=[{"url": "b", "title": "b"}],
            ),
        ):
            total = await run_burst_crawl(["AI"], "ko", pool)

        assert total == 1
