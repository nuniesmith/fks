#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading;
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
using System.Diagnostics;
using System.IO;
#endregion

namespace NinjaTrader.NinjaScript.AddOns.FKS
{
    /// <summary>
    /// Enhanced market-specific analysis and configuration management
    /// Provides advanced market regime detection, session management, dynamic parameter adjustment,
    /// machine learning integration, and comprehensive market analytics
    /// </summary>
    public static class FKS_Market
    {
        #region Thread-Safe Collections and State Management
        
        private static readonly ReaderWriterLockSlim rwLock = new ReaderWriterLockSlim();
        private static readonly object cacheLock = new object();
        private static readonly ConcurrentDictionary<string, MarketRegimeAnalysis> regimeCache = new ConcurrentDictionary<string, MarketRegimeAnalysis>();
        private static readonly ConcurrentDictionary<string, DateTime> lastRegimeUpdate = new ConcurrentDictionary<string, DateTime>();
        private static readonly ConcurrentDictionary<string, MarketAnalytics> marketAnalytics = new ConcurrentDictionary<string, MarketAnalytics>();
        private static readonly ConcurrentQueue<MarketDataSnapshot> marketHistory = new ConcurrentQueue<MarketDataSnapshot>();
        
        // Performance and monitoring
        private static readonly ConcurrentDictionary<string, long> operationCounters = new ConcurrentDictionary<string, long>();
        private static readonly ConcurrentDictionary<string, double> performanceMetrics = new ConcurrentDictionary<string, double>();
        private static readonly Timer analyticsTimer;
        private static readonly Timer cleanupTimer;
        
        // Configuration and cache management
        private static readonly TimeSpan RegimeCacheTimeout = TimeSpan.FromMinutes(2);
        private static readonly TimeSpan AnalyticsUpdateInterval = TimeSpan.FromSeconds(30);
        private static readonly int MaxHistorySize = 1000;
        private static volatile bool isInitialized = false;
        
        #endregion

        #region Enhanced Market Sessions with Commission Optimization
        
        private static readonly ConcurrentDictionary<string, MarketSession[]> marketSessions = new ConcurrentDictionary<string, MarketSession[]>(
            new Dictionary<string, MarketSession[]>
            {
                ["Gold"] = new[]
                {
                    new MarketSession { Name = "Asian", Start = 18, End = 2, IsOptimal = false, VolumeMultiplier = 0.7, CommissionEfficiency = 0.6 },
                    new MarketSession { Name = "London", Start = 3, End = 7, IsOptimal = false, VolumeMultiplier = 0.9, CommissionEfficiency = 0.7 },
                    new MarketSession { Name = "US Morning", Start = 8, End = 12, IsOptimal = true, VolumeMultiplier = 1.3, CommissionEfficiency = 1.0 },
                    new MarketSession { Name = "US Afternoon", Start = 12, End = 14, IsOptimal = true, VolumeMultiplier = 1.1, CommissionEfficiency = 0.9 }, // Shortened for commission optimization
                    new MarketSession { Name = "US Close", Start = 14, End = 16, IsOptimal = false, VolumeMultiplier = 0.8, CommissionEfficiency = 0.5 }
                },
                ["ES"] = new[]
                {
                    new MarketSession { Name = "Pre-Market", Start = 4, End = 9, IsOptimal = false, VolumeMultiplier = 0.6, CommissionEfficiency = 0.4 },
                    new MarketSession { Name = "RTH Morning", Start = 9, End = 12, IsOptimal = true, VolumeMultiplier = 1.4, CommissionEfficiency = 1.0 },
                    new MarketSession { Name = "RTH Afternoon", Start = 12, End = 14, IsOptimal = true, VolumeMultiplier = 1.2, CommissionEfficiency = 0.9 }, // Shortened
                    new MarketSession { Name = "RTH Close", Start = 14, End = 15, IsOptimal = false, VolumeMultiplier = 1.1, CommissionEfficiency = 0.7 },
                    new MarketSession { Name = "Post-Market", Start = 15, End = 18, IsOptimal = false, VolumeMultiplier = 0.5, CommissionEfficiency = 0.3 }
                },
                ["NQ"] = new[]
                {
                    new MarketSession { Name = "Pre-Market", Start = 4, End = 9, IsOptimal = false, VolumeMultiplier = 0.5, CommissionEfficiency = 0.3 },
                    new MarketSession { Name = "RTH Morning", Start = 9, End = 12, IsOptimal = true, VolumeMultiplier = 1.5, CommissionEfficiency = 1.0 },
                    new MarketSession { Name = "RTH Midday", Start = 12, End = 13, IsOptimal = true, VolumeMultiplier = 1.3, CommissionEfficiency = 0.9 }, // Shortened for commission optimization
                    new MarketSession { Name = "RTH Afternoon", Start = 13, End = 15, IsOptimal = false, VolumeMultiplier = 1.0, CommissionEfficiency = 0.6 },
                    new MarketSession { Name = "Post-Market", Start = 15, End = 18, IsOptimal = false, VolumeMultiplier = 0.4, CommissionEfficiency = 0.2 }
                },
                ["CL"] = new[]
                {
                    new MarketSession { Name = "Asia", Start = 18, End = 2, IsOptimal = false, VolumeMultiplier = 0.6, CommissionEfficiency = 0.4 },
                    new MarketSession { Name = "Europe", Start = 2, End = 8, IsOptimal = false, VolumeMultiplier = 0.8, CommissionEfficiency = 0.6 },
                    new MarketSession { Name = "US Morning", Start = 9, End = 14, IsOptimal = true, VolumeMultiplier = 1.3, CommissionEfficiency = 1.0 },
                    new MarketSession { Name = "US Close", Start = 14, End = 17, IsOptimal = false, VolumeMultiplier = 0.9, CommissionEfficiency = 0.5 }
                },
                ["BTC"] = new[]
                {
                    new MarketSession { Name = "Weekend", Start = 0, End = 24, IsOptimal = true, VolumeMultiplier = 0.8, CommissionEfficiency = 0.6 }, // Weekend only for commission optimization
                    new MarketSession { Name = "Asian Active", Start = 0, End = 8, IsOptimal = false, VolumeMultiplier = 1.2, CommissionEfficiency = 0.4 },
                    new MarketSession { Name = "European Active", Start = 8, End = 16, IsOptimal = false, VolumeMultiplier = 1.0, CommissionEfficiency = 0.3 },
                    new MarketSession { Name = "US Active", Start = 16, End = 24, IsOptimal = false, VolumeMultiplier = 1.1, CommissionEfficiency = 0.3 }
                }
            });
        #endregion
        
        #region Enhanced Market Characteristics with Commission Optimization
        
