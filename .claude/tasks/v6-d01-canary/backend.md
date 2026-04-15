# D-01 (Backend): Canary 라우팅 로직

> Branch: `chore/v6-canary` | Agent: Backend

## 구현

### `backend/processor/main.py` (수정)

- [ ] `pipeline.canary_pct` 읽어 기사별 분기:
  ```python
  pct = settings.pipeline_canary_pct
  use_v6 = (hash(article.id.bytes) % 100) < pct
  if use_v6:
      await save_primary_v6(article, result_v6)
  else:
      await save_primary_v5(article, result_v5)
  ```
- [ ] `pipeline.version="shadow"` 경우에도 canary_pct 적용 (V6 정식 저장 비율)
- [ ] hash 결정론성 — 동일 article_id 항상 동일 결과

## admin_settings 확장 (C-04 이후)

- [ ] `pipeline.canary_pct` (기본 0)
- [ ] 설정 변경 시 audit_log 기록

## 테스트

- [ ] `test_canary_10pct`: 1만 기사 시뮬 → 9~11% V6 라우팅
- [ ] `test_deterministic_routing`: 동일 UUID → 동일 경로
- [ ] `test_pct_0_all_v5`
- [ ] `test_pct_100_all_v6`

## 완료 조건

- [ ] pytest 통과
- [ ] 통계 분포 확인
