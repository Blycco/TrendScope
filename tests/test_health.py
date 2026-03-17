"""Integration tests for GET /health endpoint. (RULE 04: coverage ≥ 70%)"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient) -> None:
    """GET /health returns 200 when DB and Redis are reachable."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_db_error(app: MagicMock, mock_redis: AsyncMock) -> None:
    """GET /health returns 200 with status=degraded when DB fails."""
    broken_pool = MagicMock()
    broken_conn = AsyncMock()
    broken_conn.fetchval = AsyncMock(side_effect=Exception("DB connection refused"))
    broken_pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=broken_conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    app.state.db_pool = broken_pool

    with patch(
        "backend.api.routers.health.get_redis",
        return_value=mock_redis,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "error"
    assert body["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_redis_error(app: MagicMock, mock_db_pool: MagicMock) -> None:
    """GET /health returns 200 with status=degraded when Redis fails."""
    app.state.db_pool = mock_db_pool

    broken_redis = AsyncMock()
    broken_redis.ping = AsyncMock(side_effect=Exception("Redis connection refused"))

    with patch(
        "backend.api.routers.health.get_redis",
        return_value=broken_redis,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "ok"
    assert body["redis"] == "error"


@pytest.mark.asyncio
async def test_health_response_schema(client: AsyncClient) -> None:
    """GET /health response contains required fields."""
    response = await client.get("/health")
    body = response.json()
    assert "status" in body
    assert "db" in body
    assert "redis" in body


@pytest.mark.asyncio
async def test_health_both_error(app: MagicMock) -> None:
    """GET /health returns degraded when both DB and Redis fail."""
    broken_pool = MagicMock()
    broken_conn = AsyncMock()
    broken_conn.fetchval = AsyncMock(side_effect=Exception("DB down"))
    broken_pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=broken_conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    app.state.db_pool = broken_pool

    broken_redis = AsyncMock()
    broken_redis.ping = AsyncMock(side_effect=Exception("Redis down"))

    with patch(
        "backend.api.routers.health.get_redis",
        return_value=broken_redis,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "error"
    assert body["redis"] == "error"
