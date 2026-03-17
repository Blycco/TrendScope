"""Tests for auth endpoints: register, login, logout, refresh, oauth, me."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-auth-tests")


def _make_user_row(
    *,
    user_id: str = "00000000-0000-0000-0000-000000000001",
    email: str = "test@example.com",
    display_name: str | None = "테스터",
    role: str = "general",
    locale: str = "ko",
    plan: str = "free",
    is_active: bool = True,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": user_id,
        "email": email,
        "display_name": display_name,
        "role": role,
        "locale": locale,
        "plan": plan,
        "is_active": is_active,
    }[key]
    return row


def _make_identity_row(
    *,
    user_id: str = "00000000-0000-0000-0000-000000000001",
    provider: str = "email",
    password_hash: str | None = None,
) -> MagicMock:
    from backend.auth.password import hash_password

    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": "id-1",
        "user_id": user_id,
        "provider": provider,
        "provider_uid": None,
        "password_hash": password_hash or hash_password("password123"),
    }[key]
    return row


@pytest.fixture
async def auth_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    with patch("backend.api.routers.health.get_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_register_success(
        self, auth_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(side_effect=[None, _make_user_row()])
        conn.execute = AsyncMock()

        resp = await auth_client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "pass123"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"  # noqa: S105

    async def test_register_duplicate_email(
        self, auth_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_user_row())

        resp = await auth_client.post(
            "/api/v1/auth/register",
            json={"email": "existing@example.com", "password": "pass123"},
        )
        assert resp.status_code == 409

    async def test_register_invalid_email(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "pass123"},
        )
        assert resp.status_code == 422

    async def test_register_db_error_returns_500(
        self, auth_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(side_effect=[None, Exception("DB 장애")])

        resp = await auth_client.post(
            "/api/v1/auth/register",
            json={"email": "err@example.com", "password": "pass123"},
        )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_login_success(self, auth_client: AsyncClient, mock_db_pool: MagicMock) -> None:
        user = _make_user_row()
        identity = _make_identity_row()
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(side_effect=[user, identity])

        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password(
        self, auth_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        user = _make_user_row()
        identity = _make_identity_row()
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(side_effect=[user, identity])

        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    async def test_login_user_not_found(
        self, auth_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=None)

        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "pass"},
        )
        assert resp.status_code == 401

    async def test_login_deactivated_account(
        self, auth_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        user = _make_user_row(is_active=False)
        identity = _make_identity_row()
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(side_effect=[user, identity])

        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    async def test_refresh_success(self, auth_client: AsyncClient, mock_db_pool: MagicMock) -> None:
        from backend.auth.jwt import create_refresh_token

        user = _make_user_row()
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=user)

        token = create_refresh_token("00000000-0000-0000-0000-000000000001")
        resp = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_refresh_invalid_token(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "bad.token.here"}
        )
        assert resp.status_code == 401

    async def test_refresh_access_token_rejected(self, auth_client: AsyncClient) -> None:
        from backend.auth.jwt import create_access_token

        token = create_access_token("user-1", "free", "general")
        resp = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------


class TestLogout:
    async def test_logout_with_valid_token(self, auth_client: AsyncClient) -> None:
        from backend.auth.jwt import create_access_token

        token = create_access_token("user-1", "free", "general")
        resp = await auth_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

    async def test_logout_without_token_returns_401(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.post("/api/v1/auth/logout")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------


class TestMe:
    async def test_me_returns_user_info(
        self, auth_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        from backend.auth.jwt import create_access_token

        user = _make_user_row()
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=user)

        token = create_access_token("00000000-0000-0000-0000-000000000001", "free", "general")
        resp = await auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["plan"] == "free"

    async def test_me_without_token_returns_401(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.get("/api/v1/auth/me")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/auth/oauth/google
# ---------------------------------------------------------------------------


class TestOAuthGoogle:
    async def test_google_oauth_new_user(
        self, auth_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        # identity lookup → None, email lookup → None, create user → row, create identity → None
        new_user = _make_user_row()
        conn.fetchrow = AsyncMock(side_effect=[None, None, new_user, new_user])
        conn.execute = AsyncMock()

        with (
            patch(
                "backend.api.routers.auth.exchange_code",
                AsyncMock(return_value={"access_token": "goog-token"}),
            ),
            patch(
                "backend.api.routers.auth.fetch_userinfo",
                AsyncMock(
                    return_value={
                        "sub": "google-uid-123",
                        "email": "new@example.com",
                        "name": "New User",
                    }
                ),
            ),
        ):
            resp = await auth_client.post(
                "/api/v1/auth/oauth/google",
                json={"code": "auth-code", "redirect_uri": "http://localhost/callback"},
            )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_google_oauth_existing_user(
        self, auth_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        existing_user = _make_user_row()
        identity = _make_identity_row(provider="google")
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(side_effect=[identity, existing_user])

        with (
            patch(
                "backend.api.routers.auth.exchange_code",
                AsyncMock(return_value={"access_token": "goog-token"}),
            ),
            patch(
                "backend.api.routers.auth.fetch_userinfo",
                AsyncMock(
                    return_value={
                        "sub": "google-uid-123",
                        "email": "test@example.com",
                        "name": "테스터",
                    }
                ),
            ),
        ):
            resp = await auth_client.post(
                "/api/v1/auth/oauth/google",
                json={"code": "auth-code", "redirect_uri": "http://localhost/callback"},
            )
        assert resp.status_code == 200

    async def test_google_oauth_provider_error_returns_502(self, auth_client: AsyncClient) -> None:
        with patch(
            "backend.api.routers.auth.exchange_code",
            AsyncMock(side_effect=Exception("Google 연결 실패")),
        ):
            resp = await auth_client.post(
                "/api/v1/auth/oauth/google",
                json={"code": "bad-code", "redirect_uri": "http://localhost/callback"},
            )
        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Password reset stubs
# ---------------------------------------------------------------------------


class TestPasswordStubs:
    async def test_forgot_password_returns_501(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.post("/api/v1/auth/password/forgot")
        assert resp.status_code == 501

    async def test_reset_password_returns_501(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.post("/api/v1/auth/password/reset")
        assert resp.status_code == 501
