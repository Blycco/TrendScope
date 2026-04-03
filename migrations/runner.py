"""migrations/runner.py — 마이그레이션 순서대로 적용, 이미 적용된 것 skip."""

from __future__ import annotations

import asyncio
import importlib
import os

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

MIGRATIONS: list[str] = [
    "migrations.001_initial",
    "migrations.002_email_verified",
    "migrations.003_notifications",
    "migrations.004_personalization",
    "migrations.005_brand_monitor",
    "migrations.006_shared_links",
    "migrations.007_notification_keywords",
    "migrations.008_indexes",
    "migrations.009_audit_archive",
    "migrations.010_index_tuning",
    "migrations.011_feed_sources",
    "migrations.012_seed_feed_sources",
    "migrations.013_api_quota_alert",
    "migrations.014_seed_source_config",
    "migrations.015_article_category",
    "migrations.016_clean_titles",
    "migrations.017_error_log",
]


async def ensure_migrations_table(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS applied_migrations (
            version     TEXT PRIMARY KEY,
            description TEXT,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # Migrate existing VARCHAR(20) column to TEXT if needed
    await conn.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'applied_migrations'
                  AND column_name = 'version'
                  AND data_type = 'character varying'
            ) THEN
                ALTER TABLE applied_migrations ALTER COLUMN version TYPE TEXT;
            END IF;
        END $$;
    """)


async def get_applied(conn: asyncpg.Connection) -> set[str]:
    rows = await conn.fetch("SELECT version FROM applied_migrations")
    return {r["version"] for r in rows}


async def run_migrations() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")

    conn = await asyncpg.connect(dsn=database_url)
    try:
        await ensure_migrations_table(conn)
        applied = await get_applied(conn)

        for module_path in MIGRATIONS:
            mod = importlib.import_module(module_path)
            version = getattr(mod, "VERSION", module_path.split(".")[-1])
            description = getattr(mod, "DESCRIPTION", "")

            if version in applied:
                logger.info("migration_skipped", version=version)
                continue

            logger.info("migration_applying", version=version, description=description)
            transactional = getattr(mod, "TRANSACTIONAL", True)
            if transactional:
                async with conn.transaction():
                    await mod.up(conn)
                    await conn.execute(
                        "INSERT INTO applied_migrations (version, description) VALUES ($1, $2)",
                        version,
                        description,
                    )
            else:
                # Non-transactional migrations (e.g. CREATE INDEX CONCURRENTLY)
                await mod.up(conn)
                await conn.execute(
                    "INSERT INTO applied_migrations (version, description) VALUES ($1, $2)",
                    version,
                    description,
                )
            logger.info("migration_applied", version=version)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
