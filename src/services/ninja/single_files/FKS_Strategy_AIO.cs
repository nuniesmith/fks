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
    public class FKS_Strategy_AIO : Strategy
    {
        #region Enumerations
        public enum MarketRegime
        {
            Trending,
            Volatile,
            Ranging,
            Accumulation,
            Distribution
        }
        
        public enum SignalTier
        {
            Premium,    // Tier 1: Quality > 85%, Wave > 2.0x
            Strong,     // Tier 2: Quality 70-85%, Wave 1.5-2.0x
            Standard,   // Tier 3: Quality 60-70%, Wave > 1.5x
            None
        }
        
        public enum SetupType
        {
            None = 0,
            EMA9_VWAP_Bullish = 1,      // Setup 1
            EMA9_VWAP_Bearish = 2,      // Setup 2
            VWAP_Rejection_Bounce = 3,   // Setup 3
            SR_AO_ZeroCross = 4         // Setup 4
        }
        
        public enum FKSSignal
        {
            None,
            G,          // Strong bullish
            Top,        // Strong bearish
            Up,         // Bullish (^)
            Down        // Bearish (v)
        }
        #endregion

        #region Variables
        // Account and position management
        private const double ACCOUNT_SIZE = 150000;
        private static readonly object GlobalPositionLock = new object();
        private static Dictionary<string, int> GlobalPositions = new Dictionary<string, int>();
        private static int GlobalTotalContracts = 0;
        private const int MAX_TOTAL_CONTRACTS = 15;
        
        // Risk management parameters FROM GUIDE
        private double signalQualityThreshold = 0.50;  // Lowered for more trades
        private double volumeThreshold = 1.0;           // Lowered for tick charts
        private int maxDailyTrades = 6;                // From guide
        private int maxConsecutiveLosses = 3;          // From guide
        private double dailyLossLimitPercent = 0.02;   // 2% from guide
        private double dailyProfitTargetPercent = 0.015; // 1.5% from guide
        private double atrStopMultiplier = 2.0;        // From guide
        private double atrTargetMultiplier = 3.0;      // From guide (minimum 1:1.5 R:R)
        private double atrTrailMultiplier = 1.5;       // From guide
        
        // Position sizing matrix FROM GUIDE
        private Dictionary<string, Dictionary<SignalTier, (int min, int max)>> contractMatrix;
        
        // Market-specific parameters
        private string instrumentType = "";
        private double tickSize;
        private double pointValue;
        
        // Enhanced VWAP indicator
        private FKS_VWAP_Indicator vwapIndicator;
        
        // Technical indicators (Primary - 1 minute)
        private EMA ema9;
        private ATR atr;
        private VOL volume;
        private SMA volumeAvg;
        
        // Higher timeframe indicators (5-minute from guide)
        private EMA ema9_HT;
        private ATR atr_HT;
        private VOL volume_HT;
        private SMA volumeAvg_HT;
        
        // Context timeframe (15-minute from guide)
        private EMA ema9_Context;
        
        // FKS AI Component simulation
        private FKSSignal currentSignal = FKSSignal.None;
        private double signalQuality = 0;
        private double waveRatio = 0;
        private double nearestSupport = 0;
        private double nearestResistance = 0;
        private bool isAtSupport = false;
        private bool isAtResistance = false;
        
        // FKS AO Component (Awesome Oscillator)
        private SMA aoFast;
        private SMA aoSlow;
        private SMA aoFast_HT;
        private SMA aoSlow_HT;
        private double aoValue;
        private double aoPrevValue;
        private double aoValue_HT;
        private double aoPrevValue_HT;
        private bool aoZeroCross = false;
        private bool aoSignalCross = false;
        
        // FKS Info Component (Market Regime)
        private MarketRegime currentRegime = MarketRegime.Trending;
        private MarketRegime previousRegime = MarketRegime.Trending;
        private double regimeMultiplier = 1.0;
        private int regimeConfirmationBars = 0;
        private const int REGIME_CONFIRMATION_REQUIRED = 3;
        
        // Signal tracking
        private SignalTier currentTier = SignalTier.None;
        private SetupType activeSetup = SetupType.None;
        private int componentAgreement = 0;
        
        // Risk management state
        private double currentDailyPnL = 0;
        private int todaysTrades = 0;
        private int consecutiveLosses = 0;
        private int consecutiveShortLosses = 0;
        private bool tradingEnabled = true;
        private DateTime currentDay = DateTime.MinValue;
        private int barsSinceExit = 0;
        private const int REENTRY_COOLDOWN = 5;
        
        // Position management
        private double entryPrice = 0;
        private double stopLoss = 0;
        private double target1Price = 0;
        private double target2Price = 0;
        private double trailingStop = 0;
        private bool target1Hit = false;
        private int barsInTrade = 0;
        private int positionContracts = 0;
        
        // Debug settings
        private bool debugMode = true;
        private int debugBarInterval = 50;
        
        // Market clustering data
        private List<double> recentReturns = new List<double>();
        private List<double> recentVolatility = new List<double>();
        private List<double> recentMomentum = new List<double>();
        private int clusteringPeriod = 20;
        #endregion

        #region State Management
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"FKS Strategy AIO - Complete implementation with all setups from guide";
                Name = "FKS_Strategy_AIO";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 900; // 15 minutes before close (from guide)
                BarsRequiredToTrade = 200;       // From guide
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                
                // Initialize contract matrix from guide
                InitializeContractMatrix();
            }
            else if (State == State.Configure)
            {
                // Add data series as specified in guide
                AddDataSeries(BarsPeriodType.Minute, 5);   // Higher timeframe confirmation
                AddDataSeries(BarsPeriodType.Minute, 15);  // Context timeframe
            }
            else if (State == State.DataLoaded)
            {
                InitializeIndicators();
                DetectInstrumentType();
                ResetDailyCounters();
                
                if (debugMode) 
                {
                    ClearOutputWindow();
                    Print($"=== FKS Strategy Initialized ===");
                    Print($"Instrument: {instrumentType}");
                    Print($"Signal Quality Threshold: {signalQualityThreshold}");
                    Print($"Volume Threshold: {volumeThreshold}x");
                }
            }
        }
        
        private void InitializeIndicators()
        {
            // Primary timeframe indicators (1-minute)
            vwapIndicator = new FKS_VWAP_Indicator();
            ema9 = EMA(9);
            atr = ATR(14);
            volume = VOL();
            volumeAvg = SMA(volume, 20);
            
            // Higher timeframe indicators (5-minute)
            if (BarsArray.Length > 1)
            {
                ema9_HT = EMA(BarsArray[1], 9);
                atr_HT = ATR(BarsArray[1], 14);
                volume_HT = VOL(BarsArray[1]);
                volumeAvg_HT = SMA(volume_HT, 20);
            }
            
            // Context timeframe (15-minute)
            if (BarsArray.Length > 2)
            {
                ema9_Context = EMA(BarsArray[2], 9);
            }
            
            // Awesome Oscillator components
            aoFast = SMA(Median, 5);
            aoSlow = SMA(Median, 34);
            if (BarsArray.Length > 1)
            {
                aoFast_HT = SMA(Medians[1], 5);
                aoSlow_HT = SMA(Medians[1], 34);
            }
        }
        
        private void InitializeContractMatrix()
        {
            // Position sizing matrix from guide
            contractMatrix = new Dictionary<string, Dictionary<SignalTier, (int min, int max)>>
            {
                ["GC"] = new Dictionary<SignalTier, (int min, int max)>
                {
                    [SignalTier.Premium] = (4, 5),
                    [SignalTier.Strong] = (2, 3),
                    [SignalTier.Standard] = (1, 2)
                },
                ["NQ"] = new Dictionary<SignalTier, (int min, int max)>
                {
                    [SignalTier.Premium] = (3, 4),
                    [SignalTier.Strong] = (2, 2),
                    [SignalTier.Standard] = (1, 1)
                },
                ["CL"] = new Dictionary<SignalTier, (int min, int max)>
                {
                    [SignalTier.Premium] = (4, 5),
                    [SignalTier.Strong] = (2, 3),
                    [SignalTier.Standard] = (1, 2)
                }
            };
        }
        
        private void DetectInstrumentType()
        {
            string instrumentName = Instrument.MasterInstrument.Name.ToUpper();
            
            if (instrumentName.Contains("GC") || instrumentName.Contains("GOLD"))
                instrumentType = "GC";
            else if (instrumentName.Contains("NQ") || instrumentName.Contains("NASDAQ"))
                instrumentType = "NQ";
            else if (instrumentName.Contains("CL") || instrumentName.Contains("CRUDE"))
                instrumentType = "CL";
            else
                instrumentType = "GC"; // Default
                
            tickSize = Instrument.MasterInstrument.TickSize;
            pointValue = Instrument.MasterInstrument.PointValue;
        }
        #endregion

        #region Main Trading Logic
        protected override void OnBarUpdate()
        {
            try
            {
                // Skip if not enough data
                if (CurrentBars[0] < BarsRequiredToTrade) return;
                if (BarsInProgress != 0) return; // Only process primary series
                
                // Check if all indicators are properly initialized
                if (vwapIndicator == null || ema9 == null || atr == null || 
                    volume == null || volumeAvg == null || aoFast == null || aoSlow == null)
                {
                    if (debugMode)
                        Print($"[{Time[0]}] Waiting for indicators to initialize...");
                    return;
                }
                
                // Additional safety checks
                if (CurrentBar < 20 || Volume[0] <= 0 || Close[0] <= 0)
                    return;
                
                // Check for new trading day
                if (Time[0].Date != currentDay)
                {
                    currentDay = Time[0].Date;
                    ResetDailyCounters();
                }
                
                // Update all components
                UpdateFKSComponents();
                UpdateMarketRegime();
                UpdateTechnicalIndicators();
                
                // Check if we should continue trading
                if (!ShouldContinueTrading())
                {
                    if (debugMode && CurrentBar % debugBarInterval == 0)
                        Print($"Trading disabled - Daily PnL: {currentDailyPnL:C}, Trades: {todaysTrades}");
                    return;
                }
                
                // Manage existing position
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    ManagePosition();
                    return;
                }
                
                // Update bars since exit
                barsSinceExit++;
                
                // Check for new signals
                if (barsSinceExit >= REENTRY_COOLDOWN)
                {
                    CheckAllSetups();
                }
                
                // Debug logging
                if (debugMode && CurrentBar % debugBarInterval == 0)
                {
                    LogStrategyState();
                }
            }
            catch (Exception ex)
            {
                Print($"Error in OnBarUpdate: {ex.Message}");
            }
        }
        
        private void UpdateFKSComponents()
        {
            // Update FKS_AI component (signal detection)
            UpdateFKSAI();
            
            // Update FKS_AO component (Awesome Oscillator)
            UpdateFKSAO();
            
            // Update FKS_Dashboard component (handled in UpdateMarketRegime)
            
            // Calculate component agreement (must have 2 of 3)
            componentAgreement = 0;
            if (currentSignal != FKSSignal.None) componentAgreement++;
            if (aoValue > 0 && currentSignal == FKSSignal.G || currentSignal == FKSSignal.Up) componentAgreement++;
            if (aoValue < 0 && currentSignal == FKSSignal.Top || currentSignal == FKSSignal.Down) componentAgreement++;
            if (currentRegime == MarketRegime.Trending) componentAgreement++;
        }
        
        private void UpdateFKSAI()
        {
            try
            {
                // Safety checks
                if (vwapIndicator == null || ema9 == null || atr == null)
                    return;
                
                // Simulate FKS_AI signal detection
                double vwap = vwapIndicator.GetVWAP();
                double ema = ema9[0];
                
                // Calculate support/resistance levels
                UpdateSupportResistance();
                
                // Detect signals based on price action
                DetectFKSSignals();
                
                // Calculate signal quality
                CalculateSignalQuality();
                
                // Calculate wave ratio
                CalculateWaveRatio();
            }
            catch (Exception ex)
            {
                Print($"Error in UpdateFKSAI: {ex.Message}");
            }
        }
        
        private void UpdateSupportResistance()
        {
            try
            {
                if (atr == null || CurrentBar < 20)
                    return;
                
                // Simple S/R detection - can be enhanced
                int lookback = Math.Min(150, CurrentBar); // From guide
                
                nearestSupport = MIN(Low, lookback)[0];
                nearestResistance = MAX(High, lookback)[0];
                
                // Check if price is at support/resistance
                double buffer = atr[0] * 0.3;
                isAtSupport = Math.Abs(Low[0] - nearestSupport) < buffer;
                isAtResistance = Math.Abs(High[0] - nearestResistance) < buffer;
            }
            catch (Exception ex)
            {
                Print($"Error in UpdateSupportResistance: {ex.Message}");
            }
        }
        
        private void DetectFKSSignals()
        {
            currentSignal = FKSSignal.None;
            
            // G signal - Strong bullish at support
            if (isAtSupport && Close[0] > Open[0] && Close[0] > Close[1])
            {
                double bodySize = Math.Abs(Close[0] - Open[0]);
                double wickSize = High[0] - Close[0];
                
                if (bodySize > wickSize * 2) // Strong bullish candle
                {
                    currentSignal = FKSSignal.G;
                }
            }
            
            // Top signal - Strong bearish at resistance
            else if (isAtResistance && Close[0] < Open[0] && Close[0] < Close[1])
            {
                double bodySize = Math.Abs(Close[0] - Open[0]);
                double wickSize = Close[0] - Low[0];
                
                if (bodySize > wickSize * 2) // Strong bearish candle
                {
                    currentSignal = FKSSignal.Top;
                }
            }
            
            // ^ signal - Bullish reversal pattern
            else if (Low[0] < Low[1] && Close[0] > High[1])
            {
                currentSignal = FKSSignal.Up;
            }
            
            // v signal - Bearish reversal pattern
            else if (High[0] > High[1] && Close[0] < Low[1])
            {
                currentSignal = FKSSignal.Down;
            }
        }
        
        private void CalculateSignalQuality()
        {
            try
            {
                if (currentSignal == FKSSignal.None)
                {
                    signalQuality = 0.0;
                    return;
                }
                
                if (vwapIndicator == null || ema9 == null || volume == null || volumeAvg == null)
                {
                    signalQuality = 0.0;
                    return;
                }
                
                signalQuality = 0.2; // Base quality for having a signal
                
                // Price structure alignment (30%)
                double vwap = vwapIndicator.GetVWAP();
                if ((currentSignal == FKSSignal.G || currentSignal == FKSSignal.Up) && Close[0] > ema9[0] && ema9[0] > vwap)
                    signalQuality += 0.30;
                else if ((currentSignal == FKSSignal.Top || currentSignal == FKSSignal.Down) && Close[0] < ema9[0] && ema9[0] < vwap)
                    signalQuality += 0.30;
                
                // Volume confirmation (25%)
                double volRatio = volume[0] / volumeAvg[0];
                if (volRatio >= volumeThreshold)
                    signalQuality += 0.25;
                else if (volRatio >= volumeThreshold * 0.8)
                    signalQuality += 0.15;
                
                // Momentum alignment (20%)
                if ((currentSignal == FKSSignal.G || currentSignal == FKSSignal.Up) && aoValue > 0 && aoValue > aoPrevValue)
                    signalQuality += 0.20;
                else if ((currentSignal == FKSSignal.Top || currentSignal == FKSSignal.Down) && aoValue < 0 && aoValue < aoPrevValue)
                    signalQuality += 0.20;
                
                // Support/Resistance confluence (15%)
                if (isAtSupport && (currentSignal == FKSSignal.G || currentSignal == FKSSignal.Up))
                    signalQuality += 0.15;
                else if (isAtResistance && (currentSignal == FKSSignal.Top || currentSignal == FKSSignal.Down))
                    signalQuality += 0.15;
                
                // Market regime bonus (10%)
                if (currentRegime == MarketRegime.Trending)
                    signalQuality += 0.10;
                
                signalQuality = Math.Min(1.0, signalQuality);
            }
            catch (Exception ex)
            {
                Print($"Error in CalculateSignalQuality: {ex.Message}");
                signalQuality = 0.0;
            }
        }
        
        private void CalculateWaveRatio()
        {
            // Calculate wave ratio based on recent price swings
            if (CurrentBar < 20)
            {
                waveRatio = 1.0;
                return;
            }
            
            double recentHigh = MAX(High, 10)[0];
            double recentLow = MIN(Low, 10)[0];
            double currentWave = recentHigh - recentLow;
            
            double previousHigh = MAX(High, 10)[10];
            double previousLow = MIN(Low, 10)[10];
            double previousWave = previousHigh - previousLow;
            
            if (previousWave > 0)
                waveRatio = currentWave / previousWave;
            else
                waveRatio = 1.0;
        }
        
        private void UpdateFKSAO()
        {
            try
            {
                if (aoFast == null || aoSlow == null)
                    return;
                
                // Calculate Awesome Oscillator values
                aoPrevValue = aoValue;
                aoValue = aoFast[0] - aoSlow[0];
                
                if (BarsArray.Length > 1 && BarsArray[1].Count > 0 && aoFast_HT != null && aoSlow_HT != null)
                {
                    aoPrevValue_HT = aoValue_HT;
                    aoValue_HT = aoFast_HT[0] - aoSlow_HT[0];
                }
                
                // Check for zero cross
                aoZeroCross = (aoValue > 0 && aoPrevValue <= 0) || (aoValue < 0 && aoPrevValue >= 0);
                
                // Check for signal line cross (simplified - would need actual signal line)
                aoSignalCross = Math.Abs(aoValue) > Math.Abs(aoPrevValue) * 1.1;
            }
            catch (Exception ex)
            {
                Print($"Error in UpdateFKSAO: {ex.Message}");
            }
        }
        
        private void UpdateMarketRegime()
        {
            // Update clustering data
            UpdateClusteringData();
            
            // Classify market regime
            ClassifyMarketRegime();
            
            // Update regime multiplier
            UpdateRegimeMultiplier();
        }
        
        private void UpdateClusteringData()
        {
            if (CurrentBar < clusteringPeriod) return;
            
            // Calculate returns
            double returns = (Close[0] - Close[1]) / Close[1];
            recentReturns.Add(returns);
            if (recentReturns.Count > clusteringPeriod)
                recentReturns.RemoveAt(0);
            
            // Calculate volatility
            double volatility = StdDev(Close, clusteringPeriod)[0] / Close[0];
            recentVolatility.Add(volatility);
            if (recentVolatility.Count > clusteringPeriod)
                recentVolatility.RemoveAt(0);
            
            // Calculate momentum
            double momentum = (Close[0] - Close[clusteringPeriod]) / Close[clusteringPeriod];
            recentMomentum.Add(momentum);
            if (recentMomentum.Count > clusteringPeriod)
                recentMomentum.RemoveAt(0);
        }
        
        private void ClassifyMarketRegime()
        {
            if (recentReturns.Count < clusteringPeriod) return;
            
            double avgReturns = recentReturns.Average();
            double avgVolatility = recentVolatility.Average();
            double avgMomentum = recentMomentum.Average();
            double avgVolume = volume[0] / volumeAvg[0];
            
            // Classify based on thresholds (simplified K-means)
            MarketRegime newRegime = MarketRegime.Trending;
            
            if (avgVolatility > 0.025)
            {
                newRegime = MarketRegime.Volatile;
            }
            else if (Math.Abs(avgMomentum) < 0.01 && avgVolatility < 0.005)
            {
                newRegime = MarketRegime.Ranging;
            }
            else if (avgVolume > 1.4 && avgVolatility < 0.01 && Math.Abs(avgMomentum) < 0.01)
            {
                newRegime = MarketRegime.Accumulation;
            }
            else if (avgVolume > 1.6 && avgMomentum < -0.01)
            {
                newRegime = MarketRegime.Distribution;
            }
            else
            {
                newRegime = MarketRegime.Trending;
            }
            
            // Only change regime if confirmed for multiple bars
            if (newRegime == currentRegime)
            {
                regimeConfirmationBars = 0;
            }
            else if (newRegime == previousRegime)
            {
                regimeConfirmationBars++;
                if (regimeConfirmationBars >= REGIME_CONFIRMATION_REQUIRED)
                {
                    if (debugMode)
                        Print($"*** REGIME CHANGE: {currentRegime} -> {newRegime} ***");
                    
                    currentRegime = newRegime;
                    regimeConfirmationBars = 0;
                }
            }
            else
            {
                previousRegime = newRegime;
                regimeConfirmationBars = 1;
            }
        }
        
        private void UpdateRegimeMultiplier()
        {
            // Apply regime-based position size adjustments from guide
            switch (currentRegime)
            {
                case MarketRegime.Volatile:
                    regimeMultiplier = 0.5; // -50% from guide
                    break;
                case MarketRegime.Ranging:
                    regimeMultiplier = 0.7; // -30% from guide
                    break;
                case MarketRegime.Trending:
                default:
                    regimeMultiplier = 1.0;
                    break;
            }
        }
        
        private void UpdateTechnicalIndicators()
        {
            // All technical indicators are updated automatically by NinjaTrader
            // This method is for any custom calculations
        }
        
        private void CheckAllSetups()
        {
            // Check all 4 bulletproof setups from guide
            
            // Setup 1: EMA9 + VWAP Bullish Breakout
            if (CheckSetup1_Bullish())
            {
                ExecuteTrade(true, SetupType.EMA9_VWAP_Bullish);
                return;
            }
            
            // Setup 2: EMA9 + VWAP Bearish Breakdown
            if (CheckSetup2_Bearish())
            {
                ExecuteTrade(false, SetupType.EMA9_VWAP_Bearish);
                return;
            }
            
            // Setup 3: VWAP Rejection Bounce
            if (CheckSetup3_VWAPBounce())
            {
                ExecuteTrade(true, SetupType.VWAP_Rejection_Bounce);
                return;
            }
            
            // Setup 4: Support/Resistance + AO Zero Cross
            if (CheckSetup4_SRWithAO())
            {
                bool isLong = aoValue > 0;
                ExecuteTrade(isLong, SetupType.SR_AO_ZeroCross);
                return;
            }
        }
        
        private bool CheckSetup1_Bullish()
        {
            // Most conditions must be met (relaxed from guide)
            if (Close[0] <= ema9[0]) return false;
            if (ema9[0] <= vwapIndicator.GetVWAP()) return false;
            if (currentSignal != FKSSignal.G && currentSignal != FKSSignal.Up) return false; // Allow Up signal too
            if (aoValue <= 0) return false; // Removed aoSignalCross requirement
            if (volume[0] < volumeAvg[0] * volumeThreshold) return false;
            if (signalQuality < signalQualityThreshold) return false;
            
            // Check for recent swing high breakout
            double swingHigh = MAX(High, 10)[1];
            if (Close[0] > swingHigh && Close[1] <= swingHigh)
            {
                if (debugMode) Print($"Setup 1 Bullish triggered - Quality: {signalQuality:F2}");
                return true;
            }
            
            return false;
        }
        
        private bool CheckSetup2_Bearish()
        {
            // Most conditions must be met (relaxed from guide)
            if (Close[0] >= ema9[0]) return false;
            if (ema9[0] >= vwapIndicator.GetVWAP()) return false;
            if (currentSignal != FKSSignal.Top && currentSignal != FKSSignal.Down) return false; // Allow Down signal too
            if (aoValue >= 0) return false; // Removed aoSignalCross requirement
            if (volume[0] < volumeAvg[0] * volumeThreshold) return false;
            if (signalQuality < signalQualityThreshold) return false;
            
            // Additional short safety checks
            if (consecutiveShortLosses >= 2) return false;
            
            // Check for recent swing low breakdown
            double swingLow = MIN(Low, 10)[1];
            if (Close[0] < swingLow && Close[1] >= swingLow)
            {
                if (debugMode) Print($"Setup 2 Bearish triggered - Quality: {signalQuality:F2}");
                return true;
            }
            
            return false;
        }
        
        private bool CheckSetup3_VWAPBounce()
        {
            double vwap = vwapIndicator.GetVWAP();
            double distance = Math.Abs(Close[0] - vwap);
            
            // Price must be near VWAP
            if (distance > atr[0] * 0.5) return false;
            
            // Must have G signal and bounce pattern
            if (currentSignal != FKSSignal.G) return false;
            
            // Check for AO divergence (simplified)
            bool bullishDivergence = Low[0] < Low[5] && aoValue > aoValue - 5;
            if (!bullishDivergence) return false;
            
            // Strong support confluence
            if (!isAtSupport) return false;
            
            // High-quality rejection candle
            bool isHammer = (Close[0] > Open[0]) && 
                           ((High[0] - Close[0]) < (Close[0] - Open[0]) * 0.3) &&
                           ((Open[0] - Low[0]) > (Close[0] - Open[0]) * 2);
            
            if (isHammer)
            {
                if (debugMode) Print($"Setup 3 VWAP Bounce triggered - Quality: {signalQuality:F2}");
                return true;
            }
            
            return false;
        }
        
        private bool CheckSetup4_SRWithAO()
        {
            // Must be at key S/R level
            if (!isAtSupport && !isAtResistance) return false;
            
            // AO must cross zero
            if (!aoZeroCross) return false;
            
            // Signal quality must be higher for this setup
            if (signalQuality < signalQualityThreshold * 1.1) return false;
            
            // Clear breakout with volume
            if (volume[0] < volumeAvg[0] * volumeThreshold) return false;
            
            // Direction based on AO
            bool isLong = aoValue > 0 && isAtSupport;
            bool isShort = aoValue < 0 && isAtResistance;
            
            if (isLong || (isShort && consecutiveShortLosses < 2))
            {
                if (debugMode) Print($"Setup 4 S/R + AO triggered - Quality: {signalQuality:F2}");
                return true;
            }
            
            return false;
        }
        #endregion

        #region Trade Execution
        private void ExecuteTrade(bool isLong, SetupType setup)
        {
            // Determine signal tier
            DetermineSignalTier();
            
            // Get position size
            int contracts = CalculatePositionSize();
            if (contracts == 0) return;
            
            // Calculate stops and targets
            CalculateStopsAndTargets(isLong);
            
            // Check global position limits
            lock (GlobalPositionLock)
            {
                if (GlobalTotalContracts + contracts > MAX_TOTAL_CONTRACTS)
                {
                    contracts = Math.Max(0, MAX_TOTAL_CONTRACTS - GlobalTotalContracts);
                    if (contracts == 0)
                    {
                        if (debugMode) Print("Global position limit reached - trade skipped");
                        return;
                    }
                }
                
                GlobalTotalContracts += contracts;
                GlobalPositions[instrumentType] = contracts;
            }
            
            // Log trade entry
            LogTradeEntry(isLong, setup, contracts);
            
            // Execute trade
            if (isLong)
            {
                EnterLong(contracts, $"FKS_S{(int)setup}_L");
            }
            else
            {
                EnterShort(contracts, $"FKS_S{(int)setup}_S");
            }
            
            // Update state
            activeSetup = setup;
            entryPrice = Close[0];
            positionContracts = contracts;
            barsInTrade = 0;
            target1Hit = false;
            todaysTrades++;
            barsSinceExit = 0;
        }
        
        private void DetermineSignalTier()
        {
            // Determine tier based on guide criteria (relaxed for more trades)
            bool hasAOCross = aoZeroCross || (aoSignalCross && Math.Abs(aoValue) > 0);
            
            // TIER 1 - PREMIUM SIGNALS (relaxed requirements)
            if ((currentSignal == FKSSignal.G || currentSignal == FKSSignal.Top) && 
                hasAOCross && 
                signalQuality > 0.75 && 
                waveRatio > 1.8)
            {
                currentTier = SignalTier.Premium;
            }
            // TIER 2 - STRONG SIGNALS (relaxed requirements)
            else if ((currentSignal == FKSSignal.G || currentSignal == FKSSignal.Up || 
                      currentSignal == FKSSignal.Top || currentSignal == FKSSignal.Down) &&
                     (aoSignalCross || Math.Abs(aoValue) > 0) &&
                     signalQuality >= 0.60 && signalQuality <= 0.75 &&
                     waveRatio >= 1.2)
            {
                currentTier = SignalTier.Strong;
            }
            // TIER 3 - STANDARD SIGNALS (relaxed requirements)
            else if ((currentSignal == FKSSignal.Up || currentSignal == FKSSignal.Down || 
                      currentSignal == FKSSignal.G || currentSignal == FKSSignal.Top) &&
                     signalQuality >= 0.50 && signalQuality <= 0.60 &&
                     waveRatio > 1.0)
            {
                currentTier = SignalTier.Standard;
            }
            else
            {
                currentTier = SignalTier.None;
            }
        }
        
        private int CalculatePositionSize()
        {
            if (currentTier == SignalTier.None) return 0;
            
            // Get range from matrix
            var sizeRange = contractMatrix[instrumentType][currentTier];
            
            // Start with minimum size
            int contracts = sizeRange.min;
            
            // Scale up based on signal quality within tier
            double qualityWithinTier = 0;
            switch (currentTier)
            {
                case SignalTier.Premium:
                    qualityWithinTier = (signalQuality - 0.85) / 0.15; // 0.85 to 1.0
                    break;
                case SignalTier.Strong:
                    qualityWithinTier = (signalQuality - 0.70) / 0.15; // 0.70 to 0.85
                    break;
                case SignalTier.Standard:
                    qualityWithinTier = (signalQuality - 0.60) / 0.10; // 0.60 to 0.70
                    break;
            }
            
            // Add contracts based on quality within tier
            int additionalContracts = (int)(qualityWithinTier * (sizeRange.max - sizeRange.min));
            contracts = sizeRange.min + additionalContracts;
            
            // Apply regime multiplier
            contracts = (int)Math.Round(contracts * regimeMultiplier);
            
            // Apply consecutive loss reduction
            if (consecutiveLosses >= 2)
                contracts = Math.Max(1, contracts / 2);
            
            // Ensure within bounds
            contracts = Math.Max(sizeRange.min, Math.Min(contracts, sizeRange.max));
            
            return contracts;
        }
        
        private void CalculateStopsAndTargets(bool isLong)
        {
            double atrValue = atr[0];
            
            // Adjust stop multiplier based on regime
            double stopMultiplier = atrStopMultiplier;
            if (currentRegime == MarketRegime.Volatile)
                stopMultiplier = 2.5;
            else if (currentRegime == MarketRegime.Ranging)
                stopMultiplier = 1.8;
            
            if (isLong)
            {
                stopLoss = Close[0] - (atrValue * stopMultiplier);
                target1Price = Close[0] + (atrValue * atrTargetMultiplier);
                target2Price = Close[0] + (atrValue * atrTargetMultiplier * 1.5);
            }
            else
            {
                stopLoss = Close[0] + (atrValue * stopMultiplier);
                target1Price = Close[0] - (atrValue * atrTargetMultiplier);
                target2Price = Close[0] - (atrValue * atrTargetMultiplier * 1.5);
            }
            
            trailingStop = stopLoss;
        }
        
        private void LogTradeEntry(bool isLong, SetupType setup, int contracts)
        {
            if (!debugMode) return;
            
            string direction = isLong ? "LONG" : "SHORT";
            string signal = currentSignal.ToString();
            
            Print($"\n*** {direction} ENTRY - Setup {(int)setup}: {setup} ***");
            Print($"Time: {Time[0]}, Price: {Close[0]:F2}");
            Print($"Signal: {signal}, Quality: {signalQuality:P1}, Wave: {waveRatio:F1}x");
            Print($"Tier: {currentTier}, Contracts: {contracts}");
            Print($"Stop: {stopLoss:F2}, Target1: {target1Price:F2}, Target2: {target2Price:F2}");
            Print($"Regime: {currentRegime}, Multiplier: {regimeMultiplier:F1}");
            Print($"AO: {aoValue:F4}, Volume: {volume[0] / volumeAvg[0]:F1}x");
            Print($"Component Agreement: {componentAgreement}/3");
        }
        #endregion

        #region Position Management
        private void ManagePosition()
        {
            barsInTrade++;
            
            // Check stop loss
            if (CheckStopLoss())
            {
                ExitPosition("StopLoss", false);
                return;
            }
            
            // Check targets and trail
            if (!target1Hit)
            {
                CheckTarget1();
            }
            else
            {
                UpdateTrailingStop();
                CheckTarget2();
            }
            
            // Check for adverse exit signals
            if (CheckAdverseExit())
            {
                ExitPosition("AdverseSignal", true);
                return;
            }
            
            // Time-based exit (15 minutes before close)
            CheckTimeExit();
        }
        
        private bool CheckStopLoss()
        {
            if (Position.MarketPosition == MarketPosition.Long && Low[0] <= stopLoss)
            {
                if (debugMode) Print($"Long stop hit at {Low[0]:F2}");
                return true;
            }
            else if (Position.MarketPosition == MarketPosition.Short && High[0] >= stopLoss)
            {
                if (debugMode) Print($"Short stop hit at {High[0]:F2}");
                return true;
            }
            
            return false;
        }
        
        private void CheckTarget1()
        {
            if (Position.MarketPosition == MarketPosition.Long && High[0] >= target1Price)
            {
                // Exit half position
                int exitQuantity = positionContracts / 2;
                ExitLong(exitQuantity, "Target1", "");
                target1Hit = true;
                
                // Move stop to breakeven
                stopLoss = entryPrice;
                trailingStop = entryPrice;
                
                if (debugMode) Print($"Target 1 hit at {target1Price:F2}, {exitQuantity} contracts exited, stop moved to breakeven");
            }
            else if (Position.MarketPosition == MarketPosition.Short && Low[0] <= target1Price)
            {
                // Exit half position
                int exitQuantity = positionContracts / 2;
                ExitShort(exitQuantity, "Target1", "");
                target1Hit = true;
                
                // Move stop to breakeven
                stopLoss = entryPrice;
                trailingStop = entryPrice;
                
                if (debugMode) Print($"Target 1 hit at {target1Price:F2}, {exitQuantity} contracts exited, stop moved to breakeven");
            }
        }
        
        private void UpdateTrailingStop()
        {
            double atrValue = atr[0];
            double trailDistance = atrValue * atrTrailMultiplier;
            
            if (Position.MarketPosition == MarketPosition.Long)
            {
                double newTrail = Close[0] - trailDistance;
                if (newTrail > trailingStop && newTrail > entryPrice)
                {
                    trailingStop = newTrail;
                    stopLoss = trailingStop;
                    
                    if (debugMode && CurrentBar % 10 == 0)
                        Print($"Long trailing stop updated to {trailingStop:F2}");
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                double newTrail = Close[0] + trailDistance;
                if (newTrail < trailingStop && newTrail < entryPrice)
                {
                    trailingStop = newTrail;
                    stopLoss = trailingStop;
                    
                    if (debugMode && CurrentBar % 10 == 0)
                        Print($"Short trailing stop updated to {trailingStop:F2}");
                }
            }
        }
        
        private void CheckTarget2()
        {
            if (Position.MarketPosition == MarketPosition.Long)
            {
                if (High[0] >= target2Price)
                {
                    ExitPosition("Target2", true);
                }
                else if (Low[0] <= trailingStop)
                {
                    ExitPosition("TrailingStop", true);
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                if (Low[0] <= target2Price)
                {
                    ExitPosition("Target2", true);
                }
                else if (High[0] >= trailingStop)
                {
                    ExitPosition("TrailingStop", true);
                }
            }
        }
        
        private bool CheckAdverseExit()
        {
            // Exit on strong momentum reversal
            if (Position.MarketPosition == MarketPosition.Long)
            {
                // Strong bearish reversal
                if (aoValue < -0.001 && aoPrevValue >= 0 && Close[0] < ema9[0])
                    return true;
                
                // Break below VWAP with volume
                if (Close[0] < vwapIndicator.GetVWAP() && 
                    Close[1] >= vwapIndicator.GetVWAP() &&
                    volume[0] > volumeAvg[0] * 1.5)
                    return true;
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                // Strong bullish reversal
                if (aoValue > 0.001 && aoPrevValue <= 0 && Close[0] > ema9[0])
                    return true;
                
                // Break above VWAP with volume
                if (Close[0] > vwapIndicator.GetVWAP() && 
                    Close[1] <= vwapIndicator.GetVWAP() &&
                    volume[0] > volumeAvg[0] * 1.5)
                    return true;
            }
            
            return false;
        }
        
        private void CheckTimeExit()
        {
            SessionIterator sessionIterator = new SessionIterator(Bars);
            sessionIterator.GetNextSession(Time[0], true);
            TimeSpan timeToClose = sessionIterator.ActualSessionEnd.TimeOfDay - Time[0].TimeOfDay;
            if (timeToClose.TotalMinutes <= 15)
            {
                ExitPosition("TimeExit", true);
            }
        }
        
        private void ExitPosition(string reason, bool partial)
        {
            if (Position.MarketPosition == MarketPosition.Long)
            {
                ExitLong(reason);
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                ExitShort(reason);
            }
            
            if (debugMode) Print($"Position exited: {reason}");
        }
        #endregion

        #region Risk Management
        protected override void OnPositionUpdate(Position position, double averagePrice, int quantity, MarketPosition marketPosition)
        {
            if (position.MarketPosition == MarketPosition.Flat && marketPosition != MarketPosition.Flat)
            {
                // Position closed - update tracking
                OnPositionClosed();
            }
        }
        
        private void OnPositionClosed()
        {
            // Update global position tracking
            lock (GlobalPositionLock)
            {
                GlobalTotalContracts -= positionContracts;
                if (GlobalPositions.ContainsKey(instrumentType))
                    GlobalPositions[instrumentType] = 0;
            }
            
            // Get last trade P&L
            if (SystemPerformance.AllTrades.Count > 0)
            {
                Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                double tradePnL = lastTrade.ProfitCurrency;
                currentDailyPnL += tradePnL;
                
                // Update consecutive losses
                if (tradePnL < 0)
                {
                    consecutiveLosses++;
                    if (activeSetup == SetupType.EMA9_VWAP_Bearish || activeSetup == SetupType.SR_AO_ZeroCross)
                        consecutiveShortLosses++;
                }
                else
                {
                    consecutiveLosses = 0;
                    consecutiveShortLosses = 0;
                }
                
                if (debugMode)
                {
                    Print($"\nTrade Closed - Setup: {activeSetup}");
                    Print($"P&L: {tradePnL:C}, Daily Total: {currentDailyPnL:C}");
                    Print($"Consecutive Losses: {consecutiveLosses}");
                }
            }
            
            // Reset position variables
            ResetPositionVariables();
            
            // Check daily limits
            CheckDailyLimits();
        }
        
        private void ResetPositionVariables()
        {
            activeSetup = SetupType.None;
            currentTier = SignalTier.None;
            entryPrice = 0;
            stopLoss = 0;
            target1Price = 0;
            target2Price = 0;
            trailingStop = 0;
            target1Hit = false;
            barsInTrade = 0;
            positionContracts = 0;
            barsSinceExit = 0;
        }
        
        private bool ShouldContinueTrading()
        {
            // Check daily trade limit
            if (todaysTrades >= maxDailyTrades)
            {
                tradingEnabled = false;
                return false;
            }
            
            // Check consecutive losses
            if (consecutiveLosses >= maxConsecutiveLosses)
            {
                tradingEnabled = false;
                return false;
            }
            
            // Check daily loss limit
            double accountValue = ACCOUNT_SIZE;
            if (currentDailyPnL <= -accountValue * dailyLossLimitPercent)
            {
                tradingEnabled = false;
                return false;
            }
            
            // Check time restrictions
            if (Time[0].Hour >= 15) // Stop hour from guide
            {
                return false;
            }
            
            return tradingEnabled;
        }
        
        private void CheckDailyLimits()
        {
            double accountValue = ACCOUNT_SIZE;
            
            // Hard stop at daily loss limit
            if (currentDailyPnL <= -accountValue * dailyLossLimitPercent)
            {
                tradingEnabled = false;
                if (debugMode) Print("*** DAILY LOSS LIMIT REACHED - TRADING STOPPED ***");
            }
            
            // Notify at profit target
            if (currentDailyPnL >= accountValue * dailyProfitTargetPercent)
            {
                if (debugMode) Print("*** DAILY PROFIT TARGET REACHED - Consider stopping ***");
            }
        }
        
        private void ResetDailyCounters()
        {
            currentDailyPnL = 0;
            todaysTrades = 0;
            consecutiveLosses = 0;
            consecutiveShortLosses = 0;
            tradingEnabled = true;
            
            if (debugMode)
            {
                Print($"\n=== NEW TRADING DAY: {currentDay:yyyy-MM-dd} ===");
                Print($"Account Size: {ACCOUNT_SIZE:C}");
                Print($"Daily Loss Limit: {ACCOUNT_SIZE * dailyLossLimitPercent:C}");
                Print($"Daily Profit Target: {ACCOUNT_SIZE * dailyProfitTargetPercent:C}");
            }
        }
        #endregion

        #region Utility Methods
        private void LogStrategyState()
        {
            Print($"\n=== Strategy State at Bar {CurrentBar} ===");
            Print($"Position: {Position.MarketPosition}, Contracts: {Position.Quantity}");
            Print($"Signal: {currentSignal}, Quality: {signalQuality:F2}, Wave: {waveRatio:F1}x");
            Print($"AO: {aoValue:F4}, Previous: {aoPrevValue:F4}");
            Print($"Regime: {currentRegime}, Multiplier: {regimeMultiplier:F1}");
            Print($"Daily Stats - Trades: {todaysTrades}/{maxDailyTrades}, P&L: {currentDailyPnL:C}");
            Print($"EMA9: {ema9[0]:F2}, VWAP: {vwapIndicator.GetVWAP():F2}");
            Print($"Volume: {volume[0] / volumeAvg[0]:F1}x average");
            
            if (nearestSupport > 0 && nearestResistance > 0)
            {
                Print($"S/R Levels - Support: {nearestSupport:F2}, Resistance: {nearestResistance:F2}");
                Print($"At Support: {isAtSupport}, At Resistance: {isAtResistance}");
            }
        }
        #endregion
    }
}