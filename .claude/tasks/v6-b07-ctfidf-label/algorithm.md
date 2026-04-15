# B-07: c-TF-IDF 클러스터 라벨링

> Branch: `feat/v6-ctfidf` | Agent: Algorithm | Track: B
> 의존: B-05
> Plan 참조: §B-07

## 배경

V5 클러스터 라벨은 대표 키워드(상위 1개)만. BERTopic 표준 c-TF-IDF로 다중 텀 라벨("삼성전자 · 실적 · HBM") 자동 생성.

## 목적

- 클러스터별 상위 5 텀 추출
- 인간 가독 라벨 + JSON 구조 terms 저장
- MMR 간단 버전으로 중복 텀 제거

## 사전 확인

- [ ] kiwi tokenizer 재사용 가능 확인 (V5 keyword_extractor와 공유)
- [ ] sklearn TfidfVectorizer 버전 (≥1.4, `tokenizer` deprecation 회피)

## DB 마이그레이션

### `backend/db/migrations/037_group_label.sql` (신규)

```sql
BEGIN;
ALTER TABLE news_group
    ADD COLUMN IF NOT EXISTS auto_label TEXT,
    ADD COLUMN IF NOT EXISTS auto_label_terms JSONB;
ALTER TABLE news_group_shadow
    ADD COLUMN IF NOT EXISTS auto_label TEXT,
    ADD COLUMN IF NOT EXISTS auto_label_terms JSONB;
COMMIT;
```

- [ ] runner 등록

## 구현

### `backend/processor/shared/v6/ctfidf.py` (수정, stub 덮어씀)

```python
class CTfIdfLabeler:
    def __init__(self, ngram_range=(1, 2), top_n=5, min_df=1, max_df=0.85):
        self.ngram_range = ngram_range
        self.top_n = top_n
        self.min_df = min_df
        self.max_df = max_df

    def fit_label(self, clusters: dict[str, list[Article]]) -> dict[str, LabelResult]:
        """Group articles per cluster → concat → TF-IDF → top terms."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        cluster_ids = list(clusters.keys())
        docs = [_concat_cluster_docs(clusters[cid]) for cid in cluster_ids]
        vec = TfidfVectorizer(
            ngram_range=self.ngram_range,
            max_df=self.max_df,
            min_df=self.min_df,
            tokenizer=_kiwi_tokenize,
            token_pattern=None,
        )
        tfidf = vec.fit_transform(docs)
        vocab = np.array(vec.get_feature_names_out())
        results = {}
        for i, cid in enumerate(cluster_ids):
            row = tfidf[i].toarray().flatten()
            top_idx = row.argsort()[::-1][: self.top_n * 3]
            top_terms = [(vocab[j], float(row[j])) for j in top_idx if row[j] > 0]
            deduped = _mmr_dedupe(top_terms, k=self.top_n)
            results[cid] = LabelResult(
                label=" · ".join(t for t, _ in deduped),
                terms=[{"term": t, "score": s} for t, s in deduped],
            )
        return results
```

- [ ] `_mmr_dedupe`: Jaccard 기반 중복 텀 제거 (한 텀이 다른 텀의 서브스트링 또는 Jaccard>0.5 시 드랍)
- [ ] `_kiwi_tokenize(text)`: V5 토크나이저 재사용, NNG/NNP/SL 품사만

### `backend/processor/pipeline_v6.py` (수정)

- [ ] 클러스터링 직후 `CTfIdfLabeler.fit_label` 호출
- [ ] 결과를 `news_group.auto_label`, `auto_label_terms` 저장

## 테스트

### `tests/test_ctfidf.py` (신규)

- [ ] `test_single_cluster_top_terms`: 고정 픽스처 → 예상 상위 텀
- [ ] `test_mmr_dedupe`: "인공지능" + "인공지능 모델" → 하나만 유지
- [ ] `test_ngram_range_bigram`: bigram 추출 검증
- [ ] `test_stopword_filter`: "것", "수" 등 제거
- [ ] `test_empty_cluster_handled`: 빈 클러스터 → empty label

## 메트릭 목표

- 수동 리뷰 100건 라벨 적절성 ≥ 85% (C-03 연계)
- 상위 5 텀 중복 < 2개

## Prometheus

- [ ] `ctfidf_label_duration_seconds` histogram
- [ ] `ctfidf_clusters_labeled_total` counter

## 롤백

- `news_group.auto_label` NULL 허용, 기존 `representative_keyword` 사용

## 완료 조건

- [ ] pytest 통과
- [ ] 섀도우 데이터에서 실제 라벨 스팟체크
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: c-TF-IDF 클러스터 라벨링 (V6 B-07)"`
