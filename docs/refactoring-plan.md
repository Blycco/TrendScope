# TrendScope 전체 리팩토링 계획 v4

> 작성일: 2026-04-09  
> 목적: 운영 검증에서 드러난 품질 문제 전면 해결 + 유료 판매 가능 수준으로 끌어올리기  
> 앱 목적: "두쫀쿠·라부부·버터떡" 같은 핫트렌드를 빠르게 캐치해서 알려줌  
> 참고: Exploding Topics, BuzzSumo, Google Trends, Brandwatch, Semrush UX 패턴

---

## 핵심 원칙

1. **하드코딩 제로**: 모든 규칙·파라미터는 DB에서 로드 → 어드민에서 관리
2. **가비지 인 → 가비지 아웃**: 필터·클러스터링이 먼저, UI는 그 다음
3. **납득 가능한 랭킹**: 왜 1위인지 사용자가 이해할 수 있어야 함
4. **"왜 지금인가"**: 매 트렌드 카드·상세 모두 "지금 봐야 하는 이유"를 설득
5. **역할별 가치**: 마케터·크리에이터·사업주 각각이 "이거 돈 주고 쓸 만하다" 느껴야 함

---

## 경쟁 포지셔닝

| 경쟁사           | 핵심 강점          | 설득 방식                        | TrendScope가 가져갈 것             |
| ---------------- | ------------------ | -------------------------------- | ---------------------------------- |
| Exploding Topics | 6개월 전 조기 감지 | "선착자 우위 = ROI 10배"         | Early Trend 강조, 기회 윈도우 표시 |
| Google Trends    | 무료·객관적 데이터 | "+300% 검색 증가"                | 절대 증가율 숫자 카드 전면 노출    |
| BuzzSumo         | 콘텐츠 성과 분석   | "이 포맷으로 5배 참여도"         | 포맷 추천 + 성공 콘텐츠 예시       |
| Brandwatch       | 소셜 감정 분석     | "감정 80% 긍정, 행동 윈도우 12h" | 플랫폼별 분포 + 감정 타임라인      |
| Semrush          | 경쟁사 동향 연동   | "경쟁사 광고비 +40% 증액"        | 브랜드 모니터링 강화               |

**TrendScope 차별화 포지셔닝**: 한국 최적화 + 조기 감지 + 역할별 액션 인사이트

> "Naver·카카오·커뮤니티·SNS에서 6시간 먼저 뜨는 트렌드. 크리에이터와 마케터가 먼저 알고 움직인다."

---

## 현재 구현 현황 (구현 전 필독)

이미 존재하는 기능들 — **새로 만들지 말고 활용/개선할 것**

| 기능                  | 파일                                                   | 상태                              |
| --------------------- | ------------------------------------------------------ | --------------------------------- |
| 트렌드 예측 (Prophet) | `/forecast/{id}`, `ForecastChart.svelte`               | Pro 게이팅, 작동 중               |
| AI 인사이트 (역할별)  | `/trends/{id}/insights`, `insights/+page.svelte`       | 존재, 내용 빈약                   |
| 키워드 그래프         | `KeywordGraph.svelte`                                  | 존재, 상세 페이지 하단에 숨어있음 |
| 감성 분석             | `SentimentChart.svelte`, `AspectSentimentChart.svelte` | 존재                              |
| 브랜드 모니터링       | `/brand/*`, Business+                                  | 존재, UI 노출 부족                |
| 콘텐츠 아이디어       | `/content/ideas`, `ContentIdeaCard.svelte`             | Pro 게이팅                        |
| 키워드 트래커         | `/tracker`, `/notifications/keywords`                  | 존재, UX 개선 필요                |
| 지역별 트렌드 맵      | `RegionalMap.svelte`, `/regional`                      | 존재                              |
| 메타 트렌드           | `MetaTrendsSection.svelte`                             | 존재                              |
| SSE 실시간            | `/live/trends`, EventSource                            | 존재                              |
| CSV/PDF 내보내기      | `/trends/export`                                       | Pro/Business 게이팅               |
| 공유 링크             | `/shared/{token}`                                      | 존재                              |
| 온보딩                | `/onboarding`, 역할 선택                               | 존재                              |
| 비교 차트             | `/compare`, `ComparisonChart.svelte`                   | 존재, Pro 노출 부족               |

**현재 없는 것**: burst_score 랭킹 반영, 플랫폼별 분포, 기회 윈도우 메시지, 트렌드 카드 요약, 적절한 클러스터 제목

---

## 하드코딩 전수조사 — DB 전환 대상

