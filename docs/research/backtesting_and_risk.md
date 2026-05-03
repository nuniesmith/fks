# Project JANUS - Backtesting Framework & Risk Management
## Sections 7-9: Extending the Architectural Roadmap

**Document Version:** 1.0  
**Companion to:** Project JANUS Architectural Roadmap  
**Date:** 2024

---

## 7. Validation Framework and Backtesting Constraints

The validation of a neuro-symbolic HFT system presents unique challenges that transcend traditional machine learning evaluation. Unlike offline prediction tasks where accuracy is the sole metric, JANUS must be validated against the physics of market microstructure, the non-stationarity of financial time series, and the execution costs that dominate profitability at microsecond timescales.

### 7.1 The Impossibility of Perfect Backtesting

**Fundamental Limitations:**

1. **Lookahead Bias:** Any use of future data (even by 1 tick) invalidates results
2. **Survivorship Bias:** Historical datasets exclude delisted/bankrupt companies
3. **Market Impact:** Backtests assume infinite liquidity at quoted prices
4. **Regime Shift:** Historical patterns may not recur (non-stationarity)
5. **Execution Realism:** Cannot simulate sub-millisecond race conditions

**The JANUS Approach:** We acknowledge that backtesting provides an upper bound on performance, not a guarantee. The goal is to prove the system doesn't catastrophically fail, not to predict exact returns.

---

### 7.2 Realistic Market Simulation

#### 7.2.1 Order Book Reconstruction

Historical tick data must be reconstructed into a full limit order book (LOB) state machine.

**Data Requirements:**
- L3 (full depth) market data with order IDs
- Timestamps with nanosecond precision
- All message types: Add, Modify, Cancel, Execute
- Trade messages with aggressor side indicator

**State Machine:**
```rust
struct OrderBookSimulator {
    bids: BTreeMap<Price, VecDeque<Order>>,  // Price-time priority
    asks: BTreeMap<Price, VecDeque<Order>>,
    
    // Track our own orders
    our_orders: HashMap<OrderId, Order>,
    
    // Latency simulation
    order_ack_latency_us: f64,
    fill_latency_us: f64,
}

impl OrderBookSimulator {
    fn process_market_event(&mut self, event: MarketEvent, current_time: u64) {
        match event {
            MarketEvent::Add { side, price, quantity, order_id } => {
                self.add_order(side, price, quantity, order_id);
            }
            MarketEvent::Cancel { order_id } => {
                self.cancel_order(order_id);
            }
            MarketEvent::Execute { order_id, quantity } => {
                self.execute_order(order_id, quantity);
                
                // Check if our order was ahead in queue and got filled
                self.check_our_fills(current_time);
            }
        }
    }
    
    fn submit_order(&mut self, order: Order, current_time: u64) -> OrderStatus {
        // Simulate network latency
        let ack_time = current_time + self.order_ack_latency_us * 1000;  // ns
        
        // Check if order would have crossed the spread
        let would_execute_immediately = match order.side {
            Side::Buy => order.price >= self.best_ask(),
            Side::Sell => order.price <= self.best_bid(),
        };
        
        if would_execute_immediately {
            // Simulate aggressive execution with slippage
            return self.simulate_market_order_execution(order, current_time);
        }
        
        // Passive order joins queue
        self.our_orders.insert(order.id, order.clone());
        
        OrderStatus::Acknowledged {
            ack_time,
            queue_position: self.calculate_queue_position(&order),
        }
    }
    
    fn calculate_queue_position(&self, order: &Order) -> usize {
        // Count orders ahead of us at this price level
        let queue = match order.side {
            Side::Buy => &self.bids.get(&order.price),
            Side::Sell => &self.asks.get(&order.price),
        };
        
        queue.map(|q| q.len()).unwrap_or(0)
    }
    
    fn simulate_market_order_execution(&mut self, order: Order, time: u64) 
        -> OrderStatus 
    {
        // Walk the book to fill the order
        let mut remaining = order.quantity;
        let mut fills = Vec::new();
        let mut total_cost = 0.0;
        
        let book_side = match order.side {
            Side::Buy => &mut self.asks,
            Side::Sell => &mut self.bids,
        };
        
        // Iterate through price levels
        while remaining > 0 {
            if let Some((price, level)) = book_side.iter_mut().next() {
                let available = level.front().map(|o| o.quantity).unwrap_or(0);
                let fill_qty = remaining.min(available);
                
                fills.push(Fill {
                    price: *price,
                    quantity: fill_qty,
                    time: time + self.fill_latency_us * 1000,
                });
                
                total_cost += (*price as f64) * (fill_qty as f64);
                remaining -= fill_qty;
                
                // Remove filled liquidity from book
                if let Some(front) = level.front_mut() {
                    front.quantity -= fill_qty;
                    if front.quantity == 0 {
                        level.pop_front();
                    }
                }
            } else {
                // No more liquidity - partial fill
                break;
            }
        }
        
        if remaining > 0 {
            OrderStatus::PartialFill { fills, unfilled: remaining }
        } else {
            OrderStatus::Filled { fills }
        }
    }
}
```

