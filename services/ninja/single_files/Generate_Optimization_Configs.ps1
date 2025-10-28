# FKS Strategy Optimization Config Generator
# This script generates NinjaTrader-compatible parameter configuration files for each asset

param(
    [string]$OutputPath = ".\optimization_configs",
    [switch]$GenerateAll = $false,
    [string[]]$Assets = @("GC", "ES", "NQ", "CL", "BTC")
)

# Create output directory if it doesn't exist
if (-not (Test-Path $OutputPath)) {
    New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null
}

# Asset-specific configurations
$AssetConfigs = @{
    "GC" = @{
        Name = "Gold"
        SignalQualityThreshold = @{ Min = 0.60; Max = 0.75; Step = 0.02 }
        VolumeThreshold = @{ Min = 1.1; Max = 1.4; Step = 0.1 }
        ATRStopMultiplier = @{ Min = 1.5; Max = 2.5; Step = 0.25 }
        ATRTargetMultiplier = @{ Min = 1.2; Max = 2.0; Step = 0.2 }
        BaseContracts = @{ Min = 1; Max = 2; Step = 1 }
        MaxContracts = @{ Min = 3; Max = 5; Step = 1 }
        MaxDailyTrades = @{ Min = 8; Max = 12; Step = 1 }
        StartHour = @{ Values = @(4, 6, 7, 8) }
        EndHour = @{ Values = @(14, 15, 16, 17) }
        DailyProfitSoftTarget = 1800
        DailyProfitHardTarget = 2700
        DailyLossSoftLimit = 900
        DailyLossHardLimit = 1350
    }
    
    "ES" = @{
        Name = "S&P 500"
        SignalQualityThreshold = @{ Min = 0.60; Max = 0.75; Step = 0.02 }
        VolumeThreshold = @{ Min = 1.1; Max = 1.5; Step = 0.1 }
        ATRStopMultiplier = @{ Min = 1.8; Max = 2.5; Step = 0.2 }
        ATRTargetMultiplier = @{ Min = 1.3; Max = 2.2; Step = 0.3 }
        BaseContracts = @{ Min = 1; Max = 2; Step = 1 }
        MaxContracts = @{ Min = 3; Max = 4; Step = 1 }
        MaxDailyTrades = @{ Min = 8; Max = 12; Step = 1 }
        StartHour = @{ Values = @(4, 6, 7, 8) }
        EndHour = @{ Values = @(14, 15, 16, 17) }
        DailyProfitSoftTarget = 2000
        DailyProfitHardTarget = 3000
        DailyLossSoftLimit = 1000
        DailyLossHardLimit = 1500
    }
    
    "NQ" = @{
        Name = "Nasdaq"
        SignalQualityThreshold = @{ Min = 0.60; Max = 0.80; Step = 0.02 }
        VolumeThreshold = @{ Min = 1.1; Max = 1.6; Step = 0.1 }
        ATRStopMultiplier = @{ Min = 2.0; Max = 3.0; Step = 0.25 }
        ATRTargetMultiplier = @{ Min = 1.5; Max = 2.5; Step = 0.25 }
        BaseContracts = @{ Min = 1; Max = 2; Step = 1 }
        MaxContracts = @{ Min = 2; Max = 4; Step = 1 }
        MaxDailyTrades = @{ Min = 8; Max = 12; Step = 1 }
        StartHour = @{ Values = @(4, 6, 7, 8) }
        EndHour = @{ Values = @(14, 15, 16, 17) }
        DailyProfitSoftTarget = 2200
        DailyProfitHardTarget = 3300
        DailyLossSoftLimit = 1100
        DailyLossHardLimit = 1650
    }
    
    "CL" = @{
        Name = "Crude Oil"
        SignalQualityThreshold = @{ Min = 0.60; Max = 0.85; Step = 0.03 }
        VolumeThreshold = @{ Min = 1.1; Max = 1.8; Step = 0.1 }
        ATRStopMultiplier = @{ Min = 2.5; Max = 4.0; Step = 0.3 }
        ATRTargetMultiplier = @{ Min = 1.8; Max = 3.0; Step = 0.3 }
        BaseContracts = @{ Min = 1; Max = 1; Step = 1 }
        MaxContracts = @{ Min = 1; Max = 3; Step = 1 }
        MaxDailyTrades = @{ Min = 6; Max = 10; Step = 1 }
        StartHour = @{ Values = @(4, 6, 7, 8) }
        EndHour = @{ Values = @(13, 14, 16) }
        DailyProfitSoftTarget = 1500
        DailyProfitHardTarget = 2500
        DailyLossSoftLimit = 800
        DailyLossHardLimit = 1200
    }
    
    "BTC" = @{
        Name = "Bitcoin"
        SignalQualityThreshold = @{ Min = 0.60; Max = 0.90; Step = 0.03 }
        VolumeThreshold = @{ Min = 1.1; Max = 2.0; Step = 0.1 }
        ATRStopMultiplier = @{ Min = 3.0; Max = 5.0; Step = 0.5 }
        ATRTargetMultiplier = @{ Min = 2.0; Max = 4.0; Step = 0.5 }
        BaseContracts = @{ Min = 1; Max = 1; Step = 1 }
        MaxContracts = @{ Min = 1; Max = 2; Step = 1 }
        MaxDailyTrades = @{ Min = 6; Max = 10; Step = 1 }
        StartHour = @{ Values = @(4, 6, 8) }
        EndHour = @{ Values = @(15, 16, 18) }
        DailyProfitSoftTarget = 1200
        DailyProfitHardTarget = 2000
        DailyLossSoftLimit = 600
        DailyLossHardLimit = 1000
    }
}

