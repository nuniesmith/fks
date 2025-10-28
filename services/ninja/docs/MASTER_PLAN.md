# FKS Trading Systems Master Refactoring Plan

## 🎯 **EXECUTIVE SUMMARY**

This plan outlines the complete refactoring of the FKS Trading Systems to create a production-ready, minimal-parameter trading solution focused initially on Gold Futures (GC) with expansion capabilities for ES, NQ, BTC, and CL.

---

## 📋 **PHASE 1: CORE INFRASTRUCTURE UPDATES**

### **1.1 Update FKS_Core.cs (AddOns)**

```csharp
// Key additions needed:
- Enhanced component registry with health monitoring
- Centralized configuration management
- Market-aware parameter adjustment system
- Performance metrics tracking
- Multi-account support foundation
```

**Tasks:**
- [ ] Add `MarketProfile` class to track market conditions
- [ ] Implement `ParameterOptimizer` for dynamic adjustments
- [ ] Create `AccountManager` for multi-account support
- [ ] Add `PerformanceTracker` for real-time metrics

### **1.2 Update FKS_Market.cs (AddOns)**

```csharp
// Market-specific configurations:
public static class MarketConfigurations
{
    public static Dictionary<string, MarketConfig> Configs = new Dictionary<string, MarketConfig>
    {
        ["GC"] = new MarketConfig 
        { 
            TickSize = 0.10, 
            TickValue = 10, 
            DefaultATRMultiplier = 2.0,
            SignalQualityThreshold = 0.65,
            OptimalSessionStart = 8,
            OptimalSessionEnd = 12
        },
        ["ES"] = new MarketConfig { /* ... */ },
        ["NQ"] = new MarketConfig { /* ... */ },
        ["CL"] = new MarketConfig { /* ... */ },
        ["BTC"] = new MarketConfig { /* ... */ }
    };
}
```

### **1.3 Update FKS_Signals.cs (AddOns)**

```csharp
// Unified signal structure:
public class UnifiedSignal
{
    public SignalType Type { get; set; } // G, Top, ^, v
    public double Quality { get; set; } // 0-1
    public double WaveRatio { get; set; }
    public bool AOConfirmation { get; set; }
    public int SetupNumber { get; set; } // 1-4
    public int RecommendedContracts { get; set; }
}
```

---

## 📊 **PHASE 2: INDICATOR CONSOLIDATION**

### **2.1 Update FKS_AI.cs**

**Key Changes:**
- Remove all user-adjustable parameters except critical ones
- Implement market-based parameter selection
- Add signal quality calculation matching PineScript logic
- Ensure proper "G" and "Top" signal generation

**Baseline Parameters:**
```csharp
// Gold defaults (hardcoded baselines)
private const int SUPPORT_RESISTANCE_LENGTH = 150;
private const double SIGNAL_QUALITY_THRESHOLD = 0.65;
private const int MAX_LENGTH = 20;
private const int LOOKBACK_PERIOD = 200;
private const double MIN_WAVE_RATIO = 1.5;
```

### **2.2 Update FKS_AO.cs**

**Simplification:**
```csharp
// Fixed parameters matching PineScript
private const int FAST_PERIOD = 5;
private const int SLOW_PERIOD = 34;
private const int SIGNAL_PERIOD = 7;

// Remove all customization - these are proven values
```

### **2.3 Enhance FKS_Dashboard.cs**

**Dashboard Requirements:**
```csharp
public class DashboardData
{
    // Strategy Performance
    public double DailyPnL { get; set; }
    public double DailyPnLPercent { get; set; }
    public int Tradestoday { get; set; }
    public double WinRate { get; set; }
    
    // Component Status
    public Dictionary<string, ComponentHealth> Components { get; set; }
    
    // Market Analysis
    public string MarketRegime { get; set; }
    public string TrendDirection { get; set; }
    public double SignalQuality { get; set; }
    public double CurrentWaveRatio { get; set; }
    
    // Risk Status
    public double AccountBalance { get; set; }
    public bool SoftLimitReached { get; set; }
    public bool HardLimitReached { get; set; }
    public int ContractsInUse { get; set; }
    
    // Python Bridge Status
    public bool PythonConnected { get; set; }
    public DateTime LastPythonUpdate { get; set; }
}
```

