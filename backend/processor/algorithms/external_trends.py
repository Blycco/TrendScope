"""External trend cross-validation — boost scores confirmed by Google Trends + Naver DataLab."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

_EXTERNAL_PLATFORMS = ("google_trends", "naver_datalab")
_SNAPSHOT_WINDOW_HOURS = 24

# Multiplier by number of matching external platforms
_BOOST_MAP: dict[int, float] = {
    0: 1.0,
    1: 1.1,
    2: 1.3,
}


async def verify_external_trends(
    db_pool: asyncpg.Pool,
    keywords: list[str],
    locale: str = "ko",
) -> float:
    """Return a score multiplier based on external trend signal matching.

    Cross-references cluster keywords against sns_trend table for
    google_trends and naver_datalab platforms (last 24 hours).

    Returns:
        Multiplier in [1.0, 1.3] based on number of matching platforms.
    """
    if not keywords:
        return 1.0

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COUNT(DISTINCT platform) AS platform_count
                FROM sns_trend
                WHERE keyword = ANY($1::text[])
                  AND locale = $2
                  AND platform = ANY($3::text[])
                  AND snapshot_at > NOW() - INTERVAL '24 hours'
                """,
                keywords,
                locale,
                list(_EXTERNAL_PLATFORMS),
            )

        platform_count = row["platform_count"] if row else 0
        boost = _BOOST_MAP.get(platform_count, 1.3)

        if boost > 1.0:
            logger.debug(
                "external_trend_boost",
                keywords_sample=keywords[:3],
                locale=locale,
                platform_count=platform_count,
                boost=boost,
            )

        return boost
    except Exception as exc:
        logger.warning("external_trend_verify_failed", error=str(exc))
        return 1.0
