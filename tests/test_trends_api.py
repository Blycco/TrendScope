"""Tests for GET /api/v1/trends and /api/v1/trends/early endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trend_row(
    *,
    row_id: str = "00000000-0000-0000-0000-000000000001",
    title: str = "테스트 트렌드",
    category: str = "tech",
    score: float = 0.9,
    early_trend_score: float = 0.5,
    keywords: list[str] | None = None,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": row_id,
        "title": title,
        "category": category,
        "locale": "ko",
        "score": score,
        "early_trend_score": early_trend_score,
        "keywords": keywords or ["AI", "트렌드"],
        "created_at": datetime(2026, 3, 17, 0, 0, 0, tzinfo=timezone.utc),
        "summary": "요약 텍스트",
        "direction": "steady",
    }[key]
    return row


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-trends")


@pytest.fixture
def pro_auth_header() -> dict:
    from backend.auth.jwt import create_access_token

    token = create_access_token("user-pro", "pro", "general")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def trends_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
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
# GET /api/v1/trends
# ---------------------------------------------------------------------------


class TestListTrends:
    async def test_returns_200_with_items(
        self, trends_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        row = _make_trend_row()
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[row]
        )

        resp = await trends_client.get("/api/v1/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "테스트 트렌드"

    async def test_empty_result(self, trends_client: AsyncClient, mock_db_pool: MagicMock) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[])

        resp = await trends_client.get("/api/v1/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["next_cursor"] is None

    async def test_next_cursor_set_when_full_page(
        self, trends_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        rows = [
            _make_trend_row(row_id=f"00000000-0000-0000-0000-00000000000{i}") for i in range(1, 3)
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=rows
        )

        resp = await trends_client.get("/api/v1/trends?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["next_cursor"] is not None

    async def test_category_filter_passed(
        self, trends_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        fetch_mock = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = fetch_mock

        await trends_client.get("/api/v1/trends?category=finance&locale=ko")
        assert fetch_mock.called

    async def test_db_error_returns_500(
        self, trends_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            side_effect=Exception("DB연결 실패")
        )

        resp = await trends_client.get("/api/v1/trends")
        assert resp.status_code == 500
        assert resp.json()["code"] == "E0040"

    async def test_cache_hit_returns_cached_response(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        cached_body = json.dumps({"items": [], "next_cursor": None, "total": 0}).encode()

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.routers.trends.get_cached", return_value=cached_body),
            patch("backend.api.routers.trends.set_cached", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/v1/trends")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_with_cursor_skips_cache(
        self, trends_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """Cursor requests bypass cache."""
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[])
        from backend.db.queries.trends import encode_cursor

        cur = encode_cursor(0.5, "00000000-0000-0000-0000-000000000001")
        resp = await trends_client.get(f"/api/v1/trends?cursor={cur}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v1/trends/early
# ---------------------------------------------------------------------------


class TestListEarlyTrends:
    async def test_returns_200(
        self, trends_client: AsyncClient, mock_db_pool: MagicMock, pro_auth_header: dict
    ) -> None:
        row = _make_trend_row(early_trend_score=0.8)
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[row]
        )

        resp = await trends_client.get("/api/v1/trends/early", headers=pro_auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"][0]["early_trend_score"] == 0.8

    async def test_locale_filter(
        self, trends_client: AsyncClient, mock_db_pool: MagicMock, pro_auth_header: dict
    ) -> None:
        fetch_mock = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = fetch_mock

        resp = await trends_client.get("/api/v1/trends/early?locale=en", headers=pro_auth_header)
        assert resp.status_code == 200

    async def test_db_error_returns_500(
        self, trends_client: AsyncClient, mock_db_pool: MagicMock, pro_auth_header: dict
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            side_effect=RuntimeError("연결 끊김")
        )
        resp = await trends_client.get("/api/v1/trends/early", headers=pro_auth_header)
        assert resp.status_code == 500

    async def test_next_cursor_on_full_page(
        self, trends_client: AsyncClient, mock_db_pool: MagicMock, pro_auth_header: dict
    ) -> None:
        rows = [
            _make_trend_row(row_id=f"00000000-0000-0000-0000-00000000000{i}") for i in range(1, 3)
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=rows
        )
        resp = await trends_client.get("/api/v1/trends/early?limit=2", headers=pro_auth_header)
        assert resp.json()["next_cursor"] is not None
