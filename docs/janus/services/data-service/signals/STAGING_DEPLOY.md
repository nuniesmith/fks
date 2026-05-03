# FKS Signals - Staging Deployment Quick Start

**Target Environment**: Staging  
**Duration**: ~30 minutes  
**Purpose**: Deploy and validate signals system before production release

---

## Prerequisites

- [ ] Docker and Docker Compose installed
- [ ] Git repository cloned and up-to-date
- [ ] At least 10GB free disk space
- [ ] Ports available: 8080, 9000, 9090, 9093, 9094, 3000, 6379
- [ ] Discord webhook URL (optional but recommended)

---

## Quick Deployment (Staging)

### Step 1: Generate Environment Configuration

```bash
# Navigate to project root
cd /path/to/fks

# Run setup script to generate .env with secrets
./run.sh start

# This will:
# - Generate random passwords and secrets
# - Create .env file with JWT_SECRET, DISCORD_WEBHOOK_GENERAL, etc.
# - Build and start all services
```

### Step 2: Configure Discord Alerts (Optional)

If you want to receive alerts in Discord:

```bash
# 1. Create Discord webhook
#    - Go to your Discord server
#    - Server Settings > Integrations > Webhooks
#    - Create webhook, copy URL

# 2. Add to .env file
echo "DISCORD_WEBHOOK_GENERAL=https://discord.com/api/webhooks/YOUR_WEBHOOK" >> .env
echo "DISCORD_NOTIFICATIONS_ENABLED=true" >> .env

# 3. Restart services to pick up changes
./run.sh restart
```

### Step 3: Verify Services are Running

```bash
# Check all containers are healthy
docker-compose ps

# Expected output:
# NAME                 STATUS
# fks_data_service     Up (healthy)
# fks_questdb          Up (healthy)
# fks_redis            Up (healthy)
# fks_prometheus       Up (healthy)
# fks_grafana          Up (healthy)
# fks_alertmanager     Up (healthy)
# fks_discord_bridge   Up (healthy)
```

### Step 4: Initialize QuestDB Schema

```bash
# Create signals table in QuestDB
curl -G http://localhost:9000/exec \
  --data-urlencode "query=CREATE TABLE IF NOT EXISTS signals_crypto (
    symbol SYMBOL,
    exchange SYMBOL,
    timeframe SYMBOL,
    signal_type SYMBOL,
    direction SYMBOL,
    strength DOUBLE,
    price DOUBLE,
    trigger_value DOUBLE,
    trigger_value_2 DOUBLE,
    description STRING,
    timestamp TIMESTAMP
  ) TIMESTAMP(timestamp) PARTITION BY DAY;"

# Verify table exists
curl "http://localhost:9000/exec?query=SELECT+COUNT(*)+FROM+signals_crypto"
```

### Step 5: Warmup Indicators

The data service needs historical candle data to calculate indicators:

```bash
# Deep warmup for BTCUSD on 1m and 5m timeframes
curl -X POST http://localhost:8080/api/v1/indicators/warmup/deep \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTCUSD", "ETHUSDT"],
    "timeframes": ["1m", "5m"],
    "limit": 250
  }'

# Response will show warmup progress
# Wait 30-60 seconds for warmup to complete
```

### Step 6: Verify Indicators are Ready

```bash
# Check warmup status
curl http://localhost:8080/api/v1/indicators/BTCUSD/1m/status | jq

# Expected output (after warmup):
# {
#   "symbol": "BTCUSD",
#   "timeframe": "1m",
#   "indicators": {
#     "ema_50": { "ready": true, "data_points": 250 },
#     "ema_200": { "ready": true, "data_points": 250 },
#     "rsi": { "ready": true, "data_points": 250 },
#     "macd": { "ready": true, "data_points": 250 }
#   },
#   "all_indicators_ready": true
# }
```

### Step 7: Wait for Signals to Generate

Signals are generated in real-time as new candles arrive:

```bash
# Wait 2-5 minutes for candles and signals
echo "Waiting for signals to generate..."
sleep 120

# Check signal statistics
curl http://localhost:8080/api/v1/signals/stats | jq

# Expected output:
# {
#   "total_signals": 15,
#   "signals_by_type": {
#     "ema_golden_cross": 3,
#     "rsi_oversold": 8,
#     "macd_bullish_cross": 4
#   },
#   "signals_by_symbol": {
#     "BTCUSD": 10,
#     "ETHUSDT": 5
#   }
# }
```

---

## Validation Tests

### Test 1: REST API Endpoints

