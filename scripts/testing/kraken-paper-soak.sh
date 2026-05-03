#!/usr/bin/env bash
#
# Kraken Paper Trading Soak Test
# ==============================
#
# Runs the FKS paper trading example against Kraken live feeds in dry-run mode,
# with Prometheus metrics scraping for monitoring execution behavior.
#
# Features:
#   - Kraken live WebSocket feeds (no real trading)
#   - Configurable duration (default: 4 hours)
#   - Automatic metrics scraping to file
#   - Graceful shutdown with summary
#   - Log file rotation
#
# Usage:
#   ./kraken-paper-soak.sh                      # Default 4-hour soak
#   ./kraken-paper-soak.sh --duration 24h       # 24-hour soak
#   ./kraken-paper-soak.sh --symbols BTC,ETH    # Custom symbols
#   ./kraken-paper-soak.sh --metrics-url http://localhost:8080/metrics
#
# Environment Variables:
#   KRAKEN_API_KEY      - Kraken API key (optional, for authenticated feeds)
#   KRAKEN_API_SECRET   - Kraken API secret (optional)
#   KRAKEN_DRY_RUN      - Set to "false" to enable live trading (DANGEROUS)
#   METRICS_URL         - Prometheus metrics endpoint
#   SCRAPE_INTERVAL     - Metrics scrape interval in seconds (default: 60)
#
# Output:
#   ./soak-results/kraken-soak-YYYYMMDD-HHMMSS/
#     ├── paper-trading.log      # Main application log
#     ├── metrics/                # Timestamped metrics snapshots
#     │   ├── metrics-HHMMSS.txt
#     │   └── ...
#     ├── summary.json           # Final summary report
#     └── analysis.txt           # Human-readable analysis
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
DEFAULT_METRICS_URL="http://localhost:8080/metrics"
DEFAULT_SCRAPE_INTERVAL=60
DEFAULT_ANALYSIS_INTERVAL=30

# Parse duration to seconds
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

# =============================================================================
# Argument Parsing
# =============================================================================

DURATION="$DEFAULT_DURATION"
SYMBOLS="$DEFAULT_SYMBOLS"
MIN_SPREAD="$DEFAULT_MIN_SPREAD"
METRICS_URL="${METRICS_URL:-$DEFAULT_METRICS_URL}"
SCRAPE_INTERVAL="${SCRAPE_INTERVAL:-$DEFAULT_SCRAPE_INTERVAL}"
ANALYSIS_INTERVAL="${ANALYSIS_INTERVAL:-$DEFAULT_ANALYSIS_INTERVAL}"
DRY_RUN="${KRAKEN_DRY_RUN:-true}"
USE_SIMULATED="${USE_SIMULATED_DATA:-false}"
VERBOSE=false

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Kraken Paper Trading Soak Test

Options:
    -d, --duration DURATION     Test duration (e.g., 4h, 24h, 7d) [default: $DEFAULT_DURATION]
    -s, --symbols SYMBOLS       Comma-separated symbols [default: $DEFAULT_SYMBOLS]
    -m, --min-spread PCT        Minimum spread percentage [default: $DEFAULT_MIN_SPREAD]
    --metrics-url URL           Prometheus metrics URL [default: $DEFAULT_METRICS_URL]
    --scrape-interval SECS      Metrics scrape interval [default: $DEFAULT_SCRAPE_INTERVAL]
    --simulated                 Use simulated data instead of live feeds
    --live                      DANGER: Disable dry-run mode
    -v, --verbose               Enable verbose output
    -h, --help                  Show this help message

Environment Variables:
    KRAKEN_API_KEY              Kraken API key (for authenticated feeds)
    KRAKEN_API_SECRET           Kraken API secret
    KRAKEN_DRY_RUN              Set to "false" for live trading
    METRICS_URL                 Override metrics endpoint
    SCRAPE_INTERVAL             Metrics scrape interval

Examples:
    # Run 4-hour soak with default settings
    $(basename "$0")

    # Run 24-hour soak with specific symbols
    $(basename "$0") --duration 24h --symbols BTC,ETH,SOL

    # Run quick 30-minute test with verbose output
    $(basename "$0") --duration 30m --verbose
EOF
}

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
        --metrics-url)
            METRICS_URL="$2"
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
            DRY_RUN="false"
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
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
RUN_DIR="$RESULTS_BASE/kraken-soak-$TIMESTAMP"
METRICS_DIR="$RUN_DIR/metrics"
LOG_FILE="$RUN_DIR/paper-trading.log"
SUMMARY_FILE="$RUN_DIR/summary.json"
ANALYSIS_FILE="$RUN_DIR/analysis.txt"
PID_FILE="$RUN_DIR/paper-trading.pid"
METRICS_PID_FILE="$RUN_DIR/metrics-scraper.pid"

