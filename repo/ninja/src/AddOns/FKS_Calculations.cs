#region Using declarations
using System;
using System.Collections.Generic;
using System.Linq;
using System.Diagnostics;
using System.Threading;
using NinjaTrader.NinjaScript;
using NinjaTrader.Cbi;
using System.Threading.Tasks;
using System.Collections.Concurrent;
#endregion

namespace NinjaTrader.NinjaScript.AddOns.FKS
{
    /// <summary>
    /// Enhanced calculation utilities for FKS trading system
    /// Includes advanced position sizing, risk management, and market analysis
    /// </summary>
    public static class FKS_Calculations
    {
        #region Private Fields
        private static readonly Dictionary<string, MarketConfig> marketConfigs = new Dictionary<string, MarketConfig>();
        private static readonly Dictionary<string, PerformanceMetrics> performanceCache = new Dictionary<string, PerformanceMetrics>();
        private static readonly object lockObject = new object();
        private static DateTime lastCacheUpdate = DateTime.MinValue;
        private static readonly TimeSpan cacheTimeout = TimeSpan.FromMinutes(5);
        #endregion

        #region Static Constructor
        static FKS_Calculations()
        {
            InitializeMarketConfigs();
        }
        #endregion

        #region Market Configuration
        private static void InitializeMarketConfigs()
        {
            marketConfigs["Gold"] = new MarketConfig
            {
                Symbol = "GC",
                BaseATRMultiplier = 1.0,
                VolatilityAdjustment = 1.0,
                TypicalSpread = 0.10,
                OptimalVolatility = 0.02,
                MaxVolatility = 0.05,
                SessionMultipliers = new Dictionary<string, double>
                {
                    ["Asian"] = 0.8,
                    ["London"] = 1.0,
                    ["US"] = 1.2,
                    ["Overlap"] = 1.3
                }
            };

            marketConfigs["ES"] = new MarketConfig
            {
                Symbol = "ES",
                BaseATRMultiplier = 1.2,
                VolatilityAdjustment = 1.1,
                TypicalSpread = 0.25,
                OptimalVolatility = 0.015,
                MaxVolatility = 0.04,
                SessionMultipliers = new Dictionary<string, double>
                {
                    ["PreMarket"] = 0.7,
                    ["Open"] = 1.4,
                    ["Morning"] = 1.2,
                    ["Afternoon"] = 1.0,
                    ["Close"] = 1.3
                }
            };

            marketConfigs["NQ"] = new MarketConfig
            {
                Symbol = "NQ",
                BaseATRMultiplier = 1.3,
                VolatilityAdjustment = 1.2,
                TypicalSpread = 0.25,
                OptimalVolatility = 0.02,
                MaxVolatility = 0.06,
                SessionMultipliers = new Dictionary<string, double>
                {
                    ["PreMarket"] = 0.6,
                    ["Open"] = 1.5,
                    ["Morning"] = 1.3,
                    ["Afternoon"] = 1.0,
                    ["Close"] = 1.4
                }
            };

            marketConfigs["CL"] = new MarketConfig
            {
                Symbol = "CL",
                BaseATRMultiplier = 0.9,
                VolatilityAdjustment = 0.95,
                TypicalSpread = 0.01,
                OptimalVolatility = 0.025,
                MaxVolatility = 0.08,
                SessionMultipliers = new Dictionary<string, double>
                {
                    ["Asian"] = 0.7,
                    ["European"] = 1.0,
                    ["US"] = 1.3,
                    ["Inventory"] = 1.8 // Wednesday 10:30 AM
                }
            };

            marketConfigs["BTC"] = new MarketConfig
            {
                Symbol = "BTC",
                BaseATRMultiplier = 1.5,
                VolatilityAdjustment = 1.4,
                TypicalSpread = 5.0,
                OptimalVolatility = 0.04,
                MaxVolatility = 0.12,
                SessionMultipliers = new Dictionary<string, double>
                {
                    ["24/7"] = 1.0,
                    ["Weekend"] = 0.8,
                    ["AsianActive"] = 1.2,
                    ["USActive"] = 1.1
                }
            };
        }
        #endregion

        #region Enhanced ATR Calculations

        /// <summary>
        /// Original ATR multiplier calculation (preserved for backward compatibility)
        /// </summary>
        public static double CalculateATRMultiplier(string market, double baseMultiplier)
        {
            try
            {
                switch (market)
                {
                    case "Gold": return baseMultiplier;
                    case "ES": return baseMultiplier * 1.2;
                    case "NQ": return baseMultiplier * 1.3;
                    case "CL": return baseMultiplier * 0.9;
                    case "BTC": return baseMultiplier * 1.5;
                    default: return baseMultiplier;
                }
            }
            catch (Exception ex)
            {
                LogError($"CalculateATRMultiplier error: {ex.Message}");
                return baseMultiplier;
            }
        }

        /// <summary>
        /// Enhanced ATR multiplier with volatility and session adjustments
        /// </summary>
        public static double CalculateAdaptiveATRMultiplier(
            string market, 
            double baseMultiplier, 
            double currentVolatility,
            double averageVolatility,
            string marketRegime,
            string session = null)
        {
            try
            {
                var config = GetMarketConfig(market);
                double multiplier = baseMultiplier * config.BaseATRMultiplier;

                // Volatility adjustment
                double volatilityRatio = averageVolatility > 0 ? currentVolatility / averageVolatility : 1.0;
                
                if (volatilityRatio > 2.0)
                    multiplier *= 1.5; // Wider stops in very high volatility
                else if (volatilityRatio > 1.5)
                    multiplier *= 1.25; // Moderately wider stops
                else if (volatilityRatio < 0.5)
                    multiplier *= 0.8; // Tighter stops in low volatility
                else if (volatilityRatio < 0.7)
                    multiplier *= 0.9; // Slightly tighter stops

                // Market regime adjustment
                switch (marketRegime)
                {
                    case "TRENDING_BULL":
                    case "TRENDING_BEAR":
                        multiplier *= 0.9; // Tighter stops in strong trends
                        break;
                    case "VOLATILE":
                        multiplier *= 1.4; // Much wider stops in volatile markets
                        break;
                    case "RANGING":
                        multiplier *= 1.1; // Slightly wider for range noise
                        break;
                    case "WEAK_BULL":
                    case "WEAK_BEAR":
                        multiplier *= 1.05; // Slightly wider for weak trends
                        break;
                }

                // Session adjustment
                if (!string.IsNullOrEmpty(session) && config.SessionMultipliers.ContainsKey(session))
                {
                    multiplier *= config.SessionMultipliers[session];
                }

                // Ensure reasonable bounds
                return Math.Max(0.5, Math.Min(4.0, multiplier));
            }
            catch (Exception ex)
            {
                LogError($"CalculateAdaptiveATRMultiplier error: {ex.Message}");
                return CalculateATRMultiplier(market, baseMultiplier);
            }
        }

        /// <summary>
        /// Calculate volatility-adjusted ATR for dynamic stop placement
        /// </summary>
        public static double CalculateVolatilityAdjustedATR(
            double[] atrValues, 
            double[] returns, 
            int period = 14,
            double confidenceLevel = 0.95)
        {
            try
            {
                if (atrValues == null || atrValues.Length < period || returns == null || returns.Length < period)
                    return atrValues?.LastOrDefault() ?? 0;

                // Calculate recent ATR
                double recentATR = atrValues.Take(period).Average();

                // Calculate volatility of returns
                double avgReturn = returns.Take(period).Average();
                double variance = returns.Take(period).Select(r => Math.Pow(r - avgReturn, 2)).Average();
                double stdDev = Math.Sqrt(variance);

                // Adjust ATR based on return volatility
                double volatilityAdjustment = 1.0 + (stdDev / 0.02); // Base assumption of 2% normal volatility

                // Apply confidence level adjustment
                double confidenceAdjustment = confidenceLevel * 1.5; // 95% confidence = 1.425 multiplier

                return recentATR * volatilityAdjustment * confidenceAdjustment;
            }
            catch (Exception ex)
            {
                LogError($"CalculateVolatilityAdjustedATR error: {ex.Message}");
                return atrValues?.LastOrDefault() ?? 0;
            }
        }

        #endregion

        #region Advanced Position Sizing

