#!/usr/bin/env bash
# ============================================================================
# FKS Signals System - Integration Test Suite
# ============================================================================
# Comprehensive integration test to verify all components work together:
# - Service health and connectivity
# - JWT authentication (if enabled)
# - Signal generation pipeline
# - WebSocket streaming
# - REST API endpoints
# - Discord alert bridge
# - Prometheus metrics
# - QuestDB persistence
#
# Usage:
#   ./integration-test.sh
#   ./integration-test.sh --jwt-enabled  # Test with JWT auth
#   ./integration-test.sh --quick        # Skip long-running tests
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
API_HOST="${API_HOST:-localhost:8080}"
QUESTDB_HOST="${QUESTDB_HOST:-localhost:9000}"
PROMETHEUS_HOST="${PROMETHEUS_HOST:-localhost:9090}"
DISCORD_BRIDGE_HOST="${DISCORD_BRIDGE_HOST:-localhost:9094}"
JWT_ENABLED=false
QUICK_MODE=false
JWT_TOKEN=""

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Parse arguments
for arg in "$@"; do
    case $arg in
        --jwt-enabled)
            JWT_ENABLED=true
            shift
            ;;
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --jwt-enabled    Test with JWT authentication enabled"
            echo "  --quick          Skip long-running tests"
            echo "  --help           Show this help message"
            exit 0
            ;;
    esac
done

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo -e "${BLUE}"
    echo "============================================================================"
    echo "$1"
    echo "============================================================================"
    echo -e "${NC}"
}

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓ PASS${NC} $1"
    ((TESTS_PASSED++))
}

print_fail() {
    echo -e "${RED}✗ FAIL${NC} $1"
    ((TESTS_FAILED++))
}

print_skip() {
    echo -e "${YELLOW}⊘ SKIP${NC} $1"
    ((TESTS_SKIPPED++))
}

print_info() {
    echo -e "${BLUE}ℹ INFO${NC} $1"
}

# Make HTTP request with optional JWT
http_get() {
    local url=$1
    local headers=()

    if [ "$JWT_ENABLED" = true ] && [ -n "$JWT_TOKEN" ]; then
        headers+=(-H "Authorization: Bearer $JWT_TOKEN")
    fi

    curl -s -f "${headers[@]}" "$url"
}

