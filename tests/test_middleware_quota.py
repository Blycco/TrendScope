"""Tests for QuotaMiddleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.auth.jwt import create_access_token


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-quota")


def _make_token(user_id: str = "u1", plan: str = "free") -> str:
    return create_access_token(user_id, plan, "general")


def _make_db_pool(usage_count: int | None = 0) -> MagicMock:
    """Mock asyncpg pool. usage_count=None means no row found."""
    pool = MagicMock()
    conn = AsyncMock()

    if usage_count is None:
        conn.fetchrow = AsyncMock(return_value=None)
    else:
        row = {"usage_count": usage_count}
        conn.fetchrow = AsyncMock(return_value=row)

    conn.execute = AsyncMock(return_value=None)

    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


@pytest.fixture
def mini_app():  # noqa: ANN201
    from backend.api.middleware.quota import QuotaMiddleware
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()
    app.add_middleware(QuotaMiddleware)

    @app.get("/api/v1/trends")
    async def trends():  # noqa: ANN201
        return JSONResponse({"ok": True})

    @app.post("/api/v1/scraps")
    async def scraps():  # noqa: ANN201
        return JSONResponse({"ok": True})

    @app.get("/api/v1/content/ideas")
    async def content_ideas():  # noqa: ANN201
        return JSONResponse({"ok": True})

    @app.get("/api/v1/health")
    async def health():  # noqa: ANN201
        return JSONResponse({"ok": True})

    return app


@pytest.fixture
async def client(mini_app):  # noqa: ANN001, ANN201
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=mini_app), base_url="http://test") as ac:
        yield ac


class TestGetQuotaLimit:
    def test_trends_free_limit_10(self) -> None:
        from backend.api.middleware.quota import _get_quota_limit

        quota_type, limit = _get_quota_limit("/api/v1/trends", 0)
        assert quota_type == "daily_trends"
        assert limit == 10

    def test_trends_pro_unlimited(self) -> None:
        from backend.api.middleware.quota import _get_quota_limit

        quota_type, limit = _get_quota_limit("/api/v1/trends", 1)
        assert limit is None

    def test_scraps_free_limit_50(self) -> None:
        from backend.api.middleware.quota import _get_quota_limit

        quota_type, limit = _get_quota_limit("/api/v1/scraps", 0)
        assert quota_type == "daily_scraps"
        assert limit == 50

    def test_content_ideas_free_blocked(self) -> None:
        from backend.api.middleware.quota import _get_quota_limit

        quota_type, limit = _get_quota_limit("/api/v1/content/ideas", 0)
        assert quota_type == "daily_content_ideas"
        assert limit == -1

    def test_content_ideas_pro_limit_5(self) -> None:
        from backend.api.middleware.quota import _get_quota_limit

        quota_type, limit = _get_quota_limit("/api/v1/content/ideas", 1)
        assert limit == 5

    def test_content_ideas_business_unlimited(self) -> None:
        from backend.api.middleware.quota import _get_quota_limit

        quota_type, limit = _get_quota_limit("/api/v1/content/ideas", 2)
        assert limit is None

    def test_ungated_path_returns_none(self) -> None:
        from backend.api.middleware.quota import _get_quota_limit

        quota_type, limit = _get_quota_limit("/api/v1/health", 0)
        assert quota_type is None
        assert limit is None


class TestQuotaMiddlewareIntegration:
    async def test_ungated_path_passes(self, client, mini_app) -> None:  # noqa: ANN001
        mini_app.state.db_pool = _make_db_pool()
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200

    async def test_free_trends_under_limit_passes(self, client, mini_app) -> None:  # noqa: ANN001
        mini_app.state.db_pool = _make_db_pool(usage_count=5)
        token = _make_token("u1", "free")
        resp = await client.get("/api/v1/trends", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    async def test_free_trends_at_limit_returns_429(self, client, mini_app) -> None:  # noqa: ANN001
        mini_app.state.db_pool = _make_db_pool(usage_count=10)
        token = _make_token("u1", "free")
        resp = await client.get("/api/v1/trends", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 429
        body = resp.json()
        assert body["error_code"] == "E0030"
        assert body["quota_type"] == "daily_trends"
        assert body["limit"] == 10
        assert "reset_at" in body
        assert body["upgrade_url"] == "/pricing"

    async def test_free_trends_no_row_passes(self, client, mini_app) -> None:  # noqa: ANN001
        # no row means 0 usage — should pass
        mini_app.state.db_pool = _make_db_pool(usage_count=None)
        token = _make_token("u1", "free")
        resp = await client.get("/api/v1/trends", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    async def test_pro_trends_unlimited(self, client, mini_app) -> None:  # noqa: ANN001
        # Pro user — no DB check needed (unlimited), but middleware still skips quota
        # We provide a DB pool anyway in case it runs
        mini_app.state.db_pool = _make_db_pool(usage_count=9999)
        token = _make_token("u2", "pro")
        resp = await client.get("/api/v1/trends", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    async def test_content_ideas_free_blocked(self, client, mini_app) -> None:  # noqa: ANN001
        mini_app.state.db_pool = _make_db_pool()
        token = _make_token("u3", "free")
        resp = await client.get(
            "/api/v1/content/ideas", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "E0030"

    async def test_content_ideas_pro_under_limit(self, client, mini_app) -> None:  # noqa: ANN001
        mini_app.state.db_pool = _make_db_pool(usage_count=3)
        token = _make_token("u4", "pro")
        resp = await client.get(
            "/api/v1/content/ideas", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200

    async def test_content_ideas_pro_at_limit(self, client, mini_app) -> None:  # noqa: ANN001
        mini_app.state.db_pool = _make_db_pool(usage_count=5)
        token = _make_token("u4", "pro")
        resp = await client.get(
            "/api/v1/content/ideas", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 429
        assert resp.json()["limit"] == 5

    async def test_usage_incremented_on_success(self, client, mini_app) -> None:  # noqa: ANN001
        db_pool = _make_db_pool(usage_count=2)
        mini_app.state.db_pool = db_pool
        token = _make_token("u5", "free")
        resp = await client.get("/api/v1/trends", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        # conn.execute should have been called (usage increment)
        conn = db_pool.acquire.return_value.__aenter__.return_value
        conn.execute.assert_called_once()

    async def test_delete_method_not_gated(self, client, mini_app) -> None:  # noqa: ANN001
        # DELETE is not in _GATED_METHODS so quota is skipped
        mini_app.state.db_pool = _make_db_pool(usage_count=999)
        resp = await client.delete("/api/v1/health")
        # health doesn't have DELETE but middleware skips before routing
        # 405 is fine — the middleware didn't block it with 429
        assert resp.status_code != 429
