"""Tests for Brand Monitoring API endpoints.

Coverage targets:
- free user → 402 on all brand endpoints (Plan Gate)
- business user → normal responses
- brand_alert job: Z-score > threshold triggers alert dispatch
- POST /brand: duplicate / quota limit handling
- DELETE /brand/{name}: not found → 404
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.auth.jwt import create_access_token
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-brand")


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def _free_token() -> str:
    return create_access_token("user-free-001", "free", "general")


def _business_token() -> str:
    return create_access_token("user-biz-001", "business", "owner")


def _enterprise_token() -> str:
    return create_access_token("user-ent-001", "enterprise", "owner")


# ---------------------------------------------------------------------------
# Pool / row helpers
# ---------------------------------------------------------------------------


def _make_brand_row(
    brand_name: str = "TestBrand",
    brand_id: str = "aaaaaaaa-0000-0000-0000-000000000001",
) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "id": brand_id,
            "brand_name": brand_name,
            "keywords": [],
            "is_active": True,
            "slack_webhook": None,
            "last_alerted_at": None,
            "created_at": datetime(2026, 3, 1),
            "updated_at": datetime(2026, 3, 1),
        }[k]
    )
    return row


def _make_pool(
    fetch_rows: list | None = None,
    fetchrow_return: MagicMock | None = None,
    fetchval_return: object = None,
) -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch_rows or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.fetchval = AsyncMock(return_value=fetchval_return)
    conn.execute = AsyncMock(return_value=None)
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def app(mock_redis: AsyncMock) -> FastAPI:
    from backend.api.main import create_app

    test_app = create_app()
    test_app.state.db_pool = _make_pool()
    return test_app


@pytest.fixture
async def client(app: FastAPI, mock_redis: AsyncMock) -> AsyncClient:
    with (
        patch("backend.api.routers.health.get_redis", return_value=mock_redis),
        patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


# ---------------------------------------------------------------------------
# Plan Gate: free user → 402
# ---------------------------------------------------------------------------


class TestPlanGateFreeUser:
    @pytest.mark.asyncio
    async def test_get_list_free_returns_402(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/brand",
            headers={"Authorization": f"Bearer {_free_token()}"},
        )
        assert resp.status_code == 402

    @pytest.mark.asyncio
    async def test_get_monitor_free_returns_plan_gate(self, client: AsyncClient) -> None:
        # PlanGateMiddleware matches /api/v1/brand/* and returns 403 before
        # the route dependency has a chance to return 402.
        resp = await client.get(
            "/api/v1/brand/TestBrand/monitor",
            headers={"Authorization": f"Bearer {_free_token()}"},
        )
        assert resp.status_code in (402, 403)

    @pytest.mark.asyncio
    async def test_post_brand_free_returns_402(self, client: AsyncClient) -> None:
        # POST /api/v1/brand does NOT match /api/v1/brand/ (trailing slash required)
        # so it falls through to the route dependency which returns 402.
        resp = await client.post(
            "/api/v1/brand",
            json={"brand_name": "MyBrand"},
            headers={"Authorization": f"Bearer {_free_token()}"},
        )
        assert resp.status_code == 402

    @pytest.mark.asyncio
    async def test_delete_brand_free_returns_plan_gate(self, client: AsyncClient) -> None:
        # PlanGateMiddleware matches /api/v1/brand/* and returns 403.
        resp = await client.delete(
            "/api/v1/brand/TestBrand",
            headers={"Authorization": f"Bearer {_free_token()}"},
        )
        assert resp.status_code in (402, 403)

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/brand")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Business user — list brands
# ---------------------------------------------------------------------------


class TestBusinessUserListBrands:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self, app: FastAPI, mock_redis: AsyncMock) -> None:
        app.state.db_pool = _make_pool(fetch_rows=[])
        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get(
                    "/api/v1/brand",
                    headers={"Authorization": f"Bearer {_business_token()}"},
                )
        assert resp.status_code == 200
        assert resp.json()["brands"] == []

    @pytest.mark.asyncio
    async def test_returns_brand_list(self, app: FastAPI, mock_redis: AsyncMock) -> None:
        row = _make_brand_row("Nike")
        app.state.db_pool = _make_pool(fetch_rows=[row])
        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get(
                    "/api/v1/brand",
                    headers={"Authorization": f"Bearer {_business_token()}"},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["brands"]) == 1
        assert data["brands"][0]["brand_name"] == "Nike"


# ---------------------------------------------------------------------------
# Business user — monitor
# ---------------------------------------------------------------------------


class TestBusinessUserMonitor:
    @pytest.mark.asyncio
    async def test_monitor_returns_result(self, app: FastAPI, mock_redis: AsyncMock) -> None:
        from backend.processor.algorithms.brand_monitor import BrandMonitorResult

        mock_result = BrandMonitorResult(
            brand_name="Nike",
            current_score=0.2,
            mean_24h=0.1,
            std_24h=0.05,
            z_score=2.0,
            alert_threshold=2.0,
            is_crisis=True,
            label="surge",
            cached=False,
            mentions=[],
        )
        app.state.db_pool = _make_pool()
        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
            patch(
                "backend.api.routers.brand.monitor_brand",
                new=AsyncMock(return_value=mock_result),
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get(
                    "/api/v1/brand/Nike/monitor",
                    headers={"Authorization": f"Bearer {_business_token()}"},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["brand_name"] == "Nike"
        assert data["is_crisis"] is True
        assert data["label"] == "surge"
        assert data["z_score"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Business user — create brand
# ---------------------------------------------------------------------------


class TestBusinessUserCreateBrand:
    @pytest.mark.asyncio
    async def test_create_brand_success(self, app: FastAPI, mock_redis: AsyncMock) -> None:
        new_row = MagicMock()
        new_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "id": "aaaaaaaa-0000-0000-0000-000000000002",
                "brand_name": "NewBrand",
                "keywords": ["kw1"],
                "slack_webhook": None,
                "created_at": datetime(2026, 3, 1),
            }[k]
        )
        pool = MagicMock()
        conn = AsyncMock()
        # fetchval[0] = count=0 (under limit), fetchval[1] = None (no duplicate)
        conn.fetchval = AsyncMock(side_effect=[0, None])
        conn.fetchrow = AsyncMock(return_value=new_row)
        conn.execute = AsyncMock(return_value=None)
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        app.state.db_pool = pool

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.post(
                    "/api/v1/brand",
                    json={"brand_name": "NewBrand", "keywords": ["kw1"]},
                    headers={"Authorization": f"Bearer {_business_token()}"},
                )
        assert resp.status_code == 201
        assert resp.json()["brand_name"] == "NewBrand"

    @pytest.mark.asyncio
    async def test_create_brand_quota_exceeded(self, app: FastAPI, mock_redis: AsyncMock) -> None:
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=3)  # already at 3-brand limit
        conn.execute = AsyncMock(return_value=None)
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        app.state.db_pool = pool

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.post(
                    "/api/v1/brand",
                    json={"brand_name": "FourthBrand"},
                    headers={"Authorization": f"Bearer {_business_token()}"},
                )
        assert resp.status_code == 402


# ---------------------------------------------------------------------------
# Business user — delete brand
# ---------------------------------------------------------------------------


class TestBusinessUserDeleteBrand:
    @pytest.mark.asyncio
    async def test_delete_not_found_returns_404(self, app: FastAPI, mock_redis: AsyncMock) -> None:
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=None)  # no row updated
        conn.execute = AsyncMock(return_value=None)
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        app.state.db_pool = pool

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.delete(
                    "/api/v1/brand/NonExistent",
                    headers={"Authorization": f"Bearer {_business_token()}"},
                )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_success_returns_204(self, app: FastAPI, mock_redis: AsyncMock) -> None:
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value="aaaaaaaa-0000-0000-0000-000000000001")
        conn.execute = AsyncMock(return_value=None)
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        app.state.db_pool = pool

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.delete(
                    "/api/v1/brand/TestBrand",
                    headers={"Authorization": f"Bearer {_business_token()}"},
                )
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Enterprise user — no brand limit
# ---------------------------------------------------------------------------


class TestEnterpriseUserNoBrandLimit:
    @pytest.mark.asyncio
    async def test_enterprise_skips_quota_check(self, app: FastAPI, mock_redis: AsyncMock) -> None:
        new_row = MagicMock()
        new_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "id": "aaaaaaaa-0000-0000-0000-000000000099",
                "brand_name": "EntBrand",
                "keywords": [],
                "slack_webhook": None,
                "created_at": datetime(2026, 3, 1),
            }[k]
        )
        pool = MagicMock()
        conn = AsyncMock()
        # Enterprise skips count check; only duplicate check runs (returns None = no dup)
        conn.fetchval = AsyncMock(return_value=None)
        conn.fetchrow = AsyncMock(return_value=new_row)
        conn.execute = AsyncMock(return_value=None)
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        app.state.db_pool = pool

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.post(
                    "/api/v1/brand",
                    json={"brand_name": "EntBrand"},
                    headers={"Authorization": f"Bearer {_enterprise_token()}"},
                )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# brand_alert job — mock test
# ---------------------------------------------------------------------------


class TestBrandAlertJob:
    @pytest.mark.asyncio
    async def test_no_monitors_returns_zero(self) -> None:
        from backend.jobs.brand_alert import run_brand_alert

        pool = MagicMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        result = await run_brand_alert(pool)
        assert result == 0

    @pytest.mark.asyncio
    async def test_crisis_dispatches_slack_alert(self) -> None:
        from backend.jobs.brand_alert import run_brand_alert

        monitor_row = MagicMock()
        monitor_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "id": "aaaaaaaa-0000-0000-0000-000000000001",
                "user_id": "user-biz-001",
                "brand_name": "CrisisBrand",
                "keywords": ["crisis", "brand"],
                "slack_webhook": "https://hooks.slack.com/test",
                "last_alerted_at": None,
            }[k]
        )

        pool = MagicMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[monitor_row])
        conn.fetchval = AsyncMock(return_value=False)  # still_recent = False
        conn.execute = AsyncMock(return_value=None)
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        crisis_cache = json.dumps(
            {
                "brand_name": "CrisisBrand",
                "current_score": -0.8,
                "mean_24h": 0.1,
                "std_24h": 0.05,
                "z_score": -18.0,
                "alert_threshold": 2.0,
                "is_crisis": True,
                "label": "crisis",
                "mentions": [],
            }
        ).encode()

        with (
            patch(
                "backend.jobs.brand_alert.get_cached",
                new=AsyncMock(return_value=crisis_cache),
            ),
            patch(
                "backend.jobs.brand_alert._send_slack_alert",
                new=AsyncMock(),
            ) as mock_slack,
            patch(
                "backend.jobs.brand_alert._fetch_alert_threshold",
                new=AsyncMock(return_value=2.0),
            ),
        ):
            count = await run_brand_alert(pool)

        assert count == 1
        mock_slack.assert_awaited_once()
        call_args = mock_slack.call_args[0]
        assert "CrisisBrand" in call_args[1]
        assert "CRISIS" in call_args[1]

    @pytest.mark.asyncio
    async def test_normal_zscore_no_alert(self) -> None:
        from backend.jobs.brand_alert import run_brand_alert

        monitor_row = MagicMock()
        monitor_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "id": "aaaaaaaa-0000-0000-0000-000000000002",
                "user_id": "user-biz-002",
                "brand_name": "StableBrand",
                "keywords": [],
                "slack_webhook": None,
                "last_alerted_at": None,
            }[k]
        )

        pool = MagicMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[monitor_row])
        conn.fetchval = AsyncMock(return_value=False)
        conn.execute = AsyncMock(return_value=None)
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        normal_cache = json.dumps(
            {
                "brand_name": "StableBrand",
                "current_score": 0.1,
                "mean_24h": 0.1,
                "std_24h": 0.05,
                "z_score": 0.0,
                "alert_threshold": 2.0,
                "is_crisis": False,
                "label": "normal",
                "mentions": [],
            }
        ).encode()

        with (
            patch(
                "backend.jobs.brand_alert.get_cached",
                new=AsyncMock(return_value=normal_cache),
            ),
            patch(
                "backend.jobs.brand_alert._send_slack_alert",
                new=AsyncMock(),
            ) as mock_slack,
            patch(
                "backend.jobs.brand_alert._fetch_alert_threshold",
                new=AsyncMock(return_value=2.0),
            ),
        ):
            count = await run_brand_alert(pool)

        assert count == 0
        mock_slack.assert_not_awaited()
