"""Tests for GET /api/v1/trends/{group_id}/timeline endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _make_timeline_row(
    bucket_start: datetime | None = None,
    article_count: int = 3,
    source_count: int = 2,
) -> MagicMock:
    row = MagicMock()
    ts = bucket_start or datetime(2026, 4, 7, 10, 0, 0, tzinfo=timezone.utc)
    row.__getitem__ = lambda self, key: {
        "bucket_start": ts,
        "article_count": article_count,
        "source_count": source_count,
    }[key]
    return row


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-timeline")


@pytest.fixture
async def timeline_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool
    with (
        patch("backend.api.routers.health.get_redis", return_value=mock_redis),
        patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


GROUP_ID = "00000000-0000-0000-0000-000000000001"


class TestTrendTimeline:
    """Tests for GET /trends/{group_id}/timeline."""

    async def test_returns_200_with_points(
        self, timeline_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        rows = [
            _make_timeline_row(
                datetime(2026, 4, 7, i, 0, 0, tzinfo=timezone.utc),
                article_count=i,
                source_count=1,
            )
            for i in range(3)
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=rows
        )
        resp = await timeline_client.get(f"/api/v1/trends/{GROUP_ID}/timeline?interval=1h")
        assert resp.status_code == 200
        data = resp.json()
        assert data["group_id"] == GROUP_ID
        assert data["interval"] == "1h"
        assert len(data["points"]) == 3
        assert data["points"][0]["article_count"] == 0
        assert data["points"][2]["article_count"] == 2

    async def test_invalid_interval_returns_422(self, timeline_client: AsyncClient) -> None:
        resp = await timeline_client.get(f"/api/v1/trends/{GROUP_ID}/timeline?interval=5m")
        assert resp.status_code == 422

    async def test_empty_returns_empty_points(
        self, timeline_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[])
        resp = await timeline_client.get(f"/api/v1/trends/{GROUP_ID}/timeline?interval=1h")
        assert resp.status_code == 200
        assert resp.json()["points"] == []

    async def test_default_interval_is_1h(
        self, timeline_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[])
        resp = await timeline_client.get(f"/api/v1/trends/{GROUP_ID}/timeline")
        assert resp.status_code == 200
        assert resp.json()["interval"] == "1h"

    async def test_cache_hit_skips_db(
        self, timeline_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        cached_body = b'{"group_id":"' + GROUP_ID.encode() + b'",' b'"interval":"1h","points":[]}'
        fetch_mock = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = fetch_mock
        with patch(
            "backend.api.routers.trends.get_cached",
            return_value=cached_body,
        ):
            resp = await timeline_client.get(f"/api/v1/trends/{GROUP_ID}/timeline?interval=1h")
        assert resp.status_code == 200
        fetch_mock.assert_not_called()

    async def test_db_error_returns_500(
        self, timeline_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            side_effect=Exception("db down")
        )
        resp = await timeline_client.get(f"/api/v1/trends/{GROUP_ID}/timeline?interval=1h")
        assert resp.status_code == 500
