#!/bin/bash
set -e

# FKS NinjaTrader DLL Build & Package Script
# This script builds a proper external development DLL for NinjaTrader 8

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
NINJA_DIR="$ROOT_DIR/src/ninja"
SRC_DIR="$NINJA_DIR/src"
BIN_DIR="$NINJA_DIR/bin"
PACKAGES_DIR="$NINJA_DIR/packages"

echo -e "${BLUE}🚀 FKS NinjaTrader DLL Builder${NC}"
echo -e "${BLUE}================================${NC}"

# Function to print colored messages
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# Check if .NET is available
if ! command -v dotnet &> /dev/null; then
    log_error ".NET SDK not found. Please install .NET Framework 4.8 SDK or .NET Core SDK with Framework targeting."
    exit 1
fi

log_info "Checking project structure..."

# Verify project structure
if [ ! -f "$SRC_DIR/FKS.csproj" ]; then
    log_error "FKS.csproj not found at $SRC_DIR/FKS.csproj"
    exit 1
fi

if [ ! -f "$NINJA_DIR/manifest.xml" ]; then
    log_error "manifest.xml not found at $NINJA_DIR/manifest.xml"
    exit 1
fi

log_success "Project structure verified"

# Clean previous builds
log_info "Cleaning previous builds..."
if [ -d "$BIN_DIR" ]; then
    rm -rf "$BIN_DIR"
fi
if [ -d "$PACKAGES_DIR" ]; then
    rm -rf "$PACKAGES_DIR"
fi

# Create directories
mkdir -p "$BIN_DIR"
mkdir -p "$PACKAGES_DIR"

log_success "Build directories cleaned and created"

# Change to source directory
cd "$SRC_DIR"

# Build the project
log_info "Building FKS.dll..."
log_info "Using .NET Framework 4.8 target..."

# Build in Release mode for production
dotnet build FKS.csproj --configuration Release --verbosity normal

if [ $? -ne 0 ]; then
    log_error "Build failed! Check the errors above."
    exit 1
fi

# Verify DLL was created
DLL_PATH="$BIN_DIR/Release/FKS.dll"
if [ ! -f "$DLL_PATH" ]; then
    log_error "FKS.dll was not created at $DLL_PATH"
    log_info "Checking for alternative locations..."
    find "$BIN_DIR" -name "FKS.dll" -type f 2>/dev/null || true
    exit 1
fi

log_success "FKS.dll built successfully"

# Get DLL information
DLL_SIZE=$(stat -f%z "$DLL_PATH" 2>/dev/null || stat -c%s "$DLL_PATH" 2>/dev/null || echo "unknown")
log_info "DLL size: $DLL_SIZE bytes"

# Validate DLL using file command
if command -v file &> /dev/null; then
    FILE_INFO=$(file "$DLL_PATH")
    log_info "DLL type: $FILE_INFO"
    
    if [[ "$FILE_INFO" == *"PE32"* ]] || [[ "$FILE_INFO" == *".NET"* ]] || [[ "$FILE_INFO" == *"assembly"* ]]; then
        log_success "DLL appears to be a valid .NET assembly"
    else
        log_warning "DLL type validation inconclusive - continuing anyway"
    fi
fi

# Run the packaging target
log_info "Creating NT8 package..."
dotnet build FKS.csproj --configuration Release --target PackageNT8

if [ $? -ne 0 ]; then
    log_error "Packaging failed!"
    exit 1
fi

# Find the package directory
TEMP_DIR=$(find "$PACKAGES_DIR" -name "temp" -type d 2>/dev/null | head -1)
if [ -z "$TEMP_DIR" ]; then
    log_error "Package temp directory not found"
    exit 1
fi

log_success "Package structure created at $TEMP_DIR"

# Verify critical files in package
log_info "Verifying package contents..."

# Check for DLL at root (critical for NT8 import)
ROOT_DLL="$TEMP_DIR/FKS.dll"
if [ ! -f "$ROOT_DLL" ]; then
    log_error "FKS.dll not found at package root: $ROOT_DLL"
    exit 1
fi
log_success "✓ FKS.dll found at package root"

# Check for AdditionalReferences.txt
ADDITIONAL_REFS="$TEMP_DIR/AdditionalReferences.txt"
if [ ! -f "$ADDITIONAL_REFS" ]; then
    log_error "AdditionalReferences.txt not found: $ADDITIONAL_REFS"
    exit 1
fi
log_success "✓ AdditionalReferences.txt found"

# Check manifest
MANIFEST="$TEMP_DIR/manifest.xml"
if [ ! -f "$MANIFEST" ]; then
    # Copy manifest manually if not copied by build
    cp "$NINJA_DIR/manifest.xml" "$MANIFEST"
    log_warning "Manifest copied manually"
else
    log_success "✓ manifest.xml found"
fi

# Verify XML syntax of manifest
if command -v xmllint &> /dev/null; then
    if xmllint --noout "$MANIFEST" 2>/dev/null; then
        log_success "✓ manifest.xml is valid XML"
    else
        log_warning "manifest.xml has XML syntax issues (continuing anyway)"
    fi
fi

# Create final ZIP package
PACKAGE_NAME="FKS_TradingSystem_v1.0.0_External"
ZIP_PATH="$PACKAGES_DIR/${PACKAGE_NAME}.zip"

log_info "Creating final ZIP package..."
cd "$TEMP_DIR"

if command -v zip &> /dev/null; then
    zip -r "$ZIP_PATH" . -x "*.DS_Store*" "*.git*"
    log_success "ZIP package created: $ZIP_PATH"
elif command -v 7z &> /dev/null; then
    7z a "$ZIP_PATH" . -x!'*.DS_Store*' -x!'*.git*'
    log_success "ZIP package created using 7z: $ZIP_PATH"
else
    log_warning "No zip utility found - package directory available at: $TEMP_DIR"
fi

# Final validation summary
log_info "Package validation summary:"
echo "  📁 Package directory: $TEMP_DIR"
echo "  📦 ZIP file: $ZIP_PATH"
echo "  💾 DLL at root: $([ -f "$ROOT_DLL" ] && echo "✓" || echo "✗")"
echo "  📄 Additional refs: $([ -f "$ADDITIONAL_REFS" ] && echo "✓" || echo "✗")"
echo "  📋 Manifest: $([ -f "$MANIFEST" ] && echo "✓" || echo "✗")"

# List package contents
log_info "Package contents:"
find "$TEMP_DIR" -type f | sed 's|^'$TEMP_DIR'/||' | sort | sed 's/^/  /'

# Final instructions
echo ""
log_success "🎉 FKS DLL build and package completed successfully!"
echo ""
echo -e "${YELLOW}📋 Next steps:${NC}"
echo "1. Import the ZIP file into NinjaTrader 8:"
echo "   - Tools → Import NinjaScript..."
echo "   - Select: $ZIP_PATH"
echo "2. The DLL will be installed for external development use"
echo "3. Restart NinjaTrader to load the new assembly"
echo ""
echo -e "${BLUE}💡 External Development Notes:${NC}"
echo "- The DLL is at the package root for proper NT8 import"
echo "- AdditionalReferences.txt ensures custom DLL support"
echo "- Source files are included for hybrid development"
echo "- All components follow NT8 external development guidelines"

exit 0
