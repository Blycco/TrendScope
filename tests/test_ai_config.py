"""Tests for backend/processor/shared/ai_config.py."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.shared.ai_config import AIConfig, _default_config, get_ai_config
from pydantic import SecretStr


def _make_pool(fetchrow_return: object = None) -> MagicMock:
    """Build a minimal mock asyncpg pool."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


def _make_db_row() -> dict:
    """Simulate an admin_settings DB row whose 'value' column holds an AI config dict."""
    return {
        "value": {
            "provider": "gemini",
            "model": "gemini-1.5-flash",
            "api_key": "test-api-key-xyz",
            "max_tokens": 1024,
            "temperature": 0.7,
            "fallback_provider": "textrank",
        }
    }


class TestGetAiConfigCacheHit:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_config(self) -> None:
        cached = json.dumps(
            {
                "provider": "gemini",
                "model": "gemini-1.5-flash",
                "api_key": "cached-key",
                "max_tokens": 512,
                "temperature": 0.5,
                "fallback_provider": "textrank",
            }
        ).encode()

        pool = _make_pool()

        with patch(
            "backend.processor.shared.ai_config.get_cached",
            new=AsyncMock(return_value=cached),
        ):
            config = await get_ai_config(pool)

        assert config.provider == "gemini"
        assert config.model == "gemini-1.5-flash"
        assert config.max_tokens == 512
        assert config.temperature == 0.5
        assert config.fallback_provider == "textrank"
        assert isinstance(config.api_key, SecretStr)

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db_query(self) -> None:
        cached = json.dumps(
            {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": "cached-key",
                "max_tokens": 256,
                "temperature": 0.3,
                "fallback_provider": "textrank",
            }
        ).encode()

        pool = _make_pool()
        conn = pool.acquire.return_value.__aenter__.return_value

        with patch(
            "backend.processor.shared.ai_config.get_cached",
            new=AsyncMock(return_value=cached),
        ):
            await get_ai_config(pool)

        conn.fetchrow.assert_not_awaited()


class TestGetAiConfigCacheMiss:
    @pytest.mark.asyncio
    async def test_cache_miss_loads_from_db(self) -> None:
        pool = _make_pool(fetchrow_return=_make_db_row())
        mock_set_cached = AsyncMock()

        with (
            patch(
                "backend.processor.shared.ai_config.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.shared.ai_config.set_cached",
                new=mock_set_cached,
            ),
        ):
            config = await get_ai_config(pool)

        assert config.provider == "gemini"
        assert config.model == "gemini-1.5-flash"
        assert config.max_tokens == 1024
        mock_set_cached.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_db_miss_returns_default(self) -> None:
        pool = _make_pool(fetchrow_return=None)

        with patch(
            "backend.processor.shared.ai_config.get_cached",
            new=AsyncMock(return_value=None),
        ):
            config = await get_ai_config(pool)

        assert config.provider == "textrank"
        assert config.model == "textrank"

    @pytest.mark.asyncio
    async def test_db_exception_returns_default(self) -> None:
        pool = MagicMock()
        pool.acquire = MagicMock(side_effect=Exception("DB connection lost"))

        with patch(
            "backend.processor.shared.ai_config.get_cached",
            new=AsyncMock(return_value=None),
        ):
            config = await get_ai_config(pool)

        assert config.provider == "textrank"
        assert config.model == "textrank"


class TestDefaultConfig:
    def test_default_config_is_textrank(self) -> None:
        config = _default_config()
        assert config.provider == "textrank"
        assert config.model == "textrank"

    def test_default_config_has_empty_api_key(self) -> None:
        config = _default_config()
        assert config.api_key.get_secret_value() == ""

    def test_default_config_fallback_provider_is_textrank(self) -> None:
        config = _default_config()
        assert config.fallback_provider == "textrank"


class TestAiConfigRepr:
    def test_api_key_not_in_repr(self) -> None:
        config = AIConfig(
            provider="gemini",
            model="gemini-1.5-flash",
            api_key=SecretStr("super-secret-key-12345"),
            max_tokens=512,
            temperature=0.5,
            fallback_provider="textrank",
        )
        r = repr(config)
        assert "super-secret-key-12345" not in r

    def test_repr_contains_provider_and_model(self) -> None:
        config = AIConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key=SecretStr("secret"),
            max_tokens=256,
            temperature=0.0,
            fallback_provider="textrank",
        )
        r = repr(config)
        assert "openai" in r
        assert "gpt-4o-mini" in r
