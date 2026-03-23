"""DB queries for action insights. (RULE 02: asyncpg $1,$2 parameterized only)"""

from __future__ import annotations

import json

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def fetch_news_for_keyword(
    pool: asyncpg.Pool,
    keyword: str,
    limit: int = 10,
) -> list[asyncpg.Record]:
    """Fetch news_article rows whose title matches keyword, ordered by publish_time DESC."""
    try:
        query = """
            SELECT id::text, title, url, source, publish_time, body
            FROM news_article
            WHERE title ILIKE $1
            ORDER BY publish_time DESC
            LIMIT $2
        """
        async with pool.acquire() as conn:
            return await conn.fetch(query, f"%{keyword}%", limit)
    except Exception as exc:
        logger.error("fetch_news_for_keyword_failed", keyword=keyword, error=str(exc))
        raise


async def fetch_sns_for_keyword(
    pool: asyncpg.Pool,
    keyword: str,
    limit: int = 20,
) -> list[asyncpg.Record]:
    """Fetch sns_trend rows whose keyword matches, ordered by score DESC."""
    try:
        query = """
            SELECT id::text, platform, keyword, locale, score, snapshot_at
            FROM sns_trend
            WHERE keyword ILIKE $1
            ORDER BY score DESC
            LIMIT $2
        """
        async with pool.acquire() as conn:
            return await conn.fetch(query, f"%{keyword}%", limit)
    except Exception as exc:
        logger.error("fetch_sns_for_keyword_failed", keyword=keyword, error=str(exc))
        raise


async def insert_action_insight(
    pool: asyncpg.Pool,
    trend_kw: str,
    role: str,
    locale: str,
    content: dict,
) -> str:
    """Insert a new action_insight row and return its id."""
    try:
        content_json = json.dumps(content, ensure_ascii=False)
        query = """
            INSERT INTO action_insight (trend_kw, role, locale, content, expires_at)
            VALUES ($1, $2, $3, $4::jsonb, now() + INTERVAL '1 hour')
            RETURNING id::text
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, trend_kw, role, locale, content_json)
            return row["id"]
    except Exception as exc:
        logger.error(
            "insert_action_insight_failed",
            trend_kw=trend_kw,
            role=role,
            error=str(exc),
        )
        raise


async def get_insight_usage(
    pool: asyncpg.Pool,
    user_id: str,
    endpoint: str,
    reset_at: object,
) -> asyncpg.Record | None:
    """Return the api_usage row for (user_id, endpoint, reset_at), or None."""
    try:
        query = """
            SELECT id::text, user_id::text, endpoint, used_count, quota_limit, reset_at
            FROM api_usage
            WHERE user_id = $1::uuid AND endpoint = $2 AND reset_at = $3
        """
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, user_id, endpoint, reset_at)
    except Exception as exc:
        logger.error(
            "get_insight_usage_failed",
            user_id=user_id,
            endpoint=endpoint,
            error=str(exc),
        )
        raise


async def upsert_insight_usage(
    pool: asyncpg.Pool,
    user_id: str,
    endpoint: str,
    quota_limit: int,
    reset_at: object,
) -> None:
    """Insert api_usage row; silently skip if the row already exists."""
    try:
        query = """
            INSERT INTO api_usage (user_id, endpoint, used_count, quota_limit, reset_at)
            VALUES ($1::uuid, $2, 0, $3, $4)
            ON CONFLICT (user_id, endpoint, reset_at) DO NOTHING
        """
        async with pool.acquire() as conn:
            await conn.execute(query, user_id, endpoint, quota_limit, reset_at)
    except Exception as exc:
        logger.error(
            "upsert_insight_usage_failed",
            user_id=user_id,
            endpoint=endpoint,
            error=str(exc),
        )
        raise


async def increment_insight_usage(
    pool: asyncpg.Pool,
    user_id: str,
    endpoint: str,
    reset_at: object,
) -> None:
    """Increment used_count by 1 for the matching api_usage row."""
    try:
        query = """
            UPDATE api_usage
            SET used_count = used_count + 1
            WHERE user_id = $1::uuid AND endpoint = $2 AND reset_at = $3
        """
        async with pool.acquire() as conn:
            await conn.execute(query, user_id, endpoint, reset_at)
    except Exception as exc:
        logger.error(
            "increment_insight_usage_failed",
            user_id=user_id,
            endpoint=endpoint,
            error=str(exc),
        )
        raise
