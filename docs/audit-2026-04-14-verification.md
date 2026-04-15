# Audit 2026-04-14 웨이브별 검증 체크리스트

> develop 브랜치에 Waves 1–11 + P2 dead code 정리 전부 머지됨 (2026-04-14).
> 이 문서는 각 웨이브의 실제 동작 검증 절차를 모아둔 실행 가이드.

## 전제 조건
- Python 3.11 환경: `PY=/opt/homebrew/bin/python3.11`
- 로컬 스택 기동: `docker compose up -d postgres redis api processor crawler frontend`
- 최신 develop pull: `git checkout develop && git pull`

---

## Wave 1 — 스케줄러 누락 job 등록 (PR #236)
**대상**: `brand_alert`, `plan_expiry`, `keyword_review` cron 수정

```bash
# 단위 테스트
$PY -m pytest tests/test_jobs.py -v --no-cov

# 컨테이너 로그 확인
docker logs trendscope-crawler 2>&1 | grep -E "scheduler_job_registered|brand_alert|plan_expiry|keyword_review"
# 기대: job id 3개 모두 출력
```

---

## Wave 2 — Tracker 알림 토글 영속화 (PR #238)
**대상**: `PUT /api/tracker/alerts/{keyword_id}` + `tracker_alerts` 테이블

```bash
# 단위 테스트
$PY -m pytest tests/test_tracker_router.py -v --no-cov

# 수동 e2e
# 1) /tracker 페이지에서 알림 토글 ON
# 2) 새로고침 후 상태 유지 확인
# 3) DB: SELECT * FROM tracker_alerts WHERE user_id=$1;
```

---

## Wave 3 — Prometheus crawler 메트릭 (PR #240)
**대상**: reddit/youtube/google_trends/naver_datalab/burst 메트릭 발행

```bash
$PY -m pytest tests/test_metrics.py -v --no-cov

# 라이브 검증
curl -s localhost:8000/metrics | grep -E "crawler_requests_total|source=\"(reddit|youtube|google_trends|naver_datalab|burst)\""
```

---

## Wave 4 — trends:new pub/sub 소비자 (PR #242)
**대상**: `run_trends_consumer` + feed 캐시 무효화 + 키워드 알림 로그

```bash
$PY -m pytest tests/test_trends_pubsub_consumer.py -v --no-cov

# 라이브 검증
redis-cli KEYS 'feed:*'                               # 사전 상태
# processor에서 새 그룹 생성 시
docker logs trendscope-api 2>&1 | grep keyword_alert_triggered
redis-cli KEYS 'feed:*'                               # 사후: 비어있어야 함
```

---

## Wave 5 — score multiplier 영속화 (PR #244)
**대상**: `cross_platform_multiplier`, `external_trend_boost` 컬럼 저장

```bash
$PY -m pytest tests/test_score_multipliers_persist.py -v --no-cov

# 마이그레이션 적용 확인
psql $DATABASE_URL -c "\d trends" | grep -E "cross_platform_multiplier|external_trend_boost"

# 값 검증
psql $DATABASE_URL -c "SELECT cross_platform_multiplier, external_trend_boost FROM trends ORDER BY created_at DESC LIMIT 5;"
```

---

## Wave 6 — Plan Gate · ErrorModal UX (PR #246)
**대상**: PlanGate `upgradeUrl` 동적 반영 · share 성공 toast · export 중앙 핸들러

```bash
# 프론트 타입 체크 (기존 에러 제외 기준)
cd frontend && npx svelte-check --threshold error

# 수동 e2e
# 1) 무료 플랜으로 content 페이지 접근 → PlanGate 표시 → "업그레이드" 버튼이 서버가 준 upgradeUrl로 이동
# 2) trends 페이지에서 공유 복사 → SuccessToast가 나와야 함 (ErrorModal 아님)
# 3) trends export 실패(402) → ErrorModal + 중앙 errorCode 표시
```

---

