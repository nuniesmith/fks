// Global using directives for FKS Trading Systems
// These usings are available in all files in the project

global using System;
global using System.Collections.Generic;
global using System.ComponentModel;
global using System.ComponentModel.DataAnnotations;
global using System.Linq;
global using System.Text;
global using System.Threading.Tasks;
global using System.Windows;
global using System.Windows.Input;
global using System.Windows.Media;
global using System.Xml.Serialization;

// NinjaTrader namespaces
global using NinjaTrader.Cbi;
global using NinjaTrader.Gui;
global using NinjaTrader.Gui.Chart;
global using NinjaTrader.Gui.SuperDom;
global using NinjaTrader.Gui.Tools;
global using NinjaTrader.Data;
global using NinjaTrader.NinjaScript;
global using NinjaTrader.Core.FloatingPoint;
global using NinjaTrader.NinjaScript.DrawingTools;

// Type aliases for convenience
global using Color = System.Windows.Media.Color;
global using Brush = System.Windows.Media.Brush;
global using SolidColorBrush = System.Windows.Media.SolidColorBrush;

// FKS namespace aliases
global using FKSCore = NinjaTrader.NinjaScript.AddOns.FKS.FKS_Core;
global using FKSMarket = NinjaTrader.NinjaScript.AddOns.FKS.FKS_Market;
global using FKSSignals = NinjaTrader.NinjaScript.AddOns.FKS.FKS_Signals;

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