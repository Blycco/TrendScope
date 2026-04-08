"""Stage 6.5: Generate AI summary for each cluster. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from backend.processor.shared.ai_config import get_ai_config
from backend.processor.shared.ai_summarizer import summarize

logger = structlog.get_logger(__name__)

_SUMMARY_PROMPT = (
    "Summarize the following news articles into exactly 3 concise sentences in Korean. "
    "Focus on what happened, who is involved, and why it matters."
)


async def stage_summarize(
    scored_clusters: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> None:
    """Stage 6.5: Generate AI summary for each cluster."""
    try:
        config = await get_ai_config(db_pool)
    except Exception as exc:
        logger.warning("pipeline_ai_config_failed", error=str(exc))
        return

    for item in scored_clusters:
        try:
            articles: list[dict[str, Any]] = item.get("articles", [])
            combined = "\n\n".join(
                f"[{a.get('source', '')}] {a.get('title', '')}\n{a.get('body', '')[:500]}"
                for a in articles[:5]
            )
            if not combined.strip():
                item["summary"] = None
                continue

            summary_text, degraded = await summarize(combined, _SUMMARY_PROMPT, config, db_pool)
            item["summary"] = summary_text.strip() if summary_text else None
            if degraded:
                logger.debug("pipeline_summary_degraded", title=item.get("title", "?"))
        except Exception as exc:
            logger.warning("pipeline_summary_error", title=item.get("title", "?"), error=str(exc))
            item["summary"] = None
