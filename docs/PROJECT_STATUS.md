# TrendScope 프로젝트 현황 (2026-04-03 기준)

## 아키텍처 개요

```
[Nginx] → [FastAPI API] → [PostgreSQL 15]
                        → [Redis 7]
[Crawler] → [Processor Pipeline] → [PostgreSQL]
[SvelteKit Frontend]
```

| 서비스 | 기술 스택 | 역할 |
|--------|-----------|------|
| API | FastAPI + asyncpg | REST API, 인증, 플랜 게이트 |
| Crawler | Python + RSS/커뮤니티/뉴스 | 데이터 수집 |
| Processor | Pipeline (Dedupe → Normalize → Spam → Keywords → Cluster → Score → Save) | 데이터 가공 |
| Frontend | SvelteKit + Tailwind CSS | 사용자 UI |
| Infra | Docker Compose + Nginx | 배포, 리버스 프록시 |

---

## 기능 완성도

| 기능 | 상태 | 비고 |
|------|------|------|
| 트렌드 피드 (카테고리/시간 필터) | 완료 | cursor pagination |
| 뉴스 피드 (카테고리/소스/시간 필터) | 완료 | cursor pagination |
| 트렌드 상세 (기사 목록 + 원문 링크) | 완료 | PR #67 |
| 액션 인사이트 (AI 생성) | 완료 | Pro+ 전용, TextRank fallback |
| 콘텐츠 아이디어 (AI 생성) | 완료 | Pro+ 전용 |
| 키워드 트래커 | 완료 | |
| 브랜드 모니터링 | 완료 | Business+ 전용 |
| PDF/CSV 내보내기 | 완료 | PR #65 |
| 국내/해외 locale 필터 | 완료 | PR #67 |
| 인증 (이메일 + Google OAuth) | 완료 | |
| 구독/결제 (토스페이먼츠 mock) | 완료 | mock 모드 |
| 어드민 패널 | 완료 | 유저/소스/AI설정/감사로그/구독/쿼타 |
| 에러 영구 기록 시스템 | PR 진행 중 | PR #73 |
| 스켈레톤 로딩 UI | PR 진행 중 | PR #75 |
| EarlyBadge (초기 트렌드 감지) | 수정됨 | score < 0.3일 때 숨김 처리 |
| early_trend_score 파이프라인 통합 | PR 진행 중 | PR #71 |
| 인사이트 UUID→keyword 수정 | PR 진행 중 | PR #69 |

---

## 데이터 품질 현황

| 지표 | 값 | 비고 |
|------|-----|------|
| news_group 총 수 | 3,075 | |
| AI 요약 보유 그룹 | 317 (10.3%) | AI 요약 커버리지 낮음 |
| early_trend_score > 0 | 0 (0%) | PR #71에서 수정 예정 |
| 제목 정제 완료 | 98건 | migration 016 적용 |
| 키워드 정리 완료 | 299건 | 숫자/단문자 키워드 제거 |
| 커뮤니티 RSS body | 대부분 비어있음 | 키워드가 제목에만 의존 |

---

## 테스트 현황

| 브랜치 | 테스트 수 | 커버리지 |
|--------|-----------|----------|
| develop | 781 passed | 74.15% |
| fix/insights-uuid-keyword | 790 passed | 74.24% |
| fix/early-trend-score | 786 passed | 74.20% |
| feat/error-log-system | 786 passed | 74.11% |
| feat/ux-polish | 781 passed | 74.15% |

---

## Open PR 현황

| PR | 브랜치 | 내용 |
|----|--------|------|
| #69 | fix/insights-uuid-keyword | 인사이트 UUID→keyword 버그 수정 |
| #71 | fix/early-trend-score | early_trend_score 파이프라인 통합 |
| #73 | feat/error-log-system | 에러 영구 기록 시스템 |
| #75 | feat/ux-polish | i18n, 스켈레톤 UI, 콘텐츠 가이드 |

---

## 알려진 이슈

1. **커뮤니티 RSS body 비어있음** — 키워드 추출이 제목에만 의존. 원문 크롤링 필요 (미정)
2. **AI 요약 커버리지 10%** — 대부분 그룹에 요약 없음. AI 비용/속도 제약
3. **어드민 JWT 갱신** — DB에서 role 변경 후 재로그인 필요 (JWT에 role 포함)
4. **대시보드 차별화 부족** — 트렌드/뉴스 목록과 유사, 인사이트 스니펫 미표시
5. **접근성(ARIA)** — 최소 수준, 스크린 리더 지원 부족
6. **모바일 반응형** — 필터 버튼/어드민 테이블 모바일 미최적화
