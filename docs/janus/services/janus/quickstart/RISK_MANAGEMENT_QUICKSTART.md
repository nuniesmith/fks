# JANUS Risk Management - Quick Reference Guide

Quick reference for using the JANUS risk management module.

---

## 🚀 Quick Start

### 1. Basic Setup

```rust
use janus::risk::{RiskConfig, RiskManager, MarketData, PortfolioState};

// Create configuration
let config = RiskConfig {
    account_balance: 10000.0,
    risk_per_trade_pct: 0.01,  // 1% risk per trade
    min_risk_reward_ratio: 2.0, // 2:1 R/R minimum
    ..Default::default()
};

// Create manager
let risk_manager = RiskManager::new(config);
```

### 2. Apply Risk Management to Signal

```rust
// Your trading signal
let signal = TradingSignal::new(...)
    .with_entry_price(50000.0);

// Market data
let market_data = MarketData::new(50000.0)
    .with_atr(500.0);

// Portfolio state
let portfolio = PortfolioState::new(10000.0);

// Apply risk management
let enhanced_signal = risk_manager.apply_risk_management(
    signal,
    &market_data,
    &portfolio,
)?;

// Now has stop_loss, take_profit, and position sizing
```

---

## 📊 Position Sizing

### Fixed Fractional (Default)
```rust
use janus::risk::{PositionSizer, SizingMethod};

let sizer = PositionSizer::new(config);
let position = sizer.calculate_position_size(
    &signal,
    &market_data,
    &SizingMethod::FixedFractional,
)?;

println!("Quantity: {}", position.quantity);
println!("Risk: ${}", position.risk_amount);
```

### Kelly Criterion
```rust
let position = sizer.calculate_position_size(
    &signal,
    &market_data,
    &SizingMethod::Kelly {
        win_rate: 0.6,
        avg_win_loss_ratio: 2.0,
    },
)?;
```

### Volatility-Based
```rust
let position = sizer.calculate_position_size(
    &signal,
    &market_data,
    &SizingMethod::VolatilityBased {
        target_volatility: 0.03,
    },
)?;
```

### ATR-Based
```rust
let position = sizer.calculate_position_size(
    &signal,
    &market_data,
    &SizingMethod::AtrBased {
        target_atr_multiple: 2.0,
    },
)?;
```

---

## 🛑 Stop Loss & Take Profit

### Stop Loss Methods

#### ATR-Based (Recommended)
```rust
use janus::risk::{StopLossCalculator, StopLossMethod};

let calculator = StopLossCalculator::new(config);
let stop = calculator.calculate_stop_loss(
    &signal,
    &market_data,
    &StopLossMethod::Atr { multiplier: 2.0 },
)?;
```

#### Percentage-Based
```rust
let stop = calculator.calculate_stop_loss(
    &signal,
    &market_data,
    &StopLossMethod::Percentage { percent: 0.02 }, // 2%
)?;
```

#### Support/Resistance
```rust
let market_data = MarketData::new(50000.0)
    .with_support(49000.0);

let stop = calculator.calculate_stop_loss(
    &signal,
    &market_data,
    &StopLossMethod::SupportResistance,
)?;
```

### Take Profit Methods

#### Risk/Reward Ratio (Default)
```rust
use janus::risk::TakeProfitCalculator;

let tp_calc = TakeProfitCalculator::new(config);
let take_profit = tp_calc.calculate_take_profit(&signal, &market_data)?;
// Uses default 2:1 R/R from config
```

#### ATR-Based
```rust
let take_profit = tp_calc.calculate_take_profit_with_method(
    &signal,
    &market_data,
    &TakeProfitMethod::Atr { multiplier: 3.0 },
    entry_price,
    stop_loss,
)?;
```

---

## 🔒 Risk Limits & Validation

### Create Limits
```rust
use janus::risk::{RiskLimits, RiskValidator};

let limits = RiskLimits::from_config(&config);
let validator = RiskValidator::new(limits);
```

### Validate Signal
```rust
// Checks all limits
validator.validate_signal(&signal, &portfolio)?;
```

### Check Specific Limits
```rust
// Position size
validator.validate_position_size(1000.0)?;

// Position count
validator.validate_position_count(&portfolio)?;

// Daily loss
validator.validate_daily_loss(&portfolio)?;
```

