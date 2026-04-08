"""OAuth endpoints: Google + Kakao (redirect flow and POST legacy).

Functions call ``_auth_pkg.exchange_code`` etc. (via the package namespace)
so that ``unittest.mock.patch("backend.api.routers.auth.exchange_code", ...)``
correctly intercepts those calls in tests.
"""

from __future__ import annotations

import os
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

# Imported as the package object so that mock.patch("backend.api.routers.auth.exchange_code")
# is respected at call time.  The circular import is safe because __init__.py
# sets exchange_code / fetch_userinfo / ... *before* importing this sub-module.
import backend.api.routers.auth as _auth_pkg
from backend.api.schemas.auth import (
    KakaoOAuthCallbackRequest,
    OAuthCallbackRequest,
    TokenResponse,
)
from backend.auth.jwt import create_access_token, create_refresh_token
from backend.common.errors import ErrorCode, http_error
from backend.common.quota_alert import handle_api_exception
from backend.db.queries.users import (
    create_identity,
    create_user,
    get_identity_by_provider_uid,
    get_user_by_email,
    get_user_by_id,
)

router = APIRouter(tags=["auth"])
logger = structlog.get_logger(__name__)

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"


# ---------------------------------------------------------------------------
# Google OAuth — redirect flow
# ---------------------------------------------------------------------------


@router.get("/oauth/google/start")
async def oauth_google_start(request: Request) -> RedirectResponse:
    """Redirect user to Google consent screen."""
    try:
        client_id = os.environ.get("OAUTH_GOOGLE_CLIENT_ID", "")
        base_url = os.environ.get("BASE_URL", "http://localhost:3000")
        redirect_uri = f"{base_url}/api/v1/auth/oauth/google/callback"
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "access_type": "offline",
                "prompt": "consent",
            }
        )
        return RedirectResponse(url=f"{_GOOGLE_AUTH_URL}?{params}")
    except Exception as exc:
        logger.error("oauth_google_start_failed", error=str(exc))
        raise


@router.get("/oauth/google/callback")
async def oauth_google_callback(code: str, request: Request) -> RedirectResponse:
    """Handle Google OAuth callback: exchange code, create/find user, redirect with tokens."""
    base_url = os.environ.get("BASE_URL", "http://localhost:3000")
    redirect_uri = f"{base_url}/api/v1/auth/oauth/google/callback"
    try:
        tokens = await _auth_pkg.exchange_code(code, redirect_uri)
        userinfo = await _auth_pkg.fetch_userinfo(tokens["access_token"])
    except Exception as exc:
        logger.error("google_oauth_callback_failed", error=str(exc))
        return RedirectResponse(url=f"{base_url}/auth/login?error=oauth_failed")

    google_uid: str = userinfo["sub"]
    email: str = userinfo.get("email", "")
    display_name: str | None = userinfo.get("name")

    try:
        pool = request.app.state.db_pool
        identity = await get_identity_by_provider_uid(
            pool,
            provider="google",
            provider_uid=google_uid,
        )
        if identity:
            user = await get_user_by_id(pool, identity["user_id"])
        else:
            user = await get_user_by_email(pool, email)
            if not user:
                user = await create_user(pool, email=email, display_name=display_name)
            await create_identity(
                pool,
                user_id=user["id"],
                provider="google",
                provider_uid=google_uid,
            )

        if not user["is_active"]:
            return RedirectResponse(url=f"{base_url}/auth/login?error=account_deactivated")

        access = create_access_token(user["id"], user["plan"], user["role"])
        refresh = create_refresh_token(user["id"])
        logger.info("google_oauth_callback_success", user_id=user["id"])
        params = urlencode({"access_token": access, "refresh_token": refresh})
        return RedirectResponse(url=f"{base_url}/auth/callback?{params}")
    except Exception as exc:
        logger.error("google_oauth_callback_db_failed", error=str(exc))
        return RedirectResponse(url=f"{base_url}/auth/login?error=oauth_failed")


# ---------------------------------------------------------------------------
# Google OAuth — POST (legacy)
# ---------------------------------------------------------------------------


