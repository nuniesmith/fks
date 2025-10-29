/*
 * FKS Strategy Parameter Testing Matrix
 * Asset-Specific Optimization Guide for: GC, ES, NQ, CL, BTC
 * 
 * This file contains recommended parameter ranges for backtesting and optimization
 * across the 5 main assets in your trading portfolio.
 */

namespace NinjaTrader.NinjaScript.Strategies
{
    public static class FKSParameterTestingMatrix
    {
        #region Asset-Specific Base Configurations
        
        // GOLD (GC) - Most Stable Market
        public static class GoldConfig
        {
            // Signal Quality - Gold has clean patterns
            public const double SignalQualityThreshold_Min = 0.65;
            public const double SignalQualityThreshold_Max = 0.75;
            public const double SignalQualityThreshold_Step = 0.05;
            
            // Volume - Gold has consistent volume patterns
            public const double VolumeThreshold_Min = 1.1;
            public const double VolumeThreshold_Max = 1.4;
            public const double VolumeThreshold_Step = 0.1;
            
            // Position Sizing - Can handle larger positions
            public const int BaseContracts_Min = 1;
            public const int BaseContracts_Max = 3;
            public const int MaxContracts_Min = 3;
            public const int MaxContracts_Max = 5;
            
            // Risk Management - Lower volatility allows tighter stops
            public const double ATRStopMultiplier_Min = 1.5;
            public const double ATRStopMultiplier_Max = 2.5;
            public const double ATRStopMultiplier_Step = 0.25;
            
            public const double ATRTargetMultiplier_Min = 1.2;
            public const double ATRTargetMultiplier_Max = 2.0;
            public const double ATRTargetMultiplier_Step = 0.2;
            
            // Trading Frequency
            public const int MaxDailyTrades_Min = 6;
            public const int MaxDailyTrades_Max = 10;
            
            // Profit/Loss Limits (Conservative)
            public const double DailyProfitSoftTarget = 1800;
            public const double DailyProfitHardTarget = 2700;
            public const double DailyLossSoftLimit = 900;
            public const double DailyLossHardLimit = 1350;
        }
        
        // S&P 500 (ES) - Balanced Market
        public static class SPConfig
        {
            // Signal Quality - ES has good trend following
            public const double SignalQualityThreshold_Min = 0.68;
            public const double SignalQualityThreshold_Max = 0.75;
            public const double SignalQualityThreshold_Step = 0.02;
            
            // Volume - ES has strong volume confirmation
            public const double VolumeThreshold_Min = 1.2;
            public const double VolumeThreshold_Max = 1.5;
            public const double VolumeThreshold_Step = 0.1;
            
            // Position Sizing - Standard sizing
            public const int BaseContracts_Min = 1;
            public const int BaseContracts_Max = 2;
            public const int MaxContracts_Min = 3;
            public const int MaxContracts_Max = 4;
            
            // Risk Management - Moderate volatility
            public const double ATRStopMultiplier_Min = 1.8;
            public const double ATRStopMultiplier_Max = 2.5;
            public const double ATRStopMultiplier_Step = 0.2;
            
            public const double ATRTargetMultiplier_Min = 1.3;
            public const double ATRTargetMultiplier_Max = 2.2;
            public const double ATRTargetMultiplier_Step = 0.3;
            
            // Trading Frequency
            public const int MaxDailyTrades_Min = 5;
            public const int MaxDailyTrades_Max = 8;
            
            // Profit/Loss Limits (Standard)
            public const double DailyProfitSoftTarget = 2000;
            public const double DailyProfitHardTarget = 3000;
            public const double DailyLossSoftLimit = 1000;
            public const double DailyLossHardLimit = 1500;
        }
        
        // NASDAQ (NQ) - Higher Volatility
        public static class NasdaqConfig
        {
            // Signal Quality - NQ needs higher quality due to noise
            public const double SignalQualityThreshold_Min = 0.70;
            public const double SignalQualityThreshold_Max = 0.80;
            public const double SignalQualityThreshold_Step = 0.02;
            
