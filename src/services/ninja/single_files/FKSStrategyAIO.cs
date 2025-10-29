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
    public class FKSStrategyAIO : Strategy
    {
        #region Variables
        // Account settings
        private const double ACCOUNT_SIZE = 150000; // $150k account
        
        // Global Position Management - Shared across all strategy instances
        private static readonly object GlobalPositionLock = new object();
        private static Dictionary<string, int> GlobalPositions = new Dictionary<string, int>();
        private static int GlobalTotalContracts = 0;
        private const int MAX_TOTAL_CONTRACTS = 15;      // Never exceed 15 contracts total (your specified limit)
        private const int PREFERRED_MAX_CONTRACTS = 10;  // Prefer to stay under 10 for quick trades
        private const int ABSOLUTE_MAX_CONTRACTS = 15;   // Absolute emergency max (same as MAX_TOTAL_CONTRACTS)
        
        // Profit limits
        private double dailyProfitSoftTarget = 2000;  // Soft target: reduce risk at $2000
        private double dailyProfitHardTarget = 3000;  // Hard target: stop trading at $3000
        
        // Loss limits
        private double dailyLossSoftLimit = 1000;     // Soft limit: reduce risk at -$1000
        private double dailyLossHardLimit = 1500;     // Hard limit: stop trading at -$1500
        private double dailyLossLimit;                // Legacy variable for backward compatibility
        private double dailyProfitTarget;             // Legacy variable for backward compatibility
        
        // Indicators
        private EMA ema9;
        private SMA sma20; // VWAP proxy
        private ATR atr;
        private VOL volume;
        private SMA volumeAvg;
        
        // Custom AO implementation
        private SMA aoFast;
        private SMA aoSlow;
        private double aoValue;
        private double aoPrevValue;
        
        // Support/Resistance tracking
        private double nearestSupport;
        private double nearestResistance;
        private List<double> recentHighs = new List<double>();
        private List<double> recentLows = new List<double>();
        
        // Signal tracking
        private string currentSignal = "";
        private double signalQuality = 0;
        private double waveRatio = 1.0;
        private int activeSetup = 0;
        
        // Risk Management
        private double startingBalance;
        private double currentDailyPnL;
        private int todaysTrades;
        private int consecutiveLosses;
        private bool tradingEnabled = true;
        private bool profitSoftTargetReached = false;
        private bool profitHardTargetReached = false;
        private bool lossSoftLimitReached = false;
        private bool lossHardLimitReached = false;
        private DateTime lastTradeTime = DateTime.MinValue;
        private DateTime currentDay = DateTime.MinValue;
        
        // Session Management
        private SessionIterator sessionIterator;
        private DateTime currentSessionEnd;
        private bool sessionWarningShown = false;
        
        // Position Management
        private double entryPrice;
        private double stopPrice;
        private double target1Price;
        private double target2Price;
        private double target3Price;
        private bool target1Hit = false;
        private bool target2Hit = false;
        
        // Wave Analysis
        private int bullishWaveCount = 0;
        private int bearishWaveCount = 0;
        private double bullishWaveSum = 0;
        private double bearishWaveSum = 0;
        #endregion
        
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"FKS Strategy AIO - Single file implementation with built-in indicators";
                Name = "FKSStrategyAIO";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 50;
                
                // IMPROVED SETTINGS - Balanced for better performance
                SignalQualityThreshold = 0.65;  // Restored original value for more trades
                VolumeThreshold = 1.2;           // Restored original value for more opportunities
                MaxDailyTrades = 10;             // Increased for more opportunities
                
                // Set fixed dollar amounts for limits (not percentages)
                DailyProfitSoftTarget = 2000;
                DailyProfitHardTarget = 3000;
                DailyLossSoftLimit = 1000;
                DailyLossHardLimit = 1500;
                
                // Legacy percentage properties for UI compatibility
                DailyLossLimitPercent = 1.0;  // 1500/150000 = 1%
                DailyProfitTargetPercent = 2.0; // 3000/150000 = 2%
                
                BaseContracts = 1;
                MaxContracts = 5;
                ATRStopMultiplier = 2.0;  // 2x ATR stops (your guide)
                ATRTargetMultiplier = 1.5; // 1:1.5 R:R minimum (your guide)
                UseTimeFilter = true;
                StartHour = 6;    // 6am EST - London/NY overlap for better liquidity
                EndHour = 16;     // 4pm EST - Full NY session including afternoon moves
                MinutesBeforeClose = 15; // Simple 15 min buffer
                ShowDebugInfo = false; // Keep clean
                
                // Keep enhanced controls simple
                SignalQualityMultiplier = 1.0;
                VolumeMultiplier = 1.0;
                DisableTimeFilter = false;
            }
            else if (State == State.Configure)
            {
                // Add 15-minute data series for context
                AddDataSeries(BarsPeriodType.Minute, 15);
            }
            else if (State == State.DataLoaded)
            {
                // Initialize indicators
                ema9 = EMA(9);
                sma20 = SMA(20); // VWAP proxy
                atr = ATR(14);
                volume = VOL();
                volumeAvg = SMA(volume, 20);
                
                // AO implementation (5,34)
                aoFast = SMA(Typical, 5);
                aoSlow = SMA(Typical, 34);
                
                // Initialize session iterator
                sessionIterator = new SessionIterator(Bars);
                
                // Initialize account tracking - Use fixed account size for calculations
                startingBalance = ACCOUNT_SIZE;
                
                // Set the limits to the user-defined values
                dailyProfitSoftTarget = DailyProfitSoftTarget;
                dailyProfitHardTarget = DailyProfitHardTarget;
                dailyLossSoftLimit = DailyLossSoftLimit;
                dailyLossHardLimit = DailyLossHardLimit;
                
                // Set legacy variables for backward compatibility
                dailyLossLimit = dailyLossHardLimit;
                dailyProfitTarget = dailyProfitHardTarget;
                
                if (ShowDebugInfo)
                {
                    Print($"Account Size: {startingBalance:C}");
                    Print($"Profit Targets - Soft: {dailyProfitSoftTarget:C} | Hard: {dailyProfitHardTarget:C}");
                    Print($"Loss Limits - Soft: {dailyLossSoftLimit:C} | Hard: {dailyLossHardLimit:C}");
                }
            }
            else if (State == State.Realtime)
            {
                // Reset daily counters if needed
                if (currentDay.Date != Time[0].Date)
                {
                    ResetDailyCounters();
                }
            }
        }
        
        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade) return;
            
            // CRITICAL FIX: Force close positions outside trading hours FIRST
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                int currentHour = Time[0].Hour;
                bool outsideTradingHours = currentHour < StartHour || currentHour >= EndHour;
                
                if (outsideTradingHours && !DisableTimeFilter)
                {
                    if (Position.MarketPosition == MarketPosition.Long)
                    {
                        ExitLong("Outside Hours Exit");
                        if (ShowDebugInfo)
                            Print($"Exiting LONG - Outside trading hours ({currentHour}:00)");
                    }
                    else if (Position.MarketPosition == MarketPosition.Short)
                    {
                        ExitShort("Outside Hours Exit");
                        if (ShowDebugInfo)
                            Print($"Exiting SHORT - Outside trading hours ({currentHour}:00)");
                    }
                    return;
                }
            }
            
            // Update session information
            if (Bars.IsFirstBarOfSession)
            {
                sessionIterator.GetNextSession(Time[0], true);
                currentSessionEnd = sessionIterator.ActualSessionEnd;
                sessionWarningShown = false;
                
                // Reset daily counters on new session
                if (currentDay.Date != Time[0].Date)
                {
                    ResetDailyCounters();
                    currentDay = Time[0];
                }
            }
            
            // FIXED: Better session end calculation
            TimeSpan timeToClose = TimeSpan.Zero;
            bool nearSessionEnd = false;
            
            if (sessionIterator != null && currentSessionEnd != DateTime.MinValue)
            {
                timeToClose = currentSessionEnd - Time[0];
                nearSessionEnd = timeToClose.TotalMinutes <= MinutesBeforeClose && timeToClose.TotalMinutes > 0;
            }
            else
            {
                // Fallback: use simple hour-based check
                int currentHour = Time[0].Hour;
                nearSessionEnd = currentHour >= (EndHour - 1); // 1 hour before end
            }
            
            // Close positions if near session end
            if (nearSessionEnd && Position.MarketPosition != MarketPosition.Flat)
            {
                if (!sessionWarningShown && ShowDebugInfo)
                {
                    Print($"WARNING: Closing position - {timeToClose.TotalMinutes:F0} minutes to session end");
                    sessionWarningShown = true;
                }
                
                if (Position.MarketPosition == MarketPosition.Long)
                    ExitLong("Session End Exit");
                else if (Position.MarketPosition == MarketPosition.Short)
                    ExitShort("Session End Exit");
                    
                return; // Don't process anything else
            }
            
            // Update calculations
            UpdateCalculations();
            
            // Update limit status
            UpdateLimitStatus();
            
            // Check trading conditions
            if (!ShouldTrade()) return;
            
            // Don't open new positions near session end
            if (nearSessionEnd) return;
            
            // Check hard profit target (absolute stop)
            if (profitHardTargetReached)
            {
                if (ShowDebugInfo)
                    Print($"Hard profit target reached: {currentDailyPnL:C} >= {dailyProfitHardTarget:C} - Trading stopped");
                return;
            }
            
            // Manage existing position
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                ManagePosition();
                return;
            }
            
            // Look for new signals
            CheckForSignals();
            
            // Debug output
            if (ShowDebugInfo && CurrentBar % 20 == 0)
            {
                PrintDebugInfo();
            }
        }
        
        #region Calculations
        private void UpdateCalculations()
        {
            // Calculate AO - works with any bar type
            aoPrevValue = aoValue;
            aoValue = aoFast[0] - aoSlow[0];
            
            // Update support/resistance - adjusted for different bar types
            UpdateSupportResistance();
            
            // Update wave analysis - works with Heiken Ashi and Renko
            UpdateWaveAnalysis();
            
            // Generate signal - adapted for all bar types
            GenerateSignal();
        }
        
        private void UpdateSupportResistance()
        {
            // Standard support/resistance calculation for all bar types
            double highValue = High[0];
            double lowValue = Low[0];
            
            // For Heiken Ashi, use actual high/low not smoothed values
            if (BarsPeriod.BarsPeriodType == BarsPeriodType.HeikenAshi)
            {
                // Heiken Ashi smooths values, but High/Low are still actual
                highValue = High[0];
                lowValue = Low[0];
            }
            
            // Add current bar to recent highs/lows
            recentHighs.Add(highValue);
            recentLows.Add(lowValue);
            
            // Keep only last 150 bars
            if (recentHighs.Count > 150)
            {
                recentHighs.RemoveAt(0);
                recentLows.RemoveAt(0);
            }
            
            // Find key levels
            if (recentHighs.Count >= 20)
            {
                // Simple method: use 20-bar high/low as resistance/support
                nearestResistance = MAX(High, 20)[0];
                nearestSupport = MIN(Low, 20)[0];
                
                // For Renko bars, adjust the lookback since each bar represents fixed price movement
                if (BarsPeriod.BarsPeriodType == BarsPeriodType.Renko)
                {
                    int lookback = Math.Min(10, CurrentBar); // Shorter lookback for Renko
                    nearestResistance = MAX(High, lookback)[0];
                    nearestSupport = MIN(Low, lookback)[0];
                }
                
                // Refine with actual turning points
                for (int i = 5; i < Math.Min(50, CurrentBar); i++)
                {
                    // Check for swing highs
                    if (High[i] > High[i+1] && High[i] > High[i-1] && 
                        High[i] > High[i+2] && High[i] > High[i-2])
                    {
                        if (High[i] < Close[0] && High[i] > Close[0] * 0.995)
                        {
                            nearestResistance = High[i];
                            break;
                        }
                    }
                    
                    // Check for swing lows
                    if (Low[i] < Low[i+1] && Low[i] < Low[i-1] && 
                        Low[i] < Low[i+2] && Low[i] < Low[i-2])
                    {
                        if (Low[i] > Close[0] && Low[i] < Close[0] * 1.005)
                        {
                            nearestSupport = Low[i];
                            break;
                        }
                    }
                }
            }
        }
        
        private void UpdateWaveAnalysis()
        {
            // Track bullish and bearish waves - FIXED: Proper wave accumulation
            if (Close[0] > ema9[0] && (CurrentBar < 1 || Close[1] <= ema9[1]))
            {
                // Bullish cross - finalize previous bearish wave
                if (bearishWaveSum > 0)
                {
                    bearishWaveCount++;
                    // Don't reset bearishWaveSum here - keep for ratio calculation
                }
                // Start fresh bullish wave tracking
                // bullishWaveSum = 0; // REMOVED: Don't reset, accumulate properly
            }
            else if (Close[0] < ema9[0] && (CurrentBar < 1 || Close[1] >= ema9[1]))
            {
                // Bearish cross - finalize previous bullish wave
                if (bullishWaveSum > 0)
                {
                    bullishWaveCount++;
                    // Don't reset bullishWaveSum here - keep for ratio calculation
                }
                // Start fresh bearish wave tracking
                // bearishWaveSum = 0; // REMOVED: Don't reset, accumulate properly
            }
            
            // Accumulate wave strength (keep this as-is)
            if (Close[0] > ema9[0])
            {
                bullishWaveSum += Math.Abs(Close[0] - Open[0]); // Use absolute value for better measurement
            }
            else
            {
                bearishWaveSum += Math.Abs(Open[0] - Close[0]); // Use absolute value for better measurement
            }
            
            // Calculate wave ratio - IMPROVED: Better calculation
            if (bearishWaveCount > 0 && bullishWaveCount > 0)
            {
                double avgBullWave = bullishWaveSum / Math.Max(1, bullishWaveCount);
                double avgBearWave = bearishWaveSum / Math.Max(1, bearishWaveCount);
                
                if (avgBearWave > 0)
                {
                    waveRatio = avgBullWave / avgBearWave;
                }
            }
            else
            {
                // Default ratio when insufficient data
                waveRatio = 1.0;
            }
            
            // Reset wave data every 100 bars to prevent overflow
            if (CurrentBar % 100 == 0)
            {
                bullishWaveSum /= 2;
                bearishWaveSum /= 2;
                bullishWaveCount = Math.Max(1, bullishWaveCount / 2);
                bearishWaveCount = Math.Max(1, bearishWaveCount / 2);
            }
        }
        
        private void GenerateSignal()
        {
            currentSignal = "";
            signalQuality = 0;
            
            // Heiken Ashi specific handling for better signals
            if (BarsPeriod.BarsPeriodType == BarsPeriodType.HeikenAshi)
            {
                GenerateHeikenAshiSignal();
            }
            else
            {
                GenerateStandardSignal();
            }
        }
        
        private void GenerateStandardSignal()
        {
            // SETUP 1: EMA9 + VWAP Bullish Breakout
            // Price > EMA9 > VWAP with "G" signal at support
            if (Close[0] > ema9[0] && ema9[0] > sma20[0] && 
                Low[0] <= nearestSupport * 1.001 && Close[0] > nearestSupport && 
                Close[0] > Open[0] && volume[0] > volumeAvg[0] * VolumeThreshold * VolumeMultiplier)
            {
                currentSignal = "G"; // Premium bullish breakout
                signalQuality = CalculateSignalQuality(true) * SignalQualityMultiplier;
                activeSetup = 1;
            }
            // SETUP 2: EMA9 + VWAP Bearish Breakdown  
            // Price < EMA9 < VWAP with "Top" signal at resistance
            else if (Close[0] < ema9[0] && ema9[0] < sma20[0] && 
                     High[0] >= nearestResistance * 0.999 && Close[0] < nearestResistance && 
                     Close[0] < Open[0] && volume[0] > volumeAvg[0] * VolumeThreshold * VolumeMultiplier)
            {
                currentSignal = "Top"; // Premium bearish breakdown
                signalQuality = CalculateSignalQuality(false) * SignalQualityMultiplier;
                activeSetup = 2;
            }
            // SETUP 3: VWAP Rejection Bounce
            // Price bounces off VWAP with strong rejection candle
            else if (Math.Abs(Low[0] - sma20[0]) <= atr[0] * 0.5 && Close[0] > sma20[0] && 
                     Close[0] > Open[0] && (High[0] - Close[0]) < (Close[0] - Low[0]) * 0.5)
            {
                currentSignal = "G"; // VWAP bounce
                signalQuality = CalculateSignalQuality(true) * 0.9 * SignalQualityMultiplier;
                activeSetup = 3;
            }
            else if (Math.Abs(High[0] - sma20[0]) <= atr[0] * 0.5 && Close[0] < sma20[0] && 
                     Close[0] < Open[0] && (Close[0] - Low[0]) < (High[0] - Close[0]) * 0.5)
            {
                currentSignal = "Top"; // VWAP rejection
                signalQuality = CalculateSignalQuality(false) * 0.9 * SignalQualityMultiplier;
                activeSetup = 3;
            }
            // SETUP 4: Support/Resistance + AO Zero Cross
            // Key S/R level with AO momentum confirmation
            else if (Low[0] <= nearestSupport * 1.002 && Close[0] > Open[0] &&
                     aoValue > 0.001 && aoPrevValue <= 0)
            {
                currentSignal = "G"; // S/R + AO cross bullish
                signalQuality = CalculateSignalQuality(true) * 0.85 * SignalQualityMultiplier;
                activeSetup = 4;
            }
            else if (High[0] >= nearestResistance * 0.998 && Close[0] < Open[0] &&
                     aoValue < -0.001 && aoPrevValue >= 0)
            {
                currentSignal = "Top"; // S/R + AO cross bearish  
                signalQuality = CalculateSignalQuality(false) * 0.85 * SignalQualityMultiplier;
                activeSetup = 4;
            }
            // Fallback minor signals
            else if (Low[0] > nearestSupport && Low[0] < nearestSupport * 1.02 && Close[0] > Open[0])
            {
                currentSignal = "^"; // Minor bullish
                signalQuality = CalculateSignalQuality(true) * 0.7 * SignalQualityMultiplier;
                activeSetup = 0;
            }
            else if (High[0] < nearestResistance && High[0] > nearestResistance * 0.98 && Close[0] < Open[0])
            {
                currentSignal = "v"; // Minor bearish
                signalQuality = CalculateSignalQuality(false) * 0.7 * SignalQualityMultiplier;
                activeSetup = 0;
            }
        }
        
        private void GenerateHeikenAshiSignal()
        {
            // For Heiken Ashi, we need to be more selective due to smoothing
            // Calculate HA pattern strength
            double haBodySize = Math.Abs(Close[0] - Open[0]);
            double haUpperWick = High[0] - Math.Max(Close[0], Open[0]);
            double haLowerWick = Math.Min(Close[0], Open[0]) - Low[0];
            
            // Strong bullish HA candle: no upper wick, large body
            bool strongBullishHA = Close[0] > Open[0] && 
                                  haUpperWick < haBodySize * 0.1 && 
                                  haBodySize > atr[0] * 0.5;
            
            // Strong bearish HA candle: no lower wick, large body
            bool strongBearishHA = Close[0] < Open[0] && 
                                  haLowerWick < haBodySize * 0.1 && 
                                  haBodySize > atr[0] * 0.5;
            
            // SETUP 1: EMA9 + VWAP Bullish Breakout (HA Enhanced)
            if (Close[0] > ema9[0] && ema9[0] > sma20[0] && strongBullishHA &&
                Low[0] <= nearestSupport * 1.001 && Close[0] > nearestSupport && 
                volume[0] > volumeAvg[0] * VolumeThreshold * VolumeMultiplier * 1.2) // Higher volume requirement
            {
                currentSignal = "G";
                signalQuality = CalculateSignalQuality(true) * SignalQualityMultiplier * 1.1; // Boost for strong HA
                activeSetup = 1;
            }
            // SETUP 2: EMA9 + VWAP Bearish Breakdown (HA Enhanced)
            else if (Close[0] < ema9[0] && ema9[0] < sma20[0] && strongBearishHA &&
                     High[0] >= nearestResistance * 0.999 && Close[0] < nearestResistance && 
                     volume[0] > volumeAvg[0] * VolumeThreshold * VolumeMultiplier * 1.2)
            {
                currentSignal = "Top";
                signalQuality = CalculateSignalQuality(false) * SignalQualityMultiplier * 1.1;
                activeSetup = 2;
            }
            // SETUP 3: VWAP Rejection with HA Confirmation
            else if (Math.Abs(Low[0] - sma20[0]) <= atr[0] * 0.5 && strongBullishHA && 
                     Close[0] > sma20[0])
            {
                // Check for HA trend change (previous candles were bearish)
                bool trendChange = CurrentBar > 2 && Close[1] < Open[1] && Close[2] < Open[2];
                if (trendChange)
                {
                    currentSignal = "G";
                    signalQuality = CalculateSignalQuality(true) * SignalQualityMultiplier;
                    activeSetup = 3;
                }
            }
            else if (Math.Abs(High[0] - sma20[0]) <= atr[0] * 0.5 && strongBearishHA && 
                     Close[0] < sma20[0])
            {
                // Check for HA trend change (previous candles were bullish)
                bool trendChange = CurrentBar > 2 && Close[1] > Open[1] && Close[2] > Open[2];
                if (trendChange)
                {
                    currentSignal = "Top";
                    signalQuality = CalculateSignalQuality(false) * SignalQualityMultiplier;
                    activeSetup = 3;
                }
            }
            // SETUP 4: S/R + AO with HA Pattern Recognition
            else if (Low[0] <= nearestSupport * 1.002 && strongBullishHA &&
                     aoValue > 0.001 && aoPrevValue <= 0)
            {
                // Look for HA doji patterns at support (indecision before reversal)
                bool haDojiPattern = CurrentBar > 0 && 
                                   Math.Abs(Close[1] - Open[1]) < atr[0] * 0.1;
                
                currentSignal = "G";
                signalQuality = CalculateSignalQuality(true) * SignalQualityMultiplier * 
                               (haDojiPattern ? 1.15 : 0.9);
                activeSetup = 4;
            }
            else if (High[0] >= nearestResistance * 0.998 && strongBearishHA &&
                     aoValue < -0.001 && aoPrevValue >= 0)
            {
                // Look for HA doji patterns at resistance
                bool haDojiPattern = CurrentBar > 0 && 
                                   Math.Abs(Close[1] - Open[1]) < atr[0] * 0.1;
                
                currentSignal = "Top";
                signalQuality = CalculateSignalQuality(false) * SignalQualityMultiplier * 
                               (haDojiPattern ? 1.15 : 0.9);
                activeSetup = 4;
            }
            
            // For Heiken Ashi, reduce quality of minor signals
            if (currentSignal == "")
            {
                if (Low[0] > nearestSupport && Low[0] < nearestSupport * 1.02 && strongBullishHA)
                {
                    currentSignal = "^";
                    signalQuality = CalculateSignalQuality(true) * 0.6 * SignalQualityMultiplier; // Lower quality
                    activeSetup = 0;
                }
                else if (High[0] < nearestResistance && High[0] > nearestResistance * 0.98 && strongBearishHA)
                {
                    currentSignal = "v";
                    signalQuality = CalculateSignalQuality(false) * 0.6 * SignalQualityMultiplier; // Lower quality
                    activeSetup = 0;
                }
            }
        }
        
        private double CalculateSignalQuality(bool isBullish)
        {
            double quality = 0.4; // Base quality - more conservative
            
            // PRIORITY 1: Trend alignment - Your guide's key requirement (30%)
            if (isBullish && Close[0] > ema9[0] && ema9[0] > sma20[0])
                quality += 0.30; // Perfect bullish stack
            else if (!isBullish && Close[0] < ema9[0] && ema9[0] < sma20[0])
                quality += 0.30; // Perfect bearish stack
            else if ((isBullish && Close[0] > ema9[0]) || (!isBullish && Close[0] < ema9[0]))
                quality += 0.15; // Partial alignment
            
            // PRIORITY 2: AO momentum - Critical for your guide (25%)
            if (isBullish && aoValue > 0.001 && aoPrevValue <= 0)
                quality += 0.25; // Bullish AO cross
            else if (!isBullish && aoValue < -0.001 && aoPrevValue >= 0)
                quality += 0.25; // Bearish AO cross
            else if ((isBullish && aoValue > 0) || (!isBullish && aoValue < 0))
                quality += 0.15; // AO in right direction
            else if ((isBullish && aoValue > aoPrevValue) || (!isBullish && aoValue < aoPrevValue))
                quality += 0.10; // AO momentum in right direction
            
            // PRIORITY 3: Volume confirmation - Your guide requires 1.2x+ (20%)
            double volRatio = volume[0] / volumeAvg[0];
            if (volRatio >= VolumeThreshold * VolumeMultiplier * 1.2)
                quality += 0.20; // Strong volume (your guide standard)
            else if (volRatio >= VolumeThreshold * VolumeMultiplier)
                quality += 0.15; // Good volume
            else if (volRatio > 1.0)
                quality += 0.05; // Above average
            
            // PRIORITY 4: Wave strength - Your guide uses this for tier classification (15%)
            if (waveRatio > 2.0)
                quality += 0.15; // Tier 1 setup
            else if (waveRatio > 1.5)
                quality += 0.10; // Tier 2 setup
            else if (waveRatio > 1.2)
                quality += 0.05; // Tier 3 setup
            
            // PRIORITY 5: Support/Resistance strength (10%)
            double srDistance = isBullish ? 
                Math.Abs(Low[0] - nearestSupport) / atr[0] :
                Math.Abs(High[0] - nearestResistance) / atr[0];
            
            if (srDistance < 0.25)
                quality += 0.10; // Very close to S/R
            else if (srDistance < 0.5)
                quality += 0.05; // Close to S/R
            
            return Math.Min(1.0, quality); // Cap at 100%
        }
        #endregion
        
        #region Signal Detection
        private void CheckForSignals()
        {
            // Only trade if we have a valid signal above threshold
            if (signalQuality < SignalQualityThreshold)
                return;
                
            // Only trade if volume meets minimum requirement
            if (volume[0] < volumeAvg[0] * VolumeThreshold * VolumeMultiplier)
                return;
            
            // Execute trades based on your guide's 4 bulletproof setups
            if (currentSignal == "G" && signalQuality >= SignalQualityThreshold)
            {
                // All bullish signals ("G" = strong support bounce, "^" = minor bullish)
                int contracts = CalculatePositionSize();
                if (contracts > 0)
                {
                    EnterLong(contracts, "FKS_Long_Setup" + activeSetup);
                    if (ShowDebugInfo)
                        Print($"LONG Entry: Setup {activeSetup} | Signal: {currentSignal} | Quality: {signalQuality:P0} | Wave: {waveRatio:F2} | Contracts: {contracts}");
                }
            }
            else if (currentSignal == "Top" && signalQuality >= SignalQualityThreshold)
            {
                // All bearish signals ("Top" = strong resistance rejection, "v" = minor bearish)
                int contracts = CalculatePositionSize();
                if (contracts > 0)
                {
                    EnterShort(contracts, "FKS_Short_Setup" + activeSetup);
                    if (ShowDebugInfo)
                        Print($"SHORT Entry: Setup {activeSetup} | Signal: {currentSignal} | Quality: {signalQuality:P0} | Wave: {waveRatio:F2} | Contracts: {contracts}");
                }
            }
            else if ((currentSignal == "^" || currentSignal == "v") && signalQuality >= SignalQualityThreshold * 0.9)
            {
                // Minor signals - more conservative entry
                int contracts = Math.Max(1, CalculatePositionSize() / 2); // Reduced size for minor signals
                
                if (currentSignal == "^" && contracts > 0)
                {
                    EnterLong(contracts, "FKS_Long_Minor");
                    if (ShowDebugInfo)
                        Print($"LONG Minor: Quality: {signalQuality:P0} | Wave: {waveRatio:F2} | Contracts: {contracts}");
                }
                else if (currentSignal == "v" && contracts > 0)
                {
                    EnterShort(contracts, "FKS_Short_Minor");
                    if (ShowDebugInfo)
                        Print($"SHORT Minor: Quality: {signalQuality:P0} | Wave: {waveRatio:F2} | Contracts: {contracts}");
                }
            }
        }
        
        #endregion
        
        #region Position Management
        private void ManagePosition()
        {
            if (Position.MarketPosition == MarketPosition.Long)
            {
                ManageStandardLongPosition();
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                ManageStandardShortPosition();
            }
        }
        
        private void ManageStandardLongPosition()
        {
            // Update trailing stop after target 1
            if (!target1Hit && Close[0] >= target1Price)
            {
                target1Hit = true;
                stopPrice = entryPrice + (atr[0] * 0.5); // Move stop to breakeven + buffer
                SetStopLoss("", CalculationMode.Price, stopPrice, false);
                
                if (ShowDebugInfo)
                    Print($"Target 1 hit, moving stop to breakeven: {stopPrice:F2}");
            }
            
            // Trail stop after target 2
            if (!target2Hit && Close[0] >= target2Price)
            {
                target2Hit = true;
                double trailStop = Close[0] - (atr[0] * 1.5);
                if (trailStop > stopPrice)
                {
                    stopPrice = trailStop;
                    SetStopLoss("", CalculationMode.Price, stopPrice, false);
                }
            }
            
            // Exit signals
            if (currentSignal == "Top" || currentSignal == "v" || 
                (aoValue < 0 && aoPrevValue >= 0) || // AO bearish cross
                Close[0] < ema9[0]) // Price below EMA9
            {
                ExitLong();
            }
        }
        
        private void ManageStandardShortPosition()
        {
            // Update trailing stop after target 1
            if (!target1Hit && Close[0] <= target1Price)
            {
                target1Hit = true;
                stopPrice = entryPrice - (atr[0] * 0.5); // Move stop to breakeven + buffer
                SetStopLoss("", CalculationMode.Price, stopPrice, false);
            }
            
            // Trail stop after target 2
            if (!target2Hit && Close[0] <= target2Price)
            {
                target2Hit = true;
                double trailStop = Close[0] + (atr[0] * 1.5);
                if (trailStop < stopPrice)
                {
                    stopPrice = trailStop;
                    SetStopLoss("", CalculationMode.Price, stopPrice, false);
                }
            }
            
            // Exit signals
            if (currentSignal == "G" || currentSignal == "^" || 
                (aoValue > 0 && aoPrevValue <= 0) || // AO bullish cross
                Close[0] > ema9[0]) // Price above EMA9
            {
                ExitShort();
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
                {
                    Print($"Entry filled at {entryPrice:F2} | Setup: {activeSetup} | Signal: {currentSignal} | Quality: {signalQuality:P0}");
                }
            }
        }
        
        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            // Update global position tracking
            UpdateGlobalPositions(marketPosition, quantity);
            
            if (execution.IsEntry)
            {
                // Calculate position sizing
                int contracts = quantity; // Use actual executed quantity
                
                // Set initial stops and targets
                double atrValue = atr[0];
                
                if (marketPosition == MarketPosition.Long)
                {
                    stopPrice = price - (atrValue * ATRStopMultiplier);
                    target1Price = price + (atrValue * ATRTargetMultiplier);
                    target2Price = price + (atrValue * ATRTargetMultiplier * 2);
                    target3Price = price + (atrValue * ATRTargetMultiplier * 3);
                    
                    SetStopLoss("", CalculationMode.Price, stopPrice, false);
                    SetProfitTarget("", CalculationMode.Price, target3Price, false);
                }
                else if (marketPosition == MarketPosition.Short)
                {
                    stopPrice = price + (atrValue * ATRStopMultiplier);
                    target1Price = price - (atrValue * ATRTargetMultiplier);
                    target2Price = price - (atrValue * ATRTargetMultiplier * 2);
                    target3Price = price - (atrValue * ATRTargetMultiplier * 3);
                    
                    SetStopLoss("", CalculationMode.Price, stopPrice, false);
                    SetProfitTarget("", CalculationMode.Price, target3Price, false);
                }
            }
        }
        
        protected override void OnPositionUpdate(Position position, double averagePrice, int quantity, MarketPosition marketPosition)
        {
            // Update global position tracking
            UpdateGlobalPositions(marketPosition, quantity);
            
            if (marketPosition == MarketPosition.Flat && Position.MarketPosition == MarketPosition.Flat)
            {
                // Calculate P&L
                if (SystemPerformance.AllTrades.Count > 0)
                {
                    Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                    currentDailyPnL += lastTrade.ProfitCurrency;
                    
                    if (lastTrade.ProfitCurrency < 0)
                    {
                        consecutiveLosses++;
                    }
                    else
                    {
                        consecutiveLosses = 0;
                    }
                    
                    if (ShowDebugInfo)
                    {
                        Print($"\n--- Trade Closed ---");
                        Print($"P&L: {lastTrade.ProfitCurrency:C}");
                        Print($"Daily P&L: {currentDailyPnL:C} ({(currentDailyPnL/startingBalance)*100:F2}% of account)");
                        Print($"Consecutive Losses: {consecutiveLosses}");
                        
                        // Check hard limits
                        if (lossHardLimitReached)
                        {
                            Print("*** HARD LOSS LIMIT REACHED - TRADING STOPPED ***");
                        }
                        else if (profitHardTargetReached)
                        {
                            Print($"*** HARD PROFIT TARGET REACHED: {currentDailyPnL:C} ***");
                            Print("Trading stopped for the day");
                        }
                        
                        // Check soft limits
                        if (lossSoftLimitReached && !lossHardLimitReached)
                        {
                            Print($"*** SOFT LOSS LIMIT REACHED: {currentDailyPnL:C} ***");
                            Print("Risk will be reduced");
                        }
                        
                        if (profitSoftTargetReached && !profitHardTargetReached)
                        {
                            Print($"*** SOFT PROFIT TARGET REACHED: {currentDailyPnL:C} ***");
                            Print("Risk will be reduced");
                        }
                        
                        // Progress indicators
                        if (currentDailyPnL < 0)
                        {
                            double softProgress = Math.Abs(currentDailyPnL) / dailyLossSoftLimit;
                            double hardProgress = Math.Abs(currentDailyPnL) / dailyLossHardLimit;
                            Print($"Loss Progress - Soft: {softProgress:P0} | Hard: {hardProgress:P0}");
                        }
                        else if (currentDailyPnL > 0)
                        {
                            double softProgress = currentDailyPnL / dailyProfitSoftTarget;
                            double hardProgress = currentDailyPnL / dailyProfitHardTarget;
                            Print($"Profit Progress - Soft: {softProgress:P0} | Hard: {hardProgress:P0}");
                        }
                            
                        Print("------------------\n");
                    }
                }
            }
        }
        #endregion
        
        #region Risk Management
        private bool ShouldTrade()
        {
            // Time filter - simplified to your proven London+NY session
            if (!DisableTimeFilter && UseTimeFilter)
            {
                int currentHour = Time[0].Hour;
                
                // Standard London session into NY session: 8am-3pm EST
                bool inTradingHours = (currentHour >= StartHour && currentHour < EndHour);
                
                if (!inTradingHours)
                {
                    if (ShowDebugInfo && CurrentBar % 100 == 0)
                        Print($"Outside trading hours: {currentHour:00}:00 (Trading: {StartHour:00}:00-{EndHour:00}:00)");
                    return false;
                }
            }
            
            // Daily trade limit
            if (todaysTrades >= MaxDailyTrades)
            {
                if (ShowDebugInfo && todaysTrades == MaxDailyTrades)
                    Print($"Max daily trades reached ({MaxDailyTrades})");
                return false;
            }
            
            // Consecutive losses
            if (consecutiveLosses >= 3)
            {
                if (ShowDebugInfo)
                    Print("3 consecutive losses - stopping for the day");
                tradingEnabled = false;
                return false;
            }
            
            // HARD STOPS: These completely disable trading
            if (lossHardLimitReached)
            {
                tradingEnabled = false;
                if (ShowDebugInfo)
                    Print($"*** HARD LOSS LIMIT: {currentDailyPnL:C} <= -{dailyLossHardLimit:C} ***");
                return false;
            }
            
            if (profitHardTargetReached)
            {
                tradingEnabled = false;
                if (ShowDebugInfo)
                    Print($"*** HARD PROFIT TARGET: {currentDailyPnL:C} >= {dailyProfitHardTarget:C} ***");
                return false;
            }
            
            // SOFT LIMITS: These provide warnings and reduce risk but don't stop trading
            if (lossSoftLimitReached && ShowDebugInfo)
            {
                Print($"*** SOFT LOSS LIMIT REACHED: {currentDailyPnL:C} <= -{dailyLossSoftLimit:C} ***");
                Print("Risk will be reduced but trading continues");
            }
            
            if (profitSoftTargetReached && ShowDebugInfo)
            {
                Print($"*** SOFT PROFIT TARGET REACHED: {currentDailyPnL:C} >= {dailyProfitSoftTarget:C} ***");
                Print("Risk will be reduced but trading continues");
            }
            
            // Minimum time between trades
            if ((DateTime.Now - lastTradeTime).TotalMinutes < 5)
                return false;
            
            // Don't trade if too close to session end
            if (sessionIterator != null)
            {
                TimeSpan timeToClose = currentSessionEnd - Time[0];
                if (timeToClose.TotalMinutes <= MinutesBeforeClose)
                {
                    if (ShowDebugInfo)
                        Print($"Too close to session end ({timeToClose.TotalMinutes:F0} min) - no new trades");
                    return false;
                }
            }
            
            return tradingEnabled;
        }
        
        private int CalculatePositionSize()
        {
            int contracts = BaseContracts;
            
            // GLOBAL POSITION CHECK - Critical for multi-asset trading
            lock (GlobalPositionLock)
            {
                string instrumentName = Instrument.MasterInstrument.Name;
                
                // Get current global position count
                int currentGlobalContracts = 0;
                foreach (var kvp in GlobalPositions)
                {
                    currentGlobalContracts += Math.Abs(kvp.Value);
                }
                
                // Check if we can add more contracts (CRITICAL: 15 contract max limit)
                int availableContracts = MAX_TOTAL_CONTRACTS - currentGlobalContracts;
                
                if (availableContracts <= 0)
                {
                    if (ShowDebugInfo)
                        Print($"GLOBAL LIMIT REACHED: No contracts available. Current total: {currentGlobalContracts}/{MAX_TOTAL_CONTRACTS}");
                    return 0; // No room for new positions - HARD STOP
                }
                
                // HARD LIMIT: Never exceed available contracts
                contracts = Math.Min(contracts, availableContracts);
                
                // Conservative mode when approaching your 15 contract limit
                if (currentGlobalContracts >= PREFERRED_MAX_CONTRACTS)
                {
                    contracts = Math.Min(1, contracts); // Only 1 contract when approaching limit
                    if (ShowDebugInfo)
                        Print($"CONSERVATIVE MODE: {currentGlobalContracts}/{MAX_TOTAL_CONTRACTS} contracts used. Reducing to {contracts} (15 max limit protection)");
                }
                
                // EMERGENCY BRAKE: Double-check we never exceed 15 contracts
                if (currentGlobalContracts + contracts > ABSOLUTE_MAX_CONTRACTS)
                {
                    int allowedContracts = ABSOLUTE_MAX_CONTRACTS - currentGlobalContracts;
                    contracts = Math.Max(0, allowedContracts);
                    if (ShowDebugInfo)
                        Print($"EMERGENCY BRAKE: Limiting to {contracts} contracts to stay under {ABSOLUTE_MAX_CONTRACTS} absolute max");
                }
            }
            
            // Commission-aware sizing - ensure expected profit covers commission
            double minProfitTicks = 6; // Minimum ticks to cover $5 RT commission + profit (reduced for more trades)
            double expectedMoveTicks = (atr[0] * ATRTargetMultiplier) / (Instrument.MasterInstrument.TickSize);
            
            if (expectedMoveTicks < minProfitTicks)
            {
                return 0; // Skip trade if expected move won't cover commission
            }
            
            // Your guide's exact position sizing matrix
            // TIER 1 - PREMIUM SIGNALS: 85%+ quality + 2.0x+ wave = 4-5 contracts
            if (signalQuality >= 0.85 && waveRatio >= 2.0)
            {
                contracts = Math.Min(5, MaxContracts); // Premium signals
            }
            // TIER 2 - STRONG SIGNALS: 70-85% quality + 1.5-2.0x wave = 2-3 contracts  
            else if (signalQuality >= 0.70 && waveRatio >= 1.5)
            {
                contracts = 3; // Strong signals
            }
            // TIER 3 - STANDARD SIGNALS: 60-70% quality + 1.5x+ wave = 1-2 contracts
            else if (signalQuality >= 0.60 && waveRatio >= 1.5)
            {
                contracts = 2; // Standard signals
            }
            // Below threshold signals get minimum size
            else if (signalQuality >= SignalQualityThreshold)
            {
                contracts = 1; // Minimum for qualifying signals
            }
            else
            {
                return 0; // Don't trade if below threshold
            }
            
            // Market-specific adjustments for your 5 assets
            string instrument = Instrument.MasterInstrument.Name;
            
            switch (instrument)
            {
                case "GC": // Gold - stable, can use full size
                    // No adjustment needed - gold is your most stable market
                    break;
                    
                case "NQ": // Nasdaq - volatile, reduce size
                    contracts = Math.Max(1, (contracts * 3) / 4);
                    break;
                    
                case "CL": // Crude Oil - very volatile
                    contracts = Math.Max(1, contracts / 2);
                    // Extra reduction for inventory days (Wednesday 10:30 AM)
                    if (Time[0].DayOfWeek == DayOfWeek.Wednesday && 
                        Time[0].Hour == 10 && Time[0].Minute >= 20 && Time[0].Minute <= 40)
                    {
                        contracts = 1; // Minimum size around EIA
                    }
                    break;
                    
                case "BTC": // Bitcoin - extreme volatility
                    contracts = Math.Max(1, contracts / 2);
                    // Reduce further on weekends
                    if (Time[0].DayOfWeek == DayOfWeek.Saturday || 
                        Time[0].DayOfWeek == DayOfWeek.Sunday)
                    {
                        contracts = 1;
                    }
                    break;
                    
                case "ES": // S&P 500 - moderate volatility
                    // No adjustment needed - similar to GC
                    break;
            }
            
            // Your guide's risk reductions
            // 3 consecutive losses = stop trading (handled in ShouldTrade)
            if (consecutiveLosses >= 2)
            {
                contracts = Math.Max(1, contracts / 2); // Reduce after 2 losses
            }
            else if (consecutiveLosses >= 1)
            {
                contracts = Math.Max(1, (contracts * 2) / 3); // Slight reduction after 1 loss
            }
            
            // Soft limit adjustments (your guide allows continued trading with reduced risk)
            if (lossSoftLimitReached)
            {
                contracts = Math.Max(1, contracts / 3); // Significant reduction
            }
            
            if (profitSoftTargetReached)
            {
                contracts = Math.Max(1, contracts / 2); // Moderate reduction - consider stopping
            }
            
            // Volatility adjustment (reduce in volatile markets by 50% per your guide)
            double currentATR = atr[0];
            double avgATR = SMA(atr, 20)[0]; // Shorter period for responsiveness
            if (currentATR > avgATR * 1.5)
            {
                contracts = Math.Max(1, contracts / 2); // Volatile market reduction
            }
            
            return Math.Min(contracts, MaxContracts);
        }
        
        private void UpdateLimitStatus()
        {
            // Update profit target status
            if (currentDailyPnL >= dailyProfitHardTarget)
            {
                profitHardTargetReached = true;
            }
            else if (currentDailyPnL >= dailyProfitSoftTarget)
            {
                profitSoftTargetReached = true;
            }
            
            // Update loss limit status
            if (currentDailyPnL <= -dailyLossHardLimit)
            {
                lossHardLimitReached = true;
            }
            else if (currentDailyPnL <= -dailyLossSoftLimit)
            {
                lossSoftLimitReached = true;
            }
        }
        
        private void ResetDailyCounters()
        {
            startingBalance = ACCOUNT_SIZE; // Always use fixed account size
            currentDailyPnL = 0;
            todaysTrades = 0;
            tradingEnabled = true;
            consecutiveLosses = 0; // Reset consecutive losses on new day
            
            // Reset limit status flags
            profitSoftTargetReached = false;
            profitHardTargetReached = false;
            lossSoftLimitReached = false;
            lossHardLimitReached = false;
            
            // Set the limits from user properties
            dailyProfitSoftTarget = DailyProfitSoftTarget;
            dailyProfitHardTarget = DailyProfitHardTarget;
            dailyLossSoftLimit = DailyLossSoftLimit;
            dailyLossHardLimit = DailyLossHardLimit;
            
            // Set legacy variables for backward compatibility
            dailyLossLimit = dailyLossHardLimit;
            dailyProfitTarget = dailyProfitHardTarget;
            
            if (ShowDebugInfo)
            {
                Print($"\n=== Daily Reset ===");
                Print($"Date: {Time[0]:yyyy-MM-dd}");
                Print($"Account Size: {startingBalance:C}");
                Print($"Profit Targets - Soft: {dailyProfitSoftTarget:C} | Hard: {dailyProfitHardTarget:C}");
                Print($"Loss Limits - Soft: {dailyLossSoftLimit:C} | Hard: {dailyLossHardLimit:C}");
                Print("==================\n");
            }
        }
        #endregion
        
        #region Debug
        private void PrintDebugInfo()
        {
            Print($"\n=== FKS Debug Info ===");
            Print($"Time: {Time[0]:yyyy-MM-dd HH:mm} EST");
            Print($"Bar Type: {BarsPeriod.BarsPeriodType}");
            
            // Session info
            if (sessionIterator != null)
            {
                TimeSpan timeToClose = currentSessionEnd - Time[0];
                Print($"Session End: {currentSessionEnd:HH:mm} ({timeToClose.TotalMinutes:F0} min remaining)");
            }
            
            // Trading hours status
            Print($"Trading Hours: {StartHour:00}:00 - {EndHour:00}:00 EST");
            bool inTradingHours = Time[0].Hour >= StartHour && Time[0].Hour < EndHour;
            Print($"In Trading Hours: {(inTradingHours ? "YES" : "NO")} (Current: {Time[0].Hour:00}:00)");
            
            // Signal info
            Print($"Signal: {currentSignal} | Quality: {signalQuality:P0} | Wave Ratio: {waveRatio:F2}");
            Print($"Price: {Close[0]:F2} | EMA9: {ema9[0]:F2} | VWAP: {sma20[0]:F2}");
            Print($"AO: {aoValue:F4} | Previous: {aoPrevValue:F4}");
            Print($"Volume Ratio: {(volume[0] / volumeAvg[0]):F2}");
            Print($"Support: {nearestSupport:F2} | Resistance: {nearestResistance:F2}");
            
            // Account info
            Print($"\n--- Account Status ---");
            Print($"Daily Trades: {todaysTrades}/{MaxDailyTrades}");
            Print($"Daily P&L: {currentDailyPnL:C} ({(currentDailyPnL/startingBalance)*100:F2}%)");
            
            // Profit limits
            Print($"Profit Targets - Soft: {dailyProfitSoftTarget:C} | Hard: {dailyProfitHardTarget:C}");
            if (profitSoftTargetReached)
                Print("*** SOFT PROFIT TARGET REACHED ***");
            if (profitHardTargetReached)
                Print("*** HARD PROFIT TARGET REACHED ***");
            
            // Loss limits
            Print($"Loss Limits - Soft: -{dailyLossSoftLimit:C} | Hard: -{dailyLossHardLimit:C}");
            if (lossSoftLimitReached)
                Print("*** SOFT LOSS LIMIT REACHED ***");
            if (lossHardLimitReached)
                Print("*** HARD LOSS LIMIT REACHED ***");
            
            // Status indicators
            if (!tradingEnabled)
                Print("*** TRADING DISABLED ***");
                
            Print($"===================\n");
        }
        
        private void UpdateGlobalPositions(MarketPosition marketPosition, int quantity)
        {
            lock (GlobalPositionLock)
            {
                string instrumentName = Instrument.MasterInstrument.Name;
                
                // Update the global position tracking
                if (marketPosition == MarketPosition.Long)
                {
                    GlobalPositions[instrumentName] = quantity;
                }
                else if (marketPosition == MarketPosition.Short)
                {
                    GlobalPositions[instrumentName] = -quantity;
                }
                else // Flat
                {
                    GlobalPositions[instrumentName] = 0;
                }
                
                // Calculate total contracts across all assets
                GlobalTotalContracts = 0;
                foreach (var kvp in GlobalPositions)
                {
                    GlobalTotalContracts += Math.Abs(kvp.Value);
                }
                
                // Debug info for global positions
                if (ShowDebugInfo && CurrentBar % 20 == 0)
                {
                    Print($"\n=== GLOBAL POSITIONS ===");
                    foreach (var kvp in GlobalPositions)
                    {
                        if (kvp.Value != 0)
                            Print($"{kvp.Key}: {kvp.Value} contracts");
                    }
                    Print($"Total Contracts: {GlobalTotalContracts}/{MAX_TOTAL_CONTRACTS}");
                    Print($"Available: {MAX_TOTAL_CONTRACTS - GlobalTotalContracts}");
                    Print("========================\n");
                }
            }
        }
        
        #endregion
        
        #region Properties
        [NinjaScriptProperty]
        [Range(0.5, 1.0)]
        [Display(Name="Signal Quality Threshold", Order=1, GroupName="Signal Settings")]
        public double SignalQualityThreshold { get; set; }
        
        [NinjaScriptProperty]
        [Range(1.0, 2.0)]
        [Display(Name="Volume Threshold", Order=2, GroupName="Signal Settings")]
        public double VolumeThreshold { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name="Max Daily Trades", Order=3, GroupName="Risk Management")]
        public int MaxDailyTrades { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.5, 5.0)]
        [Display(Name="Daily Loss Limit %", Order=4, GroupName="Risk Management")]
        public double DailyLossLimitPercent { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.5, 5.0)]
        [Display(Name="Daily Profit Target %", Order=5, GroupName="Risk Management")]
        public double DailyProfitTargetPercent { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name="Base Contracts", Order=6, GroupName="Position Sizing")]
        public int BaseContracts { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name="Max Contracts", Order=7, GroupName="Position Sizing")]
        public int MaxContracts { get; set; }
        
        [NinjaScriptProperty]
        [Range(1.0, 4.0)]
        [Display(Name="ATR Stop Multiplier", Order=8, GroupName="Exit Settings")]
        public double ATRStopMultiplier { get; set; }
        
        [NinjaScriptProperty]
        [Range(1.0, 5.0)]
        [Display(Name="ATR Target Multiplier", Order=9, GroupName="Exit Settings")]
        public double ATRTargetMultiplier { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name="Use Time Filter", Order=10, GroupName="Time Settings")]
        public bool UseTimeFilter { get; set; }
        
        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name="Start Hour", Order=11, GroupName="Time Settings")]
        public int StartHour { get; set; }
        
        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name="End Hour", Order=12, GroupName="Time Settings")]
        public int EndHour { get; set; }
        
        [NinjaScriptProperty]
        [Range(5, 60)]
        [Display(Name="Minutes Before Close", Order=13, GroupName="Time Settings")]
        public int MinutesBeforeClose { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name="Show Debug Info", Order=14, GroupName="Debug")]
        public bool ShowDebugInfo { get; set; }
        
        // New hard/soft limit properties
        [NinjaScriptProperty]
        [Range(500, 10000)]
        [Display(Name="Daily Profit Soft Target ($)", Order=15, GroupName="Profit/Loss Limits")]
        public double DailyProfitSoftTarget { get; set; }
        
        [NinjaScriptProperty]
        [Range(1000, 15000)]
        [Display(Name="Daily Profit Hard Target ($)", Order=16, GroupName="Profit/Loss Limits")]
        public double DailyProfitHardTarget { get; set; }
        
        [NinjaScriptProperty]
        [Range(500, 5000)]
        [Display(Name="Daily Loss Soft Limit ($)", Order=17, GroupName="Profit/Loss Limits")]
        public double DailyLossSoftLimit { get; set; }
        
        [NinjaScriptProperty]
        [Range(1000, 10000)]
        [Display(Name="Daily Loss Hard Limit ($)", Order=18, GroupName="Profit/Loss Limits")]
        public double DailyLossHardLimit { get; set; }
        
        // Enhanced control properties
        [NinjaScriptProperty]
        [Range(0.1, 5.0)]
        [Display(Name="Signal Quality Multiplier", Order=19, GroupName="Advanced Settings")]
        public double SignalQualityMultiplier { get; set; } = 1.0;
        
        [NinjaScriptProperty]
        [Range(0.1, 3.0)]
        [Display(Name="Volume Multiplier", Order=20, GroupName="Advanced Settings")]
        public double VolumeMultiplier { get; set; } = 1.0;
        
        [NinjaScriptProperty]
        [Display(Name="Disable Time Filter", Order=21, GroupName="Advanced Settings")]
        public bool DisableTimeFilter { get; set; } = false;
        #endregion
    }
}