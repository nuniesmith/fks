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
    public class FKSStrategyAIO_Enhanced : Strategy
    {
        #region Variables
        // Account settings
        private const double ACCOUNT_SIZE = 150000; // $150k account
        
        // Global Position Management - Shared across all strategy instances
        private static readonly object GlobalPositionLock = new object();
        private static Dictionary<string, int> GlobalPositions = new Dictionary<string, int>();
        private static int GlobalTotalContracts = 0;
        private const int MAX_TOTAL_CONTRACTS = 15;
        private const int PREFERRED_MAX_CONTRACTS = 10;
        
        // Fixed profit/loss limits (optimized for your account size)
        private double dailyProfitSoftTarget = 2250;  // 1.5% of account
        private double dailyProfitHardTarget = 3000;  // 2% of account
        private double dailyLossSoftLimit = 1000;     // 0.67% of account
        private double dailyLossHardLimit = 1500;     // 1% of account
        
        // Primary timeframe indicators (1-minute)
        private EMA ema9;
        private SMA sma20; // VWAP proxy
        private ATR atr;
        private VOL volume;
        private SMA volumeAvg;
        
        // Higher timeframe indicators (5-minute for confirmation)
        private EMA ema9_HT;
        private SMA sma20_HT;
        private ATR atr_HT;
        private VOL volume_HT;
        private SMA volumeAvg_HT;
        
        // Custom AO implementation
        private SMA aoFast;
        private SMA aoSlow;
        private SMA aoFast_HT;
        private SMA aoSlow_HT;
        private double aoValue;
        private double aoPrevValue;
        private double aoValue_HT;
        private double aoPrevValue_HT;
        
        // Support/Resistance tracking
        private double nearestSupport;
        private double nearestResistance;
        private double nearestSupport_HT;
        private double nearestResistance_HT;
        
        // Signal tracking
        private string currentSignal = "";
        private double signalQuality = 0;
        private double waveRatio = 1.0;
        private int activeSetup = 0;
        private bool higherTimeframeConfirmed = false;
        
        // Risk Management
        private double startingBalance;
        private double currentDailyPnL;
        private int todaysTrades;
        private int consecutiveLosses;
        private bool tradingEnabled = true;
        private DateTime lastTradeTime = DateTime.MinValue;
        private DateTime currentDay = DateTime.MinValue;
        
        // Position Management
        private double entryPrice;
        private double stopPrice;
        private double target1Price;
        private double target2Price;
        private bool target1Hit = false;
        private bool target2Hit = false;
        
        // Enhanced signal filtering
        private Dictionary<string, double> signalHistory = new Dictionary<string, double>();
        private int consecutiveShortLosses = 0;
        private int consecutiveLongLosses = 0;
        private bool shortTradingEnabled = true;
        #endregion
        
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"FKS Strategy AIO Enhanced - Multi-timeframe confirmation with improved short strategy";
                Name = "FKSStrategyAIO_Enhanced";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                BarsRequiredToTrade = 50;
                
                // Enhanced settings for better performance
                SignalQualityThreshold = 0.70;  // Raised from 0.65 for better quality
                VolumeThreshold = 1.3;          // Raised from 1.2 for stronger confirmation
                MaxDailyTrades = 8;             // Reduced from 10 for quality over quantity
                
                BaseContracts = 1;
                MaxContracts = 5;
                ATRStopMultiplier = 2.0;
                ATRTargetMultiplier = 1.5;
                UseTimeFilter = true;
                
                // Optimized time windows based on your guide
                StartHour = 8;    // 8am EST - London overlap
                EndHour = 15;     // 3pm EST - Before NY close
                MinutesBeforeClose = 15;
                
                // Enhanced controls
                UseHigherTimeframeConfirmation = true;
                RequireVolumeConfirmation = true;
                DisableShortsDuringUptrend = true;
                MaxConsecutiveShortLosses = 3;
                ShowDebugInfo = false;
            }
            else if (State == State.Configure)
            {
                // Add 5-minute data series for higher timeframe confirmation
                AddDataSeries(BarsPeriodType.Minute, 5);
            }
            else if (State == State.DataLoaded)
            {
                // Primary timeframe indicators (1-minute)
                ema9 = EMA(9);
                sma20 = SMA(20);
                atr = ATR(14);
                volume = VOL();
                volumeAvg = SMA(volume, 20);
                aoFast = SMA(Typical, 5);
                aoSlow = SMA(Typical, 34);
                
                // Higher timeframe indicators (5-minute)
                ema9_HT = EMA(BarsArray[1], 9);
                sma20_HT = SMA(BarsArray[1], 20);
                atr_HT = ATR(BarsArray[1], 14);
                volume_HT = VOL(BarsArray[1]);
                volumeAvg_HT = SMA(volume_HT, 20);
                aoFast_HT = SMA(Typical, 5);
                aoSlow_HT = SMA(Typical, 34);
                
                startingBalance = ACCOUNT_SIZE;
                currentDay = DateTime.MinValue;
            }
        }
        
        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade) return;
            
            // Only process on primary timeframe
            if (BarsInProgress != 0) return;
            
            // Force exit outside trading hours
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                if (IsOutsideTradingHours())
                {
                    if (Position.MarketPosition == MarketPosition.Long)
                        ExitLong("Outside Hours Exit");
                    else
                        ExitShort("Outside Hours Exit");
                    return;
                }
            }
            
            // Reset daily counters
            if (currentDay.Date != Time[0].Date)
            {
                ResetDailyCounters();
                currentDay = Time[0];
            }
            
            // Update calculations
            UpdateCalculations();
            
            // Check trading conditions
            if (!ShouldTrade()) return;
            
            // Manage existing position
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                ManagePosition();
                return;
            }
            
            // Look for new signals
            CheckForSignals();
        }
        
        #region Enhanced Calculations
        private void UpdateCalculations()
        {
            // Calculate AO for both timeframes
            aoPrevValue = aoValue;
            aoValue = aoFast[0] - aoSlow[0];
            
            if (BarsArray[1].Count > 0)
            {
                aoPrevValue_HT = aoValue_HT;
                aoValue_HT = aoFast_HT[0] - aoSlow_HT[0];
            }
            
            // Update support/resistance
            UpdateSupportResistance();
            
            // Update wave analysis
            UpdateWaveAnalysis();
            
            // Generate signals with higher timeframe confirmation
            GenerateEnhancedSignal();
        }
        
        private void UpdateSupportResistance()
        {
            // Primary timeframe S/R
            if (CurrentBar >= 20)
            {
                nearestSupport = MIN(Low, 20)[0];
                nearestResistance = MAX(High, 20)[0];
                
                // Refine with swing points
                for (int i = 5; i < Math.Min(50, CurrentBar); i++)
                {
                    if (IsSwingHigh(i))
                    {
                        double swingHigh = High[i];
                        if (swingHigh > Close[0] && swingHigh < Close[0] * 1.01)
                        {
                            nearestResistance = swingHigh;
                            break;
                        }
                    }
                    
                    if (IsSwingLow(i))
                    {
                        double swingLow = Low[i];
                        if (swingLow < Close[0] && swingLow > Close[0] * 0.99)
                        {
                            nearestSupport = swingLow;
                            break;
                        }
                    }
                }
            }
            
            // Higher timeframe S/R
            if (BarsArray[1].Count > 20)
            {
                nearestSupport_HT = MIN(Lows[1], 20)[0];
                nearestResistance_HT = MAX(Highs[1], 20)[0];
            }
        }
        
        private void UpdateWaveAnalysis()
        {
            // Enhanced wave analysis considering both timeframes
            if (Close[0] > ema9[0] && ema9[0] > ema9[1])
            {
                waveRatio = Math.Max(waveRatio * 1.01, 1.0);
            }
            else if (Close[0] < ema9[0] && ema9[0] < ema9[1])
            {
                waveRatio = Math.Max(waveRatio * 1.01, 1.0);
            }
            else
            {
                waveRatio = Math.Max(waveRatio * 0.99, 0.5);
            }
            
            // Cap wave ratio
            waveRatio = Math.Min(waveRatio, 3.0);
        }
        
        private void GenerateEnhancedSignal()
        {
            currentSignal = "";
            signalQuality = 0;
            higherTimeframeConfirmed = false;
            
            // First check higher timeframe bias
            if (UseHigherTimeframeConfirmation && BarsArray[1].Count > 0)
            {
                higherTimeframeConfirmed = CheckHigherTimeframeConfirmation();
            }
            else
            {
                higherTimeframeConfirmed = true; // Skip if not using HT confirmation
            }
            
            if (!higherTimeframeConfirmed) return;
            
            // Generate signals based on your 4 setups
            GenerateSetupSignals();
        }
        
        private bool CheckHigherTimeframeConfirmation()
        {
            if (BarsArray[1].Count < 2) return false;
            
            // Higher timeframe trend confirmation
            bool htBullishTrend = Closes[1][0] > ema9_HT[0] && ema9_HT[0] > sma20_HT[0];
            bool htBearishTrend = Closes[1][0] < ema9_HT[0] && ema9_HT[0] < sma20_HT[0];
            
            // Higher timeframe momentum
            bool htBullishMomentum = aoValue_HT > 0 || (aoValue_HT > aoPrevValue_HT);
            bool htBearishMomentum = aoValue_HT < 0 || (aoValue_HT < aoPrevValue_HT);
            
            // For longs: require HT bullish trend OR momentum
            if (Close[0] > ema9[0])
            {
                return htBullishTrend || htBullishMomentum;
            }
            
            // For shorts: require HT bearish trend OR momentum
            if (Close[0] < ema9[0])
            {
                return htBearishTrend || htBearishMomentum;
            }
            
            return false;
        }
        
        private void GenerateSetupSignals()
        {
            // SETUP 1: EMA9 + VWAP Bullish Breakout (Enhanced)
            if (Close[0] > ema9[0] && ema9[0] > sma20[0] && 
                Low[0] <= nearestSupport * 1.002 && Close[0] > nearestSupport &&
                aoValue > 0 && volume[0] > volumeAvg[0] * VolumeThreshold)
            {
                currentSignal = "G";
                signalQuality = CalculateEnhancedSignalQuality(true);
                activeSetup = 1;
            }
            // SETUP 2: EMA9 + VWAP Bearish Breakdown (Enhanced with strict conditions)
            else if (Close[0] < ema9[0] && ema9[0] < sma20[0] && 
                     High[0] >= nearestResistance * 0.998 && Close[0] < nearestResistance &&
                     aoValue < 0 && volume[0] > volumeAvg[0] * VolumeThreshold &&
                     shortTradingEnabled && IsShortSafeToTrade())
            {
                currentSignal = "Top";
                signalQuality = CalculateEnhancedSignalQuality(false);
                activeSetup = 2;
            }
            // SETUP 3: VWAP Rejection Bounce (Enhanced)
            else if (IsVWAPRejectionSetup())
            {
                if (Close[0] > sma20[0] && Close[0] > Open[0])
                {
                    currentSignal = "G";
                    signalQuality = CalculateEnhancedSignalQuality(true) * 0.95;
                    activeSetup = 3;
                }
                else if (Close[0] < sma20[0] && Close[0] < Open[0] && 
                         shortTradingEnabled && IsShortSafeToTrade())
                {
                    currentSignal = "Top";
                    signalQuality = CalculateEnhancedSignalQuality(false) * 0.95;
                    activeSetup = 3;
                }
            }
            // SETUP 4: Support/Resistance + AO Zero Cross (Enhanced)
            else if (Low[0] <= nearestSupport * 1.003 && aoValue > 0.001 && aoPrevValue <= 0 &&
                     Close[0] > Open[0])
            {
                currentSignal = "G";
                signalQuality = CalculateEnhancedSignalQuality(true) * 0.90;
                activeSetup = 4;
            }
            else if (High[0] >= nearestResistance * 0.997 && aoValue < -0.001 && aoPrevValue >= 0 &&
                     Close[0] < Open[0] && shortTradingEnabled && IsShortSafeToTrade())
            {
                currentSignal = "Top";
                signalQuality = CalculateEnhancedSignalQuality(false) * 0.90;
                activeSetup = 4;
            }
        }
        
        private bool IsVWAPRejectionSetup()
        {
            double vwapDistance = Math.Abs(Close[0] - sma20[0]) / atr[0];
            return vwapDistance <= 0.6; // Within 0.6 ATR of VWAP
        }
        
        private bool IsShortSafeToTrade()
        {
            // Additional safety checks for shorts
            if (consecutiveShortLosses >= MaxConsecutiveShortLosses)
                return false;
            
            if (DisableShortsDuringUptrend)
            {
                // Check if we're in a strong uptrend
                bool strongUptrend = Close[0] > sma20[0] && sma20[0] > sma20[5] && 
                                    ema9[0] > ema9[5] && aoValue > 0;
                if (strongUptrend) return false;
            }
            
            // Check higher timeframe for shorts
            if (BarsArray[1].Count > 0)
            {
                bool htStrongUptrend = Closes[1][0] > ema9_HT[0] && 
                                      ema9_HT[0] > sma20_HT[0] && 
                                      aoValue_HT > 0;
                if (htStrongUptrend) return false;
            }
            
            return true;
        }
        
        private double CalculateEnhancedSignalQuality(bool isBullish)
        {
            double quality = 0.3; // Lower base quality for selectivity
            
            // Trend alignment (35% - most important)
            if (isBullish && Close[0] > ema9[0] && ema9[0] > sma20[0])
                quality += 0.35;
            else if (!isBullish && Close[0] < ema9[0] && ema9[0] < sma20[0])
                quality += 0.35;
            else if ((isBullish && Close[0] > ema9[0]) || (!isBullish && Close[0] < ema9[0]))
                quality += 0.20;
            
            // Higher timeframe confirmation (25%)
            if (higherTimeframeConfirmed)
                quality += 0.25;
            
            // AO momentum (20%)
            if (isBullish && aoValue > 0.001 && aoPrevValue <= 0)
                quality += 0.20;
            else if (!isBullish && aoValue < -0.001 && aoPrevValue >= 0)
                quality += 0.20;
            else if ((isBullish && aoValue > 0) || (!isBullish && aoValue < 0))
                quality += 0.15;
            
            // Volume confirmation (15%)
            if (RequireVolumeConfirmation)
            {
                double volRatio = volume[0] / volumeAvg[0];
                if (volRatio >= VolumeThreshold * 1.2)
                    quality += 0.15;
                else if (volRatio >= VolumeThreshold)
                    quality += 0.10;
            }
            else
            {
                quality += 0.10; // Default bonus if not requiring volume
            }
            
            // Wave strength (5%)
            if (waveRatio >= 2.0)
                quality += 0.05;
            else if (waveRatio >= 1.5)
                quality += 0.03;
            
            return Math.Min(1.0, quality);
        }
        #endregion
        
        #region Enhanced Signal Detection
        private void CheckForSignals()
        {
            if (signalQuality < SignalQualityThreshold) return;
            
            // Enhanced filtering for shorts
            if (currentSignal == "Top")
            {
                // Additional short confirmation
                if (!IsShortConfirmed()) return;
            }
            
            if (currentSignal == "G" && signalQuality >= SignalQualityThreshold)
            {
                int contracts = CalculateEnhancedPositionSize();
                if (contracts > 0)
                {
                    EnterLong(contracts, "FKS_Long_Setup" + activeSetup);
                    if (ShowDebugInfo)
                        Print($"LONG: Setup {activeSetup} | Q: {signalQuality:P0} | Wave: {waveRatio:F2} | Contracts: {contracts}");
                }
            }
            else if (currentSignal == "Top" && signalQuality >= SignalQualityThreshold)
            {
                int contracts = CalculateEnhancedPositionSize();
                if (contracts > 0)
                {
                    EnterShort(contracts, "FKS_Short_Setup" + activeSetup);
                    if (ShowDebugInfo)
                        Print($"SHORT: Setup {activeSetup} | Q: {signalQuality:P0} | Wave: {waveRatio:F2} | Contracts: {contracts}");
                }
            }
        }
        
        private bool IsShortConfirmed()
        {
            // Multi-factor confirmation for shorts
            bool volumeConfirmed = volume[0] > volumeAvg[0] * VolumeThreshold * 1.3; // Higher volume requirement
            bool aoBearish = aoValue < -0.001;
            bool priceAction = Close[0] < Open[0] && (High[0] - Close[0]) > (Close[0] - Low[0]);
            
            // Require at least 2 of 3 confirmations
            int confirmations = 0;
            if (volumeConfirmed) confirmations++;
            if (aoBearish) confirmations++;
            if (priceAction) confirmations++;
            
            return confirmations >= 2;
        }
        
        private int CalculateEnhancedPositionSize()
        {
            // Enhanced position sizing with commission consideration
            double minProfitTicks = 8; // Higher minimum for commission coverage
            double expectedMoveTicks = (atr[0] * ATRTargetMultiplier) / Instrument.MasterInstrument.TickSize;
            
            if (expectedMoveTicks < minProfitTicks) return 0;
            
            int contracts = BaseContracts;
            
            // Your tier system with enhancements
            if (signalQuality >= 0.85 && waveRatio >= 2.0)
                contracts = Math.Min(4, MaxContracts); // Reduced from 5 for safety
            else if (signalQuality >= 0.75 && waveRatio >= 1.6)
                contracts = Math.Min(3, MaxContracts);
            else if (signalQuality >= 0.70 && waveRatio >= 1.4)
                contracts = Math.Min(2, MaxContracts);
            else
                contracts = 1;
            
            // Additional reductions for shorts
            if (currentSignal == "Top")
            {
                contracts = Math.Max(1, contracts - 1); // Reduce short position size
                
                // Further reduction based on short performance
                if (consecutiveShortLosses >= 2)
                    contracts = 1;
            }
            
            // Global position management
            lock (GlobalPositionLock)
            {
                int totalContracts = 0;
                foreach (var kvp in GlobalPositions)
                    totalContracts += Math.Abs(kvp.Value);
                
                int available = MAX_TOTAL_CONTRACTS - totalContracts;
                contracts = Math.Min(contracts, available);
                
                if (totalContracts >= PREFERRED_MAX_CONTRACTS)
                    contracts = Math.Min(1, contracts);
            }
            
            return Math.Max(0, contracts);
        }
        #endregion
        
        #region Enhanced Position Management
        private void ManagePosition()
        {
            if (Position.MarketPosition == MarketPosition.Long)
                ManageEnhancedLongPosition();
            else if (Position.MarketPosition == MarketPosition.Short)
                ManageEnhancedShortPosition();
        }
        
        private void ManageEnhancedLongPosition()
        {
            // Enhanced long position management
            if (!target1Hit && Close[0] >= target1Price)
            {
                target1Hit = true;
                stopPrice = entryPrice + (atr[0] * 0.3); // Tighter trailing
                SetStopLoss("", CalculationMode.Price, stopPrice, false);
            }
            
            if (!target2Hit && Close[0] >= target2Price)
            {
                target2Hit = true;
                double trailStop = Close[0] - (atr[0] * 1.2); // Tighter trailing
                if (trailStop > stopPrice)
                {
                    stopPrice = trailStop;
                    SetStopLoss("", CalculationMode.Price, stopPrice, false);
                }
            }
            
            // Enhanced exit conditions
            if (ShouldExitLong())
                ExitLong();
        }
        
        private void ManageEnhancedShortPosition()
        {
            // Enhanced short position management with tighter controls
            if (!target1Hit && Close[0] <= target1Price)
            {
                target1Hit = true;
                stopPrice = entryPrice - (atr[0] * 0.2); // Very tight for shorts
                SetStopLoss("", CalculationMode.Price, stopPrice, false);
            }
            
            if (!target2Hit && Close[0] <= target2Price)
            {
                target2Hit = true;
                double trailStop = Close[0] + (atr[0] * 1.0); // Tighter trailing for shorts
                if (trailStop < stopPrice)
                {
                    stopPrice = trailStop;
                    SetStopLoss("", CalculationMode.Price, stopPrice, false);
                }
            }
            
            // Enhanced exit conditions for shorts
            if (ShouldExitShort())
                ExitShort();
        }
        
        private bool ShouldExitLong()
        {
            // Multiple exit conditions
            if (currentSignal == "Top" || currentSignal == "v") return true;
            if (aoValue < -0.001 && aoPrevValue >= 0) return true;
            if (Close[0] < ema9[0] && ema9[0] < ema9[1]) return true;
            
            // Higher timeframe reversal
            if (BarsArray[1].Count > 0 && aoValue_HT < -0.001 && aoPrevValue_HT >= 0)
                return true;
            
            return false;
        }
        
        private bool ShouldExitShort()
        {
            // More aggressive exit conditions for shorts
            if (currentSignal == "G" || currentSignal == "^") return true;
            if (aoValue > 0.001 && aoPrevValue <= 0) return true;
            if (Close[0] > ema9[0]) return true; // Exit immediately on EMA break
            
            // Higher timeframe reversal
            if (BarsArray[1].Count > 0 && aoValue_HT > 0.001 && aoPrevValue_HT <= 0)
                return true;
            
            return false;
        }
        #endregion
        
        #region Enhanced Risk Management
        private bool ShouldTrade()
        {
            // Time filter
            if (UseTimeFilter && IsOutsideTradingHours()) return false;
            
            // Daily limits
            if (todaysTrades >= MaxDailyTrades) return false;
            if (consecutiveLosses >= 3) return false;
            
            // P&L limits
            if (currentDailyPnL <= -dailyLossHardLimit) return false;
            if (currentDailyPnL >= dailyProfitHardTarget) return false;
            
            // Time between trades
            if ((DateTime.Now - lastTradeTime).TotalMinutes < 3) return false;
            
            // Short-specific checks
            if (currentSignal == "Top" && !shortTradingEnabled) return false;
            
            return true;
        }
        
        private bool IsOutsideTradingHours()
        {
            int hour = Time[0].Hour;
            return hour < StartHour || hour >= EndHour;
        }
        
        private void ResetDailyCounters()
        {
            currentDailyPnL = 0;
            todaysTrades = 0;
            consecutiveLosses = 0;
            consecutiveShortLosses = 0;
            consecutiveLongLosses = 0;
            tradingEnabled = true;
            shortTradingEnabled = true;
            
            if (ShowDebugInfo)
            {
                Print($"=== Daily Reset: {Time[0]:yyyy-MM-dd} ===");
                Print($"Account: {startingBalance:C}");
                Print($"Profit Target: {dailyProfitHardTarget:C}");
                Print($"Loss Limit: {dailyLossHardLimit:C}");
            }
        }
        #endregion
        
        #region Order Management
        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity, int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string nativeError)
        {
            if (orderState == OrderState.Filled && (order.OrderAction == OrderAction.Buy || order.OrderAction == OrderAction.SellShort))
            {
                entryPrice = averageFillPrice;
                todaysTrades++;
                lastTradeTime = time;
                target1Hit = false;
                target2Hit = false;
                
                if (ShowDebugInfo)
                    Print($"Entry: {entryPrice:F2} | Setup: {activeSetup} | Quality: {signalQuality:P0}");
            }
        }
        
        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution.IsEntry)
            {
                double atrValue = atr[0];
                
                if (marketPosition == MarketPosition.Long)
                {
                    stopPrice = price - (atrValue * ATRStopMultiplier);
                    target1Price = price + (atrValue * ATRTargetMultiplier);
                    target2Price = price + (atrValue * ATRTargetMultiplier * 2);
                    
                    SetStopLoss("", CalculationMode.Price, stopPrice, false);
                    SetProfitTarget("", CalculationMode.Price, target2Price, false);
                }
                else if (marketPosition == MarketPosition.Short)
                {
                    stopPrice = price + (atrValue * ATRStopMultiplier * 0.8); // Tighter stop for shorts
                    target1Price = price - (atrValue * ATRTargetMultiplier);
                    target2Price = price - (atrValue * ATRTargetMultiplier * 1.5); // Smaller target for shorts
                    
                    SetStopLoss("", CalculationMode.Price, stopPrice, false);
                    SetProfitTarget("", CalculationMode.Price, target2Price, false);
                }
            }
            
            // Update global positions
            UpdateGlobalPositions(marketPosition, quantity);
        }
        
        protected override void OnPositionUpdate(Position position, double averagePrice, int quantity, MarketPosition marketPosition)
        {
            if (marketPosition == MarketPosition.Flat && SystemPerformance.AllTrades.Count > 0)
            {
                Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                currentDailyPnL += lastTrade.ProfitCurrency;
                
                // Track consecutive losses by direction
                if (lastTrade.ProfitCurrency < 0)
                {
                    consecutiveLosses++;
                    if (lastTrade.Entry.Operation == Operation.Buy)
                        consecutiveLongLosses++;
                    else
                    {
                        consecutiveShortLosses++;
                        if (consecutiveShortLosses >= MaxConsecutiveShortLosses)
                            shortTradingEnabled = false;
                    }
                }
                else
                {
                    consecutiveLosses = 0;
                    consecutiveLongLosses = 0;
                    consecutiveShortLosses = 0;
                    shortTradingEnabled = true;
                }
                
                if (ShowDebugInfo)
                {
                    Print($"Trade P&L: {lastTrade.ProfitCurrency:C}");
                    Print($"Daily P&L: {currentDailyPnL:C}");
                    Print($"Consecutive Short Losses: {consecutiveShortLosses}");
                }
            }
        }
        #endregion
        
        #region Helper Methods
        private bool IsSwingHigh(int barsAgo)
        {
            if (barsAgo < 2 || barsAgo >= CurrentBar - 2) return false;
            return High[barsAgo] > High[barsAgo - 1] && High[barsAgo] > High[barsAgo + 1] &&
                   High[barsAgo] > High[barsAgo - 2] && High[barsAgo] > High[barsAgo + 2];
        }
        
        private bool IsSwingLow(int barsAgo)
        {
            if (barsAgo < 2 || barsAgo >= CurrentBar - 2) return false;
            return Low[barsAgo] < Low[barsAgo - 1] && Low[barsAgo] < Low[barsAgo + 1] &&
                   Low[barsAgo] < Low[barsAgo - 2] && Low[barsAgo] < Low[barsAgo + 2];
        }
        
        private void UpdateGlobalPositions(MarketPosition marketPosition, int quantity)
        {
            lock (GlobalPositionLock)
            {
                string instrumentName = Instrument.MasterInstrument.Name;
                
                if (marketPosition == MarketPosition.Long)
                    GlobalPositions[instrumentName] = quantity;
                else if (marketPosition == MarketPosition.Short)
                    GlobalPositions[instrumentName] = -quantity;
                else
                    GlobalPositions[instrumentName] = 0;
                
                GlobalTotalContracts = 0;
                foreach (var kvp in GlobalPositions)
                    GlobalTotalContracts += Math.Abs(kvp.Value);
            }
        }
        #endregion
        
        #region Properties
        [NinjaScriptProperty]
        [Range(0.6, 1.0)]
        [Display(Name="Signal Quality Threshold", Order=1, GroupName="Signal Settings")]
        public double SignalQualityThreshold { get; set; }
        
        [NinjaScriptProperty]
        [Range(1.0, 2.0)]
        [Display(Name="Volume Threshold", Order=2, GroupName="Signal Settings")]
        public double VolumeThreshold { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 15)]
        [Display(Name="Max Daily Trades", Order=3, GroupName="Risk Management")]
        public int MaxDailyTrades { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name="Base Contracts", Order=4, GroupName="Position Sizing")]
        public int BaseContracts { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name="Max Contracts", Order=5, GroupName="Position Sizing")]
        public int MaxContracts { get; set; }
        
        [NinjaScriptProperty]
        [Range(1.0, 4.0)]
        [Display(Name="ATR Stop Multiplier", Order=6, GroupName="Exit Settings")]
        public double ATRStopMultiplier { get; set; }
        
        [NinjaScriptProperty]
        [Range(1.0, 5.0)]
        [Display(Name="ATR Target Multiplier", Order=7, GroupName="Exit Settings")]
        public double ATRTargetMultiplier { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name="Use Time Filter", Order=8, GroupName="Time Settings")]
        public bool UseTimeFilter { get; set; }
        
        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name="Start Hour", Order=9, GroupName="Time Settings")]
        public int StartHour { get; set; }
        
        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name="End Hour", Order=10, GroupName="Time Settings")]
        public int EndHour { get; set; }
        
        [NinjaScriptProperty]
        [Range(5, 60)]
        [Display(Name="Minutes Before Close", Order=11, GroupName="Time Settings")]
        public int MinutesBeforeClose { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name="Use Higher Timeframe Confirmation", Order=12, GroupName="Enhanced Settings")]
        public bool UseHigherTimeframeConfirmation { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name="Require Volume Confirmation", Order=13, GroupName="Enhanced Settings")]
        public bool RequireVolumeConfirmation { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name="Disable Shorts During Uptrend", Order=14, GroupName="Enhanced Settings")]
        public bool DisableShortsDuringUptrend { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name="Max Consecutive Short Losses", Order=15, GroupName="Enhanced Settings")]
        public int MaxConsecutiveShortLosses { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name="Show Debug Info", Order=16, GroupName="Debug")]
        public bool ShowDebugInfo { get; set; }
        #endregion
    }
}
