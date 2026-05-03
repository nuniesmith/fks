#!/bin/bash
# =============================================================================
# FKS Paper Trading Test — Post-Deploy Verification
# =============================================================================
# Quick verification that services are healthy after deployment. Called by the
# workflow via ssh-deploy post-deploy-command.
#
# Required environment variables (set by the workflow):
#   FKS_TEST_TYPE           - Test type (paper-trading-soak, health-check, etc.)
#   FKS_TEST_ID             - Unique test identifier
#   FKS_RSS_ENABLED         - Whether RSS monitoring is enabled (true/false)
# =============================================================================
set -euo pipefail

TEST_TYPE="${FKS_TEST_TYPE}"
TEST_ID="${FKS_TEST_ID}"
RSS_ENABLED="${FKS_RSS_ENABLED:-false}"
TEST_DIR="$(cat /tmp/fks-test-dir 2>/dev/null || echo "$HOME/fks/test-results/$TEST_ID")"

echo ""
echo "🔍 Post-deploy verification..."

# ── Quick health check ──
SERVICES_OK=0
SERVICES_FAIL=0

for endpoint in \
    "http://localhost:8080/health" \
    "http://localhost:8080/api/v1/health" \
    "http://localhost:7000/health"; do
    if curl -sf "$endpoint" >/dev/null 2>&1; then
        echo "  ✅ Janus responding at $endpoint"
        SERVICES_OK=$((SERVICES_OK + 1))
        break
    fi
done

# Execution is embedded inside Janus (ENABLE_EXECUTION=true, localhost:50052 internal).
# If Janus is healthy, execution is available — no separate container or port to check.
if curl -sf http://localhost:8081/health >/dev/null 2>&1; then
    echo "  ✅ Execution service healthy (standalone at :8081)"
    SERVICES_OK=$((SERVICES_OK + 1))
elif [ "$SERVICES_OK" -gt 0 ]; then
    # Janus was already confirmed healthy above — execution is embedded
    EXEC_ENABLED=$(docker exec fks_janus printenv ENABLE_EXECUTION 2>/dev/null || echo "")
    if [ "$EXEC_ENABLED" = "true" ]; then
        echo "  ✅ Execution enabled inside Janus (ENABLE_EXECUTION=true)"
        SERVICES_OK=$((SERVICES_OK + 1))
    else
        echo "  ℹ️  Execution not enabled in Janus (ENABLE_EXECUTION=${EXEC_ENABLED:-unset})"
    fi
else
    echo "  ⚠️ Execution unavailable — Janus is not responding either"
    SERVICES_FAIL=$((SERVICES_FAIL + 1))
fi

curl -sf http://localhost:9000 >/dev/null 2>&1 \
    && { echo "  ✅ QuestDB healthy"; SERVICES_OK=$((SERVICES_OK + 1)); } \
    || { echo "  ⚠️ QuestDB not responding"; SERVICES_FAIL=$((SERVICES_FAIL + 1)); }

curl -sf http://localhost:9090/-/healthy >/dev/null 2>&1 \
    && { echo "  ✅ Prometheus healthy"; SERVICES_OK=$((SERVICES_OK + 1)); } \
    || echo "  ℹ️  Prometheus not responding"

# Load Redis password for authenticated health check
_REDIS_PW=""
if [ -f "$TEST_DIR/.env.test" ]; then
    _REDIS_PW=$(grep -E "^REDIS_PASSWORD=" "$TEST_DIR/.env.test" | head -1 | cut -d'=' -f2- | tr -d '"' || true)
fi
if [ -z "$_REDIS_PW" ] && [ -f "$HOME/fks/.env" ]; then
    _REDIS_PW=$(grep -E "^REDIS_PASSWORD=" "$HOME/fks/.env" | head -1 | cut -d'=' -f2- | tr -d '"' || true)
fi
if [ -n "$_REDIS_PW" ]; then
    REDIS_REPLY=$(docker exec fks_redis redis-cli -a "$_REDIS_PW" --no-auth-warning ping 2>/dev/null || true)
else
    REDIS_REPLY=$(docker exec fks_redis redis-cli ping 2>/dev/null || true)
fi
echo "$REDIS_REPLY" | grep -q "PONG" \
    && { echo "  ✅ Redis healthy"; SERVICES_OK=$((SERVICES_OK + 1)); } \
    || { echo "  ⚠️ Redis not responding (got: $REDIS_REPLY)"; SERVICES_FAIL=$((SERVICES_FAIL + 1)); }

echo ""

# ── Optimizer status (soak tests only) ──
if [ "$TEST_TYPE" = "paper-trading-soak" ]; then
    echo "🔧 Optimizer status:"
    docker exec fks_janus /app/janus-optimizer status 2>&1 | head -10 || echo "  ⚠️ Could not get optimizer status"
fi

# ── Check health monitor is running (soak tests only) ──
if [ -f "$TEST_DIR/logs/health-monitor.pid" ]; then
    HPID=$(cat "$TEST_DIR/logs/health-monitor.pid")
    if ps -p "$HPID" > /dev/null 2>&1; then
        echo "  ✅ Background health monitor running (PID: $HPID)"
    else
        echo "  ⚠️ Background health monitor not running"
    fi
fi

# ── Check RSS monitoring (composable layer) ──
if [ "$RSS_ENABLED" = "true" ]; then
    echo ""
    echo "📈 RSS monitoring status:"
    if [ -f "$TEST_DIR/monitoring/rss-monitor.pid" ]; then
        RPID=$(cat "$TEST_DIR/monitoring/rss-monitor.pid")
        if ps -p "$RPID" > /dev/null 2>&1; then
            echo "  ✅ RSS monitor running (PID: $RPID)"
            # Show a quick sample count if CSV exists
            CSV_FILE=$(ls -t "$TEST_DIR/monitoring/rss_samples_"*.csv 2>/dev/null | head -1)
            if [ -n "$CSV_FILE" ]; then
                SAMPLE_COUNT=$(($(wc -l < "$CSV_FILE") - 1))
                echo "  📊 Samples collected so far: $SAMPLE_COUNT"
            fi
        else
            echo "  ⚠️ RSS monitor not running (PID $RPID exited)"
            SERVICES_FAIL=$((SERVICES_FAIL + 1))
        fi
    else
        echo "  ⚠️ RSS monitor PID file not found — may not have started yet"
    fi
    echo "  📁 Output: $TEST_DIR/monitoring/"
    echo "  💡 Check: $TEST_DIR/monitoring/check-rss.sh"
elif [ "$TEST_TYPE" = "rss-monitoring" ] || [ "$TEST_TYPE" = "audit-72h-soak" ]; then
    echo ""
    echo "📈 RSS monitoring:"
    echo "  ⚠️ RSS monitoring should be enabled for this test type but FKS_RSS_ENABLED is not 'true'"
fi

echo ""
echo "✅ Deployment verified. $SERVICES_OK services OK, $SERVICES_FAIL issues."
