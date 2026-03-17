"""Auth endpoints: register, login, logout, OAuth, refresh."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from backend.api.schemas.auth import (
    LoginRequest,
    OAuthCallbackRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from backend.auth.dependencies import CurrentUser, require_auth
from backend.auth.google_oauth import exchange_code, fetch_userinfo
from backend.auth.jwt import create_access_token, create_refresh_token, decode_token
from backend.auth.password import hash_password, verify_password
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.users import (
    create_identity,
    create_user,
    get_identity,
    get_identity_by_provider_uid,
    get_user_by_email,
    get_user_by_id,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = structlog.get_logger(__name__)


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
# Email login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request) -> TokenResponse:
    """Authenticate with email + password."""
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
# Logout (client-side token drop — stub for future deny-list)
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=204, response_class=Response)
async def logout(_current_user: CurrentUser = Depends(require_auth)) -> Response:  # noqa: B008
    """Logout — client should discard tokens. Server-side deny-list TBD."""
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
# Password reset stubs (501)
# ---------------------------------------------------------------------------


@router.post("/password/forgot", status_code=501)
async def forgot_password() -> dict:
    """Password reset request — not yet implemented."""
    return {"code": "E0099", "message": "Not implemented"}


@router.post("/password/reset", status_code=501)
async def reset_password() -> dict:
    """Password reset confirm — not yet implemented."""
    return {"code": "E0099", "message": "Not implemented"}
