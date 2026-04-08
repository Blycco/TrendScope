"""DB queries for daily digest job. (RULE 02: asyncpg $1,$2 only)"""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def get_digest_subscribers(
    pool: asyncpg.Pool,
) -> list[asyncpg.Record]:
    """Return (user_id, email, keyword) for users with email digest enabled.

    Joins notification_keyword with user_profile and notification to find
    users who have email alerts turned on for keyword_alert type.
    """
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT nk.user_id::text, nk.keyword, up.email
                FROM notification_keyword nk
                JOIN user_profile up ON up.id = nk.user_id
                JOIN notification ns
                  ON ns.user_id = nk.user_id
                 AND ns.type = $1
                 AND ns.channel = $2
                 AND ns.is_enabled = true
                WHERE up.email IS NOT NULL
                """,
                "keyword_alert",
                "email",
            )
    except Exception as exc:
        logger.error("get_digest_subscribers_failed", error=str(exc))
        return []


async def get_recent_reddit_questions(
    pool: asyncpg.Pool,
) -> list[asyncpg.Record]:
    """Return Reddit posts from the last 24 hours, ordered by score descending.

    Note: sns_trend does not store permalink/meta; keyword holds the post title.
    """
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT keyword, score
                FROM sns_trend
                WHERE platform = $1
                  AND snapshot_at >= NOW() - INTERVAL '24 hours'
                ORDER BY score DESC
                LIMIT 500
                """,
                "reddit",
            )
    except Exception as exc:
        logger.error("get_recent_reddit_questions_failed", error=str(exc))
        return []
