# B-03: UMAP 차원축소

> Branch: `feat/v6-umap` | Agent: Algorithm | Track: B
> 의존: B-02
> Plan 참조: §B-03

## 배경

BERTopic 표준 전처리. 1024차원 KoE5 → 10차원 UMAP. HDBSCAN 성능·해석성 향상.

## 목적

- UMAP 차원축소 (1024→10, cosine metric)
- admin 파라미터 노출 (n_neighbors, n_components, min_dist)
- 재현성 (`random_state=42`)
- degenerate case (n<10) 스킵

## 사전 확인

- [ ] `umap-learn` 설치 가능 (numba 의존성 이슈 체크)
- [ ] Docker 이미지 크기 영향 (numba ~50MB)

## 신규 모듈

### `backend/processor/shared/v6/umap_reducer.py` (수정, stub 덮어씀)

```python
@dataclass
class UmapConfig:
    n_neighbors: int = 15
    n_components: int = 10
    min_dist: float = 0.0
    metric: str = "cosine"
    random_state: int = 42
    enabled: bool = True


class UmapReducer:
    def __init__(self, config: UmapConfig):
        self.config = config

    def fit_transform(self, embeddings: np.ndarray) -> np.ndarray:
        n = len(embeddings)
        if not self.config.enabled or n < 10:
            logger.info("umap_skipped", n=n, enabled=self.config.enabled)
            return embeddings
        import umap
        n_components = min(self.config.n_components, n - 2)
        reducer = umap.UMAP(
            n_neighbors=min(self.config.n_neighbors, n - 1),
            n_components=n_components,
            min_dist=self.config.min_dist,
            metric=self.config.metric,
            random_state=self.config.random_state,
            n_jobs=1,
        )
        return reducer.fit_transform(embeddings).astype(np.float32)
```

- [ ] admin 키:
  - `umap.enabled` (bool, True)
  - `umap.n_neighbors` (int, 15)
  - `umap.n_components` (int, 10)
  - `umap.min_dist` (float, 0.0)

### `backend/processor/shared/config_loader.py` (수정)

- [ ] `async def get_umap_config() -> UmapConfig` (Redis 5분 캐시)

## 의존성

- [ ] `requirements/processor.txt`: `umap-learn>=0.5.5`

## 테스트

### `tests/test_umap_v6.py` (신규)

- [ ] `test_fit_transform_shape`: (100, 1024) → (100, 10)
- [ ] `test_small_batch_skipped`: n<10 → 원본 그대로 반환
- [ ] `test_reproducibility`: 동일 seed → 동일 출력
- [ ] `test_n_components_auto_clip`: n_components > n-2 → 자동 축소
- [ ] `test_runtime_config_change`: admin 변경 후 반영

## 메트릭 목표

- 1000건 UMAP 처리 < 5초
- 동일 seed 재현성 100%

## Prometheus

- [ ] `umap_reduce_duration_seconds` histogram
- [ ] `umap_skipped_total` counter

## 롤백

- `umap.enabled=False` → 원본 1024차원을 HDBSCAN 직접 투입

## 완료 조건

- [ ] pytest 통과
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: UMAP 차원축소 (V6 B-03)"`
