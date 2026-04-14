"""032: Add alert_surge / alert_daily flags to notification_keyword."""

from __future__ import annotations

import asyncpg

VERSION = "032_notification_keyword_alert_flags"
DESCRIPTION = "Persist per-keyword alert toggles (surge / daily) on notification_keyword"


async def up(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        ALTER TABLE notification_keyword
        ADD COLUMN IF NOT EXISTS alert_surge BOOLEAN NOT NULL DEFAULT TRUE,
        ADD COLUMN IF NOT EXISTS alert_daily BOOLEAN NOT NULL DEFAULT FALSE
        """
    )


async def down(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        ALTER TABLE notification_keyword
        DROP COLUMN IF EXISTS alert_surge,
        DROP COLUMN IF EXISTS alert_daily
        """
    )
