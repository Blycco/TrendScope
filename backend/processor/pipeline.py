"""Pipeline orchestrator — full news processing pipeline. (RULE 06: try/except + structlog)"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import asyncpg
import structlog

from backend.processor.shared.ai_config import get_ai_config
from backend.processor.shared.ai_summarizer import summarize
from backend.processor.shared.cache_manager import set_cached
from backend.processor.shared.dedupe_filter import is_duplicate
from backend.processor.shared.keyword_extractor import Keyword, extract_keywords
from backend.processor.shared.score_calculator import ScoreInput, ScoreResult, calculate_score
from backend.processor.shared.semantic_clusterer import (
    Cluster,
    ClusterItem,
    cluster_items,
    compute_cosine_similarity,
    encode_text,
    refine_clusters,
)
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

    # Stage 4.5: Match articles against existing groups (cross-batch grouping)
    unmatched = await _stage_match_existing_groups(with_keywords, db_pool)

    # Stage 5: Semantic clustering (only unmatched articles form new clusters)
    clusters = _stage_cluster(unmatched)

    # Stage 6: Score calculation
    scored_clusters = _stage_score(clusters)

    # Stage 6.5: Generate summaries
    await _stage_summarize(scored_clusters, db_pool)

    # Stage 7: Save to DB
    saved = await _stage_save(scored_clusters, db_pool)

    # Stage 8: Warm cache
    await _stage_warm_cache(scored_clusters)

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


_EXISTING_GROUP_MATCH_THRESHOLD = 0.50
_EXISTING_GROUP_LIMIT = 500


def _jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two keyword sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


async def _stage_match_existing_groups(
    articles: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> list[dict[str, Any]]:
    """Stage 4.5: Match articles against recent existing groups.

    Assigns matching articles to an existing group via Jaccard keyword
    similarity and returns the remaining unmatched articles for new clustering.
    """
    try:
        group_rows = await db_pool.fetch(
            """
            SELECT id, title, keywords, score, category
            FROM news_group
            WHERE created_at > now() - interval '48 hours'
            ORDER BY score DESC
            LIMIT $1
            """,
            _EXISTING_GROUP_LIMIT,
        )
    except Exception as exc:
        logger.warning("pipeline_match_existing_fetch_failed", error=str(exc))
        return articles

    if not group_rows:
        return articles

    # Pre-build keyword sets and embeddings for each existing group
    import uuid as _uuid  # noqa: PLC0415

    group_data: list[tuple[_uuid.UUID, set[str], float, str]] = []
    for row in group_rows:
        group_id: _uuid.UUID = row["id"]
        raw_kw: list[str] = list(row["keywords"] or [])
        title_words = {
            w
            for w in (row["title"].split() if row["title"] else [])
            if len(w) >= 2 and not w.isdigit()
        }
        combined: set[str] = set(raw_kw) | title_words
        group_title: str = row["title"] or ""
        group_data.append((group_id, combined, float(row["score"]), group_title))

    unmatched: list[dict[str, Any]] = []

    for article in articles:
        try:
            article_kw_set: set[str] = set(article.get("keywords", []))
            title_words = {
                w
                for w in (article.get("title", "").split() if article.get("title") else [])
                if len(w) >= 2 and not w.isdigit()
            }
            article_kw_set |= title_words
            if not article_kw_set:
                unmatched.append(article)
                continue

            best_group_id: _uuid.UUID | None = None
            best_score: float = 0.0
            best_current_score: float = 0.0

            article_text = f"{article.get('title', '')} {article.get('body', '')[:500]}"
            article_embedding = encode_text(article_text)

            for group_id, group_kws, current_score, group_title in group_data:
                jaccard = _jaccard(article_kw_set, group_kws)

                # Compute cosine similarity if embeddings available
                cosine = 0.0
                if article_embedding is not None:
                    group_embedding = encode_text(group_title)
                    if group_embedding is not None:
                        cosine = compute_cosine_similarity(article_embedding, group_embedding)

                # Composite: same weights as semantic_clusterer
                sim = 0.50 * cosine + 0.50 * jaccard

                if sim > best_score:
                    best_score = sim
                    best_group_id = group_id
                    best_current_score = current_score

            if best_group_id is not None and best_score >= _EXISTING_GROUP_MATCH_THRESHOLD:
                url_hash = article.get("url_hash", "")
                if url_hash:
                    await db_pool.execute(
                        "UPDATE news_article SET group_id = $1 WHERE url_hash = $2",
                        best_group_id,
                        url_hash,
                    )

                # Recalculate group score: increment article_count by 1
                try:
                    article_count_row = await db_pool.fetchrow(
                        "SELECT COUNT(*) AS cnt FROM news_article WHERE group_id = $1",
                        best_group_id,
                    )
                    new_article_count = int(article_count_row["cnt"]) if article_count_row else 1

                    pub_time = article.get("publish_time", datetime.now(tz=timezone.utc))
                    if isinstance(pub_time, str):
                        pub_time = datetime.fromisoformat(pub_time)

                    score_input = ScoreInput(
                        published_at=pub_time,
                        category=article.get("category", "general"),
                        source_type=article.get("source", "default"),
                        article_count=new_article_count,
                        keyword_importance=article.get("keyword_importance", 0.0),
                    )
                    new_score_result: ScoreResult = calculate_score(score_input)
                    new_score = max(best_current_score, new_score_result.total)

                    # Recalculate early_trend_score based on updated article count
                    early_score = min(1.0, new_article_count / 10.0) * 0.4 + 0.3

                    await db_pool.execute(
                        "UPDATE news_group SET score = $1, early_trend_score = $2, "
                        "updated_at = now() WHERE id = $3",
                        new_score,
                        early_score,
                        best_group_id,
                    )
                except Exception as score_exc:
                    logger.warning(
                        "pipeline_match_score_update_failed",
                        group_id=best_group_id,
                        error=str(score_exc),
                    )

                logger.debug(
                    "pipeline_article_matched_existing_group",
                    url_hash=url_hash,
                    group_id=best_group_id,
                    jaccard=best_score,
                )
            else:
                unmatched.append(article)

        except Exception as exc:
            logger.warning(
                "pipeline_match_existing_error",
                url=article.get("url", "?"),
                error=str(exc),
            )
            unmatched.append(article)

    logger.info(
        "pipeline_match_existing_complete",
        total=len(articles),
        matched=len(articles) - len(unmatched),
        unmatched=len(unmatched),
    )
    return unmatched


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
        clusters = refine_clusters(clusters)

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


def _compute_early_trend_score(articles: list[dict[str, Any]]) -> float:
    """Compute a lightweight early trend score from cluster article data.

    Combines three signals:
    - velocity: normalized article count (more articles = faster growing)
    - source_diversity: ratio of unique sources (broader coverage = stronger signal)
    - recency: how recent the newest article is (newer = more likely emerging)

    Returns a score in [0.0, 1.0].
    """
    if not articles:
        return 0.0

    # Velocity: article count normalized (10+ articles → 1.0)
    velocity = min(1.0, len(articles) / 10.0)

    # Source diversity: unique sources / total articles
    sources = {a.get("source", "") for a in articles if a.get("source")}
    source_diversity = len(sources) / max(len(articles), 1)

    # Recency: newest article within last 6 hours → 1.0, 48h+ → 0.0
    now = datetime.now(tz=timezone.utc)
    newest_hours = 48.0
    for a in articles:
        pub_time = a.get("publish_time")
        if isinstance(pub_time, str):
            pub_time = datetime.fromisoformat(pub_time)
        if isinstance(pub_time, datetime):
            hours_ago = (now - pub_time).total_seconds() / 3600
            newest_hours = min(newest_hours, max(0.0, hours_ago))
    recency = max(0.0, 1.0 - (newest_hours / 48.0))

    return round(0.4 * velocity + 0.3 * source_diversity + 0.3 * recency, 4)


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

            keyword_counter: Counter[str] = Counter()
            for a in articles:
                for kw in a.get("keywords", []):
                    if not kw.isdigit() and len(kw) >= 2:
                        keyword_counter[kw] += 1
            unique_keywords = [kw for kw, _ in keyword_counter.most_common(20)]

            top_keywords = unique_keywords[:3]
            group_title = " · ".join(top_keywords) if top_keywords else rep_article.get("title", "")

            early_score = _compute_early_trend_score(articles)

            scored.append(
                {
                    "cluster": cluster,
                    "articles": articles,
                    "score": result.total,
                    "early_trend_score": early_score,
                    "title": group_title,
                    "category": rep_article.get("category", "general"),
                    "locale": rep_article.get("locale", "ko"),
                    "keywords": unique_keywords,
                }
            )
        except Exception as exc:
            logger.warning("pipeline_score_error", error=str(exc))
            continue
    return scored


_SUMMARY_PROMPT = (
    "Summarize the following news articles into exactly 3 concise sentences in Korean. "
    "Focus on what happened, who is involved, and why it matters."
)


async def _stage_summarize(
    scored_clusters: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> None:
    """Stage 6.5: Generate AI summary for each cluster."""
    try:
        config = await get_ai_config(db_pool)
    except Exception as exc:
        logger.warning("pipeline_ai_config_failed", error=str(exc))
        return

    for item in scored_clusters:
        try:
            articles: list[dict[str, Any]] = item.get("articles", [])
            combined = "\n\n".join(
                f"[{a.get('source', '')}] {a.get('title', '')}\n{a.get('body', '')[:500]}"
                for a in articles[:5]
            )
            if not combined.strip():
                item["summary"] = None
                continue

            summary_text, degraded = await summarize(combined, _SUMMARY_PROMPT, config, db_pool)
            item["summary"] = summary_text.strip() if summary_text else None
            if degraded:
                logger.debug("pipeline_summary_degraded", title=item.get("title", "?"))
        except Exception as exc:
            logger.warning("pipeline_summary_error", title=item.get("title", "?"), error=str(exc))
            item["summary"] = None


async def _stage_save(
    scored_clusters: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> int:
    """Stage 7: Save scored clusters to news_group and update news_article."""
    saved = 0
    for item in scored_clusters:
        try:
            group_id = await db_pool.fetchval(
                "INSERT INTO news_group "
                "(category, locale, title, summary, score, early_trend_score, keywords) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
                item["category"],
                item["locale"],
                item["title"],
                item.get("summary"),
                item["score"],
                item.get("early_trend_score", 0.0),
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
