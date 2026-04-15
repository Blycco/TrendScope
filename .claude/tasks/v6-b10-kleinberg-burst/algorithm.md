# B-10: Kleinberg Burst Detection (Breaking News)

> Branch: `feat/v6-kleinberg` | Agent: Algorithm | Track: B
> 의존: B-05
> Plan 참조: §B-10

## 배경

V5 burst는 velocity(기사 증가 속도) 기반만. Kleinberg 2-state automaton 추가하여 속보 구간 명시적 표기.

## 목적

- 클러스터별 timestamp 시퀀스 Kleinberg burst level 계산
- 기존 velocity_score와 선형 결합 `0.6·velocity + 0.4·kleinberg_level/3`
- breaking 태그: level ≥ 2 AND 최근 30분 기사 ≥ 50%

## DB 마이그레이션

### `backend/db/migrations/039_group_burst.sql` (신규)

```sql
BEGIN;
ALTER TABLE news_group
    ADD COLUMN IF NOT EXISTS burst_state VARCHAR(16),
    ADD COLUMN IF NOT EXISTS burst_level INT NOT NULL DEFAULT 0;
ALTER TABLE news_group_shadow
    ADD COLUMN IF NOT EXISTS burst_state VARCHAR(16),
    ADD COLUMN IF NOT EXISTS burst_level INT NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_news_group_burst_level ON news_group(burst_level DESC);
COMMIT;
```

## 구현

### `backend/processor/shared/v6/kleinberg.py` (수정, stub 덮어씀)

```python
@dataclass
class KleinbergConfig:
    s: float = 2.0    # state transition cost base
    gamma: float = 1.0
    n_states: int = 4  # 0,1,2,3
    breaking_level_threshold: int = 2
    breaking_recent_window_min: int = 30
    breaking_recent_ratio: float = 0.5


def detect_bursts(
    timestamps: list[datetime],
    config: KleinbergConfig,
) -> list[BurstInterval]:
    """Kleinberg 2-state enumeration (simplified).

    timestamps sorted ascending. Returns per-article state assignment.
    Reference: Kleinberg 2002 'Bursty and Hierarchical Structure in Streams'
    """
    # 자체 구현 또는 pybursts 의존성 활용
    ...


def assess_cluster(
    cluster: Cluster,
    config: KleinbergConfig,
) -> tuple[int, str | None]:
    """Return (level, state_tag)."""
    ts = sorted(a.published_at for a in cluster.articles)
    intervals = detect_bursts(ts, config)
    level = max((iv.level for iv in intervals), default=0)
    now = datetime.now(timezone.utc)
    recent = sum(
        1 for t in ts
        if (now - t).total_seconds() < config.breaking_recent_window_min * 60
    )
    ratio = recent / max(len(ts), 1)
    is_breaking = (
        level >= config.breaking_level_threshold
        and ratio >= config.breaking_recent_ratio
    )
    state = "breaking" if is_breaking else ("sustained" if level >= 1 else "idle")
    return level, state
```

- [ ] 자체 구현 우선, 복잡해지면 `pybursts` 의존성 추가
- [ ] 결정론: 동일 timestamps → 동일 level

### `backend/processor/algorithms/burst.py` (수정)

- [ ] 기존 `compute_burst_score` 확장:
  ```python
  score = (
      config.velocity_weight * velocity_score
      + config.kleinberg_weight * (kleinberg_level / 3.0)
  )
  ```
- [ ] admin: `v6.burst.kleinberg_weight` (0.4), `v6.burst.velocity_weight` (0.6)

### `backend/processor/pipeline_v6.py` (수정)

- [ ] 스코어 계산 전 `assess_cluster` 호출
- [ ] `news_group.burst_level`, `burst_state` 저장

## 테스트

### `tests/test_kleinberg.py` (신규)

- [ ] `test_quiet_stream_level_zero`: 일정 간격 → level 0
- [ ] `test_sudden_burst_level_high`: 급증 → level ≥ 2
- [ ] `test_breaking_requires_recent_ratio`: 과거 burst 만 있고 최근 없음 → breaking 아님
- [ ] `test_empty_timestamps`: 빈 리스트 → level 0
- [ ] `test_deterministic`
- [ ] `test_config_reload`

## 메트릭 목표

- breaking 태그 정밀도 ≥ 80% (수동 스팟체크)
- 일 breaking 클러스터 수 로그 관찰 가능

## Prometheus

- [ ] `burst_level_total{level}` counter
- [ ] `burst_breaking_total` counter

## 롤백

- `v6.burst.kleinberg_weight=0` → velocity만

## 완료 조건

- [ ] pytest 통과
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: Kleinberg burst detection (V6 B-10)"`
