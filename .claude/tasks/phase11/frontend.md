# Phase 11 / Frontend — 트렌드 UX 개선
> Agent: Frontend | Type: Refactor | Ref: #128

## 배경

현재 트렌드 카드는 뉴스 기사 헤드라인이 그대로 제목으로 표시되고,
키워드는 제목에서 단어를 쪼갠 수준("살지만", "아프다…", "넘으려면").
상세 페이지는 무관한 기사 body_snippet만 나열.
전체 카드가 "하락 중"으로 표시되는 버그도 존재.

---

## Tasks

### 1. 트렌드 카드 키워드 기반 리디자인
- [ ] 카드 제목 = 핵심 키워드 (백엔드 Task 7에서 `news_group.title` 변경 후 연동)
- [ ] 카드 하위 정보: 관련 기사 수 + 카테고리 + 점수
- [ ] EarlyBadge 유지
- [ ] 키워드 태그 목록은 관련 서브 키워드로 표시 (제목 어절 X)

**현황**: `TrendCard.svelte`에서 `trend.title` (기사 헤드라인) 표시 중
**영향 파일**: `frontend/src/components/TrendCard.svelte`

### 2. 트렌드 상세 페이지 개선 — 주식/코인 차트 스타일 시계열 그래프
- [ ] 현재 body_snippet 나열 제거 → 소스 링크 + 차트 + 키워드 중심 구성

#### 2-1. 백엔드: 시계열 데이터 기반 구축
- [ ] `trend_score_history` 테이블 신규 생성
  - `group_id (FK)`, `score`, `article_count`, `recorded_at` (시간별 스냅샷)
- [ ] `early_trend_update.py` (15분 주기) 또는 별도 job에서 `news_group` score를 주기적으로 기록
- [ ] API 엔드포인트 추가: `GET /api/v1/trends/{id}/history?range=1h|6h|24h|7d`
  - 응답: `{ points: [{ time: ISO8601, score: float, article_count: int }] }`
- [ ] 기존 `news_article.publish_time` 기반 시간별 기사 수 집계 쿼리도 추가

#### 2-2. 프론트: 주식/코인 차트 스타일 인터랙티브 차트
- [ ] 차트 라이브러리 선택: `lightweight-charts` (TradingView 오픈소스) 또는 SVG 자체 구현
- [ ] 기능 요구사항:
  - 라인 차트 (score 추이) + 하단 바 차트 (기사 수/언급량)
  - 기간 선택 탭: 1시간 / 6시간 / 24시간 / 7일
  - 마우스 호버 시 툴팁: 시간, score, 기사 수
  - 상승 구간 = 초록, 하락 구간 = 빨강 (코인 차트처럼)
  - 현재 score vs 24시간 전 대비 변동률(%) 표시
- [ ] 반응형: 모바일에서도 터치 스크롤 가능

#### 2-3. 소스 링크 목록
- [ ] 기사 제목 + 출처 + 발행일 (현재 구조 유지, body_snippet 제거)
- [ ] 시간순 정렬

**현황**: 그래프 없음. 차트 라이브러리 미설치. 시계열 DB/API 미구현. 전부 신규 구현 필요.
**영향 파일**: 
  - 백엔드: migration, `backend/db/queries/trends.py`, `backend/api/routers/trends.py`, job
  - 프론트: `frontend/src/routes/trends/[id]/+page.svelte`, 차트 컴포넌트 신규

### 3. 트렌드 방향 표시 수정
- [ ] "하락 중" 전부 표시 버그 원인 조사
  - `status.declining` i18n 키 존재하나 main 브랜치 코드에 렌더링 지점 없음
  - 배포 빌드와 main 브랜치 불일치 가능성 점검
- [ ] score 변동 기반 방향 로직 구현
  - 백엔드: `news_group`에 `previous_score` 컬럼 또는 score 히스토리 테이블 추가
  - API 응답에 `score_change` (양수=상승, 0=유지, 음수=하락) 필드 추가
  - 프론트: TrendCard/상세에 상승(↑)/유지(→)/하락(↓) 아이콘 + 색상 표시
- [ ] `status.declining` / `status.rising` / `status.stable` i18n 키 활용

**현황**: direction 로직 자체가 없음. 알고리즘 Task 8과 연계
**영향 파일**: `frontend/src/components/TrendCard.svelte`, `frontend/src/components/EarlyBadge.svelte`, 백엔드 스키마

---

## 우선순위

| 순위 | Task | 의존성 |
|---|---|---|
| 1 | 트렌드 카드 리디자인 | Algorithm Task 7 (그룹 제목 키워드 전환) |
| 2 | 상세 페이지 개선 | 없음 (기존 articles 데이터로 시작 가능) |
| 3 | 방향 표시 수정 | 백엔드 score_history 스키마 추가 |

## 검증 기준
- 트렌드 카드에 키워드가 제목으로 표시되는지 확인
- 상세 페이지에 소스 링크 + 그래프 표시되는지 확인
- 방향 표시가 score 변동에 따라 정확히 전환되는지 확인
