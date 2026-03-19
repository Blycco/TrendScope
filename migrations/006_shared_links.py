"""Migration 006: Add shared_links table for trend sharing feature."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

SQL_UP = [
    """
    CREATE TABLE IF NOT EXISTS shared_link (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        token       TEXT NOT NULL UNIQUE,
        user_id     UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
        payload     JSONB NOT NULL DEFAULT '{}',
        expires_at  TIMESTAMPTZ NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_shared_link_token ON shared_link (token)",
    "CREATE INDEX IF NOT EXISTS idx_shared_link_user  ON shared_link (user_id)",
]

SQL_DOWN = [
    "DROP TABLE IF EXISTS shared_link",
]


async def upgrade(conn: asyncpg.Connection) -> None:
    """Apply migration 006."""
    try:
        for sql in SQL_UP:
            await conn.execute(sql)
        logger.info("migration_006_applied", direction="up")
    except Exception:
        logger.exception("migration_006_failed", direction="up")
        raise


async def downgrade(conn: asyncpg.Connection) -> None:
    """Rollback migration 006."""
    try:
        for sql in SQL_DOWN:
            await conn.execute(sql)
        logger.info("migration_006_applied", direction="down")
    except Exception:
        logger.exception("migration_006_failed", direction="down")
        raise
