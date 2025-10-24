// src/Indicators/FKS_PythonBridge.cs
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Text;
using NinjaTrader.Cbi;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    [Browsable(false)]
    [EditorBrowsable(EditorBrowsableState.Never)]
    public class FKS_PythonBridge : NinjaTrader.NinjaScript.Indicators.Indicator
    {
        private System.Timers.Timer metricsTimer;
        private List<MetricData> pendingMetrics;
        private object metricsLock = new object();
        private string logFilePath;

        // Configuration - now hardcoded constants
        private readonly string pythonApiUrl = PYTHON_API_URL;
        private readonly int metricsIntervalSeconds = METRICS_INTERVAL_SECONDS;
        private readonly bool enableLiveMetrics = ENABLE_LIVE_METRICS;
        private readonly bool enableTradeTracking = ENABLE_TRADE_TRACKING;
        private readonly bool enableSignalTracking = ENABLE_SIGNAL_TRACKING;
        private readonly bool enablePerformanceTracking = ENABLE_PERFORMANCE_TRACKING;

        // Performance tracking
        private double sessionPnL = 0;
        private double maxDrawdown = 0;
        private double peakValue = 0;
        private int tradesCount = 0;
        private int winningTrades = 0;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "FKS Python Bridge - Sends real-time metrics to Python API via file logging";
                Name = "FKS_PythonBridge";
                Calculate = Calculate.OnEachTick;
                IsOverlay = false;
                DisplayInDataBox = true;
                DrawOnPricePanel = false;
                DrawHorizontalGridLines = true;
                DrawVerticalGridLines = true;
                PaintPriceMarkers = true;
                ScaleJustification = NinjaTrader.Gui.Chart.ScaleJustification.Right;
                IsSuspendedWhileInactive = false;

                // Add value series for display
                AddPlot(new Stroke(System.Windows.Media.Brushes.Blue, 2), PlotStyle.Line, "Performance");
                AddPlot(new Stroke(System.Windows.Media.Brushes.Green, 2), PlotStyle.Line, "Signals");
                AddPlot(new Stroke(System.Windows.Media.Brushes.Red, 2), PlotStyle.Line, "Drawdown");
            }
            else if (State == State.Active)
            {
                InitializePythonBridge();
            }
            else if (State == State.Terminated)
            {
                CleanupPythonBridge();
            }
        }

        private void InitializePythonBridge()
        {
            try
            {
                // Setup log file path
                string logsDir = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "logs", "fks_metrics");
                Directory.CreateDirectory(logsDir);
                logFilePath = Path.Combine(logsDir, $"metrics_{Instrument.FullName}_{DateTime.Now:yyyyMMdd}.json");

                // Initialize metrics collection
                pendingMetrics = new List<MetricData>();

                // Setup metrics timer
                if (enableLiveMetrics)
                {
                    metricsTimer = new System.Timers.Timer(metricsIntervalSeconds * 1000);
                    metricsTimer.Elapsed += OnMetricsTimer;
                    metricsTimer.Start();
                }

                // Send initialization metric
                LogMetric(new MetricData
                {
                    MetricType = "initialization",
                    Data = new Dictionary<string, object>
                    {
                        ["instrument"] = Instrument.FullName,
                        ["timestamp"] = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
                        ["session_start"] = true
                    }
                });

                Print($"FKS Python Bridge initialized for {Instrument.FullName}");
                Print($"Metrics log file: {logFilePath}");
            }
            catch (Exception ex)
            {
                Print($"Error initializing Python Bridge: {ex.Message}");
            }
        }

        private void CleanupPythonBridge()
        {
            try
            {
                // Send session end metric
                LogMetric(new MetricData
                {
                    MetricType = "session_end",
                    Data = new Dictionary<string, object>
                    {
                        ["instrument"] = Instrument.FullName,
                        ["session_pnl"] = sessionPnL,
                        ["trades_count"] = tradesCount,
                        ["winning_trades"] = winningTrades,
                        ["win_rate"] = tradesCount > 0 ? (double)winningTrades / tradesCount * 100 : 0,
                        ["max_drawdown"] = maxDrawdown,
                        ["timestamp"] = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
                        ["session_end"] = true
                    }
                });

                // Flush any pending metrics
                FlushPendingMetrics();

                // Cleanup resources
                if (metricsTimer != null)
                {
                    metricsTimer.Stop();
                    metricsTimer.Dispose();
                }

                Print("FKS Python Bridge cleaned up");
            }
            catch (Exception ex)
            {
                Print($"Error cleaning up Python Bridge: {ex.Message}");
            }
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress != 0) return;

            try
            {
                // Update performance tracking
                UpdatePerformanceMetrics();

                // Send bar update metric
                if (enableLiveMetrics && IsFirstTickOfBar)
                {
                    LogBarUpdateMetric();
                }

                // Update indicator plots
                Values[0][0] = sessionPnL; // Performance
                Values[1][0] = GetSignalStrength(); // Signals (placeholder)
                Values[2][0] = maxDrawdown; // Drawdown
            }
            catch (Exception ex)
            {
                Print($"Error in OnBarUpdate: {ex.Message}");
            }
        }

        private void UpdatePerformanceMetrics()
        {
            // Simplified performance tracking without account access
            // This would be enhanced to work with your actual strategy
            sessionPnL += (Close[0] - (CurrentBar > 0 ? Close[1] : Close[0])) * 100; // Placeholder calculation

            // Update peak and drawdown
            if (sessionPnL > peakValue)
            {
                peakValue = sessionPnL;
            }
            else
            {
                double currentDrawdown = peakValue - sessionPnL;
                maxDrawdown = Math.Max(maxDrawdown, currentDrawdown);
            }
        }

        private double GetSignalStrength()
        {
            // Placeholder for signal strength calculation
            // This would integrate with your FKS_AI, FKS_AO indicators
            return Math.Sin(CurrentBar * 0.1) * 50; // Demo signal
        }

        private void LogBarUpdateMetric()
        {
            var barData = new MetricData
            {
                MetricType = "bar_update",
                Data = new Dictionary<string, object>
                {
                    ["instrument"] = Instrument.FullName,
                    ["timestamp"] = Time[0].ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
                    ["open"] = Open[0],
                    ["high"] = High[0],
                    ["low"] = Low[0],
                    ["close"] = Close[0],
                    ["volume"] = Volume[0],
                    ["session_pnl"] = sessionPnL,
                    ["max_drawdown"] = maxDrawdown,
                    ["trades_count"] = tradesCount,
                    ["current_bar"] = CurrentBar
                }
            };

            QueueMetric(barData);
        }

        public void LogTradeMetric(string action, double price, int quantity, double pnl = 0)
        {
            if (!enableTradeTracking) return;

            tradesCount++;
            if (pnl > 0) winningTrades++;

            var tradeData = new MetricData
            {
                MetricType = "trade",
                Data = new Dictionary<string, object>
                {
                    ["instrument"] = Instrument.FullName,
                    ["action"] = action, // "buy", "sell", "close"
                    ["price"] = price,
                    ["quantity"] = quantity,
                    ["pnl"] = pnl,
                    ["timestamp"] = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
                    ["session_pnl"] = sessionPnL,
                    ["trade_number"] = tradesCount
                }
            };

            LogMetric(tradeData);
        }

        public void LogSignalMetric(string signalType, double confidence, string source)
        {
            if (!enableSignalTracking) return;

            var signalData = new MetricData
            {
                MetricType = "signal",
                Data = new Dictionary<string, object>
                {
                    ["instrument"] = Instrument.FullName,
                    ["signal_type"] = signalType, // "buy", "sell", "neutral"
                    ["confidence"] = confidence,
                    ["source"] = source, // "FKS_AI", "FKS_AO", etc.
                    ["price"] = Close[0],
                    ["timestamp"] = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
                    ["bar_time"] = Time[0].ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
                }
            };

            LogMetric(signalData);
        }

        public void LogPerformanceMetric(Dictionary<string, object> performanceData)
        {
            if (!enablePerformanceTracking) return;

            var perfData = new MetricData
            {
                MetricType = "performance",
                Data = new Dictionary<string, object>(performanceData)
                {
                    ["instrument"] = Instrument.FullName,
                    ["timestamp"] = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
                    ["session_pnl"] = sessionPnL,
                    ["max_drawdown"] = maxDrawdown,
                    ["trades_count"] = tradesCount,
                    ["win_rate"] = tradesCount > 0 ? (double)winningTrades / tradesCount * 100 : 0
                }
            };

            LogMetric(perfData);
        }

        private void QueueMetric(MetricData metric)
        {
            try
            {
                lock (metricsLock)
                {
                    pendingMetrics.Add(metric);
                }
            }
            catch (Exception ex)
            {
                Print($"Error queuing metric: {ex.Message}");
            }
        }

        private void LogMetric(MetricData metric)
        {
            try
            {
                string jsonLine = CreateJsonLine(metric);

                lock (metricsLock)
                {
                    File.AppendAllText(logFilePath, jsonLine + Environment.NewLine);
                }
            }
            catch (Exception ex)
            {
                Print($"Error logging metric: {ex.Message}");
            }
        }

        private void OnMetricsTimer(object sender, System.Timers.ElapsedEventArgs e)
        {
            FlushPendingMetrics();
        }

        private void FlushPendingMetrics()
        {
            List<MetricData> metricsToWrite;

            lock (metricsLock)
            {
                if (pendingMetrics.Count == 0) return;

                metricsToWrite = new List<MetricData>(pendingMetrics);
                pendingMetrics.Clear();
            }

            try
            {
                var jsonLines = new StringBuilder();
                foreach (var metric in metricsToWrite)
                {
                    jsonLines.AppendLine(CreateJsonLine(metric));
                }

                File.AppendAllText(logFilePath, jsonLines.ToString());
            }
            catch (Exception ex)
            {
                Print($"Error flushing metrics: {ex.Message}");

                // Re-queue failed metrics (limited retry)
                lock (metricsLock)
                {
                    if (pendingMetrics.Count < 1000) // Prevent memory leak
                    {
                        pendingMetrics.AddRange(metricsToWrite);
                    }
                }
            }
        }

        private string CreateJsonLine(MetricData metric)
        {
            var sb = new StringBuilder();
            sb.Append("{");
            sb.AppendFormat("\"timestamp\":\"{0}\",", metric.Timestamp.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"));
            sb.AppendFormat("\"metric_type\":\"{0}\",", metric.MetricType);
            sb.Append("\"data\":{");

            bool first = true;
            foreach (var kvp in metric.Data)
            {
                if (!first) sb.Append(",");
                first = false;

                sb.AppendFormat("\"{0}\":", kvp.Key);
                if (kvp.Value is string)
                    sb.AppendFormat("\"{0}\"", kvp.Value.ToString().Replace("\"", "\\\""));
                else if (kvp.Value is bool)
                    sb.Append(kvp.Value.ToString().ToLower());
                else
                    sb.Append(kvp.Value?.ToString() ?? "null");
            }

            sb.Append("}}");
            return sb.ToString();
        }

        #region Properties

        #region Production Configuration - Hardcoded per master plan
        
        // Python API configuration - hardcoded for production
        private const string PYTHON_API_URL = "http://localhost:8002";
        private const int METRICS_INTERVAL_SECONDS = 30;
        
        // Feature toggles - hardcoded for production
        private const bool ENABLE_LIVE_METRICS = true;
        private const bool ENABLE_TRADE_TRACKING = true;
        private const bool ENABLE_SIGNAL_TRACKING = true;
        private const bool ENABLE_PERFORMANCE_TRACKING = true;
        
        #endregion
    }

    public class MetricData
    {
        public DateTime Timestamp { get; set; } = DateTime.Now;
        public string MetricType { get; set; }
        public Dictionary<string, object> Data { get; set; } = new Dictionary<string, object>();
    }
    
    #endregion
}
