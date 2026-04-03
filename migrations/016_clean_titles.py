"""016_clean_titles — 커뮤니티 게시글 제목 끝 댓글수/조회수 정제."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "016"
DESCRIPTION = "Clean trailing comment/view counts from article and group titles"


async def up(conn: asyncpg.Connection) -> None:
    # Remove trailing numbers from titles: "제목 1162" → "제목"
    await conn.execute("""
        UPDATE news_article
        SET title = rtrim(regexp_replace(title, ' [0-9]+$', ''))
        WHERE title ~ ' [0-9]+$'
    """)
    await conn.execute("""
        UPDATE news_article
        SET title = btrim(title, '"')
        WHERE title LIKE '"%' AND title LIKE '%"'
    """)
    await conn.execute("""
        UPDATE news_group
        SET title = rtrim(regexp_replace(title, ' [0-9]+$', ''))
        WHERE title ~ ' [0-9]+$'
    """)
    # Remove numeric-only keywords
    await conn.execute("""
        UPDATE news_group
        SET keywords = (
            SELECT array_agg(kw)
            FROM unnest(keywords) AS kw
            WHERE kw !~ '^[0-9]+$'
        )
        WHERE EXISTS (
            SELECT 1 FROM unnest(keywords) AS kw WHERE kw ~ '^[0-9]+$'
        )
    """)
    logger.info("migration_016_clean_titles_applied")


async def down(conn: asyncpg.Connection) -> None:
    logger.info("migration_016_clean_titles_rolled_back_noop")
