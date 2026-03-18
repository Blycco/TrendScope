"""Redis-based ephemeral token store for email verification and password resets.

Uses the shared Redis pool from cache_manager. (RULE 01: env only, RULE 03: async)
"""

from __future__ import annotations

import structlog

from backend.processor.shared.cache_manager import get_redis

logger = structlog.get_logger(__name__)


async def save_auth_token(prefix: str, token: str, value: str, ttl_seconds: int) -> None:
    """Persist an auth token in Redis with a TTL.

    Key format: ``{prefix}:{token}``
    """
    try:
        redis = get_redis()
        key = f"{prefix}:{token}"
        await redis.setex(key, ttl_seconds, value.encode())
        logger.info("auth_token_saved", prefix=prefix)
    except Exception as exc:
        logger.error("auth_token_save_failed", prefix=prefix, error=str(exc))
        raise


async def get_auth_token(prefix: str, token: str) -> str | None:
    """Retrieve the value for a stored auth token, or None if expired / missing."""
    try:
        redis = get_redis()
        key = f"{prefix}:{token}"
        raw: bytes | None = await redis.get(key)
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else raw
    except Exception as exc:
        logger.error("auth_token_get_failed", prefix=prefix, error=str(exc))
        raise


async def delete_auth_token(prefix: str, token: str) -> None:
    """Remove an auth token (e.g. after successful verification)."""
    try:
        redis = get_redis()
        key = f"{prefix}:{token}"
        await redis.delete(key)
        logger.info("auth_token_deleted", prefix=prefix)
    except Exception as exc:
        logger.error("auth_token_delete_failed", prefix=prefix, error=str(exc))
        raise
