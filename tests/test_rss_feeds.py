"""Tests for backend.crawler.sources.rss_feeds — constants structure."""

from __future__ import annotations

from backend.crawler.sources.rss_feeds import (
    ALL_NEWS_FEEDS,
    COMMUNITY_FEEDS,
    GLOBAL_NEWS_FEEDS,
    KR_NEWS_FEEDS,
    NITTER_INSTANCES,
    REDDIT_SUBREDDITS,
)


class TestRssFeeds:
    def test_all_news_feeds_not_empty(self) -> None:
        assert len(ALL_NEWS_FEEDS) > 0

    def test_domestic_feeds_count(self) -> None:
        assert len(KR_NEWS_FEEDS) >= 10

    def test_global_feeds_count(self) -> None:
        assert len(GLOBAL_NEWS_FEEDS) >= 10

    def test_all_feeds_have_required_keys(self) -> None:
        for feed in ALL_NEWS_FEEDS:
            assert "url" in feed, f"Feed missing 'url': {feed}"
            assert "name" in feed, f"Feed missing 'name': {feed}"
            assert "category" in feed, f"Feed missing 'category': {feed}"
            assert "locale" in feed, f"Feed missing 'locale': {feed}"

    def test_all_feeds_have_valid_urls(self) -> None:
        for feed in ALL_NEWS_FEEDS:
            url = feed["url"]
            assert url.startswith("http"), f"Invalid URL: {url}"

    def test_community_feeds_exist(self) -> None:
        assert len(COMMUNITY_FEEDS) > 0

    def test_reddit_subreddits_exist(self) -> None:
        assert len(REDDIT_SUBREDDITS) > 0
        assert "worldnews" in REDDIT_SUBREDDITS

    def test_nitter_instances_exist(self) -> None:
        assert len(NITTER_INSTANCES) > 0