```bash
# List all signals
curl "http://localhost:8080/api/v1/signals?limit=5" | jq '.count'
# Expected: Number > 0

# Get signals for specific symbol
curl "http://localhost:8080/api/v1/signals/BTCUSD?limit=5" | jq '.signals[0]'
# Expected: Signal object with all fields

# Get signals for symbol/timeframe
curl "http://localhost:8080/api/v1/signals/BTCUSD/1m?limit=5" | jq '.count'
# Expected: Number >= 0
```

### Test 2: WebSocket Streaming

```bash
# Install websocat (if not already installed)
# Ubuntu/Debian: sudo apt install websocat
# macOS: brew install websocat
# Or: cargo install websocat

# Connect to WebSocket
websocat ws://localhost:8080/ws/signals

# Send subscription (paste this JSON):
{"symbols":["BTCUSD","ETHUSDT"],"timeframes":["1m","5m"]}

# You should receive:
# 1. Subscription confirmation message
# 2. Real-time signals as they're generated

# Press Ctrl+C to disconnect
```

### Test 3: Backtesting

```bash
# Run backtest for last 24 hours
curl -X POST http://localhost:8080/api/v1/signals/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSD",
    "timeframe": "5m",
    "start_time": "'$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)'",
    "end_time": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "profit_target": 0.02,
    "stop_loss": 0.01
  }' | jq '.summary'

# Expected output:
# {
#   "total_signals": 25,
#   "total_trades": 20,
#   "winning_trades": 12,
#   "losing_trades": 8,
#   "win_rate": 60.0,
#   "average_return_pct": 0.35,
#   "profit_factor": 1.85
# }
```

### Test 4: Monitoring & Alerts

```bash
# Check Prometheus metrics
curl http://localhost:8080/metrics | grep signals_generated_total
# Expected: signals_generated_total{...} 15

# Access Grafana dashboards
# Open browser: http://localhost:3000
# Username: admin
# Password: (check .env for GF_SECURITY_ADMIN_PASSWORD)
# Navigate to Dashboards > Technical Indicators

# Test Discord alert (if configured)
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {
      "alertname": "TestAlert",
      "severity": "info"
    },
    "annotations": {
      "summary": "Staging deployment test alert"
    }
  }]'

# Check Discord channel for alert message
```

---

## 48-Hour Soak Test

Deploy the WebSocket stability test to validate sustained connections:

### Setup

```bash
# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install websockets

# Run soak test (48 hours, 10 concurrent clients)
python scripts/testing/websocket-soak-test.py \
  --url ws://localhost:8080/ws/signals \
  --duration 48 \
  --clients 10 \
  --report-interval 300
```

### Monitor Soak Test

```bash
# In another terminal, monitor stats every 5 minutes
# The test will print reports automatically

# Monitor Docker stats
watch -n 60 'docker stats --no-stream fks_data_service'

# Monitor logs for errors
docker-compose logs -f data-service | grep -i error

# Check WebSocket client count
curl http://localhost:8080/metrics | grep websocket_clients
```

### Expected Results

After 48 hours, you should see:

- ✅ **Connection success rate**: >95%
- ✅ **Messages received**: >10,000
- ✅ **Avg message rate**: >0.1 msg/sec per client
- ✅ **Disconnections**: <50 total
- ✅ **Memory usage**: Stable (not increasing)
- ✅ **CPU usage**: <20% average

---

## Run Backtests on Known Strategies

Validate signal accuracy with historical data:

```bash
# Install dependencies
pip install requests

# Run comprehensive backtests
python scripts/testing/run-backtests.py \
  --host localhost:8080 \
  --output ./backtest-results

# This will:
# - Test multiple symbol/timeframe combinations
# - Generate performance reports
# - Create summary.md with recommendations

# Review results
cat backtest-results/summary.md

# Expected metrics:
# - Win rate: 45-65% (varies by signal type)
# - Profit factor: >1.0 (ideally >1.5)
# - Avg return: >0% (positive)
```

---

## JWT Authentication (Production Preparation)

For production deployment, enable JWT authentication:

### Generate JWT Secret

The `run.sh` script already generated a JWT secret in `.env`:

```bash
# Verify JWT secret exists
grep DATA_SERVICE_JWT_SECRET .env
# Expected: DATA_SERVICE_JWT_SECRET=<32-char-random-string>
```

### Enable JWT in Staging (Optional Test)

```bash
# Enable JWT authentication
echo "DATA_SERVICE_JWT_ENABLED=true" >> .env

# Restart data service
docker-compose restart data-service

# Verify JWT is enabled
docker-compose logs data-service | grep "JWT authentication is ENABLED"
```

### Generate Test Token

