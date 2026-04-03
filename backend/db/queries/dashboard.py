"""DB query layer for dashboard summary. (RULE 02: asyncpg $1,$2 only)"""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def fetch_dashboard_summary(
    pool: asyncpg.Pool,
) -> dict:
    """Fetch aggregated dashboard stats for the last 24 hours."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    count(*) FILTER (WHERE score >= 5.0)::int AS total_trends,
                    coalesce(avg(score) FILTER (WHERE score >= 5.0), 0)::float AS avg_score,
                    count(*) FILTER (WHERE early_trend_score > 0.3)::int AS early_signal_count
                FROM news_group
                WHERE created_at > now() - interval '24 hours'
                """,
            )

            news_count = await conn.fetchval(
                """
                SELECT count(*)::int
                FROM news_article
                WHERE publish_time > now() - interval '24 hours'
                """,
            )

            cat_rows = await conn.fetch(
                """
                SELECT category, count(*)::int AS cnt
                FROM news_group
                WHERE score >= 5.0
                  AND created_at > now() - interval '24 hours'
                GROUP BY category
                ORDER BY cnt DESC
                """,
            )

            category_counts = {r["category"]: r["cnt"] for r in cat_rows}
            top_category = cat_rows[0]["category"] if cat_rows else None

            return {
                "total_trends": row["total_trends"],
                "total_news": news_count or 0,
                "avg_score": round(row["avg_score"], 1),
                "top_category": top_category,
                "early_signal_count": row["early_signal_count"],
                "category_counts": category_counts,
            }
    except Exception as exc:
        logger.error("fetch_dashboard_summary_failed", error=str(exc))
        raise
