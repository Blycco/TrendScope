"""Tests for cross-platform verification module."""

from __future__ import annotations

from backend.processor.algorithms.cross_platform import verify_cross_platform


class TestVerifyCrossPlatform:
    """Tests for verify_cross_platform."""

    def test_empty_articles_returns_1(self) -> None:
        assert verify_cross_platform([]) == 1.0

    def test_single_source_returns_1(self) -> None:
        articles = [{"source": "rss_ko", "title": "A"}]
        assert verify_cross_platform(articles) == 1.0

    def test_all_same_source_returns_1(self) -> None:
        articles = [
            {"source": "rss_ko", "title": "A"},
            {"source": "rss_ko", "title": "B"},
            {"source": "rss_ko", "title": "C"},
        ]
        assert verify_cross_platform(articles) == 1.0

    def test_two_sources_returns_1_1(self) -> None:
        articles = [
            {"source": "rss_ko", "title": "A"},
            {"source": "rss_en", "title": "B"},
        ]
        assert verify_cross_platform(articles) == 1.1

    def test_three_sources_returns_1_2(self) -> None:
        articles = [
            {"source": "rss_ko"},
            {"source": "rss_en"},
            {"source": "dc_inside"},
        ]
        assert verify_cross_platform(articles) == 1.2

    def test_four_sources_returns_1_3(self) -> None:
        articles = [
            {"source": "rss_ko"},
            {"source": "rss_en"},
            {"source": "dc_inside"},
            {"source": "fm_korea"},
        ]
        assert verify_cross_platform(articles) == 1.3

    def test_five_plus_sources_returns_1_5(self) -> None:
        articles = [
            {"source": "rss_ko"},
            {"source": "rss_en"},
            {"source": "dc_inside"},
            {"source": "fm_korea"},
            {"source": "burst_gnews"},
        ]
        assert verify_cross_platform(articles) == 1.5

    def test_six_sources_still_1_5(self) -> None:
        articles = [
            {"source": "rss_ko"},
            {"source": "rss_en"},
            {"source": "dc_inside"},
            {"source": "fm_korea"},
            {"source": "burst_gnews"},
            {"source": "burst_reddit"},
        ]
        assert verify_cross_platform(articles) == 1.5

    def test_missing_source_field_ignored(self) -> None:
        articles = [
            {"title": "no source"},
            {"source": "rss_ko"},
        ]
        assert verify_cross_platform(articles) == 1.0

    def test_none_source_ignored(self) -> None:
        articles = [
            {"source": None},
            {"source": "rss_ko"},
        ]
        assert verify_cross_platform(articles) == 1.0

    def test_empty_source_ignored(self) -> None:
        articles = [
            {"source": ""},
            {"source": "rss_ko"},
        ]
        assert verify_cross_platform(articles) == 1.0

    def test_duplicates_counted_once(self) -> None:
        articles = [
            {"source": "rss_ko"},
            {"source": "rss_ko"},
            {"source": "rss_en"},
            {"source": "rss_en"},
        ]
        assert verify_cross_platform(articles) == 1.1