            // Volume - Higher volume requirements for NQ
            public const double VolumeThreshold_Min = 1.3;
            public const double VolumeThreshold_Max = 1.6;
            public const double VolumeThreshold_Step = 0.1;
            
            // Position Sizing - Reduced due to volatility (75% of normal)
            public const int BaseContracts_Min = 1;
            public const int BaseContracts_Max = 2;
            public const int MaxContracts_Min = 2;
            public const int MaxContracts_Max = 4; // Reduced from 5
            
            // Risk Management - Wider stops due to volatility
            public const double ATRStopMultiplier_Min = 2.0;
            public const double ATRStopMultiplier_Max = 3.0;
            public const double ATRStopMultiplier_Step = 0.25;
            
            public const double ATRTargetMultiplier_Min = 1.5;
            public const double ATRTargetMultiplier_Max = 2.5;
            public const double ATRTargetMultiplier_Step = 0.25;
            
            // Trading Frequency - Fewer trades due to volatility
            public const int MaxDailyTrades_Min = 4;
            public const int MaxDailyTrades_Max = 7;
            
            // Profit/Loss Limits (Aggressive but careful)
            public const double DailyProfitSoftTarget = 2200;
            public const double DailyProfitHardTarget = 3300;
            public const double DailyLossSoftLimit = 1100;
            public const double DailyLossHardLimit = 1650;
        }
        
        // CRUDE OIL (CL) - Very Volatile
        public static class CrudeConfig
        {
            // Signal Quality - CL needs very high quality signals
            public const double SignalQualityThreshold_Min = 0.72;
            public const double SignalQualityThreshold_Max = 0.85;
            public const double SignalQualityThreshold_Step = 0.03;
            
            // Volume - Strong volume confirmation needed
            public const double VolumeThreshold_Min = 1.4;
            public const double VolumeThreshold_Max = 1.8;
            public const double VolumeThreshold_Step = 0.1;
            
            // Position Sizing - Significantly reduced (50% of normal)
            public const int BaseContracts_Min = 1;
            public const int BaseContracts_Max = 1; // Keep at minimum
            public const int MaxContracts_Min = 1;
            public const int MaxContracts_Max = 3; // Much reduced
            
            // Risk Management - Very wide stops
            public const double ATRStopMultiplier_Min = 2.5;
            public const double ATRStopMultiplier_Max = 4.0;
            public const double ATRStopMultiplier_Step = 0.3;
            
            public const double ATRTargetMultiplier_Min = 1.8;
            public const double ATRTargetMultiplier_Max = 3.0;
            public const double ATRTargetMultiplier_Step = 0.3;
            
            // Trading Frequency - Very limited
            public const int MaxDailyTrades_Min = 2;
            public const int MaxDailyTrades_Max = 5;
            
            // Profit/Loss Limits (Conservative due to volatility)
            public const double DailyProfitSoftTarget = 1500;
            public const double DailyProfitHardTarget = 2500;
            public const double DailyLossSoftLimit = 800;
            public const double DailyLossHardLimit = 1200;
            
            // Special EIA Inventory considerations
            // Wednesday 10:30-10:40 AM: Reduce to minimum size
            public const bool UseEIAReduction = true;
        }
        
        // BITCOIN (BTC) - Extreme Volatility
        public static class BitcoinConfig
        {
            // Signal Quality - BTC needs premium signals only
            public const double SignalQualityThreshold_Min = 0.75;
            public const double SignalQualityThreshold_Max = 0.90;
            public const double SignalQualityThreshold_Step = 0.03;
            
            // Volume - Very high volume requirements
            public const double VolumeThreshold_Min = 1.5;
            public const double VolumeThreshold_Max = 2.0;
            public const double VolumeThreshold_Step = 0.1;
            
