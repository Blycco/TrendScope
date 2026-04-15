# C-03 (Backend): 수동 리뷰 샘플러 API

> Branch: `feat/v6-review` | Agent: Backend
> 의존: B-07

## DB 마이그레이션

### `backend/db/migrations/041_cluster_review.sql` (신규)

```sql
BEGIN;
CREATE TYPE cluster_review_verdict AS ENUM ('v5_better','v6_better','tie','both_bad');
CREATE TABLE cluster_review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id_v5 UUID REFERENCES news_group(id) ON DELETE SET NULL,
    group_id_v6 UUID REFERENCES news_group_shadow(id) ON DELETE SET NULL,
    reviewer_id UUID NOT NULL REFERENCES users(id),
    verdict cluster_review_verdict NOT NULL,
    note TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_cluster_review_reviewed_at ON cluster_review(reviewed_at DESC);
CREATE INDEX idx_cluster_review_verdict ON cluster_review(verdict);
COMMIT;
```

## 엔드포인트

### `backend/api/routers/admin/cluster_review.py` (신규)

- [ ] `GET /admin/cluster-review/queue?limit=50` — 미리뷰 페어 샘플 (C-02 `get_cluster_pairs_by_date` 재사용)
- [ ] `POST /admin/cluster-review` — verdict 저장
  - body: `{group_id_v5, group_id_v6, verdict, note}`
- [ ] `GET /admin/cluster-review/stats` — verdict별 분포, 최근 7일 v6_better_ratio, 진행률 (목표 100건)
- [ ] admin 권한, audit_log

### `backend/db/queries/review.py` (신규)

- [ ] `insert_review`, `get_review_queue`, `get_review_stats`
- [ ] verdict별 counter 집계

## 테스트

- [ ] INSERT/SELECT 스모크
- [ ] stats 집계 정확성
- [ ] 비어드민 403

## 완료 조건

- [ ] pytest 통과
- [ ] PR develop 머지
