"""Keyword extraction using soynlp + TF-IDF x BM25 scoring.

Pipeline spec: KeywordExtractor (soynlp + TF-IDF × BM25)
Falls back to simple regex-based extraction when soynlp is unavailable.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

# --- Configuration ---
_MIN_KEYWORD_LEN: int = 2
_MAX_KEYWORD_LEN: int = 30
_DEFAULT_TOP_K: int = 10
_BM25_K1: float = 1.5
_BM25_B: float = 0.75
_BIGRAM_MIN_FREQ: int = 2
_BIGRAM_SCORE_WEIGHT: float = 0.5

# Korean noun-like pattern (2+ syllable sequences)
_KOREAN_NOUN_PATTERN: re.Pattern[str] = re.compile(r"[가-힣]{2,}")
# English word pattern (2+ chars, no stop words filtered later)
_ENGLISH_WORD_PATTERN: re.Pattern[str] = re.compile(r"[a-zA-Z]{2,}")

# Minimal English stop words
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "the",
        "is",
        "at",
        "which",
        "on",
        "and",
        "or",
        "but",
        "in",
        "to",
        "for",
        "of",
        "with",
        "as",
        "by",
        "an",
        "be",
        "this",
        "that",
        "it",
        "are",
        "was",
        "were",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "from",
        "not",
        "no",
        "if",
        "then",
        "than",
        "so",
        "up",
        "out",
        "about",
        "into",
        "over",
        "after",
        "also",
        "its",
        "his",
        "her",
    }
)

# Korean stop words (common particles / functional words / news boilerplate)
_KOREAN_STOP_WORDS: frozenset[str] = frozenset(
    {
        # 기존 — 조사/어미/접속사
        "것이",
        "하는",
        "있는",
        "하고",
        "에서",
        "으로",
        "이다",
        "했다",
        "되는",
        "하며",
        "그리고",
        "또한",
        "이를",
        "통해",
        "이번",
        "대한",
        "위해",
        "관련",
        "따르면",
        "밝혔다",
        "전했다",
        # 뉴스 빈출 무의미 단어
        "것으로",
        "지난",
        "올해",
        "오늘",
        "내년",
        "최근",
        "현재",
        "이후",
        "가운데",
        "사이",
        "가량",
        "정도",
        "이상",
        "미만",
        "대비",
        "전년",
        "분기",
        "한편",
        "이날",
        # 매체/기자 관련
        "기자",
        "특파원",
        "뉴스",
        "연합뉴스",
        "한겨레",
        "매일경제",
        "조선일보",
        "중앙일보",
        "동아일보",
        "한국경제",
        "머니투데이",
        "아시아경제",
        "헤럴드경제",
    }
)

# POS tags to keep from kiwipiepy (nouns + English)
_NOUN_POS_TAGS: frozenset[str] = frozenset({"NNG", "NNP", "NNB", "SL"})

# --- Kiwi singleton ---
_kiwi_instance: object | None = None
_kiwi_loaded: bool = False


def _get_kiwi() -> object | None:
    """Lazy-load kiwipiepy Kiwi instance. Returns None if unavailable."""
    global _kiwi_instance, _kiwi_loaded
    if not _kiwi_loaded:
        try:
            from kiwipiepy import Kiwi  # type: ignore[import-untyped]

            _kiwi_instance = Kiwi()
            _kiwi_loaded = True
            logger.info("kiwi_loaded")
        except ImportError:
            _kiwi_loaded = True
            logger.info("kiwi_unavailable_fallback")
        except Exception as exc:
            _kiwi_loaded = True
            logger.warning("kiwi_load_failed", error=str(exc))
    return _kiwi_instance


@dataclass
class Keyword:
    """Extracted keyword with score."""

    term: str
    score: float
    frequency: int = 0


@dataclass
class CorpusStats:
    """Corpus-level statistics for IDF / BM25 computation."""

    doc_count: int = 0
    avg_doc_length: float = 0.0
    doc_freq: Counter[str] = field(default_factory=Counter)

    def update(self, terms: list[str], doc_length: int) -> None:
        """Update corpus stats with a new document's terms."""
        self.doc_count += 1
        self.avg_doc_length = (
            self.avg_doc_length * (self.doc_count - 1) + doc_length
        ) / self.doc_count
        unique_terms = set(terms)
        for term in unique_terms:
            self.doc_freq[term] += 1


# Module-level corpus stats (accumulates across processing batches)
_corpus_stats: CorpusStats = CorpusStats()


def get_corpus_stats() -> CorpusStats:
    """Get the current corpus statistics."""
    return _corpus_stats


