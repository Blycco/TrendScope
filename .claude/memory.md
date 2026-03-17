# Memory — Cross-Session Notes
> Format: {date} | {completed} | {next} | {notes}
> Most recent at top.

## 2026-03-17 | Phase 2 크롤러·파이프라인·알고리즘 구현 완료
- **Completed**:
  - backend/crawler/ (rss_feeds, quota_guard, robots, extractor, news_crawler, sns_crawler, community_crawler, scheduler)
  - backend/processor/ (pipeline, text_normalizer, dedupe_filter, keyword_extractor, score_calculator, spam_filter, burst, semantic_clusterer)
  - tests/ (238 tests, 71% coverage)
  - requirements.txt Phase 2 의존성 추가
- **Branch**: feat/phase1-foundation (Phase 2 작업 포함, 아직 main 미머지)
- **Next**: Phase 3 착수 전 Orchestrator→Jiny 승인 요청 필요
  - API endpoints (trends feed, user profile, insights)
  - Frontend (SvelteKit dashboard)
  - Auth (JWT + OAuth: Google/Kakao)
- **Notes**:
  - Dev machine: Python 3.9 (macOS system) vs Python 3.11 (Homebrew) — pre-commit uses 3.11
  - timezone.utc 사용 (datetime.UTC 대신) → UP017 global ignore in pyproject.toml
  - scheduler.py 테스트 미작성 (APScheduler 특성상 통합 테스트 필요)
  - sns_crawler.py 테스트 미작성 (0% — Phase 3에서 보완 가능)
