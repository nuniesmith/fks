# FKS Strategy Optimization Setup Guide

This guide provides step-by-step instructions for optimizing your FKS strategy across the 5 main assets: **GC, ES, NQ, CL, BTC**.

## Quick Start Optimization Sequence

### Phase 1: Asset-Specific Base Settings

Start with these recommended base configurations for each asset:

#### Gold (GC) - Most Stable
```
SignalQualityThreshold: 0.70
VolumeThreshold: 1.3
ATRStopMultiplier: 2.0
ATRTargetMultiplier: 1.5
BaseContracts: 1
MaxContracts: 5
MaxDailyTrades: 8
StartHour: 3, EndHour: 12
```

#### S&P 500 (ES) - Balanced
```
SignalQualityThreshold: 0.70
VolumeThreshold: 1.3
ATRStopMultiplier: 2.0
ATRTargetMultiplier: 1.5
BaseContracts: 1
MaxContracts: 4
MaxDailyTrades: 8
StartHour: 3, EndHour: 12
```

#### Nasdaq (NQ) - Higher Volatility
```
SignalQualityThreshold: 0.75
VolumeThreshold: 1.4
ATRStopMultiplier: 2.5
ATRTargetMultiplier: 2.0
BaseContracts: 1
MaxContracts: 3
MaxDailyTrades: 6
StartHour: 3, EndHour: 12
```

#### Crude Oil (CL) - Very Volatile
```
SignalQualityThreshold: 0.78
VolumeThreshold: 1.5
ATRStopMultiplier: 3.0
ATRTargetMultiplier: 2.5
BaseContracts: 1
MaxContracts: 2
MaxDailyTrades: 4
StartHour: 3, EndHour: 11
```

#### Bitcoin (BTC) - Extreme Volatility
```
SignalQualityThreshold: 0.80
VolumeThreshold: 1.6
ATRStopMultiplier: 4.0
ATRTargetMultiplier: 3.0
BaseContracts: 1
MaxContracts: 2
MaxDailyTrades: 3
StartHour: 6, EndHour: 16
```

## Optimization Phases

### Phase 1: Core Signal Parameters (Most Important)

**Optimize in this order:**

1. **SignalQualityThreshold** (Most critical)
   - GC: Test 0.65 to 0.75 (step 0.02)
   - ES: Test 0.68 to 0.75 (step 0.02)  
   - NQ: Test 0.70 to 0.80 (step 0.02)
   - CL: Test 0.72 to 0.85 (step 0.03)
   - BTC: Test 0.75 to 0.90 (step 0.03)

2. **VolumeThreshold** (Volume confirmation)
   - GC: Test 1.1 to 1.4 (step 0.1)
   - ES: Test 1.2 to 1.5 (step 0.1)
   - NQ: Test 1.3 to 1.6 (step 0.1)
   - CL: Test 1.4 to 1.8 (step 0.1)
   - BTC: Test 1.5 to 2.0 (step 0.1)

3. **ATRStopMultiplier** (Risk management)
   - GC: Test 1.5 to 2.5 (step 0.25)
   - ES: Test 1.8 to 2.5 (step 0.2)
   - NQ: Test 2.0 to 3.0 (step 0.25)
   - CL: Test 2.5 to 4.0 (step 0.3)
   - BTC: Test 3.0 to 5.0 (step 0.5)

4. **ATRTargetMultiplier** (Profit targets)
   - GC: Test 1.2 to 2.0 (step 0.2)
   - ES: Test 1.3 to 2.2 (step 0.3)
   - NQ: Test 1.5 to 2.5 (step 0.25)
   - CL: Test 1.8 to 3.0 (step 0.3)
   - BTC: Test 2.0 to 4.0 (step 0.5)

### Phase 2: Position Sizing

**After Phase 1 is complete:**

1. **BaseContracts** - Start with 1 for all assets
2. **MaxContracts** - Test based on volatility:
   - GC/ES: Test 3-5 contracts
   - NQ: Test 2-4 contracts  
   - CL/BTC: Test 1-3 contracts

3. **MaxDailyTrades** - Test based on signal frequency:
   - GC: Test 6-10 trades
   - ES: Test 5-8 trades
   - NQ: Test 4-7 trades
   - CL: Test 2-5 trades
   - BTC: Test 1-4 trades

### Phase 3: Time Filters

**Test different trading sessions:**

**Gold (GC):**
- (2,11) - Early London to before lunch
- (3,12) - Your current setting  
- (4,13) - Late London start
- (3,10) - London heavy
- (6,14) - NY heavy

**ES/NQ:**
- (3,12) - Your current setting
- (6,15) - Pure NY session
- (7,14) - NY core hours
- (8,13) - NY morning only

