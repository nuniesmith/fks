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
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.AddOns.FKS;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.FKS
{
    public class FKS_Dashboard : Indicator, FKS_Core.IFKSComponent
    {
        private string currentRegime = "SIDEWAYS";
        private double regimeConfidence = 0.5;
        private bool fksAI_Connected = false;
        private bool fksAO_Connected = false;
        private bool fksVWAP_Connected = false;
        private int dashboardCounter = 0;
        private DateTime lastUpdate = DateTime.MinValue;
        
        // Setup confirmation variables
        private bool trendSetup = false;
        private bool vwapSetup = false;
        private bool volumeSetup = false;
        private bool momentumSetup = false;
        private bool supportResistanceSetup = false;
        private bool riskRewardSetup = false;
        
        // Debug mode flag
        private bool debugMode = false;
        
        // Chart rendering variables
        private SimpleFont dashboardFont;
        private int dashboardWidth = 340;
        private int dashboardHeight = 180;
        
        // Colors for display - will be initialized in OnStateChange
        private Brush backgroundColor;
        private Brush textColor;
        private Brush greenColor;
        private Brush redColor;
        private Brush yellowColor;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "FKS Trading Dashboard - Displays key trading information";
                Name = "FKS_Dashboard";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;
                PaintPriceMarkers = false;
                
                // Add a plot for the dashboard value
                AddPlot(Brushes.Transparent, "Dashboard");
                
                // Properties
                ShowDashboard = true;
                UpdateFrequency = 25;
                ShowComponents = true;
                ShowMarketRegime = true;
                ShowTiming = true;
                ShowSetupConfirmations = true;
                DebugMode = false;
            }
            else if (State == State.DataLoaded)
            {
                // Initialize colors safely in DataLoaded state
                try
                {
                    backgroundColor = new SolidColorBrush(Color.FromArgb(200, 30, 30, 30));
                    textColor = Brushes.White;
                    greenColor = Brushes.LimeGreen;
                    redColor = Brushes.Red;
                    yellowColor = Brushes.Yellow;
                    
                    // Freeze brushes to make them thread-safe
                    backgroundColor.Freeze();
                    textColor.Freeze();
                    greenColor.Freeze();
                    redColor.Freeze();
                    yellowColor.Freeze();
                }
                catch (Exception ex)
                {
                    Print($"FKS Dashboard: Error initializing colors - {ex.Message}");
                    // Use fallback colors that are guaranteed to be thread-safe
                    backgroundColor = Brushes.Transparent;
                    textColor = Brushes.White;
                    greenColor = Brushes.Green;
                    redColor = Brushes.Red;
                    yellowColor = Brushes.Yellow;
                }
                
                // Initialize font for chart rendering
                try
                {
                    dashboardFont = new SimpleFont("Arial", 10);
                }
                catch (Exception ex)
                {
                    Print($"FKS Dashboard: Error initializing font - {ex.Message}");
                    dashboardFont = null;
                }
                
                debugMode = DebugMode;
                
                // Initialize FKS system
                InitializeFKSSystem();
            }
            else if (State == State.Terminated)
            {
                // Cleanup FKS system
                CleanupFKSSystem();
            }
        }

        protected override void OnBarUpdate()
        {
            try
            {
                // Thread safety check
                if (State != State.Realtime && State != State.Historical)
                    return;
                    
                if (CurrentBar < 20) 
                {
                    SafeUpdateUI(() => Name = "FKS_Dashboard: Loading...");
                    return;
                }

                // Ensure colors are initialized
                if (backgroundColor == null)
                {
                    backgroundColor = Brushes.Transparent;
                    textColor = Brushes.White;
                    greenColor = Brushes.Green;
                    redColor = Brushes.Red;
                    yellowColor = Brushes.Yellow;
                }

                // Update regime detection
                UpdateRegimeDetection();

                // Update setup confirmations
                UpdateSetupConfirmations();

                // Simulate component connections
                UpdateComponentStatus();

                // Display dashboard on chart
                if (ShowDashboard && CurrentBar % UpdateFrequency == 0)
                {
                    dashboardCounter++;
                    DisplayDashboardOnChart();
                    UpdateDashboardPlot();
                    lastUpdate = DateTime.Now;
                    
                    // Only print to output if in debug mode
                    if (debugMode) 
                    {
                        Print($"FKS Dashboard Active - Bar: {CurrentBar}, Updates: {dashboardCounter}");
                    }
                    
                    // Performance monitoring
                    PerformanceMonitoring();
                }

                // Update indicator name with key info using thread-safe method
                SafeUpdateUI(() => {
                    Name = $"FKS_Dashboard: {currentRegime} ({regimeConfidence:P0}) | {GetSetupQuality()} | {GetTradingRecommendation()}";
                });
            }
            catch (Exception ex)
            {
                Print($"FKS Dashboard Error: {ex.Message}");
                
                // Reset to safe state
                if (backgroundColor == null)
                {
                    backgroundColor = Brushes.Transparent;
                    textColor = Brushes.White;
                    greenColor = Brushes.Green;
                    redColor = Brushes.Red;
                    yellowColor = Brushes.Yellow;
                }
            }
        }

        private void UpdateDashboardPlot()
        {
            try
            {
                // Set a value for the plot that will show in the data box
                double dashboardValue = GetConfirmedSetupCount() + (regimeConfidence * 10);
                Values[0][0] = dashboardValue;
                
                // Update the plot name to show current status
                Plots[0].Name = $"FKS: {currentRegime} ({regimeConfidence:P0}) | {GetSetupQuality()} ({GetConfirmedSetupCount()}/6)";
            }
            catch (Exception ex)
            {
                if (debugMode)
                {
                    Print($"UpdateDashboardPlot error: {ex.Message}");
                }
            }
        }
        
        private void DisplayDashboardOnChart()
        {
            try
            {
                // Clear previous dashboard drawings
                RemoveDrawObjects();

                // Display dashboard info in the output window
                DisplayFKSDashboard();

                // Update the indicator name to show key info
                UpdateIndicatorName();
            }
            catch (Exception ex)
            {
                Print($"Dashboard display error: {ex.Message}");
            }
        }

        private void UpdateIndicatorName()
        {
            try
            {
                // Count confirmed setups
                int confirmedSetups = 0;
                if (trendSetup) confirmedSetups++;
                if (vwapSetup) confirmedSetups++;
                if (volumeSetup) confirmedSetups++;
                if (momentumSetup) confirmedSetups++;
                if (supportResistanceSetup) confirmedSetups++;
                if (riskRewardSetup) confirmedSetups++;

                string setupQuality = confirmedSetups >= 5 ? "EXCELLENT" : 
                                     confirmedSetups >= 4 ? "GOOD" : 
                                     confirmedSetups >= 3 ? "FAIR" : "POOR";

                // Update indicator name with comprehensive info using thread-safe method
                string newName = $"FKS_Dashboard: {currentRegime} ({regimeConfidence:P0}) | Setup: {setupQuality} ({confirmedSetups}/6) | Updates: {dashboardCounter}";
                
                ExecuteSafely(() => {
                    if (ChartControl != null && ChartControl.Dispatcher.CheckAccess())
                        Name = newName;
                    else
                        ChartControl?.Dispatcher?.BeginInvoke((Action)(() => Name = newName));
                });
            }
            catch (Exception ex)
            {
                Print($"Update indicator name error: {ex.Message}");
                SafeUpdateUI(() => {
                    Name = $"FKS_Dashboard: {currentRegime} | Error: {ex.Message}";
                });
            }
        }

        private void UpdateRegimeDetection()
        {
            try
            {
                // Use FKS_Calculations for enhanced regime detection
                if (CurrentBar >= 50)
                {
                    double sma10 = SMA(10)[0];
                    double sma20 = SMA(20)[0];
                    double sma50 = SMA(50)[0];
                    double ema9 = EMA(9)[0];
                    double atr = ATR(14)[0];
                    double avgVolume = SMA(Volume, 20)[0];
                    
                    // Build price history for enhanced analysis
                    double[] priceHistory = new double[20];
                    for (int i = 0; i < 20 && i < CurrentBar; i++)
                    {
                        priceHistory[i] = Close[i];
                    }
                    
                    // Use FKS_Calculations for enhanced market regime
                    var regimeResult = FKS_Calculations.GetEnhancedMarketRegime(
                        Close[0], ema9, sma20, atr, Volume[0], avgVolume, priceHistory, 20);
                    
                    currentRegime = regimeResult.Regime;
                    regimeConfidence = regimeResult.Confidence;
                    
                    // Record regime detection activity
                    FKS_Infrastructure.RecordComponentActivity(ComponentId, new FKS_Infrastructure.ComponentActivity
                    {
                        ActivityType = "RegimeDetection",
                        Timestamp = DateTime.Now,
                        IsError = false
                    });
                }
                else
                {
                    // Fallback for early bars
                    currentRegime = "LOADING";
                    regimeConfidence = 0.0;
                    SafeUpdateUI(() => Name = "FKS_Dashboard: Calculating...");
                }
            }
            catch (Exception ex)
            {
                Print($"Regime update error: {ex.Message}");
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "RegimeDetection");
            }
        }

        private void InitializeFKSSystem()
        {
            try
            {
                // Initialize FKS Core system
                FKS_Core.Initialize();
                
                // Register with infrastructure
                RegisterWithInfrastructure();
                
                // Record initialization
                FKS_Infrastructure.RecordComponentActivity(ComponentId, new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = "Initialize",
                    Timestamp = DateTime.Now,
                    IsError = false
                });
                
                Status = FKS_Core.ComponentStatus.Healthy;
                Print("FKS Dashboard: Successfully initialized and registered with FKS Core");
            }
            catch (Exception ex)
            {
                Status = FKS_Core.ComponentStatus.Error;
                Print($"FKS Dashboard: Initialization failed - {ex.Message}");
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "Initialization");
            }
        }
        
        private void CleanupFKSSystem()
        {
            try
            {
                // Unregister from FKS Core
                FKS_Core.UnregisterComponent(ComponentId);
                
                // Record cleanup
                FKS_Infrastructure.RecordComponentActivity(ComponentId, new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = "Cleanup",
                    Timestamp = DateTime.Now,
                    IsError = false
                });
                
                Status = FKS_Core.ComponentStatus.Disconnected;
                Print("FKS Dashboard: Successfully cleaned up and unregistered");
            }
            catch (Exception ex)
            {
                Print($"FKS Dashboard: Cleanup failed - {ex.Message}");
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "Cleanup");
            }
        }
        
        private void UpdateComponentStatus()
        {
            try
            {
                dashboardCounter++;
                
                // Get real component health from FKS infrastructure
                var systemHealth = FKS_Infrastructure.GetAdvancedSystemHealth();
                
                // Update connection status based on real component health
                fksAI_Connected = IsComponentHealthy("FKS_AI");
                fksAO_Connected = IsComponentHealthy("FKS_AO");
                fksVWAP_Connected = IsComponentHealthy("FKS_VWAP");
                
                // Record dashboard activity
                FKS_Infrastructure.RecordComponentActivity(ComponentId, new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = "StatusUpdate",
                    Timestamp = DateTime.Now,
                    IsError = false
                });
            }
            catch (Exception ex)
            {
                Print($"Component status update error: {ex.Message}");
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "StatusUpdate");
            }
        }
        
        private bool IsComponentHealthy(string componentId)
        {
            try
            {
                var systemHealth = FKS_Infrastructure.GetAdvancedSystemHealth();
                if (systemHealth.ComponentDetails.ContainsKey(componentId))
                {
                    var componentDetail = systemHealth.ComponentDetails[componentId];
                    return componentDetail.Status == FKS_Infrastructure.ComponentStatus.Healthy;
                }
                return false;
            }
            catch
            {
                return false; // Default to unhealthy if we can't determine status
            }
        }

        private void UpdateSetupConfirmations()
        {
            try
            {
                if (CurrentBar < 50) return;

                // Enhanced setup analysis using FKS system
                double sma20 = SMA(20)[0];
                double sma50 = SMA(50)[0];
                double ema9 = EMA(9)[0];
                double atr = ATR(14)[0];
                double rsi = RSI(14, 3)[0];
                double avgVolume = SMA(Volume, 20)[0];
                
                // Trend Setup - Enhanced with FKS calculations
                double[] highs = new double[20];
                double[] lows = new double[20];
                for (int i = 0; i < 20 && i < CurrentBar; i++)
                {
                    highs[i] = High[i];
                    lows[i] = Low[i];
                }
                
                double waveRatio = FKS_Calculations.CalculateWaveRatio(highs, lows, 20);
                trendSetup = (currentRegime == "BULLISH" && ema9 > sma20 && sma20 > sma50 && waveRatio > 0.6) ||
                           (currentRegime == "BEARISH" && ema9 < sma20 && sma20 < sma50 && waveRatio > 0.6);

                // VWAP Setup - Enhanced calculation
                double typicalPrice = (High[0] + Low[0] + Close[0]) / 3.0;
                vwapSetup = (currentRegime == "BULLISH" && Close[0] > typicalPrice && Volume[0] > avgVolume) ||
                           (currentRegime == "BEARISH" && Close[0] < typicalPrice && Volume[0] > avgVolume);

                // Volume Setup - Enhanced with FKS calculations
                volumeSetup = Volume[0] > avgVolume * 1.5 && regimeConfidence > 0.6;

                // Momentum Setup - Enhanced RSI analysis
                momentumSetup = (currentRegime == "BULLISH" && rsi > 45 && rsi < 75) ||
                               (currentRegime == "BEARISH" && rsi < 55 && rsi > 25);

                // Support/Resistance Setup - Enhanced with ATR
                double high20 = MAX(High, 20)[0];
                double low20 = MIN(Low, 20)[0];
                double priceRange = high20 - low20;
                supportResistanceSetup = (currentRegime == "BULLISH" && Close[0] > low20 + (atr * 2)) ||
                                       (currentRegime == "BEARISH" && Close[0] < high20 - (atr * 2));

                // Risk/Reward Setup - Enhanced with volatility analysis
                double normalizedATR = atr / Close[0];
                riskRewardSetup = normalizedATR > 0.01 && normalizedATR < 0.05 && regimeConfidence > 0.7;
                
                // Record setup analysis activity
                FKS_Infrastructure.RecordComponentActivity(ComponentId, new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = "SetupAnalysis",
                    Timestamp = DateTime.Now,
                    IsError = false
                });
            }
            catch (Exception ex)
            {
                Print($"Setup confirmation error: {ex.Message}");
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "SetupAnalysis");
            }
        }

        private void DisplayFKSDashboard()
        {
            try
            {
                // Always display in output window when ShowDashboard is enabled
                if (ShowDashboard)
                {
                    // Display detailed dashboard in output window
                    if (debugMode) { 
                        Print("");
                        Print("╔════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗");
                        Print("║                                            FKS TRADING DASHBOARD                                                       ║");
                        Print("╠════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣");

                    if (ShowMarketRegime)
                    {
                        Print($"║ MARKET REGIME: {currentRegime,-12} | CONFIDENCE: {regimeConfidence:P0,-6} | QUALITY: {GetSignalQuality(),-8}                  ║");
                    }

                    if (ShowComponents)
                    {
                        Print($"║ COMPONENTS: AI={fksAI_Connected,-5} | AO={fksAO_Connected,-5} | VWAP={fksVWAP_Connected,-5} | UPDATES: {dashboardCounter,-8}                    ║");
                    }

                    if (ShowTiming)
                    {
                        Print($"║ TIMING: BAR={CurrentBar,-6} | TIME={Time[0],-19} | LAST UPDATE: {lastUpdate:HH:mm:ss,-8}                        ║");
                    }

                    // Setup confirmations with checkmarks and X's
                    if (ShowSetupConfirmations)
                    {
                        Print("╠════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣");
                        Print("║                                           SETUP CONFIRMATIONS                                                          ║");
                        Print($"║ TREND:      {(trendSetup ? "✓" : "✗"),-3} | VWAP:      {(vwapSetup ? "✓" : "✗"),-3} | VOLUME:    {(volumeSetup ? "✓" : "✗"),-3} | MOMENTUM: {(momentumSetup ? "✓" : "✗"),-3}                        ║");
                        Print($"║ SUPPORT:    {(supportResistanceSetup ? "✓" : "✗"),-3} | RISK:      {(riskRewardSetup ? "✓" : "✗"),-3} | OVERALL:   {GetSetupQuality(),-8}                                   ║");
                    }

                    Print("╠════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣");
                    Print($"║ INSTRUMENT: {Instrument?.FullName ?? "Unknown",-15} | PRICE: {Close[0],-12:F2} | VOLUME: {Volume[0],-10:F0} | ATR: {ATR(14)[0],-8:F4}    ║");

                    // Market metrics
                    if (CurrentBar >= 50)
                    {
                        double sma20 = SMA(20)[0];
                        double sma50 = SMA(50)[0];
                        double rsi = RSI(14, 3)[0];

                        Print($"║ TECHNICALS: SMA20={sma20,-10:F2} | SMA50={sma50,-10:F2} | RSI={rsi,-6:F1} | BIAS: {GetTrendBias(),-8}                   ║");
                    }

                    // Risk metrics
                    Print($"║ RISK: ATR={ATR(14)[0],-8:F4} | VOLATILITY: {GetVolatilityLevel(),-6} | POSITION: {GetPositionAdvice(),-10}                   ║");

                    Print("╠════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣");
                    Print($"║ STATUS: Dashboard Active | Updates Every {UpdateFrequency} Bars | Last: {DateTime.Now:HH:mm:ss}                               ║");
                    Print("╚════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝");
                        Print("");
                    }
                }
                
                // Always update chart display
                DrawDashboardOnChart();
                
                // Update core state and send heartbeat
                UpdateCoreState();
                SendHeartbeat();
            }
            catch (Exception ex)
            {
                if (DebugMode)
                {
                    Print($"Dashboard display error: {ex.Message}");
                }
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "DisplayDashboard");
                
                // Simple fallback
                if (DebugMode)
                {
                    Print($"FKS Dashboard: {currentRegime} ({regimeConfidence:P0}) - Components: AI={fksAI_Connected} AO={fksAO_Connected} VWAP={fksVWAP_Connected}");
                }
            }
        }        // Chart rendering handled by indicator plot and name display
        // Dashboard info shown in output window and indicator name
        
        private void DrawDashboardOnChart()
        {
            try
            {
                // Update the indicator name to show comprehensive info on chart
                string indicatorName = $"FKS_Dashboard: {currentRegime} ({regimeConfidence:P0}) | {GetSetupQuality()} | {GetTradingRecommendation()}";
                
                ExecuteSafely(() => {
                    if (ChartControl != null && ChartControl.Dispatcher.CheckAccess())
                        Name = indicatorName;
                    else
                        ChartControl?.Dispatcher?.BeginInvoke((Action)(() => Name = indicatorName));
                });

                // Only provide additional print info if in debug mode
                if (debugMode)
                {
                    string dashboardInfo = $"{currentRegime} ({regimeConfidence:P0}) - {GetSetupQuality()}";
                    
                    if (ShowSetupConfirmations)
                    {
                        int setupCount = GetConfirmedSetupCount();
                        string setupText = $"Setups: {setupCount}/6 - {GetTradingRecommendation()}";
                        dashboardInfo += "\n" + setupText;
                        
                        // Add individual setup status
                        string detailText = $"T:{(trendSetup ? "✓" : "✗")} V:{(vwapSetup ? "✓" : "✗")} Vol:{(volumeSetup ? "✓" : "✗")} M:{(momentumSetup ? "✓" : "✗")} S:{(supportResistanceSetup ? "✓" : "✗")} R:{(riskRewardSetup ? "✓" : "✗")}";
                        dashboardInfo += "\n" + detailText;
                    }
                    
                    Print($"CHART INFO: {dashboardInfo.Replace("\n", " | ")}");
                }
                
                // Record chart drawing activity
                FKS_Infrastructure.RecordComponentActivity(ComponentId, new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = "ChartDrawing",
                    Timestamp = DateTime.Now,
                    IsError = false
                });
            }
            catch (Exception ex)
            {
                if (debugMode)
                {
                    Print($"Chart drawing error: {ex.Message}");
                }
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "ChartDrawing");
            }
        }

        private string GetSignalQuality()
        {
            if (regimeConfidence > 0.8) return "HIGH";
            if (regimeConfidence > 0.6) return "MEDIUM";
            return "LOW";
        }

        private string GetTrendBias()
        {
            if (CurrentBar < 50) return "NEUTRAL";

            double sma20 = SMA(20)[0];
            double sma50 = SMA(50)[0];

            if (sma20 > sma50 * 1.002) return "BULLISH";
            if (sma20 < sma50 * 0.998) return "BEARISH";
            return "NEUTRAL";
        }

        private string GetVolatilityLevel()
        {
            double atr = ATR(14)[0];
            double avgPrice = (High[0] + Low[0] + Close[0]) / 3;
            double volatilityPercent = (atr / avgPrice) * 100;

            if (volatilityPercent > 2.0) return "HIGH";
            if (volatilityPercent > 1.0) return "MEDIUM";
            return "LOW";
        }

        private string GetPositionAdvice()
        {
            if (currentRegime == "BULLISH" && regimeConfidence > 0.7) return "LONG";
            if (currentRegime == "BEARISH" && regimeConfidence > 0.7) return "SHORT";
            return "NEUTRAL";
        }

        private string GetSetupQuality()
        {
            // Count confirmed setups
            int confirmedSetups = 0;
            if (trendSetup) confirmedSetups++;
            if (vwapSetup) confirmedSetups++;
            if (volumeSetup) confirmedSetups++;
            if (momentumSetup) confirmedSetups++;
            if (supportResistanceSetup) confirmedSetups++;
            if (riskRewardSetup) confirmedSetups++;

            if (confirmedSetups >= 5) return "EXCELLENT";
            if (confirmedSetups >= 4) return "GOOD";
            if (confirmedSetups >= 3) return "FAIR";
            return "POOR";
        }

        private int GetConfirmedSetupCount()
        {
            int count = 0;
            if (trendSetup) count++;
            if (vwapSetup) count++;
            if (volumeSetup) count++;
            if (momentumSetup) count++;
            if (supportResistanceSetup) count++;
            if (riskRewardSetup) count++;
            return count;
        }
        
        private string GetTradingRecommendation()
        {
            int setupCount = GetConfirmedSetupCount();
            if (setupCount >= 5) return "STRONG " + (currentRegime == "BULLISH" ? "LONG" : "SHORT");
            if (setupCount >= 4) return "MODERATE " + (currentRegime == "BULLISH" ? "LONG" : "SHORT");
            if (setupCount >= 3) return "WEAK " + (currentRegime == "BULLISH" ? "LONG" : "SHORT");
            return "WAIT";
        }
        
        private int GetErrorCount()
        {
            try
            {
                var performanceReport = FKS_Infrastructure.GetComponentPerformanceReport(ComponentId);
                return (int)performanceReport.ErrorCount;
            }
            catch
            {
                return 0;
            }
        }
        
        private string GetPerformanceGrade()
        {
            try
            {
                var performanceReport = FKS_Infrastructure.GetComponentPerformanceReport(ComponentId);
                return performanceReport.PerformanceGrade ?? "UNKNOWN";
            }
            catch
            {
                return "UNKNOWN";
            }
        }

        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Show Dashboard", Order = 1, GroupName = "Dashboard Settings")]
        public bool ShowDashboard { get; set; }

        [NinjaScriptProperty]
        [Range(10, 100)]
        [Display(Name = "Update Frequency (Bars)", Order = 2, GroupName = "Dashboard Settings")]
        public int UpdateFrequency { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Components", Order = 3, GroupName = "Dashboard Settings")]
        public bool ShowComponents { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Market Regime", Order = 4, GroupName = "Dashboard Settings")]
        public bool ShowMarketRegime { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Timing Info", Order = 5, GroupName = "Dashboard Settings")]
        public bool ShowTiming { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Setup Confirmations", Order = 6, GroupName = "Dashboard Settings")]
        public bool ShowSetupConfirmations { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Debug Mode (Output Window)", Order = 7, GroupName = "Dashboard Settings")]
        public bool DebugMode { get; set; }
        #endregion

        #region IFKSComponent Implementation

        public FKS_Core.ComponentStatus Status { get; set; }

        public string ComponentId { get; set; } = "FKS_Dashboard";

        public string Version { get; set; } = "1.0.0";

        public void Initialize()
        {
            Print("LIFECYCLE: FKS Dashboard Component Initialize() called");
            Status = FKS_Core.ComponentStatus.Healthy;
        }

        public void Shutdown()
        {
            CleanupComponent();
        }

        private void CleanupComponent()
        {
            // Cleanup implementation
            Status = FKS_Core.ComponentStatus.Disconnected;
            Print("LIFECYCLE: FKS Dashboard Component shutdown completed");
        }
        #endregion

        private void UpdateCoreState()
        {
            try
            {
                // Register/update component with core
                FKS_Core.RegisterComponent(ComponentId, this);
                
                // Record state update activity
                FKS_Infrastructure.RecordComponentActivity(ComponentId, new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = "StateUpdate",
                    Timestamp = DateTime.Now,
                    IsError = false,
                    ExecutionTime = TimeSpan.FromMilliseconds(lastProcessingTime),
                    MemoryUsage = GC.GetTotalMemory(false)
                });
            }
            catch (Exception ex)
            {
                if (DebugMode)
                {
                    Print($"Core state update error: {ex.Message}");
                }
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "UpdateCoreState");
            }
        }

        private void SendHeartbeat()
        {
            try
            {
                // Send heartbeat to infrastructure
                FKS_Infrastructure.RecordComponentActivity(ComponentId, new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = "Heartbeat",
                    Timestamp = DateTime.Now,
                    IsError = false,
                    ExecutionTime = TimeSpan.FromMilliseconds(lastProcessingTime),
                    MemoryUsage = GC.GetTotalMemory(false)
                });
            }
            catch (Exception ex)
            {
                if (DebugMode)
                {
                    Print($"Heartbeat error: {ex.Message}");
                }
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "SendHeartbeat");
            }
        }

        private void RegisterWithInfrastructure()
        {
            try
            {
                // Register this component with the infrastructure
                FKS_Infrastructure.RegisterComponent(ComponentId, new FKS_Infrastructure.ComponentRegistrationInfo
                {
                    ComponentType = "Dashboard",
                    Version = Version,
                    IsCritical = false,
                    ExpectedResponseTime = TimeSpan.FromMilliseconds(100),
                    MaxMemoryUsage = 10 * 1024 * 1024 // 10MB
                });
                
                // Register with core
                FKS_Core.RegisterComponent(ComponentId, this);
                
                Print($"INFRASTRUCTURE: {ComponentId} registered successfully");
            }
            catch (Exception ex)
            {
                Print($"Infrastructure registration error: {ex.Message}");
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "Registration");
            }
        }

        private void PerformanceMonitoring()
        {
            try
            {
                // Calculate performance metrics
                var stopwatch = System.Diagnostics.Stopwatch.StartNew();
                
                // Simulate processing work (dashboard updates)
                stopwatch.Stop();
                lastProcessingTime = stopwatch.ElapsedMilliseconds;
                
                // Record performance metrics
                FKS_Infrastructure.RecordComponentActivity(ComponentId, new FKS_Infrastructure.ComponentActivity
                {
                    ActivityType = "PerformanceMonitoring",
                    Timestamp = DateTime.Now,
                    IsError = false,
                    ExecutionTime = TimeSpan.FromMilliseconds(lastProcessingTime),
                    MemoryUsage = GC.GetTotalMemory(false)
                });
                
                // Dashboard efficiency monitoring
                if (dashboardCounter > 0)
                {
                    double efficiencyScore = (double)GetConfirmedSetupCount() / 6.0; // 6 total setups
                    FKS_Infrastructure.RecordComponentActivity(ComponentId, new FKS_Infrastructure.ComponentActivity
                    {
                        ActivityType = "EfficiencyScore",
                        Timestamp = DateTime.Now,
                        IsError = false,
                        ExecutionTime = TimeSpan.FromMilliseconds(lastProcessingTime),
                        MemoryUsage = GC.GetTotalMemory(false)
                    });
                }
            }
            catch (Exception ex)
            {
                if (DebugMode)
                {
                    Print($"Performance monitoring error: {ex.Message}");
                }
                FKS_Infrastructure.RecordComponentError(ComponentId, ex, "PerformanceMonitoring");
            }
        }

        #region Thread Safety Helpers
        
        /// <summary>
        /// Execute action safely on the UI thread if needed
        /// </summary>
        private void ExecuteSafely(Action action)
        {
            try
            {
                if (ChartControl != null && ChartControl.Dispatcher != null)
                {
                    if (ChartControl.Dispatcher.CheckAccess())
                    {
                        action();
                    }
                    else
                    {
                        ChartControl.Dispatcher.BeginInvoke(action);
                    }
                }
                else
                {
                    // If no UI context, execute directly
                    action();
                }
            }
            catch (Exception ex)
            {
                Print($"Thread safety error: {ex.Message}");
            }
        }
        
        /// <summary>
        /// Safe method to update UI elements with thread checking
        /// </summary>
        private void SafeUpdateUI(Action uiAction)
        {
            try
            {
                // Check if we're on the UI thread
                if (System.Threading.Thread.CurrentThread.IsBackground)
                {
                    // We're on a background thread, need to invoke on UI thread
                    if (ChartControl?.Dispatcher != null)
                    {
                        ChartControl.Dispatcher.BeginInvoke(uiAction);
                    }
                    else
                    {
                        // No dispatcher available, skip UI update
                        if (DebugMode)
                        {
                            Print("UI update skipped - no dispatcher available");
                        }
                    }
                }
                else
                {
                    // We're on the UI thread, execute directly
                    uiAction();
                }
            }
            catch (Exception ex)
            {
                Print($"Safe UI update error: {ex.Message}");
            }
        }
        
        #endregion

        // Add missing field declarations
        private double lastProcessingTime = 0;
        private string lastError = "";
        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            base.OnRender(chartControl, chartScale);

            if (!ShowDashboard || ChartControl == null)
                return;

            try
            {
                // Get the render target
                SharpDX.Direct2D1.RenderTarget renderTarget = RenderTarget;
                if (renderTarget == null || renderTarget.IsDisposed)
                    return;

                // Define dashboard position and size
                // Move to top-right corner
                float x = ChartPanel.X + ChartPanel.W - dashboardWidth - 20; // Adjust margin for border
                float y = ChartPanel.Y + 10;
                float width = dashboardWidth;
                float height = dashboardHeight;

                // Create background rectangle
                SharpDX.RectangleF backgroundRect = new SharpDX.RectangleF(x, y, width, height);
                
                // Draw background
                using (SharpDX.Direct2D1.SolidColorBrush backgroundBrush = 
                    new SharpDX.Direct2D1.SolidColorBrush(renderTarget, 
                        new SharpDX.Color4(0.117f, 0.117f, 0.117f, 0.8f))) // Dark gray with transparency
                {
                    renderTarget.FillRectangle(backgroundRect, backgroundBrush);
                }

                // Draw border
                using (SharpDX.Direct2D1.SolidColorBrush borderBrush = 
                    new SharpDX.Direct2D1.SolidColorBrush(renderTarget, SharpDX.Color.White))
                {
                    renderTarget.DrawRectangle(backgroundRect, borderBrush, 1f);
                }

                // Draw text
                float textX = x + 10;
                float textY = y + 10;
                float lineHeight = 20;

                using (SharpDX.Direct2D1.SolidColorBrush textBrush = 
                    new SharpDX.Direct2D1.SolidColorBrush(renderTarget, SharpDX.Color.White))
                {
                    // Title
                    SharpDX.DirectWrite.TextFormat titleFormat = new SharpDX.DirectWrite.TextFormat(
                        NinjaTrader.Core.Globals.DirectWriteFactory,
                        "Arial", SharpDX.DirectWrite.FontWeight.Bold,
                        SharpDX.DirectWrite.FontStyle.Normal,
                        SharpDX.DirectWrite.FontStretch.Normal, 14f);

                    renderTarget.DrawText("FKS Trading Dashboard", titleFormat,
                        new SharpDX.RectangleF(textX, textY, width - 20, lineHeight),
                        textBrush);
                    
                    titleFormat.Dispose();
                    textY += lineHeight + 5;

                    // Regular text format
                    SharpDX.DirectWrite.TextFormat textFormat = new SharpDX.DirectWrite.TextFormat(
                        NinjaTrader.Core.Globals.DirectWriteFactory,
                        "Arial", SharpDX.DirectWrite.FontWeight.Normal,
                        SharpDX.DirectWrite.FontStyle.Normal,
                        SharpDX.DirectWrite.FontStretch.Normal, 12f);

                    // Regime info
                    string regimeText = currentRegime == "LOADING" ? "Calculating Market Data..." : $"Regime: {currentRegime} ({regimeConfidence:P0})";
                    SharpDX.Color regimeColor = currentRegime == "BULLISH" ? SharpDX.Color.LimeGreen : 
                                                currentRegime == "BEARISH" ? SharpDX.Color.Red : 
                                                currentRegime == "LOADING" ? SharpDX.Color.Gray :
                                                SharpDX.Color.Yellow;
                    
                    using (SharpDX.Direct2D1.SolidColorBrush regimeBrush = 
                        new SharpDX.Direct2D1.SolidColorBrush(renderTarget, regimeColor))
                    {
                        renderTarget.DrawText(regimeText, textFormat,
                            new SharpDX.RectangleF(textX, textY, width - 20, lineHeight),
                            regimeBrush);
                    }
                    textY += lineHeight;

                    // Setup quality
                    string setupText = $"Setup Quality: {GetSetupQuality()} ({GetConfirmedSetupCount()}/6)";
                    renderTarget.DrawText(setupText, textFormat,
                        new SharpDX.RectangleF(textX, textY, width - 20, lineHeight),
                        textBrush);
                    textY += lineHeight;

                    // Trading recommendation
                    string adviceText = $"Recommendation: {GetTradingRecommendation()}";
                    SharpDX.Color adviceColor = GetTradingRecommendation().Contains("STRONG") ? SharpDX.Color.LimeGreen :
                                               GetTradingRecommendation().Contains("MODERATE") ? SharpDX.Color.Yellow :
                                               SharpDX.Color.Gray;
                    
                    using (SharpDX.Direct2D1.SolidColorBrush adviceBrush = 
                        new SharpDX.Direct2D1.SolidColorBrush(renderTarget, adviceColor))
                    {
                        renderTarget.DrawText(adviceText, textFormat,
                            new SharpDX.RectangleF(textX, textY, width - 20, lineHeight),
                            adviceBrush);
                    }
                    textY += lineHeight;

                    // Setup confirmations
                    if (ShowSetupConfirmations)
                    {
                        string confirmText = $"T:{(trendSetup ? "✓" : "✗")} V:{(vwapSetup ? "✓" : "✗")} Vol:{(volumeSetup ? "✓" : "✗")} M:{(momentumSetup ? "✓" : "✗")} S/R:{(supportResistanceSetup ? "✓" : "✗")} R/R:{(riskRewardSetup ? "✓" : "✗")}";
                        renderTarget.DrawText(confirmText, textFormat,
                            new SharpDX.RectangleF(textX, textY, width - 20, lineHeight),
                            textBrush);
                    }

                    textFormat.Dispose();
                }
            }
            catch (Exception ex)
            {
                Print($"OnRender error: {ex.Message}");
            }
        }
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private FKS.FKS_Dashboard[] cacheFKS_Dashboard;
		public FKS.FKS_Dashboard FKS_Dashboard(bool showDashboard, int updateFrequency, bool showComponents, bool showMarketRegime, bool showTiming, bool showSetupConfirmations, bool debugMode)
		{
			return FKS_Dashboard(Input, showDashboard, updateFrequency, showComponents, showMarketRegime, showTiming, showSetupConfirmations, debugMode);
		}

		public FKS.FKS_Dashboard FKS_Dashboard(ISeries<double> input, bool showDashboard, int updateFrequency, bool showComponents, bool showMarketRegime, bool showTiming, bool showSetupConfirmations, bool debugMode)
		{
			if (cacheFKS_Dashboard != null)
				for (int idx = 0; idx < cacheFKS_Dashboard.Length; idx++)
					if (cacheFKS_Dashboard[idx] != null && cacheFKS_Dashboard[idx].ShowDashboard == showDashboard && cacheFKS_Dashboard[idx].UpdateFrequency == updateFrequency && cacheFKS_Dashboard[idx].ShowComponents == showComponents && cacheFKS_Dashboard[idx].ShowMarketRegime == showMarketRegime && cacheFKS_Dashboard[idx].ShowTiming == showTiming && cacheFKS_Dashboard[idx].ShowSetupConfirmations == showSetupConfirmations && cacheFKS_Dashboard[idx].DebugMode == debugMode && cacheFKS_Dashboard[idx].EqualsInput(input))
						return cacheFKS_Dashboard[idx];
			return CacheIndicator<FKS.FKS_Dashboard>(new FKS.FKS_Dashboard(){ ShowDashboard = showDashboard, UpdateFrequency = updateFrequency, ShowComponents = showComponents, ShowMarketRegime = showMarketRegime, ShowTiming = showTiming, ShowSetupConfirmations = showSetupConfirmations, DebugMode = debugMode }, input, ref cacheFKS_Dashboard);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.FKS.FKS_Dashboard FKS_Dashboard(bool showDashboard, int updateFrequency, bool showComponents, bool showMarketRegime, bool showTiming, bool showSetupConfirmations, bool debugMode)
		{
			return indicator.FKS_Dashboard(Input, showDashboard, updateFrequency, showComponents, showMarketRegime, showTiming, showSetupConfirmations, debugMode);
		}

		public Indicators.FKS.FKS_Dashboard FKS_Dashboard(ISeries<double> input , bool showDashboard, int updateFrequency, bool showComponents, bool showMarketRegime, bool showTiming, bool showSetupConfirmations, bool debugMode)
		{
			return indicator.FKS_Dashboard(input, showDashboard, updateFrequency, showComponents, showMarketRegime, showTiming, showSetupConfirmations, debugMode);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.FKS.FKS_Dashboard FKS_Dashboard(bool showDashboard, int updateFrequency, bool showComponents, bool showMarketRegime, bool showTiming, bool showSetupConfirmations, bool debugMode)
		{
			return indicator.FKS_Dashboard(Input, showDashboard, updateFrequency, showComponents, showMarketRegime, showTiming, showSetupConfirmations, debugMode);
		}

		public Indicators.FKS.FKS_Dashboard FKS_Dashboard(ISeries<double> input , bool showDashboard, int updateFrequency, bool showComponents, bool showMarketRegime, bool showTiming, bool showSetupConfirmations, bool debugMode)
		{
			return indicator.FKS_Dashboard(input, showDashboard, updateFrequency, showComponents, showMarketRegime, showTiming, showSetupConfirmations, debugMode);
		}
	}
}

#endregion
