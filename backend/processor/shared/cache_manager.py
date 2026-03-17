"""Redis cache manager with stampede prevention. (RULE 18: aggressive caching)"""

from __future__ import annotations

import zlib
from typing import Any

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger(__name__)

_redis_pool: aioredis.Redis | None = None

LOCK_TTL_SECONDS = 30
DEFAULT_COMPRESS_THRESHOLD = 1024  # bytes


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


def get_redis() -> aioredis.Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis pool not initialized. Call init_redis() first.")
    return _redis_pool


async def get_cached(key: str) -> bytes | None:
    """Return cached bytes for key, or None on miss / error."""
    try:
        value = await get_redis().get(key)
        return value
    except Exception as exc:
        logger.warning("cache_get_failed", key=key, error=str(exc))
        return None


async def set_cached(key: str, value: bytes | str, ttl: int) -> None:
    """Set key with TTL. Compresses values larger than threshold."""
    try:
        data = value if isinstance(value, bytes) else value.encode()
        if len(data) > DEFAULT_COMPRESS_THRESHOLD:
            data = zlib.compress(data)
        await get_redis().setex(key, ttl, data)
    except Exception as exc:
        logger.warning("cache_set_failed", key=key, error=str(exc))


async def delete_cached(key: str) -> None:
    """Delete a cache key."""
    try:
        await get_redis().delete(key)
    except Exception as exc:
        logger.warning("cache_delete_failed", key=key, error=str(exc))


async def acquire_lock(lock_key: str) -> bool:
    """Acquire a SETNX lock for stampede prevention.

    Returns True if lock was acquired, False if already held.
    """
    try:
        result = await get_redis().set(
            f"lock:{lock_key}", "1", nx=True, ex=LOCK_TTL_SECONDS
        )
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
    compute_fn: Any,
    ttl: int,
    *,
    stale_on_lock: bool = True,
) -> Any:
    """Cache-aside with stampede prevention.

    On cache miss: acquires lock, computes, stores, releases lock.
    On lock failure with stale_on_lock=True: returns stale value if present.
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
