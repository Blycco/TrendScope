# TrendScope

뉴스, SNS, 커뮤니티 트렌드를 수집하고 역할 맞춤형 인사이트로 변환하는 Trend Intelligence SaaS.

## 주요 기능

- **실시간 트렌드 피드** — RSS, Reddit, X/Twitter, YouTube, 커뮤니티에서 트렌드 수집 및 클러스터링
- **AI 액션 인사이트** — 마케터/크리에이터/사업자/일반 역할별 맞춤 행동 가이드
- **얼리 트렌드 탐지** — Z-score 기반 burst detection으로 초기 트렌드 포착
- **브랜드 모니터링** — 브랜드 언급 추적, 감성 분석, Slack/이메일 알림
- **콘텐츠 아이디어 생성** — 트렌드 기반 AI 콘텐츠 제안
- **어드민 대시보드** — 피드 헬스 모니터링, 유저/구독/소스/AI 설정 관리

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI, asyncpg, Redis 7, APScheduler |
| Frontend | SvelteKit, Svelte 5, Tailwind CSS |
| ML/NLP | soynlp, scikit-learn, XGBoost, sentence-transformers, Prophet |
| AI | Gemini Flash (configurable fallback) |
| DB | PostgreSQL 15 |
| Infra | Docker Compose, Nginx, Prometheus, Grafana |

## 아키텍처

```
[크롤러] RSS · Reddit · X · YouTube · 커뮤니티
    ↓
[프로세서] 중복제거(Bloom) → 키워드추출(soynlp+TF-IDF) → 클러스터링(MiniLM) → 스코어링
    ↓
[AI 엔진] 요약(Gemini Flash) → 감성분석(KoELECTRA) → 역할별 인사이트 생성
    ↓
[API 서버] FastAPI — 인증 · 플랜게이트 · 쿼터 · 캐시
    ↓
[프론트엔드] SvelteKit — 트렌드피드 · 인사이트 · 대시보드 · 어드민
```

**Docker 서비스**: API, Processor, Crawler, Frontend, Nginx, PostgreSQL, Redis, Prometheus, Grafana

## 빠른 시작

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에 필수 값 입력 (DB, Redis, JWT, API 키 등)

# 2. 전체 서비스 실행
docker compose up -d

# 3. 워커 추가 (크롤러 + 프로세서)
docker compose --profile workers up -d

# 4. 프론트엔드 추가
docker compose --profile frontend up -d

# 5. 모니터링 추가 (Prometheus + Grafana)
docker compose --profile monitoring up -d
```

헬스 체크: `http://localhost:8000/health`

## 개발 환경

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Frontend
cd frontend && npm install && npm run dev

# 테스트 (커버리지 70% 이상 필수)
pytest
```

## 프로젝트 구조

```
backend/
  api/            # FastAPI 앱 + 라우터 22개
  auth/           # JWT, OAuth(Google/Kakao), 2FA
  crawler/        # 뉴스/SNS/커뮤니티 크롤러
  processor/      # ML/NLP 알고리즘, 트렌드 분석
  db/             # asyncpg 쿼리 레이어
  jobs/           # 스케줄러 (감사로그 아카이빙, 쿼터 리셋 등)
  common/         # 공통 유틸 (캐시, 감사로그, 에러, 메트릭)
frontend/
  src/routes/     # 페이지 (트렌드, 뉴스, 트래커, 어드민, 인증 등)
  src/lib/        # API 클라이언트, 스토어, i18n, 컴포넌트
migrations/       # DB 마이그레이션 (12개)
tests/            # 테스트 60개
scripts/          # 배포·헬스체크·블루그린 스크립트
infra/            # Nginx, Prometheus, Grafana 설정
```

## API 개요

**공개**: 트렌드 피드, 뉴스, 인증(회원가입/로그인/OAuth), 헬스체크

**인증 필요**: 인사이트, 얼리 트렌드, 브랜드 모니터링, 콘텐츠 아이디어, 스크랩, 알림 설정, 구독, 공유 링크

**어드민**: 유저 관리, 구독/환불, API 소스 쿼터, 피드 소스 CRUD + 헬스, AI 설정, 감사로그, 분석

상세 스펙: [`context/api-spec.md`](context/api-spec.md)

## 요금제

| 플랜 | 트렌드 | 인사이트 | 얼리 트렌드 | 브랜드 모니터 | 콘텐츠 아이디어 |
|------|--------|---------|------------|-------------|---------------|
| Free | 10/일 | 3/일 | - | - | - |
| Pro (₩30k/월) | 무제한 | 무제한 | O | - | 5/일 |
| Business (₩90k/월) | 무제한 | 무제한 | O | 3개 | 무제한 |
| Enterprise | 무제한 | 무제한 | O | 무제한 | 무제한 |

## 스크립트

| 스크립트 | 용도 |
|---------|------|
| `scripts/deploy.sh` | 블루-그린 배포 (DB 백업 + 마이그레이션 포함) |
| `scripts/healthcheck.sh` | 컨테이너 헬스 프로브 |
| `scripts/switch-blue-green.sh` | Nginx 업스트림 전환 |
| `scripts/load-test.js` | k6 부하 테스트 (1,000 MAU 기준) |
