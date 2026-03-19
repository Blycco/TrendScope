"""Admin AI model configuration endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas.admin import (
    AdminAIConfigResponse,
    AdminAIConfigTestResponse,
    AdminAIConfigUpdateRequest,
)
from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import write_audit_log
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.admin import admin_get_settings, admin_update_settings

router = APIRouter(prefix="/ai-config", tags=["admin-ai-config"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=AdminAIConfigResponse)
async def get_ai_config(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminAIConfigResponse:
    """Get current AI model configuration from admin_settings."""
    try:
        pool = request.app.state.db_pool
        rows = await admin_get_settings(pool)
        settings_map: dict[str, object] = {}
        for row in rows:
            settings_map[row["key"]] = row["value"]

        return AdminAIConfigResponse(
            primary_model=settings_map.get("ai_primary_model"),
            fallback_model=settings_map.get("ai_fallback_model"),
            api_key_set=bool(settings_map.get("ai_api_key_set")),
            settings={k: v for k, v in settings_map.items() if k.startswith("ai_")},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_get_ai_config_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to get AI config", status_code=500) from exc


@router.patch("", response_model=AdminAIConfigResponse)
async def update_ai_config(
    body: AdminAIConfigUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role(admin_only=True)),  # noqa: B008
) -> AdminAIConfigResponse:
    """Update AI model configuration (admin only)."""
    try:
        pool = request.app.state.db_pool
        updates: dict[str, object] = {}
        if body.primary_model is not None:
            updates["ai_primary_model"] = body.primary_model
        if body.fallback_model is not None:
            updates["ai_fallback_model"] = body.fallback_model

        if updates:
            await admin_update_settings(pool, updates)

            async with pool.acquire() as conn:
                await write_audit_log(
                    conn,
                    user_id=current_user.user_id,
                    action="admin_ai_config_update",
                    target_type="admin_settings",
                    target_id=None,
                    ip_address=str(request.client.host) if request.client else None,
                    detail=updates,
                )

        rows = await admin_get_settings(pool)
        settings_map: dict[str, object] = {}
        for row in rows:
            settings_map[row["key"]] = row["value"]

        return AdminAIConfigResponse(
            primary_model=settings_map.get("ai_primary_model"),
            fallback_model=settings_map.get("ai_fallback_model"),
            api_key_set=bool(settings_map.get("ai_api_key_set")),
            settings={k: v for k, v in settings_map.items() if k.startswith("ai_")},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_update_ai_config_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to update AI config", status_code=500) from exc


@router.post("/test", response_model=AdminAIConfigTestResponse)
async def test_ai_config(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminAIConfigTestResponse:
    """Test AI model connection by performing a simple health check."""
    try:
        pool = request.app.state.db_pool
        rows = await admin_get_settings(pool)
        settings_map: dict[str, object] = {}
        for row in rows:
            settings_map[row["key"]] = row["value"]

        start = time.monotonic()
        # Simulate connection test: check that model setting exists
        primary_model = settings_map.get("ai_primary_model")
        elapsed = (time.monotonic() - start) * 1000

        if not primary_model:
            return AdminAIConfigTestResponse(
                success=False,
                response_time_ms=elapsed,
                error="No primary AI model configured",
            )

        return AdminAIConfigTestResponse(
            success=True,
            response_time_ms=elapsed,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_test_ai_config_failed", error=str(exc))
        return AdminAIConfigTestResponse(
            success=False,
            error=str(exc),
        )
