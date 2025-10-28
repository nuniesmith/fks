#!/bin/bash

# FKS Trading Systems - NinjaTrader 8 Package Creator
# This script creates a proper NinjaTrader 8 import package

echo "=== FKS Trading Systems - NinjaTrader 8 Package Creator ==="

# Set variables
PROJECT_ROOT="/home/ordan/fks/src/ninja"
SRC_DIR="$PROJECT_ROOT/src"
BUILD_DIR="$PROJECT_ROOT/bin/Release"
PACKAGE_DIR="$PROJECT_ROOT/package_nt8"
TEMP_DIR="$PACKAGE_DIR/temp"
PACKAGE_NAME="FKS_TradingSystem_v1.0.0"
ZIP_FILE="$PROJECT_ROOT/$PACKAGE_NAME.zip"

# Clean and create directories
echo "Setting up package directories..."
rm -rf "$PACKAGE_DIR"
mkdir -p "$TEMP_DIR/bin"
mkdir -p "$TEMP_DIR/bin/Custom/AddOns"
mkdir -p "$TEMP_DIR/bin/Custom/Indicators"
mkdir -p "$TEMP_DIR/bin/Custom/Strategies"

# Build the project first
echo "Building the project..."
cd "$SRC_DIR"
dotnet build --configuration Release --verbosity minimal

if [ $? -ne 0 ]; then
    echo "Build failed! Please fix compilation errors first."
    exit 1
fi

echo "Build successful!"

# Copy compiled assembly
echo "Copying compiled assembly..."
if [ -f "$BUILD_DIR/FKS.dll" ]; then
    cp "$BUILD_DIR/FKS.dll" "$TEMP_DIR/bin/"
    echo "  ✓ FKS.dll copied"
else
    echo "  ✗ FKS.dll not found in $BUILD_DIR"
    exit 1
fi

# Copy source files - AddOns
echo "Copying AddOn source files..."
for file in FKS_Core.cs FKS_Calculations.cs FKS_Infrastructure.cs FKS_Market.cs FKS_Signals.cs; do
    if [ -f "$SRC_DIR/AddOns/$file" ]; then
        cp "$SRC_DIR/AddOns/$file" "$TEMP_DIR/bin/Custom/AddOns/"
        echo "  ✓ $file copied"
    else
        echo "  ✗ $file not found"
    fi
done

# Copy source files - Indicators
echo "Copying Indicator source files..."
for file in FKS_AI.cs FKS_AO.cs FKS_Dashboard.cs FKS_PythonBridge.cs; do
    if [ -f "$SRC_DIR/Indicators/$file" ]; then
        cp "$SRC_DIR/Indicators/$file" "$TEMP_DIR/bin/Custom/Indicators/"
        echo "  ✓ $file copied"
    else
        echo "  ✗ $file not found"
    fi
done

# Copy source files - Strategies
echo "Copying Strategy source files..."
for file in FKS_Strategy.cs; do
    if [ -f "$SRC_DIR/Strategies/$file" ]; then
        cp "$SRC_DIR/Strategies/$file" "$TEMP_DIR/bin/Custom/Strategies/"
        echo "  ✓ $file copied"
    else
        echo "  ✗ $file not found"
    fi
done

# Copy manifest and Info.xml
echo "Copying manifest and metadata files..."
if [ -f "$PROJECT_ROOT/manifest.xml" ]; then
    cp "$PROJECT_ROOT/manifest.xml" "$TEMP_DIR/"
    echo "  ✓ manifest.xml copied"
else
    echo "  ✗ manifest.xml not found"
    exit 1
fi

if [ -f "$SRC_DIR/Info.xml" ]; then
    cp "$SRC_DIR/Info.xml" "$TEMP_DIR/"
    echo "  ✓ Info.xml copied"
else
    echo "  ✗ Info.xml not found"
fi

# Create the zip package
echo "Creating zip package..."
cd "$TEMP_DIR"
rm -f "$ZIP_FILE"
zip -r "$ZIP_FILE" . -x "*.DS_Store" "*/.*" 

if [ $? -eq 0 ]; then
    echo "  ✓ Package created: $ZIP_FILE"
else
    echo "  ✗ Failed to create zip package"
    exit 1
fi

# Show package contents
echo ""
echo "Package structure:"
cd "$TEMP_DIR"
find . -type f | sort

# Show package size
echo ""
echo "Package size: $(du -h "$ZIP_FILE" | cut -f1)"

echo ""
echo "=== Package Creation Complete ==="
echo "Import file: $ZIP_FILE"
echo ""
echo "To import into NinjaTrader 8:"
echo "1. Open NinjaTrader 8"
echo "2. Go to Tools > Import NinjaScript..."
echo "3. Select the file: $ZIP_FILE"
echo "4. Follow the import wizard"
echo ""
echo "Note: Restart NinjaTrader after import for best results."
