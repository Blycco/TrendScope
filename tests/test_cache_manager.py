"""Tests for processor/shared/cache_manager.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from backend.processor.shared import cache_manager


@pytest.fixture(autouse=True)
def reset_redis_pool() -> None:
    """Reset global pool state before each test."""
    cache_manager._redis_pool = None
    yield
    cache_manager._redis_pool = None


def test_get_redis_raises_when_not_initialized() -> None:
    with pytest.raises(RuntimeError, match="not initialized"):
        cache_manager.get_redis()


@pytest.mark.asyncio
async def test_init_redis() -> None:
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    with patch("backend.processor.shared.cache_manager.aioredis.from_url", return_value=mock_redis):
        await cache_manager.init_redis("redis://:secret@localhost:6379")

    assert cache_manager._redis_pool is mock_redis


@pytest.mark.asyncio
async def test_close_redis() -> None:
    mock_redis = AsyncMock()
    cache_manager._redis_pool = mock_redis
    await cache_manager.close_redis()
    mock_redis.aclose.assert_awaited_once()
    assert cache_manager._redis_pool is None


@pytest.mark.asyncio
async def test_get_cached_hit() -> None:
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=b"cached_value")
    cache_manager._redis_pool = mock_redis

    result = await cache_manager.get_cached("test_key")
    assert result == b"cached_value"


@pytest.mark.asyncio
async def test_get_cached_miss() -> None:
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    cache_manager._redis_pool = mock_redis

    result = await cache_manager.get_cached("test_key")
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_error_returns_none() -> None:
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=Exception("connection error"))
    cache_manager._redis_pool = mock_redis

    result = await cache_manager.get_cached("test_key")
    assert result is None


@pytest.mark.asyncio
async def test_set_cached() -> None:
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    cache_manager._redis_pool = mock_redis

    await cache_manager.set_cached("key", b"value", 60)
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_cached_string_input() -> None:
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    cache_manager._redis_pool = mock_redis

    await cache_manager.set_cached("key", "string_value", 60)
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_cached_error_is_silent() -> None:
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock(side_effect=Exception("redis error"))
    cache_manager._redis_pool = mock_redis

    # Should not raise
    await cache_manager.set_cached("key", b"value", 60)


@pytest.mark.asyncio
async def test_delete_cached() -> None:
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock()
    cache_manager._redis_pool = mock_redis

    await cache_manager.delete_cached("key")
    mock_redis.delete.assert_awaited_once_with("key")


@pytest.mark.asyncio
async def test_delete_cached_error_is_silent() -> None:
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock(side_effect=Exception("redis error"))
    cache_manager._redis_pool = mock_redis

    await cache_manager.delete_cached("key")


@pytest.mark.asyncio
async def test_acquire_lock_success() -> None:
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    cache_manager._redis_pool = mock_redis

    result = await cache_manager.acquire_lock("my_key")
    assert result is True


@pytest.mark.asyncio
async def test_acquire_lock_already_held() -> None:
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=None)
    cache_manager._redis_pool = mock_redis

    result = await cache_manager.acquire_lock("my_key")
    assert result is False


@pytest.mark.asyncio
async def test_acquire_lock_error_returns_false() -> None:
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(side_effect=Exception("redis error"))
    cache_manager._redis_pool = mock_redis

    result = await cache_manager.acquire_lock("my_key")
    assert result is False


@pytest.mark.asyncio
async def test_release_lock() -> None:
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock()
    cache_manager._redis_pool = mock_redis

    await cache_manager.release_lock("my_key")
    mock_redis.delete.assert_awaited_once_with("lock:my_key")


@pytest.mark.asyncio
async def test_get_or_compute_cache_hit() -> None:
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=b"cached")
    cache_manager._redis_pool = mock_redis

    compute_fn = AsyncMock(return_value=b"computed")
    result = await cache_manager.get_or_compute("key", compute_fn, 60)
    assert result == b"cached"
    compute_fn.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_or_compute_cache_miss_with_lock() -> None:
    mock_redis = AsyncMock()
    call_count = 0

    async def mock_get(key: str) -> bytes | None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return None  # cache miss on first get
        return None

    mock_redis.get = mock_get
    mock_redis.set = AsyncMock(return_value=True)  # lock acquired
    mock_redis.setex = AsyncMock()
    mock_redis.delete = AsyncMock()
    cache_manager._redis_pool = mock_redis

    compute_fn = AsyncMock(return_value=b"fresh_value")
    result = await cache_manager.get_or_compute("key", compute_fn, 60)
    assert result == b"fresh_value"
