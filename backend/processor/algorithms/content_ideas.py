"""Content Ideas Engine: generates role-tailored content ideas via AI + cache.

Cache key: content_ideas:{role}:{keyword.lower()}, TTL 1800s.
Anti-hallucination: ROUGE-1 gate with threshold 0.05.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import asyncpg
import structlog

from backend.processor.shared.ai_config import AIConfig
from backend.processor.shared.ai_summarizer import summarize
from backend.processor.shared.cache_manager import get_cached, set_cached

logger = structlog.get_logger(__name__)

_CACHE_TTL = 1800  # 30 minutes
_ROUGE_THRESHOLD = 0.05

_ROLE_PROMPTS: dict[str, str] = {
    "marketer": (
        "You are a marketing content strategist. Based on the provided trend sources, "
        "generate a JSON array of 3 content ideas. Each idea must have:\n"
        '- "title": compelling content title (string)\n'
        '- "hook": opening hook sentence (string)\n'
        '- "platform": one of "youtube", "instagram", "blog", "newsletter"\n'
        '- "difficulty": one of "easy", "medium", "hard"\n\n'
        "Respond ONLY with a valid JSON array. Do not include any text outside the JSON."
    ),
    "creator": (
        "You are a content creator coach. Based on the provided trend sources, "
        "generate a JSON array of 3 content ideas. Each idea must have:\n"
        '- "title": viral-worthy content title (string)\n'
        '- "hook": attention-grabbing first sentence (string)\n'
        '- "platform": one of "youtube", "instagram", "blog", "newsletter"\n'
        '- "difficulty": one of "easy", "medium", "hard"\n\n'
        "Respond ONLY with a valid JSON array. Do not include any text outside the JSON."
    ),
    "owner": (
        "You are a business growth advisor. Based on the provided trend sources, "
        "generate a JSON array of 3 content ideas for business promotion. Each idea must have:\n"
        '- "title": business-focused content title (string)\n'
        '- "hook": value proposition hook sentence (string)\n'
        '- "platform": one of "youtube", "instagram", "blog", "newsletter"\n'
        '- "difficulty": one of "easy", "medium", "hard"\n\n'
        "Respond ONLY with a valid JSON array. Do not include any text outside the JSON."
    ),
    "general": (
        "You are a social media assistant. Based on the provided trend sources, "
        "generate a JSON array of 3 content ideas. Each idea must have:\n"
        '- "title": engaging content title (string)\n'
        '- "hook": opening hook sentence (string)\n'
        '- "platform": one of "youtube", "instagram", "blog", "newsletter"\n'
        '- "difficulty": one of "easy", "medium", "hard"\n\n'
        "Respond ONLY with a valid JSON array. Do not include any text outside the JSON."
    ),
}


@dataclass
class ContentIdea:
    title: str
    hook: str
    platform: str
    difficulty: str


def _rouge1_recall(hypothesis: str, reference: str) -> float:
    """Compute ROUGE-1 recall between hypothesis and reference strings.

    Args:
        hypothesis: Generated text to evaluate.
        reference:  Source text to compare against.

    Returns:
        Recall score in [0, 1].
    """
    hyp = set(hypothesis.lower().split())
    ref = set(reference.lower().split())
    if not ref:
        return 0.0
    return len(hyp & ref) / len(ref)


def _fallback_ideas(keyword: str, role: str) -> list[ContentIdea]:
    """Return 3 keyword-based fallback content ideas when AI fails.

    Args:
        keyword: Trend keyword to base ideas on.
        role:    User role for slight variation.

    Returns:
        List of 3 ContentIdea instances.
    """
    platforms = ["youtube", "instagram", "blog"]
    difficulties = ["easy", "medium", "hard"]

    if role == "marketer":
        titles = [
            f"{keyword} 마케팅 전략 가이드",
            f"{keyword} 트렌드 활용 광고 캠페인",
            f"{keyword} 기반 콘텐츠 마케팅",
        ]
        hooks = [
            f"{keyword} 트렌드를 마케팅에 활용하는 방법을 알아보세요.",
            f"{keyword}로 광고 전환율을 높이는 전략입니다.",
            f"{keyword} 콘텐츠로 브랜드 인지도를 높여보세요.",
        ]
    elif role == "owner":
        titles = [
            f"{keyword} 비즈니스 활용 가이드",
            f"{keyword} 트렌드로 매출 올리기",
            f"{keyword} 관련 제품/서비스 기획",
        ]
        hooks = [
            f"{keyword} 트렌드를 비즈니스에 접목하는 방법입니다.",
            f"{keyword}로 새로운 수익 기회를 만들어보세요.",
            f"{keyword} 관련 고객 니즈를 파악해보세요.",
        ]
    else:
        titles = [
            f"{keyword} 완전 정복 가이드",
            f"{keyword} 트렌드 분석",
            f"{keyword} 관련 콘텐츠 아이디어",
        ]
        hooks = [
            f"{keyword}에 대해 알아야 할 모든 것을 정리했습니다.",
            f"최근 화제인 {keyword} 트렌드를 분석합니다.",
            f"{keyword} 관련 인기 콘텐츠를 만들어보세요.",
        ]

    return [
        ContentIdea(
            title=titles[i],
            hook=hooks[i],
            platform=platforms[i],
            difficulty=difficulties[i],
        )
        for i in range(3)
    ]


class ContentIdeasEngine:
    def __init__(self, pool: asyncpg.Pool, ai_config: AIConfig) -> None:
        self.pool = pool
        self.ai_config = ai_config

    async def generate(
        self,
        keyword: str,
        role: str,
        sources: list[dict],
    ) -> dict:
        """Generate role-tailored content ideas for a keyword.

        Checks Redis cache first. On miss, calls the AI provider, applies
        ROUGE-1 gate for quality control, falls back to keyword-based ideas,
        stores in cache, and returns the result.

        Args:
            keyword: Trend keyword to generate ideas for.
            role:    User role (marketer, creator, owner, general).
            sources: List of source dicts with at least 'title' and 'body' keys.

        Returns:
            Dict with keys ``ideas``, ``cached``, and ``degraded``.
        """
        cache_key = f"content_ideas:{role}:{keyword.lower()}"

        try:
            cached_bytes = await get_cached(cache_key)
            if cached_bytes is not None:
                try:
                    return {**json.loads(cached_bytes), "cached": True}
                except Exception as parse_exc:
                    logger.warning(
                        "content_ideas_cache_parse_failed",
                        cache_key=cache_key,
                        error=str(parse_exc),
                    )
        except Exception as exc:
            logger.warning("content_ideas_cache_get_failed", cache_key=cache_key, error=str(exc))

        context_text = "\n\n".join(
            f"{s.get('title', '')}\n{s.get('body', '')[:500]}" for s in sources
        )

        role_key = role if role in _ROLE_PROMPTS else "general"
        role_prompt = _ROLE_PROMPTS[role_key]

        result_str = ""
        degraded = False

        try:
            result_str, degraded = await summarize(context_text, role_prompt, self.ai_config)
        except Exception as exc:
            logger.warning(
                "content_ideas_summarize_failed",
                role=role,
                keyword=keyword,
                error=str(exc),
            )
            result_str = ""
            degraded = True

        # ROUGE-1 gate: if AI output has insufficient overlap with source, use fallback
        if result_str and not degraded:
            source_text = " ".join(s.get("body", "") for s in sources)
            rouge = _rouge1_recall(result_str, source_text)
            if rouge < _ROUGE_THRESHOLD:
                logger.warning(
                    "content_ideas_rouge_gate_triggered",
                    rouge=rouge,
                    threshold=_ROUGE_THRESHOLD,
                )
                result_str = ""
                degraded = True

        ideas: list[ContentIdea]
        if result_str:
            try:
                raw_list = json.loads(result_str)
                if not isinstance(raw_list, list):
                    raise ValueError("Expected JSON array")
                ideas = [
                    ContentIdea(
                        title=item.get("title", ""),
                        hook=item.get("hook", ""),
                        platform=item.get("platform", "blog"),
                        difficulty=item.get("difficulty", "medium"),
                    )
                    for item in raw_list
                ]
            except Exception as parse_exc:
                logger.warning(
                    "content_ideas_json_parse_failed",
                    role=role,
                    keyword=keyword,
                    error=str(parse_exc),
                )
                ideas = _fallback_ideas(keyword, role)
                degraded = True
        else:
            ideas = _fallback_ideas(keyword, role)

        ideas_dicts = [
            {
                "title": idea.title,
                "hook": idea.hook,
                "platform": idea.platform,
                "difficulty": idea.difficulty,
            }
            for idea in ideas
        ]

        output: dict = {"ideas": ideas_dicts, "cached": False, "degraded": degraded}

        try:
            await set_cached(cache_key, json.dumps(output).encode(), _CACHE_TTL)
        except Exception as exc:
            logger.warning("content_ideas_cache_set_failed", cache_key=cache_key, error=str(exc))

        return output
