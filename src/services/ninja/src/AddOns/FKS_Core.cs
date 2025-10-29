#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
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
#endregion

namespace NinjaTrader.NinjaScript.AddOns.FKS
{
    /// <summary>
    /// Enhanced FKS_Core serves as the central hub for all FKS components
    /// Provides thread-safe shared state, configuration management, inter-component communication,
    /// circuit breaker patterns, and comprehensive monitoring
    /// </summary>
    public static class FKS_Core
    {
        #region Thread-Safe Instance Management
        private static readonly ReaderWriterLockSlim rwLock = new ReaderWriterLockSlim();
        private static readonly object initLock = new object();
        private static volatile bool isInitialized = false;
        private static DateTime initializationTime;
        private static volatile bool isShuttingDown = false;
        #endregion
        
        #region Enhanced Component Registry
        private static readonly ConcurrentDictionary<string, IFKSComponent> registeredComponents 
            = new ConcurrentDictionary<string, IFKSComponent>();
        private static readonly ConcurrentDictionary<string, ComponentHealth> componentHealth 
            = new ConcurrentDictionary<string, ComponentHealth>();
        private static readonly ConcurrentDictionary<string, ComponentCircuitBreaker> circuitBreakers 
            = new ConcurrentDictionary<string, ComponentCircuitBreaker>();
        private static readonly ConcurrentDictionary<string, ComponentMetrics> componentMetrics 
            = new ConcurrentDictionary<string, ComponentMetrics>();
        #endregion
        
        #region Market Configuration - Thread Safe
        private static volatile MarketConfiguration currentMarketConfig;
        private static readonly ConcurrentDictionary<string, MarketConfiguration> marketConfigs 
            = new ConcurrentDictionary<string, MarketConfiguration>();
        private static readonly Timer configWatcher;
        private static string configFilePath;
        private static DateTime lastConfigUpdate = DateTime.MinValue;
        #endregion
        
        #region Shared State - Thread Safe
        private static MarketState currentMarketState = new MarketState();
        private static TradingState currentTradingState = new TradingState();
        private static SystemPerformance performance = new SystemPerformance();
        private static readonly object stateUpdateLock = new object();
        
        // Public properties with thread-safe access
        public static MarketConfiguration CurrentMarketConfig 
        { 
            get => currentMarketConfig; 
            private set => currentMarketConfig = value; 
        }
        
        public static MarketState CurrentMarketState 
        { 
            get { lock (stateUpdateLock) { return currentMarketState; } }
            private set { lock (stateUpdateLock) { currentMarketState = value; } }
        }
        
        public static TradingState CurrentTradingState 
        { 
            get { lock (stateUpdateLock) { return currentTradingState; } }
            private set { lock (stateUpdateLock) { currentTradingState = value; } }
        }
        
        public static SystemPerformance Performance 
        { 
            get { lock (stateUpdateLock) { return performance; } }
            private set { lock (stateUpdateLock) { performance = value; } }
        }
        
        public static DateTime InitializationTime => initializationTime;
        public static bool IsInitialized => isInitialized;
        public static bool IsShuttingDown => isShuttingDown;
        #endregion
        
        #region Enhanced Event System with Throttling
        private static readonly ConcurrentDictionary<Type, DateTime> lastEventTimes = new ConcurrentDictionary<Type, DateTime>();
        private static readonly TimeSpan eventThrottleInterval = TimeSpan.FromMilliseconds(50);
        private static readonly ConcurrentQueue<EventInfo> eventQueue = new ConcurrentQueue<EventInfo>();
        private static readonly Timer eventProcessor;
        
        public static event EventHandler<SignalEventArgs> SignalGenerated;
        public static event EventHandler<TradeEventArgs> TradeExecuted;
        public static event EventHandler<ComponentEventArgs> ComponentStatusChanged;
        public static event EventHandler<MarketEventArgs> MarketRegimeChanged;
        public static event EventHandler<SystemEventArgs> SystemHealthChanged;
        public static event EventHandler<ConfigurationEventArgs> ConfigurationChanged;
        public static event EventHandler<CircuitBreakerEventArgs> CircuitBreakerTriggered;
        #endregion
        
        #region Statistics and Monitoring
        private static readonly ConcurrentDictionary<string, long> operationCounters = new ConcurrentDictionary<string, long>();
        private static readonly ConcurrentDictionary<string, double> performanceMetrics = new ConcurrentDictionary<string, double>();
        private static readonly Timer metricsCollector;
        private static readonly Timer healthMonitor;
        private static readonly Timer memoryMonitor;
        private static long lastMemoryUsage = 0;
        private static int memoryWarningCount = 0;
        private const long MAX_MEMORY_THRESHOLD = 10L * 1024 * 1024 * 1024; // 10GB threshold for 64GB system
        private const long CLEANUP_THRESHOLD = 5L * 1024 * 1024 * 1024; // 5GB cleanup threshold
        #endregion
        
        #region Static Constructor
        static FKS_Core()
        {
            try
            {
                // Initialize timers
                configWatcher = new Timer(CheckConfigurationChanges, null, TimeSpan.FromSeconds(30), TimeSpan.FromSeconds(30));
                eventProcessor = new Timer(ProcessEventQueue, null, TimeSpan.FromMilliseconds(100), TimeSpan.FromMilliseconds(100));
                metricsCollector = new Timer(CollectMetrics, null, TimeSpan.FromSeconds(10), TimeSpan.FromSeconds(10));
                healthMonitor = new Timer(MonitorSystemHealth, null, TimeSpan.FromSeconds(15), TimeSpan.FromSeconds(15));
                memoryMonitor = new Timer(MonitorMemoryUsage, null, 5000, 5000); // 5 second intervals
                
                // Register for application shutdown
                AppDomain.CurrentDomain.ProcessExit += OnApplicationShutdown;
                
                // Set configuration file path
                configFilePath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "NinjaTrader 8", "FKS_Config.xml");
                
                LogMessage("FKS Core static constructor completed", LogLevel.Debug);
            }
            catch (Exception ex)
            {
                LogMessage($"FKS Core static constructor error: {ex.Message}", LogLevel.Error);
            }
        }
        #endregion
        
        #region Enhanced Initialization
        public static void Initialize()
        {
            lock (initLock)
            {
                if (isInitialized) return;
                
                try
                {
                    var stopwatch = Stopwatch.StartNew();
                    
                    // Initialize market configurations
                    InitializeMarketConfigs();
                    
                    // Load saved configuration
                    LoadConfiguration();
                    
                    // Set default market if none configured
                    if (CurrentMarketConfig == null)
                    {
                        SetMarket("Gold");
                    }
                    
                    // Initialize performance tracking
                    Performance = new SystemPerformance();
                    
                    // Initialize FKS Infrastructure integration
                    InitializeFKSInfrastructureIntegration();
                    
                    // Mark as initialized
                    isInitialized = true;
                    initializationTime = DateTime.Now;
                    
                    stopwatch.Stop();
                    LogMessage($"FKS Core initialized successfully in {stopwatch.ElapsedMilliseconds}ms", LogLevel.Information);
                    
                    // Record initialization metrics
                    RecordOperation("Initialize");
                    RecordPerformanceMetric("InitializationTime", stopwatch.ElapsedMilliseconds);
                    
                    // Raise system event
                    RaiseSystemEvent(SystemEventType.Initialized, "FKS Core system initialized");
                }
                catch (Exception ex)
                {
                    LogMessage($"FKS Core initialization failed: {ex.Message}", LogLevel.Error);
                    FKS_ErrorHandler.HandleError(ex, "FKS_Core.Initialize");
                    throw;
                }
            }
        }
        