```bash
# For testing, you can generate tokens using the API
# (In production, use a secure master key or admin endpoint)

# Example: Generate token programmatically
# This requires implementing a token generation endpoint
# or using the jsonwebtoken library directly

# For now, JWT is disabled by default in staging
# Enable only when ready for production security testing
```

---

## Monitoring Dashboard Access

Access monitoring tools:

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| **Grafana** | http://localhost:3000 | admin / (see .env: GF_SECURITY_ADMIN_PASSWORD) |
| **Prometheus** | http://localhost:9090 | None |
| **AlertManager** | http://localhost:9093 | None |
| **QuestDB Console** | http://localhost:9000 | None |

### Key Dashboards

1. **Technical Indicators Dashboard**
   - URL: http://localhost:3000/d/technical-indicators
   - Shows: Indicator warmup status, signal generation rates, latency

2. **Prometheus Targets**
   - URL: http://localhost:9090/targets
   - Verify: `data-service` target is UP

3. **QuestDB Console**
   - URL: http://localhost:9000
   - Run query: `SELECT * FROM signals_crypto LIMIT 100`

---

## Common Issues & Quick Fixes

### Issue: No signals generated after 5 minutes

```bash
# Check if indicators are warmed up
curl http://localhost:8080/api/v1/indicators/BTCUSD/1m/status | jq '.all_indicators_ready'

# If false, run deep warmup again
curl -X POST http://localhost:8080/api/v1/indicators/warmup/deep \
  -H "Content-Type: application/json" \
  -d '{"symbols":["BTCUSD"],"timeframes":["1m"],"limit":250}'

# Wait 60 seconds and check again
```

### Issue: WebSocket connection fails

```bash
# Check SignalActor is running
docker-compose logs data-service | grep "Signal actor started"

# Restart service if not found
docker-compose restart data-service
```

### Issue: Discord alerts not received

```bash
# Check Discord bridge is running
docker-compose ps discord
# Expected: Up (healthy)

# Check bridge logs
docker-compose logs discord | tail -20

# Test webhook directly
curl -X POST "$DISCORD_WEBHOOK_GENERAL" \
  -H "Content-Type: application/json" \
  -d '{"content":"Test from staging"}'
```

### Issue: High memory usage (>1GB)

```bash
# Check for signal backlog
curl http://localhost:8080/api/v1/signals/stats

# Restart service
docker-compose restart data-service

# If persistent, check QuestDB retention
curl "http://localhost:9000/exec?query=SELECT+COUNT(*)+FROM+signals_crypto"
```

---

## Next Steps - Production Deployment

Once staging validation is complete (48h soak test passed, backtests validated):

1. **Security Hardening**
   - Enable JWT authentication (`DATA_SERVICE_JWT_ENABLED=true`)
   - Configure HTTPS/TLS (Let's Encrypt)
   - Restrict QuestDB port to internal network only
   - Enable API rate limiting

2. **Scaling Preparation**
   - Review resource limits in docker-compose.prod.yml
   - Plan for horizontal scaling if needed
   - Set up load balancer (if multi-instance)

3. **Operational Readiness**
   - Schedule retention maintenance cron job
   - Set up Discord/PagerDuty alert escalation
   - Document runbooks for common issues
   - Train on-call team on troubleshooting

4. **Production Deployment**
   - Follow full deployment checklist (SIGNALS_DEPLOYMENT_CHECKLIST.md)
   - Deploy during low-traffic window
   - Have rollback plan ready
   - Monitor closely for first 24 hours

---

## Clean Up / Tear Down

To stop and remove staging environment:

```bash
# Stop all services
./run.sh down

# Remove volumes (WARNING: deletes all data)
./run.sh down -v

# Or use docker-compose directly
docker-compose down -v
```

---

## Support & Documentation

- **Full Deployment Checklist**: [SIGNALS_DEPLOYMENT_CHECKLIST.md](./SIGNALS_DEPLOYMENT_CHECKLIST.md)
- **API Documentation**: [SIGNALS_API_REFERENCE.md](./SIGNALS_API_REFERENCE.md)
- **Monitoring Guide**: [SIGNALS_MONITORING_GUIDE.md](./SIGNALS_MONITORING_GUIDE.md)
- **Discord Setup**: [DISCORD_WEBHOOK_SETUP.md](./DISCORD_WEBHOOK_SETUP.md)

For issues or questions, check logs first:
```bash
# Data service logs
docker-compose logs -f data-service

# All services
docker-compose logs -f
```

---

**Document Version**: 1.0  
**Last Updated**: January 2025  
**Tested On**: Docker 24.0+, Docker Compose 2.20+