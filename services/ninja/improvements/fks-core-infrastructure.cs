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
#endregion

namespace NinjaTrader.NinjaScript.AddOns.FKS
{
    /// <summary>
    /// FKS_Core serves as the central hub for all FKS components
    /// Provides shared state, configuration, and inter-component communication
    /// </summary>
    public static class FKS_Core
    {
        #region Singleton Instance Management
        private static readonly object lockObject = new object();
        private static bool isInitialized = false;
        private static DateTime initializationTime;
        #endregion
        
        #region Component Registry
        private static Dictionary<string, IFKSComponent> registeredComponents = new Dictionary<string, IFKSComponent>();
        private static Dictionary<string, ComponentHealth> componentHealth = new Dictionary<string, ComponentHealth>();
        #endregion
        
        #region Market Configuration
        public static MarketConfiguration CurrentMarketConfig { get; private set; }
        private static Dictionary<string, MarketConfiguration> marketConfigs = new Dictionary<string, MarketConfiguration>();
        #endregion
        
        #region Shared State
        public static MarketState CurrentMarketState { get; private set; } = new MarketState();
        public static TradingState CurrentTradingState { get; private set; } = new TradingState();
        public static SystemPerformance Performance { get; private set; } = new SystemPerformance();
        #endregion
        
        #region Event System
        public static event EventHandler<SignalEventArgs> SignalGenerated;
        public static event EventHandler<TradeEventArgs> TradeExecuted;
        public static event EventHandler<ComponentEventArgs> ComponentStatusChanged;
        public static event EventHandler<MarketEventArgs> MarketRegimeChanged;
        #endregion
        
        #region Initialization
        public static void Initialize()
        {
            lock (lockObject)
            {
                if (isInitialized) return;
                
                // Initialize market configurations
                InitializeMarketConfigs();
                
                // Set default market
                SetMarket("Gold");
                
                // Initialize performance tracking
                Performance = new SystemPerformance();
                
                // Mark as initialized
                isInitialized = true;
                initializationTime = DateTime.Now;
                
                LogMessage("FKS Core initialized successfully", LogLevel.Information);
            }
        }
        
        private static void InitializeMarketConfigs()
        {
            // Gold Configuration
            marketConfigs["Gold"] = new MarketConfiguration
            {
                Symbol = "GC",
                TickSize = 0.10,
                TickValue = 10,
                DefaultContracts = 1,
                MaxContracts = 5,
                ATRStopMultiplier = 2.0,
                ATRTargetMultiplier = 3.0,
                SignalQualityThreshold = 0.65,
                OptimalSessionStart = 8,
                OptimalSessionEnd = 12,
                MinWaveRatio = 1.5,
                VolumeThreshold = 1.2
            };
            
            // ES Configuration
            marketConfigs["ES"] = new MarketConfiguration
            {
                Symbol = "ES",
                TickSize = 0.25,
                TickValue = 12.50,
                DefaultContracts = 1,
                MaxContracts = 3,
                ATRStopMultiplier = 2.5,
                ATRTargetMultiplier = 3.5,
                SignalQualityThreshold = 0.65,
                OptimalSessionStart = 9,
                OptimalSessionEnd = 15,
                MinWaveRatio = 1.5,
                VolumeThreshold = 1.2
            };
            
            // NQ Configuration
            marketConfigs["NQ"] = new MarketConfiguration
            {
                Symbol = "NQ",
                TickSize = 0.25,
                TickValue = 5,
                DefaultContracts = 1,
                MaxContracts = 2,
                ATRStopMultiplier = 2.5,
                ATRTargetMultiplier = 3.5,
                SignalQualityThreshold = 0.70,
                OptimalSessionStart = 9,
                OptimalSessionEnd = 15,
                MinWaveRatio = 1.5,
                VolumeThreshold = 1.3
            };
            
            // CL Configuration
            marketConfigs["CL"] = new MarketConfiguration
            {
                Symbol = "CL",
                TickSize = 0.01,
                TickValue = 10,
                DefaultContracts = 1,
                MaxContracts = 3,
                ATRStopMultiplier = 2.0,
                ATRTargetMultiplier = 3.0,
                SignalQualityThreshold = 0.60,
                OptimalSessionStart = 9,
                OptimalSessionEnd = 14,
                MinWaveRatio = 1.5,
                VolumeThreshold = 1.2
            };
            
            // BTC Configuration
            marketConfigs["BTC"] = new MarketConfiguration
            {
                Symbol = "BTC",
                TickSize = 1,
                TickValue = 5,
                DefaultContracts = 1,
                MaxContracts = 2,
                ATRStopMultiplier = 3.0,
                ATRTargetMultiplier = 4.0,
                SignalQualityThreshold = 0.70,
                OptimalSessionStart = 0,
                OptimalSessionEnd = 24, // 24/7 market
                MinWaveRatio = 2.0,
                VolumeThreshold = 1.5
            };
        }
        #endregion
        