function Generate-ParameterRange {
    param($Config)
    
    $parameters = @()
    
    # Generate range values
    if ($Config.Min -and $Config.Max -and $Config.Step) {
        for ($i = $Config.Min; $i -le $Config.Max; $i += $Config.Step) {
            $parameters += [math]::Round($i, 3)
        }
    }
    elseif ($Config.Values) {
        $parameters = $Config.Values
    }
    
    return $parameters
}

function Generate-OptimizationConfig {
    param($Asset, $Config, $Phase = "Phase1")
    
    $content = @"
# FKS Strategy Optimization Configuration
# Asset: $Asset ($($Config.Name))
# Phase: $Phase
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

# CORE PARAMETERS - $Phase
"@

    switch ($Phase) {
        "Phase1" {
            $content += @"

[SignalQualityThreshold]
# Most critical parameter - signal quality threshold
Min = $($Config.SignalQualityThreshold.Min)
Max = $($Config.SignalQualityThreshold.Max)
Step = $($Config.SignalQualityThreshold.Step)
Values = $((Generate-ParameterRange $Config.SignalQualityThreshold) -join ', ')

[VolumeThreshold]  
# Volume confirmation requirement
Min = $($Config.VolumeThreshold.Min)
Max = $($Config.VolumeThreshold.Max)
Step = $($Config.VolumeThreshold.Step)
Values = $((Generate-ParameterRange $Config.VolumeThreshold) -join ', ')

[ATRStopMultiplier]
# Risk management - stop loss sizing
Min = $($Config.ATRStopMultiplier.Min)
Max = $($Config.ATRStopMultiplier.Max)
Step = $($Config.ATRStopMultiplier.Step)
Values = $((Generate-ParameterRange $Config.ATRStopMultiplier) -join ', ')

[ATRTargetMultiplier]
# Profit target sizing
Min = $($Config.ATRTargetMultiplier.Min)
Max = $($Config.ATRTargetMultiplier.Max)
Step = $($Config.ATRTargetMultiplier.Step)
Values = $((Generate-ParameterRange $Config.ATRTargetMultiplier) -join ', ')
"@
        }
        
        "Phase2" {
            $content += @"

[BaseContracts]
# Base position size
Min = $($Config.BaseContracts.Min)
Max = $($Config.BaseContracts.Max)
Step = $($Config.BaseContracts.Step)
Values = $((Generate-ParameterRange $Config.BaseContracts) -join ', ')

[MaxContracts]
# Maximum position size
Min = $($Config.MaxContracts.Min)
Max = $($Config.MaxContracts.Max)
Step = $($Config.MaxContracts.Step)
Values = $((Generate-ParameterRange $Config.MaxContracts) -join ', ')

[MaxDailyTrades]
# Daily trade limit
Min = $($Config.MaxDailyTrades.Min)
Max = $($Config.MaxDailyTrades.Max)
Step = $($Config.MaxDailyTrades.Step)
Values = $((Generate-ParameterRange $Config.MaxDailyTrades) -join ', ')
"@
        }
        
        "Phase3" {
            $content += @"

[StartHour]
# Trading session start hour (EST)
Values = $($Config.StartHour.Values -join ', ')

[EndHour]
# Trading session end hour (EST)
Values = $($Config.EndHour.Values -join ', ')

[MinutesBeforeClose]
# Minutes before session close to stop trading
Values = 10, 15, 20, 30
"@
        }
        
        "Phase4" {
            $content += @"

[DailyProfitSoftTarget]
# Soft profit target (reduce risk)
Values = $([math]::Round($Config.DailyProfitSoftTarget * 0.8)), $($Config.DailyProfitSoftTarget), $([math]::Round($Config.DailyProfitSoftTarget * 1.2))

[DailyProfitHardTarget]
# Hard profit target (stop trading)
Values = $([math]::Round($Config.DailyProfitHardTarget * 0.8)), $($Config.DailyProfitHardTarget), $([math]::Round($Config.DailyProfitHardTarget * 1.2))

[DailyLossSoftLimit]
# Soft loss limit (reduce risk)
Values = $([math]::Round($Config.DailyLossSoftLimit * 0.8)), $($Config.DailyLossSoftLimit), $([math]::Round($Config.DailyLossSoftLimit * 1.2))

[DailyLossHardLimit]
# Hard loss limit (stop trading)
Values = $([math]::Round($Config.DailyLossHardLimit * 0.8)), $($Config.DailyLossHardLimit), $([math]::Round($Config.DailyLossHardLimit * 1.2))
"@
        }
    }

    $content += @"


# FIXED PARAMETERS (Don't optimize these simultaneously)
UseTimeFilter = true
ShowDebugInfo = false
SignalQualityMultiplier = 1.0
VolumeMultiplier = 1.0
DisableTimeFilter = false

# PERFORMANCE TARGETS FOR $Asset
# Win Rate Target: $(if ($AssetConfigs[$Asset].Name -eq "Gold") { "55%" } elseif ($AssetConfigs[$Asset].Name -eq "S&P 500") { "52%" } elseif ($AssetConfigs[$Asset].Name -eq "Nasdaq") { "50%" } elseif ($AssetConfigs[$Asset].Name -eq "Crude Oil") { "48%" } else { "45%" })
# Profit Factor Target: $(if ($AssetConfigs[$Asset].Name -eq "Gold") { "1.4+" } elseif ($AssetConfigs[$Asset].Name -eq "S&P 500") { "1.3+" } elseif ($AssetConfigs[$Asset].Name -eq "Nasdaq") { "1.5+" } elseif ($AssetConfigs[$Asset].Name -eq "Crude Oil") { "1.6+" } else { "1.8+" })
# Max Drawdown Target: $(if ($AssetConfigs[$Asset].Name -eq "Gold") { "<8%" } elseif ($AssetConfigs[$Asset].Name -eq "S&P 500") { "<10%" } elseif ($AssetConfigs[$Asset].Name -eq "Nasdaq") { "<12%" } elseif ($AssetConfigs[$Asset].Name -eq "Crude Oil") { "<15%" } else { "<20%" })

# OPTIMIZATION NOTES:
# 1. Start with Phase1 parameters - these are most critical
# 2. Use 6+ months of tick data for reliable results  
# 3. Test on out-of-sample data before going live
# 4. Avoid over-optimization - robust parameters > perfect backtests
"@

    return $content
}

