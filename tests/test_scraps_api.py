"""Tests for scrap endpoints: create, list, delete with plan gate."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-scraps")


def _make_scrap_row(
    *,
    scrap_id: str = "00000000-0000-0000-0000-000000000010",
    user_id: str = "00000000-0000-0000-0000-000000000001",
    item_type: str = "article",
    item_id: str = "00000000-0000-0000-0000-000000000099",
) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": scrap_id,
        "user_id": user_id,
        "item_type": item_type,
        "item_id": item_id,
        "user_tags": ["tag1"],
        "memo": "note",
        "created_at": datetime.now(tz=timezone.utc),
    }[key]
    return row


@pytest.fixture
async def scraps_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    with (
        patch("backend.api.routers.health.get_redis", return_value=mock_redis),
        patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


def _auth_header() -> dict:
    from backend.auth.jwt import create_access_token

    token = create_access_token("00000000-0000-0000-0000-000000000001", "free", "general")
    return {"Authorization": f"Bearer {token}"}


def _pro_auth_header() -> dict:
    from backend.auth.jwt import create_access_token

    token = create_access_token("00000000-0000-0000-0000-000000000001", "pro", "general")
    return {"Authorization": f"Bearer {token}"}


class TestCreateScrap:
    async def test_create_scrap_success(
        self, scraps_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=10)  # scrap count
        # First fetchrow = quota middleware check (returns None = under limit),
        # subsequent calls = scrap route queries
        conn.fetchrow = AsyncMock(side_effect=[None, _make_scrap_row()])
        conn.execute = AsyncMock()

        resp = await scraps_client.post(
            "/api/v1/scraps",
            json={
                "item_type": "article",
                "item_id": "00000000-0000-0000-0000-000000000099",
                "user_tags": ["tag1"],
                "memo": "note",
            },
            headers=_auth_header(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["item_type"] == "article"

    async def test_create_scrap_free_limit(
        self, scraps_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=50)  # at limit

        resp = await scraps_client.post(
            "/api/v1/scraps",
            json={
                "item_type": "article",
                "item_id": "00000000-0000-0000-0000-000000000099",
            },
            headers=_auth_header(),
        )
        assert resp.status_code == 403

    async def test_create_scrap_pro_plan_no_limit(
        self, scraps_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=100)  # over free limit
        conn.fetchrow = AsyncMock(return_value=_make_scrap_row())
        conn.execute = AsyncMock()

        resp = await scraps_client.post(
            "/api/v1/scraps",
            json={
                "item_type": "article",
                "item_id": "00000000-0000-0000-0000-000000000099",
            },
            headers=_pro_auth_header(),
        )
        assert resp.status_code == 201

    async def test_create_scrap_requires_auth(self, scraps_client: AsyncClient) -> None:
        resp = await scraps_client.post(
            "/api/v1/scraps",
            json={"item_type": "article", "item_id": "some-id"},
        )
        assert resp.status_code == 401


class TestListScraps:
    async def test_list_scraps_success(
        self, scraps_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(return_value=[_make_scrap_row()])
        conn.fetchval = AsyncMock(return_value=1)

        resp = await scraps_client.get("/api/v1/scraps", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1


class TestDeleteScrap:
    async def test_delete_scrap_success(
        self, scraps_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.execute = AsyncMock(return_value="DELETE 1")

        resp = await scraps_client.delete(
            "/api/v1/scraps/00000000-0000-0000-0000-000000000010",
            headers=_auth_header(),
        )
        assert resp.status_code == 204

    async def test_delete_scrap_not_found(
        self, scraps_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.execute = AsyncMock(return_value="DELETE 0")

        resp = await scraps_client.delete(
            "/api/v1/scraps/00000000-0000-0000-0000-nonexistent",
            headers=_auth_header(),
        )
        assert resp.status_code == 404
