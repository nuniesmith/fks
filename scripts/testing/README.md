# FKS Testing Scripts

Comprehensive testing utilities for the FKS signals system.

## Overview

This directory contains testing scripts for validating:
- WebSocket connection stability (soak tests)
- Kraken paper-trading soak tests (execution subsystem)
- Trading signal backtests
- API endpoint functionality
- Performance under load

---

## Scripts

### 1. Kraken Paper Trading Soak Test (`kraken-paper-soak.sh`)

**Purpose**: Validate the FKS execution subsystem against Kraken live feeds in paper-trading mode.

**Features**:
- Kraken WebSocket live market data
- Automatic Prometheus metrics scraping
- Configurable duration (30m to 7d)
- Summary reports (JSON and human-readable)
- Safe dry-run mode by default
- Graceful shutdown handling

**Usage**:

```bash
# Default 4-hour soak test
./kraken-paper-soak.sh

# 24-hour test with specific symbols
./kraken-paper-soak.sh --duration 24h --symbols BTC,ETH,SOL

# Quick 30-minute validation
./kraken-paper-soak.sh --duration 30m --verbose

# With custom metrics endpoint
./kraken-paper-soak.sh --metrics-url http://localhost:9090/metrics
```

**Environment Variables**:
```bash
export KRAKEN_API_KEY=your_api_key        # Optional: for authenticated feeds
export KRAKEN_API_SECRET=your_api_secret  # Optional
export KRAKEN_DRY_RUN=true                # Default: true (paper trading)
export METRICS_URL=http://localhost:8080/metrics
export SCRAPE_INTERVAL=60                 # Metrics scrape interval in seconds
```

**Output Files**:
```
soak-results/kraken-soak-YYYYMMDD-HHMMSS/
├── paper-trading.log       # Application logs
├── metrics/                # Prometheus metrics snapshots
│   ├── metrics-HHMMSS.txt
│   └── ...
├── summary.json            # Machine-readable summary
└── analysis.txt            # Human-readable analysis
```

**Expected Results**:
- Retry success rate: >95%
- Circuit breaker state: 0 (closed)
- No sustained WebSocket disconnections
- Arbitrage opportunities detected (if spread threshold met)
- Best-execution analyses performed

**Instrumented Exchanges**:
The following exchanges have full retry metrics instrumentation:
- **Kraken**: Market orders, limit orders, cancel orders, open orders, balance queries
- **Binance**: Place order, cancel order, cancel all orders, order status, active orders, balance, health check
- **Bybit**: Place order, cancel order, cancel all orders, order status, active orders, balance, positions, health check

Each instrumented operation records:
- Success/failure counts
- Duration in milliseconds
- Rate-limit errors (exchange-specific detection)
- Network errors and timeouts

**See also**: `SOAK_TEST_RUNBOOK.md` for detailed runbook and troubleshooting.

---

### 2. WebSocket Soak Test (`websocket-soak-test.py`)

**Purpose**: Test WebSocket connection stability over extended periods (default: 48 hours)

**Features**:
- Multiple concurrent WebSocket connections
- Automatic reconnection with exponential backoff
- Message rate tracking
- Connection stability metrics
- Memory/CPU monitoring
- Detailed reporting

**Usage**:

```bash
# Install dependencies
pip install websockets

# Run 48-hour test with 10 clients
python websocket-soak-test.py \
  --url ws://localhost:8080/ws/signals \
  --duration 48 \
  --clients 10 \
  --report-interval 300

# Quick 1-hour test
python websocket-soak-test.py \
  --url ws://localhost:8080/ws/signals \
  --duration 1 \
  --clients 5

# Debug mode
python websocket-soak-test.py \
  --url ws://localhost:8080/ws/signals \
  --duration 0.5 \
  --debug
```

**Environment Variables**:
```bash
export WS_URL=ws://localhost:8080/ws/signals
export NUM_CLIENTS=10
export DURATION_HOURS=48
export REPORT_INTERVAL=300  # seconds
```

