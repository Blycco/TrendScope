#!/usr/bin/env bash
# deploy.sh — 블루-그린 전체 배포 스크립트 (idempotent)
# Usage: API_IMAGE_TAG=<tag> DOMAIN=<domain> bash scripts/deploy.sh
#
# 필수 환경변수:
#   API_IMAGE_TAG  — 배포할 Docker 이미지 태그 (e.g. abc1234)
#   DOMAIN         — 서비스 도메인 (e.g. example.com)

set -euo pipefail

# --- 필수 환경변수 검증 ---
: "${API_IMAGE_TAG:?API_IMAGE_TAG is required}"
: "${DOMAIN:?DOMAIN is required}"

COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="/opt/trendscope/backups"
HEALTH_SCRIPT="./scripts/healthcheck.sh"
SWITCH_SCRIPT="./scripts/switch-blue-green.sh"

# --- Active/Standby 슬롯 감지 ---
BLUE_RUNNING=$(docker inspect trendscope-api-blue --format '{{.State.Running}}' 2>/dev/null || echo "false")

if [[ "$BLUE_RUNNING" == "true" ]]; then
    ACTIVE_SLOT="blue"
    STANDBY_SLOT="green"
else
    ACTIVE_SLOT="green"
    STANDBY_SLOT="blue"
fi

STANDBY_SERVICE="api-${STANDBY_SLOT}"
STANDBY_CONTAINER="trendscope-api-${STANDBY_SLOT}"

echo "=== TrendScope Blue-Green Deploy: ${API_IMAGE_TAG} ==="
echo "    Active  : ${ACTIVE_SLOT}"
echo "    Standby : ${STANDBY_SLOT}"

# --- [1/7] DB 백업 ---
echo ""
echo "[1/7] DB 백업..."
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="${BACKUP_DIR}/trendscope_$(date +%Y%m%d_%H%M%S).sql"
docker exec trendscope-postgres pg_dump \
    -U "${POSTGRES_USER:-trendscope}" \
    "${POSTGRES_DB:-trendscope}" > "$BACKUP_FILE"
echo "       백업 완료: $BACKUP_FILE"

# 7일 이상 된 백업 자동 삭제
find "$BACKUP_DIR" -name "trendscope_*.sql" -mtime +7 -delete
echo "       7일 초과 백업 정리 완료"

# --- [2/7] DB 마이그레이션 ---
echo ""
echo "[2/7] DB 마이그레이션 (alembic upgrade head)..."
docker compose -f "$COMPOSE_FILE" run --rm \
    -e APP_ENV=production \
    "$STANDBY_SERVICE" \
    alembic upgrade head
echo "       마이그레이션 완료"

# --- [3/7] Standby 슬롯 기동 ---
echo ""
echo "[3/7] Standby(${STANDBY_SLOT}) 새 이미지 pull + 기동..."
API_IMAGE_TAG="$API_IMAGE_TAG" docker compose -f "$COMPOSE_FILE" pull "$STANDBY_SERVICE"
API_IMAGE_TAG="$API_IMAGE_TAG" docker compose -f "$COMPOSE_FILE" up -d "$STANDBY_SERVICE"
echo "       기동 완료"

# --- [4/7] Standby 헬스체크 ---
echo ""
echo "[4/7] Standby(${STANDBY_SLOT}) 헬스체크 (최대 60초)..."
HEALTH_OK=false
for i in $(seq 1 20); do
    if docker exec "$STANDBY_CONTAINER" curl -sf --max-time 3 http://localhost:8000/health > /dev/null 2>&1; then
        echo "       헬스체크 통과 (시도 ${i}/20)"
        HEALTH_OK=true
        break
    fi
    echo "       시도 ${i}/20 실패, 3초 후 재시도..."
    sleep 3
done

if [[ "$HEALTH_OK" != "true" ]]; then
    echo "ERROR: Standby 헬스체크 실패. Standby 종료 후 배포 중단 (Active 유지)." >&2
    docker compose -f "$COMPOSE_FILE" stop "$STANDBY_SERVICE"
    exit 1
fi

# --- [5/7] Nginx upstream 전환 ---
echo ""
echo "[5/7] Nginx upstream 전환 → ${STANDBY_SLOT}..."
bash "$SWITCH_SCRIPT" "$STANDBY_SLOT"
echo "       upstream 전환 완료"

# --- [6/7] 외부 smoke test ---
echo ""
echo "[6/7] 외부 smoke test (https://${DOMAIN}/health)..."
SMOKE_OK=false
for i in $(seq 1 5); do
    if curl -sf --max-time 10 "https://${DOMAIN}/health" > /dev/null 2>&1; then
        echo "       smoke test 통과 (시도 ${i}/5)"
        SMOKE_OK=true
        break
    fi
    echo "       시도 ${i}/5 실패, 3초 후 재시도..."
    sleep 3
done

if [[ "$SMOKE_OK" != "true" ]]; then
    echo "ERROR: smoke test 실패. upstream 복구 후 Standby 종료." >&2
    bash "$SWITCH_SCRIPT" "$ACTIVE_SLOT"
    docker compose -f "$COMPOSE_FILE" stop "$STANDBY_SERVICE"
    exit 1
fi

# --- [7/7] 구 슬롯 종료 ---
echo ""
echo "[7/7] 구 슬롯(${ACTIVE_SLOT}) 종료..."
docker compose -f "$COMPOSE_FILE" stop "api-${ACTIVE_SLOT}"
echo "       구 슬롯 종료 완료"

echo ""
echo "=== 배포 완료: ${STANDBY_SLOT} 슬롯 활성화 (tag: ${API_IMAGE_TAG}) ==="
