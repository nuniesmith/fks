// FKS_AO.cs - FKS Awesome Oscillator Indicator
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
using NinjaTrader.NinjaScript.AddOns.FKS;
using System.Diagnostics;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.FKS
{
    /// <summary>
    /// FKS Awesome Oscillator - Enhanced version with signal line and momentum confirmation
    /// </summary>
    public partial class FKS_AO : Indicator, FKS_Core.IFKSComponent
    {
        #region Variables
        // Component Interface
        public string ComponentId => "FKS_AO";
        public string Version => "1.0.0";
        
        // Fixed parameters (matching PineScript)
        private const int FAST_PERIOD = 5;
        private const int SLOW_PERIOD = 34;
        private const int SIGNAL_PERIOD = 7;
        
        // Infrastructure Integration
        private DateTime lastHeartbeat = DateTime.MinValue;
        private DateTime lastActivity = DateTime.MinValue;
        private int calculationCount = 0;
        private int errorCount = 0;
        private bool isRegistered = false;
        
        // Series for calculations
        private Series<double> aoValue;
        private Series<double> signalLine;
        
        // State tracking
        private int currentCrossDirection = 0; // 1 = bullish, -1 = bearish, 0 = none
        private double momentumStrength = 0;
        private bool isAccelerating = false;
        private bool isDiverging = false;
        
        // Visual properties
        private Brush positiveColor = Brushes.Green;
        private Brush negativeColor = Brushes.Red;
        private Brush signalColor = Brushes.Blue;
        private Brush divergenceColor = Brushes.Gold;
        #endregion
        
        #region Debug Infrastructure
        
        private readonly List<string> debugLog = new List<string>();
        private DateTime lastDebugUpdate = DateTime.MinValue;
        private readonly TimeSpan debugUpdateInterval = TimeSpan.FromSeconds(5);
        private DateTime lastAOLogTime = DateTime.MinValue;
        private DateTime lastSIGNALLogTime = DateTime.MinValue;
        private DateTime lastMOMENTUMLogTime = DateTime.MinValue;
        private string lastLogMessage = "";
        private int logSuppressCount = 0;
        
        private void LogDebug(string category, string message, string level = "INFO")
        {
            if (!EnableDebugMode) return;
            
            try
            {
                // Aggressive rate limiting for frequent categories
                if (category == "AO" && lastAOLogTime.AddSeconds(30) > DateTime.Now)
                {
                    logSuppressCount++;
                    return;
                }
                
                if (category == "SIGNAL" && lastSIGNALLogTime.AddSeconds(15) > DateTime.Now)
                {
                    logSuppressCount++;
                    return;
                }
                
                if (category == "MOMENTUM" && lastMOMENTUMLogTime.AddSeconds(15) > DateTime.Now)
                {
                    logSuppressCount++;
                    return;
                }
                
                // Suppress duplicate messages
                if (lastLogMessage == message && DateTime.Now - lastDebugUpdate < TimeSpan.FromSeconds(5))
                {
                    logSuppressCount++;
                    return;
                }
                
                string logEntry = $"{DateTime.Now:HH:mm:ss.fff} [{level}] {category}: {message} (Bar: {CurrentBar})";
                
                // Add suppression info if messages were suppressed
                if (logSuppressCount > 0)
                {
                    logEntry += $" (Suppressed {logSuppressCount} similar messages)";
                    logSuppressCount = 0;
                }
                
                debugLog.Add(logEntry);
                
                if (debugLog.Count > 100)
                    debugLog.RemoveAt(0);
                
                // Only print important messages
                if (VerboseDebug || level == "ERROR" || level == "WARN" || category == "SIGNAL")
                {
                    Print(logEntry);
                }
                
                // Update timestamps
                if (category == "AO") lastAOLogTime = DateTime.Now;
                if (category == "SIGNAL") lastSIGNALLogTime = DateTime.Now;
                if (category == "MOMENTUM") lastMOMENTUMLogTime = DateTime.Now;
                lastLogMessage = message;
                lastDebugUpdate = DateTime.Now;
            }
            catch (Exception ex)
            {
                Print($"Debug logging error: {ex.Message}");
            }
        }
        
        private void PerformDebugCheck()
        {
            if (!EnableDebugMode) return;
            
            try
            {
                LogDebug("AO", $"AO Value: {aoValue[0]:F4}, Signal: {signalLine[0]:F4}", "INFO");
                LogDebug("AO", $"Cross Direction: {currentCrossDirection}, Momentum: {momentumStrength:F2}", "INFO");
                LogDebug("AO", $"Accelerating: {isAccelerating}, Diverging: {isDiverging}", "INFO");
                LogDebug("AO", $"Component Status: Registered={isRegistered}, Errors={errorCount}", "INFO");
            }
            catch (Exception ex)
            {
                LogDebug("AO", $"Debug check error: {ex.Message}", "ERROR");
            }
        }
        
        #endregion
        
        #region OnStateChange
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"FKS Awesome Oscillator with signal line and momentum confirmation";
                Name = "FKS_AO";
                Calculate = Calculate.OnBarClose;
                IsOverlay = false;
                DisplayInDataBox = true;
                DrawOnPricePanel = false;
                DrawHorizontalGridLines = true;
                DrawVerticalGridLines = true;
                PaintPriceMarkers = false;
                ScaleJustification = NinjaTrader.Gui.Chart.ScaleJustification.Right;
                IsSuspendedWhileInactive = false;
                
                // Visual defaults
                ShowHistogram = true;
                ShowSignalLine = true;
                ShowZeroLine = true;
                ShowCrossovers = true;
                ShowDivergence = false;
                UseGradientColors = true;
                
                // Debug defaults
                EnableDebugMode = false;
                VerboseDebug = false;
                
                // Add plots
                AddPlot(new Stroke(Brushes.Red, 2), PlotStyle.Bar, "AO");
                AddPlot(new Stroke(Brushes.Blue, 2), PlotStyle.Line, "Signal");
                AddLine(Brushes.DarkGray, 0, "Zero");
            }
            else if (State == State.Configure)
            {
                // Nothing specific needed
            }
            else if (State == State.DataLoaded)
            {
                // Initialize series
                aoValue = new Series<double>(this);
                signalLine = new Series<double>(this);
                
                // Enhanced Registration with Infrastructure
                RegisterWithInfrastructure();
            }
            else if (State == State.Terminated)
            {
                // Cleanup on termination
                UnregisterFromInfrastructure();
            }
        }
        #endregion
        
        #region OnBarUpdate
        protected override void OnBarUpdate()
        {
            if (CurrentBar < SLOW_PERIOD + SIGNAL_PERIOD) return;
            
            var stopwatch = Stopwatch.StartNew();
            
            try
            {
                // Send heartbeat every 10 bars
                if (CurrentBar % 10 == 0)
                {
                    SendHeartbeat();
                }
                
                // Calculate AO value
                double ao = SMA(Typical, FAST_PERIOD)[0] - SMA(Typical, SLOW_PERIOD)[0];
                aoValue[0] = ao;
                Values[0][0] = ao;
                
                // Calculate signal line
                double signal = SMA(aoValue, SIGNAL_PERIOD)[0];
                signalLine[0] = signal;
                Values[1][0] = signal;
                
                // Detect crossovers
                DetectCrossovers();
                
                // Calculate momentum strength
                CalculateMomentumStrength();
                
                // Check for divergence if enabled
                if (ShowDivergence)
                {
                    CheckDivergence();
                }
                
                // Update histogram colors
                UpdateColors();
                
                // Update FKS Core with current state
                UpdateCoreState();
                
                // Debug check
                if (EnableDebugMode && DateTime.Now - lastDebugUpdate >= debugUpdateInterval)
                {
                    PerformDebugCheck();
                    lastDebugUpdate = DateTime.Now;
                }
                
                // Record successful activity
                calculationCount++;
                lastActivity = DateTime.Now;
                
                // Record performance metrics
                stopwatch.Stop();
                FKS_Infrastructure.RecordPerformanceMetric(ComponentId, "OnBarUpdate", stopwatch.Elapsed);
            }
            catch (Exception ex)
            {
                errorCount++;
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "OnBarUpdate");
                Log($"FKS_AO Error in OnBarUpdate: {ex.Message}", LogLevel.Error);
                LogDebug("AO", $"Error in OnBarUpdate: {ex.Message}", "ERROR");
            }
        }
        #endregion
        
        #region Calculations
        private void DetectCrossovers()
        {
            try
            {
                int previousCrossDirection = currentCrossDirection;
                currentCrossDirection = 0;
                
                // Zero line crossovers with confirmation
                if (UseAOZeroCross)
                {
                    if (aoValue[0] > 0 && aoValue[1] <= 0)
                    {
                        // Bullish zero cross - additional confirmation
                        if (momentumStrength > 0.3 || isAccelerating)
                        {
                            currentCrossDirection = 1;
                            FKS_Infrastructure.RecordOperation(ComponentId, "BullishZeroCross");
                            LogDebug("SIGNAL", $"Bullish Zero Cross detected (AO: {aoValue[0]:F4}, Momentum: {momentumStrength:F2})", "INFO");
                        }
                    }
                    else if (aoValue[0] < 0 && aoValue[1] >= 0)
                    {
                        // Bearish zero cross - additional confirmation
                        if (momentumStrength > 0.3 || isAccelerating)
                        {
                            currentCrossDirection = -1;
                            FKS_Infrastructure.RecordOperation(ComponentId, "BearishZeroCross");
                            LogDebug("SIGNAL", $"Bearish Zero Cross detected (AO: {aoValue[0]:F4}, Momentum: {momentumStrength:F2})", "INFO");
                        }
                    }
                }
                
                // Signal line crossovers with confirmation
                if (UseAOSignalCross && currentCrossDirection == 0)
                {
                    if (aoValue[0] > signalLine[0] && aoValue[1] <= signalLine[1])
                    {
                        // Bullish signal cross - check for momentum confirmation
                        if (momentumStrength > 0.2)
                        {
                            currentCrossDirection = 1;
                            FKS_Infrastructure.RecordOperation(ComponentId, "BullishSignalCross");
                            LogDebug("SIGNAL", $"Bullish Signal Cross detected (AO: {aoValue[0]:F4}, Signal: {signalLine[0]:F4})", "INFO");
                        }
                    }
                    else if (aoValue[0] < signalLine[0] && aoValue[1] >= signalLine[1])
                    {
                        // Bearish signal cross - check for momentum confirmation
                        if (momentumStrength > 0.2)
                        {
                            currentCrossDirection = -1;
                            FKS_Infrastructure.RecordOperation(ComponentId, "BearishSignalCross");
                            LogDebug("SIGNAL", $"Bearish Signal Cross detected (AO: {aoValue[0]:F4}, Signal: {signalLine[0]:F4})", "INFO");
                        }
                    }
                }
                
                // Log significant crossover changes
                if (currentCrossDirection != previousCrossDirection && currentCrossDirection != 0)
                {
                    Log($"AO Crossover detected: {(currentCrossDirection > 0 ? "Bullish" : "Bearish")} " +
                        $"with momentum strength: {momentumStrength:F2}", LogLevel.Information);
                }
            }
            catch (Exception ex)
            {
                FKS_Infrastructure.RecordError(ComponentId, "CrossoverDetection", ex.Message);
                currentCrossDirection = 0; // Safe fallback
            }
        }
        
        private void CalculateMomentumStrength()
        {
            try
            {
                // Enhanced momentum calculation using shared utilities
                double aoChange = aoValue[0] - aoValue[1];
                double aoAcceleration = CurrentBar > 2 ? (aoChange - (aoValue[1] - aoValue[2])) : 0;
                
                // Use enhanced ATR calculation for normalization
                double atr = ATR(14)[0];
                double avgRange = SMA(ATR(14), 20)[0];
                
                if (avgRange > 0)
                {
                    // Normalize momentum strength using ATR
                    momentumStrength = Math.Abs(aoValue[0]) / avgRange;
                    momentumStrength = Math.Min(1.0, momentumStrength / 2); // Scale to 0-1
                    
                    // Apply volatility adjustment using shared calculations
                    double volAdjustment = FKS_Calculations.CalculateATRMultiplier("ES", 1.0); // Use ES as default
                    momentumStrength *= volAdjustment;
                }
                else
                {
                    momentumStrength = 0.5;
                }
                
                // Enhanced acceleration detection
                bool priceAccelerating = (Close[0] - Close[1]) * (Close[1] - Close[2]) > 0;
                isAccelerating = ((aoValue[0] > 0 && aoChange > 0 && aoAcceleration > 0) ||
                               (aoValue[0] < 0 && aoChange < 0 && aoAcceleration < 0)) && priceAccelerating;
                
                // Scale momentum strength based on acceleration
                if (isAccelerating)
                {
                    momentumStrength = Math.Min(1.0, momentumStrength * 1.3);
                }
                
                // Record performance metrics
                FKS_Infrastructure.RecordOperation(ComponentId, "MomentumCalculation");
            }
            catch (Exception ex)
            {
                FKS_Infrastructure.RecordError(ComponentId, "MomentumCalculation", ex.Message);
                momentumStrength = 0.5; // Default fallback
                isAccelerating = false;
            }
        }
        
        private void CheckDivergence()
        {
            try
            {
                if (CurrentBar < 50) return;
                
                isDiverging = false;
                
                // Enhanced divergence detection using shared calculations
                int lookback = 20;
                
                // Find recent swing highs/lows with more precision
                double recentPriceHigh = MAX(High, lookback)[0];
                double recentPriceLow = MIN(Low, lookback)[0];
                double recentAOHigh = MAX(aoValue, lookback)[0];
                double recentAOLow = MIN(aoValue, lookback)[0];
                
                // Use ATR for more accurate divergence detection
                double atr = ATR(14)[0];
                double priceThreshold = atr * 0.5; // More precise threshold
                
                // Bullish divergence: price makes lower low, AO makes higher low
                if (Low[0] <= recentPriceLow + priceThreshold && 
                    aoValue[0] > recentAOLow * 1.01 && 
                    aoValue[0] < 0 && 
                    momentumStrength > 0.3)
                {
                    isDiverging = true;
                    FKS_Infrastructure.RecordOperation(ComponentId, "BullishDivergence");
                    Log($"Bullish divergence detected at bar {CurrentBar}", LogLevel.Information);
                }
                
                // Bearish divergence: price makes higher high, AO makes lower high
                if (High[0] >= recentPriceHigh - priceThreshold && 
                    aoValue[0] < recentAOHigh * 0.99 && 
                    aoValue[0] > 0 && 
                    momentumStrength > 0.3)
                {
                    isDiverging = true;
                    FKS_Infrastructure.RecordOperation(ComponentId, "BearishDivergence");
                    Log($"Bearish divergence detected at bar {CurrentBar}", LogLevel.Information);
                }
            }
            catch (Exception ex)
            {
                FKS_Infrastructure.RecordError(ComponentId, "DivergenceDetection", ex.Message);
                isDiverging = false; // Safe fallback
            }
        }
        
        private void UpdateColors()
        {
            if (!UseGradientColors)
            {
                PlotBrushes[0][0] = aoValue[0] >= 0 ? positiveColor : negativeColor;
                return;
            }
            
            // Gradient coloring based on momentum strength
            if (aoValue[0] >= 0)
            {
                // Green gradient for positive values
                int greenIntensity = (int)(100 + momentumStrength * 155);
                PlotBrushes[0][0] = new SolidColorBrush(Color.FromRgb(0, (byte)greenIntensity, 0));
            }
            else
            {
                // Red gradient for negative values
                int redIntensity = (int)(100 + momentumStrength * 155);
                PlotBrushes[0][0] = new SolidColorBrush(Color.FromRgb((byte)redIntensity, 0, 0));
            }
            
            // Highlight accelerating momentum
            if (isAccelerating && momentumStrength > 0.7)
            {
                PlotBrushes[0][0] = aoValue[0] >= 0 ? Brushes.Lime : Brushes.OrangeRed;
            }
        }
        
        private void DrawCrossoverMarkers()
        {
            // Drawing temporarily disabled due to type conflicts
            // TODO: Resolve Draw class conflicts
            return;
        }
        
        private void UpdateMomentumState()
        {
            // This would update FKS Core with momentum state
            // For now, we'll just track internally
            // In production, this would integrate with FKS_Signals
        }
        #endregion
        
        #region Public Properties for External Access
        // Properties for strategy to access
        public new double Value => aoValue[0];
        public double PreviousValue => CurrentBar > 0 ? aoValue[1] : 0; // Add missing PreviousValue property
        public double Signal => signalLine[0];
        public int CrossDirection => currentCrossDirection;
        public double MomentumStrength => momentumStrength;
        public bool IsAccelerating => isAccelerating;
        public bool IsBullish => aoValue[0] > 0 || (UseAOSignalCross && aoValue[0] > signalLine[0]);
        public bool IsBearish => aoValue[0] < 0 || (UseAOSignalCross && aoValue[0] < signalLine[0]);
        
        // Check if we have confirmation
        public bool HasBullishConfirmation()
        {
            return IsBullish && (currentCrossDirection > 0 || isAccelerating);
        }
        
        public bool HasBearishConfirmation()
        {
            return IsBearish && (currentCrossDirection < 0 || isAccelerating);
        }
        #endregion
        
        #region Public Methods for FKS_Info Integration
        public FKS_Core.ComponentSignal GetSignal()
        {
            return new FKS_Core.ComponentSignal
            {
                SignalType = "AO_Signal",
                Quality = CalculateSignalQuality(),
                Timestamp = DateTime.Now,
                Data = new Dictionary<string, object>
                {
                    ["AOValue"] = Value,
                    ["SignalLine"] = Signal,
                    ["CrossDirection"] = CrossDirection,
                    ["MomentumStrength"] = MomentumStrength,
                    ["IsAccelerating"] = IsAccelerating,
                    ["IsBullish"] = IsBullish,
                    ["IsBearish"] = IsBearish,
                    ["HasBullishConfirmation"] = HasBullishConfirmation(),
                    ["HasBearishConfirmation"] = HasBearishConfirmation(),
                    ["IsDiverging"] = isDiverging,
                    ["MarketRegime"] = DetermineMarketRegime(),
                    ["CalculationCount"] = calculationCount,
                    ["ErrorCount"] = errorCount,
                    ["LastActivity"] = lastActivity,
                    ["ComponentHealth"] = errorCount == 0 ? "Healthy" : 
                                         errorCount < 5 ? "Warning" : "Critical"
                }
            };
        }
        
        /// <summary>
        /// Get AO data specifically for FKS_Signals integration
        /// </summary>
        public SignalInputs GetAOSignalInputs()
        {
            return CreateSignalInputs();
        }
        
        /// <summary>
        /// Get current AO momentum analysis
        /// </summary>
        public Dictionary<string, object> GetMomentumAnalysis()
        {
            return new Dictionary<string, object>
            {
                ["CurrentMomentum"] = momentumStrength,
                ["IsAccelerating"] = isAccelerating,
                ["TrendDirection"] = aoValue[0] > 0 ? "Bullish" : "Bearish",
                ["SignalStrength"] = Math.Abs(aoValue[0] - signalLine[0]),
                ["ZeroLineDistance"] = Math.Abs(aoValue[0]),
                ["RecentCrossover"] = currentCrossDirection,
                ["DivergenceDetected"] = isDiverging,
                ["QualityScore"] = CalculateSignalQuality()
            };
        }
        #endregion
        
        #region User Properties
        [NinjaScriptProperty]
        [Display(Name = "Use AO Zero Cross", Order = 1, GroupName = "Parameters")]
        public bool UseAOZeroCross { get; set; } = true;
        
        [NinjaScriptProperty]
        [Display(Name = "Use AO Signal Cross", Order = 2, GroupName = "Parameters")]
        public bool UseAOSignalCross { get; set; } = true;
        
        [NinjaScriptProperty]
        [Display(Name = "Show Histogram", Order = 10, GroupName = "Visual")]
        public bool ShowHistogram { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Signal Line", Order = 11, GroupName = "Visual")]
        public bool ShowSignalLine { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Zero Line", Order = 12, GroupName = "Visual")]
        public bool ShowZeroLine { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Crossovers", Order = 13, GroupName = "Visual")]
        public bool ShowCrossovers { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Divergence", Order = 14, GroupName = "Visual")]
        public bool ShowDivergence { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Use Gradient Colors", Order = 15, GroupName = "Visual")]
        public bool UseGradientColors { get; set; }
        
        [XmlIgnore]
        [Display(Name = "Positive Color", Order = 20, GroupName = "Colors")]
        public Brush PositiveColor
        {
            get { return positiveColor; }
            set { positiveColor = value; }
        }
        
        [XmlIgnore]
        [Display(Name = "Negative Color", Order = 21, GroupName = "Colors")]
        public Brush NegativeColor
        {
            get { return negativeColor; }
            set { negativeColor = value; }
        }
        
        [XmlIgnore]
        [Display(Name = "Signal Color", Order = 22, GroupName = "Colors")]
        public Brush SignalLineColor
        {
            get { return signalColor; }
            set { signalColor = value; }
        }
        
        [XmlIgnore]
        [Display(Name = "Divergence Color", Order = 23, GroupName = "Colors")]
        public Brush DivergenceMarkerColor
        {
            get { return divergenceColor; }
            set { divergenceColor = value; }
        }
        #endregion
        
        #region Debug Properties
        [Display(Name = "Enable Debug Mode", Order = 50, GroupName = "Debug")]
        public bool EnableDebugMode { get; set; }
        
        [Display(Name = "Verbose Debug", Order = 51, GroupName = "Debug")]
        public bool VerboseDebug { get; set; }
        #endregion
        
        #region IFKSComponent Implementation
        public void Initialize()
        {
            try
            {
                // Component-specific initialization
                calculationCount = 0;
                errorCount = 0;
                lastActivity = DateTime.Now;
                
                Log("FKS_AO initialized successfully", LogLevel.Information);
                FKS_Infrastructure.RecordOperation(ComponentId, "Initialize");
            }
            catch (Exception ex)
            {
                FKS_Infrastructure.RecordError(ComponentId, "Initialize", ex.Message);
                Log($"FKS_AO initialization failed: {ex.Message}", LogLevel.Error);
            }
        }
        
        public void Shutdown()
        {
            try
            {
                // Component cleanup
                UnregisterFromInfrastructure();
                
                Log($"FKS_AO shutdown completed. Total calculations: {calculationCount}, Errors: {errorCount}", 
                    LogLevel.Information);
                FKS_Infrastructure.RecordOperation(ComponentId, "Shutdown");
            }
            catch (Exception ex)
            {
                FKS_Infrastructure.RecordError(ComponentId, "Shutdown", ex.Message);
                Log($"FKS_AO shutdown error: {ex.Message}", LogLevel.Error);
            }
        }
        
        /// <summary>
        /// Get component performance metrics
        /// </summary>
        public Dictionary<string, object> GetPerformanceMetrics()
        {
            return new Dictionary<string, object>
            {
                ["TotalCalculations"] = calculationCount,
                ["ErrorCount"] = errorCount,
                ["ErrorRate"] = calculationCount > 0 ? (double)errorCount / calculationCount : 0,
                ["LastActivity"] = lastActivity,
                ["AverageQuality"] = CalculateSignalQuality(),
                ["IsHealthy"] = errorCount < 5,
                ["UptimeSeconds"] = (DateTime.Now - lastActivity).TotalSeconds
            };
        }
        #endregion
        
        #region Infrastructure Integration
        private void RegisterWithInfrastructure()
        {
            try
            {
                // Register with FKS Core
                FKS_Core.RegisterComponent(ComponentId, this);
                
                // Register with FKS Infrastructure for health monitoring
                var registrationInfo = new FKS_Infrastructure.ComponentRegistrationInfo
                {
                    ComponentType = "Indicator",
                    Version = Version,
                    IsCritical = false,
                    ExpectedResponseTime = TimeSpan.FromSeconds(5),
                    MaxMemoryUsage = 100 * 1024 * 1024 // 100MB
                };
                
                FKS_Infrastructure.RegisterComponent(ComponentId, registrationInfo);
                isRegistered = true;
                
                Log($"FKS_AO registered successfully with infrastructure", LogLevel.Information);
            }
            catch (Exception ex)
            {
                Log($"Failed to register FKS_AO with infrastructure: {ex.Message}", LogLevel.Warning);
                isRegistered = false;
            }
        }
        
        private void UnregisterFromInfrastructure()
        {
            try
            {
                if (isRegistered)
                {
                    FKS_Core.UnregisterComponent(ComponentId);
                    FKS_Infrastructure.UnregisterComponent(ComponentId);
                    isRegistered = false;
                    Log($"FKS_AO unregistered from infrastructure", LogLevel.Information);
                }
            }
            catch (Exception ex)
            {
                Log($"Error unregistering FKS_AO: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private void SendHeartbeat()
        {
            try
            {
                if (isRegistered && DateTime.Now - lastHeartbeat > TimeSpan.FromSeconds(5))
                {
                    FKS_Infrastructure.Heartbeat(ComponentId);
                    FKS_Infrastructure.RecordComponentActivity(ComponentId, new FKS_Infrastructure.ComponentActivity
                    {
                        ActivityType = "Heartbeat",
                        Timestamp = DateTime.Now,
                        ErrorMessage = $"Calculations: {calculationCount}, Errors: {errorCount}"
                    });
                    lastHeartbeat = DateTime.Now;
                }
            }
            catch (Exception ex)
            {
                Log($"Error sending heartbeat: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private void UpdateCoreState()
        {
            try
            {
                // Update FKS Core with current AO state every 5 bars
                if (CurrentBar % 5 == 0)
                {
                    var aoData = new FKS_Core.ComponentSignal
                    {
                        SignalType = "AO_Update",
                        Quality = CalculateSignalQuality(),
                        Timestamp = DateTime.Now,
                        Data = new Dictionary<string, object>
                        {
                            ["AOValue"] = aoValue[0],
                            ["SignalLine"] = signalLine[0],
                            ["CrossDirection"] = currentCrossDirection,
                            ["MomentumStrength"] = momentumStrength,
                            ["IsAccelerating"] = isAccelerating,
                            ["IsBullish"] = IsBullish,
                            ["IsBearish"] = IsBearish,
                            ["HasBullishConfirmation"] = HasBullishConfirmation(),
                            ["HasBearishConfirmation"] = HasBearishConfirmation()
                        }
                    };
                    
                    // This would integrate with FKS_Signals if needed
                    // For now, we'll just update internal state
                }
                
                // Publish signals when crossovers occur
                if (currentCrossDirection != 0)
                {
                    var signal = new FKS_Core.FKSSignal
                    {
                        Type = currentCrossDirection > 0 ? "AO_BULLISH" : "AO_BEARISH",
                        Quality = CalculateSignalQuality(),
                        Source = ComponentId,
                        Timestamp = DateTime.Now,
                        Confidence = momentumStrength * 100,
                        MarketRegime = DetermineMarketRegime()
                    };
                    
                    FKS_Core.PublishSignal(signal);
                    
                    // Also integrate with FKS_Signals
                    try
                    {
                        var signalInputs = CreateSignalInputs();
                        var unifiedSignal = FKS_Signals.GenerateSignal(signalInputs);
                        
                        if (unifiedSignal != null && unifiedSignal.IsValid)
                        {
                            Log($"Generated unified AO signal with quality: {unifiedSignal.Quality}", LogLevel.Information);
                        }
                    }
                    catch (Exception ex)
                    {
                        Log($"Error integrating with FKS_Signals: {ex.Message}", LogLevel.Warning);
                    }
                }
            }
            catch (Exception ex)
            {
                Log($"Error updating core state: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private double CalculateSignalQuality()
        {
            double quality = 0.5; // Base quality
            
            // Add quality based on momentum strength
            quality += momentumStrength * 0.3;
            
            // Add quality for acceleration
            if (isAccelerating)
                quality += 0.2;
            
            // Add quality for strong crossovers
            if (Math.Abs(currentCrossDirection) > 0)
                quality += 0.1;
            
            // Add quality for divergence
            if (isDiverging)
                quality += 0.1;
            
            return Math.Max(0, Math.Min(1, quality));
        }
        
        private string DetermineMarketRegime()
        {
            // Simple market regime based on AO behavior
            if (aoValue[0] > 0 && isAccelerating)
                return "BULLISH_MOMENTUM";
            else if (aoValue[0] < 0 && isAccelerating)
                return "BEARISH_MOMENTUM";
            else if (Math.Abs(aoValue[0]) < Math.Abs(aoValue[10]))
                return "CONSOLIDATING";
            else
                return "TRENDING";
        }
        
        private SignalInputs CreateSignalInputs()
        {
            return new SignalInputs
            {
                AISignalType = currentCrossDirection > 0 ? "G" : currentCrossDirection < 0 ? "Top" : "",
                AISignalQuality = CalculateSignalQuality(),
                WaveRatio = 1.0, // Not directly available from AO
                Price = Close[0],
                ATR = ATR(14)[0],
                AOValue = aoValue[0],
                AOConfirmation = HasBullishConfirmation() || HasBearishConfirmation(),
                AOZeroCross = UseAOZeroCross && Math.Abs(currentCrossDirection) > 0,
                AOMomentumStrength = momentumStrength,
                VolumeRatio = Volume[0] / SMA(Volume, 20)[0],
                PriceAboveEMA9 = Close[0] > EMA(9)[0],
                EMA9AboveVWAP = EMA(9)[0] > SMA(Close, 20)[0], // Using SMA as VWAP proxy
                NearVWAP = Math.Abs(Close[0] - SMA(Close, 20)[0]) / ATR(14)[0] < 0.5,
                MarketRegime = DetermineMarketRegime(),
                IsOptimalSession = FKS_Calculations.IsWithinTradingHours(DateTime.Now, 9, 16),
                HasCandleConfirmation = true // Simplified
            };
        }
        #endregion
    }
}
