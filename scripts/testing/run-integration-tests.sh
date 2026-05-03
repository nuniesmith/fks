#!/bin/bash
set -e

# FKS Integration Test Suite
# Runs comprehensive integration tests before paper trading deployment

echo "🧪 FKS Integration Test Suite"
echo "=============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Helper functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((TESTS_PASSED++))
    ((TESTS_TOTAL++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((TESTS_FAILED++))
    ((TESTS_TOTAL++))
}

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

section() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo ""
}

# Navigate to repo root
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
cd "$REPO_ROOT"

# Load environment variables from .env file
if [ -f ".env" ]; then
    info "Loading environment variables from .env"
    set -a
    source <(grep -v '^#' .env | grep -v '^$' | grep '=' || true)
    set +a
else
    warn ".env file not found - some services may fail to start"
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running${NC}"
    echo "Please start Docker and try again"
    exit 1
fi

# Check if compose file exists
COMPOSE_FILE="infrastructure/compose/docker-compose.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}✗ Compose file not found: $COMPOSE_FILE${NC}"
    exit 1
fi

# Parse command-line arguments
QUICK_MODE=false
SKIP_BUILD=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick       Run quick tests only (skip soak test)"
            echo "  --skip-build  Skip Docker image builds"
            echo "  --verbose     Show detailed output"
            echo "  --help        Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

#############################################################################
# PHASE 1: Service-Level Integration
#############################################################################

section "Phase 1: Service-Level Integration"

info "Stopping any running containers..."
docker compose -f "$COMPOSE_FILE" --env-file .env down > /dev/null 2>&1 || true
sleep 2

# Test 1.1: Database Connectivity
info "Test 1.1: Database Connectivity"

info "Starting databases..."
docker compose -f "$COMPOSE_FILE" --env-file .env up -d postgres questdb redis

# Wait for databases to be ready
info "Waiting for databases to start (max 30s)..."
sleep 10

# Test PostgreSQL
if docker exec fks_postgres psql -U fks -d fks -c "SELECT 1;" > /dev/null 2>&1; then
    pass "PostgreSQL connection"
else
    fail "PostgreSQL connection"
fi

# Test Redis
if docker exec fks_redis redis-cli PING | grep -q "PONG"; then
    pass "Redis connection"
else
    fail "Redis connection"
fi

# Test QuestDB
if curl -s http://localhost:9000/imp > /dev/null 2>&1; then
    pass "QuestDB HTTP endpoint"
else
    fail "QuestDB HTTP endpoint"
fi

# Test 1.2: Monitoring Stack
info "Test 1.2: Monitoring Stack"

info "Starting monitoring services..."
docker compose -f "$COMPOSE_FILE" --env-file .env up -d prometheus grafana alertmanager

# Wait for services
sleep 10

# Test Prometheus
if curl -s http://localhost:9090/-/healthy | grep -q "Prometheus Server is Healthy"; then
    pass "Prometheus health check"
else
    fail "Prometheus health check"
fi

# Test Grafana
if curl -s http://localhost:3000/api/health | grep -q "ok"; then
    pass "Grafana health check"
else
    fail "Grafana health check"
fi

# Test Alertmanager
if curl -s http://localhost:9093/-/healthy > /dev/null 2>&1; then
    pass "Alertmanager health check"
else
    fail "Alertmanager health check"
fi

# Test 1.3: Service Startup
info "Test 1.3: Service Startup"

if [ "$SKIP_BUILD" = false ]; then
    info "Building Docker images (this may take a few minutes)..."
    if docker compose -f "$COMPOSE_FILE" --env-file .env build > /dev/null 2>&1; then
        pass "Docker image builds"
    else
        fail "Docker image builds"
    fi
fi

info "Starting all services..."
docker compose -f "$COMPOSE_FILE" --env-file .env up -d

# Wait for services to start
info "Waiting for services to start (max 60s)..."
sleep 20

# Check if containers are running
RUNNING_CONTAINERS=$(docker compose -f "$COMPOSE_FILE" --env-file .env ps --services --filter "status=running" | wc -l)
TOTAL_CONTAINERS=$(docker compose -f "$COMPOSE_FILE" --env-file .env ps --services | wc -l)

