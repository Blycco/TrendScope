"""Stage 4.5: Match articles against recent existing groups. (RULE 06: try/except + structlog)"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg
import structlog

from backend.processor.shared.score_calculator import ScoreInput, ScoreResult, calculate_score
from backend.processor.shared.semantic_clusterer import (
    compute_cosine_similarity,
    encode_texts,
)

logger = structlog.get_logger(__name__)

_EXISTING_GROUP_MATCH_THRESHOLD = 0.50
_EXISTING_GROUP_LIMIT = 500
_EXISTING_GROUP_WINDOW_HOURS = 6


def jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two keyword sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


async def stage_match_existing_groups(
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
            WHERE created_at > now() - make_interval(hours => $1)
            ORDER BY score DESC
            LIMIT $2
            """,
            _EXISTING_GROUP_WINDOW_HOURS,
            _EXISTING_GROUP_LIMIT,
        )
    except Exception as exc:
        logger.warning("pipeline_match_existing_fetch_failed", error=str(exc))
        return articles

    if not group_rows:
        return articles

    # Pre-build keyword sets and batch-encode group title embeddings
    group_data: list[tuple[uuid.UUID, set[str], float, list[float]]] = []
    group_titles: list[str] = []
    for row in group_rows:
        raw_kw: list[str] = list(row["keywords"] or [])
        title_words = {
            w
            for w in (row["title"].split() if row["title"] else [])
            if len(w) >= 2 and not w.isdigit()
        }
        combined: set[str] = set(raw_kw) | title_words
        group_titles.append(row["title"] or "")

    # Batch encode all group titles at once (5-10x faster than per-group)
    group_embeddings = encode_texts(group_titles)

    for idx, row in enumerate(group_rows):
        group_id: uuid.UUID = row["id"]
        raw_kw = list(row["keywords"] or [])
        title_words = {
            w
            for w in (row["title"].split() if row["title"] else [])
            if len(w) >= 2 and not w.isdigit()
        }
        combined = set(raw_kw) | title_words
        group_data.append((group_id, combined, float(row["score"]), group_embeddings[idx]))

    # Batch encode all article texts
    article_texts = [f"{a.get('title', '')} {a.get('body', '')[:500]}" for a in articles]
    article_embeddings = encode_texts(article_texts)

    unmatched: list[dict[str, Any]] = []

    for idx, article in enumerate(articles):
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

            best_group_id: uuid.UUID | None = None
            best_score: float = 0.0
            best_current_score: float = 0.0

            article_embedding = article_embeddings[idx]

            for group_id, group_kws, current_score, group_embedding in group_data:
                j = jaccard(article_kw_set, group_kws)

                # Compute cosine similarity using pre-computed embeddings
                cosine = 0.0
                if article_embedding and group_embedding:
                    cosine = compute_cosine_similarity(article_embedding, group_embedding)

                # Composite: same weights as semantic_clusterer
                sim = 0.50 * cosine + 0.50 * j

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
