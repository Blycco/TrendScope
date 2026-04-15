# D-03: EVOLUTION.md V6 섹션

> Branch: `docs/v6-evolution` | Agent: Algorithm
> 의존: D-02
> Plan 참조: §D-03

## 목적

V6 파이프라인 / 클러스터링 V6 / 키워드 추출 V5 섹션을 `docs/algorithms/EVOLUTION.md` 에 추가. 기존 포맷 규칙 준수.

## 기존 포맷 규칙 (재확인)

- [ ] TL;DR 2~3줄
- [ ] 흐름도 (ASCII 또는 mermaid)
- [ ] Step 전체 번호 기재
- [ ] 쉬운 말로 풀어 쓴 처리 과정
- [ ] 효과 / 새로 생긴 문제
- [ ] 관찰 예시 (가상, "예시이며 실제 데이터 아님" 명시)

## 작업 파일

### `docs/algorithms/EVOLUTION.md` (수정)

### 섹션 1: "Pipeline V6 (2026-MM-DD)"

- [ ] TL;DR: V5 대비 임베딩·차원축소·ANN·클러스터 라벨·토픽 분류·burst 추가
- [ ] Stage 흐름도
- [ ] 각 단계 Step N → 역할·파라미터·이전 차이
- [ ] 섀도우 → canary → 100% 이관 기록
- [ ] 관찰 예시 (가상)

### 섹션 2: "Clustering V6"

- [ ] KoE5 → UMAP → FAISS → HDBSCAN → 4요소 composite → c-TF-IDF
- [ ] V5와의 차이·개선점·새 문제(모델 크기·결정론 주의)

### 섹션 3: "Keyword Extraction V5"

- [ ] KeyBERT + PMI + LL + trigram
- [ ] V4 대비 효과
- [ ] 주의점 (코퍼스 통계 rolling window)

### 섹션 4: 용어 사전 업데이트

- [ ] KoE5, UMAP, FAISS, HNSW, c-TF-IDF, PMI, LL, Kleinberg burst, MinHash, SimHash, lingua

### 섹션 5: 현행 아키텍처 섹션 수정

- [ ] Stage 목록 9단계(V6) 로 교체
- [ ] admin 파라미터 표 업데이트

## 체크리스트

- [ ] 네 섹션 모두 작성
- [ ] 관찰 예시는 "가상" 명시
- [ ] 용어 사전 갱신
- [ ] 포맷 통일성 검토
- [ ] 커밋 + PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Docs: EVOLUTION.md V6 섹션 추가 (V6 D-03)"`
