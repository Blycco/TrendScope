# B-01 (Algorithm): V6 파이프라인 스캐폴드 + 섀도우 실행

> Branch: `feat/v6-scaffold` | Agent: Algorithm + Backend | Track: B
> 의존: A-01, A-02, A-04, A-05 완료
> Plan 참조: §B-01

## 배경

V5 코드 무수정 전제로 V6 전용 파이프라인 엔트리와 `shared/v6/` 서브패키지 격리 구축. V5/V6 동시 실행 프레임 확보.

## 목적

- `pipeline_v6.py` 신규 엔트리
- `shared/v6/` 서브패키지 스캐폴드 (빈 모듈 placeholder)
- `pipeline.version ∈ {"v5","v6","shadow"}` 분기
- 섀도우 모드: V5 정식 저장 + V6 섀도우 테이블 병렬 저장

## 사전 확인

- [ ] 현행 `pipeline.py::process_articles` 시그니처·의존성 숙지
- [ ] `main.py` 엔트리 로딩 흐름 파악
- [ ] `config_loader.get_settings()` 키 네임스페이스 관례 확인

## 신규 파일

### `backend/processor/shared/v6/__init__.py` (신규)

- [ ] 빈 패키지 initializer
- [ ] 향후 B-02~B-10 모듈이 이 패키지에 추가됨

### `backend/processor/shared/v6/embedder.py` (placeholder)
### `backend/processor/shared/v6/umap_reducer.py` (placeholder)
### `backend/processor/shared/v6/ann_index.py` (placeholder)
### `backend/processor/shared/v6/clusterer.py` (placeholder)
### `backend/processor/shared/v6/similarity.py` (placeholder)
### `backend/processor/shared/v6/ctfidf.py` (placeholder)
### `backend/processor/shared/v6/keyword_extractor.py` (placeholder)
### `backend/processor/shared/v6/topic_classifier.py` (placeholder)
### `backend/processor/shared/v6/kleinberg.py` (placeholder)
### `backend/processor/shared/v6/metrics.py` (placeholder)

각 파일에 `# Stub — implemented in B-0N` 주석 + `raise NotImplementedError`.

### `backend/processor/pipeline_v6.py` (신규)

- [ ] 엔트리: `async def process_articles_v6(articles, pool, settings) -> list[ProcessedArticle]`
- [ ] 시그니처는 V5와 동일 (교체 가능)
- [ ] 단계:
  1. dedupe (재사용: V5와 공용)
  2. normalize + lang_detect (A-01)
  3. near_dup (A-02)
  4. spam_filter (A-03, 모델 로드 시 XGB)
  5. keyword_extract_v6 (B-08)
  6. cluster_v6 (B-02→B-07)
  7. topic_classify (B-09)
  8. score + burst (B-10)
  9. save_shadow OR save_primary (config 분기)
- [ ] stage별 `structlog` timing + Prometheus histogram
- [ ] V6 단계 하나라도 실패 시 try/except → 해당 기사 skip, V5 경로 방해 X

### `backend/processor/main.py` (수정)

- [ ] `pipeline.version` 읽어 분기:
  - `"v5"`: V5만 실행 (기존)
  - `"v6"`: V6만 실행 (정식 테이블 저장)
  - `"shadow"`: V5 정식 저장 + V6 섀도우 저장 병렬 (동일 article 입력 1회)
- [ ] 병렬 실행 시 asyncio.gather 사용, V6 실패가 V5 저장 차단 금지

### `backend/processor/stages/save_shadow.py` (신규)

- [ ] `async def save_shadow(results, pool)` — 섀도우 테이블 INSERT
- [ ] news_group_shadow / article_group_shadow / group_label_shadow
- [ ] V5 save_primary 로직 참조하여 구조 동일

## 테스트

### `tests/test_pipeline_v6.py` (신규)

- [ ] `test_pipeline_version_v5_only`: flag="v5" → 섀도우 미저장
- [ ] `test_pipeline_version_v6_only`: flag="v6" → 정식 저장
- [ ] `test_pipeline_shadow_mode`: flag="shadow" → 양쪽 저장
- [ ] `test_v6_failure_does_not_break_v5`: V6 raise → V5 정상 저장
- [ ] 스모크: stub 모듈 상태에서는 V5만 동작, V6는 early return

## 메트릭

- [ ] `pipeline_stage_duration_seconds{version,stage}` histogram
- [ ] `pipeline_mode_total{mode="v5|v6|shadow"}` counter

## 롤백

- `pipeline.version="v5"` 설정 → V6 완전 우회

## 완료 조건

- [ ] pytest 통과 (스텁 상태)
- [ ] shadow 모드 DB 저장 검증
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: V6 파이프라인 스캐폴드 + shadow mode (V6 B-01)"`
