"""Tests for payment webhook endpoint with HMAC-SHA256 signature verification."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

_WEBHOOK_SECRET = "test-webhook-secret-12345"  # noqa: S105


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-webhooks")
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", _WEBHOOK_SECRET)


def _make_sub_row(
    *,
    sub_id: str = "00000000-0000-0000-0000-000000000020",
    user_id: str = "00000000-0000-0000-0000-000000000001",
    plan: str = "pro",
    status: str = "active",
) -> MagicMock:
    now = datetime.now(tz=timezone.utc)
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": sub_id,
        "user_id": user_id,
        "plan": plan,
        "status": status,
        "provider": "stripe",
        "provider_sub_id": "sub_123",
        "started_at": now,
        "expires_at": None,
        "created_at": now,
    }[key]
    return row


def _sign(payload_bytes: bytes) -> str:
    return hmac.new(_WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()


@pytest.fixture
async def webhook_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    with patch("backend.api.routers.health.get_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


class TestPaymentWebhook:
    async def test_valid_webhook(
        self, webhook_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_sub_row())
        conn.execute = AsyncMock()

        payload = {
            "type": "subscription.updated",
            "data": {
                "provider_sub_id": "sub_123",
                "status": "active",
                "plan": "pro",
            },
        }
        body = json.dumps(payload).encode()

        resp = await webhook_client.post(
            "/api/v1/webhooks/payment",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": _sign(body),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_invalid_signature(self, webhook_client: AsyncClient) -> None:
        payload = {
            "type": "subscription.updated",
            "data": {"provider_sub_id": "sub_123", "status": "active"},
        }
        body = json.dumps(payload).encode()

        resp = await webhook_client.post(
            "/api/v1/webhooks/payment",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": "invalid-signature",
            },
        )
        assert resp.status_code == 401

    async def test_missing_signature(self, webhook_client: AsyncClient) -> None:
        payload = {"type": "test", "data": {"provider_sub_id": "sub_123", "status": "active"}}
        body = json.dumps(payload).encode()

        resp = await webhook_client.post(
            "/api/v1/webhooks/payment",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    async def test_missing_data_fields(self, webhook_client: AsyncClient) -> None:
        payload = {"type": "subscription.updated", "data": {}}
        body = json.dumps(payload).encode()

        resp = await webhook_client.post(
            "/api/v1/webhooks/payment",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": _sign(body),
            },
        )
        assert resp.status_code == 400

    async def test_subscription_cancelled_webhook(
        self, webhook_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_sub_row(status="cancelled"))
        conn.execute = AsyncMock()

        payload = {
            "type": "subscription.cancelled",
            "data": {
                "provider_sub_id": "sub_123",
                "status": "cancelled",
            },
        }
        body = json.dumps(payload).encode()

        resp = await webhook_client.post(
            "/api/v1/webhooks/payment",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": _sign(body),
            },
        )
        assert resp.status_code == 200
