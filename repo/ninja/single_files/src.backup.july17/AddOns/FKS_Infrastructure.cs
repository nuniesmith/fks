using System;
using System.Collections.Generic;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.AddOns.FKS
{
    /// <summary>
    /// Component registry and health monitoring
    /// </summary>
    public static class FKS_Infrastructure
    {
        private static readonly Dictionary<string, DateTime> heartbeats = new Dictionary<string, DateTime>();
        private static readonly object lockObj = new object();
        
        public static void Heartbeat(string componentId)
        {
            lock (lockObj)
            {
                heartbeats[componentId] = DateTime.Now;
            }
        }
        
        public static bool IsHealthy(string componentId)
        {
            lock (lockObj)
            {
                if (!heartbeats.ContainsKey(componentId))
                    return false;
                    
                return (DateTime.Now - heartbeats[componentId]).TotalSeconds < 30;
            }
        }
        
        public static Dictionary<string, bool> GetSystemHealth()
        {
            var health = new Dictionary<string, bool>();
            var components = new[] { "FKS_AI", "FKS_AO", "FKS_Strategy", "FKS_Dashboard" };
            
            foreach (var component in components)
            {
                health[component] = IsHealthy(component);
            }
            
            return health;
        }
    }
}