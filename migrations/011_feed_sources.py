"""011_feed_sources — 개별 피드 소스 테이블 (동적 CRUD + 헬스 추적)."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "011"
DESCRIPTION = "Create feed_source table for dynamic feed management with health tracking"


async def up(conn: asyncpg.Connection) -> None:
    """Create feed_source table and indexes."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS feed_source (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_config_id     UUID REFERENCES source_config(id) ON DELETE SET NULL,
            source_type          TEXT NOT NULL
                CHECK (source_type IN ('rss', 'reddit', 'nitter', 'community', 'google_trends')),
            name                 TEXT NOT NULL,
            url                  TEXT NOT NULL,
            category             TEXT NOT NULL DEFAULT 'general',
            locale               CHAR(2) NOT NULL DEFAULT 'ko',
            is_active            BOOLEAN NOT NULL DEFAULT TRUE,
            priority             INT NOT NULL DEFAULT 0,
            config               JSONB NOT NULL DEFAULT '{}',
            -- health tracking
            last_crawled_at      TIMESTAMPTZ,
            last_success_at      TIMESTAMPTZ,
            last_error           TEXT,
            last_error_at        TIMESTAMPTZ,
            consecutive_failures INT NOT NULL DEFAULT 0,
            avg_latency_ms       FLOAT,
            total_crawl_count    INT NOT NULL DEFAULT 0,
            total_error_count    INT NOT NULL DEFAULT 0,
            -- timestamps
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_feed_source_url"
        " ON feed_source (url)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_source_type_active"
        " ON feed_source (source_type, is_active)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_source_config"
        " ON feed_source (source_config_id)"
    )
    logger.info("feed_source_table_created")


async def down(conn: asyncpg.Connection) -> None:
    """Drop feed_source table."""
    await conn.execute("DROP TABLE IF EXISTS feed_source CASCADE")
    logger.info("feed_source_table_dropped")
