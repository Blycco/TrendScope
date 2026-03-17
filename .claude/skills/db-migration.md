# Skill: DB Migration

1. Read context/schema.md
2. alembic revision --autogenerate -m "description"
3. Review generated file — never trust autogenerate blindly
4. alembic upgrade head (local test)
5. alembic downgrade -1 (rollback test)
6. Record reason in decisions/{date}-{title}.md
7. Commit (Chore: DB 마이그레이션 format)

Warning:
  Dropping columns with production data → Jiny approval required
  Partition table changes → coordinate with Infra agent