---

#### 7.2.2 Latency Modeling

Backtests must model the latency between decision and execution.

**Latency Components:**
1. **Processing latency** (internal): DSP + Inference + Risk checks = ~10μs
2. **Network latency** (to exchange): Kernel bypass + fiber = ~50-200μs one-way
3. **Exchange matching latency**: 10-100μs depending on exchange
4. **Ack propagation**: Same as network latency

**Implementation:**
```rust
struct LatencyModel {
    // Historical latency distribution (from production logs)
    processing_latency_dist: Histogram,
    network_latency_dist: Histogram,
    
    // Current system state affects latency
    cpu_load: f64,  // 0.0 to 1.0
}

impl LatencyModel {
    fn sample_total_latency(&self) -> Duration {
        // Base latency from distributions
        let processing = self.processing_latency_dist.sample();
        let network = self.network_latency_dist.sample();
        
        // Add load-dependent jitter
        let jitter = if self.cpu_load > 0.8 {
            // High load causes tail latency events
            Duration::from_micros(thread_rng().gen_range(0..100))
        } else {
            Duration::from_micros(0)
        };
        
        processing + network + jitter
    }
}
```

---

#### 7.2.3 Market Impact Modeling

Every order moves the market. Large orders have non-linear impact.

**Square-Root Impact Model:**
```rust
fn calculate_market_impact(
    order_size: i64,
    daily_volume: i64,
    volatility: f64,
    spread: f64,
) -> f64 {
    // Empirical model from Kyle (1985), Almgren-Chriss (2000)
    let participation_rate = (order_size as f64) / (daily_volume as f64);
    
    // Temporary impact (moves market during execution)
    let temporary_impact = spread * 0.5 * participation_rate.sqrt();
    
    // Permanent impact (information leakage)
    let permanent_impact = volatility * participation_rate.powf(0.6);
    
    temporary_impact + permanent_impact
}

// Apply to execution
fn execute_with_impact(&mut self, order: Order) -> ExecutionResult {
    let mid_price = (self.best_bid() + self.best_ask()) / 2.0;
    
    let impact_bps = calculate_market_impact(
        order.quantity,
        self.daily_volume,
        self.recent_volatility(),
        self.spread(),
    );
    
    // Adverse price movement
    let executed_price = match order.side {
        Side::Buy => mid_price * (1.0 + impact_bps),
        Side::Sell => mid_price * (1.0 - impact_bps),
    };
    
    // Update book to reflect impact
    self.shift_prices_due_to_impact(order.side, impact_bps);
    
    ExecutionResult {
        price: executed_price,
        quantity: order.quantity,
        slippage: (executed_price - mid_price).abs(),
    }
}
```

---

### 7.3 Walk-Forward Optimization

To combat overfitting, JANUS uses strict temporal splits with walk-forward validation.

**Procedure:**
1. **Training Window:** 6 months of data
2. **Validation Window:** 1 month out-of-sample
3. **Testing Window:** 1 month further out
4. **Roll forward** by 1 month and repeat

