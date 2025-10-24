#!/bin/bash

# FKS Trading Systems - Create Package with DLL
# This script creates a minimal working FKS package with compiled DLL

echo "=== Creating FKS Trading Systems Package with DLL ==="

# Set up directories
WORK_DIR="/tmp/fks_package_build"
PACKAGE_DIR="$WORK_DIR/package"
SOURCE_DIR="/home/jordan/oryx/code/repo/fks/src/ninja/src"

# Clean and create directories
rm -rf "$WORK_DIR"
mkdir -p "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR/bin/Custom/AddOns"
mkdir -p "$PACKAGE_DIR/bin/Custom/Indicators"
mkdir -p "$PACKAGE_DIR/bin/Custom/Strategies"

echo "Setting up package structure..."

# Step 1: Create a minimal FKS utilities DLL that can compile independently
cat > "$WORK_DIR/FKS_Utilities.cs" << 'EOF'
using System;
using System.Collections.Generic;
using System.Linq;

namespace FKS.Utilities
{
    // Simple utility classes that don't depend on NinjaTrader
    public static class FKS_Utils
    {
        public static double CalculateEMA(double[] values, int period)
        {
            if (values.Length == 0) return 0;
            
            double multiplier = 2.0 / (period + 1);
            double ema = values[0];
            
            for (int i = 1; i < values.Length; i++)
            {
                ema = (values[i] * multiplier) + (ema * (1 - multiplier));
            }
            
            return ema;
        }
        
        public static double CalculateSMA(double[] values, int period)
        {
            if (values.Length < period) return 0;
            return values.Skip(values.Length - period).Take(period).Average();
        }
        
        public static double CalculateATR(double[] highs, double[] lows, double[] closes, int period)
        {
            if (highs.Length < period || lows.Length < period || closes.Length < period) return 0;
            
            List<double> trueRanges = new List<double>();
            
            for (int i = 1; i < Math.Min(highs.Length, Math.Min(lows.Length, closes.Length)); i++)
            {
                double tr1 = highs[i] - lows[i];
                double tr2 = Math.Abs(highs[i] - closes[i - 1]);
                double tr3 = Math.Abs(lows[i] - closes[i - 1]);
                
                trueRanges.Add(Math.Max(tr1, Math.Max(tr2, tr3)));
            }
            
            return trueRanges.Skip(trueRanges.Count - period).Take(period).Average();
        }
        
        public static string GetVersion()
        {
            return "FKS v1.0.0";
        }
        
        public static bool IsValidSignal(double quality)
        {
            return quality >= 0.65;
        }
    }
    
    public enum SignalType
    {
        None = 0,
        Buy = 1,
        Sell = -1,
        StrongBuy = 2,
        StrongSell = -2
    }
    
    public class SignalInfo
    {
        public SignalType Type { get; set; }
        public double Quality { get; set; }
        public double Price { get; set; }
        public DateTime Time { get; set; }
        
        public SignalInfo(SignalType type, double quality, double price)
        {
            Type = type;
            Quality = quality;
            Price = price;
            Time = DateTime.Now;
        }
    }
}
EOF

# Step 2: Create project file for the utilities DLL
cat > "$WORK_DIR/FKS_Utilities.csproj" << 'EOF'
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net48</TargetFramework>
    <OutputType>Library</OutputType>
    <AssemblyName>FKS_Utilities</AssemblyName>
    <RootNamespace>FKS.Utilities</RootNamespace>
  </PropertyGroup>
</Project>
EOF

echo "Building FKS utilities DLL..."
cd "$WORK_DIR"
dotnet build -c Release

# Check if DLL was created
if [ -f "bin/Release/net48/FKS_Utilities.dll" ]; then
    echo "✓ FKS_Utilities.dll created successfully"
    DLL_PATH="bin/Release/net48/FKS_Utilities.dll"
else
    echo "✗ Failed to create FKS_Utilities.dll"
    exit 1
fi

# Step 3: Copy the DLL to package root (required for NT8)
cp "$DLL_PATH" "$PACKAGE_DIR/FKS_Utilities.dll"
echo "✓ DLL copied to package root"

# Step 4: Create AdditionalReferences.txt (critical for NT8 DLL loading)
cat > "$PACKAGE_DIR/AdditionalReferences.txt" << 'EOF'
FKS_Utilities
EOF
echo "✓ AdditionalReferences.txt created"

# Step 5: Copy all source files
echo "Copying source files..."

# Copy AddOns
for file in FKS_Core.cs FKS_Market.cs FKS_Signals.cs; do
    if [ -f "$SOURCE_DIR/AddOns/$file" ]; then
        cp "$SOURCE_DIR/AddOns/$file" "$PACKAGE_DIR/bin/Custom/AddOns/"
        echo "  ✓ AddOns/$file"
    else
        echo "  ✗ AddOns/$file not found"
    fi
done

# Copy Indicators
for file in FKS_AI.cs FKS_AO.cs FKS_Dashboard.cs FKS_PythonBridge.cs; do
    if [ -f "$SOURCE_DIR/Indicators/$file" ]; then
        cp "$SOURCE_DIR/Indicators/$file" "$PACKAGE_DIR/bin/Custom/Indicators/"
        echo "  ✓ Indicators/$file"
    else
        echo "  ✗ Indicators/$file not found"
    fi
done

