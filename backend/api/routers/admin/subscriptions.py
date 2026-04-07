"""Admin subscription management endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request

from backend.api.schemas.admin import (
    AdminRefundRequest,
    AdminRefundResponse,
    AdminSubscriptionItem,
    AdminSubscriptionListResponse,
)
from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import log_audit
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.admin import admin_list_subscriptions, admin_refund_subscription

router = APIRouter(prefix="/subscriptions", tags=["admin-subscriptions"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=AdminSubscriptionListResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to list subscriptions",
    status_code=500,
    log_event="admin_list_subscriptions_failed",
)
async def list_subscriptions(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminSubscriptionListResponse:
    """List all subscriptions with pagination."""
    pool = request.app.state.db_pool
    rows, total = await admin_list_subscriptions(pool, page=page, page_size=page_size)
    items = [
        AdminSubscriptionItem(
            id=row["id"],
            user_id=row["user_id"],
            plan=row["plan"],
            status=row["status"],
            provider=row["provider"],
            provider_sub_id=row["provider_sub_id"],
            started_at=row["started_at"],
            expires_at=row["expires_at"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return AdminSubscriptionListResponse(
        subscriptions=items, total=total, page=page, page_size=page_size
    )


@router.post("/{subscription_id}/refund", response_model=AdminRefundResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to refund subscription",
    status_code=500,
    log_event="admin_refund_subscription_failed",
)
async def refund_subscription(
    subscription_id: str,
    body: AdminRefundRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminRefundResponse:
    """Manually refund a subscription."""
    pool = request.app.state.db_pool
    row = await admin_refund_subscription(pool, subscription_id, body.reason)
    if not row:
        raise http_error(
            ErrorCode.NOT_FOUND, "Subscription not found or already refunded", status_code=404
        )

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="admin_subscription_refund",
        target_type="subscription",
        target_id=subscription_id,
        ip_address=str(request.client.host) if request.client else None,
        detail={"reason": body.reason},
    )

    logger.info(
        "admin_subscription_refunded",
        subscription_id=subscription_id,
        by=current_user.user_id,
    )
    return AdminRefundResponse(
        subscription_id=row["id"],
        status=row["status"],
        refund_reason=body.reason,
    )
