"""Tests for backend/processor/shared/ai_summarizer.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.shared.ai_config import AIConfig
from backend.processor.shared.ai_summarizer import (
    _call_gemini,
    _call_openai,
    _textrank_summary,
    summarize,
)
from pydantic import SecretStr


def _textrank_config() -> AIConfig:
    return AIConfig(
        provider="textrank",
        model="textrank",
        api_key=SecretStr(""),
        max_tokens=512,
        temperature=0.0,
        fallback_provider="textrank",
    )


def _gemini_config() -> AIConfig:
    return AIConfig(
        provider="gemini",
        model="gemini-1.5-flash",
        api_key=SecretStr("test-key"),
        max_tokens=512,
        temperature=0.5,
        fallback_provider="textrank",
    )


def _openai_config() -> AIConfig:
    return AIConfig(
        provider="openai",
        model="gpt-4o-mini",
        api_key=SecretStr("test-key"),
        max_tokens=512,
        temperature=0.5,
        fallback_provider="textrank",
    )


_SAMPLE_TEXT = (
    "인공지능이 빠르게 발전하고 있습니다. "
    "딥러닝 기술은 이미지 인식에 혁신을 가져왔습니다. "
    "자연어 처리 모델이 텍스트 이해 능력을 획기적으로 향상시켰습니다. "
    "많은 기업들이 AI를 비즈니스에 도입하고 있습니다. "
    "의료 분야에서도 AI 활용이 급증하고 있습니다. "
    "자율주행 기술은 교통 안전에 기여할 것입니다. "
    "AI 윤리에 대한 논의가 전 세계적으로 확산되고 있습니다. "
    "데이터 프라이버시 보호가 중요한 과제로 부상했습니다. "
    "인간과 AI의 협업 방식이 새롭게 정의되고 있습니다. "
    "미래 사회에서 AI의 역할은 더욱 커질 것입니다."
)


class TestSummarizeTextrank:
    @pytest.mark.asyncio
    async def test_textrank_provider_returns_degraded_true(self) -> None:
        config = _textrank_config()
        _, degraded = await summarize("테스트 텍스트입니다.", "요약해주세요.", config)
        assert degraded is True

    @pytest.mark.asyncio
    async def test_textrank_summary_not_empty(self) -> None:
        config = _textrank_config()
        summary, _ = await summarize(_SAMPLE_TEXT, "요약해주세요.", config)
        assert isinstance(summary, str)
        assert len(summary) > 0

    @pytest.mark.asyncio
    async def test_summarize_with_empty_text(self) -> None:
        config = _textrank_config()
        summary, degraded = await summarize("", "요약해주세요.", config)
        assert summary == ""
        assert degraded is True

    @pytest.mark.asyncio
    async def test_summarize_whitespace_only_text(self) -> None:
        config = _textrank_config()
        summary, degraded = await summarize("   ", "요약해주세요.", config)
        assert summary == ""
        assert degraded is True


class TestSummarizeFallback:
    @pytest.mark.asyncio
    async def test_gemini_importerror_falls_back_to_textrank(self) -> None:
        config = _gemini_config()
        with patch(
            "backend.processor.shared.ai_summarizer._call_gemini",
            new=AsyncMock(side_effect=ImportError("google-generativeai not installed")),
        ):
            summary, degraded = await summarize(_SAMPLE_TEXT, "요약해주세요.", config)

        assert degraded is True
        assert isinstance(summary, str)

    @pytest.mark.asyncio
    async def test_openai_importerror_falls_back_to_textrank(self) -> None:
        config = _openai_config()
        with patch(
            "backend.processor.shared.ai_summarizer._call_openai",
            new=AsyncMock(side_effect=ImportError("openai not installed")),
        ):
            summary, degraded = await summarize(_SAMPLE_TEXT, "요약해주세요.", config)

        assert degraded is True
        assert isinstance(summary, str)

    @pytest.mark.asyncio
    async def test_provider_exception_falls_back_to_textrank(self) -> None:
        config = _gemini_config()
        with patch(
            "backend.processor.shared.ai_summarizer._call_gemini",
            new=AsyncMock(side_effect=RuntimeError("API down")),
        ):
            summary, degraded = await summarize(_SAMPLE_TEXT, "요약해주세요.", config)

        assert degraded is True
        assert isinstance(summary, str)

    @pytest.mark.asyncio
    async def test_gemini_success_returns_degraded_false(self) -> None:
        config = _gemini_config()
        with patch(
            "backend.processor.shared.ai_summarizer._call_gemini",
            new=AsyncMock(return_value="Gemini 요약 결과"),
        ):
            summary, degraded = await summarize(_SAMPLE_TEXT, "요약해주세요.", config)

        assert degraded is False
        assert summary == "Gemini 요약 결과"

    @pytest.mark.asyncio
    async def test_openai_success_returns_degraded_false(self) -> None:
        config = _openai_config()
        with patch(
            "backend.processor.shared.ai_summarizer._call_openai",
            new=AsyncMock(return_value="OpenAI 요약 결과"),
        ):
            summary, degraded = await summarize(_SAMPLE_TEXT, "요약해주세요.", config)

        assert degraded is False
        assert summary == "OpenAI 요약 결과"

    @pytest.mark.asyncio
    async def test_unknown_provider_falls_back_to_textrank(self) -> None:
        config = AIConfig(
            provider="unknown_provider",
            model="unknown",
            api_key=SecretStr(""),
            max_tokens=512,
            temperature=0.0,
            fallback_provider="textrank",
        )
        summary, degraded = await summarize(_SAMPLE_TEXT, "요약해주세요.", config)
        assert degraded is True
        assert isinstance(summary, str)


class TestTextrankSummary:
    def test_textrank_extracts_key_sentences(self) -> None:
        result = _textrank_summary(_SAMPLE_TEXT, sentences=5)
        # Result should be non-empty
        assert len(result) > 0
        # Result should be shorter than original (10 sentences -> 5)
        assert len(result) < len(_SAMPLE_TEXT)

    def test_textrank_empty_text_returns_empty(self) -> None:
        assert _textrank_summary("") == ""

    def test_textrank_whitespace_returns_empty(self) -> None:
        assert _textrank_summary("   ") == ""

    def test_textrank_short_text_returns_all_sentences(self) -> None:
        short = "첫 번째 문장입니다. 두 번째 문장입니다."
        result = _textrank_summary(short, sentences=5)
        assert "첫 번째 문장입니다" in result
        assert "두 번째 문장입니다" in result

    def test_textrank_returns_string(self) -> None:
        result = _textrank_summary(_SAMPLE_TEXT)
        assert isinstance(result, str)


def _make_google_mock() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Return (mock_google, mock_genai, mock_model) with proper linkage.

    `import google.generativeai as genai` resolves as:
    IMPORT_NAME google.generativeai → sys.modules['google']
    IMPORT_FROM generativeai        → sys.modules['google'].generativeai

    So mock_google.generativeai must equal mock_genai.
    """
    mock_genai = MagicMock()
    mock_google = MagicMock()
    mock_google.generativeai = mock_genai
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock()
    mock_genai.GenerativeModel.return_value = mock_model
    return mock_google, mock_genai, mock_model