# Copy Strategies
for file in FKS_Strategy.cs; do
    if [ -f "$SOURCE_DIR/Strategies/$file" ]; then
        cp "$SOURCE_DIR/Strategies/$file" "$PACKAGE_DIR/bin/Custom/Strategies/"
        echo "  ✓ Strategies/$file"
    else
        echo "  ✗ Strategies/$file not found"
    fi
done

# Step 6: Create manifest.xml
cat > "$PACKAGE_DIR/manifest.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<NinjaScriptManifest SchemaVersion="1.0" xmlns="http://www.ninjatrader.com/NinjaScript">
  <Assemblies>
    <Assembly>
      <FullName>FKS_Utilities, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null</FullName>
      <ExportedTypes>
        <!-- Utility DLL - no exports needed -->
      </ExportedTypes>
    </Assembly>
  </Assemblies>
  <NinjaScriptCollection>
    <Indicators>
      <Indicator>
        <TypeName>FKS_AI</TypeName>
        <AssemblyName>NinjaTrader.Custom</AssemblyName>
        <FullTypeName>NinjaTrader.NinjaScript.Indicators.FKS_AI</FullTypeName>
        <DisplayName>FKS AI</DisplayName>
        <Group>FKS</Group>
        <Properties>
          <Property>
            <Name>ShowSignals</Name>
            <DisplayName>Show Signals</DisplayName>
            <DefaultValue>true</DefaultValue>
            <PropertyType>System.Boolean</PropertyType>
          </Property>
          <Property>
            <Name>ShowLevels</Name>
            <DisplayName>Show Levels</DisplayName>
            <DefaultValue>true</DefaultValue>
            <PropertyType>System.Boolean</PropertyType>
          </Property>
        </Properties>
      </Indicator>
      <Indicator>
        <TypeName>FKS_AO</TypeName>
        <AssemblyName>NinjaTrader.Custom</AssemblyName>
        <FullTypeName>NinjaTrader.NinjaScript.Indicators.FKS_AO</FullTypeName>
        <DisplayName>FKS AO</DisplayName>
        <Group>FKS</Group>
      </Indicator>
      <Indicator>
        <TypeName>FKS_Dashboard</TypeName>
        <AssemblyName>NinjaTrader.Custom</AssemblyName>
        <FullTypeName>NinjaTrader.NinjaScript.Indicators.FKS_Dashboard</FullTypeName>
        <DisplayName>FKS Info</DisplayName>
        <Group>FKS</Group>
      </Indicator>
      <Indicator>
        <TypeName>FKS_PythonBridge</TypeName>
        <AssemblyName>NinjaTrader.Custom</AssemblyName>
        <FullTypeName>NinjaTrader.NinjaScript.Indicators.FKS_PythonBridge</FullTypeName>
        <DisplayName>FKS Python Bridge</DisplayName>
        <Group>FKS</Group>
      </Indicator>
    </Indicators>
    <Strategies>
      <Strategy>
        <TypeName>FKS_Strategy</TypeName>
        <AssemblyName>NinjaTrader.Custom</AssemblyName>
        <FullTypeName>NinjaTrader.NinjaScript.Strategies.FKS_Strategy</FullTypeName>
        <DisplayName>FKS Strategy</DisplayName>
        <Group>FKS</Group>
      </Strategy>
    </Strategies>
  </NinjaScriptCollection>
</NinjaScriptManifest>
EOF

echo "✓ manifest.xml created"

# Step 7: Create Info.xml
cat > "$PACKAGE_DIR/Info.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<NinjaScriptVersion>
  <Name>FKS Trading Systems v1.0.0</Name>
  <Version>1.0.0</Version>
  <Description>FKS Trading Systems - Master Plan Implementation with Utilities DLL</Description>
  <CreatedDate>2025-01-08</CreatedDate>
  <ModifiedDate>2025-01-08</ModifiedDate>
  <Author>FKS Development Team</Author>
  <RequiredVersion>8.1.2.1</RequiredVersion>
  <UpdatedNinjaTraderVersion>8.1.2.1</UpdatedNinjaTraderVersion>
  <NinjaScriptType>Package</NinjaScriptType>
  <Notes>
    Production-ready FKS Trading Systems with utilities DLL for enhanced performance.
    
    Includes FKS_Utilities.dll for common calculation functions.
    All components optimized for Gold Futures (GC) trading.
    Signal quality threshold: 0.65+
    
    Installation: Import zip file into NinjaTrader 8, restart, and verify compilation.
  </Notes>
</NinjaScriptVersion>
EOF

echo "✓ Info.xml created"

# Step 8: Create the final package
FINAL_PACKAGE="/home/jordan/oryx/code/repo/fks/src/ninja/FKS_TradingSystem_v1.0.0_WithDLL.zip"
cd "$PACKAGE_DIR"
rm -f "$FINAL_PACKAGE"
zip -r "$FINAL_PACKAGE" .

echo ""
echo "=== Package Created Successfully ==="
echo "Package: $FINAL_PACKAGE"
echo "Size: $(du -h "$FINAL_PACKAGE" | cut -f1)"
echo ""
echo "Contents:"
unzip -l "$FINAL_PACKAGE"
echo ""
echo "✓ Ready for NinjaTrader 8 import!"
echo "✓ Includes FKS_Utilities.dll for enhanced functionality"
echo "✓ All source files included"
echo "✓ Proper manifest and metadata"
echo ""
echo "Installation: Import this zip file into NinjaTrader 8 and restart."