        private static void InitializeMarketConfigs()
        {
            try
            {
                // Gold Configuration - Commission Optimized
                marketConfigs["Gold"] = new MarketConfiguration
                {
                    Symbol = "GC",
                    TickSize = 0.10,
                    TickValue = 10,
                    DefaultContracts = 1,
                    MaxContracts = 4, // Reduced for commission optimization
                    ATRStopMultiplier = 1.8, // Tightened
                    ATRTargetMultiplier = 2.2, // Increased
                    SignalQualityThreshold = 0.70, // Raised
                    OptimalSessionStart = 8,
                    OptimalSessionEnd = 14, // Reduced hours
                    MinWaveRatio = 1.5,
                    VolumeThreshold = 1.35, // Increased
                    Commission = 5.0,
                    MinProfitTarget = 10, // Minimum ticks
                    SessionOptimized = true
                };
                
                // ES Configuration - Commission Optimized
                marketConfigs["ES"] = new MarketConfiguration
                {
                    Symbol = "ES",
                    TickSize = 0.25,
                    TickValue = 12.50,
                    DefaultContracts = 1,
                    MaxContracts = 4,
                    ATRStopMultiplier = 1.8,
                    ATRTargetMultiplier = 2.2,
                    SignalQualityThreshold = 0.72,
                    OptimalSessionStart = 9,
                    OptimalSessionEnd = 14,
                    MinWaveRatio = 1.5,
                    VolumeThreshold = 1.35,
                    Commission = 5.0,
                    MinProfitTarget = 8,
                    SessionOptimized = true
                };
                
                // NQ Configuration - Commission Optimized
                marketConfigs["NQ"] = new MarketConfiguration
                {
                    Symbol = "NQ",
                    TickSize = 0.25,
                    TickValue = 5,
                    DefaultContracts = 1,
                    MaxContracts = 3, // More conservative
                    ATRStopMultiplier = 1.8,
                    ATRTargetMultiplier = 2.2,
                    SignalQualityThreshold = 0.75, // Higher threshold
                    OptimalSessionStart = 9,
                    OptimalSessionEnd = 13, // Shorter hours
                    MinWaveRatio = 1.5,
                    VolumeThreshold = 1.4,
                    Commission = 5.0,
                    MinProfitTarget = 12,
                    SessionOptimized = true
                };
                
                // CL Configuration - Commission Optimized
                marketConfigs["CL"] = new MarketConfiguration
                {
                    Symbol = "CL",
                    TickSize = 0.01,
                    TickValue = 10,
                    DefaultContracts = 1,
                    MaxContracts = 2, // More conservative
                    ATRStopMultiplier = 1.8,
                    ATRTargetMultiplier = 2.2,
                    SignalQualityThreshold = 0.78, // Highest threshold
                    OptimalSessionStart = 9,
                    OptimalSessionEnd = 14,
                    MinWaveRatio = 1.5,
                    VolumeThreshold = 1.5,
                    Commission = 5.0,
                    MinProfitTarget = 15,
                    SessionOptimized = true
                };
                
                // BTC Configuration - Commission Optimized
                marketConfigs["BTC"] = new MarketConfiguration
                {
                    Symbol = "BTC",
                    TickSize = 1,
                    TickValue = 5,
                    DefaultContracts = 1,
                    MaxContracts = 2,
                    ATRStopMultiplier = 1.8,
                    ATRTargetMultiplier = 2.2,
                    SignalQualityThreshold = 0.80, // Highest threshold
                    OptimalSessionStart = 0,
                    OptimalSessionEnd = 24, // 24/7 market
                    MinWaveRatio = 2.0,
                    VolumeThreshold = 1.6,
                    Commission = 5.0,
                    MinProfitTarget = 20,
                    SessionOptimized = false // Weekend only with confirmation
                };
                
                LogMessage("Market configurations initialized with commission optimization", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to initialize market configs: {ex.Message}", LogLevel.Error);
                throw;
            }
        }
        
        private static void InitializeFKSInfrastructureIntegration()
        {
            try
            {
                // Register FKS_Core with infrastructure
                FKS_Infrastructure.RegisterComponent("FKS_Core", new FKS_Infrastructure.ComponentRegistrationInfo
                {
                    ComponentType = "CoreSystem",
                    Version = "3.0.0",
                    IsCritical = true,
                    ExpectedResponseTime = TimeSpan.FromMilliseconds(100),
                    MaxMemoryUsage = 50 * 1024 * 1024 // 50MB
                });
                
                // Subscribe to infrastructure events
                FKS_Infrastructure.OnComponentError += OnInfrastructureComponentError;
                // Disabled to prevent spam for missing optional components
                // FKS_Infrastructure.OnCriticalAlertRaised += OnInfrastructureCriticalAlert;
                
                LogMessage("FKS Infrastructure integration initialized", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"FKS Infrastructure integration failed: {ex.Message}", LogLevel.Warning);
                // Don't throw - this is not critical for basic operation
            }
        }
        #endregion
        
        #region Enhanced Component Registration
        public static void RegisterComponent(string componentId, IFKSComponent component)
        {
            if (string.IsNullOrEmpty(componentId) || component == null)
            {
                LogMessage($"Invalid component registration: {componentId}", LogLevel.Warning);
                return;
            }

            bool lockTaken = false;
            try
            {
                lockTaken = rwLock.TryEnterWriteLock(TimeSpan.FromSeconds(2));
                if (!lockTaken)
                {
                    LogMessage($"Failed to acquire write lock for component registration: {componentId}", LogLevel.Warning);
                    return;
                }
                
                if (!isInitialized) Initialize();
                
                // Register component
                registeredComponents[componentId] = component;
                
                // Initialize health tracking
                componentHealth[componentId] = new ComponentHealth
                {
                    ComponentId = componentId,
                    IsHealthy = true,
                    LastUpdate = DateTime.Now,
                    Version = component.Version,
                    RegistrationTime = DateTime.Now
                };
                
                // Initialize circuit breaker
                circuitBreakers[componentId] = new ComponentCircuitBreaker
                {
                    ComponentId = componentId,
                    State = CircuitBreakerState.Closed,
                    FailureThreshold = 5,
                    TimeoutPeriod = TimeSpan.FromMinutes(2)
                };
                
                // Initialize metrics
                componentMetrics[componentId] = new ComponentMetrics
                {
                    ComponentId = componentId,
                    RegistrationTime = DateTime.Now
                };
                
                LogMessage($"Component registered: {componentId} v{component.Version}", LogLevel.Information);
                RecordOperation("RegisterComponent");
            }
            catch (Exception ex)
            {
                LogMessage($"Component registration failed for {componentId}: {ex.Message}", LogLevel.Error);
                return;
            }
            finally
            {
                if (lockTaken && rwLock.IsWriteLockHeld)
                    rwLock.ExitWriteLock();
            }
            
            // Do all external calls OUTSIDE the lock to prevent recursion
            Task.Run(() =>
            {
                try
                {
                    // Initialize component
                    try
                    {
                        component.Initialize();
                    }
                    catch (Exception initEx)
                    {
                        LogMessage($"Component {componentId} initialization failed: {initEx.Message}", LogLevel.Warning);
                        RecordComponentError(componentId, initEx, "Component.Initialize");
                    }
                    
                    // Register with infrastructure
                    try
                    {
                        FKS_Infrastructure.RegisterComponent(componentId, new FKS_Infrastructure.ComponentRegistrationInfo
                        {
                            ComponentType = component.GetType().Name,
                            Version = component.Version,
                            IsCritical = IsCriticalComponent(componentId)
                        });
                    }
                    catch (Exception infraEx)
                    {
                        LogMessage($"Infrastructure registration failed for {componentId}: {infraEx.Message}", LogLevel.Warning);
                    }
                    
                    // Raise event (throttled)
                    RaiseComponentEvent(componentId, ComponentStatus.Connected, "Component registered");
                }
                catch (Exception ex)
                {
                    LogMessage($"Post-registration setup failed for {componentId}: {ex.Message}", LogLevel.Warning);
                }
            });
        }
        
        public static void UnregisterComponent(string componentId)
        {
            if (string.IsNullOrEmpty(componentId)) return;
            
            // Check if we're already in shutdown to prevent recursive calls
            if (isShuttingDown) return;
            
            bool lockTaken = false;
            IFKSComponent componentToShutdown = null;
            
            try
            {
                // Use timeout to prevent deadlock
                lockTaken = rwLock.TryEnterWriteLock(TimeSpan.FromSeconds(2));
                if (!lockTaken)
                {
                    LogMessage($"Failed to acquire write lock for component unregistration: {componentId}", LogLevel.Warning);
                    return;
                }
                
                // Get component reference for shutdown (do this inside lock)
                registeredComponents.TryGetValue(componentId, out componentToShutdown);
                
                // Remove from collections
                registeredComponents.TryRemove(componentId, out _);
                componentHealth.TryRemove(componentId, out _);
                circuitBreakers.TryRemove(componentId, out _);
                componentMetrics.TryRemove(componentId, out _);
                
                LogMessage($"Component unregistered: {componentId}", LogLevel.Information);
                RecordOperation("UnregisterComponent");
            }
            catch (Exception ex)
            {
                LogMessage($"Component unregistration failed for {componentId}: {ex.Message}", LogLevel.Error);
                return;
            }
            finally
            {
                if (lockTaken && rwLock.IsWriteLockHeld)
                    rwLock.ExitWriteLock();
            }
            
            // Do all external calls OUTSIDE the lock to prevent recursion
            Task.Run(() =>
            {
                try
                {
                    // Shutdown component gracefully
                    if (componentToShutdown != null)
                    {
                        try
                        {
                            componentToShutdown.Shutdown();
                        }
                        catch (Exception shutdownEx)
                        {
                            LogMessage($"Component {componentId} shutdown error: {shutdownEx.Message}", LogLevel.Warning);
                        }
                    }
                    
                    // Unregister from infrastructure
                    FKS_Infrastructure.UnregisterComponent(componentId);
                    
                    // Raise event
                    RaiseComponentEvent(componentId, ComponentStatus.Disconnected, "Component unregistered");
                }
                catch (Exception ex)
                {
                    LogMessage($"Post-unregistration cleanup failed for {componentId}: {ex.Message}", LogLevel.Warning);
                }
            });
        }
        
        public static T GetComponent<T>(string componentId) where T : class, IFKSComponent
        {
            if (string.IsNullOrEmpty(componentId)) return null;
            
            try
            {
                // Check circuit breaker first (no lock needed for ConcurrentDictionary)
                if (!IsComponentSafeToUse(componentId))
                {
                    LogMessage($"Component {componentId} circuit breaker open", LogLevel.Warning);
                    return null;
                }
                
                // ConcurrentDictionary is thread-safe for reads, no lock needed
                if (registeredComponents.TryGetValue(componentId, out var component))
                {
                    RecordOperation("GetComponent");
                    RecordComponentAccess(componentId);
                    return component as T;
                }
                
                return null;
            }
            catch (Exception ex)
            {
                LogMessage($"Get component failed for {componentId}: {ex.Message}", LogLevel.Error);
                RecordComponentError(componentId, ex, "GetComponent");
                return null;
            }
        }
        
        /// <summary>
        /// Get component with circuit breaker protection and automatic error handling
        /// </summary>
        public static T GetComponentSafe<T>(string componentId) where T : class, IFKSComponent
        {
            try
            {
                var circuitBreaker = circuitBreakers.TryGetValue(componentId, out var cbValue) ? cbValue : null;
                if (circuitBreaker == null) return GetComponent<T>(componentId);
                
                return circuitBreaker.Execute(() => GetComponent<T>(componentId));
            }
            catch (CircuitBreakerOpenException)
            {
                LogMessage($"Circuit breaker open for component: {componentId}", LogLevel.Warning);
                return null;
            }
            catch (Exception ex)
            {
                RecordComponentError(componentId, ex, "GetComponentSafe");
                return null;
            }
        }
        #endregion
        
        #region Enhanced Market State Management
        public static void UpdateMarketState(MarketState newState)
        {
            if (newState == null) return;
            
            try
            {
                lock (stateUpdateLock)
                {
                    var previousRegime = CurrentMarketState?.MarketRegime;
                    var previousState = CurrentMarketState;
                    CurrentMarketState = newState;
                    CurrentMarketState.LastUpdate = DateTime.Now;
                    
                    // Check for regime change
                    if (!string.IsNullOrEmpty(previousRegime) && previousRegime != newState.MarketRegime)
                    {
                        LogMessage($"Market regime changed: {previousRegime} -> {newState.MarketRegime}", LogLevel.Information);
                        
                        // Raise event (throttled)
                        RaiseMarketEvent(previousRegime, newState.MarketRegime, "Market regime change detected");
                        
                        // Update configuration if needed
                        ApplyRegimeBasedConfiguration(newState.MarketRegime);
                    }
                    
                    // Update component health for market analysis
                    if (componentHealth.ContainsKey("MarketAnalysis"))
                    {
                        var health = componentHealth["MarketAnalysis"];
                        health.LastUpdate = DateTime.Now;
                        health.IsHealthy = true;
                    }
                    
                    RecordOperation("UpdateMarketState");
                    RecordPerformanceMetric("MarketStateUpdateFrequency", 1);
                }
                
                // Record activity with infrastructure
                FKS_Infrastructure.RecordComponentActivity("FKS_Core", new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = "MarketStateUpdate",
                    ExecutionTime = TimeSpan.FromMilliseconds(1)
                });
            }
            catch (Exception ex)
            {
                LogMessage($"Market state update failed: {ex.Message}", LogLevel.Error);
                FKS_ErrorHandler.HandleError(ex, "FKS_Core.UpdateMarketState");
            }
        }
        
