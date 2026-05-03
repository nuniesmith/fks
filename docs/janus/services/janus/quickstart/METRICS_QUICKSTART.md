# JANUS Metrics - Quick Reference Guide

Quick reference for using Prometheus metrics in JANUS.

---

## 🚀 Quick Start

### 1. Create Metrics Collector

```rust
use janus::metrics::JanusMetrics;
use std::sync::Arc;

// Create metrics
let metrics = Arc::new(JanusMetrics::new()?);
```

### 2. Start Prometheus Server

```rust
use janus::metrics::start_metrics_server;

// Start on port 9090
let handle = start_metrics_server(Arc::clone(&metrics), 9090).await;

// Metrics available at: http://localhost:9090/metrics
// Health check at: http://localhost:9090/health
```

### 3. Record Metrics

```rust
// System metrics
metrics.system_metrics().record_http_request(0.05);

// Signal metrics
metrics.signal_metrics().record_signal_generated(
    "BTC/USD", "1h", "BUY", 0.85, 0.75
);

// Risk metrics
metrics.risk_metrics().record_position_size(
    0.1, 5000.0, 100.0, 0.01, 0.0001
);
```

---

## 📊 Available Metrics

### System Metrics

```rust
let sys = metrics.system_metrics();

// Requests
sys.record_http_request(duration_secs);
sys.record_grpc_request(duration_secs);

// Errors
sys.record_error();

// System state
sys.update_uptime(seconds);
sys.set_active_connections(count);
sys.update_memory_usage(bytes);
```

**Prometheus Metrics:**
- `janus_http_requests_total` - Total HTTP requests
- `janus_grpc_requests_total` - Total gRPC requests
- `janus_http_request_duration_seconds` - HTTP latency histogram
- `janus_grpc_request_duration_seconds` - gRPC latency histogram
- `janus_errors_total` - Total errors
- `janus_error_rate` - Error rate gauge
- `janus_uptime_seconds` - Service uptime
- `janus_active_connections` - Active connections
- `janus_memory_usage_bytes` - Memory usage

---

### Signal Metrics

```rust
let sig = metrics.signal_metrics();

// Signal generation
sig.record_signal_generated(symbol, timeframe, signal_type, confidence, strength);
sig.record_signal_filtered();
sig.record_signal_actionable();

// Quality
sig.update_signal_quality(avg_confidence, avg_strength);

// Source tracking
sig.record_signal_source(source_type);

// Performance
sig.record_generation_duration(duration_secs);
sig.record_validation_duration(duration_secs);

// Cache
sig.record_cache_hit();
sig.record_cache_miss();
sig.update_cache_size(size);

// Batch processing
sig.record_batch_processing(batch_size, duration_secs);

// ML inference
sig.record_ml_signal(inference_duration_secs, confidence);

// Strategy
sig.record_strategy_execution(strategy_name, duration_secs);

// Errors
sig.record_generation_error();
sig.record_validation_error();
```

**Prometheus Metrics:**
- `janus_signals_generated_total{symbol,timeframe,signal_type}` - Total signals
- `janus_signals_filtered_total` - Signals filtered out
- `janus_signals_actionable_total` - Actionable signals
- `janus_signal_confidence_avg` - Average confidence
- `janus_signal_strength_avg` - Average strength
- `janus_signal_confidence` - Confidence histogram
- `janus_signal_strength` - Strength histogram
- `janus_signals_by_type{signal_type}` - Signals by type
- `janus_signals_by_source{source_type}` - Signals by source
- `janus_signals_by_timeframe{timeframe}` - Signals by timeframe
- `janus_signal_generation_duration_seconds` - Generation latency
- `janus_signal_validation_duration_seconds` - Validation latency
- `janus_signal_cache_hits_total` - Cache hits
- `janus_signal_cache_misses_total` - Cache misses
- `janus_signal_cache_size` - Cache size
- `janus_signal_batch_size` - Batch size histogram
- `janus_signal_batch_processing_duration_seconds` - Batch processing time
- `janus_ml_signals_total` - ML-generated signals
- `janus_ml_inference_duration_seconds` - ML inference time
- `janus_ml_confidence_avg` - ML confidence average
- `janus_strategy_signals_total{strategy_name}` - Strategy signals
- `janus_strategy_execution_duration_seconds` - Strategy execution time
- `janus_signal_generation_errors_total` - Generation errors
- `janus_signal_validation_errors_total` - Validation errors

