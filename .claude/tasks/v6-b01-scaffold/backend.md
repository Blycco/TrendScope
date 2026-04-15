# B-01 (Backend): 섀도우 테이블 마이그레이션

> Branch: `feat/v6-scaffold` (Algorithm 공유) | Agent: Backend

## DB 마이그레이션

### `backend/db/migrations/036_pipeline_shadow.sql` (신규)

```sql
BEGIN;

CREATE TABLE news_group_shadow (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    representative_keyword TEXT,
    keyword_list JSONB,
    score DOUBLE PRECISION,
    article_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pipeline_version VARCHAR(8) NOT NULL DEFAULT 'v6'
);
CREATE INDEX idx_news_group_shadow_created_at ON news_group_shadow(created_at DESC);

CREATE TABLE article_group_shadow (
    article_id UUID NOT NULL REFERENCES article(id) ON DELETE CASCADE,
    group_id UUID NOT NULL REFERENCES news_group_shadow(id) ON DELETE CASCADE,
    similarity DOUBLE PRECISION,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (article_id, group_id)
);
CREATE INDEX idx_article_group_shadow_group_id ON article_group_shadow(group_id);

CREATE TABLE group_label_shadow (
    group_id UUID PRIMARY KEY REFERENCES news_group_shadow(id) ON DELETE CASCADE,
    auto_label TEXT,
    auto_label_terms JSONB,
    topic VARCHAR(32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;
```

- [ ] runner 등록: `backend/db/migrations/runner.py` 목록 추가
- [ ] 7일 TTL 파티셔닝은 후속 (D-02 이후)

## 쿼리

### `backend/db/queries/shadow.py` (신규)

- [ ] `insert_shadow_group(conn, group) -> UUID`
- [ ] `insert_shadow_article_group(conn, article_id, group_id, sim)`
- [ ] `insert_shadow_group_label(conn, group_id, label, terms, topic)`
- [ ] 모두 asyncpg $1 parameterized (RULE 02)

## 테스트

- [ ] `tests/test_shadow_queries.py`: INSERT·SELECT 스모크
- [ ] 존재하지 않는 article_id FK 위반 케이스

## 완료 조건

- [ ] 마이그레이션 up/down 확인
- [ ] 쿼리 테스트 통과
