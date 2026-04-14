# TrendScope 연결 누락·Dead Code 감사 및 복구 계획

생성일: 2026-04-14

## Context
프로덕션 안정화 단계(Phase 1–5 완료)에서, "구현은 되어 있지만 실제로 동작하지 않거나, 어디에도 연결되지 않은" 코드를 식별하고 순차 복구하기 위함. 3개 Explore 서브에이전트(backend/frontend/infra)로 감사 수행 → 총 35개 이슈 식별. 본 문서에는 🔴 치명 + 🟡 중간 항목만 포함하여 이슈화·해결 순서를 고정한다.

---

## 발견 사항 (Findings)

### 🔴 P0 — 치명적 (비즈니스 로직·보안·모니터링 파손)

**F1. `brand_alert` 스케줄 미등록**
- 위치: `backend/jobs/brand_alert.py:72-212` (구현 완료) ↔ `backend/crawler/scheduler.py` (미등록)
- 근거: `grep -r "run_brand_alert|brand_alert"` → self-reference만
- 영향: 브랜드 알림 기능 완전 비활성

**F2. `plan_expiry` 스케줄 미등록**
- 위치: `backend/jobs/plan_expiry.py:11-50` ↔ `backend/crawler/scheduler.py`
- 영향: 플랜 만료 자동 처리 안 됨 → 결제/구독 상태 불일치 위험

**F3. Redis pub/sub 소비자 부재**
- 위치: `backend/processor/stages/save.py:70` (publish) ↔ `backend/api/routers/live.py:26` (유일한 subscriber)
- 영향: `trends:new` 채널에 알림/추천 등 다른 소비자 미연결 → 실시간 파이프라인 일부 손실

**F4. Tracker 알림 토글 미저장**
- 위치: `frontend/src/routes/tracker/+page.svelte:125-134`
- 근거: `toggleAlert()`가 로컬 state만 mutate, API 호출 없음
- 영향: 사용자가 설정한 알림 옵션이 새로고침 시 소실

**F5. HTTP / AI / payment / crawler 메트릭 미발행**
- 위치: `infra/prometheus/alert.rules.yml:5-21, 33, 41, 50-52` vs `backend/common/metrics.py:29`
- 근거: alert rule이 `http_requests_total`, `crawler_requests_total`, `ai_api_requests_total`, `payment_failures_total` 참조하지만 backend에서 `.inc()` 호출 없음
- 영향: 알림 룰이 영구 무음 상태

**F18. 🆕 `keyword_review` cron 표현식 invalid — 스케줄러 전체 기동 실패**
- 위치: `backend/crawler/scheduler.py:212` `hour="*/24"`
- 근거: APScheduler `ValueError: step value (24) is higher than the total range of the expression (23)` — `create_scheduler()` 호출 시점에 raise
- 영향: 크롤러 컨테이너의 모든 job 자동 실행 자체가 시작되지 않고 있을 가능성. 모든 스케줄(뉴스·SNS·커뮤니티·early_trend·quota_reset 등)에 연쇄 영향
- Wave 1 사전 검증 중 `create_scheduler` 테스트로 발견됨

---

### 🟡 P1 — 중간 (값 낭비 / UX 파손 / 보안 우회)

**F6. `cross_platform_multiplier` 미저장**
- 위치: `backend/processor/stages/score.py:220` 계산 → `save.py:33-47` INSERT 누락

**F7. `external_trend_boost` 미저장**
- 위치: `backend/processor/stages/score.py:221-225` 계산 → `save.py` INSERT 누락

**F8. PlanGate `upgradeUrl` 무시**
- 위치: `frontend/src/lib/ui/PlanGate.svelte:60-70`
- 문제: API 응답의 동적 upgradeUrl 무시, 하드코딩 `/pricing` 사용

**F9. ErrorModal 성공 메시지 오용 (RULE 12 부분 위반)**
- 위치: `frontend/src/routes/trends/+page.svelte:218-220`
- 문제: 공유 링크 복사 성공도 ErrorModal + 빈 errorCode로 표시

**F10. Personalization 단방향 흐름**
- 위치: `frontend/src/routes/trends/+page.svelte:301-307`
- 문제: settings 변경 시 trends 피드 자동 재로딩 안 됨

