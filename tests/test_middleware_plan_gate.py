"""Tests for PlanGateMiddleware."""

from __future__ import annotations

import pytest
from backend.auth.jwt import create_access_token


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-plangate")


def _make_token(plan: str) -> str:
    return create_access_token("user-test", plan, "general")


def _auth_header(plan: str) -> dict:
    return {"Authorization": f"Bearer {_make_token(plan)}"}


class TestRequiredPlan:
    def test_ungated_path_returns_none(self) -> None:
        from backend.api.middleware.plan_gate import _required_plan

        assert _required_plan("/api/v1/trends") is None
        assert _required_plan("/api/v1/health") is None
        assert _required_plan("/api/v1/auth/login") is None

    def test_gated_trends_early_requires_pro(self) -> None:
        from backend.api.middleware.plan_gate import _required_plan

        assert _required_plan("/api/v1/trends/early") == "pro"

    def test_gated_content_ideas_requires_pro(self) -> None:
        from backend.api.middleware.plan_gate import _required_plan

        assert _required_plan("/api/v1/content/ideas") == "pro"

    def test_gated_brand_monitor_requires_business(self) -> None:
        from backend.api.middleware.plan_gate import _required_plan

        assert _required_plan("/api/v1/brand/acme/monitor") == "business"

    def test_gated_insights_suffix_requires_pro(self) -> None:
        from backend.api.middleware.plan_gate import _required_plan

        assert _required_plan("/api/v1/trends/python/insights") == "pro"

    def test_non_insights_suffix_ungated(self) -> None:
        from backend.api.middleware.plan_gate import _required_plan

        # /api/v1/trends/python is not an early or insights path
        assert _required_plan("/api/v1/trends/python") is None


class TestExtractUserPlan:
    def test_no_auth_header_returns_none(self) -> None:
        from unittest.mock import MagicMock

        from backend.api.middleware.plan_gate import _extract_user_plan

        request = MagicMock()
        request.headers = {}
        assert _extract_user_plan(request) is None

    def test_valid_bearer_returns_plan(self) -> None:
        from unittest.mock import MagicMock

        from backend.api.middleware.plan_gate import _extract_user_plan

        token = _make_token("pro")
        request = MagicMock()
        request.headers = {"Authorization": f"Bearer {token}"}
        assert _extract_user_plan(request) == "pro"

    def test_invalid_token_returns_none(self) -> None:
        from unittest.mock import MagicMock

        from backend.api.middleware.plan_gate import _extract_user_plan

        request = MagicMock()
        request.headers = {"Authorization": "Bearer invalid.token"}
        assert _extract_user_plan(request) is None


class TestPlanGateMiddlewareIntegration:
    """Integration tests using a minimal ASGI app."""

    @pytest.fixture
    def mini_app(self):  # noqa: ANN201
        from backend.api.middleware.plan_gate import PlanGateMiddleware
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse

        app = FastAPI()
        app.add_middleware(PlanGateMiddleware)

        @app.get("/api/v1/trends/early")
        async def early():  # noqa: ANN201
            return JSONResponse({"ok": True})

        @app.get("/api/v1/trends")
        async def trends():  # noqa: ANN201
            return JSONResponse({"ok": True})

        @app.get("/api/v1/content/ideas")
        async def ideas():  # noqa: ANN201
            return JSONResponse({"ok": True})

        @app.get("/api/v1/brand/{name}/monitor")
        async def brand_monitor(name: str):  # noqa: ANN201
            return JSONResponse({"ok": True})

        return app

    @pytest.fixture
    async def client(self, mini_app):  # noqa: ANN201
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=mini_app), base_url="http://test") as ac:
            yield ac

    async def test_ungated_path_allowed_without_token(self, client) -> None:  # noqa: ANN001
        resp = await client.get("/api/v1/trends")
        assert resp.status_code == 200

    async def test_pro_path_blocked_without_token(self, client) -> None:  # noqa: ANN001
        resp = await client.get("/api/v1/trends/early")
        assert resp.status_code == 401

    async def test_pro_path_blocked_for_free_user(self, client) -> None:  # noqa: ANN001
        resp = await client.get("/api/v1/trends/early", headers=_auth_header("free"))
        assert resp.status_code == 403
        body = resp.json()
        assert body["code"] == "E0031"
        assert body["upgrade_url"] == "/pricing"
        assert body["required_plan"] == "pro"

    async def test_pro_path_allowed_for_pro_user(self, client) -> None:  # noqa: ANN001
        resp = await client.get("/api/v1/trends/early", headers=_auth_header("pro"))
        assert resp.status_code == 200

    async def test_pro_path_allowed_for_business_user(self, client) -> None:  # noqa: ANN001
        resp = await client.get("/api/v1/trends/early", headers=_auth_header("business"))
        assert resp.status_code == 200

    async def test_business_path_blocked_for_pro_user(self, client) -> None:  # noqa: ANN001
        resp = await client.get("/api/v1/brand/acme/monitor", headers=_auth_header("pro"))
        assert resp.status_code == 403
        assert resp.json()["required_plan"] == "business"

    async def test_business_path_allowed_for_enterprise(self, client) -> None:  # noqa: ANN001
        resp = await client.get("/api/v1/brand/acme/monitor", headers=_auth_header("enterprise"))
        assert resp.status_code == 200

    async def test_content_ideas_blocked_for_free(self, client) -> None:  # noqa: ANN001
        resp = await client.get("/api/v1/content/ideas", headers=_auth_header("free"))
        assert resp.status_code == 403