**Expected Results** (48h test):
- Connection success rate: >95%
- Messages received: >10,000
- Avg message rate: >0.1 msg/sec per client
- Disconnections: <50 total
- Memory usage: Stable (not increasing)
- CPU usage: <20% average

**Interpreting Results**:

✅ **PASS** if:
- Connection success rate >95%
- Messages received >0
- No sustained errors

⚠️ **WARNING** if:
- Connection success rate 80-95%
- Frequent reconnections
- Memory slowly increasing

❌ **FAIL** if:
- Connection success rate <80%
- No messages received
- Memory leak detected
- Crashes or hangs

---

### 3. Backtest Runner (`run-backtests.py`)

**Purpose**: Validate trading strategies by backtesting historical signals

**Features**:
- Multiple symbol/timeframe combinations
- Parallel backtest execution
- Performance metrics (win rate, profit factor, etc.)
- JSON and markdown report generation
- Statistical analysis
- Custom configurations

**Usage**:

```bash
# Install dependencies
pip install requests

# Run with default configurations
python run-backtests.py \
  --host localhost:8080 \
  --output ./backtest-results

# Use custom config file
python run-backtests.py \
  --host localhost:8080 \
  --config my-backtests.json \
  --output ./results

# With JWT authentication
python run-backtests.py \
  --host localhost:8080 \
  --api-key "YOUR_JWT_TOKEN" \
  --output ./results
```

**Environment Variables**:
```bash
export API_HOST=localhost:8080
export API_KEY=your_jwt_token
export OUTPUT_DIR=./backtest-results
```

**Custom Configuration File** (`backtests.json`):

```json
{
  "backtests": [
    {
      "symbol": "BTCUSD",
      "timeframe": "5m",
      "start_time": "2025-01-01T00:00:00Z",
      "end_time": "2025-01-08T00:00:00Z",
      "profit_target": 0.02,
      "stop_loss": 0.01,
      "signal_types": ["ema_golden_cross", "rsi_oversold"]
    },
    {
      "symbol": "ETHUSDT",
      "timeframe": "15m",
      "start_time": "2025-01-01T00:00:00Z",
      "end_time": "2025-01-08T00:00:00Z",
      "profit_target": 0.03,
      "stop_loss": 0.015
    }
  ]
}
```

**Output Files**:

```
backtest-results/
├── summary.md              # Markdown summary report
├── raw_results.json        # Complete JSON results
└── details/
    ├── BTCUSDT_5m.json    # Detailed results per config
    ├── ETHUSDT_15m.json
    └── ...
```

**Expected Metrics**:
- Win rate: 45-65% (varies by signal type and market conditions)
- Profit factor: >1.0 (ideally >1.5)
- Average return: >0% (positive)
- Sample size: >10 trades for statistical significance

**Interpreting Results**:

✅ **GOOD** signals if:
- Win rate >55%
- Profit factor >1.5
- Avg return >0.5%
- Consistent across timeframes

⚠️ **FAIR** signals if:
- Win rate 45-55%
- Profit factor 1.0-1.5
- Avg return 0-0.5%

❌ **POOR** signals if:
- Win rate <45%
- Profit factor <1.0
- Avg return <0%
- High variance across timeframes

---

## Quick Start - Complete Test Suite

Run all validation tests before production deployment:

```bash
#!/bin/bash
# complete-test-suite.sh

set -e

echo "==================================================="
echo "FKS Signals - Complete Test Suite"
echo "==================================================="

# 1. Install dependencies
echo "Installing dependencies..."
pip install -q websockets requests

# 2. Run short WebSocket test (1 hour)
echo -e "\n[1/3] Running WebSocket stability test (1h)..."
python websocket-soak-test.py \
  --url ws://localhost:8080/ws/signals \
  --duration 1 \
  --clients 5 \
  --report-interval 300 &
WS_TEST_PID=$!

# 3. Run backtests in parallel
echo -e "\n[2/3] Running backtests..."
python run-backtests.py \
  --host localhost:8080 \
  --output ./backtest-results-$(date +%Y%m%d-%H%M%S)

# 4. Wait for WebSocket test to complete
echo -e "\n[3/3] Waiting for WebSocket test to complete..."
wait $WS_TEST_PID

echo -e "\n==================================================="
echo "Test Suite Complete!"
echo "==================================================="
echo "Review results:"
echo "  - Backtest results: ./backtest-results-*/"
echo "  - WebSocket test: See output above"
echo "==================================================="
```

