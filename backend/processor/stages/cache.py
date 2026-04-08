"""Stage 8: Warm feed cache after pipeline run. (RULE 06: try/except + structlog)"""

from __future__ import annotations

import json
from typing import Any

import structlog

from backend.processor.shared.cache_manager import set_cached

logger = structlog.get_logger(__name__)

_FEED_CACHE_TTL = 300  # 5 minutes


async def stage_warm_cache(scored_clusters: list[dict[str, Any]]) -> None:
    """Stage 8: Warm cache for feed keys."""
    try:
        by_feed: dict[str, list[dict[str, Any]]] = {}
        for item in scored_clusters:
            key = f"feed:{item['category']}:{item['locale']}"
            by_feed.setdefault(key, []).append(
                {
                    "title": item["title"],
                    "score": item["score"],
                    "keywords": item["keywords"],
                }
            )

        for cache_key, items in by_feed.items():
            payload = json.dumps(items, ensure_ascii=False, default=str).encode("utf-8")
            await set_cached(cache_key, payload, _FEED_CACHE_TTL)

        logger.debug("pipeline_cache_warmed", keys=len(by_feed))
    except Exception as exc:
        logger.warning("pipeline_cache_warm_error", error=str(exc))
