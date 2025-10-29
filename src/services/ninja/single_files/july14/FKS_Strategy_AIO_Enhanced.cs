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
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class FKS_Strategy_AIO_Enhanced : Strategy
    {
        #region Market Regime Enumeration
        public enum MarketRegime
        {
            Bullish,
            Bearish,
            Sideways,
            Volatile,
            Accumulation,
            Distribution
        }
        #endregion

        #region Variables
        // Account and position management
        private const double ACCOUNT_SIZE = 150000;
        private static readonly object GlobalPositionLock = new object();
        private static Dictionary<string, int> GlobalPositions = new Dictionary<string, int>();
        private static int GlobalTotalContracts = 0;
        private const int MAX_TOTAL_CONTRACTS = 15;
        private const int PREFERRED_MAX_CONTRACTS = 10;
        
        // Enhanced risk management parameters
        private double signalQualityThreshold = 0.80; // Raised from 0.72
        private double volumeThreshold = 1.5; // Raised from 1.35
        private int maxDailyTrades = 4; // Reduced from 6
        private int baseContracts = 1;
        private int maxContracts = 3; // Reduced from 4
        private double atrStopMultiplier = 1.8; // Tighter from 2.0
        private double atrTargetMultiplier = 4.5; // Increased for better risk/reward
        private double dailyProfitTarget = 2000; // Reduced from 2500
        private double dailyLossLimit = 800; // Reduced from 1200
        private bool debugMode = true;
        private int stopHour = 15;
        
        // Enhanced drawdown protection
        private double maxDrawdownPercent = 0.15; // 15% max drawdown
        private double currentDrawdown = 0;
        private double peakEquity = 0;
        private double dynamicPositionSizeMultiplier = 1.0;
        
        // Re-entry prevention
        private int barsSinceExit = 0;
        private readonly int reEntryCooldown = 5;
        
        // Volume filter option
        private readonly bool useVolumeFilter = true;
        
        // Enhanced profit and loss limits
        private double hardProfitLimit = 2500; // Reduced from 3000
        private double softProfitLimit = 1500; // Reduced from 2000
        private double hardLossLimit = 1000; // Reduced from 1500
        private double softLossLimit = 600; // Reduced from 1000
        private bool softLimitTriggered = false;
        
        // Primary timeframe indicators (1-minute)
        private FKS_VWAP_Indicator vwapIndicator;
        private EMA ema9;
        private ATR atr;
        private VOL volume;
        private SMA volumeAvg;
        
        // Higher timeframe indicators (5-minute)
        private EMA ema9_HT;
        private FKS_VWAP_Indicator vwap_HT;
        private ATR atr_HT;
        private VOL volume_HT;
        private SMA volumeAvg_HT;
        
        // Level 2 Market Data
        private double bidAskRatio;
        private double volumeImbalance;
        private bool isVolumeImbalanceBullish;
        private bool isVolumeImbalanceBearish;
        
        // Custom AO implementation
        private SMA aoFast;
        private SMA aoSlow;
        private SMA aoFast_HT;
        private SMA aoSlow_HT;
        private double aoValue;
        private double aoPrevValue;
        private double aoValue_HT;
        private double aoPrevValue_HT;
        
        // Market regime and clustering
        private MarketRegime currentRegime = MarketRegime.Sideways;
        private MarketRegime previousRegime = MarketRegime.Sideways;
        private List<ClusterData> historicalData = new List<ClusterData>();
        private double regimeSignalQualityMultiplier = 1.0;
        private double regimePositionSizeMultiplier = 1.0;
        private bool regimeAllowShorts = true;
        private int clusteringLookback = 100;
        private int recalculateInterval = 20;
        
        // Support/Resistance tracking
        private double nearestSupport;
        private double nearestResistance;
        private double nearestSupport_HT;
        private double nearestResistance_HT;
        
        // Signal tracking
        private string currentSignal = "";
        private double signalQuality = 0;
        private int activeSetup = 0;
        private bool higherTimeframeConfirmed = false;
        
        // Enhanced risk management
        private double currentDailyPnL;
        private int todaysTrades;
        private int consecutiveLosses;
        private int consecutiveShortLosses;
        private bool tradingEnabled = true;
        private bool shortTradingEnabled = true;
        private DateTime lastTradeTime = DateTime.MinValue;
        private DateTime currentDay = DateTime.MinValue;
        
        // Enhanced position management
        private double entryPrice;
        private double currentStop;
        private double stopPrice;
        private double target1Price;
        private double target2Price;
        private bool target1Hit = false;
        private bool target2Hit = false;
        private bool isLong = false;
        private bool isShort = false;
        private int barsInTrade = 0;
        
        // Enhanced debugging
        private int crossoverCheckCount = 0;
        private DateTime lastCrossoverCheck = DateTime.MinValue;
        private bool hasWarnedAboutHA = false;
        
        // Clustering data structure
        public class ClusterData
        {
            public double Returns { get; set; }
            public double Volatility { get; set; }
            public double Momentum { get; set; }
            public double Volume { get; set; }
            public double PricePosition { get; set; }
            public DateTime Timestamp { get; set; }
            public MarketRegime Regime { get; set; }
        }
        
        // Custom series for clustering
        private Series<double> returns;
        private Series<double> volatility;
        private Series<double> momentum;
        #endregion

        #region Enhanced Risk Management Methods
        
        // Get adaptive stop multiplier based on market regime
        private double GetAdaptiveStopMultiplier()
        {
            switch (currentRegime)
            {
                case MarketRegime.Volatile:
                    return 1.5; // Wider stops in volatile conditions
                case MarketRegime.Accumulation:
                    return 2.5; // Tighter stops in accumulation
                case MarketRegime.Sideways:
                    return 1.8; // Tighter stops in sideways markets
                case MarketRegime.Bullish:
                case MarketRegime.Bearish:
                    return 2.0; // Standard stops in trending markets
                default:
                    return 1.8;
            }
        }
        
        // Get regime-based position size multiplier
        private double GetRegimePositionMultiplier()
        {
            switch (currentRegime)
            {
                case MarketRegime.Volatile:
                    return 0.5; // Reduce size in volatile markets
                case MarketRegime.Sideways:
                    return 0.7; // Smaller positions in choppy markets
                case MarketRegime.Accumulation:
                    return 1.2; // Larger positions in accumulation
                case MarketRegime.Bullish:
                case MarketRegime.Bearish:
                    return 1.0; // Standard size in trending markets
                default:
                    return 0.8;
            }
        }
        
        // Get consecutive loss protection multiplier
        private double GetConsecutiveLossMultiplier()
        {
            if (consecutiveLosses >= 3) return 0.5;
            if (consecutiveLosses >= 2) return 0.75;
            return 1.0;
        }
        
        // Get drawdown protection multiplier
        private double GetDrawdownMultiplier()
        {
            if (currentDrawdown > ACCOUNT_SIZE * 0.10) // 10% drawdown
                return 0.3;
            if (currentDrawdown > ACCOUNT_SIZE * 0.05) // 5% drawdown
                return 0.5;
            if (currentDrawdown > ACCOUNT_SIZE * 0.03) // 3% drawdown
                return 0.75;
            
            return 1.0;
        }
        
        // Get signal quality multiplier
        private double GetSignalQualityMultiplier()
        {
            if (signalQuality >= 0.90) return 1.5;
            if (signalQuality >= 0.85) return 1.2;
            if (signalQuality >= 0.80) return 1.0;
            return 0.8;
        }
        
        // Update drawdown calculations
        private void UpdateDrawdownCalculations()
        {
            double currentEquity = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            
            if (currentEquity > peakEquity)
            {
                peakEquity = currentEquity;
                currentDrawdown = 0;
            }
            else
            {
                currentDrawdown = peakEquity - currentEquity;
            }
            
            // Update dynamic position size multiplier based on drawdown
            if (currentDrawdown > ACCOUNT_SIZE * 0.05) // 5% drawdown
            {
                dynamicPositionSizeMultiplier = 0.5;
            }
            else if (currentDrawdown > ACCOUNT_SIZE * 0.03) // 3% drawdown
            {
                dynamicPositionSizeMultiplier = 0.75;
            }
            else
            {
                dynamicPositionSizeMultiplier = 1.0;
            }
        }
        
        // Enhanced market condition validation
        private bool IsMarketConditionFavorable()
        {
            // Avoid trading during high volatility periods
            if (atr[0] > atr[20] * 1.5) return false;
            
            // Avoid trading during low volume periods
            if (volume[0] < volumeAvg[50] * 0.8) return false;
            
            // Add time-of-day filters for better execution
            int hour = Time[0].Hour;
            if (hour < 10 || hour > 15) return false; // Trade during active hours
            
            // Avoid lunch hour
            if (hour >= 12 && hour < 13) return false;
            
            return true;
        }
        
        // Enhanced signal quality validation
        private bool ValidateSignalQuality()
        {
            // 1. Volume confirmation
            if (volume[0] < volumeAvg[20] * volumeThreshold) return false;
            
            // 2. Momentum alignment
            double emaSlope = (ema9[0] - ema9[3]) / 3;
            if (isLong && emaSlope <= 0) return false;
            if (isShort && emaSlope >= 0) return false;
            
            // 3. Higher timeframe confirmation
            if (!ConfirmHigherTimeframe()) return false;
            
            // 4. Support/resistance levels
            if (!ValidateSupportResistance()) return false;
            
            return signalQuality >= signalQualityThreshold;
        }
        
        // Higher timeframe confirmation
        private bool ConfirmHigherTimeframe()
        {
            if (BarsArray[1].Count <= 0) return true; // Skip if no HT data
            
            // 5-minute timeframe must align
            if (isLong && ema9_HT[0] <= vwap_HT[0]) return false;
            if (isShort && ema9_HT[0] >= vwap_HT[0]) return false;
            
            return true;
        }
        
        // Support/resistance validation
        private bool ValidateSupportResistance()
        {
            double currentPrice = Close[0];
            double buffer = atr[0] * 0.5;
            
            if (isLong)
            {
                // Don't buy near resistance
                return currentPrice < (nearestResistance - buffer);
            }
            else if (isShort)
            {
                // Don't sell near support
                return currentPrice > (nearestSupport + buffer);
            }
            return true;
        }
        
        #endregion

        #region Enhanced Position Management
        
        // Enhanced position sizing with multiple risk factors
        private int CalculateOptimalPositionSize()
        {
            // Start with base size
            double baseSize = baseContracts;
            
            // Apply all multipliers
            double qualityMultiplier = GetSignalQualityMultiplier();
            double regimeMultiplier = GetRegimePositionMultiplier();
            double lossMultiplier = GetConsecutiveLossMultiplier();
            double drawdownMultiplier = GetDrawdownMultiplier();
            double dynamicMultiplier = dynamicPositionSizeMultiplier;
            
            // Calculate final size
            double finalSize = baseSize * qualityMultiplier * regimeMultiplier * 
                             lossMultiplier * drawdownMultiplier * dynamicMultiplier;
            
            int contracts = (int)Math.Round(finalSize);
            contracts = Math.Max(1, Math.Min(contracts, maxContracts));
            
            // Additional constraints for shorts
            if (currentSignal == "Top")
            {
                contracts = Math.Max(1, contracts - 1);
                if (consecutiveShortLosses >= 2)
                    contracts = 1;
            }
            
            // Soft limit adjustments
            if (softLimitTriggered)
            {
                contracts = Math.Max(1, contracts / 2);
            }
            
            return contracts;
        }
        
        // Enhanced trailing stop management
        private void UpdateEnhancedTrailingStop()
        {
            if (Position.MarketPosition == MarketPosition.Flat) return;
            
            double atrValue = atr[0];
            
            if (Position.MarketPosition == MarketPosition.Long)
            {
                // Different trailing distances based on profit
                double profitPercent = (Close[0] - entryPrice) / entryPrice;
                double trailMultiplier = 1.5; // Default
                
                if (profitPercent > 0.02) // 2% profit
                    trailMultiplier = 1.2; // Tighter trailing
                else if (profitPercent > 0.01) // 1% profit
                    trailMultiplier = 1.3;
                
                double trailAmount = atrValue * trailMultiplier;
                double newStop = Close[0] - trailAmount;
                
                // Only move stop up and ensure it's below current price
                if (newStop > currentStop && newStop < Close[0])
                {
                    currentStop = newStop;
                    if (debugMode) Print($"Enhanced trailing Long stop updated to {currentStop:F2}");
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                // Different trailing distances based on profit
                double profitPercent = (entryPrice - Close[0]) / entryPrice;
                double trailMultiplier = 1.5; // Default
                
                if (profitPercent > 0.02) // 2% profit
                    trailMultiplier = 1.2; // Tighter trailing
                else if (profitPercent > 0.01) // 1% profit
                    trailMultiplier = 1.3;
                
                double trailAmount = atrValue * trailMultiplier;
                double newStop = Close[0] + trailAmount;
                
                // Only move stop down and ensure it's above current price
                if (newStop < currentStop && newStop > Close[0])
                {
                    currentStop = newStop;
                    if (debugMode) Print($"Enhanced trailing Short stop updated to {currentStop:F2}");
                }
            }
        }
        
        // Time-based profit management
        private void ManageTimeBasedProfits()
        {
            if (Position.MarketPosition == MarketPosition.Flat) return;
            
            barsInTrade++;
            
            // Take partial profits after certain time periods
            if (barsInTrade >= 30 && !target1Hit) // 30 minutes
            {
                double profitPercent = Position.MarketPosition == MarketPosition.Long ? 
                    (Close[0] - entryPrice) / entryPrice : 
                    (entryPrice - Close[0]) / entryPrice;
                
                if (profitPercent > 0.005) // 0.5% profit
                {
                    ExitLong(Position.Quantity / 2, "PartialProfit30min", "");
                    target1Hit = true;
                    // Move stop to breakeven
                    currentStop = entryPrice;
                    if (debugMode) Print($"Partial profit taken at 30 minutes, stop moved to breakeven");
                }
            }
            
            // Exit remaining position after extended time
            if (barsInTrade >= 120) // 2 hours
            {
                ExitPosition("TimeBasedExit");
                if (debugMode) Print($"Position closed due to time limit (120 bars)");
            }
        }
        
        // Enhanced exit conditions
        private bool ShouldExitLongEnhanced()
        {
            // Strong momentum reversal
            if (aoValue < -0.001 && aoPrevValue >= 0) return true;
            
            // Strong trend reversal with volume confirmation
            if (Close[0] < ema9[0] && ema9[0] < ema9[1] && Close[0] < Close[1] && 
                volume[0] > volumeAvg[0] * 1.5) return true;
            
            // Higher timeframe momentum reversal
            if (BarsArray[1].Count > 0 && aoValue_HT < -0.001 && aoPrevValue_HT >= 0)
                return true;
            
            // Regime change to bearish
            if (currentRegime == MarketRegime.Bearish && previousRegime != MarketRegime.Bearish)
                return true;
            
            return false;
        }
        
        private bool ShouldExitShortEnhanced()
        {
            // Strong momentum reversal
            if (aoValue > 0.001 && aoPrevValue <= 0) return true;
            
            // Strong trend reversal with volume confirmation
            if (Close[0] > ema9[0] && ema9[0] > ema9[1] && Close[0] > Close[1] && 
                volume[0] > volumeAvg[0] * 1.5) return true;
            
            // Higher timeframe momentum reversal
            if (BarsArray[1].Count > 0 && aoValue_HT > 0.001 && aoPrevValue_HT <= 0)
                return true;
            
            // Regime change to bullish
            if (currentRegime == MarketRegime.Bullish && previousRegime != MarketRegime.Bullish)
                return true;
            
            return false;
        }
        
        #endregion

        #region State Management
        
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Enhanced FKS Strategy - Improved risk management and drawdown protection";
                Name = "FKS_Strategy_AIO_Enhanced";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                BarsRequiredToTrade = 100;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                
                // Initialize peak equity
                peakEquity = ACCOUNT_SIZE;
            }
            else if (State == State.Configure)
            {
                // Add 5-minute data series for higher timeframe confirmation
                AddDataSeries(BarsPeriodType.Minute, 5);
            }
            else if (State == State.DataLoaded)
            {
                // Initialize indicators
                InitializeIndicators();
                InitializeClustering();
                
                // Reset daily counters
                ResetDailyCounters();
            }
        }
        
        private void InitializeIndicators()
        {
            // Primary timeframe indicators
            vwapIndicator = FKS_VWAP_Indicator();
            ema9 = EMA(9);
            atr = ATR(14);
            volume = VOL();
            volumeAvg = SMA(volume, 50);
            
            // Higher timeframe indicators
            ema9_HT = EMA(BarsArray[1], 9);
            atr_HT = ATR(BarsArray[1], 14);
            volume_HT = VOL(BarsArray[1]);
            volumeAvg_HT = SMA(volume_HT, 50);
            
            // AO components - using Median Price series
            aoFast = SMA(Median, 5);
            aoSlow = SMA(Median, 34);
            aoFast_HT = SMA(Medians[1], 5);
            aoSlow_HT = SMA(Medians[1], 34);
        }
        
        private void InitializeClustering()
        {
            returns = new Series<double>(this);
            volatility = new Series<double>(this);
            momentum = new Series<double>(this);
        }
        
        #endregion

        #region Main Trading Logic
        
        protected override void OnBarUpdate()
        {
            try
            {
                // Skip if not enough data
                if (CurrentBars[0] < BarsRequiredToTrade) return;
                
                // Handle new trading day
                if (Time[0].Date != currentDay)
                {
                    currentDay = Time[0].Date;
                    ResetDailyCounters();
                }
                
                // Update drawdown calculations
                UpdateDrawdownCalculations();
                
                // Update clustering data
                UpdateClusteringData();
                
                // Classify current market regime
                ClassifyCurrentRegime();
                
                // Update regime multipliers if regime changed
                UpdateRegimeMultipliers();
                
                // Update technical indicators
                UpdateTechnicalIndicators();
                
                // Manage existing positions
                ManageExistingPositions();
                
                // Check for new signals only if flat
                if (Position.MarketPosition == MarketPosition.Flat)
                {
                    barsSinceExit++;
                    CheckForNewSignals();
                }
                
                // Strategy state logging
                if (CurrentBar % 50 == 0)
                {
                    LogStrategyState();
                }
            }
            catch (Exception ex)
            {
                Print($"Error in OnBarUpdate: {ex.Message}");
            }
        }
        
        private void ManageExistingPositions()
        {
            if (Position.MarketPosition == MarketPosition.Flat) return;
            
            // Initialize stop if not set
            if (currentStop == 0)
            {
                InitializeStop();
                return;
            }
            
            // Check for stop hits
            if (Position.MarketPosition == MarketPosition.Long && Close[0] <= currentStop)
            {
                Print($"Long stop hit at {Close[0]:F2}, stop was {currentStop:F2}");
                ExitPosition("LongStopHit");
                return;
            }
            else if (Position.MarketPosition == MarketPosition.Short && Close[0] >= currentStop)
            {
                Print($"Short stop hit at {Close[0]:F2}, stop was {currentStop:F2}");
                ExitPosition("ShortStopHit");
                return;
            }
            
            // Check enhanced exit conditions
            if (Position.MarketPosition == MarketPosition.Long && ShouldExitLongEnhanced())
            {
                Print($"Long exit signal at {Close[0]:F2}");
                ExitPosition("LongExitSignal");
                return;
            }
            else if (Position.MarketPosition == MarketPosition.Short && ShouldExitShortEnhanced())
            {
                Print($"Short exit signal at {Close[0]:F2}");
                ExitPosition("ShortExitSignal");
                return;
            }
            
            // Update trailing stops
            UpdateEnhancedTrailingStop();
            
            // Manage time-based profits
            ManageTimeBasedProfits();
        }
        
        private void InitializeStop()
        {
            double atrValue = atr[0];
            double stopMultiplier = GetAdaptiveStopMultiplier();
            
            if (Position.MarketPosition == MarketPosition.Long)
            {
                currentStop = entryPrice - (atrValue * stopMultiplier);
                target1Price = entryPrice + (atrValue * atrTargetMultiplier);
                target2Price = entryPrice + (atrValue * atrTargetMultiplier * 1.5);
                
                if (debugMode) Print($"Long stop initialized: {currentStop:F2}, Target1: {target1Price:F2}");
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                currentStop = entryPrice + (atrValue * stopMultiplier);
                target1Price = entryPrice - (atrValue * atrTargetMultiplier);
                target2Price = entryPrice - (atrValue * atrTargetMultiplier * 1.5);
                
                if (debugMode) Print($"Short stop initialized: {currentStop:F2}, Target1: {target1Price:F2}");
            }
        }
        
        private void CheckForNewSignals()
        {
            // Don't trade if conditions aren't favorable
            if (!ShouldTrade() || !IsMarketConditionFavorable()) return;
            
            // Re-entry cooldown
            if (barsSinceExit < reEntryCooldown) return;
            
            // Check all setups (simplified for this example)
            if (CheckPrimarySetup())
            {
                ExecuteTradeSignal();
            }
        }
        
        private bool CheckPrimarySetup()
        {
            // Simplified setup - EMA9/VWAP crossover with enhancements
            double ema9Val = ema9[0];
            double vwapVal = vwapIndicator.GetVWAPValue();
            
            // Bullish setup
            if (ema9Val > vwapVal && ema9[1] <= vwapIndicator.GetVWAPValue())
            {
                currentSignal = "G";
                isLong = true;
                isShort = false;
                signalQuality = CalculateEnhancedSignalQuality(true);
                activeSetup = 1;
                return ValidateSignalQuality();
            }
            
            // Bearish setup
            if (ema9Val < vwapVal && ema9[1] >= vwapIndicator.GetVWAPValue())
            {
                currentSignal = "Top";
                isLong = false;
                isShort = true;
                signalQuality = CalculateEnhancedSignalQuality(false);
                activeSetup = 1;
                return ValidateSignalQuality() && IsShortSafeToTrade();
            }
            
            return false;
        }
        
        private double CalculateEnhancedSignalQuality(bool isBullish)
        {
            double quality = 0.3; // Increased base quality
            
            // Trend alignment (35%)
            double vwapVal = vwapIndicator.GetVWAPValue();
            if (isBullish && Close[0] > ema9[0] && ema9[0] > vwapVal)
                quality += 0.35;
            else if (!isBullish && Close[0] < ema9[0] && ema9[0] < vwapVal)
                quality += 0.35;
            
            // Higher timeframe confirmation (25%)
            if (ConfirmHigherTimeframe())
                quality += 0.25;
            
            // Momentum confirmation (20%)
            if (isBullish && aoValue > 0.0 && aoValue > aoPrevValue)
                quality += 0.20;
            else if (!isBullish && aoValue < 0.0 && aoValue < aoPrevValue)
                quality += 0.20;
            
            // Relaxed volume confirmation (15%)
            double volRatio = volume[0] / volumeAvg[0];
            if (volRatio >= volumeThreshold)
                quality += 0.15;
            
            // Market regime bonus (5%)
            if ((isBullish && currentRegime == MarketRegime.Bullish) ||
                (!isBullish && currentRegime == MarketRegime.Bearish))
                quality += 0.05;
            
            return Math.Min(1.0, quality * regimeSignalQualityMultiplier);
        }
        
        private void ExecuteTradeSignal()
        {
            int contracts = CalculateOptimalPositionSize();
            if (contracts <= 0) return;
            
            double atrValue = atr[0];
            double stopMultiplier = GetAdaptiveStopMultiplier();
            
            if (currentSignal == "G")
            {
                double calculatedStop = Close[0] - (atrValue * stopMultiplier);
                
                Print($"\n*** ENHANCED BULLISH SIGNAL - SETUP {activeSetup} ***");
                Print($"Time: {Time[0]}, Entry: {Close[0]:F2}, Stop: {calculatedStop:F2}");
                Print($"Quality: {signalQuality:F2}, Contracts: {contracts}, Regime: {currentRegime}");
                
                EnterLong(contracts, "EnhancedLong");
                entryPrice = Close[0];
                currentStop = calculatedStop;
                barsInTrade = 0;
                target1Hit = false;
                target2Hit = false;
                
                UpdateTradeCounters();
            }
            else if (currentSignal == "Top")
            {
                double calculatedStop = Close[0] + (atrValue * stopMultiplier);
                
                Print($"\n*** ENHANCED BEARISH SIGNAL - SETUP {activeSetup} ***");
                Print($"Time: {Time[0]}, Entry: {Close[0]:F2}, Stop: {calculatedStop:F2}");
                Print($"Quality: {signalQuality:F2}, Contracts: {contracts}, Regime: {currentRegime}");
                
                EnterShort(contracts, "EnhancedShort");
                entryPrice = Close[0];
                currentStop = calculatedStop;
                barsInTrade = 0;
                target1Hit = false;
                target2Hit = false;
                
                UpdateTradeCounters();
            }
        }
        
        private void ExitPosition(string reason)
        {
            if (Position.MarketPosition == MarketPosition.Long)
            {
                ExitLong(reason);
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                ExitShort(reason);
            }
            
            // Reset position variables
            currentStop = 0;
            entryPrice = 0;
            target1Hit = false;
            target2Hit = false;
            barsInTrade = 0;
            barsSinceExit = 0;
            
            if (debugMode) Print($"Position exited: {reason}");
        }
        
        #endregion

        #region Utility Methods
        
        private bool ShouldTrade()
        {
            // Time filter
            if (IsOutsideTradingHours()) return false;
            
            // Hard limits
            if (currentDailyPnL >= hardProfitLimit || currentDailyPnL <= -hardLossLimit)
                return false;
            
            // Drawdown protection
            if (currentDrawdown > ACCOUNT_SIZE * maxDrawdownPercent)
                return false;
            
            // Daily trade limits
            if (todaysTrades >= maxDailyTrades) return false;
            
            // Consecutive loss protection
            if (consecutiveLosses >= 3) return false;
            
            // Soft limit restrictions
            if (softLimitTriggered && signalQuality < signalQualityThreshold * 1.2)
                return false;
            
            return true;
        }
        
        private bool IsOutsideTradingHours()
        {
            int hour = Time[0].Hour;
            return hour >= stopHour || hour < 9; // 9 AM to 3 PM
        }
        
        private void UpdateTradeCounters()
        {
            todaysTrades++;
            lastTradeTime = Time[0];
            barsSinceExit = 0;
        }
        
        private void ResetDailyCounters()
        {
            currentDailyPnL = 0;
            todaysTrades = 0;
            consecutiveLosses = 0;
            consecutiveShortLosses = 0;
            softLimitTriggered = false;
            
            if (debugMode) Print($"\n=== New Enhanced Trading Day: {currentDay:yyyy-MM-dd} ===");
        }
        
        private void LogStrategyState()
        {
            if (!debugMode) return;
            
            Print($"\nStrategy State - Bar: {CurrentBar}, Time: {Time[0]}");
            Print($"  Position: {Position.MarketPosition}");
            Print($"  Current Stop: {currentStop:F2}");
            Print($"  Daily P&L: {currentDailyPnL:F2}, Trades: {todaysTrades}");
            Print($"  Drawdown: {currentDrawdown:F2}, Peak: {peakEquity:F2}");
            Print($"  Regime: {currentRegime}, Signal Quality: {signalQuality:F2}");
        }
        
        private void UpdateClusteringData()
        {
            if (CurrentBar >= 10)
            {
                var clusterData = new ClusterData
                {
                    Returns = returns[0],
                    Volatility = volatility[0],
                    Momentum = momentum[0],
                    Volume = volume[0] / volumeAvg[0], // Normalized volume
                    PricePosition = CalculatePricePosition(),
                    Timestamp = Time[0],
                    Regime = currentRegime
                };

                historicalData.Add(clusterData);

                // Keep only recent data for clustering
                if (historicalData.Count > clusteringLookback)
                    historicalData.RemoveAt(0);
            }
        }
        private void ClassifyCurrentRegime()
        {
            if (CurrentBar < 10) return;

            var currentData = new ClusterData
            {
                Returns = returns[0],
                Volatility = volatility[0],
                Momentum = momentum[0],
                Volume = volume[0] / volumeAvg[0],
                PricePosition = CalculatePricePosition()
            };

            // Find the most similar historical regime
            previousRegime = currentRegime;
            currentRegime = ClassifyRegimeFromCentroid(
                currentData.Returns,
                currentData.Volatility,
                currentData.Momentum,
                currentData.Volume
            );
        }
        private void UpdateTechnicalIndicators()
        {
            if (CurrentBar >= 10)
            {
                // Calculate returns
                double todayReturn = (Close[0] - Close[1]) / Close[1];
                returns[0] = todayReturn;
                
                // Calculate volatility (rolling standard deviation)
                double sumSquaredReturns = 0;
                for (int i = 0; i < Math.Min(10, CurrentBar); i++)
                {
                    double ret = (Close[i] - Close[i + 1]) / Close[i + 1];
                    sumSquaredReturns += ret * ret;
                }
                volatility[0] = Math.Sqrt(sumSquaredReturns / Math.Min(10, CurrentBar));
                
                // Calculate momentum (price momentum)
                momentum[0] = (Close[0] - Close[Math.Min(5, CurrentBar)]) / Close[Math.Min(5, CurrentBar)];
                
                // Update AO values
                aoValue = aoFast[0] - aoSlow[0];
                aoPrevValue = aoFast[1] - aoSlow[1];
                aoValue_HT = aoFast_HT[0] - aoSlow_HT[0];
                aoPrevValue_HT = aoFast_HT[1] - aoSlow_HT[1];
                
                // Update support/resistance levels
                UpdateSupportResistanceLevels();
            }
        }
        private bool IsShortSafeToTrade()
        {
            if (!regimeAllowShorts) return false;
            if (consecutiveShortLosses >= 3) return false;

            // Check if we're in a strong uptrend
            double vwapVal = vwapIndicator.GetVWAPValue();
            bool strongUptrend = Close[0] > vwapVal && vwapVal > vwapIndicator.GetVWAPValue() &&
                                ema9[0] > ema9[5] && aoValue > 0;
            if (strongUptrend) return false;

            // Check higher timeframe for shorts
            if (BarsArray[1].Count > 0)
            {
                bool htStrongUptrend = Closes[1][0] > ema9_HT[0] &&
                                    ema9_HT[0] > vwap_HT[0] &&
                                    aoValue_HT > 0;
                if (htStrongUptrend) return false;
            }

        return true;
    }
    
    // Calculate price position relative to recent range
    private double CalculatePricePosition()
    {
        if (CurrentBar < 20) return 0.5;
        
        double highestHigh = High[0];
        double lowestLow = Low[0];
        
        for (int i = 1; i < 20; i++)
        {
            if (High[i] > highestHigh) highestHigh = High[i];
            if (Low[i] < lowestLow) lowestLow = Low[i];
        }
        
        double range = highestHigh - lowestLow;
        if (range == 0) return 0.5;
        
        return (Close[0] - lowestLow) / range;
    }
    
    // Classify market regime based on current data
    private MarketRegime ClassifyRegimeFromCentroid(double returns, double volatility, double momentum, double volume)
    {
        // Bullish: Positive returns, positive momentum, moderate volatility
        if (returns > 0.005 && momentum > 0.01 && volatility < 0.025)
            return MarketRegime.Bullish;
        
        // Bearish: Negative returns, negative momentum, high volatility
        if (returns < -0.005 && momentum < -0.01 && volatility > 0.02)
            return MarketRegime.Bearish;
        
        // Volatile: High volatility regardless of direction
        if (volatility > 0.035)
            return MarketRegime.Volatile;
        
        // Accumulation: Low volatility, high volume, neutral momentum
        if (volatility < 0.015 && volume > 1.3 && Math.Abs(momentum) < 0.005)
            return MarketRegime.Accumulation;
        
        // Distribution: High volume, negative momentum, moderate volatility
        if (volume > 1.5 && momentum < -0.005 && volatility > 0.015 && volatility < 0.03)
            return MarketRegime.Distribution;
        
        // Default to sideways
        return MarketRegime.Sideways;
    }
    
    // Update support and resistance levels
    private void UpdateSupportResistanceLevels()
    {
        if (CurrentBar < 50) return;
        
        // Find recent highs and lows for resistance and support
        double recentHigh = High[0];
        double recentLow = Low[0];
        
        for (int i = 1; i < 50; i++)
        {
            if (High[i] > recentHigh) recentHigh = High[i];
            if (Low[i] < recentLow) recentLow = Low[i];
        }
        
        nearestResistance = recentHigh;
        nearestSupport = recentLow;
        
        // Update higher timeframe levels if available
        if (BarsArray[1].Count > 10)
        {
            double htHigh = Highs[1][0];
            double htLow = Lows[1][0];
            
            for (int i = 1; i < Math.Min(20, BarsArray[1].Count); i++)
            {
                if (Highs[1][i] > htHigh) htHigh = Highs[1][i];
                if (Lows[1][i] < htLow) htLow = Lows[1][i];
            }
            
            nearestResistance_HT = htHigh;
            nearestSupport_HT = htLow;
        }
    }
    
    // Update regime multipliers based on current regime
    private void UpdateRegimeMultipliers()
    {
        if (previousRegime != currentRegime)
        {
            if (debugMode) Print($"\n*** REGIME CHANGE: {previousRegime} -> {currentRegime} ***");
            
            // Adjust multipliers based on new regime
            switch (currentRegime)
            {
                case MarketRegime.Bullish:
                    regimeSignalQualityMultiplier = 1.10;
                    regimePositionSizeMultiplier = 1.20;
                    regimeAllowShorts = false;
                    break;
                    
                case MarketRegime.Bearish:
                    regimeSignalQualityMultiplier = 1.05;
                    regimePositionSizeMultiplier = 1.10;
                    regimeAllowShorts = true;
                    break;
                    
                case MarketRegime.Volatile:
                    regimeSignalQualityMultiplier = 0.80;
                    regimePositionSizeMultiplier = 0.60;
                    regimeAllowShorts = false;
                    break;
                    
                case MarketRegime.Accumulation:
                    regimeSignalQualityMultiplier = 0.90;
                    regimePositionSizeMultiplier = 1.10;
                    regimeAllowShorts = true;
                    break;
                    
                case MarketRegime.Distribution:
                    regimeSignalQualityMultiplier = 0.85;
                    regimePositionSizeMultiplier = 0.90;
                    regimeAllowShorts = true;
                    break;
                    
                case MarketRegime.Sideways:
                default:
                    regimeSignalQualityMultiplier = 1.05;
                    regimePositionSizeMultiplier = 0.90;
                    regimeAllowShorts = true;
                    break;
            }
            
            if (debugMode) Print($"Adjustments - Signal Quality Multiplier: {regimeSignalQualityMultiplier:F2}, Position Size Multiplier: {regimePositionSizeMultiplier:F2}");
        }
    }
        
        #endregion
    }
}
