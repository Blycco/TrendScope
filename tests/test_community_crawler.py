"""Tests for backend.crawler.sources.community_crawler."""

from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.crawler.sources.community_crawler import (
    _content_fp,
    _fetch_article_body,
    _parse_time,
    _url_hash,
    crawl_all,
    crawl_dc_inside,
    crawl_fm_korea,
)


def _make_db_pool() -> MagicMock:
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="INSERT 0 1")
    return pool


class TestUrlHash:
    def test_returns_16_char_hex(self) -> None:
        result = _url_hash("https://example.com/article")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_url_same_hash(self) -> None:
        assert _url_hash("https://example.com") == _url_hash("https://example.com")

    def test_different_urls_different_hash(self) -> None:
        assert _url_hash("https://a.com") != _url_hash("https://b.com")


class TestContentFp:
    def test_returns_16_char_hex(self) -> None:
        result = _content_fp("title", "body")
        assert len(result) == 16

    def test_different_titles_different_fp(self) -> None:
        assert _content_fp("title A", "body") != _content_fp("title B", "body")


class TestParseTime:
    def test_returns_now_when_no_parsed(self) -> None:
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = None
        result = _parse_time(entry)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_returns_published_parsed_when_available(self) -> None:
        entry = MagicMock()
        entry.published_parsed = time.localtime()
        entry.updated_parsed = None
        result = _parse_time(entry)
        assert isinstance(result, datetime)

    def test_falls_back_to_updated_parsed(self) -> None:
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = time.localtime()
        result = _parse_time(entry)
        assert isinstance(result, datetime)


class TestFetchArticleBody:
    @pytest.mark.asyncio
    async def test_extracts_body_from_html(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body><p>본문 텍스트입니다. 충분히 긴 본문.</p></body></html>"

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with (
            patch(
                "backend.crawler.sources.community_crawler.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.crawler.sources.community_crawler.extract_body",
                AsyncMock(return_value="본문 텍스트입니다. 충분히 긴 본문."),
            ) as mock_extract,
        ):
            result = await _fetch_article_body(mock_client, "https://example.com/article")
            assert result == "본문 텍스트입니다. 충분히 긴 본문."
            mock_extract.assert_called_once_with("https://example.com/article", html=mock_resp.text)

    @pytest.mark.asyncio
    async def test_returns_empty_on_http_error(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 403

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch(
            "backend.crawler.sources.community_crawler.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await _fetch_article_body(mock_client, "https://example.com/blocked")
            assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self) -> None:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("timeout"))

        with patch(
            "backend.crawler.sources.community_crawler.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await _fetch_article_body(mock_client, "https://example.com/timeout")
            assert result == ""

    @pytest.mark.asyncio
    async def test_respects_delay(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body>text</body></html>"

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with (
            patch(
                "backend.crawler.sources.community_crawler.asyncio.sleep",
                new_callable=AsyncMock,
            ) as mock_sleep,
            patch(
                "backend.crawler.sources.community_crawler.extract_body",
                AsyncMock(return_value=""),
            ),
        ):
            await _fetch_article_body(mock_client, "https://example.com")
            mock_sleep.assert_called_once_with(0.5)


class TestCrawlDcInside:
    async def test_returns_empty_when_quota_exceeded(self) -> None:
        pool = _make_db_pool()
        with patch(
            "backend.crawler.sources.community_crawler.check_quota",
            AsyncMock(return_value=False),
        ):
            result = await crawl_dc_inside(pool)
            assert result == []

    async def test_returns_empty_on_http_error(self) -> None:
        pool = _make_db_pool()
        dc_row = MagicMock()
        dc_data = {
            "id": "dc-1",
            "url": "https://rss.dcinside.com/?mi=hot",
            "name": "DC 핫갤",
            "category": "general",
            "locale": "ko",
            "config": {},
        }
        dc_row.__getitem__ = lambda self, key: dc_data[key]

        with (
            patch(
                "backend.crawler.sources.community_crawler.check_quota",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.crawler.sources.community_crawler.get_feed_sources_for_crawl",
                AsyncMock(return_value=[dc_row]),
            ),
            patch(
                "backend.crawler.sources.community_crawler.update_feed_health",
                AsyncMock(),
            ),
            patch("httpx.AsyncClient") as mock_cls,
        ):
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=RuntimeError("network error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await crawl_dc_inside(pool)
            assert isinstance(result, list)


class TestCrawlFmKorea:
    async def test_returns_empty_when_quota_exceeded(self) -> None:
        pool = _make_db_pool()
        with patch(
            "backend.crawler.sources.community_crawler.check_quota",
            AsyncMock(return_value=False),
        ):
            result = await crawl_fm_korea(pool)
            assert result == []


class TestCrawlAll:
    async def test_returns_combined_list(self) -> None:
        pool = _make_db_pool()
        with (
            patch(
                "backend.crawler.sources.community_crawler.crawl_dc_inside",
                AsyncMock(return_value=[{"title": "DC article"}]),
            ),
            patch(
                "backend.crawler.sources.community_crawler.crawl_fm_korea",
                AsyncMock(return_value=[{"title": "FM article"}]),
            ),
        ):
            result = await crawl_all(pool)
            assert len(result) == 2

    async def test_returns_empty_on_no_results(self) -> None:
        pool = _make_db_pool()
        with (
            patch(
                "backend.crawler.sources.community_crawler.crawl_dc_inside",
                AsyncMock(return_value=[]),
            ),
            patch(
                "backend.crawler.sources.community_crawler.crawl_fm_korea",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await crawl_all(pool)
            assert result == []
