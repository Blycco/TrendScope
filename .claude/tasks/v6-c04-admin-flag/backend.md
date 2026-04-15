# C-04 (Backend): pipeline.version admin flag

> Branch: `feat/v6-flag` | Agent: Backend
> 의존: B-01

## admin_settings 시드

### `backend/db/seeds/admin_settings.py` (수정)

```
('pipeline.version', 'shadow', 'str'),  # v5|v6|shadow
('pipeline.canary_pct', '0', 'int'),
```

## API

### `backend/api/routers/admin/settings.py` (수정)

- [ ] `pipeline.version` 키 노출
- [ ] Pydantic validation: `version ∈ {"v5","v6","shadow"}`
- [ ] `pipeline.canary_pct` ∈ [0, 100]
- [ ] 변경 시 audit_log (RULE 16) — actor, old/new value

### `backend/processor/main.py` (수정)

- [ ] `asyncio.create_task` 주기적 설정 재로드 (5분)
- [ ] version 변경 감지 시 structlog.warning

## Frontend

### `frontend/src/routes/admin/settings/+page.svelte` (수정)

- [ ] "Pipeline Control" 섹션:
  - radio: V5 / V6 / Shadow
  - number: Canary %
  - 변경 시 critical confirm 모달 (i18n)

## 테스트

- [ ] 유효 값 / 무효 값 검증
- [ ] audit_log 엔트리 생성 확인
- [ ] settings hot-reload (5분 내 반영 mock)

## 완료 조건

- [ ] pytest 통과
- [ ] audit_log 검증
- [ ] PR develop 머지
