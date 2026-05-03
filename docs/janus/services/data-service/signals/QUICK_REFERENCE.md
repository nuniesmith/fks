# FKS Signals System - Quick Reference Card

**Version**: 2.1.0 | **Last Updated**: January 2025

---

## 🚀 Quick Start (30 minutes)

```bash
# 1. Start everything
cd /home/jordan/github/fks
./run.sh start

# 2. Configure Discord (optional)
nano .env
# Add: DISCORD_WEBHOOK_GENERAL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
./run.sh restart

# 3. Initialize & warmup
curl -G http://localhost:9000/exec --data-urlencode "query=$(cat config/questdb/init_signals.sql)"
curl -X POST http://localhost:8080/api/v1/indicators/warmup/deep \
  -H "Content-Type: application/json" \
  -d '{"symbols":["BTCUSD","ETHUSDT"],"timeframes":["1m","5m"],"limit":250}'

# 4. Wait & verify
sleep 120
curl http://localhost:8080/api/v1/signals/stats | jq
```

---

## 📡 Service URLs

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| **Data Service API** | http://localhost:8080 | None (JWT if enabled) |
| **Grafana** | http://localhost:3000 | admin / (see .env) |
| **Prometheus** | http://localhost:9090 | None |
| **AlertManager** | http://localhost:9093 | None |
| **QuestDB Console** | http://localhost:9000 | None |
| **Discord Bridge** | http://localhost:9094 | None |

---

## 🔧 Service Management

```bash
# Start all services
./run.sh start

# Stop all services
./run.sh down

# Restart services
./run.sh restart

# View logs
./run.sh logs                          # All services
docker-compose logs -f data-service    # Specific service

# Service status
docker-compose ps

# Rebuild and restart
./run.sh restart
```

---

## 🔑 JWT Authentication

```bash
# Check if JWT is enabled
docker-compose logs data-service | grep "JWT authentication"

# Enable JWT (production)
echo "DATA_SERVICE_JWT_ENABLED=true" >> .env
docker-compose restart data-service

# Disable JWT (development)
echo "DATA_SERVICE_JWT_ENABLED=false" >> .env
docker-compose restart data-service

# Make authenticated request
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8080/api/v1/signals
```

---

## 📊 API Endpoints

### Health & Metrics
```bash
# Health check
curl http://localhost:8080/health

# Prometheus metrics
curl http://localhost:8080/metrics
```

### Signals
```bash
# Get signal statistics
curl http://localhost:8080/api/v1/signals/stats | jq

# List all signals (limit 10)
curl "http://localhost:8080/api/v1/signals?limit=10" | jq

# Get signals by symbol
curl "http://localhost:8080/api/v1/signals/BTCUSD?limit=5" | jq

# Get signals by symbol and timeframe
curl "http://localhost:8080/api/v1/signals/BTCUSD/1m?limit=5" | jq

# Filter by signal type
curl "http://localhost:8080/api/v1/signals?signal_type=ema_golden_cross&limit=5" | jq

# Filter by direction
curl "http://localhost:8080/api/v1/signals?direction=long&limit=5" | jq
```

### Indicators
```bash
# List available indicators
curl http://localhost:8080/api/v1/indicators | jq

# Get indicator info
curl http://localhost:8080/api/v1/indicators/info | jq

# Get indicators for symbol/timeframe
curl http://localhost:8080/api/v1/indicators/BTCUSD/1m | jq

# Check warmup status
curl http://localhost:8080/api/v1/indicators/BTCUSD/1m/status | jq

# Trigger warmup (from QuestDB history)
curl -X POST http://localhost:8080/api/v1/indicators/warmup \
  -H "Content-Type: application/json" \
  -d '{"symbols":["BTCUSD"],"timeframes":["1m"]}'

# Deep warmup (fetch from Binance)
curl -X POST http://localhost:8080/api/v1/indicators/warmup/deep \
  -H "Content-Type: application/json" \
  -d '{"symbols":["BTCUSD","ETHUSDT"],"timeframes":["1m","5m"],"limit":250}'
```

### Backtesting
```bash
# Run backtest
curl -X POST http://localhost:8080/api/v1/signals/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSD",
    "timeframe": "5m",
    "start_time": "2025-01-01T00:00:00Z",
    "end_time": "2025-01-08T00:00:00Z",
    "profit_target": 0.02,
    "stop_loss": 0.01
  }' | jq
```

---

## 🌐 WebSocket Streaming

