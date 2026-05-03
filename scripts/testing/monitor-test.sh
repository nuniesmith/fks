#!/bin/bash
# ============================================================================
# FKS Trading System - Test Monitoring Script
# ============================================================================
# This script provides real-time monitoring and validation for the integration
# test, checking service health, signal flow, and system metrics.
#
# Usage:
#   ./monitor-test.sh [command]
#
# Commands:
#   status      - Show current system status (default)
#   health      - Check all service health endpoints
#   signals     - Show recent signals from QuestDB
#   orders      - Show recent orders from QuestDB
#   positions   - Show current positions
#   metrics     - Show key performance metrics
#   logs        - Follow service logs
#   stats       - Show comprehensive statistics
#   validate    - Run validation checks
#
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

COMMAND="${1:-status}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ============================================================================
# Service Health Checks
# ============================================================================

check_health() {
    log_section "Service Health Checks"

    cd "$PROJECT_DIR"

    # Check Docker services
    echo -e "\n${CYAN}Docker Services:${NC}"
    docker compose ps

    echo -e "\n${CYAN}Health Endpoints:${NC}"

    # Forward service
    if curl -sf http://localhost:8080/api/v1/health > /dev/null 2>&1; then
        log_success "Forward Service (REST) - http://localhost:8080"
    else
        log_error "Forward Service (REST) - UNHEALTHY"
    fi

    # Execution service (embedded inside Janus via ENABLE_EXECUTION=true)
    if curl -sf http://localhost:8081/health > /dev/null 2>&1; then
        log_success "Execution Service - http://localhost:8081 (standalone)"
        echo -e "  Response: $(curl -s http://localhost:8081/health | jq -r '.status // .message // .' 2>/dev/null || echo 'OK')"
    elif docker exec fks_janus printenv ENABLE_EXECUTION 2>/dev/null | grep -q "true"; then
        log_success "Execution Service - embedded in Janus (ENABLE_EXECUTION=true)"
        EXEC_MODE=$(docker exec fks_janus printenv EXECUTION_MODE 2>/dev/null || echo "unknown")
        echo -e "  EXECUTION_MODE: $EXEC_MODE"
    else
        log_error "Execution Service - UNAVAILABLE (not standalone, not enabled in Janus)"
    fi

    # QuestDB
    if curl -sf http://localhost:9000 > /dev/null 2>&1; then
        log_success "QuestDB - http://localhost:9000"
    else
        log_error "QuestDB - UNHEALTHY"
    fi

    # Redis
    if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        log_success "Redis - localhost:6379"
    else
        log_error "Redis - UNHEALTHY"
    fi

    # Prometheus
    if curl -sf http://localhost:9090/-/healthy > /dev/null 2>&1; then
        log_success "Prometheus - http://localhost:9090"
    else
        log_warning "Prometheus - Not running or unhealthy"
    fi

    # Grafana
    if curl -sf http://localhost:3000/api/health > /dev/null 2>&1; then
        log_success "Grafana - http://localhost:3000"
    else
        log_warning "Grafana - Not running or unhealthy"
    fi
}

# ============================================================================
# Data Queries
# ============================================================================

query_questdb() {
    local query="$1"
    curl -G --data-urlencode "query=$query" http://localhost:9000/exec 2>/dev/null | jq -r '.dataset // empty' 2>/dev/null
}

show_signals() {
    log_section "Recent Trading Signals"

    local query="SELECT timestamp, signal_id, symbol, signal_type, confidence, strength, executed FROM signals ORDER BY timestamp DESC LIMIT 20;"

    echo -e "\n${CYAN}Last 20 Signals:${NC}"
    local result=$(query_questdb "$query")

    if [ -n "$result" ]; then
        echo "$result" | jq -r '.[] | "\(.timestamp) | \(.symbol) | \(.signal_type) | Conf: \(.confidence) | Strength: \(.strength) | Exec: \(.executed)"' 2>/dev/null || echo "$result"
    else
        log_warning "No signals found or QuestDB not responding"
        log_info "Make sure data is being ingested: docker compose logs data"
    fi

    # Summary
    local count_query="SELECT COUNT(*) as total FROM signals WHERE timestamp > dateadd('h', -1, now());"
    local count=$(query_questdb "$count_query" | jq -r '.[0].total // 0' 2>/dev/null)
    echo -e "\n${CYAN}Signals in last hour:${NC} $count"
}

show_orders() {
    log_section "Recent Orders"

    local query="SELECT created_at, order_id, symbol, side, quantity, status, filled_quantity FROM orders ORDER BY created_at DESC LIMIT 20;"

    echo -e "\n${CYAN}Last 20 Orders:${NC}"
    local result=$(query_questdb "$query")

    if [ -n "$result" ]; then
        echo "$result" | jq -r '.[] | "\(.created_at) | \(.symbol) | \(.side) | Qty: \(.quantity) | Status: \(.status)"' 2>/dev/null || echo "$result"
    else
        log_warning "No orders found"
        log_info "Orders will appear once signals are executed"
    fi

    # Summary
    local count_query="SELECT COUNT(*) as total, COUNT_IF(status='FILLED') as filled FROM orders WHERE created_at > dateadd('h', -1, now());"
    local result=$(query_questdb "$count_query")
    if [ -n "$result" ]; then
        local total=$(echo "$result" | jq -r '.[0].total // 0' 2>/dev/null)
        local filled=$(echo "$result" | jq -r '.[0].filled // 0' 2>/dev/null)
        echo -e "\n${CYAN}Orders in last hour:${NC} $total (Filled: $filled)"
    fi
}

