#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Text;
using NinjaTrader.NinjaScript;
using NinjaTrader.Cbi;
#endregion

namespace NinjaTrader.NinjaScript.AddOns.FKS
{
    /// <summary>
    /// Advanced component registry, health monitoring, and system infrastructure management
    /// Provides comprehensive monitoring, alerting, and auto-recovery capabilities
    /// </summary>
    public static class FKS_Infrastructure
    {
        #region Private Fields
        
        // Legacy heartbeat system (preserved for backward compatibility)
        private static readonly Dictionary<string, DateTime> heartbeats = new Dictionary<string, DateTime>();
        private static readonly object lockObj = new object();
        
        // Advanced monitoring system
        private static readonly ConcurrentDictionary<string, ComponentMetrics> componentMetrics 
            = new ConcurrentDictionary<string, ComponentMetrics>();
        private static readonly ConcurrentDictionary<string, ComponentHealthData> componentHealthData 
            = new ConcurrentDictionary<string, ComponentHealthData>();
        private static readonly ConcurrentDictionary<string, CircuitBreakerState> circuitBreakers 
            = new ConcurrentDictionary<string, CircuitBreakerState>();
        
        // System monitoring
        private static readonly Timer healthCheckTimer;
        private static readonly Timer metricsCollectionTimer;
        private static readonly Timer cleanupTimer;
        
        // Performance tracking
        private static readonly ConcurrentQueue<SystemSnapshot> systemHistory = new ConcurrentQueue<SystemSnapshot>();
        private static readonly ConcurrentDictionary<string, PerformanceCounters> performanceCounters 
            = new ConcurrentDictionary<string, PerformanceCounters>();
        
        // Configuration
        private static readonly TimeSpan HealthCheckInterval = TimeSpan.FromSeconds(30);
        private static readonly TimeSpan MetricsCollectionInterval = TimeSpan.FromSeconds(10);
        private static readonly TimeSpan CleanupInterval = TimeSpan.FromMinutes(5);
        private static readonly TimeSpan DefaultComponentTimeout = TimeSpan.FromSeconds(30);
        private static readonly int MaxHistorySize = 1000;
        private static readonly int MaxMetricsAge = 24; // Hours
        
        // Logging configuration
        private static bool enableVerboseLogging = false; // Set to true to enable detailed logging
        private static LogLevel minimumLogLevel = LogLevel.Error; // Only log errors by default
        
        // System state
        private static DateTime systemStartTime = DateTime.Now;
        private static bool isShuttingDown = false;
        private static volatile bool isInitialized = false;
        
        // Critical components that must be healthy for system operation
        // Critical components - only include core components that should always be present
        // Optional components like FKS_AI, FKS_AO, FKS_Info are not required
        private static readonly string[] criticalComponents = { }; // Empty - all components are now optional
        private static readonly string[] optionalComponents = { "FKS_Info", "FKS_VWAP", "FKS_Market" };
        
        #endregion

        #region Static Constructor and Initialization
        
