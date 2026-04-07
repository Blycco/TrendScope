"""Tests for GET /api/v1/trends/early/pro (early_trend router)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.auth.dependencies import CurrentUser, require_auth
from backend.auth.jwt import create_access_token
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-early")


def _make_pro_user() -> CurrentUser:
    return CurrentUser(user_id="user-pro", plan="pro", role="general")


def _make_free_user() -> CurrentUser:
    return CurrentUser(user_id="user-free", plan="free", role="general")


def _make_trend_row(
    *,
    row_id: str = "00000000-0000-0000-0000-000000000001",
    title: str = "얼리 트렌드",
    category: str = "tech",
    score: float = 0.9,
    early_trend_score: float = 0.75,
    keywords: list[str] | None = None,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": row_id,
        "title": title,
        "category": category,
        "score": score,
        "early_trend_score": early_trend_score,
        "keywords": keywords or ["AI", "트렌드"],
        "created_at": datetime(2026, 3, 18, 0, 0, 0, tzinfo=timezone.utc),
        "direction": "steady",
    }[key]
    return row


@pytest.fixture
async def early_pro_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    pro_user = _make_pro_user()
    app.dependency_overrides[require_auth] = lambda: pro_user

    # Pro JWT so PlanGateMiddleware passes (middleware runs before Depends)
    pro_token = create_access_token("user-pro", "pro", "general")

    with (
        patch("backend.api.routers.health.get_redis", return_value=mock_redis),
        patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {pro_token}"},
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


class TestListEarlyTrendsPro:
    async def test_unauthenticated_returns_401(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        with patch("backend.api.routers.health.get_redis", return_value=mock_redis):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/v1/trends/early/pro")

        assert resp.status_code == 401

    async def test_free_plan_returns_403(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        # PlanGateMiddleware intercepts before route dependencies,
        # returning 403 (PLAN_GATE) for free users on pro-gated endpoints.
        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        free_token = create_access_token("user-free", "free", "general")

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(
                    "/api/v1/trends/early/pro",
                    headers={"Authorization": f"Bearer {free_token}"},
                )

        assert resp.status_code == 403
        assert resp.json()["code"] == "E0031"

    async def test_default_params_returns_trends(
        self, early_pro_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        row = _make_trend_row()
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[row]
        )
        resp = await early_pro_client.get("/api/v1/trends/early/pro")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "얼리 트렌드"

    async def test_next_cursor_set_when_limit_items(
        self, early_pro_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        rows = [
            _make_trend_row(row_id=f"00000000-0000-0000-0000-00000000000{i}") for i in range(1, 3)
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=rows
        )
        resp = await early_pro_client.get("/api/v1/trends/early/pro?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["next_cursor"] is not None

    async def test_next_cursor_none_when_fewer(
        self, early_pro_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        rows = [_make_trend_row()]
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=rows
        )
        resp = await early_pro_client.get("/api/v1/trends/early/pro?limit=20")
        assert resp.status_code == 200
        data = resp.json()
        assert data["next_cursor"] is None

    async def test_locale_filter_applied(
        self, early_pro_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        fetch_mock = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = fetch_mock
        resp = await early_pro_client.get("/api/v1/trends/early/pro?locale=ko")
        assert resp.status_code == 200

    async def test_db_error_returns_500(
        self, early_pro_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            side_effect=RuntimeError("DB 연결 실패")
        )
        resp = await early_pro_client.get("/api/v1/trends/early/pro")
        assert resp.status_code == 500

    async def test_response_schema_valid(
        self, early_pro_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        row = _make_trend_row(early_trend_score=0.85)
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[row]
        )
        resp = await early_pro_client.get("/api/v1/trends/early/pro")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "next_cursor" in data
        assert "total" in data
        item = data["items"][0]
        assert "id" in item
        assert "title" in item
        assert "early_trend_score" in item
        assert item["early_trend_score"] == 0.85

    async def test_cursor_pagination(
        self, early_pro_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        fetch_mock = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = fetch_mock
        from backend.db.queries.trends import encode_cursor

        cursor = encode_cursor(0.75, "00000000-0000-0000-0000-000000000001")
        resp = await early_pro_client.get(f"/api/v1/trends/early/pro?cursor={cursor}")
        assert resp.status_code == 200