---

## 🎮 **PHASE 3: STRATEGY CONSOLIDATION**

### **3.1 Create Unified FKS_Strategy.cs**

**Structure:**
```csharp
namespace NinjaTrader.NinjaScript.Strategies
{
    public class FKS_Strategy : Strategy
    {
        #region Variables
        // Minimal user parameters
        private string assetType = "Gold";
        private int baseContracts = 1;
        private int maxContracts = 5;
        private double dailyLossLimitPercent = 2.0;
        private double dailyProfitTargetPercent = 1.5;
        private bool useTimeFilter = true;
        
        // Internal components
        private FKS_AI fksAI;
        private FKS_AO fksAO;
        private FKS_Dashboard fksInfo;
        private FKS_PythonBridge pythonBridge;
        
        // Setup detectors
        private Setup1_EMA9_VWAP_Bull setup1;
        private Setup2_EMA9_VWAP_Bear setup2;
        private Setup3_VWAP_Bounce setup3;
        private Setup4_SR_AO_Cross setup4;
        #endregion
        
        #region Setup Detection Methods
        private bool DetectSetup1()
        {
            // EMA9 + VWAP Bullish Breakout
            return close > EMA9 && EMA9 > VWAP &&
                   fksAI.SignalType == "G" &&
                   fksAO.IsBullish &&
                   Volume > avgVolume * 1.2 &&
                   fksAI.SignalQuality >= 0.65;
        }
        
        // Similar for other setups...
        #endregion
        
        #region Position Sizing Matrix
        private int CalculateContracts(UnifiedSignal signal)
        {
            // Based on signal quality and market regime
            if (signal.Quality >= 0.85 && signal.WaveRatio > 2.0)
                return Math.Min(5, maxContracts);
            else if (signal.Quality >= 0.70 && signal.WaveRatio > 1.5)
                return 3;
            else if (signal.Quality >= 0.60)
                return baseContracts;
            else
                return 0; // No trade
        }
        #endregion
    }
}
```

### **3.2 Remove Strategy Parameters**

**Instead of parameters, use:**
- Market-based adjustments
- Volatility-responsive sizing
- Time-of-day optimization
- Signal quality thresholds

---

## 📁 **PHASE 4: FILE-BY-FILE IMPLEMENTATION**

### **File Update Order:**

#### **Week 1: Foundation**
1. **FKS_Core.cs**
   - [ ] Add MarketProfile class
   - [ ] Implement configuration manager
   - [ ] Create performance tracker
   
2. **FKS_Market.cs**
   - [ ] Add all market configurations
   - [ ] Implement market detection logic
   - [ ] Create session management

3. **FKS_Infrastructure.cs**
   - [ ] Update component registry
   - [ ] Add health monitoring
   - [ ] Implement event system

#### **Week 2: Indicators**
4. **FKS_AI.cs**
   - [ ] Port PineScript logic exactly
   - [ ] Remove unnecessary parameters
   - [ ] Add market-based adjustments
   
5. **FKS_AO.cs**
   - [ ] Simplify to match PineScript
   - [ ] Add signal quality contribution
   - [ ] Remove all parameters

6. **FKS_Dashboard.cs**
   - [ ] Redesign dashboard layout
   - [ ] Add all performance metrics
   - [ ] Implement component status display

#### **Week 3: Strategy**
7. **FKS_Strategy.cs** (New consolidated file)
   - [ ] Implement all 4 setups
   - [ ] Add position sizing matrix
   - [ ] Implement risk management
   - [ ] Add multi-account support hooks

