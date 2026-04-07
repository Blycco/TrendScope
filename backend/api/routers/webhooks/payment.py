"""Payment webhook endpoint with HMAC-SHA256 signature verification. (RULE 01, RULE 16)"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import structlog
from fastapi import APIRouter, Request

from backend.common.audit import write_audit_log
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode, http_error
from backend.common.metrics import PAYMENT_FAILURES
from backend.db.queries.subscriptions import update_subscription_by_provider_id

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = structlog.get_logger(__name__)


def _verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature against PAYMENT_WEBHOOK_SECRET env var."""
    secret = os.environ.get("PAYMENT_WEBHOOK_SECRET", "")
    if not secret:
        logger.error("payment_webhook_secret_not_set")
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/payment")
@handle_errors(
    error_code=ErrorCode.INTERNAL_ERROR,
    message="Webhook processing failed",
    status_code=500,
    log_event="payment_webhook_failed",
)
async def payment_webhook(request: Request) -> dict:
    """Handle payment provider webhook events (Stripe-style).

    Expected headers:
        X-Webhook-Signature: HMAC-SHA256 hex digest

    Expected JSON body:
        {
            "type": "subscription.updated" | "subscription.cancelled" | ...,
            "data": {
                "provider_sub_id": "...",
                "status": "active" | "cancelled" | "expired" | "past_due",
                "plan": "pro" | "business" | "enterprise" (optional)
            }
        }
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")

    if not _verify_webhook_signature(raw_body, signature):
        PAYMENT_FAILURES.inc()
        raise http_error(ErrorCode.UNAUTHORIZED, "Invalid webhook signature", status_code=401)

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise http_error(ErrorCode.VALIDATION_ERROR, "Invalid JSON", status_code=400) from exc

    event_type: str = payload.get("type", "")
    data: dict = payload.get("data", {})

    provider_sub_id = data.get("provider_sub_id")
    status = data.get("status")

    if not provider_sub_id or not status:
        raise http_error(
            ErrorCode.VALIDATION_ERROR,
            "Missing provider_sub_id or status in webhook data",
            status_code=400,
        )

    pool = request.app.state.db_pool
    plan = data.get("plan")
    result = await update_subscription_by_provider_id(
        pool, provider_sub_id=provider_sub_id, status=status, plan=plan
    )

    if result:
        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=result["user_id"],
                action=f"webhook_{event_type}",
                target_type="subscription",
                target_id=result["id"],
                detail={"event_type": event_type, "status": status},
            )

    logger.info(
        "payment_webhook_processed",
        event_type=event_type,
        provider_sub_id=provider_sub_id,
    )
    return {"status": "ok"}
