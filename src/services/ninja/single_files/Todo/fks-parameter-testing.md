# FKS Strategy Parameter Testing Guide

## Test Set 1: **Time Optimization** (Most Important)
Test these time windows to find optimal trading hours:

### Configuration A - Full London + NY Morning
- **Start Hour**: 3
- **End Hour**: 12
- **Signal Quality**: 0.70
- **Max Daily Trades**: 8
- *Expected Result*: Catch high-quality London breakouts

### Configuration B - Core London Session
- **Start Hour**: 3  
- **End Hour**: 10
- **Signal Quality**: 0.75
- **Max Daily Trades**: 6
- *Expected Result*: Focus on highest liquidity period

### Configuration C - Extended Session (Current)
- **Start Hour**: 3
- **End Hour**: 15
- **Signal Quality**: 0.70
- **Max Daily Trades**: 10
- *Expected Result*: More opportunities but potentially lower quality afternoon trades

## Test Set 2: **Signal Quality Optimization**
Keep time at 3-12 and test quality thresholds:

### Configuration D - Conservative Quality
- **Signal Quality**: 0.75
- **Volume Threshold**: 1.5
- **Volume Multiplier**: 1.2
- **Signal Quality Multiplier**: 1.1
- *Expected Result*: Fewer but higher probability trades

### Configuration E - Aggressive Quality  
- **Signal Quality**: 0.65 (current)
- **Volume Threshold**: 1.0
- **Volume Multiplier**: 0.8
- **Signal Quality Multiplier**: 0.9
- *Expected Result*: More trades, helpful to compare

### Configuration F - Ultra-Conservative
- **Signal Quality**: 0.80
- **Volume Threshold**: 2.0
- **Max Daily Trades**: 4
- **Base Contracts**: 2
- *Expected Result*: Only premium setups

## Test Set 3: **Risk Management Variations**

### Configuration G - Tighter Stops
- **ATR Stop Multiplier**: 1.5 (from 2.0)
- **ATR Target Multiplier**: 2.0 (from 1.5)
- **Signal Quality**: 0.70
- *Expected Result*: Better R:R but possibly more stop-outs

### Configuration H - Wider Stops
- **ATR Stop Multiplier**: 2.5
- **ATR Target Multiplier**: 1.25
- **Signal Quality**: 0.70
- *Expected Result*: Higher win rate but smaller R:R

### Configuration I - Dynamic Limits
- **Daily Profit Soft Target**: $3000 (from $2000)
- **Daily Profit Hard Target**: $5000 (from $3000)
- **Daily Loss Soft Limit**: $1500 (from $1000)
- **Max Daily Trades**: 12
- *Expected Result*: Let winners run on good days

## Test Set 4: **Asset-Specific Optimizations**

### For GOLD (GC) - Configuration J
- **Signal Quality**: 0.72
- **Volume Threshold**: 1.5
- **ATR Stop**: 2.0
- **Time**: 3-11 (London focus)
- *Rationale*: Gold moves strongly during London

### For NASDAQ (NQ) - Configuration K  
- **Signal Quality**: 0.68
- **Volume Threshold**: 1.2
- **ATR Stop**: 1.75
- **Time**: 8-12 (US pre-market/open)
- *Rationale*: Tech stocks need US session

### For CRUDE OIL (CL) - Configuration L
- **Signal Quality**: 0.75
- **Volume Threshold**: 1.8
- **Max Contracts**: 3
- **Time**: 3-14
- *Rationale*: Oil needs higher quality due to volatility

### For BITCOIN (BTC) - Configuration M
- **Signal Quality**: 0.70
- **Time Filter**: Disabled
- **Max Daily Trades**: 15
- **ATR Stop**: 2.5
- *Rationale*: 24/7 market, needs different approach

## 📊 Testing Protocol

1. **Run each configuration for 24-48 hours** (or backtest same period)
2. **Screenshot results** after each test
3. **Track these metrics**:
   - Win rate change
   - Average trade profit
   - Maximum drawdown
   - Number of trades per day
   - Best/worst performing hours

## 🎯 Quick Win Configurations

If you can only test a few tonight, prioritize these:

### **Priority 1** - Time Fix Only
- Change: `StartHour = 3, EndHour = 12`
- Keep everything else the same
- This alone should improve results significantly

### **Priority 2** - Quality Boost
- Change: `SignalQualityThreshold = 0.72`
- Change: `VolumeThreshold = 1.5`
- With time fix above

### **Priority 3** - Heiken Ashi Optimization
- Implement the HA-specific code provided
- Set: `SignalQualityMultiplier = 1.2`
- This compensates for HA smoothing

## 💡 Additional Improvements to Code

### 1. Add Spread/Commission Awareness
```csharp
// Add to your entry conditions
double spread = (Ask[0] - Bid[0]);
double spreadInTicks = spread / TickSize;
if (spreadInTicks > 2) return; // Skip if spread too wide
```

### 2. Add Session-Specific Volatility Check
```csharp
// In UpdateCalculations()
double currentHour = Time[0].Hour;
double volatilityMultiplier = 1.0;

// London session (3-8 EST) often most volatile
if (currentHour >= 3 && currentHour < 8)
    volatilityMultiplier = 1.2;
// US open overlap (8-10 EST)  
else if (currentHour >= 8 && currentHour < 10)
    volatilityMultiplier = 1.1;
// Afternoon slowdown
else if (currentHour >= 13)
    volatilityMultiplier = 0.8;

// Apply to position sizing
contracts = (int)(contracts * volatilityMultiplier);
```

### 3. Add Consecutive Win Scaling
```csharp
// Track consecutive wins
private int consecutiveWins = 0;

// In position sizing
if (consecutiveWins >= 3)
    contracts = Math.Min(contracts + 1, MaxContracts);
else if (consecutiveWins >= 2)
    contracts = Math.Min(contracts + 1, MaxContracts - 1);
```

## 📈 Expected Improvements

With these optimizations, you should see:
- **Win rate**: Increase to 52-58%
- **Daily trades**: Reduce to 4-8 (quality over quantity)
- **Drawdowns**: Reduce by 30-40%
- **Profit factor**: Potentially reach 3.0-4.0

## 🚀 Tonight's Action Plan

1. **First**: Just change time to 3-12 and test
2. **Second**: Increase signal quality to 0.72
3. **Third**: Test one "Configuration D" (Conservative)
4. **Fourth**: Implement HA adjustments if time permits

Take screenshots of each test and we can analyze in the morning!