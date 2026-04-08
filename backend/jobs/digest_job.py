"""Daily digest job: send Reddit question digests to subscribed users."""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from backend.common.email import send_html_email
from backend.db.queries.digest import get_digest_subscribers, get_recent_reddit_questions

logger = structlog.get_logger(__name__)

_QUESTION_WORDS_EN = frozenset({"how", "why", "what", "when", "where", "which", "who"})
_QUESTION_WORDS_KO = ("어떻게", "왜", "무엇", "언제", "어디", "누가")


def is_question_post(title: str) -> bool:
    """Return True if the title looks like a question."""
    if "?" in title:
        return True
    title_lower = title.lower()
    first_word = title_lower.split()[0] if title_lower.split() else ""
    if first_word in _QUESTION_WORDS_EN:
        return True
    return any(kw in title_lower for kw in _QUESTION_WORDS_KO)


def build_digest_html(
    keyword_questions: dict[str, list[dict[str, Any]]],
) -> str:
    """Build HTML body for the digest email.

    Note: permalink is not stored in sns_trend, so titles are rendered as
    plain list items without hyperlinks.
    """
    sections: list[str] = []
    for keyword, questions in keyword_questions.items():
        items_html = "".join(
            f'<li style="margin-bottom:4px;">{q["title"]}</li>' for q in questions[:10]
        )
        if items_html:
            sections.append(
                f'<h3 style="color:#333;margin-top:20px;">{keyword}</h3>'
                f'<ul style="padding-left:20px;">{items_html}</ul>'
            )
    body = "\n".join(sections) if sections else "<p>오늘의 관련 질문이 없습니다.</p>"
    return (
        f'<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;">'
        f'<h2 style="color:#1a73e8;">TrendScope 일일 Reddit 질문 다이제스트</h2>'
        f"{body}"
        f'<hr style="margin-top:30px;">'
        f'<p style="color:#999;font-size:12px;">'
        f"수신 거부는 TrendScope 설정 페이지에서 변경하세요.</p>"
        f"</body></html>"
    )


async def run_daily_digest(db_pool: asyncpg.Pool) -> int:
    """Run daily digest: collect questions and send emails.

    Returns the number of emails successfully sent.
    """
    try:
        subscribers = await get_digest_subscribers(db_pool)
        if not subscribers:
            logger.info("digest_no_subscribers")
            return 0

        records = await get_recent_reddit_questions(db_pool)
        if not records:
            logger.info("digest_no_reddit_data")
            return 0

        # Filter to question-style posts
        questions: list[dict[str, Any]] = []
        for rec in records:
            title = rec["keyword"]
            if is_question_post(title):
                questions.append({"title": title})

        if not questions:
            logger.info("digest_no_questions_after_filter")
            return 0

        # Build per-user keyword map
        user_map: dict[str, dict[str, Any]] = {}
        for row in subscribers:
            uid = row["user_id"]
            if uid not in user_map:
                user_map[uid] = {"email": row["email"], "keywords": {}}
            user_map[uid]["keywords"][row["keyword"]] = []

        # Match questions to keywords (case-insensitive substring match)
        for q in questions:
            title_lower = q["title"].lower()
            for udata in user_map.values():
                for kw in udata["keywords"]:
                    if kw.lower() in title_lower:
                        udata["keywords"][kw].append(q)

        sent = 0
        for _uid, udata in user_map.items():
            matched = {k: v for k, v in udata["keywords"].items() if v}
            if not matched:
                continue
            html = build_digest_html(matched)
            ok = await send_html_email(
                udata["email"],
                "TrendScope 오늘의 Reddit 질문 모음",
                html,
            )
            if ok:
                sent += 1

        logger.info("digest_completed", sent=sent, total_users=len(user_map))
        return sent
    except Exception as exc:
        logger.error("run_daily_digest_failed", error=str(exc))
        return 0
