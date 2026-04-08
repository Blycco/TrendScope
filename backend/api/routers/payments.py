"""Toss Payments mock checkout endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/toss/checkout/{session_id}")
@handle_errors(
    error_code=ErrorCode.INTERNAL_ERROR,
    message="Checkout request failed",
    status_code=500,
    log_event="toss_checkout_failed",
)
async def toss_checkout(session_id: str) -> dict:
    """Return mock Toss Payments checkout info for a given session."""
    logger.info("toss_checkout_requested", session_id=session_id)
    return {
        "provider": "toss",
        "session_id": session_id,
        "checkout_url": f"https://pay.toss.im/mock/checkout/{session_id}",
        "status": "pending",
    }
