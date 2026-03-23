"""Tests for custom Prometheus metrics instrumentation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from backend.common.metrics import (
    AI_API_REQUESTS,
    CACHE_REQUESTS,
    CRAWLER_REQUESTS,
    PAYMENT_FAILURES,
    SOURCE_QUOTA_RATIO,
)


class TestCacheMetrics:
    """Cache hit/miss metric tests."""

    @pytest.mark.asyncio
    async def test_cache_hit_increments_metric(self) -> None:
        from backend.processor.shared.cache_manager import get_cached

        before = CACHE_REQUESTS.labels(result="hit")._value.get()
        with patch("backend.processor.shared.cache_manager.get_redis") as mock_redis:
            mock_redis.return_value.get = AsyncMock(return_value=b"data")
            await get_cached("test_key")
        after = CACHE_REQUESTS.labels(result="hit")._value.get()
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_cache_miss_increments_metric(self) -> None:
        from backend.processor.shared.cache_manager import get_cached

        before = CACHE_REQUESTS.labels(result="miss")._value.get()
        with patch("backend.processor.shared.cache_manager.get_redis") as mock_redis:
            mock_redis.return_value.get = AsyncMock(return_value=None)
            await get_cached("missing_key")
        after = CACHE_REQUESTS.labels(result="miss")._value.get()
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_cache_error_increments_miss(self) -> None:
        from backend.processor.shared.cache_manager import get_cached

        before = CACHE_REQUESTS.labels(result="miss")._value.get()
        with patch("backend.processor.shared.cache_manager.get_redis") as mock_redis:
            mock_redis.return_value.get = AsyncMock(side_effect=Exception("conn error"))
            await get_cached("error_key")
        after = CACHE_REQUESTS.labels(result="miss")._value.get()
        assert after == before + 1


class TestCrawlerMetrics:
    """Crawler success/failure metric tests."""

    def test_crawler_counter_labels(self) -> None:
        before = CRAWLER_REQUESTS.labels(source="test_src", result="success")._value.get()
        CRAWLER_REQUESTS.labels(source="test_src", result="success").inc()
        after = CRAWLER_REQUESTS.labels(source="test_src", result="success")._value.get()
        assert after == before + 1

    def test_crawler_failure_counter(self) -> None:
        before = CRAWLER_REQUESTS.labels(source="test_src", result="failure")._value.get()
        CRAWLER_REQUESTS.labels(source="test_src", result="failure").inc()
        after = CRAWLER_REQUESTS.labels(source="test_src", result="failure")._value.get()
        assert after == before + 1


class TestAIAPIMetrics:
    """AI API request metric tests."""

    def test_ai_api_success_counter(self) -> None:
        before = AI_API_REQUESTS.labels(provider="gemini", result="success")._value.get()
        AI_API_REQUESTS.labels(provider="gemini", result="success").inc()
        after = AI_API_REQUESTS.labels(provider="gemini", result="success")._value.get()
        assert after == before + 1

    def test_ai_api_failure_counter(self) -> None:
        before = AI_API_REQUESTS.labels(provider="openai", result="failure")._value.get()
        AI_API_REQUESTS.labels(provider="openai", result="failure").inc()
        after = AI_API_REQUESTS.labels(provider="openai", result="failure")._value.get()
        assert after == before + 1


class TestPaymentMetrics:
    """Payment failure metric tests."""

    def test_payment_failure_counter(self) -> None:
        before = PAYMENT_FAILURES._value.get()
        PAYMENT_FAILURES.inc()
        after = PAYMENT_FAILURES._value.get()
        assert after == before + 1


class TestQuotaMetrics:
    """Source quota ratio metric tests."""

    def test_quota_ratio_gauge(self) -> None:
        SOURCE_QUOTA_RATIO.labels(source="rss_ko").set(0.85)
        assert SOURCE_QUOTA_RATIO.labels(source="rss_ko")._value.get() == 0.85

    @pytest.mark.asyncio
    async def test_check_quota_sets_ratio(self) -> None:
        from backend.crawler.quota_guard import check_quota

        mock_pool = AsyncMock()
        mock_pool.fetchrow = AsyncMock(
            return_value={"is_active": True, "quota_limit": 100, "quota_used": 75}
        )
        result = await check_quota("test_source", mock_pool)
        assert result is True
        assert SOURCE_QUOTA_RATIO.labels(source="test_source")._value.get() == 0.75
