"""Stage 5: Group similar articles into semantic clusters. (RULE 06: try/except + structlog)"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog

from backend.processor.shared.semantic_clusterer import (
    Cluster,
    ClusterItem,
    cluster_items,
    refine_clusters,
)

logger = structlog.get_logger(__name__)


def stage_cluster(articles: list[dict[str, Any]]) -> list[Cluster]:
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
