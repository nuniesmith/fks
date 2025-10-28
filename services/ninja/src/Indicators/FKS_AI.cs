// FKS_AI.cs - FKS AI Indicator
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
    /// FKS AI Indicator - FKS indicator
    /// Provides support/resistance detection, signal generation, and wave analysis
    /// </summary>
    public class FKS_AI : Indicator, FKS_Core.IFKSComponent
    {
        #region Variables
        // Component Interface
        public string ComponentId => "FKS_AI";
        public string Version => "1.0.0";
        
        // Core Parameters
        private string assetType = "Gold";
        private int maxLength = 20;
        private double accelMultiplier = 0.02;
        private int lookbackPeriod = 200;
        private double minWaveRatio = 1.5;
        private double exitMomentumThreshold = 0.7;
        
        // Infrastructure Integration
        private DateTime lastHeartbeat = DateTime.MinValue;
        private DateTime lastActivity = DateTime.MinValue;
        private int calculationCount = 0;
        private int errorCount = 0;
        private bool isRegistered = false;
        
        // Visualization
        private Brush upHistColor;
        private Brush upHistColorBright;
        private Brush dnHistColor;
        private Brush dnHistColorBright;
        private Brush supportColor;
        private Brush resistanceColor;
        
        // Pattern Detection
        private int srLength = 150;
        private double signalSensitivity = 0.5;
        private double signalQualityThreshold = 0.65;
        
        // State Variables
        private Series<double> dynamicEMA;
        private Series<double> trendSpeed;
        private Series<double> lowestSrc;
        private Series<double> highestSrc;
        private Series<double> midSrc;
        
        // Signal State
        private string currentSignalType = "";
        private double currentSignalQuality = 0;
        private double currentWaveRatio = 0;
        private string currentMarketRegime = "NEUTRAL";
        private double nearestSupport = 0;
        private double nearestResistance = 0;
        
        // Wave Analysis
        private List<double> bullishWaves = new List<double>();
        private List<double> bearishWaves = new List<double>();
        private int lastCrossBar = 0;
        private double lastCrossPrice = 0;
        private int position = 0;
        private double speed = 0;
        
        // Market Phase
        private string marketPhase = "ACCUMULATION";
        
        // Momentum & Volatility
        private ATR atr;
        private VOL volume;
        private EMA ema9;
        
        // VWAP Integration Fields
        private double currentVWAP = 0;
        private double vwapDistance = 0;
        private string vwapPosition = "NEAR"; // "ABOVE", "BELOW", "NEAR"
        private double vwapStrength = 0;
        private string vwapTrend = "NEUTRAL"; // "BULLISH", "BEARISH", "NEUTRAL"
        private double cumulativeVolume = 0;
        private double cumulativeTypicalPriceVolume = 0;
        private double cumulativeSquaredPriceVolume = 0;
        private DateTime sessionStart;
        private bool isNewSession = false;
        private Series<double> vwapValue;
        private Series<double> vwapDeviation1;
        private Series<double> vwapDeviation2;
        private double deviationMultiplier1 = 1.0;
        private double deviationMultiplier2 = 2.0;
        private double proximityThreshold = 0.5; // ATR multiplier for "near" VWAP
        private bool useSessionReset = true;
        #endregion
        
        #region Debug Infrastructure
        
        private readonly List<string> debugLog = new List<string>();
        private DateTime lastDebugUpdate = DateTime.MinValue;
        private readonly TimeSpan debugUpdateInterval = TimeSpan.FromSeconds(5);
        private DateTime lastAILogTime = DateTime.MinValue;
        private DateTime lastSIGNALLogTime = DateTime.MinValue;
        private DateTime lastMARKETLogTime = DateTime.MinValue;
        private string lastLogMessage = "";
        private int logSuppressCount = 0;
        
        private void LogDebug(string category, string message, string level = "INFO")
        {
            ConsolidateAlerts(category, message);
            if (!EnableDebugMode) return;
            
            try
            {
                // Aggressive rate limiting for frequent categories
                if (category == "AI" && lastAILogTime.AddSeconds(30) > DateTime.Now)
                {
                    logSuppressCount++;
                    return;
                }
                
                if (category == "SIGNAL" && lastSIGNALLogTime.AddSeconds(15) > DateTime.Now)
                {
                    logSuppressCount++;
                    return;
                }
                
                if (category == "MARKET" && lastMARKETLogTime.AddSeconds(15) > DateTime.Now)
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
                if (category == "AI") lastAILogTime = DateTime.Now;
                if (category == "SIGNAL") lastSIGNALLogTime = DateTime.Now;
                if (category == "MARKET") lastMARKETLogTime = DateTime.Now;
                lastLogMessage = message;
                lastDebugUpdate = DateTime.Now;
            }
            catch (Exception ex)
            {
                Print($"Debug logging error: {ex.Message}");
            }
        }

        private void ConsolidateAlerts(string category, string message)
        {
            // Centralize and filter alerts here
            if (category == "SIGNAL" && currentSignalQuality >= signalQualityThreshold)
            {
                SendAlert(category, message);
            }
        }

        private void SendAlert(string category, string message)
        {
            // Placeholder for sending alerts (e.g., logging, email)
            // Implement actual alert sending mechanism
            Print($"Alert [{category}]: {message}");
        }

        private void PerformDebugCheck()
        {
            if (!EnableDebugMode) return;
            
            try
            {
                LogDebug("AI", $"Current Signal: {currentSignalType} (Quality: {currentSignalQuality:F2})", "INFO");
                LogDebug("AI", $"S/R Levels: Support={nearestSupport:F2}, Resistance={nearestResistance:F2}", "INFO");
                LogDebug("AI", $"Market Phase: {marketPhase}, Regime: {currentMarketRegime}", "INFO");
                LogDebug("AI", $"Wave Analysis: Bull={bullishWaves.Count}, Bear={bearishWaves.Count}", "INFO");
                LogDebug("AI", $"Component Status: Registered={isRegistered}, Errors={errorCount}", "INFO");
            }
            catch (Exception ex)
            {
                LogDebug("AI", $"Debug check error: {ex.Message}", "ERROR");
            }
        }
        
        #endregion
        
        #region OnStateChange
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"FKS AI - Support/Resistance detection with signal quality scoring";
                Name = "FKS_AI";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;
                DrawHorizontalGridLines = true;
                DrawVerticalGridLines = true;
                PaintPriceMarkers = true;
                ScaleJustification = NinjaTrader.Gui.Chart.ScaleJustification.Right;
                IsSuspendedWhileInactive = false;
                
                // Visual defaults
                ShowSRBands = true;
                ShowSignalLabels = true;
                ShowEntryZones = true;
                ShowWaveInfo = false;
                ShowMarketPhase = false;
                CleanChartMode = false;
                
                // Colors
                ResistanceColor = Brushes.Red;
                SupportColor = Brushes.Green;
                MiddleColor = Brushes.Blue;
                SignalLabelColor = Brushes.White;
                
                // Debug defaults
                EnableDebugMode = false;
                VerboseDebug = false;
                
                // Add plots for data series
                AddPlot(new Stroke(Brushes.Red, 2), PlotStyle.Line, "Resistance");
                AddPlot(new Stroke(Brushes.Blue, 1), PlotStyle.Line, "Middle");
                AddPlot(new Stroke(Brushes.Green, 2), PlotStyle.Line, "Support");
                
                // Add VWAP plots
                AddPlot(new Stroke(Brushes.Orange, 2), PlotStyle.Line, "VWAP");
                AddPlot(new Stroke(Brushes.DarkOrange, DashStyleHelper.Dash, 1), PlotStyle.Line, "VWAP Dev1 Upper");
                AddPlot(new Stroke(Brushes.DarkOrange, DashStyleHelper.Dash, 1), PlotStyle.Line, "VWAP Dev1 Lower");
                AddPlot(new Stroke(Brushes.OrangeRed, DashStyleHelper.Dot, 1), PlotStyle.Line, "VWAP Dev2 Upper");
                AddPlot(new Stroke(Brushes.OrangeRed, DashStyleHelper.Dot, 1), PlotStyle.Line, "VWAP Dev2 Lower");
                
                // Add EMA9 plot
                AddPlot(new Stroke(Brushes.Magenta, 2), PlotStyle.Line, "EMA9");
            }
            else if (State == State.Configure)
            {
                // Configure market-specific parameters
                ConfigureForMarket();
            }
            else if (State == State.DataLoaded)
            {
                // Initialize series
                dynamicEMA = new Series<double>(this);
                trendSpeed = new Series<double>(this);
                lowestSrc = new Series<double>(this);
                highestSrc = new Series<double>(this);
                midSrc = new Series<double>(this);
                
                // Initialize VWAP series
                vwapValue = new Series<double>(this);
                vwapDeviation1 = new Series<double>(this);
                vwapDeviation2 = new Series<double>(this);
                
                // Initialize indicators
                atr = ATR(14);
                volume = VOL();
                
                // Initialize EMA9
                ema9 = EMA(9);
                
                // Initialize colors
                upHistColor = Brushes.LimeGreen;
                upHistColorBright = Brushes.Lime;
                dnHistColor = Brushes.Red;
                dnHistColorBright = Brushes.OrangeRed;
                
                // Initialize session
                sessionStart = DateTime.MinValue;
                
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
            if (CurrentBar < Math.Max(srLength, lookbackPeriod)) return;
            
            var stopwatch = Stopwatch.StartNew();
            
            try
            {
                // Send heartbeat every 10 bars
                if (CurrentBar % 10 == 0)
                {
                    SendHeartbeat();
                }
                
                // Check for new session
                CheckForNewSession();
                
                // Calculate VWAP
                CalculateVWAP();
                
                // Calculate Support/Resistance
                CalculateSupportResistance();
                
                // Calculate Dynamic EMA (Trend Speed)
                CalculateDynamicEMA();
                
                // Detect signals (now includes VWAP)
                DetectSignals();
                
                // Calculate signal quality (now includes VWAP)
                CalculateSignalQuality();
                
                // Enhanced signal analysis
                AnalyzeSignalWithEnhancedProcessing();
                
                // Update market phase
                UpdateMarketPhase();
                
                // Update FKS Core with current state
                UpdateCoreState();
                
                // Check system health periodically
                CheckSystemHealth();
                
                // Debug check
                if (EnableDebugMode && DateTime.Now - lastDebugUpdate >= debugUpdateInterval)
                {
                    PerformDebugCheck();
                    lastDebugUpdate = DateTime.Now;
                }
                
                // Set plot values
                Values[0][0] = highestSrc[0]; // Resistance
                Values[1][0] = midSrc[0];     // Middle
                Values[2][0] = lowestSrc[0];  // Support
                
                // Set VWAP plot values
                if (currentVWAP > 0)
                {
                    Values[3][0] = currentVWAP; // VWAP
                    Values[4][0] = currentVWAP + deviationMultiplier1 * GetVWAPDeviation(); // Dev1 Upper
                    Values[5][0] = currentVWAP - deviationMultiplier1 * GetVWAPDeviation(); // Dev1 Lower
                    Values[6][0] = currentVWAP + deviationMultiplier2 * GetVWAPDeviation(); // Dev2 Upper
                    Values[7][0] = currentVWAP - deviationMultiplier2 * GetVWAPDeviation(); // Dev2 Lower
                }
                
                // Set EMA9 plot value
                Values[8][0] = ema9[0];
                
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
                Log($"FKS_AI Error in OnBarUpdate: {ex.Message}", LogLevel.Error);
                LogDebug("AI", $"Error in OnBarUpdate: {ex.Message}", "ERROR");
            }
        }
        #endregion
        
        #region Calculations
        private void CalculateSupportResistance()
        {
            // Calculate support and resistance levels
            lowestSrc[0] = MIN(Low, srLength)[0];
            highestSrc[0] = MAX(High, srLength)[0];
            midSrc[0] = (lowestSrc[0] + highestSrc[0]) / 2;
            
            // Find nearest levels for higher timeframe analysis
            FindNearestLevels();
        }
        
        private void CalculateDynamicEMA()
        {
            // Port of PineScript dynamic EMA calculation
            double countsDiff = Close[0];
            double maxAbsCountsDiff = MAX(ATR(1), 200)[0]; // Use ATR instead of High-Low
            double countsDiffNorm = maxAbsCountsDiff > 0 ? 
                (countsDiff + maxAbsCountsDiff) / (2 * maxAbsCountsDiff) : 0.5;
            
            double dynLength = 5 + countsDiffNorm * (maxLength - 5);
            
            // Calculate accelerator factor
            double deltaCountsDiff = Math.Abs(countsDiff - (CurrentBar > 0 ? Close[1] : countsDiff));
            double maxDeltaCountsDiff = MAX(ATR(1), 200)[0]; // Simplified
            double accelFactor = maxDeltaCountsDiff > 0 ? deltaCountsDiff / maxDeltaCountsDiff : 0;
            
            // Adjust alpha
            double alphaBase = 2.0 / (dynLength + 1);
            double alpha = Math.Min(0.9, alphaBase * (1 + accelFactor * accelMultiplier * 0.8));
            
            // Calculate dynamic EMA
            if (CurrentBar == 0)
                dynamicEMA[0] = Close[0];
            else
                dynamicEMA[0] = alpha * Close[0] + (1 - alpha) * dynamicEMA[1];
            
            // Update trend speed
            UpdateTrendSpeed();
        }
        
        private void UpdateTrendSpeed()
        {
            // Wave analysis logic from PineScript
            double c = SMA(Close, 10)[0];
            double o = SMA(Open, 10)[0];
            
            // Detect crossovers
            if (Close[0] > dynamicEMA[0] && Close[1] <= dynamicEMA[1])
            {
                // Bullish cross
                if (position == -1)
                {
                    bearishWaves.Add(speed);
                    if (bearishWaves.Count > lookbackPeriod)
                        bearishWaves.RemoveAt(0);
                }
                
                lastCrossBar = CurrentBar;
                lastCrossPrice = Close[0];
                position = 1;
                speed = c - o;
            }
            else if (Close[0] < dynamicEMA[0] && Close[1] >= dynamicEMA[1])
            {
                // Bearish cross
                if (position == 1)
                {
                    bullishWaves.Add(speed);
                    if (bullishWaves.Count > lookbackPeriod)
                        bullishWaves.RemoveAt(0);
                }
                
                lastCrossBar = CurrentBar;
                lastCrossPrice = Close[0];
                position = -1;
                speed = c - o;
            }
            else
            {
                speed += c - o;
            }
            
            trendSpeed[0] = speed; // Simplified - just use the speed value directly
            
            // Calculate wave ratio
            CalculateWaveRatio();
        }
        
        private void CalculateWaveRatio()
        {
            if (bullishWaves.Count > 0 && bearishWaves.Count > 0)
            {
                double bullAvg = bullishWaves.Average();
                double bearAvg = Math.Abs(bearishWaves.Average());
                
                if (bearAvg > 0)
                {
                    currentWaveRatio = bullAvg / bearAvg;
                }
                else
                {
                    currentWaveRatio = 1.0;
                }
            }
            else
            {
                currentWaveRatio = 1.0;
            }
        }
        
        private void DetectSignals()
        {
            // Simple signal detection based on price action
            double rocNormalized = (Close[0] - Close[10]) / atr[0];
            
            if (Low[0] > lowestSrc[0] && Low[1] <= lowestSrc[1] && 
                rocNormalized < -2 * signalSensitivity && 
                CurrentBar - lastCrossBar > 5)
            {
                currentSignalType = "G";
                lastCrossBar = CurrentBar;
                LogDebug("SIGNAL", $"Strong Buy Signal detected at {Close[0]:F2} (ROC: {rocNormalized:F2})", "INFO");
            }
            else if (High[0] < highestSrc[0] && High[1] >= highestSrc[1] && 
                     rocNormalized > 2 * signalSensitivity && 
                     CurrentBar - lastCrossBar > 5)
            {
                currentSignalType = "Top";
                lastCrossBar = CurrentBar;
                LogDebug("SIGNAL", $"Strong Sell Signal detected at {Close[0]:F2} (ROC: {rocNormalized:F2})", "INFO");
            }
            else if (Low[0] > lowestSrc[0] && Low[1] <= lowestSrc[1])
            {
                currentSignalType = "^";
                LogDebug("SIGNAL", $"Weak Buy Signal detected at {Close[0]:F2}", "INFO");
            }
            else if (High[0] < highestSrc[0] && High[1] >= highestSrc[1])
            {
                currentSignalType = "v";
                LogDebug("SIGNAL", $"Weak Sell Signal detected at {Close[0]:F2}", "INFO");
            }
            else
            {
                currentSignalType = "";
            }
        }
        
        private void CalculateSignalQuality()
        {
            if (string.IsNullOrEmpty(currentSignalType))
            {
                currentSignalQuality = 0;
                return;
            }
            
            double quality = 0.5; // Base quality
            
            // Wave ratio component
            if (currentSignalType == "G" || currentSignalType == "Top")
            {
                bool trendAligned = (currentSignalType == "G" && Close[0] > EMA(9)[0]) ||
                                   (currentSignalType == "Top" && Close[0] < EMA(9)[0]);
                
                if (currentWaveRatio > 2.0)
                    quality += 0.2;
                else if (currentWaveRatio > 1.5)
                    quality += 0.15;
                else if (currentWaveRatio > 1.0)
                    quality += 0.1;
                
                if (trendAligned)
                    quality += 0.1;
                
                // Volume confirmation
                if (Volume[0] > SMA(Volume, 20)[0] * 1.2)
                    quality += 0.1;
                
                // Volatility check
                double volPercentile = atr[0] / SMA(atr, 50)[0];
                if (volPercentile > 0.5 && volPercentile < 1.5)
                    quality += 0.1;
                
                // Market phase alignment
                if ((marketPhase == "UPTREND" && position > 0) ||
                    (marketPhase == "DOWNTREND" && position < 0))
                    quality += 0.1;
            }
            
            currentSignalQuality = Math.Max(0, Math.Min(1, quality));
        }
        
        private void UpdateMarketPhase()
        {
            if (Close[0] > highestSrc[10] && trendSpeed[0] > 0)
            {
                marketPhase = "UPTREND";
            }
            else if (Close[0] < lowestSrc[10] && trendSpeed[0] < 0)
            {
                marketPhase = "DOWNTREND";
            }
            else if (Close[0] > highestSrc[5] && Close[0] < highestSrc[0] && 
                     trendSpeed[0] > 0 && trendSpeed[0] < trendSpeed[10])
            {
                marketPhase = "DISTRIBUTION";
            }
            else if (Close[0] < lowestSrc[5] && Close[0] > lowestSrc[0] && 
                     trendSpeed[0] < 0 && trendSpeed[0] > trendSpeed[10])
            {
                marketPhase = "ACCUMULATION";
            }
            
            // Volume-based regime detection
            double volRatio = Volume[0] / SMA(Volume, 20)[0];
            double normalizedSlope = (Close[0] - Close[20]) / (20 * atr[0]);
            
            if (Math.Abs(normalizedSlope) > 1.0)
            {
                currentMarketRegime = normalizedSlope > 0 ? "BULLISH" : "BEARISH";
            }
            else
            {
                if (volRatio > 1.5)
                    currentMarketRegime = "VOLATILE";
                else if (volRatio < 0.8)
                    currentMarketRegime = "QUIET";
                else
                    currentMarketRegime = "NEUTRAL";
            }
        }
        
        private void FindNearestLevels()
        {
            // Find nearest support and resistance levels
            nearestSupport = lowestSrc[0];
            nearestResistance = highestSrc[0];
            
            // Look for additional levels within the range
            for (int i = 1; i < Math.Min(50, CurrentBar); i++)
            {
                double lowLevel = MIN(Low, 10)[i];
                double highLevel = MAX(High, 10)[i];
                
                // Check if this is a significant level
                if (Math.Abs(Close[0] - lowLevel) < Math.Abs(Close[0] - nearestSupport) && lowLevel < Close[0])
                {
                    nearestSupport = lowLevel;
                }
                
                if (Math.Abs(Close[0] - highLevel) < Math.Abs(Close[0] - nearestResistance) && highLevel > Close[0])
                {
                    nearestResistance = highLevel;
                }
            }
        }
        #endregion
        
        #region Drawing
        private void DrawSignals()
        {
            // Drawing temporarily disabled due to type conflicts
            // TODO: Resolve Draw class conflicts
            return;
        }
        
        private void DrawEntryZones()
        {
            // Drawing temporarily disabled due to type conflicts
            // TODO: Resolve Draw class conflicts
            return;
        }
        #endregion
        
        #region Integration
        private void UpdateCoreState()
        {
            // Update FKS Core with current market state
            if (CurrentBar % 5 == 0) // Update every 5 bars for performance
            {
                var marketState = new FKS_Core.MarketState
                {
                    MarketRegime = currentMarketRegime,
                    TrendDirection = position > 0 ? "BULLISH" : position < 0 ? "BEARISH" : "NEUTRAL",
                    Volatility = atr[0],
                    VolumeRatio = Volume[0] / SMA(Volume, 20)[0],
                    SignalType = currentSignalType,
                    SignalQuality = currentSignalQuality,
                    WaveRatio = currentWaveRatio,
                    LastUpdate = DateTime.Now,
                    // Enhanced properties
                    TrendStrength = Math.Abs(trendSpeed[0]),
                    VolatilityRegime = GetVolatilityRegime(),
                    MomentumScore = CalculateMomentumScore()
                };
                
                FKS_Core.UpdateMarketState(marketState);
            }
            
            // Publish signals to core and FKS_Signals
            if (!string.IsNullOrEmpty(currentSignalType) && currentSignalQuality >= signalQualityThreshold)
            {
                var signal = new FKS_Core.FKSSignal
                {
                    Type = currentSignalType,
                    Quality = currentSignalQuality,
                    Source = ComponentId,
                    WaveRatio = currentWaveRatio,
                    SetupNumber = DetermineSetupNumber(),
                    RecommendedContracts = CalculateRecommendedContracts(),
                    Timestamp = DateTime.Now,
                    // Enhanced properties
                    Confidence = currentSignalQuality * 100,
                    MarketRegime = currentMarketRegime,
                    RiskRewardRatio = CalculateRiskRewardRatio()
                };
                
                FKS_Core.PublishSignal(signal);
                
                // Also integrate with FKS_Signals if available
                try
                {
                    var signalInputs = CreateSignalInputs();
                    var unifiedSignal = FKS_Signals.GenerateSignal(signalInputs);
                    
                    // Optionally use the unified signal for additional processing
                    if (unifiedSignal != null && unifiedSignal.IsValid)
                    {
                        Log($"Generated unified signal with quality: {unifiedSignal.Quality}", LogLevel.Information);
                    }
                }
                catch (Exception ex)
                {
                    Log($"Error integrating with FKS_Signals: {ex.Message}", LogLevel.Warning);
                }
            }
        }
        
        private string GetVolatilityRegime()
        {
            double volRatio = atr[0] / SMA(atr, 50)[0];
            
            if (volRatio > 1.5) return "HIGH";
            else if (volRatio > 1.2) return "ELEVATED";
            else if (volRatio < 0.8) return "LOW";
            else return "NORMAL";
        }
        
        private double CalculateMomentumScore()
        {
            double shortMomentum = (Close[0] - Close[5]) / (5 * atr[0]);
            double mediumMomentum = (Close[0] - Close[20]) / (20 * atr[0]);
            
            return (shortMomentum + mediumMomentum) / 2.0;
        }
        
        /// <summary>
        /// Calculate risk reward ratio based on support/resistance levels
        /// </summary>
        private double CalculateRiskRewardRatio()
        {
            try
            {
                if (nearestSupport == 0 || nearestResistance == 0) return 2.0; // Default

                double currentPrice = Close[0];
                double potentialProfit = 0;
                double potentialLoss = 0;

                if (currentSignalType == "G") // Bullish signal
                {
                    potentialProfit = nearestResistance - currentPrice;
                    potentialLoss = currentPrice - nearestSupport;
                }
                else if (currentSignalType == "Top") // Bearish signal
                {
                    potentialProfit = currentPrice - nearestSupport;
                    potentialLoss = nearestResistance - currentPrice;
                }

                if (potentialLoss > 0)
                {
                    double ratio = potentialProfit / potentialLoss;
                    return Math.Max(0.5, Math.Min(10.0, ratio)); // Clamp between 0.5 and 10
                }

                return 2.0; // Default ratio
            }
            catch (Exception ex)
            {
                LogDebug("AI", $"Error calculating risk reward ratio: {ex.Message}", "ERROR");
                return 2.0;
            }
        }
        
        private SignalInputs CreateSignalInputs()
        {
            return new SignalInputs
            {
                AISignalType = currentSignalType,
                AISignalQuality = currentSignalQuality,
                WaveRatio = currentWaveRatio,
                Price = Close[0],
                ATR = atr[0],
                AOValue = 0, // Not available in this indicator
                AOConfirmation = false,
                AOZeroCross = false,
                AOMomentumStrength = Math.Abs(trendSpeed[0]),
                VolumeRatio = Volume[0] / SMA(Volume, 20)[0],
                PriceAboveEMA9 = Close[0] > EMA(9)[0],
                EMA9AboveVWAP = EMA(9)[0] > currentVWAP,
                NearVWAP = vwapPosition == "NEAR",
                MarketRegime = currentMarketRegime,
                IsOptimalSession = FKS_Calculations.IsWithinTradingHours(DateTime.Now, 9, 16),
                HasCandleConfirmation = true // Simplified - always true for now
            };
        }
        
        private int DetermineSetupNumber()
        {
            // Simple setup determination based on current conditions
            bool priceAboveEMA = Close[0] > EMA(9)[0];
            bool emaAboveVWAP = EMA(9)[0] > currentVWAP;
            
            if ((currentSignalType == "G" || currentSignalType == "^") && priceAboveEMA && emaAboveVWAP)
                return 1; // Bullish breakout
            else if ((currentSignalType == "Top" || currentSignalType == "v") && !priceAboveEMA && !emaAboveVWAP)
                return 2; // Bearish breakdown
            else if (vwapPosition == "NEAR")
                return 3; // VWAP bounce
            else if (Math.Abs(Close[0] - nearestSupport) / atr[0] < 0.5 || 
                     Math.Abs(Close[0] - nearestResistance) / atr[0] < 0.5)
                return 4; // S/R setup
            
            return 0;
        }
        
        private int CalculateRecommendedContracts()
        {
            // Enhanced position sizing using shared calculation utilities
            double accountSize = 100000; // Default account size
            double riskPercent = 1.0; // 1% risk per trade
            double stopDistance = atr[0] * 2.0; // 2 ATR stop
            double tickValue = GetTickValueForMarket(assetType);
            
            // Use enhanced position sizing methods
            try
            {
                int baseContracts = FKS_Calculations.CalculateOptimalContracts(accountSize, riskPercent, stopDistance, tickValue);
                
                // Use volatility-adjusted sizing if available
                double currentATR = atr[0];
                double avgATR = SMA(atr, 20)[0];
                int volAdjustedContracts = FKS_Calculations.CalculateVolatilityAdjustedSize(
                    accountSize, baseContracts, currentATR, avgATR);
                
                // Use Kelly criterion for high-quality signals
                if (currentSignalQuality > 0.75 && currentWaveRatio > 1.5)
                {
                    // Assume historical performance metrics
                    double winRate = 0.65;
                    double avgWin = stopDistance * 2.0; // 2:1 R:R
                    double avgLoss = stopDistance;
                    
                    int kellyContracts = FKS_Calculations.CalculateKellyContracts(
                        accountSize, winRate, avgWin, avgLoss);
                    
                    return Math.Min(kellyContracts, volAdjustedContracts);
                }
                
                // Quality-based adjustments
                if (currentSignalQuality > 0.85 && currentWaveRatio > 2.0)
                    return Math.Min(volAdjustedContracts * 2, 5);
                else if (currentSignalQuality > 0.70 && currentWaveRatio > 1.5)
                    return Math.Min(volAdjustedContracts, 3);
                else if (currentSignalQuality > 0.60)
                    return Math.Min(volAdjustedContracts, 2);
                else
                    return 1;
            }
            catch (Exception ex)
            {
                Log($"Error calculating position size: {ex.Message}", LogLevel.Warning);
                return 1;
            }
        }
        
        private void CheckForNewSession()
        {
            if (useSessionReset && (sessionStart.Date != Time[0].Date || sessionStart == DateTime.MinValue))
            {
                isNewSession = true;
                sessionStart = Time[0];
                cumulativeVolume = 0;
                cumulativeTypicalPriceVolume = 0;
                cumulativeSquaredPriceVolume = 0;
            }
            else
            {
                isNewSession = false;
            }
        }

        private void CalculateVWAP()
        {
            double typicalPrice = (High[0] + Low[0] + Close[0]) / 3;
            double volume = Volume[0];
            
            cumulativeVolume += volume;
            cumulativeTypicalPriceVolume += typicalPrice * volume;
            cumulativeSquaredPriceVolume += typicalPrice * typicalPrice * volume;

            if (cumulativeVolume.ApproxCompare(0) != 0)
            {
                currentVWAP = cumulativeTypicalPriceVolume / cumulativeVolume;
                double variance = (cumulativeSquaredPriceVolume / cumulativeVolume) - (currentVWAP * currentVWAP);
                double deviation = Math.Sqrt(variance);

                vwapValue[0] = currentVWAP;
                vwapDeviation1[0] = currentVWAP + deviationMultiplier1 * deviation;
                vwapDeviation2[0] = currentVWAP + deviationMultiplier2 * deviation;
                
                vwapDistance = (Close[0] - currentVWAP) / atr[0];

                if (Math.Abs(vwapDistance) < proximityThreshold)
                    vwapPosition = "NEAR";
                else if (vwapDistance > 0)
                    vwapPosition = "ABOVE";
                else
                    vwapPosition = "BELOW";
            }
        }

        private double GetTickValueForMarket(string market)
        {
            switch (market)
            {
                case "Gold": return 10.0;
                case "ES": return 12.50;
                case "NQ": return 5.0;
                case "CL": return 10.0;
                case "BTC": return 5.0;
                default: return 10.0;
            }
        }
        
        private void ConfigureForMarket()
        {
            // Use enhanced calculation utilities for market-specific parameters
            switch (assetType)
            {
                case "Gold":
                    maxLength = 20;
                    accelMultiplier = FKS_Calculations.CalculateATRMultiplier("Gold", 0.015);
                    lookbackPeriod = 200;
                    signalSensitivity = 0.5;
                    break;
                    
                case "ES":
                case "NQ":
                    maxLength = 20;
                    accelMultiplier = FKS_Calculations.CalculateATRMultiplier("ES", 0.01);
                    lookbackPeriod = 150;
                    signalSensitivity = 0.6;
                    break;
                    
                case "CL":
                    maxLength = 20;
                    accelMultiplier = FKS_Calculations.CalculateATRMultiplier("CL", 0.02);
                    lookbackPeriod = 150;
                    signalSensitivity = 0.4;
                    break;
                    
                case "BTC":
                    maxLength = 20;
                    accelMultiplier = FKS_Calculations.CalculateATRMultiplier("BTC", 0.03);
                    lookbackPeriod = 100;
                    signalSensitivity = 0.3;
                    break;
            }
        }
        #endregion
        
        #region Properties
        // Public properties for external access
        public string SignalType => currentSignalType;
        public double SignalQuality => currentSignalQuality;
        public double CurrentWaveRatio => currentWaveRatio;
        public string MarketRegime => currentMarketRegime;
        public string MarketPhase => marketPhase;
        public double NearestSupport => nearestSupport;
        public double NearestResistance => nearestResistance;
        public double TrendSpeed => trendSpeed[0];
        
        // VWAP Access Method
        public double GetVWAP()
        {
            return currentVWAP;
        }
        
        // VWAP Deviation Access Method
        private double GetVWAPDeviation()
        {
            if (cumulativeVolume == 0) return 0;
            
            double variance = (cumulativeSquaredPriceVolume / cumulativeVolume) - (currentVWAP * currentVWAP);
            return Math.Sqrt(Math.Max(0, variance));
        }
        
        // User configurable properties
        [NinjaScriptProperty]
        [Display(Name = "Asset Type", Order = 1, GroupName = "Parameters")]
        public string AssetType
        {
            get { return assetType; }
            set { assetType = value; }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "Show S/R Bands", Order = 10, GroupName = "Visual")]
        public bool ShowSRBands { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Signal Labels", Order = 11, GroupName = "Visual")]
        public bool ShowSignalLabels { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Entry Zones", Order = 12, GroupName = "Visual")]
        public bool ShowEntryZones { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Wave Info", Order = 13, GroupName = "Visual")]
        public bool ShowWaveInfo { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Market Phase", Order = 14, GroupName = "Visual")]
        public bool ShowMarketPhase { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Clean Chart Mode", Order = 15, GroupName = "Visual")]
        public bool CleanChartMode { get; set; }
        
        [XmlIgnore]
        [Display(Name = "Resistance Color", Order = 20, GroupName = "Colors")]
        public Brush ResistanceColor { get; set; }
        
        [XmlIgnore]
        [Display(Name = "Support Color", Order = 21, GroupName = "Colors")]
        public Brush SupportColor { get; set; }
        
        [XmlIgnore]
        [Display(Name = "Middle Color", Order = 22, GroupName = "Colors")]
        public Brush MiddleColor { get; set; }
        
        [XmlIgnore]
        [Display(Name = "Signal Label Color", Order = 23, GroupName = "Colors")]
        public Brush SignalLabelColor { get; set; }
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
            // Component initialization
            Log("FKS_AI initialized", LogLevel.Information);
        }
        
        public void Shutdown()
        {
            // Component cleanup
            FKS_Core.UnregisterComponent(ComponentId);
        }
        #endregion
        
        #region Public Methods for FKS_Info Integration
        public FKS_Core.ComponentSignal GetSignal()
        {
            return new FKS_Core.ComponentSignal
            {
                SignalType = "AI_Signal",
                Quality = 0.75, // Default quality
                Timestamp = DateTime.Now,
                Data = new Dictionary<string, object>
                {
                    ["AssetType"] = assetType,
                    ["MaxLength"] = maxLength,
                    ["AccelMultiplier"] = accelMultiplier,
                    ["LookbackPeriod"] = lookbackPeriod
                }
            };
        }
        #endregion
        
        #region User Properties
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
                
                Log($"FKS_AI registered successfully with infrastructure", LogLevel.Information);
            }
            catch (Exception ex)
            {
                Log($"Failed to register FKS_AI with infrastructure: {ex.Message}", LogLevel.Warning);
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
                    Log($"FKS_AI unregistered from infrastructure", LogLevel.Information);
                }
            }
            catch (Exception ex)
            {
                Log($"Error unregistering FKS_AI: {ex.Message}", LogLevel.Warning);
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
        #endregion
        
        #region Enhanced Integration with New FKS_Calculations

        /// <summary>
        /// Use enhanced ML position sizing from FKS_Calculations
        /// </summary>
        private int CalculateEnhancedPositionSize(double accountSize, double riskPercent, double stopDistance, double tickValue)
        {
            try
            {
                // Create market condition context
                var marketContext = FKS_Calculations.AnalyzeCurrentMarketCondition(
                    Close[0], 
                    EMA(9)[0], 
                    SMA(Close, 20)[0], 
                    atr[0], 
                    Volume[0], 
                    SMA(Volume, 20)[0],
                    GetPriceHistory(20),
                    GetVolumeHistory(20)
                );

                // Use ML-enhanced position sizing
                int mlEnhancedSize = FKS_Calculations.CalculateMLEnhancedPositionSize(
                    accountSize,
                    riskPercent,
                    stopDistance,
                    tickValue,
                    marketContext
                );

                LogDebug("AI", $"ML Enhanced Position Size: {mlEnhancedSize} (Context: {marketContext.MarketRegime})", "INFO");
                return mlEnhancedSize;
            }
            catch (Exception ex)
            {
                LogDebug("AI", $"Error in ML position sizing: {ex.Message}", "ERROR");
                return FKS_Calculations.CalculateOptimalContracts(accountSize, riskPercent, stopDistance, tickValue);
            }
        }

        /// <summary>
        /// Use enhanced signal analysis from FKS_Calculations
        /// </summary>
        private void AnalyzeSignalWithEnhancedProcessing()
        {
            try
            {
                if (string.IsNullOrEmpty(currentSignalType)) return;

                // Prepare signal analysis data
                var priceData = GetPriceHistory(20);
                var volumeData = GetVolumeHistory(20);
                var indicatorData = new double[] { dynamicEMA[0], trendSpeed[0], currentWaveRatio };

                // Use advanced signal processing
                var signalAnalysis = FKS_Calculations.AnalyzeSignalQuality(
                    priceData,
                    volumeData,
                    indicatorData,
                    currentSignalType,
                    20
                );

                // Update signal quality with enhanced metrics
                currentSignalQuality = signalAnalysis.QualityScore;

                // Log enhanced signal analysis
                LogDebug("SIGNAL", $"Enhanced Signal Analysis - Quality: {signalAnalysis.QualityScore:F2}, " +
                    $"Strength: {signalAnalysis.SignalStrength:F2}, Risk: {signalAnalysis.RiskLevel}", "INFO");

                // Update FKS_Core with enhanced signal data
                try
                {
                    var enhancedSignal = new FKS_Core.FKSSignal
                    {
                        Type = currentSignalType,
                        Quality = signalAnalysis.QualityScore,
                        Source = ComponentId,
                        WaveRatio = currentWaveRatio,
                        Timestamp = DateTime.Now,
                        Confidence = signalAnalysis.SignalStrength,
                        MarketRegime = currentMarketRegime,
                        RiskRewardRatio = CalculateRiskRewardRatio()
                    };

                    FKS_Core.PublishSignal(enhancedSignal);
                    
                    LogDebug("AI", $"Published enhanced signal to FKS_Core: {currentSignalType} " +
                        $"(Quality: {signalAnalysis.QualityScore:F2}, Risk: {signalAnalysis.RiskLevel})", "INFO");
                }
                catch (Exception coreEx)
                {
                    LogDebug("AI", $"Error updating FKS_Core: {coreEx.Message}", "WARN");
                }
            }
            catch (Exception ex)
            {
                LogDebug("AI", $"Error in enhanced signal analysis: {ex.Message}", "ERROR");
            }
        }

        /// <summary>
        /// Use enhanced ATR calculation with circuit breaker protection
        /// </summary>
        private double CalculateEnhancedATR()
        {
            try
            {
                // Use circuit breaker protected ATR calculation
                return FKS_Calculations.ExecuteWithCircuitBreaker("volatility_calculation", () =>
                {
                    var atrArray = new double[14];
                    var returnsArray = new double[14];
                    
                    for (int i = 0; i < 14 && i < CurrentBar; i++)
                    {
                        atrArray[i] = atr[i];
                        if (i < 13)
                        {
                            returnsArray[i] = Close[i] != 0 ? (Close[i] - Close[i + 1]) / Close[i + 1] : 0;
                        }
                    }

                    return FKS_Calculations.CalculateVolatilityAdjustedATR(atrArray, returnsArray);
                }, atr[0]);
            }
            catch (Exception ex)
            {
                LogDebug("AI", $"Error in enhanced ATR calculation: {ex.Message}", "ERROR");
                return atr[0];
            }
        }

        /// <summary>
        /// Get system health report for monitoring
        /// </summary>
        private void CheckSystemHealth()
        {
            try
            {
                if (CurrentBar % 100 == 0) // Check every 100 bars
                {
                    var healthReport = FKS_Calculations.GetSystemHealthReport();
                    
                    if (healthReport.OverallHealth == "POOR" || healthReport.OverallHealth == "CRITICAL")
                    {
                        LogDebug("AI", $"System Health Warning: {healthReport.OverallHealth}", "WARN");
                        
                        if (healthReport.Recommendations.Count > 0)
                        {
                            LogDebug("AI", $"Recommendations: {string.Join(", ", healthReport.Recommendations)}", "INFO");
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogDebug("AI", $"Error checking system health: {ex.Message}", "ERROR");
            }
        }

        /// <summary>
        /// Get price history for analysis
        /// </summary>
        private double[] GetPriceHistory(int periods)
        {
            var history = new double[Math.Min(periods, CurrentBar + 1)];
            for (int i = 0; i < history.Length; i++)
            {
                history[i] = Close[i];
            }
            return history;
        }

        /// <summary>
        /// Get volume history for analysis
        /// </summary>
        private double[] GetVolumeHistory(int periods)
        {
            var history = new double[Math.Min(periods, CurrentBar + 1)];
            for (int i = 0; i < history.Length; i++)
            {
                history[i] = Volume[i];
            }
            return history;
        }

        /// <summary>
        /// Use enhanced adaptive ATR multiplier
        /// </summary>
        private double GetAdaptiveATRMultiplier()
        {
            try
            {
                var currentVol = CalculateEnhancedATR();
                var avgVol = SMA(atr, 20)[0];
                var sessionType = GetCurrentSessionType();

                return FKS_Calculations.CalculateAdaptiveATRMultiplier(
                    assetType,
                    accelMultiplier,
                    currentVol,
                    avgVol,
                    currentMarketRegime,
                    sessionType
                );
            }
            catch (Exception ex)
            {
                LogDebug("AI", $"Error in adaptive ATR calculation: {ex.Message}", "ERROR");
                return accelMultiplier;
            }
        }

        /// <summary>
        /// Get current session type for enhanced calculations
        /// </summary>
        private string GetCurrentSessionType()
        {
            var now = DateTime.Now;
            var hour = now.Hour;

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
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private FKS.FKS_AI[] cacheFKS_AI;
		public FKS.FKS_AI FKS_AI(string assetType, bool showSRBands, bool showSignalLabels, bool showEntryZones, bool showWaveInfo, bool showMarketPhase, bool cleanChartMode)
		{
			return FKS_AI(Input, assetType, showSRBands, showSignalLabels, showEntryZones, showWaveInfo, showMarketPhase, cleanChartMode);
		}

		public FKS.FKS_AI FKS_AI(ISeries<double> input, string assetType, bool showSRBands, bool showSignalLabels, bool showEntryZones, bool showWaveInfo, bool showMarketPhase, bool cleanChartMode)
		{
			if (cacheFKS_AI != null)
				for (int idx = 0; idx < cacheFKS_AI.Length; idx++)
					if (cacheFKS_AI[idx] != null && cacheFKS_AI[idx].AssetType == assetType && cacheFKS_AI[idx].ShowSRBands == showSRBands && cacheFKS_AI[idx].ShowSignalLabels == showSignalLabels && cacheFKS_AI[idx].ShowEntryZones == showEntryZones && cacheFKS_AI[idx].ShowWaveInfo == showWaveInfo && cacheFKS_AI[idx].ShowMarketPhase == showMarketPhase && cacheFKS_AI[idx].CleanChartMode == cleanChartMode && cacheFKS_AI[idx].EqualsInput(input))
						return cacheFKS_AI[idx];
			return CacheIndicator<FKS.FKS_AI>(new FKS.FKS_AI(){ AssetType = assetType, ShowSRBands = showSRBands, ShowSignalLabels = showSignalLabels, ShowEntryZones = showEntryZones, ShowWaveInfo = showWaveInfo, ShowMarketPhase = showMarketPhase, CleanChartMode = cleanChartMode }, input, ref cacheFKS_AI);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.FKS.FKS_AI FKS_AI(string assetType, bool showSRBands, bool showSignalLabels, bool showEntryZones, bool showWaveInfo, bool showMarketPhase, bool cleanChartMode)
		{
			return indicator.FKS_AI(Input, assetType, showSRBands, showSignalLabels, showEntryZones, showWaveInfo, showMarketPhase, cleanChartMode);
		}

		public Indicators.FKS.FKS_AI FKS_AI(ISeries<double> input , string assetType, bool showSRBands, bool showSignalLabels, bool showEntryZones, bool showWaveInfo, bool showMarketPhase, bool cleanChartMode)
		{
			return indicator.FKS_AI(input, assetType, showSRBands, showSignalLabels, showEntryZones, showWaveInfo, showMarketPhase, cleanChartMode);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.FKS.FKS_AI FKS_AI(string assetType, bool showSRBands, bool showSignalLabels, bool showEntryZones, bool showWaveInfo, bool showMarketPhase, bool cleanChartMode)
		{
			return indicator.FKS_AI(Input, assetType, showSRBands, showSignalLabels, showEntryZones, showWaveInfo, showMarketPhase, cleanChartMode);
		}

		public Indicators.FKS.FKS_AI FKS_AI(ISeries<double> input , string assetType, bool showSRBands, bool showSignalLabels, bool showEntryZones, bool showWaveInfo, bool showMarketPhase, bool cleanChartMode)
		{
			return indicator.FKS_AI(input, assetType, showSRBands, showSignalLabels, showEntryZones, showWaveInfo, showMarketPhase, cleanChartMode);
		}
	}
}

#endregion