        /// <summary>
        /// Original position sizing (preserved for backward compatibility)
        /// </summary>
        public static int CalculateOptimalContracts(double accountSize, double riskPercent, double stopDistance, double tickValue)
        {
            try
            {
                double riskAmount = accountSize * (riskPercent / 100);
                double contractRisk = stopDistance * tickValue;
                return Math.Max(1, (int)(riskAmount / contractRisk));
            }
            catch (Exception ex)
            {
                LogError($"CalculateOptimalContracts error: {ex.Message}");
                return 1;
            }
        }

        /// <summary>
        /// Kelly Criterion-based position sizing for optimal capital growth
        /// </summary>
        public static int CalculateKellyContracts(
            double accountSize,
            double winRate,
            double avgWinAmount,
            double avgLossAmount,
            double maxRiskPercent = 0.02,
            double kellyFraction = 0.25) // Use 25% of full Kelly for safety
        {
            try
            {
                if (winRate <= 0 || winRate >= 1 || avgLossAmount >= 0 || avgWinAmount <= 0)
                    return 1;

                // Kelly Criterion: f = (bp - q) / b
                // where b = odds received (avgWin/avgLoss), p = win probability, q = loss probability
                double b = avgWinAmount / Math.Abs(avgLossAmount);
                double p = winRate;
                double q = 1 - winRate;

                double kellyPercent = (b * p - q) / b;

                // Apply safety fraction and cap at max risk
                double safeKellyPercent = Math.Min(kellyPercent * kellyFraction, maxRiskPercent);

                // Ensure positive and reasonable
                safeKellyPercent = Math.Max(0.001, Math.Min(0.05, safeKellyPercent)); // 0.1% to 5% max

                // Calculate contracts based on average loss as risk per contract
                double riskAmount = accountSize * safeKellyPercent;
                double riskPerContract = Math.Abs(avgLossAmount);

                int contracts = Math.Max(1, (int)(riskAmount / riskPerContract));

                // Cap at reasonable maximum (10 contracts for most retail accounts)
                return Math.Min(contracts, 10);
            }
            catch (Exception ex)
            {
                LogError($"CalculateKellyContracts error: {ex.Message}");
                return 1;
            }
        }

        /// <summary>
        /// Volatility-adjusted position sizing
        /// </summary>
        public static int CalculateVolatilityAdjustedSize(
            double accountSize,
            int baseContracts,
            double currentATR,
            double averageATR,
            double maxVolatilityMultiplier = 2.5)
        {
            try
            {
                if (averageATR <= 0 || currentATR <= 0)
                    return baseContracts;

                double volatilityRatio = currentATR / averageATR;
                
                // Inverse relationship: higher volatility = smaller position
                double adjustment = 1.0 / Math.Min(volatilityRatio, maxVolatilityMultiplier);

                // Apply adjustment with reasonable bounds
                adjustment = Math.Max(0.25, Math.Min(2.0, adjustment));

                int adjustedSize = Math.Max(1, (int)(baseContracts * adjustment));

                return adjustedSize;
            }
            catch (Exception ex)
            {
                LogError($"CalculateVolatilityAdjustedSize error: {ex.Message}");
                return baseContracts;
            }
        }

        /// <summary>
        /// Risk parity position sizing across multiple markets
        /// </summary>
        public static Dictionary<string, int> CalculateRiskParityPositions(
            Dictionary<string, double> marketATRs,
            Dictionary<string, double> marketCorrelations,
            double totalRiskBudget,
            double accountSize,
            int maxContractsPerMarket = 5)
        {
            var positions = new Dictionary<string, int>();

            try
            {
                if (marketATRs == null || marketATRs.Count == 0)
                    return positions;

                // Calculate risk contribution per market
                double totalInverseATR = marketATRs.Values.Select(atr => 1.0 / atr).Sum();
                double totalRiskAmount = accountSize * totalRiskBudget;

                foreach (var market in marketATRs.Keys)
                {
                    double marketATR = marketATRs[market];
                    if (marketATR <= 0) continue;

                    // Equal risk contribution approach
                    double marketWeight = (1.0 / marketATR) / totalInverseATR;
                    double marketRiskAmount = totalRiskAmount * marketWeight;

                    // Calculate contracts based on ATR as proxy for risk per contract
                    int contracts = Math.Max(1, (int)(marketRiskAmount / (marketATR * 100))); // Assuming $100 per ATR point

                    // Apply correlation adjustment
                    if (marketCorrelations != null && marketCorrelations.ContainsKey(market))
                    {
                        double correlation = Math.Abs(marketCorrelations[market]);
                        if (correlation > 0.7) // Highly correlated
                        {
                            contracts = (int)(contracts * 0.7); // Reduce position due to correlation
                        }
                    }

                    positions[market] = Math.Min(Math.Max(1, contracts), maxContractsPerMarket);
                }
            }
            catch (Exception ex)
            {
                LogError($"CalculateRiskParityPositions error: {ex.Message}");
            }

            return positions;
        }

        /// <summary>
        /// Commission-optimized position sizing
        /// </summary>
        public static int CalculateCommissionOptimizedSize(
            double expectedProfit,
            double expectedLoss,
            double commissionPerContract,
            double winRate,
            int baseContracts,
            double minProfitMultiple = 3.0) // Profit should be at least 3x commission
        {
            try
            {
                // Calculate expected value per contract
                double expectedValue = (winRate * expectedProfit) - ((1 - winRate) * Math.Abs(expectedLoss));
                
                // Subtract commission cost
                double netExpectedValue = expectedValue - (2 * commissionPerContract); // Round-trip commission

                // Only trade if expected profit exceeds minimum threshold
                if (expectedProfit < commissionPerContract * minProfitMultiple)
                {
                    return 0; // Don't trade - insufficient profit potential
                }

                // If net expected value is negative, reduce position
                if (netExpectedValue <= 0)
                {
                    return Math.Max(1, baseContracts / 2);
                }

                // If net expected value is very good, can use full position
                if (netExpectedValue > commissionPerContract * 5) // 5x commission in expected value
                {
                    return baseContracts;
                }

                // Scale position based on net expected value
                double scaleFactor = netExpectedValue / (commissionPerContract * 3);
                return Math.Max(1, (int)(baseContracts * scaleFactor));
            }
            catch (Exception ex)
            {
                LogError($"CalculateCommissionOptimizedSize error: {ex.Message}");
                return baseContracts;
            }
        }

        #endregion

        #region Market Analysis

        /// <summary>
        /// Enhanced market regime detection with confidence scoring
        /// </summary>
        public static MarketRegimeResult GetEnhancedMarketRegime(
            double price, 
            double ema9, 
            double sma20, 
            double atr, 
            double volume, 
            double avgVolume,
            double[] priceHistory = null,
            int lookback = 20)
        {
            try
            {
                var result = new MarketRegimeResult
                {
                    Regime = GetMarketRegime(price, ema9, sma20, atr, volume, avgVolume),
                    Timestamp = DateTime.Now
                };

                // Calculate confidence based on multiple factors
                double trendStrength = Math.Abs(ema9 - sma20) / atr;
                double volumeStrength = volume / avgVolume;
                double priceAlignment = (price > ema9 && ema9 > sma20) ? 1.0 : 
                                      (price < ema9 && ema9 < sma20) ? 1.0 : 0.0;

                // Base confidence calculation
                result.Confidence = (trendStrength * 0.4 + volumeStrength * 0.3 + priceAlignment * 0.3);
                result.Confidence = Math.Min(1.0, result.Confidence / 2.0); // Normalize to 0-1

                // Additional analysis if price history is available
                if (priceHistory != null && priceHistory.Length >= lookback)
                {
                    result.TrendConsistency = CalculateTrendConsistency(priceHistory, lookback);
                    result.VolatilityPercentile = CalculateVolatilityPercentile(priceHistory, atr, lookback);
                    result.MomentumScore = CalculateMomentumScore(priceHistory, lookback);

                    // Adjust confidence based on consistency
                    result.Confidence *= (0.5 + result.TrendConsistency * 0.5);
                }

                // Set strength level
                if (result.Confidence > 0.8)
                    result.Strength = "VERY_STRONG";
                else if (result.Confidence > 0.6)
                    result.Strength = "STRONG";
                else if (result.Confidence > 0.4)
                    result.Strength = "MODERATE";
                else
                    result.Strength = "WEAK";

                return result;
            }
            catch (Exception ex)
            {
                LogError($"GetEnhancedMarketRegime error: {ex.Message}");
                return new MarketRegimeResult 
                { 
                    Regime = GetMarketRegime(price, ema9, sma20, atr, volume, avgVolume),
                    Confidence = 0.5,
                    Strength = "UNKNOWN"
                };
            }
        }

