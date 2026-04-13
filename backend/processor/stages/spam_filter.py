"""Stage 3: Filter spam and non-trend (obituary) articles. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from backend.processor.shared.config_loader import get_filter_keywords, get_setting
from backend.processor.shared.spam_filter import SpamResult, classify_spam

logger = structlog.get_logger(__name__)

_NON_TREND_MIN_HITS_DEFAULT: int = 2


async def stage_spam_filter(
    articles: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> list[dict[str, Any]]:
    """Stage 3: Filter spam and non-trend articles.

    Loads spam keywords and thresholds from DB (via Redis cache) once per batch,
    then applies rule-based classification to each article.
    Obituary/non-trend articles are also removed based on DB-loaded keywords.
    """
    try:
        # Load config once per batch (all cached via Redis)
        url_threshold = float(await get_setting(db_pool, "spam.url_ratio_threshold", 0.3))
        kw_threshold = int(await get_setting(db_pool, "spam.keyword_threshold", 3))
        min_length = int(await get_setting(db_pool, "spam.min_content_length", 20))
        non_trend_min_hits = int(
            await get_setting(db_pool, "spam.non_trend_min_hits", _NON_TREND_MIN_HITS_DEFAULT)
        )

        ad_kw = await get_filter_keywords(db_pool, category="ad")
        gambling_kw = await get_filter_keywords(db_pool, category="gambling")
        adult_kw = await get_filter_keywords(db_pool, category="adult")
        spam_keywords: frozenset[str] | None = ad_kw | gambling_kw | adult_kw

        obituary_kw = await get_filter_keywords(db_pool, category="obituary")
    except Exception as exc:
        logger.warning("spam_stage_config_load_failed", error=str(exc))
        spam_keywords = None
        obituary_kw = frozenset()
        url_threshold = 0.3
        kw_threshold = 3
        min_length = 20
        non_trend_min_hits = _NON_TREND_MIN_HITS_DEFAULT

    result: list[dict[str, Any]] = []
    for article in articles:
        try:
            text = f"{article.get('title', '')} {article.get('body', '')}"

            # Obituary / non-trend check
            if obituary_kw:
                text_lower = text.lower()
                hits = sum(1 for kw in obituary_kw if kw in text_lower)
                if hits >= non_trend_min_hits:
                    logger.debug(
                        "pipeline_obituary_filtered",
                        url=article.get("url", "?"),
                        hits=hits,
                    )
                    continue

            spam_result: SpamResult = classify_spam(
                text,
                spam_keywords=spam_keywords,
                url_threshold=url_threshold,
                kw_threshold=kw_threshold,
                min_length=min_length,
            )
            if not spam_result.is_spam:
                result.append(article)
            else:
                logger.debug(
                    "pipeline_spam_filtered",
                    url=article.get("url", "?"),
                    confidence=spam_result.confidence,
                    reasons=spam_result.reasons,
                )
        except Exception as exc:
            logger.warning(
                "pipeline_spam_filtered_on_error",
                url=article.get("url", "?"),
                error=str(exc),
            )
    return result