http_post() {
    local url=$1
    local data=$2
    local headers=(-H "Content-Type: application/json")

    if [ "$JWT_ENABLED" = true ] && [ -n "$JWT_TOKEN" ]; then
        headers+=(-H "Authorization: Bearer $JWT_TOKEN")
    fi

    curl -s -f "${headers[@]}" -X POST -d "$data" "$url"
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

print_header "Pre-flight Checks"

print_test "Checking docker-compose is running"
if docker-compose ps | grep -q "Up"; then
    print_success "Docker Compose services are running"
else
    print_fail "Docker Compose services not running. Run './run.sh start' first"
    exit 1
fi

print_test "Checking required commands are available"
MISSING_CMDS=()
for cmd in curl jq python3 docker-compose; do
    if ! command -v $cmd &> /dev/null; then
        MISSING_CMDS+=($cmd)
    fi
done

if [ ${#MISSING_CMDS[@]} -eq 0 ]; then
    print_success "All required commands available"
else
    print_fail "Missing commands: ${MISSING_CMDS[*]}"
    exit 1
fi

# ============================================================================
# Service Health Tests
# ============================================================================

print_header "Service Health Tests"

print_test "Data service health endpoint"
if RESPONSE=$(curl -s -f http://$API_HOST/health); then
    if echo "$RESPONSE" | jq -e '.status == "healthy"' > /dev/null 2>&1; then
        print_success "Data service is healthy"
    else
        print_fail "Data service health check returned unexpected response: $RESPONSE"
    fi
else
    print_fail "Data service health endpoint not responding"
fi

print_test "QuestDB health endpoint"
if RESPONSE=$(curl -s -f "http://$QUESTDB_HOST/exec?query=SELECT+1"); then
    print_success "QuestDB is healthy"
else
    print_fail "QuestDB not responding"
fi

print_test "Prometheus health endpoint"
if curl -s -f "http://$PROMETHEUS_HOST/-/healthy" > /dev/null; then
    print_success "Prometheus is healthy"
else
    print_fail "Prometheus not responding"
fi

print_test "Discord bridge health endpoint"
if RESPONSE=$(curl -s -f "http://$DISCORD_BRIDGE_HOST/health"); then
    if echo "$RESPONSE" | jq -e '.status == "ok"' > /dev/null 2>&1; then
        print_success "Discord bridge is healthy"
    else
        print_fail "Discord bridge health check failed: $RESPONSE"
    fi
else
    print_fail "Discord bridge not responding"
fi

# ============================================================================
# JWT Authentication Tests
# ============================================================================

if [ "$JWT_ENABLED" = true ]; then
    print_header "JWT Authentication Tests"

    print_test "Verify JWT authentication is enabled"
    if docker-compose logs data-service 2>&1 | grep -q "JWT authentication is ENABLED"; then
        print_success "JWT authentication is enabled"
    else
        print_fail "JWT authentication not enabled in logs"
    fi

    print_test "Test protected endpoint without token"
    if curl -s -o /dev/null -w "%{http_code}" "http://$API_HOST/api/v1/signals/stats" | grep -q "401"; then
        print_success "Protected endpoint returns 401 without token"
    else
        print_fail "Protected endpoint should return 401 without token"
    fi

    print_info "Note: For full JWT testing, implement token generation endpoint"
    print_skip "JWT token generation and validation (requires implementation)"
else
    print_header "JWT Authentication Tests"
    print_skip "JWT authentication disabled (use --jwt-enabled to test)"
fi

# ============================================================================
# Metrics Tests
# ============================================================================

print_header "Metrics Tests"

print_test "Prometheus metrics endpoint"
if RESPONSE=$(curl -s -f "http://$API_HOST/metrics"); then
    if echo "$RESPONSE" | grep -q "signals_generated_total"; then
        print_success "Prometheus metrics exposed"
    else
        print_fail "Prometheus metrics missing expected signal metrics"
    fi
else
    print_fail "Metrics endpoint not responding"
fi

print_test "Prometheus scraping data-service target"
if RESPONSE=$(curl -s "http://$PROMETHEUS_HOST/api/v1/targets" | jq -r '.data.activeTargets[] | select(.labels.job=="data-service") | .health'); then
    if [ "$RESPONSE" = "up" ]; then
        print_success "Prometheus is scraping data-service"
    else
        print_fail "data-service target is not up in Prometheus"
    fi
else
    print_fail "Failed to query Prometheus targets"
fi

# ============================================================================
# QuestDB Schema Tests
# ============================================================================

print_header "QuestDB Schema Tests"

print_test "Check signals_crypto table exists"
if RESPONSE=$(curl -s "http://$QUESTDB_HOST/exec?query=SELECT+COUNT(*)+FROM+signals_crypto" 2>&1); then
    if echo "$RESPONSE" | jq -e '.dataset' > /dev/null 2>&1; then
        SIGNAL_COUNT=$(echo "$RESPONSE" | jq -r '.dataset[0][0]')
        print_success "signals_crypto table exists with $SIGNAL_COUNT signals"
    else
        print_fail "signals_crypto table query failed: $RESPONSE"
    fi
else
    print_fail "Failed to query signals_crypto table"
fi

print_test "Check table schema has required columns"
if RESPONSE=$(curl -s "http://$QUESTDB_HOST/exec?query=SELECT+symbol,signal_type,timestamp+FROM+signals_crypto+LIMIT+1"); then
    if echo "$RESPONSE" | jq -e '.columns[] | select(.name=="symbol")' > /dev/null 2>&1 && \
       echo "$RESPONSE" | jq -e '.columns[] | select(.name=="signal_type")' > /dev/null 2>&1 && \
       echo "$RESPONSE" | jq -e '.columns[] | select(.name=="timestamp")' > /dev/null 2>&1; then
        print_success "Table schema has required columns"
    else
        print_fail "Table schema missing required columns"
    fi
else
    print_fail "Failed to query table schema"
fi

# ============================================================================
# Indicator Warmup Tests
# ============================================================================

print_header "Indicator Warmup Tests"

print_test "Check indicator warmup status"
if RESPONSE=$(http_get "http://$API_HOST/api/v1/indicators/BTCUSD/1m/status"); then
    ALL_READY=$(echo "$RESPONSE" | jq -r '.all_indicators_ready // false')
    if [ "$ALL_READY" = "true" ]; then
        print_success "All indicators are warmed up for BTCUSD/1m"
    else
        print_info "Indicators not yet warmed up, attempting deep warmup..."

        print_test "Trigger deep warmup"
        if WARMUP_RESPONSE=$(http_post "http://$API_HOST/api/v1/indicators/warmup/deep" \
            '{"symbols":["BTCUSD"],"timeframes":["1m"],"limit":250}'); then
            print_success "Deep warmup triggered successfully"

            # Wait for warmup to complete
            print_info "Waiting 30 seconds for warmup to complete..."
            sleep 30

            # Check again
            if RESPONSE=$(http_get "http://$API_HOST/api/v1/indicators/BTCUSD/1m/status"); then
                ALL_READY=$(echo "$RESPONSE" | jq -r '.all_indicators_ready // false')
                if [ "$ALL_READY" = "true" ]; then
                    print_success "Indicators warmed up after deep warmup"
                else
                    print_fail "Indicators still not ready after deep warmup"
                fi
            fi
        else
            print_fail "Deep warmup request failed"
        fi
    fi
else
    print_fail "Failed to check indicator warmup status"
fi

# ============================================================================
# Signal Generation Tests
# ============================================================================

print_header "Signal Generation Tests"

print_test "Wait for signals to generate (30 seconds)"
sleep 30

print_test "Check signal statistics endpoint"
if RESPONSE=$(http_get "http://$API_HOST/api/v1/signals/stats"); then
    TOTAL_SIGNALS=$(echo "$RESPONSE" | jq -r '.total_signals // 0')
    if [ "$TOTAL_SIGNALS" -gt 0 ]; then
        print_success "Signals are being generated (total: $TOTAL_SIGNALS)"
    else
        print_fail "No signals generated yet (may need more time or indicator warmup)"
    fi
else
    print_fail "Failed to fetch signal statistics"
fi

print_test "Verify signals persisted to QuestDB"
if RESPONSE=$(curl -s "http://$QUESTDB_HOST/exec?query=SELECT+COUNT(*)+FROM+signals_crypto"); then
    DB_COUNT=$(echo "$RESPONSE" | jq -r '.dataset[0][0] // 0')
    if [ "$DB_COUNT" -gt 0 ]; then
        print_success "Signals persisted to QuestDB (count: $DB_COUNT)"
    else
        print_fail "No signals found in QuestDB"
    fi
else
    print_fail "Failed to query signals from QuestDB"
fi

# ============================================================================
# REST API Tests
# ============================================================================

print_header "REST API Tests"

print_test "List all signals (limit 5)"
if RESPONSE=$(http_get "http://$API_HOST/api/v1/signals?limit=5"); then
    COUNT=$(echo "$RESPONSE" | jq -r '.count // 0')
    print_success "List signals API returned $COUNT signals"
else
    print_fail "Failed to list signals"
fi

print_test "Get signals by symbol (BTCUSD)"
if RESPONSE=$(http_get "http://$API_HOST/api/v1/signals/BTCUSD?limit=5"); then
    SIGNALS=$(echo "$RESPONSE" | jq -r '.signals // []')
    if echo "$SIGNALS" | jq -e 'length > 0' > /dev/null 2>&1; then
        print_success "Retrieved signals for BTCUSD"
    else
        print_info "No signals yet for BTCUSD (may need more time)"
        print_skip "Signals by symbol test (no data yet)"
    fi
else
    print_fail "Failed to get signals by symbol"
fi

print_test "Get signals by symbol and timeframe (BTCUSD/1m)"
if RESPONSE=$(http_get "http://$API_HOST/api/v1/signals/BTCUSD/1m?limit=5"); then
    print_success "Retrieved signals for BTCUSD/1m"
else
    print_fail "Failed to get signals by symbol and timeframe"
fi

# ============================================================================
# WebSocket Tests
# ============================================================================

print_header "WebSocket Tests"

if command -v python3 &> /dev/null; then
    print_test "WebSocket connection and subscription"

    # Create temporary Python script for WebSocket test
    WS_TEST_SCRIPT="/tmp/ws_test_$$.py"
    cat > "$WS_TEST_SCRIPT" << 'PYTHON_EOF'
import asyncio
import json
import sys
import websockets

async def test_websocket():
    try:
        async with websockets.connect('ws://localhost:8080/ws/signals', timeout=5) as ws:
            # Send subscription
            await ws.send(json.dumps({
                "symbols": ["BTCUSD"],
                "timeframes": ["1m"]
            }))

            # Wait for response (with timeout)
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)
                print(json.dumps(data))
                return 0
            except asyncio.TimeoutError:
                print('{"error": "timeout"}', file=sys.stderr)
                return 1
    except Exception as e:
        print(f'{{"error": "{str(e)}"}}', file=sys.stderr)
        return 1

sys.exit(asyncio.run(test_websocket()))
PYTHON_EOF

    if python3 -c "import websockets" 2>/dev/null; then
        if python3 "$WS_TEST_SCRIPT" > /dev/null 2>&1; then
            print_success "WebSocket connection and subscription successful"
        else
            print_fail "WebSocket connection failed (check if websockets module is installed: pip install websockets)"
        fi
        rm -f "$WS_TEST_SCRIPT"
    else
        print_skip "WebSocket test (websockets module not installed: pip install websockets)"
    fi
else
    print_skip "WebSocket test (python3 not available)"
fi

# ============================================================================
# Backtest Tests
# ============================================================================

if [ "$QUICK_MODE" = false ]; then
    print_header "Backtest Tests"

    print_test "Run backtest API"
    BACKTEST_PAYLOAD='{
        "symbol": "BTCUSD",
        "timeframe": "1m",
        "lookforward_minutes": 60,
        "profit_target_pct": 1.0,
        "stop_loss_pct": 0.5
    }'

    if RESPONSE=$(http_post "http://$API_HOST/api/v1/signals/backtest" "$BACKTEST_PAYLOAD"); then
        TOTAL_SIGNALS=$(echo "$RESPONSE" | jq -r '.total_signals // 0')
        TOTAL_TRADES=$(echo "$RESPONSE" | jq -r '.total_trades // 0')
        print_success "Backtest completed (signals: $TOTAL_SIGNALS, trades: $TOTAL_TRADES)"
    else
        print_fail "Backtest API failed"
    fi
else
    print_header "Backtest Tests"
    print_skip "Backtest test (quick mode enabled)"
fi

# ============================================================================
# Discord Alert Tests
# ============================================================================

print_header "Discord Alert Tests"

print_test "Send test alert to Discord bridge"
TEST_ALERT='[{
    "labels": {
        "alertname": "IntegrationTest",
        "severity": "info"
    },
    "annotations": {
        "summary": "Integration test alert from test suite"
    }
}]'