        /// <summary>
        /// Calculate correlation between two price series
        /// </summary>
        public static double CalculateCorrelation(double[] series1, double[] series2, int period = 20)
        {
            try
            {
                if (series1 == null || series2 == null || series1.Length < period || series2.Length < period)
                    return 0.0;

                var returns1 = CalculateReturns(series1, period);
                var returns2 = CalculateReturns(series2, period);

                return CalculatePearsonCorrelation(returns1, returns2);
            }
            catch (Exception ex)
            {
                LogError($"CalculateCorrelation error: {ex.Message}");
                return 0.0;
            }
        }

        /// <summary>
        /// Multi-timeframe trend alignment analysis
        /// </summary>
        public static TrendAlignmentResult AnalyzeTrendAlignment(
            Dictionary<string, double[]> timeframePrices,
            Dictionary<string, double> timeframeEMAs)
        {
            try
            {
                var result = new TrendAlignmentResult();
                var alignments = new List<bool>();

                foreach (var timeframe in timeframePrices.Keys)
                {
                    if (timeframeEMAs.ContainsKey(timeframe))
                    {
                        var prices = timeframePrices[timeframe];
                        var ema = timeframeEMAs[timeframe];

                        if (prices.Length > 0)
                        {
                            bool bullish = prices[0] > ema;
                            alignments.Add(bullish);
                            result.TimeframeAnalysis[timeframe] = bullish ? "BULLISH" : "BEARISH";
                        }
                    }
                }

                // Calculate overall alignment
                if (alignments.Count > 0)
                {
                    int bullishCount = alignments.Count(a => a);
                    result.AlignmentScore = (double)bullishCount / alignments.Count;

                    if (result.AlignmentScore >= 0.8)
                        result.OverallTrend = bullishCount > alignments.Count / 2 ? "STRONG_BULLISH" : "STRONG_BEARISH";
                    else if (result.AlignmentScore >= 0.6)
                        result.OverallTrend = bullishCount > alignments.Count / 2 ? "BULLISH" : "BEARISH";
                    else
                        result.OverallTrend = "MIXED";
                }

                return result;
            }
            catch (Exception ex)
            {
                LogError($"AnalyzeTrendAlignment error: {ex.Message}");
                return new TrendAlignmentResult { OverallTrend = "UNKNOWN" };
            }
        }

        #endregion

        #region Utility Methods (Preserved)

        public static double NormalizePrice(double price, double tickSize)
        {
            try
            {
                if (tickSize <= 0) return price;
                return Math.Round(price / tickSize) * tickSize;
            }
            catch (Exception ex)
            {
                LogError($"NormalizePrice error: {ex.Message}");
                return price;
            }
        }

        public static double CalculateRiskAmount(double accountSize, double riskPercent)
        {
            try
            {
                return accountSize * Math.Max(0, Math.Min(100, riskPercent)) / 100;
            }
            catch (Exception ex)
            {
                LogError($"CalculateRiskAmount error: {ex.Message}");
                return 0;
            }
        }

        public static double CalculateStopDistance(double entryPrice, double stopPrice)
        {
            try
            {
                return Math.Abs(entryPrice - stopPrice);
            }
            catch (Exception ex)
            {
                LogError($"CalculateStopDistance error: {ex.Message}");
                return 0;
            }
        }

        public static double CalculatePositionSize(double accountSize, double riskPercent, double stopDistance, double pointValue)
        {
            try
            {
                double riskAmount = CalculateRiskAmount(accountSize, riskPercent);
                double contractRisk = stopDistance * pointValue;
                return contractRisk > 0 ? riskAmount / contractRisk : 0;
            }
            catch (Exception ex)
            {
                LogError($"CalculatePositionSize error: {ex.Message}");
                return 0;
            }
        }

        public static bool IsWithinTradingHours(DateTime currentTime, int startHour, int endHour)
        {
            try
            {
                int currentHour = currentTime.Hour;
                if (startHour <= endHour)
                {
                    return currentHour >= startHour && currentHour <= endHour;
                }
                else // Handles overnight sessions
                {
                    return currentHour >= startHour || currentHour <= endHour;
                }
            }
            catch (Exception ex)
            {
                LogError($"IsWithinTradingHours error: {ex.Message}");
                return true; // Default to allowing trading
            }
        }

        public static double CalculateWaveRatio(double[] highs, double[] lows, int period)
        {
            try
            {
                if (highs == null || lows == null || highs.Length < period || lows.Length < period) 
                    return 1.0;

                double upWaves = 0;
                double downWaves = 0;

                for (int i = 1; i < period; i++)
                {
                    if (highs[i] > highs[i - 1]) upWaves++;
                    if (lows[i] < lows[i - 1]) downWaves++;
                }

                return downWaves > 0 ? upWaves / downWaves : upWaves > 0 ? 2.0 : 1.0;
            }
            catch (Exception ex)
            {
                LogError($"CalculateWaveRatio error: {ex.Message}");
                return 1.0;
            }
        }

        public static string GetMarketRegime(double price, double ema9, double sma20, double atr, double volume, double avgVolume)
        {
            try
            {
                bool trending = Math.Abs(ema9 - sma20) > atr * 0.5;
                bool bullish = price > ema9 && ema9 > sma20;
                bool bearish = price < ema9 && ema9 < sma20;
                bool highVolume = volume > avgVolume * 1.2;

                if (trending && bullish && highVolume) return "TRENDING_BULL";
                if (trending && bearish && highVolume) return "TRENDING_BEAR";
                if (trending && bullish) return "WEAK_BULL";
                if (trending && bearish) return "WEAK_BEAR";

                return "RANGING";
            }
            catch (Exception ex)
            {
                LogError($"GetMarketRegime error: {ex.Message}");
                return "UNKNOWN";
            }
        }

        #endregion

        #region Performance and Optimization

        /// <summary>
        /// Enhanced performance cache with automatic cleanup and memory management
        /// </summary>
        private static readonly ConcurrentDictionary<string, PerformanceMetrics> threadSafePerformanceCache = 
            new ConcurrentDictionary<string, PerformanceMetrics>();
        private static readonly Timer cacheCleanupTimer = new Timer(CleanupExpiredCache, null, TimeSpan.FromMinutes(5), TimeSpan.FromMinutes(5));
        private static readonly object performanceStatsLock = new object();
        private static readonly Dictionary<string, PerformanceStats> operationStats = new Dictionary<string, PerformanceStats>();

        /// <summary>
        /// Get cached or calculate expensive operations with enhanced performance tracking
        /// </summary>
        public static T GetCachedResult<T>(string key, Func<T> calculation, TimeSpan? cacheTimeout = null)
        {
            var timeout = cacheTimeout ?? FKS_Calculations.cacheTimeout;
            
            // Try to get from thread-safe cache first
            if (threadSafePerformanceCache.TryGetValue(key, out var cached))
            {
                if (DateTime.Now - cached.Timestamp < timeout)
                {
                    RecordCacheHit(key);
                    return (T)cached.Value;
                }
            }

            // Calculate new value with performance tracking
            var stopwatch = Stopwatch.StartNew();
            T result = calculation();
            stopwatch.Stop();

            // Cache the result
            var metrics = new PerformanceMetrics
            {
                Value = result,
                Timestamp = DateTime.Now,
                ExecutionTime = stopwatch.ElapsedMilliseconds
            };

            threadSafePerformanceCache.AddOrUpdate(key, metrics, (k, v) => metrics);

            // Record performance statistics
            RecordPerformanceStats(key, stopwatch.ElapsedMilliseconds);

            // Log slow operations
            if (stopwatch.ElapsedMilliseconds > 100)
            {
                LogPerformance($"Slow calculation: {key} took {stopwatch.ElapsedMilliseconds}ms");
            }

            return result;
        }

