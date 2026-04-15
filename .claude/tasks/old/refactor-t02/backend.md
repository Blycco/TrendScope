# T-02: 스팸/비트렌드 필터 DB화 + AI 키워드 제안 잡 + 어드민
> Branch: feat/managed-filters | Agent: Backend + Frontend
> 의존성: T-01 완료 후 착수 (config_loader, filter_keyword 테이블 필요)

## spam_filter.py DB 기반 전환

**파일:** `backend/processor/shared/spam_filter.py`

- [x] 모듈 상단 `_SPAM_KEYWORDS` frozenset → `config_loader.get_filter_keywords(category='ad')` 호출로 대체
- [x] `_NON_TREND_KEYWORDS` (현재 없음) → `config_loader.get_filter_keywords(category='obituary')` 추가
- [x] `_SPAM_URL_RATIO_THRESHOLD` → `config_loader.get_setting("spam.url_ratio_threshold", 0.3)`
- [x] `_SPAM_KEYWORD_THRESHOLD` → `config_loader.get_setting("spam.keyword_threshold", 3)`
- [x] `_MIN_CONTENT_LENGTH` → `config_loader.get_setting("spam.min_content_length", 20)`
- [x] `non_trend_min_hits` → `config_loader.get_setting("spam.non_trend_min_hits", 2)`
- [x] `_classify_rule_based()` 에 non-trend 판정 추가:
  - non_trend 키워드 매칭 수 ≥ non_trend_min_hits → `SpamResult(is_spam=True, confidence=0.7, method="rule_based", reasons=["non_trend"])`
- [x] `async def reload_filter_cache()` 공개 함수 추가 — `invalidate_cache("filter_kw")` 호출
- [x] 하드코딩 frozenset 제거 (기존 값은 T-01 시드로 이전 완료)

## AI 자동 비트렌드 키워드 제안 잡

**파일:** `backend/jobs/keyword_review_job.py` (신규)

- [x] `async def run_keyword_review_job()` 함수
  - 24시간마다 실행 (기존 scheduler 패턴 따를 것)
  - `news_group` 점수 하위 5% 기사 샘플링 (LIMIT 50)
  - `news_group.summary` + `news_group.title` → LLM 배치 요청
  - LLM 프롬프트: "다음 기사들이 트렌드 서비스에서 제외되어야 할 비트렌드(부고·광고·무관)인지 판단하고, 핵심 식별 키워드를 추출해줘"
  - 응답에서 키워드 추출 → `filter_keyword` INSERT (source='ai_suggested', is_active=FALSE, confidence=LLM confidence)
  - 중복 키워드 SKIP (ON CONFLICT DO NOTHING)
- [x] try/except + structlog 로깅
- [x] 기존 scheduler 파일에 등록

## 어드민 API

**파일:** `backend/api/routers/admin/filter_keywords.py` (신규)

- [x] `GET /admin/filter-keywords` — 목록 (query: category, source, is_active, limit, offset)
- [x] `POST /admin/filter-keywords` — 추가 (body: keyword, category, confidence)
- [x] `PATCH /admin/filter-keywords/{id}` — is_active 토글, category 변경
- [x] `DELETE /admin/filter-keywords/{id}` — 삭제
- [x] `POST /admin/filter-keywords/{id}/approve` — ai_suggested → is_active=TRUE, source='manual'
- [x] `POST /admin/filter-keywords/reload` — `reload_filter_cache()` 호출
- [x] require_admin_role() 적용
- [x] log_audit() 적용 (CRUD 액션마다)
- [x] handle_errors 데코레이터 적용

## 테스트
- [x] `tests/processor/test_spam_filter.py` 확장:
  - 부고 키워드 2개 포함 기사 → is_spam=True
  - 부고 키워드 1개 포함 기사 → is_spam=False (min_hits=2)
  - 기존 광고 키워드 테스트 유지
- [x] ruff 통과

## 완료 기준
- [x] 부고 기사 (`부고`, `서거` 2개 포함) SpamResult.is_spam=True 확인
- [x] admin API 5개 엔드포인트 200/201 응답 확인
- [x] reload 후 Redis `config:filter_kw:*` 키 삭제 확인