---

### Risk Metrics

```rust
let risk = metrics.risk_metrics();

// Position sizing
risk.record_position_size(quantity, value, risk_amount, risk_pct, duration_secs);
risk.update_position_averages(avg_size, avg_risk_amount, avg_risk_pct);

// Stop loss
risk.record_stop_loss(distance, duration_secs);
risk.update_stop_loss_avg(avg_distance);

// Take profit
risk.record_take_profit(distance);
risk.update_take_profit_avg(avg_distance);

// Risk/Reward
risk.record_risk_reward(ratio);
risk.update_risk_reward_avg(avg_ratio);

// Portfolio
risk.update_portfolio_metrics(
    heat,
    exposure,
    exposure_pct,
    position_count,
    concentration,
    diversification
);

// Limit violations
risk.record_position_limit_violation(limit_type);
risk.record_daily_loss_limit_violation();
risk.record_portfolio_exposure_violation();
risk.record_symbol_exposure_violation(symbol);

// Performance
risk.update_performance_metrics(
    total_trades,
    wins,
    losses,
    win_rate,
    profit_factor,
    avg_win,
    avg_loss,
    expected_value
);

// Drawdown
risk.update_drawdown_metrics(
    current_dd,
    current_dd_pct,
    max_dd,
    max_dd_pct,
    duration
);

// Advanced
risk.update_kelly_fraction(fraction);
risk.update_sharpe_ratio(ratio);

// Validation
risk.record_risk_validation(duration_secs);
risk.record_risk_calculation_error();
risk.record_risk_validation_error(error_type);
```

**Prometheus Metrics:**
- `janus_position_sizes_calculated_total` - Position sizes calculated
- `janus_position_size_avg` - Average position size
- `janus_position_size` - Position size histogram
- `janus_position_value` - Position value histogram
- `janus_risk_amount_avg` - Average risk amount
- `janus_risk_amount` - Risk amount histogram
- `janus_risk_percentage_avg` - Average risk percentage
- `janus_risk_percentage` - Risk percentage histogram
- `janus_stop_losses_calculated_total` - Stop losses calculated
- `janus_stop_loss_distance_avg` - Average stop distance
- `janus_stop_loss_distance` - Stop distance histogram
- `janus_take_profits_calculated_total` - Take profits calculated
- `janus_take_profit_distance_avg` - Average TP distance
- `janus_take_profit_distance` - TP distance histogram
- `janus_risk_reward_ratio_avg` - Average R/R ratio
- `janus_risk_reward_ratio` - R/R ratio histogram
- `janus_portfolio_heat` - Portfolio heat (risk %)
- `janus_portfolio_exposure` - Portfolio exposure ($)
- `janus_portfolio_exposure_percentage` - Portfolio exposure (%)
- `janus_portfolio_position_count` - Open positions
- `janus_portfolio_concentration_risk` - Concentration risk
- `janus_portfolio_diversification_score` - Diversification (0-1)
- `janus_position_limit_violations_total{limit_type}` - Position limit violations
- `janus_daily_loss_limit_violations_total` - Daily loss violations
- `janus_portfolio_exposure_limit_violations_total` - Exposure violations
- `janus_symbol_exposure_limit_violations_total{symbol}` - Symbol violations
- `janus_total_trades` - Total trades
- `janus_winning_trades` - Winning trades
- `janus_losing_trades` - Losing trades
- `janus_win_rate` - Win rate
- `janus_profit_factor` - Profit factor
- `janus_avg_win` - Average win
- `janus_avg_loss` - Average loss
- `janus_expected_value` - Expected value per trade
- `janus_current_drawdown` - Current drawdown ($)
- `janus_current_drawdown_percentage` - Current drawdown (%)
- `janus_max_drawdown` - Maximum drawdown ($)
- `janus_max_drawdown_percentage` - Maximum drawdown (%)
- `janus_drawdown_duration` - Drawdown duration (periods)
- `janus_kelly_fraction` - Kelly criterion fraction
- `janus_sharpe_ratio` - Sharpe ratio
- `janus_position_sizing_duration_seconds` - Position sizing time
- `janus_stop_calculation_duration_seconds` - Stop calculation time
- `janus_risk_validation_duration_seconds` - Risk validation time
- `janus_risk_calculation_errors_total` - Risk calculation errors
- `janus_risk_validation_errors_total{error_type}` - Risk validation errors

