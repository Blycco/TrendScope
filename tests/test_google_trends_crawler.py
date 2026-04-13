"""Tests for Google Trends RSS crawler in backend.crawler.sources.sns_crawler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.crawler.sources.sns_crawler import (
    _parse_approx_traffic,
    collect_all,
    crawl_google_trends_rss,
)

# ---------------------------------------------------------------------------
# _parse_approx_traffic
# ---------------------------------------------------------------------------


class TestParseApproxTraffic:
    def test_plain_number(self) -> None:
        assert _parse_approx_traffic("500000") == 500_000.0

    def test_comma_separated(self) -> None:
        assert _parse_approx_traffic("500,000+") == 500_000.0

    def test_with_plus(self) -> None:
        assert _parse_approx_traffic("1,000,000+") == 1_000_000.0

    def test_empty_string(self) -> None:
        assert _parse_approx_traffic("") == 0.0

    def test_invalid(self) -> None:
        assert _parse_approx_traffic("N/A") == 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_RSS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:ht="https://trends.google.com/trending/rss">
  <channel>
    <title>Trending Searches - South Korea</title>
    <item>
      <title>두쫀쿠</title>
      <ht:approx_traffic>500,000+</ht:approx_traffic>
      <link>https://trends.google.com/trending?q=두쫀쿠</link>
    </item>
    <item>
      <title>버터떡</title>
      <ht:approx_traffic>200,000+</ht:approx_traffic>
      <link>https://trends.google.com/trending?q=버터떡</link>
    </item>
    <item>
      <title></title>
      <ht:approx_traffic>100+</ht:approx_traffic>
    </item>
  </channel>
</rss>
"""


def _make_pool_with_quota(quota_ok: bool = True) -> MagicMock:
    """Create a mock pool where check_quota returns quota_ok."""
    pool = MagicMock()
    return pool


def _make_feed_rows(
    count: int = 1,
) -> list[MagicMock]:
    rows = []
    for i in range(count):
        row = MagicMock()
        data = {
            "id": f"feed-{i}",
            "url": "https://trends.google.com/trending/rss?geo=KR",
            "name": "Google Trends KR",
            "category": "general",
            "locale": "ko",
            "config": {},
        }
        row.__getitem__ = lambda self, key, d=data: d[key]
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# crawl_google_trends_rss
# ---------------------------------------------------------------------------


