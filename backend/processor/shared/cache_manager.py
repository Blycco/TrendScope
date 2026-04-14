"""Redis cache manager with stampede prevention. (RULE 18: aggressive caching)"""

from __future__ import annotations

import zlib
from collections.abc import Awaitable, Callable

import redis.asyncio as aioredis
import structlog

from backend.common.metrics import CACHE_REQUESTS

logger = structlog.get_logger(__name__)

_redis_pool: aioredis.Redis | None = None

LOCK_TTL_SECONDS = 30
DEFAULT_COMPRESS_THRESHOLD = 1024  # bytes

# 1-byte prefix constants for compression marker
_PREFIX_COMPRESSED: bytes = b"\x01"
_PREFIX_UNCOMPRESSED: bytes = b"\x00"
# zlib magic bytes for backwards-compatibility detection (no prefix)
_ZLIB_MAGIC: tuple[bytes, ...] = (b"\x78\x01", b"\x78\x9c", b"\x78\xda")


async def init_redis(redis_url: str) -> None:
    """Initialize the global Redis connection pool."""
    global _redis_pool
    _redis_pool = aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=False,
        max_connections=20,
    )
    await _redis_pool.ping()
    logger.info("redis_pool_initialized", url=redis_url.split("@")[-1])


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


# --- Pub/sub pool (separate connection: subscribe state is incompatible with commands) ---

_pubsub_redis: aioredis.Redis | None = None


async def init_pubsub(redis_url: str) -> None:
    """Initialize separate Redis client for pub/sub operations."""
    global _pubsub_redis
    try:
        _pubsub_redis = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=10,
        )
        await _pubsub_redis.ping()
        logger.info("redis_pubsub_initialized")
    except Exception as exc:
        logger.error("redis_pubsub_init_failed", error=str(exc))
        raise


async def close_pubsub() -> None:
    """Close the pub/sub Redis client."""
    global _pubsub_redis
    if _pubsub_redis:
        try:
            await _pubsub_redis.aclose()
        except Exception as exc:
            logger.warning("redis_pubsub_close_error", error=str(exc))
        _pubsub_redis = None
    logger.info("redis_pubsub_closed")


def get_pubsub_redis() -> aioredis.Redis:
    """Return the pub/sub Redis client. Raises RuntimeError if not initialized."""
    if _pubsub_redis is None:
        raise RuntimeError("PubSub Redis not initialized. Call init_pubsub() first.")
    return _pubsub_redis


async def publish(channel: str, message: str) -> None:
    """Publish a message to a Redis channel. Skips silently if not initialized."""
    if _pubsub_redis is None:
        logger.debug("redis_publish_skipped_not_initialized", channel=channel)
        return
    try:
        await _pubsub_redis.publish(channel, message)
        logger.debug("redis_published", channel=channel)
    except Exception as exc:
        logger.warning("redis_publish_failed", channel=channel, error=str(exc))


def get_redis() -> aioredis.Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis pool not initialized. Call init_redis() first.")
    return _redis_pool


def _decompress_value(raw: bytes) -> bytes:
    """Decode a stored cache value, handling prefix and legacy formats.

    Format (new):
      b'\\x01' + zlib.compress(data)  — compressed
      b'\\x00' + data                 — uncompressed

    Format (legacy, no prefix):
      Detect zlib magic bytes and decompress; otherwise return as-is.
    """
    if len(raw) < 1:
        return raw

    first = raw[:1]

    if first == _PREFIX_COMPRESSED:
        return zlib.decompress(raw[1:])

    if first == _PREFIX_UNCOMPRESSED:
        return raw[1:]

    # Backwards-compatibility: data written before the prefix scheme
    if raw[:2] in _ZLIB_MAGIC:
        try:
            return zlib.decompress(raw)
        except zlib.error:
            logger.warning("cache_decompress_legacy_failed_returning_raw")
            return raw

    return raw


