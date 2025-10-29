#!/bin/bash

# FKS Trading Systems - Clean Script
# Removes all build artifacts and temporary files

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[CLEAN]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Clean build artifacts
log "Cleaning build artifacts..."
rm -rf "$PROJECT_ROOT/build"
rm -rf "$PROJECT_ROOT/bin"
rm -rf "$PROJECT_ROOT/src/obj"

# Clean temporary files
log "Cleaning temporary files..."
find "$PROJECT_ROOT" -name "*.tmp" -delete 2>/dev/null || true
find "$PROJECT_ROOT" -name ".DS_Store" -delete 2>/dev/null || true
find "$PROJECT_ROOT" -name "Thumbs.db" -delete 2>/dev/null || true

# Clean old package files (keep only in build/packages)
log "Cleaning old package files..."
find "$PROJECT_ROOT" -maxdepth 1 -name "FKS_TradingSystem*.zip" -delete 2>/dev/null || true
find "$PROJECT_ROOT" -maxdepth 1 -name "*.dll" -delete 2>/dev/null || true

# Clean test directories
log "Cleaning test directories..."
rm -rf "$PROJECT_ROOT"/temp_*
rm -rf "$PROJECT_ROOT"/fks_*
rm -rf "$PROJECT_ROOT"/test_*

success "Clean completed successfully!"

# Show remaining files
echo
echo "Remaining project structure:"
tree "$PROJECT_ROOT" -I 'node_modules|.git|*.log' -L 3 2>/dev/null || \
ls -la "$PROJECT_ROOT"
