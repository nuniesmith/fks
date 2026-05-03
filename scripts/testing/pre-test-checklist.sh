#!/bin/bash
#
# FKS Pre-Test Checklist Script
# ==============================
#
# Validates system is ready for a fresh paper trading test
#
# Usage:
#   ./scripts/pre-test-checklist.sh [--duration HOURS]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
TEST_DURATION=168  # Default to 1 week
while [[ $# -gt 0 ]]; do
    case $1 in
        --duration)
            TEST_DURATION="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--duration HOURS]"
            echo ""
            echo "Validates system is ready for paper trading test"
            echo ""
            echo "Options:"
            echo "  --duration HOURS    Planned test duration (default: 168)"
            echo "  --help             Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check counters
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0
CHECKS_TOTAL=0

# Function to run check
check() {
    local status=$1
    local message=$2
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))

    if [ "$status" = "PASS" ]; then
        echo -e "  ${GREEN}✓${NC} $message"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    elif [ "$status" = "FAIL" ]; then
        echo -e "  ${RED}✗${NC} $message"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
    elif [ "$status" = "WARN" ]; then
        echo -e "  ${YELLOW}⚠${NC} $message"
        CHECKS_WARNING=$((CHECKS_WARNING + 1))
    else
        echo -e "  ${BLUE}ℹ${NC} $message"
    fi
}

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       FKS Pre-Test Checklist                             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Test Duration: ${TEST_DURATION} hours${NC}"
echo -e "${CYAN}Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")${NC}"
echo ""

# ============================================
# 1. System Requirements
# ============================================
echo -e "${YELLOW}[1/8] System Requirements${NC}"

# Check Docker
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
    check "PASS" "Docker installed (version $DOCKER_VERSION)"
else
    check "FAIL" "Docker is not installed"
fi

# Check Docker Compose
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || echo "unknown")
    check "PASS" "Docker Compose installed (version $COMPOSE_VERSION)"
else
    check "FAIL" "Docker Compose is not installed"
fi

# Check Docker daemon
if docker info &> /dev/null; then
    check "PASS" "Docker daemon is running"
else
    check "FAIL" "Docker daemon is not running"
fi

echo ""

# ============================================
# 2. Disk Space
# ============================================
echo -e "${YELLOW}[2/8] Disk Space${NC}"

# Calculate required space based on duration
REQUIRED_MB=$((TEST_DURATION * 42 / 24))  # 42 MB per day
REQUIRED_WITH_BUFFER=$((REQUIRED_MB * 3 / 2))  # 50% buffer

# Check available space
AVAILABLE_KB=$(df "$PROJECT_ROOT" | tail -1 | awk '{print $4}')
AVAILABLE_MB=$((AVAILABLE_KB / 1024))

if [ "$AVAILABLE_MB" -gt "$REQUIRED_WITH_BUFFER" ]; then
    check "PASS" "Sufficient disk space (${AVAILABLE_MB} MB available, ${REQUIRED_WITH_BUFFER} MB needed)"
elif [ "$AVAILABLE_MB" -gt "$REQUIRED_MB" ]; then
    check "WARN" "Limited disk space (${AVAILABLE_MB} MB available, ${REQUIRED_WITH_BUFFER} MB recommended)"
else
    check "FAIL" "Insufficient disk space (${AVAILABLE_MB} MB available, ${REQUIRED_MB} MB minimum)"
fi

echo ""

# ============================================
# 3. Environment Configuration
# ============================================
echo -e "${YELLOW}[3/8] Environment Configuration${NC}"

# Check for .env file
if [ -f "$PROJECT_ROOT/infrastructure/compose/.env" ]; then
    check "PASS" ".env file exists"

    # Check for required passwords
    if grep -q "POSTGRES_PASSWORD=" "$PROJECT_ROOT/infrastructure/compose/.env" 2>/dev/null; then
        check "PASS" "POSTGRES_PASSWORD is set"
    else
        check "FAIL" "POSTGRES_PASSWORD not found in .env"
    fi

    if grep -q "REDIS_PASSWORD=" "$PROJECT_ROOT/infrastructure/compose/.env" 2>/dev/null; then
        check "PASS" "REDIS_PASSWORD is set"
    else
        check "FAIL" "REDIS_PASSWORD not found in .env"
    fi

    if grep -q "QUESTDB_PASSWORD=" "$PROJECT_ROOT/infrastructure/compose/.env" 2>/dev/null; then
        check "PASS" "QUESTDB_PASSWORD is set"
    else
        check "WARN" "QUESTDB_PASSWORD not found in .env (optional)"
    fi
else
    check "FAIL" ".env file not found at infrastructure/compose/.env"
fi

echo ""

# ============================================
# 4. Code Changes
# ============================================
echo -e "${YELLOW}[4/8] Code Changes Verification${NC}"

cd "$PROJECT_ROOT"

# Check if Redis fix is applied
if grep -q "client: redis::Client" src/janus/crates/cns/src/probes.rs 2>/dev/null; then
    check "PASS" "Redis health probe fix applied (reuses client)"
else
    check "FAIL" "Redis health probe fix NOT applied - will get false alerts"
fi

# Check Redis timeout in docker-compose
if grep -A 2 "timeout" infrastructure/compose/docker-compose.prod.yml 2>/dev/null | grep -q "3600\|0"; then
    check "PASS" "Redis timeout increased (3600s or disabled)"
else
    check "WARN" "Redis timeout still at 300s (may cause issues)"
fi

# Check for uncommitted changes
if git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
    check "PASS" "No uncommitted changes"
