"""One-off script to detach mismatched articles from news_group.

Recalculates Jaccard similarity between each article's keywords and its
group's keywords. Articles below the threshold get group_id set to NULL.

Usage:
    python -m backend.scripts.fix_group_matching --dry-run
    python -m backend.scripts.fix_group_matching
"""

from __future__ import annotations

import argparse
import asyncio
import os

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

_THRESHOLD = 0.50


def _jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two keyword sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


async def fix_group_matching(*, dry_run: bool = True) -> None:
    """Detach articles whose keyword overlap with their group is below threshold."""
    dsn = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/trendscope")
    pool: asyncpg.Pool = await asyncpg.create_pool(dsn)  # type: ignore[assignment]

    try:
        groups = await pool.fetch(
            "SELECT id, title, keywords FROM news_group WHERE keywords IS NOT NULL"
        )

        detached = 0
        checked = 0

        for group in groups:
            group_id = group["id"]
            group_kw: set[str] = set(group["keywords"] or [])
            group_title_words = {
                w
                for w in (group["title"].split() if group["title"] else [])
                if len(w) >= 2 and not w.isdigit()
            }
            group_kw_combined = group_kw | group_title_words

            articles = await pool.fetch(
                """
                SELECT id, title, locale, category
                FROM news_article
                WHERE group_id = $1
                """,
                group_id,
            )

            for article in articles:
                checked += 1
                article_title = article["title"] or ""
                article_title_words = {
                    w for w in article_title.split() if len(w) >= 2 and not w.isdigit()
                }

                sim = _jaccard(article_title_words, group_kw_combined)

                if sim < _THRESHOLD:
                    if dry_run:
                        logger.info(
                            "would_detach",
                            article_id=str(article["id"]),
                            group_id=str(group_id),
                            jaccard=round(sim, 4),
                            article_title=article_title[:80],
                            group_title=(group["title"] or "")[:80],
                        )
                    else:
                        await pool.execute(
                            "UPDATE news_article SET group_id = NULL WHERE id = $1",
                            article["id"],
                        )
                        logger.info(
                            "detached",
                            article_id=str(article["id"]),
                            group_id=str(group_id),
                            jaccard=round(sim, 4),
                        )
                    detached += 1

        logger.info(
            "fix_complete",
            dry_run=dry_run,
            checked=checked,
            detached=detached,
        )
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix mismatched article-group assignments")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    asyncio.run(fix_group_matching(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