        static FKS_Infrastructure()
        {
            try
            {
                // Temporarily disable aggressive monitoring to reduce memory load
                // Initialize timers with much longer intervals
                healthCheckTimer = new Timer(PerformHealthCheck, null, TimeSpan.FromMinutes(5), TimeSpan.FromMinutes(5));
                metricsCollectionTimer = new Timer(CollectMetrics, null, TimeSpan.FromMinutes(2), TimeSpan.FromMinutes(2));
                cleanupTimer = new Timer(PerformCleanup, null, TimeSpan.FromMinutes(10), TimeSpan.FromMinutes(10));
                
                // Register for application shutdown
                AppDomain.CurrentDomain.ProcessExit += OnApplicationShutdown;
                
                isInitialized = true;
                LogMessage("FKS Infrastructure initialized successfully", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to initialize FKS Infrastructure: {ex.Message}", LogLevel.Error);
            }
        }
        
        #endregion

        #region Backward Compatibility Methods (Preserved)
        
        /// <summary>
        /// Legacy heartbeat method (preserved for backward compatibility)
        /// </summary>
        public static void Heartbeat(string componentId)
        {
            try
            {
                lock (lockObj)
                {
                    heartbeats[componentId] = DateTime.Now;
                }
                
                // Also update advanced metrics
                RecordComponentActivity(componentId);
            }
            catch (Exception ex)
            {
                LogMessage($"Heartbeat error for {componentId}: {ex.Message}", LogLevel.Warning);
            }
        }
        
        /// <summary>
        /// Legacy health check method (preserved for backward compatibility)
        /// </summary>
        public static bool IsHealthy(string componentId)
        {
            try
            {
                lock (lockObj)
                {
                    if (!heartbeats.ContainsKey(componentId))
                        return false;
                        
                    return (DateTime.Now - heartbeats[componentId]).TotalSeconds < 30;
                }
            }
            catch
            {
                return false;
            }
        }
        
        /// <summary>
        /// Legacy system health method (preserved for backward compatibility)
        /// </summary>
        public static Dictionary<string, bool> GetSystemHealth()
        {
            var health = new Dictionary<string, bool>();
            var components = new[] { "FKS_AI", "FKS_AO", "FKS_Info", "FKS_VWAP" };
            
            foreach (var component in components)
            {
                health[component] = IsHealthy(component);
            }
            
            return health;
        }
        
        #endregion

        #region Advanced Component Monitoring
        
        /// <summary>
        /// Register a component with detailed monitoring capabilities
        /// </summary>
        public static void RegisterComponent(string componentId, ComponentRegistrationInfo info)
        {
            try
            {
                var metrics = new ComponentMetrics
                {
                    ComponentId = componentId,
                    RegistrationTime = DateTime.Now,
                    ComponentType = info.ComponentType,
                    Version = info.Version,
                    IsCritical = info.IsCritical,
                    ExpectedResponseTime = info.ExpectedResponseTime,
                    MaxMemoryUsage = info.MaxMemoryUsage
                };
                
                componentMetrics[componentId] = metrics;
                
                var healthData = new ComponentHealthData
                {
                    ComponentId = componentId,
                    Status = ComponentStatus.Healthy,
                    LastSeen = DateTime.Now,
                    ConsecutiveFailures = 0
                };
                
                componentHealthData[componentId] = healthData;
                
                // Initialize circuit breaker
                circuitBreakers[componentId] = new CircuitBreakerState
                {
                    State = CircuitState.Closed,
                    FailureCount = 0,
                    LastFailureTime = DateTime.MinValue
                };
                
                // Initialize performance counters
                performanceCounters[componentId] = new PerformanceCounters();
                
                LogMessage($"Component registered: {componentId} v{info.Version}", LogLevel.Information);
                
                // Send registration event
                OnComponentRegistered?.Invoke(componentId, info);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to register component {componentId}: {ex.Message}", LogLevel.Error);
            }
        }
        
        /// <summary>
        /// Unregister a component
        /// </summary>
        public static void UnregisterComponent(string componentId)
        {
            try
            {
                componentMetrics.TryRemove(componentId, out _);
                componentHealthData.TryRemove(componentId, out _);
                circuitBreakers.TryRemove(componentId, out _);
                performanceCounters.TryRemove(componentId, out _);
                
                lock (lockObj)
                {
                    heartbeats.Remove(componentId);
                }
                
                LogMessage($"Component unregistered: {componentId}", LogLevel.Information);
                
                // Send unregistration event
                OnComponentUnregistered?.Invoke(componentId);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to unregister component {componentId}: {ex.Message}", LogLevel.Error);
            }
        }
        
        /// <summary>
        /// Record component activity and performance metrics
        /// </summary>
        public static void RecordComponentActivity(string componentId, ComponentActivity activity = null)
        {
            try
            {
                if (!componentHealthData.ContainsKey(componentId))
                {
                    // Auto-register unknown components
                    RegisterComponent(componentId, new ComponentRegistrationInfo
                    {
                        ComponentType = "Unknown",
                        Version = "1.0.0",
                        IsCritical = false
                    });
                }
                
                var healthData = componentHealthData[componentId];
                healthData.LastSeen = DateTime.Now;
                healthData.ActivityCount++;
                
                if (activity != null)
                {
                    var counters = performanceCounters[componentId];
                    counters.RecordActivity(activity);
                    
                    // Update metrics
                    var metrics = componentMetrics[componentId];
                    metrics.LastActivity = DateTime.Now;
                    metrics.TotalActivities++;
                    
                    if (activity.ExecutionTime.HasValue)
                    {
                        metrics.AverageResponseTime = CalculateMovingAverage(
                            metrics.AverageResponseTime, 
                            activity.ExecutionTime.Value.TotalMilliseconds, 
                            metrics.TotalActivities);
                    }
                    
                    if (activity.MemoryUsage.HasValue)
                    {
                        metrics.CurrentMemoryUsage = activity.MemoryUsage.Value;
                        metrics.PeakMemoryUsage = Math.Max(metrics.PeakMemoryUsage, activity.MemoryUsage.Value);
                    }
                    
                    // Check for performance issues
                    CheckPerformanceThresholds(componentId, activity);
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to record activity for {componentId}: {ex.Message}", LogLevel.Warning);
            }
        }
        
        /// <summary>
        /// Record component error
        /// </summary>
        public static void RecordComponentError(string componentId, Exception error, string context = null)
        {
            try
            {
                if (componentHealthData.ContainsKey(componentId))
                {
                    var healthData = componentHealthData[componentId];
                    healthData.ConsecutiveFailures++;
                    healthData.TotalErrors++;
                    healthData.LastError = error.Message;
                    healthData.LastErrorTime = DateTime.Now;
                    
                    // Update circuit breaker
                    var circuitBreaker = circuitBreakers[componentId];
                    circuitBreaker.FailureCount++;
                    circuitBreaker.LastFailureTime = DateTime.Now;
                    
                    // Check if circuit should open
                    if (circuitBreaker.FailureCount >= 5 && circuitBreaker.State == CircuitState.Closed)
                    {
                        circuitBreaker.State = CircuitState.Open;
                        circuitBreaker.OpenTime = DateTime.Now;
                        
                        // Circuit breaker logging disabled to reduce spam
                        // LogMessage($"Circuit breaker opened for {componentId} due to repeated failures", LogLevel.Warning);
                        OnCircuitBreakerOpened?.Invoke(componentId, error);
                    }
                    
                    // Update component status
                    if (healthData.ConsecutiveFailures >= 3)
                    {
                        healthData.Status = ComponentStatus.Critical;
                    }
                    else if (healthData.ConsecutiveFailures >= 1)
                    {
                        healthData.Status = ComponentStatus.Warning;
                    }
                }
                
                LogMessage($"Error recorded for {componentId}: {error.Message} (Context: {context})", LogLevel.Error);
                
                // Send error event
                OnComponentError?.Invoke(componentId, error, context);
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to record error for {componentId}: {ex.Message}", LogLevel.Error);
            }
        }
        
        /// <summary>
        /// Record component recovery
        /// </summary>
        public static void RecordComponentRecovery(string componentId)
        {
            try
            {
                if (componentHealthData.ContainsKey(componentId))
                {
                    var healthData = componentHealthData[componentId];
                    healthData.ConsecutiveFailures = 0;
                    healthData.Status = ComponentStatus.Healthy;
                    healthData.LastRecovery = DateTime.Now;
                    
                    // Reset circuit breaker
                    var circuitBreaker = circuitBreakers[componentId];
                    circuitBreaker.FailureCount = 0;
                    circuitBreaker.State = CircuitState.Closed;
                    
                    LogMessage($"Component recovered: {componentId}", LogLevel.Information);
                    OnComponentRecovered?.Invoke(componentId);
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to record recovery for {componentId}: {ex.Message}", LogLevel.Warning);
            }
        }
        
        /// <summary>
        /// Convenience method to record performance metrics
        /// </summary>
        public static void RecordPerformanceMetric(string componentId, string operationType, TimeSpan executionTime, bool isError = false)
        {
            RecordComponentActivity(componentId, new ComponentActivity
            {
                ActivityType = operationType,
                ExecutionTime = executionTime,
                IsError = isError,
                Timestamp = DateTime.Now
            });
        }
        
        /// <summary>
        /// Convenience method to record performance metrics with memory usage
        /// </summary>
        public static void RecordPerformanceMetric(string componentId, string operationType, TimeSpan executionTime, long memoryUsage, bool isError = false)
        {
            RecordComponentActivity(componentId, new ComponentActivity
            {
                ActivityType = operationType,
                ExecutionTime = executionTime,
                MemoryUsage = memoryUsage,
                IsError = isError,
                Timestamp = DateTime.Now
            });
        }
        
        /// <summary>
        /// Convenience method to record just operation count (no timing)
        /// </summary>
        public static void RecordOperation(string componentId, string operationType, bool isError = false)
        {
            RecordComponentActivity(componentId, new ComponentActivity
            {
                ActivityType = operationType,
                IsError = isError,
                Timestamp = DateTime.Now
            });
        }
        
        /// <summary>
        /// Convenience method to record error with message
        /// </summary>
        public static void RecordError(string componentId, string operationType, string errorMessage)
        {
            RecordComponentActivity(componentId, new ComponentActivity
            {
                ActivityType = operationType,
                IsError = true,
                ErrorMessage = errorMessage,
                Timestamp = DateTime.Now
            });
        }
        
        #endregion

        #region Advanced Health Analysis
        
        /// <summary>
        /// Get comprehensive system health summary
        /// </summary>
        public static SystemHealthSummary GetAdvancedSystemHealth()
        {
            try
            {
                var summary = new SystemHealthSummary
                {
                    Timestamp = DateTime.Now,
                    SystemUptime = DateTime.Now - systemStartTime,
                    OverallHealthScore = CalculateOverallHealthScore(),
                    ComponentDetails = new Dictionary<string, ComponentHealthDetail>()
                };
                
                // Analyze each component
                foreach (var componentId in componentHealthData.Keys)
                {
                    var healthData = componentHealthData[componentId];
                    var metrics = componentMetrics.TryGetValue(componentId, out var metricsValue) ? metricsValue : null;
                    var counters = performanceCounters.TryGetValue(componentId, out var countersValue) ? countersValue : null;
                    var circuitBreaker = circuitBreakers.TryGetValue(componentId, out var cbValue) ? cbValue : null;
                    
                    var detail = new ComponentHealthDetail
                    {
                        ComponentId = componentId,
                        Status = healthData.Status,
                        HealthScore = CalculateComponentHealthScore(componentId),
                        LastSeen = healthData.LastSeen,
                        ResponseTime = metrics?.AverageResponseTime ?? 0,
                        MemoryUsage = metrics?.CurrentMemoryUsage ?? 0,
                        ErrorRate = counters?.CalculateErrorRate() ?? 0,
                        CircuitBreakerState = circuitBreaker?.State ?? CircuitState.Closed,
                        Recommendations = GenerateComponentRecommendations(componentId)
                    };
                    
                    summary.ComponentDetails[componentId] = detail;
                }
                
                // System-level analysis
                summary.CriticalComponentsHealthy = CheckCriticalComponentsHealth();
                summary.SystemLoad = CalculateSystemLoad();
                summary.MemoryPressure = CalculateMemoryPressure();
                summary.AlertsActive = GetActiveAlerts();
                summary.Recommendations = GenerateSystemRecommendations();
                summary.TrendAnalysis = AnalyzeHealthTrends();
                
                return summary;
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to get advanced system health: {ex.Message}", LogLevel.Error);
                return new SystemHealthSummary
                {
                    Timestamp = DateTime.Now,
                    OverallHealthScore = 0.5,
                    ComponentDetails = new Dictionary<string, ComponentHealthDetail>()
                };
            }
        }
        
        /// <summary>
        /// Get component performance report
        /// </summary>
        public static ComponentPerformanceReport GetComponentPerformanceReport(string componentId, TimeSpan? period = null)
        {
            try
            {
                period = period ?? TimeSpan.FromHours(1);
                
                if (!performanceCounters.ContainsKey(componentId))
                {
                    return new ComponentPerformanceReport { ComponentId = componentId };
                }
                
                var counters = performanceCounters[componentId];
                var metrics = componentMetrics.TryGetValue(componentId, out var metricsValue) ? metricsValue : null;
                
                return new ComponentPerformanceReport
                {
                    ComponentId = componentId,
                    Period = period.Value,
                    TotalActivities = counters.TotalActivities,
                    AverageResponseTime = counters.AverageResponseTime,
                    MinResponseTime = counters.MinResponseTime,
                    MaxResponseTime = counters.MaxResponseTime,
                    ErrorCount = counters.ErrorCount,
                    ErrorRate = counters.CalculateErrorRate(),
                    ThroughputPerSecond = counters.CalculateThroughput(period.Value),
                    MemoryUsage = metrics?.CurrentMemoryUsage ?? 0,
                    PeakMemoryUsage = metrics?.PeakMemoryUsage ?? 0,
                    PerformanceGrade = CalculatePerformanceGrade(componentId),
                    Recommendations = GeneratePerformanceRecommendations(componentId)
                };
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to get performance report for {componentId}: {ex.Message}", LogLevel.Error);
                return new ComponentPerformanceReport { ComponentId = componentId };
            }
        }
        
        /// <summary>
        /// Check if component is safe to use (circuit breaker pattern)
        /// </summary>
        public static bool IsComponentSafeToUse(string componentId)
        {
            try
            {
                if (!circuitBreakers.ContainsKey(componentId))
                    return true; // Unknown components are assumed safe
                
                var circuitBreaker = circuitBreakers[componentId];
                
                switch (circuitBreaker.State)
                {
                    case CircuitState.Closed:
                        return true;
                        
                    case CircuitState.Open:
                        // Check if enough time has passed to try half-open
                        if (DateTime.Now - circuitBreaker.OpenTime > TimeSpan.FromMinutes(2))
                        {
                            circuitBreaker.State = CircuitState.HalfOpen;
                            return true;
                        }
                        return false;
                        
                    case CircuitState.HalfOpen:
                        return true; // Allow limited testing
                        
                    default:
                        return false;
                }
            }
            catch
            {
                return false; // Err on the side of caution
            }
        }
        
        #endregion

        #region System Monitoring and Alerts
        
        /// <summary>
        /// Get active system alerts
        /// </summary>
        public static List<SystemAlert> GetActiveAlerts()
        {
            var alerts = new List<SystemAlert>();
            
            try
            {
                // Check critical components
                foreach (var componentId in criticalComponents)
                {
                    if (!IsHealthy(componentId))
                    {
                        alerts.Add(new SystemAlert
                        {
                            Level = AlertLevel.Critical,
                            Component = componentId,
                            Message = $"Critical component {componentId} is not responding",
                            Timestamp = DateTime.Now,
                            RecommendedAction = "Restart component or check logs for errors"
                        });
                    }
                }
                
                // Check circuit breakers
                foreach (var kvp in circuitBreakers)
                {
                    if (kvp.Value.State == CircuitState.Open)
                    {
                        alerts.Add(new SystemAlert
                        {
                            Level = AlertLevel.Warning,
                            Component = kvp.Key,
                            Message = $"Circuit breaker open for {kvp.Key}",
                            Timestamp = kvp.Value.OpenTime,
                            RecommendedAction = "Check component for errors and restart if necessary"
                        });
                    }
                }
                
                // Check performance issues
                foreach (var kvp in componentMetrics)
                {
                    var metrics = kvp.Value;
                    if (metrics.AverageResponseTime > 5000) // 5 seconds
                    {
                        alerts.Add(new SystemAlert
                        {
                            Level = AlertLevel.Warning,
                            Component = kvp.Key,
                            Message = $"Slow response time: {metrics.AverageResponseTime:F0}ms",
                            Timestamp = DateTime.Now,
                            RecommendedAction = "Optimize component or increase resources"
                        });
                    }
                }
                
                // Check memory usage
                foreach (var kvp in componentMetrics)
                {
                    var metrics = kvp.Value;
                    if (metrics.MaxMemoryUsage > 0 && metrics.CurrentMemoryUsage > metrics.MaxMemoryUsage * 0.9)
                    {
                        alerts.Add(new SystemAlert
                        {
                            Level = AlertLevel.Warning,
                            Component = kvp.Key,
                            Message = $"High memory usage: {metrics.CurrentMemoryUsage / 1024 / 1024:F0} MB",
                            Timestamp = DateTime.Now,
                            RecommendedAction = "Check for memory leaks or increase memory allocation"
                        });
                    }
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to get active alerts: {ex.Message}", LogLevel.Error);
            }
            
            return alerts;
        }
        
        /// <summary>
        /// Get system resource usage
        /// </summary>
        public static SystemResourceUsage GetSystemResourceUsage()
        {
            try
            {
                var process = Process.GetCurrentProcess();
                
                return new SystemResourceUsage
                {
                    Timestamp = DateTime.Now,
                    CpuUsage = GetCpuUsage(),
                    MemoryUsage = process.WorkingSet64,
                    MemoryUsageMB = process.WorkingSet64 / 1024 / 1024,
                    ThreadCount = process.Threads.Count,
                    HandleCount = process.HandleCount,
                    ComponentCount = componentMetrics.Count,
                    ActiveCircuitBreakers = circuitBreakers.Values.Count(cb => cb.State != CircuitState.Closed),
                    SystemUptime = DateTime.Now - systemStartTime
                };
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to get system resource usage: {ex.Message}", LogLevel.Error);
                return new SystemResourceUsage { Timestamp = DateTime.Now };
            }
        }
        
        #endregion

        #region Automated Health Checks
        
        private static void PerformHealthCheck(object state)
        {
            if (isShuttingDown) return;
            
            try
            {
                var startTime = DateTime.Now;
                
                // Check all registered components
                Parallel.ForEach(componentHealthData.Keys, componentId =>
                {
                    CheckComponentHealth(componentId);
                });
                
                // Update system snapshot
                var snapshot = new SystemSnapshot
                {
                    Timestamp = DateTime.Now,
                    OverallHealth = CalculateOverallHealthScore(),
                    ComponentCount = componentMetrics.Count,
                    ActiveComponents = componentHealthData.Values.Count(h => h.Status == ComponentStatus.Healthy),
                    CriticalAlerts = GetActiveAlerts().Count(a => a.Level == AlertLevel.Critical),
                    WarningAlerts = GetActiveAlerts().Count(a => a.Level == AlertLevel.Warning)
                };
                
                systemHistory.Enqueue(snapshot);
                
                // Maintain history size
                while (systemHistory.Count > MaxHistorySize)
                {
                    systemHistory.TryDequeue(out _);
                }
                
                var duration = DateTime.Now - startTime;
                if (duration.TotalSeconds > 5)
                {
                    LogMessage($"Health check took {duration.TotalSeconds:F1} seconds", LogLevel.Warning);
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Health check failed: {ex.Message}", LogLevel.Error);
            }
        }
        
        private static void CheckComponentHealth(string componentId)
        {
            try
            {
                if (!componentHealthData.ContainsKey(componentId)) return;
                
                var healthData = componentHealthData[componentId];
                var timeSinceLastSeen = DateTime.Now - healthData.LastSeen;
                var timeout = componentMetrics.ContainsKey(componentId) 
                    ? componentMetrics[componentId].ExpectedResponseTime 
                    : DefaultComponentTimeout;
                
                // Check if component is responding with progressive timeout handling
                if (timeSinceLastSeen > timeout)
                {
                    if (healthData.Status == ComponentStatus.Healthy)
                    {
                        healthData.Status = ComponentStatus.Warning;
                        LogMessage($"Component {componentId} response timeout", LogLevel.Warning);
                        
                        // Attempt automatic recovery for critical components
                        if (IsCriticalComponent(componentId))
                        {
                            Task.Run(() => AttemptComponentRecovery(componentId));
                        }
                    }
                    else if (timeSinceLastSeen > timeout.Add(timeout)) // Double timeout
                    {
                        healthData.Status = ComponentStatus.Critical;
                        
                        // Only log critical timeout occasionally to prevent spam
                        if (healthData.LastCriticalLog.AddMinutes(5) < DateTime.Now) // Increased from 1 minute to 5 minutes
                        {
                            // Changed from Error to Warning level to reduce noise
                            LogMessage($"Component {componentId} extended timeout", LogLevel.Warning);
                            healthData.LastCriticalLog = DateTime.Now;
                        }
                        
                        // Circuit breaker disabled to prevent strategy shutdowns
                        // TriggerCircuitBreaker(componentId);
                    }
                }
                else if (healthData.ConsecutiveFailures == 0)
                {
                    healthData.Status = ComponentStatus.Healthy;
                }
                
                // Check circuit breaker recovery
                if (circuitBreakers.ContainsKey(componentId))
                {
                    var circuitBreaker = circuitBreakers[componentId];
                    if (circuitBreaker.State == CircuitState.HalfOpen && 
                        healthData.Status == ComponentStatus.Healthy)
                    {
                        circuitBreaker.State = CircuitState.Closed;
                        circuitBreaker.FailureCount = 0;
                        LogMessage($"Circuit breaker closed for {componentId}", LogLevel.Information);
                    }
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Component health check failed for {componentId}: {ex.Message}", LogLevel.Error);
            }
        }
        
        private static void CollectMetrics(object state)
        {
            if (isShuttingDown) return;
            
            try
            {
                // Collect system-wide metrics
                var resourceUsage = GetSystemResourceUsage();
                
                // Update component metrics
                foreach (var componentId in componentMetrics.Keys)
                {
                    var metrics = componentMetrics[componentId];
                    metrics.LastMetricsUpdate = DateTime.Now;
                    
                    // Collect garbage collection info
                    if (DateTime.Now.Second % 30 == 0) // Every 30 seconds
                    {
                        GC.Collect();
                        GC.WaitForPendingFinalizers();
                        GC.Collect();
                    }
                }
                
                // Trigger alerts if necessary
                var alerts = GetActiveAlerts();
                if (alerts.Any(a => a.Level == AlertLevel.Critical))
                {
                    // Disabled to prevent spam for missing optional components
                    // OnCriticalAlertRaised?.Invoke(alerts.Where(a => a.Level == AlertLevel.Critical).ToList());
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Metrics collection failed: {ex.Message}", LogLevel.Error);
            }
        }
        
        private static void PerformCleanup(object state)
        {
            if (isShuttingDown) return;
            
            try
            {
                var cutoffTime = DateTime.Now.AddHours(-MaxMetricsAge);
                
                // Clean up old performance data
                foreach (var counters in performanceCounters.Values)
                {
                    counters.CleanupOldData(cutoffTime);
                }
                
                // Clean up old system snapshots
                while (systemHistory.Count > MaxHistorySize)
                {
                    systemHistory.TryDequeue(out _);
                }
                
                // Reset circuit breakers that have been open too long
                foreach (var kvp in circuitBreakers.Where(cb => cb.Value.State == CircuitState.Open))
                {
                    if (DateTime.Now - kvp.Value.OpenTime > TimeSpan.FromMinutes(10))
                    {
                        kvp.Value.State = CircuitState.HalfOpen;
                        LogMessage($"Circuit breaker reset to half-open for {kvp.Key}", LogLevel.Information);
                    }
                }
                
                LogMessage("Infrastructure cleanup completed", LogLevel.Debug);
            }
            catch (Exception ex)
            {
                LogMessage($"Cleanup failed: {ex.Message}", LogLevel.Error);
            }
        }
        
        #endregion

        #region Events
        
        public static event Action<string, ComponentRegistrationInfo> OnComponentRegistered;
        public static event Action<string> OnComponentUnregistered;
        public static event Action<string, Exception, string> OnComponentError;
        public static event Action<string> OnComponentRecovered;
        public static event Action<string, Exception> OnCircuitBreakerOpened;
        public static event Action<List<SystemAlert>> OnCriticalAlertRaised;
        
        #endregion

        #region Utility Methods
        
        private static double CalculateOverallHealthScore()
        {
            try
            {
                if (!componentHealthData.Any()) return 1.0;
                
                double totalScore = 0;
                int componentCount = 0;
                
                foreach (var healthData in componentHealthData.Values)
                {
                    double componentScore = healthData.Status switch
                    {
                        ComponentStatus.Healthy => 1.0,
                        ComponentStatus.Warning => 0.6,
                        ComponentStatus.Critical => 0.2,
                        _ => 0.5
                    };
                    
                    // Weight critical components more heavily
                    if (criticalComponents.Contains(healthData.ComponentId))
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
        
        private static double CalculateComponentHealthScore(string componentId)
        {
            try
            {
                if (!componentHealthData.ContainsKey(componentId)) return 0.5;
                
                var healthData = componentHealthData[componentId];
                var baseScore = healthData.Status switch
                {
                    ComponentStatus.Healthy => 1.0,
                    ComponentStatus.Warning => 0.6,
                    ComponentStatus.Critical => 0.2,
                    _ => 0.5
                };
                
                // Adjust based on error rate
                if (performanceCounters.ContainsKey(componentId))
                {
                    var errorRate = performanceCounters[componentId].CalculateErrorRate();
                    baseScore *= (1.0 - Math.Min(0.5, errorRate)); // Max 50% penalty for errors
                }
                
                // Adjust based on response time
                if (componentMetrics.ContainsKey(componentId))
                {
                    var metrics = componentMetrics[componentId];
                    if (metrics.AverageResponseTime > 1000) // 1 second
                    {
                        var penalty = Math.Min(0.3, (metrics.AverageResponseTime - 1000) / 10000); // Max 30% penalty
                        baseScore *= (1.0 - penalty);
                    }
                }
                
                return Math.Max(0.0, Math.Min(1.0, baseScore));
            }
            catch
            {
                return 0.5;
            }
        }
        
        private static bool CheckCriticalComponentsHealth()
        {
            return criticalComponents.All(IsHealthy);
        }
        
        private static double CalculateSystemLoad()
        {
            try
            {
                var activeComponents = componentHealthData.Values.Count(h => h.Status == ComponentStatus.Healthy);
                var totalComponents = componentHealthData.Count;
                return totalComponents > 0 ? (double)activeComponents / totalComponents : 1.0;
            }
            catch
            {
                return 0.5;
            }
        }
        
        private static double CalculateMemoryPressure(double maxMemoryGB = 10.0)
        {
            try
            {
                var process = Process.GetCurrentProcess();
                var memoryGB = process.WorkingSet64 / 1024.0 / 1024.0 / 1024.0;
                
                return Math.Min(1.0, memoryGB / maxMemoryGB);
            }
            catch
            {
                return 0.3; // Default to low pressure
            }
        }
        
        private static double GetCpuUsage()
        {
            try
            {
                // Simplified CPU usage calculation
                // In production, you might want to use PerformanceCounter
                var process = Process.GetCurrentProcess();
                return Math.Min(100.0, process.TotalProcessorTime.TotalSeconds / Environment.ProcessorCount);
            }
            catch
            {
                return 0;
            }
        }
        
        private static void CheckPerformanceThresholds(string componentId, ComponentActivity activity)
        {
            try
            {
                if (!componentMetrics.ContainsKey(componentId)) return;
                
                var metrics = componentMetrics[componentId];
                
                // Check response time threshold
                if (activity.ExecutionTime.HasValue && 
                    metrics.ExpectedResponseTime > TimeSpan.Zero &&
                    activity.ExecutionTime.Value > TimeSpan.FromTicks(metrics.ExpectedResponseTime.Ticks * 2))
                {
                    LogMessage($"Slow response detected for {componentId}: {activity.ExecutionTime.Value.TotalMilliseconds:F0}ms", LogLevel.Warning);
                }
                
                // Memory threshold check temporarily disabled to prevent strategy disabling
                // The memory warnings were causing unnecessary strategy shutdowns
                /*
                // Check memory threshold
                if (activity.MemoryUsage.HasValue && 
                    metrics.MaxMemoryUsage > 0 &&
                    activity.MemoryUsage.Value > metrics.MaxMemoryUsage)
                {
                    LogMessage($"Memory threshold exceeded for {componentId}: {activity.MemoryUsage.Value / 1024 / 1024:F0} MB", LogLevel.Warning);
                }
                */
            }
            catch (Exception ex)
            {
                LogMessage($"Performance threshold check failed for {componentId}: {ex.Message}", LogLevel.Error);
            }
        }
        
        private static double CalculateMovingAverage(double currentAverage, double newValue, long count)
        {
            if (count <= 1) return newValue;
            return ((currentAverage * (count - 1)) + newValue) / count;
        }
        
        private static List<string> GenerateComponentRecommendations(string componentId)
        {
            var recommendations = new List<string>();
            
            try
            {
                if (!componentHealthData.ContainsKey(componentId)) return recommendations;
                
                var healthData = componentHealthData[componentId];
                var metrics = componentMetrics.TryGetValue(componentId, out var metricsValue) ? metricsValue : null;
                var counters = performanceCounters.TryGetValue(componentId, out var countersValue) ? countersValue : null;
                
                // Health-based recommendations
                if (healthData.Status == ComponentStatus.Critical)
                {
                    recommendations.Add("Component is in critical state - immediate attention required");
                    recommendations.Add("Check logs for errors and consider restarting");
                }
                else if (healthData.Status == ComponentStatus.Warning)
                {
                    recommendations.Add("Component showing warning signs - monitor closely");
                }
                
                // Performance recommendations
                if (metrics != null && metrics.AverageResponseTime > 2000)
                {
                    recommendations.Add("Slow response times detected - consider optimization");
                }
                
                if (counters != null && counters.CalculateErrorRate() > 0.1)
                {
                    recommendations.Add("High error rate detected - investigate error causes");
                }
                
                // Memory recommendations
                if (metrics != null && metrics.CurrentMemoryUsage > metrics.MaxMemoryUsage * 0.8)
                {
                    recommendations.Add("High memory usage - check for memory leaks");
                }
                
                // Circuit breaker recommendations
                if (circuitBreakers.ContainsKey(componentId) && 
                    circuitBreakers[componentId].State != CircuitState.Closed)
                {
                    recommendations.Add("Circuit breaker active - check component stability");
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to generate recommendations for {componentId}: {ex.Message}", LogLevel.Error);
            }
            
            return recommendations;
        }
        
        private static List<string> GenerateSystemRecommendations()
        {
            var recommendations = new List<string>();
            
            try
            {
                var healthScore = CalculateOverallHealthScore();
                
                if (healthScore < 0.6)
                {
                    recommendations.Add("System health is below optimal - check critical components");
                }
                
                var criticalAlerts = GetActiveAlerts().Count(a => a.Level == AlertLevel.Critical);
                if (criticalAlerts > 0)
                {
                    recommendations.Add($"{criticalAlerts} critical alerts active - immediate attention required");
                }
                
                var memoryPressure = CalculateMemoryPressure();
                if (memoryPressure > 0.8)
                {
                    recommendations.Add("High memory pressure detected - consider increasing memory allocation");
                }
                
                var openCircuitBreakers = circuitBreakers.Values.Count(cb => cb.State == CircuitState.Open);
                if (openCircuitBreakers > 0)
                {
                    recommendations.Add($"{openCircuitBreakers} circuit breakers open - check component stability");
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to generate system recommendations: {ex.Message}", LogLevel.Error);
            }
            
            return recommendations;
        }
        
        private static List<string> GeneratePerformanceRecommendations(string componentId)
        {
            var recommendations = new List<string>();
            
            try
            {
                if (!performanceCounters.ContainsKey(componentId)) return recommendations;
                
                var counters = performanceCounters[componentId];
                
                if (counters.AverageResponseTime > 1000)
                {
                    recommendations.Add("Optimize component for better response times");
                }
                
                if (counters.CalculateErrorRate() > 0.05)
                {
                    recommendations.Add("Investigate and fix error conditions");
                }
                
                if (counters.TotalActivities > 10000)
                {
                    recommendations.Add("High activity component - monitor for performance degradation");
                }
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to generate performance recommendations for {componentId}: {ex.Message}", LogLevel.Error);
            }
            
            return recommendations;
        }
        
        private static string CalculatePerformanceGrade(string componentId)
        {
            try
            {
                if (!performanceCounters.ContainsKey(componentId)) return "Unknown";
                
                var counters = performanceCounters[componentId];
                var score = 100.0;
                
                // Deduct points for slow response
                if (counters.AverageResponseTime > 1000)
                    score -= 20;
                else if (counters.AverageResponseTime > 500)
                    score -= 10;
                
                // Deduct points for errors
                var errorRate = counters.CalculateErrorRate();
                score -= errorRate * 50; // 50 points max deduction for errors
                
                return score switch
                {
                    >= 90 => "A",
                    >= 80 => "B", 
                    >= 70 => "C",
                    >= 60 => "D",
                    _ => "F"
                };
            }
            catch
            {
                return "Unknown";
            }
        }
        
        private static TrendAnalysis AnalyzeHealthTrends()
        {
            try
            {
                var snapshots = systemHistory.ToList();
                if (snapshots.Count < 2) return new TrendAnalysis();
                
                var recent = snapshots.Skip(Math.Max(0, snapshots.Count - 10)).ToList();
                var older = snapshots.Skip(Math.Max(0, snapshots.Count - 20)).Take(10).ToList();
                
                var recentAvgHealth = recent.Any() ? recent.Average(s => s.OverallHealth) : 0.5;
                var olderAvgHealth = older.Any() ? older.Average(s => s.OverallHealth) : 0.5;
                
                return new TrendAnalysis
                {
                    HealthTrend = recentAvgHealth > olderAvgHealth ? "Improving" : 
                                 recentAvgHealth < olderAvgHealth ? "Declining" : "Stable",
                    TrendStrength = Math.Abs(recentAvgHealth - olderAvgHealth),
                    RecentAverageHealth = recentAvgHealth,
                    PreviousAverageHealth = olderAvgHealth
                };
            }
            catch
            {
                return new TrendAnalysis { HealthTrend = "Unknown" };
            }
        }
        
        private static void LogMessage(string message, LogLevel level)
        {
            try
            {
                // Check if we should log this level
                if (!enableVerboseLogging && level < minimumLogLevel)
                {
                    return;
                }
                
                var logEntry = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] FKS_Infrastructure: {message}";
                
                switch (level)
                {
                    case LogLevel.Error:
                    case LogLevel.Critical:
                        NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab1);
                        break;
                    case LogLevel.Warning:
                        if (enableVerboseLogging) // Only show warnings if verbose logging is enabled
                        {
                            NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab1);
                        }
                        break;
                    case LogLevel.Information:
                        if (enableVerboseLogging) // Only show info if verbose logging is enabled
                        {
                            NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab2);
                        }
                        break;
                    case LogLevel.Debug:
                        // Only log debug in debug builds and when verbose logging is enabled
                        #if DEBUG
                        if (enableVerboseLogging)
                        {
                            NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab2);
                        }
                        #endif
                        break;
                }
            }
            catch
            {
                // Fail silently if logging fails
            }
        }
        
        private static void OnApplicationShutdown(object sender, EventArgs e)
        {
            Shutdown();
        }
        
        public static void Shutdown()
        {
            try
            {
                isShuttingDown = true;
                
                // Dispose timers
                healthCheckTimer?.Dispose();
                metricsCollectionTimer?.Dispose();
                cleanupTimer?.Dispose();
                
                // Clear collections
                componentMetrics.Clear();
                componentHealthData.Clear();
                circuitBreakers.Clear();
                performanceCounters.Clear();
                
                while (systemHistory.TryDequeue(out _)) { }
                
                lock (lockObj)
                {
                    heartbeats.Clear();
                }
                
                LogMessage("FKS Infrastructure shutdown completed", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"Error during shutdown: {ex.Message}", LogLevel.Error);
            }
        }
        
        #endregion

        #region Supporting Classes and Enums
        
        public class ComponentRegistrationInfo
        {
            public string ComponentType { get; set; }
            public string Version { get; set; }
            public bool IsCritical { get; set; }
            public TimeSpan ExpectedResponseTime { get; set; } = TimeSpan.FromSeconds(1);
            private const long GB = 1024 * 1024 * 1024;
            public long MaxMemoryUsage { get; set; } = 10 * GB; // 10GB default
        }

        public class ComponentActivity
        {
            public string ActivityType { get; set; }
            public TimeSpan? ExecutionTime { get; set; }
            public long? MemoryUsage { get; set; }
            public bool IsError { get; set; }
            public string ErrorMessage { get; set; }
            public DateTime Timestamp { get; set; } = DateTime.Now;
        }
        
        public class ComponentMetrics
        {
            public string ComponentId { get; set; }
            public DateTime RegistrationTime { get; set; }
            public string ComponentType { get; set; }
            public string Version { get; set; }
            public bool IsCritical { get; set; }
            public TimeSpan ExpectedResponseTime { get; set; }
            public long MaxMemoryUsage { get; set; }
            public DateTime LastActivity { get; set; }
            public long TotalActivities { get; set; }
            public double AverageResponseTime { get; set; }
            public long CurrentMemoryUsage { get; set; }
            public long PeakMemoryUsage { get; set; }
            public DateTime LastMetricsUpdate { get; set; }
        }
        
        public class ComponentHealthData
        {
            public string ComponentId { get; set; }
            public ComponentStatus Status { get; set; }
            public DateTime LastSeen { get; set; }
            public long ActivityCount { get; set; }
            public int ConsecutiveFailures { get; set; }
            public int TotalErrors { get; set; }
            public string LastError { get; set; }
            public DateTime LastErrorTime { get; set; }
            public DateTime LastRecovery { get; set; }
            public DateTime LastCriticalLog { get; set; } = DateTime.MinValue;
        }
        
        public class CircuitBreakerState
        {
            public CircuitState State { get; set; }
            public int FailureCount { get; set; }
            public DateTime LastFailureTime { get; set; }
            public DateTime OpenTime { get; set; }
        }
        
        public class PerformanceCounters
        {
            private readonly ConcurrentQueue<ActivityRecord> activities = new ConcurrentQueue<ActivityRecord>();
            
            public long TotalActivities { get; private set; }
            public double AverageResponseTime { get; private set; }
            public double MinResponseTime { get; private set; } = double.MaxValue;
            public double MaxResponseTime { get; private set; }
            public int ErrorCount { get; private set; }
            
            public void RecordActivity(ComponentActivity activity)
            {
                var record = new ActivityRecord
                {
                    Timestamp = activity.Timestamp,
                    ExecutionTime = activity.ExecutionTime?.TotalMilliseconds ?? 0,
                    IsError = activity.IsError
                };
                
                activities.Enqueue(record);
                TotalActivities++;
                
                if (activity.ExecutionTime.HasValue)
                {
                    var execTime = activity.ExecutionTime.Value.TotalMilliseconds;
                    AverageResponseTime = ((AverageResponseTime * (TotalActivities - 1)) + execTime) / TotalActivities;
                    MinResponseTime = Math.Min(MinResponseTime, execTime);
                    MaxResponseTime = Math.Max(MaxResponseTime, execTime);
                }
                
                if (activity.IsError)
                {
                    ErrorCount++;
                }
            }
            
            public double CalculateErrorRate()
            {
                return TotalActivities > 0 ? (double)ErrorCount / TotalActivities : 0;
            }
            
            public double CalculateThroughput(TimeSpan period)
            {
                var cutoff = DateTime.Now - period;
                var recentActivities = activities.Count(a => a.Timestamp >= cutoff);
                return recentActivities / period.TotalSeconds;
            }
            
            public void CleanupOldData(DateTime cutoffTime)
            {
                while (activities.TryPeek(out var activity) && activity.Timestamp < cutoffTime)
                {
                    activities.TryDequeue(out _);
                }
            }
            
            private class ActivityRecord
            {
                public DateTime Timestamp { get; set; }
                public double ExecutionTime { get; set; }
                public bool IsError { get; set; }
            }
        }
        
        public class SystemSnapshot
        {
            public DateTime Timestamp { get; set; }
            public double OverallHealth { get; set; }
            public int ComponentCount { get; set; }
            public int ActiveComponents { get; set; }
            public int CriticalAlerts { get; set; }
            public int WarningAlerts { get; set; }
        }
        
        public class SystemHealthSummary
        {
            public DateTime Timestamp { get; set; }
            public TimeSpan SystemUptime { get; set; }
            public double OverallHealthScore { get; set; }
            public Dictionary<string, ComponentHealthDetail> ComponentDetails { get; set; }
            public bool CriticalComponentsHealthy { get; set; }
            public double SystemLoad { get; set; }
            public double MemoryPressure { get; set; }
            public List<SystemAlert> AlertsActive { get; set; }
            public List<string> Recommendations { get; set; }
            public TrendAnalysis TrendAnalysis { get; set; }
        }
        
        public class ComponentHealthDetail
        {
            public string ComponentId { get; set; }
            public ComponentStatus Status { get; set; }
            public double HealthScore { get; set; }
            public DateTime LastSeen { get; set; }
            public double ResponseTime { get; set; }
            public long MemoryUsage { get; set; }
            public double ErrorRate { get; set; }
            public CircuitState CircuitBreakerState { get; set; }
            public List<string> Recommendations { get; set; }
        }
        
        public class ComponentPerformanceReport
        {
            public string ComponentId { get; set; }
            public TimeSpan Period { get; set; }
            public long TotalActivities { get; set; }
            public double AverageResponseTime { get; set; }
            public double MinResponseTime { get; set; }
            public double MaxResponseTime { get; set; }
            public int ErrorCount { get; set; }
            public double ErrorRate { get; set; }
            public double ThroughputPerSecond { get; set; }
            public long MemoryUsage { get; set; }
            public long PeakMemoryUsage { get; set; }
            public string PerformanceGrade { get; set; }
            public List<string> Recommendations { get; set; }
        }
        
        public class SystemAlert
        {
            public AlertLevel Level { get; set; }
            public string Component { get; set; }
            public string Message { get; set; }
            public DateTime Timestamp { get; set; }
            public string RecommendedAction { get; set; }
        }
        
        public class SystemResourceUsage
        {
            public DateTime Timestamp { get; set; }
            public double CpuUsage { get; set; }
            public long MemoryUsage { get; set; }
            public long MemoryUsageMB { get; set; }
            public int ThreadCount { get; set; }
            public int HandleCount { get; set; }
            public int ComponentCount { get; set; }
            public int ActiveCircuitBreakers { get; set; }
            public TimeSpan SystemUptime { get; set; }
        }
        
        public class TrendAnalysis
        {
            public string HealthTrend { get; set; }
            public double TrendStrength { get; set; }
            public double RecentAverageHealth { get; set; }
            public double PreviousAverageHealth { get; set; }
        }
        
        public enum ComponentStatus
        {
            Healthy,
            Warning,
            Critical,
            Unknown
        }
        
        public enum CircuitState
        {
            Closed,
            Open,
            HalfOpen
        }
        
        public enum AlertLevel
        {
            Information,
            Warning,
            Critical
        }
        
        public enum LogLevel
        {
            Debug,
            Information,
            Warning,
            Error,
            Critical
        }
        
        #endregion

        #region Performance Recording Helpers
        
        /// <summary>
        /// Helper class for automatic performance timing
        /// Usage: using (var timer = FKS_Infrastructure.StartTimer("FKS_Signals", "SignalGeneration")) { ... }
        /// </summary>
        public static PerformanceTimer StartTimer(string componentId, string operationType)
        {
            return new PerformanceTimer(componentId, operationType);
        }
        
        /// <summary>
        /// Record multiple performance metrics at once
        /// </summary>
        public static void RecordBatchMetrics(string componentId, params (string operationType, TimeSpan executionTime, bool isError)[] metrics)
        {
            foreach (var (operationType, executionTime, isError) in metrics)
            {
                RecordPerformanceMetric(componentId, operationType, executionTime, isError);
            }
        }
        
        /// <summary>
        /// Get performance summary for a component
        /// </summary>
        public static ComponentPerformanceSummary GetPerformanceSummary(string componentId)
        {
            try
            {
                if (!performanceCounters.TryGetValue(componentId, out var counters))
                {
                    return new ComponentPerformanceSummary { ComponentId = componentId, HasData = false };
                }
                
                var metrics = componentMetrics.TryGetValue(componentId, out var metricsValue) ? metricsValue : null;
                var healthData = componentHealthData.TryGetValue(componentId, out var healthValue) ? healthValue : null;
                
                return new ComponentPerformanceSummary
                {
                    ComponentId = componentId,
                    HasData = true,
                    TotalActivities = counters.TotalActivities,
                    AverageResponseTime = counters.AverageResponseTime,
                    ErrorRate = counters.CalculateErrorRate(),
                    ThroughputPerSecond = counters.CalculateThroughput(TimeSpan.FromMinutes(1)),
                    HealthStatus = healthData?.Status ?? ComponentStatus.Unknown,
                    LastActivity = metrics?.LastActivity ?? DateTime.MinValue,
                    Grade = CalculatePerformanceGrade(componentId)
                };
            }
            catch (Exception ex)
            {
                LogMessage($"Failed to get performance summary for {componentId}: {ex.Message}", LogLevel.Error);
                return new ComponentPerformanceSummary { ComponentId = componentId, HasData = false };
            }
        }
        
        /// <summary>
        /// Performance timer for automatic timing with using statement
        /// </summary>
        public class PerformanceTimer : IDisposable
        {
            private readonly string componentId;
            private readonly string operationType;
            private readonly Stopwatch stopwatch;
            private bool isError = false;
            
            public PerformanceTimer(string componentId, string operationType)
            {
                this.componentId = componentId;
                this.operationType = operationType;
                this.stopwatch = Stopwatch.StartNew();
            }
            
            public void MarkError()
            {
                isError = true;
            }
            
            public void Dispose()
            {
                stopwatch.Stop();
                RecordPerformanceMetric(componentId, operationType, stopwatch.Elapsed, isError);
            }
        }
        
        /// <summary>
        /// Component performance summary
        /// </summary>
        public class ComponentPerformanceSummary
        {
            public string ComponentId { get; set; }
            public bool HasData { get; set; }
            public long TotalActivities { get; set; }
            public double AverageResponseTime { get; set; }
            public double ErrorRate { get; set; }
            public double ThroughputPerSecond { get; set; }
            public ComponentStatus HealthStatus { get; set; }
            public DateTime LastActivity { get; set; }
            public string Grade { get; set; }
        }
        
        #endregion

        #region Helper Methods
        
        private static bool IsCriticalComponent(string componentId)
        {
            return criticalComponents.Contains(componentId);
        }
        
        private static void AttemptComponentRecovery(string componentId)
        {
            try
            {
                LogMessage($"Attempting recovery for component {componentId}", LogLevel.Information);
                
                // Reset circuit breaker if it exists
                if (circuitBreakers.ContainsKey(componentId))
                {
                    var circuitBreaker = circuitBreakers[componentId];
                    circuitBreaker.State = CircuitState.HalfOpen;
                    circuitBreaker.FailureCount = 0;
                }
                
                // Reset component health data
                if (componentHealthData.ContainsKey(componentId))
                {
                    var healthData = componentHealthData[componentId];
                    healthData.ConsecutiveFailures = 0;
                    healthData.LastRecovery = DateTime.Now;
                }
                
                // Force garbage collection to free up memory
                GC.Collect();
                GC.WaitForPendingFinalizers();
                
                LogMessage($"Recovery attempt completed for component {componentId}", LogLevel.Information);
            }
            catch (Exception ex)
            {
                LogMessage($"Component recovery failed for {componentId}: {ex.Message}", LogLevel.Error);
            }
        }
        
        private static void TriggerCircuitBreaker(string componentId)
        {
            try
            {
                var circuitBreaker = circuitBreakers.GetOrAdd(componentId, new CircuitBreakerState());
                circuitBreaker.FailureCount++;
                circuitBreaker.LastFailureTime = DateTime.Now;
                
                if (circuitBreaker.FailureCount >= 5) // Circuit breaker threshold
                {
                    circuitBreaker.State = CircuitState.Open;
                    circuitBreaker.OpenTime = DateTime.Now;
                    // Circuit breaker logging disabled to reduce spam
                    // LogMessage($"Circuit breaker opened for component {componentId}", LogLevel.Warning);
                }
            }
            catch (Exception)
            {
                // Circuit breaker error logging disabled to reduce spam
                // LogMessage($"Failed to trigger circuit breaker for {componentId}: {ex.Message}", LogLevel.Error);
            }
        }
        
        #endregion

        #region Logging Configuration
        
        /// <summary>
        /// Enable or disable verbose logging for debugging
        /// </summary>
        public static void SetVerboseLogging(bool enabled)
        {
            enableVerboseLogging = enabled;
            LogMessage($"Verbose logging {(enabled ? "enabled" : "disabled")}", LogLevel.Information);
        }
        
        /// <summary>
        /// Set the minimum log level
        /// </summary>
        public static void SetMinimumLogLevel(LogLevel level)
        {
            minimumLogLevel = level;
            LogMessage($"Minimum log level set to {level}", LogLevel.Information);
        }
        
        #endregion
    }
}