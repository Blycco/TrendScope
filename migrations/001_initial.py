"""Migration 001: Initial schema — 15 core tables.

Run with: python -m migrations.001_initial
or via the migration runner in the deployment pipeline.

All queries use asyncpg parameterized form where applicable.
DDL statements do not use f-strings (RULE 02).
"""

from __future__ import annotations

import asyncio
import os

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# DDL Statements
# ---------------------------------------------------------------------------

CREATE_TABLES: list[str] = [
    # --- news_group ---
    """
    CREATE TABLE IF NOT EXISTS news_group (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        category        TEXT NOT NULL,
        locale          CHAR(2) NOT NULL,
        title           TEXT NOT NULL,
        summary         TEXT,
        score           FLOAT NOT NULL DEFAULT 0.0,
        early_trend_score FLOAT NOT NULL DEFAULT 0.0,
        keywords        TEXT[] DEFAULT '{}',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,

    # --- news_article (monthly partition by publish_time) ---
    """
    CREATE TABLE IF NOT EXISTS news_article (
        id              UUID NOT NULL DEFAULT gen_random_uuid(),
        group_id        UUID REFERENCES news_group(id) ON DELETE SET NULL,
        url             TEXT NOT NULL,
        url_hash        CHAR(16) NOT NULL,
        content_fp      CHAR(16),
        title           TEXT NOT NULL,
        body            TEXT,
        source          TEXT,
        author          TEXT,
        publish_time    TIMESTAMPTZ NOT NULL,
        locale          CHAR(2) NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (id, publish_time)
    ) PARTITION BY RANGE (publish_time)
    """,

    # --- Default partition for news_article ---
    """
    CREATE TABLE IF NOT EXISTS news_article_default
        PARTITION OF news_article DEFAULT
    """,

    # --- sns_trend ---
    """
    CREATE TABLE IF NOT EXISTS sns_trend (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        platform        TEXT NOT NULL,
        keyword         TEXT NOT NULL,
        locale          CHAR(2) NOT NULL,
        category        TEXT,
        score           FLOAT NOT NULL DEFAULT 0.0,
        early_trend_score FLOAT NOT NULL DEFAULT 0.0,
        burst_z         FLOAT NOT NULL DEFAULT 0.0,
        sentiment_badge TEXT CHECK (sentiment_badge IN ('positive', 'neutral', 'negative')),
        snapshot_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,

    # --- user_profile ---
    """
    CREATE TABLE IF NOT EXISTS user_profile (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email           TEXT UNIQUE NOT NULL,
        display_name    TEXT,
        role            TEXT NOT NULL DEFAULT 'general'
                            CHECK (role IN ('marketer', 'creator', 'owner', 'general', 'admin', 'operator')),
        locale          CHAR(2) NOT NULL DEFAULT 'ko',
        category_weights JSONB NOT NULL DEFAULT '{}',
        plan            TEXT NOT NULL DEFAULT 'free'
                            CHECK (plan IN ('free', 'pro', 'business', 'enterprise')),
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,

    # --- user_identity ---
    """
    CREATE TABLE IF NOT EXISTS user_identity (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
        provider        TEXT NOT NULL CHECK (provider IN ('google', 'kakao', 'email')),
        provider_uid    TEXT,
        password_hash   TEXT,
        two_fa_enabled  BOOLEAN NOT NULL DEFAULT FALSE,
        two_fa_secret   TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (user_id, provider)
    )
    """,

    # --- action_insight ---
    """
    CREATE TABLE IF NOT EXISTS action_insight (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        trend_kw        TEXT NOT NULL,
        role            TEXT NOT NULL CHECK (role IN ('marketer', 'creator', 'owner', 'general')),
        locale          CHAR(2) NOT NULL DEFAULT 'ko',
        content         JSONB NOT NULL DEFAULT '{}',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at      TIMESTAMPTZ NOT NULL
    )
    """,

    # --- content_idea ---
    """
    CREATE TABLE IF NOT EXISTS content_idea (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
        trend_kw        TEXT NOT NULL,
        ideas           JSONB NOT NULL DEFAULT '[]',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at      TIMESTAMPTZ NOT NULL
    )
    """,

    # --- subscription ---
    """
    CREATE TABLE IF NOT EXISTS subscription (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
        plan            TEXT NOT NULL CHECK (plan IN ('free', 'pro', 'business', 'enterprise')),
        status          TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'cancelled', 'expired', 'past_due')),
        provider        TEXT,
        provider_sub_id TEXT,
        started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at      TIMESTAMPTZ,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,

    # --- api_usage ---
    """
    CREATE TABLE IF NOT EXISTS api_usage (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
        endpoint        TEXT NOT NULL,
        used_count      INT NOT NULL DEFAULT 0,
        quota_limit     INT NOT NULL DEFAULT 0,
        reset_at        TIMESTAMPTZ NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (user_id, endpoint, reset_at)
    )
    """,

    # --- brand_monitor ---
    """
    CREATE TABLE IF NOT EXISTS brand_monitor (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
        brand_name      TEXT NOT NULL,
        keywords        TEXT[] DEFAULT '{}',
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,

    # --- scrap ---
    """
    CREATE TABLE IF NOT EXISTS scrap (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
        item_type       TEXT NOT NULL CHECK (item_type IN ('article', 'trend', 'insight', 'idea')),
        item_id         UUID NOT NULL,
        user_tags       TEXT[] DEFAULT '{}',
        memo            TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,

    # --- user_action_log (monthly partition) ---
    """
    CREATE TABLE IF NOT EXISTS user_action_log (
        id              UUID NOT NULL DEFAULT gen_random_uuid(),
        user_id         UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
        action          TEXT NOT NULL,
        item_type       TEXT,
        item_id         UUID,
        dwell_ms        INT,
        meta            JSONB DEFAULT '{}',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (id, created_at)
    ) PARTITION BY RANGE (created_at)
    """,

    # --- Default partition for user_action_log ---
    """
    CREATE TABLE IF NOT EXISTS user_action_log_default
        PARTITION OF user_action_log DEFAULT
    """,

    # --- audit_log (append-only, monthly partition) ---
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id              UUID NOT NULL DEFAULT gen_random_uuid(),
        user_id         UUID,
        action          TEXT NOT NULL,
        target_type     TEXT,
        target_id       UUID,
        ip_address      INET,
        user_agent      TEXT,
        detail          JSONB DEFAULT '{}',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (id, created_at)
    ) PARTITION BY RANGE (created_at)
    """,

    # --- Default partition for audit_log ---
    """
    CREATE TABLE IF NOT EXISTS audit_log_default
        PARTITION OF audit_log DEFAULT
    """,

    # --- ab_experiment ---
    """
    CREATE TABLE IF NOT EXISTS ab_experiment (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name            TEXT UNIQUE NOT NULL,
        description     TEXT,
        variants        JSONB NOT NULL DEFAULT '[]',
        traffic_split   JSONB NOT NULL DEFAULT '{}',
        is_active       BOOLEAN NOT NULL DEFAULT FALSE,
        started_at      TIMESTAMPTZ,
        ended_at        TIMESTAMPTZ,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,

    # --- source_config ---
    """
    CREATE TABLE IF NOT EXISTS source_config (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        source_name     TEXT UNIQUE NOT NULL,
        source_type     TEXT NOT NULL CHECK (source_type IN ('rss', 'api', 'scraper')),
        endpoint_url    TEXT,
        quota_limit     INT NOT NULL DEFAULT 0,
        quota_used      INT NOT NULL DEFAULT 0,
        quota_reset_at  TIMESTAMPTZ,
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,
        config          JSONB NOT NULL DEFAULT '{}',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,

    # --- admin_settings ---
    """
    CREATE TABLE IF NOT EXISTS admin_settings (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        key             TEXT UNIQUE NOT NULL,
        value           JSONB NOT NULL,
        default_value   JSONB NOT NULL,
        description     TEXT,
        updated_by      UUID,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
]

# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

CREATE_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_ng_feed ON news_group (category, locale, score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ng_early ON news_group (early_trend_score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_na_url_hash ON news_article (url_hash)",
    "CREATE INDEX IF NOT EXISTS idx_sns_early ON sns_trend (early_trend_score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_sub_user ON subscription (user_id, expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_ai_role_kw ON action_insight (trend_kw, role, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log (action, created_at DESC)",
]

# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------


VERSION = "001_initial"
DESCRIPTION = "Initial schema — 15 core tables"


async def up(conn: asyncpg.Connection) -> None:
    """Apply migration 001 using an existing connection."""
    for ddl in CREATE_TABLES:
        await conn.execute(ddl)
    for idx in CREATE_INDEXES:
        await conn.execute(idx)
    logger.info("migration_001_complete", tables=len(CREATE_TABLES), indexes=len(CREATE_INDEXES))


async def run_migration(dsn: str) -> None:
    """Apply initial schema migration."""
    conn: asyncpg.Connection = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            for ddl in CREATE_TABLES:
                await conn.execute(ddl)
            for idx in CREATE_INDEXES:
                await conn.execute(idx)
        logger.info(
            "migration_001_complete",
            tables=len(CREATE_TABLES),
            indexes=len(CREATE_INDEXES),
        )
    except Exception as exc:
        logger.error("migration_001_failed", error=str(exc))
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL environment variable is required")
    asyncio.run(run_migration(database_url))
