"""024_burst_score — news_group에 burst_score 컬럼 추가."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "024"
DESCRIPTION = "Add burst_score column to news_group"


async def up(conn: asyncpg.Connection) -> None:
    """Add burst_score column and index."""
    await conn.execute("""
        ALTER TABLE news_group
        ADD COLUMN IF NOT EXISTS burst_score FLOAT NOT NULL DEFAULT 0.0
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_group_burst_score
        ON news_group (burst_score DESC)
    """)
    logger.info("migration_024_complete")


async def down(conn: asyncpg.Connection) -> None:
    """Remove burst_score column."""
    await conn.execute("DROP INDEX IF EXISTS idx_news_group_burst_score")
    await conn.execute("""
        ALTER TABLE news_group
        DROP COLUMN IF EXISTS burst_score
    """)
    logger.info("migration_024_reverted")
