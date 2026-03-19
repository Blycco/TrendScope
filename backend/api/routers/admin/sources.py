"""Admin source/quota management endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas.admin import (
    AdminSourceItem,
    AdminSourceListResponse,
    AdminSourceUpdateRequest,
)
from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import write_audit_log
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.admin import (
    admin_list_sources,
    admin_reset_source_quota,
    admin_update_source,
)

router = APIRouter(prefix="/sources", tags=["admin-sources"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=AdminSourceListResponse)
async def list_sources(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminSourceListResponse:
    """List all data sources with quota info."""
    try:
        pool = request.app.state.db_pool
        rows = await admin_list_sources(pool)
        items = [
            AdminSourceItem(
                id=row["id"],
                source_name=row["source_name"],
                quota_limit=row["quota_limit"],
                quota_used=row["quota_used"],
                is_active=row["is_active"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
        return AdminSourceListResponse(sources=items)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_list_sources_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to list sources", status_code=500) from exc


@router.patch("/{source_id}")
async def update_source(
    source_id: str,
    body: AdminSourceUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminSourceItem:
    """Update source quota or active status."""
    try:
        pool = request.app.state.db_pool
        row = await admin_update_source(
            pool, source_id, quota_limit=body.quota_limit, is_active=body.is_active
        )
        if not row:
            raise http_error(ErrorCode.NOT_FOUND, "Source not found", status_code=404)

        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=current_user.user_id,
                action="admin_source_update",
                target_type="source_config",
                target_id=source_id,
                ip_address=str(request.client.host) if request.client else None,
            )

        return AdminSourceItem(
            id=row["id"],
            source_name=row["source_name"],
            quota_limit=row["quota_limit"],
            quota_used=row["quota_used"],
            is_active=row["is_active"],
            updated_at=row["updated_at"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_update_source_failed", source_id=source_id, error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to update source", status_code=500) from exc


@router.post("/{source_id}/reset")
async def reset_source_quota(
    source_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminSourceItem:
    """Reset source quota_used to 0."""
    try:
        pool = request.app.state.db_pool
        row = await admin_reset_source_quota(pool, source_id)
        if not row:
            raise http_error(ErrorCode.NOT_FOUND, "Source not found", status_code=404)

        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=current_user.user_id,
                action="admin_source_quota_reset",
                target_type="source_config",
                target_id=source_id,
                ip_address=str(request.client.host) if request.client else None,
            )

        logger.info("admin_source_quota_reset", source_id=source_id, by=current_user.user_id)
        return AdminSourceItem(
            id=row["id"],
            source_name=row["source_name"],
            quota_limit=row["quota_limit"],
            quota_used=row["quota_used"],
            is_active=row["is_active"],
            updated_at=row["updated_at"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_reset_source_quota_failed", source_id=source_id, error=str(exc))
        raise http_error(
            ErrorCode.DB_ERROR, "Failed to reset source quota", status_code=500
        ) from exc
