"""Auth endpoints: register, login, logout, OAuth, refresh, 2FA, password reset."""

from __future__ import annotations

import secrets

import pyotp
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from backend.api.schemas.auth import (
    EmailVerifySendResponse,
    Enable2FAResponse,
    ForgotPasswordRequest,
    KakaoOAuthCallbackRequest,
    LoginRequest,
    OAuthCallbackRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    TwoFALoginRequest,
    TwoFARequiredResponse,
    UserResponse,
    Verify2FARequest,
)
from backend.auth.dependencies import CurrentUser, require_auth
from backend.auth.google_oauth import exchange_code, fetch_userinfo
from backend.auth.jwt import create_access_token, create_refresh_token, decode_token
from backend.auth.kakao_oauth import exchange_kakao_code, fetch_kakao_userinfo
from backend.auth.password import hash_password, verify_password
from backend.auth.token_store import delete_auth_token, get_auth_token, save_auth_token
from backend.common.audit import write_audit_log
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.users import (
    create_identity,
    create_user,
    get_identity,
    get_identity_by_provider_uid,
    get_user_by_email,
    get_user_by_id,
    update_2fa,
    update_password_hash,
    update_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = structlog.get_logger(__name__)

_EMAIL_VERIFY_PREFIX = "email_verify"
_EMAIL_VERIFY_TTL = 3600  # 1 hour
_PASSWORD_RESET_PREFIX = "password_reset"  # noqa: S105
_PASSWORD_RESET_TTL = 3600  # 1 hour
_2FA_CHALLENGE_TTL_MINUTES = 5


# ---------------------------------------------------------------------------
# Email register
# ---------------------------------------------------------------------------


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, request: Request) -> TokenResponse:
    """Create a new user with email + password."""
    try:
        pool = request.app.state.db_pool

        existing = await get_user_by_email(pool, body.email)
        if existing:
            raise http_error(ErrorCode.DUPLICATE_ENTRY, "Email already registered", status_code=409)

        user = await create_user(
            pool,
            email=body.email,
            display_name=body.display_name,
            locale=body.locale,
        )
        await create_identity(
            pool,
            user_id=user["id"],
            provider="email",
            password_hash=hash_password(body.password),
        )

        logger.info("user_registered", user_id=user["id"])
        return TokenResponse(
            access_token=create_access_token(user["id"], user["plan"], user["role"]),
            refresh_token=create_refresh_token(user["id"]),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("register_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Registration failed", status_code=500) from exc


# ---------------------------------------------------------------------------
# Email login (with 2FA support)
# ---------------------------------------------------------------------------


@router.post("/login", response_model=None)
async def login(body: LoginRequest, request: Request) -> TokenResponse | JSONResponse:
    """Authenticate with email + password. Returns 202 if 2FA is required."""
    try:
        pool = request.app.state.db_pool

        user = await get_user_by_email(pool, body.email)
        if not user:
            raise http_error(ErrorCode.UNAUTHORIZED, "Invalid credentials", status_code=401)

        identity = await get_identity(pool, user_id=user["id"], provider="email")
        if not identity or not identity["password_hash"]:
            raise http_error(ErrorCode.UNAUTHORIZED, "Invalid credentials", status_code=401)

        if not verify_password(body.password, identity["password_hash"]):
            raise http_error(ErrorCode.UNAUTHORIZED, "Invalid credentials", status_code=401)

        if not user["is_active"]:
            raise http_error(ErrorCode.FORBIDDEN, "Account deactivated", status_code=403)

        # Check if 2FA is enabled
        if identity["two_fa_enabled"]:
            import jwt as pyjwt

            challenge_payload = {
                "sub": user["id"],
                "type": "2fa_challenge",
            }
            from datetime import datetime, timedelta, timezone

            challenge_payload["iat"] = datetime.now(tz=timezone.utc)
            challenge_payload["exp"] = datetime.now(tz=timezone.utc) + timedelta(
                minutes=_2FA_CHALLENGE_TTL_MINUTES
            )
            from backend.auth.jwt import ALGORITHM, _secret

            challenge_token = pyjwt.encode(challenge_payload, _secret(), algorithm=ALGORITHM)

            logger.info("2fa_challenge_issued", user_id=user["id"])
            return JSONResponse(
                status_code=202,
                content=TwoFARequiredResponse(
                    requires_2fa=True,
                    challenge_token=challenge_token,
                ).model_dump(),
            )

        logger.info("user_logged_in", user_id=user["id"])
        return TokenResponse(
            access_token=create_access_token(user["id"], user["plan"], user["role"]),
            refresh_token=create_refresh_token(user["id"]),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("login_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Login failed", status_code=500) from exc


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, request: Request) -> TokenResponse:
    """Issue a new access token using a valid refresh token."""
    try:
        payload = decode_token(body.refresh_token)
    except Exception as exc:
        raise http_error(
            ErrorCode.TOKEN_EXPIRED, "Invalid or expired refresh token", status_code=401
        ) from exc

    if payload.get("type") != "refresh":
        raise http_error(ErrorCode.UNAUTHORIZED, "Not a refresh token", status_code=401)

    user_id = payload["sub"]
    try:
        pool = request.app.state.db_pool
        user = await get_user_by_id(pool, user_id)
    except Exception as exc:
        raise http_error(ErrorCode.DB_ERROR, "Token refresh failed", status_code=500) from exc

    if not user or not user["is_active"]:
        raise http_error(ErrorCode.UNAUTHORIZED, "User not found or deactivated", status_code=401)

    return TokenResponse(
        access_token=create_access_token(user["id"], user["plan"], user["role"]),
        refresh_token=create_refresh_token(user["id"]),
    )


# ---------------------------------------------------------------------------
# Logout (client-side token drop -- stub for future deny-list)
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=204, response_class=Response)
async def logout(_current_user: CurrentUser = Depends(require_auth)) -> Response:  # noqa: B008
    """Logout -- client should discard tokens. Server-side deny-list TBD."""
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------


