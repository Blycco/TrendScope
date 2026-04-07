"""Admin feed source CRUD + health monitoring endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, Query, Request

from backend.api.schemas.admin import (
    FeedHealthDashboardResponse,
    FeedHealthSummaryItem,
    FeedSourceBulkToggleRequest,
    FeedSourceCreateRequest,
    FeedSourceItem,
    FeedSourceListResponse,
    FeedSourceUpdateRequest,
)
from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import write_audit_log
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.feed_sources import (
    bulk_toggle_feed_sources,
    create_feed_source,
    delete_feed_source,
    get_feed_health_summary,
    get_feed_source,
    list_feed_sources,
    update_feed_source,
)

router = APIRouter(prefix="/feed-sources", tags=["admin-feed-sources"])
logger = structlog.get_logger(__name__)


def _row_to_item(row: object) -> FeedSourceItem:
    """Convert asyncpg Record to FeedSourceItem."""
    config_raw = row["config"]
    if isinstance(config_raw, str):
        config_dict = json.loads(config_raw)
    elif isinstance(config_raw, dict):
        config_dict = config_raw
    else:
        config_dict = {}

    return FeedSourceItem(
        id=row["id"],
        source_config_id=row["source_config_id"],
        source_type=row["source_type"],
        name=row["name"],
        url=row["url"],
        category=row["category"],
        locale=row["locale"],
        is_active=row["is_active"],
        priority=row["priority"],
        config=config_dict,
        health_status=row["health_status"],
        last_crawled_at=row["last_crawled_at"],
        last_success_at=row["last_success_at"],
        last_error=row["last_error"],
        last_error_at=row["last_error_at"],
        consecutive_failures=row["consecutive_failures"],
        avg_latency_ms=row["avg_latency_ms"],
        total_crawl_count=row["total_crawl_count"],
        total_error_count=row["total_error_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/health/summary", response_model=FeedHealthDashboardResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to get health summary",
    status_code=500,
    log_event="feed_health_summary_failed",
)
async def health_summary(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> FeedHealthDashboardResponse:
    """Aggregated health counts by source_type."""
    pool = request.app.state.db_pool
    rows = await get_feed_health_summary(pool)
    items = [
        FeedHealthSummaryItem(
            source_type=row["source_type"],
            total=row["total"],
            healthy=row["healthy"],
            degraded=row["degraded"],
            error=row["error"],
            unknown=row["unknown"],
        )
        for row in rows
    ]
    return FeedHealthDashboardResponse(
        summary=items,
        last_updated=datetime.now(tz=timezone.utc),
    )


@router.get("", response_model=FeedSourceListResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to list feeds",
    status_code=500,
    log_event="list_feeds_failed",
)
async def list_feeds(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
    source_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    category: str | None = Query(None),
    locale: str | None = Query(None),
    health_status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> FeedSourceListResponse:
    """List feed sources with filters and pagination."""
    pool = request.app.state.db_pool
    rows, total = await list_feed_sources(
        pool,
        source_type=source_type,
        is_active=is_active,
        category=category,
        locale=locale,
        health_status=health_status,
        search=search,
        page=page,
        page_size=page_size,
    )
    return FeedSourceListResponse(
        feeds=[_row_to_item(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{feed_id}", response_model=FeedSourceItem)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to get feed",
    status_code=500,
    log_event="get_feed_failed",
)
async def get_feed(
    feed_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> FeedSourceItem:
    """Get single feed source detail."""
    pool = request.app.state.db_pool
    row = await get_feed_source(pool, feed_id)
    if not row:
        raise http_error(ErrorCode.NOT_FOUND, "Feed not found", status_code=404)
    return _row_to_item(row)


@router.post("", response_model=FeedSourceItem, status_code=201)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to create feed",
    status_code=500,
    log_event="create_feed_failed",
)
async def create_feed(
    body: FeedSourceCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> FeedSourceItem:
    """Create a new feed source."""
    pool = request.app.state.db_pool
    row = await create_feed_source(
        pool,
        name=body.name,
        url=body.url,
        source_type=body.source_type,
        category=body.category,
        locale=body.locale,
        source_config_id=body.source_config_id,
        is_active=body.is_active,
        priority=body.priority,
        config=json.dumps(body.config),
    )

    async with pool.acquire() as conn:
        await write_audit_log(
            conn,
            user_id=current_user.user_id,
            action="admin_feed_source_create",
            target_type="feed_source",
            target_id=row["id"],
            ip_address=str(request.client.host) if request.client else None,
        )

    return _row_to_item(row)


@router.patch("/{feed_id}", response_model=FeedSourceItem)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to update feed",
    status_code=500,
    log_event="update_feed_failed",
)
async def update_feed(
    feed_id: str,
    body: FeedSourceUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> FeedSourceItem:
    """Update an existing feed source."""
    pool = request.app.state.db_pool
    update_kwargs: dict[str, object] = {}
    for field_name in body.model_fields:
        val = getattr(body, field_name)
        if val is not None:
            if field_name == "config":
                update_kwargs[field_name] = json.dumps(val)
            else:
                update_kwargs[field_name] = val

    row = await update_feed_source(pool, feed_id, **update_kwargs)
    if not row:
        raise http_error(ErrorCode.NOT_FOUND, "Feed not found", status_code=404)

    async with pool.acquire() as conn:
        await write_audit_log(
            conn,
            user_id=current_user.user_id,
            action="admin_feed_source_update",
            target_type="feed_source",
            target_id=feed_id,
            ip_address=str(request.client.host) if request.client else None,
        )

    return _row_to_item(row)


@router.delete("/{feed_id}", status_code=204, response_model=None)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to delete feed",
    status_code=500,
    log_event="delete_feed_failed",
)
async def delete_feed(
    feed_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> None:
    """Delete a feed source."""
    pool = request.app.state.db_pool
    deleted = await delete_feed_source(pool, feed_id)
    if not deleted:
        raise http_error(ErrorCode.NOT_FOUND, "Feed not found", status_code=404)

    async with pool.acquire() as conn:
        await write_audit_log(
            conn,
            user_id=current_user.user_id,
            action="admin_feed_source_delete",
            target_type="feed_source",
            target_id=feed_id,
            ip_address=str(request.client.host) if request.client else None,
        )

    logger.info("admin_feed_source_deleted", feed_id=feed_id, by=current_user.user_id)


@router.post("/bulk-toggle")
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to bulk toggle",
    status_code=500,
    log_event="bulk_toggle_feeds_failed",
)
async def bulk_toggle_feeds(
    body: FeedSourceBulkToggleRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> dict[str, int]:
    """Bulk enable/disable feed sources."""
    pool = request.app.state.db_pool
    count = await bulk_toggle_feed_sources(pool, body.feed_ids, is_active=body.is_active)

    async with pool.acquire() as conn:
        await write_audit_log(
            conn,
            user_id=current_user.user_id,
            action="admin_feed_source_bulk_toggle",
            target_type="feed_source",
            target_id=None,
            ip_address=str(request.client.host) if request.client else None,
        )

    return {"updated": count}
