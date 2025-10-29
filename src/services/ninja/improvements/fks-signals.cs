#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.AddOns.FKS
{
    /// <summary>
    /// Unified signal generation and quality assessment
    /// Coordinates signals from multiple indicators and applies quality scoring
    /// </summary>
    public static class FKS_Signals
    {
        #region Signal History
        private static readonly Queue<UnifiedSignal> signalHistory = new Queue<UnifiedSignal>();
        private static readonly int maxHistorySize = 100;
        private static readonly object signalLock = new object();
        #endregion
        
        #region Signal Quality Weights
        // These weights determine how much each factor contributes to overall signal quality
        private static readonly Dictionary<string, double> qualityWeights = new Dictionary<string, double>
        {
            ["TrendAlignment"] = 0.25,      // 25% - Is signal aligned with trend?
            ["MomentumConfirmation"] = 0.20, // 20% - AO confirmation
            ["VolumeConfirmation"] = 0.15,   // 15% - Volume above average
            ["WaveRatio"] = 0.15,           // 15% - Wave analysis strength
            ["MarketRegime"] = 0.10,        // 10% - Favorable market conditions
            ["TimeOfDay"] = 0.10,           // 10% - Optimal trading hours
            ["CandlePattern"] = 0.05        // 5%  - Candlestick confirmation
        };
        #endregion
        
        #region Setup Definitions
        private static readonly Dictionary<int, SetupDefinition> setupDefinitions = new Dictionary<int, SetupDefinition>
        {
            [1] = new SetupDefinition
            {
                Name = "EMA9 + VWAP Bullish Breakout",
                RequiredSignals = new[] { "G" },
                RequiredConditions = new[] 
                { 
                    "Price > EMA9", 
                    "EMA9 > VWAP", 
                    "AO Bullish", 
                    "Volume > 1.2x Avg" 
                },
                MinQuality = 0.65,
                PreferredMarketRegime = "TRENDING BULL",
                RiskRewardRatio = 3.0
            },
            [2] = new SetupDefinition
            {
                Name = "EMA9 + VWAP Bearish Breakdown",
                RequiredSignals = new[] { "Top" },
                RequiredConditions = new[] 
                { 
                    "Price < EMA9", 
                    "EMA9 < VWAP", 
                    "AO Bearish", 
                    "Volume > 1.2x Avg" 
                },
                MinQuality = 0.65,
                PreferredMarketRegime = "TRENDING BEAR",
                RiskRewardRatio = 3.0
            },
            [3] = new SetupDefinition
            {
                Name = "VWAP Rejection Bounce",
                RequiredSignals = new[] { "G", "^" },
                RequiredConditions = new[] 
                { 
                    "Price near VWAP", 
                    "Rejection candle", 
                    "AO momentum aligned" 
                },
                MinQuality = 0.60,
                PreferredMarketRegime = "RANGING",
                RiskRewardRatio = 2.5
            },
            [4] = new SetupDefinition
            {
                Name = "Support/Resistance + AO Zero Cross",
                RequiredSignals = new[] { "G", "Top", "^", "v" },
                RequiredConditions = new[] 
                { 
                    "At key S/R level", 
                    "AO zero cross", 
                    "Volume breakout" 
                },
                MinQuality = 0.70,
                PreferredMarketRegime = "ANY",
                RiskRewardRatio = 3.5
            }
        };
        #endregion
        
        #region Public Methods
        /// <summary>
        /// Generate a unified signal from component inputs
        /// </summary>
        public static UnifiedSignal GenerateSignal(SignalInputs inputs)
        {
            var signal = new UnifiedSignal
            {
                Timestamp = DateTime.Now,
                SignalType = inputs.AISignalType,
                BaseQuality = inputs.AISignalQuality,
                WaveRatio = inputs.WaveRatio,
                Price = inputs.Price,
                ATR = inputs.ATR
            };
            
            // Calculate comprehensive quality score
            signal.Quality = CalculateSignalQuality(inputs);
            
            // Determine which setup this matches
            signal.SetupNumber = DetermineSetup(inputs, signal);
            
            // Calculate recommended position size
            signal.RecommendedContracts = CalculatePositionSize(signal, inputs);
            
            // Set entry/stop/target levels
            CalculateTradeLevels(signal, inputs);
            
            // Validate signal
            signal.IsValid = ValidateSignal(signal, inputs);
            
            // Add to history
            AddToHistory(signal);
            
            return signal;
        }
        
        /// <summary>
        /// Get signal statistics for dashboard display
        /// </summary>
        public static SignalStatistics GetStatistics(int lookbackBars = 100)
        {
            lock (signalLock)
            {
                var recentSignals = signalHistory.Where(s => s.Timestamp > DateTime.Now.AddHours(-24)).ToList();
                
                return new SignalStatistics
                {
                    TotalSignals = recentSignals.Count,
                    ValidSignals = recentSignals.Count(s => s.IsValid),
                    AverageQuality = recentSignals.Any() ? recentSignals.Average(s => s.Quality) : 0,
                    SignalsBySetup = recentSignals.GroupBy(s => s.SetupNumber)
                        .ToDictionary(g => g.Key, g => g.Count()),
                    BestSetup = recentSignals.Any() ? 
                        recentSignals.GroupBy(s => s.SetupNumber)
                            .OrderByDescending(g => g.Average(s => s.Quality))
                            .First().Key : 0
                };
            }
        }
        
        /// <summary>
        /// Check if we should wait for a better signal
        /// </summary>
        public static bool ShouldWaitForBetterSignal(UnifiedSignal currentSignal)
        {
            // If signal quality is exceptional, take it
            if (currentSignal.Quality > 0.85)
                return false;
            
            // Check recent signal quality trend
            var recentQualities = GetRecentSignalQualities(10);
            if (!recentQualities.Any())
                return false;
            
            var avgRecentQuality = recentQualities.Average();
            var qualityTrend = recentQualities.Count > 5 ? 
                (recentQualities.TakeLast(3).Average() - recentQualities.Take(3).Average()) : 0;
            
            // If quality is improving and current signal is below recent average, wait
            if (qualityTrend > 0.05 && currentSignal.Quality < avgRecentQuality)
                return true;
            
            // If we haven't seen a good signal in a while, take what we can get
            var timeSinceLastGoodSignal = GetTimeSinceLastQualitySignal(0.7);
            if (timeSinceLastGoodSignal > TimeSpan.FromHours(2))
                return false;
            
            return false;
        }
        
        /// <summary>
        /// Get setup-specific tips
        /// </summary>
        public static List<string> GetSetupTips(int setupNumber)
        {
            if (!setupDefinitions.ContainsKey(setupNumber))
                return new List<string>();
            
            var setup = setupDefinitions[setupNumber];
            var tips = new List<string>();
            
            tips.Add($"Setup: {setup.Name}");
            tips.Add($"Min Quality Required: {setup.MinQuality:P0}");
            tips.Add($"Target R:R: {setup.RiskRewardRatio:F1}:1");
            
            if (setup.PreferredMarketRegime != "ANY")
                tips.Add($"Best in: {setup.PreferredMarketRegime} markets");
            
            // Setup-specific tips
            switch (setupNumber)
            {
                case 1:
                    tips.Add("Look for strong volume on breakout");
                    tips.Add("Best during US morning session");
                    break;
                case 2:
                    tips.Add("Watch for failed highs before entry");
                    tips.Add("Stronger in downtrending markets");
                    break;
                case 3:
                    tips.Add("Requires clean rejection candle");
                    tips.Add("Works best in ranging markets");
                    break;
                case 4:
                    tips.Add("Most reliable at major S/R levels");
                    tips.Add("Confirm with multiple timeframes");
                    break;
            }
            
            return tips;
        }
        #endregion
        
        #region Private Methods
        private static double CalculateSignalQuality(SignalInputs inputs)
        {
            var qualityScore = 0.0;
            
            // Trend Alignment (25%)
            double trendScore = 0.0;
            if (inputs.MarketRegime.Contains("BULL") && IsLongSignal(inputs.AISignalType))
                trendScore = 1.0;
            else if (inputs.MarketRegime.Contains("BEAR") && IsShortSignal(inputs.AISignalType))
                trendScore = 1.0;
            else if (inputs.MarketRegime == "RANGING")
                trendScore = 0.7; // Ranging markets are okay for both directions
            else
                trendScore = 0.3; // Counter-trend penalty
            
            qualityScore += trendScore * qualityWeights["TrendAlignment"];
            
            // Momentum Confirmation (20%)
            double momentumScore = 0.0;
            if (inputs.AOConfirmation)
            {
                momentumScore = inputs.AOMomentumStrength; // 0-1 scale
                if (inputs.AOZeroCross)
                    momentumScore = Math.Min(1.0, momentumScore + 0.2); // Bonus for zero cross
            }
            qualityScore += momentumScore * qualityWeights["MomentumConfirmation"];
            
            // Volume Confirmation (15%)
            double volumeScore = Math.Min(1.0, inputs.VolumeRatio / 2.0); // Max out at 2x volume
            qualityScore += volumeScore * qualityWeights["VolumeConfirmation"];
            
            // Wave Ratio (15%)
            double waveScore = 0.0;
            if (inputs.WaveRatio > 2.0)
                waveScore = 1.0;
            else if (inputs.WaveRatio > 1.5)
                waveScore = 0.7;
            else if (inputs.WaveRatio > 1.0)
                waveScore = 0.4;
            else
                waveScore = 0.1;
            qualityScore += waveScore * qualityWeights["WaveRatio"];
            
            // Market Regime (10%)
            double regimeScore = 0.0;
            if (inputs.MarketRegime.Contains("TRENDING"))
                regimeScore = 0.9;
            else if (inputs.MarketRegime == "NEUTRAL")
                regimeScore = 0.6;
            else if (inputs.MarketRegime == "VOLATILE")
                regimeScore = 0.3; // Penalty for high volatility
            else
                regimeScore = 0.5;
            qualityScore += regimeScore * qualityWeights["MarketRegime"];
            
            // Time of Day (10%)
            double timeScore = inputs.IsOptimalSession ? 1.0 : 0.5;
            qualityScore += timeScore * qualityWeights["TimeOfDay"];
            
            // Candle Pattern (5%)
            double candleScore = inputs.HasCandleConfirmation ? 1.0 : 0.3;
            qualityScore += candleScore * qualityWeights["CandlePattern"];
            
            // Apply base quality as a multiplier
            qualityScore *= inputs.AISignalQuality;
            
            return Math.Min(1.0, Math.Max(0.0, qualityScore));
        }
        
        private static int DetermineSetup(SignalInputs inputs, UnifiedSignal signal)
        {
            // Check each setup in order
            
            // Setup 1: EMA9 + VWAP Bullish
            if (IsLongSignal(signal.SignalType) && 
                inputs.PriceAboveEMA9 && 
                inputs.EMA9AboveVWAP &&
                inputs.AOValue > 0 &&
                inputs.VolumeRatio > 1.2)
            {
                return 1;
            }
            
            // Setup 2: EMA9 + VWAP Bearish
            if (IsShortSignal(signal.SignalType) &&
                !inputs.PriceAboveEMA9 &&
                !inputs.EMA9AboveVWAP &&
                inputs.AOValue < 0 &&
                inputs.VolumeRatio > 1.2)
            {
                return 2;
            }
            
            // Setup 3: VWAP Bounce
            if (inputs.NearVWAP && inputs.HasCandleConfirmation)
            {
                return 3;
            }
            
            // Setup 4: S/R with AO Cross
            if ((inputs.NearSupport || inputs.NearResistance) && inputs.AOZeroCross)
            {
                return 4;
            }
            
            return 0; // No specific setup matched
        }
        
        private static int CalculatePositionSize(UnifiedSignal signal, SignalInputs inputs)
        {
            var baseContracts = FKS_Core.CurrentMarketConfig.DefaultContracts;
            var maxContracts = FKS_Core.CurrentMarketConfig.MaxContracts;
            
            // Start with base
            int contracts = baseContracts;
            
            // Quality-based sizing
            if (signal.Quality > 0.85 && signal.WaveRatio > 2.0)
                contracts = Math.Min(maxContracts, 5);
            else if (signal.Quality > 0.70 && signal.WaveRatio > 1.5)
                contracts = 3;
            else if (signal.Quality > 0.60)
                contracts = 2;
            
            // Market regime adjustment
            var regimeAdjustment = FKS_Market.GetDynamicParameters(
                inputs.MarketType, 
                new FKS_Market.MarketRegimeAnalysis { OverallRegime = inputs.MarketRegime }
            );
            
            contracts = (int)(contracts * regimeAdjustment.PositionSizeAdjustment);
            
            // Never exceed max or go below 1
            return Math.Max(1, Math.Min(maxContracts, contracts));
        }
        
        private static void CalculateTradeLevels(UnifiedSignal signal, SignalInputs inputs)
        {
            var atr = inputs.ATR;
            var stopMultiplier = FKS_Core.CurrentMarketConfig.ATRStopMultiplier;
            var targetMultiplier = FKS_Core.CurrentMarketConfig.ATRTargetMultiplier;
            
            // Adjust for market conditions
            if (inputs.MarketRegime == "VOLATILE")
            {
                stopMultiplier *= 1.5;
                targetMultiplier *= 1.5;
            }
            
            if (IsLongSignal(signal.SignalType))
            {
                signal.EntryPrice = inputs.Price;
                signal.StopLoss = inputs.Price - (atr * stopMultiplier);
                signal.Target1 = inputs.Price + (atr * targetMultiplier);
                signal.Target2 = inputs.Price + (atr * targetMultiplier * 2);
                signal.Target3 = inputs.Price + (atr * targetMultiplier * 3);
            }
            else
            {
                signal.EntryPrice = inputs.Price;
                signal.StopLoss = inputs.Price + (atr * stopMultiplier);
                signal.Target1 = inputs.Price - (atr * targetMultiplier);
                signal.Target2 = inputs.Price - (atr * targetMultiplier * 2);
                signal.Target3 = inputs.Price - (atr * targetMultiplier * 3);
            }
            
            // Calculate risk/reward
            var risk = Math.Abs(signal.EntryPrice - signal.StopLoss);
            var reward = Math.Abs(signal.Target1 - signal.EntryPrice);
            signal.RiskRewardRatio = risk > 0 ? reward / risk : 0;
        }
        
        private static bool ValidateSignal(UnifiedSignal signal, SignalInputs inputs)
        {
            // Basic quality check
            if (signal.Quality < FKS_Core.CurrentMarketConfig.SignalQualityThreshold)
                return false;
            
            // Setup-specific validation
            if (signal.SetupNumber > 0 && setupDefinitions.ContainsKey(signal.SetupNumber))
            {
                var setup = setupDefinitions[signal.SetupNumber];
                if (signal.Quality < setup.MinQuality)
                    return false;
                
                if (signal.RiskRewardRatio < setup.RiskRewardRatio * 0.8) // Allow 20% tolerance
                    return false;
            }
            
            // Check for news events
            if (FKS_Market.HasUpcomingHighImpactEvent(inputs.MarketType))
                return false;
            
            // Validate price levels
            if (signal.StopLoss <= 0 || signal.Target1 <= 0)
                return false;
            
            return true;
        }
        
        private static void AddToHistory(UnifiedSignal signal)
        {
            lock (signalLock)
            {
                signalHistory.Enqueue(signal);
                
                // Maintain size limit
                while (signalHistory.Count > maxHistorySize)
                    signalHistory.Dequeue();
            }
        }
        
        private static bool IsLongSignal(string signalType)
        {
            return signalType == "G" || signalType == "^";
        }
        
        private static bool IsShortSignal(string signalType)
        {
            return signalType == "Top" || signalType == "v";
        }
        
        private static List<double> GetRecentSignalQualities(int count)
        {
            lock (signalLock)
            {
                return signalHistory
                    .OrderByDescending(s => s.Timestamp)
                    .Take(count)
                    .Select(s => s.Quality)
                    .ToList();
            }
        }
        
        private static TimeSpan GetTimeSinceLastQualitySignal(double minQuality)
        {
            lock (signalLock)
            {
                var lastGoodSignal = signalHistory
                    .Where(s => s.Quality >= minQuality)
                    .OrderByDescending(s => s.Timestamp)
                    .FirstOrDefault();
                
                return lastGoodSignal != null ? 
                    DateTime.Now - lastGoodSignal.Timestamp : 
                    TimeSpan.FromHours(24);
            }
        }
        #endregion
        
        #region Helper Classes
        public class SignalInputs
        {
            // AI Indicator inputs
            public string AISignalType { get; set; }
            public double AISignalQuality { get; set; }
            public double WaveRatio { get; set; }
            public bool NearSupport { get; set; }
            public bool NearResistance { get; set; }
            
            // AO Indicator inputs
            public double AOValue { get; set; }
            public double AOSignal { get; set; }
            public bool AOConfirmation { get; set; }
            public bool AOZeroCross { get; set; }
            public double AOMomentumStrength { get; set; }
            
            // Market data
            public double Price { get; set; }
            public double ATR { get; set; }
            public double VolumeRatio { get; set; }
            public string MarketType { get; set; }
            public string MarketRegime { get; set; }
            
            // Technical inputs
            public bool PriceAboveEMA9 { get; set; }
            public bool EMA9AboveVWAP { get; set; }
            public bool NearVWAP { get; set; }
            public bool HasCandleConfirmation { get; set; }
            
            // Session info
            public bool IsOptimalSession { get; set; }
        }
        
        public class UnifiedSignal
        {
            public DateTime Timestamp { get; set; }
            public string SignalType { get; set; }
            public double Quality { get; set; }
            public double BaseQuality { get; set; }
            public double WaveRatio { get; set; }
            public int SetupNumber { get; set; }
            public int RecommendedContracts { get; set; }
            public bool IsValid { get; set; }
            
            // Price levels
            public double Price { get; set; }
            public double EntryPrice { get; set; }
            public double StopLoss { get; set; }
            public double Target1 { get; set; }
            public double Target2 { get; set; }
            public double Target3 { get; set; }
            public double ATR { get; set; }
            public double RiskRewardRatio { get; set; }
            
            public override string ToString()
            {
                return $"{SignalType} | Setup {SetupNumber} | Quality: {Quality:P0} | Contracts: {RecommendedContracts}";
            }
        }
        
        public class SetupDefinition
        {
            public string Name { get; set; }
            public string[] RequiredSignals { get; set; }
            public string[] RequiredConditions { get; set; }
            public double MinQuality { get; set; }
            public string PreferredMarketRegime { get; set; }
            public double RiskRewardRatio { get; set; }
        }
        
        public class SignalStatistics
        {
            public int TotalSignals { get; set; }
            public int ValidSignals { get; set; }
            public double AverageQuality { get; set; }
            public Dictionary<int, int> SignalsBySetup { get; set; }
            public int BestSetup { get; set; }
        }
        #endregion
    }
}