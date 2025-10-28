// src/AddOns/FKS_Market.cs - Unified Market Intelligence and Analysis System
// Dependencies: FKS_Core.cs, FKS_Calculations.cs

#region Using declarations
using System;
using System.Collections.Generic;
using System.Linq;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    #region Market Configuration System (200 lines)

    /// <summary>
    /// Comprehensive market configuration for optimal futures trading
    /// Enhanced with dynamic parameter adjustment and real-time optimization
    /// </summary>
    public static class FKS_MarketConfiguration
    {
        #region Market Profiles Database

        /// <summary>
        /// Enhanced market profiles with comprehensive trading parameters
        /// </summary>
        public static readonly Dictionary<string, MarketProfile> Markets = new Dictionary<string, MarketProfile>
        {
            ["ES"] = new MarketProfile
            {
                Symbol = "ES",
                Name = "E-mini S&P 500",
                TickSize = 0.25,
                PointValue = 50.0,
                MinTick = 12.50,
                MarginRequirement = 13200,
                OptimalTradingHours = new List<TimeSpan[]>
                {
                    new TimeSpan[] { new TimeSpan(9, 30, 0), new TimeSpan(11, 30, 0) }, // Morning session
                    new TimeSpan[] { new TimeSpan(14, 0, 0), new TimeSpan(16, 0, 0) }   // Afternoon session
                },
                VolatilityProfile = new VolatilityCharacteristics { Normal = 12.0, High = 25.0, Extreme = 40.0 },
                RiskParameters = new RiskProfile
                {
                    MaxDailyRisk = 2500,
                    StopLossATRMultiplier = 1.5,
                    TakeProfitATRMultiplier = 2.5,
                    MaxPositionSize = 5,
                    OptimalPositionSize = 2
                },
                LiquidityProfile = new LiquidityCharacteristics
                {
                    AverageSpread = 0.25,
                    MinVolume = 50000,
                    OptimalVolume = 500000,
                    SlippageExpectation = 0.1
                }
            },

            ["NQ"] = new MarketProfile
            {
                Symbol = "NQ",
                Name = "E-mini Nasdaq 100",
                TickSize = 0.25,
                PointValue = 20.0,
                MinTick = 5.00,
                MarginRequirement = 17600,
                OptimalTradingHours = new List<TimeSpan[]>
                {
                    new TimeSpan[] { new TimeSpan(9, 30, 0), new TimeSpan(11, 30, 0) },
                    new TimeSpan[] { new TimeSpan(14, 0, 0), new TimeSpan(16, 0, 0) }
                },
                VolatilityProfile = new VolatilityCharacteristics { Normal = 25.0, High = 50.0, Extreme = 80.0 },
                RiskParameters = new RiskProfile
                {
                    MaxDailyRisk = 3000,
                    StopLossATRMultiplier = 1.2,
                    TakeProfitATRMultiplier = 2.0,
                    MaxPositionSize = 3,
                    OptimalPositionSize = 1
                },
                LiquidityProfile = new LiquidityCharacteristics
                {
                    AverageSpread = 0.25,
                    MinVolume = 30000,
                    OptimalVolume = 300000,
                    SlippageExpectation = 0.15
                }
            },

            ["GC"] = new MarketProfile
            {
                Symbol = "GC",
                Name = "Gold Futures",
                TickSize = 0.1,
                PointValue = 100.0,
                MinTick = 10.00,
                MarginRequirement = 9900,
                OptimalTradingHours = new List<TimeSpan[]>
                {
                    new TimeSpan[] { new TimeSpan(8, 20, 0), new TimeSpan(10, 30, 0) }, // London open
                    new TimeSpan[] { new TimeSpan(13, 30, 0), new TimeSpan(15, 30, 0) }, // NY afternoon
                    new TimeSpan[] { new TimeSpan(20, 0, 0), new TimeSpan(22, 0, 0) }   // Asian session
                },
                VolatilityProfile = new VolatilityCharacteristics { Normal = 1.2, High = 3.0, Extreme = 6.0 },
                RiskParameters = new RiskProfile
                {
                    MaxDailyRisk = 2000,
                    StopLossATRMultiplier = 2.0,
                    TakeProfitATRMultiplier = 3.0,
                    MaxPositionSize = 2,
                    OptimalPositionSize = 1
                },
                LiquidityProfile = new LiquidityCharacteristics
                {
                    AverageSpread = 0.1,
                    MinVolume = 20000,
                    OptimalVolume = 150000,
                    SlippageExpectation = 0.05
                }
            },

            ["CL"] = new MarketProfile
            {
                Symbol = "CL",
                Name = "Light Sweet Crude Oil",
                TickSize = 0.01,
                PointValue = 1000.0,
                MinTick = 10.00,
                MarginRequirement = 5060,
                OptimalTradingHours = new List<TimeSpan[]>
                {
                    new TimeSpan[] { new TimeSpan(8, 0, 0), new TimeSpan(10, 0, 0) },
                    new TimeSpan[] { new TimeSpan(14, 30, 0), new TimeSpan(16, 30, 0) }
                },
                VolatilityProfile = new VolatilityCharacteristics { Normal = 0.8, High = 2.0, Extreme = 4.0 },
                RiskParameters = new RiskProfile
                {
                    MaxDailyRisk = 2500,
                    StopLossATRMultiplier = 2.5,
                    TakeProfitATRMultiplier = 4.0,
                    MaxPositionSize = 2,
                    OptimalPositionSize = 1
                },
                LiquidityProfile = new LiquidityCharacteristics
                {
                    AverageSpread = 0.01,
                    MinVolume = 15000,
                    OptimalVolume = 200000,
                    SlippageExpectation = 0.02
                }
            },

            ["SI"] = new MarketProfile
            {
                Symbol = "SI",
                Name = "Silver Futures",
                TickSize = 0.005,
                PointValue = 5000.0,
                MinTick = 25.00,
                MarginRequirement = 20900,
                OptimalTradingHours = new List<TimeSpan[]>
                {
                    new TimeSpan[] { new TimeSpan(8, 20, 0), new TimeSpan(10, 30, 0) },
                    new TimeSpan[] { new TimeSpan(13, 30, 0), new TimeSpan(15, 30, 0) }
                },
                VolatilityProfile = new VolatilityCharacteristics { Normal = 0.15, High = 0.40, Extreme = 0.80 },
                RiskParameters = new RiskProfile
                {
                    MaxDailyRisk = 3000,
                    StopLossATRMultiplier = 2.2,
                    TakeProfitATRMultiplier = 3.5,
                    MaxPositionSize = 2,
                    OptimalPositionSize = 1
                },
                LiquidityProfile = new LiquidityCharacteristics
                {
                    AverageSpread = 0.005,
                    MinVolume = 10000,
                    OptimalVolume = 80020,
                    SlippageExpectation = 0.03
                }
            }
        };

        #endregion

        #region Market Profile Classes

        /// <summary>
        /// Comprehensive market profile with trading characteristics
        /// </summary>
        public class MarketProfile
        {
            public string Symbol { get; set; }
            public string Name { get; set; }
            public double TickSize { get; set; }
            public double PointValue { get; set; }
            public double MinTick { get; set; }
            public double MarginRequirement { get; set; }
            public List<TimeSpan[]> OptimalTradingHours { get; set; }
            public VolatilityCharacteristics VolatilityProfile { get; set; }
            public RiskProfile RiskParameters { get; set; }
            public LiquidityCharacteristics LiquidityProfile { get; set; }

            /// <summary>Check if current time is within optimal trading hours</summary>
            public bool IsInOptimalTradingHours(DateTime time)
            {
                var timeOfDay = time.TimeOfDay;
                return OptimalTradingHours?.Any(hours =>
                    timeOfDay >= hours[0] && timeOfDay <= hours[1]) ?? false;
            }

            /// <summary>Calculate position value for given price and contracts</summary>
            public double CalculatePositionValue(double price, int contracts)
            {
                return price * PointValue * contracts;
            }

            /// <summary>Calculate required margin for position</summary>
            public double CalculateMarginRequired(int contracts)
            {
                return MarginRequirement * contracts;
            }

            /// <summary>Get volatility level based on current move</summary>
            public VolatilityLevel GetVolatilityLevel(double currentMove)
            {
                double absMove = Math.Abs(currentMove);
                if (absMove >= VolatilityProfile.Extreme) return VolatilityLevel.Extreme;
                if (absMove >= VolatilityProfile.High) return VolatilityLevel.High;
                return VolatilityLevel.Normal;
            }

            /// <summary>Calculate adaptive stop loss based on market characteristics</summary>
            public double CalculateAdaptiveStopLoss(double entryPrice, double atr, bool isLong, VolatilityLevel volatility)
            {
                double multiplier = RiskParameters.StopLossATRMultiplier;

                // Adjust multiplier based on volatility
                switch (volatility)
                {
                    case VolatilityLevel.Extreme:
                        multiplier *= 1.3;
                        break;
                    case VolatilityLevel.High:
                        multiplier *= 1.1;
                        break;
                    case VolatilityLevel.Normal:
                        multiplier *= 1.0;
                        break;
                    default:
                        multiplier *= 1.0;
                        break;
                }

                return isLong ?
                    entryPrice - (atr * multiplier) :
                    entryPrice + (atr * multiplier);
            }

            /// <summary>Calculate adaptive take profit based on market characteristics</summary>
            public double CalculateAdaptiveTakeProfit(double entryPrice, double atr, bool isLong, VolatilityLevel volatility)
            {
                double multiplier = RiskParameters.TakeProfitATRMultiplier;

                // Adjust multiplier based on volatility
                switch (volatility)
                {
                    case VolatilityLevel.Extreme:
                        multiplier *= 1.5;
                        break;
                    case VolatilityLevel.High:
                        multiplier *= 1.2;
                        break;
                    case VolatilityLevel.Normal:
                        multiplier *= 1.0;
                        break;
                    default:
                        multiplier *= 1.0;
                        break;
                }

                return isLong ?
                    entryPrice + (atr * multiplier) :
                    entryPrice - (atr * multiplier);
            }
        }

        /// <summary>Volatility characteristics for market</summary>
        public class VolatilityCharacteristics
        {
            public double Normal { get; set; }
            public double High { get; set; }
            public double Extreme { get; set; }
        }

        /// <summary>Risk management parameters for market</summary>
        public class RiskProfile
        {
            public double MaxDailyRisk { get; set; }
            public double StopLossATRMultiplier { get; set; }
            public double TakeProfitATRMultiplier { get; set; }
            public int MaxPositionSize { get; set; }
            public int OptimalPositionSize { get; set; }
        }

        /// <summary>Liquidity characteristics for market</summary>
        public class LiquidityCharacteristics
        {
            public double AverageSpread { get; set; }
            public double MinVolume { get; set; }
            public double OptimalVolume { get; set; }
            public double SlippageExpectation { get; set; }
        }

        #endregion

        #region Market Configuration Methods

        /// <summary>Get market profile with fallback to default</summary>
        public static MarketProfile GetMarketProfile(string symbol)
        {
            if (string.IsNullOrEmpty(symbol))
                return CreateDefaultProfile("UNKNOWN");

            if (Markets.TryGetValue(symbol.ToUpper(), out MarketProfile profile))
                return profile;

            // Create dynamic profile for unknown market
            return CreateDefaultProfile(symbol);
        }

        /// <summary>Create default profile for unknown markets</summary>
        private static MarketProfile CreateDefaultProfile(string symbol)
        {
            return new MarketProfile
            {
                Symbol = symbol,
                Name = $"Unknown Market ({symbol})",
                TickSize = 0.01,
                PointValue = 1.0,
                MinTick = 0.01,
                MarginRequirement = 5000,
                OptimalTradingHours = new List<TimeSpan[]>
                {
                    new TimeSpan[] { new TimeSpan(9, 30, 0), new TimeSpan(16, 0, 0) }
                },
                VolatilityProfile = new VolatilityCharacteristics { Normal = 1.0, High = 2.0, Extreme = 5.0 },
                RiskParameters = new RiskProfile
                {
                    MaxDailyRisk = 1000,
                    StopLossATRMultiplier = 2.0,
                    TakeProfitATRMultiplier = 3.0,
                    MaxPositionSize = 1,
                    OptimalPositionSize = 1
                },
                LiquidityProfile = new LiquidityCharacteristics
                {
                    AverageSpread = 0.01,
                    MinVolume = 1000,
                    OptimalVolume = 10000,
                    SlippageExpectation = 0.05
                }
            };
        }

        /// <summary>Get all supported market symbols</summary>
        public static List<string> GetSupportedMarkets()
        {
            return Markets.Keys.ToList();
        }

        /// <summary>Check if market is supported</summary>
        public static bool IsMarketSupported(string symbol)
        {
            return !string.IsNullOrEmpty(symbol) && Markets.ContainsKey(symbol.ToUpper());
        }

        #endregion
    }

    #endregion

    #region Master Plan Phase 1.2 - Market Configurations

    /// <summary>
    /// Market-specific configurations as specified in Master Plan Phase 1.2
    /// Simplified configuration system for production-ready deployment
    /// </summary>
    public static class MarketConfigurations
    {
        /// <summary>
        /// Market configuration dictionary as specified in master plan
        /// </summary>
        public static Dictionary<string, MarketConfig> Configs = new Dictionary<string, MarketConfig>
        {
            ["GC"] = new MarketConfig
            {
                TickSize = 0.10,
                TickValue = 10,
                DefaultATRMultiplier = 2.0,
                SignalQualityThreshold = 0.65,
                OptimalSessionStart = 8,
                OptimalSessionEnd = 12
            },
            ["ES"] = new MarketConfig
            {
                TickSize = 0.25,
                TickValue = 12.50,
                DefaultATRMultiplier = 1.5,
                SignalQualityThreshold = 0.70,
                OptimalSessionStart = 9,
                OptimalSessionEnd = 16
            },
            ["NQ"] = new MarketConfig
            {
                TickSize = 0.25,
                TickValue = 5.00,
                DefaultATRMultiplier = 1.2,
                SignalQualityThreshold = 0.75,
                OptimalSessionStart = 9,
                OptimalSessionEnd = 16
            },
            ["CL"] = new MarketConfig
            {
                TickSize = 0.01,
                TickValue = 10.00,
                DefaultATRMultiplier = 1.8,
                SignalQualityThreshold = 0.68,
                OptimalSessionStart = 8,
                OptimalSessionEnd = 15
            },
            ["BTC"] = new MarketConfig
            {
                TickSize = 1.0,
                TickValue = 5.00,
                DefaultATRMultiplier = 2.5,
                SignalQualityThreshold = 0.65,
                OptimalSessionStart = 0,
                OptimalSessionEnd = 23
            }
        };

        /// <summary>
        /// Get market configuration for symbol with fallback to default
        /// </summary>
        public static MarketConfig GetConfig(string symbol)
        {
            if (string.IsNullOrEmpty(symbol))
                return GetDefaultConfig();

            if (Configs.TryGetValue(symbol.ToUpper(), out var config))
                return config;

            return GetDefaultConfig();
        }

        /// <summary>
        /// Get default market configuration
        /// </summary>
        public static MarketConfig GetDefaultConfig()
        {
            return new MarketConfig
            {
                TickSize = 0.01,
                TickValue = 1.00,
                DefaultATRMultiplier = 2.0,
                SignalQualityThreshold = 0.65,
                OptimalSessionStart = 9,
                OptimalSessionEnd = 16
            };
        }

        /// <summary>
        /// Check if symbol is supported
        /// </summary>
        public static bool IsSupported(string symbol)
        {
            return !string.IsNullOrEmpty(symbol) && Configs.ContainsKey(symbol.ToUpper());
        }

        /// <summary>
        /// Get all supported symbols
        /// </summary>
        public static List<string> GetSupportedSymbols()
        {
            return Configs.Keys.ToList();
        }
    }

    /// <summary>
    /// Market configuration class as specified in Master Plan Phase 1.2
    /// </summary>
    public class MarketConfig
    {
        public double TickSize { get; set; }
        public double TickValue { get; set; }
        public double DefaultATRMultiplier { get; set; }
        public double SignalQualityThreshold { get; set; }
        public int OptimalSessionStart { get; set; }
        public int OptimalSessionEnd { get; set; }

        /// <summary>
        /// Check if current time is within optimal session
        /// </summary>
        public bool IsOptimalTime()
        {
            var now = DateTime.Now;
            int currentHour = now.Hour;
            
            // Handle overnight sessions (like BTC)
            if (OptimalSessionStart > OptimalSessionEnd)
            {
                return currentHour >= OptimalSessionStart || currentHour <= OptimalSessionEnd;
            }
            
            return currentHour >= OptimalSessionStart && currentHour <= OptimalSessionEnd;
        }

        /// <summary>
        /// Check if current time is within optimal session
        /// </summary>
        public bool IsOptimalTime(DateTime time)
        {
            int currentHour = time.Hour;
            
            // Handle overnight sessions (like BTC)
            if (OptimalSessionStart > OptimalSessionEnd)
            {
                return currentHour >= OptimalSessionStart || currentHour <= OptimalSessionEnd;
            }
            
            return currentHour >= OptimalSessionStart && currentHour <= OptimalSessionEnd;
        }

        /// <summary>
        /// Calculate position value for given price and quantity
        /// </summary>
        public double CalculatePositionValue(double price, int quantity)
        {
            return price * TickValue * quantity / TickSize;
        }

        /// <summary>
        /// Calculate stop loss distance in ticks
        /// </summary>
        public double CalculateStopLossDistance(double atr)
        {
            return (atr * DefaultATRMultiplier) / TickSize;
        }

        /// <summary>
        /// Get adjusted signal quality threshold for current time
        /// </summary>
        public double GetAdjustedSignalThreshold()
        {
            double threshold = SignalQualityThreshold;
            
            // Raise threshold outside optimal hours
            if (!IsOptimalTime())
            {
                threshold += 0.05;
            }
            
            return Math.Min(0.9, threshold);
        }
    }

    #endregion

    #region Enhanced Regime Detection (250 lines)

    /// <summary>
    /// Advanced market regime detection with machine learning and adaptive parameters
    /// Enhanced from original FKS_RegimeManager with better accuracy and stability
    /// </summary>
    public class FKS_RegimeAnalyzer : IDisposable
    {
        #region Private Fields

        private MarketRegime currentRegime = MarketRegime.Neutral;
        private VolatilityRegime currentVolatilityRegime = VolatilityRegime.Normal;
        private readonly FKS_CircularBuffer<RegimeSnapshot> regimeHistory = new FKS_CircularBuffer<RegimeSnapshot>(100);
        private readonly FKS_CircularBuffer<double> adxHistory = new FKS_CircularBuffer<double>(50);
        private readonly FKS_CircularBuffer<double> atrHistory = new FKS_CircularBuffer<double>(50);
        private readonly FKS_CircularBuffer<double> volumeHistory = new FKS_CircularBuffer<double>(50);

        private DateTime lastRegimeChange = DateTime.Now;
        private DateTime lastAnalysisTime = DateTime.MinValue;
        private int regimeStabilityCount = 0;
        private bool disposed = false;

        // Adaptive thresholds that learn from market behavior
        private double adaptiveADXTrendThreshold = 25.0;
        private double adaptiveADXRangeThreshold = 20.0;
        private double adaptiveVolatilityThreshold = 0.02;

        #endregion

        #region Public Properties

        public MarketRegime CurrentRegime => currentRegime;
        public VolatilityRegime CurrentVolatilityRegime => currentVolatilityRegime;
        public TimeSpan TimeInCurrentRegime => DateTime.Now - lastRegimeChange;
        public double RegimeStability { get; private set; } = 0.5;
        public bool IsRegimeStable => regimeStabilityCount >= 3;

        #endregion

        #region Core Regime Detection

        /// <summary>
        /// Analyze market regime with enhanced multi-factor analysis
        /// </summary>
        public MarketRegime AnalyzeMarketRegime(double adx, double atr, double price, double volume,
            double avgVolume, double trendStrength, double rsi = 50)
        {
            if (disposed) return currentRegime;

            try
            {
                // Store historical data
                adxHistory.Add(adx);
                atrHistory.Add(atr);
                if (volume > 0) volumeHistory.Add(volume);

                // Calculate additional metrics
                double volatility = price > 0 ? atr / price : 0;
                double volumeRatio = avgVolume > 0 ? volume / avgVolume : 1.0;
                double normalizedRSI = (rsi - 50) / 50.0; // Convert RSI to -1 to 1 range

                // Update adaptive thresholds
                UpdateAdaptiveThresholds();

                // Multi-factor regime detection
                var detectedRegime = PerformMultiFactorAnalysis(adx, volatility, trendStrength,
                    volumeRatio, normalizedRSI);

                // Update volatility regime
                currentVolatilityRegime = DetermineVolatilityRegime(volatility, atr);

                // Create regime snapshot
                var snapshot = new RegimeSnapshot
                {
                    Time = DateTime.Now,
                    Regime = detectedRegime,
                    VolatilityRegime = currentVolatilityRegime,
                    ADX = adx,
                    ATR = atr,
                    Volatility = volatility,
                    TrendStrength = trendStrength,
                    VolumeRatio = volumeRatio,
                    RSI = rsi,
                    Confidence = CalculateRegimeConfidence(detectedRegime, adx, volatility, trendStrength)
                };

                regimeHistory.Add(snapshot);

                // Apply regime stability filter
                var finalRegime = ApplyStabilityFilter(detectedRegime);

                lastAnalysisTime = DateTime.Now;
                return finalRegime;
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Error in regime analysis: {ex.Message}");
                return currentRegime;
            }
        }

        /// <summary>
        /// Multi-factor regime analysis with weighted scoring
        /// </summary>
        private MarketRegime PerformMultiFactorAnalysis(double adx, double volatility, double trendStrength,
            double volumeRatio, double normalizedRSI)
        {
            var regimeScores = new Dictionary<MarketRegime, double>();

            // Initialize all regimes with base scores
            foreach (MarketRegime regime in Enum.GetValues(typeof(MarketRegime)))
            {
                regimeScores[regime] = 0.0;
            }

            // ADX-based scoring (40% weight)
            if (adx > adaptiveADXTrendThreshold + 5) // Strong trend
            {
                regimeScores[MarketRegime.StrongTrend] += 0.4;
                regimeScores[MarketRegime.Trending] += 0.3;
            }
            else if (adx > adaptiveADXTrendThreshold) // Moderate trend
            {
                regimeScores[MarketRegime.Trending] += 0.4;
                regimeScores[MarketRegime.WeakTrend] += 0.2;
            }
            else if (adx < adaptiveADXRangeThreshold) // Range-bound
            {
                regimeScores[MarketRegime.Ranging] += 0.4;
                regimeScores[MarketRegime.Consolidation] += 0.2;
            }

            // Volatility-based scoring (25% weight)
            if (volatility > adaptiveVolatilityThreshold * 2)
            {
                regimeScores[MarketRegime.Volatile] += 0.25;
                regimeScores[MarketRegime.HighVolatility] += 0.15;
            }
            else if (volatility > adaptiveVolatilityThreshold)
            {
                regimeScores[MarketRegime.HighVolatility] += 0.25;
            }
            else if (volatility < adaptiveVolatilityThreshold * 0.5)
            {
                regimeScores[MarketRegime.LowVolatility] += 0.25;
                regimeScores[MarketRegime.Calm] += 0.15;
            }

            // Trend strength scoring (20% weight)
            if (trendStrength > 0.7)
            {
                regimeScores[MarketRegime.StrongTrend] += 0.2;
            }
            else if (trendStrength > 0.4)
            {
                regimeScores[MarketRegime.Trending] += 0.2;
            }
            else if (trendStrength < 0.2)
            {
                regimeScores[MarketRegime.Ranging] += 0.2;
            }

            // Volume-based scoring (10% weight)
            if (volumeRatio > 1.5)
            {
                regimeScores[MarketRegime.Breakout] += 0.1;
            }
            else if (volumeRatio < 0.7)
            {
                regimeScores[MarketRegime.Calm] += 0.1;
            }

            // RSI directional bias (5% weight)
            if (Math.Abs(normalizedRSI) > 0.3)
            {
                var biasRegime = normalizedRSI > 0 ? MarketRegime.Bullish : MarketRegime.Bearish;
                regimeScores[biasRegime] += 0.05;
            }
            else
            {
                regimeScores[MarketRegime.Neutral] += 0.05;
            }

            // Find regime with highest score
            return regimeScores.OrderByDescending(kv => kv.Value).First().Key;
        }

        /// <summary>
        /// Determine volatility regime based on current and historical volatility
        /// </summary>
        private VolatilityRegime DetermineVolatilityRegime(double currentVolatility, double currentATR)
        {
            if (atrHistory.Count < 20) return VolatilityRegime.Normal;

            double avgATR = atrHistory.Average();
            double atrRatio = avgATR > 0 ? currentATR / avgATR : 1.0;

            if (atrRatio > 2.0) return VolatilityRegime.VeryHigh;
            if (atrRatio > 1.5) return VolatilityRegime.High;
            if (atrRatio > 1.2) return VolatilityRegime.Medium;
            if (atrRatio < 0.7) return VolatilityRegime.Low;
            if (atrRatio < 0.5) return VolatilityRegime.VeryLow;

            return VolatilityRegime.Normal;
        }

        /// <summary>
        /// Apply stability filter to prevent regime whipsaws
        /// </summary>
        private MarketRegime ApplyStabilityFilter(MarketRegime detectedRegime)
        {
            if (detectedRegime == currentRegime)
            {
                regimeStabilityCount++;
                RegimeStability = Math.Min(1.0, regimeStabilityCount / 5.0);
                return currentRegime;
            }

            // Check if we have enough confirmation for regime change
            int recentMatches = regimeHistory.GetLast(3).Count(s => s.Regime == detectedRegime);

            if (recentMatches >= 2 || regimeStabilityCount == 0) // Allow immediate change if just started
            {
                currentRegime = detectedRegime;
                lastRegimeChange = DateTime.Now;
                regimeStabilityCount = 1;
                RegimeStability = 0.2;

                return currentRegime;
            }

            // Not enough confirmation, maintain current regime
            return currentRegime;
        }

        /// <summary>
        /// Calculate confidence score for regime detection
        /// </summary>
        private double CalculateRegimeConfidence(MarketRegime regime, double adx, double volatility, double trendStrength)
        {
            double confidence = 0.5; // Base confidence

            // ADX confidence
            switch (regime)
            {
                case MarketRegime.StrongTrend:
                    confidence += Math.Min(0.3, (adx - 30) / 50.0);
                    break;
                case MarketRegime.Trending:
                    confidence += Math.Min(0.3, (adx - 20) / 30.0);
                    break;
                case MarketRegime.Ranging:
                    confidence += Math.Min(0.3, (25 - adx) / 25.0);
                    break;
            }

            // Volatility confidence
            if (regime == MarketRegime.Volatile || regime == MarketRegime.HighVolatility)
            {
                confidence += Math.Min(0.2, volatility / 0.05);
            }

            // Trend strength confidence
            if (regime == MarketRegime.StrongTrend)
            {
                confidence += Math.Min(0.2, trendStrength);
            }

            return Math.Max(0.1, Math.Min(0.95, confidence));
        }

        /// <summary>
        /// Update adaptive thresholds based on historical data
        /// </summary>
        private void UpdateAdaptiveThresholds()
        {
            if (adxHistory.Count < 50) return;

            double avgADX = adxHistory.Average();
            double stdADX = adxHistory.StandardDeviation();

            // Adapt thresholds to current market behavior
            adaptiveADXTrendThreshold = avgADX + (stdADX * 0.5);
            adaptiveADXRangeThreshold = avgADX - (stdADX * 0.5);

            // Ensure reasonable bounds
            adaptiveADXTrendThreshold = FKS_Utils.Clamp(adaptiveADXTrendThreshold, 20, 35);
            adaptiveADXRangeThreshold = FKS_Utils.Clamp(adaptiveADXRangeThreshold, 15, 25);

            if (atrHistory.Count >= 50)
            {
                double avgATRChange = 0;
                for (int i = 1; i < Math.Min(20, atrHistory.Count); i++)
                {
                    avgATRChange += Math.Abs(atrHistory[i] - atrHistory[i - 1]);
                }
                avgATRChange /= 19;

                adaptiveVolatilityThreshold = avgATRChange * 2.0;
                adaptiveVolatilityThreshold = FKS_Utils.Clamp(adaptiveVolatilityThreshold, 0.01, 0.05);
            }
        }

        #endregion

        #region Regime Parameters and Analysis

        /// <summary>
        /// Get regime-specific trading parameters
        /// </summary>
        public RegimeParameters GetRegimeParameters()
        {
            switch (currentRegime)
            {
                case MarketRegime.StrongTrend:
                    return new RegimeParameters
                    {
                        SignalThreshold = 0.55,
                        StopMultiplier = 0.8,
                        TargetMultiplier = 3.0,
                        RiskPercent = 0.025,
                        RequireConfirmation = true,
                        OptimalTimeframes = new[] { "5m", "15m", "1h" }
                    };
                case MarketRegime.Trending:
                    return new RegimeParameters
                    {
                        SignalThreshold = 0.65,
                        StopMultiplier = 1.0,
                        TargetMultiplier = 2.5,
                        RiskPercent = 0.02,
                        RequireConfirmation = true,
                        OptimalTimeframes = new[] { "15m", "1h" }
                    };
                case MarketRegime.Ranging:
                    return new RegimeParameters
                    {
                        SignalThreshold = 0.75,
                        StopMultiplier = 0.6,
                        TargetMultiplier = 1.0,
                        RiskPercent = 0.015,
                        RequireConfirmation = true,
                        OptimalTimeframes = new[] { "5m", "15m" }
                    };
                case MarketRegime.Volatile:
                case MarketRegime.HighVolatility:
                    return new RegimeParameters
                    {
                        SignalThreshold = 0.80,
                        StopMultiplier = 1.5,
                        TargetMultiplier = 2.0,
                        RiskPercent = 0.01,
                        RequireConfirmation = true,
                        OptimalTimeframes = new[] { "1m", "5m" }
                    };
                case MarketRegime.LowVolatility:
                case MarketRegime.Calm:
                    return new RegimeParameters
                    {
                        SignalThreshold = 0.60,
                        StopMultiplier = 1.2,
                        TargetMultiplier = 1.5,
                        RiskPercent = 0.025,
                        RequireConfirmation = false,
                        OptimalTimeframes = new[] { "15m", "1h", "4h" }
                    };
                default:
                    return new RegimeParameters
                    {
                        SignalThreshold = 0.70,
                        StopMultiplier = 1.0,
                        TargetMultiplier = 2.0,
                        RiskPercent = 0.02,
                        RequireConfirmation = true,
                        OptimalTimeframes = new[] { "15m", "1h" }
                    };
            }
        }

        /// <summary>
        /// Get comprehensive regime analysis
        /// </summary>
        public RegimeAnalysis GetRegimeAnalysis()
        {
            var recentSnapshots = regimeHistory.GetLast(20);

            return new RegimeAnalysis
            {
                CurrentRegime = currentRegime,
                CurrentVolatilityRegime = currentVolatilityRegime,
                TimeInRegime = TimeInCurrentRegime,
                Stability = RegimeStability,
                Confidence = recentSnapshots.LastOrDefault()?.Confidence ?? 0.5,
                RecentChanges = CalculateRecentChanges(),
                TrendDirection = DetermineTrendDirection(recentSnapshots),
                MarketPressure = CalculateMarketPressure(recentSnapshots),
                RegimeParameters = GetRegimeParameters()
            };
        }

        /// <summary>
        /// Calculate recent regime changes for stability assessment
        /// </summary>
        private int CalculateRecentChanges()
        {
            if (regimeHistory.Count < 10) return 0;

            var recent = regimeHistory.GetLast(10);
            int changes = 0;

            for (int i = 1; i < recent.Count; i++)
            {
                if (recent[i].Regime != recent[i - 1].Regime)
                    changes++;
            }

            return changes;
        }

        /// <summary>
        /// Determine overall trend direction from recent data
        /// </summary>
        private TrendDirection DetermineTrendDirection(List<RegimeSnapshot> snapshots)
        {
            if (!snapshots.Any()) return TrendDirection.Sideways;

            var bullishRegimes = new[] { MarketRegime.Bullish, MarketRegime.StrongTrend };
            var bearishRegimes = new[] { MarketRegime.Bearish };

            int bullishCount = snapshots.Count(s => bullishRegimes.Contains(s.Regime));
            int bearishCount = snapshots.Count(s => bearishRegimes.Contains(s.Regime));

            double avgRSI = snapshots.Where(s => s.RSI > 0).Select(s => s.RSI).DefaultIfEmpty(50).Average();

            if (bullishCount > bearishCount && avgRSI > 55) return TrendDirection.Up;
            if (bearishCount > bullishCount && avgRSI < 45) return TrendDirection.Down;

            return TrendDirection.Sideways;
        }

        /// <summary>
        /// Calculate overall market pressure from multiple factors
        /// </summary>
        private double CalculateMarketPressure(List<RegimeSnapshot> snapshots)
        {
            if (!snapshots.Any()) return 0.5;

            double avgVolatility = snapshots.Select(s => s.Volatility).Average();
            double avgVolumeRatio = snapshots.Select(s => s.VolumeRatio).Average();
            double avgTrendStrength = snapshots.Select(s => s.TrendStrength).Average();

            return (avgVolatility * 10 + avgVolumeRatio + avgTrendStrength) / 3.0;
        }

        #endregion

        #region Session Analysis

        /// <summary>
        /// Get current trading session with enhanced analysis
        /// </summary>
        public SessionAnalysis GetCurrentSession(DateTime time)
        {
            var session = DetermineSession(time);
            var sessionStats = CalculateSessionStatistics(session);

            return new SessionAnalysis
            {
                CurrentSession = session,
                SessionProgress = CalculateSessionProgress(time, session),
                IsOptimalTradingTime = IsOptimalTradingTime(time, session),
                ExpectedVolatility = sessionStats.ExpectedVolatility,
                ExpectedVolume = sessionStats.ExpectedVolume,
                TypicalSpread = sessionStats.TypicalSpread,
                SessionRemaining = CalculateSessionRemaining(time, session)
            };
        }

        /// <summary>
        /// Determine trading session from time
        /// </summary>
        private SessionType DetermineSession(DateTime time)
        {
            if (FKS_Utils.IsWeekend(time)) return SessionType.Weekend;

            int hour = time.Hour;

            if (hour >= 20 || hour < 2) return SessionType.AsianSession;
            if (hour >= 2 && hour < 4) return SessionType.LondonOpen;
            if (hour >= 4 && hour < 8) return SessionType.LondonSession;
            if (hour >= 8 && hour < 10) return SessionType.NYOpen;
            if (hour >= 10 && hour < 15) return SessionType.NYSession;
            if (hour >= 15 && hour < 16) return SessionType.LondonClose;
            if (hour >= 16 && hour < 17) return SessionType.NYClose;

            return SessionType.Weekend;
        }

        /// <summary>
        /// Check if current time is optimal for trading
        /// </summary>
        private bool IsOptimalTradingTime(DateTime time, SessionType session)
        {
            if (FKS_Utils.IsWeekend(time)) return false;

            var optimalSessions = new[]
            {
                SessionType.LondonOpen, SessionType.NYOpen,
                SessionType.LondonSession, SessionType.NYSession
            };

            return optimalSessions.Contains(session);
        }

        /// <summary>
        /// Calculate session progress (0.0 to 1.0)
        /// </summary>
        private double CalculateSessionProgress(DateTime time, SessionType session)
        {
            var sessionHours = GetSessionHours(session);
            if (sessionHours == null) return 0.5;

            var timeOfDay = time.TimeOfDay;
            var sessionStart = sessionHours.Value.start;
            var sessionEnd = sessionHours.Value.end;

            if (timeOfDay < sessionStart || timeOfDay > sessionEnd) return 0;

            var sessionDuration = sessionEnd - sessionStart;
            var elapsed = timeOfDay - sessionStart;

            return sessionDuration.TotalMinutes > 0 ? elapsed.TotalMinutes / sessionDuration.TotalMinutes : 0.5;
        }

        /// <summary>
        /// Calculate time remaining in current session
        /// </summary>
        private TimeSpan CalculateSessionRemaining(DateTime time, SessionType session)
        {
            var sessionHours = GetSessionHours(session);
            if (sessionHours == null) return TimeSpan.Zero;

            var timeOfDay = time.TimeOfDay;
            var sessionEnd = sessionHours.Value.end;

            return timeOfDay < sessionEnd ? sessionEnd - timeOfDay : TimeSpan.Zero;
        }

        /// <summary>
        /// Get session start and end hours
        /// </summary>
        private (TimeSpan start, TimeSpan end)? GetSessionHours(SessionType session)
        {
            switch (session)
            {
                case SessionType.AsianSession:
                    return (new TimeSpan(20, 0, 0), new TimeSpan(2, 0, 0));
                case SessionType.LondonOpen:
                    return (new TimeSpan(2, 0, 0), new TimeSpan(4, 0, 0));
                case SessionType.LondonSession:
                    return (new TimeSpan(4, 0, 0), new TimeSpan(8, 0, 0));
                case SessionType.NYOpen:
                    return (new TimeSpan(8, 0, 0), new TimeSpan(10, 0, 0));
                case SessionType.NYSession:
                    return (new TimeSpan(10, 0, 0), new TimeSpan(15, 0, 0));
                case SessionType.LondonClose:
                    return (new TimeSpan(15, 0, 0), new TimeSpan(16, 0, 0));
                case SessionType.NYClose:
                    return (new TimeSpan(16, 0, 0), new TimeSpan(17, 0, 0));
                default:
                    return null;
            }
        }
        /// <summary>
        /// Calculate session-specific statistics
        /// </summary>
        private SessionStatistics CalculateSessionStatistics(SessionType session)
        {
            // Default values - in production would be calculated from historical data
            switch (session)
            {
                case SessionType.LondonOpen:
                case SessionType.NYOpen:
                    return new SessionStatistics
                    {
                        ExpectedVolatility = 1.3,
                        ExpectedVolume = 1.5,
                        TypicalSpread = 1.0
                    };
                case SessionType.LondonSession:
                case SessionType.NYSession:
                    return new SessionStatistics
                    {
                        ExpectedVolatility = 1.0,
                        ExpectedVolume = 1.2,
                        TypicalSpread = 1.0
                    };
                case SessionType.AsianSession:
                    return new SessionStatistics
                    {
                        ExpectedVolatility = 0.7,
                        ExpectedVolume = 0.6,
                        TypicalSpread = 1.2
                    };
                default:
                    return new SessionStatistics
                    {
                        ExpectedVolatility = 0.8,
                        ExpectedVolume = 0.8,
                        TypicalSpread = 1.1
                    };
            }
        }

        #endregion

        #region Disposal

        public void Dispose()
        {
            if (!disposed)
            {
                regimeHistory?.Dispose();
                adxHistory?.Dispose();
                atrHistory?.Dispose();
                volumeHistory?.Dispose();
                disposed = true;
            }
        }

        #endregion
    }

    #endregion

    #region Market State Analysis (250 lines)

    /// <summary>
    /// Comprehensive market state analyzer combining regime, volatility, and session analysis
    /// Enhanced with multi-timeframe analysis and predictive capabilities
    /// </summary>
    public class FKS_MarketStateAnalyzer : IDisposable
    {
        #region Private Fields

        private readonly FKS_RegimeAnalyzer regimeAnalyzer;
        private readonly Dictionary<string, double> stateMetrics = new Dictionary<string, double>();
        private readonly FKS_CircularBuffer<MarketStateSnapshot> stateHistory = new FKS_CircularBuffer<MarketStateSnapshot>(200);
        private bool disposed = false;

        #endregion

        #region Constructor

        public FKS_MarketStateAnalyzer()
        {
            regimeAnalyzer = new FKS_RegimeAnalyzer();
        }

        #endregion

        #region Market State Analysis

        /// <summary>
        /// Comprehensive market state analysis with predictive insights
        /// </summary>
        public MarketStateResult AnalyzeMarketState(string symbol, double price, double atr, double adx,
            double volume, double avgVolume, double rsi, DateTime time, double trendStrength = 0.5)
        {
            if (disposed) return new MarketStateResult { Regime = MarketRegime.Neutral };

            try
            {
                // Get market profile
                var marketProfile = FKS_MarketConfiguration.GetMarketProfile(symbol);

                // Calculate derived metrics
                double volatility = price > 0 ? atr / price : 0;
                double volumeRatio = avgVolume > 0 ? volume / avgVolume : 1.0;
                double normalizedTrendStrength = FKS_Utils.Clamp(trendStrength, 0, 1);

                // Analyze regime
                var regime = regimeAnalyzer.AnalyzeMarketRegime(adx, atr, price, volume, avgVolume,
                    normalizedTrendStrength, rsi);
                var regimeAnalysis = regimeAnalyzer.GetRegimeAnalysis();
                var regimeParams = regimeAnalyzer.GetRegimeParameters();

                // Analyze session
                var sessionAnalysis = regimeAnalyzer.GetCurrentSession(time);

                // Calculate market pressure and opportunity
                double marketPressure = CalculateMarketPressure(volumeRatio, volatility, normalizedTrendStrength,
                    adx, regimeAnalysis.MarketPressure);
                double opportunityScore = CalculateOpportunityScore(regime, sessionAnalysis.CurrentSession,
                    marketPressure, time, regimeAnalysis.Stability);

                // Determine volatility level
                var volatilityLevel = marketProfile.GetVolatilityLevel(atr);

                // Calculate risk adjustment
                double riskAdjustment = CalculateRiskAdjustment(regime, volatilityLevel,
                    sessionAnalysis.CurrentSession, volatility);

                // Create comprehensive result
                var result = new MarketStateResult
                {
                    Symbol = symbol,
                    Timestamp = time,
                    Price = price,

                    // Regime analysis
                    Regime = regime,
                    VolatilityRegime = regimeAnalysis.CurrentVolatilityRegime,
                    RegimeStability = regimeAnalysis.Stability,
                    RegimeConfidence = regimeAnalysis.Confidence,
                    Parameters = regimeParams,

                    // Session analysis
                    Session = sessionAnalysis.CurrentSession,
                    SessionProgress = sessionAnalysis.SessionProgress,
                    SessionRemaining = sessionAnalysis.SessionRemaining,

                    // Market metrics
                    Volatility = volatility,
                    VolatilityLevel = volatilityLevel,
                    TrendStrength = normalizedTrendStrength,
                    TrendDirection = regimeAnalysis.TrendDirection,
                    VolumeRatio = volumeRatio,
                    MarketPressure = marketPressure,

                    // Trading assessment
                    OpportunityScore = opportunityScore,
                    IsOptimalTime = sessionAnalysis.IsOptimalTradingTime && marketProfile.IsInOptimalTradingHours(time),
                    RiskAdjustment = riskAdjustment,

                    // Quality indicators
                    IsHighQuality = IsHighQualityCondition(opportunityScore, regimeAnalysis.Stability, volatilityLevel),
                    IsTradeableCondition = IsTradeableCondition(regime, sessionAnalysis, marketPressure, opportunityScore),

                    // Market profile
                    MarketProfile = marketProfile
                };

                // Store state snapshot
                var snapshot = new MarketStateSnapshot
                {
                    Timestamp = time,
                    Regime = regime,
                    Volatility = volatility,
                    MarketPressure = marketPressure,
                    OpportunityScore = opportunityScore,
                    TrendStrength = normalizedTrendStrength
                };
                stateHistory.Add(snapshot);

                // Add predictive insights
                result.PredictiveInsights = GeneratePredictiveInsights(result, stateHistory.GetLast(10));

                return result;
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Error in market state analysis: {ex.Message}");
                return new MarketStateResult { Regime = MarketRegime.Neutral, Symbol = symbol, Timestamp = time };
            }
        }

        /// <summary>
        /// Generate predictive insights based on current and historical data
        /// </summary>
        private PredictiveInsights GeneratePredictiveInsights(MarketStateResult currentState,
            List<MarketStateSnapshot> historicalData)
        {
            var insights = new PredictiveInsights();

            if (historicalData.Count >= 5)
            {
                // Analyze trends in market pressure
                var recentPressure = historicalData.Skip(Math.Max(0, historicalData.Count - 5)).Select(h => h.MarketPressure).ToList();
                insights.PressureTrend = CalculateTrend(recentPressure);

                // Analyze volatility trend
                var recentVolatility = historicalData.Skip(Math.Max(0, historicalData.Count - 5)).Select(h => h.Volatility).ToList();
                insights.VolatilityTrend = CalculateTrend(recentVolatility);

                // Predict next likely regime
                insights.NextLikelyRegime = PredictNextRegimeFromSnapshots(historicalData);

                // Calculate regime persistence probability
                var sameRegimeCount = historicalData.Skip(Math.Max(0, historicalData.Count - 5)).Count(h => h.Regime == currentState.Regime);
                insights.RegimePersistenceProbability = sameRegimeCount / 5.0;

                // Estimate optimal entry window
                insights.OptimalEntryWindow = EstimateOptimalEntryWindow(currentState);
            }

            return insights;
        }

        /// <summary>
        /// Calculate trend direction for a series of values
        /// </summary>
        private TrendDirection CalculateTrend(List<double> values)
        {
            if (values.Count < 3) return TrendDirection.Sideways;

            double firstHalf = values.Take(values.Count / 2).Average();
            double secondHalf = values.Skip(values.Count / 2).Average();

            double change = (secondHalf - firstHalf) / firstHalf;

            if (change > 0.1) return TrendDirection.Up;
            if (change < -0.1) return TrendDirection.Down;
            return TrendDirection.Sideways;
        }

        /// <summary>
        /// Predict next likely regime based on historical patterns
        /// </summary>
        private MarketRegime PredictNextRegimeFromSnapshots(List<MarketStateSnapshot> historicalData)
        {
            if (historicalData.Count < 5) return MarketRegime.Neutral;

            // Simple pattern recognition - look for common transitions
            var recentRegimes = historicalData.Skip(Math.Max(0, historicalData.Count - 3)).Select(h => h.Regime).ToList();
            var currentRegime = recentRegimes.LastOrDefault();

            // Common regime transitions (simplified)
            if (currentRegime == MarketRegime.Trending && recentRegimes.Count(r => r == MarketRegime.Trending) >= 2)
                return MarketRegime.StrongTrend;
            if (currentRegime == MarketRegime.StrongTrend && recentRegimes.All(r => r == MarketRegime.StrongTrend))
                return MarketRegime.Ranging;
            if (currentRegime == MarketRegime.Ranging && recentRegimes.Count(r => r == MarketRegime.Ranging) >= 2)
                return MarketRegime.Breakout;
            if (currentRegime == MarketRegime.Volatile)
                return MarketRegime.Calm;

            return currentRegime;
        }

        /// <summary>
        /// Estimate optimal entry window based on current conditions
        /// </summary>
        private TimeSpan EstimateOptimalEntryWindowFromSnapshots(MarketStateResult currentState)
        {
            // Base window depending on regime
            TimeSpan baseWindow;
            if (currentState.Regime == MarketRegime.StrongTrend)
                baseWindow = TimeSpan.FromMinutes(30);
            else if (currentState.Regime == MarketRegime.Trending)
                baseWindow = TimeSpan.FromMinutes(45);
            else if (currentState.Regime == MarketRegime.Ranging)
                baseWindow = TimeSpan.FromMinutes(15);
            else if (currentState.Regime == MarketRegime.Breakout)
                baseWindow = TimeSpan.FromMinutes(10);
            else
                baseWindow = TimeSpan.FromMinutes(20);

            // Adjust based on volatility
            if (currentState.VolatilityLevel == VolatilityLevel.High) baseWindow = TimeSpan.FromTicks(baseWindow.Ticks / 2);
            if (currentState.VolatilityLevel == VolatilityLevel.Low) baseWindow = TimeSpan.FromTicks(baseWindow.Ticks * 2);

            return baseWindow;
        }

        /// <summary>
        /// Calculate comprehensive market pressure from multiple factors
        /// </summary>
        private double CalculateMarketPressure(double volumeRatio, double volatility, double trendStrength,
            double adx, double regimePressure)
        {
            // Weight different pressure components
            double volumePressure = Math.Min(2.0, volumeRatio) * 0.25;
            double volatilityPressure = Math.Min(1.0, volatility * 20) * 0.30;
            double trendPressure = trendStrength * 0.20;
            double adxPressure = Math.Min(1.0, adx / 50.0) * 0.15;
            double regimePressureComponent = regimePressure * 0.10;

            double totalPressure = volumePressure + volatilityPressure + trendPressure +
                                 adxPressure + regimePressureComponent;

            return FKS_Utils.Clamp(totalPressure, 0, 2.0);
        }

        /// <summary>
        /// Calculate trading opportunity score with enhanced factors
        /// </summary>
        private double CalculateOpportunityScore(MarketRegime regime, SessionType session, double marketPressure,
            DateTime time, double regimeStability)
        {
            double score = 0.4; // Base score

            // Regime-based adjustments
            switch (regime)
            {
                case MarketRegime.StrongTrend:
                    score += 0.25;
                    break;
                case MarketRegime.Trending:
                    score += 0.15;
                    break;
                case MarketRegime.Breakout:
                    score += 0.20;
                    break;
                case MarketRegime.Ranging:
                    score += 0.05;
                    break;
                case MarketRegime.Volatile:
                    score += -0.10;
                    break;
                case MarketRegime.Choppy:
                    score += -0.15;
                    break;
                default:
                    break;
            }

            // Session-based adjustments
            switch (session)
            {
                case SessionType.LondonOpen:
                case SessionType.NYOpen:
                    score += 0.20;
                    break;
                case SessionType.LondonSession:
                case SessionType.NYSession:
                    score += 0.15;
                    break;
                case SessionType.LondonClose:
                case SessionType.NYClose:
                    score += 0.10;
                    break;
                case SessionType.AsianSession:
                    score += -0.05;
                    break;
                case SessionType.Weekend:
                    score += -0.30;
                    break;
                default:
                    break;
            }

            // Market pressure adjustments
            score += (marketPressure - 1.0) * 0.15;

            // Regime stability adjustments
            score += regimeStability * 0.10;

            // Weekend penalty
            if (FKS_Utils.IsWeekend(time))
                score -= 0.25;

            return FKS_Utils.Clamp(score, 0.0, 1.0);
        }

        /// <summary>
        /// Calculate risk adjustment factor based on market conditions
        /// </summary>
        private double CalculateRiskAdjustment(MarketRegime regime, VolatilityLevel volatilityLevel,
            SessionType session, double volatility)
        {
            double adjustment = 1.0;

            // Regime-based risk adjustments
            switch (regime)
            {
                case MarketRegime.Volatile:
                case MarketRegime.HighVolatility:
                    adjustment *= 0.6;
                    break;
                case MarketRegime.Choppy:
                    adjustment *= 0.7;
                    break;
                case MarketRegime.StrongTrend:
                    adjustment *= 1.2;
                    break;
                case MarketRegime.Trending:
                    adjustment *= 1.1;
                    break;
                case MarketRegime.Ranging:
                    adjustment *= 0.9;
                    break;
                default:
                    adjustment *= 1.0;
                    break;
            }

            // Volatility-based adjustments
            switch (volatilityLevel)
            {
                case VolatilityLevel.Extreme:
                    adjustment *= 0.5;
                    break;
                case VolatilityLevel.High:
                    adjustment *= 0.7;
                    break;
                case VolatilityLevel.Normal:
                    adjustment *= 1.0;
                    break;
                case VolatilityLevel.Low:
                    adjustment *= 1.1;
                    break;
                default:
                    adjustment *= 1.0;
                    break;
            }

            // Session-based adjustments
            switch (session)
            {
                case SessionType.AsianSession:
                    adjustment *= 0.8;
                    break;
                case SessionType.Weekend:
                    adjustment *= 0.5;
                    break;
                default:
                    adjustment *= 1.0;
                    break;
            }

            return FKS_Utils.Clamp(adjustment, 0.3, 2.0);
        }

        /// <summary>
        /// Determine if market conditions represent high quality trading opportunity
        /// </summary>
        private bool IsHighQualityCondition(double opportunityScore, double regimeStability, VolatilityLevel volatilityLevel)
        {
            // High quality requires good opportunity score and stable regime
            if (opportunityScore < 0.7) return false;
            if (regimeStability < 0.6) return false;

            // Extreme volatility reduces quality
            if (volatilityLevel == VolatilityLevel.Extreme) return false;

            return true;
        }

        /// <summary>
        /// Determine if current conditions are suitable for trading
        /// </summary>
        private bool IsTradeableCondition(MarketRegime regime, SessionAnalysis sessionAnalysis,
            double marketPressure, double opportunityScore)
        {
            // Basic minimum requirements
            if (opportunityScore < 0.4) return false;
            if (sessionAnalysis.CurrentSession == SessionType.Weekend) return false;

            // Avoid choppy or extremely volatile conditions
            if (regime == MarketRegime.Choppy) return false;
            if (regime == MarketRegime.Volatile && marketPressure > 1.5) return false;

            // Prefer certain regimes
            var preferredRegimes = new[]
            {
                MarketRegime.Trending,
                MarketRegime.StrongTrend,
                MarketRegime.Ranging,
                MarketRegime.Breakout
            };

            return preferredRegimes.Contains(regime) || opportunityScore > 0.75;
        }

        /// <summary>
        /// Predict next likely regime based on historical patterns
        /// </summary>
        private MarketRegime PredictNextRegime(List<MarketStateSnapshot> historicalData)
        {
            if (historicalData.Count < 5) return MarketRegime.Neutral;

            // Simple pattern recognition - look for common transitions
            var recentRegimes = historicalData.Skip(Math.Max(0, historicalData.Count - 3)).Select(h => h.Regime).ToList();
            var currentRegime = recentRegimes.Last();

            // Common regime transitions (simplified)
            if (currentRegime == MarketRegime.Trending && recentRegimes.Count(r => r == MarketRegime.Trending) >= 2)
                return MarketRegime.StrongTrend;
            if (currentRegime == MarketRegime.StrongTrend && recentRegimes.All(r => r == MarketRegime.StrongTrend))
                return MarketRegime.Ranging;
            if (currentRegime == MarketRegime.Ranging && recentRegimes.Count(r => r == MarketRegime.Ranging) >= 2)
                return MarketRegime.Breakout;
            if (currentRegime == MarketRegime.Volatile)
                return MarketRegime.Calm;

            return currentRegime;
        }

        /// <summary>
        /// Estimate optimal entry window based on current conditions
        /// </summary>
        private TimeSpan EstimateOptimalEntryWindow(MarketStateResult currentState)
        {
            // Base window depending on regime
            TimeSpan baseWindow;
            switch (currentState.Regime)
            {
                case MarketRegime.StrongTrend:
                    baseWindow = TimeSpan.FromMinutes(30);
                    break;
                case MarketRegime.Trending:
                    baseWindow = TimeSpan.FromMinutes(45);
                    break;
                case MarketRegime.Ranging:
                    baseWindow = TimeSpan.FromMinutes(15);
                    break;
                case MarketRegime.Breakout:
                    baseWindow = TimeSpan.FromMinutes(10);
                    break;
                default:
                    baseWindow = TimeSpan.FromMinutes(20);
                    break;
            }

            // Adjust based on volatility
            if (currentState.VolatilityLevel == VolatilityLevel.High) baseWindow = TimeSpan.FromTicks(baseWindow.Ticks / 2);
            if (currentState.VolatilityLevel == VolatilityLevel.Low) baseWindow = TimeSpan.FromTicks(baseWindow.Ticks * 2);

            return baseWindow;
        }

        #endregion

        #region Disposal

        public void Dispose()
        {
            if (!disposed)
            {
                regimeAnalyzer?.Dispose();
                stateHistory?.Dispose();
                disposed = true;
            }
        }

        #endregion
    }

    #endregion

    #region Supporting Data Classes (200 lines)

    /// <summary>
    /// Regime snapshot for historical analysis
    /// </summary>
    public class RegimeSnapshot
    {
        public DateTime Time { get; set; }
        public MarketRegime Regime { get; set; }
        public VolatilityRegime VolatilityRegime { get; set; }
        public double ADX { get; set; }
        public double ATR { get; set; }
        public double Volatility { get; set; }
        public double TrendStrength { get; set; }
        public double VolumeRatio { get; set; }
        public double RSI { get; set; }
        public double Confidence { get; set; }
    }

    /// <summary>
    /// Regime-specific trading parameters
    /// </summary>
    public class RegimeParameters
    {
        public double SignalThreshold { get; set; }
        public double StopMultiplier { get; set; }
        public double TargetMultiplier { get; set; }
        public double RiskPercent { get; set; }
        public bool RequireConfirmation { get; set; }
        public string[] OptimalTimeframes { get; set; } = new string[0];
    }

    /// <summary>
    /// Comprehensive regime analysis result
    /// </summary>
    public class RegimeAnalysis
    {
        public MarketRegime CurrentRegime { get; set; }
        public VolatilityRegime CurrentVolatilityRegime { get; set; }
        public TimeSpan TimeInRegime { get; set; }
        public double Stability { get; set; }
        public double Confidence { get; set; }
        public int RecentChanges { get; set; }
        public TrendDirection TrendDirection { get; set; }
        public double MarketPressure { get; set; }
        public RegimeParameters RegimeParameters { get; set; }
    }

    /// <summary>
    /// Session analysis with enhanced metrics
    /// </summary>
    public class SessionAnalysis
    {
        public SessionType CurrentSession { get; set; }
        public double SessionProgress { get; set; }
        public bool IsOptimalTradingTime { get; set; }
        public double ExpectedVolatility { get; set; }
        public double ExpectedVolume { get; set; }
        public double TypicalSpread { get; set; }
        public TimeSpan SessionRemaining { get; set; }
    }

    /// <summary>
    /// Session-specific statistics
    /// </summary>
    public class SessionStatistics
    {
        public double ExpectedVolatility { get; set; }
        public double ExpectedVolume { get; set; }
        public double TypicalSpread { get; set; }
    }

    /// <summary>
    /// Market state snapshot for historical analysis
    /// </summary>
    public class MarketStateSnapshot
    {
        public DateTime Timestamp { get; set; }
        public MarketRegime Regime { get; set; }
        public double Volatility { get; set; }
        public double MarketPressure { get; set; }
        public double OpportunityScore { get; set; }
        public double TrendStrength { get; set; }
    }

    /// <summary>
    /// Predictive insights based on historical patterns
    /// </summary>
    public class PredictiveInsights
    {
        public TrendDirection PressureTrend { get; set; }
        public TrendDirection VolatilityTrend { get; set; }
        public MarketRegime NextLikelyRegime { get; set; }
        public double RegimePersistenceProbability { get; set; }
        public TimeSpan OptimalEntryWindow { get; set; }
    }

    /// <summary>
    /// Comprehensive market state analysis result
    /// </summary>
    public class MarketStateResult
    {
        // Basic information
        public string Symbol { get; set; }
        public DateTime Timestamp { get; set; }
        public double Price { get; set; }

        // Regime analysis
        public MarketRegime Regime { get; set; }
        public VolatilityRegime VolatilityRegime { get; set; }
        public double RegimeStability { get; set; }
        public double RegimeConfidence { get; set; }
        public RegimeParameters Parameters { get; set; }

        // Session analysis
        public SessionType Session { get; set; }
        public double SessionProgress { get; set; }
        public TimeSpan SessionRemaining { get; set; }

        // Market characteristics
        public double Volatility { get; set; }
        public VolatilityLevel VolatilityLevel { get; set; }
        public double TrendStrength { get; set; }
        public TrendDirection TrendDirection { get; set; }
        public double VolumeRatio { get; set; }
        public double MarketPressure { get; set; }

        // Trading assessment
        public double OpportunityScore { get; set; }
        public bool IsOptimalTime { get; set; }
        public double RiskAdjustment { get; set; }
        public bool IsHighQuality { get; set; }
        public bool IsTradeableCondition { get; set; }

        // Market profile and predictions
        public FKS_MarketConfiguration.MarketProfile MarketProfile { get; set; }
        public PredictiveInsights PredictiveInsights { get; set; }

        /// <summary>
        /// Generate summary string for logging
        /// </summary>
        public string GetSummary()
        {
            return $"{Symbol} | {Regime} | Vol:{VolatilityLevel} | Session:{Session} | " +
                   $"Opp:{OpportunityScore:F2} | Stability:{RegimeStability:F2} | " +
                   $"Quality:{(IsHighQuality ? "HIGH" : "NORMAL")}";
        }

        /// <summary>
        /// Check if conditions favor long positions
        /// </summary>
        public bool FavorsLongPositions()
        {
            return TrendDirection == TrendDirection.Up &&
                   (Regime == MarketRegime.Trending || Regime == MarketRegime.StrongTrend || Regime == MarketRegime.Bullish) &&
                   OpportunityScore > 0.6;
        }

        /// <summary>
        /// Check if conditions favor short positions
        /// </summary>
        public bool FavorsShortPositions()
        {
            return TrendDirection == TrendDirection.Down &&
                   (Regime == MarketRegime.Trending || Regime == MarketRegime.StrongTrend || Regime == MarketRegime.Bearish) &&
                   OpportunityScore > 0.6;
        }

        /// <summary>
        /// Get recommended position size multiplier
        /// </summary>
        public double GetPositionSizeMultiplier()
        {
            double multiplier = 1.0;

            // Adjust for market quality
            if (IsHighQuality) multiplier *= 1.2;

            // Adjust for volatility
            double volatilityMultiplier;
            if (VolatilityLevel == VolatilityLevel.Extreme)
                volatilityMultiplier = 0.3;
            else if (VolatilityLevel == VolatilityLevel.High)
                volatilityMultiplier = 0.6;
            else if (VolatilityLevel == VolatilityLevel.Normal)
                volatilityMultiplier = 1.0;
            else if (VolatilityLevel == VolatilityLevel.Low)
                volatilityMultiplier = 1.1;
            else
                volatilityMultiplier = 1.0;

            multiplier *= volatilityMultiplier;

            // Adjust for regime
            double regimeMultiplier;
            if (Regime == MarketRegime.StrongTrend)
                regimeMultiplier = 1.3;
            else if (Regime == MarketRegime.Trending)
                regimeMultiplier = 1.1;
            else if (Regime == MarketRegime.Ranging)
                regimeMultiplier = 0.8;
            else if (Regime == MarketRegime.Volatile)
                regimeMultiplier = 0.5;
            else if (Regime == MarketRegime.Choppy)
                regimeMultiplier = 0.4;
            else
                regimeMultiplier = 1.0;

            multiplier *= regimeMultiplier;

            return FKS_Utils.Clamp(multiplier * RiskAdjustment, 0.2, 2.0);
        }
    }

    /// <summary>
    /// Volatility level classification
    /// </summary>
    public enum VolatilityLevel
    {
        Extreme,
        High,
        Normal,
        Low
    }

    #endregion
}