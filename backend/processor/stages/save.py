"""Stage 7: Save scored clusters to DB. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def stage_save(
    scored_clusters: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> int:
    """Stage 7: Save scored clusters to news_group and update news_article."""
    saved = 0
    for item in scored_clusters:
        try:
            group_id = await db_pool.fetchval(
                "INSERT INTO news_group "
                "(category, locale, title, summary, score, early_trend_score, keywords) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
                item["category"],
                item["locale"],
                item["title"],
                item.get("summary"),
                item["score"],
                item.get("early_trend_score", 0.0),
                item["keywords"],
            )

            articles: list[dict[str, Any]] = item.get("articles", [])
            for article in articles:
                url_hash = article.get("url_hash", "")
                if url_hash:
                    await db_pool.execute(
                        "UPDATE news_article SET group_id = $1 WHERE url_hash = $2",
                        group_id,
                        url_hash,
                    )

            saved += 1
        except Exception as exc:
            logger.warning(
                "pipeline_save_error",
                title=item.get("title", "?"),
                error=str(exc),
            )
            continue
    return saved
