#!/bin/bash
# =============================================================================
# FKS Paper Trading Test — Composable RSS Memory Monitoring
# =============================================================================
# Manages RSS memory monitoring as a composable layer that can be attached to
# any test type. Called by deploy.sh when RSS monitoring is enabled.
#
# This script wraps scripts/monitoring/rss-memory-monitor.sh and integrates
# it into the test results directory structure.
#
# Commands:
#   start   — Start RSS monitoring in the background
#   stop    — Stop RSS monitoring and collect results
#   status  — Check if RSS monitoring is running and show latest stats
#   report  — Generate a summary report from collected RSS data
#
# Required environment variables:
#   FKS_TEST_ID             - Unique test identifier
#   FKS_DURATION_HOURS      - Monitoring duration in hours
#   FKS_RSS_INTERVAL        - Sampling interval in seconds (default: 10)
#   FKS_RSS_THRESHOLD       - RSS growth threshold in MB (default: 100)
#   FKS_RSS_CONTAINERS      - Container name regex (default: "janus|fks")
#   FKS_RSS_PUSHGATEWAY     - Prometheus Pushgateway URL (optional)
# =============================================================================
set -euo pipefail

COMMAND="${1:-start}"

# ── Configuration ──
TEST_ID="${FKS_TEST_ID:-unknown}"
DURATION_HOURS="${FKS_DURATION_HOURS:-24}"
RSS_INTERVAL="${FKS_RSS_INTERVAL:-10}"
RSS_THRESHOLD="${FKS_RSS_THRESHOLD:-100}"
RSS_CONTAINERS="${FKS_RSS_CONTAINERS:-janus|fks}"
RSS_PUSHGATEWAY="${FKS_RSS_PUSHGATEWAY:-}"

# ── Paths ──
PROJECT_DIR="${HOME}/fks"
TEST_DIR="${FKS_TEST_DIR:-$(cat /tmp/fks-test-dir 2>/dev/null || echo "${PROJECT_DIR}/test-results/${TEST_ID}")}"
MONITOR_DIR="${TEST_DIR}/monitoring"
RSS_SCRIPT="${PROJECT_DIR}/scripts/monitoring/rss-memory-monitor.sh"
PID_FILE="${MONITOR_DIR}/rss-monitor.pid"
LOG_FILE="${MONITOR_DIR}/rss-monitor.log"

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[RSS]${NC} $1"; }
log_success() { echo -e "${GREEN}[RSS ✓]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[RSS !]${NC} $1"; }
log_error()   { echo -e "${RED}[RSS ✗]${NC} $1"; }

