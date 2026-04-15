# C-01 (Algorithm): 메트릭 프레임워크

> Branch: `feat/v6-metrics` | Agent: Algorithm + Backend | Track: C
> 의존: B-01
> Plan 참조: §C-01

## 배경

V5/V6 정량 비교 가능한 메트릭 수집. silhouette, DBCV, c-TF-IDF NPMI coherence, topic diversity, outlier_ratio 일배치 저장.

## 목적

- 클러스터 품질 메트릭 계산기
- 일별 `cluster_metrics_daily` 테이블 적재
- Prometheus gauge 실시간 노출

## 구현

### `backend/processor/shared/v6/metrics.py` (수정, stub 덮어씀)

```python
@dataclass
class ClusterMetrics:
    silhouette: float
    dbcv: float
    coherence_npmi: float
    topic_diversity: float
    outlier_ratio: float
    n_clusters: int
    p50_cluster_size: int
    intra_sim_mean: float
    intra_sim_std: float


def compute_metrics(
    articles: list[Article],
    embeddings: np.ndarray,
    labels: np.ndarray,
    topic_terms: dict[str, list[str]],
) -> ClusterMetrics:
    from sklearn.metrics import silhouette_score
    non_noise = labels != -1
    sil = silhouette_score(embeddings[non_noise], labels[non_noise], metric="cosine") \
        if non_noise.sum() > 1 else 0.0
    dbcv = _dbcv(embeddings, labels)                       # hdbscan.validity_index
    npmi = _npmi_coherence(topic_terms, articles)          # gensim CoherenceModel
    diversity = _topic_diversity(topic_terms)               # 고유 텀 / 전체 텀
    outlier = float((labels == -1).sum()) / max(len(labels), 1)
    sizes = [int((labels == lb).sum()) for lb in set(labels) if lb != -1]
    return ClusterMetrics(
        silhouette=sil, dbcv=dbcv, coherence_npmi=npmi,
        topic_diversity=diversity, outlier_ratio=outlier,
        n_clusters=len(sizes),
        p50_cluster_size=int(np.median(sizes)) if sizes else 0,
        intra_sim_mean=..., intra_sim_std=...,
    )
```

- [ ] `_dbcv`: `hdbscan.validity.validity_index(embeddings, labels)` 래핑
- [ ] `_npmi_coherence`: gensim `CoherenceModel(topics=topic_terms, texts=tokenized_corpus, coherence='c_npmi')`
- [ ] `_topic_diversity`: `|unique_top_terms| / sum(|top_terms_per_cluster|)`

### `backend/jobs/cluster_metrics_job.py` (신규)

- [ ] CLI: `python -m backend.jobs.cluster_metrics_job --date YYYY-MM-DD --version v5|v6`
- [ ] 해당 일자 기사·클러스터·임베딩 로드 → `compute_metrics` → `cluster_metrics_daily` UPSERT
- [ ] cron: 일 1회 02:00 KST (V5 + V6 각각)

## 테스트

### `tests/test_metrics_v6.py` (신규)

- [ ] `test_silhouette_computed`
- [ ] `test_npmi_stability`: 빈 토픽 → 0.0 반환
- [ ] `test_outlier_ratio`
- [ ] `test_diversity_range_0_1`
- [ ] `test_metrics_job_upsert`

## Prometheus

- [ ] `v6_silhouette`, `v5_silhouette` gauge
- [ ] `v6_coherence_npmi`, `v5_coherence_npmi` gauge
- [ ] `v6_outlier_ratio`, `v5_outlier_ratio` gauge
- [ ] `v6_topic_diversity` gauge

## 완료 조건

- [ ] pytest 통과
- [ ] 잡 실행 후 테이블 레코드 확인
- [ ] Prometheus 노출
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: 클러스터 메트릭 프레임워크 (V6 C-01)"`