| 현재 위치                                   | 하드코딩 내용                                    | 전환 방식                      |
| ------------------------------------------- | ------------------------------------------------ | ------------------------------ |
| `keyword_extractor.py` `_KOREAN_STOP_WORDS` | 한국어 불용어 120개                              | `stopword` 신규 테이블         |
| `keyword_extractor.py` `_STOP_WORDS`        | 영어 불용어 50개                                 | `stopword` 신규 테이블         |
| `spam_filter.py` `_SPAM_KEYWORDS`           | 광고/도박/성인 키워드                            | `filter_keyword` 신규 테이블   |
| `spam_filter.py` (미구현)                   | 부고/비트렌드 키워드                             | `filter_keyword` 신규 테이블   |
| `news_crawler.py` (미구현)                  | 카테고리 분류 키워드                             | `category_keyword` 신규 테이블 |
| `semantic_clusterer.py` L19-28              | cosine/jaccard/temporal/source 가중치, threshold | `admin_settings` 확장          |
| `grouping.py` L53                           | Louvain threshold 0.55                           | `admin_settings` 확장          |
| `score_calculator.py` L25-29                | 점수 가중치 5개                                  | `admin_settings` 확장          |
| `score_calculator.py` L46-51                | 카테고리별 decay lambda                          | `admin_settings` 확장          |
| `spam_filter.py` L19-21                     | URL 비율 임계값, 최소 길이                       | `admin_settings` 확장          |

---

## Phase 0 — DB 스키마 및 공통 설정 인프라

> 모든 Phase의 기반.

### 0-1. 신규 테이블 3개

**마이그레이션:** `backend/db/migrations/023_config_tables.sql`

```sql
CREATE TABLE stopword (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    word       TEXT NOT NULL,
    locale     TEXT NOT NULL DEFAULT 'ko',
    is_active  BOOLEAN DEFAULT TRUE,
    source     TEXT DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX uq_stopword_word_locale ON stopword (word, locale);

CREATE TABLE filter_keyword (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword    TEXT NOT NULL UNIQUE,
    category   TEXT NOT NULL,  -- 'ad' | 'gambling' | 'adult' | 'obituary' | 'irrelevant' | 'custom'
    source     TEXT DEFAULT 'manual',  -- 'manual' | 'ai_suggested'
    is_active  BOOLEAN DEFAULT TRUE,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE category_keyword (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword    TEXT NOT NULL,
    category   TEXT NOT NULL,
    weight     FLOAT DEFAULT 1.0,
    locale     TEXT DEFAULT 'ko',
    is_active  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX uq_category_keyword_kw_cat ON category_keyword (keyword, category);
```

### 0-2. admin_settings 확장

**파일:** `backend/db/seeds/admin_settings.py`

```python
# 클러스터링
("cluster.cosine_weight",       "0.35", "0.35", "코사인 유사도 가중치"),
("cluster.jaccard_weight",      "0.40", "0.40", "Jaccard 키워드 가중치"),
("cluster.temporal_weight",     "0.05", "0.05", "시간 근접 가중치"),
("cluster.source_weight",       "0.20", "0.20", "소스 일치 가중치"),
("cluster.jaccard_early_filter","0.25", "0.25", "Jaccard 조기 필터"),
("cluster.threshold",           "0.65", "0.65", "합산 유사도 임계값"),
("cluster.outlier_sigma",       "0.7",  "0.7",  "이상치 제거 시그마"),
("cluster.temporal_decay_hours","24.0", "24.0", "시간 감쇠 (시간)"),
("cluster.louvain_threshold",   "0.70", "0.70", "Louvain 임계값"),
# 점수 가중치 (합계 100)
("score.weight_freshness",      "25", "25", "신선도"),
("score.weight_burst",          "25", "25", "버스트"),
("score.weight_article_count",  "15", "15", "기사 수"),
("score.weight_source_diversity","12","12", "소스 다양성"),
("score.weight_social",         "10", "10", "소셜 시그널"),
("score.weight_keyword",        "8",  "8",  "키워드 중요도"),
("score.weight_velocity",       "5",  "5",  "속도(velocity)"),
# 카테고리별 decay lambda
("decay.breaking","0.10","0.10","breaking 감쇠"),
("decay.politics","0.04","0.04","politics 감쇠"),
("decay.it",      "0.02","0.02","it 감쇠"),
("decay.default", "0.05","0.05","default 감쇠"),
# 스팸
("spam.url_ratio_threshold", "0.3","0.3","URL 비율 임계값"),
("spam.keyword_threshold",   "3",  "3",  "스팸 키워드 개수"),
("spam.min_content_length",  "20", "20", "최소 본문 길이"),
("spam.non_trend_min_hits",  "2",  "2",  "비트렌드 최소 매칭"),
# 키워드 추출
("keyword.title_boost",    "2.0","2.0","제목 토큰 가중치"),
("keyword.body_max_chars", "500","500","본문 최대 처리 글자"),
("keyword.top_k",          "10", "10", "추출 상위 K개"),
```

### 0-3. config_loader 공통 모듈

**파일:** `backend/processor/shared/config_loader.py` (신규)

