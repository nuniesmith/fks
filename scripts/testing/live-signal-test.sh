#!/bin/bash
# =============================================================================
# FKS Live Signal Test Script
# =============================================================================
# End-to-end validation of the signal generation and persistence pipeline
#
# Tests:
#   1. Service health checks (Janus, Execution, PostgreSQL, Redis, QuestDB)
#   2. Signal generation (Forward module)
#   3. Signal persistence (Backward module)
#   4. Signal → Execution flow (paper trading)
#   5. Metrics collection (CNS module)
#
# Usage:
#   ./scripts/testing/live-signal-test.sh              # Quick test (5 minutes)
#   ./scripts/testing/live-signal-test.sh --duration 30 # 30 minute test
#   ./scripts/testing/live-signal-test.sh --full       # Full test (1 hour)
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
JANUS_URL="${JANUS_URL:-http://localhost:7000}"
# NOTE: Execution is embedded inside Janus (ENABLE_EXECUTION=true, internal localhost:50052).
# Port 8081 is only used if execution runs as a standalone container (legacy).
# If Janus is healthy, execution is available — check Janus health instead.
EXECUTION_URL="${EXECUTION_URL:-http://localhost:8081}"
COMPOSE_FILE="${COMPOSE_FILE:-infrastructure/compose/docker-compose.yml}"
TEST_DURATION_MINUTES="${TEST_DURATION_MINUTES:-5}"
CHECK_INTERVAL_SECONDS=10
LOG_DIR="./logs/live-signal-test"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --duration)
            TEST_DURATION_MINUTES="$2"
            shift 2
            ;;
        --full)
            TEST_DURATION_MINUTES=60
            shift
            ;;
        --quick)
            TEST_DURATION_MINUTES=5
            shift
            ;;
        --help)
            echo "Usage: $0 [--duration MINUTES] [--full] [--quick]"
            echo ""
            echo "Options:"
            echo "  --duration N   Run test for N minutes (default: 5)"
            echo "  --full         Run full 1-hour test"
            echo "  --quick        Run quick 5-minute test"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create log directory
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/test_${TIMESTAMP}.log"
RESULTS_FILE="$LOG_DIR/results_${TIMESTAMP}.json"

# Logging function
log() {
    local level=$1
    shift
    local msg="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    case $level in
        INFO)  echo -e "${BLUE}[INFO]${NC}  $timestamp - $msg" | tee -a "$LOG_FILE" ;;
        OK)    echo -e "${GREEN}[OK]${NC}    $timestamp - $msg" | tee -a "$LOG_FILE" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC}  $timestamp - $msg" | tee -a "$LOG_FILE" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $timestamp - $msg" | tee -a "$LOG_FILE" ;;
        *)     echo "$timestamp - $msg" | tee -a "$LOG_FILE" ;;
    esac
}

# Check if a service is healthy
check_service_health() {
    local name=$1
    local url=$2
    local endpoint="${3:-/health}"

    if curl -sf "${url}${endpoint}" > /dev/null 2>&1; then
        log OK "$name is healthy"
        return 0
    else
        log ERROR "$name health check failed at ${url}${endpoint}"
        return 1
    fi
}

# Get JSON value using jq or grep fallback
get_json_value() {
    local json=$1
    local key=$2

    if command -v jq &> /dev/null; then
        echo "$json" | jq -r ".$key // empty"
    else
        echo "$json" | grep -o "\"$key\":[^,}]*" | cut -d: -f2 | tr -d ' "'
    fi
}

# Initialize counters
declare -A STATS
STATS[health_checks]=0
STATS[health_failures]=0
STATS[signals_start]=0
STATS[signals_end]=0
STATS[signals_persisted_start]=0
STATS[signals_persisted_end]=0
STATS[errors]=0