        public static void SetMarket(string marketType)
        {
            if (string.IsNullOrEmpty(marketType)) return;
            
            try
            {
                lock (stateUpdateLock)
                {
                    if (marketConfigs.TryGetValue(marketType, out var config))
                    {
                        var previousMarket = CurrentMarketConfig?.Symbol;
                        CurrentMarketConfig = config;
                        
                        LogMessage($"Market configuration set to: {marketType} ({config.Symbol})", LogLevel.Information);
                        
                        // Save configuration
                        SaveConfiguration();
                        
                        // Raise configuration change event
                        RaiseConfigurationEvent("MarketChange", previousMarket, marketType);
                        
                        RecordOperation("SetMarket");
                    }
                    else
                    {
                        LogMessage($"Unknown market type: {marketType}, using Gold defaults", LogLevel.Warning);
                        CurrentMarketConfig = marketConfigs.TryGetValue("Gold", out var goldConfig) ? goldConfig : CreateDefaultMarketConfig();
                    }
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Set market failed for {marketType}: {ex.Message}", LogLevel.Error);
                FKS_ErrorHandler.HandleError(ex, $"FKS_Core.SetMarket({marketType})");
            }
        }
        
        /// <summary>
        /// Get market configuration with validation
        /// </summary>
        public static MarketConfiguration GetMarketConfiguration(string marketType)
        {
            if (string.IsNullOrEmpty(marketType)) return CurrentMarketConfig;
            
            return marketConfigs.TryGetValue(marketType, out var config) ? config : (CurrentMarketConfig ?? CreateDefaultMarketConfig());
        }
        
        /// <summary>
        /// Update market configuration dynamically
        /// </summary>
        public static void UpdateMarketConfiguration(string marketType, MarketConfiguration config)
        {
            if (string.IsNullOrEmpty(marketType) || config == null) return;
            
            try
            {
                // Validate configuration
                if (ValidateMarketConfiguration(config))
                {
                    marketConfigs[marketType] = config;
                    
                    // Update current if this is the active market
                    if (CurrentMarketConfig?.Symbol == config.Symbol)
                    {
                        CurrentMarketConfig = config;
                    }
                    
                    SaveConfiguration();
                    LogMessage($"Market configuration updated for {marketType}", LogLevel.Information);
                    
                    RaiseConfigurationEvent("MarketConfigUpdate", marketType, config.Symbol);
                }
                else
                {
                    LogMessage($"Invalid market configuration for {marketType}", LogLevel.Warning);
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Update market configuration failed: {ex.Message}", LogLevel.Error);
                FKS_ErrorHandler.HandleError(ex, $"FKS_Core.UpdateMarketConfiguration({marketType})");
            }
        }
        #endregion
        
        #region Enhanced Signal Management
        public static void PublishSignal(FKSSignal signal)
        {
            if (signal == null) return;
            
            try
            {
                var startTime = DateTime.Now;
                
                // Validate signal quality against current market configuration
                if (CurrentMarketConfig != null && signal.Quality < CurrentMarketConfig.SignalQualityThreshold)
                {
                    LogMessage($"Signal rejected - quality {signal.Quality:P} below threshold {CurrentMarketConfig.SignalQualityThreshold:P}", LogLevel.Debug);
                    RecordOperation("SignalRejected");
                    return;
                }
                
                // Commission optimization check
                if (CurrentMarketConfig != null && !IsSignalCommissionViable(signal))
                {
                    LogMessage($"Signal rejected - insufficient profit potential vs commission", LogLevel.Debug);
                    RecordOperation("SignalRejectedCommission");
                    return;
                }
                
                lock (stateUpdateLock)
                {
                    // Update trading state
                    CurrentTradingState.LastSignal = signal;
                    CurrentTradingState.LastSignalTime = DateTime.Now;
                    signal.Timestamp = DateTime.Now;
                }
                
                // Record metrics
                RecordOperation("PublishSignal");
                RecordPerformanceMetric("SignalQuality", signal.Quality);
                RecordPerformanceMetric("SignalProcessingTime", (DateTime.Now - startTime).TotalMilliseconds);
                
                // Raise event (throttled)
                RaiseSignalEvent(signal, "Signal published");
                
                LogMessage($"Signal published: {signal.Type} | Quality: {signal.Quality:P} | Setup: {signal.SetupNumber}", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"Signal publication failed: {ex.Message}", LogLevel.Error);
                FKS_ErrorHandler.HandleError(ex, "FKS_Core.PublishSignal");
            }
        }
        
        /// <summary>
        /// Publish signal with throttling to prevent spam
        /// </summary>
        public static void PublishSignalThrottled(FKSSignal signal)
        {
            if (signal == null) return;
            
            var eventType = typeof(SignalEventArgs);
            var now = DateTime.Now;
            
            if (lastEventTimes.ContainsKey(eventType))
            {
                var lastTime = lastEventTimes[eventType];
                if (now - lastTime < eventThrottleInterval)
                {
                    RecordOperation("SignalThrottled");
                    return; // Throttle signal
                }
            }
            
            lastEventTimes[eventType] = now;
            PublishSignal(signal);
        }
        
        /// <summary>
        /// Get signal statistics for performance analysis
        /// </summary>
        public static SignalStatistics GetSignalStatistics(TimeSpan? period = null)
        {
            period = period ?? TimeSpan.FromHours(24);
            
            try
            {
                lock (stateUpdateLock)
                {
                    // This would typically be implemented with a signal history collection
                    // For now, return basic statistics
                    return new SignalStatistics
                    {
                        Period = period.Value,
                        TotalSignals = (long)(performanceMetrics.TryGetValue("PublishSignal", out var pubSignal) ? pubSignal : 0),
                        RejectedSignals = (long)(performanceMetrics.TryGetValue("SignalRejected", out var rejSignal) ? rejSignal : 0),
                        AverageQuality = performanceMetrics.TryGetValue("SignalQuality", out var avgQual) ? avgQual : 0.5,
                        LastSignalTime = CurrentTradingState.LastSignalTime,
                        LastSignalQuality = CurrentTradingState.LastSignal?.Quality ?? 0
                    };
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Get signal statistics failed: {ex.Message}", LogLevel.Error);
                return new SignalStatistics { Period = period.Value };
            }
        }
        #endregion
        
        #region Enhanced Performance Tracking
        public static void RecordTrade(TradeResult trade)
        {
            if (trade == null) return;
            
            try
            {
                var startTime = DateTime.Now;
                
                lock (stateUpdateLock)
                {
                    // Update performance tracking
                    Performance.RecordTrade(trade);
                    
                    // Update trading state
                    CurrentTradingState.TradesToday++;
                    CurrentTradingState.DailyPnL += trade.PnL;
                    
                    // Update consecutive losses with enhanced tracking
                    if (trade.PnL < 0)
                    {
                        CurrentTradingState.ConsecutiveLosses++;
                        
                        // Track consecutive short losses separately (for commission optimization)
                        if (trade.Side == "Short")
                            CurrentTradingState.ConsecutiveShortLosses++;
                        else
                            CurrentTradingState.ConsecutiveShortLosses = 0;
                    }
                    else
                    {
                        CurrentTradingState.ConsecutiveLosses = 0;
                        CurrentTradingState.ConsecutiveShortLosses = 0;
                    }
                    
                    // Commission tracking
                    CurrentTradingState.DailyCommissions += CurrentMarketConfig?.Commission ?? 0;
                }
                
                // Record metrics
                RecordOperation("RecordTrade");
                RecordPerformanceMetric("TradeProcessingTime", (DateTime.Now - startTime).TotalMilliseconds);
                RecordPerformanceMetric("TradePnL", trade.PnL);
                RecordPerformanceMetric("TradeSignalQuality", trade.SignalQuality);
                
                // Record with infrastructure
                FKS_Infrastructure.RecordComponentActivity("FKS_Core", new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = "TradeRecording",
                    ExecutionTime = DateTime.Now - startTime
                });
                
                // Raise event
                RaiseTradeEvent(trade, "Trade recorded");
                
                LogMessage($"Trade recorded: {trade.Setup} | P&L: {trade.PnL:C} | Quality: {trade.SignalQuality:P}", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"Trade recording failed: {ex.Message}", LogLevel.Error);
                FKS_ErrorHandler.HandleError(ex, "FKS_Core.RecordTrade");
            }
        }
        
        public static void ResetDailyCounters()
        {
            try
            {
                lock (stateUpdateLock)
                {
                    CurrentTradingState.ResetDaily();
                    Performance.StartNewDay();
                    
                    // Reset daily metrics
                    var dailyMetrics = performanceMetrics.Keys
                        .Where(k => k.StartsWith("Daily"))
                        .ToList();
                    
                    foreach (var metric in dailyMetrics)
                    {
                        performanceMetrics[metric] = 0;
                    }
                }
                
                RecordOperation("ResetDailyCounters");
                LogMessage("Daily counters reset", LogLevel.Information);
                
                // Raise system event
                RaiseSystemEvent(SystemEventType.DailyReset, "Daily counters reset");
            }
            catch (Exception ex)
            {
                LogMessage($"Reset daily counters failed: {ex.Message}", LogLevel.Error);
                FKS_ErrorHandler.HandleError(ex, "FKS_Core.ResetDailyCounters");
            }
        }
        
        /// <summary>
        /// Get comprehensive performance report
        /// </summary>
        public static SystemPerformanceReport GetPerformanceReport(TimeSpan? period = null)
        {
            period = period ?? TimeSpan.FromHours(24);
            
            try
            {
                lock (stateUpdateLock)
                {
                    var report = new SystemPerformanceReport
                    {
                        Period = period.Value,
                        Timestamp = DateTime.Now,
                        SystemUptime = DateTime.Now - initializationTime,
                        TotalOperations = operationCounters.Values.Sum(),
                        ComponentCount = registeredComponents.Count,
                        HealthyComponents = componentHealth.Values.Count(h => h.IsHealthy),
                        ActiveCircuitBreakers = circuitBreakers.Values.Count(cb => cb.State != CircuitBreakerState.Closed),
                        
                        // Trading performance
                        TradingPerformance = new TradingPerformanceMetrics
                        {
                            TotalTrades = Performance.AllTrades.Count,
                            TodaysTrades = CurrentTradingState.TradesToday,
                            WinRate = Performance.WinRate,
                            TotalPnL = Performance.TotalPnL,
                            DailyPnL = CurrentTradingState.DailyPnL,
                            DailyCommissions = CurrentTradingState.DailyCommissions,
                            CommissionRatio = CalculateCommissionRatio(),
                            SharpeRatio = Performance.SharpeRatio,
                            MaxDrawdown = Performance.MaxDrawdown,
                            ConsecutiveLosses = CurrentTradingState.ConsecutiveLosses
                        },
                        
                        // System performance
                        SystemMetrics = performanceMetrics.ToDictionary(kvp => kvp.Key, kvp => kvp.Value),
                        OperationCounts = operationCounters.ToDictionary(kvp => kvp.Key, kvp => kvp.Value),
                        
                        // Component health
                        ComponentHealth = componentHealth.Values.ToList(),
                        
                        // Recommendations
                        Recommendations = GeneratePerformanceRecommendations()
                    };
                    
                    return report;
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Get performance report failed: {ex.Message}", LogLevel.Error);
                return new SystemPerformanceReport { Period = period.Value, Timestamp = DateTime.Now };
            }
        }
        #endregion
        
        #region Enhanced Health Monitoring
        public static Dictionary<string, ComponentHealth> GetComponentHealth()
        {
            try
            {
                var now = DateTime.Now;
                var healthCopy = new Dictionary<string, ComponentHealth>();
                
                // ConcurrentDictionary is thread-safe, no lock needed for enumeration
                foreach (var kvp in componentHealth)
                {
                    var health = kvp.Value.Clone(); // Create a copy to avoid modifying the original
                    
                    // Check for stale components
                    if ((now - health.LastUpdate).TotalMinutes > 5)
                    {
                        health.IsHealthy = false;
                        health.ErrorMessage = "No update in 5 minutes";
                        health.Status = ComponentStatus.Warning;
                    }
                    
                    // Check circuit breaker state
                    if (circuitBreakers.TryGetValue(kvp.Key, out var circuitBreaker))
                    {
                        if (circuitBreaker.State == CircuitBreakerState.Open)
                        {
                            health.IsHealthy = false;
                            health.Status = ComponentStatus.Error;
                            health.ErrorMessage = "Circuit breaker open";
                        }
                    }
                    
                    healthCopy[kvp.Key] = health;
                }
                
                RecordOperation("GetComponentHealth");
                return healthCopy;
            }
            catch (Exception ex)
            {
                LogMessage($"Get component health failed: {ex.Message}", LogLevel.Error);
                return new Dictionary<string, ComponentHealth>();
            }
        }
        
        public static bool IsSystemHealthy()
        {
            try
            {
                // No lock needed for reading from ConcurrentDictionary
                var systemHealth = CalculateSystemHealthScore();
                var isHealthy = systemHealth >= 0.7; // 70% threshold
                
                RecordOperation("IsSystemHealthy");
                RecordPerformanceMetric("SystemHealthScore", systemHealth);
                
                return isHealthy;
            }
            catch (Exception ex)
            {
                LogMessage($"System health check failed: {ex.Message}", LogLevel.Error);
                return false;
            }
        }
        
        /// <summary>
        /// Get detailed system health report
        /// </summary>
        public static SystemHealthReport GetSystemHealthReport()
        {
            try
            {
                var report = new SystemHealthReport
                {
                    Timestamp = DateTime.Now,
                    OverallHealthScore = CalculateSystemHealthScore(),
                    IsSystemHealthy = IsSystemHealthy(),
                    SystemUptime = DateTime.Now - initializationTime,
                    ComponentCount = registeredComponents.Count,
                    HealthyComponents = componentHealth.Values.Count(h => h.IsHealthy),
                    CriticalComponents = componentHealth.Values.Count(h => IsCriticalComponent(h.ComponentId)),
                    CircuitBreakerStats = GetCircuitBreakerStatistics(),
                    PerformanceMetrics = performanceMetrics.ToDictionary(kvp => kvp.Key, kvp => kvp.Value),
                    Alerts = GetActiveAlerts(),
                    Recommendations = GenerateHealthRecommendations()
                };
                
                return report;
            }
            catch (Exception ex)
            {
                LogMessage($"Get system health report failed: {ex.Message}", LogLevel.Error);
                return new SystemHealthReport { Timestamp = DateTime.Now };
            }
        }
        #endregion
        
        #region Circuit Breaker Implementation
        private static bool IsComponentSafeToUse(string componentId)
        {
            if (!circuitBreakers.TryGetValue(componentId, out var circuitBreaker))
                return true; // Unknown components are assumed safe
            
            try
            {
                switch (circuitBreaker.State)
                {
                    case CircuitBreakerState.Closed:
                        return true;
                        
                    case CircuitBreakerState.Open:
                        // Check if enough time has passed to try half-open
                        if (DateTime.Now - circuitBreaker.LastFailureTime > circuitBreaker.TimeoutPeriod)
                        {
                            circuitBreaker.State = CircuitBreakerState.HalfOpen;
                            LogMessage($"Circuit breaker half-open for {componentId}", LogLevel.Information);
                            return true;
                        }
                        return false;
                        
                    case CircuitBreakerState.HalfOpen:
                        return true; // Allow limited testing
                        
                    default:
                        return false;
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Circuit breaker check failed for {componentId}: {ex.Message}", LogLevel.Error);
                return false; // Err on the side of caution
            }
        }
        
        private static void RecordComponentError(string componentId, Exception error, string context)
        {
            try
            {
                // Update component health
                if (componentHealth.TryGetValue(componentId, out var health))
                {
                    health.IsHealthy = false;
                    health.LastUpdate = DateTime.Now;
                    health.ErrorMessage = error.Message;
                    health.Status = ComponentStatus.Error;
                }
                
                // Update circuit breaker
                if (circuitBreakers.TryGetValue(componentId, out var circuitBreaker))
                {
                    circuitBreaker.FailureCount++;
                    circuitBreaker.LastFailureTime = DateTime.Now;
                    
                    // Check if circuit should open
                    if (circuitBreaker.FailureCount >= circuitBreaker.FailureThreshold && 
                        circuitBreaker.State == CircuitBreakerState.Closed)
                    {
                        circuitBreaker.State = CircuitBreakerState.Open;
                        LogMessage($"Circuit breaker opened for {componentId} due to repeated failures", LogLevel.Warning);
                        
                        // Raise circuit breaker event
                        RaiseCircuitBreakerEvent(componentId, CircuitBreakerState.Open, error.Message);
                    }
                }
                
                // Record with infrastructure
                FKS_Infrastructure.RecordComponentError(componentId, error, context);
                
                LogMessage($"Component error recorded for {componentId}: {error.Message} (Context: {context})", LogLevel.Error);
                RecordOperation("ComponentError");
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to record component error for {componentId}: {ex.Message}", LogLevel.Error);
            }
        }
        
        private static void RecordComponentAccess(string componentId)
        {
            try
            {
                // Update component health on successful access
                if (componentHealth.TryGetValue(componentId, out var health))
                {
                    health.LastUpdate = DateTime.Now;
                    health.AccessCount++;
                    
                    // Reset circuit breaker on successful access
                    if (circuitBreakers.TryGetValue(componentId, out var circuitBreaker))
                    {
                        if (circuitBreaker.State == CircuitBreakerState.HalfOpen)
                        {
                            circuitBreaker.State = CircuitBreakerState.Closed;
                            circuitBreaker.FailureCount = 0;
                            LogMessage($"Circuit breaker closed for {componentId}", LogLevel.Information);
                            
                            // Record recovery with infrastructure
                            FKS_Infrastructure.RecordComponentRecovery(componentId);
                        }
                    }
                    
                    if (!health.IsHealthy && health.Status != ComponentStatus.Error)
                    {
                        health.IsHealthy = true;
                        health.Status = ComponentStatus.Healthy;
                        health.ErrorMessage = null;
                    }
                }
                
                // Update metrics
                if (componentMetrics.TryGetValue(componentId, out var metrics))
                {
                    metrics.TotalAccesses++;
                    metrics.LastAccess = DateTime.Now;
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to record component access for {componentId}: {ex.Message}", LogLevel.Warning);
            }
        }
        #endregion
        
        #region Configuration Management
        public static void SaveConfiguration()
        {
            try
            {
                // Skip saving if no configuration file path is set
                if (string.IsNullOrEmpty(configFilePath))
                {
                    LogMessage("Configuration file path not set, skipping save", LogLevel.Debug);
                    return;
                }
                
                var config = new FKSConfiguration
                {
                    CurrentMarket = CurrentMarketConfig?.Symbol ?? "DEFAULT",
                    MarketConfigurations = marketConfigs?.ToDictionary(kvp => kvp.Key, kvp => kvp.Value) ?? new Dictionary<string, MarketConfiguration>(),
                    LastUpdate = DateTime.Now,
                    Version = "3.0.0"
                };
                
                // Validate configuration before saving
                if (config.MarketConfigurations == null)
                {
                    config.MarketConfigurations = new Dictionary<string, MarketConfiguration>();
                }
                
                // Simple XML serialization with better error handling
                var serializer = new XmlSerializer(typeof(FKSConfiguration));
                
                // Ensure directory exists
                var directory = Path.GetDirectoryName(configFilePath);
                if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
                {
                    Directory.CreateDirectory(directory);
                }
                
                // Use a temporary file to avoid corruption
                var tempPath = configFilePath + ".tmp";
                
                using (var writer = new StreamWriter(tempPath))
                {
                    serializer.Serialize(writer, config);
                }
                
                // Replace original file with temp file
                if (File.Exists(configFilePath))
                {
                    File.Delete(configFilePath);
                }
                File.Move(tempPath, configFilePath);
                
                lastConfigUpdate = DateTime.Now;
                
                LogMessage("Configuration saved successfully", LogLevel.Debug);
                RecordOperation("SaveConfiguration");
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to save configuration: {ex.Message}", LogLevel.Error);
                FKS_ErrorHandler.HandleError(ex, "FKS_Core.SaveConfiguration");
                
                // Clean up temp file if it exists
                try
                {
                    var tempPath = configFilePath + ".tmp";
                    if (File.Exists(tempPath))
                    {
                        File.Delete(tempPath);
                    }
                }
                catch { /* Ignore cleanup errors */ }
            }
        }
        
        public static void LoadConfiguration()
        {
            try
            {
                if (string.IsNullOrEmpty(configFilePath))
                {
                    LogMessage("Configuration file path not set, using defaults", LogLevel.Information);
                    return;
                }
                
                if (!File.Exists(configFilePath))
                {
                    LogMessage("No configuration file found, using defaults", LogLevel.Information);
                    return;
                }
                
                var serializer = new XmlSerializer(typeof(FKSConfiguration));
                FKSConfiguration config;
                
                using (var reader = new StreamReader(configFilePath))
                {
                    config = (FKSConfiguration)serializer.Deserialize(reader);
                }
                
                if (config != null)
                {
                    // Load market configurations with null checking
                    if (config.MarketConfigurations != null)
                    {
                        foreach (var kvp in config.MarketConfigurations)
                        {
                            if (kvp.Value != null && ValidateMarketConfiguration(kvp.Value))
                            {
                                marketConfigs[kvp.Key] = kvp.Value;
                            }
                        }
                    }
                    
                    // Set current market
                    if (!string.IsNullOrEmpty(config.CurrentMarket) && 
                        marketConfigs.ContainsKey(config.CurrentMarket))
                    {
                        CurrentMarketConfig = marketConfigs[config.CurrentMarket];
                    }
                    
                    lastConfigUpdate = config.LastUpdate;
                    LogMessage($"Configuration loaded successfully (Version: {config.Version})", LogLevel.Information);
                }
                
                RecordOperation("LoadConfiguration");
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to load configuration: {ex.Message}", LogLevel.Warning);
                FKS_ErrorHandler.HandleError(ex, "FKS_Core.LoadConfiguration");
                // Don't throw - use defaults and continue
            }
        }
        
        private static void CheckConfigurationChanges(object state)
        {
            if (isShuttingDown) return;
            
            try
            {
                if (File.Exists(configFilePath))
                {
                    var lastWrite = File.GetLastWriteTime(configFilePath);
                    if (lastWrite > lastConfigUpdate)
                    {
                        LogMessage("Configuration file changed, reloading...", LogLevel.Information);
                        LoadConfiguration();
                        
                        RaiseConfigurationEvent("ConfigReload", "File", "Auto-reload");
                    }
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Configuration change check failed: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static bool ValidateMarketConfiguration(MarketConfiguration config)
        {
            if (config == null) return false;
            
            return !string.IsNullOrEmpty(config.Symbol) &&
                   config.TickSize > 0 &&
                   config.TickValue > 0 &&
                   config.DefaultContracts > 0 &&
                   config.MaxContracts > 0 &&
                   config.SignalQualityThreshold >= 0 && config.SignalQualityThreshold <= 1;
        }
        #endregion
        
        #region Event Management
        private static void ProcessEventQueue(object state)
        {
            if (isShuttingDown) return;
            
            try
            {
                var processedCount = 0;
                var maxProcessing = 50; // Limit processing per cycle
                
                while (eventQueue.TryDequeue(out var eventInfo) && processedCount < maxProcessing)
                {
                    try
                    {
                        switch (eventInfo.EventType)
                        {
                            case "Signal":
                                SignalGenerated?.Invoke(null, eventInfo.EventArgs as SignalEventArgs);
                                break;
                            case "Trade":
                                TradeExecuted?.Invoke(null, eventInfo.EventArgs as TradeEventArgs);
                                break;
                            case "Component":
                                ComponentStatusChanged?.Invoke(null, eventInfo.EventArgs as ComponentEventArgs);
                                break;
                            case "Market":
                                MarketRegimeChanged?.Invoke(null, eventInfo.EventArgs as MarketEventArgs);
                                break;
                            case "System":
                                SystemHealthChanged?.Invoke(null, eventInfo.EventArgs as SystemEventArgs);
                                break;
                            case "Configuration":
                                ConfigurationChanged?.Invoke(null, eventInfo.EventArgs as ConfigurationEventArgs);
                                break;
                            case "CircuitBreaker":
                                CircuitBreakerTriggered?.Invoke(null, eventInfo.EventArgs as CircuitBreakerEventArgs);
                                break;
                        }
                        
                        processedCount++;
                    }
                    catch (Exception ex)
                    {
                        LogMessage($"Event processing error: {ex.Message}", LogLevel.Warning);
                    }
                }
                
                if (processedCount > 0)
                {
                    RecordPerformanceMetric("EventsProcessed", processedCount);
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Event queue processing failed: {ex.Message}", LogLevel.Error);
            }
        }
        
        private static void RaiseSignalEvent(FKSSignal signal, string description)
        {
            try
            {
                var eventArgs = new SignalEventArgs { Signal = signal, Description = description };
                var eventInfo = new EventInfo { EventType = "Signal", EventArgs = eventArgs, Timestamp = DateTime.Now };
                eventQueue.Enqueue(eventInfo);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to raise signal event: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void RaiseTradeEvent(TradeResult trade, string description)
        {
            try
            {
                var eventArgs = new TradeEventArgs { Trade = trade, Description = description };
                var eventInfo = new EventInfo { EventType = "Trade", EventArgs = eventArgs, Timestamp = DateTime.Now };
                eventQueue.Enqueue(eventInfo);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to raise trade event: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void RaiseComponentEvent(string componentId, ComponentStatus status, string description)
        {
            try
            {
                var eventArgs = new ComponentEventArgs 
                { 
                    ComponentId = componentId, 
                    Status = status, 
                    Description = description 
                };
                var eventInfo = new EventInfo { EventType = "Component", EventArgs = eventArgs, Timestamp = DateTime.Now };
                eventQueue.Enqueue(eventInfo);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to raise component event: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void RaiseMarketEvent(string previousRegime, string newRegime, string description)
        {
            try
            {
                var eventArgs = new MarketEventArgs 
                { 
                    PreviousRegime = previousRegime, 
                    NewRegime = newRegime,
                    Description = description
                };
                var eventInfo = new EventInfo { EventType = "Market", EventArgs = eventArgs, Timestamp = DateTime.Now };
                eventQueue.Enqueue(eventInfo);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to raise market event: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void RaiseSystemEvent(SystemEventType eventType, string description)
        {
            try
            {
                var eventArgs = new SystemEventArgs 
                { 
                    EventType = eventType, 
                    Description = description,
                    Timestamp = DateTime.Now
                };
                var eventInfo = new EventInfo { EventType = "System", EventArgs = eventArgs, Timestamp = DateTime.Now };
                eventQueue.Enqueue(eventInfo);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to raise system event: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void RaiseConfigurationEvent(string changeType, string oldValue, string newValue)
        {
            try
            {
                var eventArgs = new ConfigurationEventArgs 
                { 
                    ChangeType = changeType, 
                    OldValue = oldValue, 
                    NewValue = newValue 
                };
                var eventInfo = new EventInfo { EventType = "Configuration", EventArgs = eventArgs, Timestamp = DateTime.Now };
                eventQueue.Enqueue(eventInfo);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to raise configuration event: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void RaiseCircuitBreakerEvent(string componentId, CircuitBreakerState state, string reason)
        {
            try
            {
                var eventArgs = new CircuitBreakerEventArgs 
                { 
                    ComponentId = componentId, 
                    State = state, 
                    Reason = reason 
                };
                var eventInfo = new EventInfo { EventType = "CircuitBreaker", EventArgs = eventArgs, Timestamp = DateTime.Now };
                eventQueue.Enqueue(eventInfo);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to raise circuit breaker event: {ex.Message}", LogLevel.Warning);
            }
        }
        #endregion
        
        #region Monitoring and Metrics
        private static void CollectMetrics(object state)
        {
            if (isShuttingDown) return;
            
            try
            {
                var collectionStart = DateTime.Now;
                
                // Record system metrics
                RecordPerformanceMetric("SystemUptime", (DateTime.Now - initializationTime).TotalHours);
                RecordPerformanceMetric("ComponentCount", registeredComponents.Count);
                RecordPerformanceMetric("HealthyComponentCount", componentHealth.Values.Count(h => h.IsHealthy));
                RecordPerformanceMetric("OpenCircuitBreakers", circuitBreakers.Values.Count(cb => cb.State == CircuitBreakerState.Open));
                
                // Enhanced memory metrics
                var process = System.Diagnostics.Process.GetCurrentProcess();
                var memoryUsage = GC.GetTotalMemory(false);
                var workingSet = process.WorkingSet64;
                var privateMemory = process.PrivateMemorySize64;
                var gen0Collections = GC.CollectionCount(0);
                var gen1Collections = GC.CollectionCount(1);
                var gen2Collections = GC.CollectionCount(2);
                
                RecordPerformanceMetric("MemoryUsage", memoryUsage);
                RecordPerformanceMetric("WorkingSet", workingSet);
                RecordPerformanceMetric("PrivateMemory", privateMemory);
                RecordPerformanceMetric("Gen0Collections", gen0Collections);
                RecordPerformanceMetric("Gen1Collections", gen1Collections);
                RecordPerformanceMetric("Gen2Collections", gen2Collections);
                
                // Component-specific metrics
                foreach (var kvp in componentMetrics)
                {
                    var componentId = kvp.Key;
                    var metrics = kvp.Value;
                    
                    // Calculate access frequency
                    var timeSinceRegistration = DateTime.Now - metrics.RegistrationTime;
                    var accessFrequency = timeSinceRegistration.TotalSeconds > 0 
                        ? metrics.TotalAccesses / timeSinceRegistration.TotalSeconds 
                        : 0;
                    
                    RecordPerformanceMetric($"Component_{componentId}_AccessFrequency", accessFrequency);
                    RecordPerformanceMetric($"Component_{componentId}_TotalAccesses", metrics.TotalAccesses);
                    
                    // Component health score
                    if (componentHealth.TryGetValue(componentId, out var health))
                    {
                        var healthScore = health.IsHealthy ? 1.0 : 0.0;
                        if (health.Status == ComponentStatus.Warning) healthScore = 0.5;
                        RecordPerformanceMetric($"Component_{componentId}_HealthScore", healthScore);
                    }
                }
                
                // Trading metrics
                RecordPerformanceMetric("TradesToday", CurrentTradingState.TradesToday);
                RecordPerformanceMetric("DailyPnL", CurrentTradingState.DailyPnL);
                RecordPerformanceMetric("DailyCommissions", CurrentTradingState.DailyCommissions);
                RecordPerformanceMetric("ConsecutiveLosses", CurrentTradingState.ConsecutiveLosses);
                
                // Event queue metrics
                RecordPerformanceMetric("EventQueueSize", eventQueue.Count);
                RecordPerformanceMetric("LastEventThrottleCount", lastEventTimes.Count);
                
                // Operation counter metrics
                var topOperations = operationCounters
                    .OrderByDescending(kvp => kvp.Value)
                    .Take(10);
                
                foreach (var op in topOperations)
                {
                    RecordPerformanceMetric($"Operation_{op.Key}", op.Value);
                }
                
                // Collection performance
                var collectionTime = (DateTime.Now - collectionStart).TotalMilliseconds;
                RecordPerformanceMetric("MetricsCollectionTime", collectionTime);
                
                // Prune old metrics if needed
                if (performanceMetrics.Count > 1000)
                {
                    PruneOldMetrics();
                }
                
                // Record activity with infrastructure
                FKS_Infrastructure.RecordComponentActivity("FKS_Core", new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = "MetricsCollection",
                    ExecutionTime = TimeSpan.FromMilliseconds(collectionTime),
                    MemoryUsage = memoryUsage
                });
            }
            catch (Exception ex)
            {
                LogMessage($"Metrics collection failed: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void MonitorSystemHealth(object state)
        {
            if (isShuttingDown) return;
            
            try
            {
                var healthScore = CalculateSystemHealthScore();
                var wasHealthy = (performanceMetrics.TryGetValue("PreviousHealthScore", out var prevScore) ? prevScore : 1.0) >= 0.7;
                var isHealthy = healthScore >= 0.7;
                
                if (wasHealthy != isHealthy)
                {
                    var eventType = isHealthy ? SystemEventType.HealthRestored : SystemEventType.HealthDegraded;
                    RaiseSystemEvent(eventType, $"System health changed: {healthScore:P1}");
                }
                
                performanceMetrics["PreviousHealthScore"] = healthScore;
                RecordPerformanceMetric("SystemHealthScore", healthScore);
            }
            catch (Exception ex)
            {
                LogMessage($"System health monitoring failed: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void MonitorMemoryUsage(object state)
        {
            if (isShuttingDown) return;
            
            try
            {
                // Get current memory usage
                var currentMemory = GC.GetTotalMemory(false);
                var memoryDiff = currentMemory - lastMemoryUsage;
                
                // Check if memory usage exceeds threshold
                if (currentMemory > MAX_MEMORY_THRESHOLD)
                {
                    memoryWarningCount++;
                    
                    if (memoryWarningCount >= 5) // Five consecutive warnings for higher threshold
                    {
                        // Force garbage collection
                        GC.Collect(2, GCCollectionMode.Forced);
                        GC.WaitForPendingFinalizers();
                        GC.Collect(2, GCCollectionMode.Forced);
                        
                        // Clear old metrics to free memory
                        ClearOldMetrics();
                        
                        LogMessage($"Memory cleanup performed. Usage: {currentMemory / 1024 / 1024:F1} MB", LogLevel.Warning);
                        memoryWarningCount = 0;
                    }
                    else
                    {
                        LogMessage($"Memory threshold exceeded: {currentMemory / 1024 / 1024:F1} MB", LogLevel.Warning);
                    }
                }
                else if (currentMemory > CLEANUP_THRESHOLD)
                {
                    // Gentle cleanup at 512MB
                    if (memoryWarningCount == 0) // Only log once per cycle
                    {
                        LogMessage($"Memory usage high: {currentMemory / 1024 / 1024:F1} MB - performing gentle cleanup", LogLevel.Information);
                        ClearOldMetrics();
                    }
                    memoryWarningCount = 1;
                }
                else
                {
                    memoryWarningCount = 0;
                }
                
                // Update memory metrics
                lastMemoryUsage = currentMemory;
                RecordPerformanceMetric("MemoryUsage", currentMemory);
                RecordPerformanceMetric("MemoryDelta", memoryDiff);
            }
            catch (Exception ex)
            {
                LogMessage($"Memory monitoring failed: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void ClearOldMetrics()
        {
            try
            {
                // Clear old operation counters (keep only recent ones)
                var oldKeys = operationCounters.Keys.ToList();
                foreach (var key in oldKeys.Take(oldKeys.Count / 2))
                {
                    operationCounters.TryRemove(key, out _);
                }
                
                // Clear old performance metrics
                var metricsKeys = performanceMetrics.Keys.ToList();
                foreach (var key in metricsKeys.Take(metricsKeys.Count / 2))
                {
                    performanceMetrics.TryRemove(key, out _);
                }
                
                // Clear old health data
                var healthKeys = componentHealth.Keys.ToList();
                foreach (var key in healthKeys)
                {
                    if (componentHealth.TryGetValue(key, out var health))
                    {
                        if (health.LastUpdate < DateTime.Now.AddMinutes(-5))
                        {
                            componentHealth.TryRemove(key, out _);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to clear old metrics: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void PruneOldMetrics()
        {
            try
            {
                var now = DateTime.Now;
                var pruneThreshold = TimeSpan.FromHours(1); // Keep only last hour of detailed metrics
                
                // Prune component-specific metrics
                var componentMetricsKeys = performanceMetrics.Keys
                    .Where(k => k.StartsWith("Component_"))
                    .ToList();
                
                // Keep only the most recent component metrics
                var componentsToKeep = componentMetrics.Keys.ToHashSet();
                foreach (var key in componentMetricsKeys)
                {
                    var parts = key.Split('_');
                    if (parts.Length >= 2)
                    {
                        var componentId = parts[1];
                        if (!componentsToKeep.Contains(componentId))
                        {
                            performanceMetrics.TryRemove(key, out _);
                        }
                    }
                }
                
                // Prune operation metrics - keep only top 20
                var operationKeys = performanceMetrics.Keys
                    .Where(k => k.StartsWith("Operation_"))
                    .ToList();
                
                if (operationKeys.Count > 20)
                {
                    var keysToRemove = operationKeys
                        .OrderBy(k => performanceMetrics.TryGetValue(k, out var val) ? val : 0)
                        .Take(operationKeys.Count - 20);
                    
                    foreach (var key in keysToRemove)
                    {
                        performanceMetrics.TryRemove(key, out _);
                    }
                }
                
                // Prune event throttle times older than 1 minute
                var oldEventTimes = lastEventTimes
                    .Where(kvp => now - kvp.Value > TimeSpan.FromMinutes(1))
                    .Select(kvp => kvp.Key)
                    .ToList();
                
                foreach (var eventType in oldEventTimes)
                {
                    lastEventTimes.TryRemove(eventType, out _);
                }
                
                // Compact operation counters
                if (operationCounters.Count > 100)
                {
                    var leastUsedOperations = operationCounters
                        .OrderBy(kvp => kvp.Value)
                        .Take(operationCounters.Count - 50)
                        .Select(kvp => kvp.Key)
                        .ToList();
                    
                    foreach (var op in leastUsedOperations)
                    {
                        operationCounters.TryRemove(op, out _);
                    }
                }
                
                RecordOperation("PruneOldMetrics");
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to prune old metrics: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static void RecordOperation(string operationName)
        {
            try
            {
                operationCounters.AddOrUpdate(operationName, 1, (key, value) => value + 1);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to record operation {operationName}: {ex.Message}", LogLevel.Warning);
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
                LogMessage($"Failed to record metric {metricName}: {ex.Message}", LogLevel.Warning);
            }
        }
        #endregion
        
        #region Infrastructure Event Handlers
        private static void OnInfrastructureComponentError(string componentId, Exception error, string context)
        {
            LogMessage($"Infrastructure reported error for {componentId}: {error.Message}", LogLevel.Warning);
            RecordComponentError(componentId, error, context);
        }
        
        private static void OnInfrastructureCriticalAlert(List<FKS_Infrastructure.SystemAlert> alerts)
        {
            foreach (var alert in alerts)
            {
                LogMessage($"Critical alert: {alert.Message} ({alert.Component})", LogLevel.Error);
            }
            
            RaiseSystemEvent(SystemEventType.CriticalAlert, $"{alerts.Count} critical alerts raised");
        }
        #endregion
        
        #region Utility Methods
        private static double CalculateSystemHealthScore()
        {
            try
            {
                if (!componentHealth.Any()) return 1.0;
                
                double totalScore = 0;
                int componentCount = 0;
                
                foreach (var health in componentHealth.Values)
                {
                    double componentScore = health.Status switch
                    {
                        ComponentStatus.Healthy => 1.0,
                        ComponentStatus.Warning => 0.6,
                        ComponentStatus.Error => 0.2,
                        _ => 0.5
                    };
                    
                    // Weight critical components more heavily
                    if (IsCriticalComponent(health.ComponentId))
                    {
                        componentScore *= 2;
                        componentCount += 2;
                    }
                    else
                    {
                        componentCount++;
                    }
                    
                    totalScore += componentScore;
                }
                
                return componentCount > 0 ? totalScore / componentCount : 1.0;
            }
            catch
            {
                return 0.5; // Default to neutral health
            }
        }
        
        private static bool IsCriticalComponent(string componentId)
        {
            var criticalComponents = new[] { "FKS_AI", "FKS_AO", "FKS_Dashboard", "FKS_Core" };
            return criticalComponents.Contains(componentId);
        }
        
        private static double CalculateCommissionRatio()
        {
            lock (stateUpdateLock)
            {
                var grossPnL = CurrentTradingState.DailyPnL + CurrentTradingState.DailyCommissions;
                return grossPnL > 0 ? CurrentTradingState.DailyCommissions / grossPnL : 0;
            }
        }
        
        private static bool IsSignalCommissionViable(FKSSignal signal)
        {
            if (CurrentMarketConfig == null) return true;
            
            try
            {
                // Estimate expected profit based on signal quality and setup
                double expectedProfit = CurrentMarketConfig.MinProfitTarget * CurrentMarketConfig.TickValue * signal.Quality;
                double commission = CurrentMarketConfig.Commission;
                
                // Require at least 2x commission in expected profit
                return expectedProfit >= commission * 2;
            }
            catch
            {
                return true; // Default to allowing signal
            }
        }
        
        private static void ApplyRegimeBasedConfiguration(string regime)
        {
            try
            {
                if (CurrentMarketConfig == null) return;
                
                // Adjust thresholds based on market regime
                switch (regime)
                {
                    case "TRENDING_BULL":
                    case "TRENDING_BEAR":
                        // Reduce quality threshold slightly in strong trends
                        // This would be implemented as temporary adjustments
                        break;
                    case "VOLATILE":
                        // Increase quality threshold in volatile markets
                        break;
                    case "RANGING":
                        // Adjust for range-bound conditions
                        break;
                }
                
                LogMessage($"Applied regime-based configuration for {regime}", LogLevel.Debug);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to apply regime-based configuration: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private static MarketConfiguration CreateDefaultMarketConfig()
        {
            return new MarketConfiguration
            {
                Symbol = "DEFAULT",
                TickSize = 0.25,
                TickValue = 12.50,
                DefaultContracts = 1,
                MaxContracts = 1,
                ATRStopMultiplier = 2.0,
                ATRTargetMultiplier = 3.0,
                SignalQualityThreshold = 0.70,
                OptimalSessionStart = 9,
                OptimalSessionEnd = 15,
                MinWaveRatio = 1.5,
                VolumeThreshold = 1.2,
                Commission = 5.0,
                MinProfitTarget = 10,
                SessionOptimized = true
            };
        }
        
        private static CircuitBreakerStatistics GetCircuitBreakerStatistics()
        {
            try
            {
                var stats = new CircuitBreakerStatistics
                {
                    TotalCircuitBreakers = circuitBreakers.Count,
                    OpenCircuitBreakers = circuitBreakers.Values.Count(cb => cb.State == CircuitBreakerState.Open),
                    HalfOpenCircuitBreakers = circuitBreakers.Values.Count(cb => cb.State == CircuitBreakerState.HalfOpen),
                    ClosedCircuitBreakers = circuitBreakers.Values.Count(cb => cb.State == CircuitBreakerState.Closed)
                };
                
                return stats;
            }
            catch
            {
                return new CircuitBreakerStatistics();
            }
        }
        
        private static List<SystemAlert> GetActiveAlerts()
        {
            var alerts = new List<SystemAlert>();
            
            try
            {
                // Check for unhealthy critical components
                var criticalComponents = new[] { "FKS_AI", "FKS_AO", "FKS_Dashboard" };
                foreach (var componentId in criticalComponents)
                {
                    if (componentHealth.TryGetValue(componentId, out var health) && !health.IsHealthy)
                    {
                        alerts.Add(new SystemAlert
                        {
                            Level = AlertLevel.Critical,
                            Component = componentId,
                            Message = $"Critical component {componentId} is unhealthy",
                            Timestamp = DateTime.Now
                        });
                    }
                }
                
                // Check for open circuit breakers
                foreach (var kvp in circuitBreakers.Where(cb => cb.Value.State == CircuitBreakerState.Open))
                {
                    alerts.Add(new SystemAlert
                    {
                        Level = AlertLevel.Warning,
                        Component = kvp.Key,
                        Message = $"Circuit breaker open for {kvp.Key}",
                        Timestamp = kvp.Value.LastFailureTime
                    });
                }
                
                // Check commission ratio
                var commissionRatio = CalculateCommissionRatio();
                if (commissionRatio > 0.15)
                {
                    alerts.Add(new SystemAlert
                    {
                        Level = AlertLevel.Warning,
                        Component = "Trading",
                        Message = $"High commission ratio: {commissionRatio:P1}",
                        Timestamp = DateTime.Now
                    });
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to get active alerts: {ex.Message}", LogLevel.Warning);
            }
            
            return alerts;
        }
        
        private static List<string> GeneratePerformanceRecommendations()
        {
            var recommendations = new List<string>();
            
            try
            {
                // Commission optimization recommendations
                var commissionRatio = CalculateCommissionRatio();
                if (commissionRatio > 0.20)
                {
                    recommendations.Add("Commission ratio is high - consider increasing signal quality thresholds");
                }
                
                // Component health recommendations
                var unhealthyCount = componentHealth.Values.Count(h => !h.IsHealthy);
                if (unhealthyCount > 0)
                {
                    recommendations.Add($"{unhealthyCount} unhealthy components detected - investigate and restart if needed");
                }
                
                // Circuit breaker recommendations
                var openCircuitBreakers = circuitBreakers.Values.Count(cb => cb.State == CircuitBreakerState.Open);
                if (openCircuitBreakers > 0)
                {
                    recommendations.Add($"{openCircuitBreakers} circuit breakers open - check component stability");
                }
                
                // System health recommendations
                var healthScore = CalculateSystemHealthScore();
                if (healthScore < 0.7)
                {
                    recommendations.Add("System health below optimal - check critical components and consider restart");
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to generate performance recommendations: {ex.Message}", LogLevel.Warning);
            }
            
            return recommendations;
        }
        
        private static List<string> GenerateHealthRecommendations()
        {
            var recommendations = new List<string>();
            
            try
            {
                // Analyze component health patterns
                var criticalUnhealthy = componentHealth.Values
                    .Where(h => IsCriticalComponent(h.ComponentId) && !h.IsHealthy)
                    .ToList();
                
                if (criticalUnhealthy.Any())
                {
                    recommendations.Add("Critical components are unhealthy - immediate attention required");
                    recommendations.Add("Check logs for errors and consider component restart");
                }
                
                // Memory usage recommendations
                var memoryUsage = performanceMetrics.TryGetValue("MemoryUsage", out var memUsage) ? memUsage : 0;
                if (memoryUsage > 500 * 1024 * 1024) // 500MB
                {
                    recommendations.Add("High memory usage detected - consider optimization or restart");
                }
                
                // Performance recommendations
                var healthScore = CalculateSystemHealthScore();
                if (healthScore < 0.8)
                {
                    recommendations.Add("System performance below optimal - consider maintenance");
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to generate health recommendations: {ex.Message}", LogLevel.Warning);
            }
            
            return recommendations;
        }
        
        private static void LogMessage(string message, LogLevel level)
        {
            try
            {
                // Rate limiting to prevent excessive logging
                if (level == LogLevel.Debug && lastDebugLogTime.AddSeconds(1) > DateTime.Now)
                    return;
                
                if (level == LogLevel.Debug)
                    lastDebugLogTime = DateTime.Now;
                
                var logEntry = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] [{level}] FKS_Core: {message}";
                
                // Only log critical messages to reduce memory usage
                switch (level)
                {
                    case LogLevel.Error:
                        NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab1);
                        break;
                    case LogLevel.Warning:
                        // Limit warning frequency
                        if (lastWarningLogTime.AddSeconds(5) <= DateTime.Now)
                        {
                            NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab1);
                            lastWarningLogTime = DateTime.Now;
                        }
                        break;
                    case LogLevel.Information:
                        // Limit info frequency
                        if (lastInfoLogTime.AddSeconds(10) <= DateTime.Now)
                        {
                            NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab2);
                            lastInfoLogTime = DateTime.Now;
                        }
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
        
        private static DateTime lastDebugLogTime = DateTime.MinValue;
        private static DateTime lastWarningLogTime = DateTime.MinValue;
        private static DateTime lastInfoLogTime = DateTime.MinValue;
        
        private static void OnApplicationShutdown(object sender, EventArgs e)
        {
            Shutdown();
        }
        
        public static void Shutdown()
        {
            if (isShuttingDown) return;
            
            try
            {
                isShuttingDown = true;
                LogMessage("FKS Core shutdown initiated", LogLevel.Information);
                
                // Dispose timers first to prevent further processing
                configWatcher?.Dispose();
                eventProcessor?.Dispose();
                metricsCollector?.Dispose();
                healthMonitor?.Dispose();
                memoryMonitor?.Dispose();
                
                // Shutdown all components WITHOUT using locks to prevent deadlock
                var components = registeredComponents.Values.ToList();
                foreach (var component in components)
                {
                    try
                    {
                        component.Shutdown();
                    }
                    catch (Exception ex)
                    {
                        LogMessage($"Component shutdown error: {ex.Message}", LogLevel.Warning);
                    }
                }
                
                // Save configuration
                SaveConfiguration();
                
                // Unregister from infrastructure asynchronously to prevent deadlock
                Task.Run(() =>
                {
                    try
                    {
                        FKS_Infrastructure.UnregisterComponent("FKS_Core");
                        FKS_Infrastructure.OnComponentError -= OnInfrastructureComponentError;
                        // Disabled to prevent spam for missing optional components
                        // FKS_Infrastructure.OnCriticalAlertRaised -= OnInfrastructureCriticalAlert;
                    }
                    catch (Exception ex)
                    {
                        LogMessage($"Infrastructure unregistration error: {ex.Message}", LogLevel.Warning);
                    }
                });
                
                // Clear collections
                registeredComponents.Clear();
                componentHealth.Clear();
                circuitBreakers.Clear();
                componentMetrics.Clear();
                operationCounters.Clear();
                performanceMetrics.Clear();
                
                // Clear event queue
                while (eventQueue.TryDequeue(out _)) { }
                
                // Dispose locks
                rwLock?.Dispose();
                
                LogMessage("FKS Core shutdown completed", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"Error during shutdown: {ex.Message}", LogLevel.Error);
            }
        }
        #endregion
        
        #region Supporting Classes and Enums (Enhanced)
        
        // Preserve all existing interfaces and classes for backward compatibility
        public interface IFKSComponent
        {
            string ComponentId { get; }
            string Version { get; }
            void Initialize();
            void Shutdown();
        }
        
        [Serializable]
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
            
            // Enhanced properties for commission optimization
            public double Commission { get; set; } = 5.0;
            public int MinProfitTarget { get; set; } = 10; // Minimum ticks
            public bool SessionOptimized { get; set; } = true;
            public DateTime LastUpdate { get; set; } = DateTime.UtcNow;
            
            public MarketConfiguration()
            {
                Symbol = "DEFAULT";
                TickSize = 0.1;
                TickValue = 10.0;
                DefaultContracts = 1;
                MaxContracts = 4;
                ATRStopMultiplier = 1.8;
                ATRTargetMultiplier = 2.2;
                SignalQualityThreshold = 0.72;
                OptimalSessionStart = 6;
                OptimalSessionEnd = 15;
                MinWaveRatio = 1.5;
                VolumeThreshold = 1.35;
                Commission = 5.0;
                MinProfitTarget = 10;
                SessionOptimized = true;
            }
        }
        
        [Serializable]
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
            
            // Enhanced properties
            public double TrendStrength { get; set; }
            public string VolatilityRegime { get; set; } = "NORMAL";
            public double MomentumScore { get; set; }
        }
        
        [Serializable]
        public class TradingState
        {
            public int TradesToday { get; set; }
            public double DailyPnL { get; set; }
            public int ConsecutiveLosses { get; set; }
            public FKSSignal LastSignal { get; set; }
            public DateTime LastSignalTime { get; set; }
            public bool TradingEnabled { get; set; } = true;
            
            // Enhanced properties for commission optimization
            public double DailyCommissions { get; set; }
            public int ConsecutiveShortLosses { get; set; }
            public int MaxDailyTrades { get; set; } = 6;
            public double DailyProfitTarget { get; set; } = 2500;
            public double DailyLossLimit { get; set; } = 1200;
            
            public void ResetDaily()
            {
                TradesToday = 0;
                DailyPnL = 0;
                DailyCommissions = 0;
                ConsecutiveLosses = 0;
                ConsecutiveShortLosses = 0;
                TradingEnabled = true;
            }
        }
        
        [Serializable]
        public class FKSSignal
        {
            public string Type { get; set; } // G, Top, ^, v
            public double Quality { get; set; }
            public string Source { get; set; } // Add missing Source property
            public double WaveRatio { get; set; }
            public int SetupNumber { get; set; }
            public int RecommendedContracts { get; set; }
            public DateTime Timestamp { get; set; } = DateTime.Now;
            
            // Enhanced properties
            public double Confidence { get; set; }
            public string MarketRegime { get; set; }
            public double ExpectedProfit { get; set; }
            public double RiskRewardRatio { get; set; }
        }
        
        [Serializable]
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
            
            // Enhanced properties
            public double Commission { get; set; } = 5.0;
            public string Side { get; set; } // "Long" or "Short"
            public string ExitReason { get; set; }
            public double RiskRewardRatio { get; set; }
        }
        
        [Serializable]
        public class ComponentHealth
        {
            public string ComponentId { get; set; }
            public bool IsHealthy { get; set; }
            public DateTime LastUpdate { get; set; }
            public string Version { get; set; }
            public string ErrorMessage { get; set; }
            
            // Enhanced properties
            public ComponentStatus Status { get; set; } = ComponentStatus.Healthy;
            public DateTime RegistrationTime { get; set; }
            public long AccessCount { get; set; }
            public int ErrorCount { get; set; }
            public DateTime LastError { get; set; }
            
            public ComponentHealth Clone()
            {
                return new ComponentHealth
                {
                    ComponentId = this.ComponentId,
                    IsHealthy = this.IsHealthy,
                    LastUpdate = this.LastUpdate,
                    Version = this.Version,
                    ErrorMessage = this.ErrorMessage,
                    Status = this.Status,
                    RegistrationTime = this.RegistrationTime,
                    AccessCount = this.AccessCount,
                    ErrorCount = this.ErrorCount,
                    LastError = this.LastError
                };
            }
        }
        
        public class SystemPerformance
        {
            private List<TradeResult> allTrades = new List<TradeResult>();
            private List<TradeResult> todaysTrades = new List<TradeResult>();
            
            public double TotalPnL => allTrades.Sum(t => t.PnL);
            public double WinRate => allTrades.Count > 0 ? (double)allTrades.Count(t => t.PnL > 0) / allTrades.Count : 0;
            public double SharpeRatio { get; private set; } = 0;
            public double MaxDrawdown { get; private set; } = 0;
            
            // Enhanced properties
            public List<TradeResult> AllTrades => allTrades.ToList(); // Return copy for thread safety
            public List<TradeResult> TodaysTrades => todaysTrades.ToList();
            public double AverageWin => allTrades.Where(t => t.PnL > 0).DefaultIfEmpty().Average(t => t?.PnL ?? 0);
            public double AverageLoss => allTrades.Where(t => t.PnL < 0).DefaultIfEmpty().Average(t => t?.PnL ?? 0);
            public int WinningTrades => allTrades.Count(t => t.PnL > 0);
            public int LosingTrades => allTrades.Count(t => t.PnL < 0);
            
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
                // Enhanced Sharpe calculation
                if (allTrades.Count > 20)
                {
                    var returns = allTrades.Select(t => t.PnL).ToList();
                    var avgReturn = returns.Average();
                    var stdDev = Math.Sqrt(returns.Select(r => Math.Pow(r - avgReturn, 2)).Average());
                    SharpeRatio = stdDev > 0 ? (avgReturn / stdDev) * Math.Sqrt(252) : 0;
                }
                
                // Enhanced drawdown calculation
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
        
        // New enhanced classes
        public class ComponentCircuitBreaker
        {
            public string ComponentId { get; set; }
            public CircuitBreakerState State { get; set; } = CircuitBreakerState.Closed;
            public int FailureCount { get; set; }
            public int FailureThreshold { get; set; } = 5;
            public DateTime LastFailureTime { get; set; }
            public TimeSpan TimeoutPeriod { get; set; } = TimeSpan.FromMinutes(2);
            
            public T Execute<T>(Func<T> operation)
            {
                if (State == CircuitBreakerState.Open)
                {
                    if (DateTime.Now - LastFailureTime > TimeoutPeriod)
                    {
                        State = CircuitBreakerState.HalfOpen;
                    }
                    else
                    {
                        throw new CircuitBreakerOpenException($"Circuit breaker open for {ComponentId}");
                    }
                }
                
                try
                {
                    T result = operation();
                    OnSuccess();
                    return result;
                }
                catch (Exception)
                {
                    OnFailure();
                    throw;
                }
            }
            
            private void OnSuccess()
            {
                FailureCount = 0;
                State = CircuitBreakerState.Closed;
            }
            
            private void OnFailure()
            {
                FailureCount++;
                LastFailureTime = DateTime.Now;
                
                if (FailureCount >= FailureThreshold)
                {
                    State = CircuitBreakerState.Open;
                }
            }
        }
        
        public class ComponentMetrics
        {
            public string ComponentId { get; set; }
            public DateTime RegistrationTime { get; set; }
            public long TotalAccesses { get; set; }
            public DateTime LastAccess { get; set; }
            public double AverageResponseTime { get; set; }
            public long MemoryUsage { get; set; }
            public int ErrorCount { get; set; }
        }
        
        [Serializable]
        [XmlRoot("FKSConfiguration")]
        public class FKSConfiguration
        {
            [XmlElement("CurrentMarket")]
            public string CurrentMarket { get; set; }
            
            [XmlIgnore]
            public Dictionary<string, MarketConfiguration> MarketConfigurations { get; set; }
            
            [XmlArray("MarketConfigurations")]
            [XmlArrayItem("Configuration")]
            public List<MarketConfigurationEntry> MarketConfigurationsList
            {
                get
                {
                    if (MarketConfigurations == null) return null;
                    return MarketConfigurations.Select(kvp => new MarketConfigurationEntry
                    {
                        Key = kvp.Key,
                        Value = kvp.Value
                    }).ToList();
                }
                set
                {
                    if (value == null)
                    {
                        MarketConfigurations = new Dictionary<string, MarketConfiguration>();
                        return;
                    }
                    
                    MarketConfigurations = value.ToDictionary(entry => entry.Key, entry => entry.Value);
                }
            }
            
            [XmlElement("LastUpdate")]
            public DateTime LastUpdate { get; set; }
            
            [XmlElement("Version")]
            public string Version { get; set; }
            
            public FKSConfiguration()
            {
                CurrentMarket = "DEFAULT";
                MarketConfigurations = new Dictionary<string, MarketConfiguration>();
                LastUpdate = DateTime.MinValue;
                Version = "3.0.0";
            }

            public void PruneOldConfigurations(TimeSpan ageLimit)
            {
                lock (MarketConfigurations)
                {
                    DateTime threshold = DateTime.UtcNow - ageLimit;
                    var keysToRemove = MarketConfigurations.Where(kvp => kvp.Value.LastUpdate < threshold)
                                                           .Select(kvp => kvp.Key)
                                                           .ToList();

                    foreach (var key in keysToRemove)
                    {
                        MarketConfigurations.Remove(key);
                    }
                }
            }
        }
        
        [Serializable]
        public class MarketConfigurationEntry
        {
            [XmlAttribute("Key")]
            public string Key { get; set; }
            
            [XmlElement("Value")]
            public MarketConfiguration Value { get; set; }
        }
        
        public class EventInfo
        {
            public string EventType { get; set; }
            public EventArgs EventArgs { get; set; }
            public DateTime Timestamp { get; set; }
        }
        
        public class SignalStatistics
        {
            public TimeSpan Period { get; set; }
            public long TotalSignals { get; set; }
            public long RejectedSignals { get; set; }
            public double AverageQuality { get; set; }
            public DateTime LastSignalTime { get; set; }
            public double LastSignalQuality { get; set; }
        }
        
        public class SystemPerformanceReport
        {
            public TimeSpan Period { get; set; }
            public DateTime Timestamp { get; set; }
            public TimeSpan SystemUptime { get; set; }
            public long TotalOperations { get; set; }
            public int ComponentCount { get; set; }
            public int HealthyComponents { get; set; }
            public int ActiveCircuitBreakers { get; set; }
            public TradingPerformanceMetrics TradingPerformance { get; set; }
            public Dictionary<string, double> SystemMetrics { get; set; }
            public Dictionary<string, long> OperationCounts { get; set; }
            public List<ComponentHealth> ComponentHealth { get; set; }
            public List<string> Recommendations { get; set; }
        }
        
        public class TradingPerformanceMetrics
        {
            public int TotalTrades { get; set; }
            public int TodaysTrades { get; set; }
            public double WinRate { get; set; }
            public double TotalPnL { get; set; }
            public double DailyPnL { get; set; }
            public double DailyCommissions { get; set; }
            public double CommissionRatio { get; set; }
            public double SharpeRatio { get; set; }
            public double MaxDrawdown { get; set; }
            public int ConsecutiveLosses { get; set; }
        }
        
        public class SystemHealthReport
        {
            public DateTime Timestamp { get; set; }
            public double OverallHealthScore { get; set; }
            public bool IsSystemHealthy { get; set; }
            public TimeSpan SystemUptime { get; set; }
            public int ComponentCount { get; set; }
            public int HealthyComponents { get; set; }
            public int CriticalComponents { get; set; }
            public CircuitBreakerStatistics CircuitBreakerStats { get; set; }
            public Dictionary<string, double> PerformanceMetrics { get; set; }
            public List<SystemAlert> Alerts { get; set; }
            public List<string> Recommendations { get; set; }
        }
        
        public class CircuitBreakerStatistics
        {
            public int TotalCircuitBreakers { get; set; }
            public int OpenCircuitBreakers { get; set; }
            public int HalfOpenCircuitBreakers { get; set; }
            public int ClosedCircuitBreakers { get; set; }
        }
        
        public class SystemAlert
        {
            public AlertLevel Level { get; set; }
            public string Component { get; set; }
            public string Message { get; set; }
            public DateTime Timestamp { get; set; }
        }
        
        // Event Args Classes (Enhanced)
        public class SignalEventArgs : EventArgs
        {
            public FKSSignal Signal { get; set; }
            public string Description { get; set; }
        }
        
        public class TradeEventArgs : EventArgs
        {
            public TradeResult Trade { get; set; }
            public string Description { get; set; }
        }
        
        public class ComponentEventArgs : EventArgs
        {
            public string ComponentId { get; set; }
            public ComponentStatus Status { get; set; }
            public string Description { get; set; }
        }
        
        public class MarketEventArgs : EventArgs
        {
            public string PreviousRegime { get; set; }
            public string NewRegime { get; set; }
            public string Description { get; set; }
        }
        
        public class SystemEventArgs : EventArgs
        {
            public SystemEventType EventType { get; set; }
            public string Description { get; set; }
            public DateTime Timestamp { get; set; }
        }
        
        public class ConfigurationEventArgs : EventArgs
        {
            public string ChangeType { get; set; }
            public string OldValue { get; set; }
            public string NewValue { get; set; }
        }
        
        public class CircuitBreakerEventArgs : EventArgs
        {
            public string ComponentId { get; set; }
            public CircuitBreakerState State { get; set; }
            public string Reason { get; set; }
        }
        
        // Enums (Enhanced)
        public enum ComponentStatus
        {
            Connected,
            Disconnected,
            Error,
            Warning,
            Healthy,
            Disposed,
            Initializing,
            Disabled
        }
        
        public enum LogLevel
        {
            Debug,
            Information,
            Warning,
            Error
        }
        
        public enum SignalDirection
        {
            Neutral,
            Bullish,
            Bearish,
            Long,
            Short
        }
        
        public enum TextPosition
        {
            TopLeft,
            TopCenter,
            TopRight,
            MiddleLeft,
            Center,
            MiddleRight,
            BottomLeft,
            BottomCenter,
            BottomRight
        }
        
        public enum CircuitBreakerState
        {
            Closed,
            Open,
            HalfOpen
        }
        
        public enum SystemEventType
        {
            Initialized,
            Shutdown,
            HealthDegraded,
            HealthRestored,
            CriticalAlert,
            DailyReset,
            ConfigurationChanged
        }
        
        public enum AlertLevel
        {
            Information,
            Warning,
            Critical
        }
        
        // Exception Classes
        public class CircuitBreakerOpenException : Exception
        {
            public CircuitBreakerOpenException(string message) : base(message) { }
        }
        
        // Legacy Classes (Preserved for backward compatibility)
        public class ComponentHealthReport
        {
            public string ComponentId { get; set; }
            public string ComponentName { get; set; }
            public bool IsHealthy { get; set; }
            public ComponentStatus Status { get; set; }
            public DateTime LastUpdate { get; set; }
            public string ErrorMessage { get; set; }
            public int ErrorCount { get; set; }
            public Dictionary<string, object> Metrics { get; set; } = new Dictionary<string, object>();
            public Dictionary<string, double> PerformanceMetrics { get; set; } = new Dictionary<string, double>();
            public List<string> DiagnosticInfo { get; set; } = new List<string>();
        }
        
        public class ComponentSignal
        {
            public string SignalType { get; set; }
            public string Source { get; set; }
            public double Quality { get; set; }
            public double Confidence { get; set; }
            public double Score { get; set; }
            public SignalDirection Direction { get; set; }
            public bool IsActive { get; set; }
            public DateTime Timestamp { get; set; }
            public Dictionary<string, object> Data { get; set; } = new Dictionary<string, object>();
            public Dictionary<string, double> Metrics { get; set; } = new Dictionary<string, double>();
            public List<string> Reasons { get; set; } = new List<string>();
        }
        
        public class FKS_ComponentManager
        {
            private static FKS_ComponentManager instance;
            private Dictionary<string, IFKSComponent> components = new Dictionary<string, IFKSComponent>();
            
            public static FKS_ComponentManager Instance
            {
                get
                {
                    if (instance == null)
                        instance = new FKS_ComponentManager();
                    return instance;
                }
            }
            
            public void RegisterComponent(string id, IFKSComponent component)
            {
                components[id] = component;
                FKS_Core.RegisterComponent(id, component); // Integrate with enhanced core
            }
            
            public void UnregisterComponent(string id)
            {
                if (components.ContainsKey(id))
                    components.Remove(id);
                FKS_Core.UnregisterComponent(id); // Integrate with enhanced core
            }
            
            public T GetComponent<T>(string id) where T : class, IFKSComponent
            {
                return FKS_Core.GetComponentSafe<T>(id); // Use enhanced safe method
            }
            
            public SystemHealthInfo GetSystemHealth()
            {
                return new SystemHealthInfo
                {
                    TotalComponents = components.Count,
                    HealthyComponents = componentHealth.Values.Count(h => h.IsHealthy)
                };
            }
        }
        
        public class SystemHealthInfo
        {
            public int TotalComponents { get; set; }
            public int HealthyComponents { get; set; }
        }
        
        public static class FKS_ErrorHandler
        {
            public static void HandleError(Exception ex, string context)
            {
                var errorMessage = $"Error in {context}: {ex.Message}";
                NinjaTrader.Code.Output.Process(errorMessage, PrintTo.OutputTab1);
                
                // Enhanced error handling with infrastructure integration
                try
                {
                    FKS_Infrastructure.RecordComponentActivity("ErrorHandler", new FKS_Infrastructure.ComponentActivity
                    {
                        ActivityType = "ErrorHandling",
                        IsError = true,
                        ErrorMessage = ex.Message
                    });
                }
                catch
                {
                    // Fail silently if infrastructure is not available
                }
            }
        }
        
        #endregion

        #region Neural Network Integration
        private static FKS_NeuralNetwork neuralNetwork;

        public static void InitNeuralNetwork()
        {
            if (neuralNetwork == null)
            {
                LogMessage("Initializing Neural Network Component", LogLevel.Information);
                neuralNetwork = new FKS_NeuralNetwork();
                LoadModel(); // Load model if exists
            }
        }

        public static double PredictMarketRegime(double[][] marketData)
        {
            if (neuralNetwork == null)
            {
                LogMessage("Neural Network not initialized", LogLevel.Error);
                return 0.0;
            }

            return neuralNetwork.Predict(marketData).FirstOrDefault();
        }

        public static void SaveModel()
        {
            LogMessage("Saving Neural Network Model", LogLevel.Information);
            // Add logic to save the model state
        }

        public static void LoadModel()
        {
            LogMessage("Loading Neural Network Model", LogLevel.Information);
            // Add logic to load the model state if exists
        }
        #endregion
    }
}