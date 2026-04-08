"""020_growth_type — news_group 테이블에 growth_type 컬럼 추가."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "020"
DESCRIPTION = "Add growth_type column to news_group"


async def up(conn: asyncpg.Connection) -> None:
    """Add growth_type column and index to news_group."""
    await conn.execute("""
        ALTER TABLE news_group
        ADD COLUMN IF NOT EXISTS growth_type TEXT
            CHECK (growth_type IN ('growth', 'spike', 'unknown'))
            DEFAULT 'unknown'
    """)
    logger.info("growth_type_column_added")

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ng_growth_type
        ON news_group (growth_type, locale, score DESC)
    """)
    logger.info("growth_type_index_created")


async def down(conn: asyncpg.Connection) -> None:
    """Revert: remove growth_type index and column."""
    await conn.execute("DROP INDEX IF EXISTS idx_ng_growth_type")
    await conn.execute("ALTER TABLE news_group DROP COLUMN IF EXISTS growth_type")
    logger.info("growth_type_column_dropped")