function Generate-NinjaTraderTemplate {
    param($Asset, $Config)
    
    $template = @"
<!-- NinjaTrader Strategy Analyzer Template -->
<!-- Asset: $Asset ($($Config.Name)) -->
<!-- Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') -->

<Strategy Name="FKSStrategyAIO">
    <Parameters>
        <!-- Phase 1: Core Signal Parameters -->
        <Parameter Name="SignalQualityThreshold" Optimize="true" 
                   Min="$($Config.SignalQualityThreshold.Min)" 
                   Max="$($Config.SignalQualityThreshold.Max)" 
                   Step="$($Config.SignalQualityThreshold.Step)" />
        
        <Parameter Name="VolumeThreshold" Optimize="true" 
                   Min="$($Config.VolumeThreshold.Min)" 
                   Max="$($Config.VolumeThreshold.Max)" 
                   Step="$($Config.VolumeThreshold.Step)" />
        
        <Parameter Name="ATRStopMultiplier" Optimize="true" 
                   Min="$($Config.ATRStopMultiplier.Min)" 
                   Max="$($Config.ATRStopMultiplier.Max)" 
                   Step="$($Config.ATRStopMultiplier.Step)" />
        
        <Parameter Name="ATRTargetMultiplier" Optimize="true" 
                   Min="$($Config.ATRTargetMultiplier.Min)" 
                   Max="$($Config.ATRTargetMultiplier.Max)" 
                   Step="$($Config.ATRTargetMultiplier.Step)" />
        
        <!-- Fixed for Phase 1 -->
        <Parameter Name="BaseContracts" Optimize="false" Value="1" />
        <Parameter Name="MaxContracts" Optimize="false" Value="$($Config.MaxContracts.Min)" />
        <Parameter Name="MaxDailyTrades" Optimize="false" Value="$($Config.MaxDailyTrades.Min + 2)" />
        <Parameter Name="StartHour" Optimize="false" Value="3" />
        <Parameter Name="EndHour" Optimize="false" Value="12" />
        
        <!-- Risk Management -->
        <Parameter Name="DailyProfitSoftTarget" Optimize="false" Value="$($Config.DailyProfitSoftTarget)" />
        <Parameter Name="DailyProfitHardTarget" Optimize="false" Value="$($Config.DailyProfitHardTarget)" />
        <Parameter Name="DailyLossSoftLimit" Optimize="false" Value="$($Config.DailyLossSoftLimit)" />
        <Parameter Name="DailyLossHardLimit" Optimize="false" Value="$($Config.DailyLossHardLimit)" />
        
        <!-- Standard Settings -->
        <Parameter Name="UseTimeFilter" Optimize="false" Value="true" />
        <Parameter Name="ShowDebugInfo" Optimize="false" Value="false" />
        <Parameter Name="MinutesBeforeClose" Optimize="false" Value="15" />
    </Parameters>
    
    <!-- Fitness Function: Prioritize Profit Factor and limit Drawdown -->
    <FitnessFunction>
        Net Profit + (Profit Factor * 10000) - (Max Drawdown * 50000) + (Sharpe Ratio * 5000)
    </FitnessFunction>
    
    <!-- Minimum Trade Requirements -->
    <MinimumTrades>50</MinimumTrades>
    <MinimumWinRate>0.40</MinimumWinRate>
    <MinimumProfitFactor>1.20</MinimumProfitFactor>
    <MaximumDrawdown>0.25</MaximumDrawdown>
</Strategy>
"@

    return $template
}

