"""Tests for backend/common/email.py — async email sending."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from backend.common.email import send_email, send_quota_alert_email


class TestSendEmail:
    @pytest.mark.asyncio
    async def test_not_configured_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("SMTP_USER", raising=False)

        result = await send_email("admin@example.com", "test", "body")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASS", "password")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

        with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await send_email("admin@example.com", "test subject", "test body")
            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_failure_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASS", "password")

        with patch(
            "aiosmtplib.send",
            new_callable=AsyncMock,
            side_effect=ConnectionError("SMTP down"),
        ):
            result = await send_email("admin@example.com", "test", "body")
            assert result is False


class TestSendQuotaAlertEmail:
    @pytest.mark.asyncio
    async def test_no_admin_email_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ADMIN_ALERT_EMAIL", raising=False)
        result = await send_quota_alert_email("youtube", "rate limited")
        assert result is False

    @pytest.mark.asyncio
    async def test_sends_with_admin_email(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "admin@example.com")

        with patch(
            "backend.common.email.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send:
            result = await send_quota_alert_email("youtube", "Too Many Requests")
            assert result is True
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert args[0] == "admin@example.com"
            assert "youtube" in args[1]
