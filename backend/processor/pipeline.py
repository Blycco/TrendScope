"""Pipeline orchestrator — full news processing pipeline. (RULE 06: try/except + structlog)"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg
import structlog

from backend.processor.shared.cache_manager import set_cached
from backend.processor.shared.dedupe_filter import is_duplicate
from backend.processor.shared.keyword_extractor import Keyword, extract_keywords
from backend.processor.shared.score_calculator import ScoreInput, ScoreResult, calculate_score
from backend.processor.shared.semantic_clusterer import Cluster, ClusterItem, cluster_items
from backend.processor.shared.spam_filter import classify_spam
from backend.processor.shared.text_normalizer import normalize_text

logger = structlog.get_logger(__name__)

_FEED_CACHE_TTL = 300  # 5 minutes


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
    5. SemanticClusterer
    6. ScoreCalculator
    7. Save to news_group + update news_article
    8. Warm cache

    Returns count of news groups saved.
    """
    if not articles:
        return 0

    # Stage 1: Dedupe
    unique_articles = await _stage_dedupe(articles)
    if not unique_articles:
        logger.info("pipeline_all_duplicates", input_count=len(articles))
        return 0

    # Stage 2: Normalize text
    normalized = _stage_normalize(unique_articles)

    # Stage 3: Spam filter
    clean = _stage_spam_filter(normalized)
    if not clean:
        logger.info("pipeline_all_spam", input_count=len(normalized))
        return 0

    # Stage 4: Extract keywords
    with_keywords = _stage_extract_keywords(clean)

    # Stage 5: Semantic clustering
    clusters = _stage_cluster(with_keywords)

    # Stage 6: Score calculation
    scored_clusters = _stage_score(clusters)

    # Stage 7: Save to DB
    saved = await _stage_save(scored_clusters, db_pool)

    # Stage 8: Warm cache
    await _stage_warm_cache(scored_clusters)

    logger.info(
        "pipeline_complete",
        input=len(articles),
        unique=len(unique_articles),
        clean=len(clean),
        clusters=len(clusters),
        saved=saved,
    )
    return saved


