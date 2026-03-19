"""008_indexes — 성능 최적화용 복합 인덱스 추가."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "008"
DESCRIPTION = "Performance indexes"


async def up(conn: asyncpg.Connection) -> None:
    """Apply indexes."""
    statements = [
        # news_group
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_news_group_score_created ON news_group (score DESC, created_at DESC)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_news_group_category_score ON news_group (category, score DESC)",
        # news_article
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_news_article_group_id ON news_article (group_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_news_article_published_at ON news_article (published_at DESC)",
        # user_scrap
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_scrap_user_created ON user_scrap (user_id, created_at DESC)",
        # audit_log
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_user_created ON audit_log (user_id, created_at DESC)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_created ON audit_log (created_at DESC)",
        # shared_link
        "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_shared_link_token ON shared_link (token)",
        # notification_keyword
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
        "idx_news_article_published_at",
        "idx_user_scrap_user_created",
        "idx_audit_log_user_created",
        "idx_audit_log_created",
        "idx_shared_link_token",
        "idx_notification_keyword_user",
    ]
    for idx in indexes:
        await conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {idx}")
