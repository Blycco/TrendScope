# B-05 (Algorithm): HDBSCAN V6 + 동적 Outlier σ

> Branch: `feat/v6-hdbscan` | Agent: Algorithm + Backend | Track: B
> 의존: B-04
> Plan 참조: §B-05

## 배경

V5 HDBSCAN `min_cluster_size=2` 하드코드, outlier σ=1.0 고정. V6는 UMAP 후 저차원 공간 + FAISS sparse distance 기반 + admin 노출 + 동적 σ.

## 목적

- HDBSCAN 파라미터 admin 노출 (5종)
- Sparse precomputed distance 입력
- Outlier σ 분포 기반 동적 계산 (0.5~1.5)
- Noise 재분류: 4-요소 composite (B-06) 으로 기존 클러스터 재할당 시도

## 사전 확인

- [ ] `hdbscan` 라이브러리 precomputed sparse 지원 버전 확인 (≥0.8.33)
- [ ] V5 `semantic_clusterer.py` outlier refine 로직 현행 파악

## 구현

### `backend/processor/shared/v6/clusterer.py` (수정, stub 덮어씀)

```python
@dataclass
class HdbscanConfig:
    min_cluster_size: int = 3
    min_samples: int = 2
    cluster_selection_method: str = "eom"  # "eom"|"leaf"
    cluster_selection_epsilon: float = 0.0
    outlier_sigma_min: float = 0.5
    outlier_sigma_max: float = 1.5


async def cluster_v6(
    articles: list[Article],
    embeddings: np.ndarray,       # UMAP 후 저차원
    sparse_dist: scipy.sparse.csr_matrix,
    config: HdbscanConfig,
) -> list[Cluster]:
    import hdbscan
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=config.min_cluster_size,
        min_samples=config.min_samples,
        cluster_selection_method=config.cluster_selection_method,
        cluster_selection_epsilon=config.cluster_selection_epsilon,
        metric="precomputed",
        core_dist_n_jobs=1,
    )
    labels = clusterer.fit_predict(sparse_dist.toarray())
    clusters = _group_by_label(articles, embeddings, labels)
    clusters = _dynamic_outlier_refine(clusters, config)
    return clusters
```

- [ ] `_dynamic_outlier_refine`:
  - 클러스터별 `intra_sim` 분포 계산
  - σ = `clip(np.std(intra_sim), config.outlier_sigma_min, config.outlier_sigma_max)`
  - mean - σ·std 이하 기사 eviction → 단독 클러스터 또는 noise
- [ ] noise(-1) 재분류 (B-06 의존): FAISS 이웃 + 4요소 composite 최대값 클러스터에 재할당
- [ ] 결정론: `np.random.seed(42)` + single-threaded

### admin 설정

- [ ] `v6.hdbscan.min_cluster_size` (3)
- [ ] `v6.hdbscan.min_samples` (2)
- [ ] `v6.hdbscan.cluster_selection_method` ("eom")
- [ ] `v6.hdbscan.cluster_selection_epsilon` (0.0)
- [ ] `v6.hdbscan.outlier_sigma_min` (0.5)
- [ ] `v6.hdbscan.outlier_sigma_max` (1.5)

## 테스트

### `tests/test_clusterer_v6.py` (신규)

- [ ] `test_hdbscan_runs_on_sparse`: (20, 20) sparse → labels 반환
- [ ] `test_min_cluster_size_3`: 2건 집단 → noise 처리
- [ ] `test_dynamic_sigma_clipping`: std 값 범위 밖 → clip
- [ ] `test_outlier_evicted_from_loose_cluster`: mixed cluster → low-sim 기사 배제
- [ ] `test_runtime_config_reload`: admin 변경 반영
- [ ] `test_deterministic`: 동일 입력 → 동일 라벨

## 메트릭 목표

- silhouette V5 대비 +0.05
- outlier_ratio ≤ V5 × 1.05

## Prometheus

- [ ] `cluster_v6_duration_seconds` histogram
- [ ] `cluster_v6_clusters_total` gauge
- [ ] `cluster_v6_outlier_ratio` gauge
- [ ] `cluster_v6_sigma_used` histogram

## 롤백

- `pipeline.version="v5"`

## 완료 조건

- [ ] pytest 통과
- [ ] admin UI 실시간 변경 동작 (backend.md 참조)
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: HDBSCAN V6 + 동적 outlier σ + admin 노출 (V6 B-05)"`
