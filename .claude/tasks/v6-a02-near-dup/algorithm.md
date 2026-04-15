# A-02: Near-duplicate Detection (MinHash+LSH + SimHash)

> Branch: `feat/v6-near-dup` | Agent: Algorithm | Track: A
> 의존: A-01 (언어별 shingling 분기)
> Plan 참조: §A-02

## 배경

현행 dedupe(`dedupe_filter.py`)는 URL 해시 + Bloom filter + Redis 기반 정확 중복만 감지. 동일 이벤트의 재작성/복붙/부분 변형 기사는 통과 → V5 클러스터 내부에 near-dup 5~20% 오염 추정.

## 목적

MinHash+LSH(Jaccard 0.85) 1차 후보 + SimHash Hamming 3 검증으로 near-dup 탐지. near-dup 발견 시 `duplicate_of` 세팅 + 클러스터링 스킵.

## 사전 확인

- [ ] 현행 `dedupe_filter.py` 3단계 구조 숙지 (URL → Bloom → Redis)
- [ ] Redis 버전 확인 (datasketch Redis backend 호환: Redis 5+)
- [ ] `article` 테이블에 `duplicate_of` 컬럼 유무 확인

## DB 마이그레이션

### `backend/db/migrations/034a_article_duplicate_of.sql` (신규, A-01 이후)

- [ ] 파일 작성:
  ```sql
  BEGIN;
  ALTER TABLE article ADD COLUMN IF NOT EXISTS duplicate_of UUID REFERENCES article(id) ON DELETE SET NULL;
  CREATE INDEX IF NOT EXISTS idx_article_duplicate_of ON article(duplicate_of) WHERE duplicate_of IS NOT NULL;
  ALTER TABLE article ADD COLUMN IF NOT EXISTS skip_cluster BOOLEAN NOT NULL DEFAULT FALSE;
  COMMIT;
  ```
- [ ] runner 등록

## 신규 모듈

### `backend/processor/shared/near_dup.py` (신규)

- [ ] 상단 주석: 설계 근거 (LSH threshold 0.85, SimHash Hamming 3 선택 이유)
- [ ] Shingling:
  ```python
  def _shingle(text: str, lang: str, size: int = 5) -> list[str]:
      # 한국어: 자모 분해 후 5-char shingling (자모 단위)
      # 영문/기타: 소문자 + 5-char shingling
  ```
- [ ] MinHash 생성:
  ```python
  from datasketch import MinHash, MinHashLSH
  def compute_minhash(text: str, lang: str, num_perm: int = 128) -> MinHash:
      m = MinHash(num_perm=num_perm)
      for shingle in _shingle(text, lang):
          m.update(shingle.encode("utf-8"))
      return m
  ```
- [ ] LSH 인스턴스 (Redis backend):
  - `MinHashLSH(threshold=0.85, num_perm=128, storage_config={"type":"redis","redis":{"host":...,"port":...}})`
  - Redis key prefix: `neardup:lsh:{lang}` (lang별 분리) TTL 7일
- [ ] SimHash 64bit (본문용):
  - 자체 구현: `_simhash(tokens: list[str]) -> int` — feature hash + weighted sum
  - hamming distance `_hamming(a: int, b: int) -> int`
- [ ] 판정 `async def find_near_duplicate(article) -> Optional[str]`:
  1. MinHash 계산 → LSH 쿼리 → 후보 article_ids
  2. 후보 각각에 대해 실제 Jaccard ≥ 0.85 OR SimHash Hamming ≤ 3 검증
  3. 첫 매치 반환 (original article_id)
  4. 매치 없음 → None 반환 후 LSH 인덱스에 등록
- [ ] config:
  - `neardup.enabled` (bool, 기본 True)
  - `neardup.lsh_threshold` (float, 0.85)
  - `neardup.simhash_hamming` (int, 3)
  - `neardup.num_perm` (int, 128)

### `backend/processor/stages/dedupe.py` (수정)

- [ ] 기존 dedupe(URL 해시) 완료 후 near_dup 단계 추가
- [ ] near-dup 발견 시:
  - `article.duplicate_of = original_id`
  - `article.skip_cluster = True`
  - `logger.info("near_dup_detected", article_id=..., duplicate_of=...)`
- [ ] Prometheus counter: `near_dup_detected_total`

### `backend/processor/pipeline.py` (수정)

- [ ] `skip_cluster=True` 기사는 cluster stage 진입 시 스킵

## admin_settings 시드

- [ ] `neardup.enabled` = True
- [ ] `neardup.lsh_threshold` = 0.85
- [ ] `neardup.simhash_hamming` = 3
- [ ] `neardup.num_perm` = 128

## 의존성

- [ ] `requirements/processor.txt`: `datasketch>=1.6.0`

## 테스트

### `tests/test_near_dup.py` (신규)

- [ ] `test_identical_articles`: 동일 기사 10건 → 첫 1건만 pass, 나머지 duplicate_of 세팅
- [ ] `test_5pct_variation`: 본문 5% 변형 → near-dup 판정
- [ ] `test_different_events_same_topic`: 다른 이벤트/동일 주제 기사 → 각각 통과, FP < 3%
- [ ] `test_lsh_redis_roundtrip`: Redis 백엔드에 인덱스 저장·조회
- [ ] `test_simhash_hamming_distance`: 구현 정확성
- [ ] `test_korean_shingling_uses_jamo`: 한국어 shingling이 자모 단위인지

### 성능 벤치

- [ ] `tests/bench/near_dup_bench.py`: 1000 기사 처리 < 3초

## 메트릭 목표

- 클러스터 내 near-dup 중복 비율 < 5%
- FP(거짓 near-dup 판정) < 3%
- Stage overhead p95 < 30ms/article

## Prometheus 메트릭

- [ ] `near_dup_detected_total{lang}` counter
- [ ] `near_dup_duration_seconds` histogram
- [ ] `near_dup_lsh_candidates` histogram (LSH 후보 수 분포)

## 롤백 시나리오

1. **소프트**: `neardup.enabled=False` → stage no-op
2. **하드**:
   - `stages/dedupe.py` 에서 near_dup 호출 제거
   - 마이그레이션 roll-forward 스크립트로 `duplicate_of`/`skip_cluster` 컬럼 NULL 처리

## 완료 조건

- [ ] pytest 통과
- [ ] 샘플 1000 기사 배치 처리 확인
- [ ] near-dup 탐지 로그 실제 데이터에서 검증
- [ ] 커버리지 ≥70%, ruff clean
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: Near-duplicate 탐지 MinHash+SimHash 도입 (V6 A-02)"`
