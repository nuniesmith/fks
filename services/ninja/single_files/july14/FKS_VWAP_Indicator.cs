#region Using declarations
using System;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.DrawingTools;
using NinjaTrader.NinjaScript;
using System.Collections.Generic;
using System.Linq;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class FKS_VWAP_Indicator : Indicator
    {
        private double cumulativeVolumePrice;
        private double cumulativeVolume;
        private DateTime sessionStart;
        private bool resetOnNewSession = true;
        
        // Level 2 Data variables
        private double bidVolume;
        private double askVolume;
        private double bidAskRatio = 1.0;
        private double volumeImbalance;
        private double cumulativeBidVolume;
        private double cumulativeAskVolume;
        
        // Enhanced volume analysis
        private List<double> recentVolumes = new List<double>();
        private List<double> recentPriceChanges = new List<double>();
        private int volumeAnalysisPeriod = 10;
        
        // For better Level 2 simulation
        private double avgVolume;
        private double volumeStdDev;
        private bool debugMode = true;
        
        // EMA9 for crossover signals
        private EMA ema9;
        
        // FIXED: Properly track previous values for crossover detection
        private double previousVWAP = double.NaN;
        private double previousEMA9 = double.NaN;
        
        // Store current values to ensure we have them for next bar
        private double currentVWAP = double.NaN;
        private double currentEMA9 = double.NaN;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Custom VWAP with Level 2 Data";
                Name = "FKS_VWAP_Indicator";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                BarsRequiredToPlot = 1;
                ResetOnNewSession = true;
                
                // Add VWAP and EMA9 plots as overlay
                AddPlot(Brushes.Magenta, "VWAP");
                AddPlot(Brushes.Blue, "EMA9");
            }
            else if (State == State.DataLoaded)
            {
                sessionStart = Time[0].Date;
                recentVolumes.Clear();
                recentPriceChanges.Clear();
                cumulativeVolumePrice = 0;
                cumulativeVolume = 0;
                cumulativeBidVolume = 0;
                cumulativeAskVolume = 0;
                bidAskRatio = 1.0;
                volumeImbalance = 0;
                
                // Initialize EMA9
                ema9 = EMA(Close, 9);
                
                // Initialize previous values
                previousVWAP = double.NaN;
                previousEMA9 = double.NaN;
                
                if (debugMode) ClearOutputWindow();
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1) return;
            
            // Reset on new session if enabled
            if (resetOnNewSession && Time[0].Date != sessionStart)
            {
                ResetSession();
            }

            // Calculate typical price (HLC/3) weighted by volume
            double typicalPrice = (High[0] + Low[0] + Close[0]) / 3.0;
            double volumeWeightedPrice = typicalPrice * Volume[0];
            
            cumulativeVolumePrice += volumeWeightedPrice;
            cumulativeVolume += Volume[0];

            // Calculate VWAP
            double vwapValue = cumulativeVolume > 0 ? cumulativeVolumePrice / cumulativeVolume : typicalPrice;
            
            // Ensure VWAP value is valid
            if (double.IsNaN(vwapValue) || double.IsInfinity(vwapValue))
                vwapValue = typicalPrice;
            
            // Calculate EMA9 value
            double ema9Value = ema9[0];
            
            // FIXED: Store previous values from our own variables (not the Values array)
            if (CurrentBar > 1 && !double.IsNaN(currentVWAP) && !double.IsNaN(currentEMA9))
            {
                previousVWAP = currentVWAP;
                previousEMA9 = currentEMA9;
                
                if (debugMode && CurrentBar % 50 == 0)
                {
                    Print($"Storing previous values - PrevVWAP: {previousVWAP:F2}, PrevEMA9: {previousEMA9:F2}");
                }
            }
            
            // Store current values for next bar
            currentVWAP = vwapValue;
            currentEMA9 = ema9Value;
            
            // Set the new calculated values to the plot
            Values[0][0] = vwapValue;
            Values[1][0] = ema9Value;
            
            // Debug crossover conditions
            if (debugMode && CurrentBar % 20 == 0)
            {
                double currentEMA9 = Values[1][0];
                double currentVWAP = Values[0][0];
                Print($"Bar {CurrentBar}: Current EMA9={currentEMA9:F2}, VWAP={currentVWAP:F2}, " +
                      $"Prev EMA9={previousEMA9:F2}, Prev VWAP={previousVWAP:F2}");
                
                // Check if we're close to a crossover
                double distance = Math.Abs(currentEMA9 - currentVWAP);
                if (distance < TickSize * 5)
                {
                    Print($"  >> CLOSE TO CROSSOVER! Distance: {distance:F4}");
                }
            }
            
            // Update volume analysis data
            UpdateVolumeAnalysis();
            
            // Level 2 Data Analysis (simulated from volume and price action)
            AnalyzeLevelTwoData();
        }
        
        protected override void OnMarketData(MarketDataEventArgs marketDataUpdate)
        {
            // Process Level 2 data if available
            if (marketDataUpdate.MarketDataType == MarketDataType.Bid)
            {
                // Track bid volume and pressure
                bidVolume = marketDataUpdate.Volume;
                cumulativeBidVolume += bidVolume;
            }
            else if (marketDataUpdate.MarketDataType == MarketDataType.Ask)
            {
                // Track ask volume and pressure
                askVolume = marketDataUpdate.Volume;
                cumulativeAskVolume += askVolume;
            }
        }
        
        private void ResetSession()
        {
            cumulativeVolumePrice = 0;
            cumulativeVolume = 0;
            cumulativeBidVolume = 0;
            cumulativeAskVolume = 0;
            sessionStart = Time[0].Date;
            recentVolumes.Clear();
            recentPriceChanges.Clear();
            bidAskRatio = 1.0;
            volumeImbalance = 0;
            
            // Reset previous values on new session
            previousVWAP = double.NaN;
            previousEMA9 = double.NaN;
        }
        
        private bool IsCloseToCrossover(double threshold)
        {
            double distance = Math.Abs(currentEMA9 - currentVWAP);
            return distance < threshold;
        }
        
        private void UpdateVolumeAnalysis()
        {
            // Update recent volume data
            recentVolumes.Add(Volume[0]);
            if (recentVolumes.Count > volumeAnalysisPeriod)
                recentVolumes.RemoveAt(0);
            
            // Update recent price changes
            if (CurrentBar > 0)
            {
                double priceChange = Close[0] - Close[1];
                recentPriceChanges.Add(priceChange);
                if (recentPriceChanges.Count > volumeAnalysisPeriod)
                    recentPriceChanges.RemoveAt(0);
            }
            
            // Calculate average volume and standard deviation
            if (recentVolumes.Count > 0)
            {
                avgVolume = recentVolumes.Average();
                if (recentVolumes.Count > 1)
                {
                    double variance = recentVolumes.Select(v => Math.Pow(v - avgVolume, 2)).Average();
                    volumeStdDev = Math.Sqrt(variance);
                }
            }
        }
        
        private void AnalyzeLevelTwoData()
        {
            if (CurrentBar < 1) return;
            
            // Enhanced bid/ask ratio simulation based on price action and volume
            double priceChange = Close[0] - Close[1];
            double currentVolume = Volume[0];
            double volumeRatio = avgVolume > 0 ? currentVolume / avgVolume : 1.0;
            
            // Simulate bid/ask pressure based on price movement and volume
            if (priceChange > 0)
            {
                // Price up - more buying pressure
                double buyPressure = Math.Min(2.0, 1.0 + (priceChange / TickSize * 0.1) + (volumeRatio - 1.0) * 0.5);
                bidAskRatio = Math.Max(0.5, buyPressure);
                
                // Simulate higher bid volume
                double simulatedBidVolume = currentVolume * (0.6 + (priceChange / TickSize * 0.02));
                double simulatedAskVolume = currentVolume * (0.4 - (priceChange / TickSize * 0.02));
                
                cumulativeBidVolume += Math.Max(0, simulatedBidVolume);
                cumulativeAskVolume += Math.Max(0, simulatedAskVolume);
            }
            else if (priceChange < 0)
            {
                // Price down - more selling pressure
                double sellPressure = Math.Max(0.5, 1.0 + (priceChange / TickSize * 0.1) - (volumeRatio - 1.0) * 0.5);
                bidAskRatio = Math.Min(2.0, sellPressure);
                
                // Simulate higher ask volume
                double simulatedBidVolume = currentVolume * (0.4 + (priceChange / TickSize * 0.02));
                double simulatedAskVolume = currentVolume * (0.6 - (priceChange / TickSize * 0.02));
                
                cumulativeBidVolume += Math.Max(0, simulatedBidVolume);
                cumulativeAskVolume += Math.Max(0, simulatedAskVolume);
            }
            else
            {
                // No price change - balanced
                bidAskRatio = 1.0;
                cumulativeBidVolume += currentVolume * 0.5;
                cumulativeAskVolume += currentVolume * 0.5;
            }
            
            // Calculate volume imbalance
            volumeImbalance = cumulativeBidVolume - cumulativeAskVolume;
            
            // Normalize volume imbalance relative to total volume
            if (cumulativeVolume > 0)
                volumeImbalance = volumeImbalance / cumulativeVolume;
        }
        
        // FIXED: Improved crossover detection methods
        public bool IsBullishCrossover()
        {
            if (CurrentBar < 2) return false;
            
            double currentEMA9 = Values[1][0];
            double currentVWAP = Values[0][0];
            
            // For the first valid bars or after session reset, just check if EMA9 > VWAP
            if (double.IsNaN(previousEMA9) || double.IsNaN(previousVWAP))
            {
                if (debugMode && currentEMA9 > currentVWAP)
                    Print($"Initial bullish state detected (no previous values): EMA9={currentEMA9:F2} > VWAP={currentVWAP:F2}");
                return false; // Don't trigger on first bar to avoid false signals
            }
            
            bool isCrossover = currentEMA9 > currentVWAP && previousEMA9 <= previousVWAP;
            
            if (debugMode && isCrossover)
            {
                Print($"BULLISH CROSSOVER CONFIRMED! Current: EMA9={currentEMA9:F2} > VWAP={currentVWAP:F2}, " +
                      $"Previous: EMA9={previousEMA9:F2} <= VWAP={previousVWAP:F2}");
            }
            
            return isCrossover;
        }
        
        public bool IsBearishCrossover()
        {
            if (CurrentBar < 2) return false;
            
            double currentEMA9 = Values[1][0];
            double currentVWAP = Values[0][0];
            
            // For the first valid bars or after session reset, just check if EMA9 < VWAP
            if (double.IsNaN(previousEMA9) || double.IsNaN(previousVWAP))
            {
                if (debugMode && currentEMA9 < currentVWAP)
                    Print($"Initial bearish state detected (no previous values): EMA9={currentEMA9:F2} < VWAP={currentVWAP:F2}");
                return false; // Don't trigger on first bar to avoid false signals
            }
            
            bool isCrossover = currentEMA9 < currentVWAP && previousEMA9 >= previousVWAP;
            
            if (debugMode && isCrossover)
            {
                Print($"BEARISH CROSSOVER CONFIRMED! Current: EMA9={currentEMA9:F2} < VWAP={currentVWAP:F2}, " +
                      $"Previous: EMA9={previousEMA9:F2} >= VWAP={previousVWAP:F2}");
            }
            
            return isCrossover;
        }
        
        // All other methods remain the same...
        public double GetVolumeImbalance()
        {
            return volumeImbalance;
        }
        
        public double GetBidAskRatio()
        {
            return bidAskRatio;
        }
        
        public bool IsVolumeImbalanceBullish()
        {
            return volumeImbalance > 0.05 && bidAskRatio > 1.15;
        }
        
        public bool IsVolumeImbalanceBearish()
        {
            return volumeImbalance < -0.05 && bidAskRatio < 0.85;
        }
        
        public double GetCurrentVWAP()
        {
            return Values[0][0];
        }
        
        public double GetVolumeStrength()
        {
            if (avgVolume > 0)
                return Volume[0] / avgVolume;
            return 1.0;
        }
        
        public double GetVWAPValue()
        {
            return Values[0][0];
        }
        
        public bool IsPriceAboveVWAP()
        {
            return Close[0] > Values[0][0];
        }
        
        public bool IsPriceBelowVWAP()
        {
            return Close[0] < Values[0][0];
        }
        
        public double GetVWAPDistance()
        {
            return Close[0] - Values[0][0];
        }
        
        public double GetVWAPDistancePercent()
        {
            if (Values[0][0] > 0)
                return (Close[0] - Values[0][0]) / Values[0][0] * 100;
            return 0;
        }
        
        public double GetEMA9Value()
        {
            return Values[1][0];
        }
        
        public bool IsEMA9AboveVWAP()
        {
            return Values[1][0] > Values[0][0];
        }
        
        public bool IsEMA9BelowVWAP()
        {
            return Values[1][0] < Values[0][0];
        }
        
        public double GetEMA9Distance()
        {
            return Values[1][0] - Values[0][0];
        }

        #region Properties
        [Display(Name = "Reset On New Session", GroupName = "Parameters", Order = 1)]
        public bool ResetOnNewSession
        {
            get { return resetOnNewSession; }
            set { resetOnNewSession = value; }
        }
        
        [Display(Name = "Debug Mode", GroupName = "Parameters", Order = 2)]
        public bool DebugMode
        {
            get { return debugMode; }
            set { debugMode = value; }
        }
        
        [Display(Name = "Volume Analysis Period", GroupName = "Parameters", Order = 3)]
        public int VolumeAnalysisPeriod
        {
            get { return volumeAnalysisPeriod; }
            set { volumeAnalysisPeriod = Math.Max(5, value); }
        }
        #endregion
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private FKS_VWAP_Indicator[] cacheFKS_VWAP_Indicator;
		public FKS_VWAP_Indicator FKS_VWAP_Indicator()
		{
			return FKS_VWAP_Indicator(Input);
		}

		public FKS_VWAP_Indicator FKS_VWAP_Indicator(ISeries<double> input)
		{
			if (cacheFKS_VWAP_Indicator != null)
				for (int idx = 0; idx < cacheFKS_VWAP_Indicator.Length; idx++)
					if (cacheFKS_VWAP_Indicator[idx] != null &&  cacheFKS_VWAP_Indicator[idx].EqualsInput(input))
						return cacheFKS_VWAP_Indicator[idx];
			return CacheIndicator<FKS_VWAP_Indicator>(new FKS_VWAP_Indicator(), input, ref cacheFKS_VWAP_Indicator);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.FKS_VWAP_Indicator FKS_VWAP_Indicator()
		{
			return indicator.FKS_VWAP_Indicator(Input);
		}

		public Indicators.FKS_VWAP_Indicator FKS_VWAP_Indicator(ISeries<double> input )
		{
			return indicator.FKS_VWAP_Indicator(input);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.FKS_VWAP_Indicator FKS_VWAP_Indicator()
		{
			return indicator.FKS_VWAP_Indicator(Input);
		}

		public Indicators.FKS_VWAP_Indicator FKS_VWAP_Indicator(ISeries<double> input )
		{
			return indicator.FKS_VWAP_Indicator(input);
		}
	}
}

#endregion