Make it executable and run:
```bash
chmod +x scripts/testing/complete-test-suite.sh
./scripts/testing/complete-test-suite.sh
```

---

## Production Readiness Criteria

Before deploying to production, ensure:

### WebSocket Tests
- [ ] 48-hour soak test completed successfully
- [ ] Connection success rate >95%
- [ ] No memory leaks detected
- [ ] No sustained errors in logs
- [ ] Reconnection logic works correctly

### Backtest Validation
- [ ] Backtests completed for all target symbols
- [ ] Win rate within acceptable range (>45%)
- [ ] Profit factor >1.0 on average
- [ ] No unexpected signal types
- [ ] Signal quality consistent across timeframes

### Performance Tests
- [ ] API response time <100ms (p99)
- [ ] WebSocket message latency <5ms (p99)
- [ ] CPU usage <20% under normal load
- [ ] Memory usage stable over 48h
- [ ] No database query timeouts

---

## Troubleshooting

### WebSocket Test Issues

**Problem**: Test fails to connect

```bash
# Check data service is running
docker-compose ps data-service

# Check WebSocket endpoint
curl -i http://localhost:8080/ws/signals
# Should return: 426 Upgrade Required (WebSocket)

# Check logs
docker-compose logs data-service | grep -i websocket
```

**Problem**: High disconnection rate

```bash
# Check for network issues
ping -c 10 localhost

# Check service logs for errors
docker-compose logs data-service | grep -i "disconnect\|error"

# Monitor resource usage
docker stats data-service
```

**Problem**: No messages received

```bash
# Check if signals are being generated
curl http://localhost:8080/api/v1/signals/stats

# Check indicator warmup status
curl http://localhost:8080/api/v1/indicators/BTCUSD/1m/status

# If not warmed up, run deep warmup
curl -X POST http://localhost:8080/api/v1/indicators/warmup/deep \
  -H "Content-Type: application/json" \
  -d '{"symbols":["BTCUSD"],"timeframes":["1m"],"limit":250}'
```

### Backtest Issues

**Problem**: Backtest returns 0 trades

```bash
# Check if signals exist in time range
curl "http://localhost:9000/exec?query=SELECT+MIN(timestamp),MAX(timestamp),COUNT(*)+FROM+signals_crypto"

# Adjust time range or run for longer period
# Generate more signals by waiting or expanding symbol/timeframe coverage
```

**Problem**: API request fails with 401 Unauthorized

```bash
# Check if JWT authentication is enabled
docker-compose logs data-service | grep "JWT authentication"

# If enabled, generate token first
# (Requires implementing token generation endpoint or using master key)
```

**Problem**: Backtest takes too long

```bash
# Reduce time range
# Reduce number of symbols/timeframes
# Run in parallel (script does this by default)

# Monitor QuestDB query performance
docker-compose logs questdb | grep -i "slow query"
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Signals System Tests

on:
  pull_request:
    paths:
      - 'src/data/**'
  push:
    branches:
      - main

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Start services
        run: |
          docker-compose up -d data-service questdb redis
          sleep 30
      
      - name: Install Python dependencies
        run: pip install websockets requests
      
      - name: Run WebSocket stability test (15 min)
        run: |
          python scripts/testing/websocket-soak-test.py \
            --url ws://localhost:8080/ws/signals \
            --duration 0.25 \
            --clients 3
      
      - name: Run backtests
        run: |
          python scripts/testing/run-backtests.py \
            --host localhost:8080 \
            --output ./results
      
      - name: Upload test results
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: ./results/
```

