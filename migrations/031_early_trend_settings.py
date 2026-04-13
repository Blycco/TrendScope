"""031: Add early trend recency weight + acceleration divisor + active window settings."""

from __future__ import annotations

import asyncpg

VERSION = "031_early_trend_settings"
DESCRIPTION = "Add early_trend_w_recency, acceleration_divisor, active_window settings"

_NEW_SETTINGS = [
    ("early_trend_w_recency", "0.2", "0.2", "EarlyTrend 최신성 가중치"),
    ("early_trend_acceleration_divisor", "5.0", "5.0", "EarlyTrend 가속도 제수"),
    ("early_trend_active_window_hours", "48", "48", "EarlyTrend 활성 윈도우(시간)"),
]


async def up(conn: asyncpg.Connection) -> None:
    # Insert new settings (skip if already present)
    await conn.executemany(
        """
        INSERT INTO admin_settings (key, value, default_value, description)
        VALUES ($1, to_jsonb($2::text), to_jsonb($3::text), $4)
        ON CONFLICT (key) DO NOTHING
        """,
        _NEW_SETTINGS,
    )

    # Adjust w_burst default 0.5 → 0.3 (only if user hasn't customized it)
    await conn.execute(
        """
        UPDATE admin_settings
        SET value = to_jsonb('0.3'::text),
            default_value = to_jsonb('0.3'::text)
        WHERE key = 'early_trend_w_burst'
          AND value = to_jsonb('0.5'::text)
        """,
    )

    # Update default_value for w_burst even if value was customized
    await conn.execute(
        """
        UPDATE admin_settings
        SET default_value = to_jsonb('0.3'::text)
        WHERE key = 'early_trend_w_burst'
        """,
    )