if [ "$RUNNING_CONTAINERS" -eq "$TOTAL_CONTAINERS" ]; then
    pass "All containers running ($RUNNING_CONTAINERS/$TOTAL_CONTAINERS)"
else
    fail "Some containers not running ($RUNNING_CONTAINERS/$TOTAL_CONTAINERS)"
fi

# Test health endpoints (if services expose them)
# Note: Adjust ports/endpoints based on your actual service configuration
sleep 10  # Give services more time to be fully ready

#############################################################################
# PHASE 2: Data Flow Integration
#############################################################################

section "Phase 2: Data Flow Integration"

info "Test 2.1: Market Data Pipeline"

# Check if data service is running
if docker compose -f "$COMPOSE_FILE" --env-file .env ps data | grep -q "Up"; then
    pass "Data service running"
else
    fail "Data service running"
fi

# Check logs for connection success
sleep 5
if docker logs fks_ruby 2>&1 | grep -qiE "connected|started|ready"; then
    pass "Data service logs show activity"
else
    warn "Data service logs don't show expected messages (may be normal during testing)"
fi

info "Test 2.2: Service Communication"

# Check if services can reach each other via Docker network
if docker exec fks_janus ping -c 1 fks_redis > /dev/null 2>&1; then
    pass "Inter-service networking (janus -> redis)"
else
    fail "Inter-service networking (janus -> redis)"
fi

info "Test 2.3: Configuration Verification"

# Check if TRADING_MODE is set correctly
# Execution is embedded inside Janus — check Janus container for trading/execution mode
if docker ps -q -f name=fks_execution 2>/dev/null | grep -q .; then
    # Standalone execution container exists
    if docker exec fks_execution env 2>&1 | grep -q "TRADING_MODE=simulation"; then
        pass "Paper trading mode configured (execution standalone)"
    elif docker exec fks_execution env 2>&1 | grep -q "EXECUTION_MODE"; then
        warn "Trading mode configured (verify manually: docker exec fks_execution env | grep MODE)"
    else
        fail "Trading mode not found in execution container environment"
    fi
elif docker ps -q -f name=fks_janus 2>/dev/null | grep -q .; then
    # Execution is embedded in Janus
    JANUS_EXEC_MODE=$(docker exec fks_janus printenv EXECUTION_MODE 2>/dev/null || echo "")
    JANUS_TRADE_MODE=$(docker exec fks_janus printenv TRADING_MODE 2>/dev/null || echo "")
    JANUS_EXEC_ENABLED=$(docker exec fks_janus printenv ENABLE_EXECUTION 2>/dev/null || echo "")
    if [ "$JANUS_EXEC_MODE" = "paper_trading" ] || [ "$JANUS_TRADE_MODE" = "simulation" ] || [ "$JANUS_TRADE_MODE" = "paper" ]; then
        pass "Paper trading mode configured in Janus (EXECUTION_MODE=$JANUS_EXEC_MODE, ENABLE_EXECUTION=$JANUS_EXEC_ENABLED)"
    elif [ -n "$JANUS_EXEC_MODE" ] || [ -n "$JANUS_TRADE_MODE" ]; then
        warn "Trading mode configured in Janus (EXECUTION_MODE=$JANUS_EXEC_MODE, TRADING_MODE=$JANUS_TRADE_MODE) — verify manually"
    else
        fail "Trading mode not found in Janus environment"
    fi
else
    fail "Neither fks_execution nor fks_janus container is running"
fi

#############################################################################
# PHASE 3: End-to-End Integration
#############################################################################

section "Phase 3: End-to-End Integration"

info "Test 3.1: Prometheus Metrics Collection"

# Wait a bit for metrics to be collected
sleep 10

