-- Migration 022: is_hidden column for manual trend suppression
ALTER TABLE news_group
    ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE;
