"""GET /api/v1/trends/compare — batch timeline comparison for Pro+ users."""

from __future__ import annotations

import asyncio
import uuid

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from backend.api.schemas.compare import (
    CompareTimelineItem,
    CompareTimelineResponse,
)
from backend.api.schemas.trends import TimelinePoint
from backend.auth.dependencies import CurrentUser, require_plan
from backend.common.errors import ErrorCode, error_response
from backend.db.queries.trends import fetch_trend_detail, fetch_trend_timeline
from backend.processor.shared.cache_manager import get_cached, set_cached

router = APIRouter(tags=["compare"])
logger = structlog.get_logger(__name__)

# Interval -> (bucket_minutes, range_minutes)
_INTERVAL_MAP: dict[str, tuple[int, int]] = {
    "15m": (15, 360),
    "30m": (30, 720),
    "1h": (60, 1440),
    "6h": (360, 10080),
    "24h": (1440, 43200),
    "7d": (10080, 129600),
}
_CACHE_TTL: dict[str, int] = {
    "15m": 60,
    "30m": 60,
    "1h": 180,
    "6h": 180,
    "24h": 300,
    "7d": 300,
}


def _parse_ids(ids: str) -> list[str]:
    """Parse and validate comma-separated UUIDs. Returns list of UUID strings."""
    raw = [s.strip() for s in ids.split(",") if s.strip()]
    validated: list[str] = []
    for raw_id in raw:
        try:
            uuid.UUID(raw_id)
        except ValueError as exc:
            raise ValueError(f"Invalid UUID: {raw_id}") from exc
        validated.append(raw_id)
    return validated


@router.get("/trends/compare", response_model=CompareTimelineResponse)
async def compare_trends(
    request: Request,
    ids: str = Query(description="Comma-separated group UUIDs (2-5)"),
    interval: str = Query(
        default="1h",
        pattern="^(15m|30m|1h|6h|24h|7d)$",
    ),
    current_user: CurrentUser = Depends(require_plan("pro")),  # noqa: B008
) -> Response:
    """Return overlapping timelines for 2-5 trend groups (Pro+ only)."""
    try:
        parsed_ids = _parse_ids(ids)
    except ValueError:
        return error_response(
            ErrorCode.VALIDATION_ERROR,
            "One or more IDs are not valid UUIDs",
            status_code=400,
        )

    if len(parsed_ids) < 2 or len(parsed_ids) > 5:
        return error_response(
            ErrorCode.VALIDATION_ERROR,
            "Provide between 2 and 5 trend IDs",
            status_code=400,
        )

    # Cache key uses sorted IDs for deterministic key regardless of param order
    sorted_key = ",".join(sorted(parsed_ids))
    cache_key = f"compare:{sorted_key}:{interval}"
    cached = await get_cached(cache_key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    bucket_minutes, range_minutes = _INTERVAL_MAP[interval]
    pool = request.app.state.db_pool

    try:
        # Fetch details and timelines in parallel
        detail_tasks = [fetch_trend_detail(pool, group_id=gid) for gid in parsed_ids]
        timeline_tasks = [
            fetch_trend_timeline(
                pool,
                group_id=gid,
                interval_minutes=bucket_minutes,
                range_minutes=range_minutes,
            )
            for gid in parsed_ids
        ]
        all_results = await asyncio.gather(*detail_tasks, *timeline_tasks, return_exceptions=True)
    except Exception as exc:
        logger.error("compare_fetch_failed", error=str(exc))
        return error_response(
            ErrorCode.DB_ERROR,
            "Failed to fetch comparison data",
            status_code=500,
        )

    n = len(parsed_ids)
    details = all_results[:n]
    timelines = all_results[n:]

    items: list[CompareTimelineItem] = []
    for i, gid in enumerate(parsed_ids):
        detail = details[i]
        timeline_rows = timelines[i]

        if isinstance(detail, Exception) or isinstance(timeline_rows, Exception):
            logger.error("compare_partial_failure", group_id=gid)
            continue

        title = detail["group"]["title"] if detail else gid
        points = [
            TimelinePoint(
                timestamp=row["bucket_start"],
                article_count=row["article_count"],
                source_count=row["source_count"],
            )
            for row in (timeline_rows or [])
        ]
        items.append(CompareTimelineItem(group_id=gid, title=title, points=points))

    body = CompareTimelineResponse(interval=interval, trends=items)
    body_bytes = body.model_dump_json().encode()
    await set_cached(cache_key, body_bytes, _CACHE_TTL.get(interval, 180))

    return Response(content=body_bytes, media_type="application/json")
