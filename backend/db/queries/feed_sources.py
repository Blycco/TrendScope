"""DB query layer for feed_source CRUD and health tracking. (RULE 02, RULE 03, RULE 07)"""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

_HEALTH_STATUS_EXPR = """
    CASE
        WHEN last_crawled_at IS NULL THEN 'unknown'
        WHEN consecutive_failures >= 5 THEN 'error'
        WHEN consecutive_failures >= 2
             OR (now() - last_success_at > interval '30 minutes') THEN 'degraded'
        ELSE 'healthy'
    END AS health_status
"""

_SELECT_COLUMNS = """
    id::text, source_config_id::text, source_type, name, url,
    category, locale, is_active, priority, config,
    last_crawled_at, last_success_at, last_error, last_error_at,
    consecutive_failures, avg_latency_ms, total_crawl_count, total_error_count,
    created_at, updated_at
"""


async def list_feed_sources(
    pool: asyncpg.Pool,
    *,
    source_type: str | None = None,
    is_active: bool | None = None,
    category: str | None = None,
    locale: str | None = None,
    health_status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[asyncpg.Record], int]:
    """Paginated listing of feed_source with filters."""
    try:
        async with pool.acquire() as conn:
            conditions: list[str] = []
            params: list[object] = []
            idx = 1

            if source_type:
                conditions.append(f"source_type = ${idx}")
                params.append(source_type)
                idx += 1
            if is_active is not None:
                conditions.append(f"is_active = ${idx}")
                params.append(is_active)
                idx += 1
            if category:
                conditions.append(f"category = ${idx}")
                params.append(category)
                idx += 1
            if locale:
                conditions.append(f"locale = ${idx}")
                params.append(locale)
                idx += 1
            if search:
                conditions.append(f"(name ILIKE ${idx} OR url ILIKE ${idx})")
                params.append(f"%{search}%")
                idx += 1

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            if health_status:
                health_filter = f"""
                    WHERE health_status = ${idx}
                """
                params_with_health = [*params, health_status]
                idx += 1
            else:
                health_filter = ""
                params_with_health = list(params)

            # count query
            if health_status:
                count_query = f"""
                    SELECT count(*) FROM (
                        SELECT {_HEALTH_STATUS_EXPR}
                        FROM feed_source {where_clause}
                    ) sub {health_filter}
                """  # noqa: S608
                total = await conn.fetchval(count_query, *params_with_health) or 0
            else:
                count_query = f"SELECT count(*) FROM feed_source {where_clause}"  # noqa: S608
                total = await conn.fetchval(count_query, *params) or 0

            offset = (page - 1) * page_size
            if health_status:
                data_query = f"""
                    SELECT * FROM (
                        SELECT {_SELECT_COLUMNS}, {_HEALTH_STATUS_EXPR}
                        FROM feed_source {where_clause}
                    ) sub {health_filter}
                    ORDER BY source_type, priority DESC, name
                    LIMIT ${idx} OFFSET ${idx + 1}
                """  # noqa: S608
                params_with_health.extend([page_size, offset])
                rows = await conn.fetch(data_query, *params_with_health)
            else:
                data_query = f"""
                    SELECT {_SELECT_COLUMNS}, {_HEALTH_STATUS_EXPR}
                    FROM feed_source {where_clause}
                    ORDER BY source_type, priority DESC, name
                    LIMIT ${idx} OFFSET ${idx + 1}
                """  # noqa: S608
                params.extend([page_size, offset])
                rows = await conn.fetch(data_query, *params)

            return rows, total
    except Exception as exc:
        logger.error("list_feed_sources_failed", error=str(exc))
        raise


