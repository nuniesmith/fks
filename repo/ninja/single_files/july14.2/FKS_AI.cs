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
#endregion

namespace NinjaTrader.NinjaScript.Indicators.FKS
{
    /// <summary>
    /// FKS AI Indicator - Port of PineScript FKS indicator
    /// Provides support/resistance detection, signal generation, and wave analysis
    /// </summary>
    public class FKS_AI : Indicator, FKS_Core.IFKSComponent
    {
        #region Variables
        // Component Interface
        public string ComponentId => "FKS_AI";
        public string Version => "1.0.0";
        
        // Core Parameters (matching PineScript)
        private string assetType = "Gold";
        private int maxLength = 20;
        private double accelMultiplier = 0.02;
        private int lookbackPeriod = 200;
        private double minWaveRatio = 1.5;
        private double exitMomentumThreshold = 0.7;
        
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
                
                // Add plots for data series
                AddPlot(new Stroke(Brushes.Red, 2), PlotStyle.Line, "Resistance");
                AddPlot(new Stroke(Brushes.Blue, 1), PlotStyle.Line, "Middle");
                AddPlot(new Stroke(Brushes.Green, 2), PlotStyle.Line, "Support");
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
                
                // Initialize indicators
                atr = ATR(14);
                volume = VOL();
                
                // Initialize colors
                upHistColor = Brushes.LimeGreen;
                upHistColorBright = Brushes.Lime;
                dnHistColor = Brushes.Red;
                dnHistColorBright = Brushes.OrangeRed;
                
                // Register with FKS Core
                try
                {
                    FKS_Core.RegisterComponent(ComponentId, this);
                }
                catch (Exception ex)
                {
                    Log($"Failed to register with FKS Core: {ex.Message}", LogLevel.Warning);
                }
            }
        }
        #endregion
        
        #region OnBarUpdate
        protected override void OnBarUpdate()
        {
            if (CurrentBar < Math.Max(srLength, lookbackPeriod)) return;
            
            // Calculate Support/Resistance
            CalculateSupportResistance();
            
            // Calculate Dynamic EMA (Trend Speed)
            CalculateDynamicEMA();
            
            // Detect signals
            DetectSignals();
            
            // Calculate signal quality
            CalculateSignalQuality();
            
            // Update market phase
            UpdateMarketPhase();
            
            // Draw visualizations - temporarily disabled due to type conflicts
            // TODO: Resolve Draw class conflicts
            /*
            if (!CleanChartMode)
            {
                DrawSignals();
                DrawEntryZones();
            }
            */
            
            // Update FKS Core with current state
            UpdateCoreState();
            
            // Set plot values
            Values[0][0] = highestSrc[0]; // Resistance
            Values[1][0] = midSrc[0];     // Middle
            Values[2][0] = lowestSrc[0];  // Support
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
            }
            else if (High[0] < highestSrc[0] && High[1] >= highestSrc[1] && 
                     rocNormalized > 2 * signalSensitivity && 
                     CurrentBar - lastCrossBar > 5)
            {
                currentSignalType = "Top";
                lastCrossBar = CurrentBar;
            }
            else if (Low[0] > lowestSrc[0] && Low[1] <= lowestSrc[1])
            {
                currentSignalType = "^";
            }
            else if (High[0] < highestSrc[0] && High[1] >= highestSrc[1])
            {
                currentSignalType = "v";
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
                    LastUpdate = DateTime.Now
                };
                
                FKS_Core.UpdateMarketState(marketState);
            }
            
            // Publish signals to core
            if (!string.IsNullOrEmpty(currentSignalType) && currentSignalQuality >= signalQualityThreshold)
            {
                var signal = new FKS_Core.FKSSignal
                {
                    Type = currentSignalType,
                    Quality = currentSignalQuality,
                    WaveRatio = currentWaveRatio,
                    SetupNumber = DetermineSetupNumber(),
                    RecommendedContracts = CalculateRecommendedContracts()
                };
                
                FKS_Core.PublishSignal(signal);
            }
        }
        
        private int DetermineSetupNumber()
        {
            // Simple setup determination based on current conditions
            bool priceAboveEMA = Close[0] > EMA(9)[0];
            bool emaAboveSMA = EMA(9)[0] > SMA(Close, 20)[0]; // VWAP proxy
            
            if ((currentSignalType == "G" || currentSignalType == "^") && priceAboveEMA && emaAboveSMA)
                return 1; // Bullish breakout
            else if ((currentSignalType == "Top" || currentSignalType == "v") && !priceAboveEMA && !emaAboveSMA)
                return 2; // Bearish breakdown
            else if (Math.Abs(Close[0] - SMA(Close, 20)[0]) / atr[0] < 0.5)
                return 3; // VWAP bounce
            else if (Math.Abs(Close[0] - nearestSupport) / atr[0] < 0.5 || 
                     Math.Abs(Close[0] - nearestResistance) / atr[0] < 0.5)
                return 4; // S/R setup
            
            return 0;
        }
        
        private int CalculateRecommendedContracts()
        {
            // Use shared calculation logic with market-specific defaults
            // Account access disabled for now - return default
            double accountSize = 100000; // Default account size
            double riskPercent = 1.0; // 1% risk per trade
            double stopDistance = atr[0] * 2.0; // 2 ATR stop
            double tickValue = FKS_Core.CurrentMarketConfig?.TickValue ?? 10.0;
            
            int baseContracts = FKS_Calculations.CalculateOptimalContracts(accountSize, riskPercent, stopDistance, tickValue);
            
            // Adjust based on signal quality
            if (currentSignalQuality > 0.85 && currentWaveRatio > 2.0)
                return Math.Min(baseContracts * 2, 5);
            else if (currentSignalQuality > 0.70 && currentWaveRatio > 1.5)
                return Math.Min(baseContracts, 3);
            else if (currentSignalQuality > 0.60)
                return Math.Min(baseContracts, 2);
            else
                return 1;
        }
        
        private void ConfigureForMarket()
        {
            // Use shared calculation utilities for market-specific parameters
            switch (assetType)
            {
                case "Gold":
                    maxLength = 20;
                    accelMultiplier = FKS_Calculations.CalculateATRMultiplier("Gold", 0.015);
                    lookbackPeriod = 200;
                    break;
                    
                case "ES":
                case "NQ":
                    maxLength = 20;
                    accelMultiplier = FKS_Calculations.CalculateATRMultiplier("ES", 0.01);
                    lookbackPeriod = 150;
                    break;
                    
                case "CL":
                    maxLength = 20;
                    accelMultiplier = FKS_Calculations.CalculateATRMultiplier("CL", 0.02);
                    lookbackPeriod = 150;
                    break;
                    
                case "BTC":
                    maxLength = 20;
                    accelMultiplier = FKS_Calculations.CalculateATRMultiplier("BTC", 0.03);
                    lookbackPeriod = 100;
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
        
        #region Public Methods for FKS_Dashboard Integration
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
    }
}
