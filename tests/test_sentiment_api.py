"""Tests for GET /api/v1/trends/{group_id}/sentiment endpoint."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.algorithms.sentiment import SentimentResult
from httpx import ASGITransport, AsyncClient


def _mock_analyzer_side_effect(label_map: dict[str, str]) -> MagicMock:
    """Create a mock SentimentAnalyzer.analyze that returns labels from label_map.

    label_map maps text substrings to labels.  If no match, returns 'neutral'.
    """

    def analyze(text: str) -> SentimentResult:
        for substring, label in label_map.items():
            if substring in text:
                return SentimentResult(label=label, score=0.9)
        return SentimentResult(label="neutral", score=0.5)

    mock = MagicMock()
    mock.analyze = analyze
    return mock


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-sentiment")


@pytest.fixture
async def sentiment_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
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


GROUP_ID = "00000000-0000-0000-0000-000000000001"


class TestGetTrendSentiment:
    async def test_returns_200_with_distribution(
        self, sentiment_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """Sentiment endpoint returns correct distribution counts."""
        mock_analyzer = _mock_analyzer_side_effect(
            {
                "긍정": "positive",
                "부정": "negative",
            }
        )

        with (
            patch(
                "backend.api.routers.trends.fetch_group_article_texts",
                new_callable=AsyncMock,
                return_value=["긍정적 기사", "긍정 뉴스", "부정적 기사", "일반 기사"],
            ),
            patch("backend.api.routers.trends._sentiment_analyzer", mock_analyzer),
        ):
            resp = await sentiment_client.get(f"/api/v1/trends/{GROUP_ID}/sentiment")

        assert resp.status_code == 200
        data = resp.json()
        assert data["positive"] == 2
        assert data["negative"] == 1
        assert data["neutral"] == 1
        assert data["total"] == 4

    async def test_empty_articles_returns_zero_total(
        self, sentiment_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """When no articles exist, total should be 0."""
        with patch(
            "backend.api.routers.trends.fetch_group_article_texts",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await sentiment_client.get(f"/api/v1/trends/{GROUP_ID}/sentiment")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["positive"] == 0
        assert data["neutral"] == 0
        assert data["negative"] == 0

    async def test_cache_hit_returns_cached(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """When cache is hit, the cached response is returned directly."""
        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        cached_body = json.dumps(
            {"positive": 10, "neutral": 5, "negative": 3, "total": 18}
        ).encode()

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.routers.trends.get_cached", return_value=cached_body),
            patch("backend.api.routers.trends.set_cached", new_callable=AsyncMock),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/v1/trends/{GROUP_ID}/sentiment")

        assert resp.status_code == 200
        data = resp.json()
        assert data["positive"] == 10
        assert data["total"] == 18

    async def test_db_error_returns_500(
        self, sentiment_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """DB error returns 500."""
        with patch(
            "backend.api.routers.trends.fetch_group_article_texts",
            new_callable=AsyncMock,
            side_effect=Exception("DB연결 실패"),
        ):
            resp = await sentiment_client.get(f"/api/v1/trends/{GROUP_ID}/sentiment")

        assert resp.status_code == 500

    async def test_all_positive_articles(
        self, sentiment_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """All positive articles should have total == positive."""
        mock_analyzer = _mock_analyzer_side_effect({"pos": "positive"})

        with (
            patch(
                "backend.api.routers.trends.fetch_group_article_texts",
                new_callable=AsyncMock,
                return_value=["pos text 1", "pos text 2"],
            ),
            patch("backend.api.routers.trends._sentiment_analyzer", mock_analyzer),
        ):
            resp = await sentiment_client.get(f"/api/v1/trends/{GROUP_ID}/sentiment")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["positive"] == 2
        assert data["negative"] == 0

    async def test_all_negative_articles(
        self, sentiment_client: AsyncClient, mock_db_pool: MagicMock
    ) -> None:
        """All negative articles should have total == negative."""
        mock_analyzer = _mock_analyzer_side_effect({"neg": "negative"})

        with (
            patch(
                "backend.api.routers.trends.fetch_group_article_texts",
                new_callable=AsyncMock,
                return_value=["neg text 1", "neg text 2"],
            ),
            patch("backend.api.routers.trends._sentiment_analyzer", mock_analyzer),
        ):
            resp = await sentiment_client.get(f"/api/v1/trends/{GROUP_ID}/sentiment")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["negative"] == 2
        assert data["positive"] == 0
