# A-05: title/body 분리 정식화

> Branch: `feat/v6-preprocess-split` | Agent: Algorithm | Track: A
> 의존: 없음 (V6 임베딩에 선행 필수)
> Plan 참조: §A-05

## 배경

현행 `backend/processor/stages/cluster.py:~70` 에서 `text = f"{title} {body[:500]}"` 수동 합성 → 임베딩에 전달. 제목 가중이 문자 수 비례로 왜곡. body 절단 500자 고정.

## 목적

- title/body 독립 normalize
- body 동적 truncation (문장 경계 기반, 기본 800자)
- 임베딩 단계에서 title/body 각각 인코딩 후 가중 합산

## 사전 확인

- [ ] 현행 `text_normalizer.py::TextNormalizer` 메서드 목록
- [ ] `keyword_extractor.py` 가 이미 title/body split 지원 여부 확인 (V4)
- [ ] `semantic_clusterer.py::encode_article` 또는 호출부 시그니처

## 모듈 변경

### `backend/processor/shared/text_normalizer.py` (수정)

- [ ] `normalize(text)` 단일 진입점 유지 (하위 호환)
- [ ] 신규 메서드:
  - `normalize_title(text: str) -> str` — 제목용 정규화 (URL 제거·이모지 제거·공백 압축, 하지만 문장부호 유지)
  - `normalize_body(text: str, max_chars: int = 800) -> str` — 본문용
- [ ] body truncation:
  ```python
  def _truncate_at_sentence_boundary(text, max_chars):
      if len(text) <= max_chars: return text
      # 문장 경계 정규식: r"[.!?다]\s|[.!?다]$"
      # 경계 위치 중 max_chars 이하 최대값 선택
      # 경계 없으면 공백 경계로 fallback, 그것도 없으면 hard cut
  ```
- [ ] 테스트 커버: 문장 경계, 공백 경계, 하드 컷

### `backend/processor/shared/semantic_clusterer.py` (수정)

- [ ] `encode_article(article)` 시그니처 변경 또는 신규 함수 `encode_article_split(article, title_weight)`:
  ```python
  def encode_article_split(article, title_weight: float = 0.35) -> np.ndarray:
      title_emb = _model.encode([article.normalized_title], ...)[0]
      body_emb = _model.encode([article.normalized_body], ...)[0]
      combined = title_weight * title_emb + (1 - title_weight) * body_emb
      # L2 re-normalize
      return combined / np.linalg.norm(combined)
  ```
- [ ] V5 호환: 기존 `encode_article` 내부에서 합성 문자열 사용하던 경로 유지 (롤백용)
- [ ] 신규 admin 설정: `embed.title_weight` (기본 0.35)

### `backend/processor/stages/cluster.py` (수정)

- [ ] 기존 `text = f"{title} {body[:500]}"` 제거
- [ ] `encode_article_split(article, title_weight=config)` 로 교체
- [ ] V6 전용 경로는 B-02에서 덮어씀, 이 태스크는 V5에도 적용

### `backend/processor/shared/keyword_extractor.py` (확인만)

- [ ] 이미 `extract_keywords(title, body, ...)` 분리 지원 여부 재확인
- [ ] `body_max_chars` 파라미터 현행 500 → admin 노출 (기본 800)

### `backend/db/seeds/admin_settings.py` (수정)

```
('embed.title_weight', '0.35', 'float'),
('keyword.body_max_chars', '800', 'int'),  # 현행 500 → 800
```

## 테스트

### `tests/test_preprocess_split.py` (신규)

- [ ] `test_normalize_title_removes_urls`
- [ ] `test_normalize_body_keeps_sentence_boundary`
- [ ] `test_body_truncate_at_sentence`: 1000자 본문, max 800 → 800 이하 문장 경계에서 절단
- [ ] `test_body_truncate_no_boundary_falls_back_to_whitespace`
- [ ] `test_body_truncate_hard_cut_last_resort`
- [ ] `test_encode_article_split_weight_applied`: title_weight=1.0 → body 무시
- [ ] `test_empty_body_handled`: body 없는 기사 (title 단독 임베딩)

## 메트릭 목표

- title 전용 기사 처리 실패 0건
- body 절단이 문장 경계에서 이루어진 비율 ≥90%
- V5 → 개선된 normalize 사용 후 회귀 없음 (silhouette 변동 ≤ ±0.01)

## 롤백

1. **소프트**: `embed.title_weight=0.0` 설정 → body만 인코딩. 호환 동작 유지
2. **하드**: `stages/cluster.py` 에서 `encode_article_split` → 기존 합성 경로 복원

## 완료 조건

- [ ] pytest 통과
- [ ] 회귀 테스트: 기존 클러스터링 출력 변경폭 허용치 이내
- [ ] PR develop 머지

## 이슈 연결

- [ ] `gh issue create --title "Refactor: title/body 분리 정식화 + 동적 truncation (V6 A-05)"`