```python
async def get_setting(key: str, default: float | str | int) -> ...:
    """admin_settings → Redis 5분 캐시"""

async def get_stopwords(locale: str) -> frozenset[str]:
    """stopword 테이블 → Redis 10분 캐시"""

async def get_filter_keywords(category: str | None = None) -> frozenset[str]:
    """filter_keyword 테이블 → Redis 10분 캐시"""

async def get_category_keywords() -> dict[str, list[tuple[str, float]]]:
    """category_keyword → {category: [(keyword, weight)]}"""

async def invalidate_cache(prefix: str) -> None:
    """어드민 변경 시 호출"""
```

---

## Phase 1 — 스팸/비트렌드 필터 DB화

### 1-1. spam_filter.py DB 기반 전환

**파일:** `backend/processor/shared/spam_filter.py`

- `get_filter_keywords()` → `_SPAM_KEYWORDS`, `_NON_TREND_KEYWORDS` 대체
- `spam.*` 설정값 → `get_setting()` 호출
- 부고 키워드 초기 시드: `부고, 서거, 별세, 추도, 조문, 빈소, 장례식, 사망, 부음, 향년, 작고, 타계`
- `reload_filter_cache()` 공개 함수 (어드민 변경 시 호출)

### 1-2. AI 자동 비트렌드 키워드 제안

**파일:** `backend/jobs/keyword_review_job.py` (신규)

- 24시간마다 실행
- 점수 하위 5% 기사 샘플링 → LLM 분석 → `filter_keyword`에 `source='ai_suggested'`, `is_active=FALSE` 저장
- 어드민 검토 후 활성화

### 1-3. 어드민 필터 키워드 관리 페이지

**Backend:** `backend/api/routers/admin/filter_keywords.py` (신규)

- `GET /admin/filter-keywords` (category, source, is_active 필터)
- `POST /admin/filter-keywords`
- `PATCH /admin/filter-keywords/{id}`
- `DELETE /admin/filter-keywords/{id}`
- `POST /admin/filter-keywords/reload`

**Frontend:** `frontend/src/routes/admin/filter-keywords/+page.svelte` (신규)

- 탭: AI 제안 대기 | 활성 | 전체
- 컬럼: keyword | category | source | confidence | is_active | 액션
- 일괄 승인/거부 기능

---

## Phase 2 — 불용어 DB화

### 2-1. keyword_extractor.py DB 기반 전환

**파일:** `backend/processor/shared/keyword_extractor.py`

- `_KOREAN_STOP_WORDS`, `_STOP_WORDS` → `get_stopwords('ko')`, `get_stopwords('en')` 로드
- `keyword.title_boost`, `keyword.top_k`, `keyword.body_max_chars` → `get_setting()` 호출
- 불용어 초기 시드 추가: `1월~12월, 1분기~4분기, 상반기, 하반기, 보도, 취재, 단독, 속보, 관계자, 억원, 조원`

### 2-2. 어드민 불용어 관리 페이지

**Backend:** `backend/api/routers/admin/stopwords.py` (신규)

- `GET /admin/stopwords?locale=ko`
- `POST /admin/stopwords`
- `DELETE /admin/stopwords/{id}`
- `POST /admin/stopwords/reload`

**Frontend:** `frontend/src/routes/admin/stopwords/+page.svelte` (신규)

- 한국어/영어 탭
- 태그 형태 표시 + X로 삭제
- 단어 입력 후 추가

---

## Phase 3 — 카테고리 분류 DB화

### 3-1. 카테고리 재분류 로직

**파일:** `backend/crawler/sources/news_crawler.py`

`_infer_category(title, body, feed_category)`:

- `get_category_keywords()` → 키워드 매칭
- weight 합산 최고 카테고리로 override (3점 이상)
- 미달 시 feed_category 유지

**초기 시드 키워드:**

- sports: 축구, 야구, 농구, 선수, 감독, 경기, 리그, 골, 우승, 올림픽, K리그
- tech: 반도체, AI, 인공지능, 스타트업, 앱, 게임, 소프트웨어, 클라우드
- economy: 주가, 코스피, 금리, 환율, GDP, 실적, 증시, 투자
- entertainment: 드라마, 영화, 아이돌, 배우, 콘서트, 앨범, 유튜브, 웹툰
- science: 연구, 논문, 우주, 실험, 임상, 발견, 특허

### 3-2. RSS 피드 중복 제거

**파일:** `backend/crawler/sources/rss_feeds.py`

- 블로터 중복 항목 1개 제거
- 스포츠/IT/경제 전용 피드 category 명시

### 3-3. 어드민 카테고리 키워드 관리 페이지

**Backend:** `backend/api/routers/admin/category_keywords.py` (신규)

**Frontend:** `frontend/src/routes/admin/category-keywords/+page.svelte` (신규)

- 카테고리별 탭
- 키워드 태그 + weight 슬라이더
- 새 키워드 추가 폼

