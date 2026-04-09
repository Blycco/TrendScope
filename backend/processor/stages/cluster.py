"""Stage 5: Group similar articles into semantic clusters. (RULE 06: try/except + structlog)"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import asyncpg
import structlog

from backend.processor.shared.semantic_clusterer import (
    Cluster,
    ClusterConfig,
    ClusterItem,
    cluster_items,
    refine_clusters,
)

logger = structlog.get_logger(__name__)

_D = ClusterConfig()  # Default config reference


async def _load_config(db_pool: asyncpg.Pool) -> ClusterConfig:
    """Load cluster config from DB/Redis; falls back to defaults on error."""
    from backend.processor.shared.config_loader import get_setting

    return ClusterConfig(
        cosine_weight=float(await get_setting(db_pool, "cluster.cosine_weight", _D.cosine_weight)),
        jaccard_weight=float(
            await get_setting(db_pool, "cluster.jaccard_weight", _D.jaccard_weight)
        ),
        temporal_weight=float(
            await get_setting(db_pool, "cluster.temporal_weight", _D.temporal_weight)
        ),
        source_weight=float(await get_setting(db_pool, "cluster.source_weight", _D.source_weight)),
        jaccard_early_filter=float(
            await get_setting(db_pool, "cluster.jaccard_early_filter", _D.jaccard_early_filter)
        ),
        threshold=float(await get_setting(db_pool, "cluster.threshold", _D.threshold)),
        outlier_sigma=float(await get_setting(db_pool, "cluster.outlier_sigma", _D.outlier_sigma)),
        temporal_decay_hours=float(
            await get_setting(db_pool, "cluster.temporal_decay_hours", _D.temporal_decay_hours)
        ),
    )


async def stage_cluster(
    articles: list[dict[str, Any]],
    db_pool: asyncpg.Pool,
) -> list[Cluster]:
    """Stage 5: Group similar articles into clusters."""
    try:
        try:
            config = await _load_config(db_pool)
        except Exception as cfg_exc:
            logger.warning("cluster_config_load_failed", error=str(cfg_exc))
            config = _D

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

        clusters = cluster_items(items, config=config)
        clusters = refine_clusters(clusters, sigma=config.outlier_sigma)

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