---

## 📈 Portfolio Risk Metrics

### Calculate Portfolio Risk
```rust
use janus::risk::RiskMetrics;

let risk = RiskMetrics::calculate_portfolio_risk(&portfolio, 10000.0);

println!("Total Risk: ${}", risk.total_risk);
println!("Portfolio Heat: {:.2}%", risk.portfolio_heat * 100.0);
println!("Exposure: {:.2}%", risk.exposure_percentage * 100.0);
println!("Diversification: {:.2}", risk.diversification_score);
```

### Track Performance
```rust
use janus::risk::PerformanceMetrics;

let mut metrics = PerformanceMetrics::new();

// Add trades
metrics.add_trade(200.0);  // Win
metrics.add_trade(-100.0); // Loss

// Get metrics
println!("Win Rate: {:.2}%", metrics.win_rate * 100.0);
println!("Profit Factor: {:.2}", metrics.profit_factor);
println!("Expected Value: ${:.2}", metrics.expected_value);
println!("Kelly Fraction: {:.2}%", metrics.kelly_fraction() * 100.0);
```

### Track Drawdown
```rust
use janus::risk::DrawdownTracker;

let mut tracker = DrawdownTracker::new(10000.0);

tracker.update(11000.0); // New peak
tracker.update(10500.0); // Drawdown

println!("Current DD: {:.2}%", tracker.current_drawdown_pct * 100.0);
println!("Max DD: {:.2}%", tracker.max_drawdown_pct * 100.0);
```

### Calculate Sharpe Ratio
```rust
use janus::risk::SharpeCalculator;

let mut sharpe = SharpeCalculator::new(0.02); // 2% risk-free rate

sharpe.add_return(0.05);
sharpe.add_return(0.03);
sharpe.add_return(-0.02);

if let Some(ratio) = sharpe.calculate() {
    println!("Sharpe Ratio: {:.2}", ratio);
}
```

---

## 🎯 Market Data

### Basic Market Data
```rust
let market_data = MarketData::new(50000.0); // Current price
```

### With ATR
```rust
let market_data = MarketData::new(50000.0)
    .with_atr(500.0);
```

### With Support/Resistance
```rust
let market_data = MarketData::new(50000.0)
    .with_support(49000.0)
    .with_resistance(51000.0);
```

### Complete Market Data
```rust
let market_data = MarketData::new(50000.0)
    .with_atr(500.0)
    .with_support(49000.0)
    .with_resistance(51000.0)
    .with_volatility(0.02)
    .with_range(51500.0, 48500.0);
```

---

## 💼 Portfolio State

### Create Portfolio
```rust
let mut portfolio = PortfolioState::new(10000.0);
```

### Add Position
```rust
use janus::risk::{Position, PositionSide};

portfolio.add_position(
    "BTC/USD".to_string(),
    Position {
        symbol: "BTC/USD".to_string(),
        entry_price: 50000.0,
        quantity: 0.1,
        side: PositionSide::Long,
        stop_loss: Some(49000.0),
        take_profit: Some(52000.0),
    },
);
```

### Track P&L
```rust
portfolio.daily_pnl = -150.0; // Lost $150 today
```

### Query Portfolio
```rust
println!("Positions: {}", portfolio.position_count());
println!("Total Exposure: ${}", portfolio.total_exposure());
println!("BTC Exposure: ${}", portfolio.exposure_for_symbol("BTC/USD"));
```

---

## ⚙️ Configuration Presets

### Conservative
```rust
RiskConfig {
    account_balance: 10000.0,
    risk_per_trade_pct: 0.005,       // 0.5%
    max_position_size_pct: 0.05,     // 5%
    max_portfolio_exposure_pct: 0.3, // 30%
    min_risk_reward_ratio: 3.0,      // 3:1
    max_concurrent_positions: 3,
    max_daily_loss_pct: 0.02,        // 2%
    ..Default::default()
}
```

### Moderate (Default)
```rust
RiskConfig {
    account_balance: 10000.0,
    risk_per_trade_pct: 0.01,        // 1%
    max_position_size_pct: 0.1,      // 10%
    max_portfolio_exposure_pct: 0.5, // 50%
    min_risk_reward_ratio: 2.0,      // 2:1
    max_concurrent_positions: 5,
    max_daily_loss_pct: 0.05,        // 5%
    ..Default::default()
}
```

