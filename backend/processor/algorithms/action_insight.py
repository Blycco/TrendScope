"""Action Insight Engine: generates role-tailored actionable insights via AI + cache.

Cache key: insights:{role}:{keyword.lower()}, TTL 3600s.
Anti-hallucination: source_urls filtered to only include URLs present in input sources.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import asyncpg
import structlog

from backend.api.schemas.insights import InsightRequest
from backend.processor.shared.ai_config import AIConfig
from backend.processor.shared.ai_summarizer import summarize
from backend.processor.shared.cache_manager import get_cached, set_cached

logger = structlog.get_logger(__name__)

_CACHE_TTL = 3600  # 1 hour

_ROLE_PROMPTS: dict[str, str] = {
    "marketer": (
        "You are a marketing strategist. Based on the provided trend sources, "
        "generate a JSON response with:\n"
        '- "ad_opportunities": list of 3 specific advertising opportunities (string each)\n'
        '- "source_urls": list of URLs from the source material that support your suggestions\n\n'
        "Respond ONLY with valid JSON. Do not include any text outside the JSON."
    ),
    "creator": (
        "You are a content creator advisor. Based on the provided trend sources, "
        "generate a JSON response with:\n"
        '- "title_drafts": list of 3 compelling content title drafts\n'
        '- "timing": best posting time recommendation (string)\n'
        '- "seo_keywords": list of 5 SEO keywords to target\n'
        '- "source_urls": list of supporting URLs from the sources\n\n'
        "Respond ONLY with valid JSON. Do not include any text outside the JSON."
    ),
    "owner": (
        "You are a business consultant. Based on the provided trend sources, "
        "generate a JSON response with:\n"
        '- "consumer_reactions": list of 3 consumer sentiment observations\n'
        '- "product_hints": list of 2 product improvement hints\n'
        '- "market_ops": list of 2 market opportunity observations\n'
        '- "source_urls": list of supporting URLs from the sources\n\n'
        "Respond ONLY with valid JSON. Do not include any text outside the JSON."
    ),
    "general": (
        "You are a social media assistant. Based on the provided trend sources, "
        "generate a JSON response with:\n"
        '- "sns_drafts": list of 3 SNS post drafts (short, engaging)\n'
        '- "engagement_methods": list of 3 engagement tips\n'
        '- "source_urls": list of supporting URLs from the sources\n\n'
        "Respond ONLY with valid JSON. Do not include any text outside the JSON."
    ),
}


@dataclass
class SourceItem:
    title: str
    body: str
    url: str
    source_type: str  # "news" | "sns"


class ActionInsightEngine:
    def __init__(self, pool: asyncpg.Pool, ai_config: AIConfig) -> None:
        self.pool = pool
        self.ai_config = ai_config

    async def generate(
        self,
        req: InsightRequest,
        sources: list[SourceItem],
    ) -> dict:
        """Generate role-tailored actionable insights for a keyword.

        Checks Redis cache first. On miss, calls the AI provider, filters
        source_urls for anti-hallucination, persists to DB (best-effort),
        stores in cache, and returns the result.

        Args:
            req:     InsightRequest carrying keyword, role, and locale.
            sources: List of SourceItem objects used as context.

        Returns:
            Dict with keys ``content``, ``cached``, and ``degraded``.
        """
        cache_key = f"insights:{req.role}:{req.keyword.lower()}"

        try:
            cached_bytes = await get_cached(cache_key)
            if cached_bytes is not None:
                try:
                    return {**json.loads(cached_bytes), "cached": True}
                except Exception as parse_exc:
                    logger.warning(
                        "insight_cache_parse_failed",
                        cache_key=cache_key,
                        error=str(parse_exc),
                    )
        except Exception as exc:
            logger.warning("insight_cache_get_failed", cache_key=cache_key, error=str(exc))

        context_text = "\n\n".join(f"{s.title}\n{s.body[:500]}" for s in sources)

        role_prompt = self._build_prompt(req.role)

        try:
            result_str, degraded = await summarize(context_text, role_prompt, self.ai_config)
        except Exception as exc:
            logger.warning(
                "insight_summarize_failed",
                role=req.role,
                keyword=req.keyword,
                error=str(exc),
            )
            result_str = ""
            degraded = True

        content_dict: dict
        try:
            content_dict = json.loads(result_str)
        except Exception:
            logger.warning(
                "insight_json_parse_failed",
                role=req.role,
                keyword=req.keyword,
                result_preview=result_str[:200] if result_str else "",
            )
            content_dict = self._fallback_content(req.role, sources)

        valid_urls: set[str] = {s.url for s in sources}
        if "source_urls" in content_dict and isinstance(content_dict["source_urls"], list):
            content_dict["source_urls"] = [
                url for url in content_dict["source_urls"] if url in valid_urls
            ]

        await self._persist(req, content_dict)

        output: dict = {"content": content_dict, "cached": False, "degraded": degraded}

        try:
            await set_cached(cache_key, json.dumps(output).encode(), _CACHE_TTL)
        except Exception as exc:
            logger.warning("insight_cache_set_failed", cache_key=cache_key, error=str(exc))

        return output

    def _build_prompt(self, role: str) -> str:
        """Return the role-specific prompt string.

        Args:
            role: One of ``marketer``, ``creator``, ``owner``, ``general``.

        Returns:
            Prompt string for the given role, defaulting to ``general`` if
            the role is unrecognised.
        """
        return _ROLE_PROMPTS.get(role, _ROLE_PROMPTS["general"])

    async def _persist(self, req: InsightRequest, content: dict) -> None:
        """Persist generated insight to the action_insight table (best-effort).

        On any DB error, logs a warning and returns without raising so that a
        persist failure never blocks the caller.

        Args:
            req:     InsightRequest with keyword, role, and locale.
            content: Resolved content dict to store as JSONB.
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO action_insight (trend_kw, role, locale, content, expires_at)
                    VALUES ($1, $2, $3, $4, now() + INTERVAL '1 hour')
                    """,
                    req.keyword,
                    req.role,
                    req.locale,
                    json.dumps(content),
                )
            logger.debug(
                "insight_persisted",
                keyword=req.keyword,
                role=req.role,
                locale=req.locale,
            )
        except Exception as exc:
            logger.warning(
                "insight_persist_failed",
                keyword=req.keyword,
                role=req.role,
                error=str(exc),
            )

    def _fallback_content(self, role: str, sources: list[SourceItem]) -> dict:
        """Return minimal valid content when AI JSON parsing fails.

        Args:
            role:    User role determining which schema to produce.
            sources: Source items whose URLs are included in the fallback.

        Returns:
            Role-appropriate dict with placeholder Korean-language strings.
        """
        urls = [s.url for s in sources][:3]

        if role == "marketer":
            return {
                "ad_opportunities": ["트렌드 기반 광고 기회 분석 중"],
                "source_urls": urls,
            }
        if role == "creator":
            return {
                "title_drafts": ["트렌드 콘텐츠 제안"],
                "timing": "오전 9시-11시",
                "seo_keywords": [],
                "source_urls": urls,
            }
        if role == "owner":
            return {
                "consumer_reactions": ["소비자 반응 분석 중"],
                "product_hints": [],
                "market_ops": [],
                "source_urls": urls,
            }
        # general (default)
        return {
            "sns_drafts": ["트렌드 관련 SNS 포스트"],
            "engagement_methods": [],
            "source_urls": urls,
        }
