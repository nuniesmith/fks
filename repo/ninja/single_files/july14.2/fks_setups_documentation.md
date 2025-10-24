# FKS Trading Systems - Complete Setup Documentation

## 🎯 System Overview

The FKS Trading Systems combines three powerful indicators with six distinct trading setups. Each setup can be individually enabled/disabled for testing and optimization.

### Core Components:
- **FKS_AI**: AI-enhanced support/resistance detection with signal quality scoring
- **FKS_AO**: Enhanced Awesome Oscillator with momentum confirmation
- **FKS_VWAP**: Advanced VWAP with EMA9 crossover detection
- **FKS_Dashboard**: Real-time market analysis dashboard

### Supported Markets:
- Gold Futures (GC)
- E-mini S&P 500 (ES)
- E-mini Nasdaq (NQ)
- Crude Oil (CL)
- Bitcoin Futures (BTC)

### Recommended Timeframes:
- **Primary**: 1-minute charts
- **Fast Charts**: Renko 2-3 bars, Tick charts (100, 150, 200)
- **Confirmation**: 5-minute and 15-minute

---

## 📊 Trading Setups

### Setup 1: EMA9 + VWAP Bullish Breakout
**Code**: S1L  
**Direction**: Long Only  
**Default Quality Threshold**: 0.65  

#### Entry Conditions (ALL must be met):
1. Price > EMA9 > VWAP (stacked alignment)
2. FKS_AI signal: "G" or "^" 
3. Signal quality ≥ 0.65
4. AO bullish (value > 0)
5. Volume > 1.2x average
6. Price breaks above recent 10-bar swing high

#### GUI Implementation:
```
Condition Group: "Setup 1 Bullish"
- Price Compare: Close > EMA(9)
- Indicator Compare: EMA(9) > VWAP
- FKS_AI.SignalType = "G" OR "^"
- FKS_AI.SignalQuality >= 0.65
- FKS_AO.Value > 0
- Volume Ratio > 1.2
- Price Breakout: Close > Highest(High, 10)[1]
```

#### Notes:
- Best during US morning session (8:00-12:00 EST)
- Look for strong volume surge on breakout
- Works best in trending markets
- Consider scaling in on pullbacks to EMA9

---

### Setup 2: EMA9 + VWAP Bearish Breakdown
**Code**: S2S  
**Direction**: Short Only  
**Default Quality Threshold**: 0.65  

#### Entry Conditions (ALL must be met):
1. Price < EMA9 < VWAP (bearish stack)
2. FKS_AI signal: "Top" or "v"
3. Signal quality ≥ 0.65
4. AO bearish (value < 0)
5. Volume > 1.2x average
6. Price breaks below recent 10-bar swing low

#### GUI Implementation:
```
Condition Group: "Setup 2 Bearish"
- Price Compare: Close < EMA(9)
- Indicator Compare: EMA(9) < VWAP
- FKS_AI.SignalType = "Top" OR "v"
- FKS_AI.SignalQuality >= 0.65
- FKS_AO.Value < 0
- Volume Ratio > 1.2
- Price Breakdown: Close < Lowest(Low, 10)[1]
```

#### Notes:
- Watch for failed highs before entry
- Stronger in downtrending markets
- Be cautious of support levels below
- Consider reduced size in volatile conditions

---

### Setup 3: VWAP Rejection Bounce
**Code**: S3L  
**Direction**: Long (can be adapted for short)  
**Default Quality Threshold**: 0.60  
**Special Parameters**: Stop = 1.5 ATR, Target = 2.5 ATR

#### Entry Conditions:
1. Price within 0.5 ATR of VWAP
2. FKS_AI signal: "G" at support
3. Signal quality ≥ 0.60
4. Near identified support level
5. AO shows bullish divergence OR accelerating momentum
6. Rejection candle pattern (hammer or bullish engulfing)

#### GUI Implementation:
```
Condition Group: "Setup 3 VWAP Bounce"
- Price Distance: ABS(Close - VWAP) / ATR(14) < 0.5
- FKS_AI.SignalType = "G"
- FKS_AI.SignalQuality >= 0.60
- FKS_AI.NearSupport = True
- FKS_AO.IsAccelerating = True OR Divergence Pattern
- Candlestick Pattern: Hammer OR Bullish Engulfing
```

#### Notes:
- Requires clean rejection candle
- Works best in ranging markets
- Quick scalp opportunity
- Can mirror for short trades at resistance

---