8. **Delete old strategies**
   - [ ] Remove FKS_Strategy_Enhanced.cs
   - [ ] Remove FKS_Strategy_Original.cs

#### **Week 4: Integration**
9. **FKS_PythonBridge.cs**
   - [ ] Add performance logging
   - [ ] Implement model feedback loop
   - [ ] Add real-time updates

10. **FKS_Calculations.cs**
    - [ ] Optimize calculation methods
    - [ ] Add caching for performance
    - [ ] Implement parallel processing where applicable

---

## 🚀 **PHASE 6: OPTIMIZATION TARGETS**

### **Performance Goals:**
- **Win Rate**: 60-65%
- **Sharpe Ratio**: >1.5
- **Max Drawdown**: <5%
- **Daily Profit Target**: 1.5% ($2,250 on $150k)
- **Daily Loss Limit**: 2% ($3,000 on $150k)

### **Key Optimizations:**
1. **Signal Quality Thresholds**
   - Raise minimum to 0.65
   - Require 2/3 component agreement
   - Add wave ratio confirmation

2. **Position Sizing**
   - Start with 1 contract baseline
   - Scale up only on high-quality signals
   - Reduce in volatile markets

3. **Time Filtering**
   - Focus on 8 AM - 12 PM EST for Gold
   - Avoid news events automatically
   - Close all positions by 3 PM

4. **Risk Management**
   - Implement trailing stops after 1:1 R:R
   - Use volatility-based stop distances
   - Add time-based exits

---

## 📊 **PHASE 7: TESTING AND VALIDATION**

### **Testing Schedule:**

**Week 5: Unit Testing**
- [ ] Test each indicator independently
- [ ] Verify signal generation matches PineScript
- [ ] Validate calculations against TradingView

**Week 6: Integration Testing**
- [ ] Test full strategy on historical data
- [ ] Compare results to original strategies
- [ ] Validate risk management systems

**Week 7: Paper Trading**
- [ ] Run on sim account for 1 week
- [ ] Monitor all 4 setups
- [ ] Verify Python bridge logging

**Week 8: Production Deployment**
- [ ] Deploy to single account
- [ ] Monitor closely for 1 week
- [ ] Scale to multiple accounts

---

## 🔄 **CONTINUOUS IMPROVEMENT**

### **Python Integration Roadmap:**
1. **Phase 1**: Logging and monitoring
2. **Phase 2**: Real-time parameter optimization
3. **Phase 3**: ML model integration
4. **Phase 4**: Full Python takeover with Rithmic

### **Future Enhancements:**
- [ ] Add more sophisticated entry timing
- [ ] Implement correlation-based position sizing
- [ ] Add options strategies for hedging
- [ ] Create web-based monitoring dashboard

---

## 📝 **IMPLEMENTATION CHECKLIST**

### **Immediate Actions (This Week):**
1. [ ] Backup current working system
2. [ ] Create new branch for refactoring
3. [ ] Start with FKS_Core.cs updates
4. [ ] Document all hardcoded values

### **Critical Success Factors:**
- ✅ No breaking changes to working logic
- ✅ Maintain or improve current performance
- ✅ Reduce parameter complexity by 80%
- ✅ Enable easy multi-asset expansion
- ✅ Prepare for Python integration

### **Risk Mitigation:**
- Keep old files until new system proven
- Test each component independently
- Run parallel systems during transition
- Monitor performance metrics closely

---

## 🎯 **EXPECTED OUTCOMES**

By completing this refactoring:
1. **Simplified Operation**: One-click deployment with no parameter tuning
2. **Improved Performance**: Target 1.5+ Sharpe ratio
3. **Scalability**: Easy to run on 5+ accounts
4. **Maintainability**: Clean, modular code structure
5. **Future-Ready**: Prepared for full Python migration

Remember: The goal is production-ready code that "just works" without constant adjustment!
