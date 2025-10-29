#!/bin/bash

# FKS NinjaTrader Build Fix Script
# This script cleans up the project for reliable compilation

echo "🔧 FKS NinjaTrader Build Fix Starting..."

cd /home/ordan/fks/src/ninja/src

# 1. Remove all NinjaScript generated code sections that cause conflicts
echo "Removing problematic generated code sections..."

find . -name "*.cs" -type f -exec sed -i '/^#region NinjaScript generated code/,/^#endregion$/d' {} \;

# 2. Create a clean manifest for source-only build
echo "Creating clean manifest.xml..."
cat > ../manifest.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<NinjaScriptManifest SchemaVersion="1.0" xmlns="http://www.ninjatrader.com/NinjaScript">
  <NinjaScriptCollection>
    <Indicators>
      <Indicator>
        <TypeName>FKS_AI</TypeName>
        <AssemblyName>Custom</AssemblyName>
        <FullTypeName>NinjaTrader.NinjaScript.Indicators.FKS.FKS_AI</FullTypeName>
      </Indicator>
      <Indicator>
        <TypeName>FKS_AO</TypeName>
        <AssemblyName>Custom</AssemblyName>
        <FullTypeName>NinjaTrader.NinjaScript.Indicators.FKS.FKS_AO</FullTypeName>
      </Indicator>
      <Indicator>
        <TypeName>FKS_Dashboard</TypeName>
        <AssemblyName>Custom</AssemblyName>
        <FullTypeName>NinjaTrader.NinjaScript.Indicators.FKS.FKS_Dashboard</FullTypeName>
      </Indicator>
      <Indicator>
        <TypeName>FKS_PythonBridge</TypeName>
        <AssemblyName>Custom</AssemblyName>
        <FullTypeName>NinjaTrader.NinjaScript.Indicators.FKS.FKS_PythonBridge</FullTypeName>
      </Indicator>
    </Indicators>
    <Strategies>
      <Strategy>
        <TypeName>FKS_Strategy</TypeName>
        <AssemblyName>Custom</AssemblyName>
        <FullTypeName>NinjaTrader.NinjaScript.Strategies.FKS.FKS_Strategy</FullTypeName>
      </Strategy>
    </Strategies>
  </NinjaScriptCollection>
</NinjaScriptManifest>
EOF

# 3. Create Info.xml
cat > Info.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<NinjaTrader>
  <Export>
    <Version>8.1.2.1</Version>
  </Export>
</NinjaTrader>
EOF

# 4. Test build
echo "Testing build..."
dotnet build FKS.csproj -c Release --verbosity minimal

if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
    echo "📦 Creating source-only package..."
    dotnet build FKS.csproj --target PackageNT8 -c Release
    
    if [ $? -eq 0 ]; then
        echo "✅ Package created successfully!"
        echo "📁 Package location: /home/ordan/fks/src/ninja/packages/temp/"
        ls -la ../packages/temp/ 2>/dev/null || echo "Package directory not found"
    else
        echo "❌ Package creation failed"
    fi
else
    echo "❌ Build failed. Check errors above."
fi

echo "🏁 Fix script completed!"