**F11. Export 엔드포인트가 중앙 에러 핸들러 우회**
- 위치: `frontend/src/routes/trends/+page.svelte:155-196`
- 문제: `apiRequest` 대신 raw `fetch`, 402/403 inline 파싱

**F12. Payment webhook 미구현**
- 위치: `.env.example:37` (`PAYMENT_WEBHOOK_SECRET`) vs `backend/api/routers/payments.py`
- 문제: 시크릿 ENV만 있고 webhook handler 자체 없음

**F13. Quota / RateLimit ENV kill-switch**
- 위치: `backend/api/middleware/quota.py:10`, `rate_limit.py:9`
- 문제: `QUOTA_DISABLED=true` / `RATE_LIMIT_DISABLED=true`로 프로덕션 보안 우회 가능

**F14. RegionalMap placeholder**
- 위치: `frontend/src/lib/components/RegionalMap.svelte`
- 문제: 지도 UI 뼈대만, 대륙 placeholder 주석만 존재

**F15. nginx.prod.conf 템플릿만 존재**
- 위치: `infra/nginx/nginx.prod.conf.template` ↔ `docker-compose.prod.yml:96` 은 렌더된 `nginx.prod.conf` 참조
- 문제: `scripts/deploy.sh` envsubst에만 의존, compose 직접 실행 시 깨짐

**F16. processor/crawler Dockerfile HEALTHCHECK 누락**
- 위치: `backend/Dockerfile` (api만 헬스체크), processor·crawler 이미지 없음

**F17. AlertManager 비활성**
- 위치: `infra/prometheus/prometheus.yml:6-10` 주석 처리
- 문제: alert.rules.yml 있어도 Slack/email 발송 경로 없음

---

### 🟢 P2 — Dead code (별도 정리 이슈로 분리, 본 계획에서 제외)
- `backend/processor/algorithms/aspect_sentiment.py`, `ab_test.py`, `cf.py` — 완전 미사용 (test_*만 존재)
- `frontend/src/lib/components/KeywordTimeline.svelte` — 미 import

---

## 해결 순서 (Execution Order)

각 묶음 = 1 GitHub 이슈 + 1 브랜치 + 1 PR. CLAUDE.md 브랜치·커밋 규칙 준수.

### Wave 1 — 스케줄러 복구 (P0: F1, F2, F18)
- 브랜치: `fix/scheduler-missing-jobs`
- 작업:
  - **(선행) F18: `hour="*/24"` → `hour=1` (매일 01:00 UTC) 교체** — 이걸 먼저 고쳐야 나머지 job 등록이 실제로 작동
  - `backend/crawler/scheduler.py`에 `run_brand_alert`, `run_plan_expiry` add_job 등록
  - 각 job 주기/타임존: brand_alert 10분 interval, plan_expiry cron hour=18 (= 03:00 KST)
  - 스케줄러 시작 로그에 job id 리스트 덤프
- 테스트:
  - `tests/test_jobs.py`에 `TestSchedulerJobRegistration` 추가 → `create_scheduler()` 호출 후 `brand_alert`/`plan_expiry`/`keyword_review` id 모두 존재 검증
  - `pytest tests/test_jobs.py -x --no-cov`

### Wave 2 — Tracker 알림 영속화 (P0: F4)
- 브랜치: `fix/tracker-alert-persistence`
- 작업:
  - backend: `PUT /api/tracker/alerts/{keyword_id}` 또는 기존 tracker 라우터 확장
  - DB: `tracker_alerts` 테이블 확인, 없으면 마이그레이션 추가
  - frontend: `toggleAlert()` → `apiRequest` 호출, 로딩·에러 모달 처리
- 테스트: 토글 후 새로고침 시 유지 e2e

### Wave 3 — Prometheus 메트릭 발행 (P0: F5)
- 브랜치: `fix/prometheus-missing-metrics`
- 작업:
  - FastAPI Instrumentator `.expose()` 확인 및 alert에 쓰이는 메트릭 이름 매칭
  - crawler: 요청 성공/실패에 `CRAWLER_REQUESTS.labels(result=...).inc()`
  - AI API 호출부(sentiment 등)에 `AI_API_REQUESTS.inc()`
  - 결제 실패 경로에 `PAYMENT_FAILURES.inc()`
- 테스트: `/metrics` 엔드포인트 응답에 4개 메트릭 모두 노출 확인

