"""DB queries for user_personalization table. (RULE 02: asyncpg $1,$2 parameterization)"""

from __future__ import annotations

import json

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def get_personalization(
    pool: asyncpg.Pool,
    user_id: str,
) -> asyncpg.Record | None:
    """Fetch personalization settings for a user.

    Args:
        pool:    Active asyncpg connection pool.
        user_id: UUID of the user.

    Returns:
        Record with category_weights and locale_ratio, or None if not found.
    """
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT category_weights, locale_ratio, updated_at "
                "FROM user_personalization WHERE user_id = $1",
                user_id,
            )
    except Exception as exc:
        logger.error("get_personalization_failed", user_id=user_id, error=str(exc))
        raise


async def upsert_personalization(
    pool: asyncpg.Pool,
    user_id: str,
    category_weights: dict,
    locale_ratio: float,
) -> None:
    """Insert or update personalization settings for a user.

    Args:
        pool:             Active asyncpg connection pool.
        user_id:          UUID of the user.
        category_weights: Dict mapping category names to weight floats.
        locale_ratio:     Locale preference ratio in [0, 1].
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_personalization
                    (user_id, category_weights, locale_ratio, updated_at)
                VALUES ($1, $2::jsonb, $3, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET category_weights = $2::jsonb,
                    locale_ratio = $3,
                    updated_at = NOW()
                """,
                user_id,
                json.dumps(category_weights),
                locale_ratio,
            )
    except Exception as exc:
        logger.error("upsert_personalization_failed", user_id=user_id, error=str(exc))
        raise
