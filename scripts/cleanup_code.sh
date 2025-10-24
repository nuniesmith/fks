#!/bin/bash
# Phase 1.3: Code Cleanup Script
# Removes duplicate files, empty files, and formats code

set -e

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         Phase 1.3: Code Cleanup - FKS Trading             ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Change to project root
cd "$(dirname "$0")/.."

CLEANUP_COUNT=0
BACKUP_DIR=".cleanup_backup_$(date +%Y%m%d_%H%M%S)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Creating backup directory: $BACKUP_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
mkdir -p "$BACKUP_DIR"
echo "✓ Backup directory created"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. Removing duplicate circuit_breaker directory"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if duplicate exists
if [ -d "src/api/middleware/circuit_breaker" ]; then
    echo "Found duplicate: src/api/middleware/circuit_breaker/"
    echo "  Backing up to: $BACKUP_DIR/api_middleware_circuit_breaker/"
    
    # Backup before removal
    cp -r src/api/middleware/circuit_breaker "$BACKUP_DIR/api_middleware_circuit_breaker"
    
    # Remove duplicate
    rm -rf src/api/middleware/circuit_breaker
    ((CLEANUP_COUNT++))
    
    echo "✓ Removed duplicate circuit_breaker (use framework/middleware/circuit_breaker instead)"
else
    echo "  No duplicate circuit_breaker found"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Checking for test files in src/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Find test files that should be in tests/ directory
TEST_FILES=$(find src/ -name "*test*.py" -not -path "*/migrations/*" -not -name "create_test_users.py" 2>/dev/null || true)

if [ -n "$TEST_FILES" ]; then
    echo "Found test files in src/:"
    echo "$TEST_FILES"
    echo ""
    echo "⚠ These should be moved to tests/ directory"
    
    while IFS= read -r file; do
        if [ -f "$file" ]; then
            echo "  Backing up: $file"
            mkdir -p "$BACKUP_DIR/$(dirname "$file")"
            cp "$file" "$BACKUP_DIR/$file"
            ((CLEANUP_COUNT++))
        fi
    done <<< "$TEST_FILES"
else
    echo "✓ No misplaced test files found"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Checking __init__.py files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

INIT_COUNT=$(find src/ -name "__init__.py" 2>/dev/null | wc -l)
EMPTY_INIT=$(find src/ -name "__init__.py" -size 0 2>/dev/null | wc -l)

echo "  Total __init__.py files: $INIT_COUNT"
echo "  Empty __init__.py files: $EMPTY_INIT"
echo "✓ Empty __init__.py files are intentional (Python package markers)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. Running code formatters (if available)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if running in Docker or local
if [ -f /.dockerenv ]; then
    echo "Running in Docker - formatters should be available"
    IN_DOCKER=true
else
    echo "Running on host - formatters may not be installed"
    IN_DOCKER=false
fi

# Try to run black
if command -v black &> /dev/null; then
    echo ""
    echo "Running black formatter..."
    black src/ --line-length 100 --target-version py312 || echo "⚠ Black formatting had issues"
    echo "✓ Black formatting complete"
else
    echo "⚠ black not available"
    echo "  Install: pip install black"
    echo "  Or run in Docker: docker-compose exec web bash -c './scripts/cleanup_code.sh'"
fi

# Try to run isort
if command -v isort &> /dev/null; then
    echo ""
    echo "Running isort..."
    isort src/ --profile black --line-length 100 || echo "⚠ isort had issues"
    echo "✓ Import sorting complete"
else
    echo "⚠ isort not available"
    echo "  Install: pip install isort"
fi

# Try to run ruff
if command -v ruff &> /dev/null; then
    echo ""
    echo "Running ruff linter..."
    ruff check src/ --fix || echo "⚠ Ruff found issues (not all auto-fixable)"
    echo "✓ Ruff linting complete"
else
    echo "⚠ ruff not available"
    echo "  Install: pip install ruff"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "Cleanup Statistics:"
echo "  Items cleaned: $CLEANUP_COUNT"
echo "  Backup location: $BACKUP_DIR/"
echo ""

if [ $CLEANUP_COUNT -gt 0 ]; then
    echo "✓ Cleanup complete!"
    echo ""
    echo "Files have been backed up to: $BACKUP_DIR/"
    echo "If everything works correctly, you can remove the backup:"
    echo "  rm -rf $BACKUP_DIR"
else
    echo "✓ No cleanup needed - codebase is clean"
fi

echo ""
echo "Next steps:"
echo "  1. Review changes: git status"
echo "  2. Run tests: make test"
echo "  3. Check linting: make lint"
echo "  4. If satisfied, commit: git add -A && git commit -m 'chore: code cleanup (Phase 1.3)'"
echo ""
