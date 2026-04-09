"""Stage 4: Extract keywords for each article — DB-driven stop words & params.

(RULE 03: async/await, RULE 06: try/except + structlog)
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from backend.processor.shared.keyword_extractor import Keyword, extract_keywords

logger = structlog.get_logger(__name__)


async def stage_extract_keywords(
    articles: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> list[dict[str, Any]]:
    """Stage 4: Extract keywords — one DB round-trip per batch for config/stop words."""
    try:
        from backend.processor.shared.config_loader import (
            get_setting,
            get_stopwords,
        )

        stop_words_ko = await get_stopwords(db_pool, "ko")
        stop_words_en = await get_stopwords(db_pool, "en")
        title_boost = float(await get_setting(db_pool, "keyword.title_boost", 2.0))
        body_max_chars = int(await get_setting(db_pool, "keyword.body_max_chars", 500))
        top_k = int(await get_setting(db_pool, "keyword.top_k", 10))
    except Exception as exc:
        logger.warning("keyword_stage_config_load_failed", error=str(exc))
        stop_words_ko = None
        stop_words_en = None
        title_boost = 2.0
        body_max_chars = 500
        top_k = 10

    for article in articles:
        try:
            keywords: list[Keyword] = extract_keywords(
                title=article.get("title", ""),
                body=article.get("body", ""),
                top_k=top_k,
                title_boost=title_boost,
                body_max_chars=body_max_chars,
                stop_words_ko=stop_words_ko,
                stop_words_en=stop_words_en,
            )
            article["keywords"] = [kw.term for kw in keywords]
            article["keyword_importance"] = keywords[0].score if keywords else 0.0
        except Exception as exc:
            logger.warning("pipeline_keyword_error", url=article.get("url", "?"), error=str(exc))
            article["keywords"] = []
            article["keyword_importance"] = 0.0

    return articles
