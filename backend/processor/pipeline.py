"""Pipeline orchestrator — thin coordinator that chains processing stages.

Each stage lives in backend.processor.stages.*  (RULE 06: try/except + structlog)
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from backend.processor.stages.cache import stage_warm_cache
from backend.processor.stages.cluster import stage_cluster
from backend.processor.stages.dedupe import stage_dedupe
from backend.processor.stages.keywords import stage_extract_keywords
from backend.processor.stages.match_existing import stage_match_existing_groups
from backend.processor.stages.normalize import stage_normalize
from backend.processor.stages.save import stage_save
from backend.processor.stages.score import compute_early_trend_score, stage_score
from backend.processor.stages.spam_filter import stage_spam_filter
from backend.processor.stages.summarize import stage_summarize

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Backward-compatible aliases for existing tests that import private names
# ---------------------------------------------------------------------------
_stage_dedupe = stage_dedupe
_stage_normalize = stage_normalize
_stage_spam_filter = stage_spam_filter
_stage_extract_keywords = stage_extract_keywords
_stage_cluster = stage_cluster
_stage_score = stage_score
_stage_warm_cache = stage_warm_cache
_compute_early_trend_score = compute_early_trend_score


async def process_articles(
    articles: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> int:
    """Orchestrate the full news processing pipeline.

    Pipeline order (from context/pipeline.md):
    1. DedupeFilter
    2. TextNormalizer
    3. SpamFilter
    4. KeywordExtractor
    5. Match existing groups
    6. SemanticClusterer
    7. ScoreCalculator
    8. Summarize
    9. Save to news_group + update news_article
    10. Warm cache

    Returns count of news groups saved.
    """
    if not articles:
        return 0

    # Stage 1: Dedupe
    unique_articles = await stage_dedupe(articles)
    if not unique_articles:
        logger.info("pipeline_all_duplicates", input_count=len(articles))
        return 0

    # Stage 2: Normalize text
    normalized = stage_normalize(unique_articles)

    # Stage 3: Spam filter (async — loads config from DB/Redis cache per batch)
    clean = await stage_spam_filter(normalized, db_pool)
    if not clean:
        logger.info("pipeline_all_spam", input_count=len(normalized))
        return 0

    # Stage 4: Extract keywords (async — loads stop words & params from DB/Redis per batch)
    with_keywords = await stage_extract_keywords(clean, db_pool)

    # Stage 4.5: Match articles against existing groups (cross-batch grouping)
    unmatched = await stage_match_existing_groups(with_keywords, db_pool)

    # Stage 5: Semantic clustering (only unmatched articles form new clusters)
    clusters = await stage_cluster(unmatched, db_pool)

    # Stage 6: Score calculation
    scored_clusters = stage_score(clusters)

    # Stage 6.5: Generate summaries
    await stage_summarize(scored_clusters, db_pool)

    # Stage 7: Save to DB
    saved = await stage_save(scored_clusters, db_pool)

    # Stage 8: Warm cache
    await stage_warm_cache(scored_clusters)

    logger.info(
        "pipeline_complete",
        input=len(articles),
        unique=len(unique_articles),
        clean=len(clean),
        matched_existing=len(with_keywords) - len(unmatched),
        clusters=len(clusters),
        saved=saved,
    )
    return saved