# =============================================================================
# PHASE 1: Pre-flight Checks
# =============================================================================
phase_preflight() {
    log INFO "═══════════════════════════════════════════════════════════════"
    log INFO "PHASE 1: Pre-flight Checks"
    log INFO "═══════════════════════════════════════════════════════════════"

    # Check Docker is running
    if ! docker info > /dev/null 2>&1; then
        log ERROR "Docker is not running"
        return 1
    fi
    log OK "Docker is running"

    # Check compose file exists
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log ERROR "Docker compose file not found: $COMPOSE_FILE"
        return 1
    fi
    log OK "Compose file found"

    # Check required tools
    for tool in curl docker; do
        if ! command -v $tool &> /dev/null; then
            log ERROR "Required tool not found: $tool"
            return 1
        fi
    done
    log OK "Required tools available"

    return 0
}

# =============================================================================
# PHASE 2: Service Health Checks
# =============================================================================
phase_health_checks() {
    log INFO "═══════════════════════════════════════════════════════════════"
    log INFO "PHASE 2: Service Health Checks"
    log INFO "═══════════════════════════════════════════════════════════════"

    local all_healthy=true

    # Check Janus
    if ! check_service_health "Janus" "$JANUS_URL" "/health"; then
        all_healthy=false
    fi

    # Check Execution
    if ! check_service_health "Execution" "$EXECUTION_URL" "/health"; then
        all_healthy=false
    fi

    # Check container status
    log INFO "Checking container status..."
    local containers=$(docker compose -f "$COMPOSE_FILE" ps --format json 2>/dev/null || docker compose -f "$COMPOSE_FILE" ps 2>/dev/null)

    for service in janus execution postgres redis questdb; do
        if docker compose -f "$COMPOSE_FILE" ps "$service" 2>/dev/null | grep -q "running\|Up"; then
            log OK "Container $service is running"
        else
            log WARN "Container $service may not be running"
        fi
    done

    # Get initial signal counts from /health endpoint
    local health=$(curl -sf "$JANUS_URL/health" 2>/dev/null || echo '{}')

    if command -v jq &> /dev/null; then
        STATS[signals_start]=$(echo "$health" | jq -r '.signals_generated // 0')
        STATS[signals_persisted_start]=$(echo "$health" | jq -r '.signals_persisted // 0')
    else
        STATS[signals_start]=$(get_json_value "$health" "signals_generated" || echo "0")
        STATS[signals_persisted_start]=$(get_json_value "$health" "signals_persisted" || echo "0")
    fi

    log INFO "Initial signals_generated: ${STATS[signals_start]}"
    log INFO "Initial signals_persisted: ${STATS[signals_persisted_start]}"

    if $all_healthy; then
        return 0
    else
        return 1
    fi
}

# =============================================================================
# PHASE 3: Module Status Check
# =============================================================================
phase_module_check() {
    log INFO "═══════════════════════════════════════════════════════════════"
    log INFO "PHASE 3: Module Status Check"
    log INFO "═══════════════════════════════════════════════════════════════"

    # Get module health from Janus /health endpoint (has proper module info)
    local health=$(curl -sf "$JANUS_URL/health" 2>/dev/null || echo '{}')

    log INFO "Janus health response:"
    if command -v jq &> /dev/null; then
        echo "$health" | jq -r '.modules[] | "  \(.name): healthy=\(.healthy) (\(.message // "no message"))"' 2>/dev/null | tee -a "$LOG_FILE" || echo "$health" | head -20 | tee -a "$LOG_FILE"
    else
        echo "$health" | head -20 | tee -a "$LOG_FILE"
    fi

    # Check for enabled modules using jq or grep
    check_module_health() {
        local module=$1
        local label=$2

        if command -v jq &> /dev/null; then
            local is_healthy=$(echo "$health" | jq -r ".modules[] | select(.name==\"$module\") | .healthy" 2>/dev/null)
            local message=$(echo "$health" | jq -r ".modules[] | select(.name==\"$module\") | .message // \"unknown\"" 2>/dev/null)

            if [[ "$is_healthy" == "true" ]]; then
                log OK "$label: HEALTHY ($message)"
                return 0
            elif [[ -z "$is_healthy" || "$is_healthy" == "null" ]]; then
                log WARN "$label: NOT REGISTERED"
                return 1
            else
                log ERROR "$label: UNHEALTHY ($message)"
                return 1
            fi
        else
            # Fallback grep-based check
            if echo "$health" | grep -q "\"name\":\"$module\"" && echo "$health" | grep -q '"healthy":true'; then
                log OK "$label: ENABLED"
                return 0
            else
                log WARN "$label: may be disabled or unhealthy"
                return 1
            fi
        fi
    }

    check_module_health "forward" "Forward module"
    check_module_health "backward" "Backward module (signal persistence)"
    check_module_health "cns" "CNS module (health monitoring)"
    check_module_health "data" "Data module"
    check_module_health "api" "API module"

    return 0
}

