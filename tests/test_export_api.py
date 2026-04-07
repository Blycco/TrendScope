"""Tests for GET /api/v1/trends/export endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trend_row(
    *,
    row_id: str = "00000000-0000-0000-0000-000000000001",
    title: str = "테스트 트렌드",
    category: str = "tech",
    score: float = 0.9,
    early_trend_score: float = 0.5,
    keywords: list[str] | None = None,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": row_id,
        "title": title,
        "category": category,
        "locale": "ko",
        "score": score,
        "early_trend_score": early_trend_score,
        "keywords": keywords or ["AI", "트렌드"],
        "created_at": datetime(2026, 3, 19, 0, 0, 0, tzinfo=timezone.utc),
        "summary": "요약",
        "article_count": 3,
        "direction": "steady",
    }[key]
    return row


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-export")


def _make_token(plan: str) -> str:
    from backend.auth.jwt import create_access_token

    return create_access_token(f"user-{plan}", plan, "general")


@pytest.fixture
async def export_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    with (
        patch("backend.api.routers.health.get_redis", return_value=mock_redis),
        patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        patch("backend.api.routers.trends.get_cached", return_value=None),
        patch("backend.api.routers.trends.set_cached", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Plan gate tests
# ---------------------------------------------------------------------------


class TestExportPlanGate:
    async def test_free_user_gets_403(self, export_client: AsyncClient) -> None:
        token = _make_token("free")
        resp = await export_client.get(
            "/api/v1/trends/export?format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_gets_401(self, export_client: AsyncClient) -> None:
        resp = await export_client.get("/api/v1/trends/export?format=csv")
        assert resp.status_code == 401

    async def test_pro_user_can_export_csv(
        self, export_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[_make_trend_row()]
        )
        resp = await export_client.get(
            "/api/v1/trends/export?format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")

    async def test_pro_user_cannot_export_pdf(self, export_client: AsyncClient) -> None:
        token = _make_token("pro")
        resp = await export_client.get(
            "/api/v1/trends/export?format=pdf",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data["code"] == "E0031"

    async def test_business_user_can_export_pdf(
        self, export_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """Business user can export PDF."""
        token = _make_token("business")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[_make_trend_row()]
        )
        resp = await export_client.get(
            "/api/v1/trends/export?format=pdf",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"

    async def test_enterprise_user_can_export_csv(
        self, export_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("enterprise")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[_make_trend_row()]
        )
        resp = await export_client.get(
            "/api/v1/trends/export?format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestExportCsvContent:
    async def test_csv_has_header_and_rows(
        self, export_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[_make_trend_row(title="AI 트렌드")]
        )
        resp = await export_client.get(
            "/api/v1/trends/export?format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        lines = resp.text.strip().splitlines()
        assert lines[0].startswith("id,title,category")
        assert "AI 트렌드" in lines[1]

    async def test_csv_keywords_pipe_separated(
        self, export_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("pro")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[_make_trend_row(keywords=["키워드1", "키워드2"])]
        )
        resp = await export_client.get(
            "/api/v1/trends/export?format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert "키워드1|키워드2" in resp.text

    async def test_db_error_returns_500(
        self, export_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        token = _make_token("business")
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            side_effect=RuntimeError("DB 오류")
        )
        resp = await export_client.get(
            "/api/v1/trends/export?format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 500
        assert resp.json()["code"] == "E0040"

    async def test_invalid_format_returns_422(self, export_client: AsyncClient) -> None:
        token = _make_token("business")
        resp = await export_client.get(
            "/api/v1/trends/export?format=xlsx",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
