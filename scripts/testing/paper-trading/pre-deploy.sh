#!/bin/bash
# =============================================================================
# FKS Paper Trading Test — Pre-Deploy
# =============================================================================
# Sets up test directories, generates .env.test for soak tests, and cleans
# old test results. Called by the workflow via ssh-deploy pre-deploy-command.
#
# Required environment variables (set by the workflow):
#   FKS_TEST_LABEL          - Human-readable test label
#   FKS_TEST_TYPE           - Test type (paper-trading-soak, health-check, etc.)
#   FKS_TEST_ID             - Unique test identifier
#   FKS_DURATION_HOURS      - Test duration in hours
#   FKS_OPTIMIZE_INTERVAL   - Optimization interval (e.g., 6h)
#   FKS_ASSETS              - Comma-separated asset list
#   FKS_OPTIMIZE_TRIALS     - Number of optimization trials
#   FKS_START_TIME          - Test start time (ISO 8601)
#   FKS_DATA_SOURCE         - Data source mode: "live" for real market data, "standby" for synthetic (default: standby)
#   FKS_DATA_EXCHANGE       - Exchange for live data (default: binance)
#   FKS_DATA_KLINE_INTERVALS - Kline intervals for live data (default: 1m,5m)
#   FKS_SKIP_DEPLOY         - Skip deployment, attach to running services (true/false)
# =============================================================================
set -euo pipefail

echo "════════════════════════════════════════════════════════════"
echo "🧪 PREPARING: ${FKS_TEST_LABEL}"
echo "════════════════════════════════════════════════════════════"
echo "🖥️  Host: $(hostname) | $(date)"
echo "💾 Disk: $(df -h / | tail -1 | awk '{print $4}') free"
echo "🧠 Memory: $(free -h | grep Mem | awk '{print $7}') available"
echo ""

# ── Test variables ──
TEST_TYPE="${FKS_TEST_TYPE}"
TEST_ID="${FKS_TEST_ID}"
TEST_DURATION="${FKS_DURATION_HOURS}"
SKIP_DEPLOY="${FKS_SKIP_DEPLOY:-false}"
RESULTS_BASE="$HOME/fks/test-results"
TEST_DIR="$RESULTS_BASE/$TEST_ID"

# ── Create structured log directory ──
mkdir -p "$TEST_DIR/logs"
mkdir -p "$TEST_DIR/metrics"
mkdir -p "$TEST_DIR/monitoring"
echo "📁 Test directory: $TEST_DIR"

# ── Save a breadcrumb for the deploy step to find ──
echo "$TEST_DIR" > /tmp/fks-test-dir

# ── Skip heavy setup for monitoring-only / attach modes ──
if [ "$SKIP_DEPLOY" = "true" ] || [ "$TEST_TYPE" = "rss-monitoring" ]; then
    echo "⏭️  Skip deploy mode — skipping repo clone and volume setup"
    echo "   Attaching to already-running services."
    echo ""

    # Verify services are actually running
    RUNNING=$(docker ps --filter "name=fks" --format '{{.Names}}' 2>/dev/null | wc -l)
    if [ "$RUNNING" -lt 1 ]; then
        echo "⚠️  Warning: No FKS containers found running."
        echo "   The deploy step may fail if services aren't available."
    else
        echo "📦 Found $RUNNING running container(s):"
        docker ps --filter "name=fks" --format "  {{.Names}} ({{.Status}})" 2>/dev/null
    fi
    echo ""
else
    # ── First-time setup — clone repo if missing (mirrors ci-cd pattern) ──
    if [ ! -d ~/fks/.git ]; then
        echo "📦 First-time setup — cloning repository..."
        rm -rf ~/fks
        git clone https://github.com/nuniesmith/fks.git ~/fks
    fi

    # ── Ensure all Docker volumes exist (mirrors ci-cd pattern) ──
    echo "📦 Ensuring Docker volumes exist..."
    for vol in fks_ssl_certs fks_certbot_www fks_postgres_data fks_questdb_data \
               fks_redis_data fks_grafana_data fks_prometheus_data fks_loki_data \
               fks_alertmanager_data fks_optimizer_data fks_promtail_positions \
               fks_nginx_logs; do
        docker volume create "$vol" 2>/dev/null || true
    done
    echo "✅ Docker volumes ready"
fi