### Aggressive
```rust
RiskConfig {
    account_balance: 10000.0,
    risk_per_trade_pct: 0.02,        // 2%
    max_position_size_pct: 0.2,      // 20%
    max_portfolio_exposure_pct: 0.8, // 80%
    min_risk_reward_ratio: 1.5,      // 1.5:1
    max_concurrent_positions: 10,
    max_daily_loss_pct: 0.10,        // 10%
    ..Default::default()
}
```

---

## 🔍 Common Patterns

### Complete Trading Workflow
```rust
// 1. Setup
let risk_manager = RiskManager::new(config);
let mut portfolio = PortfolioState::new(10000.0);

// 2. Generate signal
let signal = signal_generator.generate(...).await?;

// 3. Prepare market data
let market_data = MarketData::new(current_price)
    .with_atr(calculate_atr(&candles));

// 4. Apply risk management
let final_signal = risk_manager.apply_risk_management(
    signal,
    &market_data,
    &portfolio,
)?;

// 5. Extract trading parameters
let entry = final_signal.entry_price.unwrap();
let stop = final_signal.stop_loss.unwrap();
let tp = final_signal.take_profit.unwrap();
let quantity = final_signal.metadata.get("position_size_units").unwrap();

// 6. Place order
place_order(entry, stop, tp, quantity).await?;
```

### Risk Monitoring Loop
```rust
loop {
    // Update portfolio state
    update_portfolio_state(&mut portfolio).await?;
    
    // Calculate risk
    let risk = RiskMetrics::calculate_portfolio_risk(&portfolio, account_balance);
    
    // Check if healthy
    if !risk.is_healthy(0.05, 0.5) {
        alert_risk_breach(&risk).await?;
    }
    
    // Sleep
    tokio::time::sleep(Duration::from_secs(60)).await;
}
```

---

## ⚠️ Error Handling

### Common Errors
```rust
use janus::risk::RiskError;

match risk_manager.apply_risk_management(signal, &market_data, &portfolio) {
    Ok(signal) => {
        // Success
    }
    Err(RiskError::MaxPositionsReached { max }) => {
        println!("Cannot open more positions (max: {})", max);
    }
    Err(RiskError::DailyLossLimitReached { actual, max }) => {
        println!("Daily loss limit reached: ${} >= ${}", actual, max);
    }
    Err(RiskError::InsufficientRiskReward { actual, required }) => {
        println!("R/R too low: {:.2} < {:.2}", actual, required);
    }
    Err(e) => {
        println!("Risk error: {}", e);
    }
}
```

---

## 📚 Further Reading

- **Full Documentation:** See `WEEK5_COMPLETE.md`
- **API Reference:** `cargo doc --open --package janus`
- **Tests:** `services/janus/src/risk/*/tests.rs`
- **Examples:** `services/janus/src/risk/mod.rs` tests

---

## 💡 Tips

1. **Always validate signals** before executing trades
2. **Use ATR-based stops** for dynamic market conditions
3. **Track performance metrics** to optimize parameters
4. **Monitor portfolio heat** to avoid overexposure
5. **Set realistic R/R ratios** (2:1 or higher recommended)
6. **Use Kelly Criterion carefully** (half-Kelly is safer)
7. **Check correlation** between positions to avoid concentration
8. **Update market data** regularly for accurate calculations

---

## 🆘 Troubleshooting

### "Missing entry price"
```rust
// Always set entry price before risk management
let signal = signal.with_entry_price(current_price);
```

### "Missing ATR"
```rust
// Provide ATR in market data for ATR-based methods
let market_data = market_data.with_atr(calculate_atr(&candles));
```

### "Position size limit exceeded"
```rust
// Increase max position size or reduce risk per trade
config.max_position_size_pct = 0.2; // 20% instead of 10%
```

### "Insufficient risk/reward ratio"
```rust
// Lower minimum R/R requirement or adjust take profit
config.min_risk_reward_ratio = 1.5; // Instead of 2.0
```

---

## 📞 Support

For issues or questions:
- Check test files for usage examples
- Review module documentation
- See `WEEK5_COMPLETE.md` for detailed explanations

---

**Happy Trading! 📈**