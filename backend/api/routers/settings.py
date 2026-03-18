"""User settings endpoints: get and update profile settings. (RULE 08, RULE 17)"""

from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas.settings import SettingsResponse, UpdateSettingsRequest
from backend.auth.dependencies import CurrentUser, require_auth
from backend.common.audit import write_audit_log
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.settings import get_user_settings, update_user_settings

router = APIRouter(prefix="/settings", tags=["settings"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=SettingsResponse)
async def get_settings(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> SettingsResponse:
    """Return the authenticated user's settings."""
    try:
        pool = request.app.state.db_pool
        row = await get_user_settings(pool, user_id=current_user.user_id)
        if not row:
            raise http_error(ErrorCode.NOT_FOUND, "User not found", status_code=404)

        weights = row["category_weights"]
        if isinstance(weights, str):
            weights = json.loads(weights)

        return SettingsResponse(
            id=row["id"],
            display_name=row["display_name"],
            role=row["role"],
            locale=row["locale"],
            category_weights=weights if isinstance(weights, dict) else {},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_settings_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to fetch settings", status_code=500) from exc


@router.put("", response_model=SettingsResponse)
async def update_settings(
    body: UpdateSettingsRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> SettingsResponse:
    """Update the authenticated user's settings."""
    try:
        pool = request.app.state.db_pool
        row = await update_user_settings(
            pool,
            user_id=current_user.user_id,
            display_name=body.display_name,
            role=body.role,
            locale=body.locale,
            category_weights=body.category_weights,
        )
        if not row:
            raise http_error(ErrorCode.NOT_FOUND, "User not found", status_code=404)

        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=current_user.user_id,
                action="settings_update",
                target_type="user_profile",
                target_id=current_user.user_id,
                ip_address=str(request.client.host) if request.client else None,
            )

        weights = row["category_weights"]
        if isinstance(weights, str):
            weights = json.loads(weights)

        logger.info("settings_updated", user_id=current_user.user_id)
        return SettingsResponse(
            id=row["id"],
            display_name=row["display_name"],
            role=row["role"],
            locale=row["locale"],
            category_weights=weights if isinstance(weights, dict) else {},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("update_settings_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to update settings", status_code=500) from exc
