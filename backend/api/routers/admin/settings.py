"""Admin system settings endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Depends, Request

from backend.api.schemas.admin import (
    AdminSettingItem,
    AdminSettingsResponse,
    AdminSettingsUpdateRequest,
)
from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import log_audit
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode
from backend.db.queries.admin import (
    admin_get_settings,
    admin_reset_settings,
    admin_update_settings,
)

router = APIRouter(prefix="/settings", tags=["admin-settings"])
logger = structlog.get_logger(__name__)


def _parse_jsonb(value: object) -> object:
    """Parse JSONB value if it's a string."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value


def _rows_to_response(rows: list) -> AdminSettingsResponse:
    """Convert DB rows to response schema."""
    items = [
        AdminSettingItem(
            key=row["key"],
            value=_parse_jsonb(row["value"]),
            default_value=_parse_jsonb(row["default_value"]),
            updated_at=row["updated_at"],
        )
        for row in rows
    ]
    return AdminSettingsResponse(settings=items)


@router.get("", response_model=AdminSettingsResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to get settings",
    status_code=500,
    log_event="admin_get_settings_failed",
)
async def get_settings(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminSettingsResponse:
    """Get all admin settings."""
    pool = request.app.state.db_pool
    rows = await admin_get_settings(pool)
    return _rows_to_response(rows)


@router.patch("", response_model=AdminSettingsResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to update settings",
    status_code=500,
    log_event="admin_update_settings_failed",
)
async def update_settings(
    body: AdminSettingsUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role(admin_only=True)),  # noqa: B008
) -> AdminSettingsResponse:
    """Update admin settings (admin only)."""
    pool = request.app.state.db_pool
    rows = await admin_update_settings(pool, body.settings)

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="admin_settings_update",
        target_type="admin_settings",
        target_id=None,
        ip_address=str(request.client.host) if request.client else None,
        detail={"keys": list(body.settings.keys())},
    )

    logger.info("admin_settings_updated", by=current_user.user_id)
    return _rows_to_response(rows)


@router.post("/reset", response_model=AdminSettingsResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to reset settings",
    status_code=500,
    log_event="admin_reset_settings_failed",
)
async def reset_settings(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role(admin_only=True)),  # noqa: B008
) -> AdminSettingsResponse:
    """Reset all settings to default values (admin only)."""
    pool = request.app.state.db_pool
    rows = await admin_reset_settings(pool)

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="admin_settings_reset",
        target_type="admin_settings",
        target_id=None,
        ip_address=str(request.client.host) if request.client else None,
    )

    logger.info("admin_settings_reset_to_defaults", by=current_user.user_id)
    return _rows_to_response(rows)
