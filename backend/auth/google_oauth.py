"""Google OAuth 2.0 token exchange and user-info fetch."""

from __future__ import annotations

import os

import httpx
import structlog

logger = structlog.get_logger(__name__)

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


async def exchange_code(code: str, redirect_uri: str) -> dict:
    """Exchange an authorization code for Google tokens."""
    client_id = os.environ.get("OAUTH_GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("OAUTH_GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("OAUTH_GOOGLE_CLIENT_ID / OAUTH_GOOGLE_CLIENT_SECRET not set")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.error("google_token_exchange_failed", error=str(exc))
        raise


async def fetch_userinfo(access_token: str) -> dict:
    """Fetch Google user profile using the access token."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.error("google_userinfo_failed", error=str(exc))
        raise
