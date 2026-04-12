# T-07: 어드민 알고리즘 파라미터 UI
> Branch: feat/admin-ui | Agent: Frontend
> 의존성: T-01 완료 후 착수 (admin_settings 시드 필요)
> 참고: admin_settings PATCH API는 이미 존재 (`PATCH /admin/settings`)

## 어드민 알고리즘 설정 페이지

**파일:** `frontend/src/routes/admin/algorithm/+page.svelte` (신규)

### 섹션 구성

**1. 클러스터링 가중치**
- [x] cosine / jaccard / temporal / source 가중치 슬라이더 (0.0~1.0, step 0.05)
- [x] 합계 표시: 4개 합 = 1.0이어야 함 (벗어나면 경고)
- [x] jaccard_early_filter, threshold 슬라이더
- [x] outlier_sigma, temporal_decay_hours 숫자 입력

**2. 점수 가중치**
- [x] freshness / burst / article_count / source_diversity / social / keyword / velocity 슬라이더
- [x] 합계 표시: 7개 합 = 100이어야 함 (벗어나면 경고, 저장 불가)
- [x] louvain_threshold 슬라이더

**3. 스팸 필터 파라미터**
- [x] url_ratio_threshold 숫자 입력 (0.0~1.0)
- [x] keyword_threshold 정수 입력
- [x] min_content_length 정수 입력
- [x] non_trend_min_hits 정수 입력

**4. 신선도 감쇠 (decay lambda)**
- [x] breaking / politics / it / default 숫자 입력 (0.01~0.20)

**5. 키워드 추출**
- [x] title_boost 슬라이더 (1.0~5.0)
- [x] body_max_chars 정수 입력 (100~2000)
- [x] top_k 정수 입력 (5~30)

### 공통 UX
- [x] 각 섹션 하단: "저장" 버튼 → `PATCH /admin/settings` (해당 섹션 키만)
- [x] 저장 성공 → 토스트 알림
- [x] "기본값으로 초기화" 버튼 → `DELETE /admin/settings/{key}` (각 키)
- [x] 마지막 수정 시간 표시
- [x] 어드민 사이드바에 "알고리즘 설정" 메뉴 추가
- [x] i18n 키: `admin.algorithm.*`
- [x] 에러 모달 연동

## 완료 기준
- [x] 점수 가중치 합계 ≠ 100 → 저장 버튼 disabled
- [x] 저장 후 `GET /admin/settings` 응답 값 반영 확인
- [x] 빌드 통과