        private static readonly ConcurrentDictionary<string, MarketCharacteristics> marketCharacteristics = new ConcurrentDictionary<string, MarketCharacteristics>(
            new Dictionary<string, MarketCharacteristics>
            {
                ["Gold"] = new MarketCharacteristics
                {
                    TypicalDailyRange = 25.0,
                    HighVolatilityThreshold = 40.0,
                    LowVolatilityThreshold = 15.0,
                    TrendStrengthMultiplier = 1.0,
                    NewsImpactLevel = MarketImpactLevel.High,
                    CorrelatedMarkets = new[] { "DX", "SI", "EUR" },
                    
                    // Commission optimization properties
                    OptimalCommissionWindow = new TimeSpan(8, 0, 0), // 8 AM
                    MinimumProfitMultiple = 3.0, // 3x commission minimum
                    VolatilityCommissionAdjustment = 1.2,
                    SessionCommissionMultipliers = new Dictionary<string, double>
                    {
                        ["US Morning"] = 1.0,
                        ["US Afternoon"] = 0.9,
                        ["London"] = 0.8,
                        ["Asian"] = 0.6
                    },
                    
                    // Advanced analytics
                    MeanReversionTendency = 0.6,
                    TrendPersistence = 0.7,
                    SeasonalityFactors = new Dictionary<string, double>
                    {
                        ["Monday"] = 1.0,
                        ["Tuesday"] = 1.1,
                        ["Wednesday"] = 1.2, // EIA day affects gold through dollar
                        ["Thursday"] = 1.0,
                        ["Friday"] = 0.9
                    }
                },
                ["ES"] = new MarketCharacteristics
                {
                    TypicalDailyRange = 50.0,
                    HighVolatilityThreshold = 80.0,
                    LowVolatilityThreshold = 25.0,
                    TrendStrengthMultiplier = 1.2,
                    NewsImpactLevel = MarketImpactLevel.VeryHigh,
                    CorrelatedMarkets = new[] { "NQ", "YM", "RTY" },
                    
                    OptimalCommissionWindow = new TimeSpan(9, 30, 0), // Market open
                    MinimumProfitMultiple = 2.5,
                    VolatilityCommissionAdjustment = 1.3,
                    SessionCommissionMultipliers = new Dictionary<string, double>
                    {
                        ["RTH Morning"] = 1.0,
                        ["RTH Afternoon"] = 0.8,
                        ["Pre-Market"] = 0.4,
                        ["Post-Market"] = 0.3
                    },
                    
                    MeanReversionTendency = 0.5,
                    TrendPersistence = 0.8,
                    SeasonalityFactors = new Dictionary<string, double>
                    {
                        ["Monday"] = 1.1, // Monday gap effects
                        ["Tuesday"] = 1.0,
                        ["Wednesday"] = 1.0,
                        ["Thursday"] = 1.0,
                        ["Friday"] = 0.8 // Friday afternoon weakness
                    }
                },
                ["NQ"] = new MarketCharacteristics
                {
                    TypicalDailyRange = 200.0,
                    HighVolatilityThreshold = 350.0,
                    LowVolatilityThreshold = 100.0,
                    TrendStrengthMultiplier = 1.3,
                    NewsImpactLevel = MarketImpactLevel.VeryHigh,
                    CorrelatedMarkets = new[] { "ES", "YM", "RTY" },
                    
                    OptimalCommissionWindow = new TimeSpan(9, 30, 0),
                    MinimumProfitMultiple = 3.5, // Higher due to volatility
                    VolatilityCommissionAdjustment = 1.5,
                    SessionCommissionMultipliers = new Dictionary<string, double>
                    {
                        ["RTH Morning"] = 1.0,
                        ["RTH Midday"] = 0.9,
                        ["RTH Afternoon"] = 0.6,
                        ["Pre-Market"] = 0.3,
                        ["Post-Market"] = 0.2
                    },
                    
                    MeanReversionTendency = 0.4,
                    TrendPersistence = 0.9,
                    SeasonalityFactors = new Dictionary<string, double>
                    {
                        ["Monday"] = 1.2, // Tech sector Monday effects
                        ["Tuesday"] = 1.1,
                        ["Wednesday"] = 1.0,
                        ["Thursday"] = 1.0,
                        ["Friday"] = 0.7 // Tech profit-taking on Fridays
                    }
                },
                ["CL"] = new MarketCharacteristics
                {
                    TypicalDailyRange = 2.0,
                    HighVolatilityThreshold = 3.5,
                    LowVolatilityThreshold = 1.0,
                    TrendStrengthMultiplier = 0.9,
                    NewsImpactLevel = MarketImpactLevel.VeryHigh,
                    CorrelatedMarkets = new[] { "RB", "HO", "NG" },
                    
                    OptimalCommissionWindow = new TimeSpan(10, 30, 0), // EIA report day
                    MinimumProfitMultiple = 4.0, // Highest due to news sensitivity
                    VolatilityCommissionAdjustment = 1.8,
                    SessionCommissionMultipliers = new Dictionary<string, double>
                    {
                        ["US Morning"] = 1.0,
                        ["Europe"] = 0.7,
                        ["Asia"] = 0.5,
                        ["US Close"] = 0.6
                    },
                    
                    MeanReversionTendency = 0.3,
                    TrendPersistence = 0.9,
                    SeasonalityFactors = new Dictionary<string, double>
                    {
                        ["Monday"] = 1.0,
                        ["Tuesday"] = 1.0,
                        ["Wednesday"] = 1.8, // EIA inventory day
                        ["Thursday"] = 1.0,
                        ["Friday"] = 0.9
                    }
                },
                ["BTC"] = new MarketCharacteristics
                {
                    TypicalDailyRange = 2000.0,
                    HighVolatilityThreshold = 5000.0,
                    LowVolatilityThreshold = 1000.0,
                    TrendStrengthMultiplier = 1.5,
                    NewsImpactLevel = MarketImpactLevel.Medium,
                    CorrelatedMarkets = new[] { "ETH", "LTC" },
                    
                    OptimalCommissionWindow = new TimeSpan(0, 0, 0), // Weekend only
                    MinimumProfitMultiple = 5.0, // Very high due to extreme volatility
                    VolatilityCommissionAdjustment = 2.0,
                    SessionCommissionMultipliers = new Dictionary<string, double>
                    {
                        ["Weekend"] = 1.0, // Only trade weekends for commission optimization
                        ["Asian Active"] = 0.3,
                        ["European Active"] = 0.2,
                        ["US Active"] = 0.2
                    },
                    
                    MeanReversionTendency = 0.2,
                    TrendPersistence = 0.95,
                    SeasonalityFactors = new Dictionary<string, double>
                    {
                        ["Monday"] = 1.2, // Weekend gap effects
                        ["Tuesday"] = 1.0,
                        ["Wednesday"] = 1.0,
                        ["Thursday"] = 1.0,
                        ["Friday"] = 1.1 // Weekend positioning
                    }
                }
            });
        #endregion
        
        #region Enhanced Economic Calendar Integration
        
        private static readonly ConcurrentQueue<EconomicEvent> upcomingEvents = new ConcurrentQueue<EconomicEvent>();
        private static readonly ConcurrentDictionary<string, List<EconomicEvent>> marketSpecificEvents = new ConcurrentDictionary<string, List<EconomicEvent>>();
        private static readonly Timer eventUpdateTimer;
        private static DateTime lastEventUpdate = DateTime.MinValue;
        private static readonly string[] highImpactEvents = { "NFP", "FOMC", "CPI", "EIA", "GDP" };
        private static readonly Dictionary<string, TimeSpan> eventAvoidancePeriods = new Dictionary<string, TimeSpan>
        {
            ["NFP"] = TimeSpan.FromMinutes(60),
            ["FOMC"] = TimeSpan.FromMinutes(120),
            ["CPI"] = TimeSpan.FromMinutes(45),
            ["EIA"] = TimeSpan.FromMinutes(30),
            ["GDP"] = TimeSpan.FromMinutes(30)
        };
        
        #endregion

        #region Static Constructor and Initialization
        
        static FKS_Market()
        {
            try
            {
                // Initialize timers
                analyticsTimer = new Timer(UpdateMarketAnalytics, null, AnalyticsUpdateInterval, AnalyticsUpdateInterval);
                cleanupTimer = new Timer(PerformCleanup, null, TimeSpan.FromMinutes(5), TimeSpan.FromMinutes(5));
                eventUpdateTimer = new Timer(UpdateEconomicCalendar, null, TimeSpan.FromMinutes(30), TimeSpan.FromMinutes(30));
                
                // Initialize market analytics
                InitializeMarketAnalytics();
                
                // Register with FKS Infrastructure
                RegisterWithInfrastructure();
                
                isInitialized = true;
                LogMessage("FKS Market enhanced system initialized", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"FKS Market initialization failed: {ex.Message}", LogLevel.Error);
            }
        }
        
        private static void InitializeMarketAnalytics()
        {
            try
            {
                foreach (var marketType in marketCharacteristics.Keys)
                {
                    marketAnalytics[marketType] = new MarketAnalytics
                    {
                        MarketType = marketType,
                        LastUpdate = DateTime.Now,
                        VolatilityModel = new VolatilityModel(),
                        TrendModel = new TrendModel(),
                        SessionAnalysis = new SessionAnalysis(),
                        CommissionMetrics = new CommissionMetrics()
                    };
                }
                
                LogMessage("Market analytics initialized for all markets", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"Market analytics initialization failed: {ex.Message}", LogLevel.Error);
            }
        }
        
        private static void RegisterWithInfrastructure()
        {
            try
            {
                FKS_Infrastructure.RegisterComponent("FKS_Market", new FKS_Infrastructure.ComponentRegistrationInfo
                {
                    ComponentType = "MarketAnalysis",
                    Version = "3.0.0",
                    IsCritical = false,
                    ExpectedResponseTime = TimeSpan.FromMilliseconds(200),
                    MaxMemoryUsage = 100 * 1024 * 1024 // 100MB
                });
                
                LogMessage("FKS Market registered with infrastructure", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"Infrastructure registration failed: {ex.Message}", LogLevel.Warning);
            }
        }
        
        #endregion

        #region Enhanced Public Methods
        
        /// <summary>
        /// Get current market session with enhanced analytics and commission optimization
        /// </summary>
        public static MarketSession GetCurrentSession(string marketType, DateTime time)
        {
            try
            {
                RecordOperation("GetCurrentSession");
                
                if (!marketSessions.TryGetValue(marketType, out var sessions))
                {
                    LogMessage($"Unknown market type: {marketType}", LogLevel.Warning);
                    return new MarketSession { Name = "Unknown", IsOptimal = false };
                }
                
                var hour = time.Hour;
                var dayOfWeek = time.DayOfWeek;
                
                // Special handling for BTC weekend-only trading (commission optimization)
                if (marketType == "BTC" && (dayOfWeek == DayOfWeek.Saturday || dayOfWeek == DayOfWeek.Sunday))
                {
                    return sessions.First(s => s.Name == "Weekend");
                }
                
                foreach (var session in sessions)
                {
                    if (IsInSession(hour, session))
                    {
                        // Apply dynamic commission efficiency based on market conditions
                        var analytics = marketAnalytics.TryGetValue(marketType, out var analyticsValue) ? analyticsValue : null;
                        if (analytics != null)
                        {
                            session.CommissionEfficiency *= analytics.CommissionMetrics.EfficiencyMultiplier;
                        }
                        
                        return session;
                    }
                }
                
                return sessions[0]; // Default to first session
            }
            catch (Exception ex)
            {
                LogMessage($"GetCurrentSession error: {ex.Message}", LogLevel.Error);
                return new MarketSession { Name = "Error", IsOptimal = false };
            }
        }
        