# Create directories
mkdir -p "$METRICS_DIR"

# Logging functions
log() {
    local level="$1"
    shift
    local msg="$*"
    local ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$ts] [$level] $msg" | tee -a "$LOG_FILE"
}

log_info() { log "INFO" "$@"; }
log_warn() { log "WARN" "$@"; }
log_error() { log "ERROR" "$@"; }

# =============================================================================
# Safety Check
# =============================================================================

if [[ "$DRY_RUN" != "true" ]]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║  ⚠️  WARNING: LIVE TRADING MODE ENABLED                          ║"
    echo "║                                                                  ║"
    echo "║  KRAKEN_DRY_RUN is set to 'false'.                               ║"
    echo "║  This will execute REAL trades with REAL money!                  ║"
    echo "║                                                                  ║"
    echo "║  Press Ctrl+C within 10 seconds to abort...                      ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
    sleep 10
fi

# =============================================================================
# Banner
# =============================================================================

cat << EOF

╔══════════════════════════════════════════════════════════════════════════════╗
║                    Kraken Paper Trading Soak Test                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Duration:        $(printf "%-55s" "$DURATION ($DURATION_SECS seconds)")    ║
║  Symbols:         $(printf "%-55s" "$SYMBOLS")    ║
║  Min Spread:      $(printf "%-55s" "${MIN_SPREAD}%")    ║
║  Dry Run:         $(printf "%-55s" "$DRY_RUN")    ║
║  Simulated Data:  $(printf "%-55s" "$USE_SIMULATED")    ║
║  Metrics URL:     $(printf "%-55s" "$METRICS_URL")    ║
║  Results Dir:     $(printf "%-55s" "$RUN_DIR")    ║
╚══════════════════════════════════════════════════════════════════════════════╝

EOF

log_info "Starting Kraken Paper Trading Soak Test"
log_info "Duration: $DURATION ($DURATION_SECS seconds)"
log_info "Symbols: $SYMBOLS"
log_info "Results directory: $RUN_DIR"

# =============================================================================
# Build
# =============================================================================

log_info "Building paper_trading example..."

cd "$PROJECT_ROOT"

if ! cargo build --release -p fks-execution-service --example paper_trading 2>&1 | tee -a "$LOG_FILE"; then
    log_error "Build failed!"
    exit 1
fi

log_info "Build successful"

# =============================================================================
# Metrics Scraper
# =============================================================================

scrape_metrics() {
    local iteration=0
    local start_time=$(date +%s)
    local consecutive_failures=0
    local max_consecutive_failures=5

    # Wait for metrics server to be ready (up to 30 seconds)
    log_info "Waiting for metrics server to be ready..."
    local wait_start=$(date +%s)
    local max_wait=30
    while true; do
        if curl -s --connect-timeout 2 "$METRICS_URL" > /dev/null 2>&1; then
            log_info "Metrics server is ready"
            break
        fi
        local waited=$(($(date +%s) - wait_start))
        if [[ $waited -ge $max_wait ]]; then
            log_warn "Metrics server not ready after ${max_wait}s, starting scraper anyway"
            break
        fi
        sleep 1
    done

    while true; do
        local elapsed=$(($(date +%s) - start_time))
        if [[ $elapsed -ge $DURATION_SECS ]]; then
            break
        fi

        local ts=$(date +%H%M%S)
        local metrics_file="$METRICS_DIR/metrics-$ts.txt"
        local temp_file=$(mktemp)

        # Scrape to temp file first, then validate
        if curl -s --connect-timeout 5 --max-time 10 "$METRICS_URL" > "$temp_file" 2>/dev/null; then
            # Check if we got actual content (not empty)
            if [[ -s "$temp_file" ]] && grep -q "^# HELP\|^# TYPE\|^[a-z]" "$temp_file" 2>/dev/null; then
                mv "$temp_file" "$metrics_file"
                consecutive_failures=0
                if [[ "$VERBOSE" == "true" ]]; then
                    local line_count=$(wc -l < "$metrics_file")
                    log_info "Scraped metrics to $metrics_file ($line_count lines)"
                fi
            else
                rm -f "$temp_file"
                consecutive_failures=$((consecutive_failures + 1))
                log_warn "Metrics response was empty or invalid (attempt $consecutive_failures)"
            fi
        else
            rm -f "$temp_file"
            consecutive_failures=$((consecutive_failures + 1))
            log_warn "Failed to scrape metrics from $METRICS_URL (attempt $consecutive_failures)"
        fi

        # Alert if too many consecutive failures
        if [[ $consecutive_failures -ge $max_consecutive_failures ]]; then
            log_error "Metrics scraper: $max_consecutive_failures consecutive failures - metrics server may be down"
            consecutive_failures=0  # Reset to avoid spamming
        fi

        iteration=$((iteration + 1))
        sleep "$SCRAPE_INTERVAL"
    done

    log_info "Metrics scraper completed ($iteration iterations)"
}

