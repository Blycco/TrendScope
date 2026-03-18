#!/usr/bin/env bash
# switch-blue-green.sh — Nginx upstream을 blue ↔ green으로 전환
# Usage: ./scripts/switch-blue-green.sh <blue|green>
#
# Prerequisites:
#   - docker compose -f docker-compose.prod.yml is running
#   - infra/nginx/upstream.conf exists and is mounted in nginx container
#   - deploy.sh가 헬스체크 완료 후 이 스크립트를 호출함

set -euo pipefail

TARGET="${1:-}"
UPSTREAM_CONF="./infra/nginx/upstream.conf"
NGINX_CONTAINER="trendscope-nginx"
HEALTH_SCRIPT="./scripts/healthcheck.sh"

if [[ "$TARGET" != "blue" && "$TARGET" != "green" ]]; then
    echo "Usage: $0 <blue|green>" >&2
    exit 1
fi

if [[ "$TARGET" == "blue" ]]; then
    TARGET_HOST="api-blue:8000"   # Docker Compose 서비스명 (내부 DNS)
else
    TARGET_HOST="api-green:8000"  # Docker Compose 서비스명 (내부 DNS)
fi

echo "=== Blue-Green Switch: activating $TARGET ==="

# Step 1: Write new upstream config
echo "[1/3] Writing upstream config for $TARGET..."
cat > "$UPSTREAM_CONF" <<EOF
# 이 파일은 scripts/switch-blue-green.sh가 자동 갱신합니다. 수동 편집 금지.
upstream api_backend {
    server ${TARGET_HOST};  # Docker Compose 서비스명 기준
}
EOF

# Step 2: Reload Nginx (zero-downtime)
echo "[2/3] Reloading Nginx..."
docker exec "$NGINX_CONTAINER" nginx -s reload

# Step 3: Verify traffic is routing to new slot
echo "[3/3] Verifying traffic routing..."
sleep 2
"$HEALTH_SCRIPT" "http://localhost" 5 || {
    echo "ERROR: Post-switch health check failed. Manual rollback required." >&2
    exit 1
}

echo "=== Switch to $TARGET COMPLETE ==="
echo "Previous slot can be stopped with:"
echo "  docker compose -f docker-compose.prod.yml stop $([ "$TARGET" == "blue" ] && echo "api-green" || echo "api-blue")"