@router.post("/oauth/google", response_model=TokenResponse)
async def oauth_google(body: OAuthCallbackRequest, request: Request) -> TokenResponse:
    """Exchange Google authorization code for TrendScope tokens."""
    try:
        tokens = await _auth_pkg.exchange_code(body.code, body.redirect_uri)
        userinfo = await _auth_pkg.fetch_userinfo(tokens["access_token"])
    except Exception as exc:
        logger.error("google_oauth_failed", error=str(exc))
        await handle_api_exception(exc, "google_oauth", request.app.state.db_pool)
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
# Kakao OAuth — redirect flow
# ---------------------------------------------------------------------------


@router.get("/oauth/kakao/start")
async def oauth_kakao_start(request: Request) -> RedirectResponse:
    """Redirect user to Kakao consent screen."""
    try:
        client_id = os.environ.get("KAKAO_CLIENT_ID", "")
        base_url = os.environ.get("BASE_URL", "http://localhost:3000")
        redirect_uri = f"{base_url}/api/v1/auth/oauth/kakao/callback"
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
            }
        )
        return RedirectResponse(url=f"{_KAKAO_AUTH_URL}?{params}")
    except Exception as exc:
        logger.error("oauth_kakao_start_failed", error=str(exc))
        raise


@router.get("/oauth/kakao/callback")
async def oauth_kakao_callback(code: str, request: Request) -> RedirectResponse:
    """Handle Kakao OAuth callback: exchange code, create/find user, redirect with tokens."""
    base_url = os.environ.get("BASE_URL", "http://localhost:3000")
    redirect_uri = f"{base_url}/api/v1/auth/oauth/kakao/callback"
    try:
        tokens = await _auth_pkg.exchange_kakao_code(code, redirect_uri)
        userinfo = await _auth_pkg.fetch_kakao_userinfo(tokens["access_token"])
    except Exception as exc:
        logger.error("kakao_oauth_callback_failed", error=str(exc))
        return RedirectResponse(url=f"{base_url}/auth/login?error=oauth_failed")

    kakao_uid: str = userinfo["uid"]
    email: str | None = userinfo.get("email")
    if not email:
        return RedirectResponse(url=f"{base_url}/auth/login?error=kakao_no_email")

    try:
        pool = request.app.state.db_pool
        identity = await get_identity_by_provider_uid(
            pool,
            provider="kakao",
            provider_uid=kakao_uid,
        )
        if identity:
            user = await get_user_by_id(pool, identity["user_id"])
        else:
            user = await get_user_by_email(pool, email)
            if not user:
                user = await create_user(pool, email=email, display_name=None)
            await create_identity(
                pool,
                user_id=user["id"],
                provider="kakao",
                provider_uid=kakao_uid,
            )

        if not user["is_active"]:
            return RedirectResponse(url=f"{base_url}/auth/login?error=account_deactivated")

        access = create_access_token(user["id"], user["plan"], user["role"])
        refresh = create_refresh_token(user["id"])
        logger.info("kakao_oauth_callback_success", user_id=user["id"])
        params = urlencode({"access_token": access, "refresh_token": refresh})
        return RedirectResponse(url=f"{base_url}/auth/callback?{params}")
    except Exception as exc:
        logger.error("kakao_oauth_callback_db_failed", error=str(exc))
        return RedirectResponse(url=f"{base_url}/auth/login?error=oauth_failed")


# ---------------------------------------------------------------------------
# Kakao OAuth — POST (legacy)
# ---------------------------------------------------------------------------


@router.post("/oauth/kakao", response_model=TokenResponse)
async def oauth_kakao(body: KakaoOAuthCallbackRequest, request: Request) -> TokenResponse:
    """Exchange Kakao authorization code for TrendScope tokens."""
    try:
        tokens = await _auth_pkg.exchange_kakao_code(body.code, body.redirect_uri)
        userinfo = await _auth_pkg.fetch_kakao_userinfo(tokens["access_token"])
    except Exception as exc:
        logger.error("kakao_oauth_failed", error=str(exc))
        await handle_api_exception(exc, "kakao_oauth", request.app.state.db_pool)
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
