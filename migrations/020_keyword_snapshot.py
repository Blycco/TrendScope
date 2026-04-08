"""020_keyword_snapshot — keyword_snapshot 테이블 생성."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "020"
DESCRIPTION = "Create keyword_snapshot table"


async def up(conn: asyncpg.Connection) -> None:
    """Create keyword_snapshot table and indexes."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS keyword_snapshot (
            id          BIGSERIAL PRIMARY KEY,
            group_id    UUID NOT NULL REFERENCES news_group(id) ON DELETE CASCADE,
            keyword     TEXT NOT NULL,
            frequency   INT NOT NULL DEFAULT 0,
            snapshot_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ks_group_time
        ON keyword_snapshot (group_id, snapshot_at DESC)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ks_snapshot_at
        ON keyword_snapshot (snapshot_at DESC)
    """)
    logger.info("migration_020_complete")


async def down(conn: asyncpg.Connection) -> None:
    """Drop keyword_snapshot table."""
    await conn.execute("DROP TABLE IF EXISTS keyword_snapshot CASCADE")
    logger.info("migration_020_reverted")