```python
import numpy as np
from datetime import datetime, timedelta

class WalkForwardValidator:
    def __init__(
        self,
        data,
        train_months=6,
        val_months=1,
        test_months=1,
        step_months=1,
    ):
        self.data = data
        self.train_months = train_months
        self.val_months = val_months
        self.test_months = test_months
        self.step_months = step_months
    
    def generate_splits(self):
        """Generate non-overlapping train/val/test splits"""
        total_months = self.train_months + self.val_months + self.test_months
        
        start_date = self.data.index[0]
        end_date = self.data.index[-1]
        
        current = start_date
        while current + timedelta(days=30 * total_months) <= end_date:
            train_end = current + timedelta(days=30 * self.train_months)
            val_end = train_end + timedelta(days=30 * self.val_months)
            test_end = val_end + timedelta(days=30 * self.test_months)
            
            train_data = self.data[current:train_end]
            val_data = self.data[train_end:val_end]
            test_data = self.data[val_end:test_end]
            
            yield {
                'train': train_data,
                'val': val_data,
                'test': test_data,
                'period': f"{current.date()} to {test_end.date()}"
            }
            
            # Step forward
            current += timedelta(days=30 * self.step_months)
    
    def cross_validate(self, model_factory):
        """Run walk-forward cross-validation"""
        results = []
        
        for i, split in enumerate(self.generate_splits()):
            print(f"Fold {i}: {split['period']}")
            
            # Train model on training data
            model = model_factory()
            model.fit(split['train'])
            
            # Optimize hyperparameters on validation data
            best_params = model.optimize_hyperparameters(split['val'])
            model.set_params(best_params)
            
            # Evaluate on test data (completely unseen)
            test_metrics = model.evaluate(split['test'])
            
            results.append({
                'fold': i,
                'period': split['period'],
                'metrics': test_metrics,
            })
        
        return results
```

---

### 7.4 Backtesting Metrics (Beyond Sharpe Ratio)

Traditional Sharpe ratio is insufficient for HFT evaluation.

**Comprehensive Metric Suite:**

```python
import pandas as pd
import numpy as np

class HFTBacktestMetrics:
    def __init__(self, trades_df, positions_df, tick_data):
        self.trades = trades_df
        self.positions = positions_df
        self.ticks = tick_data
    
    def calculate_all_metrics(self):
        return {
            # Return metrics
            'total_return': self.total_return(),
            'sharpe_ratio': self.sharpe_ratio(),
            'sortino_ratio': self.sortino_ratio(),
            'calmar_ratio': self.calmar_ratio(),
            
            # Risk metrics
            'max_drawdown': self.max_drawdown(),
            'var_95': self.value_at_risk(0.95),
            'cvar_95': self.conditional_var(0.95),
            'tail_ratio': self.tail_ratio(),
            
            # Execution quality
            'avg_slippage_bps': self.average_slippage(),
            'fill_rate': self.fill_rate(),
            'adverse_selection_ratio': self.adverse_selection(),
            
            # Activity metrics
            'total_trades': len(self.trades),
            'win_rate': self.win_rate(),
            'avg_hold_time_seconds': self.average_hold_time(),
            'turnover': self.turnover(),
            
            # Regime-specific
            'sharpe_in_trending': self.sharpe_by_regime('trending'),
            'sharpe_in_mean_revert': self.sharpe_by_regime('mean_reverting'),
            'sharpe_in_random': self.sharpe_by_regime('random_walk'),
        }
    
    def adverse_selection(self):
        """
        Measure if we're systematically buying high and selling low.
        
        For each trade, check price movement in next N ticks.
        Adverse selection = trades that immediately move against us.
        """
        adverse_count = 0
        
        for _, trade in self.trades.iterrows():
            # Get price N ticks later
            future_ticks = self.ticks[self.ticks['timestamp'] > trade['timestamp']]
            if len(future_ticks) < 10:
                continue
            
            future_price = future_ticks.iloc[9]['mid_price']
            
            # Check if price moved against us
            if trade['side'] == 'buy' and future_price < trade['price']:
                adverse_count += 1
            elif trade['side'] == 'sell' and future_price > trade['price']:
                adverse_count += 1
        
        return adverse_count / len(self.trades)
    
    def average_slippage(self):
        """Average slippage in basis points"""
        slippages = []
        
        for _, trade in self.trades.iterrows():
            # Get mid price at time of trade decision
            decision_mid = self.get_mid_at_time(trade['decision_timestamp'])
            
            # Actual execution price
            execution_price = trade['price']
            
            # Slippage
            slip_bps = abs(execution_price - decision_mid) / decision_mid * 10000
            slippages.append(slip_bps)
        
        return np.mean(slippages)
    
    def sharpe_by_regime(self, regime_name):
        """Calculate Sharpe ratio for specific market regime"""
        # Join trades with regime labels
        trades_with_regime = self.trades.merge(
            self.ticks[['timestamp', 'regime']], 
            on='timestamp'
        )
        
        regime_trades = trades_with_regime[
            trades_with_regime['regime'] == regime_name
        ]
        
        if len(regime_trades) == 0:
            return np.nan
        
        returns = regime_trades['pnl'].values
        return np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252 * 6.5 * 3600)
    
    def tail_ratio(self):
        """Ratio of 95th percentile gain to 5th percentile loss"""
        returns = self.trades['pnl'].values
        p95 = np.percentile(returns, 95)
        p5 = np.percentile(returns, 5)
        return abs(p95 / p5) if p5 != 0 else np.inf
```