        /// <summary>
        /// Enhanced market regime analysis with machine learning and commission optimization
        /// </summary>
        public static MarketRegimeAnalysis AnalyzeMarketRegime(
            string marketType, 
            double currentVolatility, 
            double maSlope, 
            double volumeRatio,
            double priceRange,
            double[] priceHistory = null,
            TimeSpan? lookback = null)
        {
            try
            {
                var startTime = DateTime.Now;
                RecordOperation("AnalyzeMarketRegime");
                
                // Check cache first
                var cacheKey = $"{marketType}_{currentVolatility:F2}_{maSlope:F2}_{volumeRatio:F2}";
                if (regimeCache.TryGetValue(cacheKey, out var cachedResult))
                {
                    var timeSinceUpdate = DateTime.Now - (lastRegimeUpdate.TryGetValue(cacheKey, out var lastUpdate) ? lastUpdate : DateTime.MinValue);
                    if (timeSinceUpdate < RegimeCacheTimeout)
                    {
                        RecordPerformanceMetric("RegimeCacheHit", 1);
                        return cachedResult;
                    }
                }
                
                var analysis = new MarketRegimeAnalysis();
                var characteristics = GetMarketCharacteristics(marketType);
                
                // Enhanced volatility analysis with percentile ranking
                var volPercentile = CalculateVolatilityPercentile(currentVolatility, characteristics, priceHistory);
                analysis.VolatilityScore = volPercentile;
                
                if (volPercentile > 0.9)
                {
                    analysis.VolatilityRegime = "EXTREME";
                    analysis.VolatilityScore = 1.0;
                }
                else if (volPercentile > 0.75)
                {
                    analysis.VolatilityRegime = "VERY HIGH";
                    analysis.VolatilityScore = 0.9;
                }
                else if (volPercentile > 0.6)
                {
                    analysis.VolatilityRegime = "HIGH";
                    analysis.VolatilityScore = 0.7;
                }
                else if (volPercentile < 0.2)
                {
                    analysis.VolatilityRegime = "VERY LOW";
                    analysis.VolatilityScore = 0.2;
                }
                else if (volPercentile < 0.4)
                {
                    analysis.VolatilityRegime = "LOW";
                    analysis.VolatilityScore = 0.4;
                }
                else
                {
                    analysis.VolatilityRegime = "NORMAL";
                    analysis.VolatilityScore = 0.6;
                }
                
                // Enhanced trend analysis with persistence scoring
                var trendStrength = Math.Abs(maSlope) * characteristics.TrendStrengthMultiplier;
                var trendPersistence = CalculateTrendPersistence(priceHistory, characteristics);
                
                analysis.TrendScore = trendStrength * trendPersistence;
                
                if (analysis.TrendScore > 1.8)
                {
                    analysis.TrendRegime = maSlope > 0 ? "VERY STRONG BULL" : "VERY STRONG BEAR";
                    analysis.TrendScore = 1.0;
                }
                else if (analysis.TrendScore > 1.2)
                {
                    analysis.TrendRegime = maSlope > 0 ? "STRONG BULL" : "STRONG BEAR";
                    analysis.TrendScore = 0.9;
                }
                else if (analysis.TrendScore > 0.6)
                {
                    analysis.TrendRegime = maSlope > 0 ? "BULL" : "BEAR";
                    analysis.TrendScore = 0.7;
                }
                else
                {
                    analysis.TrendRegime = "RANGING";
                    analysis.TrendScore = 0.3;
                }
                
                // Enhanced volume analysis with session normalization
                var currentSession = GetCurrentSession(marketType, DateTime.Now);
                var normalizedVolumeRatio = volumeRatio / currentSession.VolumeMultiplier;
                
                if (normalizedVolumeRatio > 2.0)
                {
                    analysis.VolumeRegime = "EXPLOSIVE";
                    analysis.VolumeScore = 1.0;
                }
                else if (normalizedVolumeRatio > 1.5)
                {
                    analysis.VolumeRegime = "HIGH";
                    analysis.VolumeScore = 0.9;
                }
                else if (normalizedVolumeRatio < 0.5)
                {
                    analysis.VolumeRegime = "VERY LOW";
                    analysis.VolumeScore = 0.2;
                }
                else if (normalizedVolumeRatio < 0.7)
                {
                    analysis.VolumeRegime = "LOW";
                    analysis.VolumeScore = 0.4;
                }
                else
                {
                    analysis.VolumeRegime = "NORMAL";
                    analysis.VolumeScore = 0.6;
                }
                
                // Overall regime determination with commission considerations
                analysis.OverallRegime = DetermineOverallRegime(analysis, characteristics);
                analysis.TradingRecommendation = GetEnhancedTradingRecommendation(analysis, marketType, currentSession);
                
                // Commission optimization analysis
                analysis.CommissionViability = CalculateCommissionViability(analysis, characteristics, currentSession);
                analysis.OptimalSessionsToday = GetOptimalSessionsForToday(marketType);
                analysis.RiskAdjustedScore = CalculateRiskAdjustedScore(analysis, characteristics);
                
                // Machine learning enhancements
                if (priceHistory != null && priceHistory.Length > 50)
                {
                    analysis.MomentumScore = CalculateMomentumScore(priceHistory);
                    analysis.MeanReversionProbability = CalculateMeanReversionProbability(priceHistory, characteristics);
                    analysis.TrendContinuationProbability = CalculateTrendContinuationProbability(priceHistory, analysis);
                }
                
                // Seasonality adjustments
                ApplySeasonalityAdjustments(analysis, marketType);
                
                // Update analytics
                UpdateMarketAnalyticsForRegime(marketType, analysis);
                
                // Cache result
                regimeCache[cacheKey] = analysis;
                lastRegimeUpdate[cacheKey] = DateTime.Now;
                
                // Record performance metrics
                var processingTime = (DateTime.Now - startTime).TotalMilliseconds;
                RecordPerformanceMetric("RegimeAnalysisTime", processingTime);
                RecordPerformanceMetric("RegimeCacheMiss", 1);
                
                if (processingTime > 100) // Log slow operations
                {
                    LogMessage($"Slow regime analysis for {marketType}: {processingTime:F0}ms", LogLevel.Warning);
                }
                
                return analysis;
            }
            catch (Exception ex)
            {
                LogMessage($"Market regime analysis failed for {marketType}: {ex.Message}", LogLevel.Error);
                return CreateFallbackRegimeAnalysis(marketType);
            }
        }
        
        /// <summary>
        /// Enhanced dynamic parameters with commission optimization and machine learning
        /// </summary>
        public static DynamicParameters GetDynamicParameters(string marketType, MarketRegimeAnalysis regime)
        {
            try
            {
                RecordOperation("GetDynamicParameters");
                
                var baseConfig = FKS_Core.CurrentMarketConfig;
                var characteristics = GetMarketCharacteristics(marketType);
                var currentSession = GetCurrentSession(marketType, DateTime.Now);
                var parameters = new DynamicParameters();
                
                // Enhanced stop loss calculation with volatility clustering
                parameters.StopLossMultiplier = baseConfig?.ATRStopMultiplier ?? 2.0;
                
                // Volatility-based adjustments
                switch (regime.VolatilityRegime)
                {
                    case "EXTREME":
                        parameters.StopLossMultiplier *= 2.0;
                        break;
                    case "VERY HIGH":
                        parameters.StopLossMultiplier *= 1.6;
                        break;
                    case "HIGH":
                        parameters.StopLossMultiplier *= 1.3;
                        break;
                    case "VERY LOW":
                        parameters.StopLossMultiplier *= 0.7;
                        break;
                    case "LOW":
                        parameters.StopLossMultiplier *= 0.8;
                        break;
                }
                
                // Commission-optimized position sizing
                parameters.PositionSizeAdjustment = 1.0;
                
                // Base position size on commission viability
                if (regime.CommissionViability < 0.5)
                {
                    parameters.PositionSizeAdjustment = 0.3; // Very small positions for marginal setups
                }
                else if (regime.CommissionViability < 0.7)
                {
                    parameters.PositionSizeAdjustment = 0.6;
                }
                
                // Regime-based adjustments
                switch (regime.OverallRegime)
                {
                    case "EXPLOSIVE":
                        parameters.PositionSizeAdjustment *= 0.4; // Very conservative in explosive markets
                        break;
                    case "VOLATILE":
                        parameters.PositionSizeAdjustment *= 0.5;
                        break;
                    case "RANGING":
                        parameters.PositionSizeAdjustment *= 0.7;
                        break;
                    case "VERY STRONG BULL":
                    case "VERY STRONG BEAR":
                        parameters.PositionSizeAdjustment *= 1.3; // Take advantage of strong trends
                        break;
                    case "STRONG BULL":
                    case "STRONG BEAR":
                        parameters.PositionSizeAdjustment *= 1.15;
                        break;
                }
                
                // Session-based commission adjustments
                parameters.PositionSizeAdjustment *= currentSession.CommissionEfficiency;
                
                // Enhanced signal quality threshold with commission considerations
                parameters.SignalQualityThreshold = baseConfig?.SignalQualityThreshold ?? 0.70;
                
                // Commission optimization quality adjustments
                var commissionAdjustment = (1.0 - regime.CommissionViability) * 0.2; // Up to 20% increase
                parameters.SignalQualityThreshold += commissionAdjustment;
                
                // Volatility quality adjustments
                if (regime.VolatilityRegime == "EXTREME" || regime.VolatilityRegime == "VERY HIGH")
                {
                    parameters.SignalQualityThreshold += 0.15; // Require much better signals
                }
                
                // Volume quality adjustments
                if (regime.VolumeRegime == "VERY LOW" || regime.VolumeRegime == "LOW")
                {
                    parameters.SignalQualityThreshold += 0.1; // Require better signals in low volume
                }
                
                // Time-based adjustments (commission optimization)
                if (!currentSession.IsOptimal)
                {
                    parameters.PositionSizeAdjustment *= 0.4; // Much smaller positions outside optimal hours
                    parameters.SignalQualityThreshold += 0.1;
                }
                
                // Machine learning adjustments
                if (regime.MeanReversionProbability > 0.7)
                {
                    parameters.MeanReversionBias = 0.8; // Favor mean reversion strategies
                    parameters.TrendFollowingBias = 0.2;
                }
                else if (regime.TrendContinuationProbability > 0.7)
                {
                    parameters.MeanReversionBias = 0.2;
                    parameters.TrendFollowingBias = 0.8; // Favor trend following
                }
                else
                {
                    parameters.MeanReversionBias = 0.5;
                    parameters.TrendFollowingBias = 0.5;
                }
                
                // Economic event adjustments
                if (HasUpcomingHighImpactEvent(marketType, 15))
                {
                    parameters.PositionSizeAdjustment *= 0.3; // Very conservative before major events
                    parameters.SignalQualityThreshold += 0.2;
                }
                
                // Bounds checking
                parameters.StopLossMultiplier = Math.Max(0.8, Math.Min(3.0, parameters.StopLossMultiplier));
                parameters.PositionSizeAdjustment = Math.Max(0.1, Math.Min(2.0, parameters.PositionSizeAdjustment));
                parameters.SignalQualityThreshold = Math.Max(0.5, Math.Min(0.95, parameters.SignalQualityThreshold));
                
                return parameters;
            }
            catch (Exception ex)
            {
                LogMessage($"Dynamic parameters calculation failed for {marketType}: {ex.Message}", LogLevel.Error);
                return CreateFallbackDynamicParameters();
            }
        }
        