# =============================================================================
# start — Launch RSS monitoring in the background
# =============================================================================
do_start() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  📈 Starting RSS Memory Monitoring${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # Validate the RSS monitor script exists
    if [ ! -f "$RSS_SCRIPT" ]; then
        log_error "RSS monitor script not found at: $RSS_SCRIPT"
        log_warning "RSS monitoring will be skipped"
        echo ""
        echo "Expected location: scripts/monitoring/rss-memory-monitor.sh"
        echo "See docs/testing/AUDIT_REMEDIATION_STATUS.md for setup details."
        return 1
    fi

    # Check if already running
    if [ -f "$PID_FILE" ]; then
        EXISTING_PID=$(cat "$PID_FILE")
        if kill -0 "$EXISTING_PID" 2>/dev/null; then
            log_warning "RSS monitor already running (PID: $EXISTING_PID)"
            log_info "Use 'monitoring.sh stop' first to restart"
            return 0
        else
            log_info "Stale PID file found, cleaning up"
            rm -f "$PID_FILE"
        fi
    fi

    # Create monitoring directory
    mkdir -p "$MONITOR_DIR"

    # Build the command
    RSS_CMD="bash ${RSS_SCRIPT}"
    RSS_CMD="${RSS_CMD} --duration ${DURATION_HOURS}"
    RSS_CMD="${RSS_CMD} --interval ${RSS_INTERVAL}"
    RSS_CMD="${RSS_CMD} --threshold ${RSS_THRESHOLD}"
    RSS_CMD="${RSS_CMD} --output ${MONITOR_DIR}"
    RSS_CMD="${RSS_CMD} --containers '${RSS_CONTAINERS}'"
    RSS_CMD="${RSS_CMD} --docker-only"

    if [ -n "$RSS_PUSHGATEWAY" ]; then
        RSS_CMD="${RSS_CMD} --pushgateway ${RSS_PUSHGATEWAY}"
    fi

    log_info "Configuration:"
    echo "  Duration:     ${DURATION_HOURS} hours"
    echo "  Interval:     ${RSS_INTERVAL}s"
    echo "  Threshold:    ${RSS_THRESHOLD} MB"
    echo "  Containers:   ${RSS_CONTAINERS}"
    echo "  Output:       ${MONITOR_DIR}"
    if [ -n "$RSS_PUSHGATEWAY" ]; then
        echo "  Pushgateway:  ${RSS_PUSHGATEWAY}"
    else
        echo "  Pushgateway:  disabled"
    fi
    echo ""

    # Save monitoring config for later reference
    cat > "${MONITOR_DIR}/monitoring-config.json" << CFGEOF
{
  "test_id": "${TEST_ID}",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_hours": ${DURATION_HOURS},
  "interval_seconds": ${RSS_INTERVAL},
  "threshold_mb": ${RSS_THRESHOLD},
  "container_regex": "${RSS_CONTAINERS}",
  "pushgateway": "${RSS_PUSHGATEWAY}",
  "monitor_script": "${RSS_SCRIPT}",
  "output_dir": "${MONITOR_DIR}"
}
CFGEOF

    # Launch in background using setsid so the process gets its own session ID
    # and survives SSH session termination. When this script is invoked via the
    # GitHub Actions ssh-deploy action, systemd kills all processes in the SSH
    # session scope on disconnect. Plain `nohup` only guards against SIGHUP but
    # not scope cleanup. `setsid` moves the child into a new session so systemd
    # leaves it alone.
    log_info "Starting RSS monitor..."
    chmod +x "$RSS_SCRIPT"
    setsid bash -c "$RSS_CMD" > "$LOG_FILE" 2>&1 &
    RSS_PID=$!
    echo "$RSS_PID" > "$PID_FILE"
    disown "$RSS_PID" 2>/dev/null || true

    # Verify it started
    sleep 2
    if kill -0 "$RSS_PID" 2>/dev/null; then
        log_success "RSS monitor running (PID: $RSS_PID)"
        log_info "Log file: ${LOG_FILE}"
        log_info "Data dir: ${MONITOR_DIR}"
    else
        log_error "RSS monitor failed to start"
        log_error "Check log: ${LOG_FILE}"
        if [ -f "$LOG_FILE" ]; then
            echo ""
            echo "Last 20 lines of log:"
            tail -20 "$LOG_FILE" | sed 's/^/  /'
        fi
        rm -f "$PID_FILE"
        return 1
    fi

    # Generate a helper script to check RSS status
    cat > "${MONITOR_DIR}/check-rss.sh" << 'RSSCHECK'
#!/bin/bash
# FKS RSS Monitoring Status — auto-generated
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "═══════════════════════════════════════════════════════════"
echo "📈 RSS Memory Monitoring Status"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check if running
PID_FILE="${SCRIPT_DIR}/rss-monitor.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "🟢 Status: RUNNING (PID: $PID)"
        UPTIME=$(ps -p "$PID" -o etime= 2>/dev/null | xargs)
        echo "   Uptime: ${UPTIME:-unknown}"
    else
        echo "🔴 Status: STOPPED (PID $PID no longer running)"
    fi
else
    echo "⚪ Status: NOT STARTED"
fi
echo ""

# Config
if [ -f "${SCRIPT_DIR}/monitoring-config.json" ]; then
    echo "📋 Configuration:"
    cat "${SCRIPT_DIR}/monitoring-config.json" | python3 -m json.tool 2>/dev/null || cat "${SCRIPT_DIR}/monitoring-config.json"
    echo ""
fi

# Latest samples
CSV_FILES=$(ls -t "${SCRIPT_DIR}"/rss_samples_*.csv 2>/dev/null | head -1)
if [ -n "$CSV_FILES" ]; then
    SAMPLE_COUNT=$(wc -l < "$CSV_FILES" 2>/dev/null || echo "0")
    echo "📊 Samples collected: $((SAMPLE_COUNT - 1))"
    echo ""
    echo "Last 10 samples:"
    tail -10 "$CSV_FILES" | column -t -s',' 2>/dev/null || tail -10 "$CSV_FILES"
    echo ""
fi

# Alerts
ALERT_FILES=$(ls -t "${SCRIPT_DIR}"/rss_alerts_*.log 2>/dev/null | head -1)
if [ -n "$ALERT_FILES" ] && [ -s "$ALERT_FILES" ]; then
    ALERT_COUNT=$(wc -l < "$ALERT_FILES" 2>/dev/null || echo "0")
    echo "⚠️  Alerts: $ALERT_COUNT"
    echo ""
    echo "Recent alerts:"
    tail -5 "$ALERT_FILES" | sed 's/^/  /'
else
    echo "✅ No leak alerts"
fi
echo ""

# Current container RSS snapshot
echo "📦 Current container RSS:"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null | grep -iE "fks|janus|NAME" || echo "  Could not get container stats"
echo ""

# Summary if available
SUMMARY_FILES=$(ls -t "${SCRIPT_DIR}"/rss_summary_*.txt 2>/dev/null | head -1)
if [ -n "$SUMMARY_FILES" ]; then
    echo "📄 Latest Summary:"
    head -30 "$SUMMARY_FILES" | sed 's/^/  /'
fi
RSSCHECK
    chmod +x "${MONITOR_DIR}/check-rss.sh"

    echo ""
    log_success "RSS monitoring started successfully"
    echo ""
    echo "  Quick commands:"
    echo "    Status:  ${MONITOR_DIR}/check-rss.sh"
    echo "    Log:     tail -f ${LOG_FILE}"
    echo "    Samples: tail -f ${MONITOR_DIR}/rss_samples_*.csv"
    echo ""
}