# =============================================================================
# Cleanup Handler
# =============================================================================

cleanup() {
    log_info "Shutting down..."

    # Kill metrics scraper
    if [[ -f "$METRICS_PID_FILE" ]]; then
        local metrics_pid=$(cat "$METRICS_PID_FILE")
        if kill -0 "$metrics_pid" 2>/dev/null; then
            kill "$metrics_pid" 2>/dev/null || true
        fi
        rm -f "$METRICS_PID_FILE"
    fi

    # Kill paper trading process
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill -SIGINT "$pid" 2>/dev/null || true
            # Wait for graceful shutdown
            sleep 5
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi

    # Generate summary
    generate_summary

    log_info "Soak test completed"
    log_info "Results saved to: $RUN_DIR"
}

trap cleanup EXIT INT TERM

# =============================================================================
# Summary Generation
# =============================================================================

generate_summary() {
    log_info "Generating summary report..."

    local end_time=$(date +%s)
    local end_timestamp=$(date -Iseconds)

    # Count metrics files
    local metrics_count=$(find "$METRICS_DIR" -name "metrics-*.txt" 2>/dev/null | wc -l)

    # Extract key metrics from the last metrics file
    local last_metrics=$(ls -t "$METRICS_DIR"/metrics-*.txt 2>/dev/null | head -1)

    local retry_total=0
    local retry_success=0
    local arb_opportunities=0
    local signal_received=0
    local signal_executed=0
    local best_exec_analyses=0

    if [[ -f "$last_metrics" ]]; then
        retry_total=$(grep -E '^execution_retry_total' "$last_metrics" | awk '{sum+=$2} END {print sum}' || echo 0)
        retry_success=$(grep -E '^execution_retry_success.*first_try' "$last_metrics" | awk '{sum+=$2} END {print sum}' || echo 0)
        arb_opportunities=$(grep -E '^arbitrage_opportunities_total' "$last_metrics" | awk '{print $2}' | head -1 || echo 0)
        signal_received=$(grep -E '^signal_flow_signals_received' "$last_metrics" | awk '{print $2}' | head -1 || echo 0)
        signal_executed=$(grep -E '^signal_flow_signals_executed' "$last_metrics" | awk '{print $2}' | head -1 || echo 0)
        best_exec_analyses=$(grep -E '^best_execution_analyses_total' "$last_metrics" | awk '{print $2}' | head -1 || echo 0)
    fi

    # Calculate success rate
    local success_rate=100
    if [[ "$retry_total" -gt 0 ]]; then
        success_rate=$(echo "scale=2; ($retry_success / $retry_total) * 100" | bc 2>/dev/null || echo "100")
    fi

    # Generate JSON summary
    cat > "$SUMMARY_FILE" << EOF
{
    "test_info": {
        "start_time": "$(date -d "@$((end_time - DURATION_SECS))" -Iseconds 2>/dev/null || echo "unknown")",
        "end_time": "$end_timestamp",
        "duration_seconds": $DURATION_SECS,
        "duration_human": "$DURATION",
        "symbols": "$(echo "$SYMBOLS" | tr ',' ' ')",
        "dry_run": $DRY_RUN,
        "simulated_data": $USE_SIMULATED
    },
    "metrics_collection": {
        "scrape_interval_seconds": $SCRAPE_INTERVAL,
        "total_scrapes": $metrics_count,
        "metrics_url": "$METRICS_URL"
    },
    "execution_metrics": {
        "retry_operations_total": $retry_total,
        "retry_first_try_success": $retry_success,
        "retry_success_rate_pct": $success_rate,
        "arbitrage_opportunities": $arb_opportunities,
        "signals_received": $signal_received,
        "signals_executed": $signal_executed,
        "best_execution_analyses": $best_exec_analyses
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
                    KRAKEN PAPER TRADING SOAK TEST ANALYSIS
================================================================================

TEST CONFIGURATION
------------------
Duration:           $DURATION ($DURATION_SECS seconds)
Symbols:            $SYMBOLS
Min Spread:         ${MIN_SPREAD}%
Dry Run Mode:       $DRY_RUN
Simulated Data:     $USE_SIMULATED

METRICS COLLECTION
------------------
Scrape Interval:    ${SCRAPE_INTERVAL}s
Total Scrapes:      $metrics_count
Metrics URL:        $METRICS_URL

EXECUTION SUMMARY
-----------------
Retry Operations:   $retry_total
First-Try Success:  $retry_success
Success Rate:       ${success_rate}%

Arbitrage Opportunities Detected: $arb_opportunities
Signals Received:   $signal_received
Signals Executed:   $signal_executed
Best-Execution Analyses: $best_exec_analyses

HEALTH ASSESSMENT
-----------------
EOF

    # Health assessment
    if [[ "$retry_total" -eq 0 ]]; then
        echo "⚠️  No retry operations recorded - check if execution was active" >> "$ANALYSIS_FILE"
    elif (( $(echo "$success_rate > 95" | bc -l 2>/dev/null || echo 1) )); then
        echo "✅ Retry success rate: EXCELLENT (>${success_rate}%)" >> "$ANALYSIS_FILE"
    elif (( $(echo "$success_rate > 80" | bc -l 2>/dev/null || echo 1) )); then
        echo "⚠️  Retry success rate: FAIR (${success_rate}%)" >> "$ANALYSIS_FILE"
    else
        echo "❌ Retry success rate: POOR (${success_rate}%)" >> "$ANALYSIS_FILE"
    fi

    if [[ "$arb_opportunities" -gt 0 ]]; then
        echo "✅ Arbitrage monitoring: ACTIVE ($arb_opportunities opportunities)" >> "$ANALYSIS_FILE"
    else
        echo "⚠️  Arbitrage monitoring: No opportunities detected" >> "$ANALYSIS_FILE"
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
        echo "- Verify that the paper trading example is connecting to exchanges" >> "$ANALYSIS_FILE"
        echo "- Check if KRAKEN_API_KEY and KRAKEN_API_SECRET are set if using authenticated feeds" >> "$ANALYSIS_FILE"
    fi

    if (( $(echo "$success_rate < 80" | bc -l 2>/dev/null || echo 0) )); then
        echo "- Investigate retry failures - check network connectivity" >> "$ANALYSIS_FILE"
        echo "- Review circuit breaker state in metrics" >> "$ANALYSIS_FILE"
        echo "- Consider adjusting retry backoff parameters" >> "$ANALYSIS_FILE"
    fi

    echo "" >> "$ANALYSIS_FILE"
    echo "=================================================================================" >> "$ANALYSIS_FILE"
    echo "Full metrics available in: $METRICS_DIR" >> "$ANALYSIS_FILE"
    echo "Application logs in: $LOG_FILE" >> "$ANALYSIS_FILE"
    echo "=================================================================================" >> "$ANALYSIS_FILE"

    log_info "Summary written to $SUMMARY_FILE"
    log_info "Analysis written to $ANALYSIS_FILE"

    # Print analysis to console
    echo ""
    cat "$ANALYSIS_FILE"
}

# =============================================================================
# Main Execution
# =============================================================================

# Start metrics scraper in background
log_info "Starting metrics scraper (interval: ${SCRAPE_INTERVAL}s)..."
scrape_metrics &
echo $! > "$METRICS_PID_FILE"

# Build environment for paper trading
export KRAKEN_DRY_RUN="$DRY_RUN"
export USE_SIMULATED_DATA="$USE_SIMULATED"
export PAPER_TRADING_SYMBOLS="$SYMBOLS"
export PAPER_TRADING_DURATION_SECS="$DURATION_SECS"
export MIN_SPREAD_PCT="$MIN_SPREAD"
export PAPER_ANALYSIS_INTERVAL_SECS="$ANALYSIS_INTERVAL"
export RUST_LOG="${RUST_LOG:-info,janus=debug,janus_execution=debug}"

log_info "Starting paper trading..."

# Run paper trading with timeout
cd "$PROJECT_ROOT/src/execution"

timeout --signal=INT "$DURATION_SECS" \
    cargo run --release --example paper_trading 2>&1 | tee -a "$LOG_FILE" &

PAPER_PID=$!
echo $PAPER_PID > "$PID_FILE"

log_info "Paper trading started (PID: $PAPER_PID)"
log_info "Test will run for $DURATION"
log_info "Press Ctrl+C to stop early"

# Wait for paper trading to complete
wait $PAPER_PID || true

log_info "Paper trading process completed"

# Cleanup will be called by trap
