"""019_fix_google_trends_source_type — google_trends → rss 소스 타입 변경 + nitter 비활성화."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "019"
DESCRIPTION = "Fix google_trends source_type to rss, deactivate nitter feeds"


async def up(conn: asyncpg.Connection) -> None:
    """Change google_trends source_type to rss and deactivate nitter feeds."""
    # Google Trends RSS feeds are standard RSS — change source_type so news_crawler picks them up
    gt_result = await conn.execute(
        "UPDATE feed_source SET source_type = 'rss', updated_at = now() "
        "WHERE source_type = 'google_trends'"
    )
    gt_count = int(gt_result.split()[-1]) if gt_result else 0
    logger.info("google_trends_to_rss", updated=gt_count)

    # Nitter project shut down in 2024 — deactivate all nitter feeds
    nt_result = await conn.execute(
        "UPDATE feed_source SET is_active = FALSE, updated_at = now() "
        "WHERE source_type = 'nitter'"
    )
    nt_count = int(nt_result.split()[-1]) if nt_result else 0
    logger.info("nitter_deactivated", updated=nt_count)


async def down(conn: asyncpg.Connection) -> None:
    """Revert: restore google_trends source_type and re-activate nitter."""
    await conn.execute(
        "UPDATE feed_source SET source_type = 'google_trends', updated_at = now() "
        "WHERE name LIKE 'Google Trends%'"
    )
    await conn.execute(
        "UPDATE feed_source SET is_active = TRUE, updated_at = now() "
        "WHERE source_type = 'nitter'"
    )