---

## Phase 4 — 클러스터링·랭킹 알고리즘 개선

### 4-1. semantic_clusterer.py config_loader 연동

**파일:** `backend/processor/shared/semantic_clusterer.py`

- 모든 `_*_WEIGHT` 상수 → `get_setting("cluster.*")` 로드
- 타임스탬프 없을 때: `return 0.5` → `return 0.0` (neutral 제거, 무시)

### 4-2. grouping.py config_loader 연동

**파일:** `backend/processor/algorithms/grouping.py`

- `threshold=0.55` → `get_setting("cluster.louvain_threshold", 0.70)`

### 4-3. 버스트 점수 랭킹 통합

**파일:** `backend/processor/shared/score_calculator.py`

- 모든 `WEIGHT_*` → `get_setting("score.weight_*")`
- `ScoreInput`에 `burst_score: float = 0.0`, `velocity: float = 0.0` 추가
- `_normalize_burst()`, `_normalize_velocity()` 추가

**파일:** `backend/processor/stages/score.py`

- `detect_burst(articles)` 호출 → `ScoreInput(burst_score=...)` 전달
- 그룹 제목: 대표 기사 원제목 우선 (50자 초과 시 truncate + "…")
- 단일 기사 클러스터: score × 0.7 페널티

### 4-4. 랭킹 투명성 — burst 정보 API 노출

**파일:** `backend/api/schemas/trends.py`

- `TrendItem`에 `burst_score: float = 0.0` 추가

**마이그레이션:** `backend/db/migrations/024_burst_score_column.sql`

```sql
ALTER TABLE news_group ADD COLUMN IF NOT EXISTS burst_score FLOAT DEFAULT 0.0;
```

**파일:** `backend/api/routers/trends.py`, `backend/api/routers/dashboard.py`

- 응답에 `burst_score`, `summary` 필드 포함

---

## Phase 5 — 어드민 알고리즘 파라미터 UI

> admin_settings PATCH API 이미 존재. UI만 추가.

**파일:** `frontend/src/routes/admin/algorithm/+page.svelte` (신규)

섹션별:

- **클러스터링** — cosine/jaccard/temporal/source 가중치 슬라이더 (합계 표시)
- **점수 가중치** — freshness/burst/article/source/social/keyword/velocity (합계 100 표시)
- **스팸 필터** — URL 비율, 최소 길이, 키워드 임계값
- **신선도 감쇠** — 카테고리별 lambda
- **키워드 추출** — title_boost, body_max_chars, top_k
- 저장 → PATCH `/admin/settings` → `invalidate_cache()` 호출

---

## Phase 6 — 필터 UI 개선 (MultiSelect)

### 6-1. MultiSelect 컴포넌트

**파일:** `frontend/src/lib/components/MultiSelect.svelte` (신규)

- 드롭다운 형태, 외부 클릭 시 닫힘
- 체크박스 + 라벨 목록, 선택 개수 배지

### 6-2. 트렌드 목록 필터 교체

**파일:** `frontend/src/routes/trends/+page.svelte`

현재 `FilterButton` 나열 → MultiSelect로 교체:

- **카테고리** (다중): 경제 / IT / 엔터 / 스포츠 / 사회 / 과학 / 라이프 / 정치
- **플랫폼** (다중, 신규): 뉴스 / 네이버 / 카카오 / YouTube / TikTok / 커뮤니티
- **기간** (단일): 1h / 6h / 24h / 7d / 30d
- **방향** (다중, 신규): 급상승 / 성장 / 유지 / 하락
- 선택 필터: 태그로 표시, X로 개별 해제, "전체 초기화" 버튼

**정렬 옵션 추가:**

- 관련성 / 증가율순 / 최신순 / 기사 수순 (드롭다운)

---

## Phase 7 — TrendCard 전면 개선

**파일:** `frontend/src/components/TrendCard.svelte`

### 현재 문제

- 제목 = 키워드 join (의미 없음)
- 요약 없음
- 점수 숫자만 (왜 높은지 모름)
- 클릭 영역 부분적

### 개선 후 카드 구조

```
┌─────────────────────────────────────────────┐
│ [카테고리 뱃지]  [DirectionBadge]  [EarlyBadge] │
│                                             │
│ 트렌드 원제목 (2줄까지)                      │
│                                             │
│ 한 줄 요약 (summary 필드, gray-500, 2줄)    │
│                                             │
│ #해시태그1  #해시태그2  #해시태그3           │
│                                             │
│ ──────────────────────────────────────────  │
│ 🔥 +67% (24h)  |  기사 12건  |  출처 5개    │
│                          [Sparkline ↗]      │
└─────────────────────────────────────────────┘
```

**세부 변경:**

