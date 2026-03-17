"""Tests for GET /api/v1/news endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_news_row(
    *,
    row_id: str = "00000000-0000-0000-0000-000000000001",
    title: str = "테스트 뉴스",
    url: str = "https://example.com/news/1",
    source: str | None = "TechCrunch",
    publish_time: datetime | None = None,
    summary: str | None = "요약",
) -> MagicMock:
    if publish_time is None:
        publish_time = datetime(2026, 3, 17, 12, 0, 0, tzinfo=timezone.utc)
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": row_id,
        "title": title,
        "url": url,
        "source": source,
        "publish_time": publish_time,
        "summary": summary,
    }[key]
    return row


@pytest.fixture
async def news_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    with patch("backend.api.routers.health.get_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# GET /api/v1/news
# ---------------------------------------------------------------------------


class TestListNews:
    async def test_returns_200_with_items(
        self, news_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        row = _make_news_row()
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[row]
        )

        resp = await news_client.get("/api/v1/news")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "테스트 뉴스"
        assert data["items"][0]["url"] == "https://example.com/news/1"

    async def test_empty_result(self, news_client: AsyncClient, mock_db_pool: MagicMock) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[])

        resp = await news_client.get("/api/v1/news")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["next_cursor"] is None

    async def test_category_and_locale_filters(
        self, news_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        fetch_mock = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = fetch_mock

        resp = await news_client.get("/api/v1/news?category=tech&locale=ko")
        assert resp.status_code == 200
        assert fetch_mock.called

    async def test_db_error_returns_500(
        self, news_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            side_effect=Exception("DB 오류")
        )

        resp = await news_client.get("/api/v1/news")
        assert resp.status_code == 500
        assert resp.json()["code"] == "E0040"

    async def test_next_cursor_set_on_full_page(
        self, news_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        rows = [
            _make_news_row(row_id=f"00000000-0000-0000-0000-00000000000{i}") for i in range(1, 3)
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=rows
        )

        resp = await news_client.get("/api/v1/news?limit=2")
        assert resp.status_code == 200
        assert resp.json()["next_cursor"] is not None

    async def test_source_can_be_none(
        self, news_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        row = _make_news_row(source=None)
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[row]
        )

        resp = await news_client.get("/api/v1/news")
        assert resp.status_code == 200
        assert resp.json()["items"][0]["source"] is None

    async def test_with_cursor_param(
        self, news_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[])
        from backend.db.queries.trends import encode_cursor

        cur = encode_cursor(1742212800.0, "00000000-0000-0000-0000-000000000001")
        resp = await news_client.get(f"/api/v1/news?cursor={cur}")
        assert resp.status_code == 200

    async def test_limit_boundary(self, news_client: AsyncClient, mock_db_pool: MagicMock) -> None:
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[])
        resp = await news_client.get("/api/v1/news?limit=100")
        assert resp.status_code == 200

    async def test_limit_too_large_rejected(self, news_client: AsyncClient) -> None:
        resp = await news_client.get("/api/v1/news?limit=101")
        assert resp.status_code == 422
