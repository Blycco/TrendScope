"""Tests for backend/jobs/digest_job.py — daily Reddit question digest."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.jobs.digest_job import build_digest_html, is_question_post, run_daily_digest


class TestIsQuestionPost:
    def test_question_mark_detected(self) -> None:
        assert is_question_post("What is trending now?") is True

    def test_how_keyword_detected(self) -> None:
        assert is_question_post("How to grow on social media") is True

    def test_why_keyword_detected(self) -> None:
        assert is_question_post("Why does this happen") is True

    def test_korean_question_detected(self) -> None:
        assert is_question_post("어떻게 트렌드를 분석하나요") is True

    def test_korean_why_detected(self) -> None:
        assert is_question_post("왜 이런 현상이 생기나") is True

    def test_non_question_excluded(self) -> None:
        assert is_question_post("New product launch announcement") is False

    def test_empty_string_returns_false(self) -> None:
        assert is_question_post("") is False

    def test_what_keyword_detected(self) -> None:
        assert is_question_post("What are the best tools for developers") is True


class TestBuildDigestHtml:
    def test_build_digest_html_success(self) -> None:
        kq = {"AI": [{"title": "How does AI work?"}]}
        html = build_digest_html(kq)
        assert "AI" in html
        assert "How does AI work?" in html

    def test_build_digest_html_empty(self) -> None:
        html = build_digest_html({})
        assert "오늘의 관련 질문이 없습니다" in html

    def test_build_digest_html_truncates_to_ten(self) -> None:
        questions = [{"title": f"Question {i}?"} for i in range(15)]
        kq = {"tech": questions}
        html = build_digest_html(kq)
        # Only first 10 should appear
        assert "Question 9?" in html
        assert "Question 10?" not in html

    def test_build_digest_html_structure(self) -> None:
        kq = {"Python": [{"title": "How to learn Python?"}]}
        html = build_digest_html(kq)
        assert "<html>" in html
        assert "</html>" in html
        assert "TrendScope" in html

    def test_build_digest_html_skips_empty_keyword(self) -> None:
        kq = {"AI": [], "Python": [{"title": "How to learn Python?"}]}
        html = build_digest_html(kq)
        assert "Python" in html
        # AI section should be absent since no questions
        assert "<h3" in html
        # Count h3 tags — only Python should appear
        assert html.count("<h3") == 1


class TestRunDailyDigest:
    @pytest.mark.asyncio
    async def test_no_subscribers_returns_zero(self) -> None:
        mock_pool = MagicMock()
        with patch(
            "backend.jobs.digest_job.get_digest_subscribers",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await run_daily_digest(mock_pool)
        assert result == 0

    @pytest.mark.asyncio
    async def test_no_reddit_data_returns_zero(self) -> None:
        mock_pool = MagicMock()
        subscribers = [{"user_id": "u1", "email": "test@example.com", "keyword": "AI"}]
        with (
            patch(
                "backend.jobs.digest_job.get_digest_subscribers",
                new_callable=AsyncMock,
                return_value=subscribers,
            ),
            patch(
                "backend.jobs.digest_job.get_recent_reddit_questions",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await run_daily_digest(mock_pool)
        assert result == 0

    @pytest.mark.asyncio
    async def test_sends_email_when_matched(self) -> None:
        mock_pool = MagicMock()
        subscribers = [{"user_id": "u1", "email": "test@example.com", "keyword": "AI"}]
        questions = [{"keyword": "How does AI work?", "score": 100.0}]
        with (
            patch(
                "backend.jobs.digest_job.get_digest_subscribers",
                new_callable=AsyncMock,
                return_value=subscribers,
            ),
            patch(
                "backend.jobs.digest_job.get_recent_reddit_questions",
                new_callable=AsyncMock,
                return_value=questions,
            ),
            patch(
                "backend.jobs.digest_job.send_html_email",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            result = await run_daily_digest(mock_pool)
        assert result == 1

    @pytest.mark.asyncio
    async def test_no_match_sends_zero_emails(self) -> None:
        mock_pool = MagicMock()
        subscribers = [{"user_id": "u1", "email": "test@example.com", "keyword": "blockchain"}]
        questions = [{"keyword": "How does AI work?", "score": 100.0}]
        with (
            patch(
                "backend.jobs.digest_job.get_digest_subscribers",
                new_callable=AsyncMock,
                return_value=subscribers,
            ),
            patch(
                "backend.jobs.digest_job.get_recent_reddit_questions",
                new_callable=AsyncMock,
                return_value=questions,
            ),
            patch(
                "backend.jobs.digest_job.send_html_email",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_send,
        ):
            result = await run_daily_digest(mock_pool)
        assert result == 0
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_questions_after_filter_returns_zero(self) -> None:
        mock_pool = MagicMock()
        subscribers = [{"user_id": "u1", "email": "test@example.com", "keyword": "AI"}]
        # None of these are question posts
        questions = [
            {"keyword": "Product launch today", "score": 50.0},
            {"keyword": "Breaking news update", "score": 40.0},
        ]
        with (
            patch(
                "backend.jobs.digest_job.get_digest_subscribers",
                new_callable=AsyncMock,
                return_value=subscribers,
            ),
            patch(
                "backend.jobs.digest_job.get_recent_reddit_questions",
                new_callable=AsyncMock,
                return_value=questions,
            ),
        ):
            result = await run_daily_digest(mock_pool)
        assert result == 0
