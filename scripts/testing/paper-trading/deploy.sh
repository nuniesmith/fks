#!/bin/bash
# =============================================================================
# FKS Paper Trading Test — Deploy (Main Test Runner)
# =============================================================================
# Runs the selected test type on the production server. Called by the workflow
# via ssh-deploy deploy-command.
#
# Required environment variables (set by the workflow):
#   FKS_TEST_LABEL          - Human-readable test label
#   FKS_TEST_TYPE           - Test type (paper-trading-soak, health-check, etc.)
#   FKS_TEST_ID             - Unique test identifier
#   FKS_DURATION_HOURS      - Test duration in hours
#   FKS_HEALTH_INTERVAL     - Health monitor interval in minutes
#   FKS_DOCKER_TOKEN        - Docker Hub token
#   FKS_DOCKER_USERNAME     - Docker Hub username
#   FKS_CLEAN_VOLUMES       - Whether to clean Docker volumes (true/false)
#   FKS_RUN_INITIAL_OPT     - Whether to run initial optimization (true/false)
#   FKS_ASSETS              - Comma-separated asset list
#   FKS_START_TIME          - Test start time (ISO 8601)
#   FKS_END_TIME            - Expected test end time (ISO 8601)
#   FKS_OPTIMIZE_INTERVAL   - Optimization interval (e.g., 6h)
#   FKS_OPTIMIZE_TRIALS     - Number of optimization trials
#   FKS_RUN_ID              - GitHub run ID
#   FKS_SHA                 - GitHub commit SHA
#   FKS_REF                 - GitHub ref name
#   FKS_ACTOR               - GitHub actor who triggered the run
#
# Monitoring environment variables (composable — works with any test type):
#   FKS_RSS_ENABLED         - Enable RSS memory monitoring (true/false)
#   FKS_RSS_INTERVAL        - RSS sampling interval in seconds (default: 10)
#   FKS_RSS_THRESHOLD       - RSS growth threshold in MB (default: 100)
#   FKS_RSS_CONTAINERS      - Container name regex (default: "janus|fks")
#   FKS_RSS_PUSHGATEWAY     - Prometheus Pushgateway URL (optional)
#   FKS_SKIP_DEPLOY         - Skip deployment, attach to running services (true/false)
#   FKS_NEEDS_DEPLOY        - Whether this test type needs deployment (true/false)
# =============================================================================
set -euo pipefail

echo "════════════════════════════════════════════════════════════"
echo "🚀 RUNNING: ${FKS_TEST_LABEL}"
echo "════════════════════════════════════════════════════════════"

TEST_TYPE="${FKS_TEST_TYPE}"
TEST_ID="${FKS_TEST_ID}"
TEST_DURATION="${FKS_DURATION_HOURS}"
TEST_DIR="$(cat /tmp/fks-test-dir 2>/dev/null || echo "$HOME/fks/test-results/$TEST_ID")"
HEALTH_INTERVAL="${FKS_HEALTH_INTERVAL}"
RSS_ENABLED="${FKS_RSS_ENABLED:-false}"
SKIP_DEPLOY="${FKS_SKIP_DEPLOY:-false}"
NEEDS_DEPLOY="${FKS_NEEDS_DEPLOY:-true}"
MONITORING_SCRIPT="$(dirname "$0")/monitoring.sh"

# =============================================================================
# HELPER: Launch a background process that survives SSH session termination.
# =============================================================================
# When this script is executed via the GitHub Actions ssh-deploy action, it runs
# inside an SSH session. Background processes started with plain `nohup ... &`
# are killed by systemd when the SSH session closes (KillUserProcesses scope
# cleanup), even though `nohup` protects against SIGHUP. Docker containers are
# unaffected because they're children of the Docker daemon (root session), but
# log collectors, health monitors, and the RSS memory monitor are shell
# processes owned by the `actions` user session and get reaped.
#
# `setsid` creates a new session ID for the child process, moving it out of the
# SSH session scope so systemd leaves it alone when the session ends.
#
# Usage:
#   run_detached <pid_file> <command> [args...]
#   Output is inherited from the caller (use redirects in the command itself).
#
# Example:
#   run_detached "$TEST_DIR/logs/my.pid" bash -c 'exec some_cmd >> logfile 2>&1'
# =============================================================================
run_detached() {
    local pid_file="$1"; shift
    setsid "$@" &
    local pid=$!
    echo "$pid" > "$pid_file"
    # Also disown so bash won't send SIGHUP from its own job control
    disown "$pid" 2>/dev/null || true
    echo "$pid"
}

# =============================================================================
# HELPER: POST to a mutating janus control route, carrying the bearer token.
# =============================================================================
# Since the janus-auth change (janus PR #161 / compose PR #215), every mutating
# (non-GET) janus route — including POST /api/services/start — requires
# `Authorization: Bearer <JANUS_API_TOKEN>`. janus is fail-closed: with the
# token set, an unauthenticated start POST returns 401 and janus stays in
# STANDBY (no ingestion, empty charts); with it unset, mutations return 503.
# Either way the plain `curl -X POST .../api/services/start` calls below would
# leave janus idle after a (re)deploy or a mid-run drop to standby.
#
# `_janus_token` resolves the token from the environment or, if not yet sourced,
# from the .env files this script uses (same precedence as the compose stack).
# `janus_post` attaches the header only when a token is configured, so behaviour
# is byte-for-byte unchanged while JANUS_API_TOKEN is unset.
_janus_token() {
    if [ -n "${JANUS_API_TOKEN:-}" ]; then
        printf '%s' "$JANUS_API_TOKEN"
        return 0
    fi
    local f t
    for f in ".env" "${TEST_DIR:-}/.env.test" "$HOME/fks/.env"; do
        [ -n "$f" ] && [ -f "$f" ] || continue
        t=$(grep -E "^JANUS_API_TOKEN=" "$f" 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '"' || true)
        if [ -n "$t" ]; then
            printf '%s' "$t"
            return 0
        fi
    done
}

# janus_post <url> — POST with the bearer when JANUS_API_TOKEN is set. Prints
# the response body; returns curl's exit status (callers keep their own
# `|| echo ""` / `|| true` fallbacks).
janus_post() {
    local url="$1" tok
    tok=$(_janus_token)
    if [ -n "$tok" ]; then
        curl -sf -X POST -H "Authorization: Bearer ${tok}" "$url"
    else
        curl -sf -X POST "$url"
    fi
}

# Export TEST_DIR for monitoring.sh to pick up
export FKS_TEST_DIR="$TEST_DIR"

# =============================================================================
# Cleanup stale monitoring processes from previous test runs
# =============================================================================
# Previous tests may have left behind detached log collectors, health monitors,
# and RSS monitors (setsid processes). These are harmless but waste resources
# and can cause confusion with duplicate docker-logs-follow processes.
# Kill them before starting fresh.
# =============================================================================
echo ""
echo "🧹 Cleaning up stale monitoring processes from previous runs..."
STALE_KILLED=0

# Kill old per-service docker log followers (e.g., "docker logs -f fks_janus")
while IFS= read -r line; do
    pid=$(echo "$line" | awk '{print $2}')
    cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
    if kill -TERM "$pid" 2>/dev/null; then
        echo "  ✅ Killed stale log collector (PID $pid): $cmd"
        STALE_KILLED=$((STALE_KILLED + 1))
    fi
done < <(ps aux | grep "[d]ocker logs -f fks_" || true)

# Kill old combined docker-compose log followers
while IFS= read -r line; do
    pid=$(echo "$line" | awk '{print $2}')
    if kill -TERM "$pid" 2>/dev/null; then
        echo "  ✅ Killed stale combined log collector (PID $pid)"
        STALE_KILLED=$((STALE_KILLED + 1))
    fi
done < <(ps aux | grep "[d]ocker compose.*logs -f" || true)
while IFS= read -r line; do
    pid=$(echo "$line" | awk '{print $2}')
    if kill -TERM "$pid" 2>/dev/null; then
        echo "  ✅ Killed stale compose plugin process (PID $pid)"
        STALE_KILLED=$((STALE_KILLED + 1))
    fi
done < <(ps aux | grep "[d]ocker-compose.*logs -f" || true)

# Kill old health monitor daemons
while IFS= read -r line; do
    pid=$(echo "$line" | awk '{print $2}')
    if kill -TERM "$pid" 2>/dev/null; then
        echo "  ✅ Killed stale health monitor (PID $pid)"
        STALE_KILLED=$((STALE_KILLED + 1))
    fi
done < <(ps aux | grep "[h]ealth-monitor-daemon" || true)

# Kill old RSS memory monitors
while IFS= read -r line; do
    pid=$(echo "$line" | awk '{print $2}')
    if kill -TERM "$pid" 2>/dev/null; then
        echo "  ✅ Killed stale RSS monitor (PID $pid)"
        STALE_KILLED=$((STALE_KILLED + 1))
    fi