### Setup 4: Support/Resistance + AO Zero Cross
**Code**: S4X  
**Direction**: Dynamic (based on location)  
**Default Quality Threshold**: 0.70  
**Special Parameters**: Target = 3.5 ATR

#### Entry Conditions:
1. Price at key S/R level (within 0.3 ATR)
2. AO crosses zero line
3. FKS_AI signal quality ≥ 0.70
4. Volume > 1.2x average
5. Direction: Long at support with bullish AO cross, Short at resistance with bearish AO cross

#### GUI Implementation:
```
Condition Group: "Setup 4 S/R Cross"
- Location Check: FKS_AI.NearSupport OR FKS_AI.NearResistance
- FKS_AO.CrossDirection != 0
- FKS_AI.SignalQuality >= 0.70
- Volume Ratio > 1.2
- Direction Logic:
  IF NearSupport AND AO.CrossDirection > 0 THEN Long
  IF NearResistance AND AO.CrossDirection < 0 THEN Short
```

#### Notes:
- Most reliable at major S/R levels
- Confirm with multiple timeframes
- Higher win rate setup
- Good for position trades

---

### Setup 5: Momentum Surge (Disabled by Default)
**Code**: S5M  
**Direction**: Dynamic (follows momentum)  
**Quality Threshold**: 0.60  

#### Entry Conditions:
1. AO momentum strength > 0.7
2. AO is accelerating
3. Strong directional signal alignment:
   - Bullish: AO > 0 + bullish cross + "G" or "^" signal
   - Bearish: AO < 0 + bearish cross + "Top" or "v" signal

#### GUI Implementation:
```
Condition Group: "Setup 5 Momentum"
- FKS_AO.MomentumStrength > 0.7
- FKS_AO.IsAccelerating = True
- Bullish Path:
  FKS_AO.Value > 0 AND
  FKS_AO.CrossDirection > 0 AND
  (FKS_AI.SignalType = "G" OR "^")
- Bearish Path:
  FKS_AO.Value < 0 AND
  FKS_AO.CrossDirection < 0 AND
  (FKS_AI.SignalType = "Top" OR "v")
```

#### Notes:
- Quick scalp setup
- Use tight stops
- Take profits quickly
- Best for experienced traders

---

### Setup 6: VWAP + EMA9 Cross (Disabled by Default)
**Code**: S6C  
**Direction**: Long (can be adapted)  
**Quality Threshold**: 0.55  

#### Entry Conditions:
1. Fresh EMA9/VWAP crossover (within 3 bars)
2. Bullish cross confirmed
3. FKS_AI signal: "G" or "^"

#### GUI Implementation:
```
Condition Group: "Setup 6 Cross"
- FKS_VWAP.GetCrossoverState = BullishCrossover
- FKS_VWAP.GetBarsSinceCrossover <= 3
- FKS_AI.SignalType = "G" OR "^"
```

#### Notes:
- Early entry setup
- Best at beginning of trends
- Lower quality threshold
- Can generate false signals in choppy markets

---

## 🎮 GUI Tool Integration (SharkIndicators/BloodHound)

### Creating Condition Sets in BloodHound:

1. **Indicator Registration**:
   - Add FKS_AI to indicators list
   - Add FKS_AO to indicators list
   - Add FKS_VWAP to indicators list
   - Add standard EMA(9), ATR(14), Volume

2. **Signal Quality Filter**:
   ```
   Create Threshold Node:
   - Input: FKS_AI.SignalQuality
   - Threshold: Variable (0.55-0.70 based on setup)
   - Output: Pass/Fail
   ```

3. **Volume Confirmation**:
   ```
   Create Ratio Node:
   - Input A: Current Volume
   - Input B: SMA(Volume, 20)
   - Comparison: A/B > 1.2
   ```

4. **Directional Alignment**:
   ```
   Create Logic Node:
   - For Longs: Price > EMA9 AND EMA9 > VWAP
   - For Shorts: Price < EMA9 AND EMA9 < VWAP
   ```

### BlackBird Integration:

For automated execution, create templates for each setup:

```yaml
Template: "FKS_Setup1_Bullish"
Entry:
  - All conditions from Setup 1
  - Contracts: Dynamic (1-5 based on quality)
Exit:
  - Stop: Entry - (ATR * 2.0)
  - Target1: Entry + (ATR * 3.0)
  - Target2: Entry + (ATR * 4.5)
  - Trailing: 1.5 ATR after Target1
```

---

## 📈 Position Sizing Matrix

