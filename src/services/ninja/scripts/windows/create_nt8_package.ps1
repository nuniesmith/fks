# FKS Trading Systems - NinjaTrader 8 Package Creator (PowerShell Version)
# This script creates a proper NinjaTrader 8 import package on Windows

Write-Host "=== FKS Trading Systems - NinjaTrader 8 Package Creator ===" -ForegroundColor Green

# Set variables
$PROJECT_ROOT = $PSScriptRoot
$SRC_DIR = Join-Path $PROJECT_ROOT "src"
$BUILD_DIR = Join-Path $PROJECT_ROOT "bin\Release"
$PACKAGE_DIR = Join-Path $PROJECT_ROOT "package_nt8"
$TEMP_DIR = Join-Path $PACKAGE_DIR "temp"
$PACKAGE_NAME = "FKS_TradingSystem_v1.0.0"
$ZIP_FILE = Join-Path $PROJECT_ROOT "$PACKAGE_NAME.zip"

# Clean and create directories
Write-Host "Setting up package directories..." -ForegroundColor Yellow
if (Test-Path $PACKAGE_DIR) {
    Remove-Item $PACKAGE_DIR -Recurse -Force
}
New-Item -ItemType Directory -Path "$TEMP_DIR\bin" -Force | Out-Null
New-Item -ItemType Directory -Path "$TEMP_DIR\bin\Custom\AddOns" -Force | Out-Null
New-Item -ItemType Directory -Path "$TEMP_DIR\bin\Custom\Indicators" -Force | Out-Null
New-Item -ItemType Directory -Path "$TEMP_DIR\bin\Custom\Strategies" -Force | Out-Null

# Build the project first
Write-Host "Building the project..." -ForegroundColor Yellow
Push-Location $SRC_DIR
try {
    $buildResult = dotnet build --configuration Release --verbosity minimal
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed! Please fix compilation errors first." -ForegroundColor Red
        exit 1
    }
    Write-Host "Build successful!" -ForegroundColor Green
} finally {
    Pop-Location
}

# Copy compiled assembly
Write-Host "Copying compiled assembly..." -ForegroundColor Yellow
$dllPath = Join-Path $BUILD_DIR "FKS.dll"
if (Test-Path $dllPath) {
    Copy-Item $dllPath -Destination "$TEMP_DIR\bin\"
    Write-Host "  ✓ FKS.dll copied" -ForegroundColor Green
} else {
    Write-Host "  ✗ FKS.dll not found in $BUILD_DIR" -ForegroundColor Red
    exit 1
}

# Copy source files - AddOns
Write-Host "Copying AddOn source files..." -ForegroundColor Yellow
$addonFiles = @("FKS_Core.cs", "FKS_Calculations.cs", "FKS_Infrastructure.cs", "FKS_Market.cs", "FKS_Signals.cs")
foreach ($file in $addonFiles) {
    $sourcePath = Join-Path "$SRC_DIR\AddOns" $file
    if (Test-Path $sourcePath) {
        Copy-Item $sourcePath -Destination "$TEMP_DIR\bin\Custom\AddOns\"
        Write-Host "  ✓ $file copied" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file not found" -ForegroundColor Red
    }
}

# Copy source files - Indicators
Write-Host "Copying Indicator source files..." -ForegroundColor Yellow
$indicatorFiles = @("FKS_AI.cs", "FKS_AO.cs", "FKS_Dashboard.cs", "FKS_PythonBridge.cs")
foreach ($file in $indicatorFiles) {
    $sourcePath = Join-Path "$SRC_DIR\Indicators" $file
    if (Test-Path $sourcePath) {
        Copy-Item $sourcePath -Destination "$TEMP_DIR\bin\Custom\Indicators\"
        Write-Host "  ✓ $file copied" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file not found" -ForegroundColor Red
    }
}

# Copy source files - Strategies
Write-Host "Copying Strategy source files..." -ForegroundColor Yellow
$strategyFiles = @("FKS_Strategy.cs")
foreach ($file in $strategyFiles) {
    $sourcePath = Join-Path "$SRC_DIR\Strategies" $file
    if (Test-Path $sourcePath) {
        Copy-Item $sourcePath -Destination "$TEMP_DIR\bin\Custom\Strategies\"
        Write-Host "  ✓ $file copied" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file not found" -ForegroundColor Red
    }
}

# Copy manifest and Info.xml
Write-Host "Copying manifest and metadata files..." -ForegroundColor Yellow
$manifestPath = Join-Path $PROJECT_ROOT "manifest.xml"
if (Test-Path $manifestPath) {
    Copy-Item $manifestPath -Destination "$TEMP_DIR\"
    Write-Host "  ✓ manifest.xml copied" -ForegroundColor Green
} else {
    Write-Host "  ✗ manifest.xml not found" -ForegroundColor Red
    exit 1
}

$infoPath = Join-Path $SRC_DIR "Info.xml"
if (Test-Path $infoPath) {
    Copy-Item $infoPath -Destination "$TEMP_DIR\"
    Write-Host "  ✓ Info.xml copied" -ForegroundColor Green
} else {
    Write-Host "  ✗ Info.xml not found" -ForegroundColor Red
}

# Create the zip package
Write-Host "Creating zip package..." -ForegroundColor Yellow
if (Test-Path $ZIP_FILE) {
    Remove-Item $ZIP_FILE -Force
}

# Use PowerShell's Compress-Archive cmdlet
try {
    Push-Location $TEMP_DIR
    Compress-Archive -Path ".\*" -DestinationPath $ZIP_FILE -CompressionLevel Optimal
    Write-Host "  ✓ Package created: $ZIP_FILE" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Failed to create zip package: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}

# Show package contents
Write-Host ""
Write-Host "Package structure:" -ForegroundColor Cyan
Push-Location $TEMP_DIR
Get-ChildItem -Recurse -File | ForEach-Object { $_.FullName.Replace((Get-Location).Path, ".") } | Sort-Object
Pop-Location

# Show package size
$zipSize = [Math]::Round((Get-Item $ZIP_FILE).Length / 1KB, 1)
Write-Host ""
Write-Host "Package size: $zipSize KB" -ForegroundColor Cyan

Write-Host ""
Write-Host "=== Package Creation Complete ===" -ForegroundColor Green
Write-Host "Import file: $ZIP_FILE" -ForegroundColor White
Write-Host ""
Write-Host "To import into NinjaTrader 8:" -ForegroundColor Yellow
Write-Host "1. Open NinjaTrader 8" -ForegroundColor White
Write-Host "2. Go to Tools > Import NinjaScript..." -ForegroundColor White
Write-Host "3. Select the file: $ZIP_FILE" -ForegroundColor White
Write-Host "4. Follow the import wizard" -ForegroundColor White
Write-Host ""
Write-Host "Note: Restart NinjaTrader after import for best results." -ForegroundColor Yellow
