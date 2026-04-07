"""GET /api/v1/trends, /api/v1/trends/early, and /api/v1/trends/export endpoints."""

from __future__ import annotations

import csv
import io
import json

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response, StreamingResponse

from backend.api.schemas.trends import (
    TimelinePoint,
    TrendArticleItem,
    TrendDetailResponse,
    TrendItem,
    TrendListResponse,
    TrendTimelineResponse,
)
from backend.auth.dependencies import PLAN_LEVEL, CurrentUser, require_plan
from backend.common.errors import ErrorCode, error_response
from backend.db.queries.trends import (
    encode_cursor,
    fetch_early_trends,
    fetch_related_trends,
    fetch_trend_detail,
    fetch_trend_timeline,
    fetch_trends,
)
from backend.processor.algorithms.trend_status import classify_trend_status
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
            article_count=row["article_count"],
            direction=row["direction"],
            status=classify_trend_status(row["score"], None, row["direction"]),
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
            article_count=row["article_count"],
            direction=row["direction"],
            status=classify_trend_status(row["score"], None, row["direction"]),
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
            article_count=row["article_count"],
            direction=row["direction"],
            status=classify_trend_status(row["score"], None, row["direction"]),
        )
        for row in rows
    ]

    next_cursor: str | None = None
    if len(rows) == limit:
        last = rows[-1]
        next_cursor = encode_cursor(last["early_trend_score"], str(last["id"]))

    response_body = TrendListResponse(items=items, next_cursor=next_cursor, total=len(items))
    return Response(content=response_body.model_dump_json().encode(), media_type="application/json")


# NOTE: This route must be AFTER /trends/export and /trends/early to avoid
# "export" and "early" being captured as {group_id}.
@router.get("/trends/{group_id}", response_model=TrendDetailResponse)
async def get_trend_detail(
    group_id: str,
    request: Request,
) -> TrendDetailResponse:
    """Get trend group detail with associated articles."""
    try:
        pool = request.app.state.db_pool
        data = await fetch_trend_detail(pool, group_id=group_id)
    except Exception as exc:
        logger.error("trend_detail_fetch_failed", error=str(exc))
        return error_response(ErrorCode.DB_ERROR, "Failed to fetch trend detail", status_code=500)

    if not data:
        return error_response(ErrorCode.NOT_FOUND, "Trend not found", status_code=404)

    group = data["group"]
    articles = [
        TrendArticleItem(
            id=str(a["id"]),
            title=a["title"],
            url=a["url"],
            source=a["source"],
            publish_time=a["publish_time"],
            body_snippet=(a["body"] or "")[:200] or None,
        )
        for a in data["articles"]
    ]
    return TrendDetailResponse(
        id=str(group["id"]),
        title=group["title"],
        category=group["category"],
        summary=group["summary"],
        score=group["score"],
        early_trend_score=group["early_trend_score"],
        keywords=list(group["keywords"] or []),
        created_at=group["created_at"],
        direction=group["direction"],
        articles=articles,
    )


# Interval → (bucket_minutes, range_minutes)
_INTERVAL_MAP: dict[str, tuple[int, int]] = {
    "15m": (15, 360),
    "30m": (30, 720),
    "1h": (60, 1440),
    "6h": (360, 10080),
    "24h": (1440, 43200),
    "7d": (10080, 129600),
}
_TIMELINE_CACHE_TTL: dict[str, int] = {
    "15m": 60,
    "30m": 60,
    "1h": 180,
    "6h": 180,
    "24h": 300,
    "7d": 300,
}


@router.get(
    "/trends/{group_id}/timeline",
    response_model=TrendTimelineResponse,
)
async def get_trend_timeline(
    group_id: str,
    request: Request,
    interval: str = Query(
        default="1h",
        pattern="^(15m|30m|1h|6h|24h|7d)$",
    ),
) -> Response:
    """Return article arrival timeline for a trend group."""
    cache_key = f"timeline:{group_id}:{interval}"
    cached = await get_cached(cache_key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    bucket_minutes, range_minutes = _INTERVAL_MAP[interval]

    try:
        pool = request.app.state.db_pool
        rows = await fetch_trend_timeline(
            pool,
            group_id=group_id,
            interval_minutes=bucket_minutes,
            range_minutes=range_minutes,
        )
    except Exception as exc:
        logger.error(
            "trend_timeline_fetch_failed",
            group_id=group_id,
            error=str(exc),
        )
        return error_response(
            ErrorCode.DB_ERROR,
            "Failed to fetch trend timeline",
            status_code=500,
        )

    points = [
        TimelinePoint(
            timestamp=row["bucket_start"],
            article_count=row["article_count"],
            source_count=row["source_count"],
        )
        for row in rows
    ]
    body = TrendTimelineResponse(
        group_id=group_id,
        interval=interval,
        points=points,
    )
    body_bytes = body.model_dump_json().encode()
    await set_cached(
        cache_key,
        body_bytes,
        _TIMELINE_CACHE_TTL.get(interval, 180),
    )
    return Response(
        content=body_bytes,
        media_type="application/json",
    )
