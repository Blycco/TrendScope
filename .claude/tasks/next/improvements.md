# Next / Improvement Tasks
> 안정화 후 예정 작업 (2026-04-03 기준)

## 1. PR 머지 + develop 통합 검증
- [ ] 11개 OPEN PR (#69, #71, #73, #75, #77, #80, #81, #84, #85, #88, #89) develop 머지
- [ ] 통합 후 pytest + ruff 전체 검증

## 2. 모바일 반응형 보강
- [ ] 필터 버튼 모바일 레이아웃 최적화
- [ ] 어드민 테이블 `overflow-x-auto` + `min-w-[640px]`
- [ ] 프라이싱 카드 모바일 패딩

## 3. 대시보드 차별화
- [ ] Hot 트렌드에 summary 스니펫 표시 (TrendItem에 summary 필드 추가)
- [ ] 카테고리 분포 시각화 (categoryStats derived 활용)
- [ ] 인사이트 미리보기 위젯

## 4. 커뮤니티 크롤러 body 추출
- [ ] 커뮤니티 RSS body 비어있음 → 원문 URL 크롤링하여 본문 텍스트 추출
- [ ] 키워드 품질 향상 검증

## 5. burst detection background job
- [ ] backend/jobs/early_trend_update.py 생성
- [ ] 15분 주기로 최근 48시간 그룹 재계산
- [ ] 기존 detect_burst() + compute_early_trend_score() 활용

## 6. crawler/processor 서비스 로깅 연동
- [ ] backend/processor/main.py: setup_logging("processor") 추가
- [ ] backend/crawler/main.py: setup_logging("crawler") 추가