---

### 7.5 Historical Data Quality Issues

Real-world tick data is messy. The backtester must handle:

**Common Issues:**
1. **Missing ticks:** Exchange downtime, data feed issues
2. **Duplicate timestamps:** Multiple events at same nanosecond
3. **Crossed markets:** Bid > Ask (should be impossible, but happens in data)
4. **Outlier prices:** "$999999" placeholder values
5. **Sequence gaps:** Lost packets in data collection

**Sanitization Pipeline:**
```python
class TickDataSanitizer:
    def clean_data(self, raw_df):
        df = raw_df.copy()
        
        # 1. Remove obvious outliers
        df = self.remove_price_outliers(df)
        
        # 2. Fix crossed markets
        df = self.uncross_markets(df)
        
        # 3. Interpolate missing ticks
        df = self.fill_gaps(df)
        
        # 4. Remove duplicates
        df = df.drop_duplicates(subset=['timestamp'], keep='first')
        
        # 5. Validate sequence
        df = self.validate_sequence(df)
        
        return df
    
    def remove_price_outliers(self, df):
        """Remove prices more than 3 sigma from rolling mean"""
        rolling_mean = df['mid_price'].rolling(100).mean()
        rolling_std = df['mid_price'].rolling(100).std()
        
        lower_bound = rolling_mean - 3 * rolling_std
        upper_bound = rolling_mean + 3 * rolling_std
        
        mask = (df['mid_price'] >= lower_bound) & (df['mid_price'] <= upper_bound)
        
        removed_count = (~mask).sum()
        if removed_count > 0:
            print(f"Removed {removed_count} outlier prices")
        
        return df[mask]
    
    def uncross_markets(self, df):
        """Fix bid > ask situations"""
        crossed = df['bid'] > df['ask']
        
        if crossed.any():
            print(f"Found {crossed.sum()} crossed markets")
            
            # Use mid price for both
            mid = (df.loc[crossed, 'bid'] + df.loc[crossed, 'ask']) / 2
            df.loc[crossed, 'bid'] = mid - 0.01
            df.loc[crossed, 'ask'] = mid + 0.01
        
        return df
```

---

## 8. Risk Management Architecture

Risk management in JANUS operates at multiple time scales and hierarchical levels. Unlike traditional portfolio management (daily rebalancing), HFT requires microsecond-level risk checks embedded in the hot path.

### 8.1 Pre-Trade Risk Checks

Every order must pass through a gauntlet of risk checks before hitting the wire.

**Check Hierarchy (in order):**

