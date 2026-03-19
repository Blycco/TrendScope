"""Admin analytics endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas.admin import AdminAnalyticsResponse
from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.admin import (
    admin_get_analytics_api_usage,
    admin_get_analytics_revenue,
    admin_get_analytics_trends,
    admin_get_analytics_users,
)

router = APIRouter(prefix="/analytics", tags=["admin-analytics"])
logger = structlog.get_logger(__name__)

_METRIC_HANDLERS = {
    "users": admin_get_analytics_users,
    "revenue": admin_get_analytics_revenue,
    "trends": admin_get_analytics_trends,
    "api_usage": admin_get_analytics_api_usage,
}


@router.get("/{metric}", response_model=AdminAnalyticsResponse)
async def get_analytics(
    metric: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminAnalyticsResponse:
    """Get analytics for the specified metric."""
    handler = _METRIC_HANDLERS.get(metric)
    if not handler:
        raise http_error(
            ErrorCode.VALIDATION_ERROR,
            f"Invalid metric: {metric}. Valid: {', '.join(_METRIC_HANDLERS.keys())}",
            status_code=400,
        )
    try:
        pool = request.app.state.db_pool
        data = await handler(pool)
        return AdminAnalyticsResponse(metric=metric, data=data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_get_analytics_failed", metric=metric, error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to get analytics", status_code=500) from exc
