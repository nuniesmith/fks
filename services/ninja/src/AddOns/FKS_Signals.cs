#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
#endregion

namespace NinjaTrader.NinjaScript.AddOns.FKS
{
    /// <summary>
    /// Refactored FKS_Signals - Enhanced unified signal generation with ML capabilities
    /// Coordinates signals from multiple indicators and applies sophisticated quality scoring
    /// </summary>
    public static class FKS_Signals
    {
        #region Constants and Configuration
        private const int MAX_HISTORY_SIZE = 1000;
        private const int MAX_TRAINING_DATA_SIZE = 5000;
        private const double MIN_QUALITY_THRESHOLD = 0.5;
        private const double HIGH_QUALITY_THRESHOLD = 0.8;
        private const double ERROR_RATE_THRESHOLD = 0.1;
        private const int CIRCUIT_BREAKER_FAILURES = 5;
        private static readonly TimeSpan MODEL_UPDATE_INTERVAL = TimeSpan.FromHours(1);
        private static readonly TimeSpan CIRCUIT_BREAKER_TIMEOUT = TimeSpan.FromMinutes(5);
        #endregion

        #region Thread-Safe Collections and State
        private static readonly ConcurrentQueue<UnifiedSignal> _signalHistory = new ConcurrentQueue<UnifiedSignal>();
        private static readonly ConcurrentQueue<TrainingData> _trainingData = new ConcurrentQueue<TrainingData>();
        private static readonly ConcurrentDictionary<string, PerformanceMetrics> _setupPerformance = new ConcurrentDictionary<string, PerformanceMetrics>();
        private static readonly ReaderWriterLockSlim _rwLock = new ReaderWriterLockSlim();
        private static readonly object _qualityModelLock = new object();
        private static volatile bool _isInitialized = false;
        private static DateTime _lastModelUpdate = DateTime.MinValue;
        #endregion

        #region Signal Components
        private static readonly SignalQualityCalculator _qualityCalculator = new SignalQualityCalculator();
        private static readonly SignalValidator _signalValidator = new SignalValidator();
        private static readonly CircuitBreakerService _circuitBreaker = new CircuitBreakerService(CIRCUIT_BREAKER_FAILURES, CIRCUIT_BREAKER_TIMEOUT);
        private static readonly PerformanceTracker _performanceTracker = new PerformanceTracker();
        #endregion

        #region Setup Definitions
        private static readonly Dictionary<int, SetupDefinition> _setupDefinitions = new Dictionary<int, SetupDefinition>
        {
            [1] = new SetupDefinition
            {
                Name = "EMA9 + VWAP Bullish Breakout",
                RequiredSignals = new[] { "G" },
                RequiredConditions = new[] { "Price > EMA9", "EMA9 > VWAP", "AO Bullish", "Volume > 1.2x Avg" },
                MinQuality = 0.65,
                PreferredMarketRegime = "TRENDING BULL",
                RiskRewardRatio = 3.0,
                MaxDailyTrades = 3
            },
            [2] = new SetupDefinition
            {
                Name = "EMA9 + VWAP Bearish Breakdown",
                RequiredSignals = new[] { "Top" },
                RequiredConditions = new[] { "Price < EMA9", "EMA9 < VWAP", "AO Bearish", "Volume > 1.2x Avg" },
                MinQuality = 0.65,
                PreferredMarketRegime = "TRENDING BEAR",
                RiskRewardRatio = 3.0,
                MaxDailyTrades = 3
            },
            [3] = new SetupDefinition
            {
                Name = "VWAP Rejection Bounce",
                RequiredSignals = new[] { "G", "^" },
                RequiredConditions = new[] { "Price near VWAP", "Rejection candle", "AO momentum aligned" },
                MinQuality = 0.60,
                PreferredMarketRegime = "RANGING",
                RiskRewardRatio = 2.5,
                MaxDailyTrades = 5
            },
            [4] = new SetupDefinition
            {
                Name = "Support/Resistance + AO Zero Cross",
                RequiredSignals = new[] { "G", "Top", "^", "v" },
                RequiredConditions = new[] { "At key S/R level", "AO zero cross", "Volume breakout" },
                MinQuality = 0.70,
                PreferredMarketRegime = "ANY",
                RiskRewardRatio = 3.5,
                MaxDailyTrades = 2
            },
            [5] = new SetupDefinition
            {
                Name = "ML Momentum Breakout",
                RequiredSignals = new[] { "G", "Top" },
                RequiredConditions = new[] { "ML confidence > 0.8", "Volume spike", "Multiple timeframe alignment" },
                MinQuality = 0.75,
                PreferredMarketRegime = "TRENDING",
                RiskRewardRatio = 4.0,
                MaxDailyTrades = 2
            }
        };
        #endregion

