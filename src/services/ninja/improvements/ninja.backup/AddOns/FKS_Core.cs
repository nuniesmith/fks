// src/AddOns/FKS_Core.cs - Complete Foundation for FKS Trading Systems
// Dependencies: None (pure foundation)

#region Using declarations
using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    #region Core Enums and Types (From FKS_Core.cs)

    /// <summary>Trading signal direction with strength indicators</summary>
    public enum SignalDirection
    {
        Long = 1,
        Short = -1,
        Neutral = 0,
        StrongLong = 2,
        StrongShort = -2
    }

    /// <summary>Market trend direction</summary>
    public enum TrendDirection
    {
        Up = 1,
        Down = -1,
        Sideways = 0,
        None = 0,
        StrongUp = 2,
        StrongDown = -2
    }

    /// <summary>Market regime classification</summary>
    public enum MarketRegime
    {
        Trending = 1,
        Ranging = 2,
        Volatile = 3,
        StrongTrend = 4,
        WeakTrend = 5,
        Unknown = 0
    }

    /// <summary>Setup types for FKS strategy</summary>
    public enum FKSSetupType
    {
        Setup1_EMA_VWAP_Bullish = 1,
        Setup2_EMA_VWAP_Bearish = 2,
        Setup3_VWAP_Rejection = 3,
        Setup4_SupportResistance_AO = 4,
        None = 0
    }

    /// <summary>Session type for time-based analysis</summary>
    public enum SessionType
    {
        PreMarket,
        MarketOpen,
        LondonOpen,
        LondonSession,
        NYOpen,
        NYSession,
        AsianOpen,
        AsianSession,
        AfterHours,
        Weekend,
        Holiday
    }

    /// <summary>Log levels for system logging</summary>
    public enum FKSLogLevel
    {
        Debug = 0,
        Information = 1,
        Warning = 2,
        Error = 3,
        Critical = 4
    }

    /// <summary>Error handling severity levels</summary>
    public enum ErrorSeverity { Low, Medium, High, Critical }

    /// <summary>Recovery action types</summary>
    public enum RecoveryAction { None, ReturnDefault, Retry, ForceGarbageCollection, ValidateAndCorrect }

    /// <summary>Retry policy types</summary>
    public enum RetryPolicy { NoRetry, Immediate, LinearBackoff, ExponentialBackoff }

    /// <summary>Component status types</summary>
    public enum ComponentStatus
    {
        Connected,
        Disconnected,
        Error,
        Warning
    }

    #endregion

    #region Core Infrastructure Classes

    /// <summary>
    /// Component signal structure
    /// </summary>
    public class ComponentSignal
    {
        public string ComponentName { get; set; }
        public SignalDirection Direction { get; set; }
        public double Confidence { get; set; }
        public double QualityScore { get; set; }
        public DateTime Timestamp { get; set; } = DateTime.Now;
        public bool IsActive { get; set; } = true;
        public List<string> Reasons { get; set; } = new List<string>();
        public double EntryPrice { get; set; }
        public double StopLoss { get; set; }
        public double Target { get; set; }

        public bool IsValid() => Direction != SignalDirection.Neutral && Confidence > 0.3;
        public bool IsStale => (DateTime.Now - Timestamp).TotalMinutes > 15;
        public bool IsHighQuality => QualityScore > 0.7 && Confidence > 0.6;
    }

    /// <summary>
    /// Market profile information
    /// </summary>
    public class MarketProfile
    {
        public string Symbol { get; set; }
        public string Name { get; set; }
        public double TickSize { get; set; }
        public double PointValue { get; set; }
        public double MinTick { get; set; }
        public double MarginRequirement { get; set; }
        public List<TimeSpan[]> OptimalTradingHours { get; set; } = new List<TimeSpan[]>();
        public VolatilityCharacteristics VolatilityProfile { get; set; }
        public RiskProfile RiskParameters { get; set; }
        public Dictionary<string, double> TechnicalSettings { get; set; } = new Dictionary<string, double>();
        public bool IsActive { get; set; } = true;
    }

    /// <summary>
    /// Volatility characteristics
    /// </summary>
    public class VolatilityCharacteristics
    {
        public double Normal { get; set; }
        public double High { get; set; }
        public double Extreme { get; set; }
        public double Low { get; set; }
    }

    /// <summary>
    /// Risk profile settings
    /// </summary>
    public class RiskProfile
    {
        public double MaxDailyRisk { get; set; }
        public double StopLossATRMultiplier { get; set; }
        public double TakeProfitATRMultiplier { get; set; }
        public int MaxPositionSize { get; set; }
        public int OptimalPositionSize { get; set; }
        public double MaxDrawdownPercent { get; set; }
        public int MaxConsecutiveLosses { get; set; }
    }

    /// <summary>
    /// Circular buffer for efficient data storage
    /// </summary>
    public class FKS_CircularBuffer<T> : IEnumerable<T>
    {
        private T[] buffer;
        private int head;
        private int tail;
        private int size;
        private readonly int capacity;

        public FKS_CircularBuffer(int capacity)
        {
            this.capacity = capacity;
            buffer = new T[capacity];
            head = 0;
            tail = 0;
            size = 0;
        }

        public int Count => size;
        public int Capacity => capacity;
        public bool IsFull => size == capacity;
        public bool IsEmpty => size == 0;

        public void Add(T item)
        {
            buffer[tail] = item;
            tail = (tail + 1) % capacity;

            if (size == capacity)
            {
                head = (head + 1) % capacity;
            }
            else
            {
                size++;
            }
        }

        public T this[int index]
        {
            get
            {
                if (index < 0 || index >= size)
                    throw new IndexOutOfRangeException();

                return buffer[(head + index) % capacity];
            }
        }

        public void Clear()
        {
            head = 0;
            tail = 0;
            size = 0;
        }

        public IEnumerator<T> GetEnumerator()
        {
            for (int i = 0; i < size; i++)
            {
                yield return buffer[(head + i) % capacity];
            }
        }

        IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();
    }

    #endregion

    #region Enhanced Core Management System

    /// <summary>
    /// Enhanced FKS Core System with centralized component management
    /// Provides shared state, configuration, and inter-component communication
    /// </summary>
    public static class FKS_CoreManager
    {
        #region Singleton Instance Management
        private static readonly object lockObject = new object();
        private static bool isInitialized = false;
        private static DateTime initializationTime;
        #endregion
        
        #region Component Registry
        private static Dictionary<string, IFKSComponent> registeredComponents = new Dictionary<string, IFKSComponent>();
        private static Dictionary<string, ComponentHealth> componentHealth = new Dictionary<string, ComponentHealth>();
        #endregion
        
        #region Market Configuration
        public static MarketConfiguration CurrentMarketConfig { get; private set; }
        private static Dictionary<string, MarketConfiguration> marketConfigs = new Dictionary<string, MarketConfiguration>();
        #endregion
        
        #region Shared State
        public static MarketState CurrentMarketState { get; private set; } = new MarketState();
        public static TradingState CurrentTradingState { get; private set; } = new TradingState();
        public static SystemPerformance Performance { get; private set; } = new SystemPerformance();
        #endregion
        
        #region Event System
        public static event EventHandler<SignalEventArgs> SignalGenerated;
        public static event EventHandler<TradeEventArgs> TradeExecuted;
        public static event EventHandler<ComponentEventArgs> ComponentStatusChanged;
        public static event EventHandler<MarketEventArgs> MarketRegimeChanged;
        #endregion
        
        #region Initialization
        public static void Initialize()
        {
            lock (lockObject)
            {
                if (isInitialized) return;
                
                InitializeMarketConfigs();
                SetMarket("Gold");
                Performance = new SystemPerformance();
                
                isInitialized = true;
                initializationTime = DateTime.Now;
                
                LogMessage("FKS Core Manager initialized successfully", FKSLogLevel.Information);
            }
        }
        
        private static void InitializeMarketConfigs()
        {
            marketConfigs["Gold"] = new MarketConfiguration
            {
                Symbol = "GC",
                TickSize = 0.10,
                TickValue = 10,
                DefaultContracts = 1,
                MaxContracts = 5,
                ATRStopMultiplier = 2.0,
                ATRTargetMultiplier = 3.0,
                SignalQualityThreshold = 0.65,
                OptimalSessionStart = 8,
                OptimalSessionEnd = 12,
                MinWaveRatio = 1.5,
                VolumeThreshold = 1.2
            };
            
            marketConfigs["ES"] = new MarketConfiguration
            {
                Symbol = "ES",
                TickSize = 0.25,
                TickValue = 12.50,
                DefaultContracts = 1,
                MaxContracts = 3,
                ATRStopMultiplier = 2.5,
                ATRTargetMultiplier = 3.5,
                SignalQualityThreshold = 0.65,
                OptimalSessionStart = 9,
                OptimalSessionEnd = 15,
                MinWaveRatio = 1.5,
                VolumeThreshold = 1.2
            };
            
            marketConfigs["NQ"] = new MarketConfiguration
            {
                Symbol = "NQ",
                TickSize = 0.25,
                TickValue = 5,
                DefaultContracts = 1,
                MaxContracts = 2,
                ATRStopMultiplier = 2.5,
                ATRTargetMultiplier = 3.5,
                SignalQualityThreshold = 0.70,
                OptimalSessionStart = 9,
                OptimalSessionEnd = 15,
                MinWaveRatio = 1.5,
                VolumeThreshold = 1.3
            };
            
            marketConfigs["CL"] = new MarketConfiguration
            {
                Symbol = "CL",
                TickSize = 0.01,
                TickValue = 10,
                DefaultContracts = 1,
                MaxContracts = 3,
                ATRStopMultiplier = 2.0,
                ATRTargetMultiplier = 3.0,
                SignalQualityThreshold = 0.60,
                OptimalSessionStart = 9,
                OptimalSessionEnd = 14,
                MinWaveRatio = 1.5,
                VolumeThreshold = 1.2
            };
            
            marketConfigs["BTC"] = new MarketConfiguration
            {
                Symbol = "BTC",
                TickSize = 1,
                TickValue = 5,
                DefaultContracts = 1,
                MaxContracts = 2,
                ATRStopMultiplier = 3.0,
                ATRTargetMultiplier = 4.0,
                SignalQualityThreshold = 0.70,
                OptimalSessionStart = 0,
                OptimalSessionEnd = 24,
                MinWaveRatio = 2.0,
                VolumeThreshold = 1.5
            };
        }
        
        public static void SetMarket(string marketType)
        {
            lock (lockObject)
            {
                if (marketConfigs.TryGetValue(marketType, out var config))
                {
                    CurrentMarketConfig = config;
                    LogMessage($"Market configuration set to: {marketType}", FKSLogLevel.Information);
                }
                else
                {
                    LogMessage($"Unknown market type: {marketType}, using Gold defaults", FKSLogLevel.Warning);
                    CurrentMarketConfig = marketConfigs["Gold"];
                }
            }
        }
        #endregion
        
        #region Component Registration
        public static void RegisterComponent(string componentId, IFKSComponent component)
        {
            lock (lockObject)
            {
                if (!isInitialized) Initialize();
                
                registeredComponents[componentId] = component;
                componentHealth[componentId] = new ComponentHealth
                {
                    ComponentId = componentId,
                    IsHealthy = true,
                    LastUpdate = DateTime.Now,
                    Version = component.Version
                };
                
                LogMessage($"Component registered: {componentId} v{component.Version}", FKSLogLevel.Information);
                
                ComponentStatusChanged?.Invoke(null, new ComponentEventArgs 
                { 
                    ComponentId = componentId, 
                    Status = ComponentStatus.Connected 
                });
            }
        }
        
        public static void UnregisterComponent(string componentId)
        {
            lock (lockObject)
            {
                if (registeredComponents.ContainsKey(componentId))
                {
                    registeredComponents.Remove(componentId);
                    componentHealth.Remove(componentId);
                    
                    LogMessage($"Component unregistered: {componentId}", FKSLogLevel.Information);
                    
                    ComponentStatusChanged?.Invoke(null, new ComponentEventArgs 
                    { 
                        ComponentId = componentId, 
                        Status = ComponentStatus.Disconnected 
                    });
                }
            }
        }
        
        public static T GetComponent<T>(string componentId) where T : class, IFKSComponent
        {
            lock (lockObject)
            {
                if (registeredComponents.TryGetValue(componentId, out var component))
                {
                    return component as T;
                }
                return null;
            }
        }
        #endregion
        
        #region Signal Management
        public static void PublishSignal(FKSSignal signal)
        {
            lock (lockObject)
            {
                if (signal.Quality < CurrentMarketConfig.SignalQualityThreshold)
                {
                    LogMessage($"Signal rejected - quality {signal.Quality:P} below threshold {CurrentMarketConfig.SignalQualityThreshold:P}", FKSLogLevel.Warning);
                    return;
                }
                
                CurrentTradingState.LastSignal = signal;
                CurrentTradingState.LastSignalTime = DateTime.Now;
                
                SignalGenerated?.Invoke(null, new SignalEventArgs { Signal = signal });
                
                LogMessage($"Signal published: {signal.Type} | Quality: {signal.Quality:P} | Setup: {signal.SetupNumber}", FKSLogLevel.Information);
            }
        }
        #endregion
        
        #region Performance Tracking
        public static void RecordTrade(TradeResult trade)
        {
            lock (lockObject)
            {
                Performance.RecordTrade(trade);
                CurrentTradingState.TradesToday++;
                CurrentTradingState.DailyPnL += trade.PnL;
                
                if (trade.PnL < 0)
                {
                    CurrentTradingState.ConsecutiveLosses++;
                }
                else
                {
                    CurrentTradingState.ConsecutiveLosses = 0;
                }
                
                TradeExecuted?.Invoke(null, new TradeEventArgs { Trade = trade });
                
                LogMessage($"Trade recorded: {trade.Setup} | P&L: {trade.PnL:C} | Quality: {trade.SignalQuality:P}", FKSLogLevel.Information);
            }
        }
        
        public static void ResetDailyCounters()
        {
            lock (lockObject)
            {
                CurrentTradingState.ResetDaily();
                Performance.StartNewDay();
                LogMessage("Daily counters reset", FKSLogLevel.Information);
            }
        }
        #endregion
        
        #region Market State Management
        public static void UpdateMarketState(MarketState newState)
        {
            lock (lockObject)
            {
                var previousRegime = CurrentMarketState?.MarketRegime;
                CurrentMarketState = newState;
                
                if (previousRegime != null && previousRegime != newState.MarketRegime)
                {
                    MarketRegimeChanged?.Invoke(null, new MarketEventArgs 
                    { 
                        PreviousRegime = previousRegime, 
                        NewRegime = newState.MarketRegime 
                    });
                    
                    LogMessage($"Market regime changed: {previousRegime} -> {newState.MarketRegime}", FKSLogLevel.Information);
                }
                
                if (componentHealth.ContainsKey("MarketAnalysis"))
                {
                    componentHealth["MarketAnalysis"].LastUpdate = DateTime.Now;
                }
            }
        }
        #endregion
        
        #region Health Monitoring
        public static Dictionary<string, ComponentHealth> GetComponentHealth()
        {
            lock (lockObject)
            {
                var now = DateTime.Now;
                foreach (var health in componentHealth.Values)
                {
                    if ((now - health.LastUpdate).TotalMinutes > 5)
                    {
                        health.IsHealthy = false;
                        health.ErrorMessage = "No update in 5 minutes";
                    }
                }
                
                return new Dictionary<string, ComponentHealth>(componentHealth);
            }
        }
        
        public static bool IsSystemHealthy()
        {
            lock (lockObject)
            {
                var criticalComponents = new[] { "FKS_AI", "FKS_AO", "FKS_Strategy" };
                
                foreach (var componentId in criticalComponents)
                {
                    if (!componentHealth.ContainsKey(componentId) || !componentHealth[componentId].IsHealthy)
                    {
                        return false;
                    }
                }
                
                return true;
            }
        }
        #endregion
        
        #region Logging
        private static void LogMessage(string message, FKSLogLevel level)
        {
            var logEntry = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] FKS_Core: {message}";
            
            if (level >= FKSLogLevel.Warning)
            {
                System.Diagnostics.Debug.WriteLine(logEntry);
            }
        }
        #endregion
    }

    #endregion

    #region Error Handling and Infrastructure

    /// <summary>
    /// Error handling strategy
    /// </summary>
    public class ErrorStrategy
    {
        public ErrorSeverity Severity { get; set; }
        public RecoveryAction RecoveryAction { get; set; }
        public RetryPolicy RetryPolicy { get; set; }
    }

    /// <summary>
    /// Enhanced error handling system with intelligent recovery
    /// </summary>
    public static class FKS_ErrorHandler
    {
        private static readonly Dictionary<Type, ErrorStrategy> ErrorStrategies = new Dictionary<Type, ErrorStrategy>();
        private static readonly Dictionary<string, int> ErrorCounts = new Dictionary<string, int>();

        static FKS_ErrorHandler()
        {
            InitializeErrorStrategies();
        }

        private static void InitializeErrorStrategies()
        {
            ErrorStrategies[typeof(OutOfMemoryException)] = new ErrorStrategy
            {
                Severity = ErrorSeverity.Critical,
                RecoveryAction = RecoveryAction.ForceGarbageCollection,
                RetryPolicy = RetryPolicy.NoRetry
            };

            ErrorStrategies[typeof(InvalidOperationException)] = new ErrorStrategy
            {
                Severity = ErrorSeverity.Medium,
                RecoveryAction = RecoveryAction.ReturnDefault,
                RetryPolicy = RetryPolicy.LinearBackoff
            };

            ErrorStrategies[typeof(ArgumentException)] = new ErrorStrategy
            {
                Severity = ErrorSeverity.Low,
                RecoveryAction = RecoveryAction.ValidateAndCorrect,
                RetryPolicy = RetryPolicy.Immediate
            };

            ErrorStrategies[typeof(DivideByZeroException)] = new ErrorStrategy
            {
                Severity = ErrorSeverity.Low,
                RecoveryAction = RecoveryAction.ReturnDefault,
                RetryPolicy = RetryPolicy.NoRetry
            };
        }

        /// <summary>
        /// Handle error with intelligent recovery
        /// </summary>
        public static T HandleError<T>(Exception ex, string context, Func<T> fallback = null, T defaultValue = default(T))
        {
            if (ex == null) return defaultValue;

            try
            {
                var strategy = GetErrorStrategy(ex.GetType());
                LogError(ex, context, strategy);
                TrackErrorFrequency(ex, context);

                if (fallback != null)
                {
                    try
                    {
                        return fallback();
                    }
                    catch (Exception fallbackEx)
                    {
                        LogError(fallbackEx, $"{context} (fallback)", strategy);
                    }
                }

                return defaultValue;
            }
            catch (Exception handlingEx)
            {
                System.Diagnostics.Debug.WriteLine($"Error in error handler: {handlingEx.Message}");
                return defaultValue;
            }
        }

        /// <summary>
        /// Execute action with error handling
        /// </summary>
        public static T ExecuteSafely<T>(Func<T> action, string context, T defaultValue = default(T))
        {
            try
            {
                return action();
            }
            catch (Exception ex)
            {
                return HandleError(ex, context, defaultValue: defaultValue);
            }
        }

        /// <summary>
        /// Execute action with error handling (no return value)
        /// </summary>
        public static bool ExecuteSafely(Action action, string context)
        {
            try
            {
                action();
                return true;
            }
            catch (Exception ex)
            {
                HandleError(ex, context);
                return false;
            }
        }

        private static ErrorStrategy GetErrorStrategy(Type exceptionType)
        {
            return ErrorStrategies.TryGetValue(exceptionType, out var strategy) ? strategy : new ErrorStrategy
            {
                Severity = ErrorSeverity.Medium,
                RecoveryAction = RecoveryAction.ReturnDefault,
                RetryPolicy = RetryPolicy.NoRetry
            };
        }

        private static void LogError(Exception ex, string context, ErrorStrategy strategy)
        {
            var logEntry = $"[ERROR] {context}: {ex.Message}";
            System.Diagnostics.Debug.WriteLine(logEntry);
        }

        private static void TrackErrorFrequency(Exception ex, string context)
        {
            string key = $"{ex.GetType().Name}_{context}";
            ErrorCounts[key] = ErrorCounts.TryGetValue(key, out var count) ? count + 1 : 1;
        }
    }

    /// <summary>
    /// Memory management utilities
    /// </summary>
    public static class FKS_MemoryManager
    {
        private static readonly object lockObject = new object();
        private static DateTime lastCleanup = DateTime.MinValue;

        /// <summary>
        /// Force garbage collection if memory pressure is high
        /// </summary>
        public static void ForceCleanupIfNeeded()
        {
            lock (lockObject)
            {
                if ((DateTime.Now - lastCleanup).TotalMinutes > 30)
                {
                    GC.Collect();
                    GC.WaitForPendingFinalizers();
                    GC.Collect();
                    lastCleanup = DateTime.Now;
                }
            }
        }

        /// <summary>
        /// Get current memory usage
        /// </summary>
        public static long GetMemoryUsage()
        {
            return GC.GetTotalMemory(false);
        }

        /// <summary>
        /// Check if memory usage is high
        /// </summary>
        public static bool IsMemoryPressureHigh()
        {
            return GetMemoryUsage() > 100 * 1024 * 1024; // 100MB threshold
        }
    }

    /// <summary>
    /// Performance monitoring utilities
    /// </summary>
    public static class FKS_Performance
    {
        private static readonly Dictionary<string, List<double>> PerformanceMetrics = new Dictionary<string, List<double>>();

        /// <summary>
        /// Record performance metric
        /// </summary>
        public static void RecordMetric(string name, double value)
        {
            if (!PerformanceMetrics.ContainsKey(name))
            {
                PerformanceMetrics[name] = new List<double>();
            }

            PerformanceMetrics[name].Add(value);

            // Keep only last 100 measurements
            if (PerformanceMetrics[name].Count > 100)
            {
                PerformanceMetrics[name].RemoveAt(0);
            }
        }

        /// <summary>
        /// Get average performance metric
        /// </summary>
        public static double GetAverageMetric(string name)
        {
            if (PerformanceMetrics.TryGetValue(name, out var values) && values.Count > 0)
            {
                return values.Average();
            }
            return 0.0;
        }

        /// <summary>
        /// Get performance summary
        /// </summary>
        public static Dictionary<string, double> GetPerformanceSummary()
        {
            var summary = new Dictionary<string, double>();
            foreach (var kvp in PerformanceMetrics)
            {
                if (kvp.Value.Count > 0)
                {
                    summary[kvp.Key] = kvp.Value.Average();
                }
            }
            return summary;
        }
    }

    #endregion

    #region Calculation and Caching System

    /// <summary>
    /// Unified calculation cache for performance optimization
    /// </summary>
    public static class FKS_UnifiedCache
    {
        private static readonly object lockObj = new object();
        private static int lastCalculatedBar = -1;
        private static readonly Dictionary<string, object> barCalculations = new Dictionary<string, object>();
        private static readonly Dictionary<string, object> persistentStates = new Dictionary<string, object>();

        /// <summary>
        /// Update current bar for cache invalidation
        /// </summary>
        public static void UpdateBar(int currentBar)
        {
            lock (lockObj)
            {
                if (currentBar != lastCalculatedBar)
                {
                    barCalculations.Clear();
                    lastCalculatedBar = currentBar;
                }
            }
        }

        /// <summary>
        /// Get or calculate bar-specific value
        /// </summary>
        public static T GetOrCalculate<T>(string key, Func<T> calculator)
        {
            lock (lockObj)
            {
                if (barCalculations.TryGetValue(key, out var cached))
                {
                    return (T)cached;
                }

                var result = calculator();
                barCalculations[key] = result;
                return result;
            }
        }

        /// <summary>
        /// Get or set persistent state value
        /// </summary>
        public static T GetOrSetPersistent<T>(string key, T value)
        {
            lock (lockObj)
            {
                if (persistentStates.TryGetValue(key, out var existing))
                {
                    return (T)existing;
                }

                persistentStates[key] = value;
                return value;
            }
        }

        /// <summary>
        /// Clear all cached data
        /// </summary>
        public static void Clear()
        {
            lock (lockObj)
            {
                barCalculations.Clear();
                persistentStates.Clear();
                lastCalculatedBar = -1;
            }
        }
    }

    /// <summary>
    /// Common calculation utilities
    /// </summary>
    public static class FKS_Calculations
    {
        /// <summary>
        /// Calculate Simple Moving Average
        /// </summary>
        public static double CalculateSMA(IList<double> values, int period)
        {
            if (values == null || values.Count < period || period <= 0)
                return 0.0;

            return values.Skip(values.Count - period).Take(period).Average();
        }

        /// <summary>
        /// Calculate Exponential Moving Average
        /// </summary>
        public static double CalculateEMA(IList<double> values, int period, double previousEMA = 0.0)
        {
            if (values == null || values.Count == 0 || period <= 0)
                return 0.0;

            double multiplier = 2.0 / (period + 1);
            double currentValue = values[values.Count - 1];

            if (previousEMA == 0.0)
            {
                return CalculateSMA(values, Math.Min(period, values.Count));
            }

            return (currentValue * multiplier) + (previousEMA * (1 - multiplier));
        }

        /// <summary>
        /// Calculate Average True Range
        /// </summary>
        public static double CalculateATR(IList<double> highs, IList<double> lows, IList<double> closes, int period)
        {
            if (highs == null || lows == null || closes == null || 
                highs.Count < period || lows.Count < period || closes.Count < period)
                return 0.0;

            var trueRanges = new List<double>();
            
            for (int i = 1; i < Math.Min(highs.Count, Math.Min(lows.Count, closes.Count)); i++)
            {
                double tr1 = highs[i] - lows[i];
                double tr2 = Math.Abs(highs[i] - closes[i - 1]);
                double tr3 = Math.Abs(lows[i] - closes[i - 1]);
                
                trueRanges.Add(Math.Max(tr1, Math.Max(tr2, tr3)));
            }

            return CalculateSMA(trueRanges, period);
        }

        /// <summary>
        /// Calculate RSI
        /// </summary>
        public static double CalculateRSI(IList<double> values, int period)
        {
            if (values == null || values.Count < period + 1)
                return 50.0;

            var gains = new List<double>();
            var losses = new List<double>();

            for (int i = 1; i < values.Count; i++)
            {
                double change = values[i] - values[i - 1];
                gains.Add(change > 0 ? change : 0);
                losses.Add(change < 0 ? -change : 0);
            }

            double avgGain = CalculateSMA(gains, period);
            double avgLoss = CalculateSMA(losses, period);

            if (avgLoss == 0) return 100.0;

            double rs = avgGain / avgLoss;
            return 100.0 - (100.0 / (1.0 + rs));
        }

        /// <summary>
        /// Calculate VWAP
        /// </summary>
        public static double CalculateVWAP(IList<double> prices, IList<double> volumes)
        {
            if (prices == null || volumes == null || prices.Count != volumes.Count || prices.Count == 0)
                return 0.0;

            double totalVolumePrice = 0.0;
            double totalVolume = 0.0;

            for (int i = 0; i < prices.Count; i++)
            {
                totalVolumePrice += prices[i] * volumes[i];
                totalVolume += volumes[i];
            }

            return totalVolume > 0 ? totalVolumePrice / totalVolume : 0.0;
        }
    }

    #endregion

    #region Utility Classes

    /// <summary>
    /// Utility functions for the FKS system
    /// </summary>
    public static class FKS_Utils
    {
        /// <summary>
        /// Clamp value between min and max
        /// </summary>
        public static T Clamp<T>(T value, T min, T max) where T : IComparable<T>
        {
            if (value.CompareTo(min) < 0) return min;
            if (value.CompareTo(max) > 0) return max;
            return value;
        }

        /// <summary>
        /// Check if current time is market hours
        /// </summary>
        public static bool IsMarketHours(DateTime dateTime)
        {
            if (IsWeekend(dateTime)) return false;
            var hour = dateTime.Hour;
            return hour >= 9 && hour <= 16; // Simplified market hours
        }

        /// <summary>
        /// Check if current time is weekend
        /// </summary>
        public static bool IsWeekend(DateTime dateTime)
        {
            return dateTime.DayOfWeek == DayOfWeek.Saturday || dateTime.DayOfWeek == DayOfWeek.Sunday;
        }

        /// <summary>
        /// Get current trading session
        /// </summary>
        public static SessionType GetCurrentSession(DateTime dateTime)
        {
            if (IsWeekend(dateTime)) return SessionType.Weekend;
            
            var hour = dateTime.Hour;
            
            if (hour >= 2 && hour < 8) return SessionType.LondonOpen;
            if (hour >= 8 && hour < 9) return SessionType.LondonSession;
            if (hour >= 9 && hour < 10) return SessionType.NYOpen;
            if (hour >= 10 && hour < 16) return SessionType.NYSession;
            if (hour >= 16 && hour < 18) return SessionType.AfterHours;
            
            return SessionType.AsianSession;
        }

        /// <summary>
        /// Format price for display
        /// </summary>
        public static string FormatPrice(double price, int decimals = 2)
        {
            return price.ToString($"F{decimals}");
        }

        /// <summary>
        /// Calculate percentage change
        /// </summary>
        public static double CalculatePercentageChange(double oldValue, double newValue)
        {
            if (oldValue == 0) return 0;
            return ((newValue - oldValue) / oldValue) * 100;
        }
    }

    #endregion

    #region Supporting Classes and Interfaces

    /// <summary>
    /// Interface for FKS components
    /// </summary>
    public interface IFKSComponent
    {
        string ComponentId { get; }
        string Version { get; }
        void Initialize();
        void Shutdown();
    }

    /// <summary>
    /// Market configuration class
    /// </summary>
    public class MarketConfiguration
    {
        public string Symbol { get; set; }
        public double TickSize { get; set; }
        public double TickValue { get; set; }
        public int DefaultContracts { get; set; }
        public int MaxContracts { get; set; }
        public double ATRStopMultiplier { get; set; }
        public double ATRTargetMultiplier { get; set; }
        public double SignalQualityThreshold { get; set; }
        public int OptimalSessionStart { get; set; }
        public int OptimalSessionEnd { get; set; }
        public double MinWaveRatio { get; set; }
        public double VolumeThreshold { get; set; }
    }

    /// <summary>
    /// Market state class
    /// </summary>
    public class MarketState
    {
        public string MarketRegime { get; set; } = "NEUTRAL";
        public string TrendDirection { get; set; } = "NEUTRAL";
        public double Volatility { get; set; }
        public double VolumeRatio { get; set; }
        public string SignalType { get; set; }
        public double SignalQuality { get; set; }
        public double WaveRatio { get; set; }
        public DateTime LastUpdate { get; set; } = DateTime.Now;
    }

    /// <summary>
    /// Trading state class
    /// </summary>
    public class TradingState
    {
        public int TradesToday { get; set; }
        public double DailyPnL { get; set; }
        public int ConsecutiveLosses { get; set; }
        public FKSSignal LastSignal { get; set; }
        public DateTime LastSignalTime { get; set; }
        public bool TradingEnabled { get; set; } = true;
        
        public void ResetDaily()
        {
            TradesToday = 0;
            DailyPnL = 0;
            ConsecutiveLosses = 0;
            TradingEnabled = true;
        }
    }

    /// <summary>
    /// FKS signal class
    /// </summary>
    public class FKSSignal
    {
        public string Type { get; set; } // G, Top, ^, v
        public double Quality { get; set; }
        public double WaveRatio { get; set; }
        public int SetupNumber { get; set; }
        public int RecommendedContracts { get; set; }
        public DateTime Timestamp { get; set; } = DateTime.Now;
    }

    /// <summary>
    /// Trade result class
    /// </summary>
    public class TradeResult
    {
        public DateTime EntryTime { get; set; }
        public DateTime ExitTime { get; set; }
        public double EntryPrice { get; set; }
        public double ExitPrice { get; set; }
        public int Contracts { get; set; }
        public double PnL { get; set; }
        public string Setup { get; set; }
        public double SignalQuality { get; set; }
    }

    /// <summary>
    /// Component health class
    /// </summary>
    public class ComponentHealth
    {
        public string ComponentId { get; set; }
        public bool IsHealthy { get; set; }
        public DateTime LastUpdate { get; set; }
        public string Version { get; set; }
        public string ErrorMessage { get; set; }
    }

    /// <summary>
    /// System performance class
    /// </summary>
    public class SystemPerformance
    {
        private List<TradeResult> allTrades = new List<TradeResult>();
        private List<TradeResult> todaysTrades = new List<TradeResult>();
        
        public double TotalPnL => allTrades.Sum(t => t.PnL);
        public double WinRate => allTrades.Count > 0 ? (double)allTrades.Count(t => t.PnL > 0) / allTrades.Count : 0;
        public double SharpeRatio { get; private set; } = 0;
        public double MaxDrawdown { get; private set; } = 0;
        
        public void RecordTrade(TradeResult trade)
        {
            allTrades.Add(trade);
            todaysTrades.Add(trade);
            CalculateMetrics();
        }
        
        public void StartNewDay()
        {
            todaysTrades.Clear();
        }
        
        private void CalculateMetrics()
        {
            if (allTrades.Count > 20)
            {
                var returns = allTrades.Select(t => t.PnL).ToList();
                var avgReturn = returns.Average();
                var stdDev = Math.Sqrt(returns.Select(r => Math.Pow(r - avgReturn, 2)).Average());
                SharpeRatio = stdDev > 0 ? (avgReturn / stdDev) * Math.Sqrt(252) : 0;
            }
            
            double peak = 0;
            double currentValue = 0;
            double maxDD = 0;
            
            foreach (var trade in allTrades)
            {
                currentValue += trade.PnL;
                if (currentValue > peak)
                    peak = currentValue;
                
                var drawdown = peak > 0 ? (peak - currentValue) / peak : 0;
                if (drawdown > maxDD)
                    maxDD = drawdown;
            }
            
            MaxDrawdown = maxDD;
        }
    }

    // Event Args Classes
    public class SignalEventArgs : EventArgs
    {
        public FKSSignal Signal { get; set; }
    }

    public class TradeEventArgs : EventArgs
    {
        public TradeResult Trade { get; set; }
    }

    public class ComponentEventArgs : EventArgs
    {
        public string ComponentId { get; set; }
        public ComponentStatus Status { get; set; }
    }

    public class MarketEventArgs : EventArgs
    {
        public string PreviousRegime { get; set; }
        public string NewRegime { get; set; }
    }

    #endregion
}