# Generate configuration files for each asset
foreach ($Asset in $Assets) {
    if (-not $AssetConfigs.ContainsKey($Asset)) {
        Write-Warning "Asset '$Asset' not found in configuration. Skipping..."
        continue
    }
    
    $config = $AssetConfigs[$Asset]
    Write-Host "Generating optimization configs for $Asset ($($config.Name))..." -ForegroundColor Green
    
    # Create asset-specific directory
    $assetPath = Join-Path $OutputPath $Asset
    if (-not (Test-Path $assetPath)) {
        New-Item -ItemType Directory -Path $assetPath -Force | Out-Null
    }
    
    # Generate phase-specific configurations
    foreach ($phase in @("Phase1", "Phase2", "Phase3", "Phase4")) {
        $configContent = Generate-OptimizationConfig -Asset $Asset -Config $config -Phase $phase
        $configFile = Join-Path $assetPath "$($Asset)_$($phase)_Config.txt"
        $configContent | Out-File -FilePath $configFile -Encoding UTF8
        Write-Host "  Created: $configFile" -ForegroundColor Cyan
    }
    
    # Generate NinjaTrader template
    $templateContent = Generate-NinjaTraderTemplate -Asset $Asset -Config $config
    $templateFile = Join-Path $assetPath "$($Asset)_NinjaTrader_Template.xml"
    $templateContent | Out-File -FilePath $templateFile -Encoding UTF8
    Write-Host "  Created: $templateFile" -ForegroundColor Cyan
    
    # Generate quick start parameters
    $quickStart = @"
# $Asset ($($config.Name)) Quick Start Parameters
# Copy these into NinjaTrader for immediate testing

SignalQualityThreshold: 0.65
VolumeThreshold: 1.2
ATRStopMultiplier: $($config.ATRStopMultiplier.Min + ($config.ATRStopMultiplier.Max - $config.ATRStopMultiplier.Min) / 2)
ATRTargetMultiplier: $($config.ATRTargetMultiplier.Min + ($config.ATRTargetMultiplier.Max - $config.ATRTargetMultiplier.Min) / 2)
BaseContracts: 1
MaxContracts: $($config.MaxContracts.Min)
MaxDailyTrades: $([math]::Round(($config.MaxDailyTrades.Min + $config.MaxDailyTrades.Max) / 2))
StartHour: 6
EndHour: 16
DailyProfitSoftTarget: $($config.DailyProfitSoftTarget)
DailyProfitHardTarget: $($config.DailyProfitHardTarget)
DailyLossSoftLimit: $($config.DailyLossSoftLimit)
DailyLossHardLimit: $($config.DailyLossHardLimit)

# Expected Performance Targets:
# Win Rate: $(if ($config.Name -eq "Gold") { "55%" } elseif ($config.Name -eq "S&P 500") { "52%" } elseif ($config.Name -eq "Nasdaq") { "50%" } elseif ($config.Name -eq "Crude Oil") { "48%" } else { "45%" })
# Profit Factor: $(if ($config.Name -eq "Gold") { "1.4+" } elseif ($config.Name -eq "S&P 500") { "1.3+" } elseif ($config.Name -eq "Nasdaq") { "1.5+" } elseif ($config.Name -eq "Crude Oil") { "1.6+" } else { "1.8+" })
# Max Drawdown: $(if ($config.Name -eq "Gold") { "<8%" } elseif ($config.Name -eq "S&P 500") { "<10%" } elseif ($config.Name -eq "Nasdaq") { "<12%" } elseif ($config.Name -eq "Crude Oil") { "<15%" } else { "<20%" })
"@
    
    $quickStartFile = Join-Path $assetPath "$($Asset)_QuickStart.txt"
    $quickStart | Out-File -FilePath $quickStartFile -Encoding UTF8
    Write-Host "  Created: $quickStartFile" -ForegroundColor Cyan
}

