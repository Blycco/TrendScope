# B-06: 4요소 가중합 복원 (FAISS 이웃 한정)

> Branch: `feat/v6-weights` | Agent: Algorithm | Track: B
> 의존: B-05
> Plan 참조: §B-06

## 배경

순수 UMAP+HDBSCAN은 temporal/source 도메인 신호 유실. V5의 4요소 composite (cos+jac+tmp+src) 를 V6에 FAISS 이웃 한정으로 복원.

## 목적

- V5 `similarity.py` 로직을 V6 경로로 포팅
- FAISS top-k 이웃 쌍에만 composite 계산 (sparse distance 채움)
- 가중치 admin 노출 (V6 전용 네임스페이스)
- noise 재분류 시 composite 최대값으로 재할당

## 사전 확인

- [ ] V5 `semantic_clusterer.py` 4요소 가중합 코드 위치·구현 확인
- [ ] Jaccard 키워드 기반 계산 방식 확인 (V5 `keyword_set` 동일 사용 가능?)

## 구현

### `backend/processor/shared/v6/similarity.py` (수정, stub 덮어씀)

```python
@dataclass
class SimilarityWeights:
    cos: float = 0.55
    jac: float = 0.20
    tmp: float = 0.15
    src: float = 0.10
    jaccard_early_filter: float = 0.0  # V6 기본 비활성

    def validate(self) -> None:
        total = self.cos + self.jac + self.tmp + self.src
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"weights sum {total} != 1.0")


def composite_similarity(
    a: Article,
    b: Article,
    emb_a: np.ndarray,
    emb_b: np.ndarray,
    weights: SimilarityWeights,
) -> float:
    cos = float(np.dot(emb_a, emb_b))  # KoE5 L2 normalized
    jac = _jaccard(a.keyword_set, b.keyword_set)
    tmp = _temporal_decay(a.published_at, b.published_at)
    src = _source_diversity(a.source, b.source)
    return (
        weights.cos * cos
        + weights.jac * jac
        + weights.tmp * tmp
        + weights.src * src
    )
```

- [ ] `_temporal_decay(t1, t2)`: V5와 동일 로직 (48시간 half-life 등)
- [ ] `_source_diversity(s1, s2)`: 동일 소스 0, 다른 소스 1
- [ ] `_jaccard(set_a, set_b)`: `|A∩B| / |A∪B|`

### `backend/processor/shared/v6/clusterer.py` (수정)

- [ ] sparse distance matrix 빌드 시:
  - FAISS search → top-k 이웃 (i, j)
  - 각 (i,j) 에 대해 `composite_similarity` 계산
  - `distance = 1.0 - composite` 로 변환
  - 그 외 쌍은 `distance = 1.0` (noise 거리)
- [ ] noise 재분류:
  - 각 noise 기사에 대해 FAISS top-k 이웃 조회
  - 이웃들이 속한 클러스터 중 composite 평균 최대값 클러스터로 재할당
  - 기준값 미만 (`< 0.3`) 유지 → noise

### admin 설정

- [ ] `v6.sim.cos_weight` (0.55)
- [ ] `v6.sim.jac_weight` (0.20)
- [ ] `v6.sim.tmp_weight` (0.15)
- [ ] `v6.sim.src_weight` (0.10)
- [ ] `v6.sim.jaccard_early_filter` (0.0)
- [ ] `v6.sim.noise_reassign_threshold` (0.3)

## 테스트

### `tests/test_similarity_v6.py` (신규)

- [ ] `test_composite_weight_sum_validation`: 합 ≠ 1 → raise
- [ ] `test_temporal_weight_separates_old_articles`: 48h+ 차이 → 동일 임베딩이라도 다른 클러스터 경향
- [ ] `test_source_weight_pulls_multi_source`: 다소스 동일 이벤트 묶임
- [ ] `test_pure_cosine_mode`: weights=(1,0,0,0) → cosine만
- [ ] `test_noise_reassignment`: 임계 초과 noise → 재할당
- [ ] `test_deterministic_with_fixed_input`

## 메트릭 목표

- 다소스 동일 이벤트 묶임 비율 ≥ V5 수준
- 48h+ 이질 기사 오병합 ≤ V5 수준

## Prometheus

- [ ] `composite_similarity_histogram` 분포
- [ ] `noise_reassigned_total` counter

## 롤백

- `v6.sim.cos_weight=1.0`, 나머지 0 → 순수 cosine 모드
- `pipeline.version="v5"`

## 완료 조건

- [ ] pytest 통과
- [ ] V5와 B-06 통합 후 메트릭 비교 (C-01 연계)
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: V6 4요소 가중합 복원 + noise 재분류 (V6 B-06)"`
