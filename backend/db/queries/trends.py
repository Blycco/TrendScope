"""DB query layer for trend and news feed. (RULE 02: asyncpg $1,$2 only)"""

from __future__ import annotations

import base64
import struct

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Cursor helpers  (opaque cursor = base64(score_bytes:uuid_bytes))
# ---------------------------------------------------------------------------


def encode_cursor(score: float, row_id: str) -> str:
    """Encode (score, id) into a URL-safe base64 cursor string."""
    score_bytes = struct.pack(">d", score)
    id_bytes = row_id.encode()
    return base64.urlsafe_b64encode(score_bytes + b":" + id_bytes).decode()


def decode_cursor(cursor: str) -> tuple[float, str]:
    """Decode cursor back to (score, id). Raises ValueError on bad input."""
    raw = base64.urlsafe_b64decode(cursor.encode())
    sep = raw.index(b":")
    score = struct.unpack(">d", raw[:sep])[0]
    row_id = raw[sep + 1 :].decode()
    return score, row_id


# ---------------------------------------------------------------------------
# Trend queries  (news_group)
# ---------------------------------------------------------------------------


async def fetch_trends(
    pool: asyncpg.Pool,
    *,
    category: str | None,
    locale: str | None,
    limit: int = 20,
    cursor: str | None = None,
) -> list[asyncpg.Record]:
    """Fetch news_group rows ordered by score DESC with cursor pagination."""
    try:
        params: list[object] = []
        conditions: list[str] = []

        if category:
            params.append(category)
            conditions.append(f"category = ${len(params)}")
        if locale:
            params.append(locale)
            conditions.append(f"locale = ${len(params)}")

        if cursor:
            pivot_score, pivot_id = decode_cursor(cursor)
            params.extend([pivot_score, pivot_id])
            n = len(params)
            conditions.append(f"(score < ${n - 1} OR (score = ${n - 1} AND id::text > ${n}))")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)

        query = f"""
            SELECT id::text, category, locale, title, summary,
                   score, early_trend_score, keywords, created_at
            FROM news_group
            {where}
            ORDER BY score DESC, id ASC
            LIMIT ${len(params)}
        """  # noqa: S608

        async with pool.acquire() as conn:
            return await conn.fetch(query, *params)
    except Exception as exc:
        logger.error("fetch_trends_failed", error=str(exc))
        raise


async def fetch_early_trends(
    pool: asyncpg.Pool,
    *,
    locale: str | None,
    limit: int = 20,
    cursor: str | None = None,
) -> list[asyncpg.Record]:
    """Fetch news_group rows where early_trend_score > 0, ordered by early_trend_score DESC."""
    try:
        params: list[object] = []
        conditions: list[str] = ["early_trend_score > 0"]

        if locale:
            params.append(locale)
            conditions.append(f"locale = ${len(params)}")

        if cursor:
            pivot_score, pivot_id = decode_cursor(cursor)
            params.extend([pivot_score, pivot_id])
            n = len(params)
            conditions.append(
                f"(early_trend_score < ${n - 1}"
                f" OR (early_trend_score = ${n - 1} AND id::text > ${n}))"
            )

        where = "WHERE " + " AND ".join(conditions)
        params.append(limit)

        query = f"""
            SELECT id::text, category, locale, title, summary,
                   score, early_trend_score, keywords, created_at
            FROM news_group
            {where}
            ORDER BY early_trend_score DESC, id ASC
            LIMIT ${len(params)}
        """  # noqa: S608

        async with pool.acquire() as conn:
            return await conn.fetch(query, *params)
    except Exception as exc:
        logger.error("fetch_early_trends_failed", error=str(exc))
        raise


# ---------------------------------------------------------------------------
# Related trends query  (same category, ordered by score DESC)
# ---------------------------------------------------------------------------


async def fetch_related_trends(
    pool: asyncpg.Pool,
    *,
    trend_id: str,
    limit: int = 10,
) -> list[asyncpg.Record]:
    """Fetch news_group rows in the same category as trend_id, excluding trend_id itself."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id::text, category, locale, title, summary,
                       score, early_trend_score, keywords, created_at
                FROM news_group
                WHERE category = (
                    SELECT category FROM news_group WHERE id = $1::uuid
                )
                  AND id <> $1::uuid
                ORDER BY score DESC
                LIMIT $2
                """,
                trend_id,
                limit,
            )
    except Exception as exc:
        logger.error("fetch_related_trends_failed", trend_id=trend_id, error=str(exc))
        raise


# ---------------------------------------------------------------------------
# News queries  (news_article JOIN news_group)
# ---------------------------------------------------------------------------


async def fetch_news(
    pool: asyncpg.Pool,
    *,
    category: str | None,
    locale: str | None,
    limit: int = 20,
    cursor: str | None = None,
) -> list[asyncpg.Record]:
    """Fetch news_article rows joined with news_group, ordered by publish_time DESC."""
    try:
        params: list[object] = []
        conditions: list[str] = []

        if category:
            params.append(category)
            conditions.append(f"ng.category = ${len(params)}")
        if locale:
            params.append(locale)
            conditions.append(f"na.locale = ${len(params)}")

        if cursor:
            pivot_score, pivot_id = decode_cursor(cursor)
            # cursor stores (publish_time_float, id) — encode with unix timestamp
            import datetime  # noqa: PLC0415

            pivot_time = datetime.datetime.fromtimestamp(pivot_score, tz=datetime.timezone.utc)
            params.extend([pivot_time, pivot_id])
            n = len(params)
            conditions.append(
                f"(na.publish_time < ${n - 1}"
                f" OR (na.publish_time = ${n - 1} AND na.id::text > ${n}))"
            )

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)

        query = f"""
            SELECT na.id::text, na.title, na.url, na.source,
                   na.publish_time, ng.summary
            FROM news_article na
            LEFT JOIN news_group ng ON na.group_id = ng.id
            {where}
            ORDER BY na.publish_time DESC, na.id ASC
            LIMIT ${len(params)}
        """  # noqa: S608

        async with pool.acquire() as conn:
            return await conn.fetch(query, *params)
    except Exception as exc:
        logger.error("fetch_news_failed", error=str(exc))
        raise
