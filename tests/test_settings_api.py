"""Tests for user settings endpoints: get and update."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-settings")


def _make_settings_row(
    *,
    user_id: str = "00000000-0000-0000-0000-000000000001",
    display_name: str = "tester",
    role: str = "general",
    locale: str = "ko",
    category_weights: dict | None = None,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": user_id,
        "display_name": display_name,
        "role": role,
        "locale": locale,
        "category_weights": category_weights or {},
    }[key]
    return row


@pytest.fixture
async def settings_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    with patch("backend.api.routers.health.get_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


def _auth_header() -> dict:
    from backend.auth.jwt import create_access_token

    token = create_access_token("00000000-0000-0000-0000-000000000001", "free", "general")
    return {"Authorization": f"Bearer {token}"}


class TestGetSettings:
    async def test_get_settings_success(
        self, settings_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_settings_row())

        resp = await settings_client.get("/api/v1/settings", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "general"
        assert data["locale"] == "ko"

    async def test_get_settings_requires_auth(self, settings_client: AsyncClient) -> None:
        resp = await settings_client.get("/api/v1/settings")
        assert resp.status_code == 401

    async def test_get_settings_user_not_found(
        self, settings_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=None)

        resp = await settings_client.get("/api/v1/settings", headers=_auth_header())
        assert resp.status_code == 404


class TestUpdateSettings:
    async def test_update_settings_success(
        self, settings_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        updated = _make_settings_row(display_name="updated name")
        conn.fetchrow = AsyncMock(return_value=updated)
        conn.execute = AsyncMock()

        resp = await settings_client.put(
            "/api/v1/settings",
            json={"display_name": "updated name"},
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "updated name"

    async def test_update_settings_requires_auth(self, settings_client: AsyncClient) -> None:
        resp = await settings_client.put("/api/v1/settings", json={"display_name": "new"})
        assert resp.status_code == 401