## Wave 7 — Personalization 양방향 (PR #248)
**대상**: 설정 변경 시 trends 피드 자동 재로딩

```bash
# 수동 e2e
# 1) /trends 페이지 열기 → 현재 피드 기억
# 2) /settings에서 관심사 토글 저장
# 3) /trends로 돌아가면 피드가 즉시 재로딩되어야 함 (새로고침 불필요)
# 4) DevTools Network 탭: /trends 요청이 자동 발생했는지 확인
```

---

## Wave 9 — 인프라 헬스체크 · Alertmanager (PR #250)
**대상**: processor/crawler heartbeat HEALTHCHECK · Alertmanager 기동 · nginx 템플릿 렌더링

```bash
$PY -m pytest tests/test_heartbeat.py -v --no-cov

# 컨테이너 상태
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "trendscope-(processor|crawler|alertmanager)"
# 기대: processor·crawler 모두 (healthy) 표시, alertmanager Up

# heartbeat 파일
docker exec trendscope-processor ls -la /tmp/heartbeat
docker exec trendscope-crawler ls -la /tmp/heartbeat

# Alertmanager UI
curl -s localhost:9093/-/ready

# nginx 렌더링
docker exec trendscope-nginx cat /etc/nginx/nginx.conf | head -20
# 기대: ${DOMAIN} 변수가 실제 값으로 치환돼 있어야 함
```

---

## Wave 10 — kill-switch 프로덕션 가드 (PR #252)
**대상**: `APP_ENV=production`에서 `QUOTA_DISABLED`/`RATE_LIMIT_DISABLED` 무시

```bash
$PY -m pytest tests/test_middleware_quota.py tests/test_middleware_rate_limit.py -v --no-cov -k "disabled_env"

# 수동 검증 (로컬)
# 1) APP_ENV=production QUOTA_DISABLED=true 로 api 기동
# 2) 무료 사용자 토큰으로 /api/v1/trends를 11번 호출 → 429 QUOTA_EXCEEDED 나와야 함
# 3) 로그에서 "quota_disabled_ignored_in_production" WARNING 확인
```

---

## Wave 11 — RegionalMap 실제 구현 (PR #254)
**대상**: 대륙 polygon + 14종 locale + scale legend

```bash
# 프론트 e2e
# 1) /regional 페이지 진입
# 2) 6개 대륙 shape + locale 점들이 지리적으로 정확한 위치에 렌더되어야 함
# 3) 점에 hover/focus → tooltip에 locale명·트렌드 수·top 3 title 출력
# 4) 오른쪽 상단에 "범위: 1–N개" legend 확인
# 5) 데이터가 없는 locale 점은 렌더되지 않아야 함

# API 동작
curl -s localhost:8000/api/v1/trends/regional | jq '.entries | length'
```

---

## P2 Dead code 정리 (PR #256)
**대상**: `ab_test.py`, `cf.py` + 각 테스트 삭제

```bash
# 잔존 참조 없음 확인
grep -rn "from backend.processor.algorithms.ab_test\|from backend.processor.algorithms.cf" backend/ frontend/ tests/ || echo "OK — no references"

# 파일 삭제 확인
test ! -f backend/processor/algorithms/ab_test.py && echo "ab_test.py deleted"
test ! -f backend/processor/algorithms/cf.py && echo "cf.py deleted"
```

---

## 통합 검증

```bash
# 전체 단위 테스트
$PY -m pytest --cov
# 기대: 1174 passed / coverage ≥ 70%

# Lint
uv run ruff check backend/ tests/
cd frontend && npx svelte-check --threshold error

# 메트릭 엔드포인트 종합
curl -s localhost:8000/metrics | grep -cE "^(http_requests_total|crawler_requests_total|ai_api_requests_total|payment_failures_total|cache_requests_total|source_quota_ratio)"
# 기대: 6

# Prometheus alert rules
curl -s localhost:9090/api/v1/rules | jq '.data.groups[].rules[] | .name'
```
