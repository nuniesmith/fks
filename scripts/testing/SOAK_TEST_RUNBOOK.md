# Kraken Paper Trading Soak Test Runbook

## Overview

This runbook describes how to run and monitor paper-trading soak tests for the FKS execution system against Kraken live feeds. These tests validate:

- WebSocket connection stability and reconnection behavior
- Retry logic and circuit breaker effectiveness
- Arbitrage opportunity detection accuracy
- Best-execution analyzer recommendations
- Signal-flow coordination under real market conditions

## Prerequisites

### System Requirements

- Linux or macOS (Windows via WSL2)
- Rust toolchain (1.70+)
- `curl` for metrics scraping
- `bc` for calculations (optional, for analysis)
- Network access to Kraken WebSocket endpoints

### Environment Setup

```bash
# Clone and navigate to the project
cd /path/to/fks

# Ensure the execution crate builds
cargo build --release -p fks-execution-service --example paper_trading
```

### Optional: Kraken API Credentials

For authenticated WebSocket feeds (private data), set:

```bash
export KRAKEN_API_KEY="your-api-key"
export KRAKEN_API_SECRET="your-api-secret"
```

**Note:** Paper trading does NOT require API credentials for public market data feeds.

---

## Quick Start

### 1. Default 4-Hour Soak Test

```bash
cd fks/scripts/testing
chmod +x kraken-paper-soak.sh
./kraken-paper-soak.sh
```

### 2. Extended 24-Hour Soak Test

```bash
./kraken-paper-soak.sh --duration 24h --symbols BTC,ETH,SOL
```

### 3. Quick 30-Minute Validation

```bash
./kraken-paper-soak.sh --duration 30m --verbose
```

---

## Test Configurations

### Command-Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `-d, --duration` | `4h` | Test duration (e.g., `30m`, `4h`, `24h`, `7d`) |
| `-s, --symbols` | `BTC,ETH` | Comma-separated trading symbols |
| `-m, --min-spread` | `0.1` | Minimum arbitrage spread percentage |
| `--metrics-url` | `http://localhost:8080/metrics` | Prometheus metrics endpoint |
| `--scrape-interval` | `60` | Metrics scrape interval in seconds |
| `--simulated` | `false` | Use simulated data instead of live feeds |
| `--live` | `false` | **DANGER**: Enable real trading (disables dry-run) |
| `-v, --verbose` | `false` | Enable verbose output |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KRAKEN_API_KEY` | (none) | Kraken API key for authenticated feeds |
| `KRAKEN_API_SECRET` | (none) | Kraken API secret |
| `KRAKEN_DRY_RUN` | `true` | Set to `false` for live trading |
| `METRICS_URL` | `http://localhost:8080/metrics` | Override metrics endpoint |
| `SCRAPE_INTERVAL` | `60` | Metrics scrape interval |
| `RUST_LOG` | `info,janus=debug` | Logging configuration (execution is embedded in Janus) |

---

## Monitoring During Tests

### Real-Time Log Monitoring

```bash
# In a separate terminal
tail -f soak-results/kraken-soak-*/paper-trading.log
```

### Metrics Inspection

```bash
# View latest metrics
cat soak-results/kraken-soak-*/metrics/metrics-*.txt | tail -100

# Monitor specific metrics
watch -n 10 'grep "execution_retry" soak-results/kraken-soak-*/metrics/metrics-*.txt | tail -20'
```

### Key Metrics to Watch

| Metric | Good Value | Warning | Action |
|--------|------------|---------|--------|
| `execution_retry_success_rate` | > 0.95 | < 0.80 | Check network/API issues |
| `execution_circuit_breaker_state` | 0 (closed) | 1 (open) | Investigate failures |
| `arbitrage_opportunities_total` | Increasing | Static | Verify price feeds |
| `signal_flow_signals_received` | > 0 | 0 | Check signal source |
| `best_execution_analyses_total` | > 0 | 0 | Verify analyzer integration |

---

## Output Structure

Each test run creates a timestamped directory:

```
soak-results/kraken-soak-YYYYMMDD-HHMMSS/
├── paper-trading.log       # Application logs
├── metrics/                # Prometheus metrics snapshots
│   ├── metrics-HHMMSS.txt  # Timestamped snapshots
│   └── ...
├── summary.json            # Machine-readable summary
└── analysis.txt            # Human-readable analysis
```

### Summary JSON Schema

```json
{
    "test_info": {
        "start_time": "2024-01-15T10:00:00Z",
        "end_time": "2024-01-15T14:00:00Z",
        "duration_seconds": 14400,
        "duration_human": "4h",
        "symbols": "BTC ETH",
        "dry_run": true,
        "simulated_data": false
    },
    "metrics_collection": {
        "scrape_interval_seconds": 60,
        "total_scrapes": 240,
        "metrics_url": "http://localhost:8080/metrics"
    },
    "execution_metrics": {
        "retry_operations_total": 150,
        "retry_first_try_success": 145,
        "retry_success_rate_pct": 96.67,
        "arbitrage_opportunities": 42,
        "signals_received": 100,
        "signals_executed": 95,
        "best_execution_analyses": 100
    }
}
```

---

## Interpreting Results

### Success Criteria

| Criteria | Threshold | Priority |
|----------|-----------|----------|
| Retry success rate | ≥ 95% | P0 |
| No circuit breaker opens | 0 opens | P0 |
| WebSocket reconnections | ≤ 5 per hour | P1 |
| Arbitrage detection active | > 0 opportunities | P1 |
| Best-execution active | > 0 analyses | P2 |

### Common Issues and Remediation

#### Issue: Low Retry Success Rate (< 80%)