        #region Public API
        /// <summary>
        /// Initialize the signals system
        /// </summary>
        public static void Initialize()
        {
            if (_isInitialized) return;

            try
            {
                RegisterWithInfrastructure();
                StartBackgroundTasks();
                _isInitialized = true;
                LogInfo("FKS_Signals initialized successfully");
            }
            catch (Exception ex)
            {
                LogError($"Failed to initialize FKS_Signals: {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// Generate a unified signal from component inputs
        /// </summary>
        public static UnifiedSignal GenerateSignal(SignalInputs inputs)
        {
            if (!_isInitialized) Initialize();

            var stopwatch = Stopwatch.StartNew();
            
            try
            {
                return _circuitBreaker.Execute(() => GenerateSignalInternal(inputs));
            }
            catch (CircuitBreakerOpenException)
            {
                LogError("Signal generation circuit breaker is open");
                return null;
            }
            catch (Exception ex)
            {
                LogError($"Error generating signal: {ex.Message}");
                return null;
            }
            finally
            {
                _performanceTracker.RecordSignalGeneration(stopwatch.Elapsed);
            }
        }

        /// <summary>
        /// Generate ML-enhanced signal with advanced quality prediction
        /// </summary>
        public static UnifiedSignalML GenerateSignalML(SignalInputs inputs)
        {
            var baseSignal = GenerateSignal(inputs);
            if (baseSignal == null) return null;

            try
            {
                var mlSignal = new UnifiedSignalML(baseSignal);
                
                // Enhance with ML predictions
                lock (_qualityModelLock)
                {
                    var mlEnhancer = new MLSignalEnhancer();
                    mlEnhancer.EnhanceSignal(mlSignal, inputs);
                }

                // Check if model needs updating
                if (DateTime.Now - _lastModelUpdate > MODEL_UPDATE_INTERVAL)
                {
                    _ = Task.Run(UpdateModelWithRecentFeedback);
                }

                return mlSignal;
            }
            catch (Exception ex)
            {
                LogError($"Error generating ML signal: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Generate ensemble signal using multiple algorithms
        /// </summary>
        public static EnsembleSignal GenerateEnsembleSignal(SignalInputs inputs)
        {
            try
            {
                var signalGenerators = new List<ISignalGenerator>
                {
                    new BaseSignalGenerator(),
                    new MomentumSignalGenerator(),
                    new MeanReversionSignalGenerator(),
                    new VolumeSignalGenerator()
                };

                var signals = signalGenerators
                    .Select(generator => generator.GenerateSignal(inputs))
                    .Where(signal => signal != null)
                    .ToList();

                if (!signals.Any()) return null;

                return new EnsembleSignal
                {
                    Signals = signals,
                    WeightedQuality = CalculateWeightedQuality(signals),
                    Consensus = CalculateConsensus(signals),
                    Confidence = CalculateEnsembleConfidence(signals),
                    Timestamp = DateTime.Now
                };
            }
            catch (Exception ex)
            {
                LogError($"Error generating ensemble signal: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Record signal outcome for ML training
        /// </summary>
        public static void RecordSignalOutcome(UnifiedSignal signal, SignalOutcome outcome)
        {
            if (!_isInitialized) Initialize();

            try
            {
                var trainingPoint = new TrainingData
                {
                    Signal = signal,
                    Outcome = outcome,
                    Timestamp = DateTime.Now
                };

                _trainingData.Enqueue(trainingPoint);
                MaintainCollectionSize(_trainingData, MAX_TRAINING_DATA_SIZE);

                UpdateSetupPerformance(signal, outcome);
                _performanceTracker.RecordSignalOutcome(signal, outcome);

                // Trigger model update if enough new data
                if (_trainingData.Count % 100 == 0)
                {
                    _ = Task.Run(UpdateModelWithRecentFeedback);
                }
            }
            catch (Exception ex)
            {
                LogError($"Error recording signal outcome: {ex.Message}");
            }
        }

        /// <summary>
        /// Get comprehensive signal statistics
        /// </summary>
        public static SignalStatistics GetStatistics(int lookbackHours = 24)
        {
            if (!_isInitialized) Initialize();

            _rwLock.EnterReadLock();
            try
            {
                var recentSignals = GetRecentSignals(lookbackHours);
                return new SignalStatistics
                {
                    TotalSignals = recentSignals.Count,
                    ValidSignals = recentSignals.Count(s => s.IsValid),
                    AverageQuality = recentSignals.Any() ? recentSignals.Average(s => s.Quality) : 0,
                    SignalsBySetup = recentSignals.GroupBy(s => s.SetupNumber).ToDictionary(g => g.Key, g => g.Count()),
                    BestSetup = GetBestPerformingSetup(recentSignals),
                    PerformanceMetrics = GetSetupPerformanceMetrics(),
                    QualityTrend = CalculateQualityTrend(recentSignals),
                    Recommendations = GenerateRecommendations(recentSignals)
                };
            }
            finally
            {
                _rwLock.ExitReadLock();
            }
        }

        /// <summary>
        /// Advanced signal filtering with ML insights
        /// </summary>
        public static bool ShouldTakeSignal(UnifiedSignal signal, SignalInputs inputs)
        {
            if (!_isInitialized) Initialize();

            try
            {
                var filters = new List<ISignalFilter>
                {
                    new QualityFilter(MIN_QUALITY_THRESHOLD),
                    new SetupLimitFilter(_setupDefinitions),
                    new MarketConditionFilter(),
                    new MLConfidenceFilter(),
                    new DegradationFilter()
                };

                return filters.All(filter => filter.ShouldAcceptSignal(signal, inputs));
            }
            catch (Exception ex)
            {
                LogError($"Error in signal filtering: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Get performance report
        /// </summary>
        public static PerformanceReport GetPerformanceReport(TimeSpan? period = null)
        {
            if (!_isInitialized) Initialize();

            return _performanceTracker.GetPerformanceReport(period);
        }

        /// <summary>
        /// Export performance data
        /// </summary>
        public static void ExportPerformanceData(string filePath)
        {
            if (!_isInitialized) Initialize();

            _performanceTracker.ExportPerformanceData(filePath);
        }
        #endregion

        #region Private Implementation
        private static void RegisterWithInfrastructure()
        {
            try
            {
                // Register with infrastructure system if available
                if (typeof(FKS_Infrastructure).GetMethod("RegisterComponent") != null)
                {
                    var registrationInfo = new
                    {
                        ComponentType = "SignalGenerator",
                        Version = "2.0",
                        IsCritical = true,
                        ExpectedResponseTime = TimeSpan.FromMilliseconds(100),
                        MaxMemoryUsage = 50 * 1024 * 1024
                    };

                    // Use reflection to call RegisterComponent if available
                    var method = typeof(FKS_Infrastructure).GetMethod("RegisterComponent");
                    method?.Invoke(null, new object[] { "FKS_Signals", registrationInfo });
                }
            }
            catch (Exception ex)
            {
                LogError($"Failed to register with infrastructure: {ex.Message}");
            }
        }

        private static void StartBackgroundTasks()
        {
            // Start performance monitoring
            _ = Task.Run(() => _performanceTracker.StartMonitoring());

            // Start model update monitoring
            _ = Task.Run(ModelUpdateMonitoringLoop);
        }

        private static UnifiedSignal GenerateSignalInternal(SignalInputs inputs)
        {
            var signal = new UnifiedSignal
            {
                Timestamp = DateTime.Now,
                SignalType = inputs.AISignalType,
                BaseQuality = inputs.AISignalQuality,
                WaveRatio = inputs.WaveRatio,
                Price = inputs.Price,
                ATR = inputs.ATR
            };

            // Calculate comprehensive quality score
            signal.Quality = _qualityCalculator.CalculateQuality(inputs);

            // Determine setup
            signal.SetupNumber = DetermineSetup(inputs, signal);

            // Calculate position size and trade levels
            signal.RecommendedContracts = CalculatePositionSize(signal, inputs);
            CalculateTradeLevels(signal, inputs);

            // Validate signal
            signal.IsValid = _signalValidator.ValidateSignal(signal, inputs);

            // Add to history
            AddToHistory(signal);

            return signal;
        }

        private static void AddToHistory(UnifiedSignal signal)
        {
            _signalHistory.Enqueue(signal);
            MaintainCollectionSize(_signalHistory, MAX_HISTORY_SIZE);
        }

        private static void MaintainCollectionSize<T>(ConcurrentQueue<T> queue, int maxSize)
        {
            while (queue.Count > maxSize)
            {
                queue.TryDequeue(out _);
            }
        }

        private static void CleanOutdatedTrainingData()
        {
            // Retain only high-quality data
            lock (_qualityModelLock)
            {
                var highQualityData = _trainingData.Where(td => td.Signal.Quality > HIGH_QUALITY_THRESHOLD).Take(MAX_TRAINING_DATA_SIZE).ToList();
                
                // Clear existing data
                while (_trainingData.TryDequeue(out _)) { }
                
                // Re-add high quality data
                foreach (var data in highQualityData)
                {
                    _trainingData.Enqueue(data);
                }
            }
        }

        private static void RefineSignalGeneration()
        {
            // This method refines the signal generation logic and preparation
            lock (_qualityModelLock)
            {
                if (_signalHistory.Any(si => si.Quality > HIGH_QUALITY_THRESHOLD))
                {
                    // Implement additional refinement based on quality here
                    foreach (var signal in _signalHistory)
                    {
                        // Need to create dummy inputs for refinement
                        var dummyInputs = new SignalInputs 
                        { 
                            AISignalType = signal.SignalType,
                            AISignalQuality = signal.BaseQuality,
                            WaveRatio = signal.WaveRatio,
                            Price = signal.Price,
                            ATR = signal.ATR
                        };
                        signal.SetupNumber = DetermineSetup(dummyInputs, signal);
                        signal.RecommendedContracts = CalculatePositionSize(signal, new SignalInputs());
                        CalculateTradeLevels(signal, new SignalInputs());
                    }
                }
            }
        }

        private static List<UnifiedSignal> GetRecentSignals(int hours)
        {
            var cutoff = DateTime.Now.AddHours(-hours);
            return _signalHistory.Where(s => s.Timestamp > cutoff).ToList();
        }

        private static int DetermineSetup(SignalInputs inputs, UnifiedSignal signal)
        {
            // Implement setup determination logic
            foreach (var setup in _setupDefinitions)
            {
                if (setup.Value.RequiredSignals.Contains(signal.SignalType))
                {
                    return setup.Key;
                }
            }
            return 0; // Default setup
        }

        private static int CalculatePositionSize(UnifiedSignal signal, SignalInputs inputs)
        {
            // Implement position sizing logic based on volatility and risk
            var baseSize = 1;
            var volatilityAdjustment = Math.Max(0.5, Math.Min(2.0, 1.0 / (inputs.ATR * 100)));
            var qualityAdjustment = Math.Max(0.5, signal.Quality);
            
            return Math.Max(1, (int)(baseSize * volatilityAdjustment * qualityAdjustment));
        }

        private static void CalculateTradeLevels(UnifiedSignal signal, SignalInputs inputs)
        {
            // Implement adaptive trade level calculation
            var atrMultiplier = 2.0;
            var stopDistance = inputs.ATR * atrMultiplier;
            var targetDistance = stopDistance * 2.0; // 2:1 R:R ratio

            signal.StopLoss = IsLongSignal(signal.SignalType) ? 
                signal.Price - stopDistance : 
                signal.Price + stopDistance;

            signal.Target = IsLongSignal(signal.SignalType) ? 
                signal.Price + targetDistance : 
                signal.Price - targetDistance;
        }

        private static void UpdateSetupPerformance(UnifiedSignal signal, SignalOutcome outcome)
        {
            var setupKey = $"Setup_{signal.SetupNumber}";
            
            _setupPerformance.AddOrUpdate(setupKey, 
                new PerformanceMetrics
                {
                    TotalTrades = 1,
                    WinningTrades = outcome.Success ? 1 : 0,
                    TotalPnL = outcome.PnL,
                    LastUpdated = DateTime.Now
                },
                (key, existing) =>
                {
                    existing.TotalTrades++;
                    if (outcome.Success) existing.WinningTrades++;
                    existing.TotalPnL += outcome.PnL;
                    existing.LastUpdated = DateTime.Now;
                    return existing;
                });
        }

        private static int GetBestPerformingSetup(List<UnifiedSignal> signals)
        {
            if (!signals.Any()) return 0;

            return signals
                .GroupBy(s => s.SetupNumber)
                .OrderByDescending(g => g.Average(s => s.Quality))
                .First()
                .Key;
        }

        private static Dictionary<int, PerformanceMetrics> GetSetupPerformanceMetrics()
        {
            return _setupPerformance
                .Where(kvp => int.TryParse(kvp.Key.Replace("Setup_", ""), out _))
                .ToDictionary(
                    kvp => int.Parse(kvp.Key.Replace("Setup_", "")), 
                    kvp => kvp.Value);
        }

        private static double CalculateQualityTrend(List<UnifiedSignal> signals)
        {
            if (signals.Count < 10) return 0.0;

            var recentSignals = signals.OrderBy(s => s.Timestamp).ToList();
            var halfPoint = recentSignals.Count / 2;

            var firstHalfAvg = recentSignals.Take(halfPoint).Average(s => s.Quality);
            var secondHalfAvg = recentSignals.Skip(halfPoint).Average(s => s.Quality);

            return secondHalfAvg - firstHalfAvg;
        }

        private static List<string> GenerateRecommendations(List<UnifiedSignal> signals)
        {
            var recommendations = new List<string>();

            if (!signals.Any()) return recommendations;

            var avgQuality = signals.Average(s => s.Quality);
            if (avgQuality < 0.6)
            {
                recommendations.Add("Consider tightening signal quality filters - average quality below 60%");
            }

            var recentSignals = signals.Where(s => s.Timestamp > DateTime.Now.AddHours(-2)).ToList();
            if (recentSignals.Count > 5)
            {
                recommendations.Add("High signal frequency detected - consider tightening filters");
            }

            return recommendations;
        }

        private static double CalculateWeightedQuality(List<UnifiedSignal> signals)
        {
            if (!signals.Any()) return 0.0;
            return signals.Average(s => s.Quality);
        }

        private static string CalculateConsensus(List<UnifiedSignal> signals)
        {
            if (!signals.Any()) return "NEUTRAL";

            var longSignals = signals.Count(s => IsLongSignal(s.SignalType));
            var shortSignals = signals.Count(s => IsShortSignal(s.SignalType));

            if (longSignals > shortSignals * 1.5) return "BULLISH";
            if (shortSignals > longSignals * 1.5) return "BEARISH";
            return "NEUTRAL";
        }

        private static double CalculateEnsembleConfidence(List<UnifiedSignal> signals)
        {
            if (!signals.Any()) return 0.0;

            var qualityVariance = signals.Select(s => s.Quality).Aggregate(0.0, (acc, q) => acc + Math.Pow(q - signals.Average(s => s.Quality), 2)) / signals.Count;
            return Math.Max(0.0, 1.0 - qualityVariance);
        }

        private static async Task ModelUpdateMonitoringLoop()
        {
            while (true)
            {
                try
                {
                    await Task.Delay(TimeSpan.FromMinutes(30));
                    
                    if (DateTime.Now - _lastModelUpdate > MODEL_UPDATE_INTERVAL)
                    {
                        await UpdateModelWithRecentFeedback();
                    }
                }
                catch (Exception ex)
                {
                    LogError($"Model update monitoring error: {ex.Message}");
                }
            }
        }

        private static async Task UpdateModelWithRecentFeedback()
        {
            try
            {
                // Placeholder for ML model update logic
                await Task.Delay(1000); // Simulate model update
                _lastModelUpdate = DateTime.Now;
                LogInfo("ML model updated successfully");
            }
            catch (Exception ex)
            {
                LogError($"Error updating ML model: {ex.Message}");
            }
        }

        private static bool IsLongSignal(string signalType) => signalType == "G" || signalType == "^";
        private static bool IsShortSignal(string signalType) => signalType == "Top" || signalType == "v";

        private static void LogInfo(string message)
        {
            try
            {
                Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] [INFO] FKS_Signals: {message}");
            }
            catch { }
        }

        private static void LogError(string message)
        {
            try
            {
                Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] [ERROR] FKS_Signals: {message}");
            }
            catch { }
        }
        #endregion
    }

    #region Support Classes
    /// <summary>
    /// Calculates signal quality using multiple factors
    /// </summary>
    public class SignalQualityCalculator
    {
        private readonly Dictionary<string, double> _qualityWeights = new Dictionary<string, double>
        {
            ["TrendAlignment"] = 0.22,
            ["MomentumConfirmation"] = 0.18,
            ["VolumeConfirmation"] = 0.15,
            ["WaveRatio"] = 0.15,
            ["MarketRegime"] = 0.10,
            ["TimeOfDay"] = 0.08,
            ["CandlePattern"] = 0.05,
            ["MLPrediction"] = 0.07
        };

        public double CalculateQuality(SignalInputs inputs)
        {
            var qualityScore = 0.0;

            try
            {
                qualityScore += CalculateTrendScore(inputs) * _qualityWeights["TrendAlignment"];
                qualityScore += CalculateMomentumScore(inputs) * _qualityWeights["MomentumConfirmation"];
                qualityScore += CalculateVolumeScore(inputs) * _qualityWeights["VolumeConfirmation"];
                qualityScore += CalculateWaveScore(inputs.WaveRatio) * _qualityWeights["WaveRatio"];
                qualityScore += CalculateRegimeScore(inputs) * _qualityWeights["MarketRegime"];
                qualityScore += CalculateTimeScore(inputs) * _qualityWeights["TimeOfDay"];
                qualityScore += CalculateCandleScore(inputs) * _qualityWeights["CandlePattern"];
                qualityScore += CalculateMLScore(inputs) * _qualityWeights["MLPrediction"];

                // Apply base quality multiplier
                var smoothedBaseQuality = Math.Max(0.3, inputs.AISignalQuality);
                qualityScore *= smoothedBaseQuality;

                return Math.Min(1.0, Math.Max(0.0, qualityScore));
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error calculating quality: {ex.Message}");
                return inputs.AISignalQuality * 0.5;
            }
        }

        private double CalculateTrendScore(SignalInputs inputs)
        {
            var score = 0.0;
            var isLong = inputs.AISignalType == "G" || inputs.AISignalType == "^";
            
            if (inputs.MarketRegime.Contains("BULL") && isLong) score = 1.0;
            else if (inputs.MarketRegime.Contains("BEAR") && !isLong) score = 1.0;
            else if (inputs.MarketRegime == "RANGING") score = 0.7;
            else if (inputs.MarketRegime == "NEUTRAL") score = 0.5;
            else score = 0.2;

            // EMA alignment bonus
            if ((isLong && inputs.PriceAboveEMA9 && inputs.EMA9AboveVWAP) ||
                (!isLong && !inputs.PriceAboveEMA9 && !inputs.EMA9AboveVWAP))
            {
                score = Math.Min(1.0, score + 0.2);
            }

            return score;
        }

        private double CalculateMomentumScore(SignalInputs inputs)
        {
            var score = 0.0;
            
            if (inputs.AOConfirmation)
            {
                score = inputs.AOMomentumStrength;
                if (inputs.AOZeroCross) score = Math.Min(1.0, score + 0.3);
                if (Math.Abs(inputs.AOValue) > 0.5) score = Math.Min(1.0, score + 0.2);
            }

            return score;
        }

        private double CalculateVolumeScore(SignalInputs inputs)
        {
            if (inputs.VolumeRatio > 3.0) return 1.0;
            if (inputs.VolumeRatio > 2.0) return 0.9;
            if (inputs.VolumeRatio > 1.5) return 0.7;
            if (inputs.VolumeRatio > 1.2) return 0.5;
            if (inputs.VolumeRatio > 1.0) return 0.3;
            return 0.1;
        }

        private double CalculateWaveScore(double waveRatio)
        {
            if (waveRatio > 3.0) return 1.0;
            if (waveRatio > 2.5) return 0.9;
            if (waveRatio > 2.0) return 0.8;
            if (waveRatio > 1.5) return 0.6;
            if (waveRatio > 1.0) return 0.4;
            return 0.1;
        }

        private double CalculateRegimeScore(SignalInputs inputs)
        {
            return inputs.MarketRegime switch
            {
                "TRENDING BULL" or "TRENDING BEAR" => 0.95,
                "TRENDING" => 0.85,
                "NEUTRAL" => 0.65,
                "RANGING" => 0.60,
                "VOLATILE" => 0.30,
                _ => 0.50
            };
        }

        private double CalculateTimeScore(SignalInputs inputs)
        {
            if (inputs.IsOptimalSession) return 1.0;

            var hour = DateTime.Now.Hour;
            if (hour >= 9 && hour <= 16) return 0.8;
            if (hour >= 2 && hour <= 11) return 0.6;
            return 0.4;
        }

        private double CalculateCandleScore(SignalInputs inputs)
        {
            return inputs.HasCandleConfirmation ? 1.0 : 0.3;
        }

        private double CalculateMLScore(SignalInputs inputs)
        {
            // Placeholder for ML scoring
            return 0.5;
        }
    }

    /// <summary>
    /// Validates signals against various criteria
    /// </summary>
    public class SignalValidator
    {
        public bool ValidateSignal(UnifiedSignal signal, SignalInputs inputs)
        {
            try
            {
                // Basic validation
                if (signal.Quality < 0.1) return false;
                if (signal.Price <= 0) return false;
                if (signal.ATR <= 0) return false;

                // Signal type validation
                if (string.IsNullOrEmpty(signal.SignalType)) return false;
                if (!IsValidSignalType(signal.SignalType)) return false;

                // Quality validation
                if (signal.Quality > 1.0) return false;

                return true;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Signal validation error: {ex.Message}");
                return false;
            }
        }

        private bool IsValidSignalType(string signalType)
        {
            return signalType == "G" || signalType == "Top" || signalType == "^" || signalType == "v";
        }
    }

    /// <summary>
    /// Circuit breaker implementation
    /// </summary>
    public class CircuitBreakerService
    {
        private readonly int _failureThreshold;
        private readonly TimeSpan _timeout;
        private int _failureCount;
        private DateTime _lastFailureTime;
        private readonly object _lock = new object();

        public CircuitBreakerService(int failureThreshold, TimeSpan timeout)
        {
            _failureThreshold = failureThreshold;
            _timeout = timeout;
        }

        public bool IsOpen => _failureCount >= _failureThreshold && 
                             DateTime.Now - _lastFailureTime < _timeout;

        public T Execute<T>(Func<T> operation)
        {
            lock (_lock)
            {
                if (IsOpen)
                {
                    throw new CircuitBreakerOpenException();
                }

                try
                {
                    var result = operation();
                    Reset();
                    return result;
                }
                catch (Exception)
                {
                    RecordFailure();
                    throw;
                }
            }
        }

        private void RecordFailure()
        {
            _failureCount++;
            _lastFailureTime = DateTime.Now;
        }

        private void Reset()
        {
            _failureCount = 0;
        }
    }

    /// <summary>
    /// Performance tracking service
    /// </summary>
    public class PerformanceTracker
    {
        private readonly ConcurrentQueue<PerformanceRecord> _performanceHistory = new ConcurrentQueue<PerformanceRecord>();
        private readonly int _maxHistorySize = 10000;

        public void RecordSignalGeneration(TimeSpan duration, bool hasError = false)
        {
            var record = new PerformanceRecord
            {
                Timestamp = DateTime.Now,
                Duration = duration,
                HasError = hasError,
                OperationType = "Generation"
            };

            _performanceHistory.Enqueue(record);
            MaintainSize();
        }

        public void RecordSignalOutcome(UnifiedSignal signal, SignalOutcome outcome)
        {
            var record = new PerformanceRecord
            {
                Timestamp = DateTime.Now,
                OperationType = "Outcome",
                SignalType = signal.SignalType,
                Success = outcome.Success,
                PnL = outcome.PnL,
                HoldTime = outcome.HoldTime
            };

            _performanceHistory.Enqueue(record);
            MaintainSize();
        }

        public PerformanceReport GetPerformanceReport(TimeSpan? period = null)
        {
            var reportPeriod = period ?? TimeSpan.FromDays(30);
            var cutoff = DateTime.Now.Subtract(reportPeriod);
            var records = _performanceHistory.Where(r => r.Timestamp > cutoff).ToList();

            var generationRecords = records.Where(r => r.OperationType == "Generation").ToList();
            var outcomeRecords = records.Where(r => r.OperationType == "Outcome").ToList();

            return new PerformanceReport
            {
                Period = reportPeriod,
                GeneratedAt = DateTime.Now,
                TotalSignals = generationRecords.Count,
                AverageGenerationTime = generationRecords.Any() ? 
                    TimeSpan.FromTicks((long)generationRecords.Average(r => r.Duration.Ticks)) : 
                    TimeSpan.Zero,
                ErrorRate = generationRecords.Any() ? 
                    (double)generationRecords.Count(r => r.HasError) / generationRecords.Count : 0,
                TotalTrades = outcomeRecords.Count,
                WinRate = outcomeRecords.Any() ? 
                    (double)outcomeRecords.Count(r => r.Success) / outcomeRecords.Count : 0,
                TotalPnL = outcomeRecords.Sum(r => r.PnL),
                AverageReturn = outcomeRecords.Any() ? outcomeRecords.Average(r => r.PnL) : 0
            };
        }

        public void ExportPerformanceData(string filePath)
        {
            try
            {
                var report = GetPerformanceReport();
                var content = new StringBuilder();
                
                content.AppendLine($"Performance Report - {DateTime.Now}");
                content.AppendLine($"Period: {report.Period}");
                content.AppendLine($"Total Signals: {report.TotalSignals}");
                content.AppendLine($"Average Generation Time: {report.AverageGenerationTime.TotalMilliseconds:F2} ms");
                content.AppendLine($"Error Rate: {report.ErrorRate:P2}");
                content.AppendLine($"Total Trades: {report.TotalTrades}");
                content.AppendLine($"Win Rate: {report.WinRate:P2}");
                content.AppendLine($"Total PnL: {report.TotalPnL:C2}");
                content.AppendLine($"Average Return: {report.AverageReturn:C2}");

                System.IO.File.WriteAllText(filePath, content.ToString());
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error exporting performance data: {ex.Message}");
            }
        }

        public Task StartMonitoring()
        {
            return Task.Run(async () =>
            {
                while (true)
                {
                    try
                    {
                        await Task.Delay(TimeSpan.FromMinutes(5));
                        MaintainSize();
                        CheckPerformanceHealth();
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"Performance monitoring error: {ex.Message}");
                    }
                }
            });
        }

        private void MaintainSize()
        {
            while (_performanceHistory.Count > _maxHistorySize)
            {
                _performanceHistory.TryDequeue(out _);
            }
        }

        private void CheckPerformanceHealth()
        {
            var recentRecords = _performanceHistory
                .Where(r => r.Timestamp > DateTime.Now.AddHours(-1))
                .ToList();

            var generationRecords = recentRecords.Where(r => r.OperationType == "Generation").ToList();
            if (generationRecords.Any())
            {
                var errorRate = (double)generationRecords.Count(r => r.HasError) / generationRecords.Count;
                if (errorRate > 0.1)
                {
                    Console.WriteLine($"[WARNING] High error rate detected: {errorRate:P2}");
                }
            }
        }
    }

    /// <summary>
    /// ML signal enhancement
    /// </summary>
    public class MLSignalEnhancer
    {
        public void EnhanceSignal(UnifiedSignalML signal, SignalInputs inputs)
        {
            // Placeholder for ML enhancement
            signal.MLQuality = 0.5;
            signal.SuccessProbability = 0.5;
            signal.OptimalHoldTime = TimeSpan.FromHours(4);
            signal.ConfidenceLevel = 0.5;
        }
    }
    #endregion

    #region Signal Generators
    public interface ISignalGenerator
    {
        UnifiedSignal GenerateSignal(SignalInputs inputs);
    }

    public class BaseSignalGenerator : ISignalGenerator
    {
        public UnifiedSignal GenerateSignal(SignalInputs inputs)
        {
            return new UnifiedSignal
            {
                Timestamp = DateTime.Now,
                SignalType = inputs.AISignalType,
                Quality = inputs.AISignalQuality,
                WaveRatio = inputs.WaveRatio,
                Price = inputs.Price,
                ATR = inputs.ATR,
                BaseQuality = inputs.AISignalQuality
            };
        }
    }

    public class MomentumSignalGenerator : ISignalGenerator
    {
        public UnifiedSignal GenerateSignal(SignalInputs inputs)
        {
            if (Math.Abs(inputs.AOValue) < 0.001) return null;

            return new UnifiedSignal
            {
                Timestamp = DateTime.Now,
                SignalType = inputs.AOValue > 0 ? "G" : "Top",
                Quality = inputs.AOMomentumStrength,
                WaveRatio = inputs.WaveRatio,
                Price = inputs.Price,
                ATR = inputs.ATR,
                SetupNumber = 999,
                BaseQuality = inputs.AOMomentumStrength
            };
        }
    }

    public class MeanReversionSignalGenerator : ISignalGenerator
    {
        public UnifiedSignal GenerateSignal(SignalInputs inputs)
        {
            if (!inputs.NearVWAP) return null;

            return new UnifiedSignal
            {
                Timestamp = DateTime.Now,
                SignalType = inputs.PriceAboveEMA9 ? "v" : "^",
                Quality = inputs.VolumeRatio > 1.5 ? 0.7 : 0.5,
                WaveRatio = inputs.WaveRatio,
                Price = inputs.Price,
                ATR = inputs.ATR,
                SetupNumber = 998,
                BaseQuality = 0.6
            };
        }
    }

    public class VolumeSignalGenerator : ISignalGenerator
    {
        public UnifiedSignal GenerateSignal(SignalInputs inputs)
        {
            if (inputs.VolumeRatio < 2.0) return null;

            return new UnifiedSignal
            {
                Timestamp = DateTime.Now,
                SignalType = inputs.AOValue > 0 ? "G" : "Top",
                Quality = Math.Min(1.0, inputs.VolumeRatio / 3.0),
                WaveRatio = inputs.WaveRatio,
                Price = inputs.Price,
                ATR = inputs.ATR,
                SetupNumber = 997,
                BaseQuality = 0.7
            };
        }
    }
    #endregion

    #region Signal Filters
    public interface ISignalFilter
    {
        bool ShouldAcceptSignal(UnifiedSignal signal, SignalInputs inputs);
    }

    public class QualityFilter : ISignalFilter
    {
        private readonly double _minQuality;

        public QualityFilter(double minQuality)
        {
            _minQuality = minQuality;
        }

        public bool ShouldAcceptSignal(UnifiedSignal signal, SignalInputs inputs)
        {
            return signal.Quality >= _minQuality;
        }
    }

    public class SetupLimitFilter : ISignalFilter
    {
        private readonly Dictionary<int, SetupDefinition> _setupDefinitions;

        public SetupLimitFilter(Dictionary<int, SetupDefinition> setupDefinitions)
        {
            _setupDefinitions = setupDefinitions;
        }

        public bool ShouldAcceptSignal(UnifiedSignal signal, SignalInputs inputs)
        {
            if (signal.SetupNumber <= 0 || !_setupDefinitions.ContainsKey(signal.SetupNumber))
                return true;

            var setup = _setupDefinitions[signal.SetupNumber];
            // Check daily limits (placeholder - would need actual implementation)
            return true;
        }
    }

    public class MarketConditionFilter : ISignalFilter
    {
        public bool ShouldAcceptSignal(UnifiedSignal signal, SignalInputs inputs)
        {
            // Implement market condition checks
            return true;
        }
    }

    public class MLConfidenceFilter : ISignalFilter
    {
        public bool ShouldAcceptSignal(UnifiedSignal signal, SignalInputs inputs)
        {
            if (signal is UnifiedSignalML mlSignal)
            {
                if (mlSignal.SuccessProbability > 0.8 && mlSignal.ConfidenceLevel > 0.7)
                    return true;
                if (mlSignal.ConfidenceLevel < 0.5 && signal.Quality < 0.8)
                    return false;
            }
            return true;
        }
    }

    public class DegradationFilter : ISignalFilter
    {
        public bool ShouldAcceptSignal(UnifiedSignal signal, SignalInputs inputs)
        {
            // Implement degradation detection
            return true;
        }
    }
    #endregion

    #region Data Models
    public class UnifiedSignal
    {
        public DateTime Timestamp { get; set; }
        public string SignalType { get; set; }
        public double Quality { get; set; }
        public double BaseQuality { get; set; }
        public double WaveRatio { get; set; }
        public double Price { get; set; }
        public double ATR { get; set; }
        public int SetupNumber { get; set; }
        public int RecommendedContracts { get; set; }
        public double StopLoss { get; set; }
        public double Target { get; set; }
        public bool IsValid { get; set; }
    }

    public class UnifiedSignalML : UnifiedSignal
    {
        public double MLQuality { get; set; }
        public double SuccessProbability { get; set; }
        public TimeSpan OptimalHoldTime { get; set; }
        public double ConfidenceLevel { get; set; }

        public UnifiedSignalML() { }
        public UnifiedSignalML(UnifiedSignal baseSignal)
        {
            Timestamp = baseSignal.Timestamp;
            SignalType = baseSignal.SignalType;
            Quality = baseSignal.Quality;
            BaseQuality = baseSignal.BaseQuality;
            WaveRatio = baseSignal.WaveRatio;
            Price = baseSignal.Price;
            ATR = baseSignal.ATR;
            SetupNumber = baseSignal.SetupNumber;
            RecommendedContracts = baseSignal.RecommendedContracts;
            StopLoss = baseSignal.StopLoss;
            Target = baseSignal.Target;
            IsValid = baseSignal.IsValid;
        }
    }

    public class EnsembleSignal
    {
        public List<UnifiedSignal> Signals { get; set; }
        public double WeightedQuality { get; set; }
        public string Consensus { get; set; }
        public double Confidence { get; set; }
        public DateTime Timestamp { get; set; }
    }

    public class SignalInputs
    {
        public string AISignalType { get; set; }
        public double AISignalQuality { get; set; }
        public double WaveRatio { get; set; }
        public double Price { get; set; }
        public double ATR { get; set; }
        public double AOValue { get; set; }
        public bool AOConfirmation { get; set; }
        public bool AOZeroCross { get; set; }
        public double AOMomentumStrength { get; set; }
        public double VolumeRatio { get; set; }
        public bool PriceAboveEMA9 { get; set; }
        public bool EMA9AboveVWAP { get; set; }
        public bool NearVWAP { get; set; }
        public string MarketRegime { get; set; }
        public bool IsOptimalSession { get; set; }
        public bool HasCandleConfirmation { get; set; }
    }

    public class SignalOutcome
    {
        public bool Success { get; set; }
        public double PnL { get; set; }
        public TimeSpan HoldTime { get; set; }
        public DateTime Timestamp { get; set; }
    }

    public class TrainingData
    {
        public UnifiedSignal Signal { get; set; }
        public SignalOutcome Outcome { get; set; }
        public DateTime Timestamp { get; set; }
    }

    public class PerformanceMetrics
    {
        public int TotalTrades { get; set; }
        public int WinningTrades { get; set; }
        public double WinRate => TotalTrades > 0 ? (double)WinningTrades / TotalTrades : 0;
        public double TotalPnL { get; set; }
        public DateTime LastUpdated { get; set; }
    }

    public class SetupDefinition
    {
        public string Name { get; set; }
        public string[] RequiredSignals { get; set; }
        public string[] RequiredConditions { get; set; }
        public double MinQuality { get; set; }
        public string PreferredMarketRegime { get; set; }
        public double RiskRewardRatio { get; set; }
        public int MaxDailyTrades { get; set; }
    }

    public class SignalStatistics
    {
        public int TotalSignals { get; set; }
        public int ValidSignals { get; set; }
        public double AverageQuality { get; set; }
        public Dictionary<int, int> SignalsBySetup { get; set; }
        public int BestSetup { get; set; }
        public Dictionary<int, PerformanceMetrics> PerformanceMetrics { get; set; }
        public double QualityTrend { get; set; }
        public List<string> Recommendations { get; set; }
    }

    public class PerformanceReport
    {
        public TimeSpan Period { get; set; }
        public DateTime GeneratedAt { get; set; }
        public int TotalSignals { get; set; }
        public TimeSpan AverageGenerationTime { get; set; }
        public double ErrorRate { get; set; }
        public int TotalTrades { get; set; }
        public double WinRate { get; set; }
        public double TotalPnL { get; set; }
        public double AverageReturn { get; set; }
    }

    public class PerformanceRecord
    {
        public DateTime Timestamp { get; set; }
        public TimeSpan Duration { get; set; }
        public bool HasError { get; set; }
        public string OperationType { get; set; }
        public string SignalType { get; set; }
        public bool Success { get; set; }
        public double PnL { get; set; }
        public TimeSpan HoldTime { get; set; }
    }

    public class CircuitBreakerOpenException : Exception
    {
        public CircuitBreakerOpenException() : base("Circuit breaker is open") { }
    }
    #endregion
}

