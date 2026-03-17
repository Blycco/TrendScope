#!/usr/bin/env bash
# switch-blue-green.sh — Nginx upstream을 blue ↔ green으로 전환
# Usage: ./scripts/switch-blue-green.sh <blue|green>
#
# Prerequisites:
#   - docker compose -f docker-compose.prod.yml is running
#   - infra/nginx/upstream.conf exists and is mounted in nginx container

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
    TARGET_HOST="trendscope-api-blue:8000"
    STANDBY_CONTAINER="trendscope-api-blue"
else
    TARGET_HOST="trendscope-api-green:8000"
    STANDBY_CONTAINER="trendscope-api-green"
fi

echo "=== Blue-Green Switch: activating $TARGET ==="

# Step 1: Health check the target slot
echo "[1/4] Health checking $TARGET slot..."
"$HEALTH_SCRIPT" "http://${TARGET_HOST}" 10 || {
    echo "ERROR: $TARGET slot is not healthy. Aborting switch." >&2
    exit 1
}

# Step 2: Write new upstream config
echo "[2/4] Writing upstream config for $TARGET..."
cat > "$UPSTREAM_CONF" <<EOF
upstream api_backend {
    server ${TARGET_HOST};
}
EOF

# Step 3: Reload Nginx (zero-downtime)
echo "[3/4] Reloading Nginx..."
docker exec "$NGINX_CONTAINER" nginx -s reload

# Step 4: Verify traffic is routing to new slot
echo "[4/4] Verifying traffic routing..."
sleep 2
"$HEALTH_SCRIPT" "http://localhost" 5 || {
    echo "ERROR: Post-switch health check failed. Manual rollback required." >&2
    exit 1
}

echo "=== Switch to $TARGET COMPLETE ==="
echo "Previous slot can be stopped with:"
echo "  docker compose -f docker-compose.prod.yml stop $([ "$TARGET" == "blue" ] && echo "api-green" || echo "api-blue")"
