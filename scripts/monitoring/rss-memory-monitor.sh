#!/usr/bin/env bash
# =============================================================================
# FKS / JANUS — 72-Hour RSS Memory Monitor
# =============================================================================
# Continuously samples RSS (Resident Set Size) memory for all JANUS services
# running in Docker or as native processes, writes CSV + summary stats, and
# optionally pushes metrics to a Prometheus pushgateway.
#
# Usage:
#   ./rss-memory-monitor.sh [OPTIONS]
#
# Options:
#   -d, --duration HOURS     Monitoring duration in hours (default: 72)
#   -i, --interval SECONDS   Sampling interval in seconds (default: 10)
#   -o, --output DIR         Output directory for CSV/reports (default: ./rss-monitor-output)
#   -p, --pushgateway URL    Prometheus pushgateway URL (optional)
#   -t, --threshold MB       RSS growth threshold to flag as leak (default: 100)
#   -c, --containers REGEX   Docker container name regex (default: "janus|fks")
#   -n, --native REGEX       Native process name regex (default: "janus|fks-")
#   --docker-only            Only monitor Docker containers
#   --native-only            Only monitor native processes
#   --no-color               Disable colored output
#   -h, --help               Show this help message
#
# Output:
#   <output_dir>/rss_samples_<timestamp>.csv    — Raw per-process RSS samples
#   <output_dir>/rss_summary_<timestamp>.txt    — End-of-run summary report
#   <output_dir>/rss_alerts_<timestamp>.log     — Growth alerts (if any)
#
# Requirements:
#   - bash >= 4.0
#   - docker (if monitoring containers)
#   - ps, awk, date, bc
#   - curl (optional, for pushgateway)
#
# Last updated: 2025-07-14 (audit remediation)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DURATION_HOURS=72
INTERVAL_SECONDS=10
OUTPUT_DIR="./rss-monitor-output"
PUSHGATEWAY_URL=""
THRESHOLD_MB=100
CONTAINER_REGEX="janus|fks"
NATIVE_REGEX="janus|fks-"
DOCKER_ONLY=false
NATIVE_ONLY=false
NO_COLOR=false

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
_color_reset="\033[0m"
_color_red="\033[1;31m"
_color_green="\033[1;32m"
_color_yellow="\033[1;33m"
_color_blue="\033[1;34m"
_color_cyan="\033[1;36m"

_c() {
    if $NO_COLOR; then
        echo -n "$2"
    else
        echo -ne "${1}${2}${_color_reset}"
    fi
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
    head -38 "$0" | tail -35 | sed 's/^# \?//'
    exit 0
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--duration)     DURATION_HOURS="$2";    shift 2 ;;
        -i|--interval)     INTERVAL_SECONDS="$2";  shift 2 ;;
        -o|--output)       OUTPUT_DIR="$2";         shift 2 ;;
        -p|--pushgateway)  PUSHGATEWAY_URL="$2";    shift 2 ;;
        -t|--threshold)    THRESHOLD_MB="$2";       shift 2 ;;
        -c|--containers)   CONTAINER_REGEX="$2";    shift 2 ;;
        -n|--native)       NATIVE_REGEX="$2";       shift 2 ;;
        --docker-only)     DOCKER_ONLY=true;        shift   ;;
        --native-only)     NATIVE_ONLY=true;        shift   ;;
        --no-color)        NO_COLOR=true;           shift   ;;
        -h|--help)         usage ;;
        *)                 echo "Unknown option: $1"; usage ;;
    esac
done

# ---------------------------------------------------------------------------
# Derived values
# ---------------------------------------------------------------------------
TOTAL_SAMPLES=$(( (DURATION_HOURS * 3600) / INTERVAL_SECONDS ))
RUN_ID=$(date +%Y%m%d_%H%M%S)
CSV_FILE="${OUTPUT_DIR}/rss_samples_${RUN_ID}.csv"
SUMMARY_FILE="${OUTPUT_DIR}/rss_summary_${RUN_ID}.txt"
ALERT_FILE="${OUTPUT_DIR}/rss_alerts_${RUN_ID}.log"

