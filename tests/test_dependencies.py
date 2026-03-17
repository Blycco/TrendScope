"""Tests for auth dependencies (get_current_user, require_plan)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-deps")


class TestGetCurrentUser:
    async def test_valid_token_returns_user(self) -> None:
        from unittest.mock import MagicMock

        from backend.auth.dependencies import get_current_user
        from backend.auth.jwt import create_access_token
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token("user-1", "pro", "marketer")
        creds = MagicMock(spec=HTTPAuthorizationCredentials)
        creds.credentials = token

        user = await get_current_user(creds)
        assert user is not None
        assert user.user_id == "user-1"
        assert user.plan == "pro"
        assert user.role == "marketer"

    async def test_no_credentials_returns_none(self) -> None:
        from backend.auth.dependencies import get_current_user

        user = await get_current_user(None)
        assert user is None

    async def test_invalid_token_returns_none(self) -> None:
        from unittest.mock import MagicMock

        from backend.auth.dependencies import get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        creds = MagicMock(spec=HTTPAuthorizationCredentials)
        creds.credentials = "invalid.token.here"

        user = await get_current_user(creds)
        assert user is None

    async def test_refresh_token_returns_none(self) -> None:
        from unittest.mock import MagicMock

        from backend.auth.dependencies import get_current_user
        from backend.auth.jwt import create_refresh_token
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_refresh_token("user-2")
        creds = MagicMock(spec=HTTPAuthorizationCredentials)
        creds.credentials = token

        user = await get_current_user(creds)
        assert user is None


class TestRequirePlan:
    async def test_sufficient_plan_passes(self) -> None:
        from backend.auth.dependencies import CurrentUser, require_plan

        user = CurrentUser(user_id="u", plan="pro", role="general")
        checker = require_plan("pro")
        result = await checker(current_user=user)
        assert result.user_id == "u"

    async def test_enterprise_passes_pro_gate(self) -> None:
        from backend.auth.dependencies import CurrentUser, require_plan

        user = CurrentUser(user_id="u", plan="enterprise", role="general")
        checker = require_plan("pro")
        result = await checker(current_user=user)
        assert result is not None

    async def test_insufficient_plan_raises_403(self) -> None:
        from backend.auth.dependencies import CurrentUser, require_plan
        from fastapi import HTTPException

        user = CurrentUser(user_id="u", plan="free", role="general")
        checker = require_plan("pro")
        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=user)
        assert exc_info.value.status_code == 403
