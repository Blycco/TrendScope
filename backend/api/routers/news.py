"""GET /api/v1/news endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from backend.api.schemas.trends import NewsItem, NewsListResponse
from backend.common.errors import ErrorCode, error_response
from backend.db.queries.trends import encode_cursor, fetch_news

router = APIRouter(tags=["news"])
logger = structlog.get_logger(__name__)


@router.get("/news", response_model=NewsListResponse)
async def list_news(
    request: Request,
    category: str | None = Query(default=None),
    locale: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    since: int | None = Query(default=None, description="Filter by hours (e.g. 1, 6, 24)"),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> Response:
    """Return news articles ordered by publish_time DESC, grouped by news_group."""
    try:
        pool = request.app.state.db_pool
        logger.info(
            "news_request",
            category=category,
            locale=locale,
            source_type=source_type,
            cursor=cursor,
        )
        rows = await fetch_news(
            pool,
            category=category,
            locale=locale,
            source_type=source_type,
            since_hours=since,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        logger.error("news_fetch_failed", error=str(exc))
        return error_response(ErrorCode.DB_ERROR, "Failed to fetch news", status_code=500)

    items = [
        NewsItem(
            id=str(row["id"]),
            title=row["title"],
            url=row["url"],
            source=row["source"],
            publish_time=row["publish_time"],
            summary=row["summary"],
            article_count=row.get("article_count", 1),
        )
        for row in rows
    ]

    next_cursor: str | None = None
    if len(rows) == limit:
        last = rows[-1]
        next_cursor = encode_cursor(last["publish_time"].timestamp(), str(last["id"]))

    response_body = NewsListResponse(items=items, next_cursor=next_cursor)
    return Response(content=response_body.model_dump_json().encode(), media_type="application/json")
