"""Stage 4: Extract keywords for each article. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from typing import Any

import structlog

from backend.processor.shared.keyword_extractor import Keyword, extract_keywords

logger = structlog.get_logger(__name__)


def stage_extract_keywords(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 4: Extract keywords for each article."""
    for article in articles:
        try:
            text = f"{article.get('title', '')} {article.get('body', '')}"
            keywords: list[Keyword] = extract_keywords(text, top_k=10)
            article["keywords"] = [kw.term for kw in keywords]
            article["keyword_importance"] = keywords[0].score if keywords else 0.0
        except Exception as exc:
            logger.warning("pipeline_keyword_error", url=article.get("url", "?"), error=str(exc))
            article["keywords"] = []
            article["keyword_importance"] = 0.0
    return articles
