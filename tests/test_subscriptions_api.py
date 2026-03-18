"""Tests for subscription endpoints: current, checkout, cancel."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-subs")


def _make_sub_row(
    *,
    sub_id: str = "00000000-0000-0000-0000-000000000020",
    user_id: str = "00000000-0000-0000-0000-000000000001",
    plan: str = "pro",
    status: str = "active",
) -> MagicMock:
    now = datetime.now(tz=timezone.utc)
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": sub_id,
        "user_id": user_id,
        "plan": plan,
        "status": status,
        "provider": "stripe",
        "provider_sub_id": "sub_123",
        "started_at": now,
        "expires_at": None,
        "created_at": now,
    }[key]
    return row


@pytest.fixture
async def subs_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
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


class TestGetCurrentSubscription:
    async def test_get_current_with_subscription(
        self, subs_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_sub_row())

        resp = await subs_client.get("/api/v1/subscriptions/current", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "pro"
        assert data["status"] == "active"

    async def test_get_current_no_subscription(
        self, subs_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=None)

        resp = await subs_client.get("/api/v1/subscriptions/current", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json() is None

    async def test_get_current_requires_auth(self, subs_client: AsyncClient) -> None:
        resp = await subs_client.get("/api/v1/subscriptions/current")
        assert resp.status_code == 401


class TestCheckout:
    async def test_checkout_success(
        self, subs_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_sub_row())
        conn.execute = AsyncMock()

        resp = await subs_client.post(
            "/api/v1/subscriptions/checkout",
            json={"plan": "pro"},
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "checkout_url" in data
        assert "session_id" in data

    async def test_checkout_invalid_plan(self, subs_client: AsyncClient) -> None:
        resp = await subs_client.post(
            "/api/v1/subscriptions/checkout",
            json={"plan": "invalid_plan"},
            headers=_auth_header(),
        )
        assert resp.status_code == 400


class TestCancelSubscription:
    async def test_cancel_success(self, subs_client: AsyncClient, mock_db_pool: MagicMock) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        sub = _make_sub_row()
        cancelled = _make_sub_row(status="cancelled")
        conn.fetchrow = AsyncMock(side_effect=[sub, cancelled])
        conn.execute = AsyncMock()

        resp = await subs_client.post("/api/v1/subscriptions/cancel", headers=_auth_header())
        assert resp.status_code == 200

    async def test_cancel_no_subscription(
        self, subs_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=None)

        resp = await subs_client.post("/api/v1/subscriptions/cancel", headers=_auth_header())
        assert resp.status_code == 404
