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
    /// Market-specific analysis and configuration management
    /// Provides market regime detection, session management, and dynamic parameter adjustment
    /// </summary>
    public static class FKS_Market
    {
        #region Market Sessions
        private static readonly Dictionary<string, MarketSession[]> marketSessions = new Dictionary<string, MarketSession[]>
        {
            ["Gold"] = new[]
            {
                new MarketSession { Name = "Asian", Start = 18, End = 2, IsOptimal = false },
                new MarketSession { Name = "London", Start = 3, End = 7, IsOptimal = false },
                new MarketSession { Name = "US Morning", Start = 8, End = 12, IsOptimal = true },
                new MarketSession { Name = "US Afternoon", Start = 12, End = 16, IsOptimal = false }
            },
            ["ES"] = new[]
            {
                new MarketSession { Name = "Pre-Market", Start = 4, End = 9, IsOptimal = false },
                new MarketSession { Name = "RTH Morning", Start = 9, End = 12, IsOptimal = true },
                new MarketSession { Name = "RTH Afternoon", Start = 12, End = 15, IsOptimal = true },
                new MarketSession { Name = "Post-Market", Start = 15, End = 18, IsOptimal = false }
            },
            ["NQ"] = new[]
            {
                new MarketSession { Name = "Pre-Market", Start = 4, End = 9, IsOptimal = false },
                new MarketSession { Name = "RTH Morning", Start = 9, End = 12, IsOptimal = true },
                new MarketSession { Name = "RTH Afternoon", Start = 12, End = 15, IsOptimal = true },
                new MarketSession { Name = "Post-Market", Start = 15, End = 18, IsOptimal = false }
            },
            ["CL"] = new[]
            {
                new MarketSession { Name = "Asia", Start = 18, End = 2, IsOptimal = false },
                new MarketSession { Name = "Europe", Start = 2, End = 8, IsOptimal = false },
                new MarketSession { Name = "US Morning", Start = 9, End = 14, IsOptimal = true },
                new MarketSession { Name = "US Close", Start = 14, End = 17, IsOptimal = false }
            },
            ["BTC"] = new[]
            {
                new MarketSession { Name = "24/7", Start = 0, End = 24, IsOptimal = true }
            }
        };
        #endregion
        
        #region Market Characteristics
        private static readonly Dictionary<string, MarketCharacteristics> marketCharacteristics = new Dictionary<string, MarketCharacteristics>
        {
            ["Gold"] = new MarketCharacteristics
            {
                TypicalDailyRange = 25.0, // $25 per contract
                HighVolatilityThreshold = 40.0,
                LowVolatilityThreshold = 15.0,
                TrendStrengthMultiplier = 1.0,
                NewsImpactLevel = MarketImpactLevel.High,
                CorrelatedMarkets = new[] { "DX", "SI", "EUR" }
            },
            ["ES"] = new MarketCharacteristics
            {
                TypicalDailyRange = 50.0, // 50 points
                HighVolatilityThreshold = 80.0,
                LowVolatilityThreshold = 25.0,
                TrendStrengthMultiplier = 1.2,
                NewsImpactLevel = MarketImpactLevel.VeryHigh,
                CorrelatedMarkets = new[] { "NQ", "YM", "RTY" }
            },
            ["NQ"] = new MarketCharacteristics
            {
                TypicalDailyRange = 200.0, // 200 points
                HighVolatilityThreshold = 350.0,
                LowVolatilityThreshold = 100.0,
                TrendStrengthMultiplier = 1.3,
                NewsImpactLevel = MarketImpactLevel.VeryHigh,
                CorrelatedMarkets = new[] { "ES", "YM", "RTY" }
            },
            ["CL"] = new MarketCharacteristics
            {
                TypicalDailyRange = 2.0, // $2.00
                HighVolatilityThreshold = 3.5,
                LowVolatilityThreshold = 1.0,
                TrendStrengthMultiplier = 0.9,
                NewsImpactLevel = MarketImpactLevel.VeryHigh,
                CorrelatedMarkets = new[] { "RB", "HO", "NG" }
            },
            ["BTC"] = new MarketCharacteristics
            {
                TypicalDailyRange = 2000.0, // $2000
                HighVolatilityThreshold = 5000.0,
                LowVolatilityThreshold = 1000.0,
                TrendStrengthMultiplier = 1.5,
                NewsImpactLevel = MarketImpactLevel.Medium,
                CorrelatedMarkets = new[] { "ETH", "LTC" }
            }
        };
        #endregion
        
        #region Economic Calendar Integration
        private static readonly List<EconomicEvent> upcomingEvents = new List<EconomicEvent>();
        private static DateTime lastEventUpdate = DateTime.MinValue;
        #endregion
        
        #region Public Methods
        /// <summary>
        /// Get current market session for the specified market
        /// </summary>
        public static MarketSession GetCurrentSession(string marketType, DateTime time)
        {
            if (!marketSessions.ContainsKey(marketType))
                return new MarketSession { Name = "Unknown", IsOptimal = false };
            
            var sessions = marketSessions[marketType];
            var hour = time.Hour;
            
            foreach (var session in sessions)
            {
                if (IsInSession(hour, session))
                    return session;
            }
            
            return sessions[0]; // Default to first session
        }
        
        /// <summary>
        /// Analyze market conditions and return regime
        /// </summary>
        public static MarketRegimeAnalysis AnalyzeMarketRegime(
            string marketType, 
            double currentVolatility, 
            double maSlope, 
            double volumeRatio,
            double priceRange)
        {
            var analysis = new MarketRegimeAnalysis();
            var characteristics = GetMarketCharacteristics(marketType);
            
            // Volatility Analysis
            var volPercentile = currentVolatility / characteristics.TypicalDailyRange;
            if (volPercentile > characteristics.HighVolatilityThreshold / characteristics.TypicalDailyRange)
            {
                analysis.VolatilityRegime = "VERY HIGH";
                analysis.VolatilityScore = 1.0;
            }
            else if (volPercentile < characteristics.LowVolatilityThreshold / characteristics.TypicalDailyRange)
            {
                analysis.VolatilityRegime = "VERY LOW";
                analysis.VolatilityScore = 0.2;
            }
            else
            {
                analysis.VolatilityRegime = "NORMAL";
                analysis.VolatilityScore = 0.5 + (volPercentile - 0.5) * 0.5;
            }
            
            // Trend Analysis
            var trendStrength = Math.Abs(maSlope) * characteristics.TrendStrengthMultiplier;
            if (trendStrength > 1.5)
            {
                analysis.TrendRegime = maSlope > 0 ? "STRONG BULL" : "STRONG BEAR";
                analysis.TrendScore = 1.0;
            }
            else if (trendStrength > 0.5)
            {
                analysis.TrendRegime = maSlope > 0 ? "BULL" : "BEAR";
                analysis.TrendScore = 0.7;
            }
            else
            {
                analysis.TrendRegime = "RANGING";
                analysis.TrendScore = 0.3;
            }
            
            // Volume Analysis
            if (volumeRatio > 1.5)
            {
                analysis.VolumeRegime = "HIGH";
                analysis.VolumeScore = 1.0;
            }
            else if (volumeRatio < 0.7)
            {
                analysis.VolumeRegime = "LOW";
                analysis.VolumeScore = 0.3;
            }
            else
            {
                analysis.VolumeRegime = "NORMAL";
                analysis.VolumeScore = 0.6;
            }
            
            // Overall Market Regime
            analysis.OverallRegime = DetermineOverallRegime(analysis);
            analysis.TradingRecommendation = GetTradingRecommendation(analysis);
            
            return analysis;
        }
        
        /// <summary>
        /// Get dynamic parameters based on current market conditions
        /// </summary>
        public static DynamicParameters GetDynamicParameters(string marketType, MarketRegimeAnalysis regime)
        {
            var baseConfig = FKS_Core.CurrentMarketConfig;
            var parameters = new DynamicParameters();
            
            // Adjust stop loss based on volatility
            parameters.StopLossMultiplier = baseConfig.ATRStopMultiplier;
            if (regime.VolatilityRegime == "VERY HIGH")
                parameters.StopLossMultiplier *= 1.5;
            else if (regime.VolatilityRegime == "VERY LOW")
                parameters.StopLossMultiplier *= 0.8;
            
            // Adjust position size based on regime
            parameters.PositionSizeAdjustment = 1.0;
            if (regime.OverallRegime == "VOLATILE")
                parameters.PositionSizeAdjustment = 0.5;
            else if (regime.OverallRegime == "RANGING")
                parameters.PositionSizeAdjustment = 0.7;
            else if (regime.OverallRegime.Contains("STRONG"))
                parameters.PositionSizeAdjustment = 1.2;
            
            // Adjust signal quality threshold
            parameters.SignalQualityThreshold = baseConfig.SignalQualityThreshold;
            if (regime.VolatilityRegime == "VERY HIGH")
                parameters.SignalQualityThreshold += 0.1; // Require better signals in volatile markets
            
            // Time-based adjustments
            var currentSession = GetCurrentSession(marketType, DateTime.Now);
            if (!currentSession.IsOptimal)
            {
                parameters.PositionSizeAdjustment *= 0.5;
                parameters.SignalQualityThreshold += 0.05;
            }
            
            return parameters;
        }
        
        /// <summary>
        /// Check if there are any high-impact events coming up
        /// </summary>
        public static bool HasUpcomingHighImpactEvent(string marketType, int minutesAhead = 30)
        {
            UpdateEconomicCalendar();
            
            var characteristics = GetMarketCharacteristics(marketType);
            var checkTime = DateTime.Now.AddMinutes(minutesAhead);
            
            return upcomingEvents.Any(e => 
                e.Time <= checkTime && 
                e.Time >= DateTime.Now &&
                e.Impact >= characteristics.NewsImpactLevel &&
                (e.Currency == GetMarketCurrency(marketType) || e.IsGlobal));
        }
        
        /// <summary>
        /// Get market-specific trading tips
        /// </summary>
        public static List<string> GetMarketTips(string marketType, MarketRegimeAnalysis regime)
        {
            var tips = new List<string>();
            
            // General tips based on market
            switch (marketType)
            {
                case "Gold":
                    tips.Add("Watch DXY for inverse correlation");
                    tips.Add("Be cautious around Fed announcements");
                    if (regime.VolatilityRegime == "VERY HIGH")
                        tips.Add("Consider reducing position size - high volatility detected");
                    break;
                    
                case "ES":
                case "NQ":
                    tips.Add("Best liquidity during RTH (9:30-4:00 ET)");
                    tips.Add("Watch for correlation with tech sector (NQ)");
                    if (DateTime.Now.DayOfWeek == DayOfWeek.Friday)
                        tips.Add("Friday afternoon can be choppy - consider early exits");
                    break;
                    
                case "CL":
                    tips.Add("Watch EIA inventory report (Wed 10:30 AM)");
                    tips.Add("Middle East news can cause gaps");
                    if (regime.TrendRegime.Contains("STRONG"))
                        tips.Add("Strong trends often continue in crude oil");
                    break;
                    
                case "BTC":
                    tips.Add("24/7 market - watch for weekend moves");
                    tips.Add("Asian session often sets the tone");
                    if (regime.VolatilityRegime == "VERY LOW")
                        tips.Add("Low volatility may precede big moves");
                    break;
            }
            
            // Regime-specific tips
            if (regime.OverallRegime == "RANGING")
                tips.Add("Focus on support/resistance levels");
            else if (regime.OverallRegime.Contains("TREND"))
                tips.Add("Trade with the trend - use pullbacks for entry");
            
            return tips;
        }
        #endregion
        
        #region Private Methods
        private static bool IsInSession(int hour, MarketSession session)
        {
            if (session.Start <= session.End)
                return hour >= session.Start && hour < session.End;
            else // Crosses midnight
                return hour >= session.Start || hour < session.End;
        }
        
        private static MarketCharacteristics GetMarketCharacteristics(string marketType)
        {
            return marketCharacteristics.ContainsKey(marketType) 
                ? marketCharacteristics[marketType] 
                : marketCharacteristics["Gold"]; // Default
        }
        
        private static string DetermineOverallRegime(MarketRegimeAnalysis analysis)
        {
            // High volatility overrides other factors
            if (analysis.VolatilityScore > 0.8)
                return "VOLATILE";
            
            // Strong trend with normal volatility
            if (analysis.TrendScore > 0.8 && analysis.VolumeScore > 0.5)
                return analysis.TrendRegime.Contains("BULL") ? "TRENDING BULL" : "TRENDING BEAR";
            
            // Low volatility ranging
            if (analysis.VolatilityScore < 0.3 && analysis.TrendScore < 0.4)
                return "RANGING";
            
            // Normal trending
            if (analysis.TrendScore > 0.6)
                return analysis.TrendRegime.Contains("BULL") ? "BULL TREND" : "BEAR TREND";
            
            return "NEUTRAL";
        }
        
        private static string GetTradingRecommendation(MarketRegimeAnalysis analysis)
        {
            if (analysis.OverallRegime == "VOLATILE")
                return "REDUCE SIZE - High volatility";
            
            if (analysis.OverallRegime.Contains("STRONG"))
                return "TREND FOLLOWING - Strong directional bias";
            
            if (analysis.OverallRegime == "RANGING")
                return "FADE EXTREMES - Range-bound market";
            
            if (analysis.VolumeRegime == "LOW")
                return "CAUTION - Low participation";
            
            return "NORMAL TRADING - Standard parameters";
        }
        
        private static void UpdateEconomicCalendar()
        {
            // In production, this would fetch from an API
            // For now, we'll simulate with some common events
            
            if ((DateTime.Now - lastEventUpdate).TotalHours < 1)
                return; // Only update hourly
            
            upcomingEvents.Clear();
            
            // Add simulated events based on day/time
            var now = DateTime.Now;
            
            // Wednesday EIA
            if (now.DayOfWeek == DayOfWeek.Wednesday)
            {
                upcomingEvents.Add(new EconomicEvent
                {
                    Time = now.Date.AddHours(10).AddMinutes(30),
                    Name = "EIA Crude Oil Inventories",
                    Currency = "USD",
                    Impact = MarketImpactLevel.High,
                    AffectedMarkets = new[] { "CL", "RB", "HO" }
                });
            }
            
            // First Friday NFP
            if (now.DayOfWeek == DayOfWeek.Friday && now.Day <= 7)
            {
                upcomingEvents.Add(new EconomicEvent
                {
                    Time = now.Date.AddHours(8).AddMinutes(30),
                    Name = "Non-Farm Payrolls",
                    Currency = "USD",
                    Impact = MarketImpactLevel.VeryHigh,
                    IsGlobal = true
                });
            }
            
            lastEventUpdate = DateTime.Now;
        }
        
        private static string GetMarketCurrency(string marketType)
        {
            switch (marketType)
            {
                case "Gold":
                case "ES":
                case "NQ":
                case "CL":
                    return "USD";
                case "BTC":
                    return "CRYPTO";
                default:
                    return "USD";
            }
        }
        #endregion
        
        #region Helper Classes
        public class MarketSession
        {
            public string Name { get; set; }
            public int Start { get; set; } // Hour in 24h format
            public int End { get; set; }
            public bool IsOptimal { get; set; }
        }
        
        public class MarketCharacteristics
        {
            public double TypicalDailyRange { get; set; }
            public double HighVolatilityThreshold { get; set; }
            public double LowVolatilityThreshold { get; set; }
            public double TrendStrengthMultiplier { get; set; }
            public MarketImpactLevel NewsImpactLevel { get; set; }
            public string[] CorrelatedMarkets { get; set; }
        }
        
        public class MarketRegimeAnalysis
        {
            public string OverallRegime { get; set; }
            public string TrendRegime { get; set; }
            public string VolatilityRegime { get; set; }
            public string VolumeRegime { get; set; }
            public double TrendScore { get; set; }
            public double VolatilityScore { get; set; }
            public double VolumeScore { get; set; }
            public string TradingRecommendation { get; set; }
        }
        
        public class DynamicParameters
        {
            public double StopLossMultiplier { get; set; }
            public double PositionSizeAdjustment { get; set; }
            public double SignalQualityThreshold { get; set; }
        }
        
        public class EconomicEvent
        {
            public DateTime Time { get; set; }
            public string Name { get; set; }
            public string Currency { get; set; }
            public MarketImpactLevel Impact { get; set; }
            public string[] AffectedMarkets { get; set; }
            public bool IsGlobal { get; set; }
        }
        
        public enum MarketImpactLevel
        {
            Low,
            Medium,
            High,
            VeryHigh
        }
        #endregion
    }
}