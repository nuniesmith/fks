#!/bin/bash

# FKS Trading Systems - Simple Build Script
# Creates source-only package for NinjaTrader 8

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SRC_DIR="$PROJECT_ROOT/src"
BUILD_DIR="$PROJECT_ROOT/build"
PACKAGES_DIR="$BUILD_DIR/packages"
TEMPLATES_DIR="$PROJECT_ROOT/templates"

PACKAGE_NAME="FKS_TradingSystem"
VERSION="1.0.0"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[BUILD]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

echo "=================================="
echo "   FKS Trading Systems Builder"
echo "=================================="
echo

# Create directories
log "Setting up build directories..."
mkdir -p "$PACKAGES_DIR"
mkdir -p "$BUILD_DIR/temp"

# Create temporary package structure
TEMP_PACKAGE="$BUILD_DIR/temp/source_package"
rm -rf "$TEMP_PACKAGE"
mkdir -p "$TEMP_PACKAGE/bin/Custom/"{AddOns,Indicators,Strategies}

# Copy source files
log "Copying source files..."
cp "$SRC_DIR/AddOns"/*.cs "$TEMP_PACKAGE/bin/Custom/AddOns/"
cp "$SRC_DIR/Indicators"/*.cs "$TEMP_PACKAGE/bin/Custom/Indicators/"
cp "$SRC_DIR/Strategies"/*.cs "$TEMP_PACKAGE/bin/Custom/Strategies/"

# Copy manifest and info
cp "$TEMPLATES_DIR/manifest-source.xml" "$TEMP_PACKAGE/manifest.xml"
cp "$TEMPLATES_DIR/Info.xml" "$TEMP_PACKAGE/"

# Create package
PACKAGE_FILE="${PACKAGE_NAME}_SOURCE_v${VERSION}.zip"
PACKAGE_PATH="$PACKAGES_DIR/$PACKAGE_FILE"

log "Creating package..."
cd "$TEMP_PACKAGE"
zip -r "$PACKAGE_PATH" . > /dev/null
cd - > /dev/null

# Get package info
PACKAGE_SIZE=$(du -h "$PACKAGE_PATH" | cut -f1)
FILE_COUNT=$(find "$TEMP_PACKAGE" -type f | wc -l)

success "Package created: $PACKAGE_FILE"
echo "Size: $PACKAGE_SIZE"
echo "Files: $FILE_COUNT"
echo "Location: $PACKAGE_PATH"

# Clean up temp files
rm -rf "$TEMP_PACKAGE"

echo
echo "✅ Build completed successfully!"
