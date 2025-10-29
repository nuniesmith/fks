#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class FKS_VWAP : Indicator
    {
        #region Variables
        // VWAP calculation
        private double cumulativeVolumePrice;
        private double cumulativeVolume;
        private DateTime sessionStart;
        
        // Standard deviation bands
        private double sumSquaredDiff;
        private List<double> vwapValues = new List<double>();
        private double stdDev1Upper, stdDev1Lower;
        private double stdDev2Upper, stdDev2Lower;
        
        // Level 2 simulation
        private double bidVolume, askVolume;
        private double bidAskRatio = 1.0;
        private double deltaVolume = 0;
        private double cumulativeDelta = 0;
        
        // Volume Profile
        private SortedDictionary<double, double> volumeProfile = new SortedDictionary<double, double>();
        private double poc = 0; // Point of Control
        private double vah = 0; // Value Area High
        private double val = 0; // Value Area Low
        
        // Crossover tracking
        private CrossoverState ema9CrossState = CrossoverState.None;
        private int barsSinceCrossover = 0;
        
        // Performance metrics
        private int touchCount = 0;
        private int bounceCount = 0;
        private double vwapEfficiency = 0;
        
        // Indicators
        private EMA ema9;
        private ATR atr;
        private VOL volume;
        private SMA volumeAvg;
        
        // Settings
        private bool showStdDevBands = true;
        private bool showVolumeProfile = false;
        private bool showDeltaVolume = true;
        private bool debugMode = true;  // Enable debugging
        #endregion

        #region Enums
        public enum CrossoverState
        {
            None,
            BullishCrossover,
            BearishCrossover,
            AboveVWAP,
            BelowVWAP
        }
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Enhanced VWAP with advanced features";
                Name = "FKS_VWAP";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;
                DrawHorizontalGridLines = true;
                DrawVerticalGridLines = true;
                PaintPriceMarkers = true;
                ScaleJustification = NinjaTrader.Gui.Chart.ScaleJustification.Right;
                IsSuspendedWhileInactive = true;
                BarsRequiredToPlot = 1;
                
                // Plots
                AddPlot(new Stroke(Brushes.Magenta, 2), PlotStyle.Line, "VWAP");
                AddPlot(new Stroke(Brushes.Blue, 1), PlotStyle.Line, "EMA9");
                AddPlot(new Stroke(Brushes.Gray, DashStyleHelper.Dot, 1), PlotStyle.Line, "StdDev1Upper");
                AddPlot(new Stroke(Brushes.Gray, DashStyleHelper.Dot, 1), PlotStyle.Line, "StdDev1Lower");
                AddPlot(new Stroke(Brushes.DarkGray, DashStyleHelper.Dot, 1), PlotStyle.Line, "StdDev2Upper");
                AddPlot(new Stroke(Brushes.DarkGray, DashStyleHelper.Dot, 1), PlotStyle.Line, "StdDev2Lower");
                
                // Parameters
                ShowStdDevBands = true;
                ShowVolumeProfile = false;
                ShowDeltaVolume = true;
                StdDev1Multiplier = 1.0;
                StdDev2Multiplier = 2.0;
                ResetOnNewSession = true;
            }
            else if (State == State.Configure)
            {
                // Request tick data for better volume analysis
                if (Calculate != Calculate.OnEachTick)
                    Calculate = Calculate.OnEachTick;
            }
            else if (State == State.DataLoaded)
            {
                ema9 = EMA(Close, 9);
                atr = ATR(14);
                volume = VOL();
                volumeAvg = SMA(volume, 20);
                
                sessionStart = Time[0].Date;
                ResetSession();
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1) return;
            
            // Check for new session
            if (ResetOnNewSession && Bars.IsFirstBarOfSession)
            {
                ResetSession();
            }
            
            // Calculate VWAP
            CalculateVWAP();
            
            // Calculate standard deviation bands
            if (showStdDevBands)
                CalculateStdDevBands();
            
            // Update volume profile
            UpdateVolumeProfile();
            
            // Track crossovers
            TrackCrossovers();
            
            // Calculate performance metrics
            CalculateMetrics();
            
            // Set plot values
            Values[0][0] = GetVWAP();
            Values[1][0] = ema9[0];
            
            if (showStdDevBands && CurrentBar > 20)
            {
                Values[2][0] = stdDev1Upper;
                Values[3][0] = stdDev1Lower;
                Values[4][0] = stdDev2Upper;
                Values[5][0] = stdDev2Lower;
            }
        }

        protected override void OnMarketData(MarketDataEventArgs marketDataUpdate)
        {
            if (marketDataUpdate.MarketDataType == MarketDataType.Last)
            {
                // Simulate bid/ask volume based on price movement
                double priceMove = marketDataUpdate.Price - Close[0];
                
                if (priceMove > 0)
                {
                    // Uptick - likely at ask
                    askVolume += marketDataUpdate.Volume;
                    deltaVolume += marketDataUpdate.Volume;
                }
                else if (priceMove < 0)
                {
                    // Downtick - likely at bid
                    bidVolume += marketDataUpdate.Volume;
                    deltaVolume -= marketDataUpdate.Volume;
                }
                else
                {
                    // No change - split volume
                    askVolume += marketDataUpdate.Volume / 2;
                    bidVolume += marketDataUpdate.Volume / 2;
                }
                
                // Update cumulative delta
                cumulativeDelta = askVolume - bidVolume;
                
                // Calculate bid/ask ratio
                if (bidVolume > 0)
                    bidAskRatio = askVolume / bidVolume;
            }
        }

        #region Calculations
        
        private void CalculateVWAP()
        {
            double typicalPrice = (High[0] + Low[0] + Close[0]) / 3.0;
            double volumePrice = typicalPrice * Volume[0];
            
            cumulativeVolumePrice += volumePrice;
            cumulativeVolume += Volume[0];
            
            // Store VWAP values for std dev calculation
            if (Bars.IsFirstBarOfSession)
                vwapValues.Clear();
                
            double vwap = cumulativeVolume > 0 ? cumulativeVolumePrice / cumulativeVolume : typicalPrice;
            vwapValues.Add(vwap);
            
            // Keep only current session values
            if (vwapValues.Count > Bars.BarsSinceNewTradingDay)
                vwapValues.RemoveAt(0);
        }
        
        private void CalculateStdDevBands()
        {
            if (vwapValues.Count < 2) return;
            
            double vwap = GetVWAP();
            double sumSquared = 0;
            int count = 0;
            
            // Calculate variance from all session VWAP touches
            for (int i = 0; i < Math.Min(CurrentBar, Bars.BarsSinceNewTradingDay); i++)
            {
                double typicalPrice = (High[i] + Low[i] + Close[i]) / 3.0;
                double diff = typicalPrice - vwap;
                sumSquared += diff * diff * Volume[i];
                count++;
            }
            
            if (count > 0 && cumulativeVolume > 0)
            {
                double variance = sumSquared / cumulativeVolume;
                double stdDev = Math.Sqrt(variance);
                
                stdDev1Upper = vwap + (stdDev * StdDev1Multiplier);
                stdDev1Lower = vwap - (stdDev * StdDev1Multiplier);
                stdDev2Upper = vwap + (stdDev * StdDev2Multiplier);
                stdDev2Lower = vwap - (stdDev * StdDev2Multiplier);
            }
        }
        
        private void UpdateVolumeProfile()
        {
            if (!showVolumeProfile) return;
            
            // Round price to nearest tick
            double price = Instrument.MasterInstrument.RoundToTickSize(Close[0]);
            
            if (volumeProfile.ContainsKey(price))
                volumeProfile[price] += Volume[0];
            else
                volumeProfile[price] = Volume[0];
            
            // Find POC (Point of Control)
            if (volumeProfile.Count > 0)
            {
                var maxVolume = volumeProfile.OrderByDescending(kvp => kvp.Value).First();
                poc = maxVolume.Key;
                
                // Calculate Value Area (70% of volume)
                double totalVolume = volumeProfile.Sum(kvp => kvp.Value);
                double targetVolume = totalVolume * 0.7;
                double accumulatedVolume = 0;
                
                var sortedProfile = volumeProfile.OrderBy(kvp => Math.Abs(kvp.Key - poc));
                
                foreach (var kvp in sortedProfile)
                {
                    accumulatedVolume += kvp.Value;
                    
                    if (kvp.Key > vah || vah == 0) vah = kvp.Key;
                    if (kvp.Key < val || val == 0) val = kvp.Key;
                    
                    if (accumulatedVolume >= targetVolume) break;
                }
            }
        }
        
        private void TrackCrossovers()
        {
            double currentEMA = ema9[0];
            double currentVWAP = GetVWAP();
            
            // Update bars since crossover
            barsSinceCrossover++;
            
            // Determine current state
            CrossoverState previousState = ema9CrossState;
            
            if (currentEMA > currentVWAP)
            {
                if (previousState == CrossoverState.BelowVWAP || previousState == CrossoverState.None)
                {
                    ema9CrossState = CrossoverState.BullishCrossover;
                    barsSinceCrossover = 0;
                    
                    if (debugMode)
                        Print($"Bullish Crossover at {Time[0]}: EMA9={currentEMA:F2} > VWAP={currentVWAP:F2}");
                }
                else
                {
                    ema9CrossState = CrossoverState.AboveVWAP;
                }
            }
            else if (currentEMA < currentVWAP)
            {
                if (previousState == CrossoverState.AboveVWAP || previousState == CrossoverState.None)
                {
                    ema9CrossState = CrossoverState.BearishCrossover;
                    barsSinceCrossover = 0;
                    
                    if (debugMode)
                        Print($"Bearish Crossover at {Time[0]}: EMA9={currentEMA:F2} < VWAP={currentVWAP:F2}");
                }
                else
                {
                    ema9CrossState = CrossoverState.BelowVWAP;
                }
            }
        }
        
        private void CalculateMetrics()
        {
            double vwap = GetVWAP();
            double distance = Math.Abs(Close[0] - vwap);
            double atrValue = atr[0];
            
            // Count VWAP touches (within 0.1 ATR)
            if (distance < atrValue * 0.1)
            {
                touchCount++;
                
                // Check if price bounces from VWAP
                if (CurrentBar > 1)
                {
                    bool bullishBounce = Low[1] <= vwap && Close[0] > vwap && Close[0] > Open[0];
                    bool bearishBounce = High[1] >= vwap && Close[0] < vwap && Close[0] < Open[0];
                    
                    if (bullishBounce || bearishBounce)
                        bounceCount++;
                }
            }
            
            // Calculate VWAP efficiency (how well price respects VWAP)
            if (touchCount > 0)
                vwapEfficiency = (double)bounceCount / touchCount;
        }
        
        private void ResetSession()
        {
            cumulativeVolumePrice = 0;
            cumulativeVolume = 0;
            sessionStart = Time[0].Date;
            vwapValues.Clear();
            volumeProfile.Clear();
            
            // Reset Level 2 data
            bidVolume = 0;
            askVolume = 0;
            deltaVolume = 0;
            cumulativeDelta = 0;
            bidAskRatio = 1.0;
            
            // Reset metrics
            touchCount = 0;
            bounceCount = 0;
            vwapEfficiency = 0;
            
            // Reset value area
            poc = 0;
            vah = 0;
            val = 0;
            
            if (debugMode)
                Print($"Session reset at {Time[0]}");
        }
        
        #endregion

        #region Public Methods
        
        public double GetVWAP()
        {
            if (cumulativeVolume <= 0)
            {
                if (debugMode)
                    Print($"Warning: No volume data for VWAP calculation, using Close price: {Close[0]:F2}");
                return Close[0];
            }
            
            double vwap = cumulativeVolumePrice / cumulativeVolume;
            
            if (debugMode && CurrentBar % 100 == 0)
                Print($"VWAP: {vwap:F2}, Volume: {cumulativeVolume:F0}, VP: {cumulativeVolumePrice:F2}");
                
            return vwap;
        }
        
        public double GetEMA9()
        {
            return ema9[0];
        }
        
        public CrossoverState GetCrossoverState()
        {
            return ema9CrossState;
        }
        
        public int GetBarsSinceCrossover()
        {
            return barsSinceCrossover;
        }
        
        public bool IsBullishCrossover()
        {
            return ema9CrossState == CrossoverState.BullishCrossover && barsSinceCrossover == 0;
        }
        
        public bool IsBearishCrossover()
        {
            return ema9CrossState == CrossoverState.BearishCrossover && barsSinceCrossover == 0;
        }
        
        public bool IsNearVWAP(double threshold = 0.1)
        {
            double distance = Math.Abs(Close[0] - GetVWAP());
            return distance < atr[0] * threshold;
        }
        
        public double GetDeltaVolume()
        {
            return deltaVolume;
        }
        
        public double GetCumulativeDelta()
        {
            return cumulativeDelta;
        }
        
        public double GetBidAskRatio()
        {
            return bidAskRatio;
        }
        
        public double GetPOC()
        {
            return poc;
        }
        
        public double GetValueAreaHigh()
        {
            return vah;
        }
        
        public double GetValueAreaLow()
        {
            return val;
        }
        
        public double GetVWAPEfficiency()
        {
            return vwapEfficiency;
        }
        
        public bool IsStrongBullishDelta()
        {
            return deltaVolume > volumeAvg[0] * 0.3 && bidAskRatio > 1.5;
        }
        
        public bool IsStrongBearishDelta()
        {
            return deltaVolume < -volumeAvg[0] * 0.3 && bidAskRatio < 0.67;
        }
        
        #endregion

        #region Properties
        
        [NinjaScriptProperty]
        [Display(Name = "Show StdDev Bands", Order = 1, GroupName = "Visual")]
        public bool ShowStdDevBands
        { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Volume Profile", Order = 2, GroupName = "Visual")]
        public bool ShowVolumeProfile
        { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Delta Volume", Order = 3, GroupName = "Visual")]
        public bool ShowDeltaVolume
        { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.1, 5)]
        [Display(Name = "StdDev 1 Multiplier", Order = 4, GroupName = "Parameters")]
        public double StdDev1Multiplier
        { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.1, 5)]
        [Display(Name = "StdDev 2 Multiplier", Order = 5, GroupName = "Parameters")]
        public double StdDev2Multiplier
        { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Reset On New Session", Order = 6, GroupName = "Parameters")]
        public bool ResetOnNewSession
        { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Debug Mode", Order = 7, GroupName = "Parameters")]
        public bool DebugMode
        {
            get { return debugMode; }
            set { debugMode = value; }
        }
        
        #endregion
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private FKS_VWAP[] cacheFKS_VWAP_Enhanced;
		public FKS_VWAP FKS_VWAP(bool showStdDevBands, bool showVolumeProfile, bool showDeltaVolume, double stdDev1Multiplier, double stdDev2Multiplier, bool resetOnNewSession, bool debugMode)
		{
			return FKS_VWAP(Input, showStdDevBands, showVolumeProfile, showDeltaVolume, stdDev1Multiplier, stdDev2Multiplier, resetOnNewSession, debugMode);
		}

		public FKS_VWAP FKS_VWAP(ISeries<double> input, bool showStdDevBands, bool showVolumeProfile, bool showDeltaVolume, double stdDev1Multiplier, double stdDev2Multiplier, bool resetOnNewSession, bool debugMode)
		{
			if (cacheFKS_VWAP_Enhanced != null)
				for (int idx = 0; idx < cacheFKS_VWAP_Enhanced.Length; idx++)
					if (cacheFKS_VWAP_Enhanced[idx] != null && cacheFKS_VWAP_Enhanced[idx].ShowStdDevBands == showStdDevBands && cacheFKS_VWAP_Enhanced[idx].ShowVolumeProfile == showVolumeProfile && cacheFKS_VWAP_Enhanced[idx].ShowDeltaVolume == showDeltaVolume && cacheFKS_VWAP_Enhanced[idx].StdDev1Multiplier == stdDev1Multiplier && cacheFKS_VWAP_Enhanced[idx].StdDev2Multiplier == stdDev2Multiplier && cacheFKS_VWAP_Enhanced[idx].ResetOnNewSession == resetOnNewSession && cacheFKS_VWAP_Enhanced[idx].DebugMode == debugMode && cacheFKS_VWAP_Enhanced[idx].EqualsInput(input))
						return cacheFKS_VWAP_Enhanced[idx];
			return CacheIndicator<FKS_VWAP>(new FKS_VWAP(){ ShowStdDevBands = showStdDevBands, ShowVolumeProfile = showVolumeProfile, ShowDeltaVolume = showDeltaVolume, StdDev1Multiplier = stdDev1Multiplier, StdDev2Multiplier = stdDev2Multiplier, ResetOnNewSession = resetOnNewSession, DebugMode = debugMode }, input, ref cacheFKS_VWAP_Enhanced);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.FKS_VWAP FKS_VWAP(bool showStdDevBands, bool showVolumeProfile, bool showDeltaVolume, double stdDev1Multiplier, double stdDev2Multiplier, bool resetOnNewSession, bool debugMode)
		{
			return indicator.FKS_VWAP(Input, showStdDevBands, showVolumeProfile, showDeltaVolume, stdDev1Multiplier, stdDev2Multiplier, resetOnNewSession, debugMode);
		}

		public Indicators.FKS_VWAP FKS_VWAP(ISeries<double> input , bool showStdDevBands, bool showVolumeProfile, bool showDeltaVolume, double stdDev1Multiplier, double stdDev2Multiplier, bool resetOnNewSession, bool debugMode)
		{
			return indicator.FKS_VWAP(input, showStdDevBands, showVolumeProfile, showDeltaVolume, stdDev1Multiplier, stdDev2Multiplier, resetOnNewSession, debugMode);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.FKS_VWAP FKS_VWAP(bool showStdDevBands, bool showVolumeProfile, bool showDeltaVolume, double stdDev1Multiplier, double stdDev2Multiplier, bool resetOnNewSession, bool debugMode)
		{
			return indicator.FKS_VWAP(Input, showStdDevBands, showVolumeProfile, showDeltaVolume, stdDev1Multiplier, stdDev2Multiplier, resetOnNewSession, debugMode);
		}

		public Indicators.FKS_VWAP FKS_VWAP(ISeries<double> input , bool showStdDevBands, bool showVolumeProfile, bool showDeltaVolume, double stdDev1Multiplier, double stdDev2Multiplier, bool resetOnNewSession, bool debugMode)
		{
			return indicator.FKS_VWAP(input, showStdDevBands, showVolumeProfile, showDeltaVolume, stdDev1Multiplier, stdDev2Multiplier, resetOnNewSession, debugMode);
		}
	}
}

#endregion