# =============================================================================
# stop — Stop RSS monitoring and collect final results
# =============================================================================
do_stop() {
    echo ""
    log_info "Stopping RSS memory monitoring..."

    if [ ! -f "$PID_FILE" ]; then
        log_warning "No PID file found — RSS monitor may not be running"
        return 0
    fi

    RSS_PID=$(cat "$PID_FILE")

    if kill -0 "$RSS_PID" 2>/dev/null; then
        # Send SIGTERM for graceful shutdown (allows summary generation)
        kill -TERM "$RSS_PID" 2>/dev/null || true

        # Wait up to 30 seconds for graceful exit
        WAIT=0
        while kill -0 "$RSS_PID" 2>/dev/null && [ $WAIT -lt 30 ]; do
            sleep 1
            WAIT=$((WAIT + 1))
        done

        if kill -0 "$RSS_PID" 2>/dev/null; then
            log_warning "Graceful shutdown timed out, sending SIGKILL"
            kill -9 "$RSS_PID" 2>/dev/null || true
        fi

        log_success "RSS monitor stopped (PID: $RSS_PID)"
    else
        log_info "RSS monitor already stopped (PID: $RSS_PID)"
    fi

    rm -f "$PID_FILE"

    # Record stop time
    if [ -f "${MONITOR_DIR}/monitoring-config.json" ]; then
        # Append stop time using a temp file (can't edit JSON in-place easily in bash)
        STOP_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        log_info "Stopped at: ${STOP_TIME}"
    fi

    # Show final summary if available
    do_report

    echo ""
}

# =============================================================================
# status — Check if RSS monitoring is running
# =============================================================================
do_status() {
    if [ -f "${MONITOR_DIR}/check-rss.sh" ]; then
        bash "${MONITOR_DIR}/check-rss.sh"
    else
        echo ""
        if [ ! -f "$PID_FILE" ]; then
            log_info "RSS monitoring is not configured for this test"
            return 0
        fi

        RSS_PID=$(cat "$PID_FILE")
        if kill -0 "$RSS_PID" 2>/dev/null; then
            log_success "RSS monitor is running (PID: $RSS_PID)"
        else
            log_warning "RSS monitor is not running (PID $RSS_PID exited)"
        fi

        # Show sample count
        CSV_FILE=$(ls -t "${MONITOR_DIR}"/rss_samples_*.csv 2>/dev/null | head -1)
        if [ -n "$CSV_FILE" ]; then
            SAMPLE_COUNT=$(wc -l < "$CSV_FILE" 2>/dev/null || echo "0")
            log_info "Samples collected: $((SAMPLE_COUNT - 1))"
        fi

        # Show alert count
        ALERT_FILE=$(ls -t "${MONITOR_DIR}"/rss_alerts_*.log 2>/dev/null | head -1)
        if [ -n "$ALERT_FILE" ] && [ -s "$ALERT_FILE" ]; then
            ALERT_COUNT=$(wc -l < "$ALERT_FILE" 2>/dev/null || echo "0")
            log_warning "Leak alerts: $ALERT_COUNT"
        else
            log_success "No leak alerts"
        fi
        echo ""
    fi
}

