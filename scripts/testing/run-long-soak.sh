#!/usr/bin/env bash
#
# FKS Long-Running Soak Test with Live Feeds
# ==========================================
#
# Runs a comprehensive soak test with:
#   - Live exchange WebSocket feeds (Kraken, Binance, Bybit)
#   - Prometheus metrics endpoint for scraping
#   - Periodic metrics snapshots
#   - Grafana dashboard integration support
#   - Comprehensive summary and analysis
#
# Usage:
#   ./run-long-soak.sh                          # Default 4-hour soak
#   ./run-long-soak.sh --duration 24h           # 24-hour soak
#   ./run-long-soak.sh --duration 4h --live     # Live feeds (not simulated)
#   ./run-long-soak.sh --help                   # Show help
#
# Prerequisites:
#   - Rust toolchain installed
#   - Network connectivity to exchanges (for live mode)
#   - Optional: Prometheus configured to scrape localhost:8080/metrics
#   - Optional: Grafana with execution-metrics dashboard imported
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULTS_BASE="$SCRIPT_DIR/soak-results"

# Defaults
DEFAULT_DURATION="4h"
DEFAULT_SYMBOLS="BTC/USDT,ETH/USDT"
DEFAULT_MIN_SPREAD="0.1"
DEFAULT_METRICS_PORT=8080
DEFAULT_SCRAPE_INTERVAL=60
DEFAULT_ANALYSIS_INTERVAL=30

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ███████╗██╗  ██╗███████╗    ███████╗ ██████╗  █████╗ ██╗  ██╗              ║
║   ██╔════╝██║ ██╔╝██╔════╝    ██╔════╝██╔═══██╗██╔══██╗██║ ██╔╝              ║
║   █████╗  █████╔╝ ███████╗    ███████╗██║   ██║███████║█████╔╝               ║
║   ██╔══╝  ██╔═██╗ ╚════██║    ╚════██║██║   ██║██╔══██║██╔═██╗               ║
║   ██║     ██║  ██╗███████║    ███████║╚██████╔╝██║  ██║██║  ██╗              ║
║   ╚═╝     ╚═╝  ╚═╝╚══════╝    ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝              ║
║                                                                               ║
║   Long-Running Soak Test with Execution Metrics                               ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

log() {
    local level="$1"
    shift
    local msg="$*"
    local ts=$(date '+%Y-%m-%d %H:%M:%S')

    case "$level" in
        INFO)  echo -e "${GREEN}[$ts] [INFO]${NC} $msg" ;;
        WARN)  echo -e "${YELLOW}[$ts] [WARN]${NC} $msg" ;;
        ERROR) echo -e "${RED}[$ts] [ERROR]${NC} $msg" ;;
        DEBUG) [[ "$VERBOSE" == "true" ]] && echo -e "${BLUE}[$ts] [DEBUG]${NC} $msg" ;;
        *)     echo "[$ts] $msg" ;;
    esac

    # Also log to file if LOG_FILE is set
    if [[ -n "${LOG_FILE:-}" ]]; then
        echo "[$ts] [$level] $msg" >> "$LOG_FILE"
    fi
}

parse_duration() {
    local duration="$1"
    local value="${duration%[smhd]}"
    local unit="${duration: -1}"

    case "$unit" in
        s) echo "$value" ;;
        m) echo $((value * 60)) ;;
        h) echo $((value * 3600)) ;;
        d) echo $((value * 86400)) ;;
        *) echo "$duration" ;;  # Assume seconds if no unit
    esac
}

format_duration() {
    local secs=$1
    local days=$((secs / 86400))
    local hours=$(( (secs % 86400) / 3600 ))
    local mins=$(( (secs % 3600) / 60 ))

    if [[ $days -gt 0 ]]; then
        echo "${days}d ${hours}h ${mins}m"
    elif [[ $hours -gt 0 ]]; then
        echo "${hours}h ${mins}m"
    else
        echo "${mins}m"
    fi
}

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

FKS Long-Running Soak Test with Live Feeds and Metrics

Options:
    -d, --duration DURATION     Test duration (e.g., 4h, 24h, 7d) [default: $DEFAULT_DURATION]
    -s, --symbols SYMBOLS       Comma-separated symbols [default: $DEFAULT_SYMBOLS]
    -m, --min-spread PCT        Minimum spread percentage [default: $DEFAULT_MIN_SPREAD]
    -p, --metrics-port PORT     Prometheus metrics port [default: $DEFAULT_METRICS_PORT]
    --scrape-interval SECS      Metrics scrape interval [default: $DEFAULT_SCRAPE_INTERVAL]
    --simulated                 Use simulated data (no network required)
    --live                      Use live exchange feeds (default with credentials)
    -v, --verbose               Enable verbose output
    -h, --help                  Show this help message