| Signal Quality | Wave Ratio | Contracts (GC) | Contracts (NQ) | Contracts (CL) |
|---------------|------------|----------------|----------------|----------------|
| > 0.85        | > 2.0      | 4-5           | 3-4            | 4-5            |
| 0.70-0.85     | > 1.5      | 2-3           | 2              | 2-3            |
| 0.60-0.70     | > 1.0      | 1-2           | 1              | 1-2            |

### Market Regime Adjustments:
- **Volatile Market**: Reduce size by 50%
- **Ranging Market**: Reduce size by 30%
- **Trending Market**: Normal size
- **After 2 Losses**: Reduce size by 50%

---

## 🛠️ Optimization Guidelines

### Testing Protocol:
1. Enable one setup at a time
2. Run for minimum 50 trades
3. Track win rate, average win/loss, profit factor
4. Note market conditions during test period
5. Adjust quality thresholds based on results

### Key Metrics to Track:
- **Win Rate**: Target 55-65%
- **Profit Factor**: Target > 1.5
- **Average R:R**: Target > 1:1.5
- **Max Drawdown**: Keep < 5%
- **Time in Trade**: Note average duration

### Setup-Specific Optimizations:

**Setup 1 & 2**: 
- Test quality thresholds from 0.60 to 0.75
- Experiment with volume thresholds (1.1x to 1.5x)
- Try different swing high/low lookback periods (5-20 bars)

**Setup 3**:
- Adjust VWAP distance threshold (0.3-0.7 ATR)
- Test different rejection patterns
- Try with/without divergence requirement

**Setup 4**:
- Test different S/R detection methods
- Adjust distance to S/R levels (0.2-0.5 ATR)
- Experiment with AO confirmation timing

---

## 🚨 Risk Management Rules

### Daily Limits:
- Maximum 6 trades per day
- Stop after 3 consecutive losses
- Daily loss limit: 2% of account
- Daily profit target: 1.5% of account

### Per-Trade Risk:
- Never risk more than 1% per trade
- Stop loss: 2x ATR (adjustable per setup)
- Minimum R:R ratio: 1:1.5

### Time-Based Rules:
- No new trades 15 minutes before session close
- Reduce size outside optimal hours
- Avoid trading around major news events

---

## 📝 Quick Reference Card

### Signal Types:
- **"G"**: Strong bullish at support
- **"Top"**: Strong bearish at resistance  
- **"^"**: Bullish reversal pattern
- **"v"**: Bearish reversal pattern

### Quality Scores:
- **0.85+**: Premium signal (max size)
- **0.70-0.85**: Strong signal (normal size)
- **0.60-0.70**: Standard signal (reduced size)
- **< 0.60**: No trade

### AO Signals:
- **CrossDirection > 0**: Bullish zero cross
- **CrossDirection < 0**: Bearish zero cross
- **MomentumStrength > 0.7**: Strong momentum
- **IsAccelerating**: Momentum increasing

### Quick Checks:
1. Is signal quality above threshold?
2. Do we have indicator alignment?
3. Is volume confirming?
4. Are we at a key level?
5. Is this the optimal session?

---

## 🎯 Performance Tracking Template

```csv
Date,Setup,Direction,Entry,Stop,Target1,Target2,Exit,P&L,R-Multiple,Notes
2024-01-15,S1L,Long,1950.50,1948.00,1955.50,1958.00,1955.50,+250,+2.0R,Clean breakout
2024-01-15,S3L,Long,1952.00,1950.50,1954.50,1956.00,1953.25,+62.50,+0.83R,Early exit on reversal
```

Track this data to identify:
- Most profitable setups
- Best times of day
- Optimal market conditions
- Areas for improvement

---

## 💡 Advanced Tips

1. **Multi-Timeframe Confirmation**: Always check 5-minute chart for trend alignment
2. **Correlation Watch**: Monitor correlated markets (DXY for Gold, VIX for indices)
3. **Session Overlaps**: Best opportunities often occur at session transitions
4. **News Awareness**: Keep economic calendar handy, avoid trading 30 min before high-impact news
5. **Scaling Strategy**: Consider scaling in at better prices on winning setups
6. **Exit Management**: Move stop to breakeven after 1:1 R:R achieved
7. **Market Profile**: Use volume profile to identify high-probability S/R levels
8. **Regime Awareness**: Adjust expectations based on current market regime

---

This documentation provides a complete reference for implementing and optimizing the FKS trading system. Each setup can be tested independently to find the best combinations for your trading style and market conditions.