- 카드 전체 영역 클릭 가능 (`<a>` 래핑)
- 제목: 원제목 (Phase 4-3으로 fix), `line-clamp-2`
- 요약: `summary` 필드 2줄 표시 (대시보드 API에 추가)
- 키워드: `#해시태그` 스타일 상위 3개
- 증가율 표시: `+67% (24h)` 숫자 형태 (burst_score 기반 계산)
- burst_score > 0.7: 🔥 아이콘 + `bg-red-50` 배경 강조
- burst_score 0.4~0.7: 📈 아이콘
- burst_score < 0.4: ➡️ 아이콘

---

## Phase 8 — 대시보드 전면 개편

**파일:** `frontend/src/routes/+page.svelte`

### 현재 문제

- 트렌드/뉴스 리스트 나열만 있음
- "왜 지금 봐야 하나"가 없음
- 역할별 개인화 없음
- Bento 그리드 없음

### 개선 후 레이아웃

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 🔥 지금 가장 뜨는 것  (실시간 SSE 연동)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Bento Grid — 상위 5개 트렌드]
┌──────────────────────┬───────────┬──────────┐
│                      │ 트렌드 2  │ 트렌드 3 │
│   트렌드 1 (대형)    │ +230% ↑  │ +115% ↑  │
│   +450% (24h) 🔥     │ 요약 한줄 │ 요약 한줄│
│   요약 텍스트        ├───────────┴──────────┤
│                      │ 트렌드 4  │ 트렌드 5 │
│   [기사 12건 · 뉴스] │ +89% ↑   │ +54% ↑  │
└──────────────────────┴───────────┴──────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 📊 통계 카드 (4개)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 총 트렌드 | 총 뉴스 | 평균 점수 | Early Signals

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 🎯 {역할}을 위한 트렌드 (개인화, 최대 3개)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 "마케터라면 지금 이 3개 주목"
 → 역할 온보딩 + personalization API 활용

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 위젯 그리드 (카테고리 분포 | 소스 분포 | 키워드 클라우드)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ⚡ 떠오르는 신호 (Early Trends)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 "아직 메인스트림이 되기 전. 선착자 우위 가능"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 🗺️ 지역 트렌드 맵 + 🔥 핫 트렌드 순위
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**세부 변경:**

- Bento Grid 컴포넌트 신규: `BentoTrendGrid.svelte`
  - 1위 카드: 대형 (col-span-2), 2-5위: 소형
  - 각 카드: 제목 + 요약 + 증가율 + Sparkline
- "역할별 추천" 섹션: 로그인 + 온보딩 완료 시 노출
  - `/personalization` API + 역할 필터 조합
  - 미완료 시: "역할을 설정하면 맞춤 트렌드를 보여드려요" → 온보딩 CTA
- KeywordCloud 개선:
  - 🔥 아이콘 (burst_score > 0.7)
  - "NEW" 뱃지 (24시간 내 첫 등장, keyword_snapshot 비교)
  - 클릭 시 해당 트렌드 상세로 이동
- Early Trends 섹션 복사:
  - "아직 메인스트림이 아님. 지금 진입하면 경쟁이 적습니다." 카피
  - early_trend_score 기반 순위

---

## Phase 9 — 트렌드 상세 페이지 전면 개편

**파일:** `frontend/src/routes/trends/[id]/+page.svelte`

### 현재 문제

- 헤더 → 요약 → 차트 나열, "왜 지금인가" 없음
- 차트 순서 임의적
- 관련 기사 단순 링크 목록
- 플랫폼별 분포 없음
- 인사이트 버튼이 별도 페이지로 이동 (맥락 단절)

### 개선 후 페이지 구조

**섹션 1: Hero — "왜 지금인가"**

```
[트렌드 제목]  🔥 급상승 중
[카테고리] · [생성일시] · [점수 바]

┌─────────────────────────────────────────────┐
│ 💡 지금 이 트렌드인 이유                    │
│                                             │
│  🔥 지난 24시간 기사 +67% 증가              │
│  📡 뉴스 · 커뮤니티 · SNS 동시 언급         │
│  ⚡ Early Signal: 아직 메인스트림 전        │
└─────────────────────────────────────────────┘
```

**섹션 2: 빠른 지표 바**

```
기사 12건 | 출처 5개 | 📈 성장 중 | 📅 3시간 전 첫 등장
```

**섹션 3: 플랫폼별 분포 (신규)**

```
어디서 뜨고 있나?
뉴스 ████████░░ 45%
커뮤니티 ██████░░░░ 32%
SNS ████░░░░░░ 23%
```

- `news_article.source_type` 기반 집계
- 백엔드: `GET /trends/{id}` 응답에 `platform_distribution: dict` 추가

**섹션 4: BurstGauge**

```
모멘텀: [속도계 0~100] 78점 / 폭발적
"이 트렌드는 현재 상위 5% 성장 속도입니다"
```

**섹션 5: 차트 순서 (재정렬)**

