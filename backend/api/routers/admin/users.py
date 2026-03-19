"""Admin user management endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas.admin import AdminUserItem, AdminUserListResponse, AdminUserUpdateRequest
from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import write_audit_log
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.admin import admin_delete_user, admin_list_users, admin_update_user

router = APIRouter(prefix="/users", tags=["admin-users"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=AdminUserListResponse)
async def list_users(
    request: Request,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminUserListResponse:
    """List users with optional search and pagination."""
    try:
        pool = request.app.state.db_pool
        rows, total = await admin_list_users(pool, search=search, page=page, page_size=page_size)
        users = [
            AdminUserItem(
                id=row["id"],
                email=row["email"],
                display_name=row["display_name"],
                role=row["role"],
                plan=row["plan"],
                locale=row["locale"],
                is_active=row["is_active"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
        return AdminUserListResponse(users=users, total=total, page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_list_users_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to list users", status_code=500) from exc


@router.patch("/{user_id}")
async def update_user(
    user_id: str,
    body: AdminUserUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminUserItem:
    """Update user plan, status, or role."""
    try:
        pool = request.app.state.db_pool
        row = await admin_update_user(
            pool, user_id, plan=body.plan, is_active=body.is_active, role=body.role
        )
        if not row:
            raise http_error(ErrorCode.NOT_FOUND, "User not found", status_code=404)

        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=current_user.user_id,
                action="admin_user_update",
                target_type="user_profile",
                target_id=user_id,
                ip_address=str(request.client.host) if request.client else None,
            )

        return AdminUserItem(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            role=row["role"],
            plan=row["plan"],
            locale=row["locale"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_update_user_failed", user_id=user_id, error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to update user", status_code=500) from exc


@router.delete("/{user_id}", status_code=204, response_model=None)
async def delete_user(
    user_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role(admin_only=True)),  # noqa: B008
) -> None:
    """Delete a user (admin only)."""
    try:
        pool = request.app.state.db_pool
        deleted = await admin_delete_user(pool, user_id)
        if not deleted:
            raise http_error(ErrorCode.NOT_FOUND, "User not found", status_code=404)

        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=current_user.user_id,
                action="admin_user_delete",
                target_type="user_profile",
                target_id=user_id,
                ip_address=str(request.client.host) if request.client else None,
            )

        logger.info("admin_user_deleted", target_user_id=user_id, by=current_user.user_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_delete_user_failed", user_id=user_id, error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to delete user", status_code=500) from exc
