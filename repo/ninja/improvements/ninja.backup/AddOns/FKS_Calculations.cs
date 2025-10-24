using System;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.AddOns
{
    /// <summary>
    /// FKS Calculations - Mathematical and statistical functions
    /// </summary>
    public static class FKS_Calculations
    {
        /// <summary>
        /// Calculate simple moving average
        /// </summary>
        public static double SimpleMovingAverage(double[] values, int period)
        {
            if (values == null || values.Length < period)
                return 0;
                
            double sum = 0;
            for (int i = values.Length - period; i < values.Length; i++)
            {
                sum += values[i];
            }
            return sum / period;
        }
        
        /// <summary>
        /// Calculate standard deviation
        /// </summary>
        public static double StandardDeviation(double[] values, int period)
        {
            if (values == null || values.Length < period)
                return 0;
                
            double mean = SimpleMovingAverage(values, period);
            double sumSquares = 0;
            
            for (int i = values.Length - period; i < values.Length; i++)
            {
                double diff = values[i] - mean;
                sumSquares += diff * diff;
            }
            
            return Math.Sqrt(sumSquares / period);
        }
        
        /// <summary>
        /// Calculate ATR (Average True Range)
        /// </summary>
        public static double AverageTrueRange(double[] highs, double[] lows, double[] closes, int period)
        {
            if (highs == null || lows == null || closes == null || highs.Length < period + 1)
                return 0;
                
            double[] trueRanges = new double[period];
            
            for (int i = 0; i < period; i++)
            {
                int idx = highs.Length - period + i;
                double high = highs[idx];
                double low = lows[idx];
                double prevClose = idx > 0 ? closes[idx - 1] : closes[idx];
                
                double tr1 = high - low;
                double tr2 = Math.Abs(high - prevClose);
                double tr3 = Math.Abs(low - prevClose);
                
                trueRanges[i] = Math.Max(tr1, Math.Max(tr2, tr3));
            }
            
            return SimpleMovingAverage(trueRanges, period);
        }
    }
}