Environment Variables:
    KRAKEN_API_KEY              Kraken API key (optional for authenticated feeds)
    KRAKEN_API_SECRET           Kraken API secret (optional)
    KRAKEN_DRY_RUN              Set to "false" for live trading (DANGEROUS!)

Examples:
    # Run 4-hour soak with simulated data (safe, no network)
    $(basename "$0") --duration 4h --simulated

    # Run 24-hour soak with live exchange feeds
    $(basename "$0") --duration 24h --live

    # Run 1-week soak with specific symbols
    $(basename "$0") --duration 7d --symbols BTC/USDT,ETH/USDT,SOL/USDT

Monitoring:
    During the test, you can:

    1. Check metrics endpoint:
       curl http://localhost:8080/metrics

    2. Check health:
       curl http://localhost:8080/health

    3. Configure Prometheus to scrape (prometheus.yml):
       scrape_configs:
         - job_name: 'fks-paper-trading'
           static_configs:
             - targets: ['localhost:8080']
           scrape_interval: 30s

    4. Import Grafana dashboard:
       $PROJECT_ROOT/scripts/monitoring/dashboards/execution-metrics.json
EOF
}

check_prerequisites() {
    log INFO "Checking prerequisites..."

    # Check cargo
    if ! command -v cargo &> /dev/null; then
        log ERROR "Rust/Cargo not found. Please install Rust: https://rustup.rs"
        exit 1
    fi

    # Check curl (for metrics scraping)
    if ! command -v curl &> /dev/null; then
        log WARN "curl not found - metrics scraping disabled"
    fi

    # Check jq (optional, for JSON parsing)
    if ! command -v jq &> /dev/null; then
        log DEBUG "jq not found - JSON pretty-printing disabled"
    fi

    # Check bc (for calculations)
    if ! command -v bc &> /dev/null; then
        log WARN "bc not found - some calculations may be limited"
    fi

    log INFO "Prerequisites check passed"
}

# =============================================================================
# Argument Parsing
# =============================================================================

DURATION="$DEFAULT_DURATION"
SYMBOLS="$DEFAULT_SYMBOLS"
MIN_SPREAD="$DEFAULT_MIN_SPREAD"
METRICS_PORT="$DEFAULT_METRICS_PORT"
SCRAPE_INTERVAL="$DEFAULT_SCRAPE_INTERVAL"
USE_SIMULATED="false"
VERBOSE="false"
DRY_RUN="${KRAKEN_DRY_RUN:-true}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -s|--symbols)
            SYMBOLS="$2"
            shift 2
            ;;
        -m|--min-spread)
            MIN_SPREAD="$2"
            shift 2
            ;;
        -p|--metrics-port)
            METRICS_PORT="$2"
            shift 2
            ;;
        --scrape-interval)
            SCRAPE_INTERVAL="$2"
            shift 2
            ;;
        --simulated)
            USE_SIMULATED="true"
            shift
            ;;
        --live)
            USE_SIMULATED="false"
            shift
            ;;
        -v|--verbose)
            VERBOSE="true"
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# =============================================================================
# Setup
# =============================================================================

DURATION_SECS=$(parse_duration "$DURATION")
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RUN_DIR="$RESULTS_BASE/long-soak-$TIMESTAMP"
METRICS_DIR="$RUN_DIR/metrics"
LOG_FILE="$RUN_DIR/soak-test.log"
SUMMARY_FILE="$RUN_DIR/summary.json"
ANALYSIS_FILE="$RUN_DIR/analysis.txt"
PID_FILE="$RUN_DIR/paper-trading.pid"
METRICS_PID_FILE="$RUN_DIR/metrics-scraper.pid"
METRICS_URL="http://localhost:$METRICS_PORT/metrics"

# Create directories
mkdir -p "$METRICS_DIR"

# =============================================================================
# Display Configuration
# =============================================================================

print_banner

echo -e "${CYAN}Configuration:${NC}"
echo "  Duration:        $(format_duration $DURATION_SECS) ($DURATION_SECS seconds)"
echo "  Symbols:         $SYMBOLS"
echo "  Min Spread:      ${MIN_SPREAD}%"
echo "  Dry Run:         $DRY_RUN"
echo "  Simulated Data:  $USE_SIMULATED"
echo "  Metrics Port:    $METRICS_PORT"
echo "  Metrics URL:     $METRICS_URL"
echo "  Results Dir:     $RUN_DIR"
echo ""

