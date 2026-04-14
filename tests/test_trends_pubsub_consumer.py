"""Tests for the `trends:new` pub/sub consumer and cache invalidation helpers."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.api.pubsub import trends_consumer
from backend.processor.shared import cache_manager


class TestDeleteKeysByPattern:
    @pytest.mark.asyncio
    async def test_scans_and_deletes(self) -> None:
        mock_redis = MagicMock()

        async def _scan_iter(match: str, count: int):  # noqa: ARG001
            for k in (b"feed:all:all", b"feed:it:ko", b"feed:general:en"):
                yield k

        mock_redis.scan_iter = _scan_iter
        mock_redis.delete = AsyncMock(return_value=3)

        with patch.object(cache_manager, "_redis_pool", mock_redis):
            deleted = await cache_manager.delete_keys_by_pattern("feed:*")

        assert deleted == 3
        mock_redis.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self) -> None:
        mock_redis = MagicMock()

        def _bad_scan(*_args: object, **_kwargs: object):
            raise RuntimeError("redis down")

        mock_redis.scan_iter = _bad_scan

        with patch.object(cache_manager, "_redis_pool", mock_redis):
            result = await cache_manager.delete_keys_by_pattern("feed:*")

        assert result == 0

    @pytest.mark.asyncio
    async def test_invalidate_feed_cache_uses_feed_prefix(self) -> None:
        with patch.object(
            cache_manager,
            "delete_keys_by_pattern",
            AsyncMock(return_value=5),
        ) as mock_delete:
            result = await cache_manager.invalidate_feed_cache()

        assert result == 5
        mock_delete.assert_awaited_once_with("feed:*")


class TestMatchKeywordAlerts:
    @pytest.mark.asyncio
    async def test_returns_empty_for_no_keywords(self) -> None:
        pool = MagicMock()
        result = await trends_consumer._match_keyword_alerts(pool, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_queries_with_lowered_keywords(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[{"id": "k1", "user_id": "u1", "keyword": "ChatGPT"}])
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_cm)

        rows = await trends_consumer._match_keyword_alerts(pool, ["ChatGPT", "AI"])

        conn.fetch.assert_awaited_once()
        _, args = conn.fetch.await_args
        # second positional argument is the lowered list
        assert conn.fetch.await_args.args[1] == ["chatgpt", "ai"]
        assert rows[0]["keyword"] == "ChatGPT"


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_logs_alert_and_invalidates(self) -> None:
        pool = MagicMock()
        detail = {
            "group": {"id": "g-1", "keywords": ["AI", "LLM"]},
            "articles": [],
        }
        with (
            patch.object(
                trends_consumer,
                "fetch_trend_detail",
                AsyncMock(return_value=detail),
            ),
            patch.object(
                trends_consumer,
                "_match_keyword_alerts",
                AsyncMock(return_value=[{"id": "k", "user_id": "u1", "keyword": "AI"}]),
            ),
            patch.object(
                trends_consumer,
                "invalidate_feed_cache",
                AsyncMock(return_value=2),
            ) as mock_invalidate,
            patch.object(trends_consumer.logger, "info") as mock_info,
        ):
            await trends_consumer._handle_message(pool, "g-1")

        mock_invalidate.assert_awaited_once()
        event_names = [call.args[0] for call in mock_info.call_args_list]
        assert "keyword_alert_triggered" in event_names

    @pytest.mark.asyncio
    async def test_skips_when_group_missing(self) -> None:
        pool = MagicMock()
        with (
            patch.object(
                trends_consumer,
                "fetch_trend_detail",
                AsyncMock(return_value=None),
            ),
            patch.object(trends_consumer, "invalidate_feed_cache", AsyncMock()) as mock_invalidate,
        ):
            await trends_consumer._handle_message(pool, "missing")

        mock_invalidate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_swallows_fetch_exception(self) -> None:
        pool = MagicMock()
        with (
            patch.object(
                trends_consumer,
                "fetch_trend_detail",
                AsyncMock(side_effect=RuntimeError("db down")),
            ),
            patch.object(trends_consumer, "invalidate_feed_cache", AsyncMock()) as mock_invalidate,
        ):
            # Must not raise
            await trends_consumer._handle_message(pool, "g-x")

        mock_invalidate.assert_not_awaited()


class TestRunTrendsConsumer:
    @pytest.mark.asyncio
    async def test_processes_message_and_cancels(self) -> None:
        """Consumer should call _handle_message for a real message then exit on cancel."""
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        call_count = {"n": 0}

        async def _get_message(*_args: object, **_kwargs: object) -> dict[str, object] | None:
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"type": "message", "data": "group-abc"}
            # subsequent calls block until cancelled
            await asyncio.sleep(3600)
            return None

        mock_pubsub.get_message = _get_message

        mock_redis = MagicMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

        pool = MagicMock()

        with (
            patch.object(trends_consumer, "get_pubsub_redis", return_value=mock_redis),
            patch.object(trends_consumer, "_handle_message", AsyncMock()) as mock_handle,
        ):
            task = asyncio.create_task(trends_consumer.run_trends_consumer(pool))
            # Let the consumer pick up the first message
            for _ in range(20):
                if mock_handle.await_count >= 1:
                    break
                await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        mock_handle.assert_awaited_with(pool, "group-abc")
        mock_pubsub.subscribe.assert_awaited_once_with("trends:new")

    @pytest.mark.asyncio
    async def test_ignores_malformed_payload(self) -> None:
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        seq = iter([{"type": "message", "data": ""}])

        async def _get_message(*_args: object, **_kwargs: object) -> dict[str, object] | None:
            try:
                return next(seq)
            except StopIteration:
                await asyncio.sleep(3600)
                return None

        mock_pubsub.get_message = _get_message
        mock_redis = MagicMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

        with (
            patch.object(trends_consumer, "get_pubsub_redis", return_value=mock_redis),
            patch.object(trends_consumer, "_handle_message", AsyncMock()) as mock_handle,
        ):
            task = asyncio.create_task(trends_consumer.run_trends_consumer(MagicMock()))
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        mock_handle.assert_not_awaited()