# =============================================================================
# PHASE 4: Signal Flow Monitoring
# =============================================================================
phase_signal_monitoring() {
    log INFO "═══════════════════════════════════════════════════════════════"
    log INFO "PHASE 4: Signal Flow Monitoring (${TEST_DURATION_MINUTES} minutes)"
    log INFO "═══════════════════════════════════════════════════════════════"

    local end_time=$(($(date +%s) + TEST_DURATION_MINUTES * 60))
    local iteration=0
    local last_signals=0
    local last_persisted=0

    while [[ $(date +%s) -lt $end_time ]]; do
        iteration=$((iteration + 1))
        local remaining=$(( (end_time - $(date +%s)) / 60 ))

        log INFO "--- Check #$iteration (${remaining}m remaining) ---"

        # Health check
        if curl -sf "$JANUS_URL/health" > /dev/null 2>&1; then
            STATS[health_checks]=$((STATS[health_checks] + 1))

            # Get current counts from /health endpoint
            local health=$(curl -sf "$JANUS_URL/health" 2>/dev/null || echo '{}')
            local current_signals current_persisted uptime

            if command -v jq &> /dev/null; then
                current_signals=$(echo "$health" | jq -r '.signals_generated // 0')
                current_persisted=$(echo "$health" | jq -r '.signals_persisted // 0')
                uptime=$(echo "$health" | jq -r '.uptime_seconds // 0')
            else
                current_signals=$(get_json_value "$health" "signals_generated" || echo "0")
                current_persisted=$(get_json_value "$health" "signals_persisted" || echo "0")
                uptime=$(get_json_value "$health" "uptime_seconds" || echo "0")
            fi

            # Calculate deltas
            local signal_delta=$((current_signals - last_signals))
            local persist_delta=$((current_persisted - last_persisted))

            log INFO "Uptime: ${uptime}s | Signals: $current_signals (+$signal_delta) | Persisted: $current_persisted (+$persist_delta)"

            # Check for signal generation
            if [[ $signal_delta -gt 0 ]]; then
                log OK "Signal generation active: +$signal_delta signals"
            elif [[ $iteration -gt 2 ]]; then
                log WARN "No new signals in last interval"
            fi

            # Check for persistence
            if [[ $persist_delta -gt 0 ]]; then
                log OK "Signal persistence active: +$persist_delta persisted"
            elif [[ $current_signals -gt 0 && $current_persisted -eq 0 && $iteration -gt 3 ]]; then
                log WARN "Signals generated but none persisted - check backward module!"
            fi

            last_signals=$current_signals
            last_persisted=$current_persisted
            STATS[signals_end]=$current_signals
            STATS[signals_persisted_end]=$current_persisted
        else
            STATS[health_failures]=$((STATS[health_failures] + 1))
            log ERROR "Health check failed"
        fi

        # Check execution service
        if curl -sf "$EXECUTION_URL/health" > /dev/null 2>&1; then
            log OK "Execution service healthy"
        else
            log WARN "Execution service health check failed"
        fi

        # Check for signals summary
        local summary=$(curl -sf "$JANUS_URL/api/signals/summary" 2>/dev/null || echo "")
        if [[ -n "$summary" && "$summary" != "null" ]]; then
            log INFO "Signals summary available"
        fi

        sleep $CHECK_INTERVAL_SECONDS
    done

    return 0
}

