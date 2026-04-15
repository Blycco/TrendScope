# C-02 (Frontend): V5/V6 비교 대시보드 UI

> Branch: `feat/v6-compare-ui` | Agent: Frontend
> 의존: C-02 Backend

## 페이지

### `frontend/src/routes/admin/pipeline-compare/+page.svelte` (신규)

- [ ] 상단: 날짜 범위 선택 (기본 최근 14일)
- [ ] 탭 1 "Metrics Timeline":
  - 2축 라인 차트 4개 (silhouette, coherence_npmi, topic_diversity, outlier_ratio)
  - V5 / V6 선 2개씩 비교
  - Chart.js 또는 기존 차트 컴포넌트 재사용
- [ ] 탭 2 "Latest Summary":
  - 최신일자 메트릭 표 (V5 | V6 | Δ)
  - Δ > 0 녹색, < 0 빨강
- [ ] 탭 3 "Cluster Diff Samples":
  - 페어 카드 리스트 (좌 V5 클러스터 / 우 V6 클러스터)
  - 각 카드: auto_label, 기사 상위 3건 제목, keyword_list
  - "C-03 리뷰 보내기" 버튼
- [ ] i18n `admin.pipeline_compare.*` (RULE 13)
- [ ] 빈 데이터 시 placeholder + 안내

### 사이드바 메뉴

- [ ] 어드민 사이드바에 "Pipeline Compare" 추가
- [ ] 네비 i18n

## 테스트

- [ ] Playwright e2e 또는 vitest 컴포넌트 테스트
- [ ] 빈 데이터·에러 처리

## 완료 조건

- [ ] 로컬 렌더링 확인
- [ ] i18n 번역 ko/en
