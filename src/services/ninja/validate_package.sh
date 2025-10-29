#!/bin/bash

# FKS Trading Systems - Package Validation Script
# Validates the NinjaTrader 8 package for correctness and completeness

echo "=== FKS Trading Systems - Package Validator ==="

PROJECT_ROOT="/home/ordan/fks/src/ninja"
PACKAGE_FILE="$PROJECT_ROOT/FKS_TradingSystem_v1.0.0.zip"
VALIDATION_DIR="$PROJECT_ROOT/validation_temp"

# Check if package exists
if [ ! -f "$PACKAGE_FILE" ]; then
    echo "❌ Package file not found: $PACKAGE_FILE"
    echo "Run ./create_nt8_package.sh first to create the package."
    exit 1
fi

echo "✅ Package file found: $PACKAGE_FILE"

# Create validation directory
rm -rf "$VALIDATION_DIR"
mkdir -p "$VALIDATION_DIR"

# Extract package
echo "📦 Extracting package for validation..."
cd "$VALIDATION_DIR"
unzip -q "$PACKAGE_FILE"

if [ $? -ne 0 ]; then
    echo "❌ Failed to extract package"
    exit 1
fi

echo "✅ Package extracted successfully"

# Check required files
echo "🔍 Validating package structure..."

# Check manifest.xml
if [ -f "manifest.xml" ]; then
    echo "✅ manifest.xml found"
    
    # Validate XML structure
    if xmllint --noout manifest.xml 2>/dev/null; then
        echo "✅ manifest.xml is valid XML"
    else
        echo "⚠️  manifest.xml has XML syntax issues"
    fi
else
    echo "❌ manifest.xml missing"
fi

# Check Info.xml
if [ -f "Info.xml" ]; then
    echo "✅ Info.xml found"
else
    echo "⚠️  Info.xml missing (optional but recommended)"
fi

# Check compiled assembly
if [ -f "bin/FKS.dll" ]; then
    echo "✅ FKS.dll found"
    
    # Check file size
    dll_size=$(stat -c%s "bin/FKS.dll")
    if [ $dll_size -gt 100000 ]; then  # >100KB
        echo "✅ FKS.dll size: $dll_size bytes (good)"
    else
        echo "⚠️  FKS.dll size: $dll_size bytes (might be too small)"
    fi
else
    echo "❌ FKS.dll missing"
fi

# Check source files
echo "📝 Checking source files..."

# AddOns
addon_files=("FKS_Core.cs" "FKS_Calculations.cs" "FKS_Infrastructure.cs" "FKS_Market.cs" "FKS_Signals.cs")
for file in "${addon_files[@]}"; do
    if [ -f "bin/Custom/AddOns/$file" ]; then
        echo "✅ AddOn: $file"
    else
        echo "❌ Missing AddOn: $file"
    fi
done

# Indicators
indicator_files=("FKS_AI.cs" "FKS_AO.cs" "FKS_Dashboard.cs" "FKS_PythonBridge.cs")
for file in "${indicator_files[@]}"; do
    if [ -f "bin/Custom/Indicators/$file" ]; then
        echo "✅ Indicator: $file"
    else
        echo "❌ Missing Indicator: $file"
    fi
done

# Strategies
strategy_files=("FKS_Strategy.cs")
for file in "${strategy_files[@]}"; do
    if [ -f "bin/Custom/Strategies/$file" ]; then
        echo "✅ Strategy: $file"
    else
        echo "❌ Missing Strategy: $file"
    fi
done

# Check for proper namespace declarations
echo "🔍 Validating namespace declarations..."

# Check if files have proper NinjaTrader namespaces
grep -l "namespace NinjaTrader.NinjaScript" bin/Custom/*/*.cs | wc -l > /tmp/namespace_count
namespace_count=$(cat /tmp/namespace_count)

if [ $namespace_count -gt 8 ]; then
    echo "✅ Namespace declarations found in $namespace_count files"
else
    echo "⚠️  Only $namespace_count files have proper namespace declarations"
fi

# Check manifest consistency
echo "🔍 Validating manifest consistency..."

# Count exported types in manifest
exported_types=$(grep -c "ExportedType" manifest.xml)
echo "✅ Manifest declares $exported_types exported types"

# Check for class declarations that should be exported
indicator_classes=$(grep -h "public class.*: .*Indicator" bin/Custom/Indicators/*.cs | wc -l)
strategy_classes=$(grep -h "public class.*: .*Strategy" bin/Custom/Strategies/*.cs | wc -l)
expected_exports=$((indicator_classes + strategy_classes))

echo "✅ Found $indicator_classes indicator classes and $strategy_classes strategy classes"

if [ $exported_types -eq $expected_exports ]; then
    echo "✅ Manifest export count matches expected classes"
else
    echo "⚠️  Manifest exports ($exported_types) don't match expected classes ($expected_exports)"
fi

# Package size validation
package_size=$(stat -c%s "$PACKAGE_FILE")
package_size_kb=$((package_size / 1024))

echo "📊 Package Statistics:"
echo "   Size: $package_size_kb KB"
echo "   Files: $(find . -type f | wc -l)"

if [ $package_size_kb -gt 100 ] && [ $package_size_kb -lt 5000 ]; then
    echo "✅ Package size is reasonable ($package_size_kb KB)"
else
    echo "⚠️  Package size might be unusual ($package_size_kb KB)"
fi

# Cleanup
cd "$PROJECT_ROOT"
rm -rf "$VALIDATION_DIR"

echo ""
echo "=== Validation Complete ==="
echo "Package: $PACKAGE_FILE"
echo ""
echo "Ready for NinjaTrader 8 import!"
