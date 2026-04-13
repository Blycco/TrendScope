# T-12: 트렌드 상세 페이지 전면 개편
> Branch: feat/trend-ux | Agent: Frontend
> 의존성: T-06 완료, T-10 완료

## BurstGauge 컴포넌트

**파일:** `frontend/src/lib/components/BurstGauge.svelte` (신규)

- [x] 반원 SVG 게이지
- [x] 5단계 색상 (빨강/주황/노랑/초록/회색)
- [x] 수치 레이블 + 단계 레이블
- [x] 마운트 시 ease-out 애니메이션
- [x] i18n 키: `trend.burst.explosive/surge/growing/stable/declining`

## 트렌드 상세 페이지

**파일:** `frontend/src/routes/trends/[id]/+page.svelte`

- [x] "왜 지금인가?" 섹션 (키워드 태그 + 방향 메시지)
- [x] 지난 24시간 기사 delta% 표시 (API 데이터 없음 → 추후)
- [x] platform_distribution 플랫폼별 분포 바 차트 (API 미지원 → 추후)
- [x] BurstGauge 배치
- [x] 차트 순서 재정렬: TrendChart → Sentiment → AspectSentiment → KeywordTimeline → KeywordGraph → Forecast
- [x] 기사 탭: 전체 / 출처별
- [x] 같은 출처 3건↑ → 1건 + "외 N건 더보기" 접기
- [x] 인라인 인사이트 미리보기 ("전체 보기 →" 링크)
- [x] 모바일 고정 액션바 (인사이트/공유/스크랩)
- [x] 데스크탑 액션버튼 (공유/인사이트)

## 완료 기준
- [x] "왜 지금인가?" 섹션 상단 표시
- [x] BurstGauge 애니메이션 동작
- [x] 기사 출처별 탭 전환 동작
- [x] 차트 순서 확인
- [x] 인라인 인사이트 미리보기 표시
- [x] 빌드 통과