log INFO "Starting FKS Long-Running Soak Test"
log INFO "Duration: $(format_duration $DURATION_SECS)"
log INFO "Results directory: $RUN_DIR"

# =============================================================================
# Prerequisites Check
# =============================================================================

check_prerequisites

# =============================================================================
# Safety Warnings
# =============================================================================

if [[ "$USE_SIMULATED" == "false" ]]; then
    echo ""
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ℹ️  LIVE FEED MODE                                              ║${NC}"
    echo -e "${YELLOW}║                                                                  ║${NC}"
    echo -e "${YELLOW}║  This test will connect to live exchange WebSocket feeds.       ║${NC}"
    echo -e "${YELLOW}║  Ensure you have network connectivity to:                        ║${NC}"
    echo -e "${YELLOW}║    - Kraken WebSocket API                                        ║${NC}"
    echo -e "${YELLOW}║    - Binance WebSocket API                                       ║${NC}"
    echo -e "${YELLOW}║    - Bybit WebSocket API                                         ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    sleep 3
fi

if [[ "$DRY_RUN" != "true" ]]; then
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ⚠️  WARNING: LIVE TRADING MODE ENABLED                          ║${NC}"
    echo -e "${RED}║                                                                  ║${NC}"
    echo -e "${RED}║  KRAKEN_DRY_RUN is NOT set to 'true'.                            ║${NC}"
    echo -e "${RED}║  This could execute REAL trades with REAL money!                 ║${NC}"
    echo -e "${RED}║                                                                  ║${NC}"
    echo -e "${RED}║  Press Ctrl+C within 10 seconds to abort...                      ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    sleep 10
fi

# =============================================================================
# Build
# =============================================================================

log INFO "Building paper_trading example (release mode)..."

cd "$PROJECT_ROOT"

if ! cargo build --release -p fks-execution-service --example paper_trading 2>&1 | tee -a "$LOG_FILE"; then
    log ERROR "Build failed!"
    exit 1
fi

log INFO "Build successful"

# =============================================================================
# Metrics Scraper Background Task
# =============================================================================

scrape_metrics() {
    local iteration=0
    local start_time=$(date +%s)
    local metrics_count=0
    local success_count=0
    local fail_count=0

    log INFO "Metrics scraper started (interval: ${SCRAPE_INTERVAL}s)"

    while true; do
        local elapsed=$(($(date +%s) - start_time))
        if [[ $elapsed -ge $DURATION_SECS ]]; then
            break
        fi

        local ts=$(date +%Y%m%d-%H%M%S)
        local metrics_file="$METRICS_DIR/metrics-$ts.txt"

        if curl -s --connect-timeout 5 --max-time 10 "$METRICS_URL" > "$metrics_file" 2>/dev/null; then
            success_count=$((success_count + 1))
            metrics_count=$((metrics_count + 1))

            if [[ "$VERBOSE" == "true" ]]; then
                # Extract key metrics for display
                local retry_total=$(grep -E '^execution_retry_total' "$metrics_file" 2>/dev/null | awk '{sum+=$2} END {print sum}' || echo 0)
                local arb_opps=$(grep -E '^arbitrage_opportunities_total' "$metrics_file" 2>/dev/null | awk '{print $2}' | head -1 || echo 0)
                log DEBUG "Scraped metrics ($metrics_count): retry_ops=$retry_total arb_opps=$arb_opps"
            fi
        else
            fail_count=$((fail_count + 1))
            [[ "$VERBOSE" == "true" ]] && log DEBUG "Failed to scrape metrics (attempt $fail_count)"
        fi

        iteration=$((iteration + 1))

        # Progress indicator every 10 iterations
        if [[ $((iteration % 10)) -eq 0 ]]; then
            local progress_pct=$((elapsed * 100 / DURATION_SECS))
            local remaining=$((DURATION_SECS - elapsed))
            log INFO "Progress: ${progress_pct}% | Elapsed: $(format_duration $elapsed) | Remaining: $(format_duration $remaining) | Metrics: $metrics_count"
        fi

        sleep "$SCRAPE_INTERVAL"
    done

    log INFO "Metrics scraper finished: $success_count successful, $fail_count failed"
}

# =============================================================================
# Cleanup Handler
# =============================================================================

