"""AI summarizer with 3-tier fallback: Gemini -> GPT-4o-mini -> TextRank.

RULE 06: try/except + structlog.
"""

from __future__ import annotations

import re

import asyncpg
import structlog

from backend.common.metrics import AI_API_REQUESTS
from backend.common.quota_alert import handle_api_exception
from backend.processor.shared.ai_config import AIConfig

logger = structlog.get_logger(__name__)

_MAX_INPUT_CHARS = 4000


async def summarize(
    text: str,
    prompt: str,
    config: AIConfig,
    db_pool: asyncpg.Pool | None = None,
) -> tuple[str, bool]:
    """Summarize text using the configured AI provider with automatic fallback.

    Dispatches to the provider specified in config. On failure, falls back to
    TextRank (degraded=True). On total failure, returns an empty string.

    Args:
        text:   Source text to summarize.
        prompt: Role-specific instruction prompt.
        config: AIConfig loaded from admin_settings.

    Returns:
        Tuple of (summary_text, degraded). degraded=True when TextRank
        fallback was used instead of the configured provider.
    """
    try:
        provider = config.provider.lower()

        if provider == "gemini":
            result = await _call_gemini(text, prompt, config)
            AI_API_REQUESTS.labels(provider="gemini", result="success").inc()
            return (result, False)

        if provider == "openai":
            result = await _call_openai(text, prompt, config)
            AI_API_REQUESTS.labels(provider="openai", result="success").inc()
            return (result, False)

        if provider == "textrank":
            result = _textrank_summary(text)
            return (result, True)

        logger.warning("ai_provider_unknown", provider=provider)
        result = _textrank_summary(text)
        return (result, True)

    except Exception as exc:
        AI_API_REQUESTS.labels(provider=config.provider, result="failure").inc()
        await handle_api_exception(exc, config.provider.lower(), db_pool)
        logger.warning(
            "ai_provider_failed",
            provider=config.provider,
            fallback_reason=str(exc),
        )
        try:
            result = _textrank_summary(text)
            return (result, True)
        except Exception as fallback_exc:
            logger.error(
                "ai_textrank_fallback_failed",
                fallback_reason=str(fallback_exc),
            )
            return ("", True)


async def _call_gemini(text: str, prompt: str, config: AIConfig) -> str:
    """Call Google Gemini Flash API.

    Args:
        text:   Source text (truncated to _MAX_INPUT_CHARS internally).
        prompt: Instruction prompt.
        config: AIConfig carrying model name and api_key.

    Returns:
        Generated summary string.

    Raises:
        ImportError: If google-generativeai is not installed.
        Exception:   On API or network failure.
    """
    try:
        import google.generativeai as genai  # lazy import (optional dep)
    except ImportError:
        raise

    try:
        genai.configure(api_key=config.api_key.get_secret_value())
        model = genai.GenerativeModel(config.model)
        full_prompt = f"{prompt}\n\nContext:\n{text[:_MAX_INPUT_CHARS]}"
        response = await model.generate_content_async(full_prompt)
        return response.text
    except ImportError:
        raise
    except Exception as exc:
        logger.error("gemini_call_failed", model=config.model, error=str(exc))
        raise


async def _call_openai(text: str, prompt: str, config: AIConfig) -> str:
    """Call OpenAI Chat Completions API.

    Args:
        text:   Source text (truncated to _MAX_INPUT_CHARS internally).
        prompt: Instruction prompt.
        config: AIConfig carrying model name, api_key, max_tokens, temperature.

    Returns:
        Generated summary string.

    Raises:
        ImportError: If openai package is not installed.
        Exception:   On API or network failure.
    """
    try:
        from openai import AsyncOpenAI  # lazy import (optional dep)
    except ImportError:
        raise

    try:
        client = AsyncOpenAI(api_key=config.api_key.get_secret_value())
        response = await client.chat.completions.create(
            model=config.model,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}\n\nContext:\n{text[:_MAX_INPUT_CHARS]}",
                }
            ],
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
        return response.choices[0].message.content or ""
    except ImportError:
        raise
    except Exception as exc:
        logger.error("openai_call_failed", model=config.model, error=str(exc))
        raise


def _textrank_summary(text: str, sentences: int = 5) -> str:
    """Pure-Python TextRank summarizer (no external dependencies).

    Splits text into sentences, scores each by word-overlap similarity
    against all other sentences (TF-IDF-like), and returns the top
    `sentences` sentences in their original order.

    Args:
        text:      Source text to summarize.
        sentences: Maximum number of sentences to return.

    Returns:
        Top sentences joined by a single space, or the original text
        if it cannot be split meaningfully.
    """
    if not text or not text.strip():
        return ""

    # Split on sentence-ending punctuation
    raw_sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    raw_sentences = [s.strip() for s in raw_sentences if s.strip()]

    if not raw_sentences:
        return text.strip()

    if len(raw_sentences) <= sentences:
        return " ".join(raw_sentences)

    # Tokenise each sentence into a set of lowercase words
    def _word_set(sentence: str) -> set[str]:
        return set(re.findall(r"\w+", sentence.lower()))

    word_sets = [_word_set(s) for s in raw_sentences]

    # Score each sentence: sum of Jaccard similarity against every other sentence
    scores: list[float] = []
    for i, ws_i in enumerate(word_sets):
        score = 0.0
        for j, ws_j in enumerate(word_sets):
            if i == j:
                continue
            union = ws_i | ws_j
            if union:
                score += len(ws_i & ws_j) / len(union)
        scores.append(score)

    # Select top-N by score, preserve original order for readability
    top_indices = sorted(
        sorted(range(len(scores)), key=lambda idx: scores[idx], reverse=True)[:sentences]
    )
    return " ".join(raw_sentences[i] for i in top_indices)
