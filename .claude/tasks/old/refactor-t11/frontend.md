# T-11: 대시보드 전면 개편 (Bento Grid + 역할별 추천)
> Branch: feat/trend-ux | Agent: Frontend
> 의존성: T-10 완료 후 착수

## BentoTrendGrid 컴포넌트

**파일:** `frontend/src/lib/components/BentoTrendGrid.svelte` (신규)

- [x] 1위 카드 (col-span-2 row-span-2 대형): 제목 + 요약 + burst 배지
- [x] 2~5위 카드 (소형): 제목 + 방향 + 점수
- [x] 모바일: 단순 세로 리스트 fallback
- [x] 각 카드 클릭 → `/trends/{id}`

## 대시보드 +page.svelte 개편

- [x] Hot Trends 섹션 → BentoTrendGrid 교체
- [x] "전체 보기 →" 링크
- [x] 역할별 추천 섹션 (로그인 + role 있을 때)
- [x] 미로그인 CTA → 역할 설정 안내
- [x] Early Trends desc2 추가 ("아직 메인스트림 아님. 선착자 우위 가능")

### 미완료
- [x] KeywordCloud 🔥 아이콘 (burst_score 높은 트렌드의 키워드)
- [x] KeywordCloud NEW 배지 (24h 내 첫 등장 키워드)
- [x] StatCard 순서 변경 (총 트렌드 | Early | 뉴스 | 평균)

## 완료 기준
- [x] Bento Grid 1위 대형 카드 표시
- [x] 역할 설정된 유저에게 맞춤 섹션 표시
- [x] KeywordCloud 🔥 아이콘 표시
- [x] 빌드 통과
