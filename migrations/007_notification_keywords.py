"""Migration 007: Add notification_keyword table for per-user keyword alerts."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

SQL_UP = [
    """
    CREATE TABLE IF NOT EXISTS notification_keyword (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id    UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
        keyword    TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (user_id, keyword)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_nk_user ON notification_keyword (user_id)",
]

SQL_DOWN = [
    "DROP TABLE IF EXISTS notification_keyword",
]


VERSION = "007_notification_keywords"
DESCRIPTION = "Add notification_keyword table for per-user keyword alerts"


async def upgrade(conn: asyncpg.Connection) -> None:
    """Apply migration 007."""
    try:
        for sql in SQL_UP:
            await conn.execute(sql)
        logger.info("migration_007_applied", direction="up")
    except Exception:
        logger.exception("migration_007_failed", direction="up")
        raise


async def downgrade(conn: asyncpg.Connection) -> None:
    """Rollback migration 007."""
    try:
        for sql in SQL_DOWN:
            await conn.execute(sql)
        logger.info("migration_007_applied", direction="down")
    except Exception:
        logger.exception("migration_007_failed", direction="down")
        raise


up = upgrade  # runner interface alias
