# Project JANUS - Production Threat Model
## What Kills HFT Systems in Production?

**Document Version:** 1.0  
**Last Updated:** 2024  
**Classification:** Internal Technical Documentation

---

## Executive Summary

High-frequency trading systems operate in an adversarial environment where microseconds matter and failures cascade instantly. This threat model catalogs the failure modes, attack vectors, and operational hazards that have historically destroyed HFT systems in production. Unlike traditional software, HFT failures are measured not just in downtime, but in catastrophic financial loss—a single bug can lose millions in milliseconds.

**Key Insight:** The majority of HFT failures are not due to clever exploits or sophisticated attacks, but rather mundane operational issues amplified by the extreme speed and leverage of the system.

---

## 1. Threat Categories

We classify threats into five primary categories:

1. **Latency Threats** - Performance degradation that causes missed opportunities or adverse selection
2. **Logic Threats** - Algorithmic errors that result in incorrect trading decisions
3. **Infrastructure Threats** - System failures, network issues, and hardware faults
4. **Market Threats** - Adverse market conditions and exchange-level issues
5. **Operational Threats** - Human error, configuration mistakes, and deployment issues

---

## 2. Latency Threats

### 2.1 Tail Latency Events

**Threat:** P99/P99.9 latency spikes during critical market events.

**Scenario:**
- System averages 10μs tick-to-trade latency
- During volatility spike, GC pause causes 5ms stall
- By the time order reaches exchange, price has moved
- System experiences systematic adverse selection: always buying after price rises, selling after it falls

**Root Causes:**
- Memory allocation on hot path triggering GC
- OS scheduler context switches
- CPU thermal throttling under sustained load
- NUMA node boundary crossings
- Cache line invalidation cascades

**Mitigation:**
```rust
// Zero-allocation policy enforcement
#![no_std]  // For critical components
#![forbid(unsafe_code)]  // Except in audited ring buffer

// Pre-allocate all data structures at startup
const RING_SIZE: usize = 4096;
static mut INGRESS_RING: [Tick; RING_SIZE] = [Tick::default(); RING_SIZE];

// CPU pinning with isolation
use core_affinity;
fn pin_thread_to_core(core_id: usize) {
    let core = CoreId { id: core_id };
    core_affinity::set_for_current(core);
}

// Disable frequency scaling
// Set in systemd service:
// CPUAffinity=1-4
// CPUQuota=400%  # 4 cores @ 100%
```

**Detection:**
- Continuous latency histogram recording (using lock-free atomic counters)
- Alert on P99 > 2x median
- Automatic circuit breaker if P99.9 > 1ms for 10 consecutive windows

---

### 2.2 Cache Coherency Storms

**Threat:** False sharing between threads causes cache line ping-pong.

**Scenario:**
```rust
// BAD: Producer and Consumer on same cache line
struct RingBuffer {
    head: AtomicUsize,  // Modified by Producer on Core 1
    tail: AtomicUsize,  // Modified by Consumer on Core 2
    // On x86-64, if these are in same 64-byte cache line,
    // every write causes MESI protocol cache invalidation
}
```

**Impact:**
- Latency increases from 50ns to 500ns per operation
- Throughput drops by 10x during high-frequency updates

**Mitigation:**
```rust
#[repr(C, align(64))]
struct PaddedHead {
    value: AtomicUsize,
    _padding: [u8; 56],
}

#[repr(C, align(64))]
struct PaddedTail {
    value: AtomicUsize,
    _padding: [u8; 56],
}

struct RingBuffer {
    head: PaddedHead,
    tail: PaddedTail,
    // Now on separate cache lines
}

// Verify at compile time
static_assertions::const_assert_eq!(
    std::mem::size_of::<PaddedHead>(), 64
);
```

---

### 2.3 Network Kernel Bypass Failures

**Threat:** Fallback to kernel networking during DPDK/Solarflare failure.