**Crude Oil (CL):**
- (3,11) - Early session (includes inventory)
- (6,14) - NY energy session
- (7,12) - Core energy hours

**Bitcoin (BTC):**
- (3,15) - Traditional hours
- (6,18) - Extended trading
- (8,16) - Conservative hours

### Phase 4: Risk Management Limits

**Final optimization of profit/loss limits:**

Test these ranges based on expected asset performance:

**Conservative (CL, BTC):**
- Daily Profit Soft: $1200-1800
- Daily Profit Hard: $2000-2700
- Daily Loss Soft: $600-900
- Daily Loss Hard: $1000-1350

**Standard (GC, ES):**
- Daily Profit Soft: $1800-2200
- Daily Profit Hard: $2700-3300
- Daily Loss Soft: $900-1100
- Daily Loss Hard: $1350-1650

**Aggressive (NQ only if performing well):**
- Daily Profit Soft: $2000-2400
- Daily Profit Hard: $3000-3600
- Daily Loss Soft: $1000-1200
- Daily Loss Hard: $1500-1800

## Bar Type Testing

### Standard Time Bars
Test these timeframes for each asset:
- **1 minute:** Higher signal quality needed (+0.05)
- **2 minute:** Slight quality increase (+0.02)
- **3 minute:** Your current standard (0.0)
- **5 minute:** Can be more lenient (-0.02)
- **15 minute:** More lenient for higher timeframes (-0.05)

### Heiken Ashi Bars
- Use 2, 3, 5, 15 minute timeframes
- Apply 1.2x volume multiplier
- Give 10% signal quality boost
- Focus on strong HA patterns (large body, minimal wicks)

### Renko Bars (Advanced)
Test these brick sizes:
- **GC:** 2-5 ticks
- **ES:** 1-4 ticks
- **NQ:** 1-3 ticks  
- **CL:** 2-6 ticks
- **BTC:** 5-20 ticks

## Performance Targets by Asset

### Minimum Acceptable Performance:

**Gold (GC):**
- Win Rate: 55%+
- Profit Factor: 1.4+
- Max Drawdown: <8%
- Daily Avg Profit: $150+

**S&P 500 (ES):**
- Win Rate: 52%+
- Profit Factor: 1.3+
- Max Drawdown: <10%
- Daily Avg Profit: $180+

**Nasdaq (NQ):**
- Win Rate: 50%+
- Profit Factor: 1.5+
- Max Drawdown: <12%
- Daily Avg Profit: $200+

**Crude Oil (CL):**
- Win Rate: 48%+
- Profit Factor: 1.6+
- Max Drawdown: <15%
- Daily Avg Profit: $120+

**Bitcoin (BTC):**
- Win Rate: 45%+
- Profit Factor: 1.8+
- Max Drawdown: <20%
- Daily Avg Profit: $100+

## Backtesting Recommendations

### Data Requirements:
- **Minimum:** 6 months of tick data
- **Recommended:** 12 months of tick data
- **Include:** Major news events and volatility periods

### Walk-Forward Analysis:
- **Training Period:** 3 months
- **Testing Period:** 1 month
- **Step Forward:** 2 weeks
- **Re-optimize:** Every 3 months

### Market Conditions to Test:
1. **Trending Markets** (Jan-Feb 2024)
2. **Choppy/Sideways** (Summer 2024)
3. **High Volatility** (Election periods)
4. **Low Volatility** (Holiday periods)
5. **News Events** (FOMC, NFP, Earnings)

## Quick Optimization Setup in NinjaTrader

1. **Load Strategy:** Apply FKSStrategyAIO to your chart
2. **Open Optimizer:** Strategy Analyzer → New → Strategy
3. **Set Optimization Type:** Genetic Algorithm (faster) or Brute Force (thorough)
4. **Configure Parameters:** Use ranges from Phase 1 above
5. **Set Fitness Function:** Net Profit + (Profit Factor * 10000) - (Max Drawdown * 50000)
6. **Run Time:** Start with 3-6 months of data
7. **Validate Results:** Test on out-of-sample data

## Red Flags - Stop Optimization If:

- **Win rate drops below 40%** for any asset
- **Profit factor below 1.2** consistently  
- **Max drawdown exceeds 25%** of account
- **Average trade below $20** (commission concerns)
- **Less than 50 trades** in test period (insufficient data)
- **Sharpe ratio below 0.5** (poor risk-adjusted returns)

## Next Steps After Optimization:

1. **Paper Trade** optimized parameters for 2 weeks
2. **Start with smallest position sizes** in live trading
3. **Monitor performance** against backtest expectations
4. **Re-optimize** if market conditions change significantly
5. **Scale up gradually** as confidence builds

Remember: **Over-optimization is the enemy**. If results look too good to be true, they probably are. Focus on robust parameters that work across different market conditions.
