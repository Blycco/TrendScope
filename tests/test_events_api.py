"""Tests for event tracking endpoints: batch insert."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-events")


@pytest.fixture
async def events_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
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


class TestBatchEvents:
    async def test_batch_events_success(
        self, events_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.executemany = AsyncMock()
        conn.execute = AsyncMock()

        resp = await events_client.post(
            "/api/v1/events/batch",
            json={
                "events": [
                    {
                        "action": "view",
                        "item_type": "article",
                        "item_id": "00000000-0000-0000-0000-000000000001",
                    },
                    {"action": "click", "dwell_ms": 5000},
                ]
            },
            headers=_auth_header(),
        )
        assert resp.status_code == 201
        assert resp.json()["inserted"] == 2

    async def test_batch_events_empty(
        self, events_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.execute = AsyncMock()

        resp = await events_client.post(
            "/api/v1/events/batch",
            json={"events": []},
            headers=_auth_header(),
        )
        assert resp.status_code == 201
        assert resp.json()["inserted"] == 0

    async def test_batch_events_requires_auth(self, events_client: AsyncClient) -> None:
        resp = await events_client.post(
            "/api/v1/events/batch",
            json={"events": [{"action": "view"}]},
        )
        assert resp.status_code == 401
