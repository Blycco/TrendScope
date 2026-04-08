"""GET /api/v1/trends/early/pro — Pro+ gated early trends with burst_z + sentiment_badge."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from backend.api.schemas.trends import TrendItem, TrendListResponse
from backend.auth.dependencies import CurrentUser, require_plan
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode
from backend.db.queries.trends import encode_cursor, fetch_early_trends

router = APIRouter(tags=["trends"])
logger = structlog.get_logger(__name__)


@router.get("/trends/early/pro", response_model=TrendListResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to fetch early trends",
    status_code=500,
    log_event="early_trends_pro_fetch_failed",
)
async def list_early_trends_pro(
    request: Request,
    locale: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_plan("pro", status_code=402)),  # noqa: B008
) -> Response:
    """Pro+ gated early trends with full burst_z and sentiment_badge data."""
    pool = request.app.state.db_pool
    rows = await fetch_early_trends(pool, locale=locale, limit=limit, cursor=cursor)

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