async def get_cached(key: str) -> bytes | None:
    """Return cached bytes for key, or None on miss / error.

    Transparently decompresses values stored with set_cached().
    """
    try:
        raw = await get_redis().get(key)
        CACHE_REQUESTS.labels(result="hit" if raw is not None else "miss").inc()
        if raw is None:
            return None
        return _decompress_value(raw)
    except Exception as exc:
        CACHE_REQUESTS.labels(result="miss").inc()
        logger.warning("cache_get_failed", key=key, error=str(exc))
        return None


async def set_cached(key: str, value: bytes | str, ttl: int) -> None:
    """Set key with TTL.

    Compresses values larger than threshold and prepends a 1-byte prefix
    so get_cached() can reliably decompress on retrieval.
    """
    try:
        data = value if isinstance(value, bytes) else value.encode()
        if len(data) > DEFAULT_COMPRESS_THRESHOLD:
            stored = _PREFIX_COMPRESSED + zlib.compress(data)
        else:
            stored = _PREFIX_UNCOMPRESSED + data
        await get_redis().setex(key, ttl, stored)
    except Exception as exc:
        logger.warning("cache_set_failed", key=key, error=str(exc))


async def delete_cached(key: str) -> None:
    """Delete a cache key."""
    try:
        await get_redis().delete(key)
    except Exception as exc:
        logger.warning("cache_delete_failed", key=key, error=str(exc))


async def delete_keys_by_pattern(pattern: str, *, batch_size: int = 200) -> int:
    """Scan Redis for keys matching `pattern` and delete them. Returns count."""
    try:
        client = get_redis()
        deleted = 0
        batch: list[bytes] = []
        async for key in client.scan_iter(match=pattern, count=batch_size):
            batch.append(key)
            if len(batch) >= batch_size:
                deleted += await client.delete(*batch)
                batch.clear()
        if batch:
            deleted += await client.delete(*batch)
        logger.info("cache_delete_by_pattern", pattern=pattern, deleted=deleted)
        return deleted
    except Exception as exc:
        logger.warning("cache_delete_by_pattern_failed", pattern=pattern, error=str(exc))
        return 0


async def invalidate_feed_cache() -> int:
    """Delete all `feed:*` cache entries. Returns number of keys deleted."""
    return await delete_keys_by_pattern("feed:*")


async def acquire_lock(lock_key: str) -> bool:
    """Acquire a SETNX lock for stampede prevention.

    Returns True if lock was acquired, False if already held.
    """
    try:
        result = await get_redis().set(f"lock:{lock_key}", "1", nx=True, ex=LOCK_TTL_SECONDS)
        return result is not None
    except Exception as exc:
        logger.warning("cache_lock_acquire_failed", lock_key=lock_key, error=str(exc))
        return False


async def release_lock(lock_key: str) -> None:
    """Release a stampede prevention lock."""
    try:
        await get_redis().delete(f"lock:{lock_key}")
    except Exception as exc:
        logger.warning("cache_lock_release_failed", lock_key=lock_key, error=str(exc))


async def get_or_compute(
    key: str,
    compute_fn: Callable[[], Awaitable[bytes | None]],
    ttl: int,
    *,
    stale_on_lock: bool = True,
) -> bytes | None:
    """Cache-aside with stampede prevention.

    On cache miss: acquires lock, computes, stores, releases lock.
    On lock failure with stale_on_lock=True: returns stale value if present.

    get_cached() transparently decompresses, so callers always receive
    plain bytes regardless of whether the value was compressed at write time.
    """
    cached = await get_cached(key)
    if cached is not None:
        return cached

    if not await acquire_lock(key):
        if stale_on_lock:
            stale = await get_cached(f"stale:{key}")
            if stale:
                logger.info("cache_returning_stale", key=key)
                return stale
        return None

    try:
        result = await compute_fn()
        if result is not None:
            encoded = result if isinstance(result, bytes) else str(result).encode()
            await set_cached(key, encoded, ttl)
            await set_cached(f"stale:{key}", encoded, ttl * 2)
        return result
    except Exception as exc:
        logger.error("cache_compute_failed", key=key, error=str(exc))
        raise
    finally:
        await release_lock(key)
