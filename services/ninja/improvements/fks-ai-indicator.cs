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
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.FKS
{
    /// <summary>
    /// FKS AI Indicator - Port of PineScript FKS indicator
    /// Provides support/resistance detection, signal generation, and wave analysis
    /// </summary>
    public class FKS_AI : Indicator, FKSCore.IFKSComponent
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
        private EMA ema9;
        private SMA sma200;
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
                ema9 = EMA(9);
                sma200 = SMA(200);
                volume = VOL();
                
                // Initialize colors
                upHistColor = Brushes.LimeGreen;
                upHistColorBright = Brushes.Lime;
                dnHistColor = Brushes.Red;
                dnHistColorBright = Brushes.OrangeRed;
                
                // Register with FKS Core
                try
                {
                    FKSCore.RegisterComponent(ComponentId, this);
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
            
            // Draw visualizations
            if (!CleanChartMode)
            {
                DrawSignals();
                DrawEntryZones();
            }
            
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
            double maxAbsCountsDiff = MAX(High - Low, 200)[0];
            double countsDiffNorm = maxAbsCountsDiff > 0 ? 
                (countsDiff + maxAbsCountsDiff) / (2 * maxAbsCountsDiff) : 0.5;
            
            double dynLength = 5 + countsDiffNorm * (maxLength - 5);
            
            // Calculate accelerator factor
            double deltaCountsDiff = Math.Abs(countsDiff - (CurrentBar > 0 ? Close[1] : countsDiff));
            double maxDeltaCountsDiff = MAX(Series<double>(deltaCountsDiff), 200)[0];
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
            
            trendSpeed[0] = SMA(Series<double>(speed), 5)[0];
            
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
            currentSignalType = "";
            
            // ROC calculation for signal detection
            double roc = CurrentBar >= 2 ? (Close[0] - Close[2]) / Close[2] * 100 : 0;
            double rocNormalized = roc / (atr[0] / Close[0] * 100);
            
            // G Signal (Bottom - Strong)
            if (Low[0] > lowestSrc[0] && Low[1] <= lowestSrc[1] && 
                rocNormalized < -2 * signalSensitivity && 
                CurrentBar - lastCrossBar > 5)
            {
                currentSignalType = "G";
            }
            // Top Signal (Top - Strong)
            else if (High[0] < highestSrc[0] && High[1] >= highestSrc[1] && 
                     rocNormalized > 2 * signalSensitivity && 
                     CurrentBar - lastCrossBar > 5)
            {
                currentSignalType = "Top";
            }
            // ^ Signal (Bottom - Weak)
            else if (Low[0] > lowestSrc[0] && Low[1] <= lowestSrc[1])
            {
                currentSignalType = "^";
            }
            // v Signal (Top - Weak)
            else if (High[0] < highestSrc[0] && High[1] >= highestSrc[1])
            {
                currentSignalType = "v";
            }
        }
        
        private void CalculateSignalQuality()
        {
            if (string.IsNullOrEmpty(currentSignalType))
            {
                currentSignalQuality = 0;
                return;
            }
            
            double quality = 0;
            
            // Base quality from signal type
            if (currentSignalType == "G" || currentSignalType == "Top")
                quality += 0.3;
            else
                quality += 0.2;
            
            // Wave ratio factor
            if (currentWaveRatio > 2.0)
                quality += 0.2;
            else if (currentWaveRatio > 1.5)
                quality += 0.15;
            else if (currentWaveRatio > 1.0)
                quality += 0.1;
            
            // Trend alignment
            bool trendAligned = (position > 0 && (currentSignalType == "G" || currentSignalType == "^")) ||
                               (position < 0 && (currentSignalType == "Top" || currentSignalType == "v"));
            if (trendAligned)
                quality += 0.2;
            
            // Volume confirmation
            if (Volume[0] > SMA(Volume, 20)[0] * 1.2)
                quality += 0.1;
            
            // Volatility factor
            double volPercentile = atr[0] / SMA(atr, 200)[0];
            if (volPercentile > 0.5 && volPercentile < 1.5)
                quality += 0.1;
            
            // Market phase bonus
            if ((marketPhase == "UPTREND" && position > 0) ||
                (marketPhase == "DOWNTREND" && position < 0))
                quality += 0.1;
            
            currentSignalQuality = Math.Min(1.0, quality);
        }
        
        private void UpdateMarketPhase()
        {
            // Determine market phase based on price action
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
            
            // Determine market regime
            double maSlope = (sma200[0] - sma200[20]) / 20;
            double normalizedSlope = maSlope / atr[0];
            
            if (Math.Abs(normalizedSlope) > 1.0)
            {
                currentMarketRegime = normalizedSlope > 0 ? "TRENDING BULL" : "TRENDING BEAR";
            }
            else
            {
                double volRatio = atr[0] / SMA(atr, 100)[0];
                if (volRatio > 1.5)
                    currentMarketRegime = "VOLATILE";
                else if (volRatio < 0.8)
                    currentMarketRegime = "RANGING";
                else
                    currentMarketRegime = "NEUTRAL";
            }
        }
        
        private void FindNearestLevels()
        {
            // Simple nearest S/R calculation
            nearestSupport = lowestSrc[0];
            nearestResistance = highestSrc[0];
            
            // Look for intermediate levels
            double currentPrice = Close[0];
            double range = highestSrc[0] - lowestSrc[0];
            
            // Check quarter levels
            double[] levels = new double[]
            {
                lowestSrc[0],
                lowestSrc[0] + range * 0.25,
                lowestSrc[0] + range * 0.5,
                lowestSrc[0] + range * 0.75,
                highestSrc[0]
            };
            
            // Find nearest support below price
            for (int i = levels.Length - 1; i >= 0; i--)
            {
                if (levels[i] < currentPrice)
                {
                    nearestSupport = levels[i];
                    break;
                }
            }
            
            // Find nearest resistance above price
            for (int i = 0; i < levels.Length; i++)
            {
                if (levels[i] > currentPrice)
                {
                    nearestResistance = levels[i];
                    break;
                }
            }
        }
        #endregion
        
        #region Drawing
        private void DrawSignals()
        {
            if (!ShowSignalLabels || string.IsNullOrEmpty(currentSignalType)) return;
            
            string labelText = currentSignalType;
            double yOffset = atr[0] * 0.5;
            
            switch (currentSignalType)
            {
                case "G":
                    Draw.Text(this, "G" + CurrentBar, true, labelText, 0, Low[0] - yOffset, 
                        0, SignalLabelColor, new SimpleFont("Arial", 12), 
                        TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                    
                    Draw.ArrowUp(this, "GArrow" + CurrentBar, true, 0, Low[0] - yOffset * 1.5, 
                        Brushes.LimeGreen);
                    break;
                    
                case "Top":
                    Draw.Text(this, "Top" + CurrentBar, true, labelText, 0, High[0] + yOffset, 
                        0, SignalLabelColor, new SimpleFont("Arial", 12), 
                        TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                    
                    Draw.ArrowDown(this, "TopArrow" + CurrentBar, true, 0, High[0] + yOffset * 1.5, 
                        Brushes.Red);
                    break;
                    
                case "^":
                    Draw.Text(this, "Up" + CurrentBar, true, labelText, 0, Low[0] - yOffset, 
                        0, SignalLabelColor, new SimpleFont("Arial", 10), 
                        TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                    break;
                    
                case "v":
                    Draw.Text(this, "Down" + CurrentBar, true, labelText, 0, High[0] + yOffset, 
                        0, SignalLabelColor, new SimpleFont("Arial", 10), 
                        TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                    break;
            }
            
            // Add quality indicator
            if (currentSignalQuality >= signalQualityThreshold)
            {
                string qualityText = $"{currentSignalQuality:P0}";
                Draw.Text(this, "Q" + CurrentBar, true, qualityText, 0, 
                    currentSignalType == "G" || currentSignalType == "^" ? Low[0] - yOffset * 2 : High[0] + yOffset * 2,
                    0, currentSignalQuality > 0.8 ? Brushes.Gold : Brushes.White, 
                    new SimpleFont("Arial", 8), TextAlignment.Center, 
                    Brushes.Transparent, Brushes.Transparent, 0);
            }
        }
        
        private void DrawEntryZones()
        {
            if (!ShowEntryZones || CurrentBar < 20) return;
            
            double range = highestSrc[0] - lowestSrc[0];
            double zoneSize = range * 0.1;
            
            // Support zone
            Draw.Rectangle(this, "SupportZone", false, 20, lowestSrc[0], -1, lowestSrc[0] + zoneSize,
                Brushes.Green, Brushes.Green, 20);
            
            // Resistance zone
            Draw.Rectangle(this, "ResistanceZone", false, 20, highestSrc[0] - zoneSize, -1, highestSrc[0],
                Brushes.Red, Brushes.Red, 20);
        }
        #endregion
        
        #region Integration
        private void UpdateCoreState()
        {
            // Update FKS Core with current market state
            if (CurrentBar % 5 == 0) // Update every 5 bars for performance
            {
                var marketState = new FKSCore.MarketState
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
                
                FKSCore.UpdateMarketState(marketState);
            }
            
            // Publish signals to core
            if (!string.IsNullOrEmpty(currentSignalType) && currentSignalQuality >= signalQualityThreshold)
            {
                var signal = new FKSCore.FKSSignal
                {
                    Type = currentSignalType,
                    Quality = currentSignalQuality,
                    WaveRatio = currentWaveRatio,
                    SetupNumber = DetermineSetupNumber(),
                    RecommendedContracts = CalculateRecommendedContracts()
                };
                
                FKSCore.PublishSignal(signal);
            }
        }
        
        private int DetermineSetupNumber()
        {
            // Simple setup determination based on current conditions
            bool priceAboveEMA = Close[0] > ema9[0];
            bool emaAboveSMA = ema9[0] > SMA(Close, 20)[0]; // VWAP proxy
            
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
            if (currentSignalQuality > 0.85 && currentWaveRatio > 2.0)
                return 5;
            else if (currentSignalQuality > 0.70 && currentWaveRatio > 1.5)
                return 3;
            else if (currentSignalQuality > 0.60)
                return 2;
            else
                return 1;
        }
        
        private void ConfigureForMarket()
        {
            // Market-specific parameter overrides
            switch (assetType)
            {
                case "Gold":
                    maxLength = 20;
                    accelMultiplier = 0.015;
                    lookbackPeriod = 200;
                    break;
                    
                case "ES":
                case "NQ":
                    maxLength = 20;
                    accelMultiplier = 0.01;
                    lookbackPeriod = 150;
                    break;
                    
                case "CL":
                    maxLength = 20;
                    accelMultiplier = 0.02;
                    lookbackPeriod = 150;
                    break;
                    
                case "BTC":
                    maxLength = 20;
                    accelMultiplier = 0.03;
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
            FKSCore.UnregisterComponent(ComponentId);
        }
        #endregion
    }
}