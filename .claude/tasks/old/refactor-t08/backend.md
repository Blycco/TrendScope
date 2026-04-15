# T-08: 어드민 트렌드 품질 모니터링
> Branch: feat/admin-ui | Agent: Backend + Frontend
> 의존성: T-06 완료 후 착수 (burst_score 컬럼 필요)

## 어드민 트렌드 품질 API

**파일:** `backend/api/routers/admin/trend_quality.py` (신규)

- [x] `GET /admin/trend-quality/pipeline-stats` — 오늘 파이프라인 통계
- [x] `GET /admin/trend-quality/top-trends` — 랭킹 상위 10개 + score breakdown
- [x] `POST /admin/trend-quality/hide/{group_id}` — 트렌드 수동 숨기기
- [x] require_admin_role(), handle_errors 적용

## 어드민 트렌드 품질 페이지

**파일:** `frontend/src/routes/admin/trend-quality/+page.svelte` (신규)

- [x] 섹션 1: 오늘 파이프라인 현황 카드 (30초 자동갱신)
- [x] 섹션 2: 현재 랭킹 상위 10개 테이블 (1분 갱신)
- [x] "숨기기" 버튼
- [x] 어드민 사이드바에 "트렌드 품질" 메뉴 추가
- [x] i18n 키: `admin.trend_quality.*`
- [x] 필터링 이유 분포 차트 (파이/바)
- [x] score breakdown 호버 툴팁

## is_hidden 마이그레이션

- [x] `ALTER TABLE news_group ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE;`
- [x] 트렌드 목록 API에 `AND ng.is_hidden = FALSE` 필터 추가

## 완료 기준
- [x] 오늘 필터링 통계 정상 표시
- [x] 상위 10개 트렌드 표시
- [x] score breakdown 툴팁 표시
- [x] "숨기기" 클릭 후 피드에서 해당 트렌드 미노출 확인
- [x] 빌드 및 ruff 통과