```rust
enum RiskCheckResult {
    Approved,
    Rejected(RiskViolation),
    RequiresReview,  // Edge case - log and continue
}

struct PreTradeRiskEngine {
    position_limits: PositionLimits,
    rate_limits: RateLimits,
    fat_finger_checks: FatFingerDetector,
    pnl_monitor: PnLMonitor,
}

impl PreTradeRiskEngine {
    fn check_order(&self, order: &Order, state: &TradingState) 
        -> RiskCheckResult 
    {
        // Check 1: Basic sanity
        if let Err(e) = self.sanity_check(order) {
            return RiskCheckResult::Rejected(e);
        }
        
        // Check 2: Position limits
        if let Err(e) = self.check_position_limit(order, state) {
            return RiskCheckResult::Rejected(e);
        }
        
        // Check 3: Notional limits
        if let Err(e) = self.check_notional_limit(order, state) {
            return RiskCheckResult::Rejected(e);
        }
        
        // Check 4: Rate limits
        if let Err(e) = self.rate_limits.check(order) {
            return RiskCheckResult::Rejected(e);
        }
        
        // Check 5: Fat finger detection
        if let Err(e) = self.fat_finger_checks.check(order, state) {
            return RiskCheckResult::Rejected(e);
        }
        
        // Check 6: PnL-based limits
        if let Err(e) = self.pnl_monitor.check_order_allowed(order, state) {
            return RiskCheckResult::Rejected(e);
        }
        
        RiskCheckResult::Approved
    }
    
    fn sanity_check(&self, order: &Order) -> Result<(), RiskViolation> {
        // Price must be positive
        if order.price <= 0.0 {
            return Err(RiskViolation::InvalidPrice(order.price));
        }
        
        // Quantity must be positive
        if order.quantity <= 0 {
            return Err(RiskViolation::InvalidQuantity(order.quantity));
        }
        
        // Price must be within collar
        let reference_price = self.get_reference_price(&order.symbol);
        let deviation = (order.price - reference_price).abs() / reference_price;
        
        if deviation > 0.05 {  // 5% collar
            return Err(RiskViolation::PriceCollar {
                order_price: order.price,
                reference_price,
                deviation,
            });
        }
        
        Ok(())
    }
}
```

---

### 8.2 Position and Exposure Limits

**Hierarchical Limits:**

1. **Per-Symbol Limits:** Max shares per instrument
2. **Sector Limits:** Max exposure to correlated instruments
3. **Portfolio Limits:** Max gross/net exposure
4. **Leverage Limits:** Max notional vs capital

```rust
struct PositionLimits {
    // Per-symbol limits
    symbol_max_shares: HashMap<Symbol, i64>,
    symbol_max_notional: HashMap<Symbol, f64>,
    
    // Sector limits (e.g., all tech stocks combined)
    sector_max_notional: HashMap<Sector, f64>,
    
    // Portfolio-wide limits
    max_gross_notional: f64,  // Sum of abs(position values)
    max_net_notional: f64,    // Abs(sum of position values)
    max_leverage: f64,         // Gross / Capital
    
    // Capital
    available_capital: f64,
}

impl PositionLimits {
    fn check_position_limit(
        &self, 
        order: &Order, 
        current_positions: &HashMap<Symbol, i64>
    ) -> Result<(), RiskViolation> {
        
        let current_position = current_positions
            .get(&order.symbol)
            .copied()
            .unwrap_or(0);
        
        let new_position = match order.side {
            Side::Buy => current_position + order.quantity,
            Side::Sell => current_position - order.quantity,
        };
        
        // Check symbol limit
        let symbol_limit = self.symbol_max_shares
            .get(&order.symbol)
            .copied()
            .unwrap_or(10_000);
        
        if new_position.abs() > symbol_limit {
            return Err(RiskViolation::SymbolPositionLimit {
                symbol: order.symbol.clone(),
                current: current_position,
                attempted: new_position,
                limit: symbol_limit,
            });
        }
        
        // Check notional limit
        let notional = (new_position as f64) * order.price;
        let notional_limit = self.symbol_max_notional
            .get(&order.symbol)
            .copied()
            .unwrap_or(1_000_000.0);
        
        if notional.abs() > notional_limit {
            return Err(RiskViolation::NotionalLimit {
                symbol: order.symbol.clone(),
                notional,
                limit: notional_limit,
            });
        }
        
        Ok(())
    }
    
    fn check_portfolio_limits(&self, positions: &HashMap<Symbol, Position>) 
        -> Result<(), RiskViolation> 
    {
        let gross_notional: f64 = positions.values()
            .map(|p| (p.quantity as f64 * p.current_price).abs())
            .sum();
        
        let net_notional: f64 = positions.values()
            .map(|p| p.quantity as f64 * p.current_price)
            .sum();
        
        if gross_notional > self.max_gross_notional {
            return Err(RiskViolation::GrossExposure {
                current: gross_notional,
                limit: self.max_gross_notional,
            });
        }
        
        if net_notional.abs() > self.max_net_notional {
            return Err(RiskViolation::NetExposure {
                current: net_notional,
                limit: self.max_net_notional,
            });
        }
        
        let leverage = gross_notional / self.available_capital;
        if leverage > self.max_leverage {
            return Err(RiskViolation::LeverageLimit {
                current: leverage,
                limit: self.max_leverage,
            });
        }
        
        Ok(())
    }
}
```

