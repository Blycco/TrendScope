"""메타 트렌드: category 내 news_group들을 keywords Jaccard로 2차 클러스터링.

(RULE 06: try/except + structlog)
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MetaTrend:
    meta_title: str
    keywords: list[str]
    sub_trend_ids: list[str]
    total_score: float


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def cluster_groups_by_keywords(
    groups: list[dict],
    threshold: float = 0.20,
    min_cluster_size: int = 2,
) -> list[MetaTrend]:
    """카테고리별 Greedy Single-Linkage 클러스터링으로 메타 트렌드 생성.

    Args:
        groups: [{id, title, keywords: list[str], score: float, category: str}]
        threshold: Jaccard 유사도 임계값 (기본 0.20)
        min_cluster_size: 최소 클러스터 크기 (기본 2)

    Returns:
        MetaTrend 목록 (total_score DESC 정렬)
    """
    if not groups:
        return []

    # 카테고리별 그룹핑
    by_category: dict[str, list[dict]] = {}
    for g in groups:
        cat = g.get("category", "")
        by_category.setdefault(cat, []).append(g)

    meta_trends: list[MetaTrend] = []

    for _cat, cat_groups in by_category.items():
        if len(cat_groups) < min_cluster_size:
            continue

        # Greedy 클러스터링
        kw_sets = [set(g.get("keywords") or []) for g in cat_groups]
        clusters: list[list[int]] = []
        assigned = [False] * len(cat_groups)

        for i in range(len(cat_groups)):
            if assigned[i]:
                continue
            cluster = [i]
            assigned[i] = True
            for j in range(i + 1, len(cat_groups)):
                if assigned[j]:
                    continue
                # 클러스터 내 임의의 멤버와 Jaccard 계산
                if any(_jaccard(kw_sets[m], kw_sets[j]) >= threshold for m in cluster):
                    cluster.append(j)
                    assigned[j] = True
            clusters.append(cluster)

        for cluster_indices in clusters:
            if len(cluster_indices) < min_cluster_size:
                continue

            cluster_groups = [cat_groups[i] for i in cluster_indices]

            # meta_title: score 최고 그룹
            best = max(cluster_groups, key=lambda g: g.get("score", 0))
            meta_title = best["title"]

            # keywords: 전체 합집합 빈도 상위 10개
            kw_freq: dict[str, int] = {}
            for g in cluster_groups:
                for kw in g.get("keywords") or []:
                    kw_freq[kw] = kw_freq.get(kw, 0) + 1
            top_keywords = sorted(kw_freq, key=lambda k: -kw_freq[k])[:10]

            meta_trends.append(
                MetaTrend(
                    meta_title=meta_title,
                    keywords=top_keywords,
                    sub_trend_ids=[g["id"] for g in cluster_groups],
                    total_score=sum(g.get("score", 0) for g in cluster_groups),
                )
            )

    # total_score DESC 정렬
    meta_trends.sort(key=lambda m: m.total_score, reverse=True)
    return meta_trends
