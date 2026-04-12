# T-10: TrendCard 전면 개선
> Branch: feat/trend-ux | Agent: Frontend
> 의존성: T-06 완료 후 착수

## TrendCard.svelte 전면 개선

**파일:** `frontend/src/components/TrendCard.svelte`

- [x] 카드 전체 `<a href="/trends/{trend.id}">` 래핑 (전체 클릭 가능)
- [x] 제목: `trend.title`, `line-clamp-2`
- [x] 요약: `trend.summary` 있으면 2줄, 없으면 숨김
- [x] 키워드 뱃지: `trend.keywords.slice(0, 3)` → `#키워드` 스타일
- [x] burst_score > 0.7: 🔥 배지 + 빨간 배경
- [x] burst_score 0.4~0.7: 📈 성장 중
- [x] burst_score < 0.4: ➡️ 유지
- [x] 기사 수: `trend.article_count`건
- [x] i18n 키: `trend.burst.high`, `trend.burst.mid`, `trend.burst.low`
- [x] 비교하기 버튼 (compareStore 연동)
- [x] Sparkline 카드 내 표시 (현재 대시보드 핫트렌드 리스트에서 분리됨)

## 완료 기준
- [x] 카드 전체 영역 클릭 시 상세 페이지 이동
- [x] summary 있는 트렌드: 2줄 요약 표시
- [x] burst_score > 0.7: 빨간 배경 + 🔥 아이콘
- [x] 빌드 통과
