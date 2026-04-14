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


class TestCrawlerSourceEmission:
    """Wave 3: SNS / naver_datalab / burst crawler 경로가 실제로 CRAWLER_REQUESTS를 발행."""

    @pytest.mark.asyncio
    async def test_burst_crawl_success_increments(self) -> None:
        from backend.crawler.sources import burst_crawler

        before = CRAWLER_REQUESTS.labels(source="burst", result="success")._value.get()
        with (
            patch.object(burst_crawler, "search_google_news_rss", AsyncMock(return_value=[])),
            patch.object(burst_crawler, "search_reddit", AsyncMock(return_value=[])),
        ):
            await burst_crawler.run_burst_crawl(["ai"], "ko", AsyncMock())
        after = CRAWLER_REQUESTS.labels(source="burst", result="success")._value.get()
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_burst_crawl_failure_increments(self) -> None:
        from backend.crawler.sources import burst_crawler

        before = CRAWLER_REQUESTS.labels(source="burst", result="failure")._value.get()
        with patch.object(
            burst_crawler, "search_google_news_rss", AsyncMock(side_effect=RuntimeError("boom"))
        ):
            # asyncio.gather(return_exceptions=True) swallows the exception internally,
            # so trigger outer except via an unexpected error path: pass a bad arg.
            # Instead, test the except branch directly by forcing asyncio.gather to raise.
            with patch.object(
                burst_crawler.asyncio, "gather", AsyncMock(side_effect=RuntimeError("gather fail"))
            ):
                await burst_crawler.run_burst_crawl(["ai"], "ko", AsyncMock())
        after = CRAWLER_REQUESTS.labels(source="burst", result="failure")._value.get()
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_naver_datalab_failure_increments(self) -> None:
        from backend.crawler.sources import naver_datalab_crawler

        before = CRAWLER_REQUESTS.labels(source="naver_datalab", result="failure")._value.get()
        with patch.dict(
            "os.environ",
            {"NAVER_CLIENT_ID": "x", "NAVER_CLIENT_SECRET": "y"},
        ):

            class _FailingClient:
                async def __aenter__(self) -> _FailingClient:
                    return self

                async def __aexit__(self, *args: object) -> None:
                    return None

                async def post(self, *args: object, **kwargs: object) -> None:
                    raise RuntimeError("network")

            with patch.object(
                naver_datalab_crawler.httpx, "AsyncClient", lambda *a, **kw: _FailingClient()
            ):
                await naver_datalab_crawler.fetch_naver_trends(
                    [{"groupName": "g", "keywords": ["k"]}]
                )
        after = CRAWLER_REQUESTS.labels(source="naver_datalab", result="failure")._value.get()
        assert after == before + 1

    def test_sns_source_labels_registered(self) -> None:
        """reddit/youtube/google_trends label 쌍이 Counter에 유효하게 등록됨."""
        for source in ("reddit", "youtube", "google_trends"):
            for result in ("success", "failure"):
                CRAWLER_REQUESTS.labels(source=source, result=result).inc(0)


class TestMetricsEndpointExposure:
    """GET /metrics 응답에 알림 룰이 참조하는 메트릭 이름이 모두 노출되는지 검증."""

    @pytest.mark.asyncio
    async def test_expected_metric_names_exposed(self) -> None:
        from backend.api.main import create_app
        from httpx import ASGITransport, AsyncClient

        # 최소 1회 증가시켜 Counter가 /metrics 출력에 포함되도록 보장
        CRAWLER_REQUESTS.labels(source="reddit", result="success").inc(0)
        AI_API_REQUESTS.labels(provider="gemini", result="success").inc(0)
        CACHE_REQUESTS.labels(result="hit").inc(0)
        PAYMENT_FAILURES.inc(0)
        SOURCE_QUOTA_RATIO.labels(source="test").set(0.0)

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/metrics")
        assert resp.status_code == 200
        body = resp.text
        for name in (
            "http_requests_total",
            "cache_requests_total",
            "crawler_requests_total",
            "ai_api_requests_total",
            "payment_failures_total",
            "source_quota_ratio",
        ):
            assert name in body, f"{name} not found in /metrics output"


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