**Symptoms:**
- `execution_retry_success_rate` below 0.80
- High `execution_retry_failure` count

**Possible Causes:**
1. Network connectivity issues
2. Kraken API rate limiting
3. API credential issues

**Remediation:**
```bash
# Check network
ping api.kraken.com

# Verify credentials (if using authenticated feeds)
echo $KRAKEN_API_KEY

# Review error breakdown in metrics
grep "execution_retry_errors_by_type" soak-results/*/metrics/metrics-*.txt | tail -10
```

#### Issue: Circuit Breaker Open

**Symptoms:**
- `execution_circuit_breaker_state` = 1 or 2
- Operations failing without retries

**Possible Causes:**
1. Sustained API failures
2. Rate limit exhaustion
3. Server-side issues at Kraken

**Remediation:**
```bash
# Check circuit breaker timeline
grep "circuit_breaker" soak-results/*/metrics/metrics-*.txt | head -50

# Review failure patterns in logs
grep -i "error\|fail\|circuit" soak-results/*/paper-trading.log | tail -50
```

#### Issue: No Arbitrage Opportunities Detected

**Symptoms:**
- `arbitrage_opportunities_total` = 0
- No price deviation alerts

**Possible Causes:**
1. Markets are efficient (normal)
2. Price feeds not updating
3. Spread threshold too high

**Remediation:**
```bash
# Check if price updates are being received
grep "price_updates" soak-results/*/metrics/metrics-*.txt | tail -10

# Lower spread threshold
./kraken-paper-soak.sh --min-spread 0.05
```

#### Issue: WebSocket Disconnections

**Symptoms:**
- Frequent reconnection messages in logs
- Gaps in metrics data

**Possible Causes:**
1. Network instability
2. Kraken maintenance
3. Connection timeout settings

**Remediation:**
```bash
# Check reconnection patterns
grep -i "reconnect\|disconnect\|closed" soak-results/*/paper-trading.log | wc -l

# Review WebSocket metrics
grep "websocket" soak-results/*/metrics/metrics-*.txt | tail -20
```

---

## Grafana Dashboard Setup

### Import Dashboard

1. Open Grafana (default: http://localhost:3000)
2. Go to Dashboards → Import
3. Upload `fks/scripts/monitoring/dashboards/execution-metrics.json`

### Key Panels

| Panel | Query | Purpose |
|-------|-------|---------|
| Retry Success Rate | `execution_retry_success_rate` | Overall health indicator |
| Circuit Breaker State | `execution_circuit_breaker_state` | Failure detection |
| Arbitrage Spread | `arbitrage_spread_bps` | Market opportunity tracking |
| Signal Flow | `signal_flow_signals_received` | Signal processing rate |
| Best Execution Score | `best_execution_score` | Execution quality |

### Alert Rules

```yaml
# Example Prometheus alerting rules
groups:
  - name: fks-execution
    rules:
      - alert: CircuitBreakerOpen
        expr: execution_circuit_breaker_state > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Execution circuit breaker is open"

      - alert: LowRetrySuccessRate
        expr: execution_retry_success_rate < 0.80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Retry success rate below 80%"

      - alert: HighArbitrageSpread
        expr: arbitrage_spread_bps > 50
        for: 1m
        labels:
          severity: info
        annotations:
          summary: "Large arbitrage spread detected"
```

---

## Scheduled Testing

### Cron Job Setup

```bash
# Run 4-hour soak test every day at 2 AM
0 2 * * * /path/to/fks/scripts/testing/kraken-paper-soak.sh --duration 4h >> /var/log/fks-soak.log 2>&1

# Run 24-hour soak test every Sunday
0 0 * * 0 /path/to/fks/scripts/testing/kraken-paper-soak.sh --duration 24h >> /var/log/fks-soak-weekly.log 2>&1
```

### CI/CD Integration

```yaml
# .github/workflows/soak-test.yml
name: Soak Test
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
  workflow_dispatch:

jobs:
  soak-test:
    runs-on: ubuntu-latest
    timeout-minutes: 300  # 5 hours
    steps:
      - uses: actions/checkout@v4
      - name: Install Rust
        uses: dtolnay/rust-action@stable
      - name: Run Soak Test
        run: |
          cd scripts/testing
          ./kraken-paper-soak.sh --duration 4h --simulated
      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: soak-results
          path: scripts/testing/soak-results/
```

---

## Cleanup

### Remove Old Test Results

```bash
# Remove results older than 7 days
find soak-results -type d -name "kraken-soak-*" -mtime +7 -exec rm -rf {} +

# Keep only last 5 test runs
ls -dt soak-results/kraken-soak-* | tail -n +6 | xargs rm -rf
```

### Archive Results

```bash
# Compress and archive
tar -czvf soak-archive-$(date +%Y%m%d).tar.gz soak-results/
```

---

## Troubleshooting

### Test Won't Start

```bash
# Check if port 8080 is available
lsof -i :8080

# Verify build succeeds
cargo build --release -p fks-execution-service --example paper_trading
```

### Metrics Not Collected

```bash
# Test metrics endpoint manually
curl http://localhost:8080/metrics

# Check if paper trading started the HTTP server
grep "HTTP server" soak-results/*/paper-trading.log
```

### Test Exits Early

```bash
# Check for panics
grep -i "panic\|thread.*panicked" soak-results/*/paper-trading.log

# Review exit reason
tail -50 soak-results/*/paper-trading.log
```

---

## Contact & Support

- **Slack:** #fks-trading
- **On-Call:** See PagerDuty rotation
- **Documentation:** https://docs.fks.internal/execution

---

*Last Updated: January 2025*