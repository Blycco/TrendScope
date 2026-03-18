"""AI model configuration loader from admin_settings table. (RULE 18: Redis cache TTL 300s)"""

from __future__ import annotations

import json
from dataclasses import dataclass

import asyncpg
import structlog
from pydantic import SecretStr

from backend.processor.shared.cache_manager import get_cached, set_cached

logger = structlog.get_logger(__name__)

_CACHE_KEY = "ai_config:settings"
_CACHE_TTL = 300  # 5 minutes


@dataclass
class AIConfig:
    provider: str  # "gemini" | "openai" | "textrank"
    model: str  # e.g. "gemini-1.5-flash", "gpt-4o-mini"
    api_key: SecretStr  # masked in logs via SecretStr
    max_tokens: int
    temperature: float
    fallback_provider: str  # "textrank" always as final fallback

    def __repr__(self) -> str:
        # RULE 01: never expose api_key
        return (
            f"AIConfig(provider={self.provider!r}, model={self.model!r},"
            f" max_tokens={self.max_tokens})"
        )


def _default_config() -> AIConfig:
    """Return TextRank-only config when DB is unavailable or not configured."""
    return AIConfig(
        provider="textrank",
        model="textrank",
        api_key=SecretStr(""),
        max_tokens=512,
        temperature=0.0,
        fallback_provider="textrank",
    )


async def get_ai_config(pool: asyncpg.Pool) -> AIConfig:
    """Load AI configuration from admin_settings, with Redis caching.

    Cache TTL is 300 seconds (RULE 18). On any failure, returns TextRank-only
    default so the caller never receives a 500 error.

    Args:
        pool: Active asyncpg connection pool.

    Returns:
        AIConfig populated from DB, or default TextRank config on failure.
    """
    try:
        cached_bytes = await get_cached(_CACHE_KEY)
        if cached_bytes is not None:
            try:
                raw = json.loads(cached_bytes)
                config = AIConfig(
                    provider=raw["provider"],
                    model=raw["model"],
                    api_key=SecretStr(raw["api_key"]),
                    max_tokens=int(raw["max_tokens"]),
                    temperature=float(raw["temperature"]),
                    fallback_provider=raw["fallback_provider"],
                )
                logger.debug("ai_config_cache_hit", provider=config.provider, model=config.model)
                return config
            except Exception as parse_exc:
                logger.warning("ai_config_cache_parse_failed", error=str(parse_exc))

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM admin_settings WHERE key = $1",
                "ai.config",
            )

        if row is None:
            logger.warning("ai_config_db_miss", key="ai.config")
            return _default_config()

        raw: dict = row["value"]

        config = AIConfig(
            provider=raw["provider"],
            model=raw["model"],
            api_key=SecretStr(raw["api_key"]),
            max_tokens=int(raw["max_tokens"]),
            temperature=float(raw["temperature"]),
            fallback_provider=raw["fallback_provider"],
        )

        # Cache the serialisable form (api_key stored as plain str in cache;
        # Redis is a server-side store — not exposed in logs per RULE 01)
        cache_payload = json.dumps(
            {
                "provider": config.provider,
                "model": config.model,
                "api_key": config.api_key.get_secret_value(),
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "fallback_provider": config.fallback_provider,
            }
        )
        await set_cached(_CACHE_KEY, cache_payload, _CACHE_TTL)

        logger.info(
            "ai_config_loaded",
            provider=config.provider,
            model=config.model,
        )
        return config

    except Exception as exc:
        logger.error("ai_config_load_failed", error=str(exc))
        return _default_config()