@router.post("/oauth/google", response_model=TokenResponse)
async def oauth_google(body: OAuthCallbackRequest, request: Request) -> TokenResponse:
    """Exchange Google authorization code for TrendScope tokens."""
    try:
        tokens = await exchange_code(body.code, body.redirect_uri)
        userinfo = await fetch_userinfo(tokens["access_token"])
    except Exception as exc:
        logger.error("google_oauth_failed", error=str(exc))
        raise http_error(ErrorCode.OAUTH_FAILED, "Google OAuth failed", status_code=502) from exc

    google_uid: str = userinfo["sub"]
    email: str = userinfo.get("email", "")
    display_name: str | None = userinfo.get("name")

    try:
        pool = request.app.state.db_pool

        identity = await get_identity_by_provider_uid(
            pool, provider="google", provider_uid=google_uid
        )

        if identity:
            user = await get_user_by_id(pool, identity["user_id"])
        else:
            # Upsert: find by email or create new
            user = await get_user_by_email(pool, email)
            if not user:
                user = await create_user(pool, email=email, display_name=display_name)
            await create_identity(
                pool, user_id=user["id"], provider="google", provider_uid=google_uid
            )

        if not user["is_active"]:
            raise http_error(ErrorCode.FORBIDDEN, "Account deactivated", status_code=403)

        logger.info("google_oauth_success", user_id=user["id"])
        return TokenResponse(
            access_token=create_access_token(user["id"], user["plan"], user["role"]),
            refresh_token=create_refresh_token(user["id"]),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("oauth_google_db_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "OAuth login failed", status_code=500) from exc


# ---------------------------------------------------------------------------
# Kakao OAuth
# ---------------------------------------------------------------------------


@router.post("/oauth/kakao", response_model=TokenResponse)
async def oauth_kakao(body: KakaoOAuthCallbackRequest, request: Request) -> TokenResponse:
    """Exchange Kakao authorization code for TrendScope tokens."""
    try:
        tokens = await exchange_kakao_code(body.code, body.redirect_uri)
        userinfo = await fetch_kakao_userinfo(tokens["access_token"])
    except Exception as exc:
        logger.error("kakao_oauth_failed", error=str(exc))
        raise http_error(ErrorCode.OAUTH_FAILED, "Kakao OAuth failed", status_code=502) from exc

    kakao_uid: str = userinfo["uid"]
    email: str | None = userinfo.get("email")

    if not email:
        raise http_error(ErrorCode.OAUTH_FAILED, "Kakao email not available", status_code=400)

    try:
        pool = request.app.state.db_pool

        identity = await get_identity_by_provider_uid(
            pool, provider="kakao", provider_uid=kakao_uid
        )

        if identity:
            user = await get_user_by_id(pool, identity["user_id"])
        else:
            user = await get_user_by_email(pool, email)
            if not user:
                user = await create_user(pool, email=email, display_name=None)
            await create_identity(
                pool, user_id=user["id"], provider="kakao", provider_uid=kakao_uid
            )

        if not user["is_active"]:
            raise http_error(ErrorCode.FORBIDDEN, "Account deactivated", status_code=403)

        logger.info("kakao_oauth_success", user_id=user["id"])
        return TokenResponse(
            access_token=create_access_token(user["id"], user["plan"], user["role"]),
            refresh_token=create_refresh_token(user["id"]),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("oauth_kakao_db_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "OAuth login failed", status_code=500) from exc


# ---------------------------------------------------------------------------
# Current user info
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def me(  # type: ignore[assignment]
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> UserResponse:
    """Return the authenticated user's profile."""
    try:
        pool = request.app.state.db_pool
        user = await get_user_by_id(pool, current_user.user_id)
    except Exception as exc:
        logger.error("me_fetch_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to fetch user", status_code=500) from exc

    if not user:
        raise http_error(ErrorCode.NOT_FOUND, "User not found", status_code=404)

    return UserResponse(
        id=user["id"],
        email=user["email"],
        display_name=user["display_name"],
        role=user["role"],
        locale=user["locale"],
        plan=user["plan"],
    )


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
        await save_auth_token(_EMAIL_VERIFY_PREFIX, token, current_user.user_id, _EMAIL_VERIFY_TTL)
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
        user_id = await get_auth_token(_EMAIL_VERIFY_PREFIX, token)
        if not user_id:
            raise http_error(
                ErrorCode.TOKEN_EXPIRED,
                "Invalid or expired verification token",
                status_code=400,
            )

        pool = request.app.state.db_pool
        await update_user(pool, user_id, email_verified=True)
        await delete_auth_token(_EMAIL_VERIFY_PREFIX, token)

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
            await save_auth_token(_PASSWORD_RESET_PREFIX, token, user["id"], _PASSWORD_RESET_TTL)
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
        user_id = await get_auth_token(_PASSWORD_RESET_PREFIX, body.token)
        if not user_id:
            raise http_error(
                ErrorCode.TOKEN_EXPIRED,
                "Invalid or expired reset token",
                status_code=400,
            )

        pool = request.app.state.db_pool
        new_hash = hash_password(body.new_password)
        await update_password_hash(pool, user_id, new_hash)
        await delete_auth_token(_PASSWORD_RESET_PREFIX, body.token)

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
