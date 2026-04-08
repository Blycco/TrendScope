"""DB query layer for keyword graph. (RULE 02: asyncpg $1,$2 only)"""

from __future__ import annotations

import asyncpg
import structlog

from backend.processor.shared.keyword_extractor import extract_keywords

logger = structlog.get_logger(__name__)


async def fetch_group_article_keywords(
    pool: asyncpg.Pool,
    group_id: str,
    limit: int = 100,
) -> list[tuple[str, list[str]]]:
    """Fetch articles for a group and extract keywords from each body.

    Returns:
        List of (article_id, keyword_terms) tuples.
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, body FROM news_article"
                " WHERE group_id = $1::uuid"
                " ORDER BY publish_time DESC LIMIT $2",
                group_id,
                limit,
            )
    except Exception as exc:
        logger.error("fetch_group_articles_failed", group_id=group_id, error=str(exc))
        raise

    results: list[tuple[str, list[str]]] = []
    for row in rows:
        body = row["body"] or ""
        if not body.strip():
            continue
        keywords = extract_keywords(body, top_k=20, use_bigrams=False)
        terms = [kw.term for kw in keywords]
        if terms:
            results.append((str(row["id"]), terms))

    logger.info(
        "group_article_keywords_extracted",
        group_id=group_id,
        article_count=len(rows),
        extracted_count=len(results),
    )
    return results
