-- Migration 023: growth_type classification column (spike / growth / unknown)
ALTER TABLE news_group
    ADD COLUMN IF NOT EXISTS growth_type TEXT NOT NULL DEFAULT 'unknown';