def reset_corpus_stats() -> None:
    """Reset corpus statistics (e.g., on daily rotation)."""
    global _corpus_stats
    _corpus_stats = CorpusStats()
    logger.info("corpus_stats_reset")


def _tokenize_simple(text: str) -> list[str]:
    """Simple tokenization: extract Korean nouns + English words."""
    korean_tokens = _KOREAN_NOUN_PATTERN.findall(text)
    english_tokens = [w.lower() for w in _ENGLISH_WORD_PATTERN.findall(text)]
    tokens = korean_tokens + english_tokens
    return [
        t
        for t in tokens
        if _MIN_KEYWORD_LEN <= len(t) <= _MAX_KEYWORD_LEN
        and t.lower() not in _STOP_WORDS
        and t not in _KOREAN_STOP_WORDS
    ]


def _try_kiwi_tokenize(text: str) -> list[str] | None:
    """Attempt kiwipiepy POS-based tokenization. Returns None if unavailable."""
    kiwi = _get_kiwi()
    if kiwi is None:
        return None
    try:
        result = kiwi.tokenize(text)
        tokens = [
            token.form
            for token in result
            if token.tag in _NOUN_POS_TAGS
            and _MIN_KEYWORD_LEN <= len(token.form) <= _MAX_KEYWORD_LEN
        ]
        return [t for t in tokens if t.lower() not in _STOP_WORDS and t not in _KOREAN_STOP_WORDS]
    except Exception as exc:
        logger.warning("kiwi_tokenize_failed", error=str(exc))
        return None


def _try_soynlp_tokenize(text: str) -> list[str] | None:
    """Attempt soynlp-based tokenization. Returns None if unavailable."""
    try:
        from soynlp.tokenizer import LTokenizer  # type: ignore[import-untyped]

        tokenizer = LTokenizer()
        tokens = tokenizer.tokenize(text)
        return [
            t
            for t in tokens
            if _MIN_KEYWORD_LEN <= len(t) <= _MAX_KEYWORD_LEN
            and t.lower() not in _STOP_WORDS
            and t not in _KOREAN_STOP_WORDS
        ]
    except ImportError:
        return None
    except Exception as exc:
        logger.warning("soynlp_tokenize_failed", error=str(exc))
        return None


def _compute_tf(term: str, term_counts: Counter[str], doc_length: int) -> float:
    """Raw term frequency normalized by document length."""
    if doc_length == 0:
        return 0.0
    return term_counts[term] / doc_length


def _compute_idf(term: str, corpus: CorpusStats) -> float:
    """Inverse document frequency with smoothing."""
    if corpus.doc_count == 0:
        return 1.0
    df = corpus.doc_freq.get(term, 0)
    return math.log((corpus.doc_count - df + 0.5) / (df + 0.5) + 1)


def _compute_bm25(
    term: str,
    term_counts: Counter[str],
    doc_length: int,
    corpus: CorpusStats,
) -> float:
    """BM25 score for a term in a document."""
    tf = term_counts[term]
    idf = _compute_idf(term, corpus)
    avg_dl = corpus.avg_doc_length if corpus.avg_doc_length > 0 else doc_length
    numerator = tf * (_BM25_K1 + 1)
    denominator = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * doc_length / avg_dl)
    return idf * numerator / denominator if denominator > 0 else 0.0


def _extract_bigrams(
    tokens: list[str],
    *,
    min_freq: int = _BIGRAM_MIN_FREQ,
) -> Counter[str]:
    """Extract bigrams (adjacent token pairs) from token list.

    Args:
        tokens: List of tokens.
        min_freq: Minimum frequency to include a bigram.

    Returns:
        Counter of bigram strings with frequency >= min_freq.
    """
    bigrams: Counter[str] = Counter()
    for i in range(len(tokens) - 1):
        bigram = f"{tokens[i]}_{tokens[i + 1]}"
        bigrams[bigram] += 1
    return Counter({b: c for b, c in bigrams.items() if c >= min_freq})


async def reload_stopword_cache() -> None:
    """어드민 변경 후 불용어 Redis 캐시 무효화."""
    from backend.processor.shared.config_loader import invalidate_cache

    await invalidate_cache("stopwords")


def _filter_tokens(
    tokens: list[str],
    *,
    stop_words_ko: frozenset[str] | None = None,
    stop_words_en: frozenset[str] | None = None,
) -> list[str]:
    """Merge DB-loaded and hardcoded stop words, then filter tokens."""
    ko_set = (stop_words_ko | _KOREAN_STOP_WORDS) if stop_words_ko else _KOREAN_STOP_WORDS
    en_set = (stop_words_en | _STOP_WORDS) if stop_words_en else _STOP_WORDS
    return [t for t in tokens if t not in ko_set and t.lower() not in en_set]


