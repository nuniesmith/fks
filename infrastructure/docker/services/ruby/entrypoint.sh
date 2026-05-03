#!/bin/bash
# =============================================================================
# fks_ruby — Container Entrypoint
# Starts supervisord which manages data, engine, and web processes.
# =============================================================================
set -eo pipefail

echo "============================================"
echo "  fks_ruby — Starting Services"
echo "============================================"
echo "[startup] PYTHONPATH=${PYTHONPATH}"
echo "[startup] REDIS_URL=${REDIS_URL:-not set}"
echo "[startup] DATABASE_URL=${DATABASE_URL:+set (hidden)}"
echo "[startup] DATA_SERVICE_PORT=${DATA_SERVICE_PORT:-8000}"
echo "[startup] WEB_PORT=${WEB_PORT:-8080}"
echo ""

# Ensure log directories exist and are writable
mkdir -p /var/log/supervisor /var/log/fks
chmod -R 755 /var/log/supervisor /var/log/fks 2>/dev/null || true

# Ensure runtime directories exist
mkdir -p /app/data /app/models 2>/dev/null || true

echo "[startup] Launching supervisord..."
exec supervisord -n -c /etc/supervisor/conf.d/supervisord.conf