**Scenario:**
- DPDK interface experiences packet loss
- System falls back to standard socket()
- Latency increases from 2μs to 200μs
- System becomes non-competitive but continues trading at bad prices

**Mitigation:**
- **Hard Fail:** Never fallback to kernel network
- Implement dead man's switch: kill all orders if network latency > threshold
- Redundant NICs on separate PCIe buses
- Continuous RTT monitoring to exchange

```rust
const MAX_NETWORK_RTT_US: u64 = 100;

if measured_rtt > MAX_NETWORK_RTT_US {
    emergency_shutdown("Network latency exceeded threshold");
    cancel_all_orders();
    std::process::exit(1);
}
```

---

## 3. Logic Threats

### 3.1 The Knight Capital Disaster (Fat Finger Amplification)

**Historical Case Study (2012):**
- Knight Capital deployed new trading software
- Old code flag `POWER PEG` was repurposed
- System entered infinite loop buying at ask, selling at bid
- Lost $440 million in 45 minutes
- Company bankrupt

**Threat:** Unconstrained position accumulation due to logic error.

**Mitigation - Position Limits:**
```rust
struct PositionManager {
    current_position: AtomicI64,
    max_position: i64,
    max_notional: f64,
    
    // Per-symbol limits
    symbol_limits: HashMap<Symbol, Limits>,
}

impl PositionManager {
    fn check_order(&self, order: &Order) -> Result<(), RiskError> {
        let new_position = self.current_position.load(Ordering::Acquire) 
                         + order.quantity;
        
        // Hard limit checks
        if new_position.abs() > self.max_position {
            error!("POSITION LIMIT BREACH: {} > {}", 
                   new_position, self.max_position);
            return Err(RiskError::PositionLimit);
        }
        
        let notional = new_position as f64 * order.price;
        if notional.abs() > self.max_notional {
            error!("NOTIONAL LIMIT BREACH: {} > {}", 
                   notional, self.max_notional);
            return Err(RiskError::NotionalLimit);
        }
        
        Ok(())
    }
}
```

**Kill Switch:**
```rust
// Independent risk monitoring thread
fn risk_monitor_thread() {
    loop {
        let pnl = calculate_realized_pnl() + calculate_unrealized_pnl();
        
        // Immediate kill if daily loss exceeds threshold
        if pnl < -MAX_DAILY_LOSS {
            EMERGENCY_STOP.store(true, Ordering::Release);
            cancel_all_orders();
            flatten_all_positions();
            
            // Hard exit - don't trust shutdown procedures
            unsafe { libc::_exit(1); }
        }
        
        std::thread::sleep(Duration::from_millis(100));
    }
}
```

---

### 3.2 Regime Detection Failure

**Threat:** Fractal dimension calculation produces NaN/Inf during extreme events.

**Scenario:**
- Flash crash: prices gap down 10%
- Sevcik algorithm encounters division by zero (P_max == P_min for flat window)
- Hurst exponent becomes NaN
- FRAMA alpha becomes NaN
- All subsequent calculations corrupted

**Mitigation:**
```rust
fn calculate_sevcik_dimension(&self) -> Result<f64, FractalError> {
    let p_min = self.min_tracker.get_value()
        .ok_or(FractalError::InsufficientData)?;
    let p_max = self.max_tracker.get_value()
        .ok_or(FractalError::InsufficientData)?;
    
    let price_range = p_max - p_min;
    
    // Explicit handling of degenerate cases
    if price_range < f64::EPSILON {
        warn!("Flat price window detected - using default D=1.5");
        return Ok(1.5);  // Neutral assumption
    }
    
    if price_range.is_nan() || price_range.is_infinite() {
        error!("Invalid price range: {}", price_range);
        return Err(FractalError::InvalidRange);
    }
    
    // ... rest of calculation with bounds checking
    
    let D = calculate_dimension(normalized_prices);
    
    // Sanity check output
    if D < 1.0 || D > 2.0 || D.is_nan() {
        error!("Invalid fractal dimension: {}", D);
        return Err(FractalError::InvalidDimension(D));
    }
    
    Ok(D)
}

// Consumer must handle errors
match self.fractal_calc.update(price) {
    Ok((D, H)) => { /* use values */ }
    Err(e) => {
        // Use safe fallback - don't trade on corrupt data
        self.pause_trading();
        error!("Fractal calculation failed: {:?}", e);
    }
}
```

