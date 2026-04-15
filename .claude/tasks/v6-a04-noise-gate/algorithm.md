# A-04: Noise Gate 재설계 + Admin 노출

> Branch: `feat/v6-noise-gate` | Agent: Algorithm | Track: A
> 의존: 없음
> Plan 참조: §A-04

## 배경

현행 `semantic_clusterer.py:~349` 의 noise 품질 게이트(`text≥20자 AND kw≥3`)가 하드코드. 20자는 1~2문장 수준으로 너무 느슨. 런타임 튜닝 불가.

## 목적

- 게이트 파라미터 5종 admin 노출
- 중복 토큰/제목만 기사 등 지능형 거부 사유 추가
- 거부 사유별 메트릭 수집

## 사전 확인

- [ ] `semantic_clusterer.py` 내 noise gate 로직 위치·조건 확인
- [ ] 현재 noise=-1 클러스터 처리 흐름 숙지

## 신규 모듈

### `backend/processor/shared/noise_gate.py` (신규)

- [ ] 책임: noise 판정 로직 분리 (SRP, RULE 11)
- [ ] 시그니처:
  ```python
  def should_reject(
      article,
      keywords: list[Keyword],
      lang: str,
      config: NoiseGateConfig,
  ) -> tuple[bool, str | None]:
      ...
  ```
  두 번째 값은 거부 사유 태그 (`"too_short" | "too_few_keywords" | "title_only" | "duplicate_keyword_spam" | None`)
- [ ] 검사 순서:
  1. `len(normalized_text) < config.min_text_chars` → `"too_short"`
  2. `len(keywords) < config.min_keyword_count` → `"too_few_keywords"`
  3. `len(unique_tokens) < config.min_unique_tokens` → `"too_few_unique_tokens"`
  4. `config.reject_if_title_only and not body` → `"title_only"`
  5. 중복 토큰 비율 > `config.reject_if_duplicate_keyword_ratio_gt` → `"duplicate_keyword_spam"`
  6. 모두 통과 → `(False, None)`

### `NoiseGateConfig` dataclass

```python
@dataclass
class NoiseGateConfig:
    min_text_chars: int = 40
    min_keyword_count: int = 3
    min_unique_tokens: int = 5
    reject_if_title_only: bool = True
    reject_if_duplicate_keyword_ratio_gt: float = 0.6
```

### `backend/processor/shared/config_loader.py` (수정)

- [ ] `async def get_noise_gate_config() -> NoiseGateConfig` 추가 (Redis 5분 캐시)

### `backend/processor/shared/semantic_clusterer.py` (수정)

- [ ] noise=-1 처리 직후 `should_reject` 호출
- [ ] 거부된 기사는 클러스터 할당에서 제외
- [ ] `logger.info("noise_rejected", article_id=..., reason=...)`
- [ ] 기존 하드코드 상수 제거

## admin_settings 시드

### `backend/db/seeds/admin_settings.py` (수정)

```
('noise.min_text_chars', '40', 'int'),
('noise.min_keyword_count', '3', 'int'),
('noise.min_unique_tokens', '5', 'int'),
('noise.reject_if_title_only', 'true', 'bool'),
('noise.reject_if_duplicate_keyword_ratio_gt', '0.6', 'float'),
```

## Backend API

### `backend/api/routers/admin/settings.py` (수정)

- [ ] 신규 키를 admin 설정 스키마에 노출
- [ ] Pydantic validation (타입, 범위)
  - `min_text_chars` ∈ [0, 500]
  - `min_keyword_count` ∈ [0, 20]
  - `min_unique_tokens` ∈ [0, 50]
  - `reject_if_duplicate_keyword_ratio_gt` ∈ [0.0, 1.0]

### `backend/api/schemas/admin.py` (수정)

- [ ] `NoiseGateSettings` 스키마 추가

## Frontend

### `frontend/src/routes/admin/settings/+page.svelte` (수정)

- [ ] "Noise Gate" 섹션 추가 (5 입력 필드)
- [ ] 기본값 표시, 변경 시 confirm 모달
- [ ] i18n 키 `admin.settings.noise_gate.*`

## Prometheus 메트릭

- [ ] `noise_rejection_total{reason="too_short|too_few_keywords|too_few_unique_tokens|title_only|duplicate_keyword_spam"}` counter
- [ ] `backend/common/metrics.py` 등록

## 테스트

### `tests/test_noise_gate.py` (신규)

- [ ] 각 거부 사유별 픽스처 (5종)
- [ ] `test_all_pass_returns_false`
- [ ] `test_runtime_config_change`: admin_settings 변경 → 다음 호출 반영 (5분 캐시 내, 강제 무효화 함수 호출 테스트)
- [ ] `test_duplicate_keyword_ratio`: "월 월 월 월 연휴" → 거부

## 메트릭 목표

- noise 제거율 현행 대비 +15%
- FP 증가 < 2% (정상 기사가 잘못 거부됨)
- 거부 사유별 분포 관찰 가능

## 롤백

1. **소프트**: 모든 파라미터 현행 값으로 원복 (min_text_chars=20, min_keyword_count=3, min_unique_tokens=0, reject_if_title_only=False, reject_if_duplicate_keyword_ratio_gt=1.0)
2. **하드**: `semantic_clusterer.py` 에서 `should_reject` 호출 제거, 하드코드 로직 복원

## 완료 조건

- [ ] pytest 통과
- [ ] admin UI에서 실시간 변경 동작
- [ ] Prometheus 메트릭 노출 확인
- [ ] 커버리지 ≥70%, ruff clean
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: Noise gate 파라미터 admin 노출 + 거부 사유 확장 (V6 A-04)"`
