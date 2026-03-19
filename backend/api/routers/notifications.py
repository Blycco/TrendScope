"""Notification settings endpoints. (RULE 08, RULE 17)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas.notifications import (
    NotificationSettingResponse,
    NotificationSettingsResponse,
    NotificationSettingUpdate,
)
from backend.auth.dependencies import CurrentUser, require_auth
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.notifications import (
    get_notification_settings,
    upsert_notification_setting,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = structlog.get_logger(__name__)


@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_settings(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> NotificationSettingsResponse:
    """Return all notification settings for the authenticated user."""
    try:
        pool = request.app.state.db_pool
        rows = await get_notification_settings(pool, user_id=current_user.user_id)
        return NotificationSettingsResponse(
            settings=[
                NotificationSettingResponse(
                    id=row["id"],
                    user_id=row["user_id"],
                    type=row["type"],
                    channel=row["channel"],
                    is_enabled=row["is_enabled"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_notification_settings_failed", error=str(exc))
        raise http_error(
            ErrorCode.DB_ERROR,
            "Failed to fetch notification settings",
            status_code=500,
        ) from exc


@router.put("/settings", response_model=NotificationSettingsResponse)
async def update_settings(
    body: NotificationSettingUpdate,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> NotificationSettingsResponse:
    """Create or update a notification setting for the authenticated user."""
    try:
        pool = request.app.state.db_pool
        await upsert_notification_setting(
            pool,
            user_id=current_user.user_id,
            notification_type=body.type,
            channel=body.channel,
            is_enabled=body.is_enabled,
        )
        rows = await get_notification_settings(pool, user_id=current_user.user_id)
        logger.info(
            "notification_setting_updated",
            user_id=current_user.user_id,
            type=body.type,
            channel=body.channel,
        )
        return NotificationSettingsResponse(
            settings=[
                NotificationSettingResponse(
                    id=row["id"],
                    user_id=row["user_id"],
                    type=row["type"],
                    channel=row["channel"],
                    is_enabled=row["is_enabled"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("update_notification_settings_failed", error=str(exc))
        raise http_error(
            ErrorCode.DB_ERROR,
            "Failed to update notification setting",
            status_code=500,
        ) from exc
