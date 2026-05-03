#!/bin/bash
#
# FKS Test Control Script
# =======================
# Monitor and control running paper trading tests on the server.
#
# Usage:
#   ./scripts/test-control.sh <command>
#
# Commands:
#   status      Show current test status
#   logs        Follow live logs
#   health      Run health check
#   optimize    Trigger manual optimization
#   stop        Stop the test
#   report      Generate test report
#   signals     Show recent signals
#   errors      Show recent errors
#   memory      Show memory usage over time
#   restart     Restart trading services
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="$PROJECT_ROOT/infrastructure/compose"
COMPOSE_FILE="$COMPOSE_DIR/docker-compose.yml"
ENV_FILE="$PROJECT_ROOT/.env.48hr-test"

# Functions
print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                   FKS Test Control                           ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_usage() {
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  status      Show current test status"
    echo "  logs        Follow live logs (Ctrl+C to exit)"
    echo "  health      Run comprehensive health check"
    echo "  optimize    Trigger manual optimization"
    echo "  stop        Stop the test gracefully"
    echo "  report      Generate test report"
    echo "  signals     Show recent trading signals"
    echo "  errors      Show recent errors"
    echo "  memory      Show memory usage"
    echo "  restart     Restart trading services"
    echo "  containers  Show container status"
    echo ""
}

check_compose() {
    if [ ! -f "$COMPOSE_FILE" ]; then
        echo -e "${RED}Error: docker-compose.yml not found${NC}"
        exit 1
    fi
}

get_test_info() {
    if [ -f "$ENV_FILE" ]; then
        source "$ENV_FILE"
        echo -e "${CYAN}Test ID:${NC} ${TEST_ID:-unknown}"
        echo -e "${CYAN}Start Time:${NC} ${TEST_START_TIME:-unknown}"
        echo -e "${CYAN}Duration:${NC} ${TEST_DURATION_HOURS:-unknown} hours"
        echo -e "${CYAN}Assets:${NC} ${OPTIMIZE_ASSETS:-unknown}"
    else
        echo -e "${YELLOW}No active test configuration found${NC}"
    fi
}

cmd_status() {
    print_header
    echo -e "${YELLOW}📊 Test Status${NC}"
    echo ""
    get_test_info
    echo ""

    echo -e "${YELLOW}📦 Container Status:${NC}"
    cd "$COMPOSE_DIR"
    docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || docker ps --filter "name=fks" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    echo ""
    echo -e "${YELLOW}⏱️ Uptime:${NC}"
    docker ps --filter "name=fks" --format "{{.Names}}: {{.RunningFor}}" | head -10

    echo ""
    echo -e "${YELLOW}🔧 Optimizer Status:${NC}"
    docker exec fks_janus /app/janus-optimizer status 2>&1 | head -20 || echo "Could not get optimizer status"
}

cmd_logs() {
    echo -e "${YELLOW}📜 Following logs (Ctrl+C to exit)...${NC}"
    echo ""
    cd "$COMPOSE_DIR"
    # Execution is embedded inside Janus — no separate container
    docker compose logs -f --tail=100 janus 2>/dev/null || docker logs -f --tail=100 fks_janus
}

cmd_health() {
    print_header
    echo -e "${YELLOW}🏥 Health Check${NC}"
    echo ""

    # Container health
    echo -e "${CYAN}Container Health:${NC}"
    # Execution is embedded inside Janus — no separate container to check
    SERVICES="postgres redis questdb janus prometheus"
    for svc in $SERVICES; do
        container="fks_$svc"
        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "running")
            if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
                echo -e "  ${GREEN}✓${NC} $svc: $status"
            else
                echo -e "  ${RED}✗${NC} $svc: $status"
            fi
        else
            echo -e "  ${RED}✗${NC} $svc: not running"
        fi
    done

    echo ""
    echo -e "${CYAN}Memory Usage:${NC}"
    docker stats --no-stream --format "  {{.Name}}: {{.MemUsage}} ({{.MemPerc}})" | grep fks | head -10

    echo ""
    echo -e "${CYAN}CPU Usage:${NC}"
    docker stats --no-stream --format "  {{.Name}}: {{.CPUPerc}}" | grep fks | head -10

    echo ""
    echo -e "${CYAN}Disk Usage:${NC}"
    docker system df 2>/dev/null | head -5

    echo ""
    echo -e "${CYAN}Redis Connection:${NC}"
    docker exec fks_redis redis-cli ping 2>/dev/null && echo -e "  ${GREEN}✓${NC} Redis responding" || echo -e "  ${RED}✗${NC} Redis not responding"

    echo ""
    echo -e "${CYAN}Postgres Connection:${NC}"
    docker exec fks_postgres pg_isready 2>/dev/null && echo -e "  ${GREEN}✓${NC} Postgres ready" || echo -e "  ${RED}✗${NC} Postgres not ready"

    echo ""
    echo -e "${CYAN}Optimizer Status:${NC}"
    docker exec fks_janus /app/janus-optimizer status -A 2>&1 | head -30 || echo "Could not get optimizer status"
}