---

## Monitoring & Alerting

### Grafana Dashboard

Import the execution metrics dashboard for visualization:

```bash
# Dashboard file location
fks/scripts/monitoring/dashboards/execution-metrics.json

# Import via Grafana UI:
# 1. Go to Dashboards → Import
# 2. Upload the JSON file
# 3. Select your Prometheus data source
```

**Dashboard Panels**:
- Retry success rate by operation (per exchange: kraken, binance, bybit)
- Circuit breaker state timeline
- Arbitrage spread and opportunities
- Best-execution recommendations and quality
- Signal flow rates (received/executed/rejected)
- Order flow (submitted/filled/cancelled)
- Exchange-specific latency histograms
- Rate-limit and network error counts by exchange

### Prometheus Alerting Rules

Deploy alerting rules for proactive monitoring:

```bash
# Alerting rules file
fks/scripts/monitoring/alerting/execution-alerts.yaml

# Copy to Prometheus rules directory
cp scripts/monitoring/alerting/execution-alerts.yaml /etc/prometheus/rules/

# Reload Prometheus
curl -X POST http://localhost:9090/-/reload
```

**Key Alerts**:
| Alert | Severity | Trigger |
|-------|----------|---------|
| ExecutionCircuitBreakerOpen | critical | Circuit breaker open > 2m |
| ExecutionLowRetrySuccessRate | warning | Success rate < 80% for 5m |
| ArbitrageExtremeSpread | warning | Spread > 100 bps for 2m |
| SignalFlowNoSignals | critical | No signals for 15m |
| BestExecutionAvoidRecommendation | warning | Avoid recommendation for 10m |

---

## Advanced Usage

### Custom WebSocket Filters

Modify the WebSocket client to test specific filters:

```python
# In websocket-soak-test.py, modify filters:
filters={
    "symbols": ["BTCUSD", "ETHUSDT", "SOLUSDT"],
    "timeframes": ["1m", "5m", "15m"],
    "signal_types": ["ema_golden_cross", "rsi_oversold"],
    "directions": ["long"]
}
```

### Custom Backtest Parameters

```bash
# Test aggressive strategy
python run-backtests.py --host localhost:8080 --config aggressive.json

# aggressive.json:
{
  "backtests": [{
    "symbol": "BTCUSD",
    "timeframe": "1m",
    "profit_target": 0.05,  # 5% target
    "stop_loss": 0.02,      # 2% stop
    "signal_types": ["ema_golden_cross"]
  }]
}
```

### Load Testing

```bash
# High concurrency WebSocket test
python websocket-soak-test.py \
  --url ws://localhost:8080/ws/signals \
  --duration 1 \
  --clients 100 \
  --report-interval 60

# Stress test API endpoints
for i in {1..1000}; do
  curl -s http://localhost:8080/api/v1/signals/stats > /dev/null &
done
wait

# Monitor during load
docker stats data-service
```

---

## Contributing

When adding new tests:

1. Follow existing script structure
2. Add proper error handling
3. Include debug logging
4. Document in this README
5. Add usage examples
6. Update CI/CD pipeline

---

## Instrumentation Coverage

All exchange REST clients are instrumented with Prometheus-style execution metrics:

| Exchange | Operations Instrumented | Metric Prefix |
|----------|------------------------|---------------|
| Kraken | Market order, Limit order, Stop-loss, Take-profit, Cancel, Cancel all, Open orders, Query orders | `kraken_*` |
| Binance | Place order, Cancel order, Cancel all orders, Order status, Active orders, Balance, Health check | `binance_*` |
| Bybit | Place order, Cancel order, Cancel all orders, Order status, Active orders, Balance, Positions, Health check | `bybit_*` |

**Metrics Collected Per Operation**:
- `execution_retry_total_operations{operation="<exchange>_<op>"}` - Total operation count
- `execution_retry_successes{operation="<exchange>_<op>"}` - Successful operations
- `execution_retry_failures{operation="<exchange>_<op>"}` - Failed operations
- `execution_retry_rate_limit_errors{operation="<exchange>_<op>"}` - Rate limit hits
- `execution_retry_network_errors{operation="<exchange>_<op>"}` - Network failures
- `execution_retry_last_duration_ms{operation="<exchange>_<op>"}` - Latest latency