            // Position Sizing - Heavily reduced (50% of normal)
            public const int BaseContracts_Min = 1;
            public const int BaseContracts_Max = 1; // Minimum only
            public const int MaxContracts_Min = 1;
            public const int MaxContracts_Max = 2; // Very limited
            
            // Risk Management - Extremely wide stops
            public const double ATRStopMultiplier_Min = 3.0;
            public const double ATRStopMultiplier_Max = 5.0;
            public const double ATRStopMultiplier_Step = 0.5;
            
            public const double ATRTargetMultiplier_Min = 2.0;
            public const double ATRTargetMultiplier_Max = 4.0;
            public const double ATRTargetMultiplier_Step = 0.5;
            
            // Trading Frequency - Very limited
            public const int MaxDailyTrades_Min = 1;
            public const int MaxDailyTrades_Max = 4;
            
            // Profit/Loss Limits (Very conservative)
            public const double DailyProfitSoftTarget = 1200;
            public const double DailyProfitHardTarget = 2000;
            public const double DailyLossSoftLimit = 600;
            public const double DailyLossHardLimit = 1000;
            
            // Weekend reduction
            public const bool UseWeekendReduction = true;
        }
        
        #endregion
        
        #region Time Filter Testing by Asset
        
        // Different assets perform better in different sessions
        public static class TimeFilterTesting
        {
            // GOLD - Best during London/early NY overlap
            public static class GoldTimes
            {
                public static readonly (int start, int end)[] TestRanges = {
                    (2, 11),   // Early London to before lunch
                    (3, 12),   // Standard London + NY morning
                    (4, 13),   // Late London start
                    (3, 10),   // London heavy
                    (6, 14)    // NY heavy
                };
            }
            
            // ES/NQ - Best during NY session
            public static class USEquityTimes
            {
                public static readonly (int start, int end)[] TestRanges = {
                    (3, 12),   // Your current setting
                    (6, 15),   // Pure NY session
                    (7, 14),   // NY core hours
                    (8, 13),   // NY morning only
                    (3, 10)    // London bias
                };
            }
            
            // CRUDE - Energy-specific times
            public static class CrudeTimes
            {
                public static readonly (int start, int end)[] TestRanges = {
                    (3, 11),   // Early session (inventory reports)
                    (6, 14),   // NY energy session
                    (7, 12),   // Core energy hours
                    (8, 11)    // Morning energy only
                };
            }
            
            // BTC - 24/7 but avoid weekend chaos
            public static class BitcoinTimes
            {
                public static readonly (int start, int end)[] TestRanges = {
                    (0, 23),   // Full day (weekdays only)
                    (3, 15),   // Traditional hours
                    (6, 18),   // NY + London overlap
                    (8, 16)    // Conservative hours
                };
            }
        }
        
        #endregion
        
        #region Bar Type Specific Testing
        
        public static class BarTypeMatrix
        {
            // Standard Time Bars
            public static class StandardBars
            {
                public static readonly int[] TimeFrames = { 1, 2, 3, 5, 15 }; // minutes
                
                // Adjust signal quality by timeframe
                public static double GetSignalQualityAdjustment(int timeframe)
                {
                    return timeframe switch
                    {
                        1 => 0.05,   // Higher quality needed for 1min
                        2 => 0.02,   // Slight increase for 2min
                        3 => 0.0,    // Your standard
                        5 => -0.02,  // Can be slightly more lenient
                        15 => -0.05  // More lenient for higher timeframes
                    };
                }
            }
            
            // Heiken Ashi Bars
            public static class HeikenAshiBars
            {
                public static readonly int[] TimeFrames = { 2, 3, 5, 15 }; // minutes
                
                // HA needs different parameters due to smoothing
                public static double GetVolumeMultiplier(int timeframe)
                {
                    return timeframe switch
                    {
                        2 => 1.3,    // Higher volume needed
                        3 => 1.2,    // Standard
                        5 => 1.1,    // Slightly lower
                        15 => 1.0    // Standard for higher TF
                    };
                }
                
