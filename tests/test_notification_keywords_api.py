"""Tests for keyword alert endpoints: POST/DELETE /notifications/keywords."""

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
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-kw")


def _make_token(plan: str, user_id: str = "00000000-0000-0000-0000-000000000001") -> str:
    from backend.auth.jwt import create_access_token

    return create_access_token(user_id, plan, "general")


def _make_keyword_row(
    keyword: str = "AI",
    kw_id: str = "00000000-0000-0000-0000-000000000010",
    user_id: str = "00000000-0000-0000-0000-000000000001",
    alert_surge: bool = True,
    alert_daily: bool = False,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": kw_id,
        "user_id": user_id,
        "keyword": keyword,
        "alert_surge": alert_surge,
        "alert_daily": alert_daily,
        "created_at": datetime(2026, 3, 19, 0, 0, 0, tzinfo=timezone.utc),
    }[key]
    return row


@pytest.fixture
async def kw_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
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
# GET /api/v1/notifications/keywords
# ---------------------------------------------------------------------------


class TestListKeywords:
    async def test_pro_user_lists_empty(
        self, kw_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[])
        resp = await kw_client.get(
            "/api/v1/notifications/keywords",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["keywords"] == []

    async def test_pro_user_lists_keywords(
        self, kw_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[_make_keyword_row("트렌드")]
        )
        resp = await kw_client.get(
            "/api/v1/notifications/keywords",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["keywords"][0]["keyword"] == "트렌드"

    async def test_free_user_gets_403(self, kw_client: AsyncClient) -> None:
        token = _make_token("free")
        resp = await kw_client.get(
            "/api/v1/notifications/keywords",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_gets_401(self, kw_client: AsyncClient) -> None:
        resp = await kw_client.get("/api/v1/notifications/keywords")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/notifications/keywords
# ---------------------------------------------------------------------------


class TestAddKeyword:
    async def test_pro_user_adds_keyword(
        self, kw_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=2)  # current count = 2 (< 5)
        conn.fetchrow = AsyncMock(return_value=_make_keyword_row("AI"))

        resp = await kw_client.post(
            "/api/v1/notifications/keywords",
            headers={"Authorization": f"Bearer {token}"},
            json={"keyword": "AI"},
        )
        assert resp.status_code == 201
        assert resp.json()["keyword"] == "AI"

    async def test_pro_user_at_limit_gets_403(
        self, kw_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=5)  # already at limit

        resp = await kw_client.post(
            "/api/v1/notifications/keywords",
            headers={"Authorization": f"Bearer {token}"},
            json={"keyword": "NewKeyword"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "E0030"

    async def test_business_user_exceeds_pro_limit(
        self, kw_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """Business users are not count-limited."""
        token = _make_token("business")
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_keyword_row("키워드6"))

        resp = await kw_client.post(
            "/api/v1/notifications/keywords",
            headers={"Authorization": f"Bearer {token}"},
            json={"keyword": "키워드6"},
        )
        assert resp.status_code == 201

    async def test_free_user_gets_403(self, kw_client: AsyncClient) -> None:
        token = _make_token("free")
        resp = await kw_client.post(
            "/api/v1/notifications/keywords",
            headers={"Authorization": f"Bearer {token}"},
            json={"keyword": "test"},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_gets_401(self, kw_client: AsyncClient) -> None:
        resp = await kw_client.post("/api/v1/notifications/keywords", json={"keyword": "x"})
        assert resp.status_code == 401

    async def test_db_error_returns_500(
        self, kw_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("business")
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(side_effect=RuntimeError("DB 오류"))

        resp = await kw_client.post(
            "/api/v1/notifications/keywords",
            headers={"Authorization": f"Bearer {token}"},
            json={"keyword": "fail"},
        )
        assert resp.status_code == 500
        assert resp.json()["code"] == "E0040"


# ---------------------------------------------------------------------------
# DELETE /api/v1/notifications/keywords/{id}
# ---------------------------------------------------------------------------


class TestDeleteKeyword:
    async def test_pro_user_deletes_own_keyword(
        self, kw_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        mock_db_pool.acquire.return_value.__aenter__.return_value.execute = AsyncMock(
            return_value="DELETE 1"
        )
        resp = await kw_client.delete(
            "/api/v1/notifications/keywords/00000000-0000-0000-0000-000000000010",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

    async def test_delete_not_found_returns_404(
        self, kw_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        mock_db_pool.acquire.return_value.__aenter__.return_value.execute = AsyncMock(
            return_value="DELETE 0"
        )
        resp = await kw_client.delete(
            "/api/v1/notifications/keywords/00000000-0000-0000-0000-000000000099",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_unauthenticated_gets_401(self, kw_client: AsyncClient) -> None:
        resp = await kw_client.delete(
            "/api/v1/notifications/keywords/00000000-0000-0000-0000-000000000010"
        )
        assert resp.status_code == 401

    async def test_db_error_returns_500(
        self, kw_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        mock_db_pool.acquire.return_value.__aenter__.return_value.execute = AsyncMock(
            side_effect=RuntimeError("DB 오류")
        )
        resp = await kw_client.delete(
            "/api/v1/notifications/keywords/00000000-0000-0000-0000-000000000010",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 500
        assert resp.json()["code"] == "E0040"


# ---------------------------------------------------------------------------
# PATCH /api/v1/notifications/keywords/{id}
# ---------------------------------------------------------------------------


class TestPatchKeywordAlerts:
    async def test_updates_alert_flags(
        self, kw_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(
            return_value=_make_keyword_row(alert_surge=False, alert_daily=True)
        )

        resp = await kw_client.patch(
            "/api/v1/notifications/keywords/00000000-0000-0000-0000-000000000010",
            headers={"Authorization": f"Bearer {token}"},
            json={"alert_surge": False, "alert_daily": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["alert_surge"] is False
        assert body["alert_daily"] is True

    async def test_patch_not_found_returns_404(
        self, kw_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            return_value=None
        )
        resp = await kw_client.patch(
            "/api/v1/notifications/keywords/00000000-0000-0000-0000-000000000099",
            headers={"Authorization": f"Bearer {token}"},
            json={"alert_surge": True, "alert_daily": False},
        )
        assert resp.status_code == 404

    async def test_unauthenticated_gets_401(self, kw_client: AsyncClient) -> None:
        resp = await kw_client.patch(
            "/api/v1/notifications/keywords/00000000-0000-0000-0000-000000000010",
            json={"alert_surge": True, "alert_daily": True},
        )
        assert resp.status_code == 401
