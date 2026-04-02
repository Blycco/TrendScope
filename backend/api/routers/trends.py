"""GET /api/v1/trends, /api/v1/trends/early, and /api/v1/trends/export endpoints."""

from __future__ import annotations

import csv
import io
import json

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response, StreamingResponse

from backend.api.schemas.trends import TrendItem, TrendListResponse
from backend.auth.dependencies import PLAN_LEVEL, CurrentUser, require_plan
from backend.common.errors import ErrorCode, error_response
from backend.db.queries.trends import (
    encode_cursor,
    fetch_early_trends,
    fetch_related_trends,
    fetch_trends,
)
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
    since: int | None = Query(default=None, description="Filter by hours (e.g. 1, 6, 24)"),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> Response:
    """Return trend feed from news_group ordered by score DESC."""
    cache_key = _trend_cache_key(category, locale)

    # Only use cache for first page (no cursor, no time filter)
    if not cursor and not since:
        cached = await get_cached(cache_key)
        if cached is not None:
            return Response(content=cached, media_type="application/json")

    try:
        pool = request.app.state.db_pool

        logger.info("trends_request", category=category, locale=locale, since=since, cursor=cursor)

        rows = await fetch_trends(
            pool, category=category, locale=locale, since_hours=since, limit=limit, cursor=cursor
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


@router.get("/trends/{trend_id}/related", response_model=TrendListResponse)
async def list_related_trends(
    trend_id: str,
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
) -> Response:
    """Return trends in the same category as the given trend, ordered by score DESC.

    Used by TrendMap to render related trend nodes. No authentication required.
    """
    try:
        pool = request.app.state.db_pool
        rows = await fetch_related_trends(pool, trend_id=trend_id, limit=limit)
    except Exception as exc:
        logger.error("related_trends_fetch_failed", trend_id=trend_id, error=str(exc))
        return error_response(ErrorCode.DB_ERROR, "Failed to fetch related trends", status_code=500)

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
    response_body = TrendListResponse(items=items, next_cursor=None, total=len(items))
    return Response(content=response_body.model_dump_json().encode(), media_type="application/json")


@router.get("/trends/export")
async def export_trends(
    request: Request,
    format: str = Query(default="csv", pattern="^(csv|pdf)$"),
    category: str | None = Query(default=None),
    locale: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_plan("pro")),  # noqa: B008
) -> Response:
    """Export trend data as CSV (Pro+) or PDF (Business+).

    Plan gates:
    - Free: 403
    - Pro: CSV only
    - Business+: CSV + PDF
    """
    user_level = PLAN_LEVEL.get(current_user.plan, 0)

    if format == "pdf" and user_level < PLAN_LEVEL["business"]:
        return error_response(
            ErrorCode.PLAN_GATE,
            "PDF export requires Business plan or above",
            detail=json.dumps(
                {
                    "message_key": "error.plan_upgrade_required",
                    "upgrade_url": "/pricing",
                    "required_plan": "business",
                }
            ),
            status_code=403,
        )

    try:
        pool = request.app.state.db_pool
        logger.info(
            "trends_export_request",
            user_id=current_user.user_id,
            plan=current_user.plan,
            format=format,
            category=category,
            locale=locale,
        )
        rows = await fetch_trends(pool, category=category, locale=locale, limit=limit)
    except Exception as exc:
        logger.error("trends_export_fetch_failed", error=str(exc))
        return error_response(
            ErrorCode.DB_ERROR, "Failed to fetch trends for export", status_code=500
        )

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "title",
                "category",
                "score",
                "early_trend_score",
                "keywords",
                "created_at",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["title"],
                    row["category"],
                    row["score"],
                    row["early_trend_score"],
                    "|".join(row["keywords"] or []),
                    row["created_at"].isoformat() if row["created_at"] else "",
                ]
            )
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=trends.csv"},
        )

    # PDF: Business+ only (already gate-checked above)
    try:
        from backend.api.utils.pdf_export import generate_trends_pdf

        pdf_bytes = generate_trends_pdf(rows)
    except Exception as exc:
        logger.error("pdf_generation_failed", error=str(exc))
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            "Failed to generate PDF report",
            status_code=500,
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=trends.pdf"},
    )


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
