# D-01 (Infra): V6 Canary 롤아웃 10→50→100%

> Branch: `chore/v6-canary` | Agent: Infra
> 의존: C-02, C-03
> Plan 참조: §D-01

## 목표

섀도우 검증 통과 후 점진 롤아웃. 자동 롤백 트리거 포함.

## 단계

### Stage 1: 10% (72h 관측)

- [ ] `pipeline.version="shadow"` 유지 + `pipeline.canary_pct=10` 세팅
- [ ] 라우팅: `hash(article_id) % 100 < 10` → V6 우선 저장 (남은 90%는 V5)
- [ ] 관측 지표 (72시간 윈도우):
  - silhouette Δ ≥ +0.03
  - outlier_ratio Δ ≤ +5%
  - 수동 리뷰 v6_better_ratio ≥ 0.45
  - stage p95 duration ≤ V5 × 1.2

### Stage 2: 50% (72h)

- [ ] Stage 1 기준 연속 통과 시 `canary_pct=50`
- [ ] 동일 기준 재검증

### Stage 3: 100%

- [ ] `pipeline.version="v6"` 설정 + `canary_pct=100`
- [ ] V5 정식 저장 중단 (단, 코드 유지)

## 자동 롤백 트리거

- [ ] silhouette Δ < -0.02 (24h 평균)
- [ ] v5_better_ratio ≥ 0.60
- [ ] outlier_ratio 절대값 > 0.30
- [ ] stage p95 > V5 × 1.5

트리거 시: `pipeline.version="v5"` 즉시 전환 + Slack 알림.

## 모니터링

### Grafana 대시보드 (신규 패널)

- [ ] "V6 Canary" 패널: version/canary_pct 실시간 값
- [ ] 메트릭 비교: silhouette, coherence, outlier, p95_duration
- [ ] 롤백 트리거 상태 (green/yellow/red)

### Prometheus 알람 룰

```yaml
- alert: V6SilhouetteRegression
  expr: (v5_silhouette - v6_silhouette) > 0.02
  for: 24h
  labels: { severity: critical }

- alert: V6OutlierSpike
  expr: v6_outlier_ratio > 0.30
  for: 1h
  labels: { severity: critical }

- alert: V6StageLatency
  expr: histogram_quantile(0.95, rate(pipeline_stage_duration_seconds{version="v6"}[5m]))
        > 1.5 * histogram_quantile(0.95, rate(pipeline_stage_duration_seconds{version="v5"}[5m]))
  for: 30m
  labels: { severity: warning }
```

### Runbook

### `docs/runbook/v6-rollout.md` (신규)

- [ ] 단계별 전환 명령 (`gh` 또는 admin UI)
- [ ] 대시보드 링크
- [ ] 롤백 절차 (설정 → 확인 → 알림)
- [ ] 연락처·승인자

## 완료 조건

- [ ] 3단계 순차 통과
- [ ] 롤백 시뮬레이션 1회 완료
- [ ] runbook 리뷰
- [ ] PR develop 머지
