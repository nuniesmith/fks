# FKS Strategy Deployment Script
param(
    [string]$NinjaTraderPath = "C:\Users\Jordan\Documents\NinjaTrader 8"
)

Write-Host "FKS Strategy Deployment Script" -ForegroundColor Green
Write-Host "==============================" -ForegroundColor Green

# Define paths
$SourceStrategy = ".\FKSStrategyAIO.cs"
$OptimizationConfigs = ".\optimization_configs"
$TargetStrategies = Join-Path $NinjaTraderPath "bin\Custom\Strategies"
$TargetTemplates = Join-Path $NinjaTraderPath "templates\Strategy\FKSStrategyAIO"
$QuickStartPath = Join-Path $NinjaTraderPath "FKS_QuickStart_Configs"

# Verify NinjaTrader path
if (-not (Test-Path $NinjaTraderPath)) {
    Write-Host "ERROR: NinjaTrader 8 directory not found at: $NinjaTraderPath" -ForegroundColor Red
    exit 1
}

Write-Host "NinjaTrader Path: $NinjaTraderPath" -ForegroundColor Cyan

# Create directories
Write-Host "`n1. Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $TargetStrategies -Force | Out-Null
New-Item -ItemType Directory -Path $TargetTemplates -Force | Out-Null  
New-Item -ItemType Directory -Path $QuickStartPath -Force | Out-Null
Write-Host "   Directories created" -ForegroundColor Green

# Deploy strategy
Write-Host "`n2. Deploying strategy..." -ForegroundColor Yellow
if (Test-Path $SourceStrategy) {
    $TargetStrategyFile = Join-Path $TargetStrategies "FKSStrategyAIO.cs"
    Copy-Item $SourceStrategy $TargetStrategyFile -Force
    Write-Host "   Strategy deployed: FKSStrategyAIO.cs" -ForegroundColor Green
} else {
    Write-Host "   ERROR: Source strategy not found: $SourceStrategy" -ForegroundColor Red
    exit 1
}

# Deploy templates
Write-Host "`n3. Deploying optimization templates..." -ForegroundColor Yellow
$Assets = @("GC", "ES", "NQ", "CL", "BTC")
$TemplatesDeployed = 0

foreach ($Asset in $Assets) {
    $AssetPath = Join-Path $OptimizationConfigs $Asset
    $TemplateFile = Join-Path $AssetPath "$Asset`_NinjaTrader_Template.xml"
    
    if (Test-Path $TemplateFile) {
        $TargetTemplate = Join-Path $TargetTemplates "FKS_$Asset`_Optimization.xml"
        Copy-Item $TemplateFile $TargetTemplate -Force
        Write-Host "   Template deployed: FKS_$Asset`_Optimization.xml" -ForegroundColor Green
        $TemplatesDeployed++
    } else {
        Write-Host "   WARNING: Template not found for $Asset" -ForegroundColor Yellow
    }
}

# Deploy quick start configs  
Write-Host "`n4. Deploying QuickStart configs..." -ForegroundColor Yellow
$ConfigsDeployed = 0

foreach ($Asset in $Assets) {
    $AssetPath = Join-Path $OptimizationConfigs $Asset
    $QuickStartFile = Join-Path $AssetPath "$Asset`_QuickStart.txt"
    
    if (Test-Path $QuickStartFile) {
        $TargetQuickStart = Join-Path $QuickStartPath "$Asset`_QuickStart.txt"
        Copy-Item $QuickStartFile $TargetQuickStart -Force
        Write-Host "   QuickStart deployed: $Asset`_QuickStart.txt" -ForegroundColor Green
        $ConfigsDeployed++
    }
}

# Copy master comparison
$MasterFile = Join-Path $OptimizationConfigs "Master_Asset_Comparison.txt"
if (Test-Path $MasterFile) {
    $TargetMaster = Join-Path $QuickStartPath "Master_Asset_Comparison.txt"
    Copy-Item $MasterFile $TargetMaster -Force
    Write-Host "   Master comparison deployed" -ForegroundColor Green
}

# Create setup instructions
Write-Host "`n5. Creating setup instructions..." -ForegroundColor Yellow

$Instructions = @"
# FKS Strategy Setup Instructions
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

DEPLOYMENT COMPLETE!

Files Deployed:
- Strategy: FKSStrategyAIO.cs -> $TargetStrategies
- Templates: $TemplatesDeployed XML files -> $TargetTemplates  
- QuickStart: $ConfigsDeployed config files -> $QuickStartPath

NEXT STEPS:

1. RESTART NINJATRADER 8 (Required!)

2. Create 5 charts:
   - Gold (GC 03-25) - 3 minute bars
   - S&P 500 (ES 03-25) - 3 minute bars
   - Nasdaq (NQ 03-25) - 3 minute bars
   - Crude Oil (CL 03-25) - 3 minute bars
   - Bitcoin (BTC 03-25) - 3 minute bars

3. Apply FKSStrategyAIO to each chart

4. Use QuickStart parameters from: $QuickStartPath

5. Global Position Limits:
   - Maximum 10 contracts total across ALL assets
   - Conservative mode at 7+ contracts
   - All instances coordinate automatically

6. Strategy Analyzer:
   - Templates located: $TargetTemplates
   - Load FKS_GC_Optimization.xml, FKS_ES_Optimization.xml, etc.

IMPORTANT:
- Start with Paper Trading
- Monitor global position limits
- Use asset-specific parameters from QuickStart files

File Locations:
- Strategy: $TargetStrategies\FKSStrategyAIO.cs
- Templates: $TargetTemplates\FKS_*_Optimization.xml
- QuickStart: $QuickStartPath\*_QuickStart.txt
"@

$InstructionsFile = Join-Path $QuickStartPath "SETUP_INSTRUCTIONS.txt"
$Instructions | Out-File -FilePath $InstructionsFile -Encoding UTF8
Write-Host "   Setup instructions created" -ForegroundColor Green

# Summary
Write-Host "`nDEPLOYMENT SUMMARY" -ForegroundColor Magenta
Write-Host "==================" -ForegroundColor Magenta
Write-Host "Strategy deployed: FKSStrategyAIO.cs" -ForegroundColor Green
Write-Host "Templates deployed: $TemplatesDeployed files" -ForegroundColor Green
Write-Host "QuickStart deployed: $ConfigsDeployed files" -ForegroundColor Green

Write-Host "`nNEXT STEPS:" -ForegroundColor Yellow
Write-Host "1. RESTART NinjaTrader 8" -ForegroundColor White
Write-Host "2. Create 5 charts (GC, ES, NQ, CL, BTC)" -ForegroundColor White
Write-Host "3. Apply FKSStrategyAIO to each chart" -ForegroundColor White
Write-Host "4. Use QuickStart parameters" -ForegroundColor White
Write-Host "5. Start with Paper Trading" -ForegroundColor White

Write-Host "`nInstructions file: $InstructionsFile" -ForegroundColor Cyan
Write-Host "`nDeployment Complete!" -ForegroundColor Green