---

### 8.3 Dynamic Risk Adjustment

Risk limits should tighten during adverse conditions.

```rust
struct DynamicRiskAdjuster {
    baseline_limits: PositionLimits,
    current_limits: PositionLimits,
    
    // Adjustment factors based on market conditions
    volatility_regime: VolatilityRegime,
    pnl_state: PnLState,
}

impl DynamicRiskAdjuster {
    fn update_limits(&mut self, market_state: &MarketState, pnl: f64) {
        let mut adjustment_factor = 1.0;
        
        // Factor 1: Volatility
        if market_state.volatility > self.baseline_limits.normal_volatility * 2.0 {
            // High volatility - reduce limits by 50%
            adjustment_factor *= 0.5;
            warn!("High volatility detected - tightening limits");
        }
        
        // Factor 2: Drawdown
        if pnl < 0.0 {
            let drawdown_pct = pnl.abs() / self.baseline_limits.available_capital;
            
            if drawdown_pct > 0.05 {  // 5% drawdown
                // For every 1% drawdown, reduce limits by 10%
                adjustment_factor *= (1.0 - drawdown_pct * 2.0).max(0.1);
                warn!("Drawdown {} - reducing limits", drawdown_pct);
            }
        }
        
        // Factor 3: Regime uncertainty
        if market_state.hurst_exponent.is_nan() {
            // Can't classify regime - be very conservative
            adjustment_factor *= 0.2;
            warn!("Regime uncertainty - minimal trading");
        }
        
        // Apply adjustment
        self.current_limits = self.baseline_limits.clone();
        self.current_limits.scale_by(adjustment_factor);
    }
}
```

---

### 8.4 PnL Monitoring and Circuit Breakers

**Real-time PnL tracking:**

```rust
struct PnLMonitor {
    realized_pnl: f64,
    unrealized_pnl: f64,
    
    // Historical tracking
    pnl_history: VecDeque<(Timestamp, f64)>,
    
    // Limits
    max_daily_loss: f64,
    max_drawdown: f64,
    
    // State
    circuit_breaker_triggered: bool,
}

impl PnLMonitor {
    fn update(&mut self, positions: &HashMap<Symbol, Position>, current_prices: &HashMap<Symbol, f64>) {
        // Calculate unrealized PnL
        self.unrealized_pnl = positions.iter()
            .map(|(symbol, pos)| {
                let current_price = current_prices.get(symbol).unwrap_or(&pos.entry_price);
                let pnl = (pos.quantity as f64) * (current_price - pos.entry_price);
                pnl
            })
            .sum();
        
        let total_pnl = self.realized_pnl + self.unrealized_pnl;
        
        // Check circuit breaker conditions
        if total_pnl < -self.max_daily_loss {
            error!("CIRCUIT BREAKER: Daily loss limit exceeded");
            error!("Total PnL: ${:.2}, Limit: ${:.2}", total_pnl, -self.max_daily_loss);
            
            self.trigger_circuit_breaker();
        }
        
        // Check drawdown from high water mark
        let high_water_mark = self.pnl_history.iter()
            .map(|(_, pnl)| pnl)
            .fold(0.0, |a, &b| a.max(b));
        
        let drawdown = high_water_mark - total_pnl;
        
        if drawdown > self.max_drawdown {
            error!("CIRCUIT BREAKER: Max drawdown exceeded");
            error!("Drawdown: ${:.2}, Limit: ${:.2}", drawdown, self.max_drawdown);
            
            self.trigger_circuit_breaker();
        }
        
        // Record history
        self.pnl_history.push_back((get_timestamp(), total_pnl));
        
        // Keep only last hour
        let cutoff = get_timestamp() - 3600_000_000_000; // 1 hour in nanoseconds
        while self.pnl_history.front().map(|(t, _)| *t < cutoff).unwrap_or(false) {
            self.pnl_history.pop_front();
        }
    }
    
    fn trigger_circuit_breaker(&mut self) {
        if self.circuit_breaker_triggered {
            return;  // Already triggered
        }
        
        self.circuit_breaker_triggered = true;
        
        // 1. Stop all trading
        TRADING_ENABLED.store(false, Ordering::Release);
        
        // 2. Cancel all orders
        cancel_all_orders();
        
        // 3. Flatten positions (if configured)
        if FLATTEN_ON_BREACH {
            flatten_all_positions();
        }
        
        // 4. Alert
        send_alert(AlertLevel::Critical, "Circuit breaker triggered - trading halted");
        
        // 5. Log state for forensics
        dump_state_to_disk("/var/log/janus/circuit_breaker_state.json");
    }
    
    fn reset_circuit_breaker(&mut self, authorization: &AdminAuth) {
        // Requires manual authorization
        if !authorization.is_valid() {
            error!("Unauthorized circuit breaker reset attempt");
            return;
        }
        
        warn!("Circuit breaker reset by {}", authorization.user);
        self.circuit_breaker_triggered = false;
        TRADING_ENABLED.store(true, Ordering::Release);
    }
}
```

