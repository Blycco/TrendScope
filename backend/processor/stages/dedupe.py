"""Stage 1: Deduplicate articles via DedupeFilter. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from typing import Any

import structlog

from backend.processor.shared.dedupe_filter import is_duplicate

logger = structlog.get_logger(__name__)


async def stage_dedupe(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 1: Filter duplicates via DedupeFilter."""
    result: list[dict[str, Any]] = []
    for article in articles:
        try:
            is_dup = await is_duplicate(
                url=article.get("url", ""),
                title=article.get("title", ""),
                body=article.get("body", ""),
            )
            if not is_dup:
                result.append(article)
        except Exception as exc:
            logger.warning("pipeline_dedupe_error", url=article.get("url", "?"), error=str(exc))
            result.append(article)
    return result