# =============================================================================
# PHASE 5: Results Summary
# =============================================================================
phase_results() {
    log INFO "═══════════════════════════════════════════════════════════════"
    log INFO "PHASE 5: Test Results Summary"
    log INFO "═══════════════════════════════════════════════════════════════"

    local signals_generated=$((STATS[signals_end] - STATS[signals_start]))
    local signals_persisted=$((STATS[signals_persisted_end] - STATS[signals_persisted_start]))
    local health_success_rate=0

    if [[ ${STATS[health_checks]} -gt 0 ]]; then
        health_success_rate=$(echo "scale=2; (${STATS[health_checks]} - ${STATS[health_failures]}) * 100 / ${STATS[health_checks]}" | bc)
    fi

    echo ""
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                    TEST RESULTS SUMMARY                       ║"
    echo "╠═══════════════════════════════════════════════════════════════╣"
    printf "║ %-30s %30s ║\n" "Test Duration:" "${TEST_DURATION_MINUTES} minutes"
    printf "║ %-30s %30s ║\n" "Health Checks:" "${STATS[health_checks]}"
    printf "║ %-30s %30s ║\n" "Health Failures:" "${STATS[health_failures]}"
    printf "║ %-30s %30s ║\n" "Health Success Rate:" "${health_success_rate}%"
    echo "╠═══════════════════════════════════════════════════════════════╣"
    printf "║ %-30s %30s ║\n" "Signals Generated:" "$signals_generated"
    printf "║ %-30s %30s ║\n" "Signals Persisted:" "$signals_persisted"
    echo "╠═══════════════════════════════════════════════════════════════╣"

    # Determine overall result
    local result="PASSED"
    local result_color=$GREEN

    if [[ ${STATS[health_failures]} -gt 0 ]]; then
        result="DEGRADED"
        result_color=$YELLOW
    fi

    if [[ $signals_generated -eq 0 ]]; then
        result="FAILED"
        result_color=$RED
        echo -e "║ ${RED}WARNING: No signals were generated!${NC}                          ║"
    fi

    if [[ $signals_persisted -eq 0 && $signals_generated -gt 0 ]]; then
        echo -e "║ ${YELLOW}WARNING: Signals generated but NOT persisted!${NC}               ║"
        echo "║ Check: JANUS_ENABLE_BACKWARD=true                             ║"
        result="DEGRADED"
        result_color=$YELLOW
    fi

    echo "╠═══════════════════════════════════════════════════════════════╣"
    printf "║ %-30s " "OVERALL RESULT:"
    echo -e "${result_color}${result}${NC}                                   ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo ""

    # Save results to JSON
    cat > "$RESULTS_FILE" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "duration_minutes": $TEST_DURATION_MINUTES,
    "health_checks": ${STATS[health_checks]},
    "health_failures": ${STATS[health_failures]},
    "health_success_rate": $health_success_rate,
    "signals_generated": $signals_generated,
    "signals_persisted": $signals_persisted,
    "result": "$result"
}
EOF

    log INFO "Results saved to: $RESULTS_FILE"
    log INFO "Full log saved to: $LOG_FILE"

    if [[ "$result" == "PASSED" ]]; then
        return 0
    else
        return 1
    fi
}

# =============================================================================
# Main
# =============================================================================
main() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║           FKS Live Signal Test - End-to-End Validation        ║"
    echo "╠═══════════════════════════════════════════════════════════════╣"
    echo "║ Duration: ${TEST_DURATION_MINUTES} minutes                                              ║"
    echo "║ Janus URL: $JANUS_URL                                  ║"
    echo "║ Execution URL: $EXECUTION_URL                              ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo ""

    log INFO "Starting Live Signal Test at $(date)"
    log INFO "Log file: $LOG_FILE"

    # Run phases
    phase_preflight || { log ERROR "Pre-flight checks failed"; exit 1; }
    phase_health_checks || { log ERROR "Health checks failed"; exit 1; }
    phase_module_check || { log WARN "Module check had warnings"; }
    phase_signal_monitoring || { log ERROR "Signal monitoring failed"; exit 1; }
    phase_results

    exit $?
}

# Run main
main "$@"
