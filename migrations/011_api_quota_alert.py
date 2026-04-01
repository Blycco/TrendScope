"""011_api_quota_alert — 외부 API rate limit/quota 초과 알림 테이블."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "011"
DESCRIPTION = "Create api_quota_alert table for external API rate limit tracking"


async def up(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS api_quota_alert (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            service_name    TEXT NOT NULL,
            error_type      TEXT NOT NULL DEFAULT 'rate_limit_429',
            status_code     INT,
            detail          TEXT,
            endpoint_url    TEXT,
            is_dismissed    BOOLEAN NOT NULL DEFAULT FALSE,
            dismissed_by    UUID REFERENCES user_profile(id),
            dismissed_at    TIMESTAMPTZ,
            email_sent      BOOLEAN NOT NULL DEFAULT FALSE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_quota_alert_created
        ON api_quota_alert (created_at DESC)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_quota_alert_active
        ON api_quota_alert (is_dismissed, created_at DESC)
    """)
    logger.info("migration_011_api_quota_alert_applied")


async def down(conn: asyncpg.Connection) -> None:
    await conn.execute("DROP TABLE IF EXISTS api_quota_alert")
    logger.info("migration_011_api_quota_alert_rolled_back")