---

### 3.3 Logic Tensor Network Axiom Conflicts

**Threat:** LTN axioms produce contradictory signals during market regime transitions.

**Scenario:**
- Trend Axiom: "If H > 0.6 AND price > FRAMA ⟹ Bullish"
- Mean Reversion Axiom: "If RSI > 80 ⟹ NOT Bullish"
- During strong trend, both conditions true simultaneously
- Reichenbach implication evaluates to conflicting truth values
- Network outputs degenerate predictions

**Mitigation:**
```rust
// Hierarchical axiom evaluation with confidence scoring
struct AxiomEvaluator {
    axioms: Vec<(Axiom, Priority, Weight)>,
}

impl AxiomEvaluator {
    fn evaluate(&self, state: &MarketState) -> Decision {
        let mut weighted_votes = Vec::new();
        
        for (axiom, priority, weight) in &self.axioms {
            let satisfaction = axiom.evaluate(state);
            
            // Only trust axioms with high satisfaction
            if satisfaction > 0.7 {
                weighted_votes.push((axiom.conclusion, weight * satisfaction));
            }
        }
        
        // If no strong signals, abstain from trading
        if weighted_votes.is_empty() {
            return Decision::NoTrade;
        }
        
        // Conflict detection
        let bullish_weight: f64 = weighted_votes.iter()
            .filter(|(d, _)| *d == Conclusion::Bullish)
            .map(|(_, w)| w)
            .sum();
            
        let bearish_weight: f64 = weighted_votes.iter()
            .filter(|(d, _)| *d == Conclusion::Bearish)
            .map(|(_, w)| w)
            .sum();
        
        // Require clear winner (not close to tie)
        let margin = (bullish_weight - bearish_weight).abs();
        if margin < MIN_CONFIDENCE_MARGIN {
            warn!("Axiom conflict: bullish={}, bearish={}", 
                  bullish_weight, bearish_weight);
            return Decision::NoTrade;
        }
        
        // Return decision with confidence metric
        Decision::with_confidence(
            if bullish_weight > bearish_weight { 
                Conclusion::Bullish 
            } else { 
                Conclusion::Bearish 
            },
            margin
        )
    }
}
```

---

## 4. Infrastructure Threats

### 4.1 Network Partition / Exchange Disconnect

**Threat:** Loss of market data feed while orders remain active.

**Scenario:**
- System places limit orders on exchange
- Network cable unplugged (fiber cut, switch failure, etc.)
- Market moves significantly
- System has no visibility into order fills
- Potential for massive unhedged position

**Mitigation:**
```rust
struct ConnectionMonitor {
    last_heartbeat: AtomicU64,  // Timestamp in nanoseconds
    heartbeat_interval_ns: u64,
}

impl ConnectionMonitor {
    fn check_health(&self) -> Result<(), ConnectionError> {
        let now = get_timestamp_ns();
        let last = self.last_heartbeat.load(Ordering::Acquire);
        
        let elapsed = now - last;
        
        // Conservative threshold: 2x expected interval
        if elapsed > 2 * self.heartbeat_interval_ns {
            error!("Exchange heartbeat timeout: {}ms", 
                   elapsed / 1_000_000);
            
            // CRITICAL: Cancel all orders IMMEDIATELY
            // Don't wait for graceful shutdown
            self.emergency_cancel_all();
            
            return Err(ConnectionError::HeartbeatTimeout);
        }
        
        Ok(())
    }
    
    fn emergency_cancel_all(&self) {
        // Send cancel via ALL available paths
        // (primary connection, backup connection, REST API, phone call to desk)
        
        // 1. TCP FIX connection
        self.fix_session.cancel_all_orders();
        
        // 2. Backup REST API
        self.rest_client.cancel_all_orders();
        
        // 3. Write to disk for manual recovery
        std::fs::write(
            "/var/run/janus/EMERGENCY_CANCEL.flag",
            format!("CANCEL ALL ORDERS - Connection lost at {}", now())
        );
        
        // 4. Alert monitoring system
        self.alerting.page_oncall("EXCHANGE DISCONNECT - MANUAL INTERVENTION REQUIRED");
    }
}
```

