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
using System.Net.Http;
using System.Net;
using Newtonsoft.Json;
using System.Collections.Concurrent;
using System.Threading;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.FKS
{
    /// <summary>
    /// FKS Python Bridge - Enables communication with Python backend for logging and analysis
    /// Sends trade data, signals, and performance metrics to Python API
    /// </summary>
    public class FKS_PythonBridge : Indicator, FKSCore.IFKSComponent
    {
        #region Variables
        // Component Interface
        public string ComponentId => "FKS_Python";
        public string Version => "1.0.0";
        
        // Connection settings
        private string apiEndpoint = "http://fkstrading.xyz:5000/api";
        private string apiKey = "";
        private int connectionTimeout = 5000; // 5 seconds
        private bool isConnected = false;
        private DateTime lastConnectionCheck = DateTime.MinValue;
        
        // HTTP client
        private HttpClient httpClient;
        private readonly ConcurrentQueue<LogEntry> logQueue = new ConcurrentQueue<LogEntry>();
        private Timer processTimer;
        private bool isProcessing = false;
        
        // Batch settings
        private int batchSize = 10;
        private int maxQueueSize = 1000;
        
        // Statistics
        private int messagesSent = 0;
        private int messagesFailed = 0;
        private DateTime startTime = DateTime.Now;
        #endregion
        
        #region OnStateChange
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"FKS Python Bridge - Connects to Python backend for logging and analysis";
                Name = "FKS_PythonBridge";
                Calculate = Calculate.OnBarClose;
                IsOverlay = false;
                DisplayInDataBox = false;
                DrawOnPricePanel = false;
                DrawHorizontalGridLines = false;
                DrawVerticalGridLines = false;
                PaintPriceMarkers = false;
                ScaleJustification = NinjaTrader.Gui.Chart.ScaleJustification.Right;
                IsSuspendedWhileInactive = false;
                
                // Default settings
                Enabled = true;
                ShowConnectionStatus = true;
                LogTrades = true;
                LogSignals = true;
                LogPerformance = true;
                BatchMode = true;
                DebugMode = false;
            }
            else if (State == State.Configure)
            {
                // Add a dummy plot to satisfy indicator requirements
                AddPlot(Brushes.Transparent, "Connection");
            }
            else if (State == State.DataLoaded)
            {
                if (Enabled)
                {
                    InitializeConnection();
                    
                    // Register with FKS Core
                    try
                    {
                        FKSCore.RegisterComponent(ComponentId, this);
                        SubscribeToEvents();
                    }
                    catch (Exception ex)
                    {
                        Log($"Failed to register with FKS Core: {ex.Message}", LogLevel.Warning);
                    }
                }
            }
            else if (State == State.Terminated)
            {
                Shutdown();
            }
        }
        #endregion
        
        #region OnBarUpdate
        protected override void OnBarUpdate()
        {
            if (!Enabled) return;
            
            // Set dummy plot value
            Values[0][0] = isConnected ? 1 : 0;
            
            // Check connection periodically
            if ((DateTime.Now - lastConnectionCheck).TotalSeconds > 30)
            {
                CheckConnection();
            }
            
            // Log market data periodically
            if (CurrentBar % 60 == 0 && LogPerformance) // Every 60 bars
            {
                LogMarketData();
            }
            
            // Update connection status display
            if (ShowConnectionStatus && CurrentBar % 5 == 0)
            {
                UpdateConnectionDisplay();
            }
        }
        #endregion
        
        #region Connection Management
        private void InitializeConnection()
        {
            try
            {
                httpClient = new HttpClient();
                httpClient.Timeout = TimeSpan.FromMilliseconds(connectionTimeout);
                
                if (!string.IsNullOrEmpty(apiKey))
                {
                    httpClient.DefaultRequestHeaders.Add("X-API-Key", apiKey);
                }
                
                // Start background processor
                processTimer = new Timer(ProcessQueue, null, TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(1));
                
                // Initial connection check
                CheckConnection();
                
                Log("Python Bridge initialized", LogLevel.Information);
            }
            catch (Exception ex)
            {
                Log($"Failed to initialize Python Bridge: {ex.Message}", LogLevel.Error);
                isConnected = false;
            }
        }
        
        private async void CheckConnection()
        {
            try
            {
                var response = await httpClient.GetAsync($"{apiEndpoint}/health");
                isConnected = response.IsSuccessStatusCode;
                lastConnectionCheck = DateTime.Now;
                
                if (isConnected && DebugMode)
                {
                    Log("Python API connection successful", LogLevel.Information);
                }
            }
            catch
            {
                isConnected = false;
                if (DebugMode)
                {
                    Log("Python API connection failed", LogLevel.Warning);
                }
            }
        }
        #endregion
        
        #region Event Subscriptions
        private void SubscribeToEvents()
        {
            // Subscribe to FKS Core events
            FKSCore.SignalGenerated += OnSignalGenerated;
            FKSCore.TradeExecuted += OnTradeExecuted;
            FKSCore.MarketRegimeChanged += OnMarketRegimeChanged;
        }
        
        private void UnsubscribeFromEvents()
        {
            FKSCore.SignalGenerated -= OnSignalGenerated;
            FKSCore.TradeExecuted -= OnTradeExecuted;
            FKSCore.MarketRegimeChanged -= OnMarketRegimeChanged;
        }
        
        private void OnSignalGenerated(object sender, FKSCore.SignalEventArgs e)
        {
            if (!LogSignals) return;
            
            var logEntry = new LogEntry
            {
                Type = "SIGNAL",
                Timestamp = DateTime.Now,
                Data = new
                {
                    SignalType = e.Signal.Type,
                    Quality = e.Signal.Quality,
                    WaveRatio = e.Signal.WaveRatio,
                    Setup = e.Signal.SetupNumber,
                    Contracts = e.Signal.RecommendedContracts,
                    Market = Instrument.FullName,
                    Price = Close[0]
                }
            };
            
            QueueLogEntry(logEntry);
        }
        
        private void OnTradeExecuted(object sender, FKSCore.TradeEventArgs e)
        {
            if (!LogTrades) return;
            
            var logEntry = new LogEntry
            {
                Type = "TRADE",
                Timestamp = DateTime.Now,
                Data = new
                {
                    EntryTime = e.Trade.EntryTime,
                    ExitTime = e.Trade.ExitTime,
                    EntryPrice = e.Trade.EntryPrice,
                    ExitPrice = e.Trade.ExitPrice,
                    Contracts = e.Trade.Contracts,
                    PnL = e.Trade.PnL,
                    Setup = e.Trade.Setup,
                    SignalQuality = e.Trade.SignalQuality,
                    Market = Instrument.FullName
                }
            };
            
            QueueLogEntry(logEntry);
        }
        
        private void OnMarketRegimeChanged(object sender, FKSCore.MarketEventArgs e)
        {
            var logEntry = new LogEntry
            {
                Type = "REGIME_CHANGE",
                Timestamp = DateTime.Now,
                Data = new
                {
                    PreviousRegime = e.PreviousRegime,
                    NewRegime = e.NewRegime,
                    Market = Instrument.FullName
                }
            };
            
            QueueLogEntry(logEntry);
        }
        #endregion
        
        #region Logging Methods
        public void LogTradeData(object data)
        {
            if (!Enabled || !LogTrades) return;
            
            var logEntry = new LogEntry
            {
                Type = "TRADE_DATA",
                Timestamp = DateTime.Now,
                Data = data
            };
            
            QueueLogEntry(logEntry);
        }
        
        public void LogSignalData(object data)
        {
            if (!Enabled || !LogSignals) return;
            
            var logEntry = new LogEntry
            {
                Type = "SIGNAL_DATA",
                Timestamp = DateTime.Now,
                Data = data
            };
            
            QueueLogEntry(logEntry);
        }
        
        public void LogPerformanceData(object data)
        {
            if (!Enabled || !LogPerformance) return;
            
            var logEntry = new LogEntry
            {
                Type = "PERFORMANCE",
                Timestamp = DateTime.Now,
                Data = data
            };
            
            QueueLogEntry(logEntry);
        }
        
        private void LogMarketData()
        {
            var marketData = new
            {
                Timestamp = DateTime.Now,
                Market = Instrument.FullName,
                Price = Close[0],
                Volume = Volume[0],
                ATR = ATR(14)[0],
                MarketState = FKSCore.CurrentMarketState,
                TradingState = FKSCore.CurrentTradingState,
                Performance = FKSCore.Performance
            };
            
            LogPerformanceData(marketData);
        }
        
        private void QueueLogEntry(LogEntry entry)
        {
            // Prevent queue overflow
            if (logQueue.Count >= maxQueueSize)
            {
                LogEntry discard;
                logQueue.TryDequeue(out discard);
                messagesFailed++;
            }
            
            logQueue.Enqueue(entry);
            
            // Process immediately if not in batch mode
            if (!BatchMode)
            {
                ProcessQueue(null);
            }
        }
        #endregion
        
        #region Queue Processing
        private async void ProcessQueue(object state)
        {
            if (isProcessing || !isConnected || logQueue.IsEmpty) return;
            
            isProcessing = true;
            var batch = new List<LogEntry>();
            
            try
            {
                // Dequeue batch
                int count = 0;
                while (count < batchSize && logQueue.TryDequeue(out LogEntry entry))
                {
                    batch.Add(entry);
                    count++;
                }
                
                if (batch.Count > 0)
                {
                    // Send batch to Python API
                    var payload = new
                    {
                        entries = batch,
                        metadata = new
                        {
                            source = "NinjaTrader",
                            version = Version,
                            account = Account.Name,
                            sessionId = startTime.Ticks
                        }
                    };
                    
                    var json = JsonConvert.SerializeObject(payload);
                    var content = new StringContent(json, Encoding.UTF8, "application/json");
                    
                    var response = await httpClient.PostAsync($"{apiEndpoint}/logs", content);
                    
                    if (response.IsSuccessStatusCode)
                    {
                        messagesSent += batch.Count;
                        
                        if (DebugMode)
                        {
                            Log($"Sent {batch.Count} log entries to Python API", LogLevel.Information);
                        }
                    }
                    else
                    {
                        messagesFailed += batch.Count;
                        
                        // Re-queue failed messages if desired
                        if (response.StatusCode != HttpStatusCode.BadRequest)
                        {
                            foreach (var entry in batch)
                            {
                                logQueue.Enqueue(entry);
                            }
                        }
                        
                        if (DebugMode)
                        {
                            Log($"Failed to send logs: {response.StatusCode}", LogLevel.Warning);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                messagesFailed += batch.Count;
                
                if (DebugMode)
                {
                    Log($"Error processing queue: {ex.Message}", LogLevel.Error);
                }
            }
            finally
            {
                isProcessing = false;
            }
        }
        #endregion
        
        #region Display
        private void UpdateConnectionDisplay()
        {
            if (!ShowConnectionStatus) return;
            
            string status = isConnected ? "Connected" : "Disconnected";
            Brush statusColor = isConnected ? Brushes.LimeGreen : Brushes.Red;
            
            string stats = $"Sent: {messagesSent} | Failed: {messagesFailed} | Queue: {logQueue.Count}";
            
            Draw.TextFixed(this, "PythonStatus", 
                $"Python API: {status}\n{stats}", 
                TextPosition.BottomLeft, 
                statusColor, 
                new SimpleFont("Arial", 10), 
                Brushes.Black, 
                Brushes.Black, 
                50);
        }
        #endregion
        
        #region Cleanup
        public void Shutdown()
        {
            try
            {
                // Stop timer
                processTimer?.Dispose();
                
                // Process remaining queue
                while (!logQueue.IsEmpty)
                {
                    ProcessQueue(null).Wait(1000);
                }
                
                // Cleanup
                httpClient?.Dispose();
                UnsubscribeFromEvents();
                FKSCore.UnregisterComponent(ComponentId);
                
                Log($"Python Bridge shutdown - Sent: {messagesSent}, Failed: {messagesFailed}", LogLevel.Information);
            }
            catch (Exception ex)
            {
                Log($"Error during shutdown: {ex.Message}", LogLevel.Error);
            }
        }
        #endregion
        
        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Enabled", Order = 1, GroupName = "Connection")]
        public bool Enabled { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "API Endpoint", Order = 2, GroupName = "Connection")]
        public string APIEndpoint
        {
            get { return apiEndpoint; }
            set { apiEndpoint = value; }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "API Key", Order = 3, GroupName = "Connection")]
        public string APIKey
        {
            get { return apiKey; }
            set { apiKey = value; }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Connection Status", Order = 10, GroupName = "Display")]
        public bool ShowConnectionStatus { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Log Trades", Order = 20, GroupName = "Logging")]
        public bool LogTrades { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Log Signals", Order = 21, GroupName = "Logging")]
        public bool LogSignals { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Log Performance", Order = 22, GroupName = "Logging")]
        public bool LogPerformance { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Batch Mode", Order = 30, GroupName = "Performance")]
        public bool BatchMode { get; set; }
        
        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Batch Size", Order = 31, GroupName = "Performance")]
        public int BatchSize
        {
            get { return batchSize; }
            set { batchSize = Math.Max(1, Math.Min(100, value)); }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "Debug Mode", Order = 40, GroupName = "Debug")]
        public bool DebugMode { get; set; }
        
        // Public properties for status
        public bool IsConnected => isConnected;
        public int QueueSize => logQueue.Count;
        public int MessagesSent => messagesSent;
        public int MessagesFailed => messagesFailed;
        #endregion
        
        #region IFKSComponent Implementation
        public void Initialize()
        {
            Log("FKS_PythonBridge initialized", LogLevel.Information);
        }
        
        void FKSCore.IFKSComponent.Shutdown()
        {
            Shutdown();
        }
        #endregion
        
        #region Helper Classes
        private class LogEntry
        {
            public string Type { get; set; }
            public DateTime Timestamp { get; set; }
            public object Data { get; set; }
        }
        #endregion
    }
}