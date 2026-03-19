"""DB query layer for notification settings table. (RULE 02: asyncpg $1,$2)"""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def get_notification_settings(
    pool: asyncpg.Pool,
    *,
    user_id: str,
) -> list[asyncpg.Record]:
    """Return all notification setting rows for a user."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id::text, user_id::text, type, channel, is_enabled,
                       created_at, updated_at
                FROM notification
                WHERE user_id = $1::uuid
                ORDER BY type, channel
                """,
                user_id,
            )
    except Exception as exc:
        logger.error("get_notification_settings_failed", user_id=user_id, error=str(exc))
        raise


async def upsert_notification_setting(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    notification_type: str,
    channel: str,
    is_enabled: bool,
) -> None:
    """Insert or update a notification setting row for a user."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO notification (user_id, type, channel, is_enabled)
                VALUES ($1::uuid, $2, $3, $4)
                ON CONFLICT (user_id, type, channel)
                DO UPDATE SET is_enabled = EXCLUDED.is_enabled,
                              updated_at = now()
                """,
                user_id,
                notification_type,
                channel,
                is_enabled,
            )
    except Exception as exc:
        logger.error(
            "upsert_notification_setting_failed",
            user_id=user_id,
            type=notification_type,
            channel=channel,
            error=str(exc),
        )
        raise