cleanup() {
    echo ""
    log INFO "Shutting down..."

    # Kill metrics scraper
    if [[ -f "$METRICS_PID_FILE" ]]; then
        local metrics_pid=$(cat "$METRICS_PID_FILE" 2>/dev/null || echo "")
        if [[ -n "$metrics_pid" ]] && kill -0 "$metrics_pid" 2>/dev/null; then
            kill "$metrics_pid" 2>/dev/null || true
            log DEBUG "Stopped metrics scraper (PID: $metrics_pid)"
        fi
        rm -f "$METRICS_PID_FILE"
    fi

    # Kill paper trading process gracefully
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            log INFO "Sending SIGINT to paper trading process (PID: $pid)..."
            kill -SIGINT "$pid" 2>/dev/null || true

            # Wait for graceful shutdown
            local wait_count=0
            while kill -0 "$pid" 2>/dev/null && [[ $wait_count -lt 10 ]]; do
                sleep 1
                wait_count=$((wait_count + 1))
            done

            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                log WARN "Force killing paper trading process..."
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi

    # Generate summary report
    generate_summary

    log INFO "Soak test completed"
    log INFO "Results saved to: $RUN_DIR"

    # Print final analysis
    if [[ -f "$ANALYSIS_FILE" ]]; then
        echo ""
        cat "$ANALYSIS_FILE"
    fi
}

trap cleanup EXIT INT TERM

# =============================================================================
# Summary Generation
# =============================================================================

