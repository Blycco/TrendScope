# T-02: 어드민 필터 키워드 관리 페이지 (Frontend)
> Branch: feat/managed-filters | Agent: Frontend
> 의존성: T-02 backend.md 완료 후

## 어드민 필터 키워드 페이지

**파일:** `frontend/src/routes/admin/filter-keywords/+page.svelte` (신규)

- [x] 탭 구성: AI 제안 대기 | 활성 | 전체
  - "AI 제안 대기" 탭: `?source=ai_suggested&is_active=false`
  - "활성" 탭: `?is_active=true`
  - "전체" 탭: 필터 없음
- [x] 테이블 컬럼: keyword | category | source | confidence | is_active | 액션
  - source 배지: ai_suggested → 보라색, system → 회색, manual → 파란색
  - confidence: 0~1 → 퍼센트 표시
- [x] AI 제안 탭 전용: 일괄 승인/거부 체크박스 + 버튼
- [x] 개별 액션: 승인(POST approve), 삭제(DELETE), 카테고리 변경(PATCH)
- [x] 신규 추가 폼: keyword 입력 + category 선택(ad/gambling/adult/obituary/irrelevant/custom) + 추가 버튼
- [x] "캐시 갱신" 버튼 → `POST /admin/filter-keywords/reload`
- [x] 에러 모달 연동 (RULE 12)
- [x] i18n 키 추가 (RULE 13): `admin.filter_keywords.*`
- [x] 어드민 레이아웃 사이드바에 메뉴 항목 추가

## 완료 기준
- [x] 프론트 빌드 통과 (`npm run build`)
- [x] 어드민 사이드바에서 "필터 키워드" 메뉴 노출
- [x] AI 제안 → 승인 플로우 동작 확인
