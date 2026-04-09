"""Tests for GET /api/v1/trends/compare endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ID_A = "00000000-0000-0000-0000-000000000001"
ID_B = "00000000-0000-0000-0000-000000000002"
ID_C = "00000000-0000-0000-0000-000000000003"


def _make_detail(group_id: str, title: str) -> dict:
    group = MagicMock()
    group.__getitem__ = lambda self, key: {
        "id": group_id,
        "title": title,
        "category": "tech",
        "locale": "ko",
        "summary": "test",
        "score": 50.0,
        "early_trend_score": 10.0,
        "keywords": ["AI"],
        "created_at": datetime(2026, 4, 7, 0, 0, 0, tzinfo=timezone.utc),
        "direction": "steady",
    }[key]
    return {"group": group, "articles": []}


def _make_timeline_row(
    bucket_start: datetime,
    article_count: int = 1,
    source_count: int = 1,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "bucket_start": bucket_start,
        "article_count": article_count,
        "source_count": source_count,
    }[key]
    return row


def _make_token(plan: str) -> str:
    from backend.auth.jwt import create_access_token

    return create_access_token(f"user-{plan}", plan, "general")


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-compare")


@pytest.fixture
async def compare_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool
    with (
        patch("backend.api.routers.health.get_redis", return_value=mock_redis),
        patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompareAPI:
    """Tests for GET /api/v1/trends/compare."""

    async def test_compare_success(
        self, compare_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """200 with 2 valid IDs should return comparison data."""
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        detail_a = _make_detail(ID_A, "Trend A")
        detail_b = _make_detail(ID_B, "Trend B")
        timeline_rows = [
            _make_timeline_row(datetime(2026, 4, 7, i, 0, 0, tzinfo=timezone.utc), i + 1)
            for i in range(3)
        ]

        # fetchrow is called by fetch_trend_detail; fetch by fetch_trend_timeline
        conn.fetchrow = AsyncMock(side_effect=[detail_a["group"], detail_b["group"]])
        conn.fetch = AsyncMock(
            side_effect=[
                # articles for detail A
                [],
                # articles for detail B
                [],
                # timeline for A
                timeline_rows,
                # timeline for B
                timeline_rows,
            ]
        )

        token = _make_token("pro")
        resp = await compare_client.get(
            f"/api/v1/trends/compare?ids={ID_A},{ID_B}&interval=1h",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["interval"] == "1h"
        assert len(data["trends"]) == 2
        assert data["trends"][0]["group_id"] == ID_A
        assert data["trends"][1]["group_id"] == ID_B
        assert len(data["trends"][0]["points"]) == 3

    async def test_compare_forbidden_free_tier(self, compare_client: AsyncClient) -> None:
        """Free user should get 403."""
        token = _make_token("free")
        resp = await compare_client.get(
            f"/api/v1/trends/compare?ids={ID_A},{ID_B}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_compare_too_many_ids(self, compare_client: AsyncClient) -> None:
        """More than 5 IDs should return 400."""
        token = _make_token("pro")
        ids = ",".join(f"00000000-0000-0000-0000-00000000000{i}" for i in range(6))
        resp = await compare_client.get(
            f"/api/v1/trends/compare?ids={ids}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_compare_invalid_uuid(self, compare_client: AsyncClient) -> None:
        """Invalid UUID should return 400."""
        token = _make_token("pro")
        resp = await compare_client.get(
            "/api/v1/trends/compare?ids=not-a-uuid,also-bad",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_compare_empty_timeline(
        self, compare_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """200 with empty timeline points."""
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        detail_a = _make_detail(ID_A, "Trend A")
        detail_b = _make_detail(ID_B, "Trend B")

        conn.fetchrow = AsyncMock(side_effect=[detail_a["group"], detail_b["group"]])
        conn.fetch = AsyncMock(
            side_effect=[
                [],  # articles A
                [],  # articles B
                [],  # timeline A (empty)
                [],  # timeline B (empty)
            ]
        )

        token = _make_token("pro")
        resp = await compare_client.get(
            f"/api/v1/trends/compare?ids={ID_A},{ID_B}&interval=1h",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["trends"]) == 2
        assert data["trends"][0]["points"] == []
        assert data["trends"][1]["points"] == []
