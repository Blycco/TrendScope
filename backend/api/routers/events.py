"""Event tracking endpoints: batch insert user actions. (RULE 08, RULE 17)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas.events import EventBatchRequest
from backend.auth.dependencies import CurrentUser, require_auth
from backend.common.audit import log_audit
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.events import batch_insert_events

router = APIRouter(prefix="/events", tags=["events"])
logger = structlog.get_logger(__name__)


@router.post("/batch", status_code=201)
async def batch_events(
    body: EventBatchRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> dict:
    """Insert a batch of user action events."""
    try:
        pool = request.app.state.db_pool
        events_data = [evt.model_dump() for evt in body.events]
        count = await batch_insert_events(pool, user_id=current_user.user_id, events=events_data)

        await log_audit(
            pool,
            user_id=current_user.user_id,
            action="events_batch",
            ip_address=str(request.client.host) if request.client else None,
            detail={"count": count},
        )

        logger.info("events_batch_inserted", user_id=current_user.user_id, count=count)
        return {"inserted": count}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("batch_events_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to insert events", status_code=500) from exc
