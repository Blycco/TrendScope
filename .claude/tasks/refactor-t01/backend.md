# T-01: DB 스키마 + config_loader + admin_settings 시드
> Branch: feat/config-infrastructure | Agent: Backend + Algorithm
> 의존성: 없음 (최우선 착수) | 이후 T-02~06 모두 이 태스크에 의존

## 사전 확인
- [x] `docker exec trendscope-postgres-1 psql -U postgres -d trendscope -c "SELECT key FROM admin_settings LIMIT 5;"` 로 현재 DB 상태 확인
- [x] 최신 적용 마이그레이션 번호 확인 (`SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 3;` 또는 파일명 기준)

## DB 마이그레이션

### 021_config_tables.sql (신규)
- [x] `backend/db/migrations/021_config_tables.sql` 작성
  - `stopword` 테이블: id(UUID PK), word(TEXT), locale(TEXT DEFAULT 'ko'), is_active(BOOL), source(TEXT DEFAULT 'system'), created_at
  - UNIQUE INDEX: `uq_stopword_word_locale ON stopword(word, locale)`
  - `filter_keyword` 테이블: id(UUID PK), keyword(TEXT), category(TEXT), source(TEXT), is_active(BOOL), confidence(FLOAT DEFAULT 1.0), created_at, updated_at
  - UNIQUE INDEX: `uq_filter_keyword ON filter_keyword(keyword)`
  - `category_keyword` 테이블: id(UUID PK), keyword(TEXT), category(TEXT), weight(FLOAT DEFAULT 1.0), locale(TEXT DEFAULT 'ko'), is_active(BOOL), created_at
  - UNIQUE INDEX: `uq_category_keyword ON category_keyword(keyword, category)`
  - 전체 BEGIN/COMMIT 트랜잭션 래핑

### 022_burst_score_column.sql (신규)
- [x] `backend/db/migrations/022_burst_score_column.sql` 작성
  - `ALTER TABLE news_group ADD COLUMN IF NOT EXISTS burst_score FLOAT NOT NULL DEFAULT 0.0;`
  - `CREATE INDEX IF NOT EXISTS idx_news_group_burst_score ON news_group (burst_score DESC);`

## 시드 파일

### backend/db/seeds/stopwords.py (신규)
- [x] 한국어 불용어 시드 (locale='ko', source='system'):
  - **기존 이전** (keyword_extractor.py `_KOREAN_STOP_WORDS`):
    것이 하는 있는 하고 에서 으로 이다 했다 되는 하며 그리고 또한 이를 통해 이번 대한 위해
    관련 따르면 밝혔다 전했다 것으로 지난 올해 오늘 내년 최근 현재 이후 가운데 사이 가량 정도
    이상 미만 대비 전년 분기 한편 이날 기자 특파원 뉴스 연합뉴스 한겨레 매일경제 조선일보
    중앙일보 동아일보 한국경제 머니투데이 아시아경제 헤럴드경제
  - **신규 추가**:
    1월 2월 3월 4월 5월 6월 7월 8월 9월 10월 11월 12월
    1분기 2분기 3분기 4분기 상반기 하반기
    연도 기간 당일 전날 다음날 내달 다음달
    보도 취재 단독 속보 긴급 업데이트 확인 발표 입장 해명 논평 공식 관계자 측에따르면
    억원 조원 만원 달러 퍼센트 배증 감소 증가
- [x] 영어 불용어 시드 (locale='en', source='system') — `_STOP_WORDS` 전체 이전
- [x] `async def seed_stopwords(conn)` 함수 작성 (INSERT ... ON CONFLICT DO NOTHING)

### backend/db/seeds/filter_keywords.py (신규)
- [x] 스팸 키워드 시드 (category='ad', source='system'):
  광고 홍보 무료 할인 쿠폰 이벤트 당첨 대출 카지노 도박 슬롯 바카라 토토 베팅
  성인 만남 채팅 부업 재택 수익 클릭 지금바로 한정
  buy now free money click here limited offer casino gambling lottery prize viagra cialis weight loss
- [x] 비트렌드/부고 키워드 시드 (category='obituary', source='system', is_active=TRUE):
  부고 訃告 서거 별세 추도 조문 영결식 빈소 장례식 사망진단 부음 향년 작고 타계 유족 발인
