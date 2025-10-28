using System;
using System.Collections.Generic;
using System.IO;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.AddOns
{
    /// <summary>
    /// FKS Infrastructure - System utilities and helpers
    /// </summary>
    public static class FKS_Infrastructure
    {
        /// <summary>
        /// Log levels for the FKS system
        /// </summary>
        public enum LogLevel
        {
            Debug,
            Info,
            Warning,
            Error
        }
        
        /// <summary>
        /// Thread-safe logging utility
        /// </summary>
        public static class Logger
        {
            private static readonly object lockObject = new object();
            
            public static void Log(LogLevel level, string message, string component = "FKS")
            {
                lock (lockObject)
                {
                    string timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
                    string logMessage = $"[{timestamp}] [{level}] [{component}] {message}";
                    
                    // Write to NinjaTrader output window
                    NinjaTrader.Code.Output.Process(logMessage, NinjaTrader.Cbi.PrintTo.OutputTab1);
                }
            }
            
            public static void Debug(string message, string component = "FKS") => Log(LogLevel.Debug, message, component);
            public static void Info(string message, string component = "FKS") => Log(LogLevel.Info, message, component);
            public static void Warning(string message, string component = "FKS") => Log(LogLevel.Warning, message, component);
            public static void Error(string message, string component = "FKS") => Log(LogLevel.Error, message, component);
        }
        
        /// <summary>
        /// Configuration manager for FKS settings
        /// </summary>
        public static class ConfigManager
        {
            private static readonly Dictionary<string, object> settings = new Dictionary<string, object>();
            
            public static T GetSetting<T>(string key, T defaultValue = default(T))
            {
                lock (settings)
                {
                    if (settings.ContainsKey(key))
                    {
                        try
                        {
                            return (T)settings[key];
                        }
                        catch
                        {
                            return defaultValue;
                        }
                    }
                    return defaultValue;
                }
            }
            
            public static void SetSetting<T>(string key, T value)
            {
                lock (settings)
                {
                    settings[key] = value;
                }
            }
        }
        
        /// <summary>
        /// Performance monitoring utilities
        /// </summary>
        public static class PerformanceMonitor
        {
            private static readonly Dictionary<string, DateTime> timers = new Dictionary<string, DateTime>();
            
            public static void StartTimer(string name)
            {
                lock (timers)
                {
                    timers[name] = DateTime.Now;
                }
            }
            
            public static double StopTimer(string name)
            {
                lock (timers)
                {
                    if (timers.ContainsKey(name))
                    {
                        double elapsed = (DateTime.Now - timers[name]).TotalMilliseconds;
                        timers.Remove(name);
                        return elapsed;
                    }
                    return 0;
                }
            }
        }
        
        /// <summary>
        /// Memory management utilities
        /// </summary>
        public static class MemoryManager
        {
            public static void ForceGarbageCollection()
            {
                GC.Collect();
                GC.WaitForPendingFinalizers();
                GC.Collect();
            }
            
            public static long GetMemoryUsage()
            {
                return GC.GetTotalMemory(false);
            }
        }
    }
}
