"""Stage 2: Normalize article title and body text. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from typing import Any

import structlog

from backend.processor.shared.text_normalizer import normalize_text, normalize_title

logger = structlog.get_logger(__name__)


def stage_normalize(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 2: Normalize title and body text."""
    result: list[dict[str, Any]] = []
    for article in articles:
        try:
            article["title"] = normalize_title(article.get("title", ""))
            article["body"] = normalize_text(article.get("body", ""))
            if article["title"]:
                result.append(article)
        except Exception as exc:
            logger.warning("pipeline_normalize_error", url=article.get("url", "?"), error=str(exc))
            continue
    return result
