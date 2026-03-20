"""009_audit_archive — audit_log 아카이브 테이블 및 컬럼 추가."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "009"
DESCRIPTION = "Audit log archive table"


async def up(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log_archive (
            id          BIGSERIAL PRIMARY KEY,
            user_id     UUID,
            action      VARCHAR(100) NOT NULL,
            resource    VARCHAR(100),
            resource_id VARCHAR(100),
            ip_address  INET,
            user_agent  TEXT,
            metadata    JSONB DEFAULT '{}',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_archive_user ON audit_log_archive (user_id, created_at DESC)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_archive_archived ON audit_log_archive (archived_at DESC)"
    )
    logger.info("audit_log_archive_created")


async def down(conn: asyncpg.Connection) -> None:
    await conn.execute("DROP TABLE IF EXISTS audit_log_archive")
