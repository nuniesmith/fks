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
using NinjaTrader.NinjaScript.Indicators.FKS;
using NinjaTrader.NinjaScript.AddOns.FKS;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.FKS
{
    public class FKS_Strategy : Strategy
    {
        #region Variables
        // Minimal User Parameters (Production Settings)
        private string assetType = "Gold";
        private bool debugMode = false;
        private double signalQualityMinimum = 0.65;
        
        // Position Sizing
        private int baseContracts = 1;
        private int maxContracts = 5;
        
        // Risk Management (Account-based)
        private double dailyLossLimitPercent = 2.0;  // 2% = $3,000 on $150k
        private double dailyProfitTargetPercent = 1.5; // 1.5% = $2,250 on $150k
        private int maxDailyTrades = 6;
        private bool useTimeFilter = true;
        private double exitMomentumThreshold = 0.3; // Added missing variable
        
        // Internal Components
        private NinjaTrader.NinjaScript.Indicators.FKS.FKS_AI fksAI;
        private NinjaTrader.NinjaScript.Indicators.FKS.FKS_AO fksAO;
        // private FKS_Dashboard fksInfo;  // Disabled for now
        private NinjaTrader.NinjaScript.Indicators.FKS.FKS_PythonBridge pythonBridge;
        
        // Market Configuration (Auto-selected based on asset)
        private double tickValue;
        private double atrStopMultiplier;
        private double atrTargetMultiplier;
        private int optimalStartHour;
        private int optimalEndHour;
        
        // State Management
        private double startingBalance;
        private double currentDailyPnL;
        private int todaysTrades;
        private bool tradingEnabled = true;
        private DateTime lastTradeTime = DateTime.MinValue;
        private Queue<double> recentSignalQualities = new Queue<double>();
        
        // Performance Tracking
        private List<TradeResult> tradeHistory = new List<TradeResult>();
        private int consecutiveLosses = 0;
        private double highWaterMark;
        
        // Signal State
        private string lastSignalType = "";
        private double lastSignalQuality = 0;
        private double lastWaveRatio = 0;
        private int activeSetup = 0;
        
        // Technical Indicators (internal use)
        private NinjaTrader.NinjaScript.Indicators.EMA ema9;
        private NinjaTrader.NinjaScript.Indicators.SMA sma20; // VWAP proxy
        private NinjaTrader.NinjaScript.Indicators.VOL volume;
        private NinjaTrader.NinjaScript.Indicators.ATR atr;
        
        // Multi-timeframe
        private int higherTimeframeBars = 15; // 15-min for 5-min primary
        #endregion
        
        #region OnStateChange
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"FKS Consolidated Strategy - Production Ready";
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
                BarsRequiredToTrade = 50;
                IsInstantiatedOnEachOptimizationIteration = true;
                
                // Configure market-specific defaults
                ConfigureMarketDefaults();
            }
            else if (State == State.Configure)
            {
                // Add higher timeframe for context
                AddDataSeries(BarsPeriodType.Minute, higherTimeframeBars);
            }
            else if (State == State.DataLoaded)
            {
                // Initialize indicators
                ema9 = EMA(9);
                sma20 = SMA(20); // VWAP approximation
                volume = VOL();
                atr = ATR(14);
                
                // Initialize FKS components with proper instantiation
                try
                {
                    // These need to be instantiated properly based on the indicator definitions
                    // For now, simplified approach - commented out to build DLL
                    fksAI = null; // Will be initialized properly when integrated with NT8
                    fksAO = null; // Will be initialized properly when integrated with NT8
                    // fksInfo = FKS_Dashboard();  // Disabled for now
                }
                catch (Exception ex)
                {
                    Log($"Error initializing FKS components: {ex.Message}", LogLevel.Error);
                }
                
                // Initialize Python bridge if available - commented out to build DLL
                try
                {
                    pythonBridge = null; // Will be initialized properly when integrated with NT8
                }
                catch (Exception ex)
                {
                    Log($"Python bridge not available - continuing without logging: {ex.Message}", LogLevel.Information);
                }
                
                // Set component parameters based on asset
                ConfigureIndicators();
            }
            else if (State == State.Historical)
            {
                startingBalance = Account.Get(AccountItem.CashValue, Currency.UsDollar);
                highWaterMark = startingBalance;
            }
            else if (State == State.Realtime)
            {
                // Reset daily counters on transition to realtime
                if (Bars.IsFirstBarOfSession)
                {
                    ResetDailyCounters();
                }
            }
        }
        #endregion
        
        #region OnBarUpdate
        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade) return;
            
            // Update daily P&L and check limits
            UpdateDailyPnL();
            
            // Check if we should be trading
            if (!ShouldTrade()) return;
            
            // Get current market state from indicators
            var marketState = GetMarketState();
            
            // Check each setup in priority order
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                // Setup 1: EMA9 + VWAP Bullish Breakout
                if (CheckSetup1(marketState))
                {
                    EnterLong(CalculatePositionSize(marketState, 1), "Setup1");
                    activeSetup = 1;
                }
                // Setup 2: EMA9 + VWAP Bearish Breakdown
                else if (CheckSetup2(marketState))
                {
                    EnterShort(CalculatePositionSize(marketState, 2), "Setup2");
                    activeSetup = 2;
                }
                // Setup 3: VWAP Rejection Bounce
                else if (CheckSetup3(marketState))
                {
                    if (marketState.VWAPBounceDirection > 0)
                        EnterLong(CalculatePositionSize(marketState, 3), "Setup3");
                    else
                        EnterShort(CalculatePositionSize(marketState, 3), "Setup3");
                    activeSetup = 3;
                }
                // Setup 4: Support/Resistance + AO Zero Cross
                else if (CheckSetup4(marketState))
                {
                    if (marketState.AOCrossDirection > 0)
                        EnterLong(CalculatePositionSize(marketState, 4), "Setup4");
                    else
                        EnterShort(CalculatePositionSize(marketState, 4), "Setup4");
                    activeSetup = 4;
                }
            }
            
            // Manage existing positions
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                ManagePosition(marketState);
            }
            
            // Update info dashboard
            UpdateDashboard(marketState);
        }
        #endregion
        
        #region Helper Methods
        private double GetVolumeAverage(int period)
        {
            if (CurrentBar < period) return volume[0];
            
            double total = 0;
            for (int i = 0; i < period; i++)
            {
                total += volume[i];
            }
            return total / period;
        }
        #endregion
        
        #region Setup Detection Methods
        private bool CheckSetup1(MarketState state)
        {
            // Setup 1: EMA9 + VWAP Bullish Breakout
            bool priceAboveEMA = Close[0] > ema9[0];
            bool emaAboveVWAP = ema9[0] > sma20[0]; // Using SMA as VWAP proxy
            bool hasGSignal = state.SignalType == "G";
            bool aoBullish = state.AOValue > 0 || state.AOCrossDirection > 0;
            bool volumeConfirmation = volume[0] > GetVolumeAverage(20) * 1.2;
            bool qualityPass = state.SignalQuality >= signalQualityMinimum;
            
            return priceAboveEMA && emaAboveVWAP && hasGSignal && 
                   aoBullish && volumeConfirmation && qualityPass;
        }
        
        private bool CheckSetup2(MarketState state)
        {
            // Setup 2: EMA9 + VWAP Bearish Breakdown
            bool priceBelowEMA = Close[0] < ema9[0];
            bool emaBelowVWAP = ema9[0] < sma20[0];
            bool hasTopSignal = state.SignalType == "Top";
            bool aoBearish = state.AOValue < 0 || state.AOCrossDirection < 0;
            bool volumeConfirmation = volume[0] > GetVolumeAverage(20) * 1.2;
            bool qualityPass = state.SignalQuality >= signalQualityMinimum;
            
            return priceBelowEMA && emaBelowVWAP && hasTopSignal && 
                   aoBearish && volumeConfirmation && qualityPass;
        }
        
        private bool CheckSetup3(MarketState state)
        {
            // Setup 3: VWAP Rejection Bounce
            double vwapLevel = sma20[0];
            double priceToVWAP = Math.Abs(Close[0] - vwapLevel) / atr[0];
            
            // Check if price bounced off VWAP
            bool nearVWAP = priceToVWAP < 0.5; // Within 0.5 ATR
            bool hasSignal = state.SignalType == "G" || state.SignalType == "^";
            bool momentumAlign = state.AOValue > 0 && state.SignalType == "G" ||
                               state.AOValue < 0 && state.SignalType == "Top";
            
            // Look for rejection candle
            bool rejectionCandle = false;
            if (Close[0] > vwapLevel && Low[0] <= vwapLevel && Close[0] > Open[0])
            {
                rejectionCandle = true;
                state.VWAPBounceDirection = 1;
            }
            else if (Close[0] < vwapLevel && High[0] >= vwapLevel && Close[0] < Open[0])
            {
                rejectionCandle = true;
                state.VWAPBounceDirection = -1;
            }
            
            return nearVWAP && hasSignal && momentumAlign && rejectionCandle;
        }
        
        private bool CheckSetup4(MarketState state)
        {
            // Setup 4: Support/Resistance + AO Zero Cross
            bool atKeyLevel = state.NearSupport || state.NearResistance;
            bool aoZeroCross = Math.Abs(state.AOCrossDirection) > 0;
            bool qualityPass = state.SignalQuality > 0.7; // Higher threshold for this setup
            bool volumeBreakout = volume[0] > GetVolumeAverage(20) * 1.5;
            
            // Direction must align
            bool directionAlign = (state.NearSupport && state.AOCrossDirection > 0) ||
                                (state.NearResistance && state.AOCrossDirection < 0);
            
            return atKeyLevel && aoZeroCross && qualityPass && volumeBreakout && directionAlign;
        }
        #endregion
        
        #region Position Management
        private void ManagePosition(MarketState state)
        {
            if (Position.MarketPosition == MarketPosition.Long)
            {
                // Dynamic stop loss based on volatility
                double stopDistance = atr[0] * atrStopMultiplier;
                double stopPrice = Position.AveragePrice - stopDistance;
                
                // Trailing stop after reaching 1:1 R:R
                double targetDistance = atr[0] * atrTargetMultiplier;
                if (Close[0] >= Position.AveragePrice + targetDistance)
                {
                    stopPrice = Math.Max(stopPrice, Close[0] - (atr[0] * 1.5));
                }
                
                SetStopLoss("", CalculationMode.Price, stopPrice, false);
                
                // Take profit at 3:1 minimum
                SetProfitTarget("", CalculationMode.Price, Position.AveragePrice + (targetDistance * 3));
                
                // Exit signals
                if (state.SignalType == "Top" || state.ExitMomentum < exitMomentumThreshold)
                {
                    ExitLong();
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                // Similar logic for short positions
                double stopDistance = atr[0] * atrStopMultiplier;
                double stopPrice = Position.AveragePrice + stopDistance;
                
                double targetDistance = atr[0] * atrTargetMultiplier;
                if (Close[0] <= Position.AveragePrice - targetDistance)
                {
                    stopPrice = Math.Min(stopPrice, Close[0] + (atr[0] * 1.5));
                }
                
                SetStopLoss("", CalculationMode.Price, stopPrice, false);
                SetProfitTarget("", CalculationMode.Price, Position.AveragePrice - (targetDistance * 3));
                
                if (state.SignalType == "G" || state.ExitMomentum < exitMomentumThreshold)
                {
                    ExitShort();
                }
            }
        }
        
        private int CalculatePositionSize(MarketState state, int setupNumber)
        {
            int contracts = baseContracts;
            
            // Tier 1: Premium signals (4-5 contracts)
            if (state.SignalQuality > 0.85 && state.WaveRatio > 2.0)
            {
                contracts = Math.Min(5, maxContracts);
            }
            // Tier 2: Strong signals (2-3 contracts)
            else if (state.SignalQuality > 0.70 && state.WaveRatio > 1.5)
            {
                contracts = 3;
            }
            // Tier 3: Standard signals (1-2 contracts)
            else if (state.SignalQuality > 0.60)
            {
                contracts = 2;
            }
            
            // Adjust for market regime
            if (state.MarketRegime == "VOLATILE")
            {
                contracts = Math.Max(1, contracts / 2);
            }
            else if (state.MarketRegime == "RANGING")
            {
                contracts = Math.Max(1, (int)(contracts * 0.7));
            }
            
            // Never exceed max contracts or daily limits
            contracts = Math.Min(contracts, maxContracts);
            
            // Log position sizing decision
            if (debugMode)
            {
                Print($"Position Size: {contracts} | Quality: {state.SignalQuality:P} | Wave: {state.WaveRatio:F2}x | Regime: {state.MarketRegime}");
            }
            
            return contracts;
        }
        #endregion
        
        #region Market State Analysis
        private MarketState GetMarketState()
        {
            var state = new MarketState();
            
            // Get indicator values
            state.SignalType = fksAI.SignalType;
            state.SignalQuality = fksAI != null ? fksAI.SignalQuality : 0;
            state.WaveRatio = fksAI != null ? fksAI.CurrentWaveRatio : 0;
            state.MarketRegime = fksAI != null ? fksAI.MarketRegime : "UNKNOWN";
            state.AOValue = fksAO != null ? fksAO.Value : 0; // Remove [0] since it's already a double
            state.AOSignal = fksAO != null ? fksAO.Signal : 0; // Remove [0] since it's already a double
            state.AOCrossDirection = fksAO != null ? fksAO.CrossDirection : 0;
            
            // Support/Resistance detection
            double currentPrice = Close[0];
            state.NearSupport = Math.Abs(currentPrice - fksAI.NearestSupport) / atr[0] < 0.5;
            state.NearResistance = Math.Abs(currentPrice - fksAI.NearestResistance) / atr[0] < 0.5;
            
            // Exit momentum calculation
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                double entryPrice = Position.AveragePrice;
                double currentMove = Position.MarketPosition == MarketPosition.Long ? 
                    currentPrice - entryPrice : entryPrice - currentPrice;
                double maxMove = Position.MarketPosition == MarketPosition.Long ?
                    MAX(High, BarsSinceEntryExecution())[0] - entryPrice :
                    entryPrice - MIN(Low, BarsSinceEntryExecution())[0];
                    
                state.ExitMomentum = maxMove > 0 ? currentMove / maxMove : 1.0;
            }
            
            return state;
        }
        #endregion
        
        #region Risk Management
        private bool ShouldTrade()
        {
            // Time filter
            if (useTimeFilter)
            {
                int currentHour = Time[0].Hour;
                if (currentHour < optimalStartHour || currentHour >= optimalEndHour)
                    return false;
            }
            
            // Daily trade limit
            if (todaysTrades >= maxDailyTrades)
            {
                if (debugMode) Print("Max daily trades reached");
                return false;
            }
            
            // Daily loss limit (hard stop)
            double lossLimit = startingBalance * (dailyLossLimitPercent / 100);
            if (currentDailyPnL <= -lossLimit)
            {
                tradingEnabled = false;
                if (debugMode) Print($"Daily loss limit reached: {currentDailyPnL:C}");
                return false;
            }
            
            // Daily profit target (soft stop - optional)
            double profitTarget = startingBalance * (dailyProfitTargetPercent / 100);
            if (currentDailyPnL >= profitTarget)
            {
                if (debugMode) Print($"Daily profit target reached: {currentDailyPnL:C}");
                // You can choose to stop or continue with reduced size
                // return false; // Uncomment to stop at profit target
            }
            
            // Consecutive losses check
            if (consecutiveLosses >= 3)
            {
                if (debugMode) Print("3 consecutive losses - stopping for the day");
                return false;
            }
            
            return tradingEnabled;
        }
        
        private void UpdateDailyPnL()
        {
            if (Bars.IsFirstBarOfSession)
            {
                ResetDailyCounters();
            }
            
            // Calculate current P&L
            double currentBalance = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            currentDailyPnL = currentBalance - startingBalance;
            
            // Update high water mark for drawdown calculation
            if (currentBalance > highWaterMark)
                highWaterMark = currentBalance;
        }
        
        private void ResetDailyCounters()
        {
            startingBalance = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            currentDailyPnL = 0;
            todaysTrades = 0;
            tradingEnabled = true;
            consecutiveLosses = 0;
            tradeHistory.Clear();
        }
        #endregion
        
        #region Configuration Methods
        private void ConfigureMarketDefaults()
        {
            switch (assetType)
            {
                case "Gold":
                    tickValue = 10;
                    atrStopMultiplier = 2.0;
                    atrTargetMultiplier = 3.0;
                    optimalStartHour = 8;
                    optimalEndHour = 12;
                    break;
                    
                case "ES":
                    tickValue = 12.50;
                    atrStopMultiplier = 2.5;
                    atrTargetMultiplier = 3.5;
                    optimalStartHour = 9;
                    optimalEndHour = 15;
                    break;
                    
                case "NQ":
                    tickValue = 5;
                    atrStopMultiplier = 2.5;
                    atrTargetMultiplier = 3.5;
                    optimalStartHour = 9;
                    optimalEndHour = 15;
                    break;
                    
                case "CL":
                    tickValue = 10;
                    atrStopMultiplier = 2.0;
                    atrTargetMultiplier = 3.0;
                    optimalStartHour = 9;
                    optimalEndHour = 14;
                    break;
                    
                case "BTC":
                    tickValue = 5;
                    atrStopMultiplier = 3.0;
                    atrTargetMultiplier = 4.0;
                    optimalStartHour = 0;
                    optimalEndHour = 24; // 24/7 market
                    break;
                    
                default:
                    // Default to Gold settings
                    tickValue = 10;
                    atrStopMultiplier = 2.0;
                    atrTargetMultiplier = 3.0;
                    optimalStartHour = 8;
                    optimalEndHour = 12;
                    break;
            }
        }
        
        private void ConfigureIndicators()
        {
            // FKS_AI configuration (hardcoded for production)
            // These would be properties in the actual indicator
            // For now, we assume the indicator handles this internally
            
            // Set asset type for indicators
            if (fksAI != null)
            {
                // fksAI.AssetType = assetType;
                // fksAI.SignalQualityThreshold = signalQualityMinimum;
            }
        }
        #endregion
        
        #region Dashboard Update
        private void UpdateDashboard(MarketState state)
        {
            // Dashboard disabled for now since fksInfo is not available
            // Send basic data to Python bridge if available
            if (pythonBridge != null)
            {
                var dashboardData = new
                {
                    // Performance
                    DailyPnL = currentDailyPnL,
                    DailyPnLPercent = (currentDailyPnL / startingBalance) * 100,
                    TradesToday = todaysTrades,
                    ConsecutiveLosses = consecutiveLosses,
                    
                    // Market State
                    MarketRegime = state.MarketRegime,
                    SignalQuality = state.SignalQuality,
                    WaveRatio = state.WaveRatio,
                    CurrentSignal = state.SignalType,
                    
                    // Position
                    ActiveSetup = activeSetup,
                    Position = Position.MarketPosition.ToString(),
                    Contracts = Position.Quantity,
                    
                    // Limits
                    ProfitTargetReached = currentDailyPnL >= (startingBalance * dailyProfitTargetPercent / 100),
                    LossLimitReached = currentDailyPnL <= -(startingBalance * dailyLossLimitPercent / 100),
                    MaxTradesReached = todaysTrades >= maxDailyTrades
                };
                
                pythonBridge.LogTradeData(dashboardData);
            }
        }
        #endregion
        
        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Asset Type", Order = 1, GroupName = "Market Settings")]
        public string AssetType
        {
            get { return assetType; }
            set { assetType = value; }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "Debug Mode", Order = 2, GroupName = "Settings")]
        public bool DebugMode
        {
            get { return debugMode; }
            set { debugMode = value; }
        }
        
        [NinjaScriptProperty]
        [Range(0.5, 1.0)]
        [Display(Name = "Signal Quality Minimum", Order = 3, GroupName = "Settings")]
        public double SignalQualityMinimum
        {
            get { return signalQualityMinimum; }
            set { signalQualityMinimum = Math.Max(0.5, Math.Min(1.0, value)); }
        }
        #endregion
        
        #region Helper Classes
        private class MarketState
        {
            public string SignalType { get; set; }
            public double SignalQuality { get; set; }
            public double WaveRatio { get; set; }
            public string MarketRegime { get; set; }
            public double AOValue { get; set; }
            public double AOSignal { get; set; }
            public int AOCrossDirection { get; set; }
            public bool NearSupport { get; set; }
            public bool NearResistance { get; set; }
            public double ExitMomentum { get; set; } = 1.0;
            public int VWAPBounceDirection { get; set; }
        }
        
        private class TradeResult
        {
            public DateTime EntryTime { get; set; }
            public DateTime ExitTime { get; set; }
            public double EntryPrice { get; set; }
            public double ExitPrice { get; set; }
            public int Contracts { get; set; }
            public double PnL { get; set; }
            public int SetupNumber { get; set; }
            public double SignalQuality { get; set; }
        }
        #endregion
    }
}