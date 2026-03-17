"""Pytest fixtures for TrendScope tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_db_pool() -> MagicMock:
    """Mock asyncpg connection pool."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture
async def app(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> FastAPI:
    """FastAPI app with mocked DB and Redis (no real connections needed)."""
    from backend.api.main import create_app

    test_app = create_app()
    test_app.state.db_pool = mock_db_pool
    return test_app


@pytest.fixture
async def client(app: FastAPI, mock_redis: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client bound to the test app."""
    with patch(
        "backend.api.routers.health.get_redis",
        return_value=mock_redis,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