### Using `websocat`
```bash
# Install websocat
# Ubuntu/Debian: sudo apt install websocat
# macOS: brew install websocat
# Rust: cargo install websocat

# Connect
websocat ws://localhost:8080/ws/signals

# Subscribe (paste JSON):
{"symbols":["BTCUSD","ETHUSDT"],"timeframes":["1m","5m"]}

# Subscribe with filters:
{"symbols":["BTCUSD"],"timeframes":["1m"],"signal_types":["ema_golden_cross"],"directions":["long"]}
```

### Using Python
```python
import asyncio
import json
import websockets

async def stream_signals():
    async with websockets.connect('ws://localhost:8080/ws/signals') as ws:
        # Subscribe
        await ws.send(json.dumps({
            "symbols": ["BTCUSD"],
            "timeframes": ["1m", "5m"]
        }))
        
        # Receive messages
        async for message in ws:
            signal = json.loads(message)
            print(signal)

asyncio.run(stream_signals())
```

---

## 🗄️ QuestDB Queries

```bash
# Count total signals
curl "http://localhost:9000/exec?query=SELECT+COUNT(*)+FROM+signals_crypto" | jq

# Get recent signals
curl "http://localhost:9000/exec?query=SELECT+*+FROM+signals_crypto+ORDER+BY+timestamp+DESC+LIMIT+10" | jq

# Signals by type
curl "http://localhost:9000/exec?query=SELECT+signal_type,COUNT(*)+FROM+signals_crypto+GROUP+BY+signal_type" | jq

# Signals today
curl "http://localhost:9000/exec?query=SELECT+*+FROM+signals_crypto+WHERE+timestamp+>+dateadd('d',-1,now())" | jq

# Check partitions
curl "http://localhost:9000/exec?query=SELECT+DISTINCT+to_str(timestamp,'yyyy-MM-dd')+FROM+signals_crypto" | jq
```

---

## 🔔 Discord Alerts

### Setup
```bash
# 1. Create webhook in Discord
#    Server Settings > Integrations > Webhooks > New Webhook

# 2. Add to .env
echo "DISCORD_WEBHOOK_GENERAL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" >> .env
echo "DISCORD_NOTIFICATIONS_ENABLED=true" >> .env

# 3. Restart services
./run.sh restart

# 4. Test alert
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {"alertname":"TestAlert","severity":"info"},
    "annotations": {"summary":"Test alert"}
  }]'
```

### Check Discord Bridge
```bash
# Health check
curl http://localhost:9094/health

# View logs
docker-compose logs discord

# Test webhook directly
curl -X POST "$DISCORD_WEBHOOK_GENERAL" \
  -H "Content-Type: application/json" \
  -d '{"content":"Test message"}'
```

---

## 🧪 Testing

### Integration Test
```bash
# Run full integration test
./scripts/testing/integration-test.sh

# Quick mode (skip long tests)
./scripts/testing/integration-test.sh --quick

# With JWT enabled
./scripts/testing/integration-test.sh --jwt-enabled
```

### WebSocket Soak Test
```bash
# Install dependencies
pip install websockets

# Run 48-hour test
python scripts/testing/websocket-soak-test.py \
  --url ws://localhost:8080/ws/signals \
  --duration 48 \
  --clients 10 \
  --report-interval 300

# Quick 1-hour test
python scripts/testing/websocket-soak-test.py \
  --duration 1 \
  --clients 5
```

### Backtests
```bash
# Install dependencies
pip install requests

# Run with default configs
python scripts/testing/run-backtests.py \
  --host localhost:8080 \
  --output ./backtest-results

# With custom config
python scripts/testing/run-backtests.py \
  --config my-backtests.json \
  --output ./results

# Review results
cat backtest-results/summary.md
```

---

## 📈 Monitoring

### Prometheus Queries
```bash
# Total signals generated
curl "http://localhost:9090/api/v1/query?query=signals_generated_total"

# Signal rate (per second)
curl "http://localhost:9090/api/v1/query?query=rate(signals_generated_total[5m])"

# WebSocket clients
curl "http://localhost:9090/api/v1/query?query=websocket_clients"
```

### Grafana Dashboards
```
http://localhost:3000/d/technical-indicators
```

### Docker Stats
```bash
# Real-time stats
docker stats fks_data_service

# Resource usage
docker stats --no-stream
```

---

## 🔍 Troubleshooting