done < <(ps aux | grep "[r]ss-memory-monitor" || true)

# Clean up stale PID files from previous test directories
for prev_dir in "$HOME/fks/test-results"/paper-trading-soak-*/; do
    [ -d "$prev_dir" ] || continue
    # Skip the current test directory
    [ "$prev_dir" = "$TEST_DIR/" ] && continue
    # Remove PID files whose processes are no longer running
    for pid_file in "$prev_dir"/logs/*.pid "$prev_dir"/monitoring/*.pid; do
        [ -f "$pid_file" ] || continue
        old_pid=$(cat "$pid_file" 2>/dev/null || true)
        if [ -n "$old_pid" ] && ! kill -0 "$old_pid" 2>/dev/null; then
            rm -f "$pid_file"
        fi
    done
done

if [ "$STALE_KILLED" -gt 0 ]; then
    echo "  🧹 Cleaned up $STALE_KILLED stale process(es)"
    sleep 1  # Brief pause for processes to exit
else
    echo "  ✅ No stale processes found"
fi

# ── Docker login ──
echo "${FKS_DOCKER_TOKEN}" | docker login -u "${FKS_DOCKER_USERNAME}" --password-stdin docker.io 2>/dev/null || true

# ── Generate .env or validate/fix existing one using run.sh (mirrors ci-cd) ──
echo "🔐 Setting up .env file..."
bash ./run.sh setup-env 2>/dev/null || true

# ── Build compose command ──
COMPOSE_BASE="docker compose -p fks --env-file .env -f infrastructure/compose/docker-compose.yml -f infrastructure/compose/docker-compose.prod.yml"
if ([ "$TEST_TYPE" = "paper-trading-soak" ] || [ "$TEST_TYPE" = "audit-72h-soak" ]) && [ -f "$TEST_DIR/.env.test" ]; then
    COMPOSE_CMD="$COMPOSE_BASE --env-file $TEST_DIR/.env.test"
else
    COMPOSE_CMD="$COMPOSE_BASE"
fi

# =============================================================================
# Helper: Start RSS monitoring if enabled (composable layer)
# =============================================================================
start_rss_monitoring() {
    if [ "$RSS_ENABLED" != "true" ]; then
        return 0
    fi

    echo ""
    echo "📈 RSS monitoring is enabled — starting composable monitoring layer..."

    if [ -f "$MONITORING_SCRIPT" ]; then
        chmod +x "$MONITORING_SCRIPT"
        bash "$MONITORING_SCRIPT" start || {
            echo "  ⚠️ RSS monitoring failed to start (non-fatal, continuing test)"
        }
    else
        echo "  ⚠️ Monitoring script not found at: $MONITORING_SCRIPT"
        echo "     RSS monitoring will be skipped."
        echo "     Expected: scripts/testing/paper-trading/monitoring.sh"
    fi
}

# ===========================================================================
# TEST TYPE: paper-trading-soak
# ===========================================================================
if [ "$TEST_TYPE" = "paper-trading-soak" ]; then
    echo "📋 Starting ${TEST_DURATION}-hour paper trading soak test..."
    echo ""

    # Source env files
    set -a
    [ -f .env ] && source .env
    [ -f "$TEST_DIR/.env.test" ] && source "$TEST_DIR/.env.test"
    set +a

    # Stop or clean existing services
    if [ "${FKS_CLEAN_VOLUMES}" = "true" ]; then
        echo "🧹 Cleaning volumes (fresh start)..."
        $COMPOSE_CMD down -v --remove-orphans 2>/dev/null || true
    else
        echo "🛑 Stopping existing containers..."
        $COMPOSE_CMD down --remove-orphans 2>/dev/null || true
    fi

    # Pull and start
    echo "📥 Pulling latest images..."
    $COMPOSE_CMD pull --ignore-pull-failures 2>&1 || true

    echo "🚀 Starting services..."
    $COMPOSE_CMD up -d --no-build 2>&1

    echo "⏳ Waiting for services to initialize (45s)..."
    sleep 45

    # ── Safety check: verify paper trading mode ──
    echo ""
    echo "🔒 Verifying paper trading safety..."
    SAFETY_OK=true

    if docker ps -q -f name=fks_execution 2>/dev/null | grep -q .; then
        # Standalone execution container exists — check it directly
        REAL_ORDERS=$(docker exec fks_execution env 2>/dev/null | grep "REAL_ORDERS_ENABLED" | cut -d'=' -f2 || echo "unknown")
        TRADE_MODE=$(docker exec fks_execution env 2>/dev/null | grep "TRADING_MODE" | cut -d'=' -f2 || echo "unknown")
        if [ "$REAL_ORDERS" = "false" ]; then
            echo "  ✅ REAL_ORDERS_ENABLED=false (execution standalone)"
        else
            echo "  🚨 REAL_ORDERS_ENABLED=$REAL_ORDERS (execution standalone) — ABORTING!"
            SAFETY_OK=false
        fi
        if [ "$TRADE_MODE" = "simulation" ] || [ "$TRADE_MODE" = "paper" ]; then
            echo "  ✅ TRADING_MODE=$TRADE_MODE (execution standalone)"
        else
            echo "  🚨 TRADING_MODE=$TRADE_MODE (execution standalone) — ABORTING!"
            SAFETY_OK=false
        fi
    fi

    # Execution is embedded inside Janus — check Janus for trading mode and execution config
    if docker ps -q -f name=fks_janus 2>/dev/null | grep -q .; then
        JANUS_EXEC_ENABLED=$(docker exec fks_janus printenv ENABLE_EXECUTION 2>/dev/null || echo "")
        JANUS_EXEC_MODE=$(docker exec fks_janus printenv EXECUTION_MODE 2>/dev/null || echo "")
        JANUS_MODE=$(docker exec fks_janus printenv TRADING_MODE 2>/dev/null || echo "")

        if [ "$JANUS_EXEC_ENABLED" = "true" ]; then
            echo "  ✅ Execution enabled inside Janus (ENABLE_EXECUTION=true)"
        elif [ -n "$JANUS_EXEC_ENABLED" ]; then
            echo "  ℹ️  Execution disabled in Janus (ENABLE_EXECUTION=$JANUS_EXEC_ENABLED)"
        fi

        if [ -n "$JANUS_EXEC_MODE" ]; then
            if [ "$JANUS_EXEC_MODE" = "simulated" ] || [ "$JANUS_EXEC_MODE" = "paper" ] || [ "$JANUS_EXEC_MODE" = "paper_trading" ] || [ "$JANUS_EXEC_MODE" = "simulation" ]; then
                echo "  ✅ EXECUTION_MODE=$JANUS_EXEC_MODE (janus)"
            elif [ "$JANUS_EXEC_MODE" = "live" ]; then
                echo "  🚨 EXECUTION_MODE=live (janus) — ABORTING! Paper trading must not use live execution."
                SAFETY_OK=false
            else
                echo "  🚨 EXECUTION_MODE=$JANUS_EXEC_MODE (janus) — unrecognised mode, ABORTING!"
                SAFETY_OK=false
            fi
        elif [ "$JANUS_EXEC_ENABLED" = "true" ]; then
            echo "  ⚠️  EXECUTION_MODE not set but execution is enabled — will default to 'simulated'"
        fi

        if [ -n "$JANUS_MODE" ]; then
            if [ "$JANUS_MODE" = "simulation" ] || [ "$JANUS_MODE" = "paper" ] || [ "$JANUS_MODE" = "paper_trading" ]; then
                echo "  ✅ TRADING_MODE=$JANUS_MODE (janus)"
            elif [ "$JANUS_MODE" = "live" ]; then
                echo "  🚨 TRADING_MODE=live (janus) — ABORTING!"
                SAFETY_OK=false
            else
                echo "  ⚠️  TRADING_MODE=$JANUS_MODE (janus) — unexpected value"
            fi
        fi
    fi

    if [ "$SAFETY_OK" != "true" ]; then
        echo ""
        echo "🚨🚨🚨 SAFETY CHECK FAILED — SHUTTING DOWN 🚨🚨🚨"
        $COMPOSE_CMD down --remove-orphans 2>/dev/null || true
        exit 1
    fi
    echo "  ✅ Paper trading mode confirmed"
    echo ""

    # ── Start Janus processing services ──
    # Janus modules (forward, backward, CNS, data) register with the
    # supervisor but idle in standby unless JANUS_AUTO_START=true or an
    # explicit POST /api/services/start is issued.
    echo "🔌 Starting Janus processing services..."
    JANUS_PORT=7000
    SVC_STATUS=$(curl -sf "http://localhost:${JANUS_PORT}/api/services/status" 2>/dev/null || echo "")
    SVC_STATE=$(echo "$SVC_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('service_state','unknown'))" 2>/dev/null || echo "unknown")

    if [ "$SVC_STATE" = "standby" ] || [ "$SVC_STATE" = "stopped" ]; then
        START_RESP=$(janus_post "http://localhost:${JANUS_PORT}/api/services/start" 2>/dev/null || echo "")
        if echo "$START_RESP" | grep -q '"success".*true'; then
            echo "  ✅ Janus services started (was: $SVC_STATE)"
        else
            echo "  ⚠️ Could not start Janus services via API (response: $START_RESP)"
        fi
        sleep 5
    elif [ "$SVC_STATE" = "running" ]; then
        echo "  ✅ Janus services already running"
    else
        echo "  ⚠️ Could not determine Janus service state ($SVC_STATE), attempting start..."
        janus_post "http://localhost:${JANUS_PORT}/api/services/start" 2>/dev/null || true
        sleep 5
    fi
    echo ""

    # ── Run initial optimization ──
    if [ "${FKS_RUN_INITIAL_OPT}" = "true" ]; then
        echo "🔧 Running initial optimization..."
        docker exec fks_janus /app/janus-optimizer run-once --quick --assets "${FKS_ASSETS}" 2>&1 || echo "⚠️ Initial optimization had issues (non-fatal)"
        echo ""
    fi

    # ── Start log collectors ──
    # NOTE: Uses run_detached / setsid so collectors survive SSH session end.
    echo "📝 Starting log collectors..."
    mkdir -p "$TEST_DIR/logs"

    # Combined log
    COLLECTOR_PID=$(run_detached "$TEST_DIR/logs/log-collector.pid" \
        bash -c "exec $COMPOSE_CMD logs -f --timestamps >> '$TEST_DIR/logs/all-services.log' 2>'$TEST_DIR/logs/log-collector.err'")

    sleep 2
    if ps -p $COLLECTOR_PID > /dev/null 2>&1; then
        echo "  ✅ Combined log collector running (PID: $COLLECTOR_PID)"
    else
        echo "  ⚠️ Combined log collector failed — check $TEST_DIR/logs/log-collector.err"
    fi

    # Individual service logs (execution is embedded in janus, no separate container)
    for svc in janus nginx web redis postgres questdb authelia grafana prometheus alertmanager; do
        if docker ps --filter "name=fks_${svc}" --format '{{.Names}}' 2>/dev/null | grep -q "fks_${svc}"; then
            run_detached "$TEST_DIR/logs/${svc}-collector.pid" \
                bash -c "exec docker logs -f 'fks_${svc}' >> '$TEST_DIR/logs/${svc}.log' 2>&1" > /dev/null
            echo "  ✅ ${svc}.log"
        fi
    done
    echo ""

# ===========================================================================
# TEST TYPE: health-check
# ===========================================================================
elif [ "$TEST_TYPE" = "health-check" ]; then
    echo "🏥 Running health check on all services..."
    echo ""
    mkdir -p "$TEST_DIR/logs"

    {
        echo "# Health Check Results"
        echo "# Test ID: $TEST_ID"
        echo "# Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "# ──────────────────────────────────────────"
        echo ""

        echo "## Container Status"
        docker ps -a --filter "name=fks" --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}\t{{.Ports}}" 2>/dev/null || echo "Could not list containers"
        echo ""

        echo "## Resource Usage"
        docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>/dev/null | grep fks || echo "Could not get stats"
        echo ""

        echo "## Health Endpoints"
        for endpoint in \
            "Janus:http://localhost:8080/health" \
            "Janus-alt:http://localhost:7000/health" \
            "Janus-api:http://localhost:8080/api/v1/health" \
            "QuestDB:http://localhost:9000" \
            "Prometheus:http://localhost:9090/-/healthy" \
            "Grafana:http://localhost:3000/api/health" \
            "Alertmanager:http://localhost:9093/-/healthy"; do
            NAME="${endpoint%%:*}"
            URL="${endpoint#*:}"
            STATUS_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null || echo "000")
            if [ "$STATUS_CODE" = "200" ] || [ "$STATUS_CODE" = "301" ] || [ "$STATUS_CODE" = "302" ]; then
                echo "  ✅ $NAME ($URL) — HTTP $STATUS_CODE"
            elif [ "$STATUS_CODE" = "000" ]; then
                echo "  ⚠️  $NAME ($URL) — not reachable"
            else
                echo "  ❌ $NAME ($URL) — HTTP $STATUS_CODE"
            fi
        done
        echo ""

        echo "## Database Checks"
        # Load Redis password for authenticated check
        _REDIS_PW=""
        if [ -f "$TEST_DIR/.env.test" ]; then
            _REDIS_PW=$(grep -E "^REDIS_PASSWORD=" "$TEST_DIR/.env.test" | head -1 | cut -d'=' -f2- | tr -d '"' || true)
        fi
        if [ -z "$_REDIS_PW" ] && [ -f .env ]; then
            _REDIS_PW=$(grep -E "^REDIS_PASSWORD=" .env | head -1 | cut -d'=' -f2- | tr -d '"' || true)
        fi
        if [ -n "$_REDIS_PW" ]; then
            REDIS_REPLY=$(docker exec fks_redis redis-cli -a "$_REDIS_PW" --no-auth-warning ping 2>/dev/null || true)
        else
            REDIS_REPLY=$(docker exec fks_redis redis-cli ping 2>/dev/null || true)
        fi
        if echo "$REDIS_REPLY" | grep -q "PONG"; then
            echo "  ✅ Redis — PONG"
        else
            echo "  ❌ Redis — no response (got: $REDIS_REPLY)"
        fi
        if docker exec fks_postgres pg_isready -U postgres 2>/dev/null | grep -q "accepting"; then
            echo "  ✅ PostgreSQL — accepting connections"
        elif docker exec fks_postgres pg_isready -U fks 2>/dev/null | grep -q "accepting"; then
            echo "  ✅ PostgreSQL — accepting connections (fks user)"
        else
            echo "  ❌ PostgreSQL — not ready"
        fi
        if curl -sf "http://localhost:9000/exec?query=SELECT%201" 2>/dev/null | grep -q "dataset"; then
            echo "  ✅ QuestDB — query OK"
        else
            echo "  ⚠️  QuestDB — query failed or not reachable"
        fi
        echo ""

        echo "## Disk Space"
        df -h / | tail -1 | awk '{printf "  Used: %s / %s (%s)\n  Available: %s\n", $3, $2, $5, $4}'
        echo ""

        echo "## Memory"
        free -h | grep Mem | awk '{printf "  Used: %s / %s\n  Available: %s\n", $3, $2, $7}'
        echo ""

        echo "## Docker Volumes"
        docker system df -v 2>/dev/null | grep -E "fks|VOLUME" | head -20 || echo "  Could not list volumes"
        echo ""

        echo "## Recent Errors (last 50 lines per service)"
        for svc in janus nginx; do
            if docker ps -q -f name=fks_${svc} 2>/dev/null | grep -q .; then
                ERRORS=$(docker logs fks_${svc} --tail 200 2>&1 | grep -i "error\|panic\|fatal" | tail -10)
                if [ -n "$ERRORS" ]; then
                    echo "  ── fks_${svc} ──"
                    echo "$ERRORS" | sed 's/^/    /'
                else
                    echo "  ✅ fks_${svc} — no recent errors"
                fi
            fi
        done

    } 2>&1 | tee "$TEST_DIR/logs/health-check.log"

    echo ""
    echo "✅ Health check complete. Results saved to: $TEST_DIR/logs/health-check.log"

# ===========================================================================
# TEST TYPE: integration-test
# ===========================================================================
elif [ "$TEST_TYPE" = "integration-test" ]; then
    echo "🧪 Running integration test suite..."
    echo ""
    mkdir -p "$TEST_DIR/logs"

    # Check if services are running, start them if not
    RUNNING=$(docker ps --filter "name=fks" --format '{{.Names}}' 2>/dev/null | wc -l)
    if [ "$RUNNING" -lt 3 ]; then
        echo "⚠️ Less than 3 FKS containers running ($RUNNING found). Starting services..."
        chmod +x ./run.sh 2>/dev/null || true
        if [ -x "./run.sh" ]; then
            ./run.sh prod start 2>&1 || $COMPOSE_CMD up -d --no-build 2>&1
        else
            $COMPOSE_CMD up -d --no-build 2>&1
        fi
        echo "⏳ Waiting for services to start (60s)..."
        sleep 60
    fi

    # Run integration test scripts
    if [ -f scripts/testing/run-integration-tests.sh ]; then
        echo "▶ Running run-integration-tests.sh..."
        chmod +x scripts/testing/run-integration-tests.sh
        bash scripts/testing/run-integration-tests.sh 2>&1 | tee "$TEST_DIR/logs/integration-test.log"
        echo ""
    fi

    if [ -f scripts/testing/integration-test.sh ]; then
        echo "▶ Running integration-test.sh..."
        chmod +x scripts/testing/integration-test.sh
        bash scripts/testing/integration-test.sh --quick 2>&1 | tee -a "$TEST_DIR/logs/integration-test.log" || true
    fi

    echo ""
    echo "✅ Integration tests complete. Results: $TEST_DIR/logs/integration-test.log"

# ===========================================================================
# TEST TYPE: signal-pipeline
# ===========================================================================
elif [ "$TEST_TYPE" = "signal-pipeline" ]; then
    echo "📡 Running signal pipeline test..."
    echo ""
    mkdir -p "$TEST_DIR/logs"

    # Ensure services are running
    RUNNING=$(docker ps --filter "name=fks" --format '{{.Names}}' 2>/dev/null | wc -l)
    if [ "$RUNNING" -lt 3 ]; then
        echo "⚠️ Services not running. Starting..."
        chmod +x ./run.sh 2>/dev/null || true
        if [ -x "./run.sh" ]; then
            ./run.sh prod start 2>&1 || $COMPOSE_CMD up -d --no-build 2>&1
        else
            $COMPOSE_CMD up -d --no-build 2>&1
        fi
        echo "⏳ Waiting for services to start (60s)..."
        sleep 60
    fi

    if [ -f scripts/testing/live-signal-test.sh ]; then
        echo "▶ Running live-signal-test.sh --duration 30..."
        chmod +x scripts/testing/live-signal-test.sh
        bash scripts/testing/live-signal-test.sh --duration 30 2>&1 | tee "$TEST_DIR/logs/signal-pipeline.log" || true
    else
        echo "⚠️ scripts/testing/live-signal-test.sh not found"
        echo "Running manual signal pipeline check..."

        {
            echo "# Signal Pipeline Manual Check"
            echo "# Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
            echo ""

            echo "## Service Status"
            docker ps --filter "name=fks" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null
            echo ""

            echo "## Signal Count (QuestDB)"
            curl -sf -G --data-urlencode "query=SELECT COUNT(*) as total_signals FROM signals" http://localhost:9000/exec 2>/dev/null | jq '.' 2>/dev/null || echo "Could not query signals"
            echo ""

            echo "## Recent Signals"
            curl -sf -G --data-urlencode "query=SELECT * FROM signals ORDER BY timestamp DESC LIMIT 10" http://localhost:9000/exec 2>/dev/null | jq '.' 2>/dev/null || echo "Could not query recent signals"
            echo ""

            echo "## Order Count"
            curl -sf -G --data-urlencode "query=SELECT COUNT(*) as total_orders FROM orders" http://localhost:9000/exec 2>/dev/null | jq '.' 2>/dev/null || echo "Could not query orders"
            echo ""

            echo "## Janus Logs (last 100 lines, signal-related)"
            docker logs fks_janus --tail 100 2>&1 | grep -i "signal\|forward\|backward\|persist" | tail -30 || echo "No signal-related log lines found"

        } 2>&1 | tee "$TEST_DIR/logs/signal-pipeline.log"
    fi

    echo ""
    echo "✅ Signal pipeline test complete. Results: $TEST_DIR/logs/signal-pipeline.log"

# ===========================================================================
# TEST TYPE: env-validation
# ===========================================================================
elif [ "$TEST_TYPE" = "env-validation" ]; then
    echo "🔍 Running environment validation..."
    echo ""
    mkdir -p "$TEST_DIR/logs"

    if [ -f scripts/testing/verify-env.sh ]; then
        echo "▶ Running verify-env.sh..."
        chmod +x scripts/testing/verify-env.sh
        bash scripts/testing/verify-env.sh 2>&1 | tee "$TEST_DIR/logs/env-validation.log" || true
    else
        echo "⚠️ verify-env.sh not found, running inline checks..."
        {
            echo "# Environment Validation"
            echo "# Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
            echo ""

            if [ -f .env ]; then
                echo "✅ .env file exists"
                TRADING_MODE=$(grep "^TRADING_MODE=" .env | cut -d'=' -f2 | tr -d '"' || echo "NOT SET")
                REAL_ORDERS=$(grep "^REAL_ORDERS_ENABLED=" .env | cut -d'=' -f2 | tr -d '"' || echo "NOT SET")
                echo "  TRADING_MODE=$TRADING_MODE"
                echo "  REAL_ORDERS_ENABLED=$REAL_ORDERS"
            else
                echo "❌ .env file missing"
            fi
            echo ""

            echo "Docker: $(docker --version 2>/dev/null || echo 'not installed')"
            echo "Compose: $(docker compose version 2>/dev/null || echo 'not installed')"
            echo "Disk: $(df -h / | tail -1 | awk '{print $4}') available"
            echo "Memory: $(free -h | grep Mem | awk '{print $7}') available"
            echo "CPU: $(nproc) cores"
        } 2>&1 | tee "$TEST_DIR/logs/env-validation.log"
    fi

    echo ""
    echo "✅ Environment validation complete. Results: $TEST_DIR/logs/env-validation.log"

# ===========================================================================
# TEST TYPE: rss-monitoring (monitoring-only — attach to running services)
# ===========================================================================
elif [ "$TEST_TYPE" = "rss-monitoring" ]; then
    echo "📈 Running RSS memory monitoring on existing services..."
    echo ""
    mkdir -p "$TEST_DIR/logs"

    # Verify services are running
    RUNNING=$(docker ps --filter "name=fks" --format '{{.Names}}' 2>/dev/null | wc -l)
    if [ "$RUNNING" -lt 1 ]; then
        echo "❌ No FKS containers running. Start services first or use a soak test type."
        echo "   Hint: Use 'audit-72h-soak' to deploy + monitor in one step."
        exit 1
    fi

    echo "📦 Found $RUNNING running container(s):"
    docker ps --filter "name=fks" --format "  {{.Names}} ({{.Status}})" 2>/dev/null
    echo ""

    # Force-enable RSS monitoring for this test type
    RSS_ENABLED="true"

    # ── Ensure Janus processing services are running (not in standby) ──
    # Janus modules (forward, backward, CNS, data) register with the
    # supervisor but idle in standby unless JANUS_AUTO_START=true or an
    # explicit POST /api/services/start is issued. Without this, there
    # are no signals, no data flow, and no meaningful logs or metrics.
    echo "🔌 Checking Janus service state..."
    JANUS_PORT=7000
    SVC_STATUS=$(curl -sf "http://localhost:${JANUS_PORT}/api/services/status" 2>/dev/null || echo "")

    if [ -n "$SVC_STATUS" ]; then
        SVC_STATE=$(echo "$SVC_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('service_state','unknown'))" 2>/dev/null || echo "unknown")
        echo "  Current service state: $SVC_STATE"

        if [ "$SVC_STATE" = "standby" ] || [ "$SVC_STATE" = "stopped" ]; then
            echo "  ⏩ Starting Janus processing services (standby → running)..."
            START_RESP=$(janus_post "http://localhost:${JANUS_PORT}/api/services/start" 2>/dev/null || echo "")
            if echo "$START_RESP" | grep -q '"success".*true'; then
                echo "  ✅ Janus services started successfully"
            else
                echo "  ⚠️ Could not start Janus services via API (response: $START_RESP)"
                echo "     Logs and metrics may be limited."
            fi

            # Give modules time to initialize after start
            echo "  ⏳ Waiting for modules to initialize (15s)..."
            sleep 15

            # Verify services transitioned
            SVC_STATUS_AFTER=$(curl -sf "http://localhost:${JANUS_PORT}/api/services/status" 2>/dev/null || echo "")
            SVC_STATE_AFTER=$(echo "$SVC_STATUS_AFTER" | python3 -c "import sys,json; print(json.load(sys.stdin).get('service_state','unknown'))" 2>/dev/null || echo "unknown")
            echo "  Service state after start: $SVC_STATE_AFTER"
        else
            echo "  ✅ Janus services already running"
        fi
    else
        echo "  ⚠️ Could not reach Janus API at localhost:${JANUS_PORT}"
        echo "     Attempting to start services anyway..."
        janus_post "http://localhost:${JANUS_PORT}/api/services/start" 2>/dev/null || true
        sleep 10
    fi
    echo ""

    # ── Run initial optimization if configured ──
    if [ "${FKS_RUN_INITIAL_OPT}" = "true" ]; then
        echo "🔧 Running initial optimization..."
        docker exec fks_janus /app/janus-optimizer run-once --quick --assets "${FKS_ASSETS}" 2>&1 || echo "⚠️ Initial optimization had issues (non-fatal)"
        echo ""
    fi

    # ── Start log collectors ──
    # NOTE: Uses run_detached / setsid so collectors survive SSH session end.
    echo "📝 Starting log collectors..."

    # Combined log
    COLLECTOR_PID=$(run_detached "$TEST_DIR/logs/log-collector.pid" \
        bash -c "exec $COMPOSE_CMD logs -f --timestamps >> '$TEST_DIR/logs/all-services.log' 2>'$TEST_DIR/logs/log-collector.err'")

    sleep 2
    if ps -p $COLLECTOR_PID > /dev/null 2>&1; then
        echo "  ✅ Combined log collector running (PID: $COLLECTOR_PID)"
    else
        echo "  ⚠️ Combined log collector failed — check $TEST_DIR/logs/log-collector.err"
    fi

    # Individual service logs
    for svc in janus nginx web redis postgres questdb authelia grafana prometheus alertmanager; do
        if docker ps --filter "name=fks_${svc}" --format '{{.Names}}' 2>/dev/null | grep -q "fks_${svc}"; then
            run_detached "$TEST_DIR/logs/${svc}-collector.pid" \
                bash -c "exec docker logs -f 'fks_${svc}' >> '$TEST_DIR/logs/${svc}.log' 2>&1" > /dev/null
            echo "  ✅ ${svc}.log"
        fi
    done
    echo ""

    # Log current container state before monitoring
    {
        echo "# RSS Monitoring Baseline"
        echo "# Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "# Duration: ${TEST_DURATION} hours"
        echo "# Janus services: started via API"
        echo ""
        echo "## Container Baseline"
        docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}" 2>/dev/null | grep -iE "fks|janus|NAME"
        echo ""
        echo "## System Baseline"
        echo "Memory: $(free -h | grep Mem | awk '{print $3 " used / " $2 " total / " $7 " available"}')"
        echo "Disk: $(df -h / | tail -1 | awk '{print $3 " used / " $2 " total / " $4 " available"}')"
    } 2>&1 | tee "$TEST_DIR/logs/monitoring-baseline.log"

    echo ""
    echo "✅ Baseline captured. Janus services running. RSS monitoring will be started below."

# ===========================================================================
# TEST TYPE: audit-72h-soak (paper trading + RSS monitoring — audit item #1)
# ===========================================================================
elif [ "$TEST_TYPE" = "audit-72h-soak" ]; then
    echo "🔒 Running 72-hour audit soak test (paper trading + RSS monitoring)..."
    echo ""

    # Force 72-hour duration and enable RSS
    TEST_DURATION=72
    RSS_ENABLED="true"

    # Source env files
    set -a
    [ -f .env ] && source .env
    [ -f "$TEST_DIR/.env.test" ] && source "$TEST_DIR/.env.test"
    set +a

    # Stop or clean existing services
    if [ "${FKS_CLEAN_VOLUMES}" = "true" ]; then
        echo "🧹 Cleaning volumes (fresh start for audit)..."
        $COMPOSE_CMD down -v --remove-orphans 2>/dev/null || true
    else
        echo "🛑 Stopping existing containers..."
        $COMPOSE_CMD down --remove-orphans 2>/dev/null || true
    fi

    # Pull and start
    echo "📥 Pulling latest images..."
    $COMPOSE_CMD pull --ignore-pull-failures 2>&1 || true

    echo "🚀 Starting services for 72-hour audit soak..."
    $COMPOSE_CMD up -d --no-build 2>&1

    echo "⏳ Waiting for services to initialize (45s)..."
    sleep 45

    # ── Safety check: verify paper trading mode ──
    echo ""
    echo "🔒 Verifying paper trading safety..."
    SAFETY_OK=true

    if docker ps -q -f name=fks_execution 2>/dev/null | grep -q .; then
        # Standalone execution container exists — check it directly
        REAL_ORDERS=$(docker exec fks_execution env 2>/dev/null | grep "REAL_ORDERS_ENABLED" | cut -d'=' -f2 || echo "unknown")
        TRADE_MODE=$(docker exec fks_execution env 2>/dev/null | grep "TRADING_MODE" | cut -d'=' -f2 || echo "unknown")
        if [ "$REAL_ORDERS" = "false" ]; then
            echo "  ✅ REAL_ORDERS_ENABLED=false (execution standalone)"
        else
            echo "  🚨 REAL_ORDERS_ENABLED=$REAL_ORDERS (execution standalone) — ABORTING!"
            SAFETY_OK=false
        fi
        if [ "$TRADE_MODE" = "simulation" ] || [ "$TRADE_MODE" = "paper" ]; then
            echo "  ✅ TRADING_MODE=$TRADE_MODE (execution standalone)"
        else
            echo "  🚨 TRADING_MODE=$TRADE_MODE (execution standalone) — ABORTING!"
            SAFETY_OK=false
        fi
    fi

    # Execution is embedded inside Janus — check Janus for trading mode and execution config
    if docker ps -q -f name=fks_janus 2>/dev/null | grep -q .; then
        JANUS_EXEC_ENABLED=$(docker exec fks_janus printenv ENABLE_EXECUTION 2>/dev/null || echo "")
        JANUS_EXEC_MODE=$(docker exec fks_janus printenv EXECUTION_MODE 2>/dev/null || echo "")
        JANUS_MODE=$(docker exec fks_janus printenv TRADING_MODE 2>/dev/null || echo "")

        if [ "$JANUS_EXEC_ENABLED" = "true" ]; then
            echo "  ✅ Execution enabled inside Janus (ENABLE_EXECUTION=true)"
        elif [ -n "$JANUS_EXEC_ENABLED" ]; then
            echo "  ℹ️  Execution disabled in Janus (ENABLE_EXECUTION=$JANUS_EXEC_ENABLED)"
        fi

        if [ -n "$JANUS_EXEC_MODE" ]; then
            if [ "$JANUS_EXEC_MODE" = "simulated" ] || [ "$JANUS_EXEC_MODE" = "paper" ] || [ "$JANUS_EXEC_MODE" = "paper_trading" ] || [ "$JANUS_EXEC_MODE" = "simulation" ]; then
                echo "  ✅ EXECUTION_MODE=$JANUS_EXEC_MODE (janus)"
            elif [ "$JANUS_EXEC_MODE" = "live" ]; then
                echo "  🚨 EXECUTION_MODE=live (janus) — ABORTING! Paper trading must not use live execution."
                SAFETY_OK=false
            else
                echo "  🚨 EXECUTION_MODE=$JANUS_EXEC_MODE (janus) — unrecognised mode, ABORTING!"
                SAFETY_OK=false
            fi
        elif [ "$JANUS_EXEC_ENABLED" = "true" ]; then
            echo "  ⚠️  EXECUTION_MODE not set but execution is enabled — will default to 'simulated'"
        fi

        if [ -n "$JANUS_MODE" ]; then
            if [ "$JANUS_MODE" = "simulation" ] || [ "$JANUS_MODE" = "paper" ] || [ "$JANUS_MODE" = "paper_trading" ]; then
                echo "  ✅ TRADING_MODE=$JANUS_MODE (janus)"
            elif [ "$JANUS_MODE" = "live" ]; then
                echo "  🚨 TRADING_MODE=live (janus) — ABORTING!"
                SAFETY_OK=false
            else
                echo "  ⚠️  TRADING_MODE=$JANUS_MODE (janus) — unexpected value"
            fi
        fi
    fi

    if [ "$SAFETY_OK" != "true" ]; then
        echo ""
        echo "🚨🚨🚨 SAFETY CHECK FAILED — SHUTTING DOWN 🚨🚨🚨"
        $COMPOSE_CMD down --remove-orphans 2>/dev/null || true
        exit 1
    fi
    echo "  ✅ Paper trading mode confirmed"
    echo ""

    # ── Start Janus processing services ──
    echo "🔌 Starting Janus processing services..."
    JANUS_PORT=7000
    SVC_STATUS=$(curl -sf "http://localhost:${JANUS_PORT}/api/services/status" 2>/dev/null || echo "")
    SVC_STATE=$(echo "$SVC_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('service_state','unknown'))" 2>/dev/null || echo "unknown")

    if [ "$SVC_STATE" = "standby" ] || [ "$SVC_STATE" = "stopped" ]; then
        START_RESP=$(janus_post "http://localhost:${JANUS_PORT}/api/services/start" 2>/dev/null || echo "")
        if echo "$START_RESP" | grep -q '"success".*true'; then
            echo "  ✅ Janus services started (was: $SVC_STATE)"
        else
            echo "  ⚠️ Could not start Janus services via API (response: $START_RESP)"
        fi
        sleep 5
    elif [ "$SVC_STATE" = "running" ]; then
        echo "  ✅ Janus services already running"
    else
        echo "  ⚠️ Could not determine Janus service state ($SVC_STATE), attempting start..."
        janus_post "http://localhost:${JANUS_PORT}/api/services/start" 2>/dev/null || true
        sleep 5
    fi
    echo ""

    # ── Run initial optimization ──
    if [ "${FKS_RUN_INITIAL_OPT}" = "true" ]; then
        echo "🔧 Running initial optimization..."
        docker exec fks_janus /app/janus-optimizer run-once --quick --assets "${FKS_ASSETS}" 2>&1 || echo "⚠️ Initial optimization had issues (non-fatal)"
        echo ""
    fi

    # ── Start log collectors ──
    # NOTE: Uses run_detached / setsid so collectors survive SSH session end.
    echo "📝 Starting log collectors..."
    mkdir -p "$TEST_DIR/logs"

    COLLECTOR_PID=$(run_detached "$TEST_DIR/logs/log-collector.pid" \
        bash -c "exec $COMPOSE_CMD logs -f --timestamps >> '$TEST_DIR/logs/all-services.log' 2>'$TEST_DIR/logs/log-collector.err'")

    sleep 2
    if ps -p $COLLECTOR_PID > /dev/null 2>&1; then
        echo "  ✅ Combined log collector running (PID: $COLLECTOR_PID)"
    else
        echo "  ⚠️ Combined log collector failed — check $TEST_DIR/logs/log-collector.err"
    fi

    for svc in janus nginx web redis postgres questdb authelia grafana prometheus alertmanager; do
        if docker ps --filter "name=fks_${svc}" --format '{{.Names}}' 2>/dev/null | grep -q "fks_${svc}"; then
            run_detached "$TEST_DIR/logs/${svc}-collector.pid" \
                bash -c "exec docker logs -f 'fks_${svc}' >> '$TEST_DIR/logs/${svc}.log' 2>&1" > /dev/null
            echo "  ✅ ${svc}.log"
        fi
    done

    echo ""
    echo "📋 Audit soak test criteria (from AUDIT_REMEDIATION_STATUS.md):"
    echo "  - No service exceeds ${FKS_RSS_THRESHOLD:-100} MB RSS growth over 72 hours"
    echo "  - 6-hour derivative stays below 0.5 KB/s for all services"
    echo "  - No OOM kills or container restarts during the run"
    echo "  - RSS monitor script exits with code 0"
    echo ""
    echo "✅ 72-hour audit soak deployed. RSS monitoring will be started below."
fi

# ===========================================================================
# COMMON: Save test metadata
# ===========================================================================
cat > "$TEST_DIR/test-metadata.json" << METAEOF
{
  "test_id": "${TEST_ID}",
  "test_type": "${TEST_TYPE}",
  "test_label": "${FKS_TEST_LABEL}",
  "start_time": "${FKS_START_TIME}",
  "expected_end_time": "${FKS_END_TIME}",
  "duration_hours": ${TEST_DURATION},
  "mode": "simulation",
  "real_orders_enabled": false,
  "assets": "${FKS_ASSETS}",
  "optimize_interval": "${FKS_OPTIMIZE_INTERVAL}",
  "optimize_trials": ${FKS_OPTIMIZE_TRIALS},
  "health_monitor_interval_min": ${HEALTH_INTERVAL},
  "clean_volumes": ${FKS_CLEAN_VOLUMES},
  "rss_monitoring_enabled": ${RSS_ENABLED},
  "rss_interval_seconds": ${FKS_RSS_INTERVAL:-10},
  "rss_threshold_mb": ${FKS_RSS_THRESHOLD:-100},
  "rss_containers": "${FKS_RSS_CONTAINERS:-janus|fks}",
  "github_run_id": "${FKS_RUN_ID}",
  "github_sha": "${FKS_SHA}",
  "github_ref": "${FKS_REF}",
  "triggered_by": "${FKS_ACTOR}"
}
METAEOF
echo "📄 Test metadata saved: $TEST_DIR/test-metadata.json"

# ===========================================================================
# COMMON: Generate helper scripts on the server
# ===========================================================================

# ── check-status.sh ──
cat > "$TEST_DIR/check-status.sh" << 'STATUSEOF'
#!/bin/bash
# FKS Test Status Checker — auto-generated
echo "════════════════════════════════════════════════════════════"
echo "📊 FKS PAPER TRADING TEST STATUS"
echo "════════════════════════════════════════════════════════════"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/test-metadata.json" ]; then
    echo "📋 Test Info:"
    cat "$SCRIPT_DIR/test-metadata.json" | python3 -m json.tool 2>/dev/null || cat "$SCRIPT_DIR/test-metadata.json"
    echo ""
fi

echo "📦 Container Status:"
docker ps -a --filter "name=fks" --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}"
echo ""

echo "💾 Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | grep fks || echo "  Could not get stats"
echo ""

echo "📈 Recent Janus Logs (last 30 lines):"
docker logs fks_janus --tail 30 2>&1 || echo "  Janus not running"
echo ""

echo "🔧 Optimizer Status:"
docker exec fks_janus /app/janus-optimizer status 2>&1 || echo "  Could not get optimizer status"
echo ""

# RSS monitoring status
if [ -d "$SCRIPT_DIR/monitoring" ]; then
    echo "📈 RSS Monitoring:"
    if [ -f "$SCRIPT_DIR/monitoring/rss-monitor.pid" ]; then
        RPID=$(cat "$SCRIPT_DIR/monitoring/rss-monitor.pid")
        if kill -0 "$RPID" 2>/dev/null; then
            echo "  🟢 Running (PID: $RPID)"
        else
            echo "  🔴 Stopped (PID $RPID exited)"
        fi
    else
        echo "  ⚪ Not configured"
    fi
    # Show latest sample count
    CSV=$(ls -t "$SCRIPT_DIR/monitoring/rss_samples_"*.csv 2>/dev/null | head -1)
    if [ -n "$CSV" ]; then
        CNT=$(($(wc -l < "$CSV") - 1))
        echo "  Samples: $CNT"
    fi
    ALERTS=$(ls -t "$SCRIPT_DIR/monitoring/rss_alerts_"*.log 2>/dev/null | head -1)
    if [ -n "$ALERTS" ] && [ -s "$ALERTS" ]; then
        echo "  ⚠️  Alerts: $(wc -l < "$ALERTS")"
    else
        echo "  ✅ No leak alerts"
    fi
fi
echo ""

echo "📊 Signal Count:"
curl -sf -G --data-urlencode "query=SELECT COUNT(*) as total FROM signals" http://localhost:9000/exec 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Total signals: {d[\"dataset\"][0][0]}')" 2>/dev/null || echo "  Could not query QuestDB"

echo ""
echo "📊 Order Count:"
curl -sf -G --data-urlencode "query=SELECT COUNT(*) as total FROM orders" http://localhost:9000/exec 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Total orders: {d[\"dataset\"][0][0]}')" 2>/dev/null || echo "  Could not query QuestDB"

echo ""
HEALTH_LOG="$SCRIPT_DIR/logs/health-monitor.log"
if [ -f "$HEALTH_LOG" ]; then
    TOTAL=$(grep -c "^HEALTH_CHECK" "$HEALTH_LOG" 2>/dev/null || echo "0")
    PASSED=$(grep -c "status=PASS" "$HEALTH_LOG" 2>/dev/null || echo "0")
    FAILED=$(grep -c "status=FAIL" "$HEALTH_LOG" 2>/dev/null || echo "0")
    echo "🏥 Health Monitor: $PASSED/$TOTAL passed, $FAILED failed"
    echo "   Last 5 checks:"
    tail -5 "$HEALTH_LOG" | sed 's/^/   /'
else
    echo "🏥 Health monitor not active"
fi

echo ""
echo "💾 Disk Space:"
df -h / | tail -1 | awk '{printf "  Used: %s / %s (%s) — %s available\n", $3, $2, $5, $4}'

echo ""
echo "📁 Log Files:"
if [ -d "$SCRIPT_DIR/logs" ]; then
    ls -lh "$SCRIPT_DIR/logs/" 2>/dev/null | tail -20
fi
STATUSEOF
chmod +x "$TEST_DIR/check-status.sh"

# ── stop-test.sh ──
cat > "$TEST_DIR/stop-test.sh" << 'STOPEOF'
#!/bin/bash
# FKS Test Stopper — auto-generated
#
# Background processes are launched with `setsid` (new session) so they survive
# SSH session termination. To stop them we send SIGTERM to the process group
# leader (kill -- -PID) which also terminates any children it spawned.
echo "🛑 Stopping FKS paper trading test..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Helper: stop a setsid process group gracefully, then force-kill if needed.
# Usage: stop_process_group <pid_file> <label>
stop_process_group() {
    local pid_file="$1"
    local label="$2"
    if [ ! -f "$pid_file" ]; then
        return 0
    fi
    local PID
    PID=$(cat "$pid_file")
    if kill -0 "$PID" 2>/dev/null; then
        # Try killing the whole process group (setsid gives it its own PGID)
        kill -- -"$PID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null || true
        local waited=0
        while kill -0 "$PID" 2>/dev/null && [ $waited -lt 5 ]; do
            sleep 1
            waited=$((waited + 1))
        done
        if kill -0 "$PID" 2>/dev/null; then
            kill -9 -- -"$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null || true
        fi
        echo "  ✅ $label stopped (PID: $PID)"
    else
        echo "  ℹ️  $label already stopped (PID: $PID)"
    fi
    rm -f "$pid_file"
}

# Stop RSS monitor
stop_process_group "$SCRIPT_DIR/monitoring/rss-monitor.pid" "RSS monitor"

# Stop health monitor
stop_process_group "$SCRIPT_DIR/logs/health-monitor.pid" "Health monitor"

# Stop combined log collector
stop_process_group "$SCRIPT_DIR/logs/log-collector.pid" "Combined log collector"

# Stop individual service log collectors
for pid_file in "$SCRIPT_DIR"/logs/*-collector.pid; do
    [ -f "$pid_file" ] || continue
    # Skip the combined collector (already handled above)
    [ "$pid_file" = "$SCRIPT_DIR/logs/log-collector.pid" ] && continue
    svc_name=$(basename "$pid_file" | sed 's/-collector\.pid$//')
    stop_process_group "$pid_file" "${svc_name} log collector"
done

# Collect final report before stopping
if [ -f "$SCRIPT_DIR/collect-report.sh" ]; then
    echo ""
    bash "$SCRIPT_DIR/collect-report.sh"
fi

# Record stop time
echo "stopped_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$SCRIPT_DIR/test-metadata.json"

echo ""
echo "ℹ️  Containers are still running. To also stop containers:"
echo "   cd ~/fks && docker compose -p fks -f infrastructure/compose/docker-compose.yml -f infrastructure/compose/docker-compose.prod.yml down"
echo ""
echo "✅ Test monitoring stopped. Logs preserved in: $SCRIPT_DIR/logs/"
STOPEOF
chmod +x "$TEST_DIR/stop-test.sh"

# ── collect-report.sh ──
cat > "$TEST_DIR/collect-report.sh" << 'REPORTEOF'
#!/bin/bash
# FKS Test Report Collector — auto-generated
echo "📊 Generating test summary report..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT="$SCRIPT_DIR/logs/summary-report.txt"

{
    echo "═══════════════════════════════════════════════════════════"
    echo "  FKS Test Summary Report"
    echo "  Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "═══════════════════════════════════════════════════════════"
    echo ""

    echo "── Test Metadata ──"
    if [ -f "$SCRIPT_DIR/test-metadata.json" ]; then
        cat "$SCRIPT_DIR/test-metadata.json" | python3 -m json.tool 2>/dev/null || cat "$SCRIPT_DIR/test-metadata.json"
    fi
    echo ""

    echo "── Container Status ──"
    docker ps -a --filter "name=fks" --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}" 2>/dev/null
    echo ""

    echo "── Resource Usage ──"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>/dev/null | grep fks || true
    echo ""

    echo "── Health Monitor Summary ──"
    HEALTH_LOG="$SCRIPT_DIR/logs/health-monitor.log"
    if [ -f "$HEALTH_LOG" ]; then
        TOTAL=$(grep -c "^HEALTH_CHECK" "$HEALTH_LOG" 2>/dev/null || echo "0")
        PASSED=$(grep -c "status=PASS" "$HEALTH_LOG" 2>/dev/null || echo "0")
        FAILED=$(grep -c "status=FAIL" "$HEALTH_LOG" 2>/dev/null || echo "0")
        echo "  Total checks: $TOTAL"
        echo "  Passed: $PASSED"
        echo "  Failed: $FAILED"
        if [ "$TOTAL" -gt 0 ]; then
            RATE=$((PASSED * 100 / TOTAL))
            echo "  Pass rate: ${RATE}%"
        fi
    else
        echo "  No health monitor data"
    fi
    echo ""

    echo "── Trading Metrics ──"
    echo "  Signals:"
    curl -sf -G --data-urlencode "query=SELECT COUNT(*) as total FROM signals" http://localhost:9000/exec 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'    Total: {d[\"dataset\"][0][0]}')" 2>/dev/null || echo "    Could not query"
    echo "  Orders:"
    curl -sf -G --data-urlencode "query=SELECT COUNT(*) as total FROM orders" http://localhost:9000/exec 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'    Total: {d[\"dataset\"][0][0]}')" 2>/dev/null || echo "    Could not query"
    echo "  Open Positions:"
    curl -sf -G --data-urlencode "query=SELECT COUNT(*) as total FROM positions WHERE closed_at IS NULL" http://localhost:9000/exec 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'    Total: {d[\"dataset\"][0][0]}')" 2>/dev/null || echo "    Could not query"
    echo ""

    echo "── Disk Usage ──"
    df -h / | tail -1 | awk '{printf "  Used: %s / %s (%s) — %s available\n", $3, $2, $5, $4}'
    echo ""

    echo "── Docker Volume Sizes ──"
    docker system df -v 2>/dev/null | grep -E "fks|VOLUME" | head -20 || echo "  Could not list volumes"
    echo ""

    echo "── Log File Sizes ──"
    if [ -d "$SCRIPT_DIR/logs" ]; then
        du -sh "$SCRIPT_DIR/logs/"* 2>/dev/null | sort -rh | head -15
    fi
    echo ""

    echo "── Error Summary (per service) ──"
    for svc in janus nginx web; do
        if docker ps -q -f name=fks_${svc} 2>/dev/null | grep -q .; then
            ERR_COUNT=$(docker logs fks_${svc} --tail 5000 2>&1 | grep -ci "error" || echo "0")
            PANIC_COUNT=$(docker logs fks_${svc} --tail 5000 2>&1 | grep -ci "panic\|fatal" || echo "0")
            echo "  fks_${svc}: $ERR_COUNT errors, $PANIC_COUNT panics/fatals"
        fi
    done
    echo ""

    echo "── RSS Monitoring Summary ──"
    if [ -d "$SCRIPT_DIR/monitoring" ]; then
        SUMMARY=$(ls -t "$SCRIPT_DIR/monitoring/rss_summary_"*.txt 2>/dev/null | head -1)
        if [ -n "$SUMMARY" ]; then
            head -30 "$SUMMARY" | sed 's/^/  /'
        else
            echo "  No RSS summary available"
        fi
        ALERTS=$(ls -t "$SCRIPT_DIR/monitoring/rss_alerts_"*.log 2>/dev/null | head -1)
        if [ -n "$ALERTS" ] && [ -s "$ALERTS" ]; then
            echo ""
            echo "  ⚠️  Leak alerts:"
            cat "$ALERTS" | sed 's/^/    /'
        fi
        RESULT="$SCRIPT_DIR/monitoring/audit-result.txt"
        if [ -f "$RESULT" ]; then
            echo ""
            echo "  Audit result: $(cat "$RESULT")"
        fi
    else
        echo "  RSS monitoring was not enabled for this test"
    fi
    echo ""

    echo "═══════════════════════════════════════════════════════════"
    echo "  Report complete"
    echo "═══════════════════════════════════════════════════════════"
} 2>&1 | tee "$REPORT"

echo ""
echo "📄 Report saved to: $REPORT"
REPORTEOF
chmod +x "$TEST_DIR/collect-report.sh"
echo "📝 Helper scripts generated: check-status.sh, stop-test.sh, collect-report.sh"

# ===========================================================================
# SOAK TEST ONLY: Start background health monitor
# ===========================================================================
if [ "$TEST_TYPE" = "paper-trading-soak" ] || [ "$TEST_TYPE" = "audit-72h-soak" ]; then
    echo ""
    echo "🏥 Starting background health monitor (every ${HEALTH_INTERVAL} min)..."

    # Generate the health monitor script
    cat > "$TEST_DIR/health-monitor-daemon.sh" << 'HEALTHEOF'
#!/bin/bash
# FKS Background Health Monitor — auto-generated
# Runs periodic health checks and logs results.
# Stops automatically when the expected test duration is exceeded.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEALTH_LOG="$SCRIPT_DIR/logs/health-monitor.log"
INTERVAL_SEC="${1:-300}"
MAX_DURATION_SEC="${2:-86400}"
START_EPOCH=$(date +%s)

mkdir -p "$SCRIPT_DIR/logs"

# ── Load Redis password from .env.test or .env ──
REDIS_PASSWORD=""
if [ -f "$SCRIPT_DIR/.env.test" ]; then
    REDIS_PASSWORD=$(grep -E "^REDIS_PASSWORD=" "$SCRIPT_DIR/.env.test" | head -1 | cut -d'=' -f2- | tr -d '"' || true)
fi
if [ -z "$REDIS_PASSWORD" ] && [ -f "$HOME/fks/.env" ]; then
    REDIS_PASSWORD=$(grep -E "^REDIS_PASSWORD=" "$HOME/fks/.env" | head -1 | cut -d'=' -f2- | tr -d '"' || true)
fi

# ── Load JANUS_API_TOKEN so the auto-restart POST below can authenticate ──
# The janus-auth change gates POST /api/services/start behind a bearer. Without
# this, a mid-run drop to standby could not be recovered once the token is set
# (401 → janus stays idle for the rest of the soak). Empty → no header sent.
JANUS_API_TOKEN="${JANUS_API_TOKEN:-}"
for _envf in "$SCRIPT_DIR/.env.test" "$HOME/fks/.env"; do
    [ -n "$JANUS_API_TOKEN" ] && break
    [ -f "$_envf" ] || continue
    JANUS_API_TOKEN=$(grep -E "^JANUS_API_TOKEN=" "$_envf" | head -1 | cut -d'=' -f2- | tr -d '"' || true)
done

echo "# Health Monitor Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$HEALTH_LOG"
echo "# Interval: ${INTERVAL_SEC}s | Max Duration: ${MAX_DURATION_SEC}s" >> "$HEALTH_LOG"

while true; do
    NOW_EPOCH=$(date +%s)
    ELAPSED=$((NOW_EPOCH - START_EPOCH))

    if [ "$ELAPSED" -ge "$MAX_DURATION_SEC" ]; then
        echo "HEALTH_MONITOR_END ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) reason=duration_reached elapsed=${ELAPSED}s" >> "$HEALTH_LOG"
        break
    fi

    # Check containers
    RUNNING=$(docker ps --filter "name=fks" --format '{{.Names}}' 2>/dev/null | wc -l)
    TOTAL=$(docker ps -a --filter "name=fks" --format '{{.Names}}' 2>/dev/null | wc -l)

    # Check key services
    # NOTE: Execution is embedded inside Janus (ENABLE_EXECUTION=true).
    # If Janus is healthy, execution is available — no separate port to check.
    JANUS="fail"
    EXEC="fail"
    REDIS="fail"
    PG="fail"
    QUEST="fail"

    curl -sf http://localhost:8080/health >/dev/null 2>&1 && JANUS="ok"
    [ "$JANUS" = "fail" ] && curl -sf http://localhost:7000/health >/dev/null 2>&1 && JANUS="ok"
    [ "$JANUS" = "fail" ] && curl -sf http://localhost:8080/api/v1/health >/dev/null 2>&1 && JANUS="ok"
    # Execution is embedded in Janus — if Janus is healthy, execution is available
    [ "$JANUS" = "ok" ] && EXEC="ok(embedded)"
    # Also check standalone port as fallback
    [ "$EXEC" != "ok(embedded)" ] && curl -sf http://localhost:8081/health >/dev/null 2>&1 && EXEC="ok(standalone)"
    if [ -n "$REDIS_PASSWORD" ]; then
        docker exec fks_redis redis-cli -a "$REDIS_PASSWORD" --no-auth-warning ping 2>/dev/null | grep -q "PONG" && REDIS="ok"
    else
        docker exec fks_redis redis-cli ping 2>/dev/null | grep -q "PONG" && REDIS="ok"
    fi
    (docker exec fks_postgres pg_isready -U postgres 2>/dev/null || docker exec fks_postgres pg_isready -U fks 2>/dev/null) | grep -q "accepting" && PG="ok"
    curl -sf http://localhost:9000 >/dev/null 2>&1 && QUEST="ok"

    # Memory and disk
    MEM_PCT=$(free 2>/dev/null | grep Mem | awk '{printf "%.0f", $3/$2 * 100}' || echo "?")
    DISK_PCT=$(df / 2>/dev/null | awk 'NR==2 {print $5}' | tr -d '%' || echo "?")

    # Determine overall status
    STATUS="PASS"
    [ "$JANUS" = "fail" ] && STATUS="FAIL"
    [ "$REDIS" = "fail" ] && STATUS="FAIL"
    [ "$PG" = "fail" ] && STATUS="FAIL"

    # Log
    REMAINING=$((MAX_DURATION_SEC - ELAPSED))
    REMAIN_H=$((REMAINING / 3600))
    REMAIN_M=$(((REMAINING % 3600) / 60))
    # ── Auto-restart Janus processing if it dropped to standby ──
    JANUS_STATE=""
    if [ "$JANUS" = "ok" ]; then
        JANUS_STATE=$(curl -sf "http://localhost:7000/api/services/status" 2>/dev/null \
            | python3 -c "import sys,json; print(json.load(sys.stdin).get('service_state','unknown'))" 2>/dev/null || echo "unknown")
        if [ "$JANUS_STATE" = "standby" ] || [ "$JANUS_STATE" = "stopped" ]; then
            if [ -n "$JANUS_API_TOKEN" ]; then
                RESTART_RESP=$(curl -sf -X POST -H "Authorization: Bearer ${JANUS_API_TOKEN}" "http://localhost:7000/api/services/start" 2>/dev/null || echo "")
            else
                RESTART_RESP=$(curl -sf -X POST "http://localhost:7000/api/services/start" 2>/dev/null || echo "")
            fi
            if echo "$RESTART_RESP" | grep -q '"success".*true'; then
                JANUS_STATE="restarted_from_${JANUS_STATE}"
                echo "HEALTH_AUTO_RESTART ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) action=janus_services_start prev_state=${JANUS_STATE} result=success" >> "$HEALTH_LOG"
            else
                echo "HEALTH_AUTO_RESTART ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) action=janus_services_start prev_state=${JANUS_STATE} result=failed response=${RESTART_RESP}" >> "$HEALTH_LOG"
            fi
        fi
    fi

    echo "HEALTH_CHECK ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) status=$STATUS containers=${RUNNING}/${TOTAL} janus=$JANUS exec=$EXEC redis=$REDIS pg=$PG questdb=$QUEST janus_state=$JANUS_STATE mem=${MEM_PCT}% disk=${DISK_PCT}% elapsed=${ELAPSED}s remaining=${REMAIN_H}h${REMAIN_M}m" >> "$HEALTH_LOG"

    sleep "$INTERVAL_SEC"
done
HEALTHEOF
    chmod +x "$TEST_DIR/health-monitor-daemon.sh"

    # Start the health monitor as a detached background process (survives SSH close)
    INTERVAL_SEC=$((HEALTH_INTERVAL * 60))
    DURATION_SEC=$((TEST_DURATION * 3600 + 3600))  # Add 1 hour buffer
    HEALTH_PID=$(run_detached "$TEST_DIR/logs/health-monitor.pid" \
        bash -c "exec bash '$TEST_DIR/health-monitor-daemon.sh' '$INTERVAL_SEC' '$DURATION_SEC' </dev/null >/dev/null 2>&1")

    sleep 1
    if ps -p $HEALTH_PID > /dev/null 2>&1; then
        echo "  ✅ Health monitor running (PID: $HEALTH_PID, interval: ${HEALTH_INTERVAL}min)"
    else
        echo "  ⚠️ Health monitor failed to start"
    fi
fi

# ===========================================================================
# COMMON: Final status
# ===========================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ ${FKS_TEST_LABEL} — DEPLOYED"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📦 Container Status:"
docker ps -a --filter "name=fks" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | head -20
echo ""
echo "📁 Test artifacts: $TEST_DIR/"
echo ""
echo "💡 SSH into server and run:"
echo "   cd ~/fks && test-results/$TEST_ID/check-status.sh   # Check status"
echo "   cd ~/fks && test-results/$TEST_ID/collect-report.sh  # Generate report"
echo "   cd ~/fks && test-results/$TEST_ID/stop-test.sh       # Stop test"
echo ""
echo "💡 Tail health monitor:"
echo "   tail -f ~/fks/test-results/$TEST_ID/logs/health-monitor.log"
echo ""
echo "💡 Tail service logs:"
echo "   tail -f ~/fks/test-results/$TEST_ID/logs/all-services.log"
echo ""

RUNNING=$(docker ps --filter "name=fks" --format '{{.Names}}' 2>/dev/null | wc -l)
echo "✅ Running containers: $RUNNING"

# ===========================================================================
# COMPOSABLE: Start RSS monitoring if enabled (runs for ANY test type)
# ===========================================================================
start_rss_monitoring

if [ "$RSS_ENABLED" = "true" ]; then
    echo ""
    echo "💡 RSS monitoring commands:"
    echo "   Status:  ~/fks/test-results/$TEST_ID/monitoring/check-rss.sh"
    echo "   Samples: tail -f ~/fks/test-results/$TEST_ID/monitoring/rss_samples_*.csv"
    echo "   Report:  bash ~/fks/scripts/testing/paper-trading/monitoring.sh report"
fi
