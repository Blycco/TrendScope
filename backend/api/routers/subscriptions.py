"""Subscription endpoints: current, checkout, cancel. (RULE 08, RULE 17)"""

from __future__ import annotations

import os
import uuid

import structlog
from fastapi import APIRouter, Depends, Request

from backend.api.schemas.subscriptions import (
    CheckoutRequest,
    CheckoutResponse,
    SubscriptionResponse,
)
from backend.auth.dependencies import CurrentUser, require_auth
from backend.common.audit import write_audit_log
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.subscriptions import (
    cancel_subscription,
    create_subscription,
    get_current_subscription,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
logger = structlog.get_logger(__name__)

_VALID_PLANS = {"pro", "business", "enterprise"}


@router.get("/current", response_model=None)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to fetch subscription",
    status_code=500,
    log_event="get_current_subscription_failed",
)
async def get_current(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> SubscriptionResponse | None:
    """Return the user's current active subscription, or null."""
    pool = request.app.state.db_pool
    row = await get_current_subscription(pool, user_id=current_user.user_id)
    if not row:
        return None
    return SubscriptionResponse(
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


@router.post("/checkout", response_model=CheckoutResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Checkout failed",
    status_code=500,
    log_event="checkout_failed",
)
async def checkout(
    body: CheckoutRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> CheckoutResponse:
    """Create a checkout session for a plan upgrade (stub)."""
    if body.plan not in _VALID_PLANS:
        raise http_error(ErrorCode.VALIDATION_ERROR, "Invalid plan", status_code=400)

    pool = request.app.state.db_pool
    session_id = str(uuid.uuid4())
    _provider = os.environ.get("PAYMENT_PROVIDER", "toss")

    await create_subscription(
        pool,
        user_id=current_user.user_id,
        plan=body.plan,
        provider=_provider,
        provider_sub_id=session_id,
    )

    async with pool.acquire() as conn:
        await write_audit_log(
            conn,
            user_id=current_user.user_id,
            action="subscription_checkout",
            target_type="subscription",
            target_id=session_id,
            ip_address=str(request.client.host) if request.client else None,
        )

    checkout_url = f"/payments/toss/checkout/{session_id}"
    logger.info("checkout_created", user_id=current_user.user_id, plan=body.plan)
    return CheckoutResponse(checkout_url=checkout_url, session_id=session_id)


@router.post("/cancel")
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Cancellation failed",
    status_code=500,
    log_event="cancel_subscription_failed",
)
async def cancel(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> dict:
    """Cancel the user's current active subscription."""
    pool = request.app.state.db_pool
    sub = await get_current_subscription(pool, user_id=current_user.user_id)
    if not sub:
        raise http_error(ErrorCode.NOT_FOUND, "No active subscription", status_code=404)

    result = await cancel_subscription(
        pool, subscription_id=sub["id"], user_id=current_user.user_id
    )
    if not result:
        raise http_error(
            ErrorCode.NOT_FOUND,
            "Subscription not found or already cancelled",
            status_code=404,
        )

    async with pool.acquire() as conn:
        await write_audit_log(
            conn,
            user_id=current_user.user_id,
            action="subscription_cancel",
            target_type="subscription",
            target_id=sub["id"],
            ip_address=str(request.client.host) if request.client else None,
        )

    logger.info("subscription_cancelled", user_id=current_user.user_id)
    return {"message": "Subscription cancelled"}
