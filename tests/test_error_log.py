"""Tests for backend/common/error_log.py and admin error_logs endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.common.error_log import write_error_log


def _make_pool() -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


class TestWriteErrorLog:
    @pytest.mark.asyncio
    async def test_writes_error_log(self) -> None:
        pool = _make_pool()
        await write_error_log(
            pool,
            service="api",
            message="Test error",
            error_code="E0001",
        )
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.execute.assert_awaited_once()
        sql = conn.execute.call_args[0][0]
        assert "INSERT INTO error_log" in sql

    @pytest.mark.asyncio
    async def test_writes_with_detail(self) -> None:
        pool = _make_pool()
        await write_error_log(
            pool,
            service="crawler",
            message="Crawl failed",
            severity="critical",
            detail={"url": "https://example.com", "status": 500},
        )
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fire_and_forget_on_db_error(self) -> None:
        pool = MagicMock()
        conn = AsyncMock()
        conn.execute = AsyncMock(side_effect=Exception("DB down"))
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        # Should not raise
        await write_error_log(pool, service="api", message="Test")


class TestAdminErrorLogsEndpoint:
    @pytest.fixture(autouse=True)
    def _set_jwt_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-error-log")

    @pytest.fixture
    async def admin_client(self, mock_db_pool: MagicMock, mock_redis: AsyncMock):
        from backend.api.main import create_app
        from backend.auth.dependencies import require_auth
        from backend.auth.jwt import create_access_token
        from httpx import ASGITransport, AsyncClient

        app = create_app()
        app.state.db_pool = mock_db_pool

        # Propagate db_pool to mounted admin sub-app
        for route in app.routes:
            if hasattr(route, "app") and hasattr(route.app, "state"):
                route.app.state.db_pool = mock_db_pool

        admin_user = MagicMock()
        admin_user.user_id = "admin-001"
        admin_user.plan = "business"
        admin_user.role = "admin"
        app.dependency_overrides[require_auth] = lambda: admin_user

        token = create_access_token("admin-001", "business", "admin")

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"Authorization": f"Bearer {token}"},
            ) as ac:
                yield ac
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_error_logs_empty(self, admin_client, mock_db_pool: MagicMock) -> None:
        mock_db_pool.fetchval = AsyncMock(return_value=0)
        mock_db_pool.fetch = AsyncMock(return_value=[])

        resp = await admin_client.get("/admin/v1/error-logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_error_logs_with_service_filter(
        self, admin_client, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.fetchval = AsyncMock(return_value=0)
        mock_db_pool.fetch = AsyncMock(return_value=[])

        resp = await admin_client.get("/admin/v1/error-logs?service=api")
        assert resp.status_code == 200