generate_summary() {
    log INFO "Generating summary report..."

    local end_time=$(date +%s)
    local end_timestamp=$(date -Iseconds)
    local start_timestamp=$(date -d "@$((end_time - DURATION_SECS))" -Iseconds 2>/dev/null || echo "unknown")

    # Count metrics files
    local metrics_count=$(find "$METRICS_DIR" -name "metrics-*.txt" 2>/dev/null | wc -l || echo 0)

    # Get the last metrics file
    local last_metrics=$(ls -t "$METRICS_DIR"/metrics-*.txt 2>/dev/null | head -1 || echo "")

    # Extract key metrics
    local retry_total=0
    local retry_success=0
    local retry_failures=0
    local rate_limit_errors=0
    local network_errors=0
    local arb_opportunities=0
    local arb_actionable=0
    local signal_received=0
    local signal_executed=0
    local best_exec_analyses=0

    if [[ -f "$last_metrics" ]]; then
        retry_total=$(grep -E '^execution_retry_total_operations' "$last_metrics" 2>/dev/null | awk '{sum+=$2} END {print sum+0}' || echo 0)
        retry_success=$(grep -E '^execution_retry_first_try_successes' "$last_metrics" 2>/dev/null | awk '{sum+=$2} END {print sum+0}' || echo 0)
        retry_failures=$(grep -E '^execution_retry_total_failures' "$last_metrics" 2>/dev/null | awk '{sum+=$2} END {print sum+0}' || echo 0)
        rate_limit_errors=$(grep -E '^execution_retry_rate_limit_errors' "$last_metrics" 2>/dev/null | awk '{sum+=$2} END {print sum+0}' || echo 0)
        network_errors=$(grep -E '^execution_retry_network_errors' "$last_metrics" 2>/dev/null | awk '{sum+=$2} END {print sum+0}' || echo 0)
        arb_opportunities=$(grep -E '^arbitrage_opportunities_total ' "$last_metrics" 2>/dev/null | awk '{print $2}' | head -1 || echo 0)
        arb_actionable=$(grep -E '^arbitrage_opportunities_actionable ' "$last_metrics" 2>/dev/null | awk '{print $2}' | head -1 || echo 0)
        signal_received=$(grep -E '^signal_flow_signals_received ' "$last_metrics" 2>/dev/null | awk '{print $2}' | head -1 || echo 0)
        signal_executed=$(grep -E '^signal_flow_signals_executed ' "$last_metrics" 2>/dev/null | awk '{print $2}' | head -1 || echo 0)
        best_exec_analyses=$(grep -E '^best_execution_analyses_total ' "$last_metrics" 2>/dev/null | awk '{print $2}' | head -1 || echo 0)
    fi

    # Calculate success rate
    local success_rate=100
    if [[ "$retry_total" -gt 0 ]] && command -v bc &> /dev/null; then
        success_rate=$(echo "scale=2; ($retry_success / $retry_total) * 100" | bc 2>/dev/null || echo "100")
    fi

    # Generate JSON summary
    cat > "$SUMMARY_FILE" << EOF
{
    "test_info": {
        "start_time": "$start_timestamp",
        "end_time": "$end_timestamp",
        "duration_seconds": $DURATION_SECS,
        "duration_human": "$(format_duration $DURATION_SECS)",
        "symbols": "$(echo "$SYMBOLS" | tr ',' ' ')",
        "dry_run": $DRY_RUN,
        "simulated_data": $USE_SIMULATED,
        "metrics_port": $METRICS_PORT
    },
    "metrics_collection": {
        "scrape_interval_seconds": $SCRAPE_INTERVAL,
        "total_scrapes": $metrics_count,
        "metrics_url": "$METRICS_URL"
    },
    "execution_metrics": {
        "retry_operations_total": $retry_total,
        "retry_first_try_success": $retry_success,
        "retry_failures": $retry_failures,
        "retry_success_rate_pct": $success_rate,
        "rate_limit_errors": $rate_limit_errors,
        "network_errors": $network_errors
    },
    "arbitrage_metrics": {
        "opportunities_total": $arb_opportunities,
        "opportunities_actionable": $arb_actionable
    },
    "signal_flow_metrics": {
        "signals_received": $signal_received,
        "signals_executed": $signal_executed
    },
    "best_execution_metrics": {
        "analyses_total": $best_exec_analyses
    },
    "files": {
        "log_file": "$LOG_FILE",
        "metrics_directory": "$METRICS_DIR",
        "analysis_file": "$ANALYSIS_FILE"
    }
}
EOF

    # Generate human-readable analysis
    cat > "$ANALYSIS_FILE" << EOF
================================================================================
              FKS LONG-RUNNING SOAK TEST ANALYSIS
================================================================================

TEST CONFIGURATION
------------------
Start Time:         $start_timestamp
End Time:           $end_timestamp
Duration:           $(format_duration $DURATION_SECS)
Symbols:            $SYMBOLS
Min Spread:         ${MIN_SPREAD}%
Dry Run Mode:       $DRY_RUN
Simulated Data:     $USE_SIMULATED
Metrics Port:       $METRICS_PORT

METRICS COLLECTION
------------------
Scrape Interval:    ${SCRAPE_INTERVAL}s
Total Scrapes:      $metrics_count
Metrics URL:        $METRICS_URL

EXECUTION METRICS
-----------------
Total Operations:       $retry_total
First-Try Successes:    $retry_success
Total Failures:         $retry_failures
Success Rate:           ${success_rate}%

Error Breakdown:
  Rate Limit Errors:    $rate_limit_errors
  Network Errors:       $network_errors

ARBITRAGE MONITORING
--------------------
Opportunities Detected:     $arb_opportunities
Actionable Opportunities:   $arb_actionable

SIGNAL FLOW
-----------
Signals Received:       $signal_received
Signals Executed:       $signal_executed

BEST-EXECUTION ANALYZER
-----------------------
Total Analyses:         $best_exec_analyses

HEALTH ASSESSMENT
-----------------
EOF

    # Health assessment logic
    if [[ "$retry_total" -eq 0 ]]; then
        echo "⚠️  No retry operations recorded" >> "$ANALYSIS_FILE"
        echo "    - Check if execution was active during the test" >> "$ANALYSIS_FILE"
        echo "    - Verify exchange connections were successful" >> "$ANALYSIS_FILE"
    elif command -v bc &> /dev/null; then
        if (( $(echo "$success_rate > 95" | bc -l 2>/dev/null || echo 1) )); then
            echo "✅ Retry Success Rate: EXCELLENT (${success_rate}%)" >> "$ANALYSIS_FILE"
        elif (( $(echo "$success_rate > 80" | bc -l 2>/dev/null || echo 1) )); then
            echo "⚠️  Retry Success Rate: FAIR (${success_rate}%)" >> "$ANALYSIS_FILE"
        else
            echo "❌ Retry Success Rate: POOR (${success_rate}%)" >> "$ANALYSIS_FILE"
        fi
    else
        echo "ℹ️  Retry Success Rate: ${success_rate}% (install bc for evaluation)" >> "$ANALYSIS_FILE"
    fi

    if [[ "$rate_limit_errors" -gt 0 ]]; then
        echo "⚠️  Rate Limit Errors: $rate_limit_errors (consider adjusting request frequency)" >> "$ANALYSIS_FILE"
    else
        echo "✅ Rate Limit Errors: None detected" >> "$ANALYSIS_FILE"
    fi

    if [[ "$network_errors" -gt 0 ]]; then
        echo "⚠️  Network Errors: $network_errors (check connectivity)" >> "$ANALYSIS_FILE"
    else
        echo "✅ Network Errors: None detected" >> "$ANALYSIS_FILE"
    fi

    if [[ "$arb_opportunities" -gt 0 ]]; then
        echo "✅ Arbitrage Monitoring: ACTIVE ($arb_opportunities opportunities)" >> "$ANALYSIS_FILE"
    else
        echo "ℹ️  Arbitrage Monitoring: No opportunities detected (normal for tight spreads)" >> "$ANALYSIS_FILE"
    fi

    if [[ "$best_exec_analyses" -gt 0 ]]; then
        echo "✅ Best-Execution Analyzer: ACTIVE ($best_exec_analyses analyses)" >> "$ANALYSIS_FILE"
    else
        echo "⚠️  Best-Execution Analyzer: No analyses recorded" >> "$ANALYSIS_FILE"
    fi

    cat >> "$ANALYSIS_FILE" << EOF

RECOMMENDATIONS
---------------
EOF

    if [[ "$retry_total" -eq 0 ]]; then
        cat >> "$ANALYSIS_FILE" << EOF
- Verify that the paper trading example connected to exchanges
- Check network connectivity and firewall rules
- If using simulated mode, verify USE_SIMULATED_DATA=true was set
EOF
    fi

    if [[ "$rate_limit_errors" -gt 10 ]]; then
        cat >> "$ANALYSIS_FILE" << EOF
- Consider reducing request frequency
- Review rate limiter configuration
- Check if API key has enhanced rate limits
EOF
    fi

    if command -v bc &> /dev/null && (( $(echo "$success_rate < 80" | bc -l 2>/dev/null || echo 0) )); then
        cat >> "$ANALYSIS_FILE" << EOF
- Investigate retry failures in logs
- Review circuit breaker state
- Consider adjusting backoff parameters
EOF
    fi

    cat >> "$ANALYSIS_FILE" << EOF

FILES
-----
Log File:           $LOG_FILE
Metrics Directory:  $METRICS_DIR
Summary JSON:       $SUMMARY_FILE

NEXT STEPS
----------
1. Review metrics snapshots in: $METRICS_DIR
2. Import Grafana dashboard for visualization:
   $PROJECT_ROOT/scripts/monitoring/dashboards/execution-metrics.json
3. Check Prometheus alerting rules:
   $PROJECT_ROOT/scripts/monitoring/alerting/execution-alerts.yaml

================================================================================
EOF

    log INFO "Summary written to $SUMMARY_FILE"
    log INFO "Analysis written to $ANALYSIS_FILE"
}

