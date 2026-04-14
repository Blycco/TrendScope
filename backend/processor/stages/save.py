"""Stage 7: Save scored clusters to DB. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from backend.processor.shared.cache_manager import publish

logger = structlog.get_logger(__name__)


async def stage_save(
    scored_clusters: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> int:
    """Stage 7: Save scored clusters to news_group and update news_article.

    Uses batch INSERT for groups and batch UPDATE for article assignments
    to reduce DB round-trips.
    """
    if not scored_clusters:
        return 0

    saved = 0
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Batch INSERT all groups
                group_rows = await conn.fetch(
                    "INSERT INTO news_group "
                    "(category, locale, title, summary, score, "
                    "early_trend_score, keywords, burst_score, "
                    "cross_platform_multiplier, external_trend_boost, growth_type) "
                    "SELECT * FROM unnest($1::text[], $2::text[], $3::text[], $4::text[], "
                    "$5::float8[], $6::float8[], $7::text[][], $8::float8[], "
                    "$9::float8[], $10::float8[], $11::text[]) "
                    "RETURNING id",
                    [c["category"] for c in scored_clusters],
                    [c["locale"] for c in scored_clusters],
                    [c["title"] for c in scored_clusters],
                    [c.get("summary") for c in scored_clusters],
                    [c["score"] for c in scored_clusters],
                    [c.get("early_trend_score", 0.0) for c in scored_clusters],
                    [c["keywords"] for c in scored_clusters],
                    [c.get("burst_score", 0.0) for c in scored_clusters],
                    [c.get("cross_platform_multiplier", 1.0) for c in scored_clusters],
                    [c.get("external_trend_boost", 1.0) for c in scored_clusters],
                    [c.get("growth_type", "unknown") for c in scored_clusters],
                )

                # Collect all article UPDATE pairs
                update_pairs: list[tuple[Any, str]] = []
                for group_row, cluster in zip(group_rows, scored_clusters, strict=True):
                    group_id = group_row["id"]
                    for article in cluster.get("articles", []):
                        url_hash = article.get("url_hash", "")
                        if url_hash:
                            update_pairs.append((group_id, url_hash))

                # Batch UPDATE articles with executemany
                if update_pairs:
                    await conn.executemany(
                        "UPDATE news_article SET group_id = $1 WHERE url_hash = $2",
                        update_pairs,
                    )

                saved = len(group_rows)

        # Publish new group IDs outside transaction (fire-and-forget)
        for group_row in group_rows:
            try:
                await publish("trends:new", str(group_row["id"]))
            except Exception as pub_exc:
                logger.warning("publish_after_save_failed", error=str(pub_exc))

    except Exception as exc:
        logger.warning("pipeline_batch_save_error", error=str(exc))
        # Fallback to individual saves
        saved = await _save_individually(scored_clusters, db_pool)

    return saved


async def _save_individually(
    scored_clusters: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> int:
    """Fallback: save clusters one-by-one if batch save fails."""
    saved = 0
    for item in scored_clusters:
        try:
            group_id = await db_pool.fetchval(
                "INSERT INTO news_group "
                "(category, locale, title, summary, score, "
                "early_trend_score, keywords, burst_score, "
                "cross_platform_multiplier, external_trend_boost, growth_type) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) RETURNING id",
                item["category"],
                item["locale"],
                item["title"],
                item.get("summary"),
                item["score"],
                item.get("early_trend_score", 0.0),
                item["keywords"],
                item.get("burst_score", 0.0),
                item.get("cross_platform_multiplier", 1.0),
                item.get("external_trend_boost", 1.0),
                item.get("growth_type", "unknown"),
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
