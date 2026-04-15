# C-03 (Frontend): 수동 리뷰 샘플러 UI

> Branch: `feat/v6-review` | Agent: Frontend

## 페이지

### `frontend/src/routes/admin/cluster-review/+page.svelte` (신규)

- [ ] 좌/우 분할 레이아웃:
  - 좌: V5 클러스터 (auto_label or representative_keyword, 기사 상위 5건 제목, keyword_list)
  - 우: V6 클러스터 (auto_label, terms, topic, 기사 상위 5건)
- [ ] 하단 4버튼: `V5 Better` / `V6 Better` / `Tie` / `Both Bad`
- [ ] 단축키: `a` / `s` / `d` / `f`
- [ ] note textarea (optional)
- [ ] 제출 후 자동 다음 페어 로드
- [ ] 진행률 바: `{labeled}/100` + v6_better_ratio 표시
- [ ] i18n `admin.cluster_review.*`

### 사이드바 메뉴

- [ ] "Cluster Review" 추가

## 테스트

- [ ] 단축키 동작
- [ ] 제출 후 다음 페어 로드
- [ ] 진행률 표시

## 완료 조건

- [ ] 로컬 UI 동작 확인
- [ ] i18n ko/en