- [x] `async def seed_filter_keywords(conn)` 함수 작성

### backend/db/seeds/category_keywords.py (신규)
- [x] 카테고리별 키워드 + weight 시드:
  - sports(1.0~2.0): 축구 야구 농구 배구 선수 감독 경기 리그 골 우승 올림픽 월드컵 K리그 MLB NBA
  - tech(1.0~1.5): 반도체 AI 인공지능 스타트업 앱 게임 소프트웨어 플랫폼 클라우드 코딩 데이터센터 GPU
  - economy(1.0~2.0): 주가 코스피 코스닥 금리 환율 GDP 실적 증시 채권 인플레이션 투자
  - entertainment(1.0~1.5): 드라마 영화 아이돌 배우 콘서트 앨범 유튜브 웹툰 OTT 뮤직비디오
  - science(1.0~1.5): 연구 논문 우주 실험 임상 발견 특허 NASA 백신
  - politics(1.0~1.5): 국회 대통령 정부 여당 야당 선거 법안 정책
  - society(1.0~1.2): 사건 사고 범죄 교육 복지 환경
- [x] `async def seed_category_keywords(conn)` 함수 작성

### backend/db/seeds/admin_settings.py 확장
- [x] 기존 파일에 다음 키 추가 (INSERT ... ON CONFLICT(key) DO NOTHING):
  - 클러스터링: cluster.cosine_weight(0.35) jaccard_weight(0.40) temporal_weight(0.05) source_weight(0.20)
    jaccard_early_filter(0.25) threshold(0.65) outlier_sigma(0.7) temporal_decay_hours(24.0) louvain_threshold(0.70)
  - 점수: score.weight_freshness(25) weight_burst(25) weight_article_count(15) weight_source_diversity(12)
    weight_social(10) weight_keyword(8) weight_velocity(5)
  - 감쇠: decay.breaking(0.10) decay.politics(0.04) decay.it(0.02) decay.default(0.05)
  - 스팸: spam.url_ratio_threshold(0.3) spam.keyword_threshold(3) spam.min_content_length(20) spam.non_trend_min_hits(2)
  - 키워드: keyword.title_boost(2.0) keyword.body_max_chars(500) keyword.top_k(10)

## config_loader.py (신규)

**파일:** `backend/processor/shared/config_loader.py`

- [x] DB 풀 + Redis 클라이언트 의존성 주입 (settings에서 가져옴, 기존 패턴 따를 것)
- [x] `async def get_setting(key, default)` — Redis `config:setting:{key}` 5분 캐시, 타입은 default 기준 캐스팅
- [x] `async def get_stopwords(locale='ko') -> frozenset[str]` — Redis `config:stopwords:{locale}` 10분 캐시
- [x] `async def get_filter_keywords(category=None) -> frozenset[str]` — Redis `config:filter_kw:{category|all}` 10분 캐시
- [x] `async def get_category_keywords() -> dict[str, list[tuple[str, float]]]` — Redis `config:category_kw` 10분 캐시
- [x] `async def invalidate_cache(prefix: str)` — 어드민 변경 시 호출, `DEL config:{prefix}:*`
- [x] 모든 함수: try/except + structlog 로깅 (RULE 06)
- [x] 타입 힌트 완비 (RULE 07)

## 마이그레이션 실행 연결
- [x] `backend/db/migrate.py` (또는 기존 마이그레이션 실행 파일) 에 021, 022 포함 확인
- [x] 시드 실행 엔트리포인트에 신규 seed 함수 3개 추가

## 테스트
- [x] `tests/processor/test_config_loader.py` (신규)
  - get_setting: 캐시 히트/미스, 타입 캐스팅
  - get_stopwords: 'ko' / 'en' 분리
  - get_filter_keywords: category 필터
  - invalidate_cache: Redis 키 삭제 확인

## 완료 기준
- [x] 마이그레이션 021, 022 적용 후 `\d stopword`, `\d filter_keyword`, `\d category_keyword`, `\d news_group` 확인
- [x] 시드 실행 후 각 테이블 row 수 확인 (stopword ≥ 80, filter_keyword ≥ 40, category_keyword ≥ 60)
- [x] pytest test_config_loader.py 통과
- [x] ruff 통과