1. `TrendChart` — 기사 수 시계열 (가장 먼저)
2. `KeywordTimeline` — 키워드 시간별 변화
3. `SentimentChart` — 감정 분포 도넛
4. `KeywordGraph` — 연관 키워드 그래프
5. `AspectSentimentChart` — 속성별 감성
6. `ForecastChart` — 12개월 예측 (Pro 게이팅)

각 차트 데이터 없을 때: "수집 중" 스피너 → "데이터가 쌓이면 자동으로 표시됩니다"

**섹션 6: 관련 기사 (전면 개선)**

현재: 단순 링크 목록

개선 후:

```
관련 기사 (12건)
[출처별 탭: 전체 | 뉴스 | 커뮤니티 | SNS]

┌─────────────────────────────────────────────┐
│ 📰 조선일보                    2시간 전      │
│ 삼성전자 반도체 사업 부진 심화…             │
│ 반도체 생산 차질로 3분기 실적 악화 전망     │
│ [읽기 →]                                    │
├─────────────────────────────────────────────┤
│ 📰 한겨레                      3시간 전      │
│ SK하이닉스도 동반 타격 불가피…              │
│ [읽기 →]                                    │
└─────────────────────────────────────────────┘
같은 출처 3건 이상 → "조선일보 외 2건 더보기"
```

- 백엔드 `TrendDetailResponse.articles`에 `source_type` 필드 추가
- 출처별 그룹화 렌더링

**섹션 7: 인라인 인사이트 미리보기 (신규)**

기존: 별도 `/trends/{id}/insights` 페이지로만 이동

개선 후: 상세 페이지 하단에 역할 선택 탭 + 핵심 1개 인사이트 미리보기

```
[마케터] [크리에이터] [사업주] [일반]

마케터 인사이트:
"지금 이 키워드로 광고 집행 시 경쟁이 낮은 구간.
 예상 참여율: 평소 대비 2.3배"
[전체 인사이트 보기 →] (Pro 게이팅)
```

**액션 버튼 바 (고정 하단)**

```
[💾 저장] [📤 공유] [🔔 알림 설정] [📊 콘텐츠 아이디어]
```

---

## Phase 10 — 인사이트 페이지 내용 강화

**파일:** `frontend/src/routes/trends/[id]/insights/+page.svelte`
**Backend:** `backend/api/routers/insights.py` (LLM 프롬프트 개선)

### 마케터 인사이트 (현재 → 개선)

현재: 일반적인 마케팅 방향 텍스트  
개선: 구체적 수치 + 행동 지침

```
📢 마케팅 타이밍
"이 트렌드는 현재 성장 초기입니다.
 광고 집행 골든타임: 향후 24~48시간"

📊 채널별 기회
- SNS 광고: 경쟁 낮음, CPM 상대적으로 저렴
- 콘텐츠 마케팅: 빠른 자연 유입 기대

🏢 경쟁 동향
- 브랜드 모니터링 키워드 관련 [브랜드명] 언급량 증가 중
- 경쟁사 광고 감지 여부 (brand_alert 연동)

🎯 추천 액션
1. SNS 포스팅 지금 제작
2. 관련 키워드 광고 집행 테스트 (소규모)
3. 트렌드 알림 설정 → 피크 시점 파악
```

### 크리에이터 인사이트

```
🎬 콘텐츠 추천 포맷
"숏폼 비디오 (15~30초)가 이 주제에 가장 효과적.
 유사 콘텐츠 평균 조회수: 23만회"

✍️ 제목 후보 3개 (자동 생성)
1. "[트렌드명]의 진짜 이유, 아무도 안 말해줘서 내가 정리함"
2. "[트렌드명] 뭔지 모르면 당신만 뒤처짐"
3. "요즘 [트렌드명] 왜 이렇게 난리야? 5분 정리"

#해시태그 추천 (10개)
#트렌드명 #관련키워드1 #관련키워드2 ...

⏰ 업로드 최적 타이밍
"오늘 오후 6~8시 (이 주제 검색 피크 시간대)"
```

### 사업주 인사이트

```
💰 시장 기회
"이 트렌드 관련 소비자 수요 급증 중
 예상 시장 확대 기간: 2~4주"

🔍 소비자 반응
감정 분석: 긍정 78% · 부정 12%
주요 불만: [aspect 분석 기반 부정 키워드]
주요 호감: [aspect 분석 기반 긍정 키워드]

📦 상품/서비스 기회
"[카테고리] 관련 제품/서비스 기획 시 참고"

🏃 경쟁사 움직임
Brand Monitor 연동: 경쟁 브랜드 언급 현황
```

### 공통 인사이트

```
📱 SNS 포스팅 초안 (자동 생성)
"[트렌드명] 요즘 왜 이렇게 핫한지 알아봤어요.
 핵심은 바로 [키워드]! #트렌드명 #관련태그"
[복사하기 버튼]
```

---

## Phase 11 — 키워드 트래커·알림 UX 개선

