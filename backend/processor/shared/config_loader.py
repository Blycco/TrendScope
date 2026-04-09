"""DB/Redis 기반 설정 로더 — 알고리즘 파라미터, 불용어, 필터 키워드, 카테고리 키워드.

모든 알고리즘 모듈은 하드코딩 대신 이 모듈을 통해 설정을 로드한다.
(RULE 18: Redis 캐시 적극 활용)
"""

from __future__ import annotations

import json

import asyncpg
import structlog

from backend.processor.shared.cache_manager import delete_cached, get_cached, set_cached

logger = structlog.get_logger(__name__)

# ── 캐시 TTL ────────────────────────────────────────────────────────────────
_SETTING_TTL = 300  # 5분
_STOPWORDS_TTL = 600  # 10분
_FILTER_KW_TTL = 600  # 10분
_CATEGORY_KW_TTL = 600  # 10분

# ── 캐시 키 패턴 ─────────────────────────────────────────────────────────────
_KEY_SETTING = "config:setting:{key}"
_KEY_STOPWORDS = "config:stopwords:{locale}"
_KEY_FILTER_KW = "config:filter_kw:{category}"
_KEY_CATEGORY_KW = "config:category_kw"


async def get_setting(
    pool: asyncpg.Pool,
    key: str,
    default: float | str | int,
) -> float | str | int:
    """admin_settings에서 값 로드. Redis 5분 캐시.

    타입은 default 값의 타입 기준으로 자동 캐스팅.
    DB/캐시 오류 시 default 반환.
    """
    cache_key = _KEY_SETTING.format(key=key)
    try:
        cached = await get_cached(cache_key)
        if cached is not None:
            raw = cached.decode() if isinstance(cached, bytes) else cached
            return _cast(raw, default)
    except Exception as exc:
        logger.warning("config_cache_read_failed", key=key, error=str(exc))

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM admin_settings WHERE key = $1",
                key,
            )
        if row is None:
            logger.debug("config_setting_not_found", key=key, using_default=default)
            return default

        raw_value = row["value"]
        # admin_settings.value는 JSONB — 문자열 값은 '"text"' 형태로 저장됨
        if isinstance(raw_value, str):
            try:
                raw_value = json.loads(raw_value)
            except (ValueError, TypeError):
                pass
        value = _cast(str(raw_value), default)
        await set_cached(cache_key, str(value).encode(), _SETTING_TTL)
        return value

    except Exception as exc:
        logger.error("config_setting_load_failed", key=key, error=str(exc))
        return default


def _cast(raw: str, default: float | str | int) -> float | str | int:
    """default 타입 기준으로 raw 문자열을 캐스팅."""
    try:
        if isinstance(default, float):
            return float(raw)
        if isinstance(default, int):
            return int(float(raw))  # "2.0" → 2
        return str(raw)
    except (ValueError, TypeError):
        return default


async def get_stopwords(pool: asyncpg.Pool, locale: str = "ko") -> frozenset[str]:
    """stopword 테이블(is_active=TRUE)에서 로드. Redis 10분 캐시."""
    cache_key = _KEY_STOPWORDS.format(locale=locale)
    try:
        cached = await get_cached(cache_key)
        if cached is not None:
            words = json.loads(cached.decode() if isinstance(cached, bytes) else cached)
            return frozenset(words)
    except Exception as exc:
        logger.warning("stopwords_cache_read_failed", locale=locale, error=str(exc))

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT word FROM stopword WHERE locale = $1 AND is_active = TRUE",
                locale,
            )
        words = [r["word"] for r in rows]
        await set_cached(cache_key, json.dumps(words).encode(), _STOPWORDS_TTL)
        logger.debug("stopwords_loaded", locale=locale, count=len(words))
        return frozenset(words)

    except Exception as exc:
        logger.error("stopwords_load_failed", locale=locale, error=str(exc))
        return frozenset()