---

## File Index

### Workflow (primary entry point)
| File | Description |
|------|-------------|
| `../../.github/workflows/paper-trading-test.yml` | **🧪 Paper Trading & Monitoring** — GitHub Actions workflow for all test types |

### Workflow Deploy Scripts
| File | Description |
|------|-------------|
| `paper-trading/pre-deploy.sh` | Test directory setup, env generation, volume provisioning |
| `paper-trading/deploy.sh` | Main test runner — handles all test types via SSH |
| `paper-trading/post-deploy.sh` | Post-deploy health verification |
| `paper-trading/monitoring.sh` | Composable RSS memory monitoring (start/stop/status/report) |

### Local Testing & Monitoring Scripts
| File | Description |
|------|-------------|
| `monitor-test.sh` | Real-time local monitoring (status, health, signals, orders, metrics, validate) |
| `test-control.sh` | Monitor and control running tests on the server |
| `kraken-paper-soak.sh` | Kraken paper-trading soak test (runs Rust binary directly) |
| `run-long-soak.sh` | Long-running soak test with live exchange feeds (Rust binary) |
| `integration-test.sh` | Integration test runner |
| `run-integration-tests.sh` | Integration test suite runner (called by workflow) |
| `start-integration-test.sh` | Local integration test startup with Docker Compose |
| `live-signal-test.sh` | Signal pipeline validation (called by workflow) |
| `verify-env.sh` | Environment validation (called by workflow) |
| `pre-test-checklist.sh` | Pre-flight checks before testing |

### Analysis & Utilities
| File | Description |
|------|-------------|
| `analyze-paper-test-logs.sh` | Post-test log analysis |
| `cleanup-test-data.sh` | Clean up old test data |
| `test-discord-webhook.sh` | Discord webhook testing utility |
| `audit-smoke-test.sh` | Audit smoke test |

### Python Test Scripts
| File | Description |
|------|-------------|
| `websocket-soak-test.py` | WebSocket connection stability test |
| `http-soak-test.py` | HTTP endpoint soak test |
| `run-backtests.py` | Trading signal backtest runner |

### Documentation
| File | Description |
|------|-------------|
| `README.md` | This file |
| `SOAK_TEST_RUNBOOK.md` | Detailed runbook for soak testing |

### Removed Scripts
The following standalone test launcher scripts have been consolidated into the
GitHub Actions workflow and deleted:
- ~~`start-paper-trading-test.sh`~~ → Use workflow: `paper-trading-soak`
- ~~`start-24hr-test.sh`~~ → Use workflow: `paper-trading-soak`, Duration: `24`
- ~~`start-48hr-test.sh`~~ → Use workflow: `paper-trading-soak`, Duration: `48`
- ~~`start-30day-test.sh`~~ → Use workflow: `paper-trading-soak`, Duration: `720`

**Related Monitoring Files**:
| File | Description |
|------|-------------|
| `../monitoring/rss-memory-monitor.sh` | RSS memory monitoring (used by `paper-trading/monitoring.sh`) |
| `../monitoring/dashboards/execution-metrics.json` | Grafana dashboard |
| `../monitoring/dashboards/rss-memory-72h.json` | Grafana RSS memory dashboard (audit item #1) |
| `../monitoring/alerting/execution-alerts.yaml` | Prometheus alerting rules |

---

## Support

For issues or questions:
1. Check script help: `python script-name.py --help` or `./script.sh --help`
2. Review logs: `docker-compose logs data-service`
3. See soak test runbook: `SOAK_TEST_RUNBOOK.md`
4. See main docs: `../docs/SIGNALS_DEPLOYMENT_CHECKLIST.md`

---

**Last Updated**: February 2026  
**Maintained By**: FKS Engineering Team