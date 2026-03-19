"""Tests for notification settings endpoints: GET and PUT /notifications/settings."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-notifs")


def _make_notif_row(
    *,
    notif_id: str = "00000000-0000-0000-0000-000000000030",
    user_id: str = "00000000-0000-0000-0000-000000000001",
    notif_type: str = "trend_alert",
    channel: str = "email",
    is_enabled: bool = True,
) -> MagicMock:
    now = datetime.now(tz=timezone.utc)
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": notif_id,
        "user_id": user_id,
        "type": notif_type,
        "channel": channel,
        "is_enabled": is_enabled,
        "created_at": now,
        "updated_at": now,
    }[key]
    return row


@pytest.fixture
async def notif_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
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


class TestGetNotificationSettings:
    async def test_get_settings_empty(
        self, notif_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(return_value=[])

        resp = await notif_client.get("/api/v1/notifications/settings", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["settings"] == []

    async def test_get_settings_with_rows(
        self, notif_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(return_value=[_make_notif_row()])

        resp = await notif_client.get("/api/v1/notifications/settings", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["settings"]) == 1
        assert data["settings"][0]["type"] == "trend_alert"
        assert data["settings"][0]["channel"] == "email"
        assert data["settings"][0]["is_enabled"] is True

    async def test_get_settings_requires_auth(self, notif_client: AsyncClient) -> None:
        resp = await notif_client.get("/api/v1/notifications/settings")
        assert resp.status_code == 401


class TestUpdateNotificationSettings:
    async def test_put_setting_creates_new(
        self, notif_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.execute = AsyncMock()
        updated_row = _make_notif_row(is_enabled=False)
        conn.fetch = AsyncMock(return_value=[updated_row])

        resp = await notif_client.put(
            "/api/v1/notifications/settings",
            json={"type": "trend_alert", "channel": "email", "is_enabled": False},
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["settings"]) == 1
        assert data["settings"][0]["is_enabled"] is False

    async def test_put_setting_requires_auth(self, notif_client: AsyncClient) -> None:
        resp = await notif_client.put(
            "/api/v1/notifications/settings",
            json={"type": "trend_alert", "channel": "email", "is_enabled": True},
        )
        assert resp.status_code == 401

    async def test_put_setting_invalid_body(self, notif_client: AsyncClient) -> None:
        resp = await notif_client.put(
            "/api/v1/notifications/settings",
            json={"type": "trend_alert"},  # missing channel and is_enabled
            headers=_auth_header(),
        )
        assert resp.status_code == 422