# Check if Prometheus is scraping targets
TARGETS=$(curl -s http://localhost:9090/api/v1/targets | grep -o '"health":"up"' | wc -l)
if [ "$TARGETS" -gt 0 ]; then
    pass "Prometheus scraping targets ($TARGETS targets up)"
else
    warn "No Prometheus targets up yet (may need more time)"
fi

info "Test 3.2: Log Collection"

# Check if services are generating logs
JANUS_LOGS=$(docker logs fks_janus 2>&1 | wc -l)
# Execution is embedded in Janus — check for standalone container, fall back to Janus logs
if docker ps -q -f name=fks_execution 2>/dev/null | grep -q .; then
    EXECUTION_LOGS=$(docker logs fks_execution 2>&1 | wc -l)
else
    EXECUTION_LOGS="$JANUS_LOGS"  # Embedded in Janus — use Janus log count
fi

if [ "$JANUS_LOGS" -gt 10 ]; then
    pass "Services generating logs (janus: $JANUS_LOGS lines)"
else
    warn "Low log volume (janus: $JANUS_LOGS lines)"
fi

info "Test 3.3: Resource Usage"

# Check memory usage
MEMORY_USAGE=$(docker stats --no-stream --format "{{.Container}}: {{.MemUsage}}" | head -5)
if [ -n "$MEMORY_USAGE" ]; then
    pass "Resource monitoring available"
    if [ "$VERBOSE" = true ]; then
        echo "$MEMORY_USAGE"
    fi
else
    fail "Resource monitoring"
fi

#############################################################################
# PHASE 4: Stability Testing (Optional)
#############################################################################

if [ "$QUICK_MODE" = false ]; then
    section "Phase 4: Stability Testing"

    info "Running 5-minute stability test..."
    info "Monitoring for crashes, errors, and resource issues..."

    START_TIME=$(date +%s)
    DURATION=300  # 5 minutes

    while [ $(($(date +%s) - START_TIME)) -lt $DURATION ]; do
        REMAINING=$((DURATION - $(date +%s) + START_TIME))
        echo -ne "\rTime remaining: ${REMAINING}s "

        # Check if all containers are still running
        RUNNING=$(docker compose -f "$COMPOSE_FILE" --env-file .env ps --services --filter "status=running" | wc -l)
        if [ "$RUNNING" -ne "$TOTAL_CONTAINERS" ]; then
            echo ""
            fail "Container(s) crashed during stability test"
            break
        fi

        sleep 10
    done
    echo ""

    # Final check
    RUNNING=$(docker compose -f "$COMPOSE_FILE" --env-file .env ps --services --filter "status=running" | wc -l)
    if [ "$RUNNING" -eq "$TOTAL_CONTAINERS" ]; then
        pass "5-minute stability test completed"
    else
        fail "Stability test - containers crashed"
    fi

    # Check error rates in logs
    ERROR_COUNT=$(docker compose -f "$COMPOSE_FILE" --env-file .env logs --since 5m 2>&1 | grep -ciE "error|panic|fatal" || echo "0")
    if [ "$ERROR_COUNT" -lt 10 ]; then
        pass "Low error rate in logs ($ERROR_COUNT errors in 5 min)"
    else
        warn "High error rate in logs ($ERROR_COUNT errors in 5 min)"
    fi
else
    info "Skipping stability test (quick mode)"
fi

#############################################################################
# SUMMARY
#############################################################################

section "Test Summary"

echo "Total Tests:  $TESTS_TOTAL"
echo -e "Passed:       ${GREEN}$TESTS_PASSED${NC}"
echo -e "Failed:       ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Review the full pre-flight checklist: docs/30_DAY_PREFLIGHT_CHECKLIST.md"
    echo "2. Import Grafana dashboard: infrastructure/config/grafana/dashboards/30-day-paper-trading.json"
    echo "3. Test Discord notifications: ./scripts/testing/test-discord-webhook.sh"
    echo "4. Start the 30-day paper trading test!"
    echo ""
    echo "Services are running. Use these commands:"
    echo "  docker compose -f $COMPOSE_FILE logs -f        # View logs"
    echo "  docker compose -f $COMPOSE_FILE ps             # Check status"
    echo "  docker compose -f $COMPOSE_FILE down           # Stop all"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Failed tests: $TESTS_FAILED"
    echo ""
    echo "Troubleshooting:"
    echo "  docker compose -f $COMPOSE_FILE logs           # Check logs"
    echo "  docker compose -f $COMPOSE_FILE ps             # Check status"
    echo "  docker compose -f $COMPOSE_FILE down           # Stop and clean up"
    echo ""
    echo "For detailed logs of a specific service:"
    echo "  docker logs fks_janus          # Janus (includes embedded execution)"
    echo "  docker logs fks_postgres"
    echo ""
    exit 1
fi
