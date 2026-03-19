"""Tests for GET /api/v1/trends/{id}/related endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-related")


def _make_trend_row(
    row_id: str = "00000000-0000-0000-0000-000000000001",
    title: str = "관련 트렌드",
    category: str = "tech",
    score: float = 0.8,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": row_id,
        "title": title,
        "category": category,
        "locale": "ko",
        "score": score,
        "early_trend_score": 0.2,
        "keywords": ["AI"],
        "created_at": datetime(2026, 3, 19, 0, 0, 0, tzinfo=timezone.utc),
        "summary": "요약",
    }[key]
    return row


@pytest.fixture
async def related_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
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
# GET /api/v1/trends/{id}/related
# ---------------------------------------------------------------------------


class TestRelatedTrends:
    async def test_returns_related_items(
        self, related_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[_make_trend_row(row_id="00000000-0000-0000-0000-000000000002")]
        )
        resp = await related_client.get(
            "/api/v1/trends/00000000-0000-0000-0000-000000000001/related"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "관련 트렌드"

    async def test_empty_related_returns_200(
        self, related_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[])
        resp = await related_client.get(
            "/api/v1/trends/00000000-0000-0000-0000-000000000001/related"
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["next_cursor"] is None

    async def test_no_auth_required(
        self, related_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """Public endpoint — no token needed."""
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[_make_trend_row()]
        )
        resp = await related_client.get(
            "/api/v1/trends/00000000-0000-0000-0000-000000000001/related"
        )
        assert resp.status_code == 200

    async def test_limit_param_respected(
        self, related_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        fetch_mock = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = fetch_mock
        await related_client.get(
            "/api/v1/trends/00000000-0000-0000-0000-000000000001/related?limit=5"
        )
        assert fetch_mock.called

    async def test_db_error_returns_500(
        self, related_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            side_effect=RuntimeError("DB 오류")
        )
        resp = await related_client.get(
            "/api/v1/trends/00000000-0000-0000-0000-000000000001/related"
        )
        assert resp.status_code == 500
        assert resp.json()["code"] == "E0040"

    async def test_multiple_related_items(
        self, related_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        rows = [
            _make_trend_row(row_id=f"00000000-0000-0000-0000-00000000000{i}") for i in range(2, 5)
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=rows
        )
        resp = await related_client.get(
            "/api/v1/trends/00000000-0000-0000-0000-000000000001/related"
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 3
