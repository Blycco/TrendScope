"""008_indexes — 성능 최적화용 복합 인덱스 추가."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "008"
DESCRIPTION = "Performance indexes"
TRANSACTIONAL = False  # CREATE INDEX CONCURRENTLY cannot run inside a transaction


async def up(conn: asyncpg.Connection) -> None:
    """Apply indexes."""
    statements = [
        # news_group (not partitioned — CONCURRENTLY ok)
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_news_group_score_created ON news_group (score DESC, created_at DESC)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_news_group_category_score ON news_group (category, score DESC)",
        # news_article (partitioned — no CONCURRENTLY; column is publish_time)
        "CREATE INDEX IF NOT EXISTS idx_news_article_group_id ON news_article (group_id)",
        "CREATE INDEX IF NOT EXISTS idx_news_article_publish_time ON news_article (publish_time DESC)",
        # scrap (table name from migration 001)
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scrap_user_created ON scrap (user_id, created_at DESC)",
        # audit_log (partitioned — no CONCURRENTLY)
        "CREATE INDEX IF NOT EXISTS idx_audit_log_user_created ON audit_log (user_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log (created_at DESC)",
        # shared_link (not partitioned — CONCURRENTLY ok)
        "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_shared_link_token ON shared_link (token)",
        # notification_keyword (not partitioned — CONCURRENTLY ok)
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_keyword_user ON notification_keyword (user_id)",
    ]
    for stmt in statements:
        await conn.execute(stmt)
        logger.info("index_created", stmt=stmt[:80])


async def down(conn: asyncpg.Connection) -> None:
    """Drop indexes."""
    indexes = [
        "idx_news_group_score_created",
        "idx_news_group_category_score",
        "idx_news_article_group_id",
        "idx_news_article_publish_time",
        "idx_scrap_user_created",
        "idx_audit_log_user_created",
        "idx_audit_log_created",
        "idx_shared_link_token",
        "idx_notification_keyword_user",
    ]
    for idx in indexes:
        await conn.execute(f"DROP INDEX IF EXISTS {idx}")
