"""Scheduled job: recalculate early_trend_score for active news groups (5-min cycle)."""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
import structlog

from backend.processor.algorithms.external_trends import verify_external_trends

logger = structlog.get_logger(__name__)

_ACTIVE_WINDOW_HOURS = 48
_ACCELERATION_DIVISOR = 5.0  # 5x acceleration → max velocity (1.0)
_MIN_HOURLY_AVG = 0.1  # Floor to avoid division by zero


async def run_early_trend_update(pool: asyncpg.Pool) -> int:
    """Recalculate early_trend_score for news groups active in the last 48 hours.

    Momentum-based formula:
        acceleration = cnt_1h / max(hourly_avg_24h, 0.1)
        momentum_velocity = min(1.0, acceleration / 5.0)
        source_diversity = unique_sources / article_count
        recency = max(0.0, 1.0 - newest_hours_ago / 48.0)
        burst = min(1.0, burst_score)
        score = 0.3 * momentum_velocity + 0.25 * burst
               + 0.25 * source_diversity + 0.2 * recency

    Returns the number of groups updated.
    """
    try:
        async with pool.acquire() as conn:
            groups = await conn.fetch(
                """
                SELECT ng.id,
                       ng.burst_score,
                       ng.keywords,
                       ng.locale,
                       COUNT(na.id)::int AS article_count,
                       COUNT(DISTINCT na.source)::int AS unique_sources,
                       MAX(na.publish_time) AS newest_publish_time,
                       COUNT(*) FILTER (
                           WHERE na.publish_time > now() - INTERVAL '1 hour'
                       )::int AS cnt_1h,
                       COUNT(*) FILTER (
                           WHERE na.publish_time > now() - INTERVAL '24 hours'
                       )::int AS cnt_24h
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

                    # Momentum velocity: recent 1h rate vs 24h average
                    cnt_1h = row["cnt_1h"]
                    cnt_24h = row["cnt_24h"]
                    hourly_avg = cnt_24h / 24.0
                    acceleration = cnt_1h / max(hourly_avg, _MIN_HOURLY_AVG)
                    momentum_velocity = min(1.0, acceleration / _ACCELERATION_DIVISOR)

                    source_diversity = unique_sources / max(article_count, 1)

                    if newest_time and newest_time.tzinfo:
                        hours_ago = (now - newest_time).total_seconds() / 3600
                    else:
                        hours_ago = float(_ACTIVE_WINDOW_HOURS)
                    recency = max(0.0, 1.0 - (hours_ago / _ACTIVE_WINDOW_HOURS))

                    burst = min(1.0, row["burst_score"] or 0.0)

                    score = round(
                        0.3 * momentum_velocity
                        + 0.25 * burst
                        + 0.25 * source_diversity
                        + 0.2 * recency,
                        4,
                    )

                    # Single-source guard + small cluster cap
                    if unique_sources < 2:
                        score = 0.0
                    elif article_count < 3:
                        score = min(score, 0.3)

                    # External trend cross-validation boost
                    if score > 0.0:
                        keywords = row["keywords"] or []
                        locale = row["locale"] or "ko"
                        external_boost = await verify_external_trends(pool, keywords, locale=locale)
                        score = round(min(1.0, score * external_boost), 4)

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