# =============================================================================
# Main Execution
# =============================================================================

# Start metrics scraper in background
log INFO "Starting metrics scraper..."
scrape_metrics &
echo $! > "$METRICS_PID_FILE"

# Build environment for paper trading
export KRAKEN_DRY_RUN="$DRY_RUN"
export USE_SIMULATED_DATA="$USE_SIMULATED"
export PAPER_TRADING_SYMBOLS="$SYMBOLS"
export PAPER_TRADING_DURATION_SECS="$DURATION_SECS"
export MIN_SPREAD_PCT="$MIN_SPREAD"
export METRICS_PORT="$METRICS_PORT"
export RUST_LOG="${RUST_LOG:-info,janus=info,janus_execution=info}"

log INFO "Starting paper trading example..."
log INFO "Metrics endpoint: http://localhost:$METRICS_PORT/metrics"
log INFO "Health endpoint:  http://localhost:$METRICS_PORT/health"

# Run paper trading
cd "$PROJECT_ROOT/src/execution"

# Use timeout to limit duration
timeout --signal=INT "$DURATION_SECS" \
    "$PROJECT_ROOT/target/release/examples/paper_trading" 2>&1 | tee -a "$LOG_FILE" &

PAPER_PID=$!
echo $PAPER_PID > "$PID_FILE"

log INFO "Paper trading started (PID: $PAPER_PID)"
log INFO "Test will run for $(format_duration $DURATION_SECS)"
log INFO "Press Ctrl+C to stop early"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Soak test running...                                                  ${NC}"
echo -e "${GREEN}  Monitor progress with: tail -f $LOG_FILE${NC}"
echo -e "${GREEN}  Check metrics with:    curl http://localhost:$METRICS_PORT/metrics${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""

# Wait for paper trading to complete
wait $PAPER_PID || true

log INFO "Paper trading process completed"

# Cleanup will be called by trap