                public static double GetSignalQualityBoost() => 0.1; // HA patterns get 10% boost
            }
            
            // Renko Bars
            public static class RenkoBars
            {
                // Renko sizes to test (in ticks)
                public static readonly Dictionary<string, int[]> RenkoSizes = new()
                {
                    ["GC"] = { 2, 3, 4, 5 },      // Gold: 2-5 ticks
                    ["ES"] = { 1, 2, 3, 4 },      // S&P: 1-4 ticks  
                    ["NQ"] = { 1, 2, 3 },         // Nasdaq: 1-3 ticks
                    ["CL"] = { 2, 3, 4, 5, 6 },   // Crude: 2-6 ticks
                    ["BTC"] = { 5, 10, 15, 20 }   // Bitcoin: 5-20 ticks
                };
                
                public static double GetATRMultiplierAdjustment() => 0.5; // Renko needs different ATR logic
            }
        }
        
        #endregion
        
        #region Optimization Sequences
        
        public static class OptimizationSequence
        {
            // Phase 1: Core Signal Parameters
            public static readonly string[] Phase1Parameters = {
                "SignalQualityThreshold",
                "VolumeThreshold", 
                "ATRStopMultiplier",
                "ATRTargetMultiplier"
            };
            
            // Phase 2: Position Sizing
            public static readonly string[] Phase2Parameters = {
                "BaseContracts",
                "MaxContracts",
                "MaxDailyTrades"
            };
            
            // Phase 3: Time Filters
            public static readonly string[] Phase3Parameters = {
                "StartHour",
                "EndHour", 
                "MinutesBeforeClose"
            };
            
            // Phase 4: Risk Management
            public static readonly string[] Phase4Parameters = {
                "DailyProfitSoftTarget",
                "DailyProfitHardTarget",
                "DailyLossSoftLimit", 
                "DailyLossHardLimit"
            };
        }
        
        #endregion
        
        #region Expected Performance Metrics by Asset
        
        public static class PerformanceTargets
        {
            public static readonly Dictionary<string, AssetTargets> Targets = new()
            {
                ["GC"] = new AssetTargets
                {
                    WinRate = 0.55,           // 55% win rate target
                    ProfitFactor = 1.4,       // 1.4+ profit factor
                    MaxDrawdown = 0.08,       // 8% max drawdown
                    Sharpe = 1.2,             // 1.2+ Sharpe ratio
                    DailyAvgProfit = 150      // $150 avg daily profit
                },
                
                ["ES"] = new AssetTargets
                {
                    WinRate = 0.52,
                    ProfitFactor = 1.3,
                    MaxDrawdown = 0.10,
                    Sharpe = 1.1,
                    DailyAvgProfit = 180
                },
                
                ["NQ"] = new AssetTargets
                {
                    WinRate = 0.50,           // Lower due to volatility
                    ProfitFactor = 1.5,       // Higher profit factor needed
                    MaxDrawdown = 0.12,
                    Sharpe = 1.0,
                    DailyAvgProfit = 200
                },
                
                ["CL"] = new AssetTargets
                {
                    WinRate = 0.48,           // Lowest due to volatility
                    ProfitFactor = 1.6,       // Highest profit factor needed
                    MaxDrawdown = 0.15,
                    Sharpe = 0.9,
                    DailyAvgProfit = 120
                },
                
                ["BTC"] = new AssetTargets
                {
                    WinRate = 0.45,           // Very challenging
                    ProfitFactor = 1.8,       // Needs big winners
                    MaxDrawdown = 0.20,       // Expect high drawdowns
                    Sharpe = 0.8,
                    DailyAvgProfit = 100      // Conservative target
                }
            };
        }
        
        public class AssetTargets
        {
            public double WinRate { get; set; }
            public double ProfitFactor { get; set; }
            public double MaxDrawdown { get; set; }
            public double Sharpe { get; set; }
            public double DailyAvgProfit { get; set; }
        }
        
        #endregion
    }
}