        #region Component Registration
        public static void RegisterComponent(string componentId, IFKSComponent component)
        {
            lock (lockObject)
            {
                if (!isInitialized) Initialize();
                
                registeredComponents[componentId] = component;
                componentHealth[componentId] = new ComponentHealth
                {
                    ComponentId = componentId,
                    IsHealthy = true,
                    LastUpdate = DateTime.Now,
                    Version = component.Version
                };
                
                LogMessage($"Component registered: {componentId} v{component.Version}", LogLevel.Information);
                
                // Raise event
                ComponentStatusChanged?.Invoke(null, new ComponentEventArgs 
                { 
                    ComponentId = componentId, 
                    Status = ComponentStatus.Connected 
                });
            }
        }
        
        public static void UnregisterComponent(string componentId)
        {
            lock (lockObject)
            {
                if (registeredComponents.ContainsKey(componentId))
                {
                    registeredComponents.Remove(componentId);
                    componentHealth.Remove(componentId);
                    
                    LogMessage($"Component unregistered: {componentId}", LogLevel.Information);
                    
                    ComponentStatusChanged?.Invoke(null, new ComponentEventArgs 
                    { 
                        ComponentId = componentId, 
                        Status = ComponentStatus.Disconnected 
                    });
                }
            }
        }
        
        public static T GetComponent<T>(string componentId) where T : class, IFKSComponent
        {
            lock (lockObject)
            {
                if (registeredComponents.TryGetValue(componentId, out var component))
                {
                    return component as T;
                }
                return null;
            }
        }
        #endregion
        
        #region Market State Management
        public static void UpdateMarketState(MarketState newState)
        {
            lock (lockObject)
            {
                var previousRegime = CurrentMarketState?.MarketRegime;
                CurrentMarketState = newState;
                
                // Check for regime change
                if (previousRegime != null && previousRegime != newState.MarketRegime)
                {
                    MarketRegimeChanged?.Invoke(null, new MarketEventArgs 
                    { 
                        PreviousRegime = previousRegime, 
                        NewRegime = newState.MarketRegime 
                    });
                    
                    LogMessage($"Market regime changed: {previousRegime} -> {newState.MarketRegime}", LogLevel.Information);
                }
                
                // Update component health
                if (componentHealth.ContainsKey("MarketAnalysis"))
                {
                    componentHealth["MarketAnalysis"].LastUpdate = DateTime.Now;
                }
            }
        }
        
        public static void SetMarket(string marketType)
        {
            lock (lockObject)
            {
                if (marketConfigs.TryGetValue(marketType, out var config))
                {
                    CurrentMarketConfig = config;
                    LogMessage($"Market configuration set to: {marketType}", LogLevel.Information);
                }
                else
                {
                    LogMessage($"Unknown market type: {marketType}, using Gold defaults", LogLevel.Warning);
                    CurrentMarketConfig = marketConfigs["Gold"];
                }
            }
        }
        #endregion
        