show_positions() {
    log_section "Current Positions"

    local query="SELECT symbol, side, quantity, average_entry_price, unrealized_pnl, realized_pnl FROM positions WHERE closed_at IS NULL ORDER BY opened_at DESC;"

    echo -e "\n${CYAN}Open Positions:${NC}"
    local result=$(query_questdb "$query")

    if [ -n "$result" ]; then
        echo "$result" | jq -r '.[] | "\(.symbol) | \(.side) | Qty: \(.quantity) | Entry: \(.average_entry_price) | PnL: \(.unrealized_pnl)"' 2>/dev/null || echo "$result"
    else
        log_info "No open positions"
    fi
}

show_metrics() {
    log_section "System Metrics"

    echo -e "\n${CYAN}Signal Statistics (Last 24 Hours):${NC}"
    local signal_query="SELECT COUNT(*) as total_signals, AVG(confidence) as avg_confidence, AVG(strength) as avg_strength FROM signals WHERE timestamp > dateadd('h', -24, now());"
    local signal_result=$(query_questdb "$signal_query")
    if [ -n "$signal_result" ]; then
        echo "$signal_result" | jq -r '.[0] | "  Total Signals: \(.total_signals)\n  Avg Confidence: \(.avg_confidence)\n  Avg Strength: \(.avg_strength)"' 2>/dev/null || echo "$signal_result"
    fi

    echo -e "\n${CYAN}Order Statistics (Last 24 Hours):${NC}"
    local order_query="SELECT COUNT(*) as total_orders, COUNT_IF(status='FILLED') as filled_orders, AVG(fill_time_ms) as avg_fill_time FROM orders WHERE created_at > dateadd('h', -24, now());"
    local order_result=$(query_questdb "$order_query")
    if [ -n "$order_result" ]; then
        echo "$order_result" | jq -r '.[0] | "  Total Orders: \(.total_orders)\n  Filled Orders: \(.filled_orders)\n  Avg Fill Time: \(.avg_fill_time)ms"' 2>/dev/null || echo "$order_result"
    fi

    echo -e "\n${CYAN}P&L Summary (All Time):${NC}"
    local pnl_query="SELECT symbol, COUNT(*) as trades, SUM(realized_pnl) as total_pnl, AVG(realized_pnl) as avg_pnl FROM positions WHERE closed_at IS NOT NULL GROUP BY symbol;"
    local pnl_result=$(query_questdb "$pnl_query")
    if [ -n "$pnl_result" ]; then
        echo "$pnl_result" | jq -r '.[] | "  \(.symbol): \(.trades) trades, Total PnL: $\(.total_pnl), Avg: $\(.avg_pnl)"' 2>/dev/null || echo "$pnl_result"
    else
        log_info "No closed positions yet"
    fi

    echo -e "\n${CYAN}Docker Resource Usage:${NC}"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" fks_janus fks_ruby 2>/dev/null || log_warning "Could not get Docker stats"
}

show_stats() {
    check_health
    show_signals
    show_orders
    show_positions
    show_metrics
}

# ============================================================================
# Validation
# ============================================================================

validate_test() {
    log_section "Test Validation"

    local errors=0
    local warnings=0

    echo -e "\n${CYAN}Checking Integration Flow:${NC}"

    # Check if forward service is connected to execution
    if docker compose logs forward | grep -q "Execution client connected"; then
        log_success "Forward service connected to execution service"
    else
        log_error "Forward service not connected to execution service"
        ((errors++))
    fi

    # Check if signals are being generated
    local signal_count=$(query_questdb "SELECT COUNT(*) as count FROM signals WHERE timestamp > dateadd('m', -10, now());" | jq -r '.[0].count // 0' 2>/dev/null)
    if [ "$signal_count" -gt 0 ]; then
        log_success "Signals being generated ($signal_count in last 10 minutes)"
    else
        log_warning "No signals generated in last 10 minutes"
        ((warnings++))
    fi

    # Check if orders are being created
    local order_count=$(query_questdb "SELECT COUNT(*) as count FROM orders WHERE created_at > dateadd('m', -10, now());" | jq -r '.[0].count // 0' 2>/dev/null)
    if [ "$order_count" -gt 0 ]; then
        log_success "Orders being created ($order_count in last 10 minutes)"
    else
        log_warning "No orders created in last 10 minutes"
        ((warnings++))
    fi

    # Check for errors in logs
    echo -e "\n${CYAN}Checking for Errors:${NC}"
    if docker compose logs --tail=100 forward execution | grep -i "error" | grep -v "error=nil" | grep -v "errors=0" > /dev/null 2>&1; then
        log_warning "Errors found in logs (check with: docker compose logs forward execution | grep -i error)"
        ((warnings++))
    else
        log_success "No errors in recent logs"
    fi

    # Check memory usage
    echo -e "\n${CYAN}Resource Health:${NC}"
    local mem_usage=$(docker stats --no-stream --format "{{.MemPerc}}" fks_forward 2>/dev/null | sed 's/%//')
    if [ -n "$mem_usage" ] && (( $(echo "$mem_usage > 80" | bc -l) )); then
        log_warning "Forward service memory usage high: ${mem_usage}%"
        ((warnings++))
    else
        log_success "Memory usage normal"
    fi

    # Summary
    echo -e "\n${CYAN}Validation Summary:${NC}"
    if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
        log_success "All checks passed!"
    elif [ $errors -eq 0 ]; then
        log_warning "$warnings warning(s) found"
    else
        log_error "$errors error(s) and $warnings warning(s) found"
    fi
}