**파일:** `frontend/src/routes/tracker/+page.svelte`

### 현재 문제

- 키워드 추가·삭제만 있음
- 알림 기준 없음
- 현재 상태 조회 없음

### 개선 후 구조

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 🔔 내 트래킹 키워드  (Pro: 최대 5개)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────┐
│ 🔑 라부부          [지금 🔥 급상승 중]       │
│ 최근 7일: +340%  기사 23건  [상세보기 →]    │
│ 알림: 급상승 시 ✓  일일 요약 ✓             │
├─────────────────────────────────────────────┤
│ 🔑 버터떡          [성장 중 📈]              │
│ 최근 7일: +120%  기사 8건   [상세보기 →]    │
│ 알림: 급상승 시 ✓  일일 요약 ✗             │
└─────────────────────────────────────────────┘

[+ 키워드 추가] [알림 설정 →]
```

- 각 키워드 카드: 현재 트렌드 상태 + 증가율 + 관련 트렌드 바로가기
- 알림 설정: 급상승 시 / 일일 요약 / 주간 요약 (토글)
- Pro 미가입: "Pro 플랜으로 5개까지 트래킹 가능" PlanGate

---

## Phase 12 — 어드민 트렌드 품질 모니터링

**파일:** `frontend/src/routes/admin/trend-quality/+page.svelte` (신규)
**Backend:** `backend/api/routers/admin/trend_quality.py` (신규)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 오늘 파이프라인 현황
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 수집: 1,240건  |  스팸 필터: 187건 제거
 클러스터: 82개  |  오늘 트렌드: 23개

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 필터링 이유 분포 (파이 차트)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 광고성: 45%  |  부고/비트렌드: 28%  |  기타: 27%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 현재 랭킹 상위 10개 직접 확인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 [트렌드 목록 + 점수 구성 breakdown]
 [문제 있어 보임 → 수동 숨기기 버튼]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 클러스터 품질 점수 분포 (히스토그램)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**백엔드 API:**

- `GET /admin/trend-quality/pipeline-stats` — 오늘 파이프라인 통계
- `GET /admin/trend-quality/top-trends` — 랭킹 상위 10개 + score breakdown
- `POST /admin/trend-quality/hide/{group_id}` — 수동 숨기기

---

## Phase 13 — 공유·소셜 기능 강화

### 13-1. 트렌드 공유 개선

**파일:** `frontend/src/routes/shared/[token]/+page.svelte`

현재: 인증 없이 트렌드 데이터 조회  
개선: 공유 페이지에 "지금 이 트렌드인 이유" 헤더 포함 + TrendScope CTA

```
[공유된 트렌드 — 기본 정보 표시]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
이 트렌드 더 자세히 분석하려면?
TrendScope에서 예측·인사이트·알림을 무료로 사용해보세요.
[무료 시작하기 →]
```

### 13-2. 내보내기 품질 개선

**파일:** `backend/api/routers/trends.py` (`/trends/export`)

현재: CSV/PDF 기본 형태  
개선 후 PDF 리포트 포함:

- 트렌드 요약 + 차트 이미지 (서버 사이드 렌더링)
- 관련 기사 목록
- 인사이트 요약
- 브랜딩: TrendScope 로고 + 날짜

---

## Phase 14 — 온보딩 및 빈 상태 개선

### 14-1. 온보딩 플로우 강화

**파일:** `frontend/src/routes/onboarding/+page.svelte`

Step 추가:

- Step 1: 역할 선택 (현재)
- Step 2: 관심사 선택 (현재)
- Step 3: 첫 키워드 트래킹 설정 (신규) — "지금 가장 관심있는 키워드를 추가해보세요"
- Step 4: 알림 설정 (신규) — 이메일 알림 기본값 설정

### 14-2. 빈 상태 개선

**파일:** `frontend/src/lib/ui/EmptyState.svelte` (기존 개선)

상황별 메시지:

- 트렌드 없음: "아직 수집된 트렌드가 없습니다. 데이터는 매시간 업데이트됩니다."
- 필터 결과 없음: "선택한 필터에 맞는 트렌드가 없습니다. 필터를 조정해보세요."
- 트래커 키워드 없음: "추적할 키워드를 추가하면 실시간 알림을 받을 수 있습니다."
- 인사이트 없음: "이 트렌드의 인사이트를 생성하려면 [생성하기] 버튼을 눌러주세요."

---

## 전체 파일 목록

### 신규 DB 마이그레이션

- `023_config_tables.sql` — stopword, filter_keyword, category_keyword
- `024_burst_score_column.sql` — news_group.burst_score

### 신규 Backend

- `backend/processor/shared/config_loader.py`
- `backend/jobs/keyword_review_job.py`
- `backend/api/routers/admin/filter_keywords.py`
- `backend/api/routers/admin/stopwords.py`
- `backend/api/routers/admin/category_keywords.py`
- `backend/api/routers/admin/trend_quality.py`

### 수정 Backend

- `backend/processor/shared/spam_filter.py`
- `backend/processor/shared/keyword_extractor.py`
- `backend/processor/shared/semantic_clusterer.py`
- `backend/processor/algorithms/grouping.py`
- `backend/processor/shared/score_calculator.py`
- `backend/processor/stages/score.py`
- `backend/processor/stages/keywords.py`
- `backend/crawler/sources/news_crawler.py`
- `backend/crawler/sources/rss_feeds.py`
- `backend/api/schemas/trends.py` (burst_score, platform_distribution, source_type 추가)
- `backend/api/routers/trends.py` (summary, burst_score 포함)
- `backend/api/routers/dashboard.py` (summary 포함)
- `backend/api/routers/insights.py` (LLM 프롬프트 강화)
- `backend/db/seeds/admin_settings.py`

### 신규 Frontend 컴포넌트

- `frontend/src/lib/components/MultiSelect.svelte`
- `frontend/src/lib/components/BurstGauge.svelte`
- `frontend/src/lib/components/BentoTrendGrid.svelte`

### 신규 Frontend 페이지 (어드민)

- `frontend/src/routes/admin/filter-keywords/+page.svelte`
- `frontend/src/routes/admin/stopwords/+page.svelte`
- `frontend/src/routes/admin/category-keywords/+page.svelte`
- `frontend/src/routes/admin/algorithm/+page.svelte`
- `frontend/src/routes/admin/trend-quality/+page.svelte`

### 수정 Frontend

- `frontend/src/components/TrendCard.svelte` (전면 개선)
- `frontend/src/routes/+page.svelte` (Bento Grid, 역할별 추천, 섹션 재편)
- `frontend/src/routes/trends/+page.svelte` (MultiSelect 필터)
- `frontend/src/routes/trends/[id]/+page.svelte` (전면 개편)
- `frontend/src/routes/trends/[id]/insights/+page.svelte` (내용 강화)
- `frontend/src/routes/tracker/+page.svelte` (상태 표시, 알림 설정)
- `frontend/src/routes/shared/[token]/+page.svelte` (CTA 추가)
- `frontend/src/routes/onboarding/+page.svelte` (Step 추가)
- `frontend/src/lib/components/dashboard/KeywordCloud.svelte` (🔥 아이콘, NEW 뱃지)
- `frontend/src/lib/ui/EmptyState.svelte` (상황별 메시지)

---

## 작업 순서 (의존성)

```
[Phase 0] DB + config_loader + admin_settings 시드
    ↓
