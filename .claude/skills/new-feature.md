# Skill: New Feature

0. Enter Plan Mode (/plan) — get approval before writing any code
1. Read all relevant context/ files for this task
2. If any behavior is unspecified → ask Orchestrator before writing code
3. git checkout develop && git pull origin develop
4. git checkout -b feat/{description}
5. Implement (type hints · async/await · try/except + structlog)
6. Apply i18n for all user-facing strings
7. Use ErrorModal for all user-facing errors
8. Write tests (70%+)
9. ruff check . && pytest --cov
10. Security agent review if auth/payment/admin code
11. git add . && git commit (follow commit format in CLAUDE.md)
12. Notify Orchestrator
