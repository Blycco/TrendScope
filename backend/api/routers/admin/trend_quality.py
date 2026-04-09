"""Admin trend quality monitoring endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog
from fastapi import APIRouter, Depends, Request

from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import log_audit
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode
from backend.processor.shared.cache_manager import get_cached, set_cached

router = APIRouter(prefix="/trend-quality", tags=["admin-trend-quality"])
logger = structlog.get_logger(__name__)

_PIPELINE_STATS_CACHE_TTL = 300  # 5 minutes
_TOP_TRENDS_CACHE_TTL = 60  # 1 minute


async def _fetch_pipeline_stats(pool: asyncpg.Pool) -> dict[str, Any]:
    """Query today's pipeline stats from DB."""
    try:
        async with pool.acquire() as conn:
            collected = await conn.fetchval(
                "SELECT COUNT(*) FROM news_article WHERE created_at >= CURRENT_DATE"
            )
            clustered = await conn.fetchval(
                "SELECT COUNT(*) FROM news_article"
                " WHERE group_id IS NOT NULL AND created_at >= CURRENT_DATE"
            )
            trends_created = await conn.fetchval(
                "SELECT COUNT(*) FROM news_group WHERE created_at >= CURRENT_DATE"
            )
        spam_filtered = max(0, int(collected or 0) - int(clustered or 0))
        return {
            "collected": int(collected or 0),
            "spam_filtered": spam_filtered,
            "clustered": int(clustered or 0),
            "trends_created": int(trends_created or 0),
            "filter_reasons": {"ad": 0, "obituary": 0, "other": spam_filtered},
        }
    except Exception as exc:
        logger.error("pipeline_stats_query_failed", error=str(exc))
        raise


async def _fetch_top_trends(pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Fetch top 10 trend groups by score."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ng.id::text, ng.title, ng.score, ng.burst_score,
                       ng.category, ng.locale, ng.created_at,
                       (SELECT COUNT(*) FROM news_article WHERE group_id = ng.id)::int
                           AS article_count
                FROM news_group ng
                WHERE ng.is_hidden = FALSE
                ORDER BY ng.score DESC
                LIMIT 10
                """  # noqa: S608
            )
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.error("top_trends_query_failed", error=str(exc))
        raise


@router.get("/pipeline-stats")
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to get pipeline stats",
    status_code=500,
    log_event="admin_pipeline_stats_failed",
)
async def get_pipeline_stats(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> dict[str, Any]:
    """Return today's pipeline stats (collected, spam_filtered, clustered, trends_created)."""
    cache_key = "admin:pipeline_stats"
    cached = await get_cached(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception as exc:
            logger.warning("pipeline_stats_cache_decode_failed", error=str(exc))

    pool: asyncpg.Pool = request.app.state.db_pool
    stats = await _fetch_pipeline_stats(pool)
    await set_cached(cache_key, json.dumps(stats), _PIPELINE_STATS_CACHE_TTL)
    return stats


@router.get("/top-trends")
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to get top trends",
    status_code=500,
    log_event="admin_top_trends_failed",
)
async def get_top_trends(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> dict[str, Any]:
    """Return top 10 trend groups by score with key metrics."""
    cache_key = "admin:top_trends"
    cached = await get_cached(cache_key)
    if cached:
        try:
            data = json.loads(cached)
            return {"trends": data}
        except Exception as exc:
            logger.warning("top_trends_cache_decode_failed", error=str(exc))

    pool: asyncpg.Pool = request.app.state.db_pool
    trends = await _fetch_top_trends(pool)
    serializable = [
        {
            **{k: v for k, v in t.items() if k != "created_at"},
            "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
        }
        for t in trends
    ]
    await set_cached(cache_key, json.dumps(serializable), _TOP_TRENDS_CACHE_TTL)
    return {"trends": serializable}


@router.post("/hide/{group_id}")
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to hide trend",
    status_code=500,
    log_event="admin_hide_trend_failed",
)
async def hide_trend(
    group_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> dict[str, str]:
    """Mark a news_group as hidden so it won't appear in the trend feed."""
    pool: asyncpg.Pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        updated = await conn.fetchval(
            "UPDATE news_group SET is_hidden = TRUE WHERE id = $1 RETURNING id",
            group_id,
        )
    if not updated:
        from backend.common.errors import http_error

        raise http_error(ErrorCode.NOT_FOUND, f"Trend group {group_id} not found", status_code=404)

    await log_audit(
        pool,
        user_id=str(current_user.id),
        action="trend_hide",
        target_type="news_group",
        target_id=group_id,
        ip_address=request.client.host if request.client else None,
    )
    logger.info("trend_hidden", group_id=group_id, admin_id=str(current_user.id))
    return {"status": "hidden", "group_id": group_id}