**Dead Man's Switch:**
Exchange-side protection (if supported):
```
# Configure orders with Time-In-Force = IOC or FOK
# Or use exchange-side "drop copy kill switch"
# Example: CME's CANCEL ON DISCONNECT feature
```

---

### 4.2 Clock Synchronization Failure

**Threat:** System clock drift causes timestamp-based logic errors.

**Scenario:**
- NTP daemon fails
- System clock drifts forward by 10 seconds
- Time-based order expiration logic fires prematurely
- Or worse: clock drifts backward, breaking causality assumptions

**Mitigation:**
```rust
// Use monotonic clock for intervals, wall clock only for logging
use std::time::Instant;  // Monotonic, never goes backward

struct TimestampValidator {
    last_wall_clock: AtomicU64,
    max_drift_ns: u64,
}

impl TimestampValidator {
    fn validate_timestamp(&self, ts: u64) -> Result<u64, ClockError> {
        let last = self.last_wall_clock.load(Ordering::Acquire);
        
        // Check for backward time travel
        if ts < last {
            error!("CLOCK WENT BACKWARD: {} -> {}", last, ts);
            return Err(ClockError::BackwardJump);
        }
        
        // Check for forward jump (NTP correction)
        let delta = ts - last;
        if delta > self.max_drift_ns {
            error!("CLOCK JUMPED FORWARD: delta={}ms", delta / 1_000_000);
            return Err(ClockError::ForwardJump);
        }
        
        self.last_wall_clock.store(ts, Ordering::Release);
        Ok(ts)
    }
}

// Monitor NTP sync status
fn check_ntp_health() -> Result<(), ClockError> {
    let output = std::process::Command::new("chronyc")
        .arg("tracking")
        .output()?;
    
    // Parse output and check offset
    // Alert if offset > 1ms
}
```

---

### 4.3 Filesystem Full / Logging Failure

**Threat:** Disk fills up, logger blocks, system hangs.

**Scenario:**
- High-frequency logging during volatility
- `/var/log` partition fills
- Logger thread blocks on write()
- Lock contention propagates to trading threads
- System freezes

**Mitigation:**
```rust
// NEVER block trading on logging
use crossbeam::channel;

fn logging_thread() {
    let (tx, rx) = channel::bounded(10_000);  // Fixed size
    
    loop {
        match rx.try_recv() {
            Ok(msg) => {
                // Best effort write - don't care if it fails
                let _ = writeln!(log_file, "{}", msg);
            }
            Err(TryRecvError::Empty) => {
                std::thread::sleep(Duration::from_micros(100));
            }
            Err(TryRecvError::Disconnected) => break,
        }
    }
}

// Trading thread
fn log_trade(msg: String) {
    // Non-blocking send
    match log_tx.try_send(msg) {
        Ok(_) => {}
        Err(_) => {
            // Channel full - drop message, DON'T BLOCK
            DROPPED_LOGS.fetch_add(1, Ordering::Relaxed);
        }
    }
}
```

**Monitoring:**
- Alert if dropped logs > 1% of total
- Automatic log rotation with size limits
- Separate partition for logs (not same as root)

---

## 5. Market Threats

### 5.1 Flash Crash / Liquidity Vacuum

**Threat:** Market liquidity disappears, system unable to exit positions.

**Historical Example:** May 6, 2010 Flash Crash
- Dow Jones dropped 1000 points in minutes
- HFT firms withdrew liquidity
- Market makers unable to hedge

