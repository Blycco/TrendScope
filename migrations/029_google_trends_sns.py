"""029_google_trends_sns — Google Trends RSS를 SNS 크롤러로 전환 + Nitter 비활성화."""

from __future__ import annotations

import asyncpg

VERSION = "029"
DESCRIPTION = "Switch Google Trends feeds to SNS crawler, add source_config, deactivate Nitter"


async def up(conn: asyncpg.Connection) -> None:
    # 1) source_config for Google Trends RSS quota
    await conn.execute(
        """
        INSERT INTO source_config (source_name, source_type, is_active, quota_limit, quota_used)
        VALUES ('google_trends_rss', 'rss', TRUE, 100, 0)
        ON CONFLICT (source_name) DO NOTHING
        """
    )

    # 2) Switch existing Google Trends feed_source rows from 'rss' to 'google_trends'
    await conn.execute(
        """
        UPDATE feed_source
        SET source_type = 'google_trends'
        WHERE name LIKE 'Google Trends%'
          AND source_type IN ('rss', 'rss_ko')
        """
    )

    # 3) Deactivate Nitter source_config (feeds already deactivated in migration 019)
    await conn.execute(
        """
        UPDATE source_config
        SET is_active = FALSE
        WHERE source_name = 'nitter_rss'
        """
    )


async def down(conn: asyncpg.Connection) -> None:
    # Revert Google Trends feeds back to 'rss'
    await conn.execute(
        """
        UPDATE feed_source
        SET source_type = 'rss'
        WHERE name LIKE 'Google Trends%'
          AND source_type = 'google_trends'
        """
    )

    # Re-enable Nitter source_config
    await conn.execute(
        """
        UPDATE source_config
        SET is_active = TRUE
        WHERE source_name = 'nitter_rss'
        """
    )

    # Remove Google Trends RSS source_config
    await conn.execute(
        "DELETE FROM source_config WHERE source_name = 'google_trends_rss'"
    )
