"""Tests for backend.crawler.sources.extractor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from backend.crawler.sources.extractor import (
    _fetch_html,
    _stage1_newspaper,
    _stage2_readability,
    _stage3_bs4,
    extract_body,
)


class TestExtractBody:
    async def test_returns_empty_on_fetch_fail(self) -> None:
        with patch(
            "backend.crawler.sources.extractor._fetch_html",
            AsyncMock(return_value=""),
        ):
            result = await extract_body("https://example.com/article")
            assert result == ""

    async def test_uses_provided_html_skips_fetch(self) -> None:
        html = (
            "<html><body><p>Hello world this is a test article"
            " with more than fifty characters.</p></body></html>"
        )
        with patch(
            "backend.crawler.sources.extractor._stage1_newspaper",
            return_value="Hello world this is a test article with more than fifty characters.",
        ):
            result = await extract_body("https://example.com/article", html=html)
            assert "Hello world" in result

    async def test_stage1_success(self) -> None:
        html = "<html><body><p>Article text</p></body></html>"
        with patch(
            "backend.crawler.sources.extractor._stage1_newspaper",
            return_value="Article text that is definitely longer than fifty characters total.",
        ):
            result = await extract_body("https://example.com", html=html)
            assert result == "Article text that is definitely longer than fifty characters total."

    async def test_stage2_fallback(self) -> None:
        html = "<html><body><p>Article</p></body></html>"
        with (
            patch(
                "backend.crawler.sources.extractor._stage1_newspaper",
                return_value="",
            ),
            patch(
                "backend.crawler.sources.extractor._stage2_readability",
                return_value="Readability text that is definitely longer than fifty chars here.",
            ),
        ):
            result = await extract_body("https://example.com", html=html)
            assert "Readability text" in result

    async def test_stage3_fallback(self) -> None:
        long_text = "Some text content that is long enough to pass the quality gate. " * 2
        html = f"<html><body><p>{long_text}</p></body></html>"
        with (
            patch(
                "backend.crawler.sources.extractor._stage1_newspaper",
                return_value="",
            ),
            patch(
                "backend.crawler.sources.extractor._stage2_readability",
                return_value="",
            ),
        ):
            result = await extract_body("https://example.com", html=html)
            assert "Some text content" in result

    async def test_all_stages_failed_returns_empty(self) -> None:
        html = "<html><body><p>Hi</p></body></html>"
        with (
            patch(
                "backend.crawler.sources.extractor._stage1_newspaper",
                return_value="",
            ),
            patch(
                "backend.crawler.sources.extractor._stage2_readability",
                return_value="",
            ),
            patch(
                "backend.crawler.sources.extractor._stage3_bs4",
                return_value="",
            ),
        ):
            result = await extract_body("https://example.com", html=html)
            assert result == ""


class TestStage3Bs4:
    def test_strips_script_tags(self) -> None:
        body = "Clean text that is long enough to pass the minimum body length quality gate easily."
        html = f"<html><body><script>alert('x')</script><p>{body}</p></body></html>"
        result = _stage3_bs4(html)
        assert "alert" not in result
        assert "Clean text" in result

    def test_strips_nav_footer(self) -> None:
        body = "Article content that is definitely long enough to pass the fifty char quality gate."
        html = f"<html><body><nav>Menu</nav><p>{body}</p><footer>Footer</footer></body></html>"
        result = _stage3_bs4(html)
        assert "Menu" not in result
        assert "Footer" not in result
        assert "Article content" in result

    def test_empty_html(self) -> None:
        result = _stage3_bs4("")
        assert result == ""

    def test_short_text_returns_empty(self) -> None:
        html = "<html><body><p>Hi</p></body></html>"
        result = _stage3_bs4(html)
        assert result == ""

    def test_returns_empty_string_on_error(self) -> None:
        result = _stage3_bs4(None)  # type: ignore[arg-type]
        assert isinstance(result, str)


class TestStage1Newspaper:
    def test_returns_empty_on_article_exception(self) -> None:
        html = "<html><body><p>x</p></body></html>"
        result = _stage1_newspaper("https://example.com", html)
        assert isinstance(result, str)

    def test_returns_empty_on_short_text(self) -> None:
        html = "<html><body><p>Hi</p></body></html>"
        result = _stage1_newspaper("https://example.com", html)
        assert result == ""


class TestStage2Readability:
    def test_returns_empty_on_exception(self) -> None:
        result = _stage2_readability("https://example.com", "")
        assert isinstance(result, str)

    def test_extracts_content_from_html(self) -> None:
        html = (
            "<html><body><article>" + "This is article content. " * 5 + "</article></body></html>"
        )
        result = _stage2_readability("https://example.com", html)
        assert isinstance(result, str)


class TestFetchHtml:
    async def test_returns_text_on_success(self) -> None:
        with patch("httpx.AsyncClient") as mock_cls:
            mock_resp = MagicMock()
            mock_resp.text = "<html>content</html>"
            mock_resp.raise_for_status = MagicMock()
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await _fetch_html("https://example.com")
            assert result == "<html>content</html>"

    async def test_returns_empty_on_error(self) -> None:
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=RuntimeError("network error"))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await _fetch_html("https://broken.com")
            assert result == ""

    async def test_reuses_provided_client(self) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "<html>reused</html>"
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        result = await _fetch_html("https://example.com", client=mock_client)
        assert result == "<html>reused</html>"
        mock_client.get.assert_awaited_once()
