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
    """Uncompressed value stored with new prefix is returned without prefix."""
    mock_redis = AsyncMock()
    # Simulate a value written by the new set_cached (uncompressed prefix b'\x00')
    mock_redis.get = AsyncMock(return_value=b"\x00cached_value")
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
    # Prefixed uncompressed value
    mock_redis.get = AsyncMock(return_value=b"\x00cached")
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


# --- Compression / decompression round-trip tests ---


def test_decompress_value_uncompressed_prefix() -> None:
    """Values stored with \\x00 prefix are returned without the prefix."""
    raw = b"\x00hello world"
    assert cache_manager._decompress_value(raw) == b"hello world"


def test_decompress_value_compressed_prefix() -> None:
    """Values stored with \\x01 prefix are decompressed correctly."""
    original = b"hello world" * 200
    compressed = cache_manager._PREFIX_COMPRESSED + __import__("zlib").compress(original)
    assert cache_manager._decompress_value(compressed) == original


def test_decompress_value_legacy_zlib() -> None:
    """Legacy values (no prefix, raw zlib) are detected and decompressed."""
    import zlib

    original = b"legacy data" * 200
    raw = zlib.compress(original)  # starts with \x78\x9c or similar
    assert cache_manager._decompress_value(raw) == original


def test_decompress_value_legacy_plain() -> None:
    """Legacy values that are neither prefixed nor zlib are returned as-is."""
    raw = b"plain old bytes"
    assert cache_manager._decompress_value(raw) == raw


def test_decompress_value_empty() -> None:
    assert cache_manager._decompress_value(b"") == b""


@pytest.mark.asyncio
async def test_set_cached_small_value_stores_uncompressed_prefix() -> None:
    """Small values are stored with \\x00 prefix (no compression)."""
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    cache_manager._redis_pool = mock_redis

    payload = b"small"
    await cache_manager.set_cached("k", payload, 60)

    args = mock_redis.setex.call_args[0]
    stored: bytes = args[2]
    assert stored[:1] == b"\x00"
    assert stored[1:] == payload


@pytest.mark.asyncio
async def test_set_cached_large_value_stores_compressed_prefix() -> None:
    """Values over threshold are stored with \\x01 prefix and zlib-compressed."""
    import zlib

    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    cache_manager._redis_pool = mock_redis

    payload = b"x" * 2000  # exceeds DEFAULT_COMPRESS_THRESHOLD
    await cache_manager.set_cached("k", payload, 60)

    args = mock_redis.setex.call_args[0]
    stored: bytes = args[2]
    assert stored[:1] == b"\x01"
    assert zlib.decompress(stored[1:]) == payload


@pytest.mark.asyncio
async def test_get_cached_decompresses_compressed_value() -> None:
    """get_cached() transparently decompresses a \\x01-prefixed value."""
    import zlib

    original = b"important json data" * 100
    compressed_stored = b"\x01" + zlib.compress(original)

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=compressed_stored)
    cache_manager._redis_pool = mock_redis

    result = await cache_manager.get_cached("k")
    assert result == original


@pytest.mark.asyncio
async def test_set_get_round_trip_large_value() -> None:
    """set_cached then get_cached returns the original bytes for large values."""
    stored_value: bytes | None = None

    mock_redis = AsyncMock()

    async def fake_setex(key: str, ttl: int, value: bytes) -> None:
        nonlocal stored_value
        stored_value = value

    async def fake_get(key: str) -> bytes | None:
        return stored_value

    mock_redis.setex = fake_setex
    mock_redis.get = fake_get
    cache_manager._redis_pool = mock_redis

    original = b"round trip test data" * 200  # > 1024 bytes
    await cache_manager.set_cached("k", original, 60)
    result = await cache_manager.get_cached("k")
    assert result == original