def extract_keywords(
    text: str = "",
    *,
    title: str = "",
    body: str = "",
    top_k: int = _DEFAULT_TOP_K,
    title_boost: float = 2.0,
    body_max_chars: int = 500,
    use_soynlp: bool = True,
    use_bigrams: bool = True,
    corpus: CorpusStats | None = None,
    stop_words_ko: frozenset[str] | None = None,
    stop_words_en: frozenset[str] | None = None,
) -> list[Keyword]:
    """Extract top-k keywords using TF-IDF x BM25 scoring.

    Accepts either a single ``text`` string (backward compat) or separate
    ``title`` + ``body`` strings.  When title/body are provided, title tokens
    are boosted by ``title_boost`` (frequency multiplied before scoring).

    Args:
        text: Combined input text — used when title/body not given.
        title: Article title (receives title_boost on token frequency).
        body: Article body — truncated to body_max_chars before tokenizing.
        top_k: Number of keywords to return.
        title_boost: Multiplier applied to title token frequencies.
        body_max_chars: Maximum characters to read from body.
        use_soynlp: Attempt soynlp tokenization first.
        use_bigrams: Include co-occurrence bigrams in keywords.
        corpus: Corpus stats for IDF computation. Uses module-level stats if None.
        stop_words_ko: Additional Korean stop words loaded from DB.
        stop_words_en: Additional English stop words loaded from DB.

    Returns:
        List of Keyword objects sorted by score descending.
    """
    # Resolve input: title+body mode or legacy text mode
    use_split = bool(title or body)

    if use_split:
        title_text = title or ""
        body_text = (body or "")[:body_max_chars]

        if not title_text.strip() and not body_text.strip():
            return []

        # Tokenize title and body separately
        def _tokenize(t: str) -> list[str]:
            toks: list[str] | None = _try_kiwi_tokenize(t)
            if toks is None and use_soynlp:
                toks = _try_soynlp_tokenize(t)
            if toks is None:
                toks = _tokenize_simple(t)
            return _filter_tokens(toks, stop_words_ko=stop_words_ko, stop_words_en=stop_words_en)

        title_tokens = _tokenize(title_text)
        body_tokens = _tokenize(body_text)

        # Build combined token list: title tokens appear with boosted frequency
        title_counter = Counter(title_tokens)
        body_counter = Counter(body_tokens)
        # Merge: title token count × title_boost + body count
        merged: Counter[str] = Counter()
        for term, cnt in title_counter.items():
            merged[term] += int(cnt * title_boost)
        for term, cnt in body_counter.items():
            merged[term] += cnt

        tokens = list(merged.elements())
    else:
        raw = text or ""
        if not raw.strip():
            return []

        toks: list[str] | None = _try_kiwi_tokenize(raw)
        if toks is None and use_soynlp:
            toks = _try_soynlp_tokenize(raw)
        if toks is None:
            toks = _tokenize_simple(raw)
        tokens = _filter_tokens(toks, stop_words_ko=stop_words_ko, stop_words_en=stop_words_en)
        merged = Counter(tokens)

    if not tokens:
        return []

    stats = corpus if corpus is not None else _corpus_stats
    term_counts = merged if use_split else Counter(tokens)
    doc_length = len(tokens)

    # Update corpus stats
    stats.update(tokens, doc_length)

    # Score each unique term: TF-IDF × BM25
    scored: list[Keyword] = []
    unigram_scores: dict[str, float] = {}
    for term, freq in term_counts.items():
        tf_idf = _compute_tf(term, term_counts, doc_length) * _compute_idf(term, stats)
        bm25 = _compute_bm25(term, term_counts, doc_length, stats)
        combined = tf_idf * bm25
        unigram_scores[term] = combined
        scored.append(Keyword(term=term, score=combined, frequency=freq))

    # Add bigrams (co-occurrence patterns)
    if use_bigrams and len(tokens) > 1:
        bigram_counts = _extract_bigrams(tokens)
        for bigram, freq in bigram_counts.items():
            parts = bigram.split("_", 1)
            avg_score = sum(unigram_scores.get(p, 0.0) for p in parts) / len(parts)
            bigram_score = avg_score * _BIGRAM_SCORE_WEIGHT
            scored.append(Keyword(term=bigram, score=bigram_score, frequency=freq))

    scored.sort(key=lambda kw: kw.score, reverse=True)
    return scored[:top_k]