        /// <summary>
        /// Enhanced cache cleanup with performance statistics
        /// </summary>
        private static void CleanupExpiredCache(object state)
        {
            try
            {
                var expiredKeys = new List<string>();
                var cutoffTime = DateTime.Now - cacheTimeout;

                foreach (var kvp in threadSafePerformanceCache)
                {
                    if (kvp.Value.Timestamp < cutoffTime)
                    {
                        expiredKeys.Add(kvp.Key);
                    }
                }

                foreach (var key in expiredKeys)
                {
                    threadSafePerformanceCache.TryRemove(key, out _);
                }

                if (expiredKeys.Count > 0)
                {
                    LogPerformance($"Cleaned up {expiredKeys.Count} expired cache entries");
                }
            }
            catch (Exception ex)
            {
                LogError($"Cache cleanup error: {ex.Message}");
            }
        }

        /// <summary>
        /// Record performance statistics for operations
        /// </summary>
        private static void RecordPerformanceStats(string operation, long executionTime)
        {
            lock (performanceStatsLock)
            {
                if (!operationStats.ContainsKey(operation))
                {
                    operationStats[operation] = new PerformanceStats { Operation = operation };
                }

                var stats = operationStats[operation];
                stats.TotalExecutions++;
                stats.TotalExecutionTime += executionTime;
                stats.AverageExecutionTime = stats.TotalExecutionTime / stats.TotalExecutions;
                stats.LastExecutionTime = executionTime;
                stats.MaxExecutionTime = Math.Max(stats.MaxExecutionTime, executionTime);
                stats.MinExecutionTime = stats.MinExecutionTime == 0 ? executionTime : Math.Min(stats.MinExecutionTime, executionTime);
            }
        }

        /// <summary>
        /// Record cache hit for performance tracking
        /// </summary>
        private static void RecordCacheHit(string key)
        {
            lock (performanceStatsLock)
            {
                if (operationStats.ContainsKey(key))
                {
                    operationStats[key].CacheHits++;
                }
            }
        }

        /// <summary>
        /// Get performance statistics for all operations
        /// </summary>
        public static Dictionary<string, PerformanceStats> GetPerformanceStatistics()
        {
            lock (performanceStatsLock)
            {
                return new Dictionary<string, PerformanceStats>(operationStats);
            }
        }

        /// <summary>
        /// Clear performance cache and statistics
        /// </summary>
        public static void ClearCache()
        {
            threadSafePerformanceCache.Clear();
            
            lock (performanceStatsLock)
            {
                operationStats.Clear();
            }
            
            lastCacheUpdate = DateTime.Now;
            LogPerformance("Performance cache and statistics cleared");
        }

        #endregion

        #region Enhanced Error Recovery and Circuit Breaker

        /// <summary>
        /// Circuit breaker states for error recovery
        /// </summary>
        public enum CircuitBreakerState
        {
            Closed,     // Normal operation
            Open,       // Circuit is open, calls are failing fast
            HalfOpen    // Testing if the circuit can be closed
        }

        /// <summary>
        /// Circuit breaker for protecting against cascading failures
        /// </summary>
        public class CircuitBreaker
        {
            private CircuitBreakerState state = CircuitBreakerState.Closed;
            private int failureCount = 0;
            private DateTime lastFailureTime = DateTime.MinValue;
            private readonly int failureThreshold;
            private readonly TimeSpan timeout;
            private readonly object lockObject = new object();

            public CircuitBreaker(int failureThreshold = 5, TimeSpan? timeout = null)
            {
                this.failureThreshold = failureThreshold;
                this.timeout = timeout ?? TimeSpan.FromMinutes(1);
            }

            public T Execute<T>(Func<T> operation, T fallbackValue = default(T))
            {
                lock (lockObject)
                {
                    if (state == CircuitBreakerState.Open)
                    {
                        if (DateTime.Now - lastFailureTime > timeout)
                        {
                            state = CircuitBreakerState.HalfOpen;
                            LogError($"Circuit breaker moving to HalfOpen state");
                        }
                        else
                        {
                            LogError($"Circuit breaker is Open, returning fallback value");
                            return fallbackValue;
                        }
                    }

                    try
                    {
                        T result = operation();
                        
                        if (state == CircuitBreakerState.HalfOpen)
                        {
                            state = CircuitBreakerState.Closed;
                            failureCount = 0;
                            LogError($"Circuit breaker moving to Closed state");
                        }
                        
                        return result;
                    }
                    catch (Exception ex)
                    {
                        RecordFailure();
                        LogError($"Circuit breaker operation failed: {ex.Message}");
                        return fallbackValue;
                    }
                }
            }

            private void RecordFailure()
            {
                failureCount++;
                lastFailureTime = DateTime.Now;

                if (failureCount >= failureThreshold)
                {
                    state = CircuitBreakerState.Open;
                    LogError($"Circuit breaker moving to Open state after {failureCount} failures");
                }
            }

            public CircuitBreakerState GetState() => state;
            public int GetFailureCount() => failureCount;
        }

        /// <summary>
        /// Global circuit breakers for different operations
        /// </summary>
        private static readonly Dictionary<string, CircuitBreaker> circuitBreakers = new Dictionary<string, CircuitBreaker>
        {
            ["position_sizing"] = new CircuitBreaker(3, TimeSpan.FromSeconds(30)),
            ["market_regime"] = new CircuitBreaker(5, TimeSpan.FromMinutes(1)),
            ["volatility_calculation"] = new CircuitBreaker(3, TimeSpan.FromSeconds(45)),
            ["correlation_analysis"] = new CircuitBreaker(5, TimeSpan.FromMinutes(2)),
            ["performance_metrics"] = new CircuitBreaker(3, TimeSpan.FromSeconds(30))
        };

        /// <summary>
        /// Execute operation with circuit breaker protection
        /// </summary>
        public static T ExecuteWithCircuitBreaker<T>(string operationType, Func<T> operation, T fallbackValue = default(T))
        {
            if (circuitBreakers.ContainsKey(operationType))
            {
                return circuitBreakers[operationType].Execute(operation, fallbackValue);
            }
            else
            {
                // Create new circuit breaker for unknown operation types
                var newBreaker = new CircuitBreaker();
                circuitBreakers[operationType] = newBreaker;
                return newBreaker.Execute(operation, fallbackValue);
            }
        }

        /// <summary>
        /// Get circuit breaker status for monitoring
        /// </summary>
        public static Dictionary<string, object> GetCircuitBreakerStatus()
        {
            var status = new Dictionary<string, object>();
            
            foreach (var kvp in circuitBreakers)
            {
                status[kvp.Key] = new
                {
                    State = kvp.Value.GetState().ToString(),
                    FailureCount = kvp.Value.GetFailureCount()
                };
            }
            
            return status;
        }

        #endregion

        #region Private Helper Methods

        private static MarketConfig GetMarketConfig(string market)
        {
            return marketConfigs.ContainsKey(market) ? marketConfigs[market] : marketConfigs["Gold"];
        }

        private static double[] CalculateReturns(double[] prices, int period)
        {
            if (prices.Length < 2) return new double[0];

            var returns = new double[Math.Min(period - 1, prices.Length - 1)];
            for (int i = 1; i < Math.Min(period, prices.Length); i++)
            {
                if (prices[i - 1] != 0)
                    returns[i - 1] = (prices[i] - prices[i - 1]) / prices[i - 1];
            }
            return returns;
        }

        private static double CalculatePearsonCorrelation(double[] x, double[] y)
        {
            int n = Math.Min(x.Length, y.Length);
            if (n < 2) return 0;

            double sumX = x.Take(n).Sum();
            double sumY = y.Take(n).Sum();
            double sumXY = x.Take(n).Zip(y.Take(n), (a, b) => a * b).Sum();
            double sumXX = x.Take(n).Sum(a => a * a);
            double sumYY = y.Take(n).Sum(b => b * b);

            double numerator = n * sumXY - sumX * sumY;
            double denominator = Math.Sqrt((n * sumXX - sumX * sumX) * (n * sumYY - sumY * sumY));

            return denominator != 0 ? numerator / denominator : 0;
        }