---

### 8.5 Correlation Risk and Portfolio Hedging

**Correlation-aware risk management:**

```rust
struct CorrelationMatrix {
    // Correlation between symbols
    correlations: HashMap<(Symbol, Symbol), f64>,
    
    // Last update time
    last_calibration: Timestamp,
    calibration_interval: Duration,
}

impl CorrelationMatrix {
    fn calculate_portfolio_var(&self, positions: &HashMap<Symbol, Position>) -> f64 {
        // Portfolio variance accounting for correlations
        let mut var = 0.0;
        
        for (symbol1, pos1) in positions {
            for (symbol2, pos2) in positions {
                let correlation = self.get_correlation(symbol1, symbol2);
                
                let vol1 = self.get_volatility(symbol1);
                let vol2 = self.get_volatility(symbol2);
                
                let cov = correlation * vol1 * vol2;
                
                let notional1 = pos1.quantity as f64 * pos1.current_price;
                let notional2 = pos2.quantity as f64 * pos2.current_price;
                
                var += notional1 * notional2 * cov;
            }
        }
        
        var.sqrt()
    }
    
    fn suggest_hedge(&self, symbol: &Symbol, position: i64) -> Option<HedgeRecommendation> {
        // Find most correlated liquid instrument
        let mut best_hedge = None;
        let mut best_correlation = 0.0;
        
        for other in self.liquid_instruments() {
            if other == *symbol {
                continue;
            }
            
            let corr = self.get_correlation(symbol, &other).abs();
            
            if corr > best_correlation && corr > 0.7 {
                best_correlation = corr;
                best_hedge = Some((other, corr));
            }
        }
        
        best_hedge.map(|(hedge_symbol, corr)| {
            // Calculate hedge ratio using beta
            let beta = self.calculate_beta(symbol, &hedge_symbol);
            let hedge_quantity = -(position as f64 * beta) as i64;
            
            HedgeRecommendation {
                hedge_symbol,
                quantity: hedge_quantity,
                correlation: corr,
                expected_hedge_ratio: beta,
            }
        })
    }
}
```

---

## 9. Production Readiness Checklist

Before deploying JANUS to production, this checklist must be completed.

### 9.1 Performance Validation

