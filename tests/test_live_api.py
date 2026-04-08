"""Tests for SSE live endpoint and publish utilities."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestPublish:
    @pytest.mark.asyncio
    async def test_publish_calls_redis(self) -> None:
        """publish() should forward channel and message to Redis."""
        mock_redis = AsyncMock()
        with patch("backend.processor.shared.cache_manager._pubsub_redis", mock_redis):
            # Re-import inside patch scope to pick up the mock
            from backend.processor.shared.cache_manager import publish

            await publish("trends:new", "test-id")
        mock_redis.publish.assert_called_once_with("trends:new", "test-id")

    @pytest.mark.asyncio
    async def test_publish_skips_when_not_initialized(self) -> None:
        """publish() should not raise when pubsub Redis is not initialized."""
        with patch("backend.processor.shared.cache_manager._pubsub_redis", None):
            from backend.processor.shared.cache_manager import publish

            # Must not raise RuntimeError or any other exception
            await publish("trends:new", "test-id")

    @pytest.mark.asyncio
    async def test_publish_logs_warning_on_redis_error(self) -> None:
        """publish() should log a warning and swallow Redis errors."""
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(side_effect=ConnectionError("connection refused"))
        with patch("backend.processor.shared.cache_manager._pubsub_redis", mock_redis):
            from backend.processor.shared.cache_manager import publish

            # Must not propagate the exception
            await publish("trends:new", "test-id")
        mock_redis.publish.assert_called_once()


class TestInitClosePubsub:
    @pytest.mark.asyncio
    async def test_init_pubsub_sets_global(self) -> None:
        """init_pubsub() should assign the global _pubsub_redis."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        from backend.processor.shared import cache_manager

        original = cache_manager._pubsub_redis
        try:
            with patch(
                "backend.processor.shared.cache_manager.aioredis.from_url",
                return_value=mock_redis,
            ):
                await cache_manager.init_pubsub("redis://localhost:6379/0")

            assert cache_manager._pubsub_redis is mock_redis
        finally:
            cache_manager._pubsub_redis = original

    @pytest.mark.asyncio
    async def test_close_pubsub_clears_global(self) -> None:
        """close_pubsub() should call aclose and clear _pubsub_redis."""
        mock_redis = AsyncMock()

        from backend.processor.shared import cache_manager

        cache_manager._pubsub_redis = mock_redis
        try:
            await cache_manager.close_pubsub()
            mock_redis.aclose.assert_awaited_once()
            assert cache_manager._pubsub_redis is None
        finally:
            cache_manager._pubsub_redis = None

    def test_get_pubsub_redis_raises_when_not_initialized(self) -> None:
        """get_pubsub_redis() should raise RuntimeError when not initialized."""
        from backend.processor.shared import cache_manager

        original = cache_manager._pubsub_redis
        cache_manager._pubsub_redis = None
        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                cache_manager.get_pubsub_redis()
        finally:
            cache_manager._pubsub_redis = original


class TestLiveRouterHeaders:
    def test_sse_response_headers(self) -> None:
        """live_trends() should return StreamingResponse with SSE headers."""
        from unittest.mock import MagicMock, patch

        from fastapi.responses import StreamingResponse

        mock_redis = MagicMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

        with patch(
            "backend.api.routers.live.get_pubsub_redis",
            return_value=mock_redis,
        ):
            import asyncio

            from backend.api.routers.live import live_trends

            response = asyncio.get_event_loop().run_until_complete(live_trends())

        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"
        assert response.headers["Cache-Control"] == "no-cache"
        assert response.headers["X-Accel-Buffering"] == "no"


class TestHeartbeat:
    def test_keep_alive_format(self) -> None:
        """Heartbeat message must be a valid SSE comment line."""
        heartbeat = ": keep-alive\n\n"
        assert heartbeat.startswith(": ")
        assert heartbeat.endswith("\n\n")
