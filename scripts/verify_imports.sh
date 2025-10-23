#!/bin/bash
# Verify imports and run tests for Phase 1.2
# This script checks for legacy imports and runs the test suite

set -e

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Phase 1.2: Import Verification & Test Execution        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Change to project root
cd "$(dirname "$0")/.."

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Checking for legacy import patterns"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

LEGACY_IMPORTS_FOUND=0

# Check for 'from config import' (legacy pattern)
echo "Checking for 'from config import' pattern..."
if grep -r "^from config import" src/ --include="*.py" 2>/dev/null; then
    echo "⚠ WARNING: Found legacy 'from config import' statements"
    LEGACY_IMPORTS_FOUND=1
else
    echo "✓ No 'from config import' patterns found"
fi

# Check for 'from shared_python' (microservices artifact)
echo "Checking for 'from shared_python' pattern..."
if grep -r "^from shared_python" src/ --include="*.py" 2>/dev/null; then
    echo "⚠ WARNING: Found legacy 'from shared_python' statements"
    LEGACY_IMPORTS_FOUND=1
else
    echo "✓ No 'from shared_python' patterns found"
fi

# Check for 'import config' (legacy pattern)
echo "Checking for 'import config' pattern..."
if grep -r "^import config$" src/ --include="*.py" 2>/dev/null; then
    echo "⚠ WARNING: Found legacy 'import config' statements"
    LEGACY_IMPORTS_FOUND=1
else
    echo "✓ No 'import config' patterns found"
fi

echo ""
if [ $LEGACY_IMPORTS_FOUND -eq 0 ]; then
    echo "✓ All imports are using the new framework.config pattern"
else
    echo "⚠ Legacy imports found - need to update to framework.config.constants"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. Verifying framework.config.constants exists"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "src/framework/config/constants.py" ]; then
    echo "✓ framework.config.constants module exists"
    
    # Check for required constants
    echo "Checking for required constants..."
    REQUIRED_CONSTANTS=("SYMBOLS" "MAINS" "ALTS" "FEE_RATE" "RISK_PER_TRADE" "DATABASE_URL")
    
    for const in "${REQUIRED_CONSTANTS[@]}"; do
        if grep -q "^$const = " src/framework/config/constants.py; then
            echo "  ✓ $const defined"
        else
            echo "  ⚠ $const NOT defined"
        fi
    done
else
    echo "✗ framework.config.constants module NOT FOUND"
    echo "  Need to create: src/framework/config/constants.py"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Checking current import usage"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

GOOD_IMPORTS=$(grep -r "from framework.config.constants import" src/ --include="*.py" 2>/dev/null | wc -l)
echo "✓ Files using framework.config.constants: $GOOD_IMPORTS"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Running pytest (if available)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v pytest &> /dev/null; then
    echo "Running pytest test collection..."
    pytest tests/ --co -q 2>&1 | head -20
    
    echo ""
    echo "Running tests..."
    pytest tests/unit/test_api/ -v --tb=short 2>&1 | tail -30
    
else
    echo "⚠ pytest not available in this environment"
    echo "  Run tests in Docker: docker-compose exec web pytest tests/ -v"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
if [ $LEGACY_IMPORTS_FOUND -eq 0 ]; then
    echo "✓ Phase 1.2 Import Migration: COMPLETE"
    echo ""
    echo "Next steps:"
    echo "  1. Start Docker services: make up"
    echo "  2. Run full test suite: docker-compose exec web pytest tests/ -v"
    echo "  3. Fix any failing tests"
    echo "  4. Verify 34/34 tests passing"
else
    echo "⚠ Phase 1.2 Import Migration: IN PROGRESS"
    echo ""
    echo "Next steps:"
    echo "  1. Update remaining legacy imports"
    echo "  2. Re-run this script to verify"
    echo "  3. Run tests in Docker"
fi
echo ""
