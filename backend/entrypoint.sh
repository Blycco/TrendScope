#!/bin/sh
set -e

echo "[entrypoint] Running migrations..."
python -m migrations.runner
echo "[entrypoint] Migrations complete. Starting server..."

exec "$@"