**Mitigation:**
```rust
struct VolatilityCircuitBreaker {
    baseline_volatility: f64,
    volatility_multiplier_threshold: f64,
}

impl VolatilityCircuitBreaker {
    fn check(&self, current_volatility: f64) -> CircuitBreakerState {
        if current_volatility > self.baseline_volatility * self.volatility_multiplier_threshold {
            warn!("VOLATILITY SPIKE: {}x baseline", 
                  current_volatility / self.baseline_volatility);
            
            // Immediately:
            // 1. Stop opening new positions
            // 2. Widen quote spreads
            // 3. Reduce position sizes
            // 4. Increase Hurst window (more conservative)
            
            CircuitBreakerState::FlashCrashMode
        } else {
            CircuitBreakerState::Normal
        }
    }
}

// Order book liquidity check
fn check_liquidity_depth(&self, symbol: &Symbol) -> bool {
    let book = self.get_order_book(symbol);
    
    // Check if we can execute our typical order size
    // without moving market significantly
    let bid_depth = book.bids.iter()
        .take(5)  // Top 5 levels
        .map(|level| level.quantity)
        .sum();
    
    let min_required_depth = self.typical_order_size * 10;
    
    if bid_depth < min_required_depth {
        warn!("THIN BOOK: {} only has {} shares at bid", 
              symbol, bid_depth);
        return false;
    }
    
    true
}
```

---

### 5.2 Exchange Halts / Trading Pauses

**Threat:** Stock halted while system holds position.

**Scenario:**
- System is long 10,000 shares
- Exchange halts trading (news pending, volatility)
- Cannot exit position for 5-30 minutes
- Price reopens significantly lower

**Mitigation:**
```rust
// Subscribe to regulatory halt messages
fn handle_halt_message(&mut self, symbol: Symbol) {
    warn!("TRADING HALT: {}", symbol);
    
    // 1. Cancel all pending orders for this symbol
    self.cancel_all_orders_for_symbol(&symbol);
    
    // 2. Mark position as frozen
    self.frozen_positions.insert(symbol);
    
    // 3. Calculate hedge in correlated instruments
    //    (e.g., if AAPL halted, hedge with QQQ)
    if let Some(hedge) = self.calculate_hedge(&symbol) {
        self.place_hedge_order(hedge);
    }
    
    // 4. Alert risk desk
    self.alert("Position frozen due to halt", &symbol);
}
```

---

### 5.3 Erroneous Exchange Data (Broken Quotes)

**Threat:** Exchange sends corrupt price data, system trades on it.

**Historical Example:** BATS "Apple for $100,000" (2012)

**Mitigation:**
```rust
struct PriceSanityChecker {
    last_valid_price: f64,
    max_price_change_percent: f64,
}

impl PriceSanityChecker {
    fn validate_price(&mut self, new_price: f64) -> Result<f64, DataError> {
        // Check for obviously invalid values
        if new_price <= 0.0 || new_price.is_nan() || new_price.is_infinite() {
            error!("INVALID PRICE: {}", new_price);
            return Err(DataError::InvalidPrice);
        }
        
        // Check for unrealistic moves
        if self.last_valid_price > 0.0 {
            let change_pct = ((new_price - self.last_valid_price) / self.last_valid_price).abs();
            
            if change_pct > self.max_price_change_percent {
                error!("SUSPICIOUS PRICE MOVE: {} -> {} ({:.1}%)",
                       self.last_valid_price, new_price, change_pct * 100.0);
                
                // Don't update last_valid_price - keep using old price
                // until we get confirmation this is real
                return Err(DataError::SuspiciousMove);
            }
        }
        
        self.last_valid_price = new_price;
        Ok(new_price)
    }
}

// Cross-exchange validation
fn validate_against_other_venues(&self, symbol: &Symbol, price: f64) -> bool {
    let prices_from_other_exchanges = self.get_prices_from_backup_feeds(symbol);
    
    for other_price in prices_from_other_exchanges {
        let diff = (price - other_price).abs() / other_price;
        if diff > 0.01 {  // More than 1% difference
            warn!("Price mismatch across venues: {} vs {}", price, other_price);
            return false;
        }
    }
    
    true
}
```

