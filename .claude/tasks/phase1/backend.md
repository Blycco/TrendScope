# Phase 1 / Backend Tasks (Weeks 1-2)
> Agent: Backend | Parallel with Infra | Security agent review required for auth structure

- [x] Project folder structure (single responsibility per file, domain grouping)
- [x] pyproject.toml (ruff · mypy · pytest config)
- [x] requirements.txt / requirements-dev.txt
- [x] backend/common/paths.py — all path constants
- [x] backend/common/errors.py — error code definitions
- [x] backend/common/audit.py — audit log writer
- [x] migrations/001_initial.py — all 15 tables DDL (context/schema.md)
- [x] backend/api/main.py — FastAPI app + structlog + asyncpg pool
- [x] backend/api/routers/health.py — GET /health (DB + Redis status)
- [x] backend/processor/shared/cache_manager.py — Redis pool + stampede prevention

Done: GET /health 200 · DB connected · Redis connected