# ============================================================================
# Logs
# ============================================================================

show_logs() {
    log_section "Following Service Logs"
    echo ""
    log_info "Showing logs for forward, execution, and data services"
    log_info "Press Ctrl+C to stop"
    echo ""

    cd "$PROJECT_DIR"
    docker compose logs -f --tail=100 forward execution data
}

# ============================================================================
# Status Overview
# ============================================================================

show_status() {
    log_section "System Status Overview"

    cd "$PROJECT_DIR"

    echo -e "\n${CYAN}Services:${NC}"
    docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"

    echo -e "\n${CYAN}Quick Metrics:${NC}"

    # Signal count
    local signals=$(query_questdb "SELECT COUNT(*) as count FROM signals WHERE timestamp > dateadd('h', -1, now());" | jq -r '.[0].count // 0' 2>/dev/null)
    echo -e "  Signals (1h):     $signals"

    # Order count
    local orders=$(query_questdb "SELECT COUNT(*) as count FROM orders WHERE created_at > dateadd('h', -1, now());" | jq -r '.[0].count // 0' 2>/dev/null)
    echo -e "  Orders (1h):      $orders"

    # Open positions
    local positions=$(query_questdb "SELECT COUNT(*) as count FROM positions WHERE closed_at IS NULL;" | jq -r '.[0].count // 0' 2>/dev/null)
    echo -e "  Open Positions:   $positions"

    echo -e "\n${CYAN}Health Status:${NC}"

    # Quick health checks
    if curl -sf http://localhost:8080/api/v1/health > /dev/null 2>&1; then
        echo -e "  Forward:   ${GREEN}✓${NC} Healthy"
    else
        echo -e "  Forward:   ${RED}✗${NC} Unhealthy"
    fi

    if curl -sf http://localhost:8081/health > /dev/null 2>&1; then
        echo -e "  Execution: ${GREEN}✓${NC} Healthy (standalone)"
    elif docker exec fks_janus printenv ENABLE_EXECUTION 2>/dev/null | grep -q "true"; then
        echo -e "  Execution: ${GREEN}✓${NC} Embedded in Janus (ENABLE_EXECUTION=true)"
    else
        echo -e "  Execution: ${RED}✗${NC} Unavailable"
    fi

    echo -e "\n${CYAN}Test Duration:${NC}"
    local start_time=$(docker compose ps janus --format json 2>/dev/null | jq -r '.[0].RunningFor // "Unknown"')
    echo -e "  Running for: $start_time"

    echo -e "\n${CYAN}Quick Commands:${NC}"
    echo -e "  Health:      ./monitor-test.sh health"
    echo -e "  Signals:     ./monitor-test.sh signals"
    echo -e "  Orders:      ./monitor-test.sh orders"
    echo -e "  Metrics:     ./monitor-test.sh metrics"
    echo -e "  Validate:    ./monitor-test.sh validate"
    echo -e "  Logs:        ./monitor-test.sh logs"
}

# ============================================================================
# Main
# ============================================================================

main() {
    case "$COMMAND" in
        status)
            show_status
            ;;
        health)
            check_health
            ;;
        signals)
            show_signals
            ;;
        orders)
            show_orders
            ;;
        positions)
            show_positions
            ;;
        metrics)
            show_metrics
            ;;
        logs)
            show_logs
            ;;
        stats)
            show_stats
            ;;
        validate)
            validate_test
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            echo ""
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  status      - Show current system status (default)"
            echo "  health      - Check all service health endpoints"
            echo "  signals     - Show recent signals from QuestDB"
            echo "  orders      - Show recent orders from QuestDB"
            echo "  positions   - Show current positions"
            echo "  metrics     - Show key performance metrics"
            echo "  logs        - Follow service logs"
            echo "  stats       - Show comprehensive statistics"
            echo "  validate    - Run validation checks"
            exit 1
            ;;
    esac
}

main
