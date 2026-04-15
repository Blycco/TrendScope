# T-06: burst 점수 랭킹 통합 + 그룹 제목 개선 + API 노출
> Branch: fix/algorithm-tuning | Agent: Algorithm + Backend
> 의존성: T-01 완료 후 착수 (config_loader, 022 마이그레이션 필요)

## score_calculator.py

**파일:** `backend/processor/shared/score_calculator.py`

- [x] `ScoreInput` dataclass에 필드 추가:
  - `burst_score: float = 0.0`
  - `velocity: float = 0.0`
- [x] 모든 `WEIGHT_*` 상수 → `config_loader.get_setting("score.weight_*", default)` 로 대체
  - WEIGHT_FRESHNESS(40→25), WEIGHT_SOURCE_DIVERSITY(15→12), WEIGHT_ARTICLE_COUNT(20→15)
  - WEIGHT_SOCIAL_SIGNAL(15→10), WEIGHT_KEYWORD_IMPORTANCE(10→8)
  - 신규: WEIGHT_BURST(→25), WEIGHT_VELOCITY(→5)
- [x] `_normalize_burst(burst_score: float) -> float` 함수 추가 (0~1 → 0~100)
- [x] `_normalize_velocity(velocity: float) -> float` 함수 추가
- [x] `calculate_score()` 에 burst_score, velocity 계산 반영
- [x] 카테고리별 decay lambda → `config_loader.get_setting("decay.*", default)` 로 대체
- [x] 단일 기사 클러스터: `score × 0.7` 페널티 적용

## stages/score.py

**파일:** `backend/processor/stages/score.py`

- [x] `stage_score()` 내부에서 `detect_burst(articles)` 호출 추가
  - `from backend.processor.algorithms.burst import detect_burst` import
  - `burst_result = await detect_burst(articles)`
  - `ScoreInput(..., burst_score=burst_result.score)`
- [x] 그룹 제목 생성 로직 변경 (L86-87):
  - 현재: `" · ".join(top_keywords[:3])`
  - 변경: 대표 기사(rep_article) 원제목 우선
    - rep_article 없음 → 기존 방식 fallback
    - 제목 ≤ 50자 → 그대로
    - 제목 > 50자 → `title[:45] + "…"`
- [x] `news_group.burst_score` 컬럼 저장 추가 (INSERT/UPDATE 쿼리에 burst_score 포함)

## API 스키마 및 라우터

**파일:** `backend/api/schemas/trends.py`

- [x] `TrendItem`에 필드 추가:
  - `burst_score: float = 0.0`
  - `platform_distribution: dict[str, float] = {}` — {"news": 0.45, "community": 0.32, "sns": 0.23}
- [x] `TrendDetailResponse` 유지 (상속)

**파일:** `backend/api/routers/trends.py`

- [x] 트렌드 목록/상세 쿼리에 `burst_score` SELECT 추가
- [x] `platform_distribution` 계산: `news_article.source_type` 기준 그룹별 비율 집계
  - 트렌드 상세 (`GET /trends/{id}`) 응답에 포함

**파일:** `backend/api/routers/dashboard.py`

- [x] 대시보드 트렌드 목록 응답에 `summary`, `burst_score` 포함
- [x] 쿼리 SELECT에 `ng.summary`, `ng.burst_score` 추가

## 테스트
- [x] `tests/processor/test_score_calculator.py` 확장:
  - burst_score=1.0 → 최종 score에서 burst 가중치 반영됨
  - 단일 기사 클러스터 → score 0.7배 페널티 확인
  - 가중치 합계 = 100 확인
- [x] `tests/api/test_trends.py`:
  - GET /trends → 응답에 burst_score 필드 존재
  - GET /dashboard/summary → 트렌드에 summary 필드 존재

## 완료 기준
- [x] 부고 기사 or 단일 기사 클러스터가 랭킹 상위에 오지 않음
- [x] 트렌드 카드에 원제목 표시됨 (키워드 join 아님)
- [x] GET /trends 응답에 burst_score 존재
- [x] pytest 통과, ruff 통과
