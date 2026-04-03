# TrendScope — CLAUDE.md
> Always read this file. Keep under 120 lines. Details in context/.
---
## Current Status
- **Phase**: Production Readiness (Phase 1–5 완료, 안정화·최적화 진행 중)
- **Active Task**: 버그 수정 및 운영 안정화 (open PRs → develop)
- **Last Session**: `.claude/memory.md`

---

## Project Definition
Trend Intelligence SaaS — collects news·SNS·community trends and converts them into actionable insights tailored to 4 user roles: marketer, creator, business owner, general user.
**Stack**: FastAPI · PostgreSQL 15 · Redis 7 · SvelteKit · Python 3.11 · Docker Compose · Linux/Ubuntu Cloud (Docker)

---

## Agent Team Structure (Claude Code Agent Teams)
```
Jiny (CEO) ← approval requests
      ↓
Orchestrator ← coordinates all agents, routes tasks, reports progress
      ↓
Backend · Algorithm · Frontend · Infra · Reviewer · Security
```

> **IMPORTANT**: This project uses **Claude Code Agent Teams** (experimental).
> Agent Teams는 각자 독립 컨텍스트 윈도우를 가진 Claude Code 인스턴스.
> Orchestrator가 teammate를 스폰하고 파일 기반 task board로 조율.
> settings.json에서 CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 활성화됨.
- Agent details: `.claude/agents/`
- Orchestrator requests Jiny's approval at: **Phase start · merge to main · unexpected situations**
- Agents must ask Orchestrator before making decisions outside their defined scope
---
## Coding Rules (Mandatory)
```
RULE 01  No hardcoded secrets — environment variables only, NEVER commit secrets
RULE 02  DB queries — asyncpg $1,$2 parameterization only, f-string SQL strictly forbidden
RULE 03  All I/O must be async/await
RULE 04  Test coverage minimum 70%
RULE 05  No dead code — remove TODO/placeholder before marking done
RULE 06  All async functions must have try/except + structlog logging
RULE 07  Python type hints required on all functions
RULE 08  Plan gate — server-side middleware validation mandatory (never trust client)
RULE 09  API quota check via api_usage before processing
RULE 10  No direct path usage — use path constants or config (e.g. settings.BASE_DIR)
RULE 11  Single Responsibility Principle — one file, one purpose; group by domain
RULE 12  All user-facing errors must use modal alerts with error codes (see context/ux.md)
RULE 13  i18n required — no hardcoded strings; use translation keys (see context/i18n.md)
RULE 14  Agents must read relevant context files before starting any task
RULE 15  Agents must ask rather than assume — never write code for unspecified behavior
RULE 16  Security-sensitive operations require Security agent review (see agents/security.md)
RULE 17  Use shared/common code where applicable (see context/common.md)
RULE 18  Caching must be applied aggressively for resource efficiency (see context/cache.md)
RULE 19  API source quotas must be tracked and never exceeded (see context/pipeline.md)
RULE 20  Plan Mode required — run /plan before writing any code; no coding without an approved plan
```

---

## Branch & Commit Rules
```
Branches:
  feat/{description}     e.g. feat/dashboard
  fix/{description}      e.g. fix/auth-token-refresh
  hotfix/{description}
  chore/{description}
  All branch names lowercase-hyphenated, no slashes beyond prefix
  phase 번호 포함 브랜치명 절대 금지 (e.g. feat/phase4-xxx → REJECT)

Commit format:
  Feat: 한글로 작업 요약
  - 작업 내용 1
  - 작업 내용 2
  Ref: #{issue-number}

  Type prefix: Feat | Fix | Perf | Refactor | Test | Docs | Chore | Ci | Revert
  Example:
    Feat: 트렌드 피드 RSS ETag 크롤러 구현
    - ETag/If-Modified-Since 헤더 기반 304 스킵 처리
    - DedupeFilter Bloom Filter 연동
    Ref: #12

Commit splitting:
  - One logical unit per commit (e.g. DB migration ≠ API endpoint ≠ test)
  - Never mix infra changes with business logic in one commit
  - Each task checkbox = at minimum one separate commit

Issue linking:
  Ref: #{N}     partial progress — issue stays open
  Closes: #{N}  fully resolves the issue — auto-closes on merge
  Fix: #{N}     bug fix that resolves the issue
```

---

## Context Reference Guide
| Task | File |
|---|---|
| DB · migrations | `context/schema.md` |
| Algorithms · ML · NLP | `context/algorithms.md` |
| Data pipeline | `context/pipeline.md` |
| API endpoints | `context/api-spec.md` |
| Infrastructure · deployment | `context/infra.md` |
| Monetization · plan gates | `context/monetization.md` |
| Security · audit | `context/security.md` |
| Operations · CI/CD · A/B | `context/ops.md` |
| Monitoring · alerting | `context/monitoring.md` |
| Caching strategy | `context/cache.md` |
| UX · error modals | `context/ux.md` |
| i18n · translation | `context/i18n.md` |
| Common/shared code | `context/common.md` |
| Admin panel | `context/admin.md` |
| Feature specs | `context/features/` |
---
## Task Completion Criteria
1. pytest passed (≥70% coverage)
2. ruff lint passed
3. No secrets committed (Security agent verified)
4. `memory.md` updated
5. Commit follows branch/commit rules above