        /// <summary>
        /// Enhanced high-impact event detection with market-specific analysis
        /// </summary>
        public static bool HasUpcomingHighImpactEvent(string marketType, int minutesAhead = 30)
        {
            try
            {
                RecordOperation("HasUpcomingHighImpactEvent");
                
                UpdateEconomicCalendar(null); // Ensure calendar is current
                
                var characteristics = GetMarketCharacteristics(marketType);
                var checkTime = DateTime.Now.AddMinutes(minutesAhead);
                
                // Check market-specific events first
                if (marketSpecificEvents.TryGetValue(marketType, out var specificEvents))
                {
                    var hasSpecificEvent = specificEvents.Any(e => 
                        e.Time <= checkTime && 
                        e.Time >= DateTime.Now &&
                        e.Impact >= characteristics.NewsImpactLevel);
                    
                    if (hasSpecificEvent)
                    {
                        LogMessage($"High impact event detected for {marketType} within {minutesAhead} minutes", LogLevel.Information);
                        return true;
                    }
                }
                
                // Check global events
                var globalEvents = new List<EconomicEvent>();
                while (upcomingEvents.TryDequeue(out var evt))
                {
                    globalEvents.Add(evt);
                }
                
                // Re-queue events
                foreach (var evt in globalEvents)
                {
                    upcomingEvents.Enqueue(evt);
                }
                
                var hasGlobalEvent = globalEvents.Any(e => 
                    e.Time <= checkTime && 
                    e.Time >= DateTime.Now &&
                    e.Impact >= characteristics.NewsImpactLevel &&
                    (e.Currency == GetMarketCurrency(marketType) || e.IsGlobal));
                
                if (hasGlobalEvent)
                {
                    LogMessage($"High impact global event affecting {marketType} within {minutesAhead} minutes", LogLevel.Information);
                }
                
                return hasGlobalEvent;
            }
            catch (Exception ex)
            {
                LogMessage($"Event detection failed for {marketType}: {ex.Message}", LogLevel.Error);
                return false; // Default to no events to avoid blocking trading
            }
        }
        
        /// <summary>
        /// Get comprehensive market tips with commission optimization focus
        /// </summary>
        public static List<string> GetMarketTips(string marketType, MarketRegimeAnalysis regime)
        {
            var tips = new List<string>();
            
            try
            {
                RecordOperation("GetMarketTips");
                
                var characteristics = GetMarketCharacteristics(marketType);
                var currentSession = GetCurrentSession(marketType, DateTime.Now);
                
                // Commission optimization tips
                if (regime.CommissionViability < 0.6)
                {
                    tips.Add("⚠️ LOW COMMISSION VIABILITY - Consider increasing quality thresholds or avoiding this session");
                }
                
                if (!currentSession.IsOptimal)
                {
                    tips.Add($"📍 Sub-optimal session ({currentSession.Name}) - commission efficiency: {currentSession.CommissionEfficiency:P0}");
                }
                
                // Market-specific tips
                switch (marketType)
                {
                    case "Gold":
                        tips.Add("📊 Watch DXY for inverse correlation (r=-0.7 typically)");
                        tips.Add("📰 Monitor Fed announcements and inflation data");
                        
                        if (regime.VolatilityRegime == "VERY HIGH")
                            tips.Add("⚡ High volatility - reduce position sizes by 50%");
                        
                        if (DateTime.Now.DayOfWeek == DayOfWeek.Wednesday)
                            tips.Add("📈 Wednesday EIA may affect USD and impact gold");
                        
                        if (regime.MeanReversionProbability > 0.7)
                            tips.Add("🔄 High mean reversion probability - consider fading extremes");
                        break;
                        
                    case "ES":
                    case "NQ":
                        tips.Add("🕘 Best liquidity during RTH (9:30-4:00 ET)");
                        tips.Add("💹 Watch VIX for market sentiment (VIX >25 = high fear)");
                        
                        if (marketType == "NQ")
                            tips.Add("💻 Tech sector correlation - watch NASDAQ news");
                        
                        if (DateTime.Now.DayOfWeek == DayOfWeek.Friday)
                            tips.Add("📅 Friday afternoon often choppy - consider early exits after 2 PM");
                        
                        if (regime.TrendContinuationProbability > 0.8)
                            tips.Add("📈 Strong trend continuation probability - follow the momentum");
                        
                        if (currentSession.Name == "Pre-Market" || currentSession.Name == "Post-Market")
                            tips.Add("⚠️ Extended hours - wider spreads and lower liquidity");
                        break;
                        
                    case "CL":
                        tips.Add("🛢️ EIA inventory report Wednesday 10:30 AM ET - major volatility expected");
                        tips.Add("🌍 Geopolitical events in Middle East create significant gaps");
                        
                        if (regime.TrendRegime.Contains("STRONG"))
                            tips.Add("📊 Oil shows strong trend persistence - trends often continue for days");
                        
                        if (DateTime.Now.DayOfWeek == DayOfWeek.Wednesday && DateTime.Now.Hour >= 9)
                            tips.Add("⚠️ EIA REPORT DAY - expect 100%+ volatility increase around 10:30 AM");
                        
                        if (regime.VolatilityRegime == "EXTREME")
                            tips.Add("🚨 EXTREME VOLATILITY - consider avoiding new positions");
                        break;
                        
                    case "BTC":
                        tips.Add("🔄 24/7 market - Asian session often sets daily tone");
                        tips.Add("📱 Social media sentiment drives short-term moves");
                        
                        if (DateTime.Now.DayOfWeek == DayOfWeek.Saturday || DateTime.Now.DayOfWeek == DayOfWeek.Sunday)
                            tips.Add("📅 WEEKEND TRADING ONLY for commission optimization");
                        else
                            tips.Add("⛔ WEEKDAY TRADING NOT RECOMMENDED due to commission inefficiency");
                        
                        if (regime.VolatilityRegime == "VERY LOW")
                            tips.Add("📈 Low volatility often precedes explosive moves in crypto");
                        
                        if (regime.TrendPersistence > 0.9)
                            tips.Add("🚀 Crypto trends can be extremely persistent - ride the momentum");
                        break;
                }
                
                // Regime-specific tips
                switch (regime.OverallRegime)
                {
                    case "RANGING":
                        tips.Add("📍 Range-bound market - focus on support/resistance levels");
                        tips.Add("🎯 Mean reversion strategies favored over trend following");
                        break;
                    case "TRENDING BULL":
                    case "TRENDING BEAR":
                        tips.Add("📈 Strong trend detected - use pullbacks for entry");
                        tips.Add("🎯 Trend following strategies favored");
                        break;
                    case "VOLATILE":
                        tips.Add("⚡ High volatility - reduce position sizes significantly");
                        tips.Add("🛡️ Use wider stops and consider shorter timeframes");
                        break;
                    case "EXPLOSIVE":
                        tips.Add("🚨 EXPLOSIVE CONDITIONS - exercise extreme caution");
                        tips.Add("💰 Commission efficiency very low - avoid new positions");
                        break;
                }
                
                // Volume-specific tips
                if (regime.VolumeRegime == "VERY LOW")
                {
                    tips.Add("📉 Very low volume - expect choppy price action and wider spreads");
                    tips.Add("⚠️ Low volume reduces commission efficiency");
                }
                else if (regime.VolumeRegime == "EXPLOSIVE")
                {
                    tips.Add("💥 Explosive volume - major moves likely, but very risky");
                }
                
                // Time-specific tips
                var timeUntilOptimal = GetTimeUntilOptimalSession(marketType);
                if (timeUntilOptimal > TimeSpan.Zero && timeUntilOptimal < TimeSpan.FromHours(2))
                {
                    tips.Add($"⏰ Optimal session begins in {timeUntilOptimal.TotalMinutes:F0} minutes");
                }
                
                // Economic event tips
                if (HasUpcomingHighImpactEvent(marketType, 60))
                {
                    tips.Add("📰 High-impact economic event within 1 hour - consider position reduction");
                }
                
                // Machine learning insights
                if (regime.MomentumScore > 0.8)
                {
                    tips.Add("🚀 Strong momentum detected - consider momentum strategies");
                }
                
                if (regime.RiskAdjustedScore < 0.5)
                {
                    tips.Add("⚠️ Poor risk-adjusted opportunity - consider waiting for better setup");
                }
                
                // Commission efficiency tips
                var commissionRatio = CalculateCurrentCommissionRatio();
                if (commissionRatio > 0.15)
                {
                    tips.Add($"💸 Daily commission ratio high ({commissionRatio:P1}) - focus on higher-quality setups only");
                }
                
                return tips;
            }
            catch (Exception ex)
            {
                LogMessage($"Market tips generation failed for {marketType}: {ex.Message}", LogLevel.Error);
                return new List<string> { "⚠️ Unable to generate market tips due to system error" };
            }
        }
        
