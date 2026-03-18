"""GET /api/v1/trends and /api/v1/trends/early endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from backend.api.schemas.trends import TrendItem, TrendListResponse
from backend.common.errors import ErrorCode, error_response
from backend.db.queries.trends import encode_cursor, fetch_early_trends, fetch_trends
from backend.processor.shared.cache_manager import get_cached, set_cached

router = APIRouter(tags=["trends"])
logger = structlog.get_logger(__name__)

_CACHE_TTL = 180  # 3 minutes


def _trend_cache_key(category: str | None, locale: str | None) -> str:
    return f"feed:{category or 'all'}:{locale or 'all'}"


@router.get("/trends", response_model=TrendListResponse)
async def list_trends(
    request: Request,
    category: str | None = Query(default=None),
    locale: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> Response:
    """Return trend feed from news_group ordered by score DESC."""
    cache_key = _trend_cache_key(category, locale)

    # Only use cache for first page (no cursor)
    if not cursor:
        cached = await get_cached(cache_key)
        if cached is not None:
            return Response(content=cached, media_type="application/json")

    try:
        pool = request.app.state.db_pool

        # Quota stub: api_usage INSERT would go here (not enforced yet)
        logger.info("trends_request", category=category, locale=locale, cursor=cursor)

        rows = await fetch_trends(
            pool, category=category, locale=locale, limit=limit, cursor=cursor
        )
    except Exception as exc:
        logger.error("trends_fetch_failed", error=str(exc))
        return error_response(ErrorCode.DB_ERROR, "Failed to fetch trends", status_code=500)

    items = [
        TrendItem(
            id=str(row["id"]),
            title=row["title"],
            category=row["category"],
            score=row["score"],
            early_trend_score=row["early_trend_score"],
            keywords=list(row["keywords"] or []),
            created_at=row["created_at"],
        )
        for row in rows
    ]

    next_cursor: str | None = None
    if len(rows) == limit:
        last = rows[-1]
        next_cursor = encode_cursor(last["score"], str(last["id"]))

    response_body = TrendListResponse(items=items, next_cursor=next_cursor, total=len(items))
    body_bytes = response_body.model_dump_json().encode()

    if not cursor:
        await set_cached(cache_key, body_bytes, _CACHE_TTL)

    return Response(content=body_bytes, media_type="application/json")


@router.get("/trends/early", response_model=TrendListResponse)
async def list_early_trends(
    request: Request,
    locale: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> Response:
    """Return early trend feed ordered by early_trend_score DESC."""
    try:
        pool = request.app.state.db_pool
        rows = await fetch_early_trends(pool, locale=locale, limit=limit, cursor=cursor)
    except Exception as exc:
        logger.error("early_trends_fetch_failed", error=str(exc))
        return error_response(ErrorCode.DB_ERROR, "Failed to fetch early trends", status_code=500)

    items = [
        TrendItem(
            id=str(row["id"]),
            title=row["title"],
            category=row["category"],
            score=row["score"],
            early_trend_score=row["early_trend_score"],
            keywords=list(row["keywords"] or []),
            created_at=row["created_at"],
        )
        for row in rows
    ]

    next_cursor: str | None = None
    if len(rows) == limit:
        last = rows[-1]
        next_cursor = encode_cursor(last["early_trend_score"], str(last["id"]))

    response_body = TrendListResponse(items=items, next_cursor=next_cursor, total=len(items))
    return Response(content=response_body.model_dump_json().encode(), media_type="application/json")
