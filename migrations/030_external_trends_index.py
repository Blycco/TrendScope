"""030_external_trends_index — sns_trend 교차 검증 쿼리 최적화 인덱스."""

from __future__ import annotations

import asyncpg

VERSION = "030"
DESCRIPTION = "Add index on sns_trend for keyword+platform cross-validation queries"

NON_TRANSACTIONAL = True  # CREATE INDEX CONCURRENTLY requires this


async def up(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sns_trend_keyword_platform
        ON sns_trend (keyword, platform, snapshot_at DESC)
        """
    )


async def down(conn: asyncpg.Connection) -> None:
    await conn.execute(
        "DROP INDEX CONCURRENTLY IF EXISTS idx_sns_trend_keyword_platform"
    )
