# T-04: 카테고리 분류 DB화 + RSS 피드 정리 + 어드민
> Branch: feat/managed-filters | Agent: Backend + Frontend
> 의존성: T-01 완료 후 착수 (config_loader, category_keyword 테이블 필요)

## news_crawler.py 카테고리 재분류

**파일:** `backend/crawler/sources/news_crawler.py`

- [x] `_infer_category(title: str, body: str, feed_category: str) -> str` 함수 추가:
  - `await config_loader.get_category_keywords()` 호출 → `{category: [(kw, weight), ...]}`
  - 제목 + 본문 앞 200자 기준 키워드 매칭
  - 카테고리별 weight 합산
  - 최고 합산 카테고리의 합계 ≥ 3.0 → 해당 카테고리 반환
  - 미달 → `feed_category` 반환 (기존 유지)
- [x] 크롤링 파이프라인에서 `category = await _infer_category(title, body, feed["category"])` 적용

## rss_feeds.py 정리

**파일:** `backend/crawler/sources/rss_feeds.py`

- [x] 블로터(bloter.net) 중복 항목 확인 후 1개 제거
- [x] 스포츠 전용 피드: `category: "sports"` 명시 (현재 "general"인 것 수정)
- [x] IT/게임 전용 피드: `category: "tech"` 명시
- [x] 경제 전용 피드: `category: "economy"` 명시
- [x] `DEPRECATED: seed data only` 주석 유지

## 어드민 API

**파일:** `backend/api/routers/admin/category_keywords.py` (신규)

- [x] `GET /admin/category-keywords?category=sports` — 목록
- [x] `POST /admin/category-keywords` — 추가 (keyword, category, weight, locale)
- [x] `PATCH /admin/category-keywords/{id}` — weight 수정
- [x] `DELETE /admin/category-keywords/{id}` — 삭제
- [x] `POST /admin/category-keywords/reload` — `invalidate_cache("category_kw")`
- [x] require_admin_role(), log_audit(), handle_errors 적용

## 어드민 페이지

**파일:** `frontend/src/routes/admin/category-keywords/+page.svelte` (신규)

- [x] 카테고리별 탭: sports / tech / economy / entertainment / science / politics / society
- [x] 각 탭: 키워드 태그 + weight 수치 표시
- [x] 새 키워드 추가 폼: keyword 입력 + weight 슬라이더(0.5~2.0)
- [x] 어드민 사이드바 메뉴 추가
- [x] i18n 키: `admin.category_keywords.*`

## 테스트
- [x] `_infer_category("축구 월드컵 경기", "선수 리그 우승", "general")` → "sports"
- [x] `_infer_category("주가 코스피 금리", "투자 증시", "general")` → "economy"
- [x] `_infer_category("날씨 맑음", "오늘 날씨", "general")` → "general" (미달)

## 완료 기준
- [x] 스포츠 기사가 "economy" 카테고리에 들어가지 않음
- [x] 어드민 카테고리 키워드 페이지 빌드 통과
- [x] ruff 통과