class TestGeminiProvider:
    @pytest.mark.asyncio
    async def test_gemini_success_returns_text(self) -> None:
        config = _gemini_config()
        mock_google, mock_genai, mock_model = _make_google_mock()
        mock_response = MagicMock()
        mock_response.text = "Gemini 요약 결과"
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch.dict("sys.modules", {"google": mock_google, "google.generativeai": mock_genai}):
            result = await _call_gemini(_SAMPLE_TEXT, "요약해주세요.", config)

        assert result == "Gemini 요약 결과"

    @pytest.mark.asyncio
    async def test_gemini_exception_reraises(self) -> None:
        config = _gemini_config()
        mock_google, mock_genai, mock_model = _make_google_mock()
        mock_model.generate_content_async = AsyncMock(side_effect=RuntimeError("API down"))

        with patch.dict("sys.modules", {"google": mock_google, "google.generativeai": mock_genai}):
            with pytest.raises(RuntimeError, match="API down"):
                await _call_gemini(_SAMPLE_TEXT, "요약해주세요.", config)

    @pytest.mark.asyncio
    async def test_gemini_importerror_reraises(self) -> None:
        config = _gemini_config()
        with patch.dict("sys.modules", {"google": None, "google.generativeai": None}):
            with pytest.raises(ImportError):
                await _call_gemini(_SAMPLE_TEXT, "요약해주세요.", config)

    @pytest.mark.asyncio
    async def test_gemini_uses_api_key_from_config(self) -> None:
        config = _gemini_config()
        mock_google, mock_genai, mock_model = _make_google_mock()
        mock_response = MagicMock()
        mock_response.text = "결과"
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch.dict("sys.modules", {"google": mock_google, "google.generativeai": mock_genai}):
            await _call_gemini(_SAMPLE_TEXT, "prompt", config)

        mock_genai.configure.assert_called_once_with(api_key="test-key")