else
    check "WARN" "Uncommitted changes detected"
    UNCOMMITTED=$(git status --short 2>/dev/null | wc -l)
    echo -e "    ${YELLOW}$UNCOMMITTED files modified${NC}"
fi

echo ""

# ============================================
# 5. Running Services
# ============================================
echo -e "${YELLOW}[5/8] Running Services${NC}"

# Check for running FKS containers
RUNNING_CONTAINERS=$(docker ps --filter "name=fks_" --format "{{.Names}}" 2>/dev/null | wc -l)

if [ "$RUNNING_CONTAINERS" -eq 0 ]; then
    check "PASS" "No existing FKS containers running (clean state)"
else
    check "WARN" "$RUNNING_CONTAINERS FKS containers already running"
    docker ps --filter "name=fks_" --format "    - {{.Names}} ({{.Status}})" 2>/dev/null
    echo -e "    ${YELLOW}Consider stopping existing test first${NC}"
fi

# Check for existing test processes
if pgrep -f "start-paper-trading-test" > /dev/null 2>&1; then
    check "WARN" "Existing test script is running"
else
    check "PASS" "No existing test scripts running"
fi

echo ""

# ============================================
# 6. Old Test Data
# ============================================
echo -e "${YELLOW}[6/8] Old Test Data${NC}"

# Check for old test directories
if [ -d "$PROJECT_ROOT/logs" ]; then
    OLD_TESTS=$(find "$PROJECT_ROOT/logs" -mindepth 1 -maxdepth 1 -type d -name "*hr-test-*" 2>/dev/null | wc -l)

    if [ "$OLD_TESTS" -eq 0 ]; then
        check "PASS" "No old test directories found"
    else
        check "WARN" "$OLD_TESTS old test directories found in logs/"
        echo -e "    ${YELLOW}Consider cleaning up with: ./scripts/cleanup-test-data.sh --logs${NC}"
    fi
else
    check "PASS" "No logs directory (clean state)"
fi

# Check for old env files
OLD_ENV_FILES=$(find "$PROJECT_ROOT/infrastructure/compose" -maxdepth 1 -name ".env.*hr-test" 2>/dev/null | wc -l)

if [ "$OLD_ENV_FILES" -eq 0 ]; then
    check "PASS" "No old test env files found"
else
    check "WARN" "$OLD_ENV_FILES old test env files found"
    echo -e "    ${YELLOW}Consider cleaning up with: ./scripts/cleanup-test-data.sh --env-files${NC}"
fi

echo ""

# ============================================
# 7. Network & Connectivity
# ============================================
echo -e "${YELLOW}[7/8] Network & Connectivity${NC}"

# Check Docker network
if docker network ls | grep -q fks-network; then
    check "PASS" "Docker network 'fks-network' exists"
else
    check "WARN" "Docker network 'fks-network' not found (will be created)"
fi

# Check internet connectivity
if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
    check "PASS" "Internet connectivity available"
else
    check "WARN" "Internet connectivity check failed (may impact some features)"
fi

echo ""

# ============================================
# 8. Test Scripts
# ============================================
echo -e "${YELLOW}[8/8] Test Scripts${NC}"

# Check test script exists
if [ -f "$PROJECT_ROOT/scripts/start-paper-trading-test.sh" ]; then
    check "PASS" "Test script exists"

    if [ -x "$PROJECT_ROOT/scripts/start-paper-trading-test.sh" ]; then
        check "PASS" "Test script is executable"
    else
        check "FAIL" "Test script is not executable (run: chmod +x scripts/start-paper-trading-test.sh)"
    fi
else
    check "FAIL" "Test script not found at scripts/start-paper-trading-test.sh"
fi

# Check analysis script
if [ -f "$PROJECT_ROOT/scripts/analyze-paper-test-logs.sh" ]; then
    check "PASS" "Analysis script exists"
else
    check "WARN" "Analysis script not found (optional)"
fi

# Check cleanup script
if [ -f "$PROJECT_ROOT/scripts/cleanup-test-data.sh" ]; then
    check "PASS" "Cleanup script exists"
else
    check "WARN" "Cleanup script not found (optional)"
fi

echo ""

# ============================================
# Summary
# ============================================
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Checklist Summary${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Total checks:    $CHECKS_TOTAL"
echo -e "  ${GREEN}Passed:          $CHECKS_PASSED${NC}"
echo -e "  ${YELLOW}Warnings:        $CHECKS_WARNING${NC}"
echo -e "  ${RED}Failed:          $CHECKS_FAILED${NC}"
echo ""

# Determine overall status
if [ "$CHECKS_FAILED" -eq 0 ]; then
    if [ "$CHECKS_WARNING" -eq 0 ]; then
        echo -e "${GREEN}✅ READY TO START TEST${NC}"
        echo ""
        echo -e "${CYAN}Run test with:${NC}"
        echo -e "  ./scripts/start-paper-trading-test.sh --duration $TEST_DURATION"
        EXIT_CODE=0
    else
        echo -e "${YELLOW}⚠️  READY WITH WARNINGS${NC}"
        echo ""
        echo -e "${YELLOW}Review warnings above before starting test.${NC}"
        echo ""
        echo -e "${CYAN}If warnings are acceptable, run test with:${NC}"
        echo -e "  ./scripts/start-paper-trading-test.sh --duration $TEST_DURATION"
        EXIT_CODE=0
    fi
else
    echo -e "${RED}❌ NOT READY - FIX FAILURES FIRST${NC}"
    echo ""
    echo -e "${RED}Please fix the failed checks above before starting test.${NC}"
    EXIT_CODE=1
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

exit $EXIT_CODE
