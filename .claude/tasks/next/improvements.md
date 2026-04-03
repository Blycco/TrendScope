# Next / Improvement Tasks
> 안정화 후 예정 작업 (2026-04-03 기준, 현행화 완료)

## 완료된 작업

### 1. PR 머지 + develop 통합 검증 ✓
- [x] 전체 PR develop 머지 완료
- [x] pytest 837 passed, coverage 74.74%, ruff clean

### 2. 모바일 반응형 보강 ✓
- [x] 메인 내비 햄버거 메뉴 (PR #115)
- [x] 어드민 사이드바 모바일 드로어 (PR #115)
- [x] 필터 버튼 flex-wrap 적용 (이전 PR #93)
- [x] 어드민 테이블 overflow-x-auto + min-w-[640px]
- [x] 프라이싱 카드 반응형 패딩

### 3. 대시보드 차별화 ✓
- [x] StatCards 4종 + SVG 도넛 차트 (PR #107)
- [x] 인기 키워드 태그 클라우드 (PR #113)
- [x] 소스 분포 SVG 스택 바 (PR #113)
- [x] TrendMap 관계 시각화 (PR #113)
- [x] 떠오르는 트렌드 위젯

### 4. 커뮤니티 크롤러 body 추출 ✓
- [x] 3단계 fallback 구현 (newspaper3k → readability-lxml → BeautifulSoup)
- [x] RSS summary < 30자 시 자동 body 추출

### 5. burst detection background job ✓
- [x] early_trend_update.py 15분 주기 재계산 (PR #99)
- [x] burst_job.py 급상승 트렌드 즉시 크롤링 (PR #111)
- [x] burst_crawler.py Google News RSS + Reddit 검색

### 6. crawler/processor 서비스 로깅 연동 ✓
- [x] crawler/main.py: setup_logging("crawler") 적용됨
- [x] processor/main.py: setup_logging("processor") 적용됨
