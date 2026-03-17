"""Tests for backend.common.audit."""

from __future__ import annotations

from unittest.mock import AsyncMock

from backend.common.audit import write_audit_log


class TestWriteAuditLog:
    async def test_calls_execute_with_correct_args(self) -> None:
        conn = AsyncMock()
        conn.execute = AsyncMock()
        await write_audit_log(
            conn=conn,
            user_id="user-123",
            action="login",
            target_type="user",
            target_id="user-123",
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0",
            detail={"method": "email"},
        )
        conn.execute.assert_awaited_once()
        args = conn.execute.call_args[0]
        assert "user-123" in args
        assert "login" in args

    async def test_no_exception_on_db_error(self) -> None:
        conn = AsyncMock()
        conn.execute = AsyncMock(side_effect=RuntimeError("DB error"))
        await write_audit_log(conn=conn, user_id=None, action="test")

    async def test_minimal_call_with_nulls(self) -> None:
        conn = AsyncMock()
        conn.execute = AsyncMock()
        await write_audit_log(conn=conn, user_id=None, action="logout")
        conn.execute.assert_awaited_once()
