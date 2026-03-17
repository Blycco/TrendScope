# Phase 1 / Backend Tasks (Weeks 1-2)
> Agent: Backend | Parallel with Infra | Security agent review required for auth structure

- [ ] Project folder structure (single responsibility per file, domain grouping)
- [ ] pyproject.toml (ruff · mypy · pytest config)
- [ ] requirements.txt / requirements-dev.txt
- [ ] backend/common/paths.py — all path constants
- [ ] backend/common/errors.py — error code definitions
- [ ] backend/common/audit.py — audit log writer
- [ ] migrations/001_initial.py — all 15 tables DDL (context/schema.md)
- [ ] backend/api/main.py — FastAPI app + structlog + asyncpg pool
- [ ] backend/api/routers/health.py — GET /health (DB + Redis status)
- [ ] backend/processor/shared/cache_manager.py — Redis pool + stampede prevention

Done: GET /health 200 · DB connected · Redis connected
