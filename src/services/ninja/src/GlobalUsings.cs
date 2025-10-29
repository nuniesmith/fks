// Common using directives for FKS Trading Systems
// .NET Framework 4.8 / C# 7.3 compatible (global using not supported)

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

// NinjaTrader namespaces
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.DrawingTools;

// Common extension methods for FKS
namespace NinjaTrader.NinjaScript.AddOns.FKS
{
    public static class FKSExtensions
    {
        /// <summary>
        /// Safely get value from dictionary with default
        /// </summary>
        public static TValue GetValueOrDefault<TKey, TValue>(this Dictionary<TKey, TValue> dict, TKey key, TValue defaultValue = default)
        {
            return dict.TryGetValue(key, out var value) ? value : defaultValue;
        }
        
        /// <summary>
        /// Format price according to tick size
        /// </summary>
        public static string FormatPrice(this double price, double tickSize)
        {
            var decimals = BitConverter.GetBytes(decimal.GetBits((decimal)tickSize)[3])[2];
            return price.ToString($"F{decimals}");
        }
        
        /// <summary>
        /// Check if value is within range
        /// </summary>
        public static bool IsWithin(this double value, double target, double tolerance)
        {
            return Math.Abs(value - target) <= tolerance;
        }
        
        /// <summary>
        /// Clamp value between min and max
        /// </summary>
        public static double Clamp(this double value, double min, double max)
        {
            return Math.Max(min, Math.Min(max, value));
        }
        
        /// <summary>
        /// Safe division with default for divide by zero
        /// </summary>
        public static double SafeDivide(this double numerator, double denominator, double defaultValue = 0)
        {
            return denominator == 0 ? defaultValue : numerator / denominator;
        }
    }
}