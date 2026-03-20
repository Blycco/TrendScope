#!/usr/bin/env bash
# local-blue-green-test.sh — 로컬 Blue-Green 전환 드릴 검증
# Usage: bash scripts/local-blue-green-test.sh
set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
PASS=0
FAIL=0

log() { echo "[$(date +%H:%M:%S)] $*"; }
ok()  { log "✓ $*"; ((PASS++)); }
fail(){ log "✗ $*"; ((FAIL++)); }

# [1] Blue 슬롯 기동
log "=== [1/5] Blue 슬롯 기동 ==="
docker compose -f "$COMPOSE_FILE" up -d api-blue 2>/dev/null || true
sleep 5

# [2] Blue 헬스체크
log "=== [2/5] Blue 헬스체크 ==="
if docker exec trendscope-api-blue curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    ok "Blue /health 응답"
else
    fail "Blue /health 실패"
fi

# [3] Green 기동 + upstream 전환
log "=== [3/5] Green 기동 + upstream 전환 ==="
docker compose -f "$COMPOSE_FILE" up -d api-green 2>/dev/null || true
sleep 5

if docker exec trendscope-api-green curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    ok "Green /health 응답"
else
    fail "Green /health 실패"
fi

# upstream 전환 (switch-blue-green.sh 있으면 사용)
if [[ -f "./scripts/switch-blue-green.sh" ]]; then
    bash ./scripts/switch-blue-green.sh green && ok "upstream → green 전환" || fail "upstream 전환 실패"
fi

# [4] Smoke test
log "=== [4/5] Smoke test ==="
SMOKE_TARGETS=("/health" "/api/v1/trends")
for path in "${SMOKE_TARGETS[@]}"; do
    if curl -sf --max-time 5 "http://localhost:8000${path}" > /dev/null 2>&1; then
        ok "GET ${path} 200"
    else
        fail "GET ${path} 실패"
    fi
done

# [5] Blue 종료
log "=== [5/5] Blue 종료 ==="
docker compose -f "$COMPOSE_FILE" stop api-blue 2>/dev/null || true
ok "Blue 슬롯 종료"

# --- 결과 리포트 ---
echo ""
echo "=============================="
echo "  Blue-Green 드릴 결과 리포트"
echo "=============================="
echo "  PASS: ${PASS}"
echo "  FAIL: ${FAIL}"
echo "=============================="

if [[ "$FAIL" -gt 0 ]]; then
    echo "일부 검증 실패. 로그를 확인하세요."
    exit 1
else
    echo "모든 검증 통과."
fi
