# B-08: KeyBERT + PMI/log-likelihood Collocation

> Branch: `feat/v6-keybert` | Agent: Algorithm | Track: B
> 의존: B-01 (embedder 재사용은 B-02)
> Plan 참조: §B-08

## 배경

V4 키워드는 BM25 k1/b 하드코드 + bigram min_freq=2. V5 KE로 승격: KeyBERT(의미 유사도) + PMI/LL(통계 collocation) + trigram.

## 목적

- KeyBERT 통합 (KoE5 임베더 재사용)
- PMI (Pointwise Mutual Information) + Dunning log-likelihood ratio
- trigram 지원
- V4 BM25/bigram 점수와 선형 결합 `0.6·keybert + 0.4·bm25_bigram`

## 사전 확인

- [ ] 현행 `keyword_extractor.py` V4 구현 완전 파악
- [ ] 기존 Redis 키워드 빈도 카운터 구조 확인
- [ ] kiwi POS 태그 필터 (NNG/NNP/NNB/SL) 유지

## 신규 모듈

### `backend/processor/shared/v6/keyword_extractor.py` (수정, stub 덮어씀)

```python
@dataclass
class KeywordV6Config:
    use_keybert: bool = True
    keybert_weight: float = 0.6
    bm25_weight: float = 0.4
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    bigram_min_freq: int = 2
    trigram_enabled: bool = True
    pmi_min: float = 3.0
    ll_min: float = 10.8
    top_k: int = 10
    mmr_diversity: float = 0.5


async def extract_keywords_v6(
    article: Article,
    config: KeywordV6Config,
    corpus_stats: CorpusStats,
) -> list[Keyword]:
    tokens = _kiwi_tokenize_pos(article.normalized_body)  # NNG/NNP/...
    # 1) unigram/bigram/trigram 후보
    candidates = _build_ngram_candidates(tokens, config)
    # 2) PMI/LL 필터
    candidates = _filter_by_pmi_ll(candidates, corpus_stats, config)
    # 3) BM25 + bigram_min_freq V4 점수
    bm25_scores = _compute_bm25(article, candidates, config)
    # 4) KeyBERT 점수 (use_keybert=True)
    if config.use_keybert:
        keybert_scores = _compute_keybert(article, candidates, config)
    else:
        keybert_scores = {c: 0.0 for c in candidates}
    # 5) 선형 결합
    merged = {
        c: config.keybert_weight * keybert_scores[c]
           + config.bm25_weight * bm25_scores[c]
        for c in candidates
    }
    # 6) MMR
    return _mmr_select(merged, article_embedding, config.mmr_diversity, config.top_k)
```

- [ ] `_compute_pmi(bigram_count, w1_count, w2_count, total)`:
  `log2( P(w1,w2) / (P(w1)·P(w2)) )`
- [ ] `_compute_ll(obs, exp)`: Dunning log-likelihood, 저빈도 안정
- [ ] Redis corpus stats: `kw_stats:unigram:{word}`, `kw_stats:bigram:{w1}:{w2}`, TTL 24h rolling
- [ ] KeyBERT 호출: `KeyBERT(model=get_embedder()).extract_keywords(doc, candidates=..., top_n=..., mmr=True, diversity=config.mmr_diversity)`

### `backend/processor/stages/keywords.py` (수정)

- [ ] V6 분기: `config.v6.kw.use_keybert` True 시 `extract_keywords_v6`, 아니면 V4

### admin 설정

```
v6.kw.use_keybert (bool, true)
v6.kw.keybert_weight (float, 0.6)
v6.kw.bm25_weight (float, 0.4)
v6.kw.bm25_k1 (float, 1.5)  # V5 하드코드 admin 승격
v6.kw.bm25_b (float, 0.75)
v6.kw.bigram_min_freq (int, 2)
v6.kw.trigram_enabled (bool, true)
v6.kw.pmi_min (float, 3.0)
v6.kw.ll_min (float, 10.8)
v6.kw.top_k (int, 10)
v6.kw.mmr_diversity (float, 0.5)
```

## 의존성

- [ ] `requirements/processor.txt`: `keybert>=0.8.0`

## 테스트

### `tests/test_keyword_v6.py` (신규)

- [ ] `test_unigram_extraction`
- [ ] `test_bigram_pmi_above_threshold`: "인공지능 모델" PMI 높음 → 포함
- [ ] `test_bigram_below_threshold_dropped`: 임의 조합 PMI 낮음 → 제외
- [ ] `test_trigram_enabled_disabled`
- [ ] `test_ll_ratio_handles_low_freq`: 희귀 단어 안정
- [ ] `test_keybert_disabled_equivalent_to_v4`: use_keybert=False → V4 동치
- [ ] `test_mmr_reduces_redundancy`

## 메트릭 목표

- 키워드 NPMI coherence ≥ V4 대비 +0.05
- collocation 정밀도(수동 샘플) ≥ 90%

## Prometheus

- [ ] `keyword_v6_duration_seconds` histogram
- [ ] `keyword_v6_mode_total{mode="keybert|v4"}` counter

## 롤백

- `v6.kw.use_keybert=False` → V4 BM25+bigram만
- `pipeline.version="v5"`

## 완료 조건

- [ ] pytest 통과
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: KeyBERT + PMI/LL 키워드 추출 V5 (V6 B-08)"`
