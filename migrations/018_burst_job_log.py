"""018_burst_job_log — Burst Job 실행 이력 추적 테이블."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "018"
DESCRIPTION = "Create burst_job_log table for burst crawl tracking"


async def up(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS burst_job_log (
            id                BIGSERIAL PRIMARY KEY,
            triggered_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            trigger_source    TEXT NOT NULL DEFAULT 'auto'
                                CHECK (trigger_source IN ('auto', 'manual')),
            group_id          UUID REFERENCES news_group(id),
            keywords          TEXT[] NOT NULL,
            threshold         FLOAT NOT NULL,
            early_trend_score FLOAT NOT NULL,
            articles_found    INT NOT NULL DEFAULT 0,
            duration_ms       FLOAT,
            status            TEXT NOT NULL DEFAULT 'running'
                                CHECK (status IN ('running', 'success', 'failed', 'skipped')),
            error_detail      TEXT,
            completed_at      TIMESTAMPTZ
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_burst_job_log_triggered
        ON burst_job_log (triggered_at DESC)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_burst_job_log_group
        ON burst_job_log (group_id, triggered_at DESC)
    """)
    logger.info("migration_018_burst_job_log_applied")


async def down(conn: asyncpg.Connection) -> None:
    await conn.execute("DROP TABLE IF EXISTS burst_job_log")
    logger.info("migration_018_burst_job_log_rolled_back")
