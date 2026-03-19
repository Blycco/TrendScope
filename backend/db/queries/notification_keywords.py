"""DB query layer for notification_keyword table. (RULE 02: asyncpg $1,$2 only)"""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def get_keywords_for_user(
    pool: asyncpg.Pool,
    *,
    user_id: str,
) -> list[asyncpg.Record]:
    """Return all keyword alert rows for a user, ordered by created_at ASC."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id::text, user_id::text, keyword, created_at
                FROM notification_keyword
                WHERE user_id = $1::uuid
                ORDER BY created_at ASC
                """,
                user_id,
            )
    except Exception as exc:
        logger.error("get_keywords_failed", user_id=user_id, error=str(exc))
        raise


async def count_keywords_for_user(
    pool: asyncpg.Pool,
    *,
    user_id: str,
) -> int:
    """Return the number of keyword alerts the user currently has."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM notification_keyword WHERE user_id = $1::uuid",
                user_id,
            )
    except Exception as exc:
        logger.error("count_keywords_failed", user_id=user_id, error=str(exc))
        raise


async def insert_keyword(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    keyword: str,
) -> asyncpg.Record:
    """Insert a new keyword alert row and return it."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO notification_keyword (user_id, keyword)
                VALUES ($1::uuid, $2)
                RETURNING id::text, user_id::text, keyword, created_at
                """,
                user_id,
                keyword,
            )
        return row
    except Exception as exc:
        logger.error("insert_keyword_failed", user_id=user_id, keyword=keyword, error=str(exc))
        raise


async def delete_keyword(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    keyword_id: str,
) -> bool:
    """Delete a keyword alert by id. Returns True if a row was deleted."""
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM notification_keyword
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                keyword_id,
                user_id,
            )
        # asyncpg returns "DELETE N" — extract N
        deleted = int(result.split()[-1])
        return deleted > 0
    except Exception as exc:
        logger.error(
            "delete_keyword_failed",
            user_id=user_id,
            keyword_id=keyword_id,
            error=str(exc),
        )
        raise
