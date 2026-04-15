# A-03 (Backend): 스팸 라벨링 API + 어드민 UI

> Branch: `feat/v6-spam-xgb` (Algorithm 공유) | Agent: Backend + Frontend
> 의존: A-03 Algorithm 선행 불필요 (병행 가능)

## 배경

XGBoost 학습에 필요한 수동 라벨 데이터(1000건) 수집 도구. 어드민이 랜덤 샘플 기사에 spam/ham/unsure 라벨 부여.

## DB 마이그레이션

### `backend/db/migrations/035_spam_labels.sql` (신규)

- [ ] 파일:
  ```sql
  BEGIN;
  CREATE TYPE spam_label_kind AS ENUM ('spam','ham','unsure');
  CREATE TABLE spam_label (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      article_id UUID NOT NULL REFERENCES article(id) ON DELETE CASCADE,
      label spam_label_kind NOT NULL,
      labeler_id UUID NOT NULL REFERENCES users(id),
      note TEXT,
      labeled_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE UNIQUE INDEX uq_spam_label_article_labeler ON spam_label(article_id, labeler_id);
  CREATE INDEX idx_spam_label_label ON spam_label(label);
  CREATE INDEX idx_spam_label_labeled_at ON spam_label(labeled_at DESC);
  COMMIT;
  ```
- [ ] runner 등록

## API 엔드포인트

### `backend/api/routers/admin/spam_labels.py` (신규)

- [ ] `GET /admin/spam-labels/queue?limit=100` — 미라벨 기사 랜덤 샘플
  - WHERE `article.id NOT IN (SELECT article_id FROM spam_label WHERE labeler_id=$1)`
  - 쿼리 파라미터 `$1`, `$2` (asyncpg) 준수 (RULE 02)
- [ ] `POST /admin/spam-labels/{article_id}` — 라벨 저장
  - body: `{"label": "spam|ham|unsure", "note": "..."}`
  - INSERT ON CONFLICT (article_id, labeler_id) DO UPDATE
- [ ] `GET /admin/spam-labels/stats` — 라벨 수 집계 (label별, 최근 7일 추이)
- [ ] 모든 엔드포인트 admin 권한 체크 (기존 dependency 재사용)
- [ ] audit_log 기록 (RULE 16)

### `backend/api/schemas/admin.py` (수정)

- [ ] `SpamLabelCreate`, `SpamLabelResponse`, `SpamLabelStats` 추가

### `backend/db/queries/admin.py` (수정)

- [ ] `get_spam_label_queue`, `upsert_spam_label`, `get_spam_label_stats`

## Frontend

### `frontend/src/routes/admin/spam-labels/+page.svelte` (신규)

- [ ] 좌측: 대기 중 기사 리스트 (제목, 소스, 타임스탬프)
- [ ] 우측: 선택 기사 상세 (본문, URL, 메타)
- [ ] 하단: 3 버튼 `Spam` / `Ham` / `Unsure` + note textarea
- [ ] 단축키: `1`/`2`/`3` 로 라벨 지정
- [ ] 진행률: `{labeled}/{target=1000}`
- [ ] i18n 키 `admin.spam_labels.*` (RULE 13)

### 라우트 등록

- [ ] 어드민 사이드바에 "Spam Labels" 메뉴 추가
- [ ] 네비게이션 i18n

## 테스트

### `tests/test_spam_labels_api.py` (신규)

- [ ] queue endpoint: 미라벨 샘플만 반환
- [ ] upsert: 동일 labeler 동일 article 재라벨 → UPDATE
- [ ] stats: 라벨 수 정확 집계
- [ ] 비어드민 접근 시 403

### Frontend 테스트

- [ ] Playwright e2e 또는 vitest 컴포넌트 테스트 (기존 패턴)

## 완료 조건

- [ ] pytest + frontend 테스트 통과
- [ ] 로컬 어드민 UI에서 실제 라벨링 동작
- [ ] Algorithm 파트(`algorithm.md`) 와 동일 PR 또는 연속 머지
- [ ] audit_log 확인

## 이슈 연결

- [ ] 동일 이슈: A-03 Algorithm과 공유