- [ ] Tick-to-trade latency P99 < 100μs (measured in production environment)
- [ ] Tick-to-trade latency P99.9 < 1ms
- [ ] Zero allocations on hot path (verified with allocator profiling)
- [ ] Cache miss rate < 1% (measured with perf)
- [ ] Network RTT to exchange < 200μs (measured with ICMP)
- [ ] Ring buffer full events < 0.01% of ticks
- [ ] CPU pinning verified (threads don't migrate cores)
- [ ] NUMA locality verified (memory and CPU on same node)

**Measurement Tools:**
```bash
# Latency profiling
perf record -e cycles,cache-misses,cache-references ./janus
perf report

# Allocation detection
valgrind --tool=massif ./janus

# CPU affinity verification
taskset -cp $(pgrep janus)

# NUMA check
numactl --show
numastat -p $(pgrep janus)
```

---

### 9.2 Correctness Validation

- [ ] Backtests show positive Sharpe on 3+ years of data
- [ ] Walk-forward validation shows consistent returns across regimes
- [ ] No single month with loss > 20% of capital
- [ ] Regime detection accuracy > 70% on validation data
- [ ] Fractal dimension calculation handles edge cases (flat markets, gaps)
- [ ] LTN axiom conflicts detected and logged
- [ ] Position reconciliation 100% accurate in simulation
- [ ] Order state machine handles all exchange message types

---

### 9.3 Risk Management Validation

- [ ] Position limits enforced (tested with deliberate violations)
- [ ] Notional limits enforced
- [ ] Rate limits enforced (order flood protection)
- [ ] Circuit breaker triggers correctly on PnL breach
- [ ] Circuit breaker triggers correctly on drawdown breach
- [ ] Fat finger detection catches extreme orders
- [ ] Network disconnect triggers order cancellation
- [ ] Heartbeat timeout triggers emergency shutdown
- [ ] Clock drift detection works
- [ ] Corrupt price data rejected by sanity checks

**Test Scenarios:**
```rust
#[cfg(test)]
mod risk_tests {
    #[test]
    fn test_position_limit_enforcement() {
        let mut engine = TradingEngine::new();
        engine.set_position_limit("AAPL", 1000);
        
        // Try to exceed limit
        let result = engine.submit_order(Order {
            symbol: "AAPL".into(),
            side: Side::Buy,
            quantity: 1500,
            price: 150.0,
        });
        
        assert!(matches!(result, Err(RiskViolation::PositionLimit(_))));
    }
    
    #[test]
    fn test_circuit_breaker() {
        let mut monitor = PnLMonitor::new();
        monitor.max_daily_loss = 10_000.0;
        
        // Simulate losing trades
        monitor.realized_pnl = -15_000.0;
        monitor.update(&positions, &prices);
        
        assert!(monitor.circuit_breaker_triggered);
        assert!(!TRADING_ENABLED.load(Ordering::Acquire));
    }
}
```

---

### 9.4 Operational Readiness

- [ ] Monitoring dashboard deployed (Grafana/Prometheus)
- [ ] All critical metrics instrumented
- [ ] Alerting configured (PagerDuty/Slack)
- [ ] Runbook documented (incident response procedures)
- [ ] Deployment automation tested (blue-green deployment)
- [ ] Rollback procedure tested
- [ ] Log aggregation configured (ELK/Splunk)
- [ ] Config management secure (encrypted secrets)
- [ ] Backup exchange connection configured
- [ ] Manual kill switch accessible (big red button)

---

### 9.5 Regulatory and Compliance

- [ ] Order tagging compliant with exchange rules
- [ ] Audit trail complete (all orders logged with nanosecond timestamps)
- [ ] Market manipulation safeguards (no quote stuffing, layering)
- [ ] Risk limits comply with regulatory capital requirements
- [ ] Failover procedures documented
- [ ] Business continuity plan approved
- [ ] Code review completed by independent team
- [ ] Security audit completed (penetration testing)

---

## 10. Conclusion

The backtesting and risk management framework for Project JANUS represents a departure from academic machine learning validation. The system must be proven not just to predict well, but to survive in an adversarial, non-stationary environment where microseconds and basis points determine profitability.

**Key Principles:**

1. **Backtests are upper bounds, not predictions:** Real trading will underperform simulations
2. **Risk management is non-negotiable:** Better to miss profits than risk catastrophic loss
3. **Operational failures dominate algorithmic failures:** Most losses are from deployment errors, not bad models
4. **Defense in depth:** Multiple layers of checks prevent single points of failure
5. **Fail-fast is critical:** Stop trading immediately when assumptions are violated

The combination of rigorous backtesting, comprehensive risk controls, and operational discipline provides the foundation for safe deployment of the JANUS neuro-symbolic trading engine.

---

**Document Control:**
- Version: 1.0
- Next Review: Quarterly
- Owner: JANUS Research Team
- Classification: Internal Technical Documentation