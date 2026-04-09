-- Migration 021: news_group에 burst_score 컬럼 추가
ALTER TABLE news_group
    ADD COLUMN IF NOT EXISTS burst_score FLOAT NOT NULL DEFAULT 0.0;
