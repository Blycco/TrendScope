# Phase 10 / Infra Tasks (Weeks 19-20)
> Agent: Infra

- [x] PostgreSQL index tuning (EXPLAIN ANALYZE-based) — PR #36 머지됨
- [x] Load testing (simulate MAU 1,000) — scripts/load-test.js (k6)
- [x] Prometheus + Grafana dashboards complete — infra/prometheus/ + infra/grafana/
- [x] Alert threshold tuning (per context/monitoring.md) — alert.rules.yml
- [x] Audit log archival strategy — backend/jobs/audit_archive.py (90일 초과 자동 이관, APScheduler)
- [ ] Full blue-green deployment drill — 미확인

Done (partial): 모니터링·부하테스트·인덱스 완료, 아카이빙·배포 드릴 미완
Approval: Orchestrator → Jiny for production launch