        /// <summary>
        /// Get optimal sessions for today with commission considerations
        /// </summary>
        public static List<OptimalSessionInfo> GetOptimalSessionsForToday(string marketType)
        {
            try
            {
                RecordOperation("GetOptimalSessionsForToday");
                
                var sessions = new List<OptimalSessionInfo>();
                var characteristics = GetMarketCharacteristics(marketType);
                var today = DateTime.Today;
                
                if (!marketSessions.TryGetValue(marketType, out var marketSessionArray))
                    return sessions;
                
                foreach (var session in marketSessionArray.Where(s => s.IsOptimal))
                {
                    var sessionStart = today.AddHours(session.Start);
                    var sessionEnd = today.AddHours(session.End);
                    
                    // Handle sessions that cross midnight
                    if (session.End <= session.Start)
                    {
                        sessionEnd = sessionEnd.AddDays(1);
                    }
                    
                    var sessionInfo = new OptimalSessionInfo
                    {
                        SessionName = session.Name,
                        StartTime = sessionStart,
                        EndTime = sessionEnd,
                        CommissionEfficiency = session.CommissionEfficiency,
                        VolumeMultiplier = session.VolumeMultiplier,
                        IsCurrentlyActive = DateTime.Now >= sessionStart && DateTime.Now <= sessionEnd,
                        ExpectedVolatility = CalculateExpectedSessionVolatility(marketType, session),
                        RecommendedPositionSizeMultiplier = session.CommissionEfficiency * session.VolumeMultiplier
                    };
                    
                    // Apply seasonality adjustments
                    var dayOfWeek = today.DayOfWeek.ToString();
                    if (characteristics.SeasonalityFactors.TryGetValue(dayOfWeek, out var seasonalityFactor))
                    {
                        sessionInfo.SeasonalityAdjustment = seasonalityFactor;
                        sessionInfo.CommissionEfficiency *= seasonalityFactor;
                    }
                    
                    sessions.Add(sessionInfo);
                }
                
                // Sort by commission efficiency
                return sessions.OrderByDescending(s => s.CommissionEfficiency).ToList();
            }
            catch (Exception ex)
            {
                LogMessage($"Optimal sessions calculation failed for {marketType}: {ex.Message}", LogLevel.Error);
                return new List<OptimalSessionInfo>();
            }
        }
        
        /// <summary>
        /// Advanced correlation analysis between markets
        /// </summary>
        public static MarketCorrelationAnalysis AnalyzeMarketCorrelations(
            Dictionary<string, double[]> marketPrices, 
            int lookbackPeriod = 20)
        {
            try
            {
                RecordOperation("AnalyzeMarketCorrelations");
                
                var analysis = new MarketCorrelationAnalysis
                {
                    Timestamp = DateTime.Now,
                    LookbackPeriod = lookbackPeriod,
                    CorrelationMatrix = new Dictionary<string, Dictionary<string, double>>()
                };
                
                var markets = marketPrices.Keys.ToList();
                
                // Calculate correlation matrix
                foreach (var market1 in markets)
                {
                    analysis.CorrelationMatrix[market1] = new Dictionary<string, double>();
                    
                    foreach (var market2 in markets)
                    {
                        if (market1 == market2)
                        {
                            analysis.CorrelationMatrix[market1][market2] = 1.0;
                            continue;
                        }
                        
                        var correlation = CalculateCorrelation(
                            marketPrices[market1].Take(lookbackPeriod).ToArray(),
                            marketPrices[market2].Take(lookbackPeriod).ToArray());
                        
                        analysis.CorrelationMatrix[market1][market2] = correlation;
                    }
                }
                
                // Identify significant correlations
                analysis.SignificantCorrelations = new List<CorrelationPair>();
                foreach (var market1 in markets)
                {
                    foreach (var market2 in markets)
                    {
                        if (market1.CompareTo(market2) >= 0) continue; // Avoid duplicates
                        
                        var correlation = analysis.CorrelationMatrix[market1][market2];
                        if (Math.Abs(correlation) > 0.6) // Significant correlation threshold
                        {
                            analysis.SignificantCorrelations.Add(new CorrelationPair
                            {
                                Market1 = market1,
                                Market2 = market2,
                                Correlation = correlation,
                                Strength = Math.Abs(correlation) > 0.8 ? "Strong" : "Moderate",
                                Type = correlation > 0 ? "Positive" : "Negative"
                            });
                        }
                    }
                }
                
                // Calculate diversification score
                analysis.DiversificationScore = CalculateDiversificationScore(analysis.CorrelationMatrix);
                
                return analysis;
            }
            catch (Exception ex)
            {
                LogMessage($"Market correlation analysis failed: {ex.Message}", LogLevel.Error);
                return new MarketCorrelationAnalysis { Timestamp = DateTime.Now };
            }
        }
        
        #endregion

        #region Advanced Analytics Methods
        
        private static double CalculateVolatilityPercentile(double currentVolatility, MarketCharacteristics characteristics, double[] priceHistory)
        {
            try
            {
                if (priceHistory == null || priceHistory.Length < 20)
                {
                    // Fallback to simple percentile calculation
                    var normalizedVol = currentVolatility / characteristics.TypicalDailyRange;
                    return Math.Min(1.0, Math.Max(0.0, normalizedVol));
                }
                
                // Calculate historical volatility distribution
                var returns = new List<double>();
                for (int i = 1; i < Math.Min(priceHistory.Length, 100); i++)
                {
                    if (priceHistory[i - 1] != 0)
                    {
                        var returnValue = Math.Abs((priceHistory[i] - priceHistory[i - 1]) / priceHistory[i - 1]);
                        returns.Add(returnValue);
                    }
                }
                
                if (!returns.Any()) return 0.5;
                
                returns.Sort();
                var currentReturn = currentVolatility / (priceHistory[0] != 0 ? priceHistory[0] : 1);
                
                // Find percentile
                var lowerCount = returns.Count(r => r < currentReturn);
                return (double)lowerCount / returns.Count;
            }
            catch
            {
                return 0.5; // Default to median
            }
        }
        
        private static double CalculateTrendPersistence(double[] priceHistory, MarketCharacteristics characteristics)
        {
            try
            {
                if (priceHistory == null || priceHistory.Length < 10)
                    return characteristics.TrendPersistence;
                
                var trendChanges = 0;
                var totalPeriods = Math.Min(priceHistory.Length - 1, 20);
                
                for (int i = 1; i < totalPeriods; i++)
                {
                    var currentTrend = priceHistory[i] > priceHistory[i - 1];
                    var previousTrend = i > 1 ? priceHistory[i - 1] > priceHistory[i - 2] : currentTrend;
                    
                    if (currentTrend != previousTrend)
                        trendChanges++;
                }
                
                var persistence = 1.0 - ((double)trendChanges / totalPeriods);
                return Math.Max(0.1, Math.Min(1.0, persistence));
            }
            catch
            {
                return characteristics.TrendPersistence;
            }
        }
        
        private static double CalculateMomentumScore(double[] priceHistory)
        {
            try
            {
                if (priceHistory == null || priceHistory.Length < 5) return 0.5;
                
                var shortMomentum = CalculateMomentum(priceHistory, 3);
                var mediumMomentum = CalculateMomentum(priceHistory, 7);
                var longMomentum = CalculateMomentum(priceHistory, 14);
                
                // Weight recent momentum more heavily
                var weightedMomentum = (shortMomentum * 0.5) + (mediumMomentum * 0.3) + (longMomentum * 0.2);
                
                // Normalize to 0-1 scale
                return Math.Max(0, Math.Min(1, 0.5 + (weightedMomentum / 0.1)));
            }
            catch
            {
                return 0.5;
            }
        }
        
        private static double CalculateMomentum(double[] prices, int period)
        {
            if (prices.Length < period + 1) return 0;
            
            var currentPrice = prices[0];
            var pastPrice = prices[Math.Min(period, prices.Length - 1)];
            
            return pastPrice != 0 ? (currentPrice - pastPrice) / pastPrice : 0;
        }
        
        private static double CalculateMeanReversionProbability(double[] priceHistory, MarketCharacteristics characteristics)
        {
            try
            {
                if (priceHistory == null || priceHistory.Length < 20) 
                    return characteristics.MeanReversionTendency;
                
                // Calculate how often price reverts to mean after extreme moves
                var sma = CalculateSMA(priceHistory, 14);
                var extremeThreshold = CalculateStandardDeviation(priceHistory, 14) * 1.5;
                
                var extremeMoves = 0;
                var reversions = 0;
                
                for (int i = 2; i < Math.Min(priceHistory.Length - 2, 50); i++)
                {
                    var deviation = Math.Abs(priceHistory[i] - sma);
                    if (deviation > extremeThreshold)
                    {
                        extremeMoves++;
                        
                        // Check if price reverted within next 3 periods
                        var reverted = false;
                        for (int j = 1; j <= 3 && i - j >= 0; j++)
                        {
                            if (Math.Abs(priceHistory[i - j] - sma) < deviation * 0.7)
                            {
                                reverted = true;
                                break;
                            }
                        }
                        
                        if (reverted) reversions++;
                    }
                }
                
                return extremeMoves > 0 ? (double)reversions / extremeMoves : characteristics.MeanReversionTendency;
            }
            catch
            {
                return characteristics.MeanReversionTendency;
            }
        }
        
        private static double CalculateTrendContinuationProbability(double[] priceHistory, MarketRegimeAnalysis regime)
        {
            try
            {
                if (priceHistory == null || priceHistory.Length < 10) return 0.5;
                
                // High trend score suggests continuation
                var baseProbability = regime.TrendScore;
                
                // Adjust based on volume
                var volumeAdjustment = regime.VolumeScore > 0.7 ? 0.1 : -0.1;
                
                // Adjust based on volatility (extreme volatility reduces continuation probability)
                var volatilityAdjustment = regime.VolatilityScore > 0.8 ? -0.2 : 0;
                
                var probability = baseProbability + volumeAdjustment + volatilityAdjustment;
                return Math.Max(0.1, Math.Min(0.9, probability));
            }
            catch
            {
                return 0.5;
            }
        }
        
        private static double CalculateCommissionViability(MarketRegimeAnalysis regime, MarketCharacteristics characteristics, MarketSession session)
        {
            try
            {
                var baseViability = session.CommissionEfficiency;
                
                // Adjust for volatility (higher volatility = better profit potential)
                var volatilityBonus = regime.VolatilityScore > 0.6 ? 0.2 : 0;
                
                // Adjust for volume (higher volume = better execution)
                var volumeBonus = regime.VolumeScore > 0.7 ? 0.1 : -0.1;
                
                // Adjust for trend strength (stronger trends = better profit potential)
                var trendBonus = regime.TrendScore > 0.7 ? 0.15 : 0;
                
                var viability = baseViability + volatilityBonus + volumeBonus + trendBonus;
                return Math.Max(0.1, Math.Min(1.0, viability));
            }
            catch
            {
                return 0.5;
            }
        }
        
