# B-05 (Backend): V6 HDBSCAN 파라미터 admin UI

> Branch: `feat/v6-hdbscan` | Agent: Backend + Frontend

## admin_settings 시드

### `backend/db/seeds/admin_settings.py` (수정)

```
('v6.hdbscan.min_cluster_size', '3', 'int'),
('v6.hdbscan.min_samples', '2', 'int'),
('v6.hdbscan.cluster_selection_method', 'eom', 'str'),
('v6.hdbscan.cluster_selection_epsilon', '0.0', 'float'),
('v6.hdbscan.outlier_sigma_min', '0.5', 'float'),
('v6.hdbscan.outlier_sigma_max', '1.5', 'float'),
```

## API

### `backend/api/routers/admin/algo_params.py` (수정)

- [ ] V6 섹션 스키마 노출
- [ ] Pydantic validation:
  - `min_cluster_size` ∈ [2, 50]
  - `min_samples` ∈ [1, 20]
  - `cluster_selection_method` ∈ {"eom", "leaf"}
  - `outlier_sigma_min` ∈ [0.1, 1.0]
  - `outlier_sigma_max` ∈ [1.0, 3.0]

### `backend/api/schemas/admin.py` (수정)

- [ ] `V6HdbscanSettings` 스키마

## Frontend

### `frontend/src/routes/admin/algo-params/+page.svelte` (수정)

- [ ] "V6 Clustering" 섹션 추가 (V5와 독립)
- [ ] 필드 6종 입력 + 변경 시 confirm 모달
- [ ] i18n 키 `admin.algo_params.v6.*`

## 테스트

- [ ] API get/put 스모크
- [ ] validation 경계값 테스트
- [ ] 비어드민 403

## 완료 조건

- [ ] pytest 통과
- [ ] UI 동작 확인
- [ ] audit_log 기록
