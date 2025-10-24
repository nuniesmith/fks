#!/usr/bin/env bash
# Enhanced startup script for fks_api with shared resources support
set -euo pipefail
IFS=$'\n\t'

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log(){ local lvl="$1"; shift; local msg="$*"; case "$lvl" in INFO) echo -e "${GREEN}[INFO]${NC} $msg";; WARN) echo -e "${YELLOW}[WARN]${NC} $msg";; ERROR) echo -e "${RED}[ERROR]${NC} $msg";; DEBUG) echo -e "${BLUE}[DEBUG]${NC} $msg";; esac; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
[ -f "$ENV_FILE" ] && set -a && source "$ENV_FILE" && set +a || log WARN "Local .env not found; continuing with current env"

# Use shared scripts if available
SHARED_DOCKER_DIR="$SCRIPT_DIR/shared/docker"
if [[ -d "$SHARED_DOCKER_DIR" ]]; then
    log INFO "✅ Shared docker resources found"
    COMPOSE_BASE="$SCRIPT_DIR/docker-compose.yml"
    COMPOSE_SHARED="$SHARED_DOCKER_DIR/compose/docker-compose.template.yml"
else
    log WARN "⚠️ Shared resources not found, using local compose only"
    COMPOSE_BASE="$SCRIPT_DIR/docker-compose.yml"
fi

# Configuration
USE_DEV=false
USE_PROD=false
NO_BUILD=false
WAIT_SECS=12
HEALTH_RETRIES=15
HEALTH_INTERVAL=2
FOLLOW_LOGS=false
ADDITIONAL_SERVICES=()

show_help(){ cat <<EOF
Usage: ./start.sh [options] [-- service1 service2 ...]

Options:
  --dev              Include development overrides (hot reload etc.)
  --prod             Include production overrides (resource limits, images)
  --no-build         Skip build/pull; just start existing images
  --wait SECONDS     Wait extra seconds after 'up' (default: $WAIT_SECS)
  --health-retries N Number of health probe retries (default: $HEALTH_RETRIES)
  --health-interval S Seconds between health probes (default: $HEALTH_INTERVAL)
  --logs             Follow logs after successful start
  --init-submodules  Initialize/update git submodules
  --help             Show this help

Service selection:
  By default all services in base compose are started. To restrict, append -- then names:
    ./start.sh --dev -- fks_api
EOF
}

check_submodules(){
    log INFO "🔍 Checking shared resource submodules..."
    
    if [[ ! -d "$SCRIPT_DIR/shared/docker/.git" || ! -d "$SCRIPT_DIR/shared/scripts/.git" ]]; then
        log WARN "⚠️ Shared submodules not initialized"
        log INFO "Initializing submodules..."
        git submodule update --init --recursive
        if [[ $? -eq 0 ]]; then
            log INFO "✅ Submodules initialized successfully"
        else
            log ERROR "❌ Failed to initialize submodules"
            return 1
        fi
    else
        log INFO "✅ Shared submodules are available"
    fi
}

parse_args(){
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dev) USE_DEV=true; shift;;
      --prod) USE_PROD=true; shift;;
      --no-build) NO_BUILD=true; shift;;
      --wait) WAIT_SECS="${2:-}"; shift 2;;
      --health-retries) HEALTH_RETRIES="${2:-}"; shift 2;;
      --health-interval) HEALTH_INTERVAL="${2:-}"; shift 2;;
      --logs) FOLLOW_LOGS=true; shift;;
      --init-submodules) git submodule update --init --recursive; exit 0;;
      --help|-h) show_help; exit 0;;
      --) shift; ADDITIONAL_SERVICES=("$@"); break;;
      *) log ERROR "Unknown option: $1"; show_help; exit 1;;
    esac
  done
}

check_tools(){
  if command -v docker-compose >/dev/null 2>&1; then COMPOSE_CMD="docker-compose"; elif docker compose version >/dev/null 2>&1; then COMPOSE_CMD="docker compose"; else log ERROR "Docker Compose not available"; exit 1; fi
  docker info >/dev/null 2>&1 || { log ERROR "Docker daemon not reachable"; exit 1; }
}

build_or_pull(){
  local files=("-f" "$COMPOSE_BASE")
  $USE_DEV && [ -f "$COMPOSE_DEV" ] && files+=( -f "$COMPOSE_DEV")
  $USE_PROD && [ -f "$COMPOSE_PROD" ] && files+=( -f "$COMPOSE_PROD")
  if $NO_BUILD; then
    log INFO "Skipping build/pull as requested (--no-build)"
  else
    log INFO "Ensuring images are present (build if context present, pull otherwise)"
    $COMPOSE_CMD "${files[@]}" build --pull --parallel || log WARN "Build step had issues; continuing"
  fi
  FILE_ARGS=("${files[@]}")
}

bring_up(){
  local up_args=("${FILE_ARGS[@]}" up -d)
  if ((${#ADDITIONAL_SERVICES[@]})); then up_args+=("${ADDITIONAL_SERVICES[@]}"); fi
  log INFO "Starting services..."
  $COMPOSE_CMD "${up_args[@]}"
}

health_checks(){
  log INFO "Running health probes (retries=$HEALTH_RETRIES interval=${HEALTH_INTERVAL}s)"
  local attempts=0
  local ok_api=false ok_db=false ok_redis=false
  while (( attempts < HEALTH_RETRIES )); do
    attempts=$((attempts+1))
    # API
    if ! $ok_api; then
      if curl -s -f http://localhost:8000/health >/dev/null 2>&1; then ok_api=true; log INFO "API healthy"; fi
    fi
    # Postgres container exists? use pg_isready
    if ! $ok_db && docker ps --format '{{.Names}}' | grep -q '^fks_postgres$'; then
      if docker exec fks_postgres pg_isready -U fks_user >/dev/null 2>&1; then ok_db=true; log INFO "Postgres ready"; fi
    fi
    # Redis
    if ! $ok_redis && docker ps --format '{{.Names}}' | grep -q '^fks_redis$'; then
      if docker exec fks_redis redis-cli ping 2>/dev/null | grep -q PONG; then ok_redis=true; log INFO "Redis ready"; fi
    fi
    if $ok_api && $ok_db && $ok_redis; then break; fi
    sleep "$HEALTH_INTERVAL"
  done
  ($ok_api && $ok_db && $ok_redis) || log WARN "Some services not healthy after retries (api=$ok_api db=$ok_db redis=$ok_redis)"
}

summary(){
  log INFO "Compose ps:"; $COMPOSE_CMD "${FILE_ARGS[@]}" ps || true
  log INFO "Key endpoints:"
  echo "  API:   http://localhost:8000"
  echo "  Auth:  http://localhost:9000 (if enabled)"
}

follow_logs(){
  $FOLLOW_LOGS || return 0
  log INFO "Following logs (Ctrl+C to detach)"
  $COMPOSE_CMD "${FILE_ARGS[@]}" logs -f ${ADDITIONAL_SERVICES[*]:-}
}

main(){
  parse_args "$@"
  check_submodules
  check_tools
  build_or_pull
  bring_up
  log INFO "Waiting ${WAIT_SECS}s for initial boot"; sleep "$WAIT_SECS"
  health_checks
  summary
  follow_logs
}

main "$@"
