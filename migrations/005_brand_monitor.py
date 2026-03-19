"""Migration 005: Add slack_webhook and last_alerted_at to brand_monitor table."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

SQL_UP = [
    """
    ALTER TABLE brand_monitor
        ADD COLUMN IF NOT EXISTS slack_webhook TEXT,
        ADD COLUMN IF NOT EXISTS alert_threshold FLOAT NOT NULL DEFAULT 2.0,
        ADD COLUMN IF NOT EXISTS last_alerted_at TIMESTAMPTZ
    """,
]

SQL_DOWN = [
    """
    ALTER TABLE brand_monitor
        DROP COLUMN IF EXISTS slack_webhook,
        DROP COLUMN IF EXISTS alert_threshold,
        DROP COLUMN IF EXISTS last_alerted_at
    """,
]


async def upgrade(conn: asyncpg.Connection) -> None:
    """Apply migration 005."""
    try:
        for sql in SQL_UP:
            await conn.execute(sql)
        logger.info("migration_005_applied", direction="up")
    except Exception:
        logger.exception("migration_005_failed", direction="up")
        raise


async def downgrade(conn: asyncpg.Connection) -> None:
    """Rollback migration 005."""
    try:
        for sql in SQL_DOWN:
            await conn.execute(sql)
        logger.info("migration_005_applied", direction="down")
    except Exception:
        logger.exception("migration_005_failed", direction="down")
        raise
