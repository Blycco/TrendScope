"""Basic auth endpoints: register, login, refresh, logout, me."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from backend.api.routers.auth._constants import _2FA_CHALLENGE_TTL_MINUTES
from backend.api.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    TwoFARequiredResponse,
    UserResponse,
)
from backend.auth.dependencies import CurrentUser, require_auth
from backend.auth.jwt import (
    ALGORITHM,
    _secret,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from backend.auth.password import hash_password, verify_password
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.users import (
    create_identity,
    create_user,
    get_identity,
    get_user_by_email,
    get_user_by_id,
)

router = APIRouter(tags=["auth"])
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
            challenge_payload = {
                "sub": user["id"],
                "type": "2fa_challenge",
                "iat": datetime.now(tz=timezone.utc),
                "exp": datetime.now(tz=timezone.utc)
                + timedelta(minutes=_2FA_CHALLENGE_TTL_MINUTES),
            }
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
    try:
        return Response(status_code=204)
    except Exception as exc:
        logger.error("logout_failed", error=str(exc))
        raise


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