        private static double CalculateTrendConsistency(double[] prices, int lookback)
        {
            if (prices.Length < lookback) return 0.5;

            int trendChanges = 0;
            bool? lastTrend = null;

            for (int i = 1; i < lookback; i++)
            {
                bool currentTrend = prices[i] > prices[i - 1];
                if (lastTrend.HasValue && lastTrend.Value != currentTrend)
                    trendChanges++;
                lastTrend = currentTrend;
            }

            // More changes = less consistency
            return Math.Max(0, 1.0 - (double)trendChanges / (lookback - 1));
        }

        private static double CalculateVolatilityPercentile(double[] prices, double currentATR, int lookback)
        {
            if (prices.Length < lookback) return 0.5;

            var returns = CalculateReturns(prices, lookback);
            if (returns.Length == 0) return 0.5;

            double avgReturn = returns.Average();
            double variance = returns.Select(r => Math.Pow(r - avgReturn, 2)).Average();
            double historicalVol = Math.Sqrt(variance);

            // Compare current ATR to historical volatility
            double currentVol = currentATR / prices[0]; // Normalize by price
            return historicalVol > 0 ? Math.Min(1.0, currentVol / historicalVol) : 0.5;
        }

        private static double CalculateMomentumScore(double[] prices, int lookback)
        {
            if (prices.Length < lookback) return 0.5;

            // Calculate rate of change over different periods
            double shortMomentum = prices.Length > 5 ? (prices[0] - prices[4]) / prices[4] : 0;
            double mediumMomentum = prices.Length > 10 ? (prices[0] - prices[9]) / prices[9] : 0;
            double longMomentum = prices.Length > 20 ? (prices[0] - prices[19]) / prices[19] : 0;

            // Weight recent momentum more heavily
            double weightedMomentum = (shortMomentum * 0.5) + (mediumMomentum * 0.3) + (longMomentum * 0.2);

            // Normalize to 0-1 scale (assume ±10% is extreme)
            return Math.Max(0, Math.Min(1, 0.5 + (weightedMomentum / 0.2)));
        }

        private static void LogError(string message)
        {
            try
            {
                NinjaTrader.Code.Output.Process($"FKS_Calculations Error: {message}", PrintTo.OutputTab1);
            }
            catch
            {
                // Fail silently if logging fails
            }
        }

        private static void LogPerformance(string message)
        {
            try
            {
                NinjaTrader.Code.Output.Process($"FKS_Calculations Performance: {message}", PrintTo.OutputTab2);
            }
            catch
            {
                // Fail silently if logging fails
            }
        }

        #endregion

        #region Supporting Classes

        public class MarketConfig
        {
            public string Symbol { get; set; }
            public double BaseATRMultiplier { get; set; }
            public double VolatilityAdjustment { get; set; }
            public double TypicalSpread { get; set; }
            public double OptimalVolatility { get; set; }
            public double MaxVolatility { get; set; }
            public Dictionary<string, double> SessionMultipliers { get; set; } = new Dictionary<string, double>();
        }

        public class PerformanceMetrics
        {
            public object Value { get; set; }
            public DateTime Timestamp { get; set; }
            public long ExecutionTime { get; set; }
        }

        public class MarketRegimeResult
        {
            public string Regime { get; set; }
            public double Confidence { get; set; }
            public string Strength { get; set; }
            public double TrendConsistency { get; set; }
            public double VolatilityPercentile { get; set; }
            public double MomentumScore { get; set; }
            public DateTime Timestamp { get; set; }
        }

        public class TrendAlignmentResult
        {
            public string OverallTrend { get; set; }
            public double AlignmentScore { get; set; }
            public Dictionary<string, string> TimeframeAnalysis { get; set; } = new Dictionary<string, string>();
        }

        public class PerformanceStats
        {
            public string Operation { get; set; }
            public long TotalExecutions { get; set; }
            public long TotalExecutionTime { get; set; }
            public double AverageExecutionTime { get; set; }
            public long LastExecutionTime { get; set; }
            public long MaxExecutionTime { get; set; }
            public long MinExecutionTime { get; set; }
            public long CacheHits { get; set; }
            public double CacheHitRate => TotalExecutions > 0 ? (double)CacheHits / TotalExecutions : 0;
        }

        /// <summary>
        /// Result of signal analysis with quality metrics
        /// </summary>
        public class SignalAnalysisResult
        {
            public string SignalType { get; set; }
            public DateTime Timestamp { get; set; }
            public int LookbackPeriod { get; set; }
            public double SignalStrength { get; set; }
            public PatternMatchResult PatternMatch { get; set; }
            public double VolumeConfirmation { get; set; }
            public double MomentumScore { get; set; }
            public double NoiseLevel { get; set; }
            public double QualityScore { get; set; }
            public string RiskLevel { get; set; }
            public Dictionary<string, object> AdditionalMetrics { get; set; } = new Dictionary<string, object>();
        }

        /// <summary>
        /// Result of pattern matching analysis
        /// </summary>
        public class PatternMatchResult
        {
            public string TrendPattern { get; set; } = "UNKNOWN";
            public string ReversalPattern { get; set; } = "NONE";
            public string ConsolidationPattern { get; set; } = "NONE";
            public double Confidence { get; set; } = 0.0;
            public Dictionary<string, double> PatternScores { get; set; } = new Dictionary<string, double>();
        }

        /// <summary>
        /// System health report for monitoring and diagnostics
        /// </summary>
        public class SystemHealthReport
        {
            public DateTime Timestamp { get; set; }
            public string OverallHealth { get; set; }
            public Dictionary<string, PerformanceStats> PerformanceMetrics { get; set; } = new Dictionary<string, PerformanceStats>();
            public Dictionary<string, object> CircuitBreakerStatus { get; set; } = new Dictionary<string, object>();
            public Dictionary<string, object> CacheStatistics { get; set; } = new Dictionary<string, object>();
            public Dictionary<string, object> MemoryUsage { get; set; } = new Dictionary<string, object>();
            public Dictionary<string, object> OperationLatency { get; set; } = new Dictionary<string, object>();
            public List<string> Recommendations { get; set; } = new List<string>();
            public string ErrorMessage { get; set; }
        }

        #endregion

        #region ML-Enhanced Position Sizing

        /// <summary>
        /// Machine learning enhanced position sizing with historical pattern recognition
        /// </summary>
        public static int CalculateMLEnhancedPositionSize(
            double accountSize,
            double baseRiskPercent,
            double stopDistance,
            double tickValue,
            MarketConditionContext context,
            HistoricalPerformanceData historicalData = null)
        {
            return ExecuteWithCircuitBreaker("position_sizing", () =>
            {
                // Start with base calculation
                int baseSize = CalculateOptimalContracts(accountSize, baseRiskPercent, stopDistance, tickValue);

                // Apply market condition adjustments
                double marketAdjustment = GetMarketConditionAdjustment(context);
                
                // Apply historical performance adjustment
                double historicalAdjustment = 1.0;
                if (historicalData != null)
                {
                    historicalAdjustment = CalculateHistoricalAdjustment(historicalData, context);
                }

                // Apply time-based adjustments
                double timeAdjustment = GetTimeBasedAdjustment(context.CurrentTime);

                // Apply volatility clustering adjustment
                double volatilityAdjustment = GetVolatilityClusteringAdjustment(context.RecentVolatility);

                // Combine all adjustments
                double totalAdjustment = marketAdjustment * historicalAdjustment * timeAdjustment * volatilityAdjustment;
                
                // Apply bounds checking
                totalAdjustment = Math.Max(0.25, Math.Min(3.0, totalAdjustment));

                int adjustedSize = Math.Max(1, (int)(baseSize * totalAdjustment));

                // Log the decision process for ML training
                LogPositionSizingDecision(baseSize, adjustedSize, context, totalAdjustment);

                return adjustedSize;
            }, 1); // Fallback to 1 contract if circuit breaker is open
        }