# Associative arrays for tracking per-service stats
declare -A FIRST_RSS      # service -> first observed RSS (KB)
declare -A LAST_RSS       # service -> last observed RSS (KB)
declare -A PEAK_RSS       # service -> peak RSS (KB)
declare -A MIN_RSS        # service -> minimum RSS (KB)
declare -A SAMPLE_COUNT   # service -> number of samples
declare -A SUM_RSS        # service -> cumulative RSS for average (KB)
declare -A FIRST_TS       # service -> first sample epoch
declare -A LAST_TS        # service -> last sample epoch

ALERT_COUNT=0
SAMPLE_TOTAL=0

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
mkdir -p "$OUTPUT_DIR"
echo "timestamp_utc,epoch_s,service,pid,rss_kb,rss_mb,source" > "$CSV_FILE"
: > "$ALERT_FILE"

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

log_info()  { echo -e "[$(_c "$_color_blue" "INFO")] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
log_warn()  { echo -e "[$(_c "$_color_yellow" "WARN")] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
log_alert() { echo -e "[$(_c "$_color_red" "ALERT")] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
log_ok()    { echo -e "[$(_c "$_color_green" "OK")] $(date '+%Y-%m-%d %H:%M:%S') $*"; }

has_docker() {
    command -v docker &>/dev/null && docker info &>/dev/null 2>&1
}

# Read RSS (in KB) for a container via host-side /proc/<pid> and cgroup files.
# This avoids `docker exec` entirely, so it works with distroless/scratch
# images that don't ship /bin/sh.
#
# Strategy (tried in order):
#   1. cgroup v2: /sys/fs/cgroup/memory.stat  → "anon <bytes>"
#      Path on host: /proc/<pid>/root/sys/fs/cgroup/memory.stat  OR
#      the unified cgroup path from /proc/<pid>/cgroup
#   2. cgroup v1: /sys/fs/cgroup/memory/memory.stat → "rss <bytes>"
#   3. /proc/<pid>/status → VmRSS (KB, already in the right unit)
#   4. (caller falls back to `docker stats` if all above fail)
#
# Outputs the RSS value in KB on stdout. Empty output = failure.
_read_container_rss_from_host() {
    local container_pid="$1"

    # --- cgroup v2 (unified) via /proc/<pid>/root ---
    local cgv2_stat="/proc/${container_pid}/root/sys/fs/cgroup/memory.stat"
    if [[ -r "$cgv2_stat" ]]; then
        local val
        val=$(awk '/^anon /{print int($2/1024)}' "$cgv2_stat" 2>/dev/null)
        if [[ -n "$val" && "$val" != "0" ]]; then
            echo "$val"
            return
        fi
    fi

    # --- cgroup v2 via the host cgroup mount ---
    # /proc/<pid>/cgroup contains e.g. "0::/system.slice/docker-<id>.scope"
    local cg_rel
    cg_rel=$(awk -F: '$1=="0" && $2=="" {print $3}' "/proc/${container_pid}/cgroup" 2>/dev/null || true)
    if [[ -n "$cg_rel" ]]; then
        local host_cg="/sys/fs/cgroup${cg_rel}/memory.stat"
        if [[ -r "$host_cg" ]]; then
            local val
            val=$(awk '/^anon /{print int($2/1024)}' "$host_cg" 2>/dev/null)
            if [[ -n "$val" && "$val" != "0" ]]; then
                echo "$val"
                return
            fi
        fi
    fi

    # --- cgroup v1 via /proc/<pid>/root ---
    local cgv1_stat="/proc/${container_pid}/root/sys/fs/cgroup/memory/memory.stat"
    if [[ -r "$cgv1_stat" ]]; then
        local val
        val=$(awk '/^rss /{print int($2/1024)}' "$cgv1_stat" 2>/dev/null)
        if [[ -n "$val" && "$val" != "0" ]]; then
            echo "$val"
            return
        fi
    fi

    # --- /proc/<pid>/status  (VmRSS is already in KB) ---
    local proc_status="/proc/${container_pid}/status"
    if [[ -r "$proc_status" ]]; then
        local val
        val=$(awk '/^VmRSS:/{print int($2)}' "$proc_status" 2>/dev/null)
        if [[ -n "$val" && "$val" != "0" ]]; then
            echo "$val"
            return
        fi
    fi

    # All host-side reads failed — caller should fall back to docker stats.
}

# Convert a human-readable docker-stats memory string (e.g. "123.4MiB") to KB.
_mem_usage_to_kb() {
    local mem_usage="$1"
    if [[ "$mem_usage" == *GiB* ]]; then
        echo "$mem_usage" | tr -d 'GiB' | awk '{printf "%d", $1 * 1048576}'
    elif [[ "$mem_usage" == *MiB* ]]; then
        echo "$mem_usage" | tr -d 'MiB' | awk '{printf "%d", $1 * 1024}'
    elif [[ "$mem_usage" == *KiB* ]]; then
        echo "$mem_usage" | tr -d 'KiB' | awk '{printf "%d", $1}'
    elif [[ "$mem_usage" == *GB* ]]; then
        echo "$mem_usage" | tr -d 'GB' | awk '{printf "%d", $1 * 1000000}'
    elif [[ "$mem_usage" == *MB* ]]; then
        echo "$mem_usage" | tr -d 'MB' | awk '{printf "%d", $1 * 1000}'
    elif [[ "$mem_usage" == *KB* ]]; then
        echo "$mem_usage" | tr -d 'KB' | awk '{printf "%d", $1}'
    fi
}

# Sample Docker container RSS via host-side /proc reads (preferred) or
# docker stats (fallback). Never uses `docker exec`, so distroless/scratch
# containers are handled correctly.
sample_docker_containers() {
    if $NATIVE_ONLY; then return; fi
    if ! has_docker; then return; fi

    local containers
    containers=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E "$CONTAINER_REGEX" || true)

    for container in $containers; do
        local rss_kb=""
        local container_pid=""

        # Obtain the container's init PID on the host via docker inspect.
        container_pid=$(docker inspect --format '{{.State.Pid}}' "$container" 2>/dev/null || true)

        # Strategy 1: Host-side /proc + cgroup reads (accurate, no exec needed)
        if [[ -n "$container_pid" && "$container_pid" != "0" ]]; then
            rss_kb=$(_read_container_rss_from_host "$container_pid")
        fi

        # Strategy 2: Fallback to docker stats (includes file-cache, less precise)
        if [[ -z "$rss_kb" || "$rss_kb" == "0" ]]; then
            local mem_usage
            mem_usage=$(docker stats --no-stream --format '{{.MemUsage}}' "$container" 2>/dev/null \
                        | awk -F/ '{print $1}' | tr -d ' ')
            if [[ -n "$mem_usage" ]]; then
                rss_kb=$(_mem_usage_to_kb "$mem_usage")
            fi
        fi

        if [[ -n "$rss_kb" && "$rss_kb" != "0" ]]; then
            emit_sample "$container" "${container_pid:-container}" "$rss_kb" "docker"
        fi
    done
}

# Sample native (non-Docker) process RSS via /proc or ps
sample_native_processes() {
    if $DOCKER_ONLY; then return; fi

    # Use ps to find matching processes
    local ps_output
    ps_output=$(ps -eo pid,rss,comm --no-headers 2>/dev/null | grep -E "$NATIVE_REGEX" || true)

    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        local pid rss_kb comm
        pid=$(echo "$line" | awk '{print $1}')
        rss_kb=$(echo "$line" | awk '{print $2}')
        comm=$(echo "$line" | awk '{print $3}')

        if [[ -n "$rss_kb" && "$rss_kb" != "0" ]]; then
            emit_sample "$comm" "$pid" "$rss_kb" "native"
        fi
    done <<< "$ps_output"
}

# Emit a single sample: update tracking and write CSV row
emit_sample() {
    local service="$1"
    local pid="$2"
    local rss_kb="$3"
    local source="$4"
    local now_utc now_epoch rss_mb

    now_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    now_epoch=$(date +%s)
    rss_mb=$(awk "BEGIN {printf \"%.2f\", $rss_kb / 1024}")

    # Write CSV row
    echo "${now_utc},${now_epoch},${service},${pid},${rss_kb},${rss_mb},${source}" >> "$CSV_FILE"

    # Update tracking arrays
    if [[ -z "${FIRST_RSS[$service]+x}" ]]; then
        FIRST_RSS[$service]=$rss_kb
        MIN_RSS[$service]=$rss_kb
        PEAK_RSS[$service]=$rss_kb
        SUM_RSS[$service]=$rss_kb
        SAMPLE_COUNT[$service]=1
        FIRST_TS[$service]=$now_epoch
    else
        SAMPLE_COUNT[$service]=$(( ${SAMPLE_COUNT[$service]} + 1 ))
        SUM_RSS[$service]=$(( ${SUM_RSS[$service]} + rss_kb ))

        if (( rss_kb > ${PEAK_RSS[$service]} )); then
            PEAK_RSS[$service]=$rss_kb
        fi
        if (( rss_kb < ${MIN_RSS[$service]} )); then
            MIN_RSS[$service]=$rss_kb
        fi
    fi
    LAST_RSS[$service]=$rss_kb
    LAST_TS[$service]=$now_epoch

    # Check for growth alert
    check_growth_alert "$service" "$rss_kb" "$now_utc"

    # Push to Prometheus if configured
    if [[ -n "$PUSHGATEWAY_URL" ]]; then
        push_to_prometheus "$service" "$rss_kb" "$pid" "$source"
    fi

    SAMPLE_TOTAL=$((SAMPLE_TOTAL + 1))
}

# Check if RSS growth exceeds threshold
check_growth_alert() {
    local service="$1"
    local current_kb="$2"
    local timestamp="$3"

    local first_kb=${FIRST_RSS[$service]}
    local growth_kb=$(( current_kb - first_kb ))
    local growth_mb
    growth_mb=$(awk "BEGIN {printf \"%.1f\", $growth_kb / 1024}")
    local threshold_kb=$(( THRESHOLD_MB * 1024 ))

    if (( growth_kb > threshold_kb )); then
        local msg="MEMORY GROWTH ALERT: ${service} grew ${growth_mb}MB (threshold: ${THRESHOLD_MB}MB) — first=${first_kb}KB current=${current_kb}KB"
        log_alert "$msg"
        echo "${timestamp} ${msg}" >> "$ALERT_FILE"
        ALERT_COUNT=$((ALERT_COUNT + 1))
    fi
}

# Push metric to Prometheus pushgateway
push_to_prometheus() {
    local service="$1"
    local rss_kb="$2"
    local pid="$3"
    local source="$4"

    # Best-effort push, don't fail the monitor on pushgateway issues
    cat <<EOF | curl -s --max-time 5 --data-binary @- "${PUSHGATEWAY_URL}/metrics/job/rss_monitor/instance/${service}" 2>/dev/null || true
# HELP janus_rss_kb Resident Set Size in kilobytes
# TYPE janus_rss_kb gauge
janus_rss_kb{service="${service}",pid="${pid}",source="${source}"} ${rss_kb}
# HELP janus_rss_peak_kb Peak RSS in kilobytes since monitor start
# TYPE janus_rss_peak_kb gauge
janus_rss_peak_kb{service="${service}"} ${PEAK_RSS[$service]}
EOF
}

# Generate the final summary report
generate_summary() {
    local end_time
    end_time=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

    {
        echo "============================================================================="
        echo " FKS / JANUS — RSS Memory Monitoring Summary"
        echo "============================================================================="
        echo ""
        echo " Run ID:         ${RUN_ID}"
        echo " Started:        $(head -2 "$CSV_FILE" | tail -1 | cut -d, -f1)"
        echo " Ended:          ${end_time}"
        echo " Duration:       ${DURATION_HOURS}h (target), actual see timestamps above"
        echo " Interval:       ${INTERVAL_SECONDS}s"
        echo " Total Samples:  ${SAMPLE_TOTAL}"
        echo " Alerts Fired:   ${ALERT_COUNT}"
        echo " Threshold:      ${THRESHOLD_MB}MB growth"
        echo ""
        echo "-----------------------------------------------------------------------------"
        printf " %-25s %10s %10s %10s %10s %10s %10s\n" \
            "SERVICE" "FIRST(MB)" "LAST(MB)" "PEAK(MB)" "MIN(MB)" "AVG(MB)" "GROWTH(MB)"
        echo "-----------------------------------------------------------------------------"

        for service in "${!FIRST_RSS[@]}"; do
            local first_mb last_mb peak_mb min_mb avg_mb growth_mb
            first_mb=$(awk "BEGIN {printf \"%.1f\", ${FIRST_RSS[$service]} / 1024}")
            last_mb=$(awk "BEGIN {printf \"%.1f\", ${LAST_RSS[$service]} / 1024}")
            peak_mb=$(awk "BEGIN {printf \"%.1f\", ${PEAK_RSS[$service]} / 1024}")
            min_mb=$(awk "BEGIN {printf \"%.1f\", ${MIN_RSS[$service]} / 1024}")
            avg_mb=$(awk "BEGIN {printf \"%.1f\", ${SUM_RSS[$service]} / ${SAMPLE_COUNT[$service]} / 1024}")
            growth_mb=$(awk "BEGIN {printf \"%.1f\", (${LAST_RSS[$service]} - ${FIRST_RSS[$service]}) / 1024}")

            printf " %-25s %10s %10s %10s %10s %10s %10s\n" \
                "$service" "$first_mb" "$last_mb" "$peak_mb" "$min_mb" "$avg_mb" "$growth_mb"
        done

        echo "-----------------------------------------------------------------------------"
        echo ""

        # Per-service growth rate analysis
        echo " Growth Rate Analysis:"
        echo ""
        for service in "${!FIRST_RSS[@]}"; do
            local first_kb=${FIRST_RSS[$service]}
            local last_kb=${LAST_RSS[$service]}
            local growth_kb=$(( last_kb - first_kb ))
            local elapsed_s=$(( ${LAST_TS[$service]} - ${FIRST_TS[$service]} ))

            if (( elapsed_s > 0 )); then
                local rate_kb_per_hour
                rate_kb_per_hour=$(awk "BEGIN {printf \"%.2f\", ($growth_kb / $elapsed_s) * 3600}")
                local rate_mb_per_hour
                rate_mb_per_hour=$(awk "BEGIN {printf \"%.3f\", $rate_kb_per_hour / 1024}")
                local projected_24h_mb
                projected_24h_mb=$(awk "BEGIN {printf \"%.1f\", $rate_kb_per_hour * 24 / 1024}")

                local verdict="OK"
                if (( growth_kb > THRESHOLD_MB * 1024 )); then
                    verdict="LEAK SUSPECTED"
                elif (( growth_kb > THRESHOLD_MB * 512 )); then
                    verdict="WATCH"
                fi

                printf "   %-25s rate=%s MB/h  projected-24h=%s MB  [%s]\n" \
                    "$service" "$rate_mb_per_hour" "$projected_24h_mb" "$verdict"
            else
                printf "   %-25s insufficient data (single sample)\n" "$service"
            fi
        done

        echo ""
        echo "-----------------------------------------------------------------------------"
        echo " Verdict:"
        echo ""

        if (( ALERT_COUNT == 0 )); then
            echo "   ✓ No memory growth alerts during the monitoring period."
            echo "   All services stayed within the ${THRESHOLD_MB}MB growth threshold."
        else
            echo "   ✗ ${ALERT_COUNT} memory growth alert(s) detected!"
            echo "   Review ${ALERT_FILE} for details."
            echo "   Consider capturing heap profiles for flagged services."
        fi

        echo ""
        echo " Files:"
        echo "   CSV data:  ${CSV_FILE}"
        echo "   Alerts:    ${ALERT_FILE}"
        echo "   Summary:   ${SUMMARY_FILE}"
        echo "============================================================================="

    } | tee "$SUMMARY_FILE"
}

# ---------------------------------------------------------------------------
# Signal handling for graceful shutdown
# ---------------------------------------------------------------------------
RUNNING=true

cleanup() {
    RUNNING=false
    echo ""
    log_warn "Received termination signal. Generating summary..."
    generate_summary
    log_info "Monitor stopped. Data saved to ${OUTPUT_DIR}/"
    exit 0
}

trap cleanup SIGINT SIGTERM SIGHUP

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
main() {
    log_info "=== FKS/JANUS RSS Memory Monitor ==="
    log_info "Duration:       ${DURATION_HOURS}h (${TOTAL_SAMPLES} samples at ${INTERVAL_SECONDS}s intervals)"
    log_info "Output:         ${OUTPUT_DIR}/"
    log_info "Threshold:      ${THRESHOLD_MB}MB growth triggers alert"
    log_info "Container filter: ${CONTAINER_REGEX}"
    log_info "Process filter:   ${NATIVE_REGEX}"

    if [[ -n "$PUSHGATEWAY_URL" ]]; then
        log_info "Pushgateway:    ${PUSHGATEWAY_URL}"
    fi

    if $DOCKER_ONLY; then
        log_info "Mode: Docker containers only"
    elif $NATIVE_ONLY; then
        log_info "Mode: Native processes only"
    else
        log_info "Mode: Docker containers + native processes"
    fi

    # Verify we can find at least one target
    local found=false
    if ! $NATIVE_ONLY && has_docker; then
        local containers
        containers=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E "$CONTAINER_REGEX" || true)
        if [[ -n "$containers" ]]; then
            log_ok "Found Docker containers: $(echo "$containers" | tr '\n' ' ')"
            found=true
        else
            log_warn "No Docker containers matching '${CONTAINER_REGEX}' found"
        fi
    fi

    if ! $DOCKER_ONLY; then
        local procs
        procs=$(ps -eo comm --no-headers 2>/dev/null | grep -E "$NATIVE_REGEX" | sort -u || true)
        if [[ -n "$procs" ]]; then
            log_ok "Found native processes: $(echo "$procs" | tr '\n' ' ')"
            found=true
        else
            log_warn "No native processes matching '${NATIVE_REGEX}' found"
        fi
    fi

    if ! $found; then
        log_warn "No targets found yet. Will keep polling — services may start later."
    fi

    log_info "Starting sampling loop... (Ctrl+C to stop early and generate report)"
    echo ""

    local sample_num=0
    local start_epoch
    start_epoch=$(date +%s)

    while $RUNNING && (( sample_num < TOTAL_SAMPLES )); do
        sample_docker_containers
        sample_native_processes

        sample_num=$((sample_num + 1))

        # Progress update every 60 samples (or every ~10 minutes at default interval)
        if (( sample_num % 60 == 0 )); then
            local elapsed_s=$(( $(date +%s) - start_epoch ))
            local elapsed_h
            elapsed_h=$(awk "BEGIN {printf \"%.1f\", $elapsed_s / 3600}")
            local services_seen=${#FIRST_RSS[@]}
            log_info "Progress: ${sample_num}/${TOTAL_SAMPLES} samples | ${elapsed_h}h elapsed | ${services_seen} services tracked | ${ALERT_COUNT} alerts"
        fi

        # Sleep, but in small increments so we can catch signals
        local sleep_remaining=$INTERVAL_SECONDS
        while $RUNNING && (( sleep_remaining > 0 )); do
            if (( sleep_remaining > 1 )); then
                sleep 1
                sleep_remaining=$((sleep_remaining - 1))
            else
                sleep "$sleep_remaining"
                sleep_remaining=0
            fi
        done
    done

    log_info "Monitoring complete. Generating summary..."
    generate_summary
    log_info "Done. All data saved to ${OUTPUT_DIR}/"

    if (( ALERT_COUNT > 0 )); then
        exit 1  # Non-zero exit if leaks detected — useful for CI
    fi
}

main
