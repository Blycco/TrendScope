"""033: Persist cross_platform_multiplier and external_trend_boost on news_group."""

from __future__ import annotations

import asyncpg

VERSION = "033_score_multipliers"
DESCRIPTION = "Add cross_platform_multiplier / external_trend_boost columns to news_group"


async def up(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        ALTER TABLE news_group
        ADD COLUMN IF NOT EXISTS cross_platform_multiplier FLOAT NOT NULL DEFAULT 1.0,
        ADD COLUMN IF NOT EXISTS external_trend_boost FLOAT NOT NULL DEFAULT 1.0
        """
    )


async def down(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        ALTER TABLE news_group
        DROP COLUMN IF EXISTS cross_platform_multiplier,
        DROP COLUMN IF EXISTS external_trend_boost
        """
    )
