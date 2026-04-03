"""Scheduled job: recalculate early_trend_score for active news groups (15-min cycle)."""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

_ACTIVE_WINDOW_HOURS = 48
_MAX_ARTICLES_PER_GROUP = 10.0


async def run_early_trend_update(pool: asyncpg.Pool) -> int:
    """Recalculate early_trend_score for news groups active in the last 48 hours.

    Formula (same as pipeline._compute_early_trend_score):
        velocity = min(1.0, article_count / 10)
        source_diversity = unique_sources / article_count
        recency = max(0.0, 1.0 - newest_hours_ago / 48.0)
        score = 0.4 * velocity + 0.3 * source_diversity + 0.3 * recency

    Returns the number of groups updated.
    """
    try:
        async with pool.acquire() as conn:
            groups = await conn.fetch(
                """
                SELECT ng.id,
                       COUNT(na.id)::int AS article_count,
                       COUNT(DISTINCT na.source)::int AS unique_sources,
                       MAX(na.publish_time) AS newest_publish_time
                FROM news_group ng
                JOIN news_article na ON na.group_id = ng.id
                WHERE ng.created_at > now() - INTERVAL '48 hours'
                GROUP BY ng.id
                """,
            )

        if not groups:
            logger.info("early_trend_update_skip", reason="no_active_groups")
            return 0

        now = datetime.now(tz=timezone.utc)
        updated = 0

        async with pool.acquire() as conn:
            for row in groups:
                try:
                    article_count = row["article_count"]
                    unique_sources = row["unique_sources"]
                    newest_time = row["newest_publish_time"]

                    velocity = min(1.0, article_count / _MAX_ARTICLES_PER_GROUP)

                    source_diversity = unique_sources / max(article_count, 1)

                    if newest_time and newest_time.tzinfo:
                        hours_ago = (now - newest_time).total_seconds() / 3600
                    else:
                        hours_ago = float(_ACTIVE_WINDOW_HOURS)
                    recency = max(0.0, 1.0 - (hours_ago / _ACTIVE_WINDOW_HOURS))

                    score = round(
                        0.4 * velocity + 0.3 * source_diversity + 0.3 * recency,
                        4,
                    )

                    await conn.execute(
                        "UPDATE news_group SET early_trend_score = $1 WHERE id = $2",
                        score,
                        row["id"],
                    )
                    updated += 1
                except Exception as exc:
                    logger.warning(
                        "early_trend_update_row_error",
                        error=str(exc),
                    )
                    continue

        logger.info(
            "early_trend_update_complete",
            total_groups=len(groups),
            updated=updated,
        )
        return updated
    except Exception as exc:
        logger.error("early_trend_update_failed", error=str(exc))
        raise
