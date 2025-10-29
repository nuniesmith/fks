using System;
using System.Linq;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.AddOns.FKS
{
    /// <summary>
    /// Shared calculation utilities
    /// </summary>
    public static class FKS_Calculations
    {
        public static double CalculateATRMultiplier(string market, double baseMultiplier)
        {
            switch (market)
            {
                case "Gold": return baseMultiplier;
                case "ES": return baseMultiplier * 1.2;
                case "NQ": return baseMultiplier * 1.3;
                case "CL": return baseMultiplier * 0.9;
                case "BTC": return baseMultiplier * 1.5;
                default: return baseMultiplier;
            }
        }
        
        public static int CalculateOptimalContracts(double accountSize, double riskPercent, double stopDistance, double tickValue)
        {
            double riskAmount = accountSize * (riskPercent / 100);
            double contractRisk = stopDistance * tickValue;
            return Math.Max(1, (int)(riskAmount / contractRisk));
        }
        
        public static double NormalizePrice(double price, double tickSize)
        {
            return Math.Round(price / tickSize) * tickSize;
        }
        
        public static double CalculateRiskAmount(double accountSize, double riskPercent)
        {
            return accountSize * (riskPercent / 100);
        }
        
        public static double CalculateStopDistance(double entryPrice, double stopPrice)
        {
            return Math.Abs(entryPrice - stopPrice);
        }
        
        public static double CalculatePositionSize(double accountSize, double riskPercent, double stopDistance, double pointValue)
        {
            double riskAmount = CalculateRiskAmount(accountSize, riskPercent);
            double contractRisk = stopDistance * pointValue;
            return contractRisk > 0 ? riskAmount / contractRisk : 0;
        }
        
        public static bool IsWithinTradingHours(DateTime currentTime, int startHour, int endHour)
        {
            int currentHour = currentTime.Hour;
            return currentHour >= startHour && currentHour <= endHour;
        }
        
        public static double CalculateWaveRatio(double[] highs, double[] lows, int period)
        {
            if (highs.Length < period || lows.Length < period) return 1.0;
            
            double upWaves = 0;
            double downWaves = 0;
            
            for (int i = 1; i < period; i++)
            {
                if (highs[i] > highs[i-1]) upWaves++;
                if (lows[i] < lows[i-1]) downWaves++;
            }
            
            return downWaves > 0 ? upWaves / downWaves : upWaves > 0 ? 2.0 : 1.0;
        }
        
        public static string GetMarketRegime(double price, double ema9, double sma20, double atr, double volume, double avgVolume)
        {
            bool trending = Math.Abs(ema9 - sma20) > atr * 0.5;
            bool bullish = price > ema9 && ema9 > sma20;
            bool bearish = price < ema9 && ema9 < sma20;
            bool highVolume = volume > avgVolume * 1.2;
            
            if (trending && bullish && highVolume) return "TRENDING_BULL";
            if (trending && bearish && highVolume) return "TRENDING_BEAR";
            if (trending && bullish) return "WEAK_BULL";
            if (trending && bearish) return "WEAK_BEAR";
            
            return "RANGING";
        }
    }
}