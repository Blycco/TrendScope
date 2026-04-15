# A-01: 언어 감지 단계 도입

> Branch: `feat/v6-lang-detect` | Agent: Algorithm | Track: A
> 의존: 없음 (Track A 최우선 착수)
> Plan 참조: `/Users/verity/.claude/plans/partitioned-spinning-locket.md` §A-01

## 배경

현행 파이프라인은 기사 언어를 한국어로 가정. 영문/일문/중문 기사 혼입 시 KR-SBERT 임베딩 품질 저하, 한국어 형태소 분석기에 영문 토큰이 regex 폴백으로 빠지는 문제. 하류 단계(임베딩·키워드·클러스터링)가 언어별 분기하려면 먼저 `article.language` 필드가 있어야 함.

## 목적

각 기사에 `language` 필드(ISO 639-1: `ko`/`en`/`ja`/`zh`/`und`) 부여. 하류 단계가 언어별 토크나이저·임베딩·불용어를 분기 가능하도록.

## 사전 확인

- [ ] `SELECT column_name FROM information_schema.columns WHERE table_name='article' AND column_name='language';` — 컬럼 미존재 확인
- [ ] 최신 마이그레이션 번호 `SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1;` (034 이전인지)
- [ ] `requirements/processor.txt` 에 `lingua` 미존재 확인

## DB 마이그레이션

### `backend/db/migrations/034_article_language.sql` (신규)

- [ ] 파일 작성:
  ```sql
  BEGIN;
  ALTER TABLE article ADD COLUMN IF NOT EXISTS language VARCHAR(3) NOT NULL DEFAULT 'und';
  CREATE INDEX IF NOT EXISTS idx_article_language ON article(language);
  COMMIT;
  ```
- [ ] `backend/db/migrations/runner.py` 에 034 등록 확인 (기존 패턴 참조)

## 신규 모듈

### `backend/processor/shared/lang_detect.py` (신규)

- [ ] `lingua` 선택 이유 상단 주석: langdetect 대비 한국어 정확도 향상, fasttext-lid 대비 배포 간편(순수 Python)
- [ ] 싱글톤 패턴:
  ```python
  from lingua import Language, LanguageDetectorBuilder
  _DETECTOR = None
  def _get_detector():
      global _DETECTOR
      if _DETECTOR is None:
          _DETECTOR = (
              LanguageDetectorBuilder
              .from_languages(Language.KOREAN, Language.ENGLISH, Language.JAPANESE, Language.CHINESE)
              .with_preloaded_language_models()
              .build()
          )
      return _DETECTOR
  ```
- [ ] `async def detect(text: str) -> tuple[str, float]` 구현
  - 빈 문자열/None → `("und", 0.0)`
  - 20자 미만 → `("und", 0.0)`
  - `detector.compute_language_confidence_values(text)` → 최상위 언어 ISO 코드 + confidence
  - ISO 코드 매핑: `Language.KOREAN → "ko"`, `ENGLISH → "en"`, `JAPANESE → "ja"`, `CHINESE → "zh"`
- [ ] `min_confidence` 미만 시 `"und"` 반환 (admin_settings `lang_detect.min_confidence` 기본 0.70)
- [ ] 결과 Redis 캐시 `langdet:{sha1(text[:200])}` TTL 1일

## 파이프라인 통합

### `backend/processor/stages/normalize.py` (수정)

- [ ] normalize 완료 후 `detect(title + " " + body[:500])` 호출
- [ ] `article.language` 세팅
- [ ] structlog: `logger.info("lang_detected", article_id=..., lang=..., confidence=...)`

### `backend/processor/pipeline.py` (수정)

- [ ] Stage 1(normalize) 내부에서 lang_detect 호출되도록 — 별도 stage 불필요(normalize 확장)
- [ ] 실패 시 `language="und"` 로 graceful degrade

### `backend/processor/shared/config_loader.py` (수정)

- [ ] 신규 키 로딩: `lang_detect.min_confidence` (float, 기본 0.70)

