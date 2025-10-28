// src/GlobalUsings.cs - Common using directives for NinjaTrader 8 (.NET Framework 4.8 / C# 7.3)
// Note: global using is NOT available in C# 7.3, so we provide common utilities instead

using System;
using System.Collections.Generic;
using System.Linq;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.AddOns;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;

namespace NinjaTrader.NinjaScript
{
    /// <summary>
    /// Extension methods and utilities for FKS trading system
    /// Compatible with .NET Framework 4.8 / C# 7.3
    /// </summary>
    public static class FKSExtensions
    {
        #region MarketPosition Extensions
        
        /// <summary>
        /// Convert NinjaTrader MarketPosition to FKS SignalDirection
        /// </summary>
        public static AddOns.SignalDirection ToFKSSignalDirection(this MarketPosition position)
        {
            switch (position)
            {
                case MarketPosition.Long:
                    return AddOns.SignalDirection.Long;
                case MarketPosition.Short:
                    return AddOns.SignalDirection.Short;
                default:
                    return AddOns.SignalDirection.Neutral;
            }
        }

        /// <summary>
        /// Convert FKS SignalDirection to NinjaTrader MarketPosition
        /// </summary>
        public static MarketPosition ToMarketPosition(this AddOns.SignalDirection direction)
        {
            switch (direction)
            {
                case AddOns.SignalDirection.Long:
                case AddOns.SignalDirection.StrongLong:
                    return MarketPosition.Long;
                case AddOns.SignalDirection.Short:
                case AddOns.SignalDirection.StrongShort:
                    return MarketPosition.Short;
                default:
                    return MarketPosition.Flat;
            }
        }

        #endregion

        #region OrderAction Extensions

        /// <summary>
        /// Convert FKS SignalDirection to NinjaTrader OrderAction
        /// </summary>
        public static OrderAction ToOrderAction(this AddOns.SignalDirection direction)
        {
            switch (direction)
            {
                case AddOns.SignalDirection.Long:
                case AddOns.SignalDirection.StrongLong:
                    return OrderAction.Buy;
                case AddOns.SignalDirection.Short:
                case AddOns.SignalDirection.StrongShort:
                    return OrderAction.Sell;
                default:
                    return OrderAction.Buy; // Default fallback
            }
        }

        #endregion

        #region Signal Strength Utilities

        /// <summary>
        /// Check if signal is strong (Strong Long or Strong Short)
        /// </summary>
        public static bool IsStrongSignal(this AddOns.SignalDirection direction)
        {
            return direction == AddOns.SignalDirection.StrongLong || direction == AddOns.SignalDirection.StrongShort;
        }

        /// <summary>
        /// Get signal strength as double (-2 to +2)
        /// </summary>
        public static double GetSignalStrength(this AddOns.SignalDirection direction)
        {
            return (double)direction;
        }

        /// <summary>
        /// Invert signal direction (Long becomes Short, etc.)
        /// </summary>
        public static AddOns.SignalDirection Invert(this AddOns.SignalDirection direction)
        {
            switch (direction)
            {
                case AddOns.SignalDirection.Long:
                    return AddOns.SignalDirection.Short;
                case AddOns.SignalDirection.Short:
                    return AddOns.SignalDirection.Long;
                case AddOns.SignalDirection.StrongLong:
                    return AddOns.SignalDirection.StrongShort;
                case AddOns.SignalDirection.StrongShort:
                    return AddOns.SignalDirection.StrongLong;
                default:
                    return AddOns.SignalDirection.Neutral;
            }
        }

        #endregion

        #region Price/Time Utilities

        /// <summary>
        /// Convert price to pips (assuming 4-decimal forex pair)
        /// </summary>
        public static double ToPips(this double price, double referencePrice)
        {
            return Math.Abs(price - referencePrice) * 10000.0;
        }

        /// <summary>
        /// Check if time is within trading session
        /// </summary>
        public static bool IsInTradingSession(this DateTime time, TimeSpan sessionStart, TimeSpan sessionEnd)
        {
            var timeOfDay = time.TimeOfDay;
            
            if (sessionStart <= sessionEnd)
            {
                return timeOfDay >= sessionStart && timeOfDay <= sessionEnd;
            }
            else
            {
                // Session crosses midnight
                return timeOfDay >= sessionStart || timeOfDay <= sessionEnd;
            }
        }

        #endregion

        #region Math Utilities

        /// <summary>
        /// Calculate percentage change between two values
        /// </summary>
        public static double PercentageChange(this double newValue, double oldValue)
        {
            if (Math.Abs(oldValue) < double.Epsilon)
                return 0.0;
                
            return ((newValue - oldValue) / oldValue) * 100.0;
        }

        /// <summary>
        /// Normalize value to range [0, 1]
        /// </summary>
        public static double Normalize(this double value, double min, double max)
        {
            if (Math.Abs(max - min) < double.Epsilon)
                return 0.0;
                
            return (value - min) / (max - min);
        }

        /// <summary>
        /// Clamp value between min and max
        /// </summary>
        public static double Clamp(this double value, double min, double max)
        {
            return Math.Min(Math.Max(value, min), max);
        }

        /// <summary>
        /// Round to specified tick size
        /// </summary>
        public static double RoundToTickSize(this double value, double tickSize)
        {
            if (tickSize <= 0)
                return value;
                
            return Math.Round(value / tickSize) * tickSize;
        }

        #endregion
    }

    /// <summary>
    /// Common constants for FKS trading system
    /// </summary>
    public static class FKSConstants
    {
        // Time constants
        public static readonly TimeSpan MarketOpen = new TimeSpan(9, 30, 0);
        public static readonly TimeSpan MarketClose = new TimeSpan(16, 0, 0);
        
        // Default parameters
        public const int DefaultLookbackPeriod = 20;
        public const double DefaultThreshold = 0.5;
        public const int DefaultSMAPeriod = 50;
        public const int DefaultEMAPeriod = 21;
        
        // Risk management
        public const double DefaultRiskPerTrade = 0.02; // 2%
        public const double DefaultStopLossMultiplier = 2.0;
        public const double DefaultTakeProfitMultiplier = 3.0;
        
        // Performance thresholds
        public const double MinimumWinRate = 0.40; // 40%
        public const double MaximumDrawdown = 0.10; // 10%
    }
}