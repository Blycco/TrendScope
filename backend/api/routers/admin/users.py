"""Admin user management endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request

from backend.api.schemas.admin import AdminUserItem, AdminUserListResponse, AdminUserUpdateRequest
from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import log_audit
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.admin import admin_delete_user, admin_list_users, admin_update_user

router = APIRouter(prefix="/users", tags=["admin-users"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=AdminUserListResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to list users",
    status_code=500,
    log_event="admin_list_users_failed",
)
async def list_users(
    request: Request,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminUserListResponse:
    """List users with optional search and pagination."""
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


@router.patch("/{user_id}")
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to update user",
    status_code=500,
    log_event="admin_update_user_failed",
)
async def update_user(
    user_id: str,
    body: AdminUserUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminUserItem:
    """Update user plan, status, or role."""
    pool = request.app.state.db_pool
    row = await admin_update_user(
        pool, user_id, plan=body.plan, is_active=body.is_active, role=body.role
    )
    if not row:
        raise http_error(ErrorCode.NOT_FOUND, "User not found", status_code=404)

    await log_audit(
        pool,
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


@router.delete("/{user_id}", status_code=204, response_model=None)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to delete user",
    status_code=500,
    log_event="admin_delete_user_failed",
)
async def delete_user(
    user_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role(admin_only=True)),  # noqa: B008
) -> None:
    """Delete a user (admin only)."""
    pool = request.app.state.db_pool
    deleted = await admin_delete_user(pool, user_id)
    if not deleted:
        raise http_error(ErrorCode.NOT_FOUND, "User not found", status_code=404)

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="admin_user_delete",
        target_type="user_profile",
        target_id=user_id,
        ip_address=str(request.client.host) if request.client else None,
    )

    logger.info("admin_user_deleted", target_user_id=user_id, by=current_user.user_id)
