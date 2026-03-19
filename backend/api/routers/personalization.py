"""GET/PUT /api/v1/personalization — per-user content personalization settings."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas.personalization import PersonalizationResponse, PersonalizationUpdate
from backend.auth.dependencies import CurrentUser, require_auth
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.personalization import get_personalization, upsert_personalization

router = APIRouter(prefix="/personalization", tags=["personalization"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=PersonalizationResponse)
async def get_my_personalization(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> PersonalizationResponse:
    """Return personalization settings for the authenticated user."""
    try:
        pool = request.app.state.db_pool
        row = await get_personalization(pool, user_id=current_user.user_id)
        if row is None:
            return PersonalizationResponse(category_weights={}, locale_ratio=0.5)
        return PersonalizationResponse(
            category_weights=dict(row["category_weights"]),
            locale_ratio=row["locale_ratio"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_personalization_failed", user_id=current_user.user_id, error=str(exc))
        raise http_error(
            ErrorCode.DB_ERROR,
            "Failed to fetch personalization settings",
            status_code=500,
        ) from exc


@router.put("", response_model=PersonalizationResponse)
async def update_my_personalization(
    body: PersonalizationUpdate,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> PersonalizationResponse:
    """Create or update personalization settings for the authenticated user."""
    try:
        pool = request.app.state.db_pool
        await upsert_personalization(
            pool,
            user_id=current_user.user_id,
            category_weights=body.category_weights,
            locale_ratio=body.locale_ratio,
        )
        logger.info(
            "personalization_updated",
            user_id=current_user.user_id,
            locale_ratio=body.locale_ratio,
        )
        return PersonalizationResponse(
            category_weights=body.category_weights,
            locale_ratio=body.locale_ratio,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("update_personalization_failed", user_id=current_user.user_id, error=str(exc))
        raise http_error(
            ErrorCode.DB_ERROR,
            "Failed to update personalization settings",
            status_code=500,
        ) from exc
