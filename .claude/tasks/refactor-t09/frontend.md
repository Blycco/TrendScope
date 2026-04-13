# T-09: MultiSelect 필터 컴포넌트 + 트렌드 목록 필터 교체
> Branch: feat/trend-ux | Agent: Frontend
> 의존성: T-06 완료 후 착수 (burst_score API 필요)

## MultiSelect 컴포넌트

**파일:** `frontend/src/lib/components/MultiSelect.svelte` (신규)

- [x] 드롭다운 버튼 — 선택 개수 배지 표시
- [x] 외부 클릭 시 닫힘
- [x] 체크박스 + 라벨 목록
- [x] "전체 선택" / "전체 해제" 옵션
- [x] multiple=false → 단일 선택 (라디오 동작)
- [x] Escape 닫기
- [x] Tab 이동 접근성 (a11y)
- [x] i18n 키: `filter.select_all`, `filter.clear_all`

## 트렌드 목록 필터 교체

**파일:** `frontend/src/routes/trends/+page.svelte`

- [x] 카테고리 MultiSelect (multiple)
- [x] 소스 타입 MultiSelect (news/community/sns) — TrendItem에 source_type 필드 없어 제외
- [x] 방향 MultiSelect (multiple, 클라이언트 사이드)
- [x] 기간 단일 선택 (multiple=false)
- [x] 정렬 드롭다운 (score/burst_score/created_at/article_count)
- [x] 선택된 필터 태그 표시 + X 개별 해제
- [x] "전체 초기화" 버튼
- [x] URL 쿼리 파라미터 반영
- [x] i18n 키: `filter.direction.*`, `filter.sort.*`

## 백엔드

- [x] `category` comma-separated → `ANY($N::text[])` 지원
- [x] `sort` 파라미터 추가 + `_SAFE_SORT_COLS` whitelist

## 완료 기준
- [x] MultiSelect 다중 선택 후 URL 파라미터 반영
- [x] 필터 태그 X 클릭 → 해당 필터만 해제
- [x] 빌드 통과
- [x] Tab 키 접근성 확인