# ── Create test env file for soak tests and audit-72h-soak ──
if [ "$TEST_TYPE" = "paper-trading-soak" ] || [ "$TEST_TYPE" = "audit-72h-soak" ]; then
    # Override duration for audit-72h-soak
    if [ "$TEST_TYPE" = "audit-72h-soak" ]; then
        TEST_DURATION=72
        echo "🔒 Audit 72h soak: forcing duration to 72 hours"
    fi

    TEST_ENV_FILE="$TEST_DIR/.env.test"
    cat > "$TEST_ENV_FILE" << ENVEOF
# ============================================
# FKS Paper Trading Test Configuration
# ============================================
# Test ID: ${TEST_ID}
# Type: ${TEST_TYPE}
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Duration: ${TEST_DURATION} hours
# Audit Mode: $([ "$TEST_TYPE" = "audit-72h-soak" ] && echo "YES — 72h RSS monitoring" || echo "no")
#
# ⚠️ PAPER TRADING ONLY — NO REAL ORDERS
# ============================================

TRADING_MODE=simulation
REAL_ORDERS_ENABLED=false

ENABLE_EXECUTION=true
EXECUTION_MODE=simulated
EXECUTION_EXCHANGE=binance
BYBIT_TESTNET=true

# ── Live Market Data Configuration ──
# Set DATA_SOURCE=live to ingest real exchange data via WebSocket.
# When "standby" (default), Forward uses synthetic demo signals.
DATA_SOURCE=${FKS_DATA_SOURCE:-standby}
DATA_EXCHANGE=${FKS_DATA_EXCHANGE:-binance}
DATA_WS_URL=${FKS_DATA_WS_URL:-wss://stream.binance.com:9443/ws}
DATA_KLINE_INTERVALS=${FKS_DATA_KLINE_INTERVALS:-1m,5m}
DATA_RECONNECT_DELAY_SECS=5
DATA_MAX_RECONNECT_ATTEMPTS=50
DATA_HEALTH_POLL_SECS=10

MAX_POSITION_SIZE=100
MAX_DAILY_LOSS=50
MAX_OPEN_ORDERS=5

OPTIMIZER_ENABLED=true
OPTIMIZE_INTERVAL=${FKS_OPTIMIZE_INTERVAL}
OPTIMIZE_ASSETS=${FKS_ASSETS}
OPTIMIZE_TRIALS=${FKS_OPTIMIZE_TRIALS}
OPTIMIZE_HISTORICAL_DAYS=14
OPTIMIZER_INSTANCE_ID=${TEST_ID}

POSTGRES_USER=fks_user
JANUS_DB=janus_db

TEST_ID=${TEST_ID}
TEST_START_TIME=${FKS_START_TIME}
TEST_DURATION_HOURS=${TEST_DURATION}
ENVEOF

    # Merge passwords from existing .env
    if [ -f .env ]; then
        grep -E "^(POSTGRES_PASSWORD|REDIS_PASSWORD|QUESTDB_PASSWORD|GRAFANA_PASSWORD|GF_SECURITY_ADMIN_PASSWORD)=" .env >> "$TEST_ENV_FILE" 2>/dev/null || true
    fi

    echo "✅ Test env file created: $TEST_ENV_FILE"
fi

# ── Clean up old test results (keep last 10) ──
if [ -d "$RESULTS_BASE" ]; then
    OLD_DIRS=$(ls -dt "$RESULTS_BASE"/*/ 2>/dev/null | tail -n +11 || true)
    if [ -n "$OLD_DIRS" ]; then
        echo "🧹 Cleaning up old test results (keeping last 10)..."
        echo "$OLD_DIRS" | xargs rm -rf 2>/dev/null || true
    fi
fi

# ── Log monitoring intent ──
if [ "$TEST_TYPE" = "rss-monitoring" ]; then
    echo ""
    echo "📈 RSS monitoring mode:"
    echo "  This run will attach RSS memory monitoring to existing services."
    echo "  No services will be deployed or restarted."
    echo "  Output: $TEST_DIR/monitoring/"
elif [ "$TEST_TYPE" = "audit-72h-soak" ]; then
    echo ""
    echo "🔒 Audit 72-hour soak test mode:"
    echo "  Paper trading + RSS memory monitoring for 72 hours."
    echo "  This satisfies Audit Remediation Item #1."
    echo "  Pass criteria:"
    echo "    - No service exceeds RSS growth threshold"
    echo "    - 6h derivative < 0.5 KB/s"
    echo "    - No OOM kills or container restarts"
    echo "  Output: $TEST_DIR/monitoring/"
fi

echo ""
echo "✅ Pre-deploy setup complete"