---

## 6. Operational Threats

### 6.1 Deployment Errors (Rolling Update Gone Wrong)

**Threat:** New code deployed with bug, old version unavailable.

**Mitigation:**
```bash
#!/bin/bash
# Blue-Green Deployment Script

# 1. Deploy new version alongside old
deploy_new_version() {
    # New binary runs on different port
    ./janus-v2 --port 9091 &
    NEW_PID=$!
    
    # Health check
    sleep 5
    if ! check_health localhost:9091; then
        echo "HEALTH CHECK FAILED"
        kill $NEW_PID
        exit 1
    fi
}

# 2. Canary testing (small % of traffic)
canary_test() {
    # Send 1% of symbols to new version
    # Monitor error rates, latency, PnL
    
    for i in {1..60}; do
        if check_canary_metrics; then
            echo "Canary healthy: $i/60 minutes"
            sleep 60
        else
            echo "CANARY FAILURE - ROLLBACK"
            switch_to_old_version
            exit 1
        fi
    done
}

# 3. Full cutover with instant rollback capability
switch_to_new_version() {
    # Keep old version running for 5 minutes
    OLD_PID=$(pgrep janus-v1)
    
    # Atomically switch traffic
    update_load_balancer --new-backend localhost:9091
    
    # Watch for issues
    sleep 300
    
    if check_production_metrics; then
        echo "Migration successful"
        kill $OLD_PID
    else
        echo "EMERGENCY ROLLBACK"
        update_load_balancer --new-backend localhost:9090
        kill $NEW_PID
    fi
}
```

---

### 6.2 Configuration Errors

**Threat:** Typo in config file causes catastrophic behavior.

**Example:**
```toml
# Intended:
max_position_size = 1000

# Typo:
max_position_size = 1000000
```

**Mitigation:**
```rust
use serde::{Deserialize, Serialize};
use validator::{Validate, ValidationError};

#[derive(Debug, Deserialize, Validate)]
struct TradingConfig {
    #[validate(range(min = 1, max = 10_000))]
    max_position_size: i64,
    
    #[validate(range(min = 0.0, max = 1_000_000.0))]
    max_notional: f64,
    
    #[validate(custom = "validate_symbol")]
    symbol: String,
}

fn validate_symbol(symbol: &str) -> Result<(), ValidationError> {
    // Only allow known symbols
    if ALLOWED_SYMBOLS.contains(symbol) {
        Ok(())
    } else {
        Err(ValidationError::new("Unknown symbol"))
    }
}

// Load config with validation
fn load_config(path: &str) -> Result<TradingConfig, ConfigError> {
    let contents = std::fs::read_to_string(path)?;
    let config: TradingConfig = toml::from_str(&contents)?;
    
    // Validate before returning
    config.validate()?;
    
    // Additional semantic checks
    if config.max_notional < config.max_position_size as f64 * MIN_EXPECTED_PRICE {
        return Err(ConfigError::InconsistentLimits);
    }
    
    Ok(config)
}

// Two-person verification for production configs
fn verify_config_change(old: &TradingConfig, new: &TradingConfig) {
    println!("Configuration Changes:");
    if old.max_position_size != new.max_position_size {
        println!("  max_position_size: {} -> {}", 
                 old.max_position_size, new.max_position_size);
    }
    
    println!("\nType 'CONFIRM' to proceed:");
    let mut input = String::new();
    std::io::stdin().read_line(&mut input).unwrap();
    
    if input.trim() != "CONFIRM" {
        eprintln!("Configuration change aborted");
        std::process::exit(1);
    }
}
```

---

### 6.3 Monitoring Blind Spots

**Threat:** Critical metric not monitored, issue goes undetected.

