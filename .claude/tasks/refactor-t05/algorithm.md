# T-05: 클러스터링 알고리즘 config_loader 연동
> Branch: fix/algorithm-tuning | Agent: Algorithm
> 의존성: T-01 완료 후 착수 (config_loader, admin_settings 시드 필요)

## semantic_clusterer.py

**파일:** `backend/processor/shared/semantic_clusterer.py`

현재 하드코딩 상수 (L19-28):
```
_COSINE_WEIGHT = 0.50
_JACCARD_WEIGHT = 0.25
_TEMPORAL_WEIGHT = 0.15
_SOURCE_WEIGHT = 0.10
_JACCARD_EARLY_FILTER = 0.10
_DEFAULT_CLUSTER_THRESHOLD = 0.55
_OUTLIER_SIGMA = 1.0
```

- [x] 모든 상수를 `config_loader.get_setting("cluster.*", default)` 로 대체
  - `_COSINE_WEIGHT` → `get_setting("cluster.cosine_weight", 0.35)`
  - `_JACCARD_WEIGHT` → `get_setting("cluster.jaccard_weight", 0.40)`
  - `_TEMPORAL_WEIGHT` → `get_setting("cluster.temporal_weight", 0.05)`
  - `_SOURCE_WEIGHT` → `get_setting("cluster.source_weight", 0.20)`
  - `_JACCARD_EARLY_FILTER` → `get_setting("cluster.jaccard_early_filter", 0.25)`
  - `_DEFAULT_CLUSTER_THRESHOLD` → `get_setting("cluster.threshold", 0.65)`
  - `_OUTLIER_SIGMA` → `get_setting("cluster.outlier_sigma", 0.7)`
- [x] `compute_temporal_similarity()`: 타임스탬프 None → `return 0.0` (기존 0.5 → 변경)
  - 이유: 시간 정보 없을 때 neutral(0.5)로 처리하면 시간 무관 기사가 같은 클러스터로 묶임
- [x] 파라미터 로딩 타이밍: 함수 호출 시마다 (캐시 Redis에서 가져오므로 부담 없음)

## grouping.py

**파일:** `backend/processor/algorithms/grouping.py` L53

- [x] `louvain_cluster(items, threshold=0.55)` 기본값 변경:
  - `threshold: float = await config_loader.get_setting("cluster.louvain_threshold", 0.70)`
- [x] 함수 시그니처를 async로 전환 필요 시 확인 후 처리

## 테스트
- [x] `tests/processor/test_semantic_clusterer.py` 확장:
  - "12월 실적" vs "12월 날씨" → 다른 클러스터 (Jaccard < 0.25)
  - 타임스탬프 None 케이스 → temporal_similarity = 0.0
  - 같은 출처 기사 → source_weight 반영 확인
- [x] `tests/processor/test_grouping.py`:
  - Louvain threshold 0.70 기준으로 클러스터 분리 확인

## 완료 기준
- [x] "12월" 단일 키워드 기사들이 다른 클러스터로 분리됨
- [x] pytest 통과, ruff 통과