if curl -s -f -X POST "http://$DISCORD_BRIDGE_HOST/" \
    -H "Content-Type: application/json" \
    -d "$TEST_ALERT" > /dev/null; then
    print_success "Test alert sent to Discord bridge"
    print_info "Check your Discord channel for the test message"
else
    print_fail "Failed to send test alert to Discord bridge"
fi

# ============================================================================
# Load Test (Quick)
# ============================================================================

if [ "$QUICK_MODE" = false ]; then
    print_header "Load Test (Quick)"

    print_test "API load test (100 concurrent requests)"
    START_TIME=$(date +%s)
    for i in {1..100}; do
        curl -s -f "http://$API_HOST/api/v1/signals/stats" > /dev/null &
    done
    wait
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    if [ $DURATION -lt 10 ]; then
        print_success "Load test completed in ${DURATION}s (100 requests)"
    else
        print_fail "Load test took too long: ${DURATION}s (expected <10s)"
    fi
else
    print_header "Load Test"
    print_skip "Load test (quick mode enabled)"
fi

# ============================================================================
# Test Summary
# ============================================================================

print_header "Test Summary"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))

echo ""
echo -e "${GREEN}Passed:  $TESTS_PASSED${NC}"
echo -e "${RED}Failed:  $TESTS_FAILED${NC}"
echo -e "${YELLOW}Skipped: $TESTS_SKIPPED${NC}"
echo -e "Total:   $TOTAL_TESTS"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "System is ready for deployment."
    echo ""
    echo "Next steps:"
    echo "  1. Run 48-hour soak test: python scripts/testing/websocket-soak-test.py --duration 48"
    echo "  2. Run comprehensive backtests: python scripts/testing/run-backtests.py"
    echo "  3. Review docs/SIGNALS_DEPLOYMENT_CHECKLIST.md for production deployment"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Review the failures above and fix issues before deploying."
    echo "Common fixes:"
    echo "  - Ensure all services are running: ./run.sh start"
    echo "  - Check service logs: docker-compose logs data-service"
    echo "  - Verify indicators are warmed up: curl http://localhost:8080/api/v1/indicators/BTCUSD/1m/status"
    exit 1
fi