**Mitigation - Comprehensive Metrics:**
```rust
struct JanusMetrics {
    // Latency metrics
    tick_to_decision_latency_us: Histogram,
    decision_to_order_latency_us: Histogram,
    order_to_ack_latency_us: Histogram,
    
    // Throughput metrics
    ticks_processed_per_second: Counter,
    orders_sent_per_second: Counter,
    fills_received_per_second: Counter,
    
    // Quality metrics
    fractal_calculation_errors: Counter,
    ltn_axiom_conflicts: Counter,
    price_sanity_check_failures: Counter,
    
    // Financial metrics
    realized_pnl: Gauge,
    unrealized_pnl: Gauge,
    current_position: Gauge,
    trade_count: Counter,
    
    // System health
    cpu_usage_percent: Gauge,
    memory_usage_bytes: Gauge,
    network_packets_dropped: Counter,
    ring_buffer_full_events: Counter,
    
    // Risk metrics
    max_drawdown: Gauge,
    sharpe_ratio: Gauge,
    var_95: Gauge,  // Value at Risk
}

// Automatic anomaly detection
fn check_metrics_health(metrics: &JanusMetrics) -> HealthStatus {
    let mut issues = Vec::new();
    
    // Example checks
    if metrics.tick_to_decision_latency_us.percentile(0.99) > 100.0 {
        issues.push("P99 latency elevated");
    }
    
    if metrics.price_sanity_check_failures.get() > 0 {
        issues.push("Data quality issues detected");
    }
    
    if metrics.unrealized_pnl.get() < -MAX_DRAWDOWN {
        issues.push("CRITICAL: Max drawdown exceeded");
    }
    
    if issues.is_empty() {
        HealthStatus::Healthy
    } else {
        HealthStatus::Degraded(issues)
    }
}
```

---

## 7. Defense in Depth Strategy

### 7.1 Pre-Trade Risk Checks (Layered)

```rust
fn validate_order(order: &Order) -> Result<(), RiskError> {
    // Layer 1: Basic sanity
    basic_sanity_check(order)?;
    
    // Layer 2: Position limits
    position_limit_check(order)?;
    
    // Layer 3: Notional limits
    notional_limit_check(order)?;
    
    // Layer 4: Rate limits (don't flood exchange)
    rate_limit_check(order)?;
    
    // Layer 5: Market conditions
    market_condition_check(order)?;
    
    // Layer 6: Price collar (don't buy at crazy price)
    price_collar_check(order)?;
    
    Ok(())
}
```

### 7.2 Post-Trade Reconciliation

```rust
// Run every 1 second
fn reconciliation_loop() {
    loop {
        // Compare our position view vs exchange confirmation
        for symbol in active_symbols {
            let our_position = state.get_position(symbol);
            let exchange_position = query_exchange_position(symbol);
            
            if our_position != exchange_position {
                error!("POSITION MISMATCH: {} our={} exchange={}", 
                       symbol, our_position, exchange_position);
                
                // Halt trading immediately
                emergency_stop();
                
                // Manual reconciliation required
                alert_ops_team();
            }
        }
        
        std::thread::sleep(Duration::from_secs(1));
    }
}
```

---

## 8. Testing for Production Threats

### 8.1 Chaos Engineering

```rust
// Inject failures during testing
#[cfg(test)]
mod chaos {

    fn inject_latency_spike() {
        if random() < CHAOS_PROBABILITY {
            std::thread::sleep(Duration::from_millis(10));
        }
    }
    
    fn inject_network_partition() {
        if random() < CHAOS_PROBABILITY {
            return Err(NetworkError::Timeout);
        }
    }
    
    fn inject_corrupted_data() {
        if random() < CHAOS_PROBABILITY {
            return f64::NAN;
        }
    }
}
```

### 8.2 Load Testing

- Replay historical high-volatility days (flash crash, etc.)
- Inject 10x normal message rate
- Verify no allocations occur under load
- Check tail latency remains bounded

---

