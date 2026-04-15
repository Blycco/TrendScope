# B-02: KoE5 임베딩 어댑터

> Branch: `feat/v6-koe5` | Agent: Algorithm | Track: B
> 의존: B-01
> Plan 참조: §B-02

## 배경

KR-SBERT (snunlp, 2021) → `nlpai-lab/KoE5` (2024). Korean retrieval SOTA, KLUE-STS spearman 0.78 → 0.82 예상.

## 목적

- KoE5 1024차원 L2-normalized 임베딩
- Redis 캐시 3일 TTL
- KR-SBERT 폴백 (로드 실패 시)
- title/body 독립 인코딩 (A-05 연계)

## 사전 확인

- [ ] `sentence-transformers` 버전 확인 (KoE5 호환 ≥2.7)
- [ ] Redis 메모리 여유 (1024차원 × 4byte × 캐시 크기)
- [ ] Docker 이미지에 모델 pre-download 전략 수립 (infra 연계)

## 신규 모듈

### `backend/processor/shared/v6/embedder.py` (수정, B-01 stub 덮어씀)

```python
class Embedder:
    _instance = None
    _model = None

    def __init__(self, model_name: str = "nlpai-lab/KoE5", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._fallback_name = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

    def _lazy_load(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device=self.device)
            logger.info("embedder_loaded", model=self.model_name)
        except Exception as e:
            logger.warning("embedder_fallback", error=str(e))
            self._model = SentenceTransformer(self._fallback_name, device=self.device)

    def encode_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        self._lazy_load()
        return self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
```

- [ ] 싱글톤 접근자 `get_embedder()`
- [ ] 배치 내 중복 텍스트 캐시: sha1(text) → 1024-vec
- [ ] Redis 캐시: `embedv6:{sha1}` TTL 3일, pickle bytes
- [ ] admin: `embedder.model_name` (기본 "nlpai-lab/KoE5")

### `backend/processor/shared/cache_manager.py` (수정)

- [ ] `get_embedding_cache(sha: str) -> np.ndarray | None`
- [ ] `set_embedding_cache(sha: str, vec: np.ndarray, ttl: int = 259200)`

## 의존성

- [ ] `requirements/processor.txt`: `sentence-transformers>=2.7.0` (기존 업그레이드)
- [ ] Docker: Dockerfile stage에서 `huggingface-cli download nlpai-lab/KoE5` pre-cache

## 테스트

### `tests/test_embedder_v6.py` (신규)

- [ ] `test_encode_batch_shape`: 10 texts → (10, 1024) shape, L2 norm ≈ 1.0
- [ ] `test_similar_pair_high_cosine`: "삼성전자 실적" vs "삼성 실적" → cos > 0.80
- [ ] `test_dissimilar_low_cosine`: "날씨" vs "반도체" → cos < 0.30
- [ ] `test_cache_hit`: 동일 텍스트 재호출 → Redis hit
- [ ] `test_fallback_on_load_fail`: KoE5 로드 실패 mock → KR-SBERT 사용
- [ ] `test_batch_performance`: 500건 < 10초 (CPU)

### 벤치

- [ ] `tests/bench/embedder_bench.py`: KoE5 vs KR-SBERT 시간·품질 비교

## 메트릭 목표

- KLUE-STS spearman ≥ 0.82
- 캐시 히트율 ≥ 70% (반복 배치)
- 500건 인코딩 < 10초 (CPU)

## Prometheus

- [ ] `embedder_encode_duration_seconds{model}` histogram
- [ ] `embedder_cache_hit_total` counter
- [ ] `embedder_fallback_active` gauge

## 롤백

1. **소프트**: `embedder.model_name = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"`
2. **하드**: `pipeline.version="v5"`

## 완료 조건

- [ ] pytest 통과
- [ ] Docker 이미지 빌드 성공 (모델 포함)
- [ ] 벤치 기준치 달성
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: KoE5 임베딩 어댑터 (V6 B-02)"`