### Wave 4 — Redis pub/sub 소비자 연결 (P0: F3)
- 브랜치: `fix/trends-pubsub-consumer`
- 작업:
  - 요구사항 확인: `trends:new` 소비자 대상 후보 (알림 발송, 추천 재계산, 캐시 invalidation 중 어느 것?)
  - AskUser 결과에 따라 적절한 consumer task 추가
- 주의: 범위 확정 전 구현 금지 (RULE 15)

### Wave 5 — 점수 영속화 (P1: F6, F7)
- 브랜치: `fix/score-multipliers-persist`
- 작업:
  - 마이그레이션: `trends` 테이블에 `cross_platform_multiplier FLOAT`, `external_trend_boost FLOAT` 컬럼 추가
  - `save.py` INSERT 컬럼 확장
  - `db/queries/trends.py` SELECT 업데이트, API 응답 스키마 확장
- 테스트: 신규 트렌드 insert 후 컬럼 값 검증

### Wave 6 — Plan Gate & ErrorModal UX (P1: F8, F9, F11)
- 브랜치: `fix/plan-gate-error-modal-ux`
- 작업:
  - PlanGate에 `upgradeUrl` prop 반영, 하드코딩 제거
  - Share 복사 성공은 별도 toast/success 모달로 분리
  - trends export: `apiRequest` + 중앙 `handleApiError` 경로 통일
- 테스트: 유료 플랜 요구 에러 시 동적 URL 이동 확인

### Wave 7 — Personalization 양방향 (P1: F10)
- 브랜치: `fix/personalization-refresh-on-change`
- 작업: settings store subscribe → trends 페이지 재로딩 트리거

### Wave 8 — 결제 Webhook 구현 (P1: F12)
- 브랜치: `feat/payment-webhook-handler`
- 주의: Security agent 필수 리뷰 (RULE 16)
- 작업: 토스페이먼츠 webhook endpoint, 서명 검증, audit_log 기록

### Wave 9 — 인프라 헬스체크·Alertmanager·nginx (P1: F15, F16, F17)
- 브랜치: `chore/infra-healthcheck-alertmanager`
- 작업:
  - processor/crawler Dockerfile HEALTHCHECK 추가
  - Alertmanager 서비스 docker-compose.prod.yml에 추가, Slack receiver 설정
  - nginx.prod.conf 렌더링을 compose entrypoint로 이동 or .gitignore 처리 문서화

### Wave 10 — 보안 kill-switch 정리 (P1: F13)
- 브랜치: `fix/disable-env-kill-switch-in-prod`
- 작업: `ENV=production`일 때 kill-switch ENV 무시하도록 가드 추가

### Wave 11 — RegionalMap 구현 여부 결정 (P1: F14)
- AskUser: "구현할 것인가 / 숨길 것인가 / 롤백할 것인가" 의사결정 필요

### (별건) Dead code 정리
- 브랜치: `chore/remove-dead-algorithms`
- F1~F17과 분리, 최종 단계에서 일괄 처리

---

## 이슈화 산출물
- 본 plan 파일을 기반으로 `gh issue create` 11건 (Wave 1~11) 발행 예정
- 각 이슈 body = 해당 Wave 섹션 복사
- 라벨: `bug` / `chore` / `feat` + `audit-2026-04-14`

---

## 검증 (End-to-end)
1. Wave별 PR 머지 후 `docker compose up` → 스케줄러 로그에 모든 job 등록 확인
2. `/metrics` curl → 4개 누락 메트릭 노출 확인
3. Prometheus UI → alert rule 상태 `OK`/`FIRING` 정상 전환 확인
4. frontend e2e: tracker 토글 영속, plan gate 동적 URL, share 성공 toast
5. `pytest --cov` ≥70% 유지, `ruff check` 통과

---

## Critical Files
- `backend/crawler/scheduler.py` (Wave 1)
- `backend/jobs/brand_alert.py`, `plan_expiry.py` (Wave 1)
- `frontend/src/routes/tracker/+page.svelte` (Wave 2)
- `backend/common/metrics.py` + crawler/processor 호출부 (Wave 3)
- `backend/processor/stages/{save,score}.py`, `backend/db/migrations/` (Wave 5)
- `frontend/src/lib/ui/{PlanGate,ErrorModal}.svelte` (Wave 6)
- `backend/api/routers/payments.py` (Wave 8)
- `infra/prometheus/prometheus.yml`, `docker-compose.prod.yml` (Wave 9)
