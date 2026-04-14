"""Tests for RateLimitMiddleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.auth.jwt import create_access_token


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-ratelimit")


def _make_token(user_id: str = "user-1", plan: str = "free") -> str:
    return create_access_token(user_id, plan, "general")


def _make_redis_mock(current_count: int = 0, ttl: int = 30) -> AsyncMock:
    """Return a Redis mock with configurable current counter."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=str(current_count).encode() if current_count else None)
    redis.ttl = AsyncMock(return_value=ttl)
    pipe = AsyncMock()
    pipe.incr = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[current_count + 1, True])
    redis.pipeline = MagicMock(return_value=pipe)
    return redis


@pytest.fixture
def mini_app():  # noqa: ANN201
    from backend.api.middleware.rate_limit import RateLimitMiddleware
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/api/v1/trends")
    async def trends():  # noqa: ANN201
        return JSONResponse({"ok": True})

    @app.get("/api/v1/events")
    async def events():  # noqa: ANN201
        return JSONResponse({"ok": True})

    return app


@pytest.fixture
async def client(mini_app):  # noqa: ANN001, ANN201
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=mini_app), base_url="http://test") as ac:
        yield ac


class TestGetClientIp:
    def test_forwarded_for_header(self) -> None:
        from unittest.mock import MagicMock

        from backend.api.middleware.rate_limit import _get_client_ip

        req = MagicMock()
        req.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        req.client = None
        assert _get_client_ip(req) == "1.2.3.4"

    def test_direct_client_ip(self) -> None:
        from unittest.mock import MagicMock

        from backend.api.middleware.rate_limit import _get_client_ip

        req = MagicMock()
        req.headers = {}
        req.client = MagicMock()
        req.client.host = "9.9.9.9"
        assert _get_client_ip(req) == "9.9.9.9"


class TestExtractUserId:
    def test_no_auth_returns_none(self) -> None:
        from unittest.mock import MagicMock

        from backend.api.middleware.rate_limit import _extract_user_id

        req = MagicMock()
        req.headers = {}
        assert _extract_user_id(req) is None

    def test_valid_token_returns_user_id(self) -> None:
        from unittest.mock import MagicMock

        from backend.api.middleware.rate_limit import _extract_user_id

        token = _make_token("u-42")
        req = MagicMock()
        req.headers = {"Authorization": f"Bearer {token}"}
        assert _extract_user_id(req) == "u-42"


class TestRateLimitMiddlewareIntegration:
    async def test_under_limit_passes(self, client) -> None:  # noqa: ANN001
        redis_mock = _make_redis_mock(current_count=0)
        with patch("backend.api.middleware.rate_limit.get_redis", return_value=redis_mock):
            resp = await client.get("/api/v1/trends")
        assert resp.status_code == 200

    async def test_anonymous_at_limit_returns_429(self, client) -> None:  # noqa: ANN001
        redis_mock = _make_redis_mock(current_count=60, ttl=45)
        with patch("backend.api.middleware.rate_limit.get_redis", return_value=redis_mock):
            resp = await client.get("/api/v1/trends")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert int(resp.headers["Retry-After"]) == 45

    async def test_authenticated_higher_limit(self, client) -> None:  # noqa: ANN001
        # 300 req/min for authenticated — count=299 should pass
        redis_mock = _make_redis_mock(current_count=299)
        token = _make_token("user-2", "pro")
        with patch("backend.api.middleware.rate_limit.get_redis", return_value=redis_mock):
            resp = await client.get("/api/v1/trends", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    async def test_authenticated_at_limit_returns_429(self, client) -> None:  # noqa: ANN001
        redis_mock = _make_redis_mock(current_count=300, ttl=10)
        token = _make_token("user-3", "pro")
        with patch("backend.api.middleware.rate_limit.get_redis", return_value=redis_mock):
            resp = await client.get("/api/v1/trends", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 429

    async def test_events_path_uses_events_key(self, client) -> None:  # noqa: ANN001
        redis_mock = _make_redis_mock(current_count=599)
        token = _make_token("user-4", "pro")
        with patch("backend.api.middleware.rate_limit.get_redis", return_value=redis_mock):
            resp = await client.get("/api/v1/events", headers={"Authorization": f"Bearer {token}"})
        # 599 < 600, should pass
        assert resp.status_code == 200

    async def test_events_at_limit_returns_429(self, client) -> None:  # noqa: ANN001
        redis_mock = _make_redis_mock(current_count=600, ttl=20)
        token = _make_token("user-5", "pro")
        with patch("backend.api.middleware.rate_limit.get_redis", return_value=redis_mock):
            resp = await client.get("/api/v1/events", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 429

    async def test_redis_error_fails_open(self, client) -> None:  # noqa: ANN001
        """On Redis failure, request should still pass through (fail-open)."""
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch("backend.api.middleware.rate_limit.get_redis", return_value=redis_mock):
            resp = await client.get("/api/v1/trends")
        assert resp.status_code == 200

    async def test_retry_after_minimum_one(self, client) -> None:  # noqa: ANN001
        redis_mock = _make_redis_mock(current_count=60, ttl=0)
        with patch("backend.api.middleware.rate_limit.get_redis", return_value=redis_mock):
            resp = await client.get("/api/v1/trends")
        assert resp.status_code == 429
        assert int(resp.headers["Retry-After"]) >= 1

    async def test_rate_limit_disabled_env_bypasses_in_non_production(
        self, client, monkeypatch
    ) -> None:  # noqa: ANN001
        monkeypatch.setenv("RATE_LIMIT_DISABLED", "true")
        monkeypatch.delenv("APP_ENV", raising=False)
        redis_mock = _make_redis_mock(current_count=9999, ttl=45)
        with patch("backend.api.middleware.rate_limit.get_redis", return_value=redis_mock):
            resp = await client.get("/api/v1/trends")
        assert resp.status_code == 200

    async def test_rate_limit_disabled_env_ignored_in_production(self, client, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.setenv("RATE_LIMIT_DISABLED", "true")
        monkeypatch.setenv("APP_ENV", "production")
        redis_mock = _make_redis_mock(current_count=60, ttl=45)
        with patch("backend.api.middleware.rate_limit.get_redis", return_value=redis_mock):
            resp = await client.get("/api/v1/trends")
        assert resp.status_code == 429