# Generate master comparison file
$masterComparison = @"
# FKS Strategy Asset Comparison Matrix
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

ASSET VOLATILITY RANKING (Low to High):
1. Gold (GC) - Most Stable
2. S&P 500 (ES) - Balanced  
3. Nasdaq (NQ) - Higher Volatility
4. Crude Oil (CL) - Very Volatile
5. Bitcoin (BTC) - Extreme Volatility

OPTIMIZATION PRIORITY ORDER:
1. Start with Gold (GC) - most predictable
2. Move to S&P 500 (ES) - good balance
3. Test Nasdaq (NQ) - higher rewards/risks
4. Crude Oil (CL) - specialized timing needed
5. Bitcoin (BTC) - proceed with extreme caution

PARAMETER RANGES SUMMARY:
Asset | SigQual | Volume | ATRStop | ATRTarget | MaxContracts | MaxTrades
------|---------|--------|---------|-----------|--------------|----------
"@

foreach ($Asset in $Assets) {
    if ($AssetConfigs.ContainsKey($Asset)) {
        $config = $AssetConfigs[$Asset]
        $masterComparison += "`n$Asset    | $($config.SignalQualityThreshold.Min)-$($config.SignalQualityThreshold.Max)  | $($config.VolumeThreshold.Min)-$($config.VolumeThreshold.Max)   | $($config.ATRStopMultiplier.Min)-$($config.ATRStopMultiplier.Max)    | $($config.ATRTargetMultiplier.Min)-$($config.ATRTargetMultiplier.Max)      | $($config.MaxContracts.Min)-$($config.MaxContracts.Max)         | $($config.MaxDailyTrades.Min)-$($config.MaxDailyTrades.Max)"
    }
}

$masterComparison += @"


EXPECTED PERFORMANCE TARGETS:
Asset | WinRate | ProfitFactor | MaxDrawdown | DailyProfit
------|---------|--------------|-------------|------------
GC    | 55%+    | 1.4+         | <8%         | `$150+
ES    | 52%+    | 1.3+         | <10%        | `$180+  
NQ    | 50%+    | 1.5+         | <12%        | `$200+
CL    | 48%+    | 1.6+         | <15%        | `$120+
BTC   | 45%+    | 1.8+         | <20%        | `$100+

TRADING SESSIONS BY ASSET:
Gold: 2am-11am EST (London heavy)
ES/NQ: 3am-12pm EST (London + NY morning) 
Crude: 3am-11am EST (includes inventory)
Bitcoin: 6am-4pm EST (avoid weekend chaos)

OPTIMIZATION PHASES:
Phase 1: Signal Quality + Volume + ATR (Most Critical)
Phase 2: Position Sizing + Trade Limits
Phase 3: Time Filters + Session Times
Phase 4: Risk Management Limits

Remember: Robust parameters that work across conditions > perfect backtests!
"@

$masterFile = Join-Path $OutputPath "Master_Asset_Comparison.txt"
$masterComparison | Out-File -FilePath $masterFile -Encoding UTF8

Write-Host "`nOptimization configurations generated successfully!" -ForegroundColor Green
Write-Host "Output directory: $OutputPath" -ForegroundColor Yellow
Write-Host "Master comparison: $masterFile" -ForegroundColor Yellow
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1. Start with Gold (GC) Phase1 optimization" -ForegroundColor White
Write-Host "2. Use 6+ months of tick data" -ForegroundColor White  
Write-Host "3. Test on out-of-sample data" -ForegroundColor White
Write-Host "4. Paper trade before going live" -ForegroundColor White