---

## 🔍 Common Queries

### Signal Performance
```promql
# Signal generation rate (signals/second)
rate(janus_signals_generated_total[5m])

# Average confidence over time
janus_signal_confidence_avg

# Signal distribution by type
sum by (signal_type) (janus_signals_by_type)
```

### Latency
```promql
# p50 signal generation latency
histogram_quantile(0.5, rate(janus_signal_generation_duration_seconds_bucket[5m]))

# p95 latency
histogram_quantile(0.95, rate(janus_signal_generation_duration_seconds_bucket[5m]))

# p99 latency
histogram_quantile(0.99, rate(janus_signal_generation_duration_seconds_bucket[5m]))
```

### Risk Monitoring
```promql
# Portfolio heat (should be < 5%)
janus_portfolio_heat

# Win rate (should be > 50%)
janus_win_rate * 100

# Current drawdown
janus_current_drawdown_percentage * 100

# Profit factor (should be > 1.5)
janus_profit_factor
```

### Errors
```promql
# Error rate
rate(janus_errors_total[5m])

# Signal generation errors
rate(janus_signal_generation_errors_total[5m])

# Risk calculation errors
rate(janus_risk_calculation_errors_total[5m])
```

### Cache Performance
```promql
# Cache hit rate
janus_signal_cache_hits_total / (janus_signal_cache_hits_total + janus_signal_cache_misses_total)

# Cache size
janus_signal_cache_size
```

---

## 📈 Grafana Dashboard

### Import Dashboard
1. Copy `config/grafana/janus_dashboard.json`
2. Grafana → Dashboards → Import
3. Paste JSON or upload file
4. Select Prometheus datasource
5. Click Import

### Dashboard Panels
- **Total Signals Generated** - Overall signal volume
- **Average Signal Confidence** - Signal quality gauge
- **Portfolio Heat** - Current risk level (with thresholds)
- **Win Rate** - Trading performance
- **Signal Generation Rate** - Signals per second by type
- **Portfolio Risk Metrics** - Heat and exposure over time
- **Signal Distribution** - Pie charts (type/timeframe/source)
- **Performance Gauges** - Positions, R/R, drawdown, profit factor
- **Latency Charts** - p50/p95/p99 signal generation time
- **Error Rate** - Overall and component-specific errors

---

## ⚙️ Prometheus Configuration

### prometheus.yml
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'janus'
    static_configs:
      - targets: ['localhost:9090']
        labels:
          service: 'janus'
          environment: 'production'
