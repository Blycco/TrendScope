# Phase 11 / Algorithm — 클러스터링 리팩터링
> Agent: Algorithm | Type: Refactor | Ref: #128 (트렌드 소스 매칭 버그)

## 배경

현재 클러스터링은 설계상 composite similarity(cosine 50% + jaccard 25% + temporal 15% + source 10%)이나,
`sentence-transformers` 미설치로 cosine=0.0 → 사실상 키워드 단어 매칭에 의존.
Stage 4.5(기존 그룹 매칭)는 Jaccard only + 낮은 threshold로 무관한 기사가 같은 그룹에 할당되는 문제 발생.

응급 조치(PR #129): threshold 0.25→0.50 상향 + article title 키워드 보강.
이 페이즈에서는 구조적 개선을 진행한다.

---

## Tasks

### 1. 임베딩 기반 클러스터링 활성화
- [ ] `requirements.txt`에 `sentence-transformers`, `torch` 추가
- [ ] `semantic_clusterer.py` `_MODEL_NAME`을 `snunlp/KR-SBERT`로 변경 (한국어 최적화)
- [ ] cosine 50% 가중치 정상 작동 검증 테스트 작성
- [ ] Stage 4.5(`pipeline.py` `_stage_match_existing_groups`)에도 cosine similarity 적용

**현황**: 코드 구현 완료(`semantic_clusterer.py:93-138`), 의존성만 추가하면 즉시 활성화
**영향 파일**: `requirements.txt`, `backend/processor/shared/semantic_clusterer.py`, `backend/processor/pipeline.py`

### 2. HDBSCAN 클러스터링 도입
- [ ] `requirements.txt`에 `hdbscan` 추가
- [ ] `backend/processor/algorithms/grouping.py`에 `hdbscan_cluster()` 함수 추가
- [ ] 노이즈 포인트(label=-1) 처리: 단독 그룹 생성 또는 미분류 처리
- [ ] 기존 Louvain/greedy → HDBSCAN 전환 (Louvain을 fallback으로 유지)
- [ ] `min_cluster_size`, `min_samples` 파라미터 튜닝 테스트

**현황**: 미구현. 현재 greedy single-linkage + Louvain 사용 중
**영향 파일**: `requirements.txt`, `backend/processor/algorithms/grouping.py`

### 3. 시간 윈도우 클러스터링
- [ ] Stage 4.5의 기존 그룹 매칭 범위 48시간 → 6시간으로 축소
- [ ] `_stage_cluster`에서 시간대별 배치 클러스터링 적용 (같은 시간대 기사끼리 먼저 묶기)
- [ ] temporal 가중치 비율 재검토 (15% → 20% 상향 여부)

**현황**: `compute_temporal_similarity` 존재하나, cosine 비활성으로 실질 비중 왜곡. Stage 4.5는 48시간 전체 대상
**영향 파일**: `backend/processor/pipeline.py`, `backend/processor/shared/semantic_clusterer.py`

### 4. 후처리 — 클러스터 정제 (outlier 제거)
- [ ] `pipeline.py`에 `_stage_refine_clusters()` 스테이지 추가 (Stage 5.5)
- [ ] 클러스터 centroid 대비 similarity 하위 항목(threshold 미만) 제거
- [ ] 제거된 항목은 단독 클러스터로 재분류
- [ ] 클러스터 내부 평균 similarity 로깅

**현황**: 미구현. 클러스터링 후 정제 단계 없음
**영향 파일**: `backend/processor/pipeline.py`

### 5. 키워드 co-occurrence 기반 보정
- [ ] `keyword_extractor.py`에 bigram/trigram 추출 옵션 추가
- [ ] 동시출현 패턴을 클러스터링 유사도에 반영 ("아이폰+출시" vs "아이폰+주가" 구분)
- [ ] co-occurrence matrix 기반 keyword set 보정

**현황**: 미구현. 단어 개별 매칭만 사용
**영향 파일**: `backend/processor/shared/keyword_extractor.py`, `backend/processor/shared/semantic_clusterer.py`

### 6. 품사 필터링 강화
- [ ] `keyword_extractor.py`의 regex 기반 토크나이저를 POS 태깅 기반으로 전환
- [ ] `kiwipiepy` 의존성 추가 (경량 한국어 형태소 분석기)
- [ ] 명사/고유명사 중심 필터링
- [ ] 한국어 뉴스 빈출 무의미 단어 stopwords 확장

**현황**: regex `[가-힣]{2,}` + 기본 stopwords 21개. soynlp fallback 있으나 미설치
**영향 파일**: `requirements.txt`, `backend/processor/shared/keyword_extractor.py`

---

## 우선순위

| 순위 | Task | 이유 |
|---|---|---|
| 1 | 임베딩 활성화 | 코드 이미 있음. 의존성 추가만으로 cosine 50% 즉시 활성화. 임팩트 최대 |
| 2 | 후처리 정제 | 클러스터링 방식 무관하게 품질 보장. 구현 난이도 낮음 |
| 3 | 시간 윈도우 | Stage 4.5 범위 축소로 오매칭 즉시 감소 |
| 4 | 품사 필터링 | 키워드 품질 향상 → 모든 클러스터링의 기반 개선 |
| 5 | HDBSCAN | 알고리즘 전환. 임베딩 활성화 후 효과 극대화 |
| 6 | co-occurrence | 고급 최적화. 앞선 개선 적용 후 추가 효과 검증 필요 |

### 7. 트렌드 그룹 제목을 핵심 키워드로 전환
- [ ] `pipeline.py` `_stage_score`에서 그룹 제목 생성 로직 변경
- [ ] 현재: 대표 기사의 `title`을 그대로 `news_group.title`로 저장 (`pipeline.py:425`)
- [ ] 변경: 클러스터 내 기사들의 키워드 중 빈도·중요도 최상위 키워드를 그룹 제목으로 사용
- [ ] 예: "더 오래 살지만 더 오래 아프다… 유병장수 시대 넘으려면" → "유병장수"
- [ ] 기사 원문 제목은 `news_article.title`에 이미 보존되어 있으므로 데이터 손실 없음

**현황**: 미구현. 대표 기사 title을 그대로 사용하여 트렌드 카드가 뉴스 헤드라인처럼 보임
**영향 파일**: `backend/processor/pipeline.py`

### 8. "하락 중" 전부 표시 버그 조사 및 수정
- [ ] /trends 페이지에서 전체 카드가 "하락 중"으로 표시됨 (사용자 리포트)
- [ ] `status.declining` i18n 키 존재하나 main 브랜치 코드에서 렌더링 지점 없음
- [ ] 배포 코드와 main 브랜치 불일치 가능성 조사
- [ ] score 변동 기반 방향 로직이 없어 근본적으로 재구현 필요 (Task → frontend.md Task 3 연계)

**현황**: 원인 미확인. 배포 빌드 점검 필요
**영향 파일**: `frontend/src/components/TrendCard.svelte`, 배포 빌드

---

## 우선순위

| 순위 | Task | 이유 |
|---|---|---|
| 1 | 임베딩 활성화 | 코드 이미 있음. 의존성 추가만으로 cosine 50% 즉시 활성화. 임팩트 최대 |
| 2 | 그룹 제목 키워드 전환 | 트렌드 카드 UX 핵심. 기사 헤드라인 → 키워드로 전환 |
| 3 | 품사 필터링 | "살지만", "넘으려면" 같은 무의미 어절 제거. 키워드 품질 기반 |
| 4 | 후처리 정제 | 클러스터링 방식 무관하게 품질 보장. 구현 난이도 낮음 |
| 5 | 시간 윈도우 | Stage 4.5 범위 축소로 오매칭 즉시 감소 |
| 6 | HDBSCAN | 알고리즘 전환. 임베딩 활성화 후 효과 극대화 |
| 7 | co-occurrence | 고급 최적화. 앞선 개선 적용 후 추가 효과 검증 필요 |
| 8 | 하락 버그 조사 | 배포 환경 점검 필요. frontend Task 3과 연계 |

## 검증 기준
- pytest ≥ 70% coverage
- ruff lint/format 통과
- 클러스터 purity 측정 테스트 추가 (샘플 데이터 기반)
