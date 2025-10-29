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
using NinjaTrader.NinjaScript.Indicators;
// Removed using NinjaTrader.NinjaScript.Indicators.FKS to avoid ambiguous type resolution; explicit namespace qualifiers used below.
using NinjaTrader.NinjaScript.AddOns.FKS;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.FKS
{
    public class FKS_Strategy : Strategy, FKS_Core.IFKSComponent
    {
        #region FKS Component Infrastructure
        
        public string ComponentId => "FKS_Strategy";
        public string Version => "1.0.0";
        
        private FKS_Core.FKS_ComponentManager componentRegistry = null;
        private bool isRegisteredWithCore = false;
        
        [XmlIgnore]
        [Browsable(false)]
        public FKS_Core.ComponentStatus Status { get; set; } = FKS_Core.ComponentStatus.Healthy;
        
        // FKS Enhanced Infrastructure Integration
        private string componentId;
        private DateTime lastHeartbeat = DateTime.MinValue;
        private readonly Dictionary<string, object> componentMetrics = new Dictionary<string, object>();
        private readonly Dictionary<string, object> performanceMetrics = new Dictionary<string, object>();
        private readonly Dictionary<string, double> signalQualityMetrics = new Dictionary<string, double>();
        private readonly List<string> errorLog = new List<string>();
        private readonly object infrastructureLock = new object();
        private bool infrastructureInitialized = false;
        private DateTime lastInfrastructureUpdate = DateTime.MinValue;
        private readonly TimeSpan infrastructureUpdateInterval = TimeSpan.FromSeconds(1);
        
        // FKS Shared Components - Static classes accessed directly
        // FKS_Infrastructure, FKS_Calculations, FKS_Signals, FKS_Market are static classes
        
        #endregion
        
        #region Setup Definitions Only

        // Fixed Profit/Loss Targets
        private const double HARD_PROFIT_TARGET = 3000;
        private const double SOFT_PROFIT_TARGET = 2000;
        private const double HARD_LOSS_LIMIT = 1500;
        private const double SOFT_LOSS_LIMIT = 1000;
        
        // Default thresholds for signal quality and volume
        private const double DEFAULT_SIGNAL_QUALITY_THRESHOLD = 0.75;
        private const double DEFAULT_VOLUME_THRESHOLD = 1.5;
        
        // Fixed commission and contract limits
        private const double COMMISSION_PER_RT = 5.0;
        private const int MAX_TOTAL_CONTRACTS = 4;
        private const double ACCOUNT_SIZE = 150000;
        
        // Daily loss limit as percentage
        private double dailyLossLimitPercent = 0.008; // 0.8% of account
        
        // Global thresholds (now as readonly fields instead of parameters)
        private double globalSignalQualityThreshold = DEFAULT_SIGNAL_QUALITY_THRESHOLD;
        private double globalVolumeThreshold = DEFAULT_VOLUME_THRESHOLD;
        
        // FKS Indicators - will be instantiated in DataLoaded
    private NinjaTrader.NinjaScript.Indicators.FKS.FKS_AI fksAI;
    private NinjaTrader.NinjaScript.Indicators.FKS.FKS_AO fksAO;
    private NinjaTrader.NinjaScript.Indicators.FKS.FKS_AI fksVWAP;
    private NinjaTrader.NinjaScript.Indicators.FKS.FKS_Dashboard fksInfo;
        
        // Standard Indicators
        private EMA ema9;
        private ATR atr;
        private VOL volume;
        private SMA volumeAvg;
        
        // Higher Timeframe Analysis
        private EMA ema9_HT; // Higher timeframe EMA
        private double aoValue_HT;
        private double aoPrevValue_HT;
        private bool higherTimeframeConfirmed = true;
        
        // Multi-Timeframe Synchronization
        private double htfTrend = 0; // 1 = bullish, -1 = bearish, 0 = neutral
        private double htfMomentum = 0;
        private DateTime lastHTFUpdate = DateTime.MinValue;
        private readonly TimeSpan htfUpdateInterval = TimeSpan.FromMinutes(5);
        
        // Support/Resistance Detection
        private double nearestSupport = 0;
        private double nearestResistance = 0;
        private List<double> supportLevels = new List<double>();
        private List<double> resistanceLevels = new List<double>();
        
        // Trade Management - Enhanced
        private List<TradeSetup> activeSetups = new List<TradeSetup>();
        private TradeSetup currentTrade;
        private double entryPrice;
        private double stopLoss;
        private double target1;
        private double target2;
        private bool target1Hit;
        private int positionContracts;
        private int activeSetup = 0;
        
        // Daily Tracking - Commission Aware
        private DateTime currentDay = DateTime.MinValue;
        private int todaysTrades = 0;
        private double currentDailyPnL = 0;
        private double currentDailyCommissions = 0;
        // Trading State Variables
        private DateTime lastTradingDay = DateTime.MinValue;
        private int dailyTradeCount = 0;
        private double dailyPnL = 0;
        private int consecutiveLosses = 0;
        private bool tradingEnabled = true;
        private int maxConsecutiveShortLosses = 2; // New for commission optimization
        private int consecutiveShortLosses = 0;
        
        // Enhanced Risk Management
        private double maxDailyLoss = 0;
        private double maxDailyProfit = 0;
        private double currentSessionPnL = 0;
        private bool dailyLossLimitHit = false;
        private bool dailyProfitTargetHit = false;
        private DateTime riskResetTime = DateTime.MinValue;
        
        // Setup Tracking - Enhanced
        private Dictionary<string, int> setupExecutions = new Dictionary<string, int>();
        private Dictionary<string, double> setupPerformance = new Dictionary<string, double>();
        private Dictionary<string, double> setupCommissionCosts = new Dictionary<string, double>();
        
        // Market Analysis
        private string instrumentType = "Gold";
        private FKS_Market.MarketRegimeAnalysis currentRegime;
        private FKS_Market.DynamicParameters dynamicParams;
        
        // Signal Management
        private DateTime lastSignalTime = DateTime.MinValue;
        private string currentSignal = "";
        private double signalQuality = 0;
        
        // Debug Infrastructure
        private readonly List<string> debugLog = new List<string>();
        private DateTime lastDebugUpdate = DateTime.MinValue;
        private readonly TimeSpan debugUpdateInterval = TimeSpan.FromSeconds(10);
        private StringBuilder tradeLog = new StringBuilder();
        
        #endregion

        #region Trade Setup Definitions - Enhanced
        
        private class TradeSetup
        {
            public string Name { get; set; }
            public string Code { get; set; }
            public Func<bool> Condition { get; set; }
            public bool IsLong { get; set; }
            public bool Enabled { get; set; }
            public double MinQuality { get; set; }
            public string Description { get; set; }
            public string Notes { get; set; }
            public double ATRStopMultiplier { get; set; } = 1.8; // Tightened from 2.0
            public double ATRTargetMultiplier { get; set; } = 2.2; // Increased from 1.5
            public int Priority { get; set; } = 5; // 1 = highest priority
            public double QualityBonus { get; set; } = 1.0; // Quality multiplier
        }

        private void InitializeSetups()
        {
            activeSetups.Clear();
            
            // Setup 1: EMA9 + VWAP Bullish Breakout
            activeSetups.Add(new TradeSetup
            {
                Name = "EMA9_VWAP_Bullish",
                Code = "S1L",
                IsLong = true,
                Enabled = EnableSetup1Bullish,
                MinQuality = Math.Max(Setup1MinQuality, globalSignalQualityThreshold),
                Condition = () => CheckSetup1_EMAVWAPBreakout(),
                Description = "Bullish breakout with stacked alignment (Price > EMA9 > VWAP)",
                Notes = "Best in trending markets during optimal hours",
                Priority = 3,
                QualityBonus = 0.95
            });
            
            // Setup 2: EMA9 + VWAP Bearish Breakdown
            activeSetups.Add(new TradeSetup
            {
                Name = "EMA9_VWAP_Bearish", 
                Code = "S2S",
                IsLong = false,
                Enabled = EnableSetup2Bearish && !DisableShortsInUptrend,
                MinQuality = Math.Max(Setup2MinQuality, globalSignalQualityThreshold),
                Condition = () => CheckSetup2_EMAVWAPBreakdown(),
                Description = "Bearish breakdown with stacked alignment (Price < EMA9 < VWAP)",
                Notes = "Watch for failed highs before entry",
                Priority = 3,
                QualityBonus = 0.95
            });
            
            // Setup 3: VWAP Rejection Bounce
            activeSetups.Add(new TradeSetup
            {
                Name = "VWAP_Rejection",
                Code = "S3L", 
                IsLong = true,
                Enabled = EnableSetup3VWAP,
                MinQuality = Math.Max(Setup3MinQuality, globalSignalQualityThreshold),
                Condition = () => CheckSetup3_VWAPRejection(),
                Description = "VWAP rejection with support confluence",
                Notes = "Requires clean rejection candle",
                ATRStopMultiplier = 1.5,
                ATRTargetMultiplier = 2.5,
                Priority = 4,
                QualityBonus = 0.90
            });
            
            // Setup 4: S/R + AO Zero Cross
            activeSetups.Add(new TradeSetup
            {
                Name = "SR_AO_Cross",
                Code = "S4X",
                IsLong = true, // Dynamic
                Enabled = EnableSetup4SR,
                MinQuality = Math.Max(Setup4MinQuality, globalSignalQualityThreshold),
                Condition = () => CheckSetup4_SupportResistanceAO(),
                Description = "Support/Resistance level with AO zero line cross",
                Notes = "Most reliable at major S/R levels",
                ATRTargetMultiplier = 3.5,
                Priority = 4,
                QualityBonus = 0.90
            });
            
            // Setup 5: Pivot Zone Reversal (NEW)
            activeSetups.Add(new TradeSetup
            {
                Name = "Pivot_Zone_Reversal",
                Code = "S5P",
                IsLong = true, // Dynamic
                Enabled = EnableSetup5Pivot,
                MinQuality = Math.Max(0.70, globalSignalQualityThreshold),
                Condition = () => CheckSetup5_PivotZoneReversal(),
                Description = "Pivot zone reversal with momentum confirmation",
                Notes = "Based on NSDT Pivot concepts",
                Priority = 4,
                QualityBonus = 0.92
            });
            
            // Setup 6: Manipulation Candle (NEW)
            activeSetups.Add(new TradeSetup
            {
                Name = "Manipulation_Candle",
                Code = "S6M",
                IsLong = true, // Dynamic
                Enabled = EnableSetup6Manipulation,
                MinQuality = Math.Max(0.75, globalSignalQualityThreshold),
                Condition = () => CheckSetup6_ManipulationCandle(),
                Description = "Manipulation candle reversal setup",
                Notes = "High quality reversal signals",
                Priority = 2,
                QualityBonus = 1.05
            });
            
            // Setup 7: Volume Price Analysis (NEW)
            activeSetups.Add(new TradeSetup
            {
                Name = "Volume_Price_Analysis",
                Code = "S7V",
                IsLong = true, // Dynamic
                Enabled = EnableSetup7VPA,
                MinQuality = Math.Max(0.65, globalSignalQualityThreshold),
                Condition = () => CheckSetup7_VPA(),
                Description = "Volume Price Analysis setup",
                Notes = "Accumulation/distribution patterns",
                Priority = 5,
                QualityBonus = 0.88
            });
            
            // Setup 8: Multi-Timeframe Momentum Alignment (NEW - HIGHEST PRIORITY)
            activeSetups.Add(new TradeSetup
            {
                Name = "MTF_Momentum_Alignment",
                Code = "S8A",
                IsLong = true, // Dynamic
                Enabled = EnableSetup8MTF,
                MinQuality = Math.Max(0.75, globalSignalQualityThreshold),
                Condition = () => CheckSetup8_MomentumAlignment(),
                Description = "Multi-timeframe momentum alignment",
                Notes = "Highest quality setup - all timeframes aligned",
                Priority = 1,
                QualityBonus = 1.08
            });
            
            // Setup 9: Gap Fill Strategy (NEW)
            activeSetups.Add(new TradeSetup
            {
                Name = "Gap_Fill",
                Code = "S9G",
                IsLong = true, // Dynamic
                Enabled = EnableSetup9Gap,
                MinQuality = Math.Max(0.60, globalSignalQualityThreshold),
                Condition = () => CheckSetup9_GapFill(),
                Description = "Gap fill mean reversion",
                Notes = "Use sparingly - mean reversion setup",
                Priority = 6,
                QualityBonus = 0.85
            });
            
            // Setup 10: Breakout Retest (NEW)
            activeSetups.Add(new TradeSetup
            {
                Name = "Breakout_Retest",
                Code = "S10R",
                IsLong = true, // Dynamic
                Enabled = EnableSetup10Retest,
                MinQuality = Math.Max(0.70, globalSignalQualityThreshold),
                Condition = () => CheckSetup10_BreakoutRetest(),
                Description = "Breakout retest confirmation",
                Notes = "High probability continuation setup",
                Priority = 3,
                QualityBonus = 0.90
            });
            
            // Sort by priority (1 = highest)
            activeSetups = activeSetups.OrderBy(s => s.Priority).ToList();
        }
        
        #endregion

        #region Enhanced Setup Logic Methods
        
        private bool CheckSetup1_EMAVWAPBreakout()
        {
            if (!EnableSetup1Bullish) return false;
            if (fksAI == null || fksAO == null || fksVWAP == null) return false;
            
            try
            {
                // Price > EMA9 > VWAP alignment
                if (Close[0] <= ema9[0]) return false;
                if (ema9[0] <= fksVWAP.GetVWAP()) return false;
                
                // AI Signal confirmation
                if (fksAI.SignalType != "G" && fksAI.SignalType != "^") return false;
                if (fksAI.SignalQuality < Math.Max(Setup1MinQuality, globalSignalQualityThreshold)) return false;
                
                // AO Confirmation
                if (!fksAO.IsBullish || fksAO.Value <= 0) return false;
                
                // Enhanced volume confirmation
                if (volume[0] < volumeAvg[0] * globalVolumeThreshold) return false;
                
                // Breakout confirmation
                double swingHigh = MAX(High, 10)[1];
                if (Close[0] > swingHigh && Close[1] <= swingHigh)
                {
                    currentSignal = "G";
                    signalQuality = CalculateSignalQuality(true) * 0.95;
                    activeSetup = 1;
                    LogDebug("SETUP1", $"EMA9+VWAP Bullish breakout - Quality: {signalQuality:F2}");
                    return true;
                }
                
                return false;
            }
            catch (Exception ex)
            {
                LogDebug("SETUP1", $"Error in Setup 1 check: {ex.Message}", "ERROR");
                return false;
            }
        }
        
        private bool CheckSetup2_EMAVWAPBreakdown()
        {
            if (!EnableSetup2Bearish || (DisableShortsInUptrend && IsInUptrend())) return false;
            if (fksAI == null || fksAO == null || fksVWAP == null) return false;
            if (consecutiveShortLosses >= maxConsecutiveShortLosses) return false;
            
            try
            {
                // Price < EMA9 < VWAP alignment
                if (Close[0] >= ema9[0]) return false;
                if (ema9[0] >= fksVWAP.GetVWAP()) return false;
                
                // AI Signal confirmation
                if (fksAI.SignalType != "Top" && fksAI.SignalType != "v") return false;
                if (fksAI.SignalQuality < Math.Max(Setup2MinQuality, globalSignalQualityThreshold)) return false;
                
                // AO Confirmation
                if (!fksAO.IsBearish || fksAO.Value >= 0) return false;
                
                // Enhanced volume confirmation
                if (volume[0] < volumeAvg[0] * globalVolumeThreshold) return false;
                
                // Breakdown confirmation
                double swingLow = MIN(Low, 10)[1];
                if (Close[0] < swingLow && Close[1] >= swingLow)
                {
                    currentSignal = "Top";
                    signalQuality = CalculateSignalQuality(false) * 0.95;
                    activeSetup = 2;
                    LogDebug("SETUP2", $"EMA9+VWAP Bearish breakdown - Quality: {signalQuality:F2}");
                    return true;
                }
                
                return false;
            }
            catch (Exception ex)
            {
                LogDebug("SETUP2", $"Error in Setup 2 check: {ex.Message}", "ERROR");
                return false;
            }
        }
        
        private bool CheckSetup3_VWAPRejection()
        {
            if (!EnableSetup3VWAP) return false;
            if (fksAI == null || fksVWAP == null) return false;
            
            try
            {
                // Must be near VWAP
                double vwapValue = fksVWAP.GetVWAP();
                if (Math.Abs(Close[0] - vwapValue) > atr[0] * 0.5) return false;
                
                // AI Signal at support
                if (fksAI.SignalType != "G") return false;
                if (fksAI.SignalQuality < Math.Max(Setup3MinQuality, globalSignalQualityThreshold)) return false;
                
                // Check for support level
                if (Math.Abs(Close[0] - nearestSupport) > atr[0] * 0.4) return false;
                
                // Volume confirmation
                if (volume[0] < volumeAvg[0] * globalVolumeThreshold) return false;
                
                // AO momentum shift
                if (fksAO != null && (!fksAO.IsAccelerating && fksAO.MomentumStrength < 0.5)) return false;
                
                // Rejection candle pattern
                if (IsHammerCandle() || IsBullishEngulfing())
                {
                    currentSignal = "G";
                    signalQuality = CalculateSignalQuality(true) * 0.90;
                    activeSetup = 3;
                    LogDebug("SETUP3", $"VWAP rejection bounce - Quality: {signalQuality:F2}");
                    return true;
                }
                
                return false;
            }
            catch (Exception ex)
            {
                LogDebug("SETUP3", $"Error in Setup 3 check: {ex.Message}", "ERROR");
                return false;
            }
        }
        
        private bool CheckSetup4_SupportResistanceAO()
        {
            if (!EnableSetup4SR) return false;
            if (fksAI == null || fksAO == null) return false;
            
            try
            {
                // Must be at key S/R level
                bool atSupport = Math.Abs(Close[0] - nearestSupport) <= atr[0] * 0.3;
                bool atResistance = Math.Abs(Close[0] - nearestResistance) <= atr[0] * 0.3;
                if (!atSupport && !atResistance) return false;
                
                // AO must cross zero or show strong momentum
                bool aoSignal = (fksAO.CrossDirection != 0) || (Math.Abs(fksAO.Value) > 0.5);
                if (!aoSignal) return false;
                
                // AI Signal quality check
                if (fksAI.SignalQuality < Math.Max(Setup4MinQuality, globalSignalQualityThreshold)) return false;
                
                // Enhanced volume confirmation
                if (volume[0] < volumeAvg[0] * globalVolumeThreshold) return false;
                
                // Direction based on AO and location
                bool goLong = (fksAO.Value >= 0 || fksAO.CrossDirection > 0) && atSupport;
                bool goShort = (fksAO.Value <= 0 || fksAO.CrossDirection < 0) && atResistance && !DisableShortsInUptrend;
                
                if (goLong || goShort)
                {
                    currentSignal = goLong ? "G" : "Top";
                    signalQuality = CalculateSignalQuality(goLong) * 0.90;
                    activeSetup = 4;
                    LogDebug("SETUP4", $"S/R + AO setup - Direction: {(goLong ? "LONG" : "SHORT")}, Quality: {signalQuality:F2}");
                    return true;
                }
                
                return false;
            }
            catch (Exception ex)
            {
                LogDebug("SETUP4", $"Error in Setup 4 check: {ex.Message}", "ERROR");
                return false;
            }
        }
        
        // NEW SETUPS (5-10)
        
        private bool CheckSetup5_PivotZoneReversal()
        {
            if (!EnableSetup5Pivot || CurrentBar < 3) return false;
            
            try
            {
                // Calculate pivot-like levels
                double pivotPoint = (High[1] + Low[1] + Close[1]) / 3;
                double r1 = (2 * pivotPoint) - Low[1];
                double s1 = (2 * pivotPoint) - High[1];
                
                bool atPivotSupport = Math.Abs(Close[0] - s1) <= atr[0] * 0.3;
                bool atPivotResistance = Math.Abs(Close[0] - r1) <= atr[0] * 0.3;
                
                // Long setup at pivot support
                if (atPivotSupport && Close[0] > Open[0] && fksAO != null && fksAO.Value > fksAO.PreviousValue &&
                    volume[0] > volumeAvg[0] * globalVolumeThreshold)
                {
                    currentSignal = "G";
                    signalQuality = CalculateSignalQuality(true) * 0.92;
                    activeSetup = 5;
                    LogDebug("SETUP5", $"Pivot support reversal - Quality: {signalQuality:F2}");
                    return true;
                }
                
                // Short setup at pivot resistance
                if (atPivotResistance && Close[0] < Open[0] && fksAO != null && fksAO.Value < fksAO.PreviousValue &&
                    volume[0] > volumeAvg[0] * globalVolumeThreshold && !DisableShortsInUptrend)
                {
                    currentSignal = "Top";
                    signalQuality = CalculateSignalQuality(false) * 0.92;
                    activeSetup = 5;
                    LogDebug("SETUP5", $"Pivot resistance reversal - Quality: {signalQuality:F2}");
                    return true;
                }
                
                return false;
            }
            catch (Exception ex)
            {
                LogDebug("SETUP5", $"Error in Setup 5 check: {ex.Message}", "ERROR");
                return false;
            }
        }
        
        private bool CheckSetup6_ManipulationCandle()
        {
            if (!EnableSetup6Manipulation || CurrentBar < 3) return false;
            
            try
            {
                // Bullish Manipulation Candle - price dips below previous low, then closes above previous high
                bool bullishMC = Low[0] < Low[1] && Close[0] > High[1] && Close[0] > Open[0];
                
                // Bearish Manipulation Candle - price spikes above previous high, then closes below previous low
                bool bearishMC = High[0] > High[1] && Close[0] < Low[1] && Close[0] < Open[0];
                
                // Additional confirmation requirements
                bool strongVolume = volume[0] > volumeAvg[0] * globalVolumeThreshold * 1.4;
                bool nearKeyLevel = Math.Abs(Close[0] - nearestSupport) <= atr[0] * 0.4 ||
                                   Math.Abs(Close[0] - nearestResistance) <= atr[0] * 0.4;
                
                if (bullishMC && strongVolume && nearKeyLevel)
                {
                    currentSignal = "G";
                    signalQuality = CalculateSignalQuality(true) * 1.05; // Bonus for manipulation setup
                    activeSetup = 6;
                    LogDebug("SETUP6", $"Bullish manipulation candle - Quality: {signalQuality:F2}");
                    return true;
                }
                
                if (bearishMC && strongVolume && nearKeyLevel && !DisableShortsInUptrend)
                {
                    currentSignal = "Top";
                    signalQuality = CalculateSignalQuality(false) * 1.05;
                    activeSetup = 6;
                    LogDebug("SETUP6", $"Bearish manipulation candle - Quality: {signalQuality:F2}");
                    return true;
                }
                
                return false;
            }
            catch (Exception ex)
            {
                LogDebug("SETUP6", $"Error in Setup 6 check: {ex.Message}", "ERROR");
                return false;
            }
        }
        
        private bool CheckSetup7_VPA()
        {
            if (!EnableSetup7VPA || CurrentBar < 5) return false;
            
            try
            {
                // Calculate volume characteristics
                double avgVolume5 = (volume[0] + volume[1] + volume[2] + volume[3] + volume[4]) / 5;
                double currentVolumeRatio = avgVolume5 > 0 ? volume[0] / avgVolume5 : 1;
                
                // High volume with narrow spread (accumulation/distribution)
                double spread = High[0] - Low[0];
                double avgSpread = (Math.Abs(High[0] - Low[0]) + Math.Abs(High[1] - Low[1]) + 
                                  Math.Abs(High[2] - Low[2])) / 3;
                
                bool highVolumeNarrowSpread = currentVolumeRatio > 2.0 && spread < avgSpread * 0.7;
                bool closingStrong = Close[0] > (High[0] + Low[0]) / 2; // Close in upper half
                bool closingWeak = Close[0] < (High[0] + Low[0]) / 2;   // Close in lower half
                
                // Bullish VPA
                if (highVolumeNarrowSpread && closingStrong && Close[0] > ema9[0])
                {
                    currentSignal = "G";
                    signalQuality = CalculateSignalQuality(true) * 0.88;
                    activeSetup = 7;
                    LogDebug("SETUP7", $"Bullish VPA - Quality: {signalQuality:F2}");
                    return true;
                }
                
                // Bearish VPA
                if (highVolumeNarrowSpread && closingWeak && Close[0] < ema9[0] && !DisableShortsInUptrend)
                {
                    currentSignal = "Top";
                    signalQuality = CalculateSignalQuality(false) * 0.88;
                    activeSetup = 7;
                    LogDebug("SETUP7", $"Bearish VPA - Quality: {signalQuality:F2}");
                    return true;
                }
                
                return false;
            }
            catch (Exception ex)
            {
                LogDebug("SETUP7", $"Error in Setup 7 check: {ex.Message}", "ERROR");
                return false;
            }
        }
        
        private bool CheckSetup8_MomentumAlignment()
        {
            if (!EnableSetup8MTF || !UseHigherTimeframeConfirmation) return false;
            if (BarsArray.Length < 2 || BarsArray[1].Count < 3) return false;
            
            try
            {
                // Check momentum alignment across timeframes
                bool primaryBullish = Close[0] > ema9[0] && fksAO != null && fksAO.Value > 0;
                bool primaryBearish = Close[0] < ema9[0] && fksAO != null && fksAO.Value < 0;
                
                bool higherTFBullish = Closes[1][0] > ema9_HT[0] && aoValue_HT > 0;
                bool higherTFBearish = Closes[1][0] < ema9_HT[0] && aoValue_HT < 0;
                
                // Look for momentum acceleration
                bool momentumAccelerating = false;
                if (primaryBullish && higherTFBullish && fksAO != null)
                {
                    momentumAccelerating = fksAO.Value > fksAO.PreviousValue && aoValue_HT > aoPrevValue_HT;
                }
                else if (primaryBearish && higherTFBearish && fksAO != null)
                {
                    momentumAccelerating = fksAO.Value < fksAO.PreviousValue && aoValue_HT < aoPrevValue_HT;
                }
                
                // Strong volume confirmation
                bool volumeExpansion = volume[0] > volumeAvg[0] * globalVolumeThreshold * 1.5;
                
                if (primaryBullish && higherTFBullish && momentumAccelerating && volumeExpansion)
                {
                    currentSignal = "G";
                    signalQuality = CalculateSignalQuality(true) * 1.08; // High quality setup
                    activeSetup = 8;
                    LogDebug("SETUP8", $"Bullish MTF alignment - Quality: {signalQuality:F2}");
                    return true;
                }
                
                if (primaryBearish && higherTFBearish && momentumAccelerating && volumeExpansion && !DisableShortsInUptrend)
                {
                    currentSignal = "Top";
                    signalQuality = CalculateSignalQuality(false) * 1.08;
                    activeSetup = 8;
                    LogDebug("SETUP8", $"Bearish MTF alignment - Quality: {signalQuality:F2}");
                    return true;
                }
                
                return false;
            }
            catch (Exception ex)
            {
                LogDebug("SETUP8", $"Error in Setup 8 check: {ex.Message}", "ERROR");
                return false;
            }
        }
        
        private bool CheckSetup9_GapFill()
        {
            if (!EnableSetup9Gap || CurrentBar < 2) return false;
            
            try
            {
                // Detect gap (difference between previous close and current open)
                double gapSize = Math.Abs(Open[0] - Close[1]);
                double minGapSize = atr[0] * 0.5; // Minimum gap size to consider
                
                if (gapSize < minGapSize) return false;
                
                bool isGapUp = Open[0] > Close[1] + minGapSize;
                bool isGapDown = Open[0] < Close[1] - minGapSize;
                
                // Look for gap fill opportunity
                bool gapFillLong = isGapDown && Close[0] > Open[0] && 
                                  Close[0] > (Open[0] + Close[1]) / 2; // Moving toward gap fill
                
                bool gapFillShort = isGapUp && Close[0] < Open[0] && 
                                   Close[0] < (Open[0] + Close[1]) / 2; // Moving toward gap fill
                
                if (gapFillLong && volume[0] > volumeAvg[0] * globalVolumeThreshold)
                {
                    currentSignal = "G";
                    signalQuality = CalculateSignalQuality(true) * 0.85; // Lower quality as it's mean reversion
                    activeSetup = 9;
                    LogDebug("SETUP9", $"Gap fill long - Quality: {signalQuality:F2}");
                    return true;
                }
                
                if (gapFillShort && volume[0] > volumeAvg[0] * globalVolumeThreshold && !DisableShortsInUptrend)
                {
                    currentSignal = "Top";
                    signalQuality = CalculateSignalQuality(false) * 0.85;
                    activeSetup = 9;
                    LogDebug("SETUP9", $"Gap fill short - Quality: {signalQuality:F2}");
                    return true;
                }
                
                return false;
            }
            catch (Exception ex)
            {
                LogDebug("SETUP9", $"Error in Setup 9 check: {ex.Message}", "ERROR");
                return false;
            }
        }
        
        private bool CheckSetup10_BreakoutRetest()
        {
            if (!EnableSetup10Retest || CurrentBar < 20) return false;
            
            try
            {
                // Look for recent breakout in the last 10 bars
                bool recentBreakoutUp = false;
                bool recentBreakoutDown = false;
                double breakoutLevel = 0;
                
                for (int i = 1; i <= 10; i++)
                {
                    if (Close[i] > nearestResistance && Close[i-1] <= nearestResistance)
                    {
                        recentBreakoutUp = true;
                        breakoutLevel = nearestResistance;
                        break;
                    }
                    if (Close[i] < nearestSupport && Close[i-1] >= nearestSupport)
                    {
                        recentBreakoutDown = true;
                        breakoutLevel = nearestSupport;
                        break;
                    }
                }
                
                // Now look for retest of breakout level
                if (recentBreakoutUp && Math.Abs(Close[0] - breakoutLevel) <= atr[0] * 0.4 &&
                    Close[0] > breakoutLevel && Close[0] > Open[0])
                {
                    currentSignal = "G";
                    signalQuality = CalculateSignalQuality(true) * 0.90;
                    activeSetup = 10;
                    LogDebug("SETUP10", $"Bullish breakout retest - Quality: {signalQuality:F2}");
                    return true;
                }
                
                if (recentBreakoutDown && Math.Abs(Close[0] - breakoutLevel) <= atr[0] * 0.4 &&
                    Close[0] < breakoutLevel && Close[0] < Open[0] && !DisableShortsInUptrend)
                {
                    currentSignal = "Top";
                    signalQuality = CalculateSignalQuality(false) * 0.90;
                    activeSetup = 10;
                    LogDebug("SETUP10", $"Bearish breakout retest - Quality: {signalQuality:F2}");
                    return true;
                }
                
                return false;
            }
            catch (Exception ex)
            {
                LogDebug("SETUP10", $"Error in Setup 10 check: {ex.Message}", "ERROR");
                return false;
            }
        }
        
        #endregion

        #region Enhanced Signal Quality Calculation
        
        private double CalculateSignalQuality(bool isLong)
        {
            try
            {
                double quality = 0.5; // Base quality
                
                // AI Signal Quality
                if (fksAI != null)
                {
                    quality += fksAI.SignalQuality * 0.3;
                }
                
                // Volume confirmation
                double volumeRatio = volume[0] / volumeAvg[0];
                if (volumeRatio > globalVolumeThreshold)
                {
                    quality += Math.Min(0.15, (volumeRatio - 1.0) * 0.1);
                }
                
                // Momentum confirmation
                if (fksAO != null)
                {
                    if (isLong && fksAO.Value > 0 && fksAO.IsAccelerating)
                        quality += 0.1;
                    else if (!isLong && fksAO.Value < 0 && fksAO.IsAccelerating)
                        quality += 0.1;
                }
                
                // VWAP alignment
                if (fksVWAP != null)
                {
                    double vwapValue = fksVWAP.GetVWAP();
                    if (isLong && Close[0] > vwapValue && ema9[0] > vwapValue)
                        quality += 0.08;
                    else if (!isLong && Close[0] < vwapValue && ema9[0] < vwapValue)
                        quality += 0.08;
                }
                
                // Support/Resistance proximity
                if (nearestSupport > 0 || nearestResistance > 0)
                {
                    bool nearLevel = (isLong && Math.Abs(Close[0] - nearestSupport) <= atr[0] * 0.3) ||
                                    (!isLong && Math.Abs(Close[0] - nearestResistance) <= atr[0] * 0.3);
                    if (nearLevel) quality += 0.05;
                }
                
                // Time-based bonus (optimal trading hours)
                if (IsWithinTradingHours())
                {
                    quality += 0.02;
                }
                
                // Market regime bonus
                if (currentRegime != null)
                {
                    if (currentRegime.OverallRegime == "TRENDING")
                    {
                        quality += 0.05;
                    }
                }
                
                return Math.Min(1.0, Math.Max(0.0, quality));
            }
            catch (Exception ex)
            {
                LogDebug("QUALITY", $"Error calculating signal quality: {ex.Message}", "ERROR");
                return 0.5;
            }
        }
        
        #endregion

        #region Commission-Optimized Position Sizing
        
        private int CalculatePositionSize(TradeSetup setup)
        {
            try
            {
                if (UseFixedContracts)
                    return Math.Min(FixedContracts, MAX_TOTAL_CONTRACTS);
                
                // Base contract calculation - more conservative for commission environment
                int baseContracts = 1;
                
                // Quality-based sizing
                if (signalQuality >= 0.80)
                    baseContracts = 3;
                else if (signalQuality >= 0.75)
                    baseContracts = 2;
                else
                    baseContracts = 1;
                
                // Apply regime adjustment if enabled
                if (EnableRegimeAdjustment && dynamicParams != null)
                {
                    baseContracts = (int)(baseContracts * dynamicParams.PositionSizeAdjustment);
                }
                
                // Apply consecutive loss reduction - more aggressive for commission environment
                if (consecutiveLosses >= 2)
                    baseContracts = 1; // Drop to minimum
                else if (consecutiveLosses >= 1)
                    baseContracts = Math.Max(1, baseContracts - 1);
                
                // Commission-to-profit ratio check
                double expectedProfitTicks = atr[0] * setup.ATRTargetMultiplier / Instrument.MasterInstrument.TickSize;
                double expectedProfitDollars = expectedProfitTicks * Instrument.MasterInstrument.PointValue;
                
                // Ensure minimum profit covers commission + reasonable profit
                if (expectedProfitDollars < COMMISSION_PER_RT * 2) // 2x commission minimum
                {
                    LogDebug("POSITION_SIZE", $"Trade rejected - insufficient profit potential: ${expectedProfitDollars:F2}");
                    return 0;
                }
                
                // Ensure we don't exceed max contracts
                baseContracts = Math.Min(baseContracts, MAX_TOTAL_CONTRACTS);
                
                LogDebug("POSITION_SIZE", $"Position size: {baseContracts} contracts, Expected profit: ${expectedProfitDollars:F2}");
                
                return Math.Max(1, baseContracts);
            }
            catch (Exception ex)
            {
                LogDebug("POSITION_SIZE", $"Error calculating position size: {ex.Message}", "ERROR");
                return 1;
            }
        }
        
        /// <summary>
        /// Use ML-enhanced position sizing from FKS_Calculations
        /// </summary>
        private int CalculateEnhancedPositionSize(TradeSetup setup, double stopDistance)
        {
            try
            {
                // Check if indicators are properly initialized
                if (ema9 == null || atr == null || CurrentBar < 20)
                {
                    return 1; // Default position size when not enough data
                }

                // Create market condition context with null checks
                var marketContext = FKS_Calculations.AnalyzeCurrentMarketCondition(
                    Close[0], 
                    ema9?[0] ?? Close[0], 
                    SMA(Close, 20)?[0] ?? Close[0], 
                    atr?[0] ?? 1.0, 
                    Volume[0], 
                    volumeAvg?[0] ?? Volume[0],
                    GetPriceHistory(Math.Min(20, CurrentBar + 1)),
                    GetVolumeHistory(Math.Min(20, CurrentBar + 1))
                );

                // Use ML-enhanced position sizing
                int mlEnhancedSize = FKS_Calculations.CalculateMLEnhancedPositionSize(
                    ACCOUNT_SIZE,
                    dailyLossLimitPercent * 100, // Convert to percentage
                    Math.Max(0.1, stopDistance), // Ensure minimum stop distance
                    Instrument.MasterInstrument.PointValue,
                    marketContext
                );

                // Apply commission optimization
                int commissionOptimizedSize = FKS_Calculations.CalculateCommissionOptimizedSize(
                    setup.ATRTargetMultiplier * (atr?[0] ?? 1.0) * Instrument.MasterInstrument.PointValue, // Expected profit
                    Math.Max(0.1, stopDistance) * Instrument.MasterInstrument.PointValue, // Expected loss
                    COMMISSION_PER_RT,
                    0.65, // Win rate assumption
                    mlEnhancedSize,
                    3.0 // Minimum profit multiple
                );

                // Apply setup-specific adjustments
                int finalSize = (int)(commissionOptimizedSize * setup.QualityBonus);

                LogDebug("POSITION_SIZE", $"Enhanced Position Sizing - ML: {mlEnhancedSize}, " +
                    $"Commission Optimized: {commissionOptimizedSize}, Final: {finalSize}", "INFO");

                return Math.Max(1, Math.Min(finalSize, MAX_TOTAL_CONTRACTS));
            }
            catch (Exception ex)
            {
                LogDebug("POSITION_SIZE", $"Error in enhanced position sizing: {ex.Message}", "ERROR");
                return 1; // Safe fallback
            }
        }

        /// <summary>
        /// Get enhanced signal quality using FKS_Calculations
        /// </summary>
        private double GetEnhancedSignalQuality(TradeSetup setup)
        {
            try
            {
                // Check if indicators are properly initialized
                if (ema9 == null || atr == null || CurrentBar < 20)
                {
                    return 0.5; // Default quality when not enough data
                }

                // Ensure we have enough bars for analysis
                if (CurrentBar < 20)
                {
                    return 0.5;
                }

                // Prepare signal analysis data with null checks
                var priceData = GetPriceHistory(Math.Min(20, CurrentBar + 1));
                var volumeData = GetVolumeHistory(Math.Min(20, CurrentBar + 1));
                
                // Safe indicator data with null checks
                var indicatorData = new double[] { 
                    ema9?[0] ?? Close[0], 
                    atr?[0] ?? 1.0, 
                    currentSignalQuality 
                };

                // Use advanced signal processing
                var signalAnalysis = FKS_Calculations.AnalyzeSignalQuality(
                    priceData,
                    volumeData,
                    indicatorData,
                    setup?.Code ?? "DEFAULT",
                    Math.Min(20, CurrentBar + 1)
                );

                // Combine with existing signal quality - use safe fallback
                double baseQuality = 0.5; // Default base quality
                double enhancedQuality = (baseQuality * 0.6) + (signalAnalysis.QualityScore * 0.4);

                return Math.Max(0.0, Math.Min(1.0, enhancedQuality)); // Clamp between 0-1
            }
            catch (Exception ex)
            {
                LogDebug("SIGNAL_QUALITY", $"Error in enhanced signal quality: {ex.Message}", "ERROR");
                return 0.5; // Safe fallback value
            }
        }

        /// <summary>
        /// Use enhanced ATR calculation with circuit breaker protection
        /// </summary>
        private double GetEnhancedATR()
        {
            try
            {
                // Check if ATR is properly initialized
                if (atr == null || CurrentBar < 14)
                {
                    return 1.0; // Default ATR when not enough data
                }

                return FKS_Calculations.ExecuteWithCircuitBreaker("volatility_calculation", () =>
                {
                    var atrArray = new double[Math.Min(14, CurrentBar + 1)];
                    var returnsArray = new double[Math.Min(14, CurrentBar + 1)];
                    
                    for (int i = 0; i < atrArray.Length && i <= CurrentBar; i++)
                    {
                        atrArray[i] = atr?[i] ?? 1.0;
                        if (i < returnsArray.Length - 1 && i <= CurrentBar - 1 && Close[i + 1] != 0)
                        {
                            returnsArray[i] = (Close[i] - Close[i + 1]) / Close[i + 1];
                        }
                    }

                    return FKS_Calculations.CalculateVolatilityAdjustedATR(atrArray, returnsArray);
                }, atr?[0] ?? 1.0);
            }
            catch (Exception ex)
            {
                LogDebug("ATR", $"Error in enhanced ATR calculation: {ex.Message}", "ERROR");
                return atr?[0] ?? 1.0; // Safe fallback
            }
        }

        /// <summary>
        /// Get adaptive ATR multiplier based on market conditions
        /// </summary>
        private double GetAdaptiveATRMultiplier(TradeSetup setup)
        {
            try
            {
                // Check if indicators are properly initialized
                if (atr == null || CurrentBar < 20)
                {
                    return setup.ATRStopMultiplier; // Default to setup value
                }

                var currentVol = GetEnhancedATR();
                var avgVol = SMA(atr, 20)?[0] ?? currentVol;
                var sessionType = GetCurrentSessionType();

                return FKS_Calculations.CalculateAdaptiveATRMultiplier(
                    instrumentType,
                    setup.ATRStopMultiplier,
                    currentVol,
                    avgVol,
                    marketRegime,
                    sessionType
                );
            }
            catch (Exception ex)
            {
                LogDebug("ATR", $"Error in adaptive ATR calculation: {ex.Message}", "ERROR");
                return setup.ATRStopMultiplier; // Safe fallback
            }
        }

        /// <summary>
        /// Monitor system health and performance
        /// </summary>
        private void MonitorSystemHealth()
        {
            try
            {
                if (CurrentBar % 100 == 0) // Check every 100 bars
                {
                    var healthReport = FKS_Calculations.GetSystemHealthReport();
                    
                    if (healthReport.OverallHealth == "POOR" || healthReport.OverallHealth == "CRITICAL")
                    {
                        LogDebug("SYSTEM_HEALTH", $"System Health Warning: {healthReport.OverallHealth}", "WARN");
                        
                        // Consider reducing position sizes if system health is poor
                        if (healthReport.OverallHealth == "CRITICAL")
                        {
                            tradingEnabled = false;
                            LogDebug("SYSTEM_HEALTH", "Trading disabled due to critical system health", "ERROR");
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogDebug("SYSTEM_HEALTH", $"Error monitoring system health: {ex.Message}", "ERROR");
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

        #endregion

        #region Missing Properties and Methods

        // Add Interface Implementation
        public void Initialize()
        {
            // FKS Component initialization
            try
            {
                // Register with core system
                componentRegistry = FKS_Core.FKS_ComponentManager.Instance;
                componentRegistry.RegisterComponent(ComponentId, this);
                isRegisteredWithCore = true;
                
                // Initialize infrastructure
                InitializeInfrastructure();
                
                Status = FKS_Core.ComponentStatus.Healthy;
            }
            catch (Exception ex)
            {
                Status = FKS_Core.ComponentStatus.Error;
                Print($"Error initializing FKS Strategy: {ex.Message}");
            }
        }

        public void Shutdown()
        {
            try
            {
                // Unregister from core system
                if (isRegisteredWithCore && componentRegistry != null)
                {
                    componentRegistry.UnregisterComponent(ComponentId);
                    isRegisteredWithCore = false;
                }
                
                Status = FKS_Core.ComponentStatus.Healthy; // Use available status
            }
            catch (Exception ex)
            {
                Print($"Error shutting down FKS Strategy: {ex.Message}");
            }
        }

        // Add LogDebug method
        private void LogDebug(string category, string message, string level = "INFO")
        {
            try
            {
                string logMessage = $"[{DateTime.Now:HH:mm:ss}] [{level}] [{category}] {message}";
                
                if (level == "ERROR")
                {
                    Print(logMessage);
                    errorLog.Add(logMessage);
                }
                else if (level == "WARN")
                {
                    Print(logMessage);
                }
                else
                {
                    // For INFO level, optionally log to console
                    if (category == "TRADE" || category == "SYSTEM_HEALTH")
                    {
                        Print(logMessage);
                    }
                }
                
                // Keep error log size manageable
                if (errorLog.Count > 100)
                {
                    errorLog.RemoveAt(0);
                }
            }
            catch (Exception ex)
            {
                Print($"Error in LogDebug: {ex.Message}");
            }
        }

        // Add missing variables (only new ones)
        private string marketRegime = "NORMAL";
        private double currentSignalQuality = 0.0;

        #endregion

        #region Setup Enable/Disable Properties
        
        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 1 Bullish", Description = "Enable EMA9+VWAP Bullish Setup", Order = 1, GroupName = "Setup Controls")]
        public bool EnableSetup1Bullish { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Setup 1 Min Quality", Description = "Minimum signal quality for Setup 1", Order = 2, GroupName = "Setup Controls")]
        public double Setup1MinQuality { get; set; } = 0.75;

        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 2 Bearish", Description = "Enable EMA9+VWAP Bearish Setup", Order = 3, GroupName = "Setup Controls")]
        public bool EnableSetup2Bearish { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Setup 2 Min Quality", Description = "Minimum signal quality for Setup 2", Order = 4, GroupName = "Setup Controls")]
        public double Setup2MinQuality { get; set; } = 0.75;

        [NinjaScriptProperty]
        [Display(Name = "Disable Shorts In Uptrend", Description = "Disable short setups in uptrend", Order = 5, GroupName = "Setup Controls")]
        public bool DisableShortsInUptrend { get; set; } = false;

        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 3 VWAP", Description = "Enable VWAP Rejection Setup", Order = 6, GroupName = "Setup Controls")]
        public bool EnableSetup3VWAP { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Setup 3 Min Quality", Description = "Minimum signal quality for Setup 3", Order = 7, GroupName = "Setup Controls")]
        public double Setup3MinQuality { get; set; } = 0.75;

        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 4 SR", Description = "Enable Support/Resistance Setup", Order = 8, GroupName = "Setup Controls")]
        public bool EnableSetup4SR { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Setup 4 Min Quality", Description = "Minimum signal quality for Setup 4", Order = 9, GroupName = "Setup Controls")]
        public double Setup4MinQuality { get; set; } = 0.75;

        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 5 Pivot", Description = "Enable Pivot Point Setup", Order = 10, GroupName = "Setup Controls")]
        public bool EnableSetup5Pivot { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 6 Manipulation", Description = "Enable Manipulation Setup", Order = 11, GroupName = "Setup Controls")]
        public bool EnableSetup6Manipulation { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 7 VPA", Description = "Enable Volume Price Analysis Setup", Order = 12, GroupName = "Setup Controls")]
        public bool EnableSetup7VPA { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 8 MTF", Description = "Enable Multi-Timeframe Setup", Order = 13, GroupName = "Setup Controls")]
        public bool EnableSetup8MTF { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 9 Gap", Description = "Enable Gap Fill Setup", Order = 14, GroupName = "Setup Controls")]
        public bool EnableSetup9Gap { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 10 Retest", Description = "Enable Level Retest Setup", Order = 15, GroupName = "Setup Controls")]
        public bool EnableSetup10Retest { get; set; } = true;

        #endregion

        #region Missing Strategy Methods and Properties

        // Add missing properties
        [NinjaScriptProperty]
        [Display(Name = "Use Higher Timeframe Confirmation", Description = "Use higher timeframe confirmation", Order = 16, GroupName = "Setup Controls")]
        public bool UseHigherTimeframeConfirmation { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Use Fixed Contracts", Description = "Use fixed contract size", Order = 17, GroupName = "Risk Management")]
        public bool UseFixedContracts { get; set; } = false;

        [NinjaScriptProperty]
        [Display(Name = "Fixed Contracts", Description = "Fixed contract size", Order = 18, GroupName = "Risk Management")]
        public int FixedContracts { get; set; } = 1;

        [NinjaScriptProperty]
        [Display(Name = "Enable Regime Adjustment", Description = "Enable regime-based adjustments", Order = 19, GroupName = "Risk Management")]
        public bool EnableRegimeAdjustment { get; set; } = false;

        // Add missing methods
        private bool IsInUptrend()
        {
            try
            {
                // Check if EMA9 is above longer-term average
                if (ema9 != null && CurrentBar > 20)
                {
                    var sma20 = SMA(Close, 20)[0];
                    return ema9[0] > sma20 && ema9[0] > ema9[5];
                }
                return false;
            }
            catch
            {
                return false;
            }
        }

        private bool IsHammerCandle()
        {
            try
            {
                if (CurrentBar < 1) return false;
                
                double bodySize = Math.Abs(Close[0] - Open[0]);
                double lowerShadow = Math.Min(Open[0], Close[0]) - Low[0];
                double upperShadow = High[0] - Math.Max(Open[0], Close[0]);
                double candleRange = High[0] - Low[0];
                
                return lowerShadow > (bodySize * 2) && 
                       upperShadow < (bodySize * 0.5) && 
                       candleRange > (atr[0] * 0.5);
            }
            catch
            {
                return false;
            }
        }

        private bool IsBullishEngulfing()
        {
            try
            {
                if (CurrentBar < 1) return false;
                
                bool prevBearish = Close[1] < Open[1];
                bool currentBullish = Close[0] > Open[0];
                bool engulfs = Close[0] > Open[1] && Open[0] < Close[1];
                
                return prevBearish && currentBullish && engulfs;
            }
            catch
            {
                return false;
            }
        }

        private bool IsWithinTradingHours()
        {
            try
            {
                var now = DateTime.Now;
                var hour = now.Hour;
                // Standard market hours (9:30 AM to 4:00 PM ET)
                return hour >= 9 && hour <= 16;
            }
            catch
            {
                return true; // Default to allow trading
            }
        }

        #endregion

        #region Enhanced Strategy Methods

        /// <summary>
        /// Enhanced OnBarUpdate with system monitoring
        /// </summary>
        protected override void OnBarUpdate()
        {
            try
            {
                // Ensure minimum bars for strategy operation
                if (CurrentBar < 20)
                {
                    return;
                }

                // Check if indicators are properly initialized
                if (ema9 == null || atr == null || volumeAvg == null)
                {
                    return;
                }

                // Monitor system health
                MonitorSystemHealth();
                
                // Check if trading is enabled
                if (!tradingEnabled)
                {
                    return;
                }

                // Update signal quality using enhanced methods - with safe fallback
                var defaultSetup = new TradeSetup 
                { 
                    Code = "GENERAL", 
                    QualityBonus = 1.0,
                    ATRStopMultiplier = 1.8,
                    ATRTargetMultiplier = 2.2
                };
                
                currentSignalQuality = GetEnhancedSignalQuality(defaultSetup);

                // Check for trade setups using enhanced methods
                foreach (var setup in activeSetups.Where(s => s.Enabled))
                {
                    if (CheckSetupConditions(setup))
                    {
                        ExecuteTradeSetup(setup);
                    }
                }
            }
            catch (Exception ex)
            {
                LogDebug("STRATEGY", $"Error in OnBarUpdate: {ex.Message}", "ERROR");
            }
        }

        /// <summary>
        /// Enhanced trade execution using ML position sizing
        /// </summary>
        private void ExecuteTradeSetup(TradeSetup setup)
        {
            try
            {
                // Calculate enhanced position size
                double stopDistance = GetAdaptiveATRMultiplier(setup) * GetEnhancedATR();
                int positionSize = CalculateEnhancedPositionSize(setup, stopDistance);

                // Use enhanced signal quality
                double enhancedQuality = GetEnhancedSignalQuality(setup);

                if (enhancedQuality < setup.MinQuality)
                {
                    LogDebug("TRADE", $"Setup {setup.Code} rejected - Quality {enhancedQuality:F2} < {setup.MinQuality:F2}", "INFO");
                    return;
                }

                // Execute trade with enhanced parameters
                if (setup.IsLong)
                {
                    EnterLong(positionSize, setup.Code);
                }
                else
                {
                    EnterShort(positionSize, setup.Code);
                }

                LogDebug("TRADE", $"Executed {setup.Code} - Size: {positionSize}, Quality: {enhancedQuality:F2}", "INFO");
            }
            catch (Exception ex)
            {
                LogDebug("TRADE", $"Error executing trade setup {setup.Code}: {ex.Message}", "ERROR");
            }
        }

        /// <summary>
        /// Enhanced setup condition checking
        /// </summary>
        private bool CheckSetupConditions(TradeSetup setup)
        {
            try
            {
                // Use enhanced signal quality analysis
                var enhancedQuality = GetEnhancedSignalQuality(setup);
                
                // Check if quality meets threshold
                if (enhancedQuality < setup.MinQuality)
                {
                    return false;
                }

                // Additional enhanced checks based on setup type
                switch (setup.Code)
                {
                    case "EMA9_VWAP_BULLISH":
                        return CheckSetup1_EMAVWAPBreakout();
                    case "EMA9_VWAP_BEARISH":
                        return CheckSetup2_EMAVWAPBreakdown();
                    case "VWAP_REJECTION":
                        return CheckSetup3_VWAPRejection();
                    case "SUPPORT_RESISTANCE":
                        return CheckSetup4_SupportResistanceAO();
                    case "PIVOT_POINT":
                        return CheckSetup5_PivotZoneReversal();
                    case "MANIPULATION":
                        return CheckSetup6_ManipulationCandle();
                    case "VOLUME_PRICE_ANALYSIS":
                        return CheckSetup7_VPA();
                    case "MULTI_TIMEFRAME":
                        return CheckSetup8_MomentumAlignment();
                    case "GAP_FILL":
                        return CheckSetup9_GapFill();
                    case "LEVEL_RETEST":
                        return CheckSetup10_BreakoutRetest();
                    default:
                        return false;
                }
            }
            catch (Exception ex)
            {
                LogDebug("SETUP", $"Error checking setup conditions for {setup.Code}: {ex.Message}", "ERROR");
                return false;
            }
        }

        /// <summary>
        /// Initialize infrastructure with enhanced monitoring
        /// </summary>
        private void InitializeInfrastructure()
        {
            try
            {
                lock (infrastructureLock)
                {
                    if (infrastructureInitialized)
                        return;

                    // Initialize component metrics
                    componentMetrics["TradesExecuted"] = 0;
                    componentMetrics["SignalQuality"] = 0.0;
                    componentMetrics["SystemHealth"] = "HEALTHY";
                    componentMetrics["LastUpdate"] = DateTime.Now;

                    // Initialize performance metrics
                    performanceMetrics["WinRate"] = 0.0;
                    performanceMetrics["ProfitFactor"] = 0.0;
                    performanceMetrics["MaxDrawdown"] = 0.0;
                    performanceMetrics["AverageWin"] = 0.0;
                    performanceMetrics["AverageLoss"] = 0.0;

                    // Initialize signal quality metrics
                    signalQualityMetrics["CurrentQuality"] = 0.0;
                    signalQualityMetrics["AverageQuality"] = 0.0;
                    signalQualityMetrics["QualityTrend"] = 0.0;

                    infrastructureInitialized = true;
                    lastInfrastructureUpdate = DateTime.Now;

                    LogDebug("INFRASTRUCTURE", "Enhanced infrastructure initialized successfully", "INFO");
                }
            }
            catch (Exception ex)
            {
                LogDebug("INFRASTRUCTURE", $"Error initializing infrastructure: {ex.Message}", "ERROR");
            }
        }

        #endregion

        #region Enhanced OnStateChange with Proper Initialization

        protected override void OnStateChange()
        {
            try
            {
                if (State == State.SetDefaults)
                {
                    // Set strategy defaults
                    Description = "Enhanced FKS Strategy with ML Integration";
                    Name = "FKS_Strategy";
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
                    BarsRequiredToTrade = 20;
                    
                    // Initialize FKS Component
                    Initialize();
                }
                else if (State == State.DataLoaded)
                {
                    // Initialize indicators
                    try
                    {
                        ema9 = EMA(Close, 9);
                        atr = ATR(Close, 14);
                        volume = VOL();
                        volumeAvg = SMA(volume, 20);
                        
                        // Initialize FKS indicators
                        // FKS_AI requires parameters: assetType, showSRBands, showSignalLabels, showEntryZones, showWaveInfo, showMarketPhase, cleanChartMode
                        fksAI = new NinjaTrader.NinjaScript.Indicators.FKS.FKS_AI();
                        fksAO = new NinjaTrader.NinjaScript.Indicators.FKS.FKS_AO();
                        fksVWAP = new NinjaTrader.NinjaScript.Indicators.FKS.FKS_AI();

                        // Add them to the chart if needed
                        AddChartIndicator(fksAI);
                        AddChartIndicator(fksAO);
                        AddChartIndicator(fksVWAP);
                        
                        LogDebug("INITIALIZATION", "FKS indicators initialized", "INFO");
                        
                        // Initialize setups
                        InitializeSetups();
                        
                        LogDebug("INITIALIZATION", "Strategy indicators initialized successfully", "INFO");
                    }
                    catch (Exception ex)
                    {
                        LogDebug("INITIALIZATION", $"Error initializing indicators: {ex.Message}", "ERROR");
                    }
                }
                else if (State == State.Terminated)
                {
                    // Cleanup
                    Shutdown();
                }
            }
            catch (Exception ex)
            {
                LogDebug("STATE_CHANGE", $"Error in OnStateChange: {ex.Message}", "ERROR");
            }
        }

        #endregion
    }
}