## 9. Incident Response Playbook

### When Things Go Wrong

**Level 1: Performance Degradation**
1. Check latency dashboard
2. Inspect per-thread CPU usage
3. Review system logs for errors
4. If P99 > threshold, reduce position sizes

**Level 2: Logic Anomaly**
1. Check PnL trend (should be stable, not monotonic loss)
2. Review recent trades for pattern
3. If systematic adverse selection detected, halt trading
4. Investigate fractal dimension / Hurst exponent values

**Level 3: Financial Loss**
1. IMMEDIATELY flatten all positions
2. Cancel all pending orders
3. Alert executive team
4. Preserve all logs and state for forensics
5. Do NOT restart system (preserves evidence)

**Level 4: Complete Failure**
1. Kill switch activated
2. Manual intervention at exchange level
3. Contact exchange help desk
4. Regulatory notification (if required)

---

## 10. Monitoring Dashboard - Critical Metrics

**Real-time Display (Update every 100ms):**

```
┌─ Project JANUS Health ────────────────────────────────────────┐
│ Status: ●TRADING   Uptime: 04:23:15   Last Update: 12:34:56.789│
├───────────────────────────────────────────────────────────────┤
│ LATENCY (μs)      P50    P99    P99.9   Max                   │
│ Tick→Decision     8.2    15.3   23.1    45.2                  │
│ Decision→Order    2.1    4.5    8.9     12.3                  │
│ Order→Ack         45.2   89.3   145.2   234.5                 │
├───────────────────────────────────────────────────────────────┤
│ FINANCIAL                                                      │
│ Realized PnL:     +$12,345.67                                 │
│ Unrealized PnL:   -$234.56                                    │
│ Position:         SPY +1,250 shares                           │
│ Max Drawdown:     -$1,023.45 (8.2% of daily limit)           │
├───────────────────────────────────────────────────────────────┤
│ SYSTEM                                                         │
│ Msg Rate:         45,234 msg/sec                              │
│ CPU (Core 3):     87% (inference thread)                      │
│ Ring Buffer:      34% full (Ingress)                          │
│ Dropped Logs:     12 (0.001%)                                 │
├───────────────────────────────────────────────────────────────┤
│ MARKET                                                         │
│ Hurst Exponent:   0.72 (TRENDING)                            │
│ Fractal Dim:      1.28                                        │
│ FRAMA Alpha:      0.32                                        │
│ Bid-Ask Spread:   0.01 (normal)                              │
└───────────────────────────────────────────────────────────────┘

⚠ WARNINGS: None
🔴 ALERTS: None
```

---

## 11. Conclusion

The threat model for HFT systems is fundamentally different from traditional software:

1. **Speed kills:** Microseconds matter, so defensive programming cannot add latency
2. **Fail-fast is critical:** Better to stop trading than trade incorrectly
3. **Financial loss is irreversible:** Cannot "roll back" trades
4. **Monitoring must be comprehensive:** Blind spots are fatal
5. **Human intervention is too slow:** Automated circuit breakers are mandatory

**The JANUS system must be designed with the assumption that every component will fail.** The question is not "if" but "when" and "how do we contain the blast radius?"

---

## Appendix A: Historical HFT Failures

| Date | Company | Failure Mode | Loss | Root Cause |
|------|---------|--------------|------|------------|
| 2012-08-01 | Knight Capital | Logic error (infinite loop) | $440M | Deployment error, old flag reused |
| 2010-05-06 | Multiple | Flash crash liquidity withdrawal | Billions | Cascading algorithm failures |
| 2013-08-22 | Goldman Sachs | Erroneous orders | $-100M+ | Configuration error |
| 2016-10-04 | Multiple | Sterling crash (GBP) | N/A | Thin liquidity, algorithm cascade |

**Key Takeaway:** Most failures are operational (deployment, config) not algorithmic.

---

**Document Control:**
- Review frequency: Quarterly
- Owner: JANUS Risk Committee
- Next review: Q1 2025
