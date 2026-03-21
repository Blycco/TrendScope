"""Migration 003: Add notification table for per-user channel settings.

Run with: python -m migrations.003_notifications
"""

from __future__ import annotations

import asyncio
import os

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

DDL_UP = """
CREATE TABLE IF NOT EXISTS notification (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    type        TEXT NOT NULL,
    channel     TEXT NOT NULL,
    is_enabled  BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, type, channel)
)
"""

DDL_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_notification_user ON notification(user_id)"
)

DDL_DOWN = "DROP TABLE IF EXISTS notification"


VERSION = "003_notifications"
DESCRIPTION = "Add notification table for per-user channel settings"


async def up(conn: asyncpg.Connection) -> None:
    """Apply migration 003 using an existing connection."""
    await conn.execute(DDL_UP)
    await conn.execute(DDL_INDEX)


async def run_migration(dsn: str, *, rollback: bool = False) -> None:
    """Apply or rollback migration 003."""
    conn: asyncpg.Connection = await asyncpg.connect(dsn)
    try:
        if rollback:
            await conn.execute(DDL_DOWN)
            logger.info("migration_003_complete", direction="rollback")
        else:
            async with conn.transaction():
                await conn.execute(DDL_UP)
                await conn.execute(DDL_INDEX)
            logger.info("migration_003_complete", direction="apply")
    except Exception as exc:
        logger.error("migration_003_failed", error=str(exc))
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL environment variable is required")
    asyncio.run(run_migration(database_url))
