"""Migration 017: error_log 테이블 — 에러 영구 기록용 append-only 테이블."""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

DESCRIPTION = "Create error_log table for permanent error recording"


async def apply(conn: object) -> None:
    """Create error_log table and indexes."""
    logger.info("migration_017_start")

    await conn.execute(  # type: ignore[attr-defined]
        """
        CREATE TABLE IF NOT EXISTS error_log (
            id              BIGSERIAL PRIMARY KEY,
            occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            service         TEXT NOT NULL,
            severity        TEXT NOT NULL DEFAULT 'error'
                                CHECK (severity IN ('warning', 'error', 'critical')),
            error_code      TEXT,
            message         TEXT NOT NULL,
            detail          JSONB,
            user_id         UUID,
            request_path    TEXT
        )
        """
    )

    await conn.execute(  # type: ignore[attr-defined]
        "CREATE INDEX IF NOT EXISTS idx_error_log_occurred " "ON error_log (occurred_at DESC)"
    )

    await conn.execute(  # type: ignore[attr-defined]
        "CREATE INDEX IF NOT EXISTS idx_error_log_service " "ON error_log (service, severity)"
    )

    logger.info("migration_017_complete")
