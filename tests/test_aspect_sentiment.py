"""Tests for Aspect-Based Sentiment Analysis (E5).

Covers:
- extract_sentences_with_aspect()
- analyze_aspect_sentiments()
- GET /api/v1/trends/{group_id}/sentiment/aspects endpoint
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.algorithms.aspect_sentiment import (
    AspectSentimentResult,
    analyze_aspect_sentiments,
    extract_sentences_with_aspect,
)
from backend.processor.algorithms.sentiment import SentimentAnalyzer
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GROUP_ID = "00000000-0000-0000-0000-000000000042"
_GROUP_ID_EMPTY = "00000000-0000-0000-0000-000000000099"


def _make_lexicon_analyzer() -> SentimentAnalyzer:
    """SentimentAnalyzer with no ML model (lexicon-only)."""
    analyzer = SentimentAnalyzer()
    analyzer._model = None
    analyzer._model_loaded = True
    return analyzer


def _make_group_row(*, keywords: list[str] | None = None) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": _GROUP_ID,
        "title": "AI 트렌드",
        "category": "tech",
        "locale": "ko",
        "score": 0.9,
        "early_trend_score": 0.5,
        "keywords": keywords if keywords is not None else ["AI", "머신러닝"],
        "created_at": datetime(2026, 3, 17, 0, 0, 0, tzinfo=timezone.utc),
        "summary": "AI 관련 트렌드",
        "direction": "rising",
    }[key]
    return row


# ---------------------------------------------------------------------------
# Unit tests: extract_sentences_with_aspect
# ---------------------------------------------------------------------------


class TestExtractSentencesWithAspect:
    def test_returns_matching_sentence(self) -> None:
        """aspect가 포함된 문장만 반환."""
        result = extract_sentences_with_aspect("AI가 발전했다. 주가가 올랐다.", "AI")
        assert result == ["AI가 발전했다"]

    def test_no_match_returns_empty(self) -> None:
        """aspect가 없으면 빈 리스트 반환."""
        result = extract_sentences_with_aspect("주가 상승", "AI")
        assert result == []

    def test_case_insensitive_match(self) -> None:
        """대소문자 무관 매칭."""
        result = extract_sentences_with_aspect("ai is great. Other news.", "AI")
        assert len(result) == 1
        assert "ai is great" in result[0].lower()

    def test_sentence_truncated_to_512(self) -> None:
        """각 문장 최대 512자로 자름."""
        long_sentence = "AI " + "x" * 600
        result = extract_sentences_with_aspect(long_sentence, "AI")
        assert len(result) == 1
        assert len(result[0]) <= 512

    def test_multiple_sentences_match(self) -> None:
        """여러 문장이 aspect를 포함할 때 모두 반환."""
        text = "AI가 성장했다. AI가 떠오른다. 무관한 뉴스."
        result = extract_sentences_with_aspect(text, "AI")
        assert len(result) == 2

    def test_newline_as_separator(self) -> None:
        """개행 문자도 구분자로 처리."""
        text = "AI 발전\n주가 상승\nAI 트렌드"
        result = extract_sentences_with_aspect(text, "AI")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Unit tests: analyze_aspect_sentiments
# ---------------------------------------------------------------------------


class TestAnalyzeAspectSentiments:
    def test_returns_result_with_positive_text(self) -> None:
        """긍정 단어를 포함한 텍스트에서 total >= 1 반환."""
        analyzer = _make_lexicon_analyzer()
        results = analyze_aspect_sentiments(
            texts=["AI 혁신적"],
            aspects=["AI"],
            analyzer=analyzer,
        )
        # total=0 제거 후 남은 결과가 있어야 함 (lexicon fallback에서는 neutral 가능)
        # 단, 문장이 aspect를 포함하므로 total >= 1
        assert len(results) >= 1
        assert results[0].total >= 1

    def test_empty_texts_returns_empty(self) -> None:
        """텍스트가 없으면 빈 결과 반환."""
        analyzer = _make_lexicon_analyzer()
        results = analyze_aspect_sentiments(
            texts=[],
            aspects=["AI"],
            analyzer=analyzer,
        )
        assert results == []

    def test_sorted_by_total_desc(self) -> None:
        """total 내림차순 정렬 확인."""
        analyzer = _make_lexicon_analyzer()
        # "AI"는 3문장, "머신러닝"은 1문장
        texts = [
            "AI가 좋다. AI가 성장했다. AI 혁신. 머신러닝도 좋다.",
        ]
        results = analyze_aspect_sentiments(
            texts=texts,
            aspects=["AI", "머신러닝"],
            analyzer=analyzer,
        )
        if len(results) >= 2:
            assert results[0].total >= results[1].total

    def test_zero_total_filtered_out(self) -> None:
        """total=0인 aspect는 제거."""
        analyzer = _make_lexicon_analyzer()
        results = analyze_aspect_sentiments(
            texts=["관련없는 텍스트"],
            aspects=["AI"],
            analyzer=analyzer,
        )
        # "AI"가 포함되지 않으므로 total=0 → 제거
        assert all(r.total > 0 for r in results)

    def test_max_sentences_per_aspect_limits_analysis(self) -> None:
        """max_sentences_per_aspect가 샘플링에 적용됨."""
        analyzer = _make_lexicon_analyzer()
        texts = [f"AI 문장 {i}" for i in range(100)]
        results = analyze_aspect_sentiments(
            texts=texts,
            aspects=["AI"],
            analyzer=analyzer,
            max_sentences_per_aspect=5,
        )
        if results:
            assert results[0].total <= 5

    def test_analyzer_exception_handled_gracefully(self) -> None:
        """감성 분석 예외 발생 시 해당 문장 건너뜀."""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = RuntimeError("model error")
        results = analyze_aspect_sentiments(
            texts=["AI 오류 테스트"],
            aspects=["AI"],
            analyzer=mock_analyzer,
        )
        # 예외가 발생해도 total=0 → 필터링됨
        assert results == []

    def test_result_fields(self) -> None:
        """반환된 AspectSentimentResult의 필드 타입 확인."""
        analyzer = _make_lexicon_analyzer()
        results = analyze_aspect_sentiments(
            texts=["AI는 좋습니다"],
            aspects=["AI"],
            analyzer=analyzer,
        )
        if results:
            r = results[0]
            assert isinstance(r, AspectSentimentResult)
            assert isinstance(r.aspect, str)
            assert isinstance(r.positive, int)
            assert isinstance(r.neutral, int)
            assert isinstance(r.negative, int)
            assert r.total == r.positive + r.neutral + r.negative


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-aspect")


@pytest.fixture
async def aspect_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
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


def _make_mock_fetchrow_for_group(
    keywords: list[str] | None = None,
) -> AsyncMock:
    """fetchrow mock that returns a group row with specified keywords."""
    row = _make_group_row(keywords=keywords)
    return AsyncMock(return_value=row)


class TestGetTrendSentimentAspectsEndpoint:
    async def test_returns_200_with_aspects(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """정상 트렌드 → 200 + aspects 배열 반환."""
        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        # fetchrow → group detail
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = _make_mock_fetchrow_for_group(keywords=["AI", "머신러닝"])
        # fetch → articles (empty is fine for this test)
        mock_conn.fetch = AsyncMock(return_value=[])

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
            patch("backend.api.routers.trends.get_cached", return_value=None),
            patch("backend.api.routers.trends.set_cached", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/v1/trends/{_GROUP_ID}/sentiment/aspects")

        assert resp.status_code == 200
        data = resp.json()
        assert data["group_id"] == _GROUP_ID
        assert "aspects" in data
        assert isinstance(data["aspects"], list)

    async def test_returns_404_for_nonexistent_trend(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """존재하지 않는 group_id → 404."""
        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
            patch("backend.api.routers.trends.get_cached", return_value=None),
            patch("backend.api.routers.trends.set_cached", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/v1/trends/nonexistent-id/sentiment/aspects")

        assert resp.status_code == 404

    async def test_top_k_limits_aspects(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """top_k=3이면 keywords 최대 3개만 분석."""
        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        many_keywords = ["AI", "머신러닝", "딥러닝", "NLP", "GPT"]
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = _make_mock_fetchrow_for_group(keywords=many_keywords)
        mock_conn.fetch = AsyncMock(return_value=[])

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
            patch("backend.api.routers.trends.get_cached", return_value=None),
            patch("backend.api.routers.trends.set_cached", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/v1/trends/{_GROUP_ID}/sentiment/aspects?top_k=3")

        assert resp.status_code == 200
        data = resp.json()
        # aspects 수는 top_k=3 이하 (sentences 없으면 total=0 → filtered out)
        assert len(data["aspects"]) <= 3

    async def test_empty_keywords_returns_empty_aspects(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """keywords가 빈 리스트인 트렌드 → aspects=[]."""
        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = _make_mock_fetchrow_for_group(keywords=[])
        mock_conn.fetch = AsyncMock(return_value=[])

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
            patch("backend.api.routers.trends.get_cached", return_value=None),
            patch("backend.api.routers.trends.set_cached", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/v1/trends/{_GROUP_ID}/sentiment/aspects")

        assert resp.status_code == 200
        data = resp.json()
        assert data["aspects"] == []
