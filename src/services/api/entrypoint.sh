#!/bin/bash
# Enhanced entrypoint script for fks_api using shared scripts
set -euo pipefail

# Basic logging
log_info() { echo -e "\033[0;32m[INFO]\033[0m $(date -Iseconds) - $1"; }
log_warn() { echo -e "\033[1;33m[WARN]\033[0m $(date -Iseconds) - $1" >&2; }
log_error() { echo -e "\033[0;31m[ERROR]\033[0m $(date -Iseconds) - $1" >&2; }

log_info "🚀 Starting FKS API with shared scripts integration"

# Check if shared scripts are available
SHARED_DOCKER_ENTRYPOINT="/app/shared/scripts/docker/entrypoint-python.sh"
if [[ -f "$SHARED_DOCKER_ENTRYPOINT" ]]; then
    log_info "✅ Using shared Docker entrypoint script"
    exec "$SHARED_DOCKER_ENTRYPOINT" "$@"
fi

# Fallback to local entrypoint if shared script is not available
log_warn "⚠️ Shared entrypoint not found, using local fallback"

# Set environment
export SERVICE_TYPE="${SERVICE_TYPE:-api}"
export SERVICE_PORT="${SERVICE_PORT:-8000}"
export PYTHONPATH="/app/src:/app:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Activate virtual environment if available
if [[ -d "/opt/venv" ]]; then
    source /opt/venv/bin/activate
    log_info "✅ Activated virtual environment"
fi

# Try to run the FastAPI app
cd /app/src || cd /app

if [[ -f "fastapi_main.py" ]]; then
    log_info "🌐 Starting FastAPI application"
    exec uvicorn fastapi_main:app --host 0.0.0.0 --port "$SERVICE_PORT"
elif [[ -f "main.py" ]]; then
    log_info "🐍 Running main.py"
    exec python main.py
else
    log_error "❌ No entry point found (fastapi_main.py or main.py)"
    exit 1
fi