### No Signals Generated
```bash
# Check indicators are warmed up
curl http://localhost:8080/api/v1/indicators/BTCUSD/1m/status | jq

# Force warmup
curl -X POST http://localhost:8080/api/v1/indicators/warmup/deep \
  -H "Content-Type: application/json" \
  -d '{"symbols":["BTCUSD"],"timeframes":["1m"],"limit":250}'

# Check logs
docker-compose logs data-service | grep -i "signal\|error"
```

### WebSocket Connection Fails
```bash
# Check SignalActor is running
docker-compose logs data-service | grep "Signal actor started"

# Restart service
docker-compose restart data-service
```

### Discord Alerts Not Received
```bash
# Check bridge is running
docker-compose ps discord

# Check logs
docker-compose logs discord

# Test webhook
curl -X POST "$DISCORD_WEBHOOK_GENERAL" \
  -H "Content-Type: application/json" \
  -d '{"content":"Test"}'
```

### High Memory Usage
```bash
# Check stats
docker stats fks_data_service

# Check signal backlog
curl http://localhost:8080/api/v1/signals/stats

# Restart if needed
docker-compose restart data-service
```

---

## 🗂️ File Locations

```
fks/
├── run.sh                              # Main management script
├── .env                                # Environment variables (auto-generated)
├── docker-compose.yml                  # Service orchestration
├── config/
│   ├── questdb/init_signals.sql       # QuestDB schema
│   └── prometheus/
│       ├── alertmanager.yml           # Alert configuration
│       └── alerts/                    # Alert rules
├── scripts/
│   ├── testing/
│   │   ├── integration-test.sh        # Integration test
│   │   ├── websocket-soak-test.py     # Soak test
│   │   └── run-backtests.py           # Backtest runner
│   └── monitoring/
│       └── alertmanager-discord.py  # Discord bridge
├── src/data/                          # Data service source
└── docs/
    ├── SIGNALS_STAGING_DEPLOY.md      # Staging guide
    ├── SIGNALS_DEPLOYMENT_CHECKLIST.md # Production checklist
    └── SIGNALS_PRODUCTION_READY.md     # Production summary
```

---

## 🎯 Environment Variables

```bash
# Database
QUESTDB_HOST=questdb
QUESTDB_HTTP_PORT=9000

# JWT Authentication
DATA_SERVICE_JWT_SECRET=<auto-generated>
DATA_SERVICE_JWT_EXPIRY=86400
DATA_SERVICE_JWT_ENABLED=false         # true for production

# Discord Alerts
DISCORD_WEBHOOK_GENERAL=https://discord.com/api/webhooks/...
DISCORD_NOTIFICATIONS_ENABLED=true

# Logging
RUST_LOG=info,fks_data=debug
LOG_LEVEL=info
```

---

## 🚨 Production Deployment

```bash
# 1. Enable JWT
echo "DATA_SERVICE_JWT_ENABLED=true" >> .env

# 2. Configure SSL
./run.sh ssl-init

# 3. Deploy with production overrides
./run.sh prod up

# 4. Verify deployment
./scripts/testing/integration-test.sh --jwt-enabled
```

**See**: `docs/SIGNALS_DEPLOYMENT_CHECKLIST.md` for complete production checklist

---

## 📚 Documentation

- **Quick Start**: `docs/SIGNALS_STAGING_DEPLOY.md`
- **Production Checklist**: `docs/SIGNALS_DEPLOYMENT_CHECKLIST.md`
- **Production Ready**: `docs/SIGNALS_PRODUCTION_READY.md`
- **Testing Guide**: `scripts/testing/README.md`
- **API Reference**: `docs/SIGNALS_API_REFERENCE.md`
- **Next Steps**: `NEXT_STEPS.md`

---

## 💡 Tips

- **Always warmup indicators** before expecting signals
- **Use deep warmup** for long EMAs (EMA-200)
- **Monitor Discord** for critical alerts
- **Check Grafana dashboards** for real-time metrics
- **Run integration test** after any changes
- **Review logs** if signals stop generating

---

## 🆘 Emergency Commands

```bash
# Stop everything
./run.sh down

# Force cleanup (removes volumes - DATA LOSS!)
./run.sh down -v

# Restart everything
./run.sh restart

# Check all service status
docker-compose ps

# View all logs
docker-compose logs -f

# Restart specific service
docker-compose restart data-service
```

---

**Last Updated**: January 2025  
**Version**: 2.1.0  
**Status**: Production Ready