"""Tests for POST /api/v1/trends/share and GET /api/v1/shared/{token} endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-shares")


def _make_token(plan: str) -> str:
    from backend.auth.jwt import create_access_token

    return create_access_token(f"user-{plan}", plan, "general")


def _make_share_row(token: str = "abc123") -> MagicMock:  # noqa: S107
    row = MagicMock()
    expires = datetime(2026, 3, 20, 0, 0, 0, tzinfo=timezone.utc)
    created = datetime(2026, 3, 19, 0, 0, 0, tzinfo=timezone.utc)
    row.__getitem__ = lambda self, key: {
        "id": "00000000-0000-0000-0000-000000000001",
        "token": token,
        "user_id": "user-business",
        "payload": {"trend_id": "t1"},
        "expires_at": expires,
        "created_at": created,
    }[key]
    return row


@pytest.fixture
async def shares_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    with (
        patch("backend.api.routers.health.get_redis", return_value=mock_redis),
        patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        patch("backend.api.routers.trends.get_cached", return_value=None),
        patch("backend.api.routers.trends.set_cached", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# POST /api/v1/trends/share
# ---------------------------------------------------------------------------


class TestCreateShareLink:
    async def test_business_user_can_create_share(
        self, shares_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("business")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            return_value=_make_share_row("tok-xyz")
        )
        resp = await shares_client.post(
            "/api/v1/trends/share",
            headers={"Authorization": f"Bearer {token}"},
            json={"payload": {"trend_id": "t1"}},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["token"] == "tok-xyz"  # noqa: S105
        assert "/shared/" in data["share_url"]
        assert "expires_at" in data

    async def test_enterprise_user_can_create_share(
        self, shares_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("enterprise")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            return_value=_make_share_row("tok-ent")
        )
        resp = await shares_client.post(
            "/api/v1/trends/share",
            headers={"Authorization": f"Bearer {token}"},
            json={"payload": {}},
        )
        assert resp.status_code == 201

    async def test_pro_user_gets_403(self, shares_client: AsyncClient) -> None:
        token = _make_token("pro")
        resp = await shares_client.post(
            "/api/v1/trends/share",
            headers={"Authorization": f"Bearer {token}"},
            json={"payload": {}},
        )
        assert resp.status_code == 403

    async def test_free_user_gets_403(self, shares_client: AsyncClient) -> None:
        token = _make_token("free")
        resp = await shares_client.post(
            "/api/v1/trends/share",
            headers={"Authorization": f"Bearer {token}"},
            json={"payload": {}},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_gets_401(self, shares_client: AsyncClient) -> None:
        resp = await shares_client.post("/api/v1/trends/share", json={"payload": {}})
        assert resp.status_code == 401

    async def test_db_error_returns_500(
        self, shares_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("business")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            side_effect=RuntimeError("DB 오류")
        )
        resp = await shares_client.post(
            "/api/v1/trends/share",
            headers={"Authorization": f"Bearer {token}"},
            json={"payload": {}},
        )
        assert resp.status_code == 500
        assert resp.json()["code"] == "E0040"


# ---------------------------------------------------------------------------
# GET /api/v1/shared/{token}
# ---------------------------------------------------------------------------


class TestGetSharedLink:
    async def test_valid_token_returns_200(
        self, shares_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            return_value=_make_share_row("valid-token")
        )
        resp = await shares_client.get("/api/v1/shared/valid-token")
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == "valid-token"  # noqa: S105
        assert "payload" in data
        assert "expires_at" in data

    async def test_missing_token_returns_404(
        self, shares_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            return_value=None
        )
        resp = await shares_client.get("/api/v1/shared/nonexistent-token")
        assert resp.status_code == 404

    async def test_no_auth_required(
        self, shares_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """Public endpoint — no token needed."""
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            return_value=_make_share_row("pub-token")
        )
        resp = await shares_client.get("/api/v1/shared/pub-token")
        assert resp.status_code == 200

    async def test_db_error_returns_500(
        self, shares_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            side_effect=RuntimeError("DB 오류")
        )
        resp = await shares_client.get("/api/v1/shared/some-token")
        assert resp.status_code == 500
        assert resp.json()["code"] == "E0040"

    async def test_payload_is_dict(
        self, shares_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            return_value=_make_share_row("tok-payload")
        )
        resp = await shares_client.get("/api/v1/shared/tok-payload")
        assert isinstance(resp.json()["payload"], dict)
