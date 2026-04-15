# D-02: V5 Deprecation

> Branch: `chore/v6-deprecate` | Agent: Algorithm
> 의존: D-01 100% 롤아웃 완료
> Plan 참조: §D-02

## 배경

V6 100% 롤아웃 이후 V5 코드를 DEPRECATED 마킹 (삭제는 롤백 창 1개월 유지).

## 작업

### 코드 주석

- [ ] V5 진입점 파일에 모듈 상단 주석:
  ```python
  """DEPRECATED (2026-MM-DD): superseded by pipeline_v6.

  Retained for rollback window. Scheduled removal: 2026-MM+1-DD.
  Do not add new features here.
  """
  ```
- [ ] 대상 파일:
  - `backend/processor/pipeline.py`
  - `backend/processor/shared/semantic_clusterer.py`
  - `backend/processor/shared/keyword_extractor.py` (V4 부분)

### Startup Warning

- [ ] `pipeline.version="v5"` 설정 감지 시:
  ```python
  logger.warning("pipeline_v5_deprecated",
                 message="V5 pipeline is deprecated. Scheduled removal: <date>.")
  ```

### 섀도우 → 정식 이관 스크립트

### `backend/jobs/shadow_to_primary_cleanup.py` (신규)

- [ ] V6 100% 전환 후 실행
- [ ] 섀도우 테이블 DROP (또는 백업 스키마로 MOVE)
- [ ] 정식 테이블 검증 (row count, FK 무결성)

### EVOLUTION.md 업데이트 (D-03에서 상세)

- [ ] 본 태스크는 "Deprecated" 태그만 달고, 전체 V6 섹션 작성은 D-03에서

## 체크리스트

- [ ] V5 파일 상단 주석
- [ ] Startup warning
- [ ] cleanup 스크립트
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Chore: V5 파이프라인 DEPRECATED 마킹 (V6 D-02)"`
