"""Stage 3: Filter spam articles. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from typing import Any

import structlog

from backend.processor.shared.spam_filter import classify_spam

logger = structlog.get_logger(__name__)


def stage_spam_filter(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 3: Filter spam articles."""
    result: list[dict[str, Any]] = []
    for article in articles:
        try:
            text = f"{article.get('title', '')} {article.get('body', '')}"
            spam_result = classify_spam(text)
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
            logger.warning("pipeline_spam_error", url=article.get("url", "?"), error=str(exc))
            result.append(article)
    return result