class TestCrawlGoogleTrendsRss:
    @pytest.mark.asyncio
    @patch("backend.crawler.sources.sns_crawler.update_feed_health", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.increment_quota", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.get_feed_sources_for_crawl", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.check_quota", new_callable=AsyncMock)
    async def test_returns_parsed_items(
        self,
        mock_check_quota: AsyncMock,
        mock_get_feeds: AsyncMock,
        mock_increment: AsyncMock,
        mock_health: AsyncMock,
    ) -> None:
        mock_check_quota.return_value = True
        mock_get_feeds.return_value = _make_feed_rows(1)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = _SAMPLE_RSS_XML

        with patch("backend.crawler.sources.sns_crawler.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            pool = _make_pool_with_quota()
            results = await crawl_google_trends_rss(pool)

        # Empty title item should be skipped
        assert len(results) == 2
        assert results[0]["platform"] == "google_trends"
        assert results[0]["keyword"] == "두쫀쿠"
        assert results[0]["score"] == 500_000.0
        assert results[0]["locale"] == "ko"
        assert results[1]["keyword"] == "버터떡"
        assert results[1]["score"] == 200_000.0

    @pytest.mark.asyncio
    @patch("backend.crawler.sources.sns_crawler.check_quota", new_callable=AsyncMock)
    async def test_quota_exceeded_returns_empty(
        self,
        mock_check_quota: AsyncMock,
    ) -> None:
        mock_check_quota.return_value = False
        pool = _make_pool_with_quota()
        results = await crawl_google_trends_rss(pool)
        assert results == []

    @pytest.mark.asyncio
    @patch("backend.crawler.sources.sns_crawler.get_feed_sources_for_crawl", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.check_quota", new_callable=AsyncMock)
    async def test_no_active_feeds_returns_empty(
        self,
        mock_check_quota: AsyncMock,
        mock_get_feeds: AsyncMock,
    ) -> None:
        mock_check_quota.return_value = True
        mock_get_feeds.return_value = []
        pool = _make_pool_with_quota()
        results = await crawl_google_trends_rss(pool)
        assert results == []

    @pytest.mark.asyncio
    @patch("backend.crawler.sources.sns_crawler.update_feed_health", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.get_feed_sources_for_crawl", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.check_quota", new_callable=AsyncMock)
    async def test_http_error_skips_feed(
        self,
        mock_check_quota: AsyncMock,
        mock_get_feeds: AsyncMock,
        mock_health: AsyncMock,
    ) -> None:
        mock_check_quota.return_value = True
        mock_get_feeds.return_value = _make_feed_rows(1)

        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("backend.crawler.sources.sns_crawler.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            pool = _make_pool_with_quota()
            results = await crawl_google_trends_rss(pool)

        assert results == []
        mock_health.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.crawler.sources.sns_crawler.update_feed_health", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.increment_quota", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.get_feed_sources_for_crawl", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.check_quota", new_callable=AsyncMock)
    async def test_meta_contains_traffic_and_link(
        self,
        mock_check_quota: AsyncMock,
        mock_get_feeds: AsyncMock,
        mock_increment: AsyncMock,
        mock_health: AsyncMock,
    ) -> None:
        mock_check_quota.return_value = True
        mock_get_feeds.return_value = _make_feed_rows(1)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = _SAMPLE_RSS_XML

        with patch("backend.crawler.sources.sns_crawler.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            pool = _make_pool_with_quota()
            results = await crawl_google_trends_rss(pool)

        meta = results[0]["meta"]
        assert meta["approx_traffic"] == 500_000.0
        assert "link" in meta


# ---------------------------------------------------------------------------
# collect_all — Nitter removed, Google Trends added
# ---------------------------------------------------------------------------


class TestCollectAllGoogleTrends:
    @pytest.mark.asyncio
    @patch("backend.crawler.sources.sns_crawler._save_sns_trends", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.crawl_naver_datalab", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.crawl_youtube", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.crawl_google_trends_rss", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.crawl_reddit", new_callable=AsyncMock)
    async def test_collect_all_includes_google_trends(
        self,
        mock_reddit: AsyncMock,
        mock_gt: AsyncMock,
        mock_youtube: AsyncMock,
        mock_naver: AsyncMock,
        mock_save: AsyncMock,
    ) -> None:
        mock_reddit.return_value = []
        mock_gt.return_value = [{"platform": "google_trends", "keyword": "test", "score": 1000.0}]
        mock_youtube.return_value = []
        mock_naver.return_value = []
        mock_save.return_value = 1

        pool = MagicMock()
        results = await collect_all(pool)

        assert len(results) == 1
        assert results[0]["platform"] == "google_trends"
        mock_gt.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.crawler.sources.sns_crawler._save_sns_trends", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.crawl_naver_datalab", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.crawl_youtube", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.crawl_google_trends_rss", new_callable=AsyncMock)
    @patch("backend.crawler.sources.sns_crawler.crawl_reddit", new_callable=AsyncMock)
    async def test_collect_all_no_nitter_call(
        self,
        mock_reddit: AsyncMock,
        mock_gt: AsyncMock,
        mock_youtube: AsyncMock,
        mock_naver: AsyncMock,
        mock_save: AsyncMock,
    ) -> None:
        """Nitter should not be called — it's been removed from collect_all."""
        mock_reddit.return_value = []
        mock_gt.return_value = []
        mock_youtube.return_value = []
        mock_naver.return_value = []
        mock_save.return_value = 0

        pool = MagicMock()
        await collect_all(pool)

        # Verify crawl_nitter has been removed from the module
        import importlib

        mod = importlib.import_module("backend.crawler.sources.sns_crawler")
        assert not hasattr(mod, "crawl_nitter")
