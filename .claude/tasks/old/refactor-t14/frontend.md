# T-14: 키워드 트래커 UX + 공유 개선 + 온보딩 강화 + 빈 상태
> Branch: feat/engagement | Agent: Frontend
> 의존성: T-12, T-13 완료 후 착수

## 키워드 트래커 UX 개선

**파일:** `frontend/src/routes/tracker/+page.svelte`

- [x] 키워드 카드 UI (급상승/일일 알림 ON/OFF 토글)
- [x] 삭제 버튼
- [x] "트렌드 상세 →" 링크
- [x] 키워드별 현재 트렌드 상태 뱃지 (GET /trends?keyword={kw}&limit=1)
- [x] Pro 미가입 5개 초과 시 PlanGate 모달
- [x] 빈 상태 메시지

## 공유 페이지 CTA 추가

**파일:** `frontend/src/routes/shared/[token]/+page.svelte`

- [x] 페이지 하단 TrendScope 소개 배너 (로그인 시 숨김)
- [x] "무료 시작하기" / "앱 둘러보기" 버튼
- [x] `/auth/register?ref=share` UTM 링크

## 온보딩 플로우 강화

**파일:** `frontend/src/routes/onboarding/+page.svelte`

- [x] Step 3: 첫 키워드 트래킹 (입력 + 인기 키워드 제안, 건너뛰기 가능)
- [x] Step 4: 알림 설정 (급상승/주간 요약 토글)
- [x] Step 5: 로케일 비율 (기존 Step 3 → Step 5로 이동)
- [x] 진행 표시: Step N/5 프로그레스 바
- [x] 완료 시 키워드/알림 설정 저장

## 빈 상태 개선

**파일:** `frontend/src/lib/ui/EmptyState.svelte`

- [x] variant prop 추가: no_trends / no_results / no_tracker / no_insights
- [x] variant별 메시지 + 액션 버튼
- [x] 기존 icon/titleKey/descriptionKey 하위호환 유지
- [x] 기존 사용처에 variant 적용 (trends/+page.svelte, tracker 등)

## 완료 기준
- [x] 트래커: 키워드 카드 표시
- [x] 공유 페이지: 미로그인 시 CTA 배너 표시
- [x] 온보딩: Step 3 키워드 추가 동작
- [x] EmptyState variant별 다른 메시지
- [x] 트래커 키워드 상태 뱃지 (API 연동)
- [x] 빌드 통과
