#!/bin/bash
# FKS Trading Systems - Build Script
# Automates the build and packaging process

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="/home/ordan/fks/src/ninja"
SRC_DIR="$PROJECT_ROOT/src"
BUILD_CONFIG="Release"
OUTPUT_DIR="$PROJECT_ROOT/bin/Release"
PACKAGE_DIR="$PROJECT_ROOT/package_nt8"

echo -e "${GREEN}FKS Trading Systems - Build Script${NC}"
echo "======================================"

# Function to print status
print_status() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] ✓ $1${NC}"
}

print_error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ✗ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/FKS.csproj" ]; then
    print_error "FKS.csproj not found. Please run from the project root."
    exit 1
fi

# Clean previous builds
print_status "Cleaning previous builds..."
rm -rf "$OUTPUT_DIR"/*
rm -rf "$PROJECT_ROOT/obj"/*
rm -rf "$PACKAGE_DIR/temp"/*
print_success "Clean completed"

# Update assembly version with timestamp
print_status "Updating assembly version..."
VERSION="1.0.0.$(date +'%Y%m%d')"
sed -i "s/\[assembly: AssemblyVersion(\".*\")\]/[assembly: AssemblyVersion(\"$VERSION\")]/" "$SRC_DIR/Properties/AssemblyInfo.cs"
print_success "Version set to $VERSION"

# Build the project
print_status "Building FKS.dll..."
dotnet build "$PROJECT_ROOT/FKS.csproj" -c $BUILD_CONFIG

if [ $? -eq 0 ]; then
    print_success "Build successful!"
else
    print_error "Build failed!"
    exit 1
fi

# Verify output files
print_status "Verifying output files..."
if [ -f "$OUTPUT_DIR/FKS.dll" ]; then
    print_success "FKS.dll created successfully"
    # Show file info
    ls -lh "$OUTPUT_DIR/FKS.dll"
else
    print_error "FKS.dll not found in output directory"
    exit 1
fi

# Create NinjaTrader package
print_status "Creating NinjaTrader package..."

# Create temp directory structure
mkdir -p "$PACKAGE_DIR/temp/bin"
mkdir -p "$PACKAGE_DIR/temp/templates"

# Copy files
cp "$OUTPUT_DIR/FKS.dll" "$PACKAGE_DIR/temp/bin/"
cp "$OUTPUT_DIR/FKS.pdb" "$PACKAGE_DIR/temp/bin/" 2>/dev/null || true
cp "$OUTPUT_DIR/FKS.xml" "$PACKAGE_DIR/temp/bin/" 2>/dev/null || true
cp "$PROJECT_ROOT/manifest.xml" "$PACKAGE_DIR/temp/"
cp "$SRC_DIR/Info.xml" "$PACKAGE_DIR/temp/"

# Create the zip package
PACKAGE_NAME="FKS_TradingSystem_v${VERSION}.zip"
cd "$PACKAGE_DIR/temp"
zip -r "../$PACKAGE_NAME" ./*
cd - > /dev/null

if [ -f "$PACKAGE_DIR/$PACKAGE_NAME" ]; then
    print_success "Package created: $PACKAGE_NAME"
    ls -lh "$PACKAGE_DIR/$PACKAGE_NAME"
else
    print_error "Package creation failed"
    exit 1
fi

# Run basic validation
print_status "Running validation checks..."

# Check DLL dependencies
print_status "Checking DLL dependencies..."
if command -v monodis &> /dev/null; then
    monodis --assemblyref "$OUTPUT_DIR/FKS.dll" | grep -E "(NinjaTrader|System)" || true
else
    print_status "monodis not found, skipping dependency check"
fi

# Check for required files in package
print_status "Validating package contents..."
unzip -l "$PACKAGE_DIR/$PACKAGE_NAME" | grep -E "(manifest.xml|FKS.dll|Info.xml)" > /dev/null
if [ $? -eq 0 ]; then
    print_success "Package contains required files"
else
    print_error "Package missing required files"
    exit 1
fi

# Generate build report
print_status "Generating build report..."
cat > "$PROJECT_ROOT/build_report_$(date +'%Y%m%d_%H%M%S').txt" << EOF
FKS Trading Systems Build Report
==============================
Date: $(date)
Version: $VERSION
Build Config: $BUILD_CONFIG
Package: $PACKAGE_NAME

Files in Package:
$(unzip -l "$PACKAGE_DIR/$PACKAGE_NAME")

Build Output:
$(ls -la "$OUTPUT_DIR")

Assembly Info:
$(file "$OUTPUT_DIR/FKS.dll")
EOF

print_success "Build report generated"

# Summary
echo ""
echo -e "${GREEN}========== BUILD COMPLETE ==========${NC}"
echo -e "Version:  ${YELLOW}$VERSION${NC}"
echo -e "Package:  ${YELLOW}$PACKAGE_NAME${NC}"
echo -e "Location: ${YELLOW}$PACKAGE_DIR${NC}"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo "1. Import $PACKAGE_NAME into NinjaTrader 8"
echo "2. Tools → Import → NinjaScript Add-On"
echo "3. Restart NinjaTrader after import"
echo "4. Add FKS indicators and strategy to chart"
echo ""

# Optional: Copy to NinjaTrader import folder
if [ -d "$HOME/Documents/NinjaTrader 8/bin/Custom/ImportNinjaScript" ]; then
    print_status "Copying to NinjaTrader import folder..."
    cp "$PACKAGE_DIR/$PACKAGE_NAME" "$HOME/Documents/NinjaTrader 8/bin/Custom/ImportNinjaScript/"
    print_success "Package copied to NinjaTrader import folder"
fi

exit 0