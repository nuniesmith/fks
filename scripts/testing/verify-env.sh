#!/bin/bash

# FKS Environment Verification Script
# Quick check to ensure environment is ready for deployment

echo "🔍 FKS Environment Verification"
echo "================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_TOTAL=0

pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
    ((CHECKS_TOTAL++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
    ((CHECKS_TOTAL++))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Navigate to repo root
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$REPO_ROOT"

echo "Repository: $REPO_ROOT"
echo ""

# Check 1: .env file exists
echo "Checking environment configuration..."
if [ -f ".env" ]; then
    pass ".env file exists"
else
    fail ".env file missing"
    echo ""
    echo "Create .env file from template:"
    echo "  cp .env.example .env"
    echo "  # Then edit .env with your settings"
    exit 1
fi

# Check 2: Required environment variables
echo ""
echo "Checking required variables..."

REQUIRED_VARS=(
    "POSTGRES_PASSWORD"
    "REDIS_PASSWORD"
    "QUESTDB_HTTP_PORT"
    "TRADING_MODE"
)

for var in "${REQUIRED_VARS[@]}"; do
    if grep -q "^${var}=" .env 2>/dev/null; then
        VALUE=$(grep "^${var}=" .env | cut -d'=' -f2- 2>/dev/null || echo "")
        if [ -n "$VALUE" ]; then
            pass "$var is set"
        else
            fail "$var is empty"
        fi
    else
        fail "$var not found in .env"
    fi
done

# Check 3: Trading mode (CRITICAL SAFETY CHECK)
echo ""
echo "Checking trading mode (SAFETY CHECK)..."

TRADING_MODE=$(grep "^TRADING_MODE=" .env 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" || echo "")
if [ "$TRADING_MODE" = "simulation" ] || [ "$TRADING_MODE" = "paper" ]; then
    pass "Trading mode: $TRADING_MODE (SAFE)"
elif [ "$TRADING_MODE" = "live" ]; then
    echo -e "${RED}✗ WARNING: LIVE TRADING MODE DETECTED!${NC}"
    echo ""
    echo "Your .env file has TRADING_MODE=live"
    echo "This will execute REAL TRADES with REAL MONEY!"
    echo ""
    echo "For paper trading, change to:"
    echo "  TRADING_MODE=simulation"
    echo ""
    ((CHECKS_FAILED++))
    ((CHECKS_TOTAL++))
else
    fail "Trading mode unclear or not set: '$TRADING_MODE'"
fi

# Check 4: Real orders flag
REAL_ORDERS=$(grep "^REAL_ORDERS_ENABLED=" .env 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" || echo "")
if [ "$REAL_ORDERS" = "false" ] || [ "$REAL_ORDERS" = "FALSE" ] || [ "$REAL_ORDERS" = "0" ]; then
    pass "Real orders disabled (SAFE)"
elif [ "$REAL_ORDERS" = "true" ] || [ "$REAL_ORDERS" = "TRUE" ] || [ "$REAL_ORDERS" = "1" ]; then
    echo -e "${RED}✗ WARNING: REAL ORDERS ENABLED!${NC}"
    ((CHECKS_FAILED++))
    ((CHECKS_TOTAL++))
else
    warn "REAL_ORDERS_ENABLED not found (defaulting to disabled)"
fi

# Check 5: Docker
echo ""
echo "Checking Docker..."

if command -v docker &> /dev/null; then
    pass "Docker installed"

    if docker info > /dev/null 2>&1; then
        pass "Docker daemon running"
    else
        fail "Docker daemon not running"
    fi
else
    fail "Docker not installed"
fi

if command -v docker compose &> /dev/null; then
    pass "Docker Compose v2 available"
elif command -v docker-compose &> /dev/null; then
    warn "Docker Compose v1 detected (v2 recommended)"
    ((CHECKS_TOTAL++))
else
    fail "Docker Compose not installed"
fi

# Check 6: Required files
echo ""
echo "Checking required files..."

REQUIRED_FILES=(
    "infrastructure/compose/docker-compose.yml"
    "Cargo.toml"
    "scripts/testing/run-integration-tests.sh"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        pass "$file"
    else
        fail "$file not found"
    fi
done

# Check 7: Disk space
echo ""
echo "Checking resources..."

AVAILABLE_GB=$(df -BG . 2>/dev/null | tail -1 | awk '{print $4}' | sed 's/G//' || echo "0")
if [ "$AVAILABLE_GB" -ge 50 ]; then
    pass "Disk space: ${AVAILABLE_GB}GB available"
elif [ "$AVAILABLE_GB" -ge 20 ]; then
    warn "Disk space: ${AVAILABLE_GB}GB available (minimum 50GB recommended)"
    ((CHECKS_TOTAL++))
else
    fail "Disk space: ${AVAILABLE_GB}GB available (need at least 20GB)"
fi

# Check 8: Memory
TOTAL_MEM_GB=$(free -g 2>/dev/null | grep Mem | awk '{print $2}' || echo "0")
if [ "$TOTAL_MEM_GB" -ge 16 ]; then
    pass "Memory: ${TOTAL_MEM_GB}GB total"
elif [ "$TOTAL_MEM_GB" -ge 8 ]; then
    warn "Memory: ${TOTAL_MEM_GB}GB total (16GB recommended)"
    ((CHECKS_TOTAL++))
else
    warn "Memory: ${TOTAL_MEM_GB}GB total (may need to limit services)"
    ((CHECKS_TOTAL++))
fi

# Summary
echo ""
echo "================================"
echo "Verification Summary"
echo "================================"
echo "Total checks: $CHECKS_TOTAL"
echo -e "Passed:       ${GREEN}$CHECKS_PASSED${NC}"
echo -e "Failed:       ${RED}$CHECKS_FAILED${NC}"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ Environment ready!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Run integration tests:"
    echo "     ./scripts/testing/run-integration-tests.sh"
    echo ""
    echo "  2. Or start services directly:"
    echo "     docker compose -f infrastructure/compose/docker-compose.yml --env-file .env up -d"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Environment has issues${NC}"
    echo ""
    echo "Please fix the issues above before proceeding."
    echo ""
    exit 1
fi