async def get_filter_keywords(
    pool: asyncpg.Pool,
    category: str | None = None,
) -> frozenset[str]:
    """filter_keyword 테이블(is_active=TRUE)에서 로드. Redis 10분 캐시.

    category=None → 전체 활성 키워드 반환.
    category='obituary' → 해당 카테고리만 반환.
    """
    cache_key = _KEY_FILTER_KW.format(category=category or "all")
    try:
        cached = await get_cached(cache_key)
        if cached is not None:
            keywords = json.loads(cached.decode() if isinstance(cached, bytes) else cached)
            return frozenset(keywords)
    except Exception as exc:
        logger.warning("filter_kw_cache_read_failed", category=category, error=str(exc))

    try:
        async with pool.acquire() as conn:
            if category is not None:
                rows = await conn.fetch(
                    """
                    SELECT keyword FROM filter_keyword
                    WHERE category = $1 AND is_active = TRUE
                    """,
                    category,
                )
            else:
                rows = await conn.fetch("SELECT keyword FROM filter_keyword WHERE is_active = TRUE")
        keywords = [r["keyword"] for r in rows]
        await set_cached(cache_key, json.dumps(keywords).encode(), _FILTER_KW_TTL)
        logger.debug("filter_keywords_loaded", category=category, count=len(keywords))
        return frozenset(keywords)

    except Exception as exc:
        logger.error("filter_keywords_load_failed", category=category, error=str(exc))
        return frozenset()


async def get_category_keywords(
    pool: asyncpg.Pool,
) -> dict[str, list[tuple[str, float]]]:
    """category_keyword 테이블(is_active=TRUE)에서 로드. Redis 10분 캐시.

    Returns:
        {category: [(keyword, weight), ...]} 형태.
    """
    try:
        cached = await get_cached(_KEY_CATEGORY_KW)
        if cached is not None:
            return json.loads(cached.decode() if isinstance(cached, bytes) else cached)
    except Exception as exc:
        logger.warning("category_kw_cache_read_failed", error=str(exc))

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT keyword, category, weight
                FROM category_keyword
                WHERE is_active = TRUE
                ORDER BY category, weight DESC
                """
            )
        result: dict[str, list[tuple[str, float]]] = {}
        for row in rows:
            cat = row["category"]
            if cat not in result:
                result[cat] = []
            result[cat].append((row["keyword"], float(row["weight"])))

        await set_cached(_KEY_CATEGORY_KW, json.dumps(result).encode(), _CATEGORY_KW_TTL)
        logger.debug("category_keywords_loaded", categories=list(result.keys()))
        return result

    except Exception as exc:
        logger.error("category_keywords_load_failed", error=str(exc))
        return {}


async def invalidate_cache(prefix: str) -> None:
    """어드민 변경 시 관련 캐시 키 무효화.

    prefix:
        'setting:{key}' → 특정 설정 키 하나
        'stopwords'     → 전체 불용어 (ko + en)
        'filter_kw'     → 전체 필터 키워드
        'category_kw'   → 카테고리 키워드 전체
    """
    try:
        if prefix.startswith("setting:"):
            key = prefix.split("setting:")[-1]
            await delete_cached(_KEY_SETTING.format(key=key))
            logger.info("config_cache_invalidated", cache_key=prefix)

        elif prefix == "stopwords":
            for locale in ("ko", "en"):
                await delete_cached(_KEY_STOPWORDS.format(locale=locale))
            logger.info("stopwords_cache_invalidated")

        elif prefix == "filter_kw":
            # 카테고리별 + 전체 캐시 모두 삭제
            for cat in ("ad", "gambling", "adult", "obituary", "irrelevant", "custom", "all"):
                await delete_cached(_KEY_FILTER_KW.format(category=cat))
            logger.info("filter_kw_cache_invalidated")

        elif prefix == "category_kw":
            await delete_cached(_KEY_CATEGORY_KW)
            logger.info("category_kw_cache_invalidated")

        else:
            logger.warning("config_invalidate_unknown_prefix", prefix=prefix)

    except Exception as exc:
        logger.error("config_cache_invalidate_failed", prefix=prefix, error=str(exc))
