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
    public class EMA9_VWAP_Crossover_Strategy_Fixed : Strategy
    {
        #region Variables
        private FKS_VWAP_Indicator vwapIndicator;
        private ATR atr;
        private VOL volume;
        private SMA volumeAvg;
        
        // Hardcoded strategy parameters
        private readonly int quantity = 1;
        private readonly double atrStopMultiplier = 2.0;
        private readonly double minVolumeThreshold = 1.0;
        private readonly bool debugMode = true;
        private readonly int stopHour = 15;
        
        // TEST OPTION: Disable volume filter for testing
        private readonly bool useVolumeFilter = false; // Set to false to test without volume filter
        
        // Hard/Soft Risk Management (hardcoded)
        private readonly double hardProfitLimit = 3000;
        private readonly double softProfitLimit = 2000;
        private readonly double hardLossLimit = 1500;
        private readonly double softLossLimit = 1000;
        
        // Position management
        private double entryPrice;
        private double currentStop;
        private bool isLong = false;
        private bool isShort = false;
        private bool softLimitTriggered = false;
        
        // Daily P&L tracking
        private double dailyPnL = 0;
        private DateTime currentDay = DateTime.MinValue;
        private int tradesCount = 0;
        
        // Enhanced debugging
        private int crossoverCheckCount = 0;
        private DateTime lastCrossoverCheck = DateTime.MinValue;
        
        // NEW: Re-entry prevention
        private int barsSinceExit = 0;
        private readonly int reEntryCooldown = 5; // Wait 5 bars before re-entering
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"EMA9/VWAP crossover strategy with hard/soft risk management and critical fixes";
                Name = "EMA9_VWAP_Crossover_Strategy_Fixed";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                BarsRequiredToTrade = 20; // Works for both minute and tick charts
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
            }
            else if (State == State.DataLoaded)
            {
                // Initialize indicators
                vwapIndicator = FKS_VWAP_Indicator();
                atr = ATR(14);
                volume = VOL();
                volumeAvg = SMA(volume, 20);
                
                // Reset all state variables
                entryPrice = 0;
                currentStop = 0;
                isLong = false;
                isShort = false;
                barsSinceExit = reEntryCooldown; // Start ready to trade
                currentDay = DateTime.MinValue;
                
                if (debugMode)
                {
                    ClearOutputWindow();
                    Print("=== EMA9/VWAP Crossover Strategy FIXED Version ===");
                    Print($"Debug Mode: ON");
                    Print($"Volume Filter: {(useVolumeFilter ? "ENABLED" : "DISABLED")}");
                    Print($"Bars Required to Trade: {BarsRequiredToTrade}");
                    Print($"ATR Stop Multiplier: {atrStopMultiplier}");
                    Print($"Min Volume Threshold: {minVolumeThreshold}");
                    Print($"Re-entry Cooldown: {reEntryCooldown} bars");
                    Print("========================================");
                }
            }
            else if (State == State.Terminated)
            {
                // Ensure clean termination
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    ExitPosition("Strategy Terminated");
                }
            }
        }

        protected override void OnBarUpdate()
        {
            // Warn about Heiken-Ashi
            if (CurrentBar == 0 && BarsArray[0].BarsType.Name.Contains("HeikenAshi"))
            {
                Print("WARNING: Strategy running on Heiken-Ashi bars. Stops may behave unexpectedly.");
                Print("Consider using standard candlestick or bar charts for more accurate stop execution.");
            }
            
            // Increment bars since exit
            if (Position.MarketPosition == MarketPosition.Flat && barsSinceExit < reEntryCooldown)
                barsSinceExit++;
            
            if (CurrentBar < BarsRequiredToTrade)
            {
                if (debugMode && CurrentBar == BarsRequiredToTrade - 1)
                    Print($"Will start trading on next bar. Current bar: {CurrentBar}");
                return;
            }
            
            // Enhanced state logging
            if (debugMode && CurrentBar % 50 == 0)
            {
                Print($"\nStrategy State Check - Bar: {CurrentBar}, Time: {Time[0]}");
                Print($"  Position: {Position.MarketPosition}");
                Print($"  Current Stop: {currentStop:F2}");
                Print($"  Bars Since Exit: {barsSinceExit}/{reEntryCooldown}");
                Print($"  Daily P&L: {dailyPnL:F2}, Trades Today: {tradesCount}");
                Print($"  EMA9: {vwapIndicator.GetEMA9Value():F2}, VWAP: {vwapIndicator.GetVWAPValue():F2}");
                Print($"  ATR: {atr[0]:F2}");
            }
            
            // Reset daily P&L tracking
            if (currentDay.Date != Time[0].Date)
            {
                dailyPnL = 0;
                tradesCount = 0;
                softLimitTriggered = false;
                currentDay = Time[0];
                crossoverCheckCount = 0;
                if (debugMode) Print($"\n=== New day: {currentDay.Date} ===");
            }
            
            // Check if we should stop trading (time or P&L limits)
            if (ShouldStopTrading()) return;
            
            // Force exit outside trading hours
            if (Position.MarketPosition != MarketPosition.Flat && IsOutsideTradingHours())
            {
                if (debugMode) Print($"Exiting position at {Time[0]} due to outside trading hours");
                ExitPosition("Outside Hours");
                return;
            }
            
            // Manage existing position
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                ManagePosition();
                return;
            }
            
            // Look for new entry signals
            CheckForEntrySignals();
        }

        private void CheckForEntrySignals()
        {
            // Don't enter if we just exited
            if (barsSinceExit < reEntryCooldown)
            {
                if (debugMode && (vwapIndicator.IsBullishCrossover() || vwapIndicator.IsBearishCrossover()))
                    Print($"Crossover detected but in cooldown period. Bars since exit: {barsSinceExit}");
                return;
            }
            
            // Get current values
            double ema9 = vwapIndicator.GetEMA9Value();
            double vwap = vwapIndicator.GetVWAPValue();
            double currentVolume = volume[0];
            double avgVolume = volumeAvg[0];
            
            // Enhanced debug output
            bool bullishCross = vwapIndicator.IsBullishCrossover();
            bool bearishCross = vwapIndicator.IsBearishCrossover();
            
            // Track when we check for crossovers
            if (Time[0] != lastCrossoverCheck)
            {
                lastCrossoverCheck = Time[0];
                crossoverCheckCount++;
            }
            
            // Log every 10 bars or when close to crossover
            double distance = Math.Abs(ema9 - vwap);
            bool closeToXover = distance < (TickSize * 10);
            
            if (debugMode && (CurrentBar % 10 == 0 || closeToXover || bullishCross || bearishCross))
            {
                Print($"\nCrossover Check #{crossoverCheckCount} at {Time[0]}:");
                Print($"  EMA9: {ema9:F4}, VWAP: {vwap:F4}, Distance: {distance:F4}");
                Print($"  Bullish Crossover: {bullishCross}, Bearish Crossover: {bearishCross}");
                Print($"  Close to Crossover: {closeToXover}");
                Print($"  Volume: {currentVolume:F0}, Avg: {avgVolume:F0}, Ratio: {currentVolume/avgVolume:F2}");
                
                if (closeToXover && !bullishCross && !bearishCross)
                {
                    Print($"  >> APPROACHING CROSSOVER! EMA9 {(ema9 > vwap ? "above" : "below")} VWAP by {distance:F4}");
                }
            }
            
            // Volume filter check (can be disabled for testing)
            bool volumeCheckPassed = true;
            if (useVolumeFilter)
            {
                double volumeThreshold = softLimitTriggered ? minVolumeThreshold * 1.5 : minVolumeThreshold;
                volumeCheckPassed = currentVolume >= avgVolume * volumeThreshold;
                
                if (debugMode && (bullishCross || bearishCross) && !volumeCheckPassed)
                {
                    Print($"  >> CROSSOVER BLOCKED by volume filter: {currentVolume:F0} < {avgVolume * volumeThreshold:F0}");
                }
            }
            
            // Check for bullish crossover (EMA9 crosses above VWAP)
            if (bullishCross && volumeCheckPassed)
            {
                // Calculate stop BEFORE entering
                double atrValue = atr[0];
                double ema9Value = vwapIndicator.GetEMA9Value();
                
                // Validate stop calculation
                if (atrValue <= 0 || double.IsNaN(atrValue))
                {
                    Print($"WARNING: Invalid ATR value: {atrValue}");
                    return;
                }
                
                double calculatedStop = ema9Value - (atrValue * atrStopMultiplier);
                
                // Ensure stop is reasonable
                if (calculatedStop <= 0 || calculatedStop >= Close[0])
                {
                    Print($"WARNING: Invalid stop calculation. Stop: {calculatedStop}, Close: {Close[0]}, EMA9: {ema9Value}, ATR: {atrValue}");
                    return;
                }
                
                Print($"\n*** BULLISH CROSSOVER SIGNAL ***");
                Print($"Time: {Time[0]}, EMA9: {ema9:F2}, VWAP: {vwap:F2}");
                Print($"Entry: {Close[0]:F2}, Calculated Stop: {calculatedStop:F2}, ATR: {atrValue:F2}");
                
                EnterLong(quantity, "EMA9_VWAP_Long");
                isLong = true;
                isShort = false;
                entryPrice = Close[0];
                currentStop = calculatedStop;
                tradesCount++;
            }
            // Check for bearish crossover (EMA9 crosses below VWAP)
            else if (bearishCross && volumeCheckPassed)
            {
                // Calculate stop BEFORE entering
                double atrValue = atr[0];
                double ema9Value = vwapIndicator.GetEMA9Value();
                
                // Validate stop calculation
                if (atrValue <= 0 || double.IsNaN(atrValue))
                {
                    Print($"WARNING: Invalid ATR value: {atrValue}");
                    return;
                }
                
                double calculatedStop = ema9Value + (atrValue * atrStopMultiplier);
                
                // Ensure stop is reasonable
                if (calculatedStop <= 0 || calculatedStop <= Close[0])
                {
                    Print($"WARNING: Invalid stop calculation. Stop: {calculatedStop}, Close: {Close[0]}, EMA9: {ema9Value}, ATR: {atrValue}");
                    return;
                }
                
                Print($"\n*** BEARISH CROSSOVER SIGNAL ***");
                Print($"Time: {Time[0]}, EMA9: {ema9:F2}, VWAP: {vwap:F2}");
                Print($"Entry: {Close[0]:F2}, Calculated Stop: {calculatedStop:F2}, ATR: {atrValue:F2}");
                
                EnterShort(quantity, "EMA9_VWAP_Short");
                isLong = false;
                isShort = true;
                entryPrice = Close[0];
                currentStop = calculatedStop;
                tradesCount++;
            }
        }

        private void ManagePosition()
        {
            double ema9Value = vwapIndicator.GetEMA9Value();
            double atrValue = atr[0];
            
            // CRITICAL FIX: Initialize stop if it's 0 (shouldn't happen but safety check)
            if (currentStop == 0)
            {
                if (Position.MarketPosition == MarketPosition.Long)
                {
                    currentStop = ema9Value - (atrValue * atrStopMultiplier);
                    Print($"WARNING: Stop was 0, initialized Long stop to {currentStop:F2}");
                }
                else if (Position.MarketPosition == MarketPosition.Short)
                {
                    currentStop = ema9Value + (atrValue * atrStopMultiplier);
                    Print($"WARNING: Stop was 0, initialized Short stop to {currentStop:F2}");
                }
            }
            
            if (Position.MarketPosition == MarketPosition.Long)
            {
                // Update trailing stop with EMA9
                double newStop = ema9Value - (atrValue * atrStopMultiplier);
                if (newStop > currentStop)
                {
                    currentStop = newStop;
                    if (debugMode && CurrentBar % 20 == 0)
                        Print($"Long stop updated to {currentStop:F2} (EMA9: {ema9Value:F2})");
                }
                
                // Check if we should exit - but only if stop is valid
                if (currentStop > 0 && Close[0] <= currentStop)
                {
                    Print($"\n*** STOP HIT *** Long position stopped at {Close[0]:F2}, stop was {currentStop:F2}");
                    ExitPosition("EMA9_Trail_Stop");
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                // Update trailing stop with EMA9
                double newStop = ema9Value + (atrValue * atrStopMultiplier);
                if (newStop < currentStop || currentStop == 0)
                {
                    currentStop = newStop;
                    if (debugMode && CurrentBar % 20 == 0)
                        Print($"Short stop updated to {currentStop:F2} (EMA9: {ema9Value:F2})");
                }
                
                // Check if we should exit - but only if stop is valid
                if (currentStop > 0 && Close[0] >= currentStop)
                {
                    Print($"\n*** STOP HIT *** Short position stopped at {Close[0]:F2}, stop was {currentStop:F2}");
                    ExitPosition("EMA9_Trail_Stop");
                }
            }
        }

        private void ExitPosition(string reason)
        {
            if (Position.MarketPosition == MarketPosition.Long)
                ExitLong(reason);
            else if (Position.MarketPosition == MarketPosition.Short)
                ExitShort(reason);
                
            isLong = false;
            isShort = false;
            currentStop = 0;
            barsSinceExit = 0; // Reset cooldown counter
        }

        private bool ShouldStopTrading()
        {
            // Hard limits - completely stop trading
            if (dailyPnL >= hardProfitLimit)
            {
                if (debugMode && CurrentBar % 100 == 0) 
                    Print($"HARD PROFIT LIMIT REACHED: {dailyPnL:F2} >= {hardProfitLimit}");
                return true;
            }
            
            if (dailyPnL <= -hardLossLimit)
            {
                if (debugMode && CurrentBar % 100 == 0) 
                    Print($"HARD LOSS LIMIT REACHED: {dailyPnL:F2} <= -{hardLossLimit}");
                return true;
            }
            
            // Soft limits - trigger cautious trading
            if (!softLimitTriggered)
            {
                if (dailyPnL >= softProfitLimit)
                {
                    softLimitTriggered = true;
                    Print($"\n*** SOFT PROFIT LIMIT TRIGGERED: {dailyPnL:F2} >= {softProfitLimit} ***");
                }
                else if (dailyPnL <= -softLossLimit)
                {
                    softLimitTriggered = true;
                    Print($"\n*** SOFT LOSS LIMIT TRIGGERED: {dailyPnL:F2} <= -{softLossLimit} ***");
                }
            }
            
            return false;
        }

        private bool IsOutsideTradingHours()
        {
            int hour = Time[0].Hour;
            return hour >= stopHour;
        }

        protected override void OnPositionUpdate(Position position, double averagePrice, int quantity, MarketPosition marketPosition)
        {
            if (marketPosition == MarketPosition.Flat && SystemPerformance.AllTrades.Count > 0)
            {
                Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                dailyPnL += lastTrade.ProfitCurrency;
                
                Print($"\n*** TRADE CLOSED ***");
                Print($"P&L: {lastTrade.ProfitCurrency:F2}");
                Print($"Daily P&L: {dailyPnL:F2}");
                Print($"Trades Today: {tradesCount}");
                Print($"Soft Limit Triggered: {softLimitTriggered}");
                Print("******************");
            }
        }

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            if (Position.MarketPosition != MarketPosition.Flat && currentStop > 0)
            {
                // Draw current stop level
                double stopY = chartScale.GetYByValue(currentStop);
                SharpDX.Direct2D1.Brush stopBrush = Position.MarketPosition == MarketPosition.Long ? 
                    Brushes.Red.ToDxBrush(RenderTarget) : Brushes.Green.ToDxBrush(RenderTarget);
                
                RenderTarget.DrawLine(
                    new SharpDX.Vector2(ChartPanel.X, (float)stopY),
                    new SharpDX.Vector2(ChartPanel.X + ChartPanel.W, (float)stopY),
                    stopBrush, 2);
                    
                // Draw stop label
                SharpDX.Direct2D1.Brush textBrush = Brushes.White.ToDxBrush(RenderTarget);
                RenderTarget.DrawText($"Stop: {currentStop:F2}", 
                    ChartControl.Properties.LabelFont.ToDirectWriteTextFormat(), 
                    new SharpDX.RectangleF(ChartPanel.X + 10, (float)stopY - 10, 100, 20),
                    textBrush);
            }
        }

        #region Properties
        // All parameters are hardcoded for simplicity
        // To test without volume filter, change useVolumeFilter to false at the top
        #endregion
    }
}
