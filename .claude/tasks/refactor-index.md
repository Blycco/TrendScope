# TrendScope 리팩토링 태스크 인덱스
> 기준 문서: `docs/refactoring-plan.md` v4  
> 생성일: 2026-04-09

## 의존성 순서

```
T-01 (DB 인프라) ← 모든 T-02~08 의존
    ├─ T-02 (스팸 필터 DB화)
    ├─ T-03 (불용어 DB화)
    ├─ T-04 (카테고리 DB화)
    ├─ T-05 (클러스터링 파라미터)
    └─ T-06 (burst 통합 + API) ← T-07~14 일부 의존
            ├─ T-07 (어드민 알고리즘 UI)
            ├─ T-08 (트렌드 품질 모니터링)
            ├─ T-09 (MultiSelect 필터)
            ├─ T-10 (TrendCard 개선)
            │       └─ T-11 (대시보드 개편)
            ├─ T-12 (상세 페이지 개편)
            ├─ T-13 (인사이트 강화)
            └─ T-14 (트래커·공유·온보딩) ← T-12, T-13 이후
```

## 브랜치 → 태스크 매핑

| 브랜치 | 태스크 | 태스크 파일 |
|--------|--------|------------|
| feat/config-infrastructure | T-01 | refactor-t01/backend.md |
| feat/managed-filters | T-02, T-03, T-04 | refactor-t02/, t03/, t04/ |
| fix/algorithm-tuning | T-05, T-06 | refactor-t05/, t06/ |
| feat/admin-ui | T-07, T-08 | refactor-t07/, t08/ |
| feat/trend-ux | T-09, T-10, T-11, T-12, T-13 | refactor-t09/ ~ t13/ |
| feat/engagement | T-14 | refactor-t14/ |

## 태스크 상태

| ID | 제목 | 브랜치 | 담당 에이전트 | 상태 |
|----|------|--------|-------------|------|
| T-01 | DB 스키마 + config_loader + admin_settings 시드 | feat/config-infrastructure | Backend | ✅ done (merged) |
| T-02 | 스팸/비트렌드 필터 DB화 + AI 제안 잡 | feat/managed-filters | Backend+Frontend | ✅ done (merged) |
| T-03 | 불용어 DB화 + 어드민 페이지 | feat/managed-filters | Algorithm+Backend+Frontend | ✅ done (merged) |
| T-04 | 카테고리 분류 DB화 + 어드민 페이지 | feat/managed-filters | Backend+Frontend | ✅ done (merged) |
| T-05 | 클러스터링 알고리즘 config_loader 연동 | fix/algorithm-tuning | Algorithm | ✅ done (merged) |
| T-06 | burst 점수 랭킹 통합 + 그룹 제목 + API | fix/algorithm-tuning | Algorithm+Backend | ✅ done (merged) |
| T-07 | 어드민 알고리즘 파라미터 UI | feat/admin-ui | Frontend | ✅ done (PR#214) |
| T-08 | 어드민 트렌드 품질 모니터링 | feat/admin-ui | Backend+Frontend | ✅ done (PR#214) |
| T-09 | MultiSelect 필터 + 트렌드 목록 교체 | feat/trend-ux | Frontend | ✅ done (PR#215) |
| T-10 | TrendCard 전면 개선 | feat/trend-ux | Frontend | ✅ done (PR#215) |
| T-11 | 대시보드 Bento Grid + 역할별 추천 | feat/trend-ux | Frontend | ✅ done (PR#215) |
| T-12 | 트렌드 상세 페이지 전면 개편 | feat/trend-ux | Frontend | ✅ done (PR#215) |
| T-13 | 인사이트 페이지 LLM 프롬프트 + UI 강화 | feat/trend-ux | Backend+Frontend | ✅ done (PR#215) |
| T-14 | 트래커·공유·온보딩·빈 상태 개선 | feat/engagement | Frontend | ✅ done (PR#216) |

## 검증 기준 (최종)

| 항목 | 기준 |
|------|------|
| 부고 기사 필터링 | 랭킹 상위 20개에 부고 0건 |
| 불용어 클러스터 | "12월" 단일 키워드 클러스터 0건 |
| 카드 제목 | 원제목 표시율 95%+ |
| 카드 요약 | summary 노출율 80%+ |
| burst 랭킹 | burst_score>0.7 트렌드가 상위 10개 중 5개+ |
| 테스트 커버리지 | ≥ 70% |
| ruff lint | 전체 통과 |
| 빌드 | npm run build 통과 |
