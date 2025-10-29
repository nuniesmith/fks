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
    /// FKS Awesome Oscillator - Enhanced version with signal line and momentum confirmation
    /// Matches PineScript AOv2KIVANC implementation
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
                
                // Remove SMA initialization as we'll use direct calls
                
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
            if (CurrentBar < SLOW_PERIOD + SIGNAL_PERIOD) return;
            
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
            
            // Check for divergence - temporarily disabled
            // TODO: Resolve Draw class conflicts
            /*
            if (ShowDivergence)
                CheckDivergence();
            */
            
            // Update histogram colors
            UpdateColors();
            
            // Drawing and momentum update temporarily disabled
            // TODO: Resolve Draw class conflicts and unreachable code
        }
        #endregion
        
        #region Calculations
        private void DetectCrossovers()
        {
            currentCrossDirection = 0;
            
            // Zero line crossovers
            if (UseAOZeroCross)
            {
                if (aoValue[0] > 0 && aoValue[1] <= 0)
                {
                    currentCrossDirection = 1; // Bullish zero cross
                }
                else if (aoValue[0] < 0 && aoValue[1] >= 0)
                {
                    currentCrossDirection = -1; // Bearish zero cross
                }
            }
            
            // Signal line crossovers
            if (UseAOSignalCross)
            {
                if (aoValue[0] > signalLine[0] && aoValue[1] <= signalLine[1])
                {
                    if (currentCrossDirection == 0)
                        currentCrossDirection = 1; // Bullish signal cross
                }
                else if (aoValue[0] < signalLine[0] && aoValue[1] >= signalLine[1])
                {
                    if (currentCrossDirection == 0)
                        currentCrossDirection = -1; // Bearish signal cross
                }
            }
        }
        
        private void CalculateMomentumStrength()
        {
            // Calculate momentum based on AO acceleration
            double aoChange = aoValue[0] - aoValue[1];
            double aoAcceleration = CurrentBar > 2 ? (aoChange - (aoValue[1] - aoValue[2])) : 0;
            
            // Normalize momentum strength
            double avgRange = SMA(ATR(1), 20)[0]; // Simplified
            if (avgRange > 0)
            {
                momentumStrength = Math.Abs(aoValue[0]) / avgRange;
                momentumStrength = Math.Min(1.0, momentumStrength / 2); // Scale to 0-1
            }
            else
            {
                momentumStrength = 0.5;
            }
            
            // Check if accelerating
            isAccelerating = (aoValue[0] > 0 && aoChange > 0 && aoAcceleration > 0) ||
                           (aoValue[0] < 0 && aoChange < 0 && aoAcceleration < 0);
        }
        
        private void CheckDivergence()
        {
            if (CurrentBar < 50) return;
            
            isDiverging = false;
            
            // Look for price/AO divergence over last 20 bars
            int lookback = 20;
            
            // Find recent swing highs/lows
            double recentPriceHigh = MAX(High, lookback)[0];
            double recentPriceLow = MIN(Low, lookback)[0];
            double recentAOHigh = MAX(aoValue, lookback)[0];
            double recentAOLow = MIN(aoValue, lookback)[0];
            
            // Bullish divergence: price makes lower low, AO makes higher low
            if (Low[0] <= recentPriceLow * 1.001 && aoValue[0] > recentAOLow * 0.999 && aoValue[0] < 0)
            {
                isDiverging = true;
                // Drawing disabled: Draw.Text(this, "BullDiv" + CurrentBar, "↑", 0, aoValue[0] - 0.0001, divergenceColor);
            }
            
            // Bearish divergence: price makes higher high, AO makes lower high
            if (High[0] >= recentPriceHigh * 0.999 && aoValue[0] < recentAOHigh * 1.001 && aoValue[0] > 0)
            {
                isDiverging = true;
                // Drawing disabled: Draw.Text(this, "BearDiv" + CurrentBar, "↓", 0, aoValue[0] + 0.0001, divergenceColor);
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
        
        #region Public Methods for FKS_Dashboard Integration
        public FKS_Core.ComponentSignal GetSignal()
        {
            return new FKS_Core.ComponentSignal
            {
                SignalType = "AO_Signal",
                Quality = 0.80, // Default quality
                Timestamp = DateTime.Now,
                Data = new Dictionary<string, object>
                {
                    ["Value"] = Value,
                    ["Signal"] = Signal,
                    ["CrossDirection"] = CrossDirection,
                    ["MomentumStrength"] = MomentumStrength,
                    ["IsAccelerating"] = IsAccelerating,
                    ["IsBullish"] = IsBullish,
                    ["IsBearish"] = IsBearish
                }
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
        
        #region IFKSComponent Implementation
        public void Initialize()
        {
            Log("FKS_AO initialized", LogLevel.Information);
        }
        
        public void Shutdown()
        {
            FKS_Core.UnregisterComponent(ComponentId);
        }
        #endregion
    }
}

// End of file - NinjaScript generated code removed for clean build
