"""Tests for admin panel API endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-admin")


def _auth_header(role: str = "admin", plan: str = "enterprise") -> dict:
    from backend.auth.jwt import create_access_token

    token = create_access_token("00000000-0000-0000-0000-000000000099", plan, role)
    return {"Authorization": f"Bearer {token}"}


def _general_user_header() -> dict:
    return _auth_header(role="general", plan="free")


def _operator_header() -> dict:
    return _auth_header(role="operator", plan="enterprise")


def _admin_header() -> dict:
    return _auth_header(role="admin", plan="enterprise")


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


def _make_user_row(
    user_id: str = "00000000-0000-0000-0000-000000000001",
    email: str = "test@example.com",
    display_name: str = "tester",
    role: str = "general",
    plan: str = "free",
    locale: str = "ko",
    is_active: bool = True,
) -> MagicMock:
    row = MagicMock()
    data = {
        "id": user_id,
        "email": email,
        "display_name": display_name,
        "role": role,
        "plan": plan,
        "locale": locale,
        "is_active": is_active,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    row.__getitem__ = lambda self, key: data[key]
    return row


def _make_subscription_row(
    sub_id: str = "00000000-0000-0000-0000-000000000010",
) -> MagicMock:
    row = MagicMock()
    data = {
        "id": sub_id,
        "user_id": "00000000-0000-0000-0000-000000000001",
        "plan": "pro",
        "status": "active",
        "provider": "toss",
        "provider_sub_id": "sub_123",
        "started_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "expires_at": datetime(2025, 12, 31, tzinfo=timezone.utc),
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    row.__getitem__ = lambda self, key: data[key]
    return row


def _make_source_row(
    source_id: str = "00000000-0000-0000-0000-000000000020",
) -> MagicMock:
    row = MagicMock()
    data = {
        "id": source_id,
        "source_name": "google_trends",
        "quota_limit": 1000,
        "quota_used": 250,
        "is_active": True,
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    row.__getitem__ = lambda self, key: data[key]
    return row


def _make_settings_row(key: str = "test_key", value: str = '"test_value"') -> MagicMock:
    row = MagicMock()
    data = {
        "key": key,
        "value": value,
        "default_value": '"default_value"',
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    row.__getitem__ = lambda self, key_name: data[key_name]
    return row


def _make_audit_row() -> MagicMock:
    row = MagicMock()
    data = {
        "id": "00000000-0000-0000-0000-000000000030",
        "user_id": "user1",
        "action": "login",
        "target_type": "session",
        "target_id": None,
        "ip_address": "127.0.0.1",
        "detail": None,
        "created_at": datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    }
    row.__getitem__ = lambda self, key: data[key]
    return row


# =============================================================================
# Access Control Tests — general user should get 403 on all admin endpoints
# =============================================================================
class TestAdminAccessControl:
    async def test_general_user_cannot_list_users(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.get("/admin/v1/users", headers=_general_user_header())
        assert resp.status_code == 403

    async def test_general_user_cannot_update_user(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.patch(
            "/admin/v1/users/some-id",
            json={"plan": "pro"},
            headers=_general_user_header(),
        )
        assert resp.status_code == 403

    async def test_general_user_cannot_delete_user(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.delete(
            "/admin/v1/users/some-id",
            headers=_general_user_header(),
        )
        assert resp.status_code == 403

    async def test_general_user_cannot_list_subscriptions(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.get("/admin/v1/subscriptions", headers=_general_user_header())
        assert resp.status_code == 403

    async def test_general_user_cannot_refund(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.post(
            "/admin/v1/subscriptions/some-id/refund",
            json={"reason": "test"},
            headers=_general_user_header(),
        )
        assert resp.status_code == 403

    async def test_general_user_cannot_list_sources(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.get("/admin/v1/sources", headers=_general_user_header())
        assert resp.status_code == 403

    async def test_general_user_cannot_get_ai_config(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.get("/admin/v1/ai-config", headers=_general_user_header())
        assert resp.status_code == 403

    async def test_general_user_cannot_get_settings(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.get("/admin/v1/settings", headers=_general_user_header())
        assert resp.status_code == 403

    async def test_general_user_cannot_list_audit_logs(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.get("/admin/v1/audit", headers=_general_user_header())
        assert resp.status_code == 403

    async def test_general_user_cannot_get_analytics(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.get("/admin/v1/analytics/users", headers=_general_user_header())
        assert resp.status_code == 403


# =============================================================================
# Operator access tests — operator can access most endpoints but not admin-only
# =============================================================================
class TestOperatorAccess:
    async def test_operator_can_list_users(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[_make_user_row()])

        resp = await admin_client.get("/admin/v1/users", headers=_operator_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    async def test_operator_can_list_subscriptions(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[_make_subscription_row()])

        resp = await admin_client.get("/admin/v1/subscriptions", headers=_operator_header())
        assert resp.status_code == 200

    async def test_operator_cannot_delete_user(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.delete("/admin/v1/users/some-id", headers=_operator_header())
        assert resp.status_code == 403

    async def test_operator_cannot_update_ai_config(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.patch(
            "/admin/v1/ai-config",
            json={"primary_model": "gpt-4"},
            headers=_operator_header(),
        )
        assert resp.status_code == 403

    async def test_operator_cannot_update_settings(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.patch(
            "/admin/v1/settings",
            json={"settings": {"key": "value"}},
            headers=_operator_header(),
        )
        assert resp.status_code == 403

    async def test_operator_cannot_reset_settings(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.post("/admin/v1/settings/reset", headers=_operator_header())
        assert resp.status_code == 403


# =============================================================================
# Admin full access tests
# =============================================================================
class TestAdminUsers:
    async def test_admin_list_users_success(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=2)
        conn.fetch = AsyncMock(return_value=[_make_user_row(), _make_user_row(user_id="u2")])

        resp = await admin_client.get("/admin/v1/users", headers=_admin_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["users"]) == 2

    async def test_admin_update_user_plan(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_user_row(plan="pro"))
        conn.execute = AsyncMock()

        resp = await admin_client.patch(
            "/admin/v1/users/00000000-0000-0000-0000-000000000001",
            json={"plan": "pro"},
            headers=_admin_header(),
        )
        assert resp.status_code == 200
        assert resp.json()["plan"] == "pro"

    async def test_admin_delete_user_success(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.execute = AsyncMock(return_value="DELETE 1")

        resp = await admin_client.delete(
            "/admin/v1/users/00000000-0000-0000-0000-000000000001",
            headers=_admin_header(),
        )
        assert resp.status_code == 204


class TestAdminSubscriptions:
    async def test_admin_list_subscriptions(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[_make_subscription_row()])

        resp = await admin_client.get("/admin/v1/subscriptions", headers=_admin_header())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["subscriptions"]) == 1

    async def test_admin_refund_subscription(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        refunded_row = _make_subscription_row()
        refunded_row.__getitem__ = lambda self, key: {
            **{
                "id": "00000000-0000-0000-0000-000000000010",
                "user_id": "00000000-0000-0000-0000-000000000001",
                "plan": "pro",
                "status": "refunded",
                "provider": "toss",
                "provider_sub_id": "sub_123",
                "started_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "expires_at": datetime(2025, 12, 31, tzinfo=timezone.utc),
                "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            },
        }[key]

        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=refunded_row)
        conn.execute = AsyncMock()

        resp = await admin_client.post(
            "/admin/v1/subscriptions/00000000-0000-0000-0000-000000000010/refund",
            json={"reason": "Customer request"},
            headers=_admin_header(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "refunded"


class TestAdminSources:
    async def test_admin_list_sources(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(return_value=[_make_source_row()])

        resp = await admin_client.get("/admin/v1/sources", headers=_admin_header())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sources"]) == 1
        assert data["sources"][0]["quota_limit"] == 1000

    async def test_admin_update_source_quota(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        updated = _make_source_row()
        conn.fetchrow = AsyncMock(return_value=updated)
        conn.execute = AsyncMock()

        resp = await admin_client.patch(
            "/admin/v1/sources/00000000-0000-0000-0000-000000000020",
            json={"quota_limit": 2000},
            headers=_admin_header(),
        )
        assert resp.status_code == 200

    async def test_admin_reset_source_quota(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        reset_row = _make_source_row()
        conn.fetchrow = AsyncMock(return_value=reset_row)
        conn.execute = AsyncMock()

        resp = await admin_client.post(
            "/admin/v1/sources/00000000-0000-0000-0000-000000000020/reset",
            headers=_admin_header(),
        )
        assert resp.status_code == 200


class TestAdminSettings:
    async def test_admin_get_settings(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(return_value=[_make_settings_row()])

        resp = await admin_client.get("/admin/v1/settings", headers=_admin_header())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["settings"]) == 1
        assert data["settings"][0]["key"] == "test_key"

    async def test_admin_update_settings(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(return_value=[_make_settings_row()])
        conn.execute = AsyncMock()
        conn.transaction = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        resp = await admin_client.patch(
            "/admin/v1/settings",
            json={"settings": {"test_key": "new_value"}},
            headers=_admin_header(),
        )
        assert resp.status_code == 200

    async def test_admin_reset_settings_to_defaults(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        default_row = _make_settings_row(value='"default_value"')
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.execute = AsyncMock()
        conn.fetch = AsyncMock(return_value=[default_row])

        resp = await admin_client.post("/admin/v1/settings/reset", headers=_admin_header())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["settings"]) == 1
        # After reset, value should equal default_value
        setting = data["settings"][0]
        assert setting["value"] == setting["default_value"]


class TestAdminAudit:
    async def test_admin_list_audit_logs(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[_make_audit_row()])

        resp = await admin_client.get("/admin/v1/audit", headers=_admin_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["logs"]) == 1

    async def test_admin_export_audit_csv(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[_make_audit_row()])

        resp = await admin_client.get("/admin/v1/audit/export?format=csv", headers=_admin_header())
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        content = resp.text
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        # First line should be CSV header
        assert lines[0] == "id,user_id,action,target_type,target_id,ip_address,detail,created_at"
        # Should have header + 1 data row
        assert len(lines) == 2

    async def test_admin_export_audit_json(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[_make_audit_row()])

        resp = await admin_client.get("/admin/v1/audit/export?format=json", headers=_admin_header())
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        data = json.loads(resp.text)
        assert len(data) == 1


class TestAdminAnalytics:
    async def test_admin_get_analytics_users(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=10)
        conn.fetch = AsyncMock(return_value=[])

        resp = await admin_client.get("/admin/v1/analytics/users", headers=_admin_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "users"

    async def test_admin_invalid_metric(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.get("/admin/v1/analytics/invalid", headers=_admin_header())
        assert resp.status_code == 400


class TestAdminAIConfig:
    async def test_admin_get_ai_config(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(
            return_value=[
                _make_settings_row(key="ai_primary_model", value='"gemini-flash"'),
            ]
        )

        resp = await admin_client.get("/admin/v1/ai-config", headers=_admin_header())
        assert resp.status_code == 200

    async def test_admin_test_ai_config(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(
            return_value=[
                _make_settings_row(key="ai_primary_model", value='"gemini-flash"'),
            ]
        )

        resp = await admin_client.post("/admin/v1/ai-config/test", headers=_admin_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["response_time_ms"] is not None


# ---------------------------------------------------------------------------
# Quota Alerts
# ---------------------------------------------------------------------------


class TestQuotaAlerts:
    @pytest.mark.asyncio
    async def test_list_quota_alerts_requires_admin(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.get("/admin/v1/quota-alerts", headers=_general_user_header())
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_quota_alerts_success(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        import uuid
        from datetime import datetime, timezone

        alert_id = uuid.uuid4()
        alert_row = MagicMock()
        alert_row.__getitem__ = lambda self, key: {
            "id": alert_id,
            "service_name": "youtube",
            "error_type": "rate_limit_429",
            "status_code": 429,
            "detail": "Too Many Requests",
            "endpoint_url": "https://api.example.com",
            "is_dismissed": False,
            "dismissed_by": None,
            "dismissed_at": None,
            "email_sent": False,
            "created_at": datetime.now(tz=timezone.utc),
        }[key]

        with patch(
            "backend.api.routers.admin.quota_alerts.admin_list_quota_alerts",
            new_callable=AsyncMock,
            return_value=([alert_row], 1),
        ):
            resp = await admin_client.get("/admin/v1/quota-alerts", headers=_admin_header())
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert len(data["alerts"]) == 1
            assert data["alerts"][0]["service_name"] == "youtube"

    @pytest.mark.asyncio
    async def test_get_active_alert_count(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        with patch(
            "backend.api.routers.admin.quota_alerts.admin_get_active_alert_count",
            new_callable=AsyncMock,
            return_value=3,
        ):
            resp = await admin_client.get("/admin/v1/quota-alerts/count", headers=_admin_header())
            assert resp.status_code == 200
            assert resp.json()["active_count"] == 3

    @pytest.mark.asyncio
    async def test_dismiss_quota_alert(
        self, admin_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        import uuid
        from datetime import datetime, timezone

        alert_id = uuid.uuid4()
        dismissed_row = MagicMock()
        dismissed_row.__getitem__ = lambda self, key: {
            "id": alert_id,
            "service_name": "youtube",
            "error_type": "rate_limit_429",
            "status_code": 429,
            "detail": "Too Many Requests",
            "endpoint_url": None,
            "is_dismissed": True,
            "dismissed_by": uuid.uuid4(),
            "dismissed_at": datetime.now(tz=timezone.utc),
            "email_sent": False,
            "created_at": datetime.now(tz=timezone.utc),
        }[key]

        with (
            patch(
                "backend.api.routers.admin.quota_alerts.admin_dismiss_quota_alert",
                new_callable=AsyncMock,
                return_value=dismissed_row,
            ),
            patch(
                "backend.api.routers.admin.quota_alerts.write_audit_log",
                new_callable=AsyncMock,
            ),
        ):
            resp = await admin_client.post(
                f"/admin/v1/quota-alerts/{alert_id}/dismiss",
                headers=_admin_header(),
            )
            assert resp.status_code == 200
            assert resp.json()["is_dismissed"] is True