        private static double CalculateRiskAdjustedScore(MarketRegimeAnalysis regime, MarketCharacteristics characteristics)
        {
            try
            {
                // Combine opportunity (trend + volume) with risk adjustment (volatility)
                var opportunity = (regime.TrendScore * 0.6) + (regime.VolumeScore * 0.4);
                var riskAdjustment = regime.VolatilityScore > 0.8 ? 0.5 : 1.0; // Penalize extreme volatility
                
                return opportunity * riskAdjustment;
            }
            catch
            {
                return 0.5;
            }
        }
        
        private static void ApplySeasonalityAdjustments(MarketRegimeAnalysis analysis, string marketType)
        {
            try
            {
                var characteristics = GetMarketCharacteristics(marketType);
                var dayOfWeek = DateTime.Now.DayOfWeek.ToString();
                
                if (characteristics.SeasonalityFactors.TryGetValue(dayOfWeek, out var seasonalityFactor))
                {
                    analysis.SeasonalityFactor = seasonalityFactor;
                    
                    // Apply seasonality to scores
                    analysis.TrendScore *= seasonalityFactor;
                    analysis.VolumeScore *= seasonalityFactor;
                    analysis.CommissionViability *= seasonalityFactor;
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Seasonality adjustment failed: {ex.Message}", LogLevel.Warning);
            }
        }
        
        #endregion

        #region Utility and Helper Methods
        
        private static bool IsInSession(int hour, MarketSession session)
        {
            if (session.Start <= session.End)
                return hour >= session.Start && hour < session.End;
            else // Crosses midnight
                return hour >= session.Start || hour < session.End;
        }
        
        private static MarketCharacteristics GetMarketCharacteristics(string marketType)
        {
            if (marketCharacteristics.TryGetValue(marketType, out var characteristics))
                return characteristics;
            
            if (marketCharacteristics.TryGetValue("Gold", out var fallback))
                return fallback;
            
            return new MarketCharacteristics { TypicalDailyRange = 25.0 };
        }
        
        private static string DetermineOverallRegime(MarketRegimeAnalysis analysis, MarketCharacteristics characteristics)
        {
            try
            {
                // Extreme volatility overrides everything
                if (analysis.VolatilityScore > 0.95)
                    return "EXPLOSIVE";
                
                // Very high volatility
                if (analysis.VolatilityScore > 0.8)
                    return "VOLATILE";
                
                // Strong trend with good volume
                if (analysis.TrendScore > 0.8 && analysis.VolumeScore > 0.6)
                {
                    return analysis.TrendRegime.Contains("BULL") ? "TRENDING BULL" : "TRENDING BEAR";
                }
                
                // Medium trend
                if (analysis.TrendScore > 0.6)
                {
                    return analysis.TrendRegime.Contains("BULL") ? "BULL TREND" : "BEAR TREND";
                }
                
                // Low volatility ranging
                if (analysis.VolatilityScore < 0.3 && analysis.TrendScore < 0.4)
                    return "RANGING";
                
                return "NEUTRAL";
            }
            catch
            {
                return "NEUTRAL";
            }
        }
        
        private static string GetEnhancedTradingRecommendation(MarketRegimeAnalysis analysis, string marketType, MarketSession session)
        {
            try
            {
                var recommendations = new List<string>();
                
                // Commission-based recommendations
                if (analysis.CommissionViability < 0.5)
                    recommendations.Add("AVOID - Poor commission efficiency");
                else if (analysis.CommissionViability > 0.8)
                    recommendations.Add("FAVORABLE - Good commission efficiency");
                
                // Regime-based recommendations
                switch (analysis.OverallRegime)
                {
                    case "EXPLOSIVE":
                        recommendations.Add("EXTREME CAUTION - Explosive conditions");
                        break;
                    case "VOLATILE":
                        recommendations.Add("REDUCE SIZE - High volatility");
                        break;
                    case "TRENDING BULL":
                    case "TRENDING BEAR":
                        recommendations.Add("TREND FOLLOWING - Strong directional bias");
                        break;
                    case "RANGING":
                        recommendations.Add("MEAN REVERSION - Range-bound market");
                        break;
                    default:
                        recommendations.Add("STANDARD APPROACH - Normal conditions");
                        break;
                }
                
                // Session-based recommendations
                if (!session.IsOptimal)
                    recommendations.Add("SUB-OPTIMAL SESSION - Consider waiting");
                
                // Volume-based recommendations
                if (analysis.VolumeRegime == "VERY LOW")
                    recommendations.Add("LOW VOLUME - Expect choppy action");
                
                return string.Join(" | ", recommendations);
            }
            catch
            {
                return "STANDARD APPROACH - Normal conditions";
            }
        }
        
        private static TimeSpan GetTimeUntilOptimalSession(string marketType)
        {
            try
            {
                if (!marketSessions.TryGetValue(marketType, out var sessions))
                    return TimeSpan.Zero;
                
                var now = DateTime.Now;
                var optimalSessions = sessions.Where(s => s.IsOptimal).ToList();
                
                foreach (var session in optimalSessions)
                {
                    var sessionStart = now.Date.AddHours(session.Start);
                    
                    // Handle sessions that cross midnight
                    if (session.End <= session.Start && now.Hour < session.Start)
                    {
                        sessionStart = sessionStart.AddDays(-1);
                    }
                    
                    if (sessionStart > now)
                    {
                        return sessionStart - now;
                    }
                }
                
                // No optimal session today, check tomorrow
                var tomorrowStart = now.Date.AddDays(1).AddHours(optimalSessions[0].Start);
                return tomorrowStart - now;
            }
            catch
            {
                return TimeSpan.Zero;
            }
        }
        
        private static double CalculateExpectedSessionVolatility(string marketType, MarketSession session)
        {
            try
            {
                var characteristics = GetMarketCharacteristics(marketType);
                var baseVolatility = characteristics.TypicalDailyRange;
                
                // Adjust for session characteristics
                var sessionVolatility = baseVolatility * session.VolumeMultiplier;
                
                // Apply time-based adjustments
                switch (session.Name)
                {
                    case "US Morning":
                    case "RTH Morning":
                        sessionVolatility *= 1.3; // Morning volatility boost
                        break;
                    case "Asian":
                    case "Pre-Market":
                        sessionVolatility *= 0.7; // Lower volatility in thin sessions
                        break;
                }
                
                return sessionVolatility;
            }
            catch
            {
                return 25.0; // Default volatility
            }
        }
        
        private static double CalculateCurrentCommissionRatio()
        {
            try
            {
                var tradingState = FKS_Core.CurrentTradingState;
                if (tradingState == null) return 0;
                
                var grossPnL = tradingState.DailyPnL + tradingState.DailyCommissions;
                return grossPnL > 0 ? tradingState.DailyCommissions / grossPnL : 0;
            }
            catch
            {
                return 0;
            }
        }
        
        private static double CalculateCorrelation(double[] series1, double[] series2)
        {
            try
            {
                var n = Math.Min(series1.Length, series2.Length);
                if (n < 2) return 0;
                
                var sum1 = series1.Take(n).Sum();
                var sum2 = series2.Take(n).Sum();
                var sum1Sq = series1.Take(n).Sum(x => x * x);
                var sum2Sq = series2.Take(n).Sum(x => x * x);
                var sum12 = series1.Take(n).Zip(series2.Take(n), (x, y) => x * y).Sum();
                
                var numerator = n * sum12 - sum1 * sum2;
                var denominator = Math.Sqrt((n * sum1Sq - sum1 * sum1) * (n * sum2Sq - sum2 * sum2));
                
                return denominator != 0 ? numerator / denominator : 0;
            }
            catch
            {
                return 0;
            }
        }
        
        private static double CalculateDiversificationScore(Dictionary<string, Dictionary<string, double>> correlationMatrix)
        {
            try
            {
                var correlations = new List<double>();
                
                foreach (var market1 in correlationMatrix.Keys)
                {
                    foreach (var market2 in correlationMatrix[market1].Keys)
                    {
                        if (market1.CompareTo(market2) < 0) // Avoid duplicates
                        {
                            correlations.Add(Math.Abs(correlationMatrix[market1][market2]));
                        }
                    }
                }
                
                if (!correlations.Any()) return 1.0;
                
                var avgCorrelation = correlations.Average();
                return 1.0 - avgCorrelation; // Higher diversification = lower average correlation
            }
            catch
            {
                return 0.5;
            }
        }
        
        private static double CalculateSMA(double[] prices, int period)
        {
            var validPeriod = Math.Min(period, prices.Length);
            return prices.Take(validPeriod).Average();
        }
        
        private static double CalculateStandardDeviation(double[] prices, int period)
        {
            try
            {
                var validPeriod = Math.Min(period, prices.Length);
                var values = prices.Take(validPeriod).ToArray();
                var mean = values.Average();
                var variance = values.Select(x => Math.Pow(x - mean, 2)).Average();
                return Math.Sqrt(variance);
            }
            catch
            {
                return 0;
            }
        }
        
        private static string GetMarketCurrency(string marketType)
        {
            switch (marketType)
            {
                case "Gold":
                case "ES":
                case "NQ":
                case "CL":
                    return "USD";
                case "BTC":
                    return "CRYPTO";
                default:
                    return "USD";
            }
        }
        
        #endregion

        #region Fallback Methods
        
        private static MarketRegimeAnalysis CreateFallbackRegimeAnalysis(string marketType)
        {
            return new MarketRegimeAnalysis
            {
                OverallRegime = "NEUTRAL",
                TrendRegime = "RANGING", 
                VolatilityRegime = "NORMAL",
                VolumeRegime = "NORMAL",
                TrendScore = 0.5,
                VolatilityScore = 0.5,
                VolumeScore = 0.5,
                TradingRecommendation = "CAUTION - System error, use manual analysis",
                CommissionViability = 0.5,
                RiskAdjustedScore = 0.5
            };
        }
        
        private static DynamicParameters CreateFallbackDynamicParameters()
        {
            return new DynamicParameters
            {
                StopLossMultiplier = 2.0,
                PositionSizeAdjustment = 0.5, // Conservative fallback
                SignalQualityThreshold = 0.75, // Higher threshold for safety
                MeanReversionBias = 0.5,
                TrendFollowingBias = 0.5
            };
        }
        
        #endregion

        #region Timer-Based Updates
        
        private static void UpdateMarketAnalytics(object state)
        {
            if (!isInitialized) return;
            
            try
            {
                var startTime = DateTime.Now;
                
                // Update analytics for each market
                Parallel.ForEach(marketAnalytics.Keys, marketType =>
                {
                    try
                    {
                        var analytics = marketAnalytics[marketType];
                        analytics.LastUpdate = DateTime.Now;
                        
                        // Update commission metrics
                        analytics.CommissionMetrics.UpdateEfficiency();
                        
                        // Update session analysis
                        var currentSession = GetCurrentSession(marketType, DateTime.Now);
                        analytics.SessionAnalysis.CurrentSession = currentSession.Name;
                        analytics.SessionAnalysis.IsOptimalSession = currentSession.IsOptimal;
                    }
                    catch (Exception ex)
                    {
                        LogMessage($"Analytics update failed for {marketType}: {ex.Message}", LogLevel.Warning);
                    }
                });
                
                // Update market data snapshot
                var snapshot = new MarketDataSnapshot
                {
                    Timestamp = DateTime.Now,
                    ProcessingTime = DateTime.Now - startTime
                };
                
                marketHistory.Enqueue(snapshot);
                
                // Maintain history size
                while (marketHistory.Count > MaxHistorySize)
                {
                    marketHistory.TryDequeue(out _);
                }
                
                RecordPerformanceMetric("AnalyticsUpdateTime", (DateTime.Now - startTime).TotalMilliseconds);
            }
            catch (Exception ex)
            {
                LogMessage($"Market analytics update failed: {ex.Message}", LogLevel.Error);
            }
        }
        
        private static void UpdateEconomicCalendar(object state)
        {
            try
            {
                if ((DateTime.Now - lastEventUpdate).TotalHours < 1)
                    return; // Only update hourly
                
                // Clear old events
                while (upcomingEvents.TryDequeue(out _)) { }
                marketSpecificEvents.Clear();
                
                var now = DateTime.Now;
                
                // Add simulated events based on day/time patterns
                AddScheduledEvents(now);
                
                lastEventUpdate = DateTime.Now;
                LogMessage("Economic calendar updated", LogLevel.Debug);
            }
            catch (Exception ex)
            {
                LogMessage($"Economic calendar update failed: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void AddScheduledEvents(DateTime now)
        {
            try
            {
                // Wednesday EIA (affects CL primarily, USD markets secondarily)
                if (now.DayOfWeek == DayOfWeek.Wednesday)
                {
                    var eiaTime = now.Date.AddHours(10).AddMinutes(30);
                    if (eiaTime > now)
                    {
                        var eiaEvent = new EconomicEvent
                        {
                            Time = eiaTime,
                            Name = "EIA Crude Oil Inventories",
                            Currency = "USD",
                            Impact = MarketImpactLevel.VeryHigh,
                            AffectedMarkets = new[] { "CL", "RB", "HO" },
                            IsGlobal = false
                        };
                        
                        upcomingEvents.Enqueue(eiaEvent);
                        
                        // Add to market-specific events
                        foreach (var market in eiaEvent.AffectedMarkets)
                        {
                            if (!marketSpecificEvents.ContainsKey(market))
                                marketSpecificEvents[market] = new List<EconomicEvent>();
                            marketSpecificEvents[market].Add(eiaEvent);
                        }
                    }
                }
                
                // First Friday NFP (affects all USD markets)
                if (now.DayOfWeek == DayOfWeek.Friday && now.Day <= 7)
                {
                    var nfpTime = now.Date.AddHours(8).AddMinutes(30);
                    if (nfpTime > now)
                    {
                        var nfpEvent = new EconomicEvent
                        {
                            Time = nfpTime,
                            Name = "Non-Farm Payrolls",
                            Currency = "USD",
                            Impact = MarketImpactLevel.VeryHigh,
                            AffectedMarkets = new[] { "Gold", "ES", "NQ", "CL" },
                            IsGlobal = true
                        };
                        
                        upcomingEvents.Enqueue(nfpEvent);
                        
                        foreach (var market in nfpEvent.AffectedMarkets)
                        {
                            if (!marketSpecificEvents.ContainsKey(market))
                                marketSpecificEvents[market] = new List<EconomicEvent>();
                            marketSpecificEvents[market].Add(nfpEvent);
                        }
                    }
                }
                
                // FOMC meetings (8 times per year, affects all markets)
                var fomc = GetNextFOMCDate(now);
                if (fomc.HasValue && fomc.Value > now && fomc.Value < now.AddDays(7))
                {
                    var fomcEvent = new EconomicEvent
                    {
                        Time = fomc.Value,
                        Name = "FOMC Rate Decision",
                        Currency = "USD",
                        Impact = MarketImpactLevel.VeryHigh,
                        AffectedMarkets = new[] { "Gold", "ES", "NQ", "CL", "BTC" },
                        IsGlobal = true
                    };
                    
                    upcomingEvents.Enqueue(fomcEvent);
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Event scheduling failed: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static DateTime? GetNextFOMCDate(DateTime now)
        {
            // Simplified FOMC schedule (typically 8 meetings per year)
            var fomcMonths = new[] { 1, 3, 5, 6, 7, 9, 11, 12 };
            
            foreach (var month in fomcMonths)
            {
                if (month >= now.Month)
                {
                    // Usually second or third Tuesday/Wednesday of the month
                    var targetDate = new DateTime(now.Year, month, 15).AddHours(14); // 2 PM ET
                    if (targetDate > now)
                        return targetDate;
                }
            }
            
            // Next year
            return new DateTime(now.Year + 1, fomcMonths[0], 15).AddHours(14);
        }
        
        private static void PerformCleanup(object state)
        {
            try
            {
                // Clean up old cache entries
                var cutoffTime = DateTime.Now - TimeSpan.FromTicks(RegimeCacheTimeout.Ticks * 3);
                var keysToRemove = lastRegimeUpdate
                    .Where(kvp => kvp.Value < cutoffTime)
                    .Select(kvp => kvp.Key)
                    .ToList();
                
                foreach (var key in keysToRemove)
                {
                    regimeCache.TryRemove(key, out _);
                    lastRegimeUpdate.TryRemove(key, out _);
                }
                
                // Clean up old market history
                while (marketHistory.Count > MaxHistorySize)
                {
                    marketHistory.TryDequeue(out _);
                }
                
                // Clean up old events
                var eventCutoff = DateTime.Now.AddHours(-2);
                var currentEvents = new List<EconomicEvent>();
                
                while (upcomingEvents.TryDequeue(out var evt))
                {
                    if (evt.Time > eventCutoff)
                        currentEvents.Add(evt);
                }
                
                foreach (var evt in currentEvents)
                {
                    upcomingEvents.Enqueue(evt);
                }
                
                LogMessage($"Cleanup completed - removed {keysToRemove.Count} cache entries", LogLevel.Debug);
            }
            catch (Exception ex)
            {
                LogMessage($"Cleanup failed: {ex.Message}", LogLevel.Warning);
            }
        }
        
        #endregion

        #region Performance and Analytics Updates
        
        private static void UpdateMarketAnalyticsForRegime(string marketType, MarketRegimeAnalysis regime)
        {
            try
            {
                if (marketAnalytics.TryGetValue(marketType, out var analytics))
                {
                    analytics.VolatilityModel.Update(regime.VolatilityScore);
                    analytics.TrendModel.Update(regime.TrendScore);
                    analytics.CommissionMetrics.UpdateViability(regime.CommissionViability);
                    analytics.LastUpdate = DateTime.Now;
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Analytics update failed for {marketType}: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void RecordOperation(string operationName)
        {
            try
            {
                operationCounters.AddOrUpdate(operationName, 1, (key, value) => value + 1);
                
                // Record with infrastructure
                FKS_Infrastructure.RecordComponentActivity("FKS_Market", new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = operationName,
                    ExecutionTime = TimeSpan.FromMilliseconds(1)
                });
            }
            catch (Exception ex)
            {
                LogMessage($"Operation recording failed for {operationName}: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void RecordPerformanceMetric(string metricName, double value)
        {
            try
            {
                performanceMetrics[metricName] = value;
            }
            catch (Exception ex)
            {
                LogMessage($"Performance metric recording failed for {metricName}: {ex.Message}", LogLevel.Warning);
            }
        }
        
        #endregion

        #region Logging
        
        private static void LogMessage(string message, LogLevel level)
        {
            try
            {
                var logEntry = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] [{level}] FKS_Market: {message}";
                
                switch (level)
                {
                    case LogLevel.Error:
                        NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab1);
                        break;
                    case LogLevel.Warning:
                        NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab1);
                        break;
                    case LogLevel.Information:
                        NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab2);
                        break;
                    case LogLevel.Debug:
                        #if DEBUG
                        NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab2);
                        #endif
                        break;
                }
            }
            catch
            {
                // Fail silently if logging fails
            }
        }
        
        #endregion

        #region Cleanup and Disposal
        
        public static void Shutdown()
        {
            try
            {
                // Dispose timers
                analyticsTimer?.Dispose();
                cleanupTimer?.Dispose();
                eventUpdateTimer?.Dispose();
                
                // Clear collections
                regimeCache.Clear();
                lastRegimeUpdate.Clear();
                marketAnalytics.Clear();
                marketSpecificEvents.Clear();
                operationCounters.Clear();
                performanceMetrics.Clear();
                
                while (marketHistory.TryDequeue(out _)) { }
                while (upcomingEvents.TryDequeue(out _)) { }
                
                // Unregister from infrastructure
                try
                {
                    FKS_Infrastructure.UnregisterComponent("FKS_Market");
                }
                catch (Exception ex)
                {
                    LogMessage($"Infrastructure unregistration failed: {ex.Message}", LogLevel.Warning);
                }
                
                // Dispose locks
                rwLock?.Dispose();
                
                isInitialized = false;
                LogMessage("FKS Market shutdown completed", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"Shutdown error: {ex.Message}", LogLevel.Error);
            }
        }
        
        #endregion

        #region Enhanced Helper Classes and Data Structures
        
        public class MarketSession
        {
            public string Name { get; set; }
            public int Start { get; set; } // Hour in 24h format
            public int End { get; set; }
            public bool IsOptimal { get; set; }
            
            // Enhanced properties for commission optimization
            public double VolumeMultiplier { get; set; } = 1.0;
            public double CommissionEfficiency { get; set; } = 1.0;
            public double VolatilityExpectation { get; set; } = 1.0;
            public List<string> OptimalSetups { get; set; } = new List<string>();
        }
        
        public class MarketCharacteristics
        {
            public double TypicalDailyRange { get; set; }
            public double HighVolatilityThreshold { get; set; }
            public double LowVolatilityThreshold { get; set; }
            public double TrendStrengthMultiplier { get; set; }
            public MarketImpactLevel NewsImpactLevel { get; set; }
            public string[] CorrelatedMarkets { get; set; }
            
            // Enhanced properties for commission optimization
            public TimeSpan OptimalCommissionWindow { get; set; }
            public double MinimumProfitMultiple { get; set; } = 3.0;
            public double VolatilityCommissionAdjustment { get; set; } = 1.0;
            public Dictionary<string, double> SessionCommissionMultipliers { get; set; } = new Dictionary<string, double>();
            
            // Advanced analytics properties
            public double MeanReversionTendency { get; set; } = 0.5;
            public double TrendPersistence { get; set; } = 0.7;
            public Dictionary<string, double> SeasonalityFactors { get; set; } = new Dictionary<string, double>();
        }
        
        public class MarketRegimeAnalysis
        {
            public string OverallRegime { get; set; }
            public string TrendRegime { get; set; }
            public string VolatilityRegime { get; set; }
            public string VolumeRegime { get; set; }
            public double TrendScore { get; set; }
            public double VolatilityScore { get; set; }
            public double VolumeScore { get; set; }
            public string TradingRecommendation { get; set; }
            
            // Enhanced properties
            public double CommissionViability { get; set; }
            public List<OptimalSessionInfo> OptimalSessionsToday { get; set; } = new List<OptimalSessionInfo>();
            public double RiskAdjustedScore { get; set; }
            public double MomentumScore { get; set; }
            public double MeanReversionProbability { get; set; }
            public double TrendContinuationProbability { get; set; }
            public double SeasonalityFactor { get; set; } = 1.0;
            public double TrendPersistence { get; set; }
            public DateTime AnalysisTimestamp { get; set; } = DateTime.Now;
        }
        
        public class DynamicParameters
        {
            public double StopLossMultiplier { get; set; }
            public double PositionSizeAdjustment { get; set; }
            public double SignalQualityThreshold { get; set; }
            
            // Enhanced parameters for machine learning
            public double MeanReversionBias { get; set; } = 0.5;
            public double TrendFollowingBias { get; set; } = 0.5;
            public double VolatilityAdjustment { get; set; } = 1.0;
            public double SessionAdjustment { get; set; } = 1.0;
            public double CommissionAdjustment { get; set; } = 1.0;
        }
        
        public class EconomicEvent
        {
            public DateTime Time { get; set; }
            public string Name { get; set; }
            public string Currency { get; set; }
            public MarketImpactLevel Impact { get; set; }
            public string[] AffectedMarkets { get; set; }
            public bool IsGlobal { get; set; }
            
            // Enhanced properties
            public TimeSpan AvoidancePeriod { get; set; } = TimeSpan.FromMinutes(30);
            public double VolatilityMultiplier { get; set; } = 1.5;
            public string EventCategory { get; set; }
        }
        
        public class OptimalSessionInfo
        {
            public string SessionName { get; set; }
            public DateTime StartTime { get; set; }
            public DateTime EndTime { get; set; }
            public double CommissionEfficiency { get; set; }
            public double VolumeMultiplier { get; set; }
            public bool IsCurrentlyActive { get; set; }
            public double ExpectedVolatility { get; set; }
            public double RecommendedPositionSizeMultiplier { get; set; }
            public double SeasonalityAdjustment { get; set; } = 1.0;
        }
        
        public class MarketCorrelationAnalysis
        {
            public DateTime Timestamp { get; set; }
            public int LookbackPeriod { get; set; }
            public Dictionary<string, Dictionary<string, double>> CorrelationMatrix { get; set; }
            public List<CorrelationPair> SignificantCorrelations { get; set; }
            public double DiversificationScore { get; set; }
        }
        
        public class CorrelationPair
        {
            public string Market1 { get; set; }
            public string Market2 { get; set; }
            public double Correlation { get; set; }
            public string Strength { get; set; } // "Strong", "Moderate", "Weak"
            public string Type { get; set; } // "Positive", "Negative"
        }
        
        public class MarketAnalytics
        {
            public string MarketType { get; set; }
            public DateTime LastUpdate { get; set; }
            public VolatilityModel VolatilityModel { get; set; }
            public TrendModel TrendModel { get; set; }
            public SessionAnalysis SessionAnalysis { get; set; }
            public CommissionMetrics CommissionMetrics { get; set; }
        }
        
        public class VolatilityModel
        {
            public double CurrentLevel { get; private set; }
            public double Average { get; private set; }
            public double StandardDeviation { get; private set; }
            public List<double> History { get; private set; } = new List<double>();
            
            public void Update(double volatility)
            {
                History.Add(volatility);
                if (History.Count > 100) History.RemoveAt(0);
                
                CurrentLevel = volatility;
                Average = History.Average();
                StandardDeviation = CalculateStandardDeviation(History);
            }
            
            private double CalculateStandardDeviation(List<double> values)
            {
                if (values.Count < 2) return 0;
                var mean = values.Average();
                var variance = values.Select(x => Math.Pow(x - mean, 2)).Average();
                return Math.Sqrt(variance);
            }
        }
        
        public class TrendModel
        {
            public double CurrentStrength { get; private set; }
            public double Persistence { get; private set; }
            public List<double> History { get; private set; } = new List<double>();
            
            public void Update(double trendStrength)
            {
                History.Add(trendStrength);
                if (History.Count > 50) History.RemoveAt(0);
                
                CurrentStrength = trendStrength;
                Persistence = CalculatePersistence();
            }
            
            private double CalculatePersistence()
            {
                if (History.Count < 10) return 0.5;
                
                var changes = 0;
                for (int i = 1; i < History.Count; i++)
                {
                    if (Math.Sign(History[i]) != Math.Sign(History[i - 1]))
                        changes++;
                }
                
                return 1.0 - ((double)changes / (History.Count - 1));
            }
        }
        
        public class SessionAnalysis
        {
            public string CurrentSession { get; set; }
            public bool IsOptimalSession { get; set; }
            public double SessionEfficiency { get; set; }
            public DateTime LastUpdate { get; set; }
        }
        
        public class CommissionMetrics
        {
            public double EfficiencyMultiplier { get; set; } = 1.0;
            public double AverageViability { get; private set; }
            public List<double> ViabilityHistory { get; private set; } = new List<double>();
            
            public void UpdateViability(double viability)
            {
                ViabilityHistory.Add(viability);
                if (ViabilityHistory.Count > 50) ViabilityHistory.RemoveAt(0);
                
                AverageViability = ViabilityHistory.Average();
                UpdateEfficiency();
            }
            
            public void UpdateEfficiency()
            {
                // Adjust efficiency based on recent performance
                if (ViabilityHistory.Any())
                {
                    var recentAvg = ViabilityHistory.Skip(Math.Max(0, ViabilityHistory.Count - 10)).Average();
                    EfficiencyMultiplier = Math.Max(0.5, Math.Min(1.5, recentAvg * 1.2));
                }
            }
        }
        
        public class MarketDataSnapshot
        {
            public DateTime Timestamp { get; set; }
            public TimeSpan ProcessingTime { get; set; }
            public Dictionary<string, double> MarketMetrics { get; set; } = new Dictionary<string, double>();
            public int ActiveComponents { get; set; }
            public double MemoryUsage { get; set; }
            public Dictionary<string, double> PerformanceMetrics { get; set; } = new Dictionary<string, double>();
        }
        
        public class MetricValue
        {
            public double Total { get; set; }
            public double Average { get; set; }
            public double Min { get; set; } = double.MaxValue;
            public double Max { get; set; } = double.MinValue;
            public int Count { get; set; }
            
            public void AddValue(double value)
            {
                Total += value;
                Count++;
                Average = Total / Count;
                Min = Math.Min(Min, value);
                Max = Math.Max(Max, value);
            }
        }
        
        #endregion

        #region Enums and Supporting Types
        
        public enum MarketImpactLevel
        {
            Low = 1,
            Medium = 2,
            High = 3,
            VeryHigh = 4
        }
        
        public enum LogLevel
        {
            Debug = 1,
            Information = 2,
            Warning = 3,
            Error = 4
        }
        
        public enum CircuitBreakerState
        {
            Closed,
            Open,
            HalfOpen
        }
        
        #endregion
    }
}