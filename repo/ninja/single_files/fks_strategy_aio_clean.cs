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
using NinjaTrader.NinjaScript.Indicators.FKS;
using NinjaTrader.NinjaScript.AddOns.FKS;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class FKS_Strategy_AIO : Strategy
    {
        #region Variables
        // Account and Risk Management
        private const double ACCOUNT_SIZE = 150000;
        private const int MAX_TOTAL_CONTRACTS = 15;
        private int maxDailyTrades = 6;
        private int maxConsecutiveLosses = 3;
        private double dailyLossLimitPercent = 0.02;
        private double dailyProfitTargetPercent = 0.015;
        
        // Indicators
        private FKS_AI fksAI;
        private FKS_AO fksAO;
        private FKS_VWAP_Indicator fksVWAP;
        private FKS_Dashboard fksInfo;
        
        // Standard Indicators
        private EMA ema9;
        private ATR atr;
        private VOL volume;
        private SMA volumeAvg;
        
        // Trade Management
        private List<TradeSetup> activeSetups = new List<TradeSetup>();
        private TradeSetup currentTrade;
        private double entryPrice;
        private double stopLoss;
        private double target1;
        private double target2;
        private bool target1Hit;
        private int positionContracts;
        
        // Daily Tracking
        private DateTime currentDay = DateTime.MinValue;
        private int todaysTrades = 0;
        private double currentDailyPnL = 0;
        private int consecutiveLosses = 0;
        private bool tradingEnabled = true;
        
        // Setup Tracking
        private Dictionary<string, int> setupExecutions = new Dictionary<string, int>();
        private Dictionary<string, double> setupPerformance = new Dictionary<string, double>();
        
        // Debug
        private bool debugMode = true;
        private StringBuilder tradeLog = new StringBuilder();
        #endregion

        #region Trade Setup Definitions
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
            public double ATRStopMultiplier { get; set; } = 2.0;
            public double ATRTargetMultiplier { get; set; } = 3.0;
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
                MinQuality = Setup1MinQuality,
                Condition = () =>
                {
                    if (!EnableSetup1Bullish) return false;
                    
                    // Price > EMA9 > VWAP alignment
                    if (Close[0] <= ema9[0]) return false;
                    if (ema9[0] <= fksVWAP.GetVWAP()) return false;
                    
                    // AI Signal confirmation
                    if (fksAI.SignalType != "G" && fksAI.SignalType != "^") return false;
                    if (fksAI.SignalQuality < Setup1MinQuality) return false;
                    
                    // AO Confirmation
                    if (!fksAO.IsBullish || fksAO.Value <= 0) return false;
                    
                    // Volume confirmation
                    if (volume[0] < volumeAvg[0] * VolumeThreshold) return false;
                    
                    // Breakout confirmation
                    double swingHigh = MAX(High, 10)[1];
                    if (Close[0] > swingHigh && Close[1] <= swingHigh)
                    {
                        LogSetupTrigger("Setup 1 Bullish", fksAI.SignalQuality);
                        return true;
                    }
                    
                    return false;
                },
                Description = "Bullish breakout with stacked alignment (Price > EMA9 > VWAP)",
                Notes = "Best in trending markets during optimal hours. Look for volume surge on breakout."
            });
            
            // Setup 2: EMA9 + VWAP Bearish Breakdown
            activeSetups.Add(new TradeSetup
            {
                Name = "EMA9_VWAP_Bearish",
                Code = "S2S",
                IsLong = false,
                Enabled = EnableSetup2Bearish,
                MinQuality = Setup2MinQuality,
                Condition = () =>
                {
                    if (!EnableSetup2Bearish) return false;
                    
                    // Price < EMA9 < VWAP alignment
                    if (Close[0] >= ema9[0]) return false;
                    if (ema9[0] >= fksVWAP.GetVWAP()) return false;
                    
                    // AI Signal confirmation
                    if (fksAI.SignalType != "Top" && fksAI.SignalType != "v") return false;
                    if (fksAI.SignalQuality < Setup2MinQuality) return false;
                    
                    // AO Confirmation
                    if (!fksAO.IsBearish || fksAO.Value >= 0) return false;
                    
                    // Volume confirmation
                    if (volume[0] < volumeAvg[0] * VolumeThreshold) return false;
                    
                    // Breakdown confirmation
                    double swingLow = MIN(Low, 10)[1];
                    if (Close[0] < swingLow && Close[1] >= swingLow)
                    {
                        LogSetupTrigger("Setup 2 Bearish", fksAI.SignalQuality);
                        return true;
                    }
                    
                    return false;
                },
                Description = "Bearish breakdown with stacked alignment (Price < EMA9 < VWAP)",
                Notes = "Watch for failed highs before entry. Stronger in downtrending markets."
            });
            
            // Setup 3: VWAP Rejection Bounce
            activeSetups.Add(new TradeSetup
            {
                Name = "VWAP_Rejection",
                Code = "S3L",
                IsLong = true,
                Enabled = EnableSetup3VWAP,
                MinQuality = Setup3MinQuality,
                Condition = () =>
                {
                    if (!EnableSetup3VWAP) return false;
                    
                    // Must be near VWAP
                    double vwap = fksVWAP.GetVWAP();
                    double distance = Math.Abs(Close[0] - vwap) / atr[0];
                    if (distance > 0.5) return false;
                    
                    // AI Signal at support
                    if (fksAI.SignalType != "G") return false;
                    if (fksAI.SignalQuality < Setup3MinQuality) return false;
                    if (!IsNearSupport()) return false;
                    
                    // AO Divergence or momentum shift
                    bool bullishDiv = CheckBullishDivergence();
                    if (!bullishDiv && !fksAO.IsAccelerating) return false;
                    
                    // Rejection candle pattern
                    if (IsHammerCandle() || IsBullishEngulfing())
                    {
                        LogSetupTrigger("Setup 3 VWAP Bounce", fksAI.SignalQuality);
                        return true;
                    }
                    
                    return false;
                },
                Description = "VWAP rejection with support confluence and reversal pattern",
                Notes = "Requires clean rejection candle. Works best in ranging markets.",
                ATRStopMultiplier = 1.5,
                ATRTargetMultiplier = 2.5
            });
            
            // Setup 4: S/R + AO Zero Cross
            activeSetups.Add(new TradeSetup
            {
                Name = "SR_AO_Cross",
                Code = "S4X",
                IsLong = true, // Direction determined dynamically
                Enabled = EnableSetup4SR,
                MinQuality = Setup4MinQuality,
                Condition = () =>
                {
                    if (!EnableSetup4SR) return false;
                    
                    // Must be at key S/R level
                    bool atSupport = IsNearSupport();
                    bool atResistance = IsNearResistance();
                    if (!atSupport && !atResistance) return false;
                    
                    // AO must cross zero
                    if (fksAO.CrossDirection == 0) return false;
                    
                    // AI Signal quality check
                    if (fksAI.SignalQuality < Setup4MinQuality) return false;
                    
                    // Volume confirmation
                    if (volume[0] < volumeAvg[0] * VolumeThreshold) return false;
                    
                    // Direction based on AO and location
                    bool goLong = fksAO.CrossDirection > 0 && atSupport;
                    bool goShort = fksAO.CrossDirection < 0 && atResistance;
                    
                    if (goLong || goShort)
                    {
                        // Update direction for this instance
                        var setup = activeSetups.FirstOrDefault(s => s.Code == "S4X");
                        if (setup != null) setup.IsLong = goLong;
                        
                        LogSetupTrigger("Setup 4 S/R + AO", fksAI.SignalQuality);
                        return true;
                    }
                    
                    return false;
                },
                Description = "Support/Resistance level with AO zero line cross",
                Notes = "Most reliable at major S/R levels. Confirm with multiple timeframes.",
                ATRTargetMultiplier = 3.5
            });
            
            // Setup 5: Momentum Surge
            activeSetups.Add(new TradeSetup
            {
                Name = "Momentum_Surge",
                Code = "S5M",
                IsLong = true, // Direction determined by momentum
                Enabled = EnableSetup5Momentum,
                MinQuality = 0.60,
                Condition = () =>
                {
                    if (!EnableSetup5Momentum) return false;
                    
                    // Strong momentum required
                    if (fksAO.MomentumStrength < 0.7) return false;
                    if (!fksAO.IsAccelerating) return false;
                    
                    // AI Signal alignment
                    bool bullishMomentum = fksAO.Value > 0 && fksAO.CrossDirection > 0;
                    bool bearishMomentum = fksAO.Value < 0 && fksAO.CrossDirection < 0;
                    
                    if (bullishMomentum && (fksAI.SignalType == "G" || fksAI.SignalType == "^"))
                    {
                        var setup = activeSetups.FirstOrDefault(s => s.Code == "S5M");
                        if (setup != null) setup.IsLong = true;
                        LogSetupTrigger("Setup 5 Bullish Momentum", fksAO.MomentumStrength);
                        return true;
                    }
                    else if (bearishMomentum && (fksAI.SignalType == "Top" || fksAI.SignalType == "v"))
                    {
                        var setup = activeSetups.FirstOrDefault(s => s.Code == "S5M");
                        if (setup != null) setup.IsLong = false;
                        LogSetupTrigger("Setup 5 Bearish Momentum", fksAO.MomentumStrength);
                        return true;
                    }
                    
                    return false;
                },
                Description = "High momentum acceleration with directional confirmation",
                Notes = "Quick scalp setup. Use tight stops and take profits quickly."
            });
            
            // Setup 6: VWAP + EMA9 Cross
            activeSetups.Add(new TradeSetup
            {
                Name = "VWAP_EMA_Cross",
                Code = "S6C",
                IsLong = true,
                Enabled = EnableSetup6Cross,
                MinQuality = 0.55,
                Condition = () =>
                {
                    if (!EnableSetup6Cross) return false;
                    
                    // Check for fresh crossover
                    var crossState = fksVWAP.GetCrossoverState();
                    if (fksVWAP.GetBarsSinceCrossover() > 3) return false;
                    
                    // Bullish cross
                    if (fksVWAP.IsBullishCrossover())
                    {
                        // Confirm with AI signal
                        if (fksAI.SignalType == "G" || fksAI.SignalType == "^")
                        {
                            LogSetupTrigger("Setup 6 Bullish Cross", fksAI.SignalQuality);
                            return true;
                        }
                    }
                    
                    return false;
                },
                Description = "EMA9 crossing above VWAP with signal confirmation",
                Notes = "Early entry setup. Best in beginning of trends."
            });
        }
        #endregion

        #region State Management
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"FKS Strategy AIO - Modular setup system with indicator integration";
                Name = "FKS_Strategy_AIO";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 900;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 200;
                
                // Initialize default parameters
                InitializeDefaultParameters();
            }
            else if (State == State.Configure)
            {
                // Add data series for multi-timeframe analysis
                AddDataSeries(BarsPeriodType.Minute, 5);   // Higher timeframe
                AddDataSeries(BarsPeriodType.Minute, 15);  // Context timeframe
            }
            else if (State == State.DataLoaded)
            {
                InitializeIndicators();
                InitializeSetups();
                InitializeFKSCore();
                
                if (debugMode)
                {
                    Print("=== FKS Strategy AIO Initialized ===");
                    Print($"Enabled Setups: {CountEnabledSetups()}");
                    PrintEnabledSetups();
                }
            }
            else if (State == State.Terminated)
            {
                // Clean up and export logs
                if (ExportTradeLog && tradeLog.Length > 0)
                {
                    ExportTradeLogs();
                }
                
                // Unregister from FKS Core
                FKS_Core.UnregisterComponent("FKS_Strategy");
            }
        }
        
        private void InitializeIndicators()
        {
            // Initialize FKS indicators
            fksAI = FKS_AI();
            fksAO = FKS_AO();
            fksVWAP = FKS_VWAP_Indicator();
            fksInfo = FKS_Dashboard();
            
            // Standard indicators
            ema9 = EMA(9);
            atr = ATR(14);
            volume = VOL();
            volumeAvg = SMA(volume, 20);
        }
        
        private void InitializeFKSCore()
        {
            // Initialize FKS Core system
            FKS_Core.Initialize();
            
            // Set market configuration
            string instrumentType = DetectInstrumentType();
            FKS_Core.SetMarket(instrumentType);
            
            // Register strategy component
            FKS_Core.RegisterComponent("FKS_Strategy", new StrategyComponent(this));
            
            // Subscribe to events
            FKS_Core.SignalGenerated += OnSignalGenerated;
            FKS_Core.MarketRegimeChanged += OnMarketRegimeChanged;
        }
        
        private void InitializeDefaultParameters()
        {
            // Setup toggles
            EnableSetup1Bullish = true;
            EnableSetup2Bearish = true;
            EnableSetup3VWAP = true;
            EnableSetup4SR = true;
            EnableSetup5Momentum = false;
            EnableSetup6Cross = false;
            
            // Quality thresholds
            Setup1MinQuality = 0.65;
            Setup2MinQuality = 0.65;
            Setup3MinQuality = 0.60;
            Setup4MinQuality = 0.70;
            
            // Risk parameters
            ATRStopMultiplier = 2.0;
            ATRTargetMultiplier = 3.0;
            VolumeThreshold = 1.2;
            
            // Position sizing
            UseFixedContracts = false;
            FixedContracts = 1;
            EnableRegimeAdjustment = true;
            
            // Trading hours
            EnableTimeFilter = true;
            StartHour = 8;
            EndHour = 15;
            
            // Logging
            DebugMode = true;
            ExportTradeLog = true;
        }
        #endregion

        #region Main Trading Logic
        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade) return;
            if (BarsInProgress != 0) return; // Only process primary series
            
            try
            {
                // Update daily counters
                CheckNewTradingDay();
                
                // Check if we should continue trading
                if (!ShouldContinueTrading())
                {
                    if (debugMode && CurrentBar % 50 == 0)
                        Print($"Trading disabled - Trades: {todaysTrades}/{maxDailyTrades}, P&L: {currentDailyPnL:C}");
                    return;
                }
                
                // Check time filter
                if (EnableTimeFilter && !IsWithinTradingHours())
                    return;
                
                // Manage existing position
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    ManagePosition();
                    return;
                }
                
                // Check for new signals
                CheckAllSetups();
                
                // Update performance tracking
                if (CurrentBar % 100 == 0)
                {
                    UpdatePerformanceMetrics();
                }
            }
            catch (Exception ex)
            {
                Print($"Error in OnBarUpdate: {ex.Message}");
                Log($"Error in OnBarUpdate: {ex.Message}", LogLevel.Error);
            }
        }
        
        private void CheckAllSetups()
        {
            foreach (var setup in activeSetups.Where(s => s.Enabled))
            {
                try
                {
                    if (setup.Condition())
                    {
                        ExecuteTrade(setup);
                        break; // Only one trade at a time
                    }
                }
                catch (Exception ex)
                {
                    Print($"Error checking setup {setup.Name}: {ex.Message}");
                }
            }
        }
        
        private void ExecuteTrade(TradeSetup setup)
        {
            // Calculate position size
            int contracts = CalculatePositionSize(setup);
            if (contracts == 0) return;
            
            // Calculate stops and targets
            CalculateStopsAndTargets(setup);
            
            // Log trade entry
            LogTradeEntry(setup, contracts);
            
            // Execute trade
            if (setup.IsLong)
            {
                EnterLong(contracts, setup.Code);
            }
            else
            {
                EnterShort(contracts, setup.Code);
            }
            
            // Update tracking
            currentTrade = setup;
            entryPrice = Close[0];
            positionContracts = contracts;
            target1Hit = false;
            todaysTrades++;
            
            // Track setup execution
            if (!setupExecutions.ContainsKey(setup.Name))
                setupExecutions[setup.Name] = 0;
            setupExecutions[setup.Name]++;
        }
        
        private int CalculatePositionSize(TradeSetup setup)
        {
            if (UseFixedContracts)
                return FixedContracts;
            
            // Get signal quality-based sizing
            var signalInputs = BuildSignalInputs();
            var signal = FKS_Signals.GenerateSignal(signalInputs);
            
            int baseContracts = signal.RecommendedContracts;
            
            // Apply regime adjustment if enabled
            if (EnableRegimeAdjustment)
            {
                var regime = FKS_Market.AnalyzeMarketRegime(
                    DetectInstrumentType(),
                    atr[0],
                    (ema9[0] - ema9[20]) / 20,
                    volume[0] / volumeAvg[0],
                    High[0] - Low[0]
                );
                
                var dynamicParams = FKS_Market.GetDynamicParameters(DetectInstrumentType(), regime);
                baseContracts = (int)(baseContracts * dynamicParams.PositionSizeAdjustment);
            }
            
            // Apply consecutive loss reduction
            if (consecutiveLosses >= 2)
                baseContracts = Math.Max(1, baseContracts / 2);
            
            return Math.Max(1, Math.Min(baseContracts, MAX_TOTAL_CONTRACTS));
        }
        
        private void CalculateStopsAndTargets(TradeSetup setup)
        {
            double atrValue = atr[0];
            double stopMultiplier = setup.ATRStopMultiplier;
            double targetMultiplier = setup.ATRTargetMultiplier;
            
            if (setup.IsLong)
            {
                stopLoss = Close[0] - (atrValue * stopMultiplier);
                target1 = Close[0] + (atrValue * targetMultiplier);
                target2 = Close[0] + (atrValue * targetMultiplier * 1.5);
            }
            else
            {
                stopLoss = Close[0] + (atrValue * stopMultiplier);
                target1 = Close[0] - (atrValue * targetMultiplier);
                target2 = Close[0] - (atrValue * targetMultiplier * 1.5);
            }
        }
        #endregion

        #region Position Management
        private void ManagePosition()
        {
            // Check stop loss
            if (CheckStopLoss())
            {
                ExitPosition("StopLoss");
                return;
            }
            
            // Check targets
            if (!target1Hit && CheckTarget1())
            {
                // Scale out half at target 1
                int exitQuantity = positionContracts / 2;
                if (Position.MarketPosition == MarketPosition.Long)
                    ExitLong(exitQuantity, "Target1", "");
                else
                    ExitShort(exitQuantity, "Target1", "");
                
                target1Hit = true;
                stopLoss = entryPrice; // Move stop to breakeven
            }
            
            if (target1Hit && CheckTarget2())
            {
                ExitPosition("Target2");
                return;
            }
            
            // Trail stop after target 1
            if (target1Hit)
            {
                UpdateTrailingStop();
            }
            
            // Check for adverse exit signals
            if (CheckAdverseExit())
            {
                ExitPosition("AdverseSignal");
                return;
            }
        }
        
        private bool CheckStopLoss()
        {
            if (Position.MarketPosition == MarketPosition.Long)
                return Low[0] <= stopLoss;
            else if (Position.MarketPosition == MarketPosition.Short)
                return High[0] >= stopLoss;
            
            return false;
        }
        
        private bool CheckTarget1()
        {
            if (Position.MarketPosition == MarketPosition.Long)
                return High[0] >= target1;
            else if (Position.MarketPosition == MarketPosition.Short)
                return Low[0] <= target1;
            
            return false;
        }
        
        private bool CheckTarget2()
        {
            if (Position.MarketPosition == MarketPosition.Long)
                return High[0] >= target2;
            else if (Position.MarketPosition == MarketPosition.Short)
                return Low[0] <= target2;
            
            return false;
        }
        
        private void UpdateTrailingStop()
        {
            double trailDistance = atr[0] * 1.5;
            
            if (Position.MarketPosition == MarketPosition.Long)
            {
                double newStop = Close[0] - trailDistance;
                if (newStop > stopLoss && newStop > entryPrice)
                    stopLoss = newStop;
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                double newStop = Close[0] + trailDistance;
                if (newStop < stopLoss && newStop < entryPrice)
                    stopLoss = newStop;
            }
        }
        
        private bool CheckAdverseExit()
        {
            // Exit on strong momentum reversal
            if (Position.MarketPosition == MarketPosition.Long)
            {
                if (fksAO.Value < 0 && fksAO.CrossDirection < 0 && Close[0] < ema9[0])
                    return true;
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                if (fksAO.Value > 0 && fksAO.CrossDirection > 0 && Close[0] > ema9[0])
                    return true;
            }
            
            return false;
        }
        
        private void ExitPosition(string reason)
        {
            if (Position.MarketPosition == MarketPosition.Long)
                ExitLong(reason);
            else if (Position.MarketPosition == MarketPosition.Short)
                ExitShort(reason);
        }
        #endregion

        #region Helper Methods
        private bool IsNearSupport()
        {
            double support = fksAI.NearestSupport;
            double distance = Math.Abs(Low[0] - support) / atr[0];
            return distance < 0.3;
        }
        
        private bool IsNearResistance()
        {
            double resistance = fksAI.NearestResistance;
            double distance = Math.Abs(High[0] - resistance) / atr[0];
            return distance < 0.3;
        }
        
        private bool CheckBullishDivergence()
        {
            // Simple divergence check
            if (CurrentBar < 20) return false;
            
            double priceLow1 = MIN(Low, 10)[0];
            double priceLow2 = MIN(Low, 10)[10];
            double aoLow1 = MIN(fksAO.Value, 10)[0];
            double aoLow2 = MIN(fksAO.Value, 10)[10];
            
            return priceLow1 < priceLow2 && aoLow1 > aoLow2;
        }
        
        private bool IsHammerCandle()
        {
            double bodySize = Math.Abs(Close[0] - Open[0]);
            double lowerWick = Math.Min(Open[0], Close[0]) - Low[0];
            double upperWick = High[0] - Math.Max(Open[0], Close[0]);
            
            return lowerWick > bodySize * 2 && upperWick < bodySize * 0.3 && Close[0] > Open[0];
        }
        
        private bool IsBullishEngulfing()
        {
            if (CurrentBar < 1) return false;
            
            return Close[1] < Open[1] && // Previous bearish
                   Close[0] > Open[0] && // Current bullish
                   Open[0] <= Close[1] && // Engulfs body
                   Close[0] >= Open[1];
        }
        
        private string DetectInstrumentType()
        {
            string instrumentName = Instrument.MasterInstrument.Name.ToUpper();
            
            if (instrumentName.Contains("GC") || instrumentName.Contains("GOLD"))
                return "Gold";
            else if (instrumentName.Contains("ES"))
                return "ES";
            else if (instrumentName.Contains("NQ"))
                return "NQ";
            else if (instrumentName.Contains("CL") || instrumentName.Contains("CRUDE"))
                return "CL";
            else if (instrumentName.Contains("BTC"))
                return "BTC";
            else
                return "Gold"; // Default
        }
        
        private bool IsWithinTradingHours()
        {
            int currentHour = Time[0].Hour;
            return currentHour >= StartHour && currentHour < EndHour;
        }
        
        private void CheckNewTradingDay()
        {
            if (Time[0].Date != currentDay)
            {
                currentDay = Time[0].Date;
                ResetDailyCounters();
            }
        }
        
        private void ResetDailyCounters()
        {
            todaysTrades = 0;
            currentDailyPnL = 0;
            consecutiveLosses = 0;
            tradingEnabled = true;
            
            if (debugMode)
            {
                Print($"\n=== NEW TRADING DAY: {currentDay:yyyy-MM-dd} ===");
                Print($"Daily Loss Limit: {ACCOUNT_SIZE * dailyLossLimitPercent:C}");
                Print($"Daily Profit Target: {ACCOUNT_SIZE * dailyProfitTargetPercent:C}");
            }
        }
        
        private bool ShouldContinueTrading()
        {
            // Check daily trade limit
            if (todaysTrades >= maxDailyTrades)
                return false;
            
            // Check consecutive losses
            if (consecutiveLosses >= maxConsecutiveLosses)
                return false;
            
            // Check daily loss limit
            if (currentDailyPnL <= -ACCOUNT_SIZE * dailyLossLimitPercent)
                return false;
            
            return tradingEnabled;
        }
        
        private int CountEnabledSetups()
        {
            return activeSetups.Count(s => s.Enabled);
        }
        
        private void PrintEnabledSetups()
        {
            foreach (var setup in activeSetups.Where(s => s.Enabled))
            {
                Print($"  - {setup.Name}: {setup.Description}");
            }
        }
        
        private FKS_Signals.SignalInputs BuildSignalInputs()
        {
            return new FKS_Signals.SignalInputs
            {
                // AI Indicator inputs
                AISignalType = fksAI.SignalType,
                AISignalQuality = fksAI.SignalQuality,
                WaveRatio = fksAI.CurrentWaveRatio,
                NearSupport = IsNearSupport(),
                NearResistance = IsNearResistance(),
                
                // AO Indicator inputs
                AOValue = fksAO.Value,
                AOSignal = fksAO.Signal,
                AOConfirmation = fksAO.HasBullishConfirmation() || fksAO.HasBearishConfirmation(),
                AOZeroCross = fksAO.CrossDirection != 0,
                AOMomentumStrength = fksAO.MomentumStrength,
                
                // Market data
                Price = Close[0],
                ATR = atr[0],
                VolumeRatio = volume[0] / volumeAvg[0],
                MarketType = DetectInstrumentType(),
                MarketRegime = fksAI.MarketRegime,
                
                // Technical inputs
                PriceAboveEMA9 = Close[0] > ema9[0],
                EMA9AboveVWAP = ema9[0] > fksVWAP.GetVWAP(),
                NearVWAP = fksVWAP.IsNearVWAP(0.1),
                HasCandleConfirmation = IsHammerCandle() || IsBullishEngulfing(),
                
                // Session info
                IsOptimalSession = IsWithinTradingHours()
            };
        }
        #endregion

        #region Logging and Performance
        private void LogSetupTrigger(string setupName, double quality)
        {
            if (debugMode)
            {
                Print($"\n*** SETUP TRIGGERED: {setupName} ***");
                Print($"Time: {Time[0]:HH:mm:ss}, Price: {Close[0]:F2}");
                Print($"Quality: {quality:P1}, AI Signal: {fksAI.SignalType}");
                Print($"AO: {fksAO.Value:F4}, Momentum: {fksAO.MomentumStrength:P0}");
                Print($"Volume: {volume[0]/volumeAvg[0]:F1}x average");
            }
        }
        
        private void LogTradeEntry(TradeSetup setup, int contracts)
        {
            string entry = $"{Time[0]:yyyy-MM-dd HH:mm:ss},{setup.Name},{setup.Code}," +
                          $"{(setup.IsLong ? "LONG" : "SHORT")},{contracts},{Close[0]:F2}," +
                          $"{stopLoss:F2},{target1:F2},{fksAI.SignalQuality:F2}";
            
            tradeLog.AppendLine(entry);
            
            if (debugMode)
            {
                Print($"Stop: {stopLoss:F2}, T1: {target1:F2}, T2: {target2:F2}");
            }
        }
        
        protected override void OnPositionUpdate(Position position, double averagePrice, 
            int quantity, MarketPosition marketPosition)
        {
            if (position.MarketPosition == MarketPosition.Flat && marketPosition != MarketPosition.Flat)
            {
                // Position closed
                OnPositionClosed();
            }
        }
        
        private void OnPositionClosed()
        {
            if (SystemPerformance.AllTrades.Count > 0)
            {
                Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                double tradePnL = lastTrade.ProfitCurrency;
                currentDailyPnL += tradePnL;
                
                // Update setup performance
                if (currentTrade != null && !setupPerformance.ContainsKey(currentTrade.Name))
                    setupPerformance[currentTrade.Name] = 0;
                
                if (currentTrade != null)
                    setupPerformance[currentTrade.Name] += tradePnL;
                
                // Update consecutive losses
                if (tradePnL < 0)
                    consecutiveLosses++;
                else
                    consecutiveLosses = 0;
                
                // Log trade result
                string result = $"{lastTrade.Exit.Time:yyyy-MM-dd HH:mm:ss}," +
                               $"{lastTrade.Exit.Price:F2},{tradePnL:F2}," +
                               $"{(tradePnL > 0 ? "WIN" : "LOSS")}";
                
                tradeLog.AppendLine(result);
                
                if (debugMode)
                {
                    Print($"\nTrade Closed - {currentTrade?.Name ?? "Unknown"}");
                    Print($"P&L: {tradePnL:C}, Daily Total: {currentDailyPnL:C}");
                }
            }
            
            currentTrade = null;
        }
        
        private void UpdatePerformanceMetrics()
        {
            if (!debugMode || setupExecutions.Count == 0) return;
            
            Print("\n=== SETUP PERFORMANCE ===");
            foreach (var kvp in setupExecutions)
            {
                double pnl = setupPerformance.ContainsKey(kvp.Key) ? setupPerformance[kvp.Key] : 0;
                Print($"{kvp.Key}: {kvp.Value} trades, P&L: {pnl:C}");
            }
        }
        
        private void ExportTradeLogs()
        {
            try
            {
                string fileName = $"FKS_Trades_{DateTime.Now:yyyyMMdd_HHmmss}.csv";
                string header = "EntryTime,SetupName,Code,Direction,Contracts,EntryPrice," +
                               "StopLoss,Target1,SignalQuality,ExitTime,ExitPrice,PnL,Result";
                
                // In production, write to file
                Print($"\n=== TRADE LOG ===\n{header}\n{tradeLog}");
            }
            catch (Exception ex)
            {
                Print($"Error exporting trade log: {ex.Message}");
            }
        }
        #endregion

        #region Event Handlers
        private void OnSignalGenerated(object sender, FKS_Core.SignalEventArgs e)
        {
            if (debugMode)
            {
                Print($"[FKS Core Signal] {e.Signal.Type} | Quality: {e.Signal.Quality:P0}");
            }
        }
        
        private void OnMarketRegimeChanged(object sender, FKS_Core.MarketEventArgs e)
        {
            if (debugMode)
            {
                Print($"[Market Regime Change] {e.PreviousRegime} -> {e.NewRegime}");
            }
        }
        #endregion

        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 1 (Bullish)", Order = 100, GroupName = "Setup Toggles")]
        public bool EnableSetup1Bullish { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 2 (Bearish)", Order = 101, GroupName = "Setup Toggles")]
        public bool EnableSetup2Bearish { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 3 (VWAP)", Order = 102, GroupName = "Setup Toggles")]
        public bool EnableSetup3VWAP { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 4 (S/R)", Order = 103, GroupName = "Setup Toggles")]
        public bool EnableSetup4SR { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 5 (Momentum)", Order = 104, GroupName = "Setup Toggles")]
        public bool EnableSetup5Momentum { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Enable Setup 6 (Cross)", Order = 105, GroupName = "Setup Toggles")]
        public bool EnableSetup6Cross { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.5, 1.0)]
        [Display(Name = "Setup 1 Min Quality", Order = 200, GroupName = "Quality Thresholds")]
        public double Setup1MinQuality { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.5, 1.0)]
        [Display(Name = "Setup 2 Min Quality", Order = 201, GroupName = "Quality Thresholds")]
        public double Setup2MinQuality { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.5, 1.0)]
        [Display(Name = "Setup 3 Min Quality", Order = 202, GroupName = "Quality Thresholds")]
        public double Setup3MinQuality { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.5, 1.0)]
        [Display(Name = "Setup 4 Min Quality", Order = 203, GroupName = "Quality Thresholds")]
        public double Setup4MinQuality { get; set; }
        
        [NinjaScriptProperty]
        [Range(1.0, 3.0)]
        [Display(Name = "ATR Stop Multiplier", Order = 300, GroupName = "Risk Management")]
        public double ATRStopMultiplier { get; set; }
        
        [NinjaScriptProperty]
        [Range(1.0, 5.0)]
        [Display(Name = "ATR Target Multiplier", Order = 301, GroupName = "Risk Management")]
        public double ATRTargetMultiplier { get; set; }
        
        [NinjaScriptProperty]
        [Range(1.0, 2.0)]
        [Display(Name = "Volume Threshold", Order = 302, GroupName = "Risk Management")]
        public double VolumeThreshold { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Use Fixed Contracts", Order = 400, GroupName = "Position Sizing")]
        public bool UseFixedContracts { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name = "Fixed Contracts", Order = 401, GroupName = "Position Sizing")]
        public int FixedContracts { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Enable Regime Adjustment", Order = 402, GroupName = "Position Sizing")]
        public bool EnableRegimeAdjustment { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Enable Time Filter", Order = 500, GroupName = "Trading Hours")]
        public bool EnableTimeFilter { get; set; }
        
        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Start Hour", Order = 501, GroupName = "Trading Hours")]
        public int StartHour { get; set; }
        
        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "End Hour", Order = 502, GroupName = "Trading Hours")]
        public int EndHour { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Debug Mode", Order = 600, GroupName = "Logging")]
        public bool DebugMode 
        { 
            get { return debugMode; }
            set { debugMode = value; }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "Export Trade Log", Order = 601, GroupName = "Logging")]
        public bool ExportTradeLog { get; set; }
        #endregion

        #region Helper Component Class
        private class StrategyComponent : FKS_Core.IFKSComponent
        {
            private readonly FKS_Strategy_AIO strategy;
            
            public StrategyComponent(FKS_Strategy_AIO strat)
            {
                strategy = strat;
            }
            
            public string ComponentId => "FKS_Strategy";
            public string Version => "1.0.0";
            
            public void Initialize() { }
            public void Shutdown() { }
        }
        #endregion
    }
}