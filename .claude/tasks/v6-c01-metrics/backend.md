# C-01 (Backend): cluster_metrics_daily 마이그레이션

> Branch: `feat/v6-metrics` | Agent: Backend

## DB 마이그레이션

### `backend/db/migrations/040_cluster_metrics.sql` (신규)

```sql
BEGIN;
CREATE TABLE cluster_metrics_daily (
    date DATE NOT NULL,
    pipeline_version VARCHAR(8) NOT NULL,
    silhouette DOUBLE PRECISION,
    dbcv DOUBLE PRECISION,
    coherence_npmi DOUBLE PRECISION,
    topic_diversity DOUBLE PRECISION,
    outlier_ratio DOUBLE PRECISION,
    n_clusters INT,
    p50_cluster_size INT,
    intra_sim_mean DOUBLE PRECISION,
    intra_sim_std DOUBLE PRECISION,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (date, pipeline_version)
);
CREATE INDEX idx_cluster_metrics_date ON cluster_metrics_daily(date DESC);
COMMIT;
```

- [ ] runner 등록

## 쿼리

### `backend/db/queries/metrics.py` (신규)

- [ ] `upsert_daily_metrics(conn, date, version, metrics)`
- [ ] `get_metrics_range(conn, from_date, to_date, version) -> list`
- [ ] `get_latest_metrics_comparison(conn) -> dict[version, metrics]`

## 테스트

- [ ] UPSERT 중복 키 동작
- [ ] 범위 쿼리 성능

## 완료 조건

- [ ] 마이그레이션 확인
- [ ] 쿼리 pytest