[Phase 1] spam_filter DB화 + AI 키워드 제안 + 어드민 filter-keywords
[Phase 2] keyword_extractor DB화 + 어드민 stopwords
[Phase 3] category_keyword DB화 + 카테고리 재분류 + 어드민 category-keywords
    ↓
[Phase 4] 클러스터링·랭킹 알고리즘 (config_loader 연동 + burst 통합)
[Phase 5] 어드민 알고리즘 파라미터 UI
    ↓
[Phase 6] MultiSelect 필터 컴포넌트
[Phase 7] TrendCard 전면 개선 (summary/burst API 완료 후)
[Phase 8] 대시보드 전면 개편 (BentoTrendGrid 신규)
[Phase 9] 트렌드 상세 페이지 전면 개편
[Phase 10] 인사이트 페이지 내용 강화
    ↓
[Phase 11] 키워드 트래커 UX 개선
[Phase 12] 어드민 트렌드 품질 모니터링
[Phase 13] 공유·내보내기 개선
[Phase 14] 온보딩·빈 상태 개선
```

---

## 브랜치 전략

```
feat/config-infrastructure    ← Phase 0 (DB 스키마, config_loader)
feat/managed-filters          ← Phase 1+2+3 (필터/불용어/카테고리 DB화)
fix/algorithm-tuning          ← Phase 4 (클러스터링·랭킹·burst)
feat/admin-ui                 ← Phase 5+12 (어드민 UI)
feat/trend-ux                 ← Phase 6+7+8+9+10 (필터·카드·대시보드·상세·인사이트)
feat/engagement               ← Phase 11+13+14 (트래커·공유·온보딩)
```

---

## 검증 기준

| 항목             | 기준                                               |
| ---------------- | -------------------------------------------------- |
| 부고 기사 필터링 | 랭킹 상위 20개에 부고 0건                          |
| 클러스터 품질    | "12월" 단일 키워드 클러스터 발생 0건               |
| 카드 제목        | 원제목 표시율 95% 이상                             |
| 카드 요약        | summary 필드 노출율 80% 이상                       |
| 랭킹 납득도      | burst_score > 0.7인 트렌드가 상위 10개 중 5개 이상 |
| pytest 커버리지  | ≥ 70% 유지                                         |
| ruff lint        | 통과                                               |
