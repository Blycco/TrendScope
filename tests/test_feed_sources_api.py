"""Tests for admin feed source CRUD API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-feed-sources")


def _auth_header(role: str = "admin") -> dict:
    from backend.auth.jwt import create_access_token

    token = create_access_token("00000000-0000-0000-0000-000000000099", "enterprise", role)
    return {"Authorization": f"Bearer {token}"}


def _general_header() -> dict:
    return _auth_header(role="general")


@pytest.fixture
async def admin_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    with (
        patch("backend.api.routers.health.get_redis", return_value=mock_redis),
        patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


def _make_feed_row(
    feed_id: str = "00000000-0000-0000-0000-000000000050",
    name: str = "Test Feed",
    url: str = "https://example.com/rss",
    source_type: str = "rss",
) -> MagicMock:
    row = MagicMock()
    data = {
        "id": feed_id,
        "source_config_id": None,
        "source_type": source_type,
        "name": name,
        "url": url,
        "category": "general",
        "locale": "ko",
        "is_active": True,
        "priority": 0,
        "config": {},
        "health_status": "unknown",
        "last_crawled_at": None,
        "last_success_at": None,
        "last_error": None,
        "last_error_at": None,
        "consecutive_failures": 0,
        "avg_latency_ms": None,
        "total_crawl_count": 0,
        "total_error_count": 0,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    row.__getitem__ = lambda self, key: data[key]
    return row


def _make_health_row(source_type: str = "rss") -> MagicMock:
    row = MagicMock()
    data = {
        "source_type": source_type,
        "total": 10,
        "healthy": 8,
        "degraded": 1,
        "error": 0,
        "unknown": 1,
    }
    row.__getitem__ = lambda self, key: data[key]
    return row


class TestListFeedSources:
    async def test_list_success(self, admin_client: AsyncClient) -> None:
        rows = [_make_feed_row()]
        with patch(
            "backend.api.routers.admin.feed_sources.list_feed_sources",
            new_callable=AsyncMock,
            return_value=(rows, 1),
        ):
            resp = await admin_client.get("/admin/v1/feed-sources", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["feeds"]) == 1
        assert data["feeds"][0]["name"] == "Test Feed"

    async def test_list_with_filters(self, admin_client: AsyncClient) -> None:
        with patch(
            "backend.api.routers.admin.feed_sources.list_feed_sources",
            new_callable=AsyncMock,
            return_value=([], 0),
        ) as mock_fn:
            resp = await admin_client.get(
                "/admin/v1/feed-sources?source_type=rss&locale=ko&page=2",
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        mock_fn.assert_awaited_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["source_type"] == "rss"
        assert call_kwargs["locale"] == "ko"
        assert call_kwargs["page"] == 2

    async def test_list_requires_admin(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.get("/admin/v1/feed-sources", headers=_general_header())
        assert resp.status_code == 403


class TestGetFeedSource:
    async def test_get_success(self, admin_client: AsyncClient) -> None:
        row = _make_feed_row()
        with patch(
            "backend.api.routers.admin.feed_sources.get_feed_source",
            new_callable=AsyncMock,
            return_value=row,
        ):
            resp = await admin_client.get("/admin/v1/feed-sources/some-id", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://example.com/rss"

    async def test_get_not_found(self, admin_client: AsyncClient) -> None:
        with patch(
            "backend.api.routers.admin.feed_sources.get_feed_source",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await admin_client.get(
                "/admin/v1/feed-sources/nonexistent", headers=_auth_header()
            )
        assert resp.status_code == 404


class TestCreateFeedSource:
    async def test_create_success(self, admin_client: AsyncClient) -> None:
        row = _make_feed_row(name="New Feed", url="https://new.com/rss")
        with patch(
            "backend.api.routers.admin.feed_sources.create_feed_source",
            new_callable=AsyncMock,
            return_value=row,
        ):
            resp = await admin_client.post(
                "/admin/v1/feed-sources",
                headers=_auth_header(),
                json={
                    "source_type": "rss",
                    "name": "New Feed",
                    "url": "https://new.com/rss",
                },
            )
        assert resp.status_code == 201
        assert resp.json()["name"] == "New Feed"

    async def test_create_invalid_source_type(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.post(
            "/admin/v1/feed-sources",
            headers=_auth_header(),
            json={
                "source_type": "invalid_type",
                "name": "Bad Feed",
                "url": "https://bad.com",
            },
        )
        assert resp.status_code == 422


class TestUpdateFeedSource:
    async def test_update_success(self, admin_client: AsyncClient) -> None:
        row = _make_feed_row(name="Updated Name")
        with patch(
            "backend.api.routers.admin.feed_sources.update_feed_source",
            new_callable=AsyncMock,
            return_value=row,
        ):
            resp = await admin_client.patch(
                "/admin/v1/feed-sources/some-id",
                headers=_auth_header(),
                json={"name": "Updated Name"},
            )
        assert resp.status_code == 200

    async def test_update_not_found(self, admin_client: AsyncClient) -> None:
        with patch(
            "backend.api.routers.admin.feed_sources.update_feed_source",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await admin_client.patch(
                "/admin/v1/feed-sources/nonexistent",
                headers=_auth_header(),
                json={"name": "X"},
            )
        assert resp.status_code == 404


class TestDeleteFeedSource:
    async def test_delete_success(self, admin_client: AsyncClient) -> None:
        with patch(
            "backend.api.routers.admin.feed_sources.delete_feed_source",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await admin_client.delete(
                "/admin/v1/feed-sources/some-id", headers=_auth_header()
            )
        assert resp.status_code == 204

    async def test_delete_not_found(self, admin_client: AsyncClient) -> None:
        with patch(
            "backend.api.routers.admin.feed_sources.delete_feed_source",
            new_callable=AsyncMock,
            return_value=False,
        ):
            resp = await admin_client.delete(
                "/admin/v1/feed-sources/nonexistent", headers=_auth_header()
            )
        assert resp.status_code == 404


class TestBulkToggle:
    async def test_bulk_toggle_success(self, admin_client: AsyncClient) -> None:
        with patch(
            "backend.api.routers.admin.feed_sources.bulk_toggle_feed_sources",
            new_callable=AsyncMock,
            return_value=3,
        ):
            resp = await admin_client.post(
                "/admin/v1/feed-sources/bulk-toggle",
                headers=_auth_header(),
                json={"feed_ids": ["a", "b", "c"], "is_active": False},
            )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 3

    async def test_bulk_toggle_empty_ids_rejected(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.post(
            "/admin/v1/feed-sources/bulk-toggle",
            headers=_auth_header(),
            json={"feed_ids": [], "is_active": True},
        )
        assert resp.status_code == 422


class TestHealthSummary:
    async def test_health_summary_success(self, admin_client: AsyncClient) -> None:
        rows = [_make_health_row("rss"), _make_health_row("reddit")]
        with patch(
            "backend.api.routers.admin.feed_sources.get_feed_health_summary",
            new_callable=AsyncMock,
            return_value=rows,
        ):
            resp = await admin_client.get(
                "/admin/v1/feed-sources/health/summary", headers=_auth_header()
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["summary"]) == 2
        assert data["summary"][0]["healthy"] == 8
