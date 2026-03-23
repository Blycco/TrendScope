"""Migration 004: Add user_personalization table for per-user content weights.

Run with: python -m migrations.004_personalization
"""

from __future__ import annotations

import asyncio
import os

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

DDL_UP = """
CREATE TABLE IF NOT EXISTS user_personalization (
    user_id          UUID PRIMARY KEY REFERENCES user_profile(id) ON DELETE CASCADE,
    category_weights JSONB NOT NULL DEFAULT '{}',
    locale_ratio     FLOAT NOT NULL DEFAULT 0.5,
    updated_at       TIMESTAMPTZ DEFAULT NOW()
)
"""

DDL_DOWN = "DROP TABLE IF EXISTS user_personalization"


VERSION = "004_personalization"
DESCRIPTION = "Add user_personalization table for per-user content weights"


async def up(conn: asyncpg.Connection) -> None:
    """Apply migration 004 using an existing connection."""
    await conn.execute(DDL_UP)


async def run_migration(dsn: str, *, rollback: bool = False) -> None:
    """Apply or rollback migration 004."""
    conn: asyncpg.Connection = await asyncpg.connect(dsn)
    try:
        if rollback:
            await conn.execute(DDL_DOWN)
            logger.info("migration_004_complete", direction="rollback")
        else:
            async with conn.transaction():
                await conn.execute(DDL_UP)
            logger.info("migration_004_complete", direction="apply")
    except Exception as exc:
        logger.error("migration_004_failed", error=str(exc))
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL environment variable is required")
    asyncio.run(run_migration(database_url))
