"""2FA endpoints: enable, verify, disable, login."""

from __future__ import annotations

import pyotp
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas.auth import (
    Enable2FAResponse,
    TokenResponse,
    TwoFALoginRequest,
    Verify2FARequest,
)
from backend.auth.dependencies import CurrentUser, require_auth
from backend.auth.jwt import create_access_token, create_refresh_token, decode_token
from backend.common.audit import write_audit_log
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.users import (
    get_identity,
    get_user_by_id,
    update_2fa,
)

router = APIRouter(tags=["auth"])
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# 2FA: enable / verify / disable / login
# ---------------------------------------------------------------------------


@router.post("/2fa/enable", response_model=Enable2FAResponse)
async def enable_2fa(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> Enable2FAResponse:
    """Generate a TOTP secret and return the otpauth URL for QR scanning."""
    try:
        pool = request.app.state.db_pool
        user = await get_user_by_id(pool, current_user.user_id)
        if not user:
            raise http_error(ErrorCode.NOT_FOUND, "User not found", status_code=404)

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        otpauth_url = totp.provisioning_uri(user["email"], issuer_name="TrendScope")

        # Save secret but keep 2FA disabled until verified
        await update_2fa(pool, current_user.user_id, secret=secret, enabled=False)

        logger.info("2fa_secret_generated", user_id=current_user.user_id)
        return Enable2FAResponse(otpauth_url=otpauth_url, secret=secret)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("enable_2fa_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to enable 2FA", status_code=500) from exc


@router.post("/2fa/verify")
async def verify_2fa(
    body: Verify2FARequest,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> dict:
    """Verify a TOTP code and activate 2FA for the user."""
    try:
        pool = request.app.state.db_pool
        identity = await get_identity(pool, user_id=current_user.user_id, provider="email")
        if not identity or not identity["two_fa_secret"]:
            raise http_error(ErrorCode.VALIDATION_ERROR, "2FA not initialized", status_code=400)

        totp = pyotp.TOTP(identity["two_fa_secret"])
        if not totp.verify(body.totp_code, valid_window=1):
            raise http_error(ErrorCode.UNAUTHORIZED, "Invalid TOTP code", status_code=401)

        await update_2fa(pool, current_user.user_id, secret=identity["two_fa_secret"], enabled=True)

        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=current_user.user_id,
                action="2fa_enabled",
                ip_address=str(request.client.host) if request.client else None,
            )

        logger.info("2fa_enabled", user_id=current_user.user_id)
        return {"message": "2FA has been enabled"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("verify_2fa_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "2FA verification failed", status_code=500) from exc


@router.post("/2fa/disable")
async def disable_2fa(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> dict:
    """Disable 2FA for the authenticated user."""
    try:
        pool = request.app.state.db_pool
        await update_2fa(pool, current_user.user_id, secret=None, enabled=False)

        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=current_user.user_id,
                action="2fa_disabled",
                ip_address=str(request.client.host) if request.client else None,
            )

        logger.info("2fa_disabled", user_id=current_user.user_id)
        return {"message": "2FA has been disabled"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("disable_2fa_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to disable 2FA", status_code=500) from exc


@router.post("/2fa/login", response_model=TokenResponse)
async def login_2fa(body: TwoFALoginRequest, request: Request) -> TokenResponse:
    """Complete login for users with 2FA enabled using challenge token + TOTP code."""
    try:
        payload = decode_token(body.challenge_token)
    except Exception as exc:
        raise http_error(
            ErrorCode.TOKEN_EXPIRED, "Invalid or expired challenge token", status_code=401
        ) from exc

    if payload.get("type") != "2fa_challenge":
        raise http_error(ErrorCode.UNAUTHORIZED, "Not a 2FA challenge token", status_code=401)

    user_id = payload["sub"]
    try:
        pool = request.app.state.db_pool
        user = await get_user_by_id(pool, user_id)
        if not user:
            raise http_error(ErrorCode.NOT_FOUND, "User not found", status_code=404)

        identity = await get_identity(pool, user_id=user_id, provider="email")
        if not identity or not identity["two_fa_secret"]:
            raise http_error(ErrorCode.VALIDATION_ERROR, "2FA not configured", status_code=400)

        totp = pyotp.TOTP(identity["two_fa_secret"])
        if not totp.verify(body.totp_code, valid_window=1):
            raise http_error(ErrorCode.UNAUTHORIZED, "Invalid TOTP code", status_code=401)

        logger.info("2fa_login_success", user_id=user_id)
        return TokenResponse(
            access_token=create_access_token(user["id"], user["plan"], user["role"]),
            refresh_token=create_refresh_token(user["id"]),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("2fa_login_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "2FA login failed", status_code=500) from exc
