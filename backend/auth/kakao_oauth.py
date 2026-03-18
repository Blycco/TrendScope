"""Kakao OAuth 2.0 token exchange and user-info fetch. (RULE 01: env only)"""

from __future__ import annotations

import os

import httpx
import structlog

logger = structlog.get_logger(__name__)

_KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"  # noqa: S105
_KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"


async def exchange_kakao_code(code: str, redirect_uri: str) -> dict:
    """Exchange a Kakao authorization code for tokens."""
    client_id = os.environ.get("KAKAO_CLIENT_ID")
    client_secret = os.environ.get("KAKAO_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("KAKAO_CLIENT_ID / KAKAO_CLIENT_SECRET not set")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _KAKAO_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.error("kakao_token_exchange_failed", error=str(exc))
        raise


async def fetch_kakao_userinfo(access_token: str) -> dict:
    """Fetch Kakao user profile using the access token.

    Returns dict with keys ``uid`` (str) and ``email`` (str | None).
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _KAKAO_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

        uid = str(data["id"])
        email: str | None = None
        kakao_account = data.get("kakao_account", {})
        if kakao_account.get("has_email") and kakao_account.get("is_email_verified"):
            email = kakao_account.get("email")

        return {"uid": uid, "email": email}
    except Exception as exc:
        logger.error("kakao_userinfo_failed", error=str(exc))
        raise
