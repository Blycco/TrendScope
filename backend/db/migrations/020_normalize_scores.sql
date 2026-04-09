-- Migration 020: Normalize existing news_group scores to 0-100 range.
--
-- Before this migration, scores were unbounded (freshness 0-100 + source_weight
-- + article_bonus + social + keyword = potentially > 100).
-- After normalization, all scores should be in [0, 100].
--
-- Strategy: divide each score by the current max score, then multiply by 100.
-- Use LEAST(100, ...) to cap at 100 in case of rounding.

BEGIN;

-- Only run normalization if there are rows and max score > 100
DO $$
DECLARE
    max_score float8;
    normalization_factor float8;
BEGIN
    SELECT MAX(score) INTO max_score FROM news_group;

    IF max_score IS NULL OR max_score = 0 THEN
        RAISE NOTICE 'No scores to normalize (max_score is NULL or 0)';
        RETURN;
    END IF;

    IF max_score <= 100 THEN
        RAISE NOTICE 'Scores already within 0-100 range (max=%), skipping', max_score;
        RETURN;
    END IF;

    normalization_factor := 100.0 / max_score;
    RAISE NOTICE 'Normalizing scores: max=%, factor=%', max_score, normalization_factor;

    UPDATE news_group
    SET score = LEAST(100, ROUND((score * normalization_factor)::numeric, 2))
    WHERE score > 0;
END $$;

COMMIT;