async def _stage_dedupe(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 1: Filter duplicates via DedupeFilter."""
    result: list[dict[str, Any]] = []
    for article in articles:
        try:
            is_dup = await is_duplicate(
                url=article.get("url", ""),
                title=article.get("title", ""),
                body=article.get("body", ""),
            )
            if not is_dup:
                result.append(article)
        except Exception as exc:
            logger.warning("pipeline_dedupe_error", url=article.get("url", "?"), error=str(exc))
            result.append(article)
    return result


def _stage_normalize(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 2: Normalize title and body text."""
    result: list[dict[str, Any]] = []
    for article in articles:
        try:
            article["title"] = normalize_text(article.get("title", ""))
            article["body"] = normalize_text(article.get("body", ""))
            if article["title"]:
                result.append(article)
        except Exception as exc:
            logger.warning("pipeline_normalize_error", url=article.get("url", "?"), error=str(exc))
            continue
    return result


def _stage_spam_filter(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 3: Filter spam articles."""
    result: list[dict[str, Any]] = []
    for article in articles:
        try:
            text = f"{article.get('title', '')} {article.get('body', '')}"
            spam_result = classify_spam(text)
            if not spam_result.is_spam:
                result.append(article)
            else:
                logger.debug(
                    "pipeline_spam_filtered",
                    url=article.get("url", "?"),
                    confidence=spam_result.confidence,
                    reasons=spam_result.reasons,
                )
        except Exception as exc:
            logger.warning("pipeline_spam_error", url=article.get("url", "?"), error=str(exc))
            result.append(article)
    return result


def _stage_extract_keywords(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 4: Extract keywords for each article."""
    for article in articles:
        try:
            text = f"{article.get('title', '')} {article.get('body', '')}"
            keywords: list[Keyword] = extract_keywords(text, top_k=10)
            article["keywords"] = [kw.term for kw in keywords]
            article["keyword_importance"] = keywords[0].score if keywords else 0.0
        except Exception as exc:
            logger.warning("pipeline_keyword_error", url=article.get("url", "?"), error=str(exc))
            article["keywords"] = []
            article["keyword_importance"] = 0.0
    return articles


def _stage_cluster(articles: list[dict[str, Any]]) -> list[Cluster]:
    """Stage 5: Group similar articles into clusters."""
    try:
        items: list[ClusterItem] = []
        for article in articles:
            pub_time = article.get("publish_time")
            if isinstance(pub_time, str):
                pub_time = datetime.fromisoformat(pub_time)

            items.append(
                ClusterItem(
                    item_id=article.get("url_hash", str(uuid.uuid4())[:16]),
                    text=f"{article.get('title', '')} {article.get('body', '')[:500]}",
                    keywords=set(article.get("keywords", [])),
                    published_at=pub_time,
                    source_type=article.get("source", ""),
                )
            )

        clusters = cluster_items(items)

        # Attach original article data to clusters
        article_map = {a.get("url_hash", ""): a for a in articles}
        for cluster in clusters:
            cluster_articles = []
            all_member_ids = [cluster.representative.item_id] + [m.item_id for m in cluster.members]
            for member_id in all_member_ids:
                if member_id in article_map:
                    cluster_articles.append(article_map[member_id])
            cluster._articles = cluster_articles  # type: ignore[attr-defined]

        return clusters
    except Exception as exc:
        logger.error("pipeline_cluster_error", error=str(exc))
        return []


def _stage_score(clusters: list[Cluster]) -> list[dict[str, Any]]:
    """Stage 6: Calculate score for each cluster."""
    scored: list[dict[str, Any]] = []
    for cluster in clusters:
        try:
            articles: list[dict[str, Any]] = getattr(cluster, "_articles", [])
            rep_article = articles[0] if articles else {}

            pub_time = rep_article.get("publish_time", datetime.now(tz=timezone.utc))
            if isinstance(pub_time, str):
                pub_time = datetime.fromisoformat(pub_time)

            score_input = ScoreInput(
                published_at=pub_time,
                category=rep_article.get("category", "default"),
                source_type=rep_article.get("source", "default"),
                article_count=len(articles),
                keyword_importance=rep_article.get("keyword_importance", 0.0),
            )
            result: ScoreResult = calculate_score(score_input)

            all_keywords: list[str] = []
            for a in articles:
                all_keywords.extend(a.get("keywords", []))
            unique_keywords = list(dict.fromkeys(all_keywords))[:20]

            scored.append(
                {
                    "cluster": cluster,
                    "articles": articles,
                    "score": result.total,
                    "title": rep_article.get("title", ""),
                    "category": rep_article.get("category", "general"),
                    "locale": rep_article.get("locale", "ko"),
                    "keywords": unique_keywords,
                }
            )
        except Exception as exc:
            logger.warning("pipeline_score_error", error=str(exc))
            continue
    return scored


async def _stage_save(
    scored_clusters: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> int:
    """Stage 7: Save scored clusters to news_group and update news_article."""
    saved = 0
    for item in scored_clusters:
        try:
            group_id = await db_pool.fetchval(
                "INSERT INTO news_group (category, locale, title, score, keywords) "
                "VALUES ($1, $2, $3, $4, $5) RETURNING id",
                item["category"],
                item["locale"],
                item["title"],
                item["score"],
                item["keywords"],
            )

            articles: list[dict[str, Any]] = item.get("articles", [])
            for article in articles:
                url_hash = article.get("url_hash", "")
                if url_hash:
                    await db_pool.execute(
                        "UPDATE news_article SET group_id = $1 WHERE url_hash = $2",
                        group_id,
                        url_hash,
                    )

            saved += 1
        except Exception as exc:
            logger.warning(
                "pipeline_save_error",
                title=item.get("title", "?"),
                error=str(exc),
            )
            continue
    return saved


async def _stage_warm_cache(scored_clusters: list[dict[str, Any]]) -> None:
    """Stage 8: Warm cache for feed keys."""
    try:
        by_feed: dict[str, list[dict[str, Any]]] = {}
        for item in scored_clusters:
            key = f"feed:{item['category']}:{item['locale']}"
            by_feed.setdefault(key, []).append(
                {
                    "title": item["title"],
                    "score": item["score"],
                    "keywords": item["keywords"],
                }
            )

        for cache_key, items in by_feed.items():
            payload = json.dumps(items, ensure_ascii=False, default=str).encode("utf-8")
            await set_cached(cache_key, payload, _FEED_CACHE_TTL)

        logger.debug("pipeline_cache_warmed", keys=len(by_feed))
    except Exception as exc:
        logger.warning("pipeline_cache_warm_error", error=str(exc))
