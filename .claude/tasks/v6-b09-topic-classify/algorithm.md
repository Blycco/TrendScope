# B-09: KLUE-TC 기반 Zero-shot 토픽 분류

> Branch: `feat/v6-topic` | Agent: Algorithm | Track: B
> 의존: B-02
> Plan 참조: §B-09

## 배경

V5는 카테고리 분류 없음. V6은 클러스터별 KLUE-TC 7종(정치·경제·사회·생활문화·세계·IT과학·스포츠) + "etc" 자동 부여. UI/카테고리 필터 정확도 ↑.

## 목적

- KoE5 기반 zero-shot 분류 (프로토타입 임베딩 cosine)
- 임계 미달 시 "etc"
- 레이블 정의 admin JSON 편집 가능

## DB 마이그레이션

### `backend/db/migrations/038_group_topic.sql` (신규)

```sql
BEGIN;
ALTER TABLE news_group ADD COLUMN IF NOT EXISTS topic VARCHAR(32);
ALTER TABLE news_group_shadow ADD COLUMN IF NOT EXISTS topic VARCHAR(32);
CREATE INDEX IF NOT EXISTS idx_news_group_topic ON news_group(topic);
COMMIT;
```

## 구현

### `backend/processor/shared/v6/topic_classifier.py` (수정, stub 덮어씀)

```python
@dataclass
class TopicConfig:
    min_cosine: float = 0.35
    labels: dict[str, LabelSpec]  # name -> {description, keywords}


DEFAULT_LABELS = {
    "정치": {"desc": "정부·국회·정당·선거", "kw": ["대통령","국회","정당","선거","외교"]},
    "경제": {"desc": "기업·증시·부동산·금리", "kw": ["증시","환율","금리","부동산","실적"]},
    "사회": {"desc": "사건사고·교육·노동·복지", "kw": ["경찰","법원","교육","노동","사고"]},
    "생활문화": {"desc": "문화·예술·여행·음식", "kw": ["영화","음악","전시","여행","요리"]},
    "세계": {"desc": "국제·해외·외신", "kw": ["미국","중국","유럽","일본","국제"]},
    "IT과학": {"desc": "기술·AI·반도체·과학", "kw": ["AI","반도체","소프트웨어","연구","기술"]},
    "스포츠": {"desc": "축구·야구·올림픽", "kw": ["축구","야구","올림픽","선수","경기"]},
}


class TopicClassifier:
    def __init__(self, embedder: Embedder, config: TopicConfig):
        self.embedder = embedder
        self.config = config
        self._prototypes: dict[str, np.ndarray] = {}

    def warmup(self) -> None:
        names, texts = [], []
        for name, spec in self.config.labels.items():
            names.append(name)
            texts.append(spec["desc"] + " " + " ".join(spec["kw"]))
        protos = self.embedder.encode_batch(texts)
        self._prototypes = dict(zip(names, protos))

    def classify(self, centroid: np.ndarray) -> tuple[str, float]:
        best_name, best_sim = "etc", 0.0
        for name, proto in self._prototypes.items():
            sim = float(np.dot(centroid, proto))
            if sim > best_sim:
                best_name, best_sim = name, sim
        if best_sim < self.config.min_cosine:
            return "etc", best_sim
        return best_name, best_sim
```

- [ ] 클러스터 센트로이드 = 소속 기사 KoE5 임베딩 평균 → L2 재정규화
- [ ] admin: `v6.topic.min_cosine` (0.35), `v6.topic.labels` (JSON)
- [ ] 레이블 JSON 변경 시 `warmup()` 재실행

### `backend/processor/pipeline_v6.py` (수정)

- [ ] c-TF-IDF 라벨링 후 `topic_classifier.classify(centroid)` 호출
- [ ] `news_group.topic` 저장

## 테스트

### `tests/test_topic_classifier.py` (신규)

- [ ] `test_ko_political_article_classified`
- [ ] `test_ambiguous_article_etc`: 임계 미달 → "etc"
- [ ] `test_label_config_reload`: JSON 변경 후 재분류
- [ ] `test_prototypes_warmup`
- [ ] 수동 라벨 100건 top-1 accuracy ≥ 0.75

## 메트릭 목표

- top-1 accuracy ≥ 0.75
- "etc" 비율 ≤ 15%

## Prometheus

- [ ] `topic_classification_total{topic}` counter
- [ ] `topic_cosine_score` histogram

## 롤백

- `v6.topic.enabled=False` → topic NULL

## 완료 조건

- [ ] pytest 통과
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Feat: KLUE-TC zero-shot 토픽 분류 (V6 B-09)"`