        /// <summary>
        /// Calculate market condition adjustment factor
        /// </summary>
        private static double GetMarketConditionAdjustment(MarketConditionContext context)
        {
            double adjustment = 1.0;

            // Trend strength adjustment
            if (context.TrendStrength > 0.8)
                adjustment *= 1.2; // Increase size in strong trends
            else if (context.TrendStrength < 0.3)
                adjustment *= 0.8; // Decrease size in weak trends

            // Volatility adjustment
            if (context.VolatilityPercentile > 0.8)
                adjustment *= 0.7; // Decrease size in high volatility
            else if (context.VolatilityPercentile < 0.2)
                adjustment *= 1.1; // Increase size in low volatility

            // Market regime adjustment
            switch (context.MarketRegime)
            {
                case "TRENDING_BULL":
                case "TRENDING_BEAR":
                    adjustment *= 1.15;
                    break;
                case "VOLATILE":
                    adjustment *= 0.6;
                    break;
                case "RANGING":
                    adjustment *= 0.9;
                    break;
            }

            return adjustment;
        }

        /// <summary>
        /// Calculate historical performance adjustment
        /// </summary>
        private static double CalculateHistoricalAdjustment(HistoricalPerformanceData data, MarketConditionContext context)
        {
            // Find similar historical conditions
            var similarConditions = data.GetSimilarConditions(context);
            
            if (similarConditions.Count == 0)
                return 1.0;

            // Calculate average performance in similar conditions
            double averageReturn = similarConditions.Average(c => c.Return);
            double winRate = similarConditions.Count(c => c.Return > 0) / (double)similarConditions.Count;

            // Adjust based on historical success
            double adjustment = 1.0;
            
            if (averageReturn > 0 && winRate > 0.6)
                adjustment = 1.0 + (averageReturn * 0.5); // Increase size for historically successful conditions
            else if (averageReturn < 0 || winRate < 0.4)
                adjustment = 1.0 - (Math.Abs(averageReturn) * 0.3); // Decrease size for historically poor conditions

            return Math.Max(0.5, Math.Min(2.0, adjustment));
        }

        /// <summary>
        /// Get time-based adjustment factor
        /// </summary>
        private static double GetTimeBasedAdjustment(DateTime currentTime)
        {
            // Adjust based on time of day/week
            double adjustment = 1.0;
            
            // Market open/close volatility
            if (currentTime.Hour >= 9 && currentTime.Hour <= 10)
                adjustment *= 0.8; // Reduce size during market open volatility
            else if (currentTime.Hour >= 15 && currentTime.Hour <= 16)
                adjustment *= 0.85; // Reduce size during market close volatility

            // Friday afternoon caution
            if (currentTime.DayOfWeek == DayOfWeek.Friday && currentTime.Hour >= 14)
                adjustment *= 0.9;

            return adjustment;
        }

        /// <summary>
        /// Get volatility clustering adjustment
        /// </summary>
        private static double GetVolatilityClusteringAdjustment(double[] recentVolatility)
        {
            if (recentVolatility == null || recentVolatility.Length < 5)
                return 1.0;

            // Check if we're in a volatility cluster
            double avgVolatility = recentVolatility.Average();
            double currentVolatility = recentVolatility[0];
            
            if (currentVolatility > avgVolatility * 1.5)
            {
                // High volatility cluster - reduce position size
                return 0.7;
            }
            else if (currentVolatility < avgVolatility * 0.5)
            {
                // Low volatility cluster - can increase position size slightly
                return 1.1;
            }

            return 1.0;
        }

        /// <summary>
        /// Log position sizing decision for ML training
        /// </summary>
        private static void LogPositionSizingDecision(int baseSize, int finalSize, MarketConditionContext context, double adjustment)
        {
            try
            {
                var logData = new
                {
                    Timestamp = DateTime.Now,
                    BaseSize = baseSize,
                    FinalSize = finalSize,
                    Adjustment = adjustment,
                    MarketRegime = context.MarketRegime,
                    TrendStrength = context.TrendStrength,
                    VolatilityPercentile = context.VolatilityPercentile,
                    TimeOfDay = context.CurrentTime.Hour
                };

                // In a real implementation, this would feed into ML training data
                LogPerformance($"Position sizing decision: {logData}");
            }
            catch (Exception ex)
            {
                LogError($"Error logging position sizing decision: {ex.Message}");
            }
        }

        #endregion

        #region ML Supporting Classes

        /// <summary>
        /// Context for market conditions used in ML-enhanced calculations
        /// </summary>
        public class MarketConditionContext
        {
            public string MarketRegime { get; set; }
            public double TrendStrength { get; set; }
            public double VolatilityPercentile { get; set; }
            public DateTime CurrentTime { get; set; }
            public double[] RecentVolatility { get; set; }
            public double CurrentPrice { get; set; }
            public double Volume { get; set; }
            public double AverageVolume { get; set; }
            public string SessionType { get; set; }
            public Dictionary<string, double> TechnicalIndicators { get; set; } = new Dictionary<string, double>();
        }

        /// <summary>
        /// Historical performance data for ML training
        /// </summary>
        public class HistoricalPerformanceData
        {
            public List<HistoricalCondition> Conditions { get; set; } = new List<HistoricalCondition>();

            public List<HistoricalCondition> GetSimilarConditions(MarketConditionContext context, double threshold = 0.8)
            {
                return Conditions.Where(c => CalculateSimilarity(c, context) >= threshold).ToList();
            }

            private double CalculateSimilarity(HistoricalCondition historical, MarketConditionContext current)
            {
                double similarity = 0.0;
                int factors = 0;

                // Compare market regime
                if (historical.MarketRegime == current.MarketRegime)
                {
                    similarity += 1.0;
                }
                factors++;

                // Compare trend strength (within 20% tolerance)
                if (Math.Abs(historical.TrendStrength - current.TrendStrength) < 0.2)
                {
                    similarity += 1.0;
                }
                factors++;

                // Compare volatility percentile (within 30% tolerance)
                if (Math.Abs(historical.VolatilityPercentile - current.VolatilityPercentile) < 0.3)
                {
                    similarity += 1.0;
                }
                factors++;

                // Compare time of day (within 2 hours)
                if (Math.Abs(historical.TimeOfDay - current.CurrentTime.Hour) <= 2)
                {
                    similarity += 1.0;
                }
                factors++;

                return similarity / factors;
            }
        }

        /// <summary>
        /// Historical condition record for ML training
        /// </summary>
        public class HistoricalCondition
        {
            public DateTime Timestamp { get; set; }
            public string MarketRegime { get; set; }
            public double TrendStrength { get; set; }
            public double VolatilityPercentile { get; set; }
            public int TimeOfDay { get; set; }
            public double Return { get; set; }
            public int PositionSize { get; set; }
            public double Risk { get; set; }
            public bool WasSuccessful { get; set; }
            public Dictionary<string, double> TechnicalIndicators { get; set; } = new Dictionary<string, double>();
        }

        /// <summary>
        /// Real-time market condition analyzer
        /// </summary>
        public static MarketConditionContext AnalyzeCurrentMarketCondition(
            double price, 
            double ema9, 
            double sma20, 
            double atr, 
            double volume, 
            double avgVolume,
            double[] priceHistory = null,
            double[] volumeHistory = null)
        {
            var context = new MarketConditionContext
            {
                CurrentTime = DateTime.Now,
                CurrentPrice = price,
                Volume = volume,
                AverageVolume = avgVolume
            };

            // Get enhanced market regime
            var regimeResult = GetEnhancedMarketRegime(price, ema9, sma20, atr, volume, avgVolume, priceHistory);
            context.MarketRegime = regimeResult.Regime;
            context.TrendStrength = regimeResult.Confidence;
            context.VolatilityPercentile = regimeResult.VolatilityPercentile;

            // Calculate recent volatility
            if (priceHistory != null && priceHistory.Length >= 5)
            {
                context.RecentVolatility = CalculateRecentVolatility(priceHistory, 5);
            }

            // Determine session type
            context.SessionType = GetSessionType(context.CurrentTime);

            // Add technical indicators
            context.TechnicalIndicators["EMA9"] = ema9;
            context.TechnicalIndicators["SMA20"] = sma20;
            context.TechnicalIndicators["ATR"] = atr;
            context.TechnicalIndicators["VolumeRatio"] = volume / avgVolume;

            return context;
        }

        /// <summary>
        /// Calculate recent volatility array
        /// </summary>
        private static double[] CalculateRecentVolatility(double[] prices, int periods)
        {
            if (prices.Length < periods + 1)
                return new double[0];

            var volatility = new double[periods];
            for (int i = 0; i < periods; i++)
            {
                if (i < prices.Length - 1)
                {
                    volatility[i] = Math.Abs(prices[i] - prices[i + 1]) / prices[i + 1];
                }
            }

            return volatility;
        }