        #region Signal Management
        public static void PublishSignal(FKSSignal signal)
        {
            lock (lockObject)
            {
                // Validate signal quality
                if (signal.Quality < CurrentMarketConfig.SignalQualityThreshold)
                {
                    LogMessage($"Signal rejected - quality {signal.Quality:P} below threshold {CurrentMarketConfig.SignalQualityThreshold:P}", LogLevel.Warning);
                    return;
                }
                
                // Update trading state
                CurrentTradingState.LastSignal = signal;
                CurrentTradingState.LastSignalTime = DateTime.Now;
                
                // Raise event
                SignalGenerated?.Invoke(null, new SignalEventArgs { Signal = signal });
                
                LogMessage($"Signal published: {signal.Type} | Quality: {signal.Quality:P} | Setup: {signal.SetupNumber}", LogLevel.Information);
            }
        }
        #endregion
        
        #region Performance Tracking
        public static void RecordTrade(TradeResult trade)
        {
            lock (lockObject)
            {
                Performance.RecordTrade(trade);
                CurrentTradingState.TradesToday++;
                CurrentTradingState.DailyPnL += trade.PnL;
                
                // Update consecutive losses
                if (trade.PnL < 0)
                {
                    CurrentTradingState.ConsecutiveLosses++;
                }
                else
                {
                    CurrentTradingState.ConsecutiveLosses = 0;
                }
                
                // Raise event
                TradeExecuted?.Invoke(null, new TradeEventArgs { Trade = trade });
                
                LogMessage($"Trade recorded: {trade.Setup} | P&L: {trade.PnL:C} | Quality: {trade.SignalQuality:P}", LogLevel.Information);
            }
        }
        
        public static void ResetDailyCounters()
        {
            lock (lockObject)
            {
                CurrentTradingState.ResetDaily();
                Performance.StartNewDay();
                LogMessage("Daily counters reset", LogLevel.Information);
            }
        }
        #endregion
        
        #region Health Monitoring
        public static Dictionary<string, ComponentHealth> GetComponentHealth()
        {
            lock (lockObject)
            {
                // Check for stale components
                var now = DateTime.Now;
                foreach (var health in componentHealth.Values)
                {
                    if ((now - health.LastUpdate).TotalMinutes > 5)
                    {
                        health.IsHealthy = false;
                        health.ErrorMessage = "No update in 5 minutes";
                    }
                }
                
                return new Dictionary<string, ComponentHealth>(componentHealth);
            }
        }
        
        public static bool IsSystemHealthy()
        {
            lock (lockObject)
            {
                // Check all critical components
                var criticalComponents = new[] { "FKS_AI", "FKS_AO", "FKS_Strategy" };
                
                foreach (var componentId in criticalComponents)
                {
                    if (!componentHealth.ContainsKey(componentId) || !componentHealth[componentId].IsHealthy)
                    {
                        return false;
                    }
                }
                
                return true;
            }
        }
        #endregion
        
        #region Logging
        private static void LogMessage(string message, LogLevel level)
        {
            // In production, this would integrate with NinjaTrader's logging
            // and potentially send to Python bridge
            var logEntry = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] FKS_Core: {message}";
            
            // Console output for debugging
            if (level >= LogLevel.Warning)
            {
                NinjaTrader.Code.Output.Process(logEntry, PrintTo.OutputTab1);
            }
        }
        #endregion
        
        #region Helper Classes
        public interface IFKSComponent
        {
            string ComponentId { get; }
            string Version { get; }
            void Initialize();
            void Shutdown();
        }
        
        public class MarketConfiguration
        {
            public string Symbol { get; set; }
            public double TickSize { get; set; }
            public double TickValue { get; set; }
            public int DefaultContracts { get; set; }
            public int MaxContracts { get; set; }
            public double ATRStopMultiplier { get; set; }
            public double ATRTargetMultiplier { get; set; }
            public double SignalQualityThreshold { get; set; }
            public int OptimalSessionStart { get; set; }
            public int OptimalSessionEnd { get; set; }
            public double MinWaveRatio { get; set; }
            public double VolumeThreshold { get; set; }
        }
        
