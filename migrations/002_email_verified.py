"""Migration 002: Add email_verified column to user_profile.

Run with: python -m migrations.002_email_verified
"""

from __future__ import annotations

import asyncio
import os

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

DDL_UP = """
ALTER TABLE user_profile
    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE
"""

DDL_DOWN = """
ALTER TABLE user_profile
    DROP COLUMN IF EXISTS email_verified
"""


VERSION = "002_email_verified"
DESCRIPTION = "Add email_verified column to user_profile"


async def up(conn: asyncpg.Connection) -> None:
    """Apply migration 002 using an existing connection."""
    await conn.execute(DDL_UP)


async def run_migration(dsn: str, *, rollback: bool = False) -> None:
    """Apply or rollback migration 002."""
    conn: asyncpg.Connection = await asyncpg.connect(dsn)
    try:
        ddl = DDL_DOWN if rollback else DDL_UP
        await conn.execute(ddl)
        direction = "rollback" if rollback else "apply"
        logger.info("migration_002_complete", direction=direction)
    except Exception as exc:
        logger.error("migration_002_failed", error=str(exc))
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL environment variable is required")
    asyncio.run(run_migration(database_url))
