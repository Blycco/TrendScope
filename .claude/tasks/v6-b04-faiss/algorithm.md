# B-04: FAISS ANN 인덱스

> Branch: `feat/v6-faiss` | Agent: Algorithm | Track: B
> 의존: B-03
> Plan 참조: §B-04

## 배경

V5 O(n²) 거리행렬 → FAISS HNSW O(n log n). 증분 업데이트 + 영속화로 재기동 고속.

## 목적

- IndexFlatIP(소규모) / IndexHNSWFlat(대규모) 자동 선택
- 영속 인덱스 `IndexIDMap2` + 24시간 rolling rotation
- top-k=30 이웃만 composite 계산 → sparse distance matrix

## 사전 확인

- [ ] `faiss-cpu` Docker 이미지 빌드 OpenBLAS 호환 확인
- [ ] `models/` 디렉터리 쓰기 권한 + `.gitignore`
- [ ] macOS ARM 개발 환경 호환 (faiss-cpu wheel)

## 신규 모듈

### `backend/processor/shared/v6/ann_index.py` (수정, stub 덮어씀)

```python
@dataclass
class AnnConfig:
    top_k: int = 30
    index_type: str = "auto"  # "flat" | "hnsw" | "auto"
    hnsw_m: int = 32
    hnsw_ef_construction: int = 200
    hnsw_ef_search: int = 64


class AnnIndex:
    def __init__(self, dim: int, config: AnnConfig):
        self.dim = dim
        self.config = config
        self._index = None
        self._id_map: list[str] = []

    def build(self, ids: list[str], vectors: np.ndarray) -> None:
        import faiss
        n = len(ids)
        use_hnsw = (self.config.index_type == "hnsw") or (
            self.config.index_type == "auto" and n >= 10_000
        )
        if use_hnsw:
            base = faiss.IndexHNSWFlat(self.dim, self.config.hnsw_m, faiss.METRIC_INNER_PRODUCT)
            base.hnsw.efConstruction = self.config.hnsw_ef_construction
            base.hnsw.efSearch = self.config.hnsw_ef_search
        else:
            base = faiss.IndexFlatIP(self.dim)
        self._index = faiss.IndexIDMap2(base)
        int_ids = np.arange(n, dtype=np.int64)
        self._id_map = list(ids)
        self._index.add_with_ids(vectors.astype(np.float32), int_ids)

    def search(self, vectors: np.ndarray, k: int | None = None) -> tuple[np.ndarray, np.ndarray]:
        k = k or self.config.top_k
        return self._index.search(vectors.astype(np.float32), k)

    def save(self, path: Path) -> None:
        import faiss
        faiss.write_index(self._index, str(path))

    def load(self, path: Path, id_map: list[str]) -> None:
        import faiss
        self._index = faiss.read_index(str(path))
        self._id_map = id_map
```

- [ ] `build_sparse_distance_matrix(embeddings, ids, k)`:
  - FAISS search → (n, k) distances, indices
  - scipy.sparse CSR 구성
  - HDBSCAN `metric="precomputed"` 에 투입
- [ ] 결정론: `faiss.omp_set_num_threads(1)` 전역 설정
- [ ] 영속 경로: `settings.MODELS_DIR / f"faiss_v6_{YYYYMMDD}.index"`
- [ ] ID map: `settings.MODELS_DIR / f"faiss_v6_{YYYYMMDD}.ids.json"`
- [ ] 24h rotation: 빌드 시점 날짜 변경되면 새 파일, 구 파일 7일 보관 후 삭제

### admin 설정

- [ ] `ann.top_k` (int, 30)
- [ ] `ann.index_type` ("auto"|"flat"|"hnsw", "auto")
- [ ] `ann.hnsw_m` (int, 32)
- [ ] `ann.hnsw_ef_search` (int, 64)

## 의존성

- [ ] `requirements/processor.txt`: `faiss-cpu>=1.8.0`

## 테스트

### `tests/test_ann_index.py` (신규)

- [ ] `test_flat_vs_hnsw_equivalence_small`: n=200, ARI ≥ 0.95
- [ ] `test_search_top_k`: k=30 반환
- [ ] `test_persist_roundtrip`: save → load → search 동일
- [ ] `test_auto_type_selection`: n<10000 → flat, n≥10000 → hnsw
- [ ] `test_benchmark_5000`: 5000건 < 15초

### `backend/processor/shared/v6/clusterer.py` (수정, sparse matrix 통합 - B-05에서 완성)

- [ ] `build_sparse_distance(embeddings, ids) -> scipy.sparse.csr_matrix`

## 메트릭 목표

- n=1000 클러스터링 stage 시간 V5 대비 -30%
- HNSW recall@30 ≥ 0.95 (vs flat)
- 재기동 후 인덱스 로드 < 2초

## Prometheus

- [ ] `ann_build_duration_seconds{index_type}` histogram
- [ ] `ann_search_duration_seconds` histogram
- [ ] `ann_index_size_bytes` gauge

## 롤백

- `ann.enabled=False` (별도 키) → V5 전체 거리행렬 계산 폴백
- 또는 `ann.top_k = n` 로 설정 시 사실상 flat full search

## 완료 조건

- [ ] pytest 통과
- [ ] 벤치 목표 달성
- [ ] 영속 인덱스 파일 확인
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: FAISS ANN 인덱스 (V6 B-04)"`
