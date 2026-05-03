#!/bin/bash
#
# FKS Paper Trading Test Log Analysis Script
# ===========================================
#
# Analyzes logs from a paper trading test run and generates metrics.
#
# Usage:
#   ./scripts/analyze-paper-test-logs.sh [LOG_DIRECTORY]
#
# Example:
#   ./scripts/analyze-paper-test-logs.sh logs/168hr-test-20260126-125410
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Function to print section headers
print_header() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
}

# Function to print metrics
print_metric() {
    printf "${BLUE}%-35s${NC} %s\n" "$1:" "$2"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Check if directory provided
if [ -z "$1" ]; then
    # Try to find most recent test directory
    LOG_DIR=$(ls -td logs/*hr-test-* 2>/dev/null | head -1)
    if [ -z "$LOG_DIR" ]; then
        echo -e "${RED}Error: No test directory found${NC}"
        echo "Usage: $0 [LOG_DIRECTORY]"
        echo "Example: $0 logs/168hr-test-20260126-125410"
        exit 1
    fi
    echo -e "${YELLOW}No directory specified, using most recent: $LOG_DIR${NC}"
else
    LOG_DIR="$1"
fi

# Verify directory exists
if [ ! -d "$LOG_DIR" ]; then
    echo -e "${RED}Error: Directory not found: $LOG_DIR${NC}"
    exit 1
fi

# Header
echo -e "${MAGENTA}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       FKS Paper Trading Test - Log Analysis                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

print_metric "Analysis Directory" "$LOG_DIR"
print_metric "Analysis Time" "$(date -u +"%Y-%m-%d %H:%M:%S UTC")"

# ============================================
# TEST METADATA
# ============================================
print_header "1. TEST METADATA"

if [ -f "$LOG_DIR/test-info.json" ]; then
    TEST_ID=$(grep -oP '"test_id":\s*"\K[^"]+' "$LOG_DIR/test-info.json" 2>/dev/null || echo "Unknown")
    TEST_TYPE=$(grep -oP '"test_type":\s*"\K[^"]+' "$LOG_DIR/test-info.json" 2>/dev/null || echo "Unknown")
    START_TIME=$(grep -oP '"start_time":\s*"\K[^"]+' "$LOG_DIR/test-info.json" 2>/dev/null || echo "Unknown")
    EXPECTED_END=$(grep -oP '"expected_end_time":\s*"\K[^"]+' "$LOG_DIR/test-info.json" 2>/dev/null || echo "Unknown")
    DURATION_HOURS=$(grep -oP '"duration_hours":\s*\K[0-9]+' "$LOG_DIR/test-info.json" 2>/dev/null || echo "Unknown")

    print_metric "Test ID" "$TEST_ID"
    print_metric "Test Type" "$TEST_TYPE"
    print_metric "Start Time" "$START_TIME"
    print_metric "Expected End" "$EXPECTED_END"
    print_metric "Planned Duration" "$DURATION_HOURS hours"
else
    print_warning "test-info.json not found"
fi

# Calculate actual runtime
if [ -f "$LOG_DIR/janus.log" ]; then
    FIRST_LOG=$(head -1 "$LOG_DIR/janus.log" | grep -oP '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}' || echo "")
    LAST_LOG=$(tail -1 "$LOG_DIR/janus.log" | grep -oP '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}' || echo "")

    if [ -n "$FIRST_LOG" ] && [ -n "$LAST_LOG" ]; then
        START_EPOCH=$(date -d "$FIRST_LOG" +%s 2>/dev/null || echo 0)
        END_EPOCH=$(date -d "$LAST_LOG" +%s 2>/dev/null || echo 0)

        if [ "$START_EPOCH" -gt 0 ] && [ "$END_EPOCH" -gt 0 ]; then
            RUNTIME_SECONDS=$((END_EPOCH - START_EPOCH))
            RUNTIME_HOURS=$(echo "scale=2; $RUNTIME_SECONDS / 3600" | bc)
            RUNTIME_DAYS=$(echo "scale=2; $RUNTIME_SECONDS / 86400" | bc)

            print_metric "Actual Runtime" "$RUNTIME_HOURS hours ($RUNTIME_DAYS days)"
            print_metric "First Log Entry" "$FIRST_LOG"
            print_metric "Last Log Entry" "$LAST_LOG"
        fi
    fi
fi

# ============================================
# LOG FILE SIZES
# ============================================
print_header "2. LOG FILE SIZES & GROWTH RATES"

echo ""
printf "${BLUE}%-20s %12s %15s %15s${NC}\n" "File" "Size" "Growth/Day" "Projected/Week"
echo "────────────────────────────────────────────────────────────────"

TOTAL_SIZE=0
for logfile in janus.log execution.log questdb.log postgres.log redis.log all-services.log; do
    if [ -f "$LOG_DIR/$logfile" ]; then
        SIZE=$(stat -f%z "$LOG_DIR/$logfile" 2>/dev/null || stat -c%s "$LOG_DIR/$logfile" 2>/dev/null || echo 0)
        SIZE_MB=$(echo "scale=2; $SIZE / 1048576" | bc)
        TOTAL_SIZE=$((TOTAL_SIZE + SIZE))

        # Calculate growth rate if we have runtime
        if [ -n "$RUNTIME_DAYS" ] && [ "$(echo "$RUNTIME_DAYS > 0" | bc)" -eq 1 ]; then
            GROWTH_PER_DAY=$(echo "scale=2; $SIZE_MB / $RUNTIME_DAYS" | bc)
            GROWTH_PER_WEEK=$(echo "scale=2; $GROWTH_PER_DAY * 7" | bc)

            # Color code for issues
            if [ "$SIZE" -eq 0 ] && [ "$logfile" = "all-services.log" ]; then
                printf "${RED}%-20s %10s MB %13s MB %13s MB${NC}\n" "$logfile" "$SIZE_MB" "$GROWTH_PER_DAY" "$GROWTH_PER_WEEK"
            else
                printf "%-20s %10s MB %13s MB %13s MB\n" "$logfile" "$SIZE_MB" "$GROWTH_PER_DAY" "$GROWTH_PER_WEEK"
            fi
        else
            printf "%-20s %10s MB\n" "$logfile" "$SIZE_MB"
        fi
    fi
done

TOTAL_SIZE_MB=$(echo "scale=2; $TOTAL_SIZE / 1048576" | bc)
echo "────────────────────────────────────────────────────────────────"
printf "${GREEN}%-20s %10s MB${NC}\n" "TOTAL" "$TOTAL_SIZE_MB"

# Storage projections
if [ -n "$RUNTIME_DAYS" ] && [ "$(echo "$RUNTIME_DAYS > 0" | bc)" -eq 1 ]; then
    echo ""
    print_metric "Storage Projections" ""

    DAILY_RATE=$(echo "scale=2; $TOTAL_SIZE_MB / $RUNTIME_DAYS" | bc)
    PROJ_WEEK=$(echo "scale=2; $DAILY_RATE * 7" | bc)
    PROJ_MONTH=$(echo "scale=2; $DAILY_RATE * 30" | bc)

    printf "  ${BLUE}%-30s${NC} %s MB/day\n" "Daily Growth Rate" "$DAILY_RATE"
    printf "  ${BLUE}%-30s${NC} %s MB\n" "7-Day Test (168h)" "$PROJ_WEEK"
    printf "  ${BLUE}%-30s${NC} %s MB (~%.1f GB)\n" "30-Day Test (720h)" "$PROJ_MONTH" "$(echo "scale=1; $PROJ_MONTH / 1024" | bc)"
fi

# ============================================
# SIGNAL ANALYSIS
# ============================================
print_header "3. SIGNAL GENERATION & PERSISTENCE"

if [ -f "$LOG_DIR/janus.log" ]; then
    SIGNALS_GENERATED=$(grep -c "Published signal" "$LOG_DIR/janus.log" 2>/dev/null || echo 0)
    SIGNALS_PERSISTED=$(grep -c "Persisted signal" "$LOG_DIR/janus.log" 2>/dev/null || echo 0)

    print_metric "Signals Generated" "$SIGNALS_GENERATED"
    print_metric "Signals Persisted" "$SIGNALS_PERSISTED"

    if [ "$SIGNALS_GENERATED" -gt 0 ]; then
        PERSISTENCE_RATE=$(echo "scale=4; $SIGNALS_PERSISTED * 100 / $SIGNALS_GENERATED" | bc)
        print_metric "Persistence Rate" "$PERSISTENCE_RATE%"

        if [ "$(echo "$PERSISTENCE_RATE > 99.9" | bc)" -eq 1 ]; then
            print_success "Excellent persistence rate!"
        elif [ "$(echo "$PERSISTENCE_RATE > 99" | bc)" -eq 1 ]; then
            print_warning "Good persistence rate"
        else
            print_error "Low persistence rate - investigate!"
        fi
    fi

    # Signals per hour
    if [ -n "$RUNTIME_HOURS" ] && [ "$(echo "$RUNTIME_HOURS > 0" | bc)" -eq 1 ]; then
        SIGNALS_PER_HOUR=$(echo "scale=2; $SIGNALS_GENERATED / $RUNTIME_HOURS" | bc)
        print_metric "Signals per Hour" "$SIGNALS_PER_HOUR"

        # Expected is ~720/hour (1 every 5 seconds)
        if [ "$(echo "$SIGNALS_PER_HOUR > 650" | bc)" -eq 1 ] && [ "$(echo "$SIGNALS_PER_HOUR < 800" | bc)" -eq 1 ]; then
            print_success "Signal rate within expected range (650-800/hr)"
        else
            print_warning "Signal rate outside expected range (expected ~720/hr)"
        fi
    fi

    # Signal type distribution
    echo ""
    echo -e "${BLUE}Signal Type Distribution:${NC}"
    grep "Published signal" "$LOG_DIR/janus.log" 2>/dev/null | grep -oE "\((Buy|Sell|Hold)" | sed 's/(//' | sort | uniq -c | while read count type; do
        printf "  %-10s %6d signals (%5.1f%%)\n" "$type" "$count" "$(echo "scale=1; $count * 100 / $SIGNALS_GENERATED" | bc)"
    done

    # Asset distribution (top 10)
    echo ""
    echo -e "${BLUE}Most Active Assets (Top 10):${NC}"
    grep "Published signal" "$LOG_DIR/janus.log" 2>/dev/null | grep -oE "[A-Z]+/USD" | sort | uniq -c | sort -rn | head -10 | while read count asset; do
        printf "  %-15s %6d signals\n" "$asset" "$count"
    done

    # Average confidence
    AVG_CONFIDENCE=$(grep "confidence:" "$LOG_DIR/janus.log" 2>/dev/null | grep -oE "confidence: [0-9.]+" | awk '{print $2}' | awk '{sum+=$1; count++} END {if(count>0) printf "%.2f", sum/count; else print "0"}')
    if [ -n "$AVG_CONFIDENCE" ] && [ "$AVG_CONFIDENCE" != "0" ]; then
        echo ""
        print_metric "Average Confidence Score" "$AVG_CONFIDENCE"
    fi
fi

# ============================================
# HEALTH CHECKS
# ============================================
print_header "4. SYSTEM HEALTH"

if [ -f "$LOG_DIR/janus.log" ]; then
    HEALTH_CHECKS=$(grep -c "CNS health check" "$LOG_DIR/janus.log" 2>/dev/null || echo 0)
    HEALTHY_CHECKS=$(grep "CNS health check" "$LOG_DIR/janus.log" 2>/dev/null | grep -c "All 5 modules healthy" || echo 0)

    print_metric "Total Health Checks" "$HEALTH_CHECKS"
    print_metric "Successful Health Checks" "$HEALTHY_CHECKS"

    if [ "$HEALTH_CHECKS" -gt 0 ]; then
        HEALTH_RATE=$(echo "scale=2; $HEALTHY_CHECKS * 100 / $HEALTH_CHECKS" | bc)
        print_metric "Health Check Success Rate" "$HEALTH_RATE%"

        if [ "$(echo "$HEALTH_RATE == 100" | bc)" -eq 1 ]; then
            print_success "Perfect health check rate!"
        elif [ "$(echo "$HEALTH_RATE > 95" | bc)" -eq 1 ]; then
            print_warning "Some health check failures detected"
        else
            print_error "Significant health check failures!"
        fi
    fi
fi

# ============================================
# EXECUTION ANALYSIS
# ============================================
print_header "5. EXECUTION SERVICE"

if [ -f "$LOG_DIR/execution.log" ]; then
    EXEC_SUCCESS=$(grep -c "submitted successfully" "$LOG_DIR/execution.log" 2>/dev/null || echo 0)
    BLANK_ORDER_IDS=$(grep "order_id:" "$LOG_DIR/execution.log" 2>/dev/null | grep -c "order_id: ," || echo 0)

    print_metric "Successful Submissions" "$EXEC_SUCCESS"

    if [ "$BLANK_ORDER_IDS" -gt 0 ]; then
        print_metric "Blank Order IDs" "$BLANK_ORDER_IDS"
        print_warning "Order IDs are blank - expected for paper trading?"
    fi

    # Check execution errors
    EXEC_ERRORS=$(grep -ci "error" "$LOG_DIR/execution.log" 2>/dev/null || echo 0)
    if [ "$EXEC_ERRORS" -gt 0 ]; then
        print_metric "Execution Errors" "$EXEC_ERRORS"
        if [ "$EXEC_ERRORS" -gt 100 ]; then
            print_error "High error count in execution service!"
        fi
    fi
fi

# ============================================
# ERROR ANALYSIS
# ============================================
print_header "6. ERROR ANALYSIS"

TOTAL_ERRORS=0
for logfile in janus.log execution.log questdb.log postgres.log; do
    if [ -f "$LOG_DIR/$logfile" ]; then
        ERROR_COUNT=$(grep -ci "error" "$LOG_DIR/$logfile" 2>/dev/null || echo 0)
        WARN_COUNT=$(grep -ci "warn" "$LOG_DIR/$logfile" 2>/dev/null || echo 0)

        if [ "$ERROR_COUNT" -gt 0 ] || [ "$WARN_COUNT" -gt 0 ]; then
            printf "${BLUE}%-20s${NC} %6d errors, %6d warnings\n" "$logfile" "$ERROR_COUNT" "$WARN_COUNT"
            TOTAL_ERRORS=$((TOTAL_ERRORS + ERROR_COUNT))
        fi
    fi
done

if [ "$TOTAL_ERRORS" -eq 0 ]; then
    print_success "No errors found in logs!"
elif [ "$TOTAL_ERRORS" -lt 10 ]; then
    print_warning "Minimal errors found ($TOTAL_ERRORS total)"
else
    print_error "Multiple errors found ($TOTAL_ERRORS total) - review logs"
fi

# ============================================
# ISSUES & RECOMMENDATIONS
# ============================================
print_header "7. ISSUES & RECOMMENDATIONS"

ISSUES_FOUND=0

# Check for empty all-services.log
if [ -f "$LOG_DIR/all-services.log" ]; then
    ALL_SERVICES_SIZE=$(stat -f%z "$LOG_DIR/all-services.log" 2>/dev/null || stat -c%s "$LOG_DIR/all-services.log" 2>/dev/null || echo 0)
    if [ "$ALL_SERVICES_SIZE" -eq 0 ]; then
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
        echo ""
        print_error "ISSUE #1: all-services.log is empty"
        echo "  Description: Combined log file is not collecting output"
        echo "  Impact: Medium - individual logs are working"
        echo "  Recommendation: Use individual service logs or investigate docker compose logging"
    fi
fi

# Check for blank order IDs
if [ "$BLANK_ORDER_IDS" -gt 0 ]; then
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    echo ""
    print_warning "ISSUE #$((ISSUES_FOUND)): Blank order IDs in execution logs"
    echo "  Description: Order IDs showing as blank in paper trading mode"
    echo "  Impact: Low - signals are being submitted"
    echo "  Recommendation: Verify if paper trading should generate mock order IDs"
fi

# Check for high error rate
if [ "$TOTAL_ERRORS" -gt 100 ]; then
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    echo ""
    print_error "ISSUE #$((ISSUES_FOUND)): High error count detected"
    echo "  Description: More than 100 errors found in logs"
    echo "  Impact: Variable - review error logs for severity"
    echo "  Recommendation: Analyze error patterns and root causes"
fi

if [ "$ISSUES_FOUND" -eq 0 ]; then
    echo ""
    print_success "No major issues detected!"
fi

# ============================================
# SUMMARY
# ============================================
print_header "8. SUMMARY"

echo ""
if [ -n "$RUNTIME_HOURS" ]; then
    print_metric "Test Duration" "$RUNTIME_HOURS hours ($RUNTIME_DAYS days)"
fi
print_metric "Total Log Size" "$TOTAL_SIZE_MB MB"
if [ "$SIGNALS_GENERATED" -gt 0 ]; then
    print_metric "Signals Generated" "$SIGNALS_GENERATED"
    print_metric "Success Rate" "$PERSISTENCE_RATE%"
fi
print_metric "Issues Found" "$ISSUES_FOUND"

if [ "$ISSUES_FOUND" -eq 0 ] && [ "$(echo "$PERSISTENCE_RATE > 99.9" | bc)" -eq 1 ] 2>/dev/null; then
    echo ""
    print_success "TEST PERFORMANCE: EXCELLENT ✨"
elif [ "$ISSUES_FOUND" -le 2 ] && [ "$(echo "$PERSISTENCE_RATE > 99" | bc)" -eq 1 ] 2>/dev/null; then
    echo ""
    echo -e "${GREEN}TEST PERFORMANCE: GOOD ✓${NC}"
else
    echo ""
    echo -e "${YELLOW}TEST PERFORMANCE: NEEDS ATTENTION ⚠${NC}"
fi

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}Analysis complete. Review issues section for action items.${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""
