# TrendScope V6 Algorithm Upgrade — Task Index
> Plan: `/Users/verity/.claude/plans/partitioned-spinning-locket.md`
> 생성일: 2026-04-15
> 기준 문서: `docs/algorithms/EVOLUTION.md` (V5 현행)

## 목표

V5 → V6 알고리즘 업그레이드. 전처리·임베딩·클러스터링·키워드·스코어링 전반 고도화. **2-트랙 병행 + 섀도우 배포** 전략으로 롤백 안전 확보.

## 정량 목표 (V5 대비 Δ)

| 메트릭 | V5 | V6 목표 | Δ |
|--------|----|---------|---|
| Silhouette | ~0.18 | ≥0.23 | +0.05 |
| 수동 리뷰 클러스터 순도 | ~75% | ≥85% | +10pp |
| 스팸 F1 | ~0.70 | ≥0.85 | +0.15 |
| Stage p95 (n=1000) | 기준 | ≤×1.2 | FAISS로 상쇄 |
| 클러스터 내 near-dup 비율 | 미측정 | <5% | 신규 |
| 한국어 기사 오분류 | 미측정 | <2% | 신규 |

## 의존성 그래프

```
A-01 ──┐
A-02 ──┤
A-05 ──┼──→ B-01 ──→ B-02 ──→ B-03 ──→ B-04 ──→ B-05 ──→ B-06 ──→ B-07
A-04 ──┘                                                          │
A-03 (병행)                                                       ├──→ B-08
                                                                  ├──→ B-09
                                                                  └──→ B-10
C-01 ──→ C-02 ──→ C-03 (B-07 완료 이후 실데이터 생성)
C-04 admin flag (B-01 병행)
D-01 (C-02 + C-03 완료 후 착수)
D-02, D-03 (D-01 100% 롤아웃 후)
```

## 타임라인 (7주)

| 주차 | Track A | Track B | Track C | Track D |
|------|---------|---------|---------|---------|
| W1 | A-01, A-02, A-04, A-05 | B-01 | C-01 | — |
| W2 | A-03 | B-02, B-03 | — | — |
| W3 | — | B-04, B-05, B-06 | C-02 | — |
| W4 | — | B-07, B-08 | C-03 | — |
| W5 | — | B-09, B-10 | — | D-01 (10%) |
| W6 | — | 버그픽스 | 비교 분석 | D-01 (50%) |
| W7 | — | — | — | D-01 (100%), D-02, D-03 |

## 태스크 상태

| ID | 제목 | 트랙 | 에이전트 | 브랜치 | 상태 | 의존 | 파일 |
|----|------|------|----------|--------|------|------|------|
| A-01 | 언어 감지 단계 | A | Algorithm | `feat/v6-lang-detect` | todo | — | `v6-a01-language-detect/` |
| A-02 | Near-dup (MinHash+SimHash) | A | Algorithm | `feat/v6-near-dup` | todo | A-01 | `v6-a02-near-dup/` |
| A-03 | XGBoost 스팸 실학습 배포 | A | Algorithm+Backend | `feat/v6-spam-xgb` | todo | — | `v6-a03-spam-xgboost/` |
| A-04 | Noise gate 재설계 | A | Algorithm | `feat/v6-noise-gate` | todo | — | `v6-a04-noise-gate/` |
| A-05 | title/body 분리 정식화 | A | Algorithm | `feat/v6-preprocess-split` | todo | — | `v6-a05-preprocess-split/` |
| B-01 | V6 파이프라인 스캐폴드 | B | Algorithm+Backend | `feat/v6-scaffold` | todo | A-01,02,04,05 | `v6-b01-scaffold/` |
| B-02 | KoE5 임베딩 어댑터 | B | Algorithm | `feat/v6-koe5` | todo | B-01 | `v6-b02-koe5-embedding/` |
| B-03 | UMAP 차원축소 | B | Algorithm | `feat/v6-umap` | todo | B-02 | `v6-b03-umap/` |
| B-04 | FAISS ANN 인덱스 | B | Algorithm | `feat/v6-faiss` | todo | B-03 | `v6-b04-faiss/` |
| B-05 | HDBSCAN V6 + admin 노출 | B | Algorithm+Backend | `feat/v6-hdbscan` | todo | B-04 | `v6-b05-hdbscan-v6/` |
| B-06 | 4요소 가중합 복원 | B | Algorithm | `feat/v6-weights` | todo | B-05 | `v6-b06-weight-recovery/` |
| B-07 | c-TF-IDF 라벨링 | B | Algorithm | `feat/v6-ctfidf` | todo | B-05 | `v6-b07-ctfidf-label/` |
| B-08 | KeyBERT + PMI/log-likelihood | B | Algorithm | `feat/v6-keybert` | todo | B-01 | `v6-b08-keybert-pmi/` |
| B-09 | KLUE-TC 토픽 분류 | B | Algorithm | `feat/v6-topic` | todo | B-02 | `v6-b09-topic-classify/` |
| B-10 | Kleinberg burst | B | Algorithm | `feat/v6-kleinberg` | todo | B-05 | `v6-b10-kleinberg-burst/` |
| C-01 | 메트릭 프레임워크 | C | Algorithm+Backend | `feat/v6-metrics` | todo | B-01 | `v6-c01-metrics/` |
| C-02 | 비교 대시보드 | C | Backend+Frontend | `feat/v6-compare-ui` | todo | C-01 | `v6-c02-compare-dashboard/` |
| C-03 | 수동 리뷰 샘플러 | C | Backend+Frontend | `feat/v6-review` | todo | B-07 | `v6-c03-review-sampler/` |
| C-04 | admin flag | C | Backend | `feat/v6-flag` | todo | B-01 | `v6-c04-admin-flag/` |
| D-01 | Canary 10→50→100 | D | Infra+Backend | `chore/v6-canary` | todo | C-02,C-03 | `v6-d01-canary/` |
| D-02 | V5 deprecation | D | Algorithm | `chore/v6-deprecate` | todo | D-01 | `v6-d02-v5-deprecate/` |
| D-03 | EVOLUTION.md V6 섹션 | D | Algorithm | `docs/v6-evolution` | todo | D-02 | `v6-d03-evolution-doc/` |

## 전체 완료 조건 (DoD)

- [ ] 모든 Track A·B·C 태스크 PR develop 머지
- [ ] pytest 전 범위 통과, 커버리지 ≥70%
- [ ] ruff lint clean
- [ ] `cluster_metrics_daily` 에 V5/V6 섀도우 데이터 ≥7일 축적
- [ ] 수동 리뷰 샘플 ≥100건, v6_better_ratio ≥0.45
- [ ] silhouette Δ≥+0.03, coherence Δ≥+0.05, outlier_ratio Δ≤+5%
- [ ] 운영 부하 V5 대비 ×1.2 이내
- [ ] Canary 100% 배포 + V5 deprecation
- [ ] EVOLUTION.md V6 섹션 머지

## 브랜치·커밋 규약

- prefix: `feat/v6-*`, `chore/v6-*`, `docs/v6-*` — phase 문자열 금지
- 각 태스크 이슈 생성 후 `Ref: #N`
- 커밋 타입: `Feat|Fix|Docs|Chore|Refactor|Test|Perf`
- Co-Authored-By 금지
- PR `--base develop` 필수

## 범위 외 (V7로 분리)

- LightGBM LTR 연결 (라벨 데이터 선행)
- Bayesian / Optuna 자동 튜닝
- 다국어 하이브리드 라우팅
- GPU 추론 인프라
- Kafka/Flink 스트리밍