cmd_optimize() {
    echo -e "${YELLOW}🔧 Triggering manual optimization...${NC}"
    echo ""

    ASSETS="${1:-BTC,ETH,SOL}"
    echo "Assets: $ASSETS"
    echo ""

    docker exec fks_janus /app/janus-optimizer run-once --quick --assets "$ASSETS" 2>&1
}

cmd_stop() {
    echo -e "${YELLOW}🛑 Stopping test...${NC}"
    echo ""

    # Stop log collector if running
    if [ -f "$ENV_FILE" ]; then
        source "$ENV_FILE"
        if [ -n "$TEST_LOG_DIR" ] && [ -f "$PROJECT_ROOT/$TEST_LOG_DIR/log-collector.pid" ]; then
            PID=$(cat "$PROJECT_ROOT/$TEST_LOG_DIR/log-collector.pid")
            kill "$PID" 2>/dev/null || true
            echo "Stopped log collector"
        fi
    fi

    cd "$COMPOSE_DIR"
    docker compose stop janus execution

    echo ""
    echo -e "${GREEN}✓ Test stopped${NC}"
    echo "Infrastructure services (postgres, redis, etc.) are still running."
    echo "To stop everything: docker compose down"
}

cmd_report() {
    print_header
    echo -e "${YELLOW}📊 Test Report${NC}"
    echo ""

    get_test_info
    echo ""

    echo "════════════════════════════════════════════════════════════"
    echo ""

    echo -e "${CYAN}Container Uptime:${NC}"
    docker ps --filter "name=fks" --format "  {{.Names}}: {{.RunningFor}}" | head -10

    echo ""
    echo -e "${CYAN}Memory Usage:${NC}"
    docker stats --no-stream --format "  {{.Name}}: {{.MemUsage}}" | grep fks | head -10

    echo ""
    echo -e "${CYAN}Signal Count (janus logs):${NC}"
    SIGNAL_COUNT=$(docker logs fks_janus 2>&1 | grep -ci "signal" || echo "0")
    echo "  Total signals: $SIGNAL_COUNT"

    echo ""
    echo -e "${CYAN}Error Count:${NC}"
    ERROR_COUNT=$(docker logs fks_janus 2>&1 | grep -ci "error\|panic\|fatal" || echo "0")
    echo "  Total errors: $ERROR_COUNT"

    echo ""
    echo -e "${CYAN}Optimization Runs:${NC}"
    OPT_COUNT=$(docker logs fks_janus 2>&1 | grep -ci "optimization complete\|optimization.*complete" || echo "0")
    echo "  Completed: $OPT_COUNT"

    echo ""
    echo -e "${CYAN}Recent Activity (last 10 lines):${NC}"
    docker logs fks_janus --tail 10 2>&1 | grep -v "^$"

    echo ""
    echo "════════════════════════════════════════════════════════════"
}

cmd_signals() {
    echo -e "${YELLOW}📈 Recent Trading Signals${NC}"
    echo ""
    docker logs fks_janus 2>&1 | grep -i "signal" | tail -50
}

cmd_errors() {
    echo -e "${YELLOW}⚠️ Recent Errors${NC}"
    echo ""
    docker logs fks_janus 2>&1 | grep -iE "error|panic|fatal|failed" | tail -50
    echo ""
    docker logs fks_execution 2>&1 | grep -iE "error|panic|fatal|failed" | tail -20
}

cmd_memory() {
    echo -e "${YELLOW}💾 Memory Usage${NC}"
    echo ""
    docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}" | grep -E "NAME|fks"
}

cmd_restart() {
    echo -e "${YELLOW}🔄 Restarting trading services...${NC}"
    echo ""
    cd "$COMPOSE_DIR"
    docker compose restart janus execution
    echo ""
    echo -e "${GREEN}✓ Services restarted${NC}"
}

cmd_containers() {
    echo -e "${YELLOW}📦 All FKS Containers${NC}"
    echo ""
    docker ps -a --filter "name=fks" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
}

# Main
check_compose

case "${1:-}" in
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    health)
        cmd_health
        ;;
    optimize)
        cmd_optimize "${2:-}"
        ;;
    stop)
        cmd_stop
        ;;
    report)
        cmd_report
        ;;
    signals)
        cmd_signals
        ;;
    errors)
        cmd_errors
        ;;
    memory)
        cmd_memory
        ;;
    restart)
        cmd_restart
        ;;
    containers)
        cmd_containers
        ;;
    help|--help|-h)
        print_header
        print_usage
        ;;
    *)
        print_header
        print_usage
        exit 1
        ;;
esac
