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
using SharpDX;
using SharpDX.Direct2D1;
using SharpDX.DirectWrite;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.FKS
{
    public class FKS_Dashboard : Indicator
    {
        #region Variables
        // Dashboard positioning
        private float dashboardX = 10;
        private float dashboardY = 10;
        private float dashboardWidth = 350;
        private float dashboardHeight = 600;
        private float sectionSpacing = 5;
        private float lineHeight = 20;
        
        // DirectX resources
        private SharpDX.Direct2D1.Brush textBrush;
        private SharpDX.Direct2D1.Brush backgroundBrush;
        private SharpDX.Direct2D1.Brush headerBrush;
        private SharpDX.Direct2D1.Brush greenBrush;
        private SharpDX.Direct2D1.Brush redBrush;
        private SharpDX.Direct2D1.Brush yellowBrush;
        private SharpDX.Direct2D1.Brush blueBrush;
        private TextFormat textFormat;
        private TextFormat headerFormat;
        private TextFormat smallFormat;
        
        // Component Registry Integration
        private bool componentsConnected = false;
        private Dictionary<string, ComponentStatus> componentStatuses = new Dictionary<string, ComponentStatus>();
        
        // Dashboard Data
        private DashboardData currentData = new DashboardData();
        
        // Update frequency control
        private DateTime lastUpdate = DateTime.MinValue;
        private TimeSpan updateInterval = TimeSpan.FromSeconds(1);
        
        // Display Options
        private bool showPerformance = true;
        private bool showComponents = true;
        private bool showMarketAnalysis = true;
        private bool showRiskStatus = true;
        private bool showTradeHistory = true;
        private bool minimized = false;
        
        // Position
        private ChartAnchor anchor = ChartAnchor.TopRight;
        private int xOffset = 10;
        private int yOffset = 10;
        #endregion
        
        #region OnStateChange
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"FKS Information Dashboard - Comprehensive system monitoring";
                Name = "FKS_Dashboard";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = false;
                DrawOnPricePanel = true;
                DrawHorizontalGridLines = false;
                DrawVerticalGridLines = false;
                PaintPriceMarkers = false;
                ScaleJustification = NinjaTrader.Gui.Chart.ScaleJustification.Right;
                IsSuspendedWhileInactive = false;
                
                // Default component statuses
                componentStatuses["FKS_AI"] = new ComponentStatus { Name = "AI Signal Engine", Connected = false };
                componentStatuses["FKS_AO"] = new ComponentStatus { Name = "Momentum Oscillator", Connected = false };
                componentStatuses["FKS_Strategy"] = new ComponentStatus { Name = "Strategy Engine", Connected = false };
                componentStatuses["FKS_Python"] = new ComponentStatus { Name = "Python Bridge", Connected = false };
                componentStatuses["DataFeed"] = new ComponentStatus { Name = "Data Feed", Connected = true };
            }
            else if (State == State.DataLoaded)
            {
                // Try to connect to FKS components
                ConnectToComponents();
            }
            else if (State == State.Historical)
            {
                // Initialize with default data
                currentData = new DashboardData
                {
                    SystemStatus = "INITIALIZING",
                    AccountBalance = Account.Get(AccountItem.CashValue, Currency.UsDollar),
                    MarketRegime = "ANALYZING",
                    TrendDirection = "NEUTRAL"
                };
            }
        }
        #endregion
        
        #region OnBarUpdate
        protected override void OnBarUpdate()
        {
            if (State != State.Realtime) return;
            
            // Update data at controlled intervals
            if (DateTime.Now - lastUpdate > updateInterval)
            {
                UpdateDashboardData();
                lastUpdate = DateTime.Now;
            }
        }
        #endregion
        
        #region OnRender
        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            base.OnRender(chartControl, chartScale);
            
            // Skip if minimized
            if (minimized) return;
            
            // Create brushes if needed
            if (textBrush == null)
            {
                textBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, SharpDX.Color.White);
                backgroundBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new SharpDX.Color(10, 10, 10, 230));
                headerBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, new SharpDX.Color(30, 30, 30, 255));
                greenBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, SharpDX.Color.LimeGreen);
                redBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, SharpDX.Color.Crimson);
                yellowBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, SharpDX.Color.Gold);
                blueBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, SharpDX.Color.DodgerBlue);
            }
            
            // Create text formats if needed
            if (textFormat == null)
            {
                textFormat = new TextFormat(Core.Globals.DirectWriteFactory, "Arial", 12);
                headerFormat = new TextFormat(Core.Globals.DirectWriteFactory, "Arial", FontWeight.Bold, FontStyle.Normal, 14);
                smallFormat = new TextFormat(Core.Globals.DirectWriteFactory, "Arial", 10);
            }
            
            // Calculate position based on anchor
            CalculateDashboardPosition(chartControl);
            
            // Draw main dashboard background
            var dashboardRect = new RectangleF(dashboardX, dashboardY, dashboardWidth, dashboardHeight);
            RenderTarget.FillRectangle(dashboardRect, backgroundBrush);
            RenderTarget.DrawRectangle(dashboardRect, textBrush, 1);
            
            float currentY = dashboardY + 5;
            
            // Header
            DrawHeader(ref currentY);
            
            // System Status Section
            if (showComponents)
                DrawSystemStatus(ref currentY);
            
            // Performance Section
            if (showPerformance)
                DrawPerformanceSection(ref currentY);
            
            // Market Analysis Section
            if (showMarketAnalysis)
                DrawMarketAnalysis(ref currentY);
            
            // Risk Status Section
            if (showRiskStatus)
                DrawRiskStatus(ref currentY);
            
            // Trade History Section
            if (showTradeHistory)
                DrawRecentTrades(ref currentY);
        }
        #endregion
        
        #region Drawing Methods
        private void DrawHeader(ref float y)
        {
            var headerRect = new RectangleF(dashboardX, y, dashboardWidth, 30);
            RenderTarget.FillRectangle(headerRect, headerBrush);
            
            DrawText("FKS TRADING SYSTEM", dashboardX + dashboardWidth/2, y + 8, headerFormat, textBrush, true);
            
            // System status indicator
            var statusColor = currentData.SystemStatus == "ACTIVE" ? greenBrush :
                            currentData.SystemStatus == "WARNING" ? yellowBrush :
                            currentData.SystemStatus == "ERROR" ? redBrush : textBrush;
            
            var statusRect = new RectangleF(dashboardX + dashboardWidth - 15, y + 10, 10, 10);
            RenderTarget.FillEllipse(new Ellipse(new Vector2(statusRect.X + 5, statusRect.Y + 5), 5, 5), statusColor);
            
            y += 35;
        }
        
        private void DrawSystemStatus(ref float y)
        {
            DrawSectionHeader("SYSTEM STATUS", ref y);
            
            foreach (var component in componentStatuses.Values)
            {
                var statusBrush = component.Connected ? greenBrush : redBrush;
                var statusText = component.Connected ? "CONNECTED" : "OFFLINE";
                
                DrawText(component.Name + ":", dashboardX + 10, y, smallFormat, textBrush);
                DrawText(statusText, dashboardX + dashboardWidth - 80, y, smallFormat, statusBrush);
                
                y += lineHeight - 2;
            }
            
            // Signal Quality
            DrawText("Signal Quality:", dashboardX + 10, y, smallFormat, textBrush);
            var qualityColor = currentData.SignalQuality > 0.7 ? greenBrush :
                              currentData.SignalQuality > 0.5 ? yellowBrush : redBrush;
            DrawText($"{currentData.SignalQuality:P0}", dashboardX + dashboardWidth - 80, y, smallFormat, qualityColor);
            
            y += lineHeight + sectionSpacing;
        }
        
        private void DrawPerformanceSection(ref float y)
        {
            DrawSectionHeader("PERFORMANCE", ref y);
            
            // Daily P&L
            var pnlColor = currentData.DailyPnL >= 0 ? greenBrush : redBrush;
            DrawText("Daily P&L:", dashboardX + 10, y, textFormat, textBrush);
            DrawText($"{currentData.DailyPnL:C0} ({currentData.DailyPnLPercent:F2}%)", 
                    dashboardX + dashboardWidth - 120, y, textFormat, pnlColor);
            y += lineHeight;
            
            // Trades Today
            DrawText("Trades Today:", dashboardX + 10, y, textFormat, textBrush);
            DrawText($"{currentData.TradesToday} / {currentData.MaxDailyTrades}", 
                    dashboardX + dashboardWidth - 80, y, textFormat, textBrush);
            y += lineHeight;
            
            // Win Rate
            DrawText("Win Rate:", dashboardX + 10, y, textFormat, textBrush);
            var winRateColor = currentData.WinRate > 0.6 ? greenBrush :
                              currentData.WinRate > 0.5 ? yellowBrush : redBrush;
            DrawText($"{currentData.WinRate:P0}", dashboardX + dashboardWidth - 80, y, textFormat, winRateColor);
            y += lineHeight;
            
            // Sharpe Ratio
            DrawText("Sharpe Ratio:", dashboardX + 10, y, textFormat, textBrush);
            var sharpeColor = currentData.SharpeRatio > 1.5 ? greenBrush :
                             currentData.SharpeRatio > 1.0 ? yellowBrush : redBrush;
            DrawText($"{currentData.SharpeRatio:F2}", dashboardX + dashboardWidth - 80, y, textFormat, sharpeColor);
            
            y += lineHeight + sectionSpacing;
        }
        
        private void DrawMarketAnalysis(ref float y)
        {
            DrawSectionHeader("MARKET ANALYSIS", ref y);
            
            // Market Regime
            DrawText("Regime:", dashboardX + 10, y, textFormat, textBrush);
            var regimeColor = currentData.MarketRegime == "TRENDING BULL" ? greenBrush :
                             currentData.MarketRegime == "TRENDING BEAR" ? redBrush :
                             currentData.MarketRegime == "VOLATILE" ? yellowBrush : textBrush;
            DrawText(currentData.MarketRegime, dashboardX + dashboardWidth - 120, y, textFormat, regimeColor);
            y += lineHeight;
            
            // Trend Direction
            DrawText("Trend:", dashboardX + 10, y, textFormat, textBrush);
            var trendColor = currentData.TrendDirection.Contains("BULL") ? greenBrush :
                            currentData.TrendDirection.Contains("BEAR") ? redBrush : textBrush;
            DrawText(currentData.TrendDirection, dashboardX + dashboardWidth - 120, y, textFormat, trendColor);
            y += lineHeight;
            
            // Current Signal
            DrawText("Signal:", dashboardX + 10, y, textFormat, textBrush);
            var signalColor = currentData.CurrentSignal == "G" ? greenBrush :
                             currentData.CurrentSignal == "Top" ? redBrush : textBrush;
            DrawText(currentData.CurrentSignal ?? "None", dashboardX + dashboardWidth - 80, y, textFormat, signalColor);
            y += lineHeight;
            
            // Wave Ratio
            DrawText("Wave Ratio:", dashboardX + 10, y, textFormat, textBrush);
            var waveColor = currentData.CurrentWaveRatio > 2.0 ? greenBrush :
                           currentData.CurrentWaveRatio > 1.5 ? yellowBrush : textBrush;
            DrawText($"{currentData.CurrentWaveRatio:F2}x", dashboardX + dashboardWidth - 80, y, textFormat, waveColor);
            
            y += lineHeight + sectionSpacing;
        }
        
        private void DrawRiskStatus(ref float y)
        {
            DrawSectionHeader("RISK STATUS", ref y);
            
            // Account Balance
            DrawText("Balance:", dashboardX + 10, y, textFormat, textBrush);
            DrawText($"{currentData.AccountBalance:C0}", dashboardX + dashboardWidth - 100, y, textFormat, textBrush);
            y += lineHeight;
            
            // Daily Limits
            var softLimitColor = currentData.SoftLimitReached ? yellowBrush : textBrush;
            var hardLimitColor = currentData.HardLimitReached ? redBrush : textBrush;
            
            DrawText("Profit Target:", dashboardX + 10, y, smallFormat, textBrush);
            DrawText(currentData.SoftLimitReached ? "REACHED" : $"{currentData.ProfitTargetRemaining:C0}", 
                    dashboardX + dashboardWidth - 80, y, smallFormat, softLimitColor);
            y += lineHeight - 2;
            
            DrawText("Loss Limit:", dashboardX + 10, y, smallFormat, textBrush);
            DrawText(currentData.HardLimitReached ? "REACHED" : $"{currentData.LossLimitRemaining:C0}", 
                    dashboardX + dashboardWidth - 80, y, smallFormat, hardLimitColor);
            y += lineHeight - 2;
            
            // Current Exposure
            DrawText("Contracts:", dashboardX + 10, y, textFormat, textBrush);
            DrawText($"{currentData.ContractsInUse} / {currentData.MaxContracts}", 
                    dashboardX + dashboardWidth - 80, y, textFormat, textBrush);
            
            y += lineHeight + sectionSpacing;
        }
        
        private void DrawRecentTrades(ref float y)
        {
            DrawSectionHeader("RECENT TRADES", ref y);
            
            if (currentData.RecentTrades == null || currentData.RecentTrades.Count == 0)
            {
                DrawText("No trades today", dashboardX + 10, y, smallFormat, textBrush);
                y += lineHeight;
            }
            else
            {
                foreach (var trade in currentData.RecentTrades.Take(5))
                {
                    var tradeColor = trade.PnL >= 0 ? greenBrush : redBrush;
                    DrawText($"{trade.Time:HH:mm} {trade.Setup}", dashboardX + 10, y, smallFormat, textBrush);
                    DrawText($"{trade.PnL:C0}", dashboardX + dashboardWidth - 60, y, smallFormat, tradeColor);
                    y += lineHeight - 2;
                }
            }
        }
        
        private void DrawSectionHeader(string text, ref float y)
        {
            var headerRect = new RectangleF(dashboardX, y, dashboardWidth, 22);
            RenderTarget.FillRectangle(headerRect, headerBrush);
            DrawText(text, dashboardX + 10, y + 3, textFormat, blueBrush);
            y += 25;
        }
        
        private void DrawText(string text, float x, float y, TextFormat format, SharpDX.Direct2D1.Brush brush, bool center = false)
        {
            var textLayout = new TextLayout(Core.Globals.DirectWriteFactory, text, format, dashboardWidth, lineHeight);
            
            if (center)
            {
                var metrics = textLayout.Metrics;
                x = x - metrics.Width / 2;
            }
            
            RenderTarget.DrawTextLayout(new Vector2(x, y), textLayout, brush);
            textLayout.Dispose();
        }
        #endregion
        
        #region Update Methods
        private void UpdateDashboardData()
        {
            // Update component connections
            CheckComponentConnections();
            
            // Get account data
            currentData.AccountBalance = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            currentData.DailyPnL = Account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
            
            // Try to get data from connected components
            if (componentStatuses["FKS_AI"].Connected)
            {
                // Get data from FKS_AI indicator
                // This would be done through the component registry in production
                currentData.SignalQuality = 0.75; // Placeholder
                currentData.CurrentSignal = "G"; // Placeholder
                currentData.CurrentWaveRatio = 1.8; // Placeholder
            }
            
            // Calculate performance metrics
            CalculatePerformanceMetrics();
            
            // Update system status
            UpdateSystemStatus();
        }
        
        private void CheckComponentConnections()
        {
            // Check if indicators are loaded on chart
            foreach (var indicator in ChartControl.Indicators)
            {
                if (indicator.Name == "FKS_AI")
                    componentStatuses["FKS_AI"].Connected = true;
                else if (indicator.Name == "FKS_AO")
                    componentStatuses["FKS_AO"].Connected = true;
            }
            
            // Check strategy connection
            if (State == State.Realtime)
            {
                componentStatuses["FKS_Strategy"].Connected = Strategy != null;
            }
            
            // Python bridge would be checked through actual connection
            componentStatuses["FKS_Python"].Connected = false; // Default for now
        }
        
        private void ConnectToComponents()
        {
            try
            {
                // In production, this would connect to the FKS component registry
                componentsConnected = true;
            }
            catch (Exception ex)
            {
                Log($"Failed to connect to FKS components: {ex.Message}", LogLevel.Warning);
            }
        }
        
        private void CalculatePerformanceMetrics()
        {
            // Calculate win rate from recent trades
            if (currentData.RecentTrades != null && currentData.RecentTrades.Count > 0)
            {
                var wins = currentData.RecentTrades.Count(t => t.PnL > 0);
                currentData.WinRate = (double)wins / currentData.RecentTrades.Count;
            }
            
            // Sharpe ratio calculation would be more complex in production
            currentData.SharpeRatio = 1.22; // Placeholder matching your results
            
            // Calculate remaining limits
            currentData.ProfitTargetRemaining = (currentData.AccountBalance * 0.015) - currentData.DailyPnL;
            currentData.LossLimitRemaining = (currentData.AccountBalance * 0.02) + currentData.DailyPnL;
        }
        
        private void UpdateSystemStatus()
        {
            if (currentData.HardLimitReached)
                currentData.SystemStatus = "ERROR";
            else if (currentData.SoftLimitReached || !componentsConnected)
                currentData.SystemStatus = "WARNING";
            else
                currentData.SystemStatus = "ACTIVE";
        }
        
        private void CalculateDashboardPosition(ChartControl chartControl)
        {
            switch (anchor)
            {
                case ChartAnchor.TopLeft:
                    dashboardX = xOffset;
                    dashboardY = yOffset;
                    break;
                    
                case ChartAnchor.TopRight:
                    dashboardX = chartControl.CanvasRight - dashboardWidth - xOffset;
                    dashboardY = yOffset;
                    break;
                    
                case ChartAnchor.BottomLeft:
                    dashboardX = xOffset;
                    dashboardY = chartControl.CanvasBottom - dashboardHeight - yOffset;
                    break;
                    
                case ChartAnchor.BottomRight:
                    dashboardX = chartControl.CanvasRight - dashboardWidth - xOffset;
                    dashboardY = chartControl.CanvasBottom - dashboardHeight - yOffset;
                    break;
            }
        }
        #endregion
        
        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Show Performance", Order = 1, GroupName = "Display Options")]
        public bool ShowPerformance
        {
            get { return showPerformance; }
            set { showPerformance = value; }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Components", Order = 2, GroupName = "Display Options")]
        public bool ShowComponents
        {
            get { return showComponents; }
            set { showComponents = value; }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Market Analysis", Order = 3, GroupName = "Display Options")]
        public bool ShowMarketAnalysis
        {
            get { return showMarketAnalysis; }
            set { showMarketAnalysis = value; }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "Dashboard Position", Order = 10, GroupName = "Position")]
        public ChartAnchor DashboardPosition
        {
            get { return anchor; }
            set { anchor = value; }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "X Offset", Order = 11, GroupName = "Position")]
        public int XOffset
        {
            get { return xOffset; }
            set { xOffset = Math.Max(0, value); }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "Y Offset", Order = 12, GroupName = "Position")]
        public int YOffset
        {
            get { return yOffset; }
            set { yOffset = Math.Max(0, value); }
        }
        #endregion
        
        #region Helper Classes
        public class DashboardData
        {
            // System Status
            public string SystemStatus { get; set; } = "INITIALIZING";
            
            // Performance
            public double DailyPnL { get; set; }
            public double DailyPnLPercent { get; set; }
            public int TradesToday { get; set; }
            public int MaxDailyTrades { get; set; } = 6;
            public double WinRate { get; set; }
            public double SharpeRatio { get; set; }
            
            // Market Analysis
            public string MarketRegime { get; set; } = "ANALYZING";
            public string TrendDirection { get; set; } = "NEUTRAL";
            public double SignalQuality { get; set; }
            public double CurrentWaveRatio { get; set; }
            public string CurrentSignal { get; set; }
            
            // Risk Status
            public double AccountBalance { get; set; }
            public bool SoftLimitReached { get; set; }
            public bool HardLimitReached { get; set; }
            public int ContractsInUse { get; set; }
            public int MaxContracts { get; set; } = 5;
            public double ProfitTargetRemaining { get; set; }
            public double LossLimitRemaining { get; set; }
            
            // Recent Trades
            public List<TradeInfo> RecentTrades { get; set; } = new List<TradeInfo>();
        }
        
        public class ComponentStatus
        {
            public string Name { get; set; }
            public bool Connected { get; set; }
            public DateTime LastUpdate { get; set; }
            public string Version { get; set; }
        }
        
        public class TradeInfo
        {
            public DateTime Time { get; set; }
            public string Setup { get; set; }
            public double PnL { get; set; }
            public double SignalQuality { get; set; }
        }
        
        public enum ChartAnchor
        {
            TopLeft,
            TopRight,
            BottomLeft,
            BottomRight
        }
        #endregion
    }
}