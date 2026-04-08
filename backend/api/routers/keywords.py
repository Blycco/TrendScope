"""GET /api/v1/trends/{group_id}/keywords/graph endpoint."""

from __future__ import annotations

from collections import Counter, defaultdict

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import Response

from backend.api.schemas.keywords import (
    KeywordEdge,
    KeywordGraphResponse,
    KeywordNode,
)
from backend.common.errors import ErrorCode, error_response
from backend.db.queries.keywords import fetch_group_article_keywords
from backend.processor.shared.cache_manager import get_cached, set_cached
from backend.processor.shared.keyword_extractor import extract_keywords

router = APIRouter(tags=["keywords"])
logger = structlog.get_logger(__name__)

_CACHE_TTL = 1800  # 30 minutes
_MAX_NODES = 30
_MAX_EDGES = 50
_MIN_JACCARD = 0.1


@router.get(
    "/trends/{group_id}/keywords/graph",
    response_model=KeywordGraphResponse,
)
async def get_keyword_graph(
    group_id: str,
    request: Request,
) -> Response:
    """Return keyword co-occurrence graph for a trend group.

    No authentication required (Free tier).
    """
    cache_key = f"keyword_graph:{group_id}"
    try:
        cached = await get_cached(cache_key)
        if cached is not None:
            return Response(content=cached, media_type="application/json")
    except Exception as exc:
        logger.warning("keyword_graph_cache_read_failed", error=str(exc))

    try:
        pool = request.app.state.db_pool
        article_keywords = await fetch_group_article_keywords(pool, group_id=group_id)
    except Exception as exc:
        logger.error("keyword_graph_fetch_failed", group_id=group_id, error=str(exc))
        return error_response(ErrorCode.DB_ERROR, "Failed to fetch keyword graph", status_code=500)

    if not article_keywords:
        body = KeywordGraphResponse(group_id=group_id, nodes=[], edges=[])
        body_bytes = body.model_dump_json().encode()
        try:
            await set_cached(cache_key, body_bytes, _CACHE_TTL)
        except Exception as exc:
            logger.warning("keyword_graph_cache_write_failed", error=str(exc))
        return Response(content=body_bytes, media_type="application/json")

    # Build keyword frequency and article sets for Jaccard computation
    keyword_freq: Counter[str] = Counter()
    keyword_articles: defaultdict[str, set[str]] = defaultdict(set)

    for article_id, terms in article_keywords:
        unique_terms = set(terms)
        for term in terms:
            keyword_freq[term] += 1
        for term in unique_terms:
            keyword_articles[term].add(article_id)

    # Get scores from a combined extraction over frequent terms
    # More efficient: use the keyword_extractor on a combined text representation
    all_terms: list[str] = []
    for _, terms in article_keywords:
        all_terms.extend(terms)

    combined_text = " ".join(all_terms)
    scored_keywords = extract_keywords(combined_text, top_k=100, use_bigrams=False)
    score_map: dict[str, float] = {kw.term: kw.score for kw in scored_keywords}

    # Select top nodes by frequency
    top_keywords = keyword_freq.most_common(_MAX_NODES)
    top_terms = {term for term, _ in top_keywords}

    nodes: list[KeywordNode] = []
    for term, freq in top_keywords:
        nodes.append(
            KeywordNode(
                term=term,
                score=round(score_map.get(term, 0.0), 4),
                frequency=freq,
            )
        )

    # Compute Jaccard similarity for edges
    edges: list[KeywordEdge] = []
    top_terms_list = list(top_terms)
    for i in range(len(top_terms_list)):
        for j in range(i + 1, len(top_terms_list)):
            term_a = top_terms_list[i]
            term_b = top_terms_list[j]
            articles_a = keyword_articles[term_a]
            articles_b = keyword_articles[term_b]
            intersection = len(articles_a & articles_b)
            union = len(articles_a | articles_b)
            if union == 0:
                continue
            jaccard = intersection / union
            if jaccard >= _MIN_JACCARD:
                edges.append(
                    KeywordEdge(
                        source=term_a,
                        target=term_b,
                        weight=round(jaccard, 4),
                    )
                )

    # Keep top edges by weight
    edges.sort(key=lambda e: e.weight, reverse=True)
    edges = edges[:_MAX_EDGES]

    body = KeywordGraphResponse(group_id=group_id, nodes=nodes, edges=edges)
    body_bytes = body.model_dump_json().encode()

    try:
        await set_cached(cache_key, body_bytes, _CACHE_TTL)
    except Exception as exc:
        logger.warning("keyword_graph_cache_write_failed", error=str(exc))

    logger.info(
        "keyword_graph_built",
        group_id=group_id,
        node_count=len(nodes),
        edge_count=len(edges),
    )
    return Response(content=body_bytes, media_type="application/json")