        /// <summary>
        /// Get current session type
        /// </summary>
        private static string GetSessionType(DateTime currentTime)
        {
            int hour = currentTime.Hour;
            
            if (hour >= 9 && hour <= 10)
                return "MARKET_OPEN";
            else if (hour >= 15 && hour <= 16)
                return "MARKET_CLOSE";
            else if (hour >= 11 && hour <= 14)
                return "MIDDAY";
            else if (hour >= 17 || hour <= 8)
                return "AFTER_HOURS";
            else
                return "REGULAR_HOURS";
        }

        #endregion

        #region Advanced Signal Processing

        /// <summary>
        /// Advanced signal processing with pattern recognition
        /// </summary>
        public static SignalAnalysisResult AnalyzeSignalQuality(
            double[] prices, 
            double[] volumes, 
            double[] indicators,
            string signalType,
            int lookbackPeriod = 20)
        {
            return ExecuteWithCircuitBreaker("signal_analysis", () =>
            {
                var result = new SignalAnalysisResult
                {
                    SignalType = signalType,
                    Timestamp = DateTime.Now,
                    LookbackPeriod = lookbackPeriod
                };

                // Calculate signal strength
                result.SignalStrength = CalculateSignalStrength(prices, volumes, indicators);

                // Analyze price patterns
                result.PatternMatch = AnalyzePricePatterns(prices, lookbackPeriod);

                // Calculate volume confirmation
                result.VolumeConfirmation = CalculateVolumeConfirmation(volumes, lookbackPeriod);

                // Analyze momentum
                result.MomentumScore = CalculateMomentumScore(prices, lookbackPeriod);

                // Calculate noise level
                result.NoiseLevel = CalculateNoiseLevel(prices, lookbackPeriod);

                // Overall quality score
                result.QualityScore = CalculateOverallQualityScore(result);

                // Risk assessment
                result.RiskLevel = AssessSignalRisk(result);

                return result;
            }, new SignalAnalysisResult { SignalType = signalType, QualityScore = 0.0 });
        }

        /// <summary>
        /// Calculate signal strength based on multiple factors
        /// </summary>
        private static double CalculateSignalStrength(double[] prices, double[] volumes, double[] indicators)
        {
            if (prices.Length < 5) return 0.0;

            double priceStrength = 0.0;
            double volumeStrength = 0.0;
            double indicatorStrength = 0.0;

            // Price momentum strength
            double recentChange = (prices[0] - prices[Math.Min(4, prices.Length - 1)]) / prices[Math.Min(4, prices.Length - 1)];
            priceStrength = Math.Min(1.0, Math.Abs(recentChange) * 10); // Normalize to 0-1

            // Volume strength
            if (volumes.Length >= 5)
            {
                double avgVolume = volumes.Skip(1).Take(4).Average();
                volumeStrength = Math.Min(1.0, volumes[0] / avgVolume - 1.0);
            }

            // Indicator strength
            if (indicators.Length >= 2)
            {
                double indicatorChange = Math.Abs(indicators[0] - indicators[1]);
                indicatorStrength = Math.Min(1.0, indicatorChange * 5); // Normalize
            }

            return (priceStrength * 0.4) + (volumeStrength * 0.3) + (indicatorStrength * 0.3);
        }

        /// <summary>
        /// Analyze price patterns for signal confirmation
        /// </summary>
        private static PatternMatchResult AnalyzePricePatterns(double[] prices, int lookback)
        {
            var result = new PatternMatchResult();

            if (prices.Length < lookback)
                return result;

            // Check for trending patterns
            result.TrendPattern = DetectTrendPattern(prices, lookback);

            // Check for reversal patterns
            result.ReversalPattern = DetectReversalPattern(prices, lookback);

            // Check for consolidation patterns
            result.ConsolidationPattern = DetectConsolidationPattern(prices, lookback);

            // Calculate overall pattern confidence
            result.Confidence = CalculatePatternConfidence(result);

            return result;
        }

        /// <summary>
        /// Detect trending patterns in price data
        /// </summary>
        private static string DetectTrendPattern(double[] prices, int lookback)
        {
            if (prices.Length < lookback) return "UNKNOWN";

            int upCount = 0;
            int downCount = 0;

            for (int i = 1; i < Math.Min(lookback, prices.Length); i++)
            {
                if (prices[i-1] > prices[i]) upCount++;
                else if (prices[i-1] < prices[i]) downCount++;
            }

            double upRatio = (double)upCount / (lookback - 1);
            
            if (upRatio > 0.7) return "STRONG_UPTREND";
            else if (upRatio > 0.6) return "UPTREND";
            else if (upRatio < 0.3) return "STRONG_DOWNTREND";
            else if (upRatio < 0.4) return "DOWNTREND";
            else return "SIDEWAYS";
        }

        /// <summary>
        /// Detect reversal patterns
        /// </summary>
        private static string DetectReversalPattern(double[] prices, int lookback)
        {
            if (prices.Length < 5) return "NONE";

            // Simple reversal detection based on recent price action
            double recentHigh = prices.Take(3).Max();
            double recentLow = prices.Take(3).Min();
            double priorHigh = prices.Skip(2).Take(3).Max();
            double priorLow = prices.Skip(2).Take(3).Min();

            if (recentHigh > priorHigh && prices[0] < prices[1])
                return "POTENTIAL_TOP";
            else if (recentLow < priorLow && prices[0] > prices[1])
                return "POTENTIAL_BOTTOM";
            else
                return "NONE";
        }

        /// <summary>
        /// Detect consolidation patterns
        /// </summary>
        private static string DetectConsolidationPattern(double[] prices, int lookback)
        {
            if (prices.Length < lookback) return "NONE";

            double high = prices.Take(lookback).Max();
            double low = prices.Take(lookback).Min();
            double range = high - low;
            double avgPrice = prices.Take(lookback).Average();

            // Check if price is consolidating (low volatility)
            if (range / avgPrice < 0.02) // Less than 2% range
                return "TIGHT_CONSOLIDATION";
            else if (range / avgPrice < 0.04) // Less than 4% range
                return "CONSOLIDATION";
            else
                return "NONE";
        }

        /// <summary>
        /// Calculate pattern confidence score
        /// </summary>
        private static double CalculatePatternConfidence(PatternMatchResult pattern)
        {
            double confidence = 0.0;
            int factors = 0;

            // Add confidence based on pattern types
            if (pattern.TrendPattern != "UNKNOWN" && pattern.TrendPattern != "SIDEWAYS")
            {
                confidence += 0.4;
                factors++;
            }

            if (pattern.ReversalPattern != "NONE")
            {
                confidence += 0.3;
                factors++;
            }

            if (pattern.ConsolidationPattern != "NONE")
            {
                confidence += 0.3;
                factors++;
            }

            return factors > 0 ? confidence / factors : 0.0;
        }

        /// <summary>
        /// Calculate volume confirmation score
        /// </summary>
        private static double CalculateVolumeConfirmation(double[] volumes, int lookback)
        {
            if (volumes.Length < 5) return 0.5;

            double currentVolume = volumes[0];
            double avgVolume = volumes.Skip(1).Take(Math.Min(lookback, volumes.Length - 1)).Average();

            // Volume confirmation based on current vs average
            double volumeRatio = currentVolume / avgVolume;
            
            if (volumeRatio > 1.5) return 1.0; // Strong volume confirmation
            else if (volumeRatio > 1.2) return 0.8; // Good volume confirmation
            else if (volumeRatio > 0.8) return 0.6; // Moderate volume confirmation
            else return 0.3; // Weak volume confirmation
        }

        /// <summary>
        /// Calculate noise level in price data
        /// </summary>
        private static double CalculateNoiseLevel(double[] prices, int lookback)
        {
            if (prices.Length < lookback) return 0.5;

            // Calculate price changes
            var changes = new List<double>();
            for (int i = 1; i < Math.Min(lookback, prices.Length); i++)
            {
                changes.Add(Math.Abs(prices[i-1] - prices[i]) / prices[i]);
            }

            if (changes.Count == 0) return 0.5;

            // Calculate coefficient of variation as noise measure
            double avgChange = changes.Average();
            double stdDev = Math.Sqrt(changes.Select(x => Math.Pow(x - avgChange, 2)).Average());
            
            double noiseLevel = avgChange > 0 ? stdDev / avgChange : 0.5;
            
            return Math.Min(1.0, noiseLevel);
        }