async def get_feed_source(pool: asyncpg.Pool, feed_id: str) -> asyncpg.Record | None:
    """Get single feed_source by UUID."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                f"""
                SELECT {_SELECT_COLUMNS}, {_HEALTH_STATUS_EXPR}
                FROM feed_source
                WHERE id = $1::uuid
                """,  # noqa: S608
                feed_id,
            )
    except Exception as exc:
        logger.error("get_feed_source_failed", feed_id=feed_id, error=str(exc))
        raise


async def create_feed_source(
    pool: asyncpg.Pool,
    *,
    name: str,
    url: str,
    source_type: str,
    category: str = "general",
    locale: str = "ko",
    source_config_id: str | None = None,
    is_active: bool = True,
    priority: int = 0,
    config: str = "{}",
) -> asyncpg.Record:
    """Insert a new feed_source row."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                f"""
                INSERT INTO feed_source (
                    source_config_id, source_type, name, url,
                    category, locale, is_active, priority, config
                ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                RETURNING {_SELECT_COLUMNS}, {_HEALTH_STATUS_EXPR}
                """,
                source_config_id,
                source_type,
                name,
                url,
                category,
                locale,
                is_active,
                priority,
                config,
            )
    except Exception as exc:
        logger.error("create_feed_source_failed", url=url, error=str(exc))
        raise


_UPDATABLE_COLUMNS = frozenset(
    {
        "name",
        "url",
        "source_type",
        "category",
        "locale",
        "source_config_id",
        "is_active",
        "priority",
        "config",
    }
)


async def update_feed_source(
    pool: asyncpg.Pool,
    feed_id: str,
    **kwargs: object,
) -> asyncpg.Record | None:
    """Update feed_source with whitelisted columns."""
    fields = {k: v for k, v in kwargs.items() if k in _UPDATABLE_COLUMNS and v is not None}
    if not fields:
        return None

    set_clauses: list[str] = []
    params: list[object] = [feed_id]
    for idx, (col, val) in enumerate(fields.items(), start=2):
        if col == "config":
            set_clauses.append(f"{col} = ${idx}::jsonb")
        elif col == "source_config_id":
            set_clauses.append(f"{col} = ${idx}::uuid")
        else:
            set_clauses.append(f"{col} = ${idx}")
        params.append(val)

    # Safe: set_clauses built from whitelisted column names only (RULE 02)
    query = (
        f"UPDATE feed_source SET {', '.join(set_clauses)}, updated_at = now() "  # noqa: S608
        f"WHERE id = $1::uuid "
        f"RETURNING {_SELECT_COLUMNS}, {_HEALTH_STATUS_EXPR}"
    )
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *params)
    except Exception as exc:
        logger.error("update_feed_source_failed", feed_id=feed_id, error=str(exc))
        raise


async def delete_feed_source(pool: asyncpg.Pool, feed_id: str) -> bool:
    """Delete a feed_source by ID. Returns True if deleted."""
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM feed_source WHERE id = $1::uuid", feed_id)
            return result == "DELETE 1"
    except Exception as exc:
        logger.error("delete_feed_source_failed", feed_id=feed_id, error=str(exc))
        raise


async def bulk_toggle_feed_sources(
    pool: asyncpg.Pool, feed_ids: list[str], *, is_active: bool
) -> int:
    """Bulk enable/disable feed_source rows. Returns count of updated rows."""
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE feed_source
                SET is_active = $1, updated_at = now()
                WHERE id = ANY($2::uuid[])
                """,
                is_active,
                feed_ids,
            )
            return int(result.split()[-1]) if result else 0
    except Exception as exc:
        logger.error("bulk_toggle_feed_sources_failed", error=str(exc))
        raise


async def get_feed_sources_for_crawl(
    pool: asyncpg.Pool,
    source_type: str,
) -> list[asyncpg.Record]:
    """Lightweight query for crawlers — active feeds of given type."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id::text, url, name, category, locale, config
                FROM feed_source
                WHERE source_type = $1 AND is_active = TRUE
                ORDER BY priority DESC, name
                """,
                source_type,
            )
    except Exception as exc:
        logger.error("get_feed_sources_for_crawl_failed", source_type=source_type, error=str(exc))
        raise


async def update_feed_health(
    pool: asyncpg.Pool,
    feed_id: str,
    *,
    success: bool,
    latency_ms: float,
    error: str | None = None,
) -> None:
    """Update health columns after a crawl attempt."""
    try:
        async with pool.acquire() as conn:
            if success:
                await conn.execute(
                    """
                    UPDATE feed_source SET
                        last_crawled_at = now(),
                        last_success_at = now(),
                        consecutive_failures = 0,
                        avg_latency_ms = CASE
                            WHEN avg_latency_ms IS NULL THEN $2::float8
                            ELSE (avg_latency_ms * 0.7 + $2::float8 * 0.3)
                        END,
                        total_crawl_count = total_crawl_count + 1,
                        updated_at = now()
                    WHERE id = $1::uuid
                    """,
                    feed_id,
                    latency_ms,
                )
            else:
                await conn.execute(
                    """
                    UPDATE feed_source SET
                        last_crawled_at = now(),
                        last_error = $2,
                        last_error_at = now(),
                        consecutive_failures = consecutive_failures + 1,
                        avg_latency_ms = CASE
                            WHEN avg_latency_ms IS NULL THEN $3::float8
                            ELSE (avg_latency_ms * 0.7 + $3::float8 * 0.3)
                        END,
                        total_crawl_count = total_crawl_count + 1,
                        total_error_count = total_error_count + 1,
                        updated_at = now()
                    WHERE id = $1::uuid
                    """,
                    feed_id,
                    error,
                    latency_ms,
                )
    except Exception as exc:
        logger.error("update_feed_health_failed", feed_id=feed_id, error=str(exc))
        raise


async def get_feed_health_summary(
    pool: asyncpg.Pool,
) -> list[asyncpg.Record]:
    """Aggregated health counts by source_type for the dashboard."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(
                f"""
                SELECT
                    source_type,
                    count(*) AS total,
                    count(*) FILTER (WHERE health_status = 'healthy') AS healthy,
                    count(*) FILTER (WHERE health_status = 'degraded') AS degraded,
                    count(*) FILTER (WHERE health_status = 'error') AS error,
                    count(*) FILTER (WHERE health_status = 'unknown') AS unknown
                FROM (
                    SELECT source_type, {_HEALTH_STATUS_EXPR}
                    FROM feed_source
                    WHERE is_active = TRUE
                ) sub
                GROUP BY source_type
                ORDER BY source_type
                """  # noqa: S608
            )
    except Exception as exc:
        logger.error("get_feed_health_summary_failed", error=str(exc))
        raise
