# A-03 (Algorithm): XGBoost 스팸 필터 실학습·배포

> Branch: `feat/v6-spam-xgb` | Agent: Algorithm | Track: A
> 의존: 없음 (A-01 완료 시 language 피처 활용)
> Backend 파트: `backend.md` 참조
> Plan 참조: §A-03

## 배경

현행 `spam_filter.py` 는 XGBoost 경로 코드만 존재하고 **학습된 모델이 없어 규칙 기반 폴백**만 작동. F1 ~0.70 추정. 모델 파일 생성 + 피처 확장 + 추론 통합이 목표.

## 목적

- 수동 라벨 1000건 + weak label 2000건으로 XGBoost 학습
- 피처 7종 → 13종 확장 (title_has_cta, emoji_count, language 등)
- 규칙 폴백 유지 + 모델 로드 실패 시 자동 복귀
- 주 1회 재학습 cron

## 사전 확인

- [ ] 현행 `spam_filter.py::SpamFilter` 클래스 구조 숙지
- [ ] 기존 피처 7종 로직 확인 (url_ratio, keyword_hits, phone_count, caps_ratio, special_count, content_length, url_count)
- [ ] `xgboost>=2.0.0` 이미 설치됨 확인

## 피처 엔지니어링

### 기존 7종 (유지)

| 피처 | 타입 | 계산 |
|------|------|------|
| url_ratio | float | URL 문자 길이 / 전체 길이 |
| keyword_hits | int | filter_keyword 테이블 카테고리 'ad' 히트 수 |
| phone_count | int | 전화번호 패턴 매치 |
| caps_ratio | float | 대문자 / 영문 전체 |
| special_count | int | 특수문자 밀도 |
| content_length | int | 본문 문자 수 |
| url_count | int | URL 개수 |

### 신규 6종

| 피처 | 타입 | 계산 |
|------|------|------|
| title_has_cta | int(0/1) | 제목에 "클릭", "지금", "무료", "bit.ly" 등 CTA 패턴 |
| emoji_count | int | unicode emoji 매치 수 |
| external_link_domain_entropy | float | 외부 링크 도메인 분포 엔트로피 (동일 도메인 집중 시 낮음) |
| language | categorical (one-hot: ko/en/ja/zh/und) | A-01의 `article.language` |
| repeated_ngram_ratio | float | 3-gram 중복 비율 (스팸 도배 지표) |
| numeric_token_ratio | float | 숫자 토큰 / 전체 토큰 |

## 신규 모듈

### `backend/processor/shared/spam_features.py` (신규)

- [ ] `compute_features(article) -> dict[str, float]` — 13종 모두 계산
- [ ] 단위테스트 가능한 순수 함수

### `backend/processor/shared/spam_filter.py` (수정)

- [ ] `SpamFilter.__init__`:
  - 모델 경로 `settings.MODELS_DIR / "spam_xgb_v1.json"`
  - `xgboost.Booster()` lazy load + metadata JSON 검증
  - 로드 실패 시 `self._fallback = True`, 규칙 기반 유지
- [ ] `predict(article) -> tuple[bool, float]` (is_spam, prob):
  - 모델 있으면: `compute_features` → DMatrix → `booster.predict` → prob
  - `spam.xgb_threshold` 비교해 판정
  - 모델 없으면 기존 규칙 로직
- [ ] 로깅: `logger.info("spam_predicted", article_id=..., prob=..., mode="xgb"|"rules")`

## 학습 잡

### `backend/jobs/spam_model_train.py` (신규)

- [ ] CLI: `python -m backend.jobs.spam_model_train --min-labels 500`
- [ ] 데이터 로드:
  - `spam_label` 테이블 (A-03 Backend 참조) 에서 labeled 데이터
  - label='spam' → 1, 'ham' → 0, 'unsure' → 제외
- [ ] Weak label (선택): 기존 규칙에서 고확신 spam/ham 자동 라벨 최대 2000건
- [ ] Train/val split 80/20 stratified
- [ ] `xgboost.train`:
  - `objective='binary:logistic'`
  - `tree_method='hist'`, `max_depth=6`, `learning_rate=0.05`, `n_estimators=500`
  - `early_stopping_rounds=50`
  - `eval_metric=['logloss','auc']`
- [ ] 평가: ROC-AUC ≥ 0.92, F1 ≥ 0.85 통과 시 저장
- [ ] 저장:
  - `models/spam_xgb_v1.json` (booster.save_model)
  - `models/spam_xgb_v1.metadata.json` (학습일, 피처 목록, 메트릭)
- [ ] 실패 시 기존 모델 유지(atomic 교체)

## 의존성

- [ ] `xgboost` 버전 고정: `xgboost==2.1.3` (결정론성)
- [ ] `models/` 디렉터리 `.gitignore` 확인, CI에서 모델 아티팩트 별도 관리 (S3 또는 Docker volume)

## 테스트

### `tests/test_spam_xgb.py` (신규)

- [ ] `test_features_computation`: 각 피처 단위 테스트
- [ ] `test_train_smoke`: 샘플 100건으로 학습 → 모델 파일 생성
- [ ] `test_inference_with_model`: 모델 로드 후 예측 확률 반환
- [ ] `test_fallback_without_model`: 모델 파일 없음 → 규칙 폴백 정상
- [ ] `test_threshold_config`: `spam.xgb_threshold` 변경 반영
- [ ] `test_metadata_validation`: 피처 목록 불일치 시 로드 실패

## 메트릭 목표

- ROC-AUC ≥ 0.92
- F1 ≥ 0.85
- 추론 overhead < 5ms/article
- 규칙 폴백 동작 무변경

## Prometheus

- [ ] `spam_predict_total{mode="xgb|rules",verdict="spam|ham"}` counter
- [ ] `spam_predict_probability` histogram
- [ ] `spam_model_load_success` gauge

## 롤백

1. `models/spam_xgb_v1.json` 삭제 → 규칙 폴백 자동 복귀
2. `spam.xgb_threshold=1.0` 설정 → 모든 기사 ham 판정

## 완료 조건

- [ ] pytest 통과
- [ ] 스모크 학습 완료 (샘플 데이터)
- [ ] 추론 경로 검증
- [ ] PR develop 머지
- [ ] Backend 파트(`backend.md`) 함께 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: XGBoost 스팸 필터 실학습·배포 (V6 A-03)"`