        /// <summary>
        /// Calculate overall signal quality score
        /// </summary>
        private static double CalculateOverallQualityScore(SignalAnalysisResult result)
        {
            double score = 0.0;
            
            // Weight different factors
            score += result.SignalStrength * 0.25;
            score += result.PatternMatch.Confidence * 0.25;
            score += result.VolumeConfirmation * 0.20;
            score += result.MomentumScore * 0.15;
            score += (1.0 - result.NoiseLevel) * 0.15; // Lower noise = higher quality
            
            return Math.Max(0.0, Math.Min(1.0, score));
        }

        /// <summary>
        /// Assess signal risk level
        /// </summary>
        private static string AssessSignalRisk(SignalAnalysisResult result)
        {
            if (result.QualityScore > 0.8 && result.NoiseLevel < 0.3)
                return "LOW";
            else if (result.QualityScore > 0.6 && result.NoiseLevel < 0.5)
                return "MEDIUM";
            else if (result.QualityScore > 0.4 && result.NoiseLevel < 0.7)
                return "HIGH";
            else
                return "VERY_HIGH";
        }

        #endregion

        #region Enhanced Monitoring and Diagnostics

        /// <summary>
        /// System health monitoring and diagnostics
        /// </summary>
        public static SystemHealthReport GetSystemHealthReport()
        {
            var report = new SystemHealthReport
            {
                Timestamp = DateTime.Now,
                OverallHealth = "HEALTHY"
            };

            try
            {
                // Performance metrics
                var perfStats = GetPerformanceStatistics();
                report.PerformanceMetrics = perfStats;

                // Circuit breaker status
                var circuitStatus = GetCircuitBreakerStatus();
                report.CircuitBreakerStatus = circuitStatus;

                // Cache statistics
                report.CacheStatistics = GetCacheStatistics();

                // Memory usage
                report.MemoryUsage = GetMemoryUsage();

                // Operation latency
                report.OperationLatency = GetOperationLatency();

                // Determine overall health
                report.OverallHealth = DetermineOverallHealth(report);

                // Generate recommendations
                report.Recommendations = GenerateRecommendations(report);

            }
            catch (Exception ex)
            {
                report.OverallHealth = "ERROR";
                report.ErrorMessage = ex.Message;
                LogError($"System health check failed: {ex.Message}");
            }

            return report;
        }

        /// <summary>
        /// Get cache statistics
        /// </summary>
        private static Dictionary<string, object> GetCacheStatistics()
        {
            var stats = new Dictionary<string, object>();
            
            lock (lockObject)
            {
                stats["TotalCacheEntries"] = threadSafePerformanceCache.Count;
                stats["CacheHitRate"] = CalculateOverallCacheHitRate();
                stats["LastCacheCleanup"] = lastCacheUpdate;
                stats["CacheMemoryEstimate"] = EstimateCacheMemoryUsage();
            }

            return stats;
        }

        /// <summary>
        /// Calculate overall cache hit rate
        /// </summary>
        private static double CalculateOverallCacheHitRate()
        {
            lock (performanceStatsLock)
            {
                if (operationStats.Count == 0) return 0.0;

                long totalExecutions = operationStats.Values.Sum(s => s.TotalExecutions);
                long totalCacheHits = operationStats.Values.Sum(s => s.CacheHits);

                return totalExecutions > 0 ? (double)totalCacheHits / totalExecutions : 0.0;
            }
        }

        /// <summary>
        /// Estimate cache memory usage
        /// </summary>
        private static long EstimateCacheMemoryUsage()
        {
            // Rough estimate - each cache entry is approximately 100 bytes
            return threadSafePerformanceCache.Count * 100;
        }

        /// <summary>
        /// Get memory usage statistics
        /// </summary>
        private static Dictionary<string, object> GetMemoryUsage()
        {
            var stats = new Dictionary<string, object>();
            
            try
            {
                var process = Process.GetCurrentProcess();
                stats["WorkingSet"] = process.WorkingSet64;
                stats["VirtualMemory"] = process.VirtualMemorySize64;
                stats["PrivateMemory"] = process.PrivateMemorySize64;
                stats["GCTotalMemory"] = GC.GetTotalMemory(false);
            }
            catch (Exception ex)
            {
                stats["Error"] = ex.Message;
            }

            return stats;
        }

        /// <summary>
        /// Get operation latency statistics
        /// </summary>
        private static Dictionary<string, object> GetOperationLatency()
        {
            var latencyStats = new Dictionary<string, object>();
            
            lock (performanceStatsLock)
            {
                foreach (var kvp in operationStats)
                {
                    latencyStats[kvp.Key] = new
                    {
                        AverageLatency = kvp.Value.AverageExecutionTime,
                        MaxLatency = kvp.Value.MaxExecutionTime,
                        MinLatency = kvp.Value.MinExecutionTime,
                        LastLatency = kvp.Value.LastExecutionTime
                    };
                }
            }

            return latencyStats;
        }

        /// <summary>
        /// Determine overall system health
        /// </summary>
        private static string DetermineOverallHealth(SystemHealthReport report)
        {
            int healthScore = 100;

            // Check circuit breakers
            foreach (var cb in report.CircuitBreakerStatus.Values)
            {
                var cbData = cb as dynamic;
                if (cbData != null && cbData.State == "Open")
                {
                    healthScore -= 20;
                }
            }

            // Check cache hit rate
            if (report.CacheStatistics.ContainsKey("CacheHitRate"))
            {
                var hitRate = (double)report.CacheStatistics["CacheHitRate"];
                if (hitRate < 0.5) healthScore -= 10;
            }

            // Check performance metrics
            if (report.PerformanceMetrics.Any(pm => pm.Value.AverageExecutionTime > 1000))
            {
                healthScore -= 15; // Slow operations
            }

            if (healthScore >= 90) return "EXCELLENT";
            else if (healthScore >= 80) return "GOOD";
            else if (healthScore >= 70) return "FAIR";
            else if (healthScore >= 60) return "POOR";
            else return "CRITICAL";
        }

        /// <summary>
        /// Generate system recommendations
        /// </summary>
        private static List<string> GenerateRecommendations(SystemHealthReport report)
        {
            var recommendations = new List<string>();

            // Cache recommendations
            if (report.CacheStatistics.ContainsKey("CacheHitRate"))
            {
                var hitRate = (double)report.CacheStatistics["CacheHitRate"];
                if (hitRate < 0.5)
                {
                    recommendations.Add("Consider increasing cache timeout to improve hit rate");
                }
            }

            // Performance recommendations
            var slowOperations = report.PerformanceMetrics.Where(pm => pm.Value.AverageExecutionTime > 500);
            if (slowOperations.Any())
            {
                recommendations.Add($"Optimize slow operations: {string.Join(", ", slowOperations.Select(so => so.Key))}");
            }

            // Circuit breaker recommendations
            var openCircuits = report.CircuitBreakerStatus.Where(cb => 
            {
                var cbData = cb.Value as dynamic;
                return cbData != null && cbData.State == "Open";
            });
            
            if (openCircuits.Any())
            {
                recommendations.Add($"Investigate open circuit breakers: {string.Join(", ", openCircuits.Select(oc => oc.Key))}");
            }

            // Memory recommendations
            if (report.MemoryUsage.ContainsKey("WorkingSet"))
            {
                var workingSet = (long)report.MemoryUsage["WorkingSet"];
                if (workingSet > 500 * 1024 * 1024) // 500MB
                {
                    recommendations.Add("Consider memory optimization - working set is high");
                }
            }

            return recommendations;
        }

        /// <summary>
        /// Reset all system statistics
        /// </summary>
        public static void ResetSystemStatistics()
        {
            ClearCache();
            
            lock (performanceStatsLock)
            {
                operationStats.Clear();
            }

            // Reset circuit breakers
            foreach (var cb in circuitBreakers.Values)
            {
                // Circuit breakers will reset themselves over time
            }

            LogPerformance("System statistics reset");
        }

        #endregion
    }
}