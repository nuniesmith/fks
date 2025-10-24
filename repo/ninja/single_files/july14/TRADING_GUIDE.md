# FKS Trading Systems - Complete Trading Guide

## 🎯 **SYSTEM OVERVIEW**

FKS is a bulletproof trading system that combines AI-enhanced signals with traditional technical analysis for futures trading. The system uses three core components that must agree before generating trades.

### **Core Components:**
- **FKS_AI**: Support/resistance detection with signal quality scoring
- **FKS_AO**: Awesome Oscillator with momentum confirmation  
- **FKS_Dashboard**: Market regime and performance dashboard

---

## 📊 **SIGNAL HIERARCHY (Trade Only These)**

### 🟢 **TIER 1 - PREMIUM SIGNALS** (4-5 contracts)
```
LONG:  "G" signal + AO cross > 0 + Quality > 85% + Wave > 2.0x
SHORT: "Top" signal + AO cross < 0 + Quality > 85% + Wave > 2.0x
```

### 🟡 **TIER 2 - STRONG SIGNALS** (2-3 contracts)  
```
LONG:  "G" or "^" + AO > signal line + Quality 70-85% + Wave 1.5-2.0x
SHORT: "Top" or "v" + AO < signal line + Quality 70-85% + Wave 1.5-2.0x
```

### ⚪ **TIER 3 - STANDARD SIGNALS** (1-2 contracts)
```
LONG:  "^" + AO bullish + Quality 60-70% + Wave > 1.5x
SHORT: "v" + AO bearish + Quality 60-70% + Wave > 1.5x
```

---

## 🎯 **THE 4 BULLETPROOF SETUPS**

### **Setup 1: EMA9 + VWAP Bullish Breakout**
**Entry Conditions (ALL must be met):**
- Price > EMA9 > VWAP (stacked alignment)
- "G" signal appears at support level
- AO crosses above zero OR shows bullish momentum
- Volume > 1.2x average
- Signal quality ≥ 65%

**Entry Trigger:** Price breaks above recent swing high with volume

### **Setup 2: EMA9 + VWAP Bearish Breakdown**
**Entry Conditions (ALL must be met):**
- Price < EMA9 < VWAP (bearish stack)
- "Top" signal appears at resistance level  
- AO crosses below zero OR shows bearish momentum
- Volume > 1.2x average
- Signal quality ≥ 65%

**Entry Trigger:** Price breaks below recent swing low with volume

### **Setup 3: VWAP Rejection Bounce**
**Entry Conditions:**
- Price approaches VWAP and bounces with "G" signal
- AO shows bullish divergence or momentum
- Strong support confluence
- High-quality rejection candle (hammer, pin bar)

### **Setup 4: Support/Resistance + AO Zero Cross**
**Entry Conditions:**
- Price at key S/R level from FKS_AI
- AO crosses zero line (bullish/bearish)
- Signal quality > 70%
- Clear breakout with volume confirmation

---

## 📈 **POSITION SIZING MATRIX**

| Signal Quality | Wave Ratio | Market Regime | GC | NQ | CL |
|---------------|------------|---------------|----|----|---- |
| **85%+** | **>2.0x** | **TRENDING** | 4-5 | 3-4 | 4-5 |
| **70-85%** | **1.5-2.0x** | **TRENDING** | 2-3 | 2 | 2-3 |
| **60-70%** | **>1.5x** | **TRENDING** | 1-2 | 1 | 1-2 |
| **Any** | **Any** | **VOLATILE** | -50% | -50% | -50% |
| **Any** | **Any** | **RANGING** | -30% | -30% | -30% |

---

## 🛑 **RISK MANAGEMENT RULES**

### **Daily Limits**
- **Maximum 6 trades per day** (stop at 6 regardless of P&L)
- **3 consecutive losses = Stop trading for the day**
- **Daily loss limit = 2% of account** (hard stop)
- **Daily profit target = 1.5% of account** (consider stopping)

### **Position Sizing Rules**
- **Base contract size**: 1 contract for Tier 3 signals
- **Scale up**: Only for Tier 1-2 signals in trending markets
- **Scale down**: -50% in volatile markets, -30% in ranging markets
- **Never risk more than 1% per trade**

### **Exit Rules**
- **Stop Loss**: 2x ATR from entry point
- **Take Profit**: 3x ATR (minimum 1:1.5 R:R)
- **Trailing Stop**: Use 1.5x ATR trail after 1:1 R:R achieved
- **Time Exit**: Close all positions 15 minutes before session close

---

## 🥇 **MARKET-SPECIFIC PARAMETERS**

### **GOLD FUTURES (GC)**
```
FKS_AI Settings:
- Asset Type: "Gold"
- Signal Quality Threshold: 0.6
- Max Length: 20
- Lookback Period: 200

Trading Specs:
- Tick Size: $0.10 = $10/contract
- Daily Range: $15-25 ($1,500-2,500)
- Best Hours: 8:00 AM - 12:00 PM EST
- Key Levels: Round numbers ($1950, $2000, etc.)
```

### **NASDAQ FUTURES (NQ)**
```
FKS_AI Settings:
- Asset Type: "Stocks"  
- Signal Quality Threshold: 0.65
- Max Length: 20
- Lookback Period: 150

Trading Specs:
- Tick Size: 0.25 = $5/contract
- Point Value: $20/point
- Daily Range: 150-250 points
- Best Hours: 9:30-10:30 AM, 3:00-4:00 PM EST
```

### **CRUDE OIL FUTURES (CL)**
```
FKS_AI Settings:
- Asset Type: "Forex"
- Signal Quality Threshold: 0.6
- Max Length: 20
- Lookback Period: 150

Trading Specs:
- Tick Size: $0.01 = $10/contract
- Daily Range: $1.50-2.50
- Best Hours: 9:00 AM - 2:30 PM EST
- Key Events: Wed 10:30 AM (EIA inventory)
```

---

## 🔧 **NINJATRADER 8 SETUP**

### **FKS_AI (Primary Panel)**
```
Support/Resistance Length: 150
Show Entry Zones: TRUE
Show Signal Labels: TRUE  
Show Market Phase: FALSE (clean chart)
Signal Quality Threshold: 0.65
```

### **FKS_AO (Lower Panel)**
```
Fast Period: 5
Slow Period: 34
Signal Period: 7
Use AO Zero Cross: TRUE
Use AO Signal Cross: TRUE
```

### **Chart Configuration**
```
Primary Timeframe: 5-minute (main trading)
Confirmation Timeframe: 15-minute (context)
Data Series: Last (not bid/ask)
Session Template: CME US Index Futures RTH
```

---

## ⚡ **QUICK START CHECKLIST**

### **Daily Preparation:**
1. [ ] Check FKS_AI signal quality threshold (≥0.65)
2. [ ] Verify AO settings are correct
3. [ ] Review daily limits and account balance
4. [ ] Check market news and key events
5. [ ] Set up charts with proper timeframes

### **Pre-Trade Verification:**
1. [ ] Signal quality ≥ 60% (minimum)
2. [ ] AO confirmation present
3. [ ] Volume above 1.2x average
4. [ ] Position size calculated correctly
5. [ ] Stop loss and take profit levels set

### **Post-Trade Review:**
1. [ ] Record signal quality and outcome
2. [ ] Update daily trade count
3. [ ] Calculate running P&L
4. [ ] Review what worked/didn't work
5. [ ] Adjust parameters if needed

---

## 📚 **STRATEGY IMPLEMENTATION STATUS**

### ✅ **Completed:**
- Refactored strategy from 4000+ lines to 800 lines
- Created modular FKS_Strategy_Clean.cs
- Unified FKS AddOns system
- Component health monitoring
- Basic signal coordination

### ⚠️ **Current Issues:**
1. **Signal Quality**: Thresholds may be too low (need 0.65+ minimum)
2. **Setup Detection**: Logic needs enhancement
3. **Risk Management**: Dynamic position sizing incomplete

### 🚀 **Next Phase Improvements:**
1. **Fix Core Thresholds**: Raise signal quality requirements
2. **Implement Proper VWAP**: Replace SMA proxy with real VWAP
3. **Enhance Component Agreement**: Require 2 of 3 components
4. **Add Time-Based Filtering**: Improve trade timing
5. **Market Condition Detection**: Better regime awareness

---

## 🎯 **PERFORMANCE TARGETS**

### **Expected Results:**
- **Win Rate**: 55-65% (quality over quantity)
- **Average R:R**: 1:1.5 minimum
- **Monthly Return**: 8-15% (conservative estimate)
- **Maximum Drawdown**: <5% (with proper risk management)
- **Trade Frequency**: 2-4 trades per day average

### **Key Metrics to Track:**
- Signal quality vs. win rate correlation
- Best performing setups by market
- Time of day performance analysis
- Market regime performance comparison
- Component agreement impact on success rate

Remember: **Quality over quantity** - It's better to take 2 high-quality signals than 5 mediocre ones.
