"""010_index_tuning — 커서 페이지네이션·ILIKE 검색 성능 인덱스 추가."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "010"
DESCRIPTION = "Index tuning: cursor pagination + pg_trgm GIN"


async def up(conn: asyncpg.Connection) -> None:
    """Apply performance indexes for cursor pagination and ILIKE search."""
    statements = [
        # news_article — locale+publish_time 커서 페이지네이션 (publish_time 컬럼명 통일)
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_na_locale_pubtime"
        " ON news_article (locale, publish_time DESC, id ASC)",
        # news_article — group_id JOIN + publish_time 정렬 최적화
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_na_group_pubtime"
        " ON news_article (group_id, publish_time DESC)",
        # news_group — 피드 커서 (category+locale+score+id)
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ng_feed_cursor"
        " ON news_group (category, locale, score DESC, id ASC)",
        # news_group — early_trend 커서 (locale+early_trend_score+id)
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ng_early_cursor"
        " ON news_group (locale, early_trend_score DESC, id ASC)",
        # pg_trgm 확장 (ILIKE 가속)
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        # news_article.title ILIKE 검색 GIN 인덱스
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_na_title_trgm"
        " ON news_article USING GIN (title gin_trgm_ops)",
        # sns_trend.keyword ILIKE 검색 GIN 인덱스
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sns_keyword_trgm"
        " ON sns_trend USING GIN (keyword gin_trgm_ops)",
    ]
    for stmt in statements:
        await conn.execute(stmt)
        logger.info("index_created", stmt=stmt[:80])


async def down(conn: asyncpg.Connection) -> None:
    """Drop tuning indexes."""
    indexes = [
        "idx_na_locale_pubtime",
        "idx_na_group_pubtime",
        "idx_ng_feed_cursor",
        "idx_ng_early_cursor",
        "idx_na_title_trgm",
        "idx_sns_keyword_trgm",
    ]
    for idx in indexes:
        await conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {idx}")
        logger.info("index_dropped", index=idx)