### `backend/db/seeds/admin_settings.py` (수정)

- [ ] `INSERT ... ON CONFLICT(key) DO NOTHING` 로 `('lang_detect.min_confidence', '0.70', 'float')` 추가

## Article 모델 확장

- [ ] `backend/processor/shared/models.py` 또는 dataclass 정의 위치에 `language: str = "und"` 추가
- [ ] Pydantic 스키마 `backend/api/schemas/trends.py` 등에 `language` 노출 여부 확인(내부용이면 제외)

## Backfill 잡

### `backend/jobs/article_language_backfill.py` (신규)

- [ ] 1회성 잡: 기존 `article.language='und'` 레코드를 배치(1000건씩)로 업데이트
- [ ] CLI 진입점: `python -m backend.jobs.article_language_backfill`
- [ ] 진행률 로그 + 체크포인트(마지막 처리 ID Redis 저장)
- [ ] pyproject/scripts 등록 or `docs/runbook/v6-backfill.md` 에 실행 절차 기재

## 의존성

### `requirements/processor.txt`

- [ ] `lingua-language-detector>=2.0.0` 추가
- [ ] `pip install -r requirements/processor.txt` 후 import 확인

## 테스트

### `tests/test_lang_detect.py` (신규)

- [ ] fixture: 한국어 10건, 영문 10건, 일문 5건, 중문 5건 샘플 기사
- [ ] `test_korean_accuracy`: ko 분류 ≥95%
- [ ] `test_english_accuracy`: en 분류 ≥95%
- [ ] `test_short_text_returns_und`: 20자 미만 입력 → `"und"`
- [ ] `test_empty_returns_und`: 빈 문자열
- [ ] `test_low_confidence_returns_und`: 이중 언어 짧은 텍스트 confidence <0.70 → `"und"`
- [ ] `test_cache_hit`: 동일 텍스트 2회 호출 시 Redis 캐시 히트

### 성능 벤치

- [ ] `tests/bench/lang_detect_bench.py`: 1000기사 배치 < 2초 확인

## 메트릭 목표

- 한국어 기사 오분류 < 2%
- 영문 기사 정분류 ≥ 95%
- Stage overhead p95 < 20ms/article (캐시 히트 시)

## Prometheus 메트릭

- [ ] `lang_detect_total{lang="ko|en|ja|zh|und"}` counter
- [ ] `lang_detect_duration_seconds` histogram
- [ ] `backend/common/metrics.py` 에 등록

## 롤백 시나리오

1. **소프트 롤백**: `admin_settings` 에서 `lang_detect.min_confidence=1.0` → 모두 `und`, 하류 단계가 기본(한국어) 로직 사용
2. **하드 롤백**:
   - `pipeline.py` normalize stage에서 lang_detect 호출 제거
   - 마이그레이션 `DROP COLUMN language` (선택 — 필드 유지해도 무방)
   - `requirements/processor.txt` 에서 `lingua` 제거

## 완료 조건 (DoD)

- [ ] pytest 통과 (신규 테스트 포함)
- [ ] 커버리지 ≥70% 유지
- [ ] ruff lint clean
- [ ] `docker-compose up` 로컬 기동 → 실제 기사에서 `article.language` 채워짐 확인
- [ ] 프로덕션 마이그레이션 없이 브랜치 상에서 PR develop 머지까지

## 커밋 플랜

1. `Feat: 언어 감지 모듈 lang_detect 추가` — lang_detect.py + tests
2. `Feat: article.language 컬럼 + 파이프라인 통합` — migration 034 + normalize stage 수정
3. `Feat: article language backfill 잡 추가` — backfill script
4. `Chore: lingua-language-detector 의존성 추가` — requirements 변경

각 커밋 별도 PR 또는 단일 PR 내 분리 커밋 (단일 PR 권장).

## 이슈 연결

- [ ] `gh issue create --title "Feat: 언어 감지 파이프라인 단계 추가 (V6 A-01)"` → 이슈 번호 `Ref: #N` 사용
