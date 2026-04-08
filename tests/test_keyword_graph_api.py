"""Tests for GET /api/v1/trends/{group_id}/keywords/graph endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_GROUP_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-keyword-graph")


def _make_article_keywords() -> list[tuple[str, list[str]]]:
    """Return sample article keywords for testing co-occurrence."""
    return [
        ("article-1", ["AI", "딥러닝", "GPT", "자연어처리"]),
        ("article-2", ["AI", "딥러닝", "컴퓨터비전", "로봇"]),
        ("article-3", ["AI", "GPT", "챗봇", "자연어처리"]),
    ]


@pytest.fixture
async def keyword_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    with (
        patch("backend.api.routers.health.get_redis", return_value=mock_redis),
        patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        patch("backend.api.routers.keywords.get_cached", return_value=None),
        patch("backend.api.routers.keywords.set_cached", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestKeywordGraph:
    async def test_keyword_graph_success(
        self, keyword_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """200 with valid keyword graph data."""
        with patch(
            "backend.api.routers.keywords.fetch_group_article_keywords",
            new_callable=AsyncMock,
            return_value=_make_article_keywords(),
        ):
            resp = await keyword_client.get(f"/api/v1/trends/{_VALID_GROUP_ID}/keywords/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["group_id"] == _VALID_GROUP_ID
        assert len(data["nodes"]) > 0
        assert any(n["term"] == "AI" for n in data["nodes"])
        # AI appears in all 3 articles, should have highest frequency
        ai_node = next(n for n in data["nodes"] if n["term"] == "AI")
        assert ai_node["frequency"] >= 3

    async def test_keyword_graph_empty(
        self, keyword_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """Empty articles return empty graph."""
        with patch(
            "backend.api.routers.keywords.fetch_group_article_keywords",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await keyword_client.get(f"/api/v1/trends/{_VALID_GROUP_ID}/keywords/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []

    async def test_keyword_graph_cache_hit(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Cache hit returns cached response without DB query."""
        cached_body = b'{"group_id":"cached-id","nodes":[],"edges":[]}'

        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
            patch("backend.api.routers.keywords.get_cached", return_value=cached_body),
            patch("backend.api.routers.keywords.set_cached", new_callable=AsyncMock),
            patch(
                "backend.api.routers.keywords.fetch_group_article_keywords",
                new_callable=AsyncMock,
            ) as mock_fetch,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/v1/trends/{_VALID_GROUP_ID}/keywords/graph")

        assert resp.status_code == 200
        assert resp.json()["group_id"] == "cached-id"
        mock_fetch.assert_not_called()

    async def test_keyword_graph_db_error(
        self, keyword_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """DB error returns 500."""
        with patch(
            "backend.api.routers.keywords.fetch_group_article_keywords",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB error"),
        ):
            resp = await keyword_client.get(f"/api/v1/trends/{_VALID_GROUP_ID}/keywords/graph")
        assert resp.status_code == 500
        assert resp.json()["code"] == "E0040"

    async def test_keyword_graph_edges_have_jaccard(
        self, keyword_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """Edges have weight (Jaccard similarity) > 0."""
        with patch(
            "backend.api.routers.keywords.fetch_group_article_keywords",
            new_callable=AsyncMock,
            return_value=_make_article_keywords(),
        ):
            resp = await keyword_client.get(f"/api/v1/trends/{_VALID_GROUP_ID}/keywords/graph")
        data = resp.json()
        if data["edges"]:
            for edge in data["edges"]:
                assert edge["weight"] > 0
                assert isinstance(edge["source"], str)
                assert isinstance(edge["target"], str)

    async def test_no_auth_required(
        self, keyword_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """Public endpoint works without auth token."""
        with patch(
            "backend.api.routers.keywords.fetch_group_article_keywords",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await keyword_client.get(f"/api/v1/trends/{_VALID_GROUP_ID}/keywords/graph")
        assert resp.status_code == 200