class TestOpenAIProvider:
    @pytest.mark.asyncio
    async def test_openai_success_returns_text(self) -> None:
        config = _openai_config()
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OpenAI 요약 결과"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_module.AsyncOpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            result = await _call_openai(_SAMPLE_TEXT, "요약해주세요.", config)

        assert result == "OpenAI 요약 결과"

    @pytest.mark.asyncio
    async def test_openai_exception_reraises(self) -> None:
        config = _openai_config()
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("OpenAI API down"))
        mock_openai_module.AsyncOpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            with pytest.raises(RuntimeError, match="OpenAI API down"):
                await _call_openai(_SAMPLE_TEXT, "요약해주세요.", config)

    @pytest.mark.asyncio
    async def test_openai_importerror_reraises(self) -> None:
        config = _openai_config()
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(ImportError):
                await _call_openai(_SAMPLE_TEXT, "요약해주세요.", config)

    @pytest.mark.asyncio
    async def test_openai_respects_model_name(self) -> None:
        config = _openai_config()
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "결과"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_module.AsyncOpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            await _call_openai(_SAMPLE_TEXT, "prompt", config)

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o-mini"


class TestSummarizeFallbackChain:
    @pytest.mark.asyncio
    async def test_all_providers_fail_returns_empty_string(self) -> None:
        """Lines 62-67: textrank fallback itself fails → return ("", True)."""
        config = _gemini_config()
        with (
            patch(
                "backend.processor.shared.ai_summarizer._call_gemini",
                new=AsyncMock(side_effect=RuntimeError("API down")),
            ),
            patch(
                "backend.processor.shared.ai_summarizer._textrank_summary",
                side_effect=RuntimeError("textrank failed"),
            ),
        ):
            summary, degraded = await summarize(_SAMPLE_TEXT, "요약해주세요.", config)

        assert summary == ""
        assert degraded is True

    @pytest.mark.asyncio
    async def test_gemini_fail_textrank_success(self) -> None:
        config = _gemini_config()
        with patch(
            "backend.processor.shared.ai_summarizer._call_gemini",
            new=AsyncMock(side_effect=RuntimeError("API down")),
        ):
            summary, degraded = await summarize(_SAMPLE_TEXT, "요약해주세요.", config)

        assert degraded is True
        assert isinstance(summary, str)

    @pytest.mark.asyncio
    async def test_openai_fail_textrank_success(self) -> None:
        config = _openai_config()
        with patch(
            "backend.processor.shared.ai_summarizer._call_openai",
            new=AsyncMock(side_effect=RuntimeError("API down")),
        ):
            summary, degraded = await summarize(_SAMPLE_TEXT, "요약해주세요.", config)

        assert degraded is True
        assert isinstance(summary, str)
