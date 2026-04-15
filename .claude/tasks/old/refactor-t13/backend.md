# T-13: 인사이트 페이지 내용 강화
> Branch: feat/trend-ux | Agent: Backend + Frontend
> 의존성: T-06 완료

## LLM 프롬프트 개선 (backend)

**파일:** `backend/api/routers/insights.py`, 스키마 확장

### 마케터
- [x] 스키마에 `timing_recommendation`, `channel_opportunities`, `competitor_note`, `action_items` 추가
- [x] 프롬프트에 새 필드 요청 추가

### 크리에이터
- [x] 스키마에 `recommended_format`, `title_suggestions`, `hashtag_suggestions`, `best_upload_time`, `action_items` 추가

### 사업주
- [x] 스키마에 `market_opportunity`, `consumer_sentiment`, `product_hint`, `action_items` 추가

### 공통
- [x] `sns_post_draft: str` 필드 추가
- [x] 스키마 파일 (`backend/api/schemas/insights.py`) 확장
- [x] `_parse_content` 함수 업데이트

## 인사이트 페이지 UI 개선 (frontend)

**파일:** `frontend/src/routes/trends/[id]/insights/+page.svelte`

- [x] 섹션별 카드 구조 (getSections 함수)
- [x] 섹션 전체 복사 버튼
- [x] 개별 항목 호버 복사 버튼
- [x] SNS 초안 카드 (green 강조)
- [x] 크리에이터 타이밍 섹션
- [x] 생성 시각 표시 + 캐시 여부
- [x] timing_recommendation 박스
- [x] channel_opportunities 목록
- [x] action_items 섹션 (역할별)
- [x] i18n 키: `insights.marketer.*`, `insights.creator.*`, `insights.owner.*`

## 완료 기준
- [x] 복사 버튼 클릭 → 클립보드 복사 동작
- [x] SNS 초안 텍스트 표시
- [x] 새 스키마 필드 반영 확인
- [x] pytest 스키마 검증 통과 (76% coverage)
- [x] 빌드 통과