        public class MarketState
        {
            public string MarketRegime { get; set; } = "NEUTRAL";
            public string TrendDirection { get; set; } = "NEUTRAL";
            public double Volatility { get; set; }
            public double VolumeRatio { get; set; }
            public string SignalType { get; set; }
            public double SignalQuality { get; set; }
            public double WaveRatio { get; set; }
            public DateTime LastUpdate { get; set; } = DateTime.Now;
        }
        
        public class TradingState
        {
            public int TradesToday { get; set; }
            public double DailyPnL { get; set; }
            public int ConsecutiveLosses { get; set; }
            public FKSSignal LastSignal { get; set; }
            public DateTime LastSignalTime { get; set; }
            public bool TradingEnabled { get; set; } = true;
            
            public void ResetDaily()
            {
                TradesToday = 0;
                DailyPnL = 0;
                ConsecutiveLosses = 0;
                TradingEnabled = true;
            }
        }
        
        public class FKSSignal
        {
            public string Type { get; set; } // G, Top, ^, v
            public double Quality { get; set; }
            public double WaveRatio { get; set; }
            public int SetupNumber { get; set; }
            public int RecommendedContracts { get; set; }
            public DateTime Timestamp { get; set; } = DateTime.Now;
        }
        
        public class TradeResult
        {
            public DateTime EntryTime { get; set; }
            public DateTime ExitTime { get; set; }
            public double EntryPrice { get; set; }
            public double ExitPrice { get; set; }
            public int Contracts { get; set; }
            public double PnL { get; set; }
            public string Setup { get; set; }
            public double SignalQuality { get; set; }
        }
        
        public class ComponentHealth
        {
            public string ComponentId { get; set; }
            public bool IsHealthy { get; set; }
            public DateTime LastUpdate { get; set; }
            public string Version { get; set; }
            public string ErrorMessage { get; set; }
        }
        
        public class SystemPerformance
        {
            private List<TradeResult> allTrades = new List<TradeResult>();
            private List<TradeResult> todaysTrades = new List<TradeResult>();
            
            public double TotalPnL => allTrades.Sum(t => t.PnL);
            public double WinRate => allTrades.Count > 0 ? (double)allTrades.Count(t => t.PnL > 0) / allTrades.Count : 0;
            public double SharpeRatio { get; private set; } = 0;
            public double MaxDrawdown { get; private set; } = 0;
            
            public void RecordTrade(TradeResult trade)
            {
                allTrades.Add(trade);
                todaysTrades.Add(trade);
                CalculateMetrics();
            }
            
            public void StartNewDay()
            {
                todaysTrades.Clear();
            }
            
            private void CalculateMetrics()
            {
                // Simplified Sharpe calculation
                if (allTrades.Count > 20)
                {
                    var returns = allTrades.Select(t => t.PnL).ToList();
                    var avgReturn = returns.Average();
                    var stdDev = Math.Sqrt(returns.Select(r => Math.Pow(r - avgReturn, 2)).Average());
                    SharpeRatio = stdDev > 0 ? (avgReturn / stdDev) * Math.Sqrt(252) : 0;
                }
                
                // Calculate max drawdown
                double peak = 0;
                double currentValue = 0;
                double maxDD = 0;
                
                foreach (var trade in allTrades)
                {
                    currentValue += trade.PnL;
                    if (currentValue > peak)
                        peak = currentValue;
                    
                    var drawdown = peak > 0 ? (peak - currentValue) / peak : 0;
                    if (drawdown > maxDD)
                        maxDD = drawdown;
                }
                
                MaxDrawdown = maxDD;
            }
        }
        
        // Event Args Classes
        public class SignalEventArgs : EventArgs
        {
            public FKSSignal Signal { get; set; }
        }
        
        public class TradeEventArgs : EventArgs
        {
            public TradeResult Trade { get; set; }
        }
        
        public class ComponentEventArgs : EventArgs
        {
            public string ComponentId { get; set; }
            public ComponentStatus Status { get; set; }
        }
        
        public class MarketEventArgs : EventArgs
        {
            public string PreviousRegime { get; set; }
            public string NewRegime { get; set; }
        }
        
        public enum ComponentStatus
        {
            Connected,
            Disconnected,
            Error,
            Warning
        }
        #endregion
    }
}