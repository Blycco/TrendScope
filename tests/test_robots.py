"""Tests for backend.crawler.sources.robots."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


class TestIsAllowed:
    async def test_allowed_when_no_disallow(self) -> None:
        robots_txt = "User-agent: *\nAllow: /"
        with (
            patch(
                "backend.crawler.sources.robots.get_cached",
                AsyncMock(return_value=None),
            ),
            patch(
                "backend.crawler.sources.robots.set_cached",
                AsyncMock(),
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = robots_txt
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(get=AsyncMock(return_value=mock_resp))
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            from backend.crawler.sources.robots import is_allowed

            result = await is_allowed("https://example.com/article")
            assert result is True

    async def test_disallowed_path(self) -> None:
        robots_txt = "User-agent: *\nDisallow: /private/"
        with (
            patch(
                "backend.crawler.sources.robots.get_cached",
                AsyncMock(return_value=None),
            ),
            patch(
                "backend.crawler.sources.robots.set_cached",
                AsyncMock(),
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = robots_txt
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            from backend.crawler.sources.robots import is_allowed

            result = await is_allowed("https://example.com/private/secret")
            assert result is False

    async def test_returns_true_on_cache_hit(self) -> None:
        robots_txt = b"User-agent: *\nAllow: /"
        with (
            patch(
                "backend.crawler.sources.robots.get_cached",
                AsyncMock(return_value=robots_txt),
            ),
        ):
            from backend.crawler.sources.robots import is_allowed

            result = await is_allowed("https://cached.com/article")
            assert result is True

    async def test_returns_true_on_404(self) -> None:
        with (
            patch(
                "backend.crawler.sources.robots.get_cached",
                AsyncMock(return_value=None),
            ),
            patch(
                "backend.crawler.sources.robots.set_cached",
                AsyncMock(),
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            from backend.crawler.sources.robots import is_allowed

            result = await is_allowed("https://notfound.com/article")
            assert result is True

    async def test_returns_true_on_fetch_error(self) -> None:
        with (
            patch(
                "backend.crawler.sources.robots.get_cached",
                AsyncMock(return_value=None),
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=RuntimeError("network error"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            from backend.crawler.sources.robots import is_allowed

            result = await is_allowed("https://broken.com/article")
            assert result is True
