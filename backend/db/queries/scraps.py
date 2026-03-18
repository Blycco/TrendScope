"""DB query layer for scrap table. (RULE 02: asyncpg $1,$2 parameterization)"""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def get_scrap_count(pool: asyncpg.Pool, *, user_id: str) -> int:
    """Return the total number of scraps for a user."""
    try:
        async with pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT count(*) FROM scrap WHERE user_id = $1::uuid",
                user_id,
            )
            return int(result or 0)
    except Exception as exc:
        logger.error("get_scrap_count_failed", user_id=user_id, error=str(exc))
        raise


async def create_scrap(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    item_type: str,
    item_id: str,
    user_tags: list[str] | None = None,
    memo: str | None = None,
) -> asyncpg.Record:
    """Insert a new scrap row and return it."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                INSERT INTO scrap (user_id, item_type, item_id, user_tags, memo)
                VALUES ($1::uuid, $2, $3::uuid, $4, $5)
                RETURNING id::text, user_id::text, item_type, item_id::text,
                          user_tags, memo, created_at
                """,
                user_id,
                item_type,
                item_id,
                user_tags or [],
                memo,
            )
    except Exception as exc:
        logger.error("create_scrap_failed", user_id=user_id, error=str(exc))
        raise


async def list_scraps(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    limit: int = 20,
    offset: int = 0,
) -> list[asyncpg.Record]:
    """List scraps for a user, newest first."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id::text, user_id::text, item_type, item_id::text,
                       user_tags, memo, created_at
                FROM scrap
                WHERE user_id = $1::uuid
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )
    except Exception as exc:
        logger.error("list_scraps_failed", user_id=user_id, error=str(exc))
        raise


async def delete_scrap(
    pool: asyncpg.Pool,
    *,
    scrap_id: str,
    user_id: str,
) -> bool:
    """Delete a scrap by id (owner check). Returns True if deleted."""
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM scrap WHERE id = $1::uuid AND user_id = $2::uuid",
                scrap_id,
                user_id,
            )
            return result == "DELETE 1"
    except Exception as exc:
        logger.error("delete_scrap_failed", scrap_id=scrap_id, error=str(exc))
        raise
