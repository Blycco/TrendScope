#!/usr/bin/env bash
# healthcheck.sh — /health 엔드포인트 curl 체크
# Usage: ./scripts/healthcheck.sh [HOST] [MAX_RETRIES]

set -euo pipefail

HOST="${1:-http://localhost:8000}"
MAX_RETRIES="${2:-10}"
RETRY_INTERVAL=3

check_health() {
    local url="${HOST}/health"
    local response
    response=$(curl -sf --max-time 5 "$url" 2>/dev/null) || return 1
    echo "$response"
    return 0
}

echo "Checking health at ${HOST}/health ..."

for i in $(seq 1 "$MAX_RETRIES"); do
    if check_health; then
        echo "Health check passed (attempt $i/$MAX_RETRIES)"
        exit 0
    fi
    echo "Attempt $i/$MAX_RETRIES failed. Retrying in ${RETRY_INTERVAL}s..."
    sleep "$RETRY_INTERVAL"
done

echo "Health check FAILED after $MAX_RETRIES attempts." >&2
exit 1
