# Memory — Cross-Session Notes
> Format: {date} | {completed} | {next} | {notes}
> Most recent at top.

## 2026-04-03 | 운영 안정화 및 버그 수정 일괄 진행
- **Completed (open PRs → develop)**:
  - PR #85: 코드 무결성 검증
  - PR #84: 로그 로테이션 구현
  - PR #81: 캐시 zlib 디컴프레션 누락 수정
  - PR #80: Admin sources $effect 무한 루프 수정
  - PR #77: 프로젝트 상태 문서 업데이트
  - PR #75: UX 폴리시
  - PR #73: 에러 로그 시스템
  - PR #71: early_trend_score 항상 0 버그 수정
  - PR #69: Insights UUID→keyword 불일치 수정
- **State**: Phase 1–5 완료, Production Readiness 단계
- **Next**: open PR 리뷰·머지 후 develop → main 릴리스 준비
- **Notes**:
  - 모든 open PR은 develop 브랜치 대상
  - 763 tests / 77.31% coverage (Issue #42 시점 기준)

## 2026-03-18 | 백엔드 API 라우터 + Infra/CI/CD 구현 완료
- **Completed**:
  - Auth 완성 (이메일 인증, 비밀번호 재설정, TOTP 2FA, Kakao OAuth)
  - 유저 기능 라우터 (스크랩, 설정, 이벤트)
  - 결제·구독 라우터 (Security 검토 완료)
  - API main.py 백엔드 라우터 등록
  - infra/nginx/upstream.conf 초기화 + nginx.prod.conf.template (SSL)
  - scripts/switch-blue-green.sh Docker 서비스명 DNS 버그 수정
  - scripts/deploy.sh 블루-그린 전체 배포 스크립트 (7단계 idempotent)
  - .github/workflows/ci.yml (lint, test, build, secret-scan)
  - .github/workflows/deploy.yml (블루-그린 배포 자동화)
- **Branch**: feat/backend-api-routers (origin에 push 완료)
- **Next**: feat/backend-api-routers → **develop** PR 생성 (base: develop, main 아님)
  - develop → main 머지는 Jiny 승인 후 진행
  - 이후: 프론트엔드 SvelteKit UI 구현 or 알고리즘 ML/NLP 스코어링
- **Notes**:
  - upstream.conf :ro 없이 마운트 (switch 스크립트 호환)
  - deploy.sh 필수 환경변수: API_IMAGE_TAG, DOMAIN
  - CI pytest: DATABASE_URL, REDIS_URL, APP_ENV=test
  - CD secrets 필요: REGISTRY_URL/USERNAME/PASSWORD, DEPLOY_HOST/USER/SSH_KEY, DOMAIN
  - 운영 작업 미완: Ubuntu 24.04 서버 세팅, certbot SSL 발급

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