# =============================================================================
# report — Generate a summary report from RSS data
# =============================================================================
do_report() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  📊 RSS Monitoring Report${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    if [ ! -d "$MONITOR_DIR" ]; then
        log_warning "No monitoring data found at: $MONITOR_DIR"
        return 0
    fi

    # Check for summary file (generated by rss-memory-monitor.sh on completion)
    SUMMARY_FILE=$(ls -t "${MONITOR_DIR}"/rss_summary_*.txt 2>/dev/null | head -1)
    if [ -n "$SUMMARY_FILE" ]; then
        log_info "Summary from rss-memory-monitor.sh:"
        echo ""
        cat "$SUMMARY_FILE"
        echo ""
    fi

    # Check for alerts
    ALERT_FILE=$(ls -t "${MONITOR_DIR}"/rss_alerts_*.log 2>/dev/null | head -1)
    if [ -n "$ALERT_FILE" ] && [ -s "$ALERT_FILE" ]; then
        ALERT_COUNT=$(wc -l < "$ALERT_FILE")
        log_warning "${ALERT_COUNT} leak alert(s) detected!"
        echo ""
        echo "Alert details:"
        cat "$ALERT_FILE" | sed 's/^/  /'
        echo ""
    else
        log_success "No leak alerts — all services within threshold"
    fi

    # Quick stats from CSV
    CSV_FILE=$(ls -t "${MONITOR_DIR}"/rss_samples_*.csv 2>/dev/null | head -1)
    if [ -n "$CSV_FILE" ]; then
        TOTAL_SAMPLES=$(($(wc -l < "$CSV_FILE") - 1))
        FIRST_SAMPLE=$(head -2 "$CSV_FILE" | tail -1 | cut -d',' -f1 2>/dev/null || echo "unknown")
        LAST_SAMPLE=$(tail -1 "$CSV_FILE" | cut -d',' -f1 2>/dev/null || echo "unknown")

        echo "📊 Data Summary:"
        echo "  Total samples:  ${TOTAL_SAMPLES}"
        echo "  First sample:   ${FIRST_SAMPLE}"
        echo "  Last sample:    ${LAST_SAMPLE}"
        echo "  CSV file:       ${CSV_FILE}"
        echo ""

        # Show per-service RSS range if we can parse it
        if command -v awk &>/dev/null; then
            echo "📈 Per-Service RSS Range (MB):"
            # CSV format: timestamp,service,pid,rss_kb,rss_mb,source
            awk -F',' 'NR>1 {
                svc=$2;
                mb=$5+0;
                if (!(svc in min_mb) || mb < min_mb[svc]) min_mb[svc]=mb;
                if (!(svc in max_mb) || mb > max_mb[svc]) max_mb[svc]=mb;
                if (!(svc in first_mb)) first_mb[svc]=mb;
                last_mb[svc]=mb;
                count[svc]++;
                sum[svc]+=mb;
            }
            END {
                printf "  %-25s %8s %8s %8s %8s %8s\n", "SERVICE", "FIRST", "LAST", "MIN", "MAX", "GROWTH";
                printf "  %-25s %8s %8s %8s %8s %8s\n", "-------", "-----", "----", "---", "---", "------";
                for (svc in count) {
                    growth = last_mb[svc] - first_mb[svc];
                    flag = "";
                    if (growth > '"${RSS_THRESHOLD}"') flag = " ⚠️";
                    printf "  %-25s %7.1f %7.1f %7.1f %7.1f %+7.1f%s\n",
                        svc, first_mb[svc], last_mb[svc], min_mb[svc], max_mb[svc], growth, flag;
                }
            }' "$CSV_FILE" 2>/dev/null || log_warning "Could not parse CSV for per-service stats"
            echo ""
        fi
    else
        log_warning "No CSV sample data found"
    fi

    # Audit pass/fail assessment
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  Audit Item #1 — Pass/Fail Assessment"
    echo "═══════════════════════════════════════════════════════════"
    echo ""

    PASS=true
    ISSUES=0

    # Check for alerts (growth exceeding threshold)
    if [ -n "$ALERT_FILE" ] && [ -s "$ALERT_FILE" ]; then
        echo "  ❌ FAIL: RSS growth alerts detected"
        PASS=false
        ISSUES=$((ISSUES + 1))
    else
        echo "  ✅ PASS: No RSS growth exceeds ${RSS_THRESHOLD} MB threshold"
    fi

    # Check for OOM kills
    OOM_COUNT=$(dmesg 2>/dev/null | grep -ci "oom\|out of memory" || echo "0")
    if [ "$OOM_COUNT" -gt 0 ]; then
        echo "  ❌ FAIL: $OOM_COUNT OOM event(s) detected in dmesg"
        PASS=false
        ISSUES=$((ISSUES + 1))
    else
        echo "  ✅ PASS: No OOM kills detected"
    fi

    # Check for container restarts
    RESTARTS=$(docker ps -a --filter "name=fks" --format "{{.Names}}: {{.Status}}" 2>/dev/null | grep -ci "restarting" || echo "0")
    if [ "$RESTARTS" -gt 0 ]; then
        echo "  ❌ FAIL: $RESTARTS container(s) in restarting state"
        PASS=false
        ISSUES=$((ISSUES + 1))
    else
        echo "  ✅ PASS: No container restarts"
    fi

    # Check duration coverage
    if [ -n "$CSV_FILE" ] && [ "$TOTAL_SAMPLES" -gt 0 ]; then
        EXPECTED_SAMPLES=$(( (DURATION_HOURS * 3600) / RSS_INTERVAL ))
        COVERAGE_PCT=$(( (TOTAL_SAMPLES * 100) / (EXPECTED_SAMPLES > 0 ? EXPECTED_SAMPLES : 1) ))
        if [ "$COVERAGE_PCT" -lt 90 ]; then
            echo "  ⚠️  WARN: Only ${COVERAGE_PCT}% sample coverage (${TOTAL_SAMPLES}/${EXPECTED_SAMPLES})"
            ISSUES=$((ISSUES + 1))
        else
            echo "  ✅ PASS: ${COVERAGE_PCT}% sample coverage"
        fi
    fi

    echo ""
    if [ "$PASS" = true ]; then
        echo "  🎉 OVERALL: PASS — All criteria met"
    else
        echo "  🚨 OVERALL: FAIL — ${ISSUES} issue(s) found"
    fi
    echo ""

    # Write pass/fail result to a file for collect-report.sh to pick up
    if [ "$PASS" = true ]; then
        echo "PASS" > "${MONITOR_DIR}/audit-result.txt"
    else
        echo "FAIL" > "${MONITOR_DIR}/audit-result.txt"
    fi
}

# =============================================================================
# Main
# =============================================================================
case "$COMMAND" in
    start)
        do_start
        ;;
    stop)
        do_stop
        ;;
    status)
        do_status
        ;;
    report)
        do_report
        ;;
    *)
        echo "Usage: $0 {start|stop|status|report}"
        echo ""
        echo "Commands:"
        echo "  start   Start RSS monitoring in the background"
        echo "  stop    Stop RSS monitoring and collect results"
        echo "  status  Check if monitoring is running"
        echo "  report  Generate summary report from collected data"
        echo ""
        echo "Environment variables:"
        echo "  FKS_TEST_ID          Test identifier"
        echo "  FKS_DURATION_HOURS   Monitoring duration in hours"
        echo "  FKS_RSS_INTERVAL     Sampling interval in seconds (default: 10)"
        echo "  FKS_RSS_THRESHOLD    Growth threshold in MB (default: 100)"
        echo "  FKS_RSS_CONTAINERS   Container name regex (default: janus|fks)"
        echo "  FKS_RSS_PUSHGATEWAY  Prometheus Pushgateway URL (optional)"
        exit 1
        ;;
esac
