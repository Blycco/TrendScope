"""Password endpoints: forgot_password, reset_password.

Functions call ``_auth_pkg.save_auth_token`` etc. (via the package namespace)
so that ``unittest.mock.patch("backend.api.routers.auth.save_auth_token", ...)``
correctly intercepts those calls in tests.
"""

from __future__ import annotations

import secrets

import structlog
from fastapi import APIRouter, HTTPException, Request

# Imported as the package object so mock.patch("backend.api.routers.auth.*")
# is respected at call time.  The circular import is safe because __init__.py
# sets the token_store names *before* importing this sub-module.
import backend.api.routers.auth as _auth_pkg
from backend.api.routers.auth._constants import _PASSWORD_RESET_PREFIX, _PASSWORD_RESET_TTL
from backend.api.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest
from backend.auth.password import hash_password
from backend.common.audit import write_audit_log
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.users import get_user_by_email, update_password_hash

router = APIRouter(tags=["auth"])
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Password forgot / reset
# ---------------------------------------------------------------------------


@router.post("/password/forgot")
async def forgot_password(body: ForgotPasswordRequest, request: Request) -> dict:
    """Send a password reset token. Always returns 200 to prevent email enumeration."""
    try:
        pool = request.app.state.db_pool
        user = await get_user_by_email(pool, body.email)
        if user:
            token = secrets.token_urlsafe(32)
            await _auth_pkg.save_auth_token(
                _PASSWORD_RESET_PREFIX, token, user["id"], _PASSWORD_RESET_TTL
            )
            logger.info("password_reset_token_created", user_id=user["id"])
            # In production: send email with token link
        return {"message": "If the email exists, a reset link has been sent"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("forgot_password_failed", error=str(exc))
        raise http_error(
            ErrorCode.DB_ERROR,
            "Password reset request failed",
            status_code=500,
        ) from exc


@router.post("/password/reset")
async def reset_password(body: ResetPasswordRequest, request: Request) -> dict:
    """Reset the password using a valid reset token."""
    try:
        user_id = await _auth_pkg.get_auth_token(_PASSWORD_RESET_PREFIX, body.token)
        if not user_id:
            raise http_error(
                ErrorCode.TOKEN_EXPIRED,
                "Invalid or expired reset token",
                status_code=400,
            )

        pool = request.app.state.db_pool
        new_hash = hash_password(body.new_password)
        await update_password_hash(pool, user_id, new_hash)
        await _auth_pkg.delete_auth_token(_PASSWORD_RESET_PREFIX, body.token)

        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=user_id,
                action="password_reset",
                ip_address=str(request.client.host) if request.client else None,
            )

        logger.info("password_reset_complete", user_id=user_id)
        return {"message": "Password has been reset"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("reset_password_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Password reset failed", status_code=500) from exc
