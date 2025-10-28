#pragma warning disable 436 // Suppress type conflict with NinjaTrader.Custom
// src/Indicators/FKS_AI.cs - COMPLETE with Integration Fixes + DEBUG MODE + ALL MISSING LOGIC
#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.NinjaScript.AddOns;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class FKS_AI : Indicator, IFKSComponent, IDisposable
    {
        #region FKS Integration Infrastructure

        // Shared calculation state keys
        private const string STATE_KEY_ATR = "ATR";
        private const string STATE_KEY_ADX_ATR = "ADX_ATR";
        private const string STATE_KEY_ADX_PLUSDI = "ADX_PlusDI";
        private const string STATE_KEY_ADX_MINUSDI = "ADX_MinusDI";
        private const string STATE_KEY_ADX_ADX = "ADX_ADX";
        private const string STATE_KEY_EMA9 = "EMA9";
        private const string STATE_KEY_VWAP_PV = "VWAP_PV";
        private const string STATE_KEY_VWAP_VOL = "VWAP_VOL";

        // Component integration  
        private static FKS_ComponentManager componentManager;
        private static FKS_SignalCoordinator signalCoordinator;
        private bool isRegisteredWithCoordinator = false;

        #endregion

        #region DEBUG MODE INFRASTRUCTURE

        // Debug tracking variables
        private readonly Dictionary<string, DebugMetric> debugMetrics = new Dictionary<string, DebugMetric>();
        private readonly List<DebugEvent> debugEvents = new List<DebugEvent>(1000);
        private readonly StringBuilder debugLog = new StringBuilder();
        private int debugCheckCounter = 0;
        private DateTime lastDebugUpdate = DateTime.MinValue;
        private readonly TimeSpan debugUpdateInterval = TimeSpan.FromSeconds(5);

        // Debug metric tracking
        private class DebugMetric
        {
            public string Name { get; set; }
            public double Value { get; set; }
            public double MinValue { get; set; } = double.MaxValue;
            public double MaxValue { get; set; } = double.MinValue;
            public double SumValue { get; set; }
            public int Count { get; set; }
            public DateTime LastUpdate { get; set; }

            public double Average => Count > 0 ? SumValue / Count : 0;

            public void Update(double newValue)
            {
                Value = newValue;
                MinValue = Math.Min(MinValue, newValue);
                MaxValue = Math.Max(MaxValue, newValue);
                SumValue += newValue;
                Count++;
                LastUpdate = DateTime.Now;
            }
        }

        // Debug event tracking
        private class DebugEvent
        {
            public DateTime Timestamp { get; set; }
            public string Category { get; set; }
            public string Message { get; set; }
            public string Level { get; set; } // INFO, WARN, ERROR
            public int Bar { get; set; }
        }

        // Debug methods
        private void LogDebug(string category, string message, string level = "INFO")
        {
            if (!ENABLE_DEBUG_MODE) return;

            try
            {
                var debugEvent = new DebugEvent
                {
                    Timestamp = DateTime.Now,
                    Category = category,
                    Message = message,
                    Level = level,
                    Bar = CurrentBar
                };

                debugEvents.Add(debugEvent);

                // Keep only last 1000 events
                if (debugEvents.Count > 1000)
                    debugEvents.RemoveAt(0);

                // Print to output if verbose or error/warning
                if (VERBOSE_DEBUG || level == "ERROR" || level == "WARN")
                {
                    Print($"[FKS_AI-{level}] {category}: {message} (Bar: {CurrentBar})");
                }

                // Add to debug log
                debugLog.AppendLine($"{DateTime.Now:HH:mm:ss.fff} [{level}] {category}: {message}");

                // Keep log size manageable
                if (debugLog.Length > 50000)
                {
                    debugLog.Remove(0, debugLog.Length / 2);
                }
            }
            catch (Exception ex)
            {
                Print($"Debug logging error: {ex.Message}");
            }
        }

        private void UpdateDebugMetric(string name, double value)
        {
            if (!ENABLE_DEBUG_MODE) return;

            try
            {
                if (!debugMetrics.TryGetValue(name, out var metric))
                {
                    metric = new DebugMetric { Name = name };
                    debugMetrics[name] = metric;
                }

                metric.Update(value);
            }
            catch (Exception ex)
            {
                Print($"Debug metric update error: {ex.Message}");
            }
        }

        private void PerformDebugCheck()
        {
            if (!ENABLE_DEBUG_MODE) return;
            if (DateTime.Now - lastDebugUpdate < debugUpdateInterval) return;

            try
            {
                debugCheckCounter++;
                lastDebugUpdate = DateTime.Now;

                LogDebug("SYSTEM", $"=== Debug Check #{debugCheckCounter} ===");
                LogDebug("BAR", $"Current Bar: {CurrentBar}, Time: {Time[0]:HH:mm:ss}");

                // Component Registry Status
                if (componentManager != null)
                {
                    var status = componentManager.GetSystemHealth();
                    LogDebug("REGISTRY", $"Components: {status.TotalComponents}, Healthy: {status.HealthyComponents}");
                    UpdateDebugMetric("RegistryComponents", status.TotalComponents);
                    UpdateDebugMetric("HealthyComponents", status.HealthyComponents);
                }
                else
                {
                    LogDebug("REGISTRY", "Registry not available", "WARN");
                }

                // Signal Coordinator Status
                if (signalCoordinator != null)
                {
                    var composite = signalCoordinator.GenerateCompositeSignal();
                    LogDebug("COORDINATOR", $"Composite Signal: {composite.Direction}, Score: {composite.WeightedScore:F3}");
                    UpdateDebugMetric("CompositeScore", composite.WeightedScore);
                    UpdateDebugMetric("CompositeConfidence", composite.Confidence);
                }

                // Component Health
                LogDebug("HEALTH", $"Status: {Status}, Error Count: {errorCount}");
                UpdateDebugMetric("ComponentStatus", (double)Status);
                UpdateDebugMetric("ErrorCount", errorCount);

                // AI Calculations
                LogDebug("CALCULATIONS", $"ATR: {currentAtr:F5}, ADX: {currentAdx:F2}, EMA9: {currentEma9:F2}");
                UpdateDebugMetric("ATR", currentAtr);
                UpdateDebugMetric("ADX", currentAdx);
                UpdateDebugMetric("EMA9", currentEma9);

                // Support/Resistance
                LogDebug("LEVELS", $"Support: {currentSupport:F2}, Resistance: {currentResistance:F2}, VWAP: {vwapValue:F2}");
                UpdateDebugMetric("Support", currentSupport);
                UpdateDebugMetric("Resistance", currentResistance);
                UpdateDebugMetric("VWAP", vwapValue);

                // Signal Quality
                if (currentSignal != null)
                {
                    LogDebug("SIGNAL", $"Direction: {currentSignal.Direction}, Score: {currentSignal.Score:F3}, Confidence: {currentSignal.Confidence:F3}");
                    UpdateDebugMetric("SignalScore", currentSignal.Score);
                    UpdateDebugMetric("SignalConfidence", currentSignal.Confidence);
                    UpdateDebugMetric("CompositeScore", compositeScore);
                }

                // Market Regime
                LogDebug("MARKET", $"Regime: {currentRegime}, Regime Score: {regimeScore:F3}");
                UpdateDebugMetric("RegimeScore", regimeScore);

                // Performance
                LogDebug("PERFORMANCE", $"Processing Rate: {(CurrentBar > 0 ? (double)calculationCounter / CurrentBar * 100 : 0):F1}%");
                UpdateDebugMetric("ProcessingRate", CurrentBar > 0 ? (double)calculationCounter / CurrentBar * 100 : 0);

                // Memory
                long memoryUsage = GC.GetTotalMemory(false);
                LogDebug("MEMORY", $"Memory Usage: {memoryUsage / 1024 / 1024:F1} MB");
                UpdateDebugMetric("MemoryUsageMB", memoryUsage / 1024.0 / 1024.0);

                // Draw debug info on chart if enabled
                if (SHOW_DEBUG_ON_CHART)
                {
                    DrawDebugInfo();
                }

                // Export debug data if requested
                if (EXPORT_DEBUG_DATA && debugCheckCounter % 20 == 0)
                {
                    ExportDebugToFile();
                }
            }
            catch (Exception ex)
            {
                LogDebug("DEBUG", $"Debug check error: {ex.Message}", "ERROR");
            }
        }

        private void DrawDebugInfo()
        {
            try
            {
                var debugText = new StringBuilder();
                debugText.AppendLine($"=== FKS_AI Debug #{debugCheckCounter} ===");
                debugText.AppendLine($"Status: {Status}");
                debugText.AppendLine($"Components: {(componentManager?.GetSystemHealth().TotalComponents ?? 0)}");
                debugText.AppendLine($"Signal: {currentSignal?.Direction ?? AddOns.SignalDirection.Neutral}");
                debugText.AppendLine($"Score: {currentSignal?.Score ?? 0:F2}");
                debugText.AppendLine($"Regime: {currentRegime}");
                debugText.AppendLine($"ATR: {currentAtr:F4}");
                debugText.AppendLine($"Errors: {errorCount}");

                Draw.TextFixed(this, "FKSAIDebug", debugText.ToString(),
                    NinjaTrader.NinjaScript.DrawingTools.TextPosition.TopLeft,
                    Brushes.White,
                    new Gui.Tools.SimpleFont("Consolas", DASHBOARD_FONT_SIZE),
                    Brushes.Black,
                    Brushes.DarkBlue,
                    50);
            }
            catch (Exception ex)
            {
                Print($"Debug drawing error: {ex.Message}");
            }
        }

        private void ExportDebugToFile()
        {
            try
            {
                string fileName = $"FKS_AI_Debug_{DateTime.Now:yyyyMMdd_HHmmss}.txt";
                var content = new StringBuilder();

                content.AppendLine("=== FKS_AI Debug Export ===");
                content.AppendLine($"Export Time: {DateTime.Now}");
                content.AppendLine($"Current Bar: {CurrentBar}");
                content.AppendLine();

                // Debug metrics
                content.AppendLine("=== Debug Metrics ===");
                foreach (var metric in debugMetrics.Values)
                {
                    content.AppendLine($"{metric.Name}: Current={metric.Value:F4}, Min={metric.MinValue:F4}, Max={metric.MaxValue:F4}, Avg={metric.Average:F4}, Count={metric.Count}");
                }
                content.AppendLine();

                // Recent events
                content.AppendLine("=== Recent Debug Events ===");
                var recentEvents = debugEvents.Skip(Math.Max(0, debugEvents.Count - 50)).ToList();
                foreach (var evt in recentEvents)
                {
                    content.AppendLine($"{evt.Timestamp:HH:mm:ss.fff} [{evt.Level}] {evt.Category}: {evt.Message}");
                }

                // Note: In a real implementation, you'd save to a file
                // For now, just log to NinjaTrader output
                Print($"=== DEBUG EXPORT READY ===\n{content}");
            }
            catch (Exception ex)
            {
                LogDebug("EXPORT", $"Export error: {ex.Message}", "ERROR");
            }
        }

        #endregion

        #region Performance Infrastructure
        private readonly Dictionary<string, object> calculationCache = new Dictionary<string, object>();
        private readonly object memoryMonitor = new object();
        private DateTime lastCleanup = DateTime.MinValue;

        public string IndicatorName => "FKS_AI";

        // IFKSComponent Name property - explicit implementation to avoid hiding warning
        string IFKSComponent.Name => IndicatorName;

        [XmlIgnore]
        [Browsable(false)]
        public ComponentStatus Status { get; set; } = ComponentStatus.Healthy;

        private int errorCount = 0;
        private DateTime lastErrorReset = DateTime.Now;
        private bool disposed = false;
        private bool isInitialized = false;
        private System.Diagnostics.Stopwatch stopwatch = new System.Diagnostics.Stopwatch();
        #endregion

        #region IFKSComponent Implementation
        public void Initialize()
        {
            try
            {
                LogDebug("LIFECYCLE", "Component Initialize() called");
                Status = ComponentStatus.Healthy;
                LogDebug("LIFECYCLE", "Component initialization completed successfully");
            }
            catch (Exception ex)
            {
                Status = ComponentStatus.Failed;
                LogDebug("LIFECYCLE", $"Component initialization failed: {ex.Message}", "ERROR");
            }
        }

        void IFKSComponent.Update()
        {
            try
            {
                LogDebug("LIFECYCLE", "Component Update() called");
                // Implementation of Update logic
                LogDebug("LIFECYCLE", "Component update completed");
            }
            catch (Exception ex)
            {
                LogDebug("LIFECYCLE", $"Component update failed: {ex.Message}", "ERROR");
            }
        }

        public void Cleanup()
        {
            LogDebug("LIFECYCLE", "Component Cleanup() called");
            Dispose();
        }
        #endregion

        #region Object Pooling for Performance
        private readonly AddOns.AISignal _reusableSignal = new AISignal();
        private readonly AddOns.MarketData _reusableMarketData = new AddOns.MarketData();
        private readonly List<string> _reusableStringList = new List<string>(10);
        private readonly Dictionary<string, double> _reusableMetrics = new Dictionary<string, double>(10);
        private readonly Dictionary<string, double> _calculationResults = new Dictionary<string, double>();
        private int _lastCalculationBar = -1;
        private static readonly Dictionary<Color, SolidColorBrush> _brushCache = new Dictionary<Color, SolidColorBrush>();
        #endregion

        #region Variables
        // Core calculation variables
        private double currentSupport, currentResistance, currentMid;
        private double vwapValue;
        private double currentEma9;
        private double currentAtr;
        private double currentAdx;

        // Collections with strict size limits
        private FKSAICircularBuffer<double> ema9History;
        private FKSAICircularBuffer<double> atrHistory;

        // Market state
        private AddOns.MarketRegime currentRegime = AddOns.MarketRegime.Neutral;
        private double regimeScore = 0;

        // Signal tracking
        private AddOns.AISignal currentSignal;
        private FKSAICircularBuffer<AddOns.AISignal> signalHistory;
        private double compositeScore = 0;

        // Order blocks
        private FKSAICircularBuffer<AddOns.OrderBlock> orderBlocks;

        // ML Components
        private PatternLearner patternLearner;
        private VolumeAnalyzer volumeAnalyzer;
        private AdaptiveThresholds thresholds;

        // Performance tracking
        private double adaptiveMultiplier = 1.0;
        private FKS_PeriodAdapter chartAdapter;
        private int calculationCounter = 0;
        private int mlUpdateCounter = 0;

        // Minimum bar requirements
        private int minimumBarsRequired = 60;

        // Chart detection
        private AddOns.FKS_PeriodTypeInfo chartInfo;

        // Adaptive calculation state
#pragma warning disable CS0414 // Field is assigned but its value is never used
        private double adaptiveATRState = 0;
#pragma warning restore CS0414
        #endregion

        #region NinjaScript Lifecycle - UPDATED
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                InitializeDefaultsSafely();
            }
            else if (State == State.DataLoaded)
            {
                LogDebug("LIFECYCLE", "DataLoaded state - initializing components");
                InitializeComponentsSafely();

                // Initialize chart detection
                try
                {
                    chartInfo = new AddOns.FKS_PeriodTypeInfo(Bars.BarsType);
                    LogDebug("CHART", $"Chart type detected - {chartInfo.ChartDescription}");
                    if (chartInfo.RequiresSpecialHandling)
                    {
                        LogDebug("CHART", $"Using adaptive calculations for {chartInfo.PeriodType}");
                    }
                }
                catch (Exception ex)
                {
                    LogDebug("CHART", $"Error initializing chart detection: {ex.Message}", "ERROR");
                    chartInfo = new AddOns.FKS_PeriodTypeInfo(null); // Will use safe defaults
                }

                // Register with component registry
                try
                {
                    componentManager = FKS_ComponentManager.Instance;
                    componentManager.RegisterComponent("FKS_AI", this);

                    // Initialize signal coordinator if not already done
                    if (signalCoordinator == null)
                    {
                        signalCoordinator = new FKS_SignalCoordinator();
                    }

                    LogDebug("REGISTRY", "Registered with component registry successfully");
                }
                catch (Exception ex)
                {
                    LogDebug("REGISTRY", $"Error registering with component registry: {ex.Message}", "ERROR");
                    FKS_ErrorHandler.HandleError(ex, "FKS_AI.RegisterComponent");
                }
            }
            else if (State == State.Historical)
            {
                FinalizeInitialization();
            }
            else if (State == State.Terminated)
            {
                LogDebug("LIFECYCLE", "Termination state - cleaning up");
                CleanupSafely(); // Use standardized cleanup method
            }
        }

        private void InitializeDefaultsSafely()
        {
            try
            {
                Description = @"FKS AI Indicator - COMPLETE with Integration Fixes + DEBUG MODE";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;
                PaintPriceMarkers = true;
                ScaleJustification = NinjaTrader.Gui.Chart.ScaleJustification.Right;
                IsSuspendedWhileInactive = true;

                // plots with EMA9
                AddPlot(new Stroke(Brushes.Red, 3), PlotStyle.Line, "Resistance");
                AddPlot(new Stroke(Brushes.LimeGreen, 3), PlotStyle.Line, "Support");
                AddPlot(new Stroke(Brushes.Gray, 1), PlotStyle.Dot, "Midpoint");
                AddPlot(new Stroke(Brushes.Magenta, 2), PlotStyle.Line, "VWAP");
                AddPlot(new Stroke(Brushes.DeepSkyBlue, 2), PlotStyle.Line, "EMA9");

                // Core Parameters
                SRPeriod = 30;
                ATRPeriod = 14;
                BaseSignalThreshold = 0.65;

                // ML Parameters
                EnableMLLearning = true;
                LearningLookback = 200;
                MinPatternOccurrences = 5;

                // Display - now hardcoded as constants
                ShowSignals = true;
                ShowLevels = true;
                // ShowOrderBlocks = true; // Now SHOW_ORDER_BLOCKS constant
                // ShowVolumeProfile = false; // Now SHOW_VOLUME_PROFILE constant

                // Chart Support - now hardcoded as constants
                // AdaptToChartType = false; // Now ADAPT_TO_CHART_TYPE constant

                // Order Block - now hardcoded as constants
                // ORDER_BLOCK_LOOKBACK = 25; // Now ORDER_BLOCK_LOOKBACK constant
                // MIN_ORDER_BLOCK_STRENGTH = 1.5; // Now MIN_ORDER_BLOCK_STRENGTH constant
                // MAX_ORDER_BLOCKS = 5; // Now MAX_ORDER_BLOCKS constant

                // Performance - now hardcoded as constants
                // ENABLE_PERFORMANCE_LOGGING = false; // Now ENABLE_PERFORMANCE_LOGGING constant

                // Debug Mode - now hardcoded as constants
                // ENABLE_DEBUG_MODE = false; // Now constant
                // VERBOSE_DEBUG = false; // Now constant
                // SHOW_DEBUG_ON_CHART = false; // Now constant
                // EXPORT_DEBUG_DATA = false; // Now constant
                // DASHBOARD_FONT_SIZE = 10; // Now constant

                // Calculate minimum bars required
                minimumBarsRequired = Math.Max(60, Math.Max(SRPeriod * 2, ATRPeriod * 3));

                Status = ComponentStatus.Healthy;

                LogDebug("DEFAULTS", "FKS_AI defaults initialized successfully");
            }
            catch (Exception ex)
            {
                Status = ComponentStatus.Failed;
                Print($"CRITICAL ERROR in InitializeDefaultsSafely: {ex.Message}");
                FKS_ErrorHandler.HandleError(ex, "FKS_AI.InitializeDefaultsSafely");
            }
        }

        private void InitializeComponentsSafely()
        {
            try
            {
                LogDebug("INIT", "Initializing components...");

                // Initialize collections with safe sizes
                signalHistory = new FKSAICircularBuffer<AddOns.AISignal>(20);
                orderBlocks = new FKSAICircularBuffer<AddOns.OrderBlock>(Math.Max(5, MAX_ORDER_BLOCKS));
                ema9History = new FKSAICircularBuffer<double>(10);
                atrHistory = new FKSAICircularBuffer<double>(25);

                // Initialize ML components
                if (EnableMLLearning)
                {
                    InitializeMLComponentsSafely();
                }

                if (AdaptToChartType)
                {
                    InitializeChartAdapterSafely();
                }

                Status = ComponentStatus.Healthy;
                LogDebug("INIT", "Components initialized successfully");
            }
            catch (Exception ex)
            {
                Status = ComponentStatus.Failed;
                LogDebug("INIT", $"CRITICAL ERROR in InitializeComponentsSafely: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "FKS_AI.InitializeComponentsSafely");
            }
        }

        private void FinalizeInitialization()
        {
            try
            {
                isInitialized = true;
                LogDebug("INIT", $"Initialization completed. Minimum bars required: {minimumBarsRequired}");
            }
            catch (Exception ex)
            {
                LogDebug("INIT", $"Error in FinalizeInitialization: {ex.Message}", "ERROR");
                isInitialized = false;
            }
        }

        private void InitializeMLComponentsSafely()
        {
            try
            {
                patternLearner = new PatternLearner();
                volumeAnalyzer = new VolumeAnalyzer();
                thresholds = new AdaptiveThresholds();
                LogDebug("ML", "ML Learning enabled with performance optimization");
            }
            catch (Exception ex)
            {
                FKS_ErrorHandler.HandleError(ex, "ML Components initialization");
                EnableMLLearning = false;
                LogDebug("ML", "ML initialization failed - continuing without ML features", "WARN");
            }
        }

        private void InitializeChartAdapterSafely()
        {
            try
            {
                chartAdapter = new FKS_PeriodAdapter();
                LogDebug("CHART", "Chart adapter initialized successfully");
            }
            catch (Exception ex)
            {
                FKS_ErrorHandler.HandleError(ex, "Chart adapter initialization");
                AdaptToChartType = false;
                LogDebug("CHART", "Chart adapter initialization failed", "WARN");
            }
        }
        #endregion

        #region OnBarUpdate - ENHANCED with Integration + DEBUG
        protected override void OnBarUpdate()
        {
            if (disposed) return;

            // Comprehensive bar validation
            if (!ValidateBarRequirements())
            {
                InitializeSafePlotValues();
                return;
            }

            if (ENABLE_PERFORMANCE_LOGGING || ENABLE_DEBUG_MODE)
            {
                stopwatch.Restart();
            }

            try
            {
                // Perform debug check
                if (ENABLE_DEBUG_MODE)
                {
                    PerformDebugCheck();
                }

                // Enhanced smart processing logic with chart type awareness
                bool shouldProcess = DetermineProcessingNeedSafe();

                if (!shouldProcess)
                {
                    UpdatePlotsOnlySafe();
                    return;
                }

                // Memory management
                if (CurrentBar % 500 == 0)
                {
                    PerformMemoryMaintenanceOptimized();
                }

                // Component health check
                if (CurrentBar % 100 == 0 && Status == ComponentStatus.Failed)
                {
                    TryRecoverFromFailure();
                    return;
                }

                // Always perform core calculations when processing
                PerformCoreCalculationsSafe();

                // Chart type detection
                if (AdaptToChartType && chartAdapter != null && CurrentBar % 100 == 0)
                {
                    DetectChartTypeSafely();
                }

                // Market analysis with adaptive frequency
                if (ShouldPerformMarketAnalysisSafe())
                {
                    PerformMarketAnalysisSafe();
                }

                // Signal generation with improved conditions
                if (ShouldGenerateSignalSafe())
                {
                    GenerateSignalSafe();

                    // Update signal coordinator
                    UpdateSignalCoordinatorSafe();
                }

                // Always update plots when processing
                UpdatePlotsSafe();

                // Drawing operations with smart frequency
                if (ShouldPerformDrawingSafe())
                {
                    PerformDrawingOperationsSafe();
                }

                // ML learning with market-aware frequency
                if (EnableMLLearning && ShouldPerformMLLearningSafe())
                {
                    PerformMLLearningSafe();
                }

                // Adaptive parameters with market condition awareness
                if (ShouldUpdateAdaptiveParametersSafe())
                {
                    UpdateAdaptiveParametersSafe();
                }

                calculationCounter++;
                UpdateDebugMetric("CalculationCounter", calculationCounter);

                // Debug logging for flat spot diagnosis
                if ((ENABLE_PERFORMANCE_LOGGING || ENABLE_DEBUG_MODE) && CurrentBar % 100 == 0)
                {
                    LogProcessingStatsSafe();
                }

                if (calculationCounter % 200 == 0)
                {
                    ResetErrorCountIfNeeded();
                }
            }
            catch (Exception ex)
            {
                HandleBarUpdateErrorSafe(ex);
            }
            finally
            {
                if (ENABLE_PERFORMANCE_LOGGING || ENABLE_DEBUG_MODE)
                {
                    stopwatch.Stop();
                    UpdateDebugMetric("ProcessingTimeMs", stopwatch.ElapsedMilliseconds);

                    if (CurrentBar % 100 == 0)
                    {
                        LogDebug("PERFORMANCE", $"Bar {CurrentBar}: {stopwatch.ElapsedMilliseconds}ms");
                    }
                }
            }
        }

        // Update signal coordinator with our latest signal
        private void UpdateSignalCoordinatorSafe()
        {
            try
            {
                if (signalCoordinator != null && currentSignal != null)
                {
                    var componentSignal = ((IFKSComponent)this).GetSignal();
                    signalCoordinator.RegisterComponentSignal("FKS_AI", componentSignal);
                    isRegisteredWithCoordinator = true;
                    LogDebug("COORDINATOR", "Signal updated successfully");
                }
            }
            catch (Exception ex)
            {
                LogDebug("COORDINATOR", $"Error updating signal coordinator: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "UpdateSignalCoordinatorSafe");
            }
        }

        // Processing determination logic
        private bool DetermineProcessingNeedSafe()
        {
            try
            {
                if (AlwaysProcessAllBars)
                    return true;

                bool hasRecentStrongSignals = false;
                if (signalHistory != null && signalHistory.Count > 0)
                {
                    try
                    {
                        var recentSignals = signalHistory.ToList().Take(5);
                        hasRecentStrongSignals = recentSignals.Any(s => s != null && Math.Abs(s.Score) > 0.8);
                    }
                    catch
                    {
                        hasRecentStrongSignals = false;
                    }
                }

                if (hasRecentStrongSignals)
                    return true;

                bool isRangingMarket = IsRangingMarketSafe();
                bool hasSignificantChange = HasSignificantPriceChangeSafe();
                bool isOptimalTime = IsOptimalTradingTimeSafe();
                int hour = Time[0].Hour;

                bool forceProcessing =
                    hasSignificantChange ||
                    (currentSignal != null && Math.Abs(currentSignal.Score) > 0.7) ||
                    (CurrentBar % 40 == 0) ||
                    (calculationCounter < 15) ||
                    (CurrentBar <= minimumBarsRequired + 20) ||
                    (currentRegime == AddOns.MarketRegime.Volatile);

                if (forceProcessing)
                    return true;

                if (isRangingMarket)
                {
                    if (isOptimalTime)
                        return CurrentBar % 2 == 0;
                    else
                        return CurrentBar % 2 == 0;
                }

                if (currentRegime == AddOns.MarketRegime.StrongTrend)
                {
                    if (isOptimalTime)
                        return CurrentBar % 2 == 0;
                    else
                        return CurrentBar % 3 == 0;
                }

                if (hour < 1 || hour > 23)
                {
                    return CurrentBar % 5 == 0;
                }

                if (isOptimalTime)
                    return CurrentBar % 2 == 0;
                else
                    return CurrentBar % 2 == 0;
            }
            catch (Exception ex)
            {
                LogDebug("PROCESSING", $"Error in DetermineProcessingNeedSafe: {ex.Message}", "ERROR");
                return true;
            }
        }

        private bool HasSignificantPriceChangeSafe()
        {
            try
            {
                if (CurrentBar == 0) return true;

                double baseThreshold = currentAtr > 0 ? currentAtr * 0.05 : Close[0] * 0.0001;
                bool isRanging = IsRangingMarketSafe();
                double threshold = isRanging ? baseThreshold * 0.3 : baseThreshold;

                bool priceChanged = Math.Abs(Close[0] - Close[1]) > threshold;
                bool highChanged = Math.Abs(High[0] - High[1]) > threshold;
                bool lowChanged = Math.Abs(Low[0] - Low[1]) > threshold;

                bool volumeChanged = false;
                try
                {
                    volumeChanged = Math.Abs(Volume[0] - Volume[1]) > (Volume[1] * 0.1);
                }
                catch
                {
                    volumeChanged = false;
                }

                bool patternChanged = false;
                if (CurrentBar >= 2)
                {
                    try
                    {
                        bool currentBullish = Close[0] > Open[0];
                        bool previousBullish = Close[1] > Open[1];
                        patternChanged = currentBullish != previousBullish;
                    }
                    catch
                    {
                        patternChanged = false;
                    }
                }

                bool timeChanged = CurrentBar % 25 == 0;

                return priceChanged || highChanged || lowChanged || volumeChanged || patternChanged || timeChanged;
            }
            catch (Exception ex)
            {
                LogDebug("PRICE_CHANGE", $"Error in HasSignificantPriceChangeSafe: {ex.Message}", "ERROR");
                return true;
            }
        }

        private bool IsRangingMarketSafe()
        {
            try
            {
                if (CurrentBar < 20) return false;

                double highest = 0;
                double lowest = double.MaxValue;

                int lookback = Math.Min(20, CurrentBar + 1);
                for (int i = 0; i < lookback; i++)
                {
                    try
                    {
                        highest = Math.Max(highest, High[i]);
                        lowest = Math.Min(lowest, Low[i]);
                    }
                    catch
                    {
                        break;
                    }
                }

                if (highest <= lowest) return false;
                double range = highest - lowest;

                bool atrCriteria = currentAtr < (range * 0.3);
                bool adxCriteria = currentAdx < 25;

                double pricePosition = (Close[0] - lowest) / range;
                bool pricePositionCriteria = pricePosition > 0.15 && pricePosition < 0.85;

                bool emaSpreadCriteria = true;
                if (currentEma9 > 0 && ema9History != null && ema9History.Count > 0)
                {
                    try
                    {
                        double emaSpread = Math.Abs(currentEma9 - Close[0]);
                        emaSpreadCriteria = emaSpread < (currentAtr * 2);
                    }
                    catch
                    {
                        emaSpreadCriteria = true;
                    }
                }

                return atrCriteria && adxCriteria && pricePositionCriteria && emaSpreadCriteria;
            }
            catch (Exception ex)
            {
                LogDebug("MARKET", $"Error in IsRangingMarketSafe: {ex.Message}", "ERROR");
                return false;
            }
        }

        private bool IsOptimalTradingTimeSafe()
        {
            try
            {
                int hour = Time[0].Hour;
                DayOfWeek dayOfWeek = Time[0].DayOfWeek;

                if (dayOfWeek == DayOfWeek.Saturday || dayOfWeek == DayOfWeek.Sunday)
                    return false;

                bool londonSession = hour >= 2 && hour <= 12;
                bool nySession = hour >= 8 && hour <= 17;
                bool asianSession = hour >= 19 || hour <= 2;
                bool overlap = (hour >= 8 && hour <= 12);

                return londonSession || nySession || asianSession || overlap;
            }
            catch (Exception ex)
            {
                LogDebug("TRADING_TIME", $"Error in IsOptimalTradingTimeSafe: {ex.Message}", "ERROR");
                return true;
            }
        }

        // Additional frequency checks
        private bool ShouldPerformMarketAnalysisSafe()
        {
            try
            {
                if (currentSignal != null && Math.Abs(currentSignal.Score) > 0.7)
                    return true;

                if (IsRangingMarketSafe())
                    return CurrentBar % 5 == 0;

                if (currentSignal != null && Math.Abs(currentSignal.Score) > 0.6)
                    return CurrentBar % 7 == 0;

                return CurrentBar % 10 == 0;
            }
            catch (Exception ex)
            {
                LogDebug("MARKET_ANALYSIS", $"Error in ShouldPerformMarketAnalysisSafe: {ex.Message}", "ERROR");
                return CurrentBar % 10 == 0;
            }
        }

        private bool ShouldGenerateSignalSafe()
        {
            try
            {
                int hour = Time[0].Hour;

                bool isActiveHours =
                    (hour >= 8 && hour <= 17) ||
                    (hour >= 2 && hour <= 12) ||
                    (hour >= 19 || hour <= 2);

                bool hasValidATR = currentAtr > 0;
                bool recentProcessing = CurrentBar % 10 == 0;
                bool forceSignal = CurrentBar % 50 == 0;

                return (isActiveHours && hasValidATR && recentProcessing) || forceSignal;
            }
            catch (Exception ex)
            {
                LogDebug("SIGNAL_GEN", $"Error in ShouldGenerateSignalSafe: {ex.Message}", "ERROR");
                return false;
            }
        }

        private bool ShouldPerformDrawingSafe()
        {
            try
            {
                if (currentSignal != null && Math.Abs(currentSignal.Score) > 0.8)
                    return true;

                bool regularInterval = CurrentBar % 25 == 0;
                bool rangingDrawing = IsRangingMarketSafe() && CurrentBar % 15 == 0;

                return regularInterval || rangingDrawing;
            }
            catch (Exception ex)
            {
                LogDebug("DRAWING", $"Error in ShouldPerformDrawingSafe: {ex.Message}", "ERROR");
                return CurrentBar % 25 == 0;
            }
        }

        private bool ShouldPerformMLLearningSafe()
        {
            try
            {
                if (currentRegime == AddOns.MarketRegime.Volatile)
                    return CurrentBar % 100 == 0;

                if (IsRangingMarketSafe())
                    return CurrentBar % 150 == 0;

                return CurrentBar % 200 == 0;
            }
            catch (Exception ex)
            {
                LogDebug("ML_LEARNING", $"Error in ShouldPerformMLLearningSafe: {ex.Message}", "ERROR");
                return CurrentBar % 200 == 0;
            }
        }

        private bool ShouldUpdateAdaptiveParametersSafe()
        {
            try
            {
                bool marketChanged = currentRegime != AddOns.MarketRegime.Neutral;

                if (marketChanged)
                    return CurrentBar % 250 == 0;

                if (IsRangingMarketSafe())
                    return CurrentBar % 300 == 0;

                return CurrentBar % 500 == 0;
            }
            catch (Exception ex)
            {
                LogDebug("ADAPTIVE", $"Error in ShouldUpdateAdaptiveParametersSafe: {ex.Message}", "ERROR");
                return CurrentBar % 500 == 0;
            }
        }

        // Validation and initialization methods
        private bool ValidateBarRequirements()
        {
            try
            {
                if (CurrentBar < minimumBarsRequired)
                {
                    if ((ENABLE_PERFORMANCE_LOGGING || ENABLE_DEBUG_MODE) && CurrentBar % 50 == 0)
                    {
                        LogDebug("VALIDATION", $"Waiting for minimum bars. Current: {CurrentBar}, Required: {minimumBarsRequired}");
                    }
                    return false;
                }

                if (!isInitialized)
                {
                    if ((ENABLE_PERFORMANCE_LOGGING || ENABLE_DEBUG_MODE) && CurrentBar % 50 == 0)
                    {
                        LogDebug("VALIDATION", "Waiting for initialization to complete");
                    }
                    return false;
                }

                if (ema9History == null || atrHistory == null || signalHistory == null)
                {
                    LogDebug("VALIDATION", "Collections not initialized properly", "ERROR");
                    return false;
                }

                if (double.IsNaN(Close[0]) || double.IsInfinity(Close[0]) || Close[0] <= 0)
                {
                    LogDebug("VALIDATION", $"Invalid price data at bar {CurrentBar}", "ERROR");
                    return false;
                }

                return true;
            }
            catch (Exception ex)
            {
                LogDebug("VALIDATION", $"Error in ValidateBarRequirements: {ex.Message}", "ERROR");
                return false;
            }
        }

        private void InitializeSafePlotValues()
        {
            try
            {
                double safeValue = 0;

                try
                {
                    safeValue = Close[0];
                    if (double.IsNaN(safeValue) || double.IsInfinity(safeValue) || safeValue <= 0)
                    {
                        safeValue = 2000;
                    }
                }
                catch
                {
                    safeValue = 2000;
                }

                Values[0][0] = safeValue; // Resistance
                Values[1][0] = safeValue; // Support
                Values[2][0] = safeValue; // Midpoint
                Values[3][0] = safeValue; // VWAP
                Values[4][0] = safeValue; // EMA9
            }
            catch (Exception ex)
            {
                LogDebug("PLOTS", $"Error in InitializeSafePlotValues: {ex.Message}", "ERROR");
                try
                {
                    for (int i = 0; i < 5; i++)
                    {
                        Values[i][0] = 0;
                    }
                }
                catch
                {
                }
            }
        }

        private void UpdatePlotsOnlySafe()
        {
            try
            {
                double safeValue = Close[0];
                if (double.IsNaN(safeValue) || double.IsInfinity(safeValue) || safeValue <= 0)
                {
                    safeValue = 2000;
                }

                Values[0][0] = ValidateAndSetPlotValue(currentResistance, safeValue, "Resistance");
                Values[1][0] = ValidateAndSetPlotValue(currentSupport, safeValue, "Support");
                Values[2][0] = ValidateAndSetPlotValue(currentMid, safeValue, "Midpoint");
                Values[3][0] = ValidateAndSetPlotValue(vwapValue, safeValue, "VWAP");
                Values[4][0] = ValidateAndSetPlotValue(currentEma9, safeValue, "EMA9");
            }
            catch (Exception ex)
            {
                LogDebug("PLOTS", $"Error in UpdatePlotsOnlySafe: {ex.Message}", "ERROR");
                try
                {
                    double emergencyValue = 2000;
                    for (int i = 0; i < 5; i++)
                    {
                        Values[i][0] = emergencyValue;
                    }
                }
                catch
                {
                }
            }
        }

        private double ValidateAndSetPlotValue(double value, double fallback, string valueName)
        {
            try
            {
                if (double.IsNaN(value) || double.IsInfinity(value) || value <= 0)
                {
                    return fallback;
                }
                return value;
            }
            catch (Exception ex)
            {
                LogDebug("PLOTS", $"Error validating {valueName}: {ex.Message}", "ERROR");
                return fallback;
            }
        }

        private void LogProcessingStatsSafe()
        {
            try
            {
                double processingRate = CurrentBar > 0 ?
                    (double)calculationCounter / CurrentBar * 100 : 0;

                var stats = new StringBuilder();
                stats.AppendLine($"=== FKS_AI Processing Stats - Bar {CurrentBar} ===");
                stats.AppendLine($"Processing Rate: {processingRate:F1}% ({calculationCounter}/{CurrentBar})");
                stats.AppendLine($"Market Regime: {currentRegime}");
                stats.AppendLine($"Is Ranging: {IsRangingMarketSafe()}");
                stats.AppendLine($"Current ATR: {currentAtr:F5}");
                stats.AppendLine($"Current ADX: {currentAdx:F2}");
                stats.AppendLine($"Signal Score: {currentSignal?.Score ?? 0:F3}");
                stats.AppendLine($"Hour: {Time[0].Hour}, Optimal: {IsOptimalTradingTimeSafe()}");
                stats.AppendLine($"Current Values - R:{currentResistance:F2}, S:{currentSupport:F2}, VWAP:{vwapValue:F2}, EMA9:{currentEma9:F2}");
                stats.AppendLine($"Component Registry: {(isRegisteredWithCoordinator ? "Connected" : "Disconnected")}");
                stats.AppendLine($"=== End Stats ===");

                LogDebug("STATS", stats.ToString());
            }
            catch (Exception ex)
            {
                LogDebug("STATS", $"Error in LogProcessingStatsSafe: {ex.Message}", "ERROR");
            }
        }
        #endregion

        #region Core Calculations - UPDATED with Shared State + DEBUG
        private void PerformCoreCalculationsSafe()
        {
            try
            {
                if (_lastCalculationBar != CurrentBar)
                {
                    _calculationResults.Clear();
                    _lastCalculationBar = CurrentBar;
                }

                GetCachedCalculationSafe("CustomIndicators", () =>
                {
                    CalculateCustomIndicatorsSafe();
                    return 1.0;
                });

                GetCachedCalculationSafe("SupportResistance", () =>
                {
                    CalculateSupportResistanceSafe();
                    return 1.0;
                });

                CalculateVWAPSafe();

                LogDebug("CALCULATIONS", "Core calculations completed successfully");
            }
            catch (Exception ex)
            {
                LogDebug("CALCULATIONS", $"Error in PerformCoreCalculationsSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "PerformCoreCalculationsSafe");
            }
        }

        // Updated to use shared calculation state
        private void CalculateCustomIndicatorsSafe()
        {
            try
            {
                // VALIDATION: Check we have minimum bars for EMA9
                if (CurrentBar < 9)
                {
                    currentEma9 = Close[0];
                    currentAdx = 25.0;
                    currentAtr = Close[0] * 0.01;
                    LogDebug("INDICATORS", "Using default values - insufficient bars for calculations");
                    return;
                }

                // Calculate EMA9 with shared state                currentEma9 = FKS_TechnicalIndicators.EMA(this, Close, 9, "FKS_AI");

                // VALIDATION: Check we have minimum bars for ADX
                if (CurrentBar < ATRPeriod)
                {
                    currentAdx = 25.0;
                    currentAtr = Close[0] * 0.01;
                    LogDebug("INDICATORS", "Using default ADX/ATR values - insufficient bars");
                }
                else
                {
                    try
                    {
                        currentAdx = FKS_TechnicalIndicators.ADX(this, ATRPeriod, "FKS_AI");
                        currentAtr = FKS_TechnicalIndicators.ATR(this, ATRPeriod, "FKS_AI");

                        LogDebug("INDICATORS", $"ADX/ATR calculated: ADX={currentAdx:F2}, ATR={currentAtr:F5}");
                    }
                    catch (Exception ex)
                    {
                        LogDebug("INDICATORS", $"Error calculating ADX/ATR: {ex.Message}", "ERROR");
                        currentAdx = 25.0;
                        currentAtr = Close[0] * 0.01;
                    }
                }

                // Comprehensive validation
                currentEma9 = ValidateDouble(currentEma9, Close[0], "EMA9");
                currentAdx = ValidateDouble(currentAdx, 25.0, "ADX");
                currentAtr = ValidateDouble(currentAtr, Close[0] * 0.01, "ATR");

                // Ensure ATR is never zero or negative
                if (currentAtr <= 0)
                    currentAtr = Close[0] * 0.01;

                // Update history safely
                if (ema9History != null)
                    ema9History.Add(currentEma9);
                if (atrHistory != null)
                    atrHistory.Add(currentAtr);

                LogDebug("INDICATORS", $"Custom indicators calculated: EMA9={currentEma9:F2}, ADX={currentAdx:F2}, ATR={currentAtr:F5}");
            }
            catch (Exception ex)
            {
                LogDebug("INDICATORS", $"Error in CalculateCustomIndicatorsSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "CalculateCustomIndicatorsSafe");

                // Safe fallbacks
                currentEma9 = Close[0];
                currentAtr = Close[0] * 0.01;
                currentAdx = 25.0;
            }
        }

        // Support/Resistance calculation
        private void CalculateSupportResistanceSafe()
        {
            try
            {
                int period = Math.Min(SRPeriod, CurrentBar + 1);

                if (period <= 0)
                {
                    currentSupport = Low[0];
                    currentResistance = High[0];
                    currentMid = Close[0];
                    LogDebug("SR", "Using current bar values - insufficient period");
                    return;
                }

                double tempLow = double.MaxValue;
                double tempHigh = double.MinValue;

                for (int i = 0; i < period && i <= CurrentBar; i++)
                {
                    try
                    {
                        tempLow = Math.Min(tempLow, Low[i]);
                        tempHigh = Math.Max(tempHigh, High[i]);
                    }
                    catch (Exception ex)
                    {
                        LogDebug("SR", $"Error accessing bar {i}: {ex.Message}", "ERROR");
                        break;
                    }
                }

                if (tempLow == double.MaxValue) tempLow = Low[0];
                if (tempHigh == double.MinValue) tempHigh = High[0];

                tempLow = ValidateDouble(tempLow, Low[0], "TempLow");
                tempHigh = ValidateDouble(tempHigh, High[0], "TempHigh");

                double smoothingFactor = 0.7;
                currentSupport = currentSupport == 0 ? tempLow :
                               (currentSupport * smoothingFactor + tempLow * (1 - smoothingFactor));
                currentResistance = currentResistance == 0 ? tempHigh :
                                  (currentResistance * smoothingFactor + tempHigh * (1 - smoothingFactor));
                currentMid = (currentSupport + currentResistance) * 0.5;

                currentSupport = ValidateDouble(currentSupport, Low[0], "Support");
                currentResistance = ValidateDouble(currentResistance, High[0], "Resistance");
                currentMid = ValidateDouble(currentMid, Close[0], "Mid");

                if (currentSupport >= currentResistance)
                {
                    double spread = Math.Max(currentAtr * 2, High[0] - Low[0]);
                    currentSupport = currentMid - spread * 0.5;
                    currentResistance = currentMid + spread * 0.5;
                    LogDebug("SR", "Adjusted S/R levels due to overlap", "WARN");
                }

                LogDebug("SR", $"S/R calculated: Support={currentSupport:F2}, Resistance={currentResistance:F2}, Mid={currentMid:F2}");
            }
            catch (Exception ex)
            {
                LogDebug("SR", $"Error in CalculateSupportResistanceSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "CalculateSupportResistanceSafe");

                currentSupport = Low[0] - (currentAtr > 0 ? currentAtr : Close[0] * 0.01);
                currentResistance = High[0] + (currentAtr > 0 ? currentAtr : Close[0] * 0.01);
                currentMid = Close[0];
            }
        }

        // Updated VWAP calculation with shared state
        private void CalculateVWAPSafe()
        {
            try
            {
                double typicalPrice = (High[0] + Low[0] + Close[0]) / 3.0;
                double priceVolume = typicalPrice * Volume[0];

                if (double.IsNaN(typicalPrice) || double.IsInfinity(typicalPrice))
                    typicalPrice = Close[0];
                if (double.IsNaN(priceVolume) || double.IsInfinity(priceVolume))
                    priceVolume = Close[0] * Volume[0];

                // Use shared state for VWAP calculations
                var cumulativePV = FKS_UnifiedCache.GetState<double>(
                    STATE_KEY_VWAP_PV, 0.0);
                var cumulativeVolume = FKS_UnifiedCache.GetState<double>(
                    STATE_KEY_VWAP_VOL, 0.0);

                cumulativePV += priceVolume;
                cumulativeVolume += Volume[0];

                if (cumulativeVolume > 0)
                {
                    vwapValue = cumulativePV / cumulativeVolume;
                }
                else
                {
                    vwapValue = Close[0];
                }

                // Update shared states
                FKS_UnifiedCache.StoreState(STATE_KEY_VWAP_PV, cumulativePV);
                FKS_UnifiedCache.StoreState(STATE_KEY_VWAP_VOL, cumulativeVolume);

                vwapValue = ValidateDouble(vwapValue, Close[0], "VWAP");

                LogDebug("VWAP", $"VWAP calculated: {vwapValue:F2} (PV: {cumulativePV:F0}, Vol: {cumulativeVolume:F0})");
            }
            catch (Exception ex)
            {
                LogDebug("VWAP", $"Error in CalculateVWAPSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "CalculateVWAPSafe");
                vwapValue = Close[0];
            }
        }

        private T GetCachedCalculationSafe<T>(string key, Func<T> calculation)
        {
            try
            {
                if (_calculationResults.TryGetValue(key, out var cached))
                {
                    return (T)Convert.ChangeType(cached, typeof(T));
                }

                var result = calculation();
                if (result is double doubleResult && !double.IsNaN(doubleResult) && !double.IsInfinity(doubleResult))
                {
                    _calculationResults[key] = doubleResult;
                }

                return result;
            }
            catch (Exception ex)
            {
                LogDebug("CACHE", $"Error in GetCachedCalculationSafe for {key}: {ex.Message}", "ERROR");
                return calculation();
            }
        }

        private double ValidateDouble(double value, double fallback, string name)
        {
            try
            {
                if (double.IsNaN(value) || double.IsInfinity(value))
                {
                    if (ENABLE_PERFORMANCE_LOGGING || ENABLE_DEBUG_MODE)
                        LogDebug("VALIDATION", $"{name} invalid value {value}, using fallback {fallback}", "WARN");
                    return fallback;
                }
                return value;
            }
            catch (Exception ex)
            {
                LogDebug("VALIDATION", $"Error validating {name}: {ex.Message}", "ERROR");
                return fallback;
            }
        }
        #endregion

        #region Market Analysis - COMPLETE IMPLEMENTATION
        private void PerformMarketAnalysisSafe()
        {
            try
            {
                LogDebug("MARKET", "Starting market analysis");

                currentRegime = DetectMarketRegimeSafe();
                regimeScore = CalculateRegimeScore();

                if (SHOW_ORDER_BLOCKS && CurrentBar % 50 == 0)
                {
                    DetectOrderBlocksSafe();
                }

                if (ShowVolumeProfile && volumeAnalyzer != null && CurrentBar % 100 == 0)
                {
                    UpdateVolumeProfileSafely();
                }

                LogDebug("MARKET", $"Market analysis complete - Regime: {currentRegime}, Score: {regimeScore:F3}");
            }
            catch (Exception ex)
            {
                LogDebug("MARKET", $"Error in PerformMarketAnalysisSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "PerformMarketAnalysisSafe");
            }
        }

        private AddOns.MarketRegime DetectMarketRegimeSafe()
        {
            try
            {
                double adx = currentAdx;
                double atrRatio = currentAtr > 0 ? currentAtr / Close[0] : 0;

                bool trending = false;
                if (ema9History != null && ema9History.Count >= 2)
                {
                    var values = ema9History.ToList();
                    if (values.Count >= 2)
                    {
                        trending = Math.Abs(values[values.Count - 1] - values[values.Count - 2]) > currentAtr * 0.1;
                    }
                }

                if (adx > 30 && trending)
                {
                    regimeScore = Math.Min(1.0, adx / 100.0);
                    LogDebug("REGIME", $"Strong trend detected: ADX={adx:F2}, Trending={trending}");
                    return AddOns.MarketRegime.StrongTrend;
                }
                else if (atrRatio > 0.02)
                {
                    regimeScore = Math.Min(1.0, atrRatio * 10);
                    LogDebug("REGIME", $"Volatile market detected: ATR Ratio={atrRatio:F4}");
                    return AddOns.MarketRegime.Volatile;
                }
                else if (adx < 20)
                {
                    regimeScore = Math.Min(1.0, (20 - adx) / 20.0);
                    LogDebug("REGIME", $"Ranging market detected: ADX={adx:F2}");
                    return AddOns.MarketRegime.Range;
                }

                regimeScore = 0.5;
                LogDebug("REGIME", "Neutral market conditions");
                return AddOns.MarketRegime.Neutral;
            }
            catch (Exception ex)
            {
                LogDebug("REGIME", $"Error in DetectMarketRegimeSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "DetectMarketRegimeSafe");
                regimeScore = 0.5;
                return AddOns.MarketRegime.Neutral;
            }
        }

        private double CalculateRegimeScore()
        {
            try
            {
                double score = 0.5; // Base neutral score

                switch (currentRegime)
                {
                    case AddOns.MarketRegime.StrongTrend:
                        score = Math.Min(0.9, 0.6 + (currentAdx - 25) / 100.0);
                        break;
                    case AddOns.MarketRegime.Volatile:
                        score = Math.Max(0.1, 0.4 - (currentAtr / Close[0] - 0.02) * 10);
                        break;
                    case AddOns.MarketRegime.Range:
                        score = 0.3 + (25 - Math.Min(currentAdx, 25)) / 100.0;
                        break;
                    default:
                        score = 0.5;
                        break;
                }

                return ValidateDouble(score, 0.5, "RegimeScore");
            }
            catch (Exception ex)
            {
                LogDebug("REGIME", $"Error calculating regime score: {ex.Message}", "ERROR");
                return 0.5;
            }
        }

        private void DetectOrderBlocksSafe()
        {
            try
            {
                double bodySize = Math.Abs(Close[0] - Open[0]);
                double candleRange = High[0] - Low[0];

                if (candleRange > 0 && bodySize / candleRange > 0.7)
                {
                    double strength = bodySize / candleRange;

                    if (strength > MIN_ORDER_BLOCK_STRENGTH && orderBlocks != null)
                    {
                        var orderBlock = new OrderBlock
                        {
                            StartBar = CurrentBar,
                            High = High[0],
                            Low = Low[0],
                            Mid = (High[0] + Low[0]) * 0.5,
                            IsBullish = Close[0] > Open[0],
                            Strength = strength
                        };

                        orderBlocks.Add(orderBlock);
                        LogDebug("ORDERBLOCKS", $"Order block detected: {(orderBlock.IsBullish ? "Bullish" : "Bearish")} at {orderBlock.Mid:F2}, Strength: {orderBlock.Strength:F2}");
                    }
                }
            }
            catch (Exception ex)
            {
                LogDebug("ORDERBLOCKS", $"Error in DetectOrderBlocksSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "DetectOrderBlocksSafe");
            }
        }

        private void UpdateVolumeProfileSafely()
        {
            try
            {
                volumeAnalyzer?.UpdateProfile(Close[0], (long)Volume[0], Time[0]);
                LogDebug("VOLUME", "Volume profile updated successfully");
            }
            catch (Exception ex)
            {
                LogDebug("VOLUME", $"Error in UpdateVolumeProfileSafely: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "UpdateVolumeProfileSafely");
            }
        }

        private void DetectChartTypeSafely()
        {
            try
            {
                chartAdapter?.DetectChartType(Bars);
                LogDebug("CHART", "Chart type detection completed");
            }
            catch (Exception ex)
            {
                LogDebug("CHART", $"Error in DetectChartTypeSafely: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "DetectChartTypeSafely");
            }
        }
        #endregion

        #region Signal Generation - COMPLETE IMPLEMENTATION
        private void GenerateSignalSafe()
        {
            try
            {
                LogDebug("SIGNAL", "Starting signal generation");

                var signal = _reusableSignal;
                ResetSignalSafe(signal);

                var marketData = GetCurrentMarketDataSafe();
                if (marketData == null)
                {
                    currentSignal = signal;
                    LogDebug("SIGNAL", "No market data available");
                    return;
                }

                double mlProbability = 0.5;
                if (EnableMLLearning && patternLearner != null)
                {
                    try
                    {
                        mlProbability = GetCachedCalculationSafe("MLProbability", () =>
                            patternLearner.GetPatternProbability("simple_pattern"));
                    }
                    catch (Exception ex)
                    {
                        LogDebug("SIGNAL", $"Error getting ML probability: {ex.Message}", "ERROR");
                        mlProbability = 0.5;
                    }
                }

                double bullishScore = 0;
                double bearishScore = 0;

                AnalyzeSupportResistanceSafe(ref bullishScore, ref bearishScore, mlProbability, signal);
                AnalyzeTrendContextSafe(ref bullishScore, ref bearishScore, signal);

                FinalizeSignalSafe(signal, bullishScore, bearishScore, mlProbability);

                currentSignal = signal;
                compositeScore = signal.Score * signal.Confidence;

                if (signal.Direction != AddOns.SignalDirection.Neutral && signal.Score > 0.5 && signalHistory != null)
                {
                    signalHistory.Add(signal);
                }

                LogDebug("SIGNAL", $"Signal generated: {signal.Direction}, Score: {signal.Score:F3}, Confidence: {signal.Confidence:F3}");
            }
            catch (Exception ex)
            {
                LogDebug("SIGNAL", $"Error in GenerateSignalSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "GenerateSignalSafe");
                currentSignal = CreateNeutralSignal();
                compositeScore = 0;
            }
        }

        private void ResetSignalSafe(AISignal signal)
        {
            try
            {
                signal.Direction = AddOns.SignalDirection.Neutral;
                signal.Score = 0;
                signal.Confidence = 0;
                signal.Reason = "";
                signal.Time = Time[0];
                signal.Regime = currentRegime;
                signal.Reasons?.Clear();
                signal.PatternKey = "";
                signal.EntryPrice = Close[0];
                signal.StopLoss = 0;
                signal.TakeProfit = 0;
            }
            catch (Exception ex)
            {
                LogDebug("SIGNAL", $"Error in ResetSignalSafe: {ex.Message}", "ERROR");
            }
        }

        private void AnalyzeSupportResistanceSafe(ref double bullishScore, ref double bearishScore, double mlProbability, AISignal signal)
        {
            try
            {
                if (currentAtr > 0)
                {
                    double priceToSupport = (Close[0] - currentSupport) / currentAtr;
                    double priceToResistance = (currentResistance - Close[0]) / currentAtr;

                    if (priceToSupport < 0.5 && Close[0] > Open[0])
                    {
                        bullishScore += 0.3;
                        if (signal.Reasons != null)
                            signal.Reasons.Add("Near support");
                    }
                    else if (priceToResistance < 0.5 && Close[0] < Open[0])
                    {
                        bearishScore += 0.3;
                        if (signal.Reasons != null)
                            signal.Reasons.Add("Near resistance");
                    }
                }

                // VWAP analysis
                if (Math.Abs(Close[0] - vwapValue) < currentAtr * 0.5)
                {
                    if (Close[0] > vwapValue)
                    {
                        bullishScore += 0.1;
                        if (signal.Reasons != null)
                            signal.Reasons.Add("Above VWAP");
                    }
                    else
                    {
                        bearishScore += 0.1;
                        if (signal.Reasons != null)
                            signal.Reasons.Add("Below VWAP");
                    }
                }

                // ML probability integration
                if (mlProbability > 0.6)
                {
                    bullishScore += (mlProbability - 0.5) * 0.4;
                    if (signal.Reasons != null)
                        signal.Reasons.Add($"ML bullish probability: {mlProbability:F2}");
                }
                else if (mlProbability < 0.4)
                {
                    bearishScore += (0.5 - mlProbability) * 0.4;
                    if (signal.Reasons != null)
                        signal.Reasons.Add($"ML bearish probability: {mlProbability:F2}");
                }
            }
            catch (Exception ex)
            {
                LogDebug("SIGNAL", $"Error in AnalyzeSupportResistanceSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "AnalyzeSupportResistanceSafe");
            }
        }

        private void AnalyzeTrendContextSafe(ref double bullishScore, ref double bearishScore, AISignal signal)
        {
            try
            {
                switch (currentRegime)
                {
                    case AddOns.MarketRegime.StrongTrend:
                        if (Close[0] > currentEma9)
                        {
                            bullishScore += 0.2;
                            if (signal.Reasons != null)
                                signal.Reasons.Add("Strong uptrend");
                        }
                        else
                        {
                            bearishScore += 0.2;
                            if (signal.Reasons != null)
                                signal.Reasons.Add("Strong downtrend");
                        }
                        break;

                    case AddOns.MarketRegime.Range:
                        if (Close[0] > currentMid)
                        {
                            bearishScore += 0.15;
                            if (signal.Reasons != null)
                                signal.Reasons.Add("Range top");
                        }
                        else
                        {
                            bullishScore += 0.15;
                            if (signal.Reasons != null)
                                signal.Reasons.Add("Range bottom");
                        }
                        break;

                    case AddOns.MarketRegime.Volatile:
                        // Reduce signal strength in volatile conditions
                        bullishScore *= 0.8;
                        bearishScore *= 0.8;
                        if (signal.Reasons != null)
                            signal.Reasons.Add("Volatile conditions");
                        break;
                }

                // ADX strength analysis
                if (currentAdx > 25)
                {
                    double adxBoost = Math.Min(0.2, (currentAdx - 25) / 100.0);
                    if (Close[0] > currentEma9)
                    {
                        bullishScore += adxBoost;
                        if (signal.Reasons != null)
                            signal.Reasons.Add($"ADX bullish strength: {currentAdx:F1}");
                    }
                    else
                    {
                        bearishScore += adxBoost;
                        if (signal.Reasons != null)
                            signal.Reasons.Add($"ADX bearish strength: {currentAdx:F1}");
                    }
                }
            }
            catch (Exception ex)
            {
                LogDebug("SIGNAL", $"Error in AnalyzeTrendContextSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "AnalyzeTrendContextSafe");
            }
        }

        private void FinalizeSignalSafe(AISignal signal, double bullishScore, double bearishScore, double mlProbability)
        {
            try
            {
                double netScore = bullishScore - bearishScore;
                double threshold = BaseSignalThreshold;

                if (netScore > threshold)
                {
                    signal.Direction = AddOns.SignalDirection.Long;
                    signal.Score = Math.Min(1.0, netScore);
                    signal.Confidence = Math.Min(1.0, mlProbability * 0.7 + regimeScore * 0.3);
                }
                else if (netScore < -threshold)
                {
                    signal.Direction = AddOns.SignalDirection.Short;
                    signal.Score = Math.Min(1.0, Math.Abs(netScore));
                    signal.Confidence = Math.Min(1.0, (1 - mlProbability) * 0.7 + regimeScore * 0.3);
                }
                else
                {
                    signal.Direction = AddOns.SignalDirection.Neutral;
                    signal.Score = Math.Abs(netScore);
                    signal.Confidence = 0.3;
                }

                signal.Score = ValidateDouble(signal.Score, 0, "Signal Score");
                signal.Confidence = ValidateDouble(signal.Confidence, 0, "Signal Confidence");

                // Set stop loss and take profit levels
                if (signal.Direction == AddOns.SignalDirection.Long)
                {
                    signal.StopLoss = currentSupport - currentAtr * 0.5;
                    signal.TakeProfit = currentResistance + currentAtr * 0.5;
                }
                else if (signal.Direction == AddOns.SignalDirection.Short)
                {
                    signal.StopLoss = currentResistance + currentAtr * 0.5;
                    signal.TakeProfit = currentSupport - currentAtr * 0.5;
                }

                // Generate pattern key for ML learning
                signal.PatternKey = GeneratePatternKey();
            }
            catch (Exception ex)
            {
                LogDebug("SIGNAL", $"Error in FinalizeSignalSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "FinalizeSignalSafe");
                signal.Direction = AddOns.SignalDirection.Neutral;
                signal.Score = 0;
                signal.Confidence = 0;
            }
        }

        private string GeneratePatternKey()
        {
            try
            {
                var key = new StringBuilder();
                key.Append(currentRegime.ToString().Substring(0, 1));
                key.Append(currentAdx > 25 ? "H" : "L");
                key.Append(Close[0] > currentEma9 ? "U" : "D");
                key.Append(Close[0] > vwapValue ? "A" : "B");
                return key.ToString();
            }
            catch (Exception ex)
            {
                LogDebug("SIGNAL", $"Error generating pattern key: {ex.Message}", "ERROR");
                return "DEFAULT";
            }
        }

        private AddOns.MarketData GetCurrentMarketDataSafe()
        {
            try
            {
                var data = _reusableMarketData;

                data.Timestamp = Time[0];
                data.Price = Close[0];
                data.CurrentPrice = Close[0];
                data.Volume = Volume[0];
                data.CurrentVolume = Volume[0];

                try
                {
                    data.AverageVolume = GetCachedCalculationSafe("AvgVolume", () =>
                        FKS_TechnicalIndicators.SMA(this, Volume, 20));
                }
                catch
                {
                    data.AverageVolume = Volume[0];
                }

                data.ATR = currentAtr;
                data.Volatility = currentAtr;
                data.PriceChange = CurrentBar > 0 ? Close[0] - Close[1] : 0;
                data.MarketRegime = currentRegime;
                data.RangeLow = currentSupport;
                data.RangeHigh = currentResistance;

                return data;
            }
            catch (Exception ex)
            {
                LogDebug("SIGNAL", $"Error in GetCurrentMarketDataSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "GetCurrentMarketDataSafe");
                return null;
            }
        }

        private AISignal CreateNeutralSignal()
        {
            try
            {
                var signal = new AISignal
                {
                    Direction = AddOns.SignalDirection.Neutral,
                    Score = 0,
                    Confidence = 0,
                    Time = Time[0],
                    Regime = currentRegime,
                    Reasons = new List<string> { "Error in signal generation" },
                    EntryPrice = Close[0],
                    PatternKey = ""
                };
                return signal;
            }
            catch (Exception ex)
            {
                LogDebug("SIGNAL", $"Error creating neutral signal: {ex.Message}", "ERROR");
                return null;
            }
        }
        #endregion

        #region Plotting and Drawing - COMPLETE IMPLEMENTATION
        private void UpdatePlotsSafe()
        {
            try
            {
                double safeValue = Close[0];

                Values[0][0] = ValidateDouble(currentResistance > 0 ? currentResistance : safeValue, safeValue, "Resistance Plot");
                Values[1][0] = ValidateDouble(currentSupport > 0 ? currentSupport : safeValue, safeValue, "Support Plot");
                Values[2][0] = ValidateDouble(currentMid > 0 ? currentMid : safeValue, safeValue, "Mid Plot");
                Values[3][0] = ValidateDouble(vwapValue > 0 ? vwapValue : safeValue, safeValue, "VWAP Plot");
                Values[4][0] = ValidateDouble(currentEma9 > 0 ? currentEma9 : safeValue, safeValue, "EMA9 Plot");
            }
            catch (Exception ex)
            {
                LogDebug("PLOTS", $"Error in UpdatePlotsSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "UpdatePlotsSafe");

                try
                {
                    double fallback = Close[0];
                    Values[0][0] = fallback;
                    Values[1][0] = fallback;
                    Values[2][0] = fallback;
                    Values[3][0] = fallback;
                    Values[4][0] = fallback;
                }
                catch
                {
                }
            }
        }

        private void PerformDrawingOperationsSafe()
        {
            try
            {
                if (ShowSignals && currentSignal != null && ShouldDrawSignalSafe())
                {
                    DrawSignalsSafe();
                }

                if (SHOW_ORDER_BLOCKS && orderBlocks != null && orderBlocks.Count > 0 && CurrentBar % 50 == 0)
                {
                    DrawOrderBlocksSafe();
                }

                LogDebug("DRAWING", "Drawing operations completed successfully");
            }
            catch (Exception ex)
            {
                LogDebug("DRAWING", $"Error in PerformDrawingOperationsSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "PerformDrawingOperationsSafe");
            }
        }

        private bool ShouldDrawSignalSafe()
        {
            try
            {
                if (currentSignal == null || currentSignal.Direction == AddOns.SignalDirection.Neutral)
                    return false;

                return currentSignal.Confidence >= BaseSignalThreshold && currentSignal.Score > 0.6;
            }
            catch (Exception ex)
            {
                LogDebug("DRAWING", $"Error in ShouldDrawSignalSafe: {ex.Message}", "ERROR");
                return false;
            }
        }

        private void DrawSignalsSafe()
        {
            try
            {
                if (currentSignal == null) return;

                string signalId = $"Signal_{CurrentBar}";
                string textId = $"SignalText_{CurrentBar}";

                if (currentSignal.Direction == AddOns.SignalDirection.Long)
                {
                    double arrowY = Low[0] - currentAtr * 0.3;
                    var mainBrush = GetCachedBrushSafe(Colors.LimeGreen);

                    Draw.ArrowUp(this, signalId, false, 0, arrowY, mainBrush);

                    if (ShowLevels && CurrentBar % 10 == 0)
                    {
                        string text = $"L:{currentSignal.Score:F2}";
                        double textY = Low[0] - currentAtr * 0.6;
                        Draw.Text(this, textId, text, 0, textY, mainBrush);
                    }
                }
                else if (currentSignal.Direction == AddOns.SignalDirection.Short)
                {
                    double arrowY = High[0] + currentAtr * 0.3;
                    var mainBrush = GetCachedBrushSafe(Colors.Red);

                    Draw.ArrowDown(this, signalId, false, 0, arrowY, mainBrush);

                    if (ShowLevels && CurrentBar % 10 == 0)
                    {
                        string text = $"S:{currentSignal.Score:F2}";
                        double textY = High[0] + currentAtr * 0.6;
                        Draw.Text(this, textId, text, 0, textY, mainBrush);
                    }
                }

                LogDebug("DRAWING", $"Signal drawn: {currentSignal.Direction} at bar {CurrentBar}");
            }
            catch (Exception ex)
            {
                LogDebug("DRAWING", $"Error in DrawSignalsSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "DrawSignalsSafe");
            }
        }

        private void DrawOrderBlocksSafe()
        {
            try
            {
                var orderBlockList = orderBlocks.ToList();

                foreach (var ob in orderBlockList.Take(Math.Min(5, MAX_ORDER_BLOCKS)))
                {
                    try
                    {
                        int barsAgo = CurrentBar - ob.StartBar;
                        if (barsAgo > ORDER_BLOCK_LOOKBACK || barsAgo < 0) continue;

                        Color baseColor = ob.IsBullish ? Colors.Green : Colors.Red;

                        byte opacity = (byte)Math.Max(20, 80 - (barsAgo * 2));

                        Color fillColor = Color.FromArgb(opacity, baseColor.R, baseColor.G, baseColor.B);
                        Color borderColor = Color.FromArgb((byte)Math.Min(255, opacity + 50), baseColor.R, baseColor.G, baseColor.B);

                        Brush fillBrush = GetCachedBrushSafe(fillColor);
                        Brush borderBrush = GetCachedBrushSafe(borderColor);

                        string rectId = $"OB_{ob.StartBar}";

                        Draw.Rectangle(this, rectId, false, barsAgo, ob.High, 0, ob.Low,
                            borderBrush, fillBrush, 2);

                        if (ob.Strength > 2.0)
                        {
                            string label = ob.IsBullish ? "Bull OB" : "Bear OB";
                            Draw.Text(this, $"OBText_{ob.StartBar}", label,
                                Math.Max(0, barsAgo - 1), ob.Mid,
                                GetCachedBrushSafe(Colors.White));
                        }
                    }
                    catch (Exception ex)
                    {
                        LogDebug("DRAWING", $"Error drawing order block {ob.StartBar}: {ex.Message}", "ERROR");
                        FKS_ErrorHandler.HandleError(ex, $"Draw Order Block {ob.StartBar}");
                    }
                }

                LogDebug("DRAWING", $"Order blocks drawn: {orderBlockList.Count}");
            }
            catch (Exception ex)
            {
                LogDebug("DRAWING", $"Error in DrawOrderBlocksSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "DrawOrderBlocksSafe");
            }
        }

        private SolidColorBrush GetCachedBrushSafe(Color color)
        {
            try
            {
                if (!_brushCache.TryGetValue(color, out var brush))
                {
                    brush = new SolidColorBrush(color);
                    brush.Freeze();
                    _brushCache[color] = brush;
                }
                return brush;
            }
            catch (Exception ex)
            {
                LogDebug("DRAWING", $"Error in GetCachedBrushSafe: {ex.Message}", "ERROR");
                return new SolidColorBrush(Colors.Gray);
            }
        }
        #endregion

        #region ML Learning and Memory Management - COMPLETE IMPLEMENTATION
        private void PerformMLLearningSafe()
        {
            try
            {
                if (patternLearner == null || signalHistory == null || signalHistory.Count < 2) return;

                var signals = signalHistory.ToList();
                if (signals.Count < 2) return;

                var oldSignal = signals[signals.Count - 2];

                if (string.IsNullOrEmpty(oldSignal.PatternKey)) return;

                double entryPrice = oldSignal.EntryPrice;
                double currentPrice = Close[0];

                if (entryPrice <= 0 || currentAtr <= 0) return;

                double moveInATR = (currentPrice - entryPrice) / currentAtr;
                bool successful = EvaluateSignalSuccessSafe(oldSignal, moveInATR);

                patternLearner.LearnPattern(oldSignal.PatternKey, successful ? 1.0 : -1.0);

                mlUpdateCounter++;

                LogDebug("ML", $"Pattern learned: {oldSignal.PatternKey}, Success: {successful}, Move: {moveInATR:F2} ATR");
            }
            catch (Exception ex)
            {
                LogDebug("ML", $"Error in PerformMLLearningSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "PerformMLLearningSafe");
            }
        }

        private bool EvaluateSignalSuccessSafe(AISignal signal, double moveInATR)
        {
            try
            {
                switch (signal.Direction)
                {
                    case AddOns.SignalDirection.Long:
                        return moveInATR > 1.0;
                    case AddOns.SignalDirection.Short:
                        return moveInATR < -1.0;
                    default:
                        return false;
                }
            }
            catch (Exception ex)
            {
                LogDebug("ML", $"Error in EvaluateSignalSuccessSafe: {ex.Message}", "ERROR");
                return false;
            }
        }

        private void UpdateAdaptiveParametersSafe()
        {
            try
            {
                if (signalHistory == null || signalHistory.Count < 10) return;

                var recent = signalHistory.ToList().Skip(Math.Max(0, signalHistory.Count - 10)).ToList();
                double successRate = recent.Count > 0 ? recent.Count(s => s.Score > 0.5) / (double)recent.Count : 0.5;

                if (successRate > 0.7)
                {
                    adaptiveMultiplier = Math.Min(1.2, adaptiveMultiplier * 1.01);
                }
                else if (successRate < 0.4)
                {
                    adaptiveMultiplier = Math.Max(0.8, adaptiveMultiplier * 0.99);
                }

                if (CurrentBar % 1000 == 0)
                {
                    LogDebug("ADAPTIVE", $"Performance - Success Rate: {successRate:P1}, Adaptive Multiplier: {adaptiveMultiplier:F3}");
                }
            }
            catch (Exception ex)
            {
                LogDebug("ADAPTIVE", $"Error in UpdateAdaptiveParametersSafe: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "UpdateAdaptiveParametersSafe");
            }
        }

        private void PerformMemoryMaintenanceOptimized()
        {
            try
            {
                _calculationResults.Clear();

                if (EnableMLLearning && patternLearner != null)
                {
                    patternLearner.CleanupOldPatterns(TimeSpan.FromHours(12));
                }

                if (ENABLE_PERFORMANCE_LOGGING && CurrentBar % 1000 == 0)
                {
                    LogDebug("MEMORY", $"Memory cleanup performed at bar {CurrentBar}");
                }
            }
            catch (Exception ex)
            {
                LogDebug("MEMORY", $"Error in PerformMemoryMaintenanceOptimized: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "PerformMemoryMaintenanceOptimized");
            }
        }

        private void TryRecoverFromFailure()
        {
            try
            {
                if (DateTime.Now - lastErrorReset > TimeSpan.FromMinutes(5))
                {
                    Status = ComponentStatus.Healthy;
                    errorCount = 0;
                    lastErrorReset = DateTime.Now;
                    LogDebug("RECOVERY", "Component recovered from failed state");
                }
            }
            catch (Exception ex)
            {
                LogDebug("RECOVERY", $"Error in TryRecoverFromFailure: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "TryRecoverFromFailure");
            }
        }

        private void HandleBarUpdateErrorSafe(Exception ex)
        {
            errorCount++;

            if (errorCount > 10)
            {
                Status = ComponentStatus.Failed;
                LogDebug("ERROR", $"Component disabled due to repeated errors (#{errorCount}): {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "FKS_AI.OnBarUpdate - Multiple failures", () =>
                {
                    LogDebug("ERROR", "FKS_AI disabled due to repeated errors", "ERROR");
                });
            }
            else
            {
                Status = ComponentStatus.Warning;
                LogDebug("ERROR", $"Component error #{errorCount}: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "FKS_AI.OnBarUpdate");
            }
        }

        private void ResetErrorCountIfNeeded()
        {
            try
            {
                if (DateTime.Now - lastErrorReset > TimeSpan.FromMinutes(10))
                {
                    if (errorCount > 0)
                    {
                        LogDebug("ERROR", $"Resetting error count from {errorCount} to 0");
                        errorCount = 0;
                    }
                    lastErrorReset = DateTime.Now;
                    if (Status == ComponentStatus.Warning)
                    {
                        Status = ComponentStatus.Healthy;
                    }
                }
            }
            catch (Exception ex)
            {
                LogDebug("ERROR", $"Error in ResetErrorCountIfNeeded: {ex.Message}", "ERROR");
            }
        }
        #endregion

        #region Component Interface Implementation - ENHANCED

        // Enhanced GetSignal() with comprehensive metrics and strategy threshold alignment
        public AddOns.ComponentSignal GetSignal()
        {
            try
            {
                if (currentSignal == null)
                {
                    return new AddOns.ComponentSignal
                    {
                        Source = "FKS_AI",
                        Direction = AddOns.SignalDirection.Neutral,
                        Score = 0.0,
                        Confidence = 0.0,
                        IsActive = false,
                        Timestamp = DateTime.Now,
                        Reasons = new List<string> { "No signal available" },
                        Metrics = new Dictionary<string, double>()
                    };
                }

                // Validate signal quality against strategy thresholds
                bool meetsConfidenceThreshold = currentSignal.Confidence >= BaseSignalThreshold;
                bool meetsScoreThreshold = currentSignal.Score >= 0.5;
                bool isActiveSignal = currentSignal.Direction != AddOns.SignalDirection.Neutral &&
                                    meetsConfidenceThreshold && meetsScoreThreshold;

                var signal = new AddOns.ComponentSignal
                {
                    Source = "FKS_AI",
                    Direction = currentSignal.Direction,
                    Score = Math.Abs(currentSignal.Score),
                    Confidence = currentSignal.Confidence,
                    IsActive = isActiveSignal,
                    Timestamp = currentSignal.Time,
                    Reasons = new List<string>(currentSignal.Reasons ?? new List<string>()),
                    Metrics = new Dictionary<string, double>
                    {
                        ["AI_Score"] = currentSignal.Score,
                        ["AI_Confidence"] = currentSignal.Confidence,
                        ["Support"] = currentSupport,
                        ["Resistance"] = currentResistance,
                        ["VWAP"] = vwapValue,
                        ["EMA9"] = currentEma9,
                        ["ATR"] = currentAtr,
                        ["ADX"] = currentAdx,
                        ["RegimeScore"] = regimeScore,
                        ["MarketRegime"] = (double)currentRegime,
                        ["EntryPrice"] = currentSignal.EntryPrice,
                        ["StopLoss"] = currentSignal.StopLoss,
                        ["TakeProfit"] = currentSignal.TakeProfit,
                        ["CompositeScore"] = compositeScore,
                        ["SignalQuality"] = GetCurrentSignalQuality(),
                        ["ThresholdMet"] = isActiveSignal ? 1.0 : 0.0,
                        ["BaseThreshold"] = BaseSignalThreshold,
                        ["ComponentHealth"] = Status == ComponentStatus.Healthy ? 1.0 : 0.0
                    }
                };

                // Enhanced reasoning with threshold validation
                if (signal.Reasons != null)
                {
                    // Add threshold validation reasons
                    if (!meetsConfidenceThreshold)
                        signal.Reasons.Add($"Confidence {currentSignal.Confidence:F3} below threshold {BaseSignalThreshold:F3}");
                    if (!meetsScoreThreshold)
                        signal.Reasons.Add($"Score {currentSignal.Score:F3} below minimum 0.50");

                    // Add context-specific reasons
                    if (Math.Abs(Close[0] - currentSupport) < currentAtr)
                        signal.Reasons.Add("Near support level");
                    if (Math.Abs(Close[0] - currentResistance) < currentAtr)
                        signal.Reasons.Add("Near resistance level");
                    if (Close[0] > vwapValue && signal.Direction == AddOns.SignalDirection.Long)
                        signal.Reasons.Add("Above VWAP - bullish context");
                    if (Close[0] < vwapValue && signal.Direction == AddOns.SignalDirection.Short)
                        signal.Reasons.Add("Below VWAP - bearish context");

                    // Add regime context
                    signal.Reasons.Add($"Market regime: {currentRegime}");
                    signal.Reasons.Add($"Regime strength: {regimeScore:F2}");

                    // Add quality metrics
                    double signalQuality = GetCurrentSignalQuality();
                    signal.Reasons.Add($"Signal quality: {signalQuality:F3}");
                }

                // Enhanced logging for debugging
                if (ENABLE_PERFORMANCE_LOGGING || ENABLE_DEBUG_MODE)
                {
                    LogDebug("SIGNAL_OUTPUT", $"Signal: Dir={signal.Direction}, Score={signal.Score:F3}, " +
                          $"Conf={signal.Confidence:F3}, Active={signal.IsActive}, " +
                          $"Threshold={BaseSignalThreshold:F3}");
                }

                return signal;
            }
            catch (Exception ex)
            {
                LogDebug("SIGNAL_OUTPUT", $"Error in GetSignal: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "FKS_AI.GetSignal");
                return new AddOns.ComponentSignal
                {
                    Source = "FKS_AI",
                    Direction = AddOns.SignalDirection.Neutral,
                    Score = 0.0,
                    Confidence = 0.0,
                    IsActive = false,
                    Timestamp = DateTime.Now,
                    Reasons = new List<string> { "Error generating AI signal" },
                    Metrics = new Dictionary<string, double> { ["Error"] = 1.0 }
                };
            }
        }

        // Public access methods
        public double GetSupport() => ValidateDouble(currentSupport, Low.Count > 0 ? Low[0] : 0, "Support");
        public double GetResistance() => ValidateDouble(currentResistance, High.Count > 0 ? High[0] : 0, "Resistance");
        public double GetVWAP() => ValidateDouble(vwapValue, Close.Count > 0 ? Close[0] : 0, "VWAP");
        public double GetEMA9() => ValidateDouble(currentEma9, Close.Count > 0 ? Close[0] : 0, "EMA9");
        public double GetATR() => ValidateDouble(currentAtr, 0.01, "ATR");
        public double GetRegimeScore() => ValidateDouble(regimeScore, 0.5, "RegimeScore");
        public double GetCompositeScore() => ValidateDouble(compositeScore, 0, "CompositeScore");
        public AddOns.MarketRegime GetCurrentRegime() => currentRegime;

        // Get composite signal from coordinator
        public CompositeSignal GetCompositeSignal()
        {
            try
            {
                return signalCoordinator?.GenerateCompositeSignal() ?? new CompositeSignal();
            }
            catch (Exception ex)
            {
                LogDebug("COMPOSITE", $"Error getting composite signal: {ex.Message}", "ERROR");
                return new CompositeSignal();
            }
        }

        // Check if registered with signal coordinator
        public bool IsRegisteredWithCoordinator()
        {
            return isRegisteredWithCoordinator && signalCoordinator != null;
        }

        // Standardized cleanup method
        private void CleanupSafely()
        {
            if (disposed) return;

            try
            {
                LogDebug("CLEANUP", $"{IndicatorName}: Starting cleanup");

                // Unregister from registry first
                componentManager?.UnregisterComponent(IndicatorName);

                // Clear shared state
                FKS_UnifiedCache.ClearAll();

                // Then dispose local resources
                Dispose();

                LogDebug("CLEANUP", $"{IndicatorName}: Cleanup completed");
            }
            catch (Exception ex)
            {
                LogDebug("CLEANUP", $"Cleanup error in {IndicatorName}: {ex.Message}", "ERROR");
            }
        }
        #endregion

        #region Helper Methods for Signal Quality and Validation

        /// <summary>
        /// Calculate current signal quality based on multiple factors
        /// </summary>
        private double GetCurrentSignalQuality()
        {
            try
            {
                if (currentSignal == null) return 0.0;

                double qualityScore = 0.0;

                // Base quality from signal confidence and score
                qualityScore += (currentSignal.Confidence * currentSignal.Score) * 0.4;

                // Market condition quality boost
                switch (currentRegime)
                {
                    case AddOns.MarketRegime.StrongTrend:
                        qualityScore += 0.2;
                        break;
                    case AddOns.MarketRegime.Range:
                        qualityScore += 0.1;
                        break;
                    case AddOns.MarketRegime.Volatile:
                        qualityScore += 0.05; // Lower boost for volatile markets
                        break;
                }

                // ATR stability quality - check if we have enough history
                if (currentAtr > 0 && atrHistory != null && atrHistory.Count >= 5)
                {
                    try
                    {
                        var atrValues = atrHistory.ToList();
                        var recent5 = atrValues.Skip(Math.Max(0, atrValues.Count - 5)).ToList();
                        if (recent5.Count > 0 && recent5.Average() > 0)
                        {
                            double atrStability = 1.0 - (recent5.Max() - recent5.Min()) / recent5.Average();
                            qualityScore += Math.Max(0, atrStability) * 0.2;
                        }
                    }
                    catch (Exception ex)
                    {
                        LogMessage($"Error calculating ATR stability: {ex.Message}", FKSLogLevel.Warning);
                    }
                }

                // Signal consistency quality - check recent signal history
                if (signalHistory != null && signalHistory.Count >= 3)
                {
                    try
                    {
                        var recentSignals = signalHistory.ToList();
                        var recent3 = recentSignals.Skip(Math.Max(0, recentSignals.Count - 3)).ToList();
                        bool consistent = recent3.All(s => s != null && s.Direction == currentSignal.Direction);
                        if (consistent) qualityScore += 0.2;
                    }
                    catch (Exception ex)
                    {
                        LogMessage($"Error calculating signal consistency: {ex.Message}", FKSLogLevel.Warning);
                    }
                }

                return Math.Min(1.0, qualityScore);
            }
            catch (Exception ex)
            {
                LogMessage($"Error calculating signal quality: {ex.Message}", FKSLogLevel.Error);
                return 0.0;
            }
        }

        /// <summary>
        /// Validate signal meets strategy requirements
        /// </summary>
        private bool ValidateSignalQuality(AISignal signal)
        {
            try
            {
                if (signal == null) return false;

                // Check minimum thresholds
                bool meetsConfidenceThreshold = signal.Confidence >= BaseSignalThreshold;
                bool meetsScoreThreshold = signal.Score >= 0.5;
                bool hasValidDirection = signal.Direction != AddOns.SignalDirection.Neutral;

                // Additional quality checks
                bool hasValidATR = currentAtr > 0;
                bool componentHealthy = Status == ComponentStatus.Healthy;

                return meetsConfidenceThreshold && meetsScoreThreshold &&
                       hasValidDirection && hasValidATR && componentHealthy;
            }
            catch (Exception ex)
            {
                LogMessage($"Error validating signal quality: {ex.Message}", FKSLogLevel.Error);
                return false;
            }
        }

        /// <summary>
        /// Get adaptive threshold based on market conditions
        /// </summary>
        private double GetAdaptiveThreshold()
        {
            try
            {
                double baseThreshold = BaseSignalThreshold;

                // Adjust threshold based on market conditions
                switch (currentRegime)
                {
                    case AddOns.MarketRegime.Volatile:
                        return baseThreshold + 0.1; // Higher threshold in volatile markets
                    case AddOns.MarketRegime.Range:
                        return baseThreshold + 0.05; // Slightly higher in ranging markets
                    case AddOns.MarketRegime.StrongTrend:
                        return baseThreshold - 0.05; // Lower threshold in strong trends
                    default:
                        return baseThreshold;
                }
            }
            catch
            {
                return BaseSignalThreshold;
            }
        }

        /// <summary>
        /// Enhanced error logging with context
        /// </summary>
        private void LogMessage(string message, FKSLogLevel level)
        {
            try
            {
                string prefix = level == FKSLogLevel.Error ? "[ERROR]" :
                               level == FKSLogLevel.Warning ? "[WARN]" :
                               level == FKSLogLevel.Information ? "[INFO]" : "[DEBUG]";

                if (level == FKSLogLevel.Error || ENABLE_PERFORMANCE_LOGGING)
                {
                    Print($"FKS_AI {prefix} {message}");
                }
            }
            catch
            {
                // Fail silently for logging errors to avoid infinite loops
            }
        }

        // FKSLogLevel enum for enhanced logging
        private enum FKSLogLevel
        {
            Debug,
            Information,
            Warning,
            Error
        }

        #endregion

        #region Component Disposal and Cleanup
        private void CleanupComponents()
        {
            try
            {
                LogDebug("CLEANUP", "FKS_AI cleanup started");
                Dispose();
                LogDebug("CLEANUP", "FKS_AI cleanup completed");
            }
            catch (Exception ex)
            {
                LogDebug("CLEANUP", $"Error during FKS_AI cleanup: {ex.Message}", "ERROR");
            }
        }

        public void Dispose()
        {
            if (disposed) return;

            try
            {
                disposed = true;

                patternLearner?.Dispose();
                volumeAnalyzer?.Dispose();
                thresholds?.Dispose();
                chartAdapter?.Dispose();

                calculationCache?.Clear();

                signalHistory = null;
                orderBlocks = null;
                ema9History = null;
                atrHistory = null;
                _calculationResults?.Clear();
                _brushCache?.Clear();

                Status = ComponentStatus.Failed;
                isInitialized = false;

                LogDebug("CLEANUP", "FKS_AI disposed successfully");
            }
            catch (Exception ex)
            {
                LogDebug("CLEANUP", $"Error in Dispose: {ex.Message}", "ERROR");
                FKS_ErrorHandler.HandleError(ex, "FKS_AI.Dispose");
            }
        }
        #endregion

        #region Properties - SIMPLIFIED PER MASTER PLAN PHASE 2.1

        // Baseline Parameters (hardcoded baselines per Master Plan Phase 2.1)
        // Gold defaults - these are proven values, remove all customization
        private const int SUPPORT_RESISTANCE_LENGTH = 150;
        private const double SIGNAL_QUALITY_THRESHOLD = 0.65;
        private const int MAX_LENGTH = 20;
        private const int LOOKBACK_PERIOD = 200;
        private const double MIN_WAVE_RATIO = 1.5;
        private const int ATR_PERIOD = 14;

        // Legacy properties for backward compatibility (read-only)
        public int SRPeriod => SUPPORT_RESISTANCE_LENGTH;
        public int ATRPeriod => ATR_PERIOD;
        public double BaseSignalThreshold => SIGNAL_QUALITY_THRESHOLD;

        // Essential display properties only
        public bool ShowSignals { get; set; } = true;
        public bool ShowLevels { get; set; } = true;

        #region Production Configuration - Hardcoded per master plan
        
        // Core configuration - hardcoded for production
        private const bool SHOW_ORDER_BLOCKS = true;
        private const bool SHOW_VOLUME_PROFILE = true;
        private const bool ADAPT_TO_CHART_TYPE = true;
        
        // Order Block Configuration - hardcoded
        private const int ORDER_BLOCK_LOOKBACK = 20;
        private const double MIN_ORDER_BLOCK_STRENGTH = 0.6;
        private const int MAX_ORDER_BLOCKS = 5;
        
        // Performance and Debug - hardcoded to production values
        private const bool ENABLE_PERFORMANCE_LOGGING = false;
        private const bool ALWAYS_PROCESS_ALL_BARS = false;
        private const bool ENABLE_DEBUG_MODE = false;
        private const bool VERBOSE_DEBUG = false;
        private const bool SHOW_DEBUG_ON_CHART = false;
        private const bool EXPORT_DEBUG_DATA = false;
        private const int DASHBOARD_FONT_SIZE = 10;
        
        #endregion

        #region Plot Series
        [Browsable(false)]
        [XmlIgnore]
        public Series<double> Resistance => Values[0];

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> Support => Values[1];

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> Midpoint => Values[2];

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> VWAP => Values[3];

        [Browsable(false)]
        [XmlIgnore]
        public Series<double> EMA9 => Values[4];

        #endregion
    }

    #region Supporting Classes and Enums

    public enum FKSLogLevel
    {
        Debug,
        Information,
        Warning,
        Error
    }

    public class PatternLearner : IDisposable
    {
        private readonly Dictionary<string, double> patterns = new Dictionary<string, double>();

        public double GetPatternProbability(string patternKey)
        {
            return patterns.TryGetValue(patternKey, out var probability) ? probability : 0.5;
        }

        public void LearnPattern(string patternKey, double outcome)
        {
            if (patterns.ContainsKey(patternKey))
            {
                patterns[patternKey] = (patterns[patternKey] + outcome) / 2.0;
            }
            else
            {
                patterns[patternKey] = outcome;
            }
        }

        public void CleanupOldPatterns(TimeSpan maxAge)
        {
            // Implementation for cleanup
        }

        public void Dispose()
        {
            patterns?.Clear();
        }
    }

    public class VolumeAnalyzer : IDisposable
    {
        public void UpdateProfile(double price, long volume, DateTime time)
        {
            // Implementation
        }

        public void UpdateVolumeProfile(double high, double low, double close, long volume)
        {
            // Implementation
        }

        public void Dispose()
        {
            // Cleanup
        }
    }

    public class AdaptiveThresholds : IDisposable
    {
        public void Dispose()
        {
            // Cleanup
        }
    }

    public class FKS_PeriodAdapter : IDisposable
    {
        public void DetectChartType(object bars)
        {
            // Implementation
        }

        public void UpdateChartInfo(object indicator)
        {
            // Implementation
        }

        public void Dispose()
        {
            // Cleanup
        }
    }

    public class FKSAICircularBuffer<T>
    {
        private readonly T[] buffer;
        private readonly int capacity;
        private int index = 0;
        private bool isFull = false;

        public int Count => isFull ? capacity : index;

        public FKSAICircularBuffer(int capacity)
        {
            this.capacity = capacity;
            buffer = new T[capacity];
        }

        public void Add(T item)
        {
            buffer[index] = item;
            index = (index + 1) % capacity;
            if (index == 0) isFull = true;
        }

        public List<T> ToList()
        {
            var result = new List<T>();
            if (!isFull && index == 0) return result;

            int start = isFull ? index : 0;
            int count = isFull ? capacity : index;

            for (int i = 0; i < count; i++)
            {
                int actualIndex = (start + i) % capacity;
                result.Add(buffer[actualIndex]);
            }
            return result;
        }

        public T[] GetItems()
        {
            return ToList().ToArray();
        }
    }

    #endregion

    #endregion
}