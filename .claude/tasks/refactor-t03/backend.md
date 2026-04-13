# T-03: 불용어 DB화 + 어드민
> Branch: feat/managed-filters | Agent: Algorithm + Backend + Frontend
> 의존성: T-01 완료 후 착수 (config_loader, stopword 테이블 필요)

## keyword_extractor.py DB 기반 전환

**파일:** `backend/processor/shared/keyword_extractor.py`

- [x] `_KOREAN_STOP_WORDS` 하드코딩 frozenset 제거 → `await config_loader.get_stopwords('ko')` 로드
- [x] `_STOP_WORDS` (영어) 제거 → `await config_loader.get_stopwords('en')` 로드
- [x] `extract_keywords()` 함수 시그니처 변경:
  - `title_boost: float` 파라미터 추가 (기본값은 `await get_setting("keyword.title_boost", 2.0)`)
  - `body_max_chars: int` 파라미터 추가 (기본값은 `await get_setting("keyword.body_max_chars", 500)`)
  - `top_k: int` 파라미터 추가 (기본값은 `await get_setting("keyword.top_k", 10)`)
- [x] 제목 토큰 TF 계산 시 `frequency × title_boost` 적용
- [x] 본문 처리: `body[:body_max_chars]` 로 앞부분만 처리
- [x] 제목/본문 분리 전달 방식으로 변경 (단순 concat → 가중치 적용)
- [x] `async def reload_stopword_cache()` 공개 함수 추가

**파일:** `backend/processor/stages/keywords.py`
- [x] `stage_keywords()` 에서 title/body 분리 후 `extract_keywords(title=..., body=...)` 호출

## 어드민 API

**파일:** `backend/api/routers/admin/stopwords.py` (신규)

- [x] `GET /admin/stopwords?locale=ko` — 목록 (is_active 포함)
- [x] `POST /admin/stopwords` — 추가 (body: word, locale)
- [x] `DELETE /admin/stopwords/{id}` — 삭제
- [x] `POST /admin/stopwords/reload` — `invalidate_cache("stopwords")` 호출
- [x] require_admin_role(), log_audit(), handle_errors 적용

## 어드민 페이지

**파일:** `frontend/src/routes/admin/stopwords/+page.svelte` (신규)

- [x] 한국어/영어 탭 전환
- [x] 태그 형태 표시 (단어 + X 버튼으로 삭제)
- [x] 입력 필드 + "추가" 버튼
- [x] "캐시 갱신" 버튼
- [x] 어드민 사이드바 메뉴 추가
- [x] i18n 키: `admin.stopwords.*`

## 테스트
- [x] `tests/processor/test_keyword_extractor.py` 확장:
  - "1월" → 추출 키워드에 포함 안 됨
  - "12월" → 추출 키워드에 포함 안 됨
  - title_boost: 제목 단어가 본문 단어보다 높은 TF 점수
- [x] ruff 통과

## 완료 기준
- [x] `extract_keywords("12월 결산", "12월 실적 발표")` → keywords에 "12월" 없음
- [x] pytest 통과, ruff 통과
