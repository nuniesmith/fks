# JANUS API Quick Start Guide

## Table of Contents
- [Getting Started](#getting-started)
- [Quick Examples](#quick-examples)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

---

## Getting Started

### Start the Service

```bash
# Clone and build
cd fks/src/janus
cargo build --release

# Run the service
./target/release/janus

# Or with custom ports
JANUS_REST_PORT=8080 JANUS_METRICS_PORT=9090 ./target/release/janus
```

### Verify Service is Running

```bash
# Health check
curl http://localhost:8080/api/v1/health

# Expected response:
# {"status":"healthy","service":"janus","version":"0.1.0","uptime_seconds":0}
```

---

## Quick Examples

### 1. Generate a Trading Signal

```bash
curl -X POST http://localhost:8080/api/v1/signals/generate \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USD",
    "timeframe": "1h",
    "current_price": 50000.0,
    "enable_ml": false,
    "analysis": {
      "ema_fast": 50100.0,
      "ema_slow": 49900.0,
      "ema_cross": 1.0,
      "rsi": 35.0,
      "rsi_signal": -1.0,
      "macd_line": 120.0,
      "macd_signal": 100.0,
      "macd_histogram": 20.0,
      "macd_cross": 1.0,
      "bb_upper": 51000.0,
      "bb_middle": 50000.0,
      "bb_lower": 49000.0,
      "bb_position": 0.5,
      "atr": 500.0,
      "trend_strength": 0.8,
      "volatility": 0.015
    }
  }'
```

### 2. Calculate Position Size

```bash
curl -X POST http://localhost:8080/api/v1/risk/calculate/position-size \
  -H "Content-Type: application/json" \
  -d '{
    "signal": {
      "symbol": "BTC/USD",
      "signal_type": "Buy",
      "timeframe": "1h",
      "confidence": 0.85,
      "entry_price": 50000.0,
      "stop_loss": 49000.0
    },
    "market_data": {
      "current_price": 50000.0,
      "atr": 500.0,
      "volatility": 0.015
    },
    "sizing_method": "FixedFractional"
  }'
```

### 3. Get Risk Configuration

```bash
curl http://localhost:8080/api/v1/risk/config
```

### 4. View Portfolio

```bash
curl http://localhost:8080/api/v1/risk/portfolio
```

### 5. Check Metrics

```bash
curl http://localhost:9090/metrics
```

---

## Common Workflows

### Workflow 1: Generate Signal → Calculate Size → Validate → Execute

```bash
#!/bin/bash

# Step 1: Generate signal
SIGNAL=$(curl -s -X POST http://localhost:8080/api/v1/signals/generate \
  -H "Content-Type: application/json" \
  -d '{...}')

echo "Signal: $SIGNAL"

# Step 2: Calculate position size
SIZE=$(curl -s -X POST http://localhost:8080/api/v1/risk/calculate/position-size \
  -H "Content-Type: application/json" \
  -d '{...}')

echo "Position Size: $SIZE"

# Step 3: Validate signal
VALIDATION=$(curl -s -X POST http://localhost:8080/api/v1/risk/validate \
  -H "Content-Type: application/json" \
  -d '{...}')

echo "Validation: $VALIDATION"

# Step 4: Add to portfolio (if valid)
curl -X POST http://localhost:8080/api/v1/risk/portfolio/positions \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Workflow 2: Monitor Portfolio Risk

```bash
#!/bin/bash

# Get current portfolio state
curl http://localhost:8080/api/v1/risk/portfolio

# Get risk metrics
curl http://localhost:8080/api/v1/risk/metrics

# Get performance summary
curl http://localhost:8080/api/v1/risk/performance
```

### Workflow 3: Update Risk Parameters

```bash
# Get current config
curl http://localhost:8080/api/v1/risk/config > current_config.json

# Edit config
nano current_config.json

# Update config
curl -X PUT http://localhost:8080/api/v1/risk/config \
  -H "Content-Type: application/json" \
  -d @current_config.json
```

---

## API Endpoints Reference

### Signal Generation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/signals/generate` | Generate single signal |
| POST | `/api/v1/signals/batch` | Generate multiple signals |

### Risk Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/risk/config` | Get risk config |
| PUT | `/api/v1/risk/config` | Update risk config |
| GET | `/api/v1/risk/portfolio` | Get portfolio state |
| POST | `/api/v1/risk/portfolio/positions` | Add position |
| DELETE | `/api/v1/risk/portfolio/positions/:symbol` | Remove position |
| GET | `/api/v1/risk/metrics` | Get risk metrics |
| GET | `/api/v1/risk/performance` | Get performance |
| POST | `/api/v1/risk/validate` | Validate signal |
| POST | `/api/v1/risk/calculate/position-size` | Calculate size |
| POST | `/api/v1/risk/calculate/stop-loss` | Calculate stop |
| POST | `/api/v1/risk/calculate/take-profit` | Calculate TP |

### Health & Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/version` | Service version |
| GET | `/metrics` | Prometheus metrics |

---

## Configuration

### Environment Variables

```bash
# Service ports
export JANUS_REST_PORT=8080
export JANUS_METRICS_PORT=9090
export JANUS_GRPC_PORT=50051

# Signal thresholds
export JANUS_MIN_CONFIDENCE=0.7
export JANUS_MIN_STRENGTH=0.6

# Logging
export RUST_LOG=info,janus=debug
```

### Risk Configuration Parameters

```json
{
  "account_balance": 10000.0,           // Account size
  "risk_per_trade_pct": 0.01,           // 1% risk per trade
  "max_position_size_pct": 0.1,         // 10% max position
  "max_portfolio_exposure_pct": 0.5,    // 50% max exposure
  "min_risk_reward_ratio": 1.5,         // Minimum 1.5:1 R:R
  "max_concurrent_positions": 5,        // Max open positions
  "max_daily_loss_pct": 0.05,          // 5% max daily loss
  "per_symbol_exposure_pct": 0.2,      // 20% per symbol
  "atr_stop_multiplier": 2.0,          // 2x ATR for stops
  "atr_tp_multiplier": 3.0,            // 3x ATR for TP
  "default_risk_reward": 2.0           // Default 2:1 R:R
}
```

---

## Timeframes

Supported timeframe values:
- `1m` or `M1` - 1 minute
- `5m` or `M5` - 5 minutes
- `15m` or `M15` - 15 minutes
- `1h` or `H1` - 1 hour
- `4h` or `H4` - 4 hours
- `1d` or `D1` - 1 day

---

## Signal Types

Valid signal types:
- `Buy` - Long/buy signal
- `Sell` - Short/sell signal
- `Hold` - No action signal

---

## Position Sizing Methods

Available sizing methods:
- `FixedFractional` - Risk fixed % of account (default)
- `Kelly` - Kelly criterion optimal sizing
- `VolatilityBased` - Adjust for volatility
- `FixedDollar` - Risk fixed dollar amount
- `AtrBased` - Normalize by ATR

---

## Stop Loss Methods

Available stop loss methods:
- `Atr` - ATR-based stop (e.g., 2x ATR)
- `Percentage` - Fixed % from entry
- `SupportResistance` - Use support/resistance
- `Volatility` - Based on volatility
- `HighLow` - Based on recent high/low

---

## Error Codes

| Status | Error | Description |
|--------|-------|-------------|
| 200 | - | Success |
| 400 | `bad_request` | Invalid parameters |
| 404 | `not_found` | Resource not found |
| 422 | `risk_error` | Risk validation failed |
| 500 | `internal_error` | Server error |

---

## Troubleshooting

### Service Won't Start

```bash
# Check if ports are in use
lsof -i :8080
lsof -i :9090

# Check logs
RUST_LOG=debug ./target/release/janus
```

### Connection Refused

```bash
# Verify service is running
curl http://localhost:8080/api/v1/health

# Check firewall
sudo ufw allow 8080
sudo ufw allow 9090
```

### Invalid Signal Errors

```bash
# Check signal format
cat signal.json | jq .

# Validate JSON
jq . < signal.json
```

### High Filter Rate

If many signals are filtered:
1. Lower `min_confidence` threshold
2. Lower `min_strength` threshold
3. Check indicator values are realistic
4. Verify timeframe is correct

### Risk Validation Failures

Common causes:
- Position size exceeds limits
- Portfolio exposure too high
- Daily loss limit reached
- Insufficient risk/reward ratio

Check current limits:
```bash
curl http://localhost:8080/api/v1/risk/config
```

---

## Monitoring with Prometheus

### Add to Prometheus Config

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'janus'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: '/metrics'
```

### Key Metrics to Watch

```promql
# Signal generation rate
rate(janus_signals_generated_total[5m])

# Filter rate
janus_signal_filter_rate

# HTTP latency (p99)
histogram_quantile(0.99, janus_http_request_duration_seconds)

# Portfolio exposure
janus_portfolio_exposure_percentage

# Risk violations
increase(janus_risk_limit_violations_total[5m])
```

---

## Testing with cURL

### Generate Test Signal

```bash
curl -X POST http://localhost:8080/api/v1/signals/generate \
  -H "Content-Type: application/json" \
  -d @test_signal.json
```

**test_signal.json**:
```json
{
  "symbol": "TEST/USD",
  "timeframe": "1h",
  "current_price": 100.0,
  "analysis": {
    "ema_fast": 101.0,
    "ema_slow": 99.0,
    "ema_cross": 1.0,
    "rsi": 45.0,
    "rsi_signal": 0.0,
    "macd_line": 0.5,
    "macd_signal": 0.3,
    "macd_histogram": 0.2,
    "macd_cross": 1.0,
    "bb_upper": 105.0,
    "bb_middle": 100.0,
    "bb_lower": 95.0,
    "bb_position": 0.5,
    "atr": 2.0,
    "trend_strength": 0.7,
    "volatility": 0.02
  }
}
```

---

## Python Integration Example

```python
import requests
import json

BASE_URL = "http://localhost:8080"

def generate_signal(symbol, timeframe, analysis):
    """Generate a trading signal"""
    response = requests.post(
        f"{BASE_URL}/api/v1/signals/generate",
        json={
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": analysis["current_price"],
            "analysis": analysis
        }
    )
    return response.json()

def calculate_position_size(signal, market_data):
    """Calculate position size for signal"""
    response = requests.post(
        f"{BASE_URL}/api/v1/risk/calculate/position-size",
        json={
            "signal": signal,
            "market_data": market_data,
            "sizing_method": "FixedFractional"
        }
    )
    return response.json()

def get_portfolio():
    """Get current portfolio state"""
    response = requests.get(f"{BASE_URL}/api/v1/risk/portfolio")
    return response.json()

# Example usage
analysis = {
    "current_price": 50000.0,
    "ema_fast": 50100.0,
    "ema_slow": 49900.0,
    "ema_cross": 1.0,
    "rsi": 35.0,
    "rsi_signal": -1.0,
    "atr": 500.0,
    "trend_strength": 0.8,
    "volatility": 0.015,
    # ... other indicators
}

signal = generate_signal("BTC/USD", "1h", analysis)
print(f"Signal: {signal}")

portfolio = get_portfolio()
print(f"Portfolio: {portfolio}")
```

---

## Next Steps

1. **Read Full Documentation**: See `WEEK6_REST_API.md` for complete API reference
2. **Set Up Monitoring**: Configure Prometheus and Grafana (see `METRICS_QUICKSTART.md`)
3. **Integrate with System**: Use Python/Node.js client libraries
4. **Add Authentication**: Implement JWT or API keys for production
5. **Scale Up**: Deploy with Docker/Kubernetes

---

## Support & Resources

- **Full API Docs**: `docs/WEEK6_REST_API.md`
- **Metrics Guide**: `docs/METRICS_QUICKSTART.md`
- **Risk Management**: `docs/RISK_MANAGEMENT_QUICKSTART.md`
- **Source Code**: `services/janus/src/api/`
- **Tests**: `services/janus/src/api/*/tests.rs`

---

**Last Updated**: Week 6  
**Version**: 0.1.0