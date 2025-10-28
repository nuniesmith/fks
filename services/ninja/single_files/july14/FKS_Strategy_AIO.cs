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
        
        // Hardcoded optimized parameters
        private double signalQualityThreshold = 0.72;
        private double volumeThreshold = 1.35;
        private int maxDailyTrades = 6;
        private int baseContracts = 1;
        private int maxContracts = 4;
        private double atrStopMultiplier = 2.0; // From crossover strategy
        private double atrTargetMultiplier = 2.2;
        private double dailyProfitTarget = 2500;
        private double dailyLossLimit = 1200;
        private bool debugMode = true;
        private int stopHour = 15;
        
        // Re-entry prevention (from crossover strategy)
        private int barsSinceExit = 0;
        private readonly int reEntryCooldown = 5;
        
        // Volume filter option (from crossover strategy)
        private readonly bool useVolumeFilter = true;
        
        // Hard/Soft Profit and Loss Limits
        private double hardProfitLimit = 3000;
        private double softProfitLimit = 2000;
        private double hardLossLimit = 1500;
        private double softLossLimit = 1000;
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
        
        // Risk Management
        private double currentDailyPnL;
        private int todaysTrades;
        private int consecutiveLosses;
        private int consecutiveShortLosses;
        private bool tradingEnabled = true;
        private bool shortTradingEnabled = true;
        private DateTime lastTradeTime = DateTime.MinValue;
        private DateTime currentDay = DateTime.MinValue;
        
        // Position Management (enhanced from crossover strategy)
        private double entryPrice;
        private double currentStop; // Using dynamic stop from crossover strategy
        private double stopPrice;
        private double target1Price;
        private double target2Price;
        private bool target1Hit = false;
        private bool target2Hit = false;
        private bool isLong = false;
        private bool isShort = false;
        
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

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"FKS Strategy Merged - Complete multi-setup strategy with enhanced stops";
                Name = "FKS_Strategy_AIO";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                BarsRequiredToTrade = 100;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                
                // Asset-specific optimizations (will be auto-detected)
                SetAssetSpecificDefaults();
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
                
                // Reset state variables
                currentDay = DateTime.MinValue;
                entryPrice = 0;
                currentStop = 0;
                isLong = false;
                isShort = false;
                barsSinceExit = reEntryCooldown;
                hasWarnedAboutHA = false;
                
                if (debugMode)
                {
                    ClearOutputWindow();
                    Print("=== FKS Strategy Merged initialized ===");
                    Print($"Debug Mode: ON");
                    Print($"Volume Filter: {(useVolumeFilter ? "ENABLED" : "DISABLED")}");
                    Print($"Bars Required to Trade: {BarsRequiredToTrade}");
                    Print($"ATR Stop Multiplier: {atrStopMultiplier}");
                    Print($"Re-entry Cooldown: {reEntryCooldown} bars");
                    Print($"Signal Quality Threshold: {signalQualityThreshold}");
                    Print("=====================================");
                }
            }
            else if (State == State.Terminated)
            {
                // Ensure clean termination
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    if (debugMode) Print("Strategy terminating - closing open positions");
                }
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade) return;
            
            // Only process on primary timeframe
            if (BarsInProgress != 0) return;
            
            // Warn about Heiken-Ashi once
            if (!hasWarnedAboutHA && BarsArray[0].BarsType.Name.Contains("HeikenAshi"))
            {
                Print("\n*** WARNING: Strategy running on Heiken-Ashi bars ***");
                Print("Heiken-Ashi bars can cause inaccurate stop calculations.");
                Print("Consider using standard candlestick charts for better results.\n");
                hasWarnedAboutHA = true;
            }
            
            // Increment bars since exit counter
            if (Position.MarketPosition == MarketPosition.Flat && barsSinceExit < reEntryCooldown)
            {
                barsSinceExit++;
                if (debugMode && barsSinceExit == reEntryCooldown)
                    Print("Re-entry cooldown complete - ready to trade again");
            }
            
            // Force exit outside trading hours
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                if (IsOutsideTradingHours())
                {
                    if (debugMode) Print($"Exiting position at {Time[0]} due to outside trading hours.");
                    ExitPosition("Outside Hours");
                    return;
                }
            }
            
            // Reset daily counters
            if (currentDay.Date != Time[0].Date)
            {
                ResetDailyCounters();
                currentDay = Time[0];
                crossoverCheckCount = 0;
            }
            
            // Update calculations
            UpdateCalculations();
            
            // Perform clustering analysis
            if (CurrentBar % recalculateInterval == 0)
            {
                PerformClusteringAnalysis();
            }
            
            // Classify regime and adjust parameters
            ClassifyCurrentRegime();
            
            // Check trading conditions
            if (!ShouldTrade()) return;
            
            // Manage existing position (using enhanced stop management from crossover strategy)
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                ManagePositionEnhanced();
                return;
            }
            
            // Look for new signals
            CheckForSignals();
        }

        #region Initialization Methods
        private void SetAssetSpecificDefaults()
        {
            // Auto-detect asset and set optimized parameters
            string instrumentName = "";
            if (Instrument?.MasterInstrument?.Name != null)
            {
                instrumentName = Instrument.MasterInstrument.Name.ToUpper();
            }
            
            // Asset-specific optimizations from commission settings
            switch (instrumentName)
            {
                case "GC": // Gold
                    signalQualityThreshold = 0.70;
                    maxContracts = 4;
                    break;
                case "NQ": // Nasdaq
                    signalQualityThreshold = 0.75;
                    maxContracts = 3;
                    break;
                case "ES": // S&P 500
                    signalQualityThreshold = 0.72;
                    maxContracts = 4;
                    break;
                case "CL": // Crude Oil
                    signalQualityThreshold = 0.78;
                    maxContracts = 2;
                    break;
                case "BTC": // Bitcoin
                    signalQualityThreshold = 0.80;
                    maxContracts = 2;
                    break;
                default:
                    signalQualityThreshold = 0.72;
                    maxContracts = 4;
                    break;
            }
        }
        
        private void InitializeIndicators()
        {
            // Primary timeframe indicators (1-minute)
            vwapIndicator = FKS_VWAP_Indicator();
            ema9 = EMA(9);
            atr = ATR(14);
            volume = VOL();
            volumeAvg = SMA(volume, 20);
            aoFast = SMA(Typical, 5);
            aoSlow = SMA(Typical, 34);
            
            // Higher timeframe indicators (5-minute)
            ema9_HT = EMA(BarsArray[1], 9);
            vwap_HT = FKS_VWAP_Indicator(BarsArray[1]);
            atr_HT = ATR(BarsArray[1], 14);
            volume_HT = VOL(BarsArray[1]);
            volumeAvg_HT = SMA(volume_HT, 20);
            aoFast_HT = SMA(BarsArray[1], 5);
            aoSlow_HT = SMA(BarsArray[1], 34);
        }
        
        private void InitializeClustering()
        {
            // Initialize custom series for clustering
            returns = new Series<double>(this);
            volatility = new Series<double>(this);
            momentum = new Series<double>(this);
            
            historicalData = new List<ClusterData>();
            currentRegime = MarketRegime.Sideways;
            previousRegime = MarketRegime.Sideways;
        }
        #endregion
        
        #region Calculation Methods
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
            
            // Update Level 2 data analysis
            UpdateLevelTwoData();
            
            // Update support/resistance
            UpdateSupportResistance();
            
            // Update market data for clustering
            UpdateMarketData();
            
            // Generate signals with higher timeframe confirmation
            GenerateEnhancedSignal();
            
            // Enhanced state logging (from crossover strategy)
            if (debugMode && CurrentBar % 50 == 0)
            {
                Print($"\nStrategy State Check - Bar: {CurrentBar}, Time: {Time[0]}");
                Print($"  Position: {Position.MarketPosition}");
                Print($"  Current Stop: {currentStop:F2}");
                Print($"  Bars Since Exit: {barsSinceExit}/{reEntryCooldown}");
                Print($"  Daily P&L: {currentDailyPnL:F2}, Trades Today: {todaysTrades}");
                Print($"  EMA9: {vwapIndicator.GetEMA9Value():F2}, VWAP: {vwapIndicator.GetVWAPValue():F2}");
                Print($"  ATR: {atr[0]:F2}");
                Print($"  Regime: {currentRegime}");
                Print($"  Signal Quality: {signalQuality:F2}, Active Setup: {activeSetup}");
            }
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
        
        private void UpdateLevelTwoData()
        {
            if (vwapIndicator != null)
            {
                // Get Level 2 data from our custom VWAP indicator
                bidAskRatio = vwapIndicator.GetBidAskRatio();
                volumeImbalance = vwapIndicator.GetVolumeImbalance();
                isVolumeImbalanceBullish = vwapIndicator.IsVolumeImbalanceBullish();
                isVolumeImbalanceBearish = vwapIndicator.IsVolumeImbalanceBearish();
            }
        }
        
        private void UpdateMarketData()
        {
            if (CurrentBar < 2) return;
            
            // Calculate returns (1-bar percentage change)
            double currentReturns = (Close[0] - Close[1]) / Close[1];
            returns[0] = currentReturns;
            
            // Calculate volatility (10-bar rolling standard deviation of returns)
            if (CurrentBar >= 10)
            {
                double[] recentReturns = new double[10];
                for (int i = 0; i < 10; i++)
                {
                    if (CurrentBar - i >= 1)
                        recentReturns[i] = (Close[i] - Close[i + 1]) / Close[i + 1];
                }
                volatility[0] = CalculateStandardDeviation(recentReturns);
            }
            
            // Calculate momentum (current price vs 10-bar moving average)
            if (CurrentBar >= 10)
            {
                double avgPrice = 0;
                for (int i = 0; i < 10; i++)
                {
                    avgPrice += Close[i];
                }
                avgPrice /= 10;
                momentum[0] = (Close[0] - avgPrice) / avgPrice;
            }
            
            // Store data for clustering
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
                {
                    historicalData.RemoveAt(0);
                }
            }
        }
        #endregion
        
        #region Clustering Methods
        private void PerformClusteringAnalysis()
        {
            if (historicalData.Count < 50) return;
            
            // Simple K-Means clustering implementation
            var clusters = PerformKMeansClustering(historicalData, 6);
            
            // Assign regimes to clusters based on characteristics
            AssignRegimesToClusters(clusters);
        }
        
        private List<List<ClusterData>> PerformKMeansClustering(List<ClusterData> data, int k)
        {
            var clusters = new List<List<ClusterData>>();
            var centroids = new List<double[]>();
            
            // Initialize centroids randomly
            Random rand = new Random();
            for (int i = 0; i < k; i++)
            {
                centroids.Add(new double[] {
                    data[rand.Next(data.Count)].Returns,
                    data[rand.Next(data.Count)].Volatility,
                    data[rand.Next(data.Count)].Momentum,
                    data[rand.Next(data.Count)].Volume,
                    data[rand.Next(data.Count)].PricePosition
                });
                clusters.Add(new List<ClusterData>());
            }
            
            // Iterate until convergence (simplified - just 10 iterations)
            for (int iter = 0; iter < 10; iter++)
            {
                // Clear clusters
                foreach (var cluster in clusters)
                    cluster.Clear();
                
                // Assign points to nearest centroid
                foreach (var point in data)
                {
                    int nearestCluster = FindNearestCentroid(point, centroids);
                    clusters[nearestCluster].Add(point);
                }
                
                // Update centroids
                for (int i = 0; i < k; i++)
                {
                    if (clusters[i].Count > 0)
                    {
                        centroids[i] = CalculateCentroid(clusters[i]);
                    }
                }
            }
            
            return clusters;
        }
        
        private int FindNearestCentroid(ClusterData point, List<double[]> centroids)
        {
            double minDistance = double.MaxValue;
            int nearestIndex = 0;
            
            for (int i = 0; i < centroids.Count; i++)
            {
                double distance = CalculateDistance(point, centroids[i]);
                if (distance < minDistance)
                {
                    minDistance = distance;
                    nearestIndex = i;
                }
            }
            
            return nearestIndex;
        }
        
        private double CalculateDistance(ClusterData point, double[] centroid)
        {
            double distance = 0;
            distance += Math.Pow(point.Returns - centroid[0], 2);
            distance += Math.Pow(point.Volatility - centroid[1], 2);
            distance += Math.Pow(point.Momentum - centroid[2], 2);
            distance += Math.Pow(point.Volume - centroid[3], 2);
            distance += Math.Pow(point.PricePosition - centroid[4], 2);
            return Math.Sqrt(distance);
        }
        
        private double[] CalculateCentroid(List<ClusterData> cluster)
        {
            if (cluster.Count == 0) return new double[5];
            
            double[] centroid = new double[5];
            foreach (var point in cluster)
            {
                centroid[0] += point.Returns;
                centroid[1] += point.Volatility;
                centroid[2] += point.Momentum;
                centroid[3] += point.Volume;
                centroid[4] += point.PricePosition;
            }
            
            for (int i = 0; i < 5; i++)
            {
                centroid[i] /= cluster.Count;
            }
            
            return centroid;
        }
        
        private void AssignRegimesToClusters(List<List<ClusterData>> clusters)
        {
            for (int i = 0; i < clusters.Count; i++)
            {
                if (clusters[i].Count == 0) continue;
                
                var centroid = CalculateCentroid(clusters[i]);
                double avgReturns = centroid[0];
                double avgVolatility = centroid[1];
                double avgMomentum = centroid[2];
                double avgVolume = centroid[3];
                
                // Classify regime based on cluster characteristics
                MarketRegime regime = ClassifyRegimeFromCentroid(avgReturns, avgVolatility, avgMomentum, avgVolume);
                
                // Assign regime to all points in cluster
                foreach (var point in clusters[i])
                {
                    point.Regime = regime;
                }
            }
        }
        
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
            
            // Apply regime-specific adjustments
            ApplyRegimeAdjustments();
            
            // Log regime changes
            if (debugMode && currentRegime != previousRegime)
            {
                Print($"\n*** REGIME CHANGE: {previousRegime} -> {currentRegime} ***");
                Print($"Adjustments - Signal Quality Multiplier: {regimeSignalQualityMultiplier:F2}, " +
                      $"Position Size Multiplier: {regimePositionSizeMultiplier:F2}");
            }
        }
        
        private void ApplyRegimeAdjustments()
        {
            switch (currentRegime)
            {
                case MarketRegime.Bullish:
                    regimeSignalQualityMultiplier = 0.95;
                    regimePositionSizeMultiplier = 1.2;
                    regimeAllowShorts = false;
                    maxDailyTrades = 10;
                    break;
                    
                case MarketRegime.Bearish:
                    regimeSignalQualityMultiplier = 1.1;
                    regimePositionSizeMultiplier = 0.8;
                    regimeAllowShorts = true;
                    maxDailyTrades = 6;
                    break;
                    
                case MarketRegime.Sideways:
                    regimeSignalQualityMultiplier = 1.05;
                    regimePositionSizeMultiplier = 0.9;
                    regimeAllowShorts = true;
                    maxDailyTrades = 8;
                    break;
                    
                case MarketRegime.Volatile:
                    regimeSignalQualityMultiplier = 1.2;
                    regimePositionSizeMultiplier = 0.6;
                    regimeAllowShorts = false;
                    maxDailyTrades = 4;
                    break;
                    
                case MarketRegime.Accumulation:
                    regimeSignalQualityMultiplier = 0.9;
                    regimePositionSizeMultiplier = 1.1;
                    regimeAllowShorts = false;
                    maxDailyTrades = 8;
                    break;
                    
                case MarketRegime.Distribution:
                    regimeSignalQualityMultiplier = 1.15;
                    regimePositionSizeMultiplier = 0.7;
                    regimeAllowShorts = true;
                    maxDailyTrades = 5;
                    break;
            }
        }
        #endregion
        
        #region Signal Generation
        private void GenerateEnhancedSignal()
        {
            currentSignal = "";
            signalQuality = 0;
            higherTimeframeConfirmed = false;
            
            // First check higher timeframe bias
            if (BarsArray[1].Count > 0)
            {
                higherTimeframeConfirmed = CheckHigherTimeframeConfirmation();
            }
            else
            {
                higherTimeframeConfirmed = true;
            }
            
            if (!higherTimeframeConfirmed) return;
            
            // Check all setups in priority order (highest quality first)
            // Check simple crossover first (from crossover strategy)
            if (CheckEMA9VWAPCrossover()) return;
            if (CheckSetup8_MomentumAlignment()) return;
            if (CheckSetup6_ManipulationCandle()) return;
            if (CheckSetup1_EMAVWAPBreakout()) return;
            if (CheckSetup5_PivotZoneReversal()) return;
            if (CheckSetup3_VWAPRejection()) return;
            if (CheckSetup4_SupportResistanceAO()) return;
            if (CheckSetup10_BreakoutRetest()) return;
            if (CheckSetup7_VPA()) return;
            if (CheckSetup9_GapFill()) return;
            
            // Log crossover status (from crossover strategy)
            if (debugMode && Time[0] != lastCrossoverCheck)
            {
                lastCrossoverCheck = Time[0];
                crossoverCheckCount++;
                
                double ema9Val = vwapIndicator.GetEMA9Value();
                double vwapVal = vwapIndicator.GetVWAPValue();
                double distance = Math.Abs(ema9Val - vwapVal);
                bool closeToXover = distance < (TickSize * 10);
                
                if (CurrentBar % 10 == 0 || closeToXover)
                {
                    Print($"\nSignal Check #{crossoverCheckCount} at {Time[0]}:");
                    Print($"  EMA9: {ema9Val:F4}, VWAP: {vwapVal:F4}, Distance: {distance:F4}");
                    Print($"  Close to Crossover: {closeToXover}");
                }
            }
        }
        
        private bool CheckHigherTimeframeConfirmation()
        {
            if (BarsArray[1].Count < 2) return false;
            
            // Higher timeframe trend confirmation
            bool htBullishTrend = Closes[1][0] > ema9_HT[0] && ema9_HT[0] > vwap_HT[0];
            bool htBearishTrend = Closes[1][0] < ema9_HT[0] && ema9_HT[0] < vwap_HT[0];
            
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
        
        // Simple EMA9/VWAP Crossover (from crossover strategy)
        private bool CheckEMA9VWAPCrossover()
        {
            bool bullishCross = vwapIndicator.IsBullishCrossover();
            bool bearishCross = vwapIndicator.IsBearishCrossover();
            
            if (bullishCross)
            {
                currentSignal = "G";
                signalQuality = CalculateSignalQuality(true);
                activeSetup = 0; // Simple crossover
                return true;
            }
            
            if (bearishCross && shortTradingEnabled && IsShortSafeToTrade())
            {
                currentSignal = "Top";
                signalQuality = CalculateSignalQuality(false);
                activeSetup = 0; // Simple crossover
                return true;
            }
            
            return false;
        }
        
        // SETUP 1: EMA9 + VWAP Bullish Breakout
        private bool CheckSetup1_EMAVWAPBreakout()
        {
            if (Close[0] > ema9[0] && ema9[0] > vwapIndicator.GetVWAPValue() && 
                Low[0] <= nearestSupport * 1.002 && Close[0] > nearestSupport &&
                aoValue > 0 && volume[0] > volumeAvg[0] * volumeThreshold)
            {
                currentSignal = "G";
                signalQuality = CalculateSignalQuality(true);
                activeSetup = 1;
                return true;
            }
            return false;
        }
        
        // SETUP 2: EMA9 + VWAP Bearish Breakdown
        private bool CheckSetup2_EMAVWAPBreakdown()
        {
            if (Close[0] < ema9[0] && ema9[0] < vwapIndicator.GetVWAPValue() && 
                High[0] >= nearestResistance * 0.998 && Close[0] < nearestResistance &&
                aoValue < 0 && volume[0] > volumeAvg[0] * volumeThreshold &&
                shortTradingEnabled && IsShortSafeToTrade())
            {
                currentSignal = "Top";
                signalQuality = CalculateSignalQuality(false);
                activeSetup = 2;
                return true;
            }
            return false;
        }
        
        // SETUP 3: VWAP Rejection Setup
        private bool CheckSetup3_VWAPRejection()
        {
            if (IsVWAPRejectionSetup())
            {
                double vwapVal = vwapIndicator.GetVWAPValue();
                if (Close[0] > vwapVal && Close[0] > Open[0])
                {
                    currentSignal = "G";
                    signalQuality = CalculateSignalQuality(true) * 0.95;
                    activeSetup = 3;
                    return true;
                }
                else if (Close[0] < vwapVal && Close[0] < Open[0] && 
                         shortTradingEnabled && IsShortSafeToTrade())
                {
                    currentSignal = "Top";
                    signalQuality = CalculateSignalQuality(false) * 0.95;
                    activeSetup = 3;
                    return true;
                }
            }
            return false;
        }
        
        // SETUP 4: Support/Resistance + AO Zero Cross
        private bool CheckSetup4_SupportResistanceAO()
        {
            if (Low[0] <= nearestSupport * 1.003 && aoValue > 0.001 && aoPrevValue <= 0 &&
                Close[0] > Open[0])
            {
                currentSignal = "G";
                signalQuality = CalculateSignalQuality(true) * 0.90;
                activeSetup = 4;
                return true;
            }
            else if (High[0] >= nearestResistance * 0.997 && aoValue < -0.001 && aoPrevValue >= 0 &&
                     Close[0] < Open[0] && shortTradingEnabled && IsShortSafeToTrade())
            {
                currentSignal = "Top";
                signalQuality = CalculateSignalQuality(false) * 0.90;
                activeSetup = 4;
                return true;
            }
            return false;
        }
        
        // SETUP 5: Pivot Zone Reversal
        private bool CheckSetup5_PivotZoneReversal()
        {
            if (CurrentBar < 2) return false;
            
            double pivotPoint = (High[1] + Low[1] + Close[1]) / 3;
            double r1 = (2 * pivotPoint) - Low[1];
            double s1 = (2 * pivotPoint) - High[1];
            
            bool atPivotSupport = Math.Abs(Close[0] - s1) <= atr[0] * 0.3;
            bool atPivotResistance = Math.Abs(Close[0] - r1) <= atr[0] * 0.3;
            
            if (atPivotSupport && Close[0] > Open[0] && aoValue > aoPrevValue &&
                volume[0] > volumeAvg[0] * volumeThreshold)
            {
                currentSignal = "G";
                signalQuality = CalculateSignalQuality(true) * 0.92;
                activeSetup = 5;
                return true;
            }
            
            if (atPivotResistance && Close[0] < Open[0] && aoValue < aoPrevValue &&
                volume[0] > volumeAvg[0] * volumeThreshold &&
                IsShortSafeToTrade())
            {
                currentSignal = "Top";
                signalQuality = CalculateSignalQuality(false) * 0.92;
                activeSetup = 5;
                return true;
            }
            
            return false;
        }
        
        // SETUP 6: Manipulation Candle Setup
        private bool CheckSetup6_ManipulationCandle()
        {
            if (CurrentBar < 3) return false;
            
            bool bullishMC = Low[0] < Low[1] && Close[0] > High[1] && Close[0] > Open[0];
            bool bearishMC = High[0] > High[1] && Close[0] < Low[1] && Close[0] < Open[0];
            
            bool strongVolume = volume[0] > volumeAvg[0] * volumeThreshold * 1.4;
            bool nearKeyLevel = Math.Abs(Close[0] - nearestSupport) <= atr[0] * 0.4 ||
                               Math.Abs(Close[0] - nearestResistance) <= atr[0] * 0.4;
            
            if (bullishMC && strongVolume && nearKeyLevel)
            {
                currentSignal = "G";
                signalQuality = CalculateSignalQuality(true) * 1.05;
                activeSetup = 6;
                return true;
            }
            
            if (bearishMC && strongVolume && nearKeyLevel && IsShortSafeToTrade())
            {
                currentSignal = "Top";
                signalQuality = CalculateSignalQuality(false) * 1.05;
                activeSetup = 6;
                return true;
            }
            
            return false;
        }
        
        // SETUP 7: Volume Price Analysis
        private bool CheckSetup7_VPA()
        {
            if (CurrentBar < 5) return false;
            
            double avgVolume5 = (volume[0] + volume[1] + volume[2] + volume[3] + volume[4]) / 5;
            double currentVolumeRatio = volume[0] / avgVolume5;
            
            double spread = High[0] - Low[0];
            double avgSpread = (Math.Abs(High[0] - Low[0]) + Math.Abs(High[1] - Low[1]) + 
                              Math.Abs(High[2] - Low[2])) / 3;
            
            bool highVolumeNarrowSpread = currentVolumeRatio > 2.0 && spread < avgSpread * 0.7;
            bool closingStrong = Close[0] > (High[0] + Low[0]) / 2;
            bool closingWeak = Close[0] < (High[0] + Low[0]) / 2;
            
            if (highVolumeNarrowSpread && closingStrong && Close[0] > ema9[0])
            {
                currentSignal = "G";
                signalQuality = CalculateSignalQuality(true) * 0.88;
                activeSetup = 7;
                return true;
            }
            
            if (highVolumeNarrowSpread && closingWeak && Close[0] < ema9[0] && IsShortSafeToTrade())
            {
                currentSignal = "Top";
                signalQuality = CalculateSignalQuality(false) * 0.88;
                activeSetup = 7;
                return true;
            }
            
            return false;
        }
        
        // SETUP 8: Multi-Timeframe Momentum Alignment
        private bool CheckSetup8_MomentumAlignment()
        {
            if (BarsArray[1].Count < 3) return false;
            
            bool primaryBullish = Close[0] > ema9[0] && aoValue > 0;
            bool primaryBearish = Close[0] < ema9[0] && aoValue < 0;
            
            bool higherTFBullish = Closes[1][0] > ema9_HT[0] && aoValue_HT > 0;
            bool higherTFBearish = Closes[1][0] < ema9_HT[0] && aoValue_HT < 0;
            
            bool momentumAccelerating = false;
            if (primaryBullish && higherTFBullish)
            {
                momentumAccelerating = aoValue > aoPrevValue && aoValue_HT > aoPrevValue_HT;
            }
            else if (primaryBearish && higherTFBearish)
            {
                momentumAccelerating = aoValue < aoPrevValue && aoValue_HT < aoPrevValue_HT;
            }
            
            bool volumeExpansion = volume[0] > volumeAvg[0] * volumeThreshold * 1.5;
            
            if (primaryBullish && higherTFBullish && momentumAccelerating && volumeExpansion)
            {
                currentSignal = "G";
                signalQuality = CalculateSignalQuality(true) * 1.08;
                activeSetup = 8;
                return true;
            }
            
            if (primaryBearish && higherTFBearish && momentumAccelerating && volumeExpansion && IsShortSafeToTrade())
            {
                currentSignal = "Top";
                signalQuality = CalculateSignalQuality(false) * 1.08;
                activeSetup = 8;
                return true;
            }
            
            return false;
        }
        
        // SETUP 9: Gap Fill Strategy
        private bool CheckSetup9_GapFill()
        {
            if (CurrentBar < 2) return false;
            
            double gapSize = Math.Abs(Open[0] - Close[1]);
            double minGapSize = atr[0] * 0.5;
            
            if (gapSize < minGapSize) return false;
            
            bool isGapUp = Open[0] > Close[1] + minGapSize;
            bool isGapDown = Open[0] < Close[1] - minGapSize;
            
            bool gapFillLong = isGapDown && Close[0] > Open[0] && 
                              Close[0] > (Open[0] + Close[1]) / 2;
            
            bool gapFillShort = isGapUp && Close[0] < Open[0] && 
                               Close[0] < (Open[0] + Close[1]) / 2;
            
            if (gapFillLong && volume[0] > volumeAvg[0] * volumeThreshold)
            {
                currentSignal = "G";
                signalQuality = CalculateSignalQuality(true) * 0.85;
                activeSetup = 9;
                return true;
            }
            
            if (gapFillShort && volume[0] > volumeAvg[0] * volumeThreshold && IsShortSafeToTrade())
            {
                currentSignal = "Top";
                signalQuality = CalculateSignalQuality(false) * 0.85;
                activeSetup = 9;
                return true;
            }
            
            return false;
        }
        
        // SETUP 10: Breakout Retest Setup
        private bool CheckSetup10_BreakoutRetest()
        {
            if (CurrentBar < 20) return false;
            
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
            
            if (recentBreakoutUp && Math.Abs(Close[0] - breakoutLevel) <= atr[0] * 0.4 &&
                Close[0] > breakoutLevel && Close[0] > Open[0])
            {
                currentSignal = "G";
                signalQuality = CalculateSignalQuality(true) * 0.90;
                activeSetup = 10;
                return true;
            }
            
            if (recentBreakoutDown && Math.Abs(Close[0] - breakoutLevel) <= atr[0] * 0.4 &&
                Close[0] < breakoutLevel && Close[0] < Open[0] && IsShortSafeToTrade())
            {
                currentSignal = "Top";
                signalQuality = CalculateSignalQuality(false) * 0.90;
                activeSetup = 10;
                return true;
            }
            
            return false;
        }
        
        private bool IsVWAPRejectionSetup()
        {
            double vwapDistance = Math.Abs(Close[0] - vwapIndicator.GetVWAPValue()) / atr[0];
            return vwapDistance <= 0.6;
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
        
        private double CalculateSignalQuality(bool isBullish)
        {
            double quality = 0.25; // Reduced base to accommodate Level 2 data
            
            // Trend alignment (30%)
            double vwapVal = vwapIndicator.GetVWAPValue();
            if (isBullish && Close[0] > ema9[0] && ema9[0] > vwapVal)
                quality += 0.30;
            else if (!isBullish && Close[0] < ema9[0] && ema9[0] < vwapVal)
                quality += 0.30;
            else if ((isBullish && Close[0] > ema9[0]) || (!isBullish && Close[0] < ema9[0]))
                quality += 0.18;
            
            // Higher timeframe confirmation (20%)
            if (higherTimeframeConfirmed)
                quality += 0.20;
            
            // AO momentum (15%)
            if (isBullish && aoValue > 0.001 && aoPrevValue <= 0)
                quality += 0.15;
            else if (!isBullish && aoValue < -0.001 && aoPrevValue >= 0)
                quality += 0.15;
            else if ((isBullish && aoValue > 0) || (!isBullish && aoValue < 0))
                quality += 0.10;
            
            // Volume confirmation (10%)
            double volRatio = volume[0] / volumeAvg[0];
            if (volRatio >= volumeThreshold * 1.2)
                quality += 0.10;
            else if (volRatio >= volumeThreshold)
                quality += 0.08;
            
            // Level 2 Market Data confirmation (15%)
            if (isBullish && isVolumeImbalanceBullish)
                quality += 0.15;
            else if (!isBullish && isVolumeImbalanceBearish)
                quality += 0.15;
            else if (isBullish && bidAskRatio > 1.0)
                quality += 0.08;
            else if (!isBullish && bidAskRatio < 1.0)
                quality += 0.08;
            
            // Apply regime adjustment
            quality *= regimeSignalQualityMultiplier;
            
            return Math.Min(1.0, quality);
        }
        #endregion
        
        #region Trading Logic
        private void CheckForSignals()
        {
            // Don't enter if we just exited (from crossover strategy)
            if (barsSinceExit < reEntryCooldown)
            {
                if (debugMode && (currentSignal == "G" || currentSignal == "Top"))
                    Print($"Signal detected but in cooldown period. Bars since exit: {barsSinceExit}/{reEntryCooldown}");
                return;
            }
            
            // Get current values
            double ema9Val = vwapIndicator.GetEMA9Value();
            double vwapVal = vwapIndicator.GetVWAPValue();
            double currentVolume = volume[0];
            double avgVolume = volumeAvg[0];
            double atrValue = atr[0];
            
            // Validate indicator values (from crossover strategy)
            if (double.IsNaN(ema9Val) || double.IsNaN(vwapVal) || double.IsNaN(atrValue) || atrValue <= 0)
            {
                if (debugMode && CurrentBar % 50 == 0)
                    Print($"Invalid indicator values - EMA9: {ema9Val}, VWAP: {vwapVal}, ATR: {atrValue}");
                return;
            }
            
            // Volume filter check (from crossover strategy)
            bool volumeCheckPassed = true;
            if (useVolumeFilter && avgVolume > 0)
            {
                double volumeThresholdAdjusted = softLimitTriggered ? volumeThreshold * 1.5 : volumeThreshold;
                volumeCheckPassed = currentVolume >= avgVolume * volumeThresholdAdjusted;
                
                if (debugMode && (currentSignal == "G" || currentSignal == "Top") && !volumeCheckPassed)
                {
                    Print($"  >> SIGNAL BLOCKED by volume filter: {currentVolume:F0} < {avgVolume * volumeThresholdAdjusted:F0}");
                }
            }
            
            double adjustedThreshold = signalQualityThreshold * regimeSignalQualityMultiplier;
            
            if (signalQuality < adjustedThreshold || !volumeCheckPassed) return;
            
            if (currentSignal == "G" && signalQuality >= adjustedThreshold)
            {
                // Calculate stop BEFORE entering (from crossover strategy)
                double calculatedStop = ema9Val - (atrValue * atrStopMultiplier);
                
                // Validate stop
                if (calculatedStop <= 0 || calculatedStop >= Close[0] || double.IsNaN(calculatedStop))
                {
                    Print($"WARNING: Invalid long stop calculation. Stop: {calculatedStop:F2}, Close: {Close[0]:F2}, EMA9: {ema9Val:F2}, ATR: {atrValue:F2}");
                    return;
                }
                
                int contracts = CalculatePositionSize();
                if (contracts > 0)
                {
                    Print($"\n*** BULLISH SIGNAL - SETUP {activeSetup} ***");
                    Print($"Time: {Time[0]}, EMA9: {ema9Val:F2}, VWAP: {vwapVal:F2}");
                    Print($"Entry: {Close[0]:F2}, Calculated Stop: {calculatedStop:F2}, Risk: {Close[0] - calculatedStop:F2} points");
                    Print($"Signal Quality: {signalQuality:F2}, Contracts: {contracts}");
                    Print($"Regime: {currentRegime}");
                    
                    EnterLong(contracts, "FKS_Long_Setup" + activeSetup);
                    isLong = true;
                    isShort = false;
                    entryPrice = Close[0];
                    currentStop = calculatedStop;
                    
                    Print($"LONG ENTERED - Entry: {entryPrice:F2}, Stop: {currentStop:F2}");
                    Print("********************************\n");
                }
            }
            else if (currentSignal == "Top" && signalQuality >= adjustedThreshold)
            {
                // Calculate stop BEFORE entering (from crossover strategy)
                double calculatedStop = ema9Val + (atrValue * atrStopMultiplier);
                
                // Validate stop
                if (calculatedStop <= 0 || calculatedStop <= Close[0] || double.IsNaN(calculatedStop))
                {
                    Print($"WARNING: Invalid short stop calculation. Stop: {calculatedStop:F2}, Close: {Close[0]:F2}, EMA9: {ema9Val:F2}, ATR: {atrValue:F2}");
                    return;
                }
                
                int contracts = CalculatePositionSize();
                if (contracts > 0)
                {
                    Print($"\n*** BEARISH SIGNAL - SETUP {activeSetup} ***");
                    Print($"Time: {Time[0]}, EMA9: {ema9Val:F2}, VWAP: {vwapVal:F2}");
                    Print($"Entry: {Close[0]:F2}, Calculated Stop: {calculatedStop:F2}, Risk: {calculatedStop - Close[0]:F2} points");
                    Print($"Signal Quality: {signalQuality:F2}, Contracts: {contracts}");
                    Print($"Regime: {currentRegime}");
                    
                    EnterShort(contracts, "FKS_Short_Setup" + activeSetup);
                    isLong = false;
                    isShort = true;
                    entryPrice = Close[0];
                    currentStop = calculatedStop;
                    
                    Print($"SHORT ENTERED - Entry: {entryPrice:F2}, Stop: {currentStop:F2}");
                    Print("*********************************\n");
                }
            }
        }
        
        private int CalculatePositionSize()
        {
            // Check minimum profit potential
            double minProfitTicks = 10; // From commission optimization
            double expectedMoveTicks = (atr[0] * atrTargetMultiplier) / Instrument.MasterInstrument.TickSize;
            
            if (expectedMoveTicks < minProfitTicks) return 0;
            
            int contracts = baseContracts;
            
            // Tier system with regime adjustment
            if (signalQuality >= 0.85)
                contracts = Math.Min(maxContracts, baseContracts * 3);
            else if (signalQuality >= 0.75)
                contracts = Math.Min(maxContracts, baseContracts * 2);
            else
                contracts = baseContracts;
            
            // Apply regime position size multiplier
            contracts = (int)(contracts * regimePositionSizeMultiplier);
            contracts = Math.Max(1, Math.Min(maxContracts, contracts));
            
            // Reduce position size when soft limits are triggered
            if (softLimitTriggered)
            {
                contracts = Math.Max(1, contracts / 2);
            }
            
            // Additional reductions for shorts
            if (currentSignal == "Top")
            {
                contracts = Math.Max(1, contracts - 1);
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
        
        private bool ShouldTrade()
        {
            // Time filter
            if (IsOutsideTradingHours()) return false;
            
            // Hard limits - completely stop trading
            if (currentDailyPnL >= hardProfitLimit)
            {
                if (debugMode && CurrentBar % 100 == 0) 
                    Print($"HARD PROFIT LIMIT REACHED: {currentDailyPnL:F2} >= {hardProfitLimit}");
                return false;
            }
            
            if (currentDailyPnL <= -hardLossLimit)
            {
                if (debugMode && CurrentBar % 100 == 0) 
                    Print($"HARD LOSS LIMIT REACHED: {currentDailyPnL:F2} <= -{hardLossLimit}");
                return false;
            }
            
            // Soft limits - reduce trading activity
            if (!softLimitTriggered)
            {
                if (currentDailyPnL >= softProfitLimit)
                {
                    softLimitTriggered = true;
                    Print($"\n*** SOFT PROFIT LIMIT TRIGGERED: {currentDailyPnL:F2} >= {softProfitLimit} ***");
                }
                else if (currentDailyPnL <= -softLossLimit)
                {
                    softLimitTriggered = true;
                    Print($"\n*** SOFT LOSS LIMIT TRIGGERED: {currentDailyPnL:F2} <= -{softLossLimit} ***");
                }
            }
            
            // Only allow high-quality trades when soft limits are triggered
            if (softLimitTriggered && signalQuality < signalQualityThreshold * 1.15) return false;
            
            // Daily limits
            if (todaysTrades >= maxDailyTrades) return false;
            if (consecutiveLosses >= 3) return false;
            
            // Original P&L limits (keep as backup)
            if (currentDailyPnL <= -dailyLossLimit) return false;
            if (currentDailyPnL >= dailyProfitTarget) return false;
            
            // Time between trades (increase when soft limits triggered)
            double minMinutesBetweenTrades = softLimitTriggered ? 5 : 3;
            if ((DateTime.Now - lastTradeTime).TotalMinutes < minMinutesBetweenTrades) return false;
            
            // Short-specific checks
            if (currentSignal == "Top" && !shortTradingEnabled) return false;
            
            return true;
        }
        
        private bool IsOutsideTradingHours()
        {
            int hour = Time[0].Hour;
            return hour >= stopHour;
        }
        
        private void ResetDailyCounters()
        {
            currentDailyPnL = 0;
            todaysTrades = 0;
            consecutiveLosses = 0;
            consecutiveShortLosses = 0;
            tradingEnabled = true;
            shortTradingEnabled = true;
            softLimitTriggered = false;
            crossoverCheckCount = 0;
            
            if (debugMode) Print($"\n=== New trading day: {currentDay} ===");
        }
        #endregion
        
        #region Position Management (Enhanced from Crossover Strategy)
        private void ManagePositionEnhanced()
        {
            // Exit early if no position is currently open
            if (Position.MarketPosition == MarketPosition.Flat)
                return;

            double ema9Value = vwapIndicator.GetEMA9Value();
            double atrValue = atr[0];

            // Validate values
            if (double.IsNaN(ema9Value) || double.IsNaN(atrValue) || atrValue <= 0)
            {
                if (debugMode) Print($"WARNING: Invalid values in position management - EMA9: {ema9Value}, ATR: {atrValue}");
                return;
            }

            // Initialize stop only once when a new position is opened
            if (currentStop == 0)
            {
                if (Position.MarketPosition == MarketPosition.Long)
                {
                    currentStop = ema9Value - (atrValue * atrStopMultiplier);
                    if (debugMode) Print($"Initialized Long stop to {currentStop:F2}");
                }
                else if (Position.MarketPosition == MarketPosition.Short)
                {
                    currentStop = ema9Value + (atrValue * atrStopMultiplier);
                    if (debugMode) Print($"Initialized Short stop to {currentStop:F2}");
                }
                return; // Exit here; we do not update the stop in the same cycle
            }

            // Manage position based on the type
            if (Position.MarketPosition == MarketPosition.Long)
            {
                // Exit if stop has been hit
                if (Close[0] <= currentStop) {
                    Print($"Exiting Long at {Close[0]:F2}, triggered by stop at {currentStop:F2}");
                    ExitPosition("Long_Stop_Hit");
                    return;
                }
                
                // Check for other exit conditions
                if (ShouldExitLong()) {
                    Print($"Exiting Long at {Close[0]:F2}, other conditions met");
                    ExitPosition("Long_Exit");
                    return;
                }
                
                // Trail stop if price moves favorably
                double newStop = ema9Value - (atrValue * atrStopMultiplier);
                if (newStop > currentStop && newStop < Close[0]) {
                    currentStop = newStop;
                    if (debugMode) Print($"Trailing Long stop updated to {currentStop:F2}");
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                // Exit if stop has been hit
                if (Close[0] >= currentStop) {
                    Print($"Exiting Short at {Close[0]:F2}, triggered by stop at {currentStop:F2}");
                    ExitPosition("Short_Stop_Hit");
                    return;
                }
                
                // Check for other exit conditions
                if (ShouldExitShort()) {
                    Print($"Exiting Short at {Close[0]:F2}, other conditions met");
                    ExitPosition("Short_Exit");
                    return;
                }
                
                // Trail stop if price moves favorably
                double newStop = ema9Value + (atrValue * atrStopMultiplier);
                if (newStop < currentStop && newStop > Close[0]) {
                    currentStop = newStop;
                    if (debugMode) Print($"Trailing Short stop updated to {currentStop:F2}");
                }
            }
        }
        
        private bool ShouldExitLong()
        {
            // REMOVED: Crossover exit logic to prevent infinite loop
            // REMOVED: Signal-based exits as they cause rapid cycling
            
            // Only exit on strong momentum reversal
            if (aoValue < -0.001 && aoPrevValue >= 0) return true;
            
            // Exit on strong trend reversal
            if (Close[0] < ema9[0] && ema9[0] < ema9[1] && Close[0] < Close[1]) return true;
            
            // Exit on higher timeframe momentum reversal
            if (BarsArray[1].Count > 0 && aoValue_HT < -0.001 && aoPrevValue_HT >= 0)
                return true;
            
            return false;
        }
        
        private bool ShouldExitShort()
        {
            // REMOVED: Crossover exit logic to prevent infinite loop
            // REMOVED: Signal-based exits as they cause rapid cycling
            
            // Only exit on strong momentum reversal
            if (aoValue > 0.001 && aoPrevValue <= 0) return true;
            
            // Exit on strong trend reversal
            if (Close[0] > ema9[0] && ema9[0] > ema9[1] && Close[0] > Close[1]) return true;
            
            // Exit on higher timeframe momentum reversal
            if (BarsArray[1].Count > 0 && aoValue_HT > 0.001 && aoPrevValue_HT <= 0)
                return true;
            
            return false;
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
            target1Hit = false;
            target2Hit = false;
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
            }
        }
        
        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution.IsEntry)
            {
                double atrValue = atr[0];
                
                if (marketPosition == MarketPosition.Long)
                {
                    // Initial stop is already set in CheckForSignals
                    // Set targets
                    target1Price = price + (atrValue * atrTargetMultiplier);
                    target2Price = price + (atrValue * atrTargetMultiplier * 2);
                    
                    SetStopLoss("", CalculationMode.Price, currentStop, false);
                    SetProfitTarget("", CalculationMode.Price, target2Price, false);
                }
                else if (marketPosition == MarketPosition.Short)
                {
                    // Initial stop is already set in CheckForSignals
                    // Set targets
                    target1Price = price - (atrValue * atrTargetMultiplier);
                    target2Price = price - (atrValue * atrTargetMultiplier * 1.5);
                    
                    SetStopLoss("", CalculationMode.Price, currentStop, false);
                    SetProfitTarget("", CalculationMode.Price, target2Price, false);
                }
            }
            
            UpdateGlobalPositions(marketPosition, quantity);
        }
        
        protected override void OnPositionUpdate(Position position, double averagePrice, int quantity, MarketPosition marketPosition)
        {
            if (marketPosition == MarketPosition.Flat && SystemPerformance.AllTrades.Count > 0)
            {
                Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                currentDailyPnL += lastTrade.ProfitCurrency;
                
                Print($"\n*** TRADE CLOSED ***");
                Print($"Setup: {activeSetup}");
                Print($"Exit Price: {lastTrade.Exit.Price:F2}");
                Print($"P&L: {lastTrade.ProfitCurrency:F2}");
                Print($"Daily P&L: {currentDailyPnL:F2}");
                Print($"Trades Today: {todaysTrades}");
                Print($"Soft Limit Triggered: {softLimitTriggered}");
                Print("********************\n");
                
                if (lastTrade.ProfitCurrency < 0)
                {
                    consecutiveLosses++;
                    if (lastTrade.Entry.Order.OrderAction == OrderAction.SellShort)
                    {
                        consecutiveShortLosses++;
                        if (consecutiveShortLosses >= 3)
                        {
                            shortTradingEnabled = false;
                            if (debugMode) Print("Short trading disabled due to consecutive losses");
                        }
                    }
                }
                else
                {
                    consecutiveLosses = 0;
                    consecutiveShortLosses = 0;
                    shortTradingEnabled = true;
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
        
        private double CalculatePricePosition()
        {
            if (CurrentBar < 20) return 0.5;
            
            double high20 = MAX(High, 20)[0];
            double low20 = MIN(Low, 20)[0];
            
            if (high20 == low20) return 0.5;
            
            return (Close[0] - low20) / (high20 - low20);
        }
        
        private double CalculateStandardDeviation(double[] values)
        {
            if (values.Length == 0) return 0;
            
            double mean = values.Average();
            double sumSquaredDiff = values.Sum(v => Math.Pow(v - mean, 2));
            return Math.Sqrt(sumSquaredDiff / values.Length);
        }
        #endregion
        
        #region Rendering
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
                string stopText = Position.MarketPosition == MarketPosition.Long ? 
                    $"Long Stop: {currentStop:F2}" : $"Short Stop: {currentStop:F2}";
                
                using (var textFormat = new SharpDX.DirectWrite.TextFormat(Core.Globals.DirectWriteFactory, 
                    ChartControl.Properties.LabelFont.Family.ToString(), 
                    (float)ChartControl.Properties.LabelFont.Size))
                {
                    RenderTarget.DrawText(stopText, 
                        textFormat, 
                        new SharpDX.RectangleF(ChartPanel.X + 10, (float)stopY - 15, 150, 20),
                        textBrush);
                }
                    
                // Draw targets if not hit
                if (!target1Hit)
                {
                    double target1Y = chartScale.GetYByValue(target1Price);
                    SharpDX.Direct2D1.Brush target1Brush = Brushes.Green.ToDxBrush(RenderTarget);
                    RenderTarget.DrawLine(
                        new SharpDX.Vector2(ChartPanel.X, (float)target1Y),
                        new SharpDX.Vector2(ChartPanel.X + ChartPanel.W, (float)target1Y),
                        target1Brush, 1);
                }
                
                if (!target2Hit)
                {
                    double target2Y = chartScale.GetYByValue(target2Price);
                    SharpDX.Direct2D1.Brush target2Brush = Brushes.LightGreen.ToDxBrush(RenderTarget);
                    RenderTarget.DrawLine(
                        new SharpDX.Vector2(ChartPanel.X, (float)target2Y),
                        new SharpDX.Vector2(ChartPanel.X + ChartPanel.W, (float)target2Y),
                        target2Brush, 1);
                }
            }
        }
        #endregion
    }
}