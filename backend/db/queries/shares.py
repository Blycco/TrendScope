"""DB query layer for shared_link table. (RULE 02: asyncpg $1,$2 only)"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

_SHARE_TTL_HOURS = 24


async def create_shared_link(
    pool: asyncpg.Pool,
    *,
    token: str,
    user_id: str,
    payload: dict,
) -> asyncpg.Record:
    """Insert a new shared_link row and return it."""
    try:
        expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=_SHARE_TTL_HOURS)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO shared_link (token, user_id, payload, expires_at)
                VALUES ($1, $2::uuid, $3::jsonb, $4)
                RETURNING id::text, token, user_id::text, payload, expires_at, created_at
                """,
                token,
                user_id,
                json.dumps(payload),
                expires_at,
            )
        return row
    except Exception as exc:
        logger.error("create_shared_link_failed", error=str(exc))
        raise


async def get_shared_link_by_token(
    pool: asyncpg.Pool,
    *,
    token: str,
) -> asyncpg.Record | None:
    """Fetch a non-expired shared_link by token."""
    try:
        now = datetime.now(tz=timezone.utc)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id::text, token, user_id::text, payload, expires_at, created_at
                FROM shared_link
                WHERE token = $1
                  AND expires_at > $2
                """,
                token,
                now,
            )
        return row
    except Exception as exc:
        logger.error("get_shared_link_failed", error=str(exc))
        raise
