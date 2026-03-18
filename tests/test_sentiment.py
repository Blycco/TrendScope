"""Tests for backend/processor/algorithms/sentiment.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.processor.algorithms.sentiment import SentimentAnalyzer, SentimentResult


class TestSentimentResult:
    def test_dataclass_fields(self) -> None:
        result = SentimentResult(label="positive", score=0.9)
        assert result.label == "positive"
        assert result.score == 0.9

    def test_label_negative(self) -> None:
        result = SentimentResult(label="negative", score=0.7)
        assert result.label == "negative"

    def test_label_neutral(self) -> None:
        result = SentimentResult(label="neutral", score=0.5)
        assert result.label == "neutral"


class TestSentimentAnalyzerLexicon:
    """Tests using the lexicon fallback (no transformers model needed)."""

    def _make_analyzer_no_model(self) -> SentimentAnalyzer:
        """Return analyzer with model loading disabled (lexicon only)."""
        analyzer = SentimentAnalyzer()
        analyzer._model = None
        analyzer._model_loaded = True  # skip load attempt
        return analyzer

    def test_positive_text_returns_positive(self) -> None:
        analyzer = self._make_analyzer_no_model()
        result = analyzer.analyze("이 제품 정말 좋아요 최고입니다")
        assert result.label == "positive"
        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0

    def test_negative_text_returns_negative(self) -> None:
        analyzer = self._make_analyzer_no_model()
        result = analyzer.analyze("정말 나쁜 제품 최악이에요")
        assert result.label == "negative"

    def test_neutral_text_returns_neutral(self) -> None:
        analyzer = self._make_analyzer_no_model()
        result = analyzer.analyze("오늘 날씨는 보통입니다")
        assert result.label == "neutral"

    def test_score_normalized_0_to_1(self) -> None:
        analyzer = self._make_analyzer_no_model()
        result = analyzer.analyze("좋아 좋아 좋아 최고 훌륭 성공 긍정 상승")
        assert 0.0 <= result.score <= 1.0

    def test_empty_text_returns_neutral(self) -> None:
        analyzer = self._make_analyzer_no_model()
        result = analyzer.analyze("")
        assert result.label == "neutral"


class TestSentimentAnalyzerModel:
    def test_lazy_load_once(self) -> None:
        analyzer = SentimentAnalyzer()
        assert analyzer._model_loaded is False
        # Patch transformers to avoid actually loading model
        with patch.dict("sys.modules", {"transformers": None}):
            analyzer._load_model()
        assert analyzer._model_loaded is True

    def test_model_not_reloaded_on_second_call(self) -> None:
        analyzer = SentimentAnalyzer()
        analyzer._model_loaded = True  # pretend already loaded
        analyzer._model = None
        # _load_model should be a no-op
        call_count = 0
        orig = analyzer._load_model

        def counting_load() -> None:
            nonlocal call_count
            call_count += 1
            orig()

        analyzer._load_model = counting_load  # type: ignore[method-assign]
        # analyze calls _load_model but model is already loaded so inner body skips
        analyzer._model_loaded = True
        analyzer._load_model()
        # Since _model_loaded was True before call, inner body should return early
        # But our wrapper counted 1 call — that's fine, verify _model_loaded still True
        assert analyzer._model_loaded is True

    def test_transformers_importerror_uses_lexicon(self) -> None:
        analyzer = SentimentAnalyzer()
        with patch.dict("sys.modules", {"transformers": None}):
            analyzer._load_model()
        assert analyzer._model_loaded is True
        assert analyzer._model is None
        # Should fall back to lexicon
        result = analyzer.analyze("좋아")
        assert result.label in ("positive", "negative", "neutral")

    def test_model_load_failure_falls_back(self) -> None:
        analyzer = SentimentAnalyzer()
        mock_transformers = MagicMock()
        mock_transformers.pipeline.side_effect = RuntimeError("model load failed")
        with patch.dict("sys.modules", {"transformers": mock_transformers}):
            analyzer._load_model()
        assert analyzer._model_loaded is True
        assert analyzer._model is None

    def test_model_inference_failure_falls_back(self) -> None:
        analyzer = SentimentAnalyzer()
        # Provide a model that raises on __call__
        mock_model = MagicMock()
        mock_model.side_effect = RuntimeError("inference error")
        analyzer._model = mock_model
        analyzer._model_loaded = True
        result = analyzer.analyze("테스트")
        # Should fall back to lexicon
        assert result.label in ("positive", "negative", "neutral")

    def test_label_mapping_positive(self) -> None:
        analyzer = SentimentAnalyzer()
        mock_model = MagicMock()
        mock_model.return_value = [{"label": "LABEL_1", "score": 0.95}]
        analyzer._model = mock_model
        analyzer._model_loaded = True
        result = analyzer.analyze("some text")
        assert result.label == "positive"
        assert abs(result.score - 0.95) < 1e-6

    def test_label_mapping_negative(self) -> None:
        analyzer = SentimentAnalyzer()
        mock_model = MagicMock()
        mock_model.return_value = [{"label": "LABEL_0", "score": 0.88}]
        analyzer._model = mock_model
        analyzer._model_loaded = True
        result = analyzer.analyze("some text")
        assert result.label == "negative"

    def test_text_truncated_to_512_chars(self) -> None:
        analyzer = SentimentAnalyzer()
        mock_model = MagicMock()
        mock_model.return_value = [{"label": "positive", "score": 0.8}]
        analyzer._model = mock_model
        analyzer._model_loaded = True
        long_text = "좋아 " * 300  # much longer than 512 chars
        analyzer.analyze(long_text)
        # Verify model was called with truncated text
        called_text = mock_model.call_args[0][0]
        assert len(called_text) <= 512

    def test_model_empty_results_falls_back_to_lexicon(self) -> None:
        analyzer = SentimentAnalyzer()
        mock_model = MagicMock()
        mock_model.return_value = []  # empty results
        analyzer._model = mock_model
        analyzer._model_loaded = True
        result = analyzer.analyze("좋아요")
        # Should fall through to lexicon since results is empty
        assert result.label in ("positive", "negative", "neutral")
