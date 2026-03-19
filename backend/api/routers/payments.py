"""Toss Payments mock checkout endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/toss/checkout/{session_id}")
async def toss_checkout(session_id: str) -> dict:
    """Return mock Toss Payments checkout info for a given session."""
    try:
        logger.info("toss_checkout_requested", session_id=session_id)
        return {
            "provider": "toss",
            "session_id": session_id,
            "checkout_url": f"https://pay.toss.im/mock/checkout/{session_id}",
            "status": "pending",
        }
    except Exception as exc:
        logger.error("toss_checkout_failed", session_id=session_id, error=str(exc))
        raise
