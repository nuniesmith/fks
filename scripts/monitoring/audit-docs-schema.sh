#!/bin/bash
# Documentation Schema Audit Script
# Purpose: Validate documentation organization and quality locally
# Usage: ./scripts/audit-docs-schema.sh [--fix] [--verbose]

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
FIX_MODE=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --fix)
            FIX_MODE=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Usage: $0 [--fix] [--verbose]"
            echo "  --fix      Attempt to auto-fix simple issues"
            echo "  --verbose  Show detailed output"
            exit 1
            ;;
    esac
done

echo "================================================================================"
echo -e "${BLUE}Documentation Schema Audit${NC}"
echo "================================================================================"
echo ""

# Verify we're in project root
if [ ! -d "docs" ] || [ ! -d "src/audit" ]; then
    echo -e "${RED}❌ Error: Must run from project root${NC}"
    exit 1
fi

# Step 1: Build audit CLI
echo -e "${BLUE}Step 1: Building audit CLI...${NC}"
cd src/audit
cargo build --release --bin audit-cli 2>&1 | tail -5
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Build failed${NC}"
    exit 1
fi
cd ../..
echo -e "${GREEN}✅ Audit CLI built${NC}"
echo ""

# Step 2: Run documentation schema audit
echo -e "${BLUE}Step 2: Running documentation schema audit...${NC}"
src/audit/target/release/audit-cli static \
    docs \
    --output DOCS_SCHEMA_AUDIT_REPORT.md

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Audit failed to run${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Audit completed${NC}"
echo ""

# Step 3: Parse results
echo -e "${BLUE}Step 3: Analyzing results...${NC}"
echo ""

CRITICAL_COUNT=$(grep -c "CRITICAL" DOCS_SCHEMA_AUDIT_REPORT.md 2>/dev/null || echo 0)
HIGH_COUNT=$(grep -c "HIGH" DOCS_SCHEMA_AUDIT_REPORT.md 2>/dev/null || echo 0)
MEDIUM_COUNT=$(grep -c "MEDIUM" DOCS_SCHEMA_AUDIT_REPORT.md 2>/dev/null || echo 0)
LOW_COUNT=$(grep -c "LOW" DOCS_SCHEMA_AUDIT_REPORT.md 2>/dev/null || echo 0)

echo "📊 Findings Summary:"
echo "  • Critical: $CRITICAL_COUNT"
echo "  • High:     $HIGH_COUNT"
echo "  • Medium:   $MEDIUM_COUNT"
echo "  • Low:      $LOW_COUNT"
echo ""

# Step 4: Show critical issues
if [ $CRITICAL_COUNT -gt 0 ]; then
    echo -e "${RED}❌ CRITICAL ISSUES FOUND:${NC}"
    grep -A 5 "CRITICAL" DOCS_SCHEMA_AUDIT_REPORT.md | head -30
    echo ""
    echo -e "${YELLOW}⚠️  Fix critical issues before committing!${NC}"
    echo ""
fi

# Step 5: Common fixes (if --fix mode)
if [ "$FIX_MODE" = true ]; then
    echo -e "${BLUE}Step 4: Attempting auto-fixes...${NC}"
    FIXES_APPLIED=0

    # Fix 1: Move status files to archive
    for file in docs/architecture/*STATUS* docs/architecture/*PROGRESS* docs/architecture/*COMPLETE*; do
        if [ -f "$file" ]; then
            BASENAME=$(basename "$file")
            echo "  → Moving $BASENAME to archive/status-logs/"
            mv "$file" "docs/archive/status-logs/"
            FIXES_APPLIED=$((FIXES_APPLIED + 1))
        fi
    done

    # Fix 2: Move summary files to archive
    for file in docs/operations/*SUMMARY* docs/operations/*FIXES*; do
        if [ -f "$file" ]; then
            BASENAME=$(basename "$file")
            echo "  → Moving $BASENAME to archive/fixes/"
            mv "$file" "docs/archive/fixes/"
            FIXES_APPLIED=$((FIXES_APPLIED + 1))
        fi
    done

    # Fix 3: Remove auto-generated API docs from Git
    if [ -d "docs/api/rust" ] && [ -n "$(ls -A docs/api/rust/*.html 2>/dev/null)" ]; then
        echo "  → Removing auto-generated HTML from docs/api/rust/"
        git rm -r --cached docs/api/rust/*.html 2>/dev/null || true
        FIXES_APPLIED=$((FIXES_APPLIED + 1))
    fi

    # Fix 4: Ensure .gitignore has proper exclusions
    if ! grep -q "docs/api/rust/" .gitignore 2>/dev/null; then
        echo "  → Adding docs/api/ exclusions to .gitignore"
        echo "" >> .gitignore
        echo "# Auto-generated documentation" >> .gitignore
        echo "docs/api/rust/" >> .gitignore
        echo "docs/api/python/" >> .gitignore
        FIXES_APPLIED=$((FIXES_APPLIED + 1))
    fi

    echo ""
    echo -e "${GREEN}✅ Applied $FIXES_APPLIED automatic fixes${NC}"
    echo ""

    # Re-run audit to check improvements
    if [ $FIXES_APPLIED -gt 0 ]; then
        echo -e "${BLUE}Re-running audit after fixes...${NC}"
        src/audit/target/release/audit-cli static \
            docs \
            --output DOCS_SCHEMA_AUDIT_REPORT.md

        NEW_CRITICAL=$(grep -c "CRITICAL" DOCS_SCHEMA_AUDIT_REPORT.md 2>/dev/null || echo 0)
        echo "Critical issues: $CRITICAL_COUNT → $NEW_CRITICAL"
        echo ""
    fi
fi

# Step 6: Detailed report (if verbose)
if [ "$VERBOSE" = true ]; then
    echo "================================================================================"
    echo -e "${BLUE}Detailed Report:${NC}"
    echo "================================================================================"
    cat DOCS_SCHEMA_AUDIT_REPORT.md
fi

# Step 7: Quick fixes guidance
if [ $CRITICAL_COUNT -gt 0 ] || [ $HIGH_COUNT -gt 0 ]; then
    echo "================================================================================"
    echo -e "${YELLOW}Recommended Actions:${NC}"
    echo "================================================================================"
    echo ""
    echo "1. Review the full report:"
    echo "   cat DOCS_SCHEMA_AUDIT_REPORT.md"
    echo ""
    echo "2. Run with auto-fix to resolve common issues:"
    echo "   ./scripts/audit-docs-schema.sh --fix"
    echo ""
    echo "3. Common manual fixes:"
    echo "   • Move status/progress files to docs/archive/"
    echo "   • Add missing README.md indices"
    echo "   • Fix broken relative links"
    echo "   • Complete placeholder content"
    echo ""
    echo "4. After fixes, re-run this script to verify"
    echo ""
fi

# Step 8: Summary
echo "================================================================================"
if [ $CRITICAL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ Documentation schema validation PASSED${NC}"
    echo "================================================================================"
    exit 0
else
    echo -e "${RED}❌ Documentation schema validation FAILED${NC}"
    echo "================================================================================"
    echo ""
    echo "Fix critical issues before committing documentation changes."
    exit 1
fi
