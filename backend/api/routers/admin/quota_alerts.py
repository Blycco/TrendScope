"""Admin quota alert endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request

from backend.api.schemas.admin import (
    QuotaAlertCountResponse,
    QuotaAlertItem,
    QuotaAlertListResponse,
)
from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import write_audit_log
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.admin import (
    admin_dismiss_quota_alert,
    admin_get_active_alert_count,
    admin_list_quota_alerts,
)

router = APIRouter(prefix="/quota-alerts", tags=["admin-quota-alerts"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=QuotaAlertListResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to list quota alerts",
    status_code=500,
    log_event="list_quota_alerts_failed",
)
async def list_quota_alerts(
    request: Request,
    service_name: str | None = None,
    is_dismissed: bool | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> QuotaAlertListResponse:
    """List API quota alerts with optional filters."""
    pool = request.app.state.db_pool
    rows, total = await admin_list_quota_alerts(
        pool,
        service_name=service_name,
        is_dismissed=is_dismissed,
        page=page,
        page_size=page_size,
    )
    items = [
        QuotaAlertItem(
            id=str(row["id"]),
            service_name=row["service_name"],
            error_type=row["error_type"],
            status_code=row["status_code"],
            detail=row["detail"],
            endpoint_url=row["endpoint_url"],
            is_dismissed=row["is_dismissed"],
            dismissed_by=str(row["dismissed_by"]) if row["dismissed_by"] else None,
            dismissed_at=row["dismissed_at"],
            email_sent=row["email_sent"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return QuotaAlertListResponse(alerts=items, total=total, page=page, page_size=page_size)


@router.get("/count", response_model=QuotaAlertCountResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to get alert count",
    status_code=500,
    log_event="get_active_alert_count_failed",
)
async def get_active_alert_count(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> QuotaAlertCountResponse:
    """Get count of undismissed quota alerts."""
    pool = request.app.state.db_pool
    count = await admin_get_active_alert_count(pool)
    return QuotaAlertCountResponse(active_count=count)


@router.post("/{alert_id}/dismiss", response_model=QuotaAlertItem)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to dismiss alert",
    status_code=500,
    log_event="dismiss_quota_alert_failed",
)
async def dismiss_quota_alert(
    alert_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> QuotaAlertItem:
    """Dismiss a quota alert."""
    pool = request.app.state.db_pool
    row = await admin_dismiss_quota_alert(pool, alert_id, current_user.user_id)

    if not row:
        raise http_error(ErrorCode.NOT_FOUND, "Alert not found", status_code=404)

    async with pool.acquire() as conn:
        await write_audit_log(
            conn,
            user_id=current_user.user_id,
            action="admin_dismiss_quota_alert",
            target_type="api_quota_alert",
            target_id=alert_id,
            ip_address=str(request.client.host) if request.client else None,
        )

    return QuotaAlertItem(
        id=str(row["id"]),
        service_name=row["service_name"],
        error_type=row["error_type"],
        status_code=row["status_code"],
        detail=row["detail"],
        endpoint_url=row["endpoint_url"],
        is_dismissed=row["is_dismissed"],
        dismissed_by=str(row["dismissed_by"]) if row["dismissed_by"] else None,
        dismissed_at=row["dismissed_at"],
        email_sent=row["email_sent"],
        created_at=row["created_at"],
    )
