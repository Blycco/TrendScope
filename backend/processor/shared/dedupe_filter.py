"""3-stage deduplication filter: Bloom Filter → Redis SET → content fingerprint.

Pipeline spec: DedupeFilter (Bloom Filter FP 0.1% + Redis SET 3-stage)
"""

from __future__ import annotations

import hashlib
import math
from typing import TYPE_CHECKING

import structlog

from backend.processor.shared.cache_manager import get_redis

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = structlog.get_logger(__name__)

# --- Bloom Filter (in-memory, stage 1) ---

_BLOOM_FP_RATE: float = 0.001  # 0.1%
_BLOOM_EXPECTED_ITEMS: int = 500_000

# Redis keys
_REDIS_URL_SET_KEY: str = "dedupe:url_hash"
_REDIS_FP_SET_KEY: str = "dedupe:content_fp"
_REDIS_SET_TTL: int = 86400 * 7  # 7 days


def _optimal_bloom_size(n: int, p: float) -> tuple[int, int]:
    """Calculate optimal bit array size (m) and hash count (k)."""
    m = int(-n * math.log(p) / (math.log(2) ** 2))
    k = int((m / n) * math.log(2))
    return m, max(k, 1)


class BloomFilter:
    """Simple in-memory Bloom filter for fast pre-check."""

    __slots__ = ("_bit_array", "_size", "_hash_count")

    def __init__(
        self,
        expected_items: int = _BLOOM_EXPECTED_ITEMS,
        fp_rate: float = _BLOOM_FP_RATE,
    ) -> None:
        self._size, self._hash_count = _optimal_bloom_size(expected_items, fp_rate)
        self._bit_array: bytearray = bytearray(self._size // 8 + 1)

    def _get_hashes(self, item: str) -> list[int]:
        h1 = int(hashlib.md5(item.encode()).hexdigest(), 16)  # noqa: S324
        h2 = int(hashlib.sha1(item.encode()).hexdigest(), 16)  # noqa: S324
        return [(h1 + i * h2) % self._size for i in range(self._hash_count)]

    def add(self, item: str) -> None:
        """Add an item to the Bloom filter."""
        for pos in self._get_hashes(item):
            byte_idx, bit_idx = divmod(pos, 8)
            self._bit_array[byte_idx] |= 1 << bit_idx

    def might_contain(self, item: str) -> bool:
        """Check if item might be in the set (false positives possible)."""
        for pos in self._get_hashes(item):
            byte_idx, bit_idx = divmod(pos, 8)
            if not (self._bit_array[byte_idx] & (1 << bit_idx)):
                return False
        return True

    @property
    def size_bytes(self) -> int:
        """Return memory usage of the bit array."""
        return len(self._bit_array)


# Module-level singleton
_bloom: BloomFilter | None = None


def get_bloom() -> BloomFilter:
    """Get or create the module-level Bloom filter singleton."""
    global _bloom
    if _bloom is None:
        _bloom = BloomFilter()
    return _bloom


def reset_bloom() -> None:
    """Reset the Bloom filter (e.g., on daily rotation)."""
    global _bloom
    _bloom = BloomFilter()
    logger.info("bloom_filter_reset")


def compute_url_hash(url: str) -> str:
    """SHA-256[:16] of URL for dedup (matches news_article.url_hash schema)."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def compute_content_fingerprint(title: str, body: str) -> str:
    """SHA-256[:16] of title+body[:200] (matches news_article.content_fp schema)."""
    content = title + body[:200]
    return hashlib.sha256(content.encode()).hexdigest()[:16]


async def is_duplicate(
    url: str,
    title: str = "",
    body: str = "",
) -> bool:
    """3-stage duplicate check.

    Stage 1: Bloom filter (in-memory, fast reject)
    Stage 2: Redis URL hash SET (authoritative URL check)
    Stage 3: Redis content fingerprint SET (near-duplicate body check)

    Returns True if the item is a duplicate.
    """
    url_hash = compute_url_hash(url)
    bloom = get_bloom()

    try:
        # Stage 1: Bloom filter pre-check
        if not bloom.might_contain(url_hash):
            bloom.add(url_hash)
            # Not in bloom → definitely new (bloom has no false negatives)
            # Still register in Redis for persistence
            await _register_in_redis(url_hash, title, body)
            return False

        # Stage 2: Bloom says maybe → check Redis URL set
        redis: aioredis.Redis = get_redis()
        url_exists = await redis.sismember(_REDIS_URL_SET_KEY, url_hash)
        if url_exists:
            logger.debug("dedupe_url_hit", url_hash=url_hash)
            return True

        # Stage 3: Content fingerprint check (near-duplicate)
        if title or body:
            fp = compute_content_fingerprint(title, body)
            fp_exists = await redis.sismember(_REDIS_FP_SET_KEY, fp)
            if fp_exists:
                logger.debug("dedupe_content_fp_hit", fingerprint=fp)
                return True

        # Not a duplicate — register it
        bloom.add(url_hash)
        await _register_in_redis(url_hash, title, body)
        return False

    except Exception as exc:
        logger.error("dedupe_check_failed", url=url, error=str(exc))
        # On error, let the item through (prefer processing over dropping)
        return False


async def _register_in_redis(url_hash: str, title: str, body: str) -> None:
    """Register URL hash and content fingerprint in Redis SETs."""
    try:
        redis: aioredis.Redis = get_redis()
        pipe = redis.pipeline(transaction=False)
        pipe.sadd(_REDIS_URL_SET_KEY, url_hash)
        pipe.expire(_REDIS_URL_SET_KEY, _REDIS_SET_TTL)
        if title or body:
            fp = compute_content_fingerprint(title, body)
            pipe.sadd(_REDIS_FP_SET_KEY, fp)
            pipe.expire(_REDIS_FP_SET_KEY, _REDIS_SET_TTL)
        await pipe.execute()
    except Exception as exc:
        logger.warning("dedupe_register_failed", error=str(exc))
