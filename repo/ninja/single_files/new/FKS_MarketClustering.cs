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
    public class FKS_MarketClustering : Strategy
    {
        #region Market Regime Detection
        
        // Market regime enumeration
        public enum MarketRegime
        {
            Bullish,      // Strong uptrend - high momentum, low volatility
            Bearish,      // Strong downtrend - negative returns, high volatility
            Sideways,     // Range-bound - low momentum, stable prices
            Volatile,     // High volatility - uncertain direction
            Accumulation, // Low volatility buildup - preparing for move
            Distribution  // High volume selling - potential reversal
        }
        
        // Clustering data structure
        public class ClusterData
        {
            public double Returns { get; set; }
            public double Volatility { get; set; }
            public double Momentum { get; set; }
            public double Volume { get; set; }
            public double PricePosition { get; set; } // Position within recent range
            public DateTime Timestamp { get; set; }
            public MarketRegime Regime { get; set; }
        }
        
        // Clustering variables
        private List<ClusterData> historicalData = new List<ClusterData>();
        private MarketRegime currentRegime = MarketRegime.Sideways;
        private MarketRegime previousRegime = MarketRegime.Sideways;
        private int regimeChangeCount = 0;
        private DateTime lastRegimeChange = DateTime.MinValue;
        
        // Clustering parameters
        private int clusteringLookback = 100;  // Bars to analyze for clustering
        private int recalculateInterval = 20;  // Recalculate clusters every N bars
        private double regimeConfidenceThreshold = 0.7;
        
        // Market regime thresholds (dynamically adjusted)
        private double bullishMomentumThreshold = 0.02;
        private double bearishMomentumThreshold = -0.02;
        private double lowVolatilityThreshold = 0.015;
        private double highVolatilityThreshold = 0.035;
        private double highVolumeThreshold = 1.5;
        
        // Indicators for clustering
        private ATR atr;
        private VOL volume;
        private SMA volumeAvg;
        private EMA ema20;
        private EMA ema50;
        private Series<double> returns;
        private Series<double> volatility;
        private Series<double> momentum;
        
        #endregion
        
        #region Strategy Integration Variables
        
        // Strategy adjustments based on regime
        private double regimeSignalQualityMultiplier = 1.0;
        private double regimePositionSizeMultiplier = 1.0;
        private double regimeStopMultiplier = 1.0;
        private double regimeTargetMultiplier = 1.0;
        private bool regimeAllowShorts = true;
        
        // Regime-specific settings
        private Dictionary<MarketRegime, RegimeSettings> regimeSettings;
        
        public class RegimeSettings
        {
            public double SignalQualityMultiplier { get; set; }
            public double PositionSizeMultiplier { get; set; }
            public double StopMultiplier { get; set; }
            public double TargetMultiplier { get; set; }
            public bool AllowShorts { get; set; }
            public double VolumeThresholdMultiplier { get; set; }
            public int MaxDailyTrades { get; set; }
            public string PreferredSetups { get; set; }
        }
        
        #endregion
        
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"FKS Strategy with Market Clustering Analysis";
                Name = "FKS_MarketClustering";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                BarsRequiredToTrade = 100; // Higher requirement for clustering
                
                // Clustering parameters
                EnableClustering = true;
                ClusteringLookback = 100;
                RecalculateInterval = 20;
                ShowRegimeInfo = true;
                
                // Base strategy parameters
                SignalQualityThreshold = 0.65;
                VolumeThreshold = 1.2;
                MaxDailyTrades = 8;
                
                InitializeRegimeSettings();
            }
            else if (State == State.DataLoaded)
            {
                // Initialize indicators
                atr = ATR(14);
                volume = VOL();
                volumeAvg = SMA(volume, 20);
                ema20 = EMA(20);
                ema50 = EMA(50);
                
                // Initialize custom series
                returns = new Series<double>(this);
                volatility = new Series<double>(this);
                momentum = new Series<double>(this);
                
                // Initialize clustering data
                historicalData = new List<ClusterData>();
                currentRegime = MarketRegime.Sideways;
                previousRegime = MarketRegime.Sideways;
            }
        }
        
        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade) return;
            
            // Update market data for clustering
            UpdateMarketData();
            
            // Perform clustering analysis
            if (EnableClustering && CurrentBar % RecalculateInterval == 0)
            {
                PerformClusteringAnalysis();
            }
            
            // Classify current market regime
            ClassifyCurrentRegime();
            
            // Adjust strategy parameters based on regime
            AdjustStrategyForRegime();
            
            // Your existing strategy logic here with regime adjustments
            // (This would integrate with your existing FKSStrategyAIO code)
            
            // Display regime information
            if (ShowRegimeInfo)
            {
                DisplayRegimeInfo();
            }
        }
        
        #region Clustering Implementation
        
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
        
        private void PerformClusteringAnalysis()
        {
            if (historicalData.Count < 50) return;
            
            // Simple K-Means clustering implementation
            var clusters = PerformKMeansClustering(historicalData, 6); // 6 clusters for 6 regimes
            
            // Assign regimes to clusters based on characteristics
            AssignRegimesToClusters(clusters);
            
            // Update dynamic thresholds based on clustering results
            UpdateDynamicThresholds(clusters);
        }
        
        private List<List<ClusterData>> PerformKMeansClustering(List<ClusterData> data, int k)
        {
            // Simplified K-Means implementation
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
            
            // Track regime changes
            if (currentRegime != previousRegime)
            {
                regimeChangeCount++;
                lastRegimeChange = Time[0];
                
                if (ShowRegimeInfo)
                {
                    Print($"Regime Change: {previousRegime} → {currentRegime} at {Time[0]}");
                }
            }
        }
        
        private void UpdateDynamicThresholds(List<List<ClusterData>> clusters)
        {
            // Update thresholds based on clustering results
            var allData = clusters.SelectMany(c => c).ToList();
            if (allData.Count == 0) return;
            
            var returns = allData.Select(d => d.Returns).ToArray();
            var volatilities = allData.Select(d => d.Volatility).ToArray();
            var momenta = allData.Select(d => d.Momentum).ToArray();
            var volumes = allData.Select(d => d.Volume).ToArray();
            
            // Calculate percentiles for dynamic thresholds
            Array.Sort(returns);
            Array.Sort(volatilities);
            Array.Sort(momenta);
            Array.Sort(volumes);
            
            int count = returns.Length;
            bullishMomentumThreshold = momenta[(int)(count * 0.75)]; // 75th percentile
            bearishMomentumThreshold = momenta[(int)(count * 0.25)]; // 25th percentile
            lowVolatilityThreshold = volatilities[(int)(count * 0.25)];
            highVolatilityThreshold = volatilities[(int)(count * 0.75)];
            highVolumeThreshold = volumes[(int)(count * 0.75)];
        }
        
        #endregion
        
        #region Strategy Adjustments
        
        private void InitializeRegimeSettings()
        {
            regimeSettings = new Dictionary<MarketRegime, RegimeSettings>
            {
                {
                    MarketRegime.Bullish,
                    new RegimeSettings
                    {
                        SignalQualityMultiplier = 0.95,    // Slightly lower threshold in bull market
                        PositionSizeMultiplier = 1.2,      // Larger positions in bull market
                        StopMultiplier = 1.1,              // Slightly wider stops
                        TargetMultiplier = 1.3,            // Larger targets
                        AllowShorts = false,               // No shorts in bull market
                        VolumeThresholdMultiplier = 0.9,   // Lower volume requirement
                        MaxDailyTrades = 10,               // More trades allowed
                        PreferredSetups = "1,3,6,8"       // Momentum and breakout setups
                    }
                },
                {
                    MarketRegime.Bearish,
                    new RegimeSettings
                    {
                        SignalQualityMultiplier = 1.1,     // Higher threshold in bear market
                        PositionSizeMultiplier = 0.8,      // Smaller positions
                        StopMultiplier = 0.9,              // Tighter stops
                        TargetMultiplier = 0.8,            // Smaller targets
                        AllowShorts = true,                // Allow shorts
                        VolumeThresholdMultiplier = 1.2,   // Higher volume requirement
                        MaxDailyTrades = 6,                // Fewer trades
                        PreferredSetups = "2,4,7,9"       // Breakdown and reversal setups
                    }
                },
                {
                    MarketRegime.Sideways,
                    new RegimeSettings
                    {
                        SignalQualityMultiplier = 1.05,    // Slightly higher threshold
                        PositionSizeMultiplier = 0.9,      // Smaller positions
                        StopMultiplier = 0.85,             // Tighter stops
                        TargetMultiplier = 0.9,            // Smaller targets
                        AllowShorts = true,                // Allow shorts
                        VolumeThresholdMultiplier = 1.1,   // Higher volume requirement
                        MaxDailyTrades = 8,                // Normal trades
                        PreferredSetups = "3,5,7,10"      // Range and reversal setups
                    }
                },
                {
                    MarketRegime.Volatile,
                    new RegimeSettings
                    {
                        SignalQualityMultiplier = 1.2,     // Much higher threshold
                        PositionSizeMultiplier = 0.6,      // Much smaller positions
                        StopMultiplier = 0.8,              // Tighter stops
                        TargetMultiplier = 0.7,            // Smaller targets
                        AllowShorts = false,               // No shorts in volatile market
                        VolumeThresholdMultiplier = 1.3,   // Much higher volume requirement
                        MaxDailyTrades = 4,                // Very few trades
                        PreferredSetups = "6,8"           // Only highest quality setups
                    }
                },
                {
                    MarketRegime.Accumulation,
                    new RegimeSettings
                    {
                        SignalQualityMultiplier = 0.9,     // Lower threshold - good for entries
                        PositionSizeMultiplier = 1.1,      // Larger positions
                        StopMultiplier = 1.2,              // Wider stops
                        TargetMultiplier = 1.4,            // Larger targets
                        AllowShorts = false,               // No shorts during accumulation
                        VolumeThresholdMultiplier = 0.8,   // Lower volume requirement
                        MaxDailyTrades = 8,                // Normal trades
                        PreferredSetups = "1,5,6,8"       // Accumulation and breakout setups
                    }
                },
                {
                    MarketRegime.Distribution,
                    new RegimeSettings
                    {
                        SignalQualityMultiplier = 1.15,    // Higher threshold
                        PositionSizeMultiplier = 0.7,      // Smaller positions
                        StopMultiplier = 0.85,             // Tighter stops
                        TargetMultiplier = 0.85,           // Smaller targets
                        AllowShorts = true,                // Allow shorts
                        VolumeThresholdMultiplier = 1.2,   // Higher volume requirement
                        MaxDailyTrades = 5,                // Fewer trades
                        PreferredSetups = "2,4,7,9"       // Distribution and reversal setups
                    }
                }
            };
        }
        
        private void AdjustStrategyForRegime()
        {
            if (!regimeSettings.ContainsKey(currentRegime)) return;
            
            var settings = regimeSettings[currentRegime];
            
            // Apply regime-specific adjustments
            regimeSignalQualityMultiplier = settings.SignalQualityMultiplier;
            regimePositionSizeMultiplier = settings.PositionSizeMultiplier;
            regimeStopMultiplier = settings.StopMultiplier;
            regimeTargetMultiplier = settings.TargetMultiplier;
            regimeAllowShorts = settings.AllowShorts;
            
            // These would be used in your main strategy logic:
            // - Adjusted signal quality threshold: SignalQualityThreshold * regimeSignalQualityMultiplier
            // - Adjusted position size: baseSize * regimePositionSizeMultiplier
            // - Adjusted stops: ATRStopMultiplier * regimeStopMultiplier
            // - Adjusted targets: ATRTargetMultiplier * regimeTargetMultiplier
        }
        
        #endregion
        
        #region Helper Methods
        
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
        
        private void DisplayRegimeInfo()
        {
            if (CurrentBar % 20 == 0) // Update every 20 bars
            {
                string regimeInfo = $"Market Regime: {currentRegime} | " +
                                   $"Quality Mult: {regimeSignalQualityMultiplier:F2} | " +
                                   $"Size Mult: {regimePositionSizeMultiplier:F2} | " +
                                   $"Shorts: {(regimeAllowShorts ? "Yes" : "No")}";
                
                Print(regimeInfo);
                
                // Draw regime on chart
                DrawTextFixed("RegimeInfo", regimeInfo, TextPosition.TopLeft, 
                             Brushes.White, new SimpleFont("Arial", 10), 
                             Brushes.Black, Brushes.Gray, 100);
            }
        }
        
        // Method to get current regime adjustments for use in main strategy
        public double GetAdjustedSignalQuality(double baseQuality)
        {
            return baseQuality * regimeSignalQualityMultiplier;
        }
        
        public int GetAdjustedPositionSize(int baseSize)
        {
            return (int)(baseSize * regimePositionSizeMultiplier);
        }
        
        public double GetAdjustedStopMultiplier(double baseMultiplier)
        {
            return baseMultiplier * regimeStopMultiplier;
        }
        
        public double GetAdjustedTargetMultiplier(double baseMultiplier)
        {
            return baseMultiplier * regimeTargetMultiplier;
        }
        
        public bool IsShortAllowed()
        {
            return regimeAllowShorts;
        }
        
        public MarketRegime GetCurrentRegime()
        {
            return currentRegime;
        }
        
        #endregion
        
        #region Properties
        
        [NinjaScriptProperty]
        [Display(Name="Enable Clustering", Order=1, GroupName="Clustering Settings")]
        public bool EnableClustering { get; set; }
        
        [NinjaScriptProperty]
        [Range(50, 200)]
        [Display(Name="Clustering Lookback", Order=2, GroupName="Clustering Settings")]
        public int ClusteringLookback { get; set; }
        
        [NinjaScriptProperty]
        [Range(10, 50)]
        [Display(Name="Recalculate Interval", Order=3, GroupName="Clustering Settings")]
        public int RecalculateInterval { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name="Show Regime Info", Order=4, GroupName="Clustering Settings")]
        public bool ShowRegimeInfo { get; set; }
        
        [NinjaScriptProperty]
        [Range(0.5, 1.0)]
        [Display(Name="Signal Quality Threshold", Order=5, GroupName="Strategy Settings")]
        public double SignalQualityThreshold { get; set; }
        
        [NinjaScriptProperty]
        [Range(1.0, 2.0)]
        [Display(Name="Volume Threshold", Order=6, GroupName="Strategy Settings")]
        public double VolumeThreshold { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name="Max Daily Trades", Order=7, GroupName="Strategy Settings")]
        public int MaxDailyTrades { get; set; }
        
        #endregion
    }
}
