# C-02 (Backend): V5/V6 비교 대시보드 API

> Branch: `feat/v6-compare-ui` | Agent: Backend
> 의존: C-01

## 엔드포인트

### `backend/api/routers/admin/pipeline_compare.py` (신규)

- [ ] `GET /admin/pipeline-compare/daily?from=YYYY-MM-DD&to=YYYY-MM-DD`
  - response: `{v5: [{date, silhouette, ...}, ...], v6: [...]}`
- [ ] `GET /admin/pipeline-compare/latest`
  - response: 최신일자 V5/V6 요약 + Δ
- [ ] `GET /admin/pipeline-compare/cluster-diff?date=YYYY-MM-DD&limit=20`
  - response: 동일 기사 배치에서 V5 vs V6 클러스터 페어 샘플 (C-03 연계)
- [ ] 모든 엔드포인트 admin 권한
- [ ] audit_log 기록 불필요 (읽기 전용, 민감 데이터 아님)

### `backend/api/schemas/admin.py` (수정)

- [ ] `PipelineMetricPoint`, `PipelineCompareResponse`, `ClusterDiffPair` 스키마

### `backend/db/queries/metrics.py` (수정)

- [ ] `get_metrics_range` C-01에서 이미 추가됨
- [ ] `get_cluster_pairs_by_date(date, limit)`:
  - 섀도우 테이블 `article_group_shadow` ⋈ 정식 `article_group` → 동일 article 기준 페어
  - 기사 수 ≥ 2 조건

## 테스트

### `tests/test_pipeline_compare_api.py` (신규)

- [ ] 빈 데이터 → 빈 배열
- [ ] 범위 쿼리 동작
- [ ] 클러스터 diff 페어 반환
- [ ] 비어드민 403

## 완료 조건

- [ ] pytest 통과
- [ ] OpenAPI 스키마 업데이트
