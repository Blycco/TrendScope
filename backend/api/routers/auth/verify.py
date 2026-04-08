"""Email verification endpoints: verify_send, verify_email.

Functions call ``_auth_pkg.save_auth_token`` etc. (via the package namespace)
so that ``unittest.mock.patch("backend.api.routers.auth.save_auth_token", ...)``
correctly intercepts those calls in tests.
"""

from __future__ import annotations

import secrets

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

# Imported as the package object so mock.patch("backend.api.routers.auth.*")
# is respected at call time.  The circular import is safe because __init__.py
# sets the token_store names *before* importing this sub-module.
import backend.api.routers.auth as _auth_pkg
from backend.api.routers.auth._constants import _EMAIL_VERIFY_PREFIX, _EMAIL_VERIFY_TTL
from backend.api.schemas.auth import EmailVerifySendResponse
from backend.auth.dependencies import CurrentUser, require_auth
from backend.common.audit import write_audit_log
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.users import update_user

router = APIRouter(tags=["auth"])
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


@router.post("/verify/send", response_model=EmailVerifySendResponse)
async def verify_send(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> EmailVerifySendResponse:
    """Generate an email verification token and store it in Redis.

    In production, this would also send an email. Currently returns the token
    for testing purposes via the response message.
    """
    try:
        token = secrets.token_urlsafe(32)
        await _auth_pkg.save_auth_token(
            _EMAIL_VERIFY_PREFIX, token, current_user.user_id, _EMAIL_VERIFY_TTL
        )
        logger.info("email_verify_token_created", user_id=current_user.user_id)
        return EmailVerifySendResponse(message="Verification email sent")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("verify_send_failed", error=str(exc))
        raise http_error(
            ErrorCode.REDIS_ERROR,
            "Failed to create verification token",
            status_code=500,
        ) from exc


@router.get("/verify/{token}")
async def verify_email(token: str, request: Request) -> dict:
    """Verify a user's email using the token from the verification email."""
    try:
        user_id = await _auth_pkg.get_auth_token(_EMAIL_VERIFY_PREFIX, token)
        if not user_id:
            raise http_error(
                ErrorCode.TOKEN_EXPIRED,
                "Invalid or expired verification token",
                status_code=400,
            )

        pool = request.app.state.db_pool
        await update_user(pool, user_id, email_verified=True)
        await _auth_pkg.delete_auth_token(_EMAIL_VERIFY_PREFIX, token)

        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=user_id,
                action="email_verified",
                ip_address=str(request.client.host) if request.client else None,
            )

        logger.info("email_verified", user_id=user_id)
        return {"message": "Email verified successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("verify_email_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Email verification failed", status_code=500) from exc