```

---

## 🎯 Best Practices

### 1. Metric Naming
- Use consistent prefixes (`janus_`)
- Include units in name (`_seconds`, `_bytes`, `_total`)
- Use underscores, not hyphens

### 2. Labels
- Keep cardinality low (< 1000 unique combinations)
- Use for grouping, not for unique IDs
- Consistent label names across metrics

### 3. Histograms vs Gauges
- **Histograms:** For latency, sizes (e.g., duration, batch size)
- **Gauges:** For current values (e.g., portfolio heat, win rate)
- **Counters:** For totals (e.g., signals generated, errors)

### 4. Performance
- Metrics collection is very fast (< 1 μs)
- Use Arc for sharing metrics across threads
- Don't worry about overhead in hot paths

### 5. Testing
```rust
#[test]
fn test_metrics_recording() {
    let metrics = JanusMetrics::default();
    
    // Record some metrics
    metrics.signal_metrics().record_signal_generated(
        "BTC/USD", "1h", "BUY", 0.85, 0.75
    );
    
    // Verify
    let gathered = metrics.gather();
    assert!(gathered.len() > 0);
}
```

---

## 🚨 Alerting Rules

### prometheus_alerts.yml
```yaml
groups:
  - name: janus_alerts
    interval: 30s
    rules:
      - alert: HighPortfolioHeat
        expr: janus_portfolio_heat > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Portfolio heat too high"
          description: "Portfolio heat is {{ $value }} (> 5%)"
      
      - alert: LowWinRate
        expr: janus_win_rate < 0.5
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Win rate below 50%"
      
      - alert: HighDrawdown
        expr: janus_current_drawdown_percentage > 0.2
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Drawdown exceeds 20%"
      
      - alert: HighErrorRate
        expr: rate(janus_errors_total[5m]) > 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate too high"
```

---

## 📊 Example: Complete Integration

```rust
use janus::{
    metrics::{JanusMetrics, start_metrics_server},
    signal::SignalGenerator,
    risk::RiskManager,
};
use std::sync::Arc;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // 1. Create metrics
    let metrics = Arc::new(JanusMetrics::new()?);
    
    // 2. Start Prometheus server
    let _handle = start_metrics_server(Arc::clone(&metrics), 9090).await;
    
    // 3. Use metrics in your application
    let signal_generator = SignalGenerator::new(config);
    let risk_manager = RiskManager::new(risk_config);
    
    loop {
        let start = std::time::Instant::now();
        
        // Generate signal
        let signal = signal_generator.generate(...).await?;
        
        // Record metrics
        if let Some(sig) = &signal {
            metrics.signal_metrics().record_signal_generated(
                &sig.symbol,
                sig.timeframe.as_str(),
                format!("{:?}", sig.signal_type).as_str(),
                sig.confidence,
                sig.strength,
            );
        }
        
        // Record duration
        let duration = start.elapsed().as_secs_f64();
        metrics.signal_metrics().record_generation_duration(duration);
        
        // Apply risk management
        if let Some(sig) = signal {
            let enhanced = risk_manager.apply_risk_management(
                sig, &market_data, &portfolio
            )?;
            
            // Record risk metrics
            if let Some(meta) = enhanced.metadata.get("position_size_units") {
                // ... record position sizing metrics
            }
        }
        
        tokio::time::sleep(Duration::from_secs(60)).await;
    }
}
```

---

## 🔧 Troubleshooting

### Metrics Not Appearing
- Check Prometheus server is running on correct port
- Verify `/metrics` endpoint returns data: `curl http://localhost:9090/metrics`
- Check Prometheus is scraping: Prometheus UI → Status → Targets

### High Memory Usage
- Reduce label cardinality
- Use counters instead of gauges where appropriate
- Implement metric cleanup for old data

### Slow Queries
- Optimize PromQL queries
- Use recording rules for complex queries
- Increase Prometheus resources

---

## 📚 Further Reading

- **Prometheus Documentation:** https://prometheus.io/docs/
- **Grafana Documentation:** https://grafana.com/docs/
- **PromQL Guide:** https://prometheus.io/docs/prometheus/latest/querying/basics/
- **Best Practices:** https://prometheus.io/docs/practices/naming/

---

**Happy Monitoring! 📊**