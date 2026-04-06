# Troubleshooting: 트렌드 카드 소스 불일치

> Issue: #128 | 응급 조치: PR #129 | 근본 해결: Phase 11

---

## 현상

트렌드 카드 상세 페이지(`/trends/{id}`)에서 소스(기사) 3개 중 1번만 해당 트렌드와 관련 있고, 2·3번은 전혀 무관한 기사가 표시됨.

**재현 경로**: 트렌드 목록 → 카드 클릭 → 상세 페이지 → 기사 목록 확인

---

## 원인 분석

### 직접 원인: Stage 4.5 Jaccard threshold 과소 설정

`backend/processor/pipeline.py`의 `_stage_match_existing_groups`에서 기존 `news_group`에 신규 기사를 매칭할 때:

- **Jaccard 키워드 유사도만** 사용 (의미적 유사도 없음)
- **threshold = 0.25** (25%만 겹치면 같은 그룹에 할당)
- 비교 대상: 48시간 내 전체 그룹 (범위 과대)

Stage 5 클러스터링(threshold 0.55, composite similarity)보다 훨씬 느슨한 기준.

### 근본 원인: cosine similarity 비활성

`semantic_clusterer.py`에 MiniLM-L6 cosine similarity 로직이 구현되어 있으나, `sentence-transformers`가 `requirements.txt`에 없어서 `ImportError` → cosine = 0.0.

설계상 가중치:
```
sim(A,B) = 0.50*cosine + 0.25*jaccard + 0.15*temporal + 0.10*source
```

실제 작동:
```
sim(A,B) = 0.00*cosine + 0.25*jaccard + 0.15*temporal + 0.10*source
           ^^^^^^^^^^^^
           항상 0 — 전체 유사도의 50%가 소실
```

결과적으로 키워드 단어 겹침에 과도하게 의존 → 맥락이 다른 기사가 같은 그룹에 배정.

---

## 응급 조치 (PR #129)

| 변경 | 파일 | 내용 |
|---|---|---|
| threshold 상향 | `pipeline.py:167` | `_EXISTING_GROUP_MATCH_THRESHOLD` 0.25 → 0.50 |
| article 키워드 보강 | `pipeline.py:227-232` | article title words를 keyword set에 합산 |
| 데이터 정리 스크립트 | `backend/scripts/fix_group_matching.py` | 기존 오매칭 article의 group_id 해제 |

### 데이터 정리 스크립트 사용법

```bash
# 영향 범위 확인 (DB 변경 없음)
python -m backend.scripts.fix_group_matching --dry-run

# 실제 적용
python -m backend.scripts.fix_group_matching
```

- `DATABASE_URL` 환경변수 필요
- group keywords와 article title 간 Jaccard < 0.50인 article의 `group_id`를 NULL로 해제
- `news_group` 자체는 삭제하지 않음 (summary 등 데이터 보존)

---

## 근본 해결

Phase 11 클러스터링 리팩터링 (`.claude/tasks/phase11/algorithm.md`) 참조.

핵심 개선:
1. `sentence-transformers` + `snunlp/KR-SBERT` 의존성 추가 → cosine 50% 활성화
2. HDBSCAN 클러스터링 도입 → 노이즈 자동 제거
3. 시간 윈도우 축소 (48h → 6h) → 오매칭 범위 감소
4. 클러스터 후처리 정제 → outlier 제거

---

## 재발 방지 체크리스트

- [ ] 클러스터링 관련 threshold 변경 시 Stage 4.5와 Stage 5 동시 검토
- [ ] 새로운 similarity 컴포넌트 추가 시 의존성 설치 여부 확인
- [ ] 클러스터 purity 측정 테스트 추가 (Phase 11 Task)
- [ ] Stage 4.5 매칭 로그(`pipeline_article_matched_existing_group`)에 similarity 값 모니터링
