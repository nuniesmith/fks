# FKS Signals System - Deployment Checklist

**Version**: 2.0.0  
**Last Updated**: January 2025  
**Purpose**: Pre-deployment verification and operational readiness checklist

---

## Pre-Deployment Checklist

### 1. Code & Build Verification

- [ ] **Release build passes**
  ```bash
  cd src/data
  cargo build --release
  # Expected: 0 errors, warnings OK
  ```

- [ ] **Binary exists and is executable**
  ```bash
  ls -lh target/release/data-service
  # Expected: ~15MB binary
  ```

- [ ] **All unit tests pass**
  ```bash
  cargo test --release
  # Expected: All tests passing
  ```

- [ ] **No critical warnings**
  ```bash
  cargo clippy --release
  # Expected: No clippy::correctness or clippy::perf warnings
  ```

### 2. Configuration Verification

- [ ] **Environment variables set**
  ```bash
  # Check .env or docker-compose.yml
  grep -E "QUESTDB_HOST|QUESTDB_HTTP_PORT|RUST_LOG|JWT_SECRET|DISCORD_WEBHOOK" docker-compose.yml
  ```
  Required variables:
  - `QUESTDB_HOST=questdb`
  - `QUESTDB_HTTP_PORT=9000`
  - `RUST_LOG=info,fks_data=debug`
  - `DATA_SERVICE_JWT_SECRET=<generated>` (production only)
  - `DATA_SERVICE_JWT_ENABLED=true` (production only)
DISCORD_WEBHOOK_GENERAL
- [ ] **QuestDB schema initialized**
  ```bash
  # Execute init script
  curl -G http://localhost:9000/exec \
    --data-urlencode "query=$(cat config/questdb/init_signals.sql)"
  # Expected: HTTP 200, table created
  ```

- [ ] **Retention script is executable**
  ```bash
  chmod +x scripts/signals_retention_maintenance.sh
  test -x scripts/signals_retention_maintenance.sh && echo "OK"
  ```

- [ ] **Discord webhook configured (for alerts)**
  ```bash
DISCORD_WEBHOOK_GENERALDISCORD_WEBHOOK_GENERAL  ```

- [ ] **JWT secret generated (production)**
  ```bash
  # Check if JWT secret exists in .env
  grep DATA_SERVICE_JWT_SECRET .env | grep -v "^#"
  # Expected: 32+ character random string
  ```

### 3. Infrastructure Readiness

- [ ] **QuestDB running and accessible**
  ```bash
  curl http://localhost:9000/exec?query=SELECT+1
  # Expected: HTTP 200, JSON response
  ```

- [ ] **Redis running and accessible**
  ```bash
  redis-cli ping
  # Expected: PONG
  ```

- [ ] **Prometheus configured**
  ```bash
  grep -r "technical-indicators.yml" config/prometheus/
  # Expected: Alert rules file exists
  ```

- [ ] **Grafana dashboards provisioned**
  ```bash
  ls -l config/grafana/dashboards/technical-indicators.json
  # Expected: Dashboard file exists
  ```

- [ ] **Disk space available (at least 10GB)**
  ```bash
  df -h | grep -E "/$|/var"
  # Expected: 10GB+ available
  ```

### 4. Service Deployment

- [ ] **Docker images built**
  ```bash
  docker-compose build data-service
  # Expected: Image built successfully
  ```

- [ ] **Services start successfully**
  ```bash
  docker-compose up -d data-service questdb redis prometheus grafana discord alertmanager
  # Expected: All containers running
  ```

- [ ] **Discord bridge healthy**
  ```bash
  curl http://localhost:9094/health
  # Expected: {"status": "ok"}
  ```

- [ ] **Service logs show no errors**
  ```bash
  docker-compose logs --tail=50 data-service | grep -i error
  # Expected: No critical errors
  ```

- [ ] **SignalActor started**
  ```bash
  docker-compose logs data-service | grep "Signal actor started"
  # Expected: "✅ Signal actor started (EMA cross, RSI zones, MACD cross, confluence)"
  ```

- [ ] **API server listening**
  ```bash
  docker-compose logs data-service | grep "API server started"
  # Expected: "✅ API server started on port 8080"
  ```


- [ ] **Alertmanager configured for Discord**
  ```bash
  docker-compose logs alertmanager | grep discord
  # Expected: No errors connecting to discord
  ```

---

## Post-Deployment Verification

### 1. Health Checks

- [ ] **Health endpoint responds**
  ```bash
  curl http://localhost:8080/health
  # Expected: {"status": "healthy"}
  ```

- [ ] **Metrics endpoint responds**
  ```bash
  curl http://localhost:8080/metrics | grep signals_generated_total
  # Expected: Prometheus metrics exposed
  ```

- [ ] **JWT authentication status**
  ```bash
  docker-compose logs data-service | grep "JWT authentication"
  # Expected: "JWT authentication is ENABLED" (prod) or "DISABLED" (dev)
  ```

- [ ] **Protected endpoints require auth (production only)**
  ```bash
  # Should fail without token if JWT enabled
  curl http://localhost:8080/api/v1/signals
  # Expected: 401 Unauthorized (if JWT enabled)
  
  # Generate token first (if JWT enabled)
  # TOKEN=$(curl -X POST http://localhost:8080/api/v1/auth/token \
  #   -H "X-Master-Key: YOUR_MASTER_KEY" \
  #   -H "Content-Type: application/json" \
  #   -d '{"subject":"test-user","expiry_seconds":3600}' | jq -r '.token')
  
  # Then use token
  # curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/v1/signals
  ```

### 2. Indicator Warmup

- [ ] **Warmup indicators from QuestDB**
  ```bash
  # Check indicator status
  curl http://localhost:8080/api/v1/indicators/BTCUSD/1m/status
  # Expected: {"all_indicators_ready": true} or false (if no history)
  ```

- [ ] **Deep warmup completes successfully**
  ```bash
  curl -X POST http://localhost:8080/api/v1/indicators/warmup/deep \
    -H "Content-Type: application/json" \
    -d '{"symbols":["BTCUSD"],"timeframes":["1m"],"limit":250}'
  # Expected: HTTP 200, warmup results
  ```

- [ ] **Indicators ready after warmup**
  ```bash
  sleep 30
  curl http://localhost:8080/api/v1/indicators/BTCUSD/1m/status | jq '.all_indicators_ready'
  # Expected: true
  ```

### 3. Signal Generation

- [ ] **Wait for signals to generate (1-2 minutes)**
  ```bash
  sleep 120
  ```

- [ ] **Signals visible in stats**
  ```bash
  curl http://localhost:8080/api/v1/signals/stats | jq '.total_signals'
  # Expected: > 0
  ```

- [ ] **Signals persisted to QuestDB**
  ```bash
  curl "http://localhost:9000/exec?query=SELECT+COUNT(*)+FROM+signals_crypto" | jq '.dataset[0][0]'
  # Expected: > 0
  ```

- [ ] **Signal types detected**
  ```bash
  curl http://localhost:8080/api/v1/signals/stats | jq '.signals_by_type'
  # Expected: JSON object with signal type counts
  ```

### 4. REST API Verification

- [ ] **List all signals**
  ```bash
  curl "http://localhost:8080/api/v1/signals?limit=10" | jq '.count'
  # Expected: Number between 0-10
  ```

- [ ] **Query by symbol**
  ```bash
  curl "http://localhost:8080/api/v1/signals/BTCUSD?limit=5" | jq '.signals[0].symbol'
  # Expected: "BTCUSD"
  ```

- [ ] **Query by symbol and timeframe**
  ```bash
  curl "http://localhost:8080/api/v1/signals/BTCUSD/1m?limit=5" | jq '.signals[0].timeframe'
  # Expected: "1m"
  ```

- [ ] **Filter by signal type**
  ```bash
  curl "http://localhost:8080/api/v1/signals?signal_type=ema_golden_cross&limit=5" | jq '.signals[0].signal_type'
  # Expected: "ema_golden_cross" (if any exist)
  ```

### 5. WebSocket Verification

- [ ] **WebSocket endpoint accessible**
  ```bash
  # Install websocat: https://github.com/vi/websocat
  # Or use wscat: npm install -g wscat
  
  # Connect (this will hang - that's expected)
  timeout 5 websocat ws://localhost:8080/ws/signals || echo "Connection OK"
  ```

- [ ] **WebSocket accepts subscriptions** (manual test)
  ```bash
  # Terminal 1: Connect and subscribe
  websocat ws://localhost:8080/ws/signals
  # Send: {"symbols":["BTCUSD"],"timeframes":["1m"],"signal_types":[]}
  # Expected: Subscription confirmation message
  # Expected: Real-time signals as they're generated
  ```

- [ ] **Prometheus metrics track WebSocket clients**
  ```bash
  curl http://localhost:8080/metrics | grep websocket_clients
  # Expected: websocket_clients gauge
  ```

### 6. Backtesting Verification

- [ ] **Backtest endpoint responds**
  ```bash
  curl -X POST http://localhost:8080/api/v1/signals/backtest \
    -H "Content-Type: application/json" \
    -d '{
      "symbol": "BTCUSD",
      "timeframe": "1m",
      "lookforward_minutes": 60,
      "profit_target_pct": 1.0,
      "stop_loss_pct": 0.5
    }' | jq '.total_signals'
  # Expected: Number >= 0
  ```

- [ ] **Backtest returns valid metrics**
  ```bash
  curl -X POST http://localhost:8080/api/v1/signals/backtest \
    -H "Content-Type: application/json" \
    -d '{"symbol":"BTCUSD","timeframe":"1m"}' | jq '.win_rate'
  # Expected: Number between 0-100 (or null if no signals)
  ```

### 7. Monitoring & Observability

- [ ] **Prometheus scraping metrics**
  ```bash
  curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="data-service")'
  # Expected: Target is UP
  ```

- [ ] **Grafana accessible**
  ```bash
  curl -u admin:admin http://localhost:3000/api/health
  # Expected: {"database": "ok"}
  ```

- [ ] **Technical indicators dashboard loaded**
  ```bash
  curl -u admin:admin http://localhost:3000/api/search | jq '.[] | select(. | contains("Technical"))'
  # Expected: Dashboard name containing "Technical"
  ```

- [ ] **Alert rules loaded**
  ```bash
  curl http://localhost:9090/api/v1/rules | jq '.data.groups[] | select(.name | contains("technical-indicators"))'
  # Expected: Alert rules group
  ```

### 8. Retention Management

- [ ] **Dry-run retention script**
  ```bash
  DRY_RUN=true QUESTDB_HOST=localhost ./scripts/signals_retention_maintenance.sh 90
  # Expected: Script completes successfully, logs preview
  ```

- [ ] **QuestDB partitions visible**
  ```bash
  curl "http://localhost:9000/exec?query=SELECT+DISTINCT+to_str(timestamp,'yyyy-MM-dd')+FROM+signals_crypto+LIMIT+10"
  # Expected: List of partition dates
  ```

- [ ] **Cron job scheduled (production only)**
  ```bash
  crontab -l | grep signals_retention_maintenance.sh
  # Expected: Cron entry (0 2 * * * ...)
  ```

---

## Performance Validation

### 1. Signal Generation Performance

- [ ] **Signal latency < 10ms**
  ```bash
  # Check logs for signal timing
  docker-compose logs data-service | grep "Generated.*signal" | tail -5
  # Expected: Recent signals within last minute
  ```

- [ ] **CPU usage < 20%**
  ```bash
  docker stats data-service --no-stream | awk '{print $3}'
  # Expected: < 20%
  ```

- [ ] **Memory usage < 500MB**
  ```bash
  docker stats data-service --no-stream | awk '{print $4}'
  # Expected: < 500MB
  ```

### 2. API Performance

- [ ] **REST API latency < 100ms**
  ```bash
  time curl -s http://localhost:8080/api/v1/signals/stats > /dev/null
  # Expected: real time < 0.1s
  ```

- [ ] **WebSocket delivery latency < 5ms** (check Prometheus)
  ```bash
  curl http://localhost:8080/metrics | grep signal_delivery_duration
  # Expected: P99 < 0.005
  ```

### 3. Database Performance

- [ ] **QuestDB query latency < 50ms**
  ```bash
  time curl -s "http://localhost:9000/exec?query=SELECT+*+FROM+signals_crypto+LIMIT+10" > /dev/null
  # Expected: real time < 0.05s
  ```

- [ ] **QuestDB disk usage monitored**
  ```bash
  du -sh /var/lib/questdb/db/signals_crypto/
  # Expected: Reasonable size based on retention period
  ```

---

## Security Checklist

### Production Security (Critical for Production)

- [ ] **Enable HTTPS/TLS** (production only)
  - Update nginx/reverse proxy configuration
  - Obtain SSL certificates (Let's Encrypt)
  - Redirect HTTP → HTTPS

- [ ] **Enable JWT authentication** (production only)
  ```bash
  # Set in .env
  DATA_SERVICE_JWT_ENABLED=true
  DATA_SERVICE_JWT_SECRET=<strong-random-secret>
  DATA_SERVICE_JWT_EXPIRY=86400
  
  # Restart service
  docker-compose restart data-service
  
  # Verify JWT is enabled
  docker-compose logs data-service | grep "JWT authentication is ENABLED"
  ```

- [ ] **Secure JWT secret**
  - Use cryptographically random 32+ character secret
  - Never commit to git (use .env, secrets manager)
  - Rotate periodically (e.g., quarterly)
  
- [ ] **API rate limiting** (production only)
  - Implement per-IP rate limiting
  - Add per-token rate limiting
  - Configure nginx/reverse proxy limits

- [ ] **Secure QuestDB access** (production only)
  - Restrict port 9000 to internal network only
  - Add authentication to QuestDB (enterprise feature)
  - Enable ILP authentication

- [ ] **Harden WebSocket** (production only)
  - Add connection authentication
  - Implement per-client rate limiting
  - Add DDoS protection (Cloudflare, etc.)

- [ ] **Secret management**
  - Move API keys to secrets manager (AWS Secrets Manager, Vault)
  - Move Discord webhook URL to secrets manager
  - Rotate credentials regularly
  - Never commit secrets to git
  - Verify .gitignore includes .env

- [ ] **Discord webhook security**
  - Use a private/restricted Discord channel
  - Limit channel access to ops team only
  - Monitor webhook for unauthorized access
  - Regenerate webhook URL if compromised

### Network Security

- [ ] **Firewall rules configured**
  ```bash
  # Allow only necessary ports
  # 8080 - API (with reverse proxy)
  # 9090 - Prometheus (internal only)
  # 3000 - Grafana (internal only)
  # 9000 - QuestDB (internal only)
  ```

- [ ] **Docker network isolation**
  ```bash
  docker network ls | grep fks
  # Expected: Isolated network for services
  ```

---

## Troubleshooting Guide

### Issue: Discord alerts not received

**Symptoms**: Prometheus alerts firing but no Discord messages

**Diagnosis**:
```bash
# 1. Check Discord bridge is running
docker-compose ps discord

# 2. Check Discord bridge logs
docker-compose logs discord | tail -20

# 3. Check alertmanager is sending to bridge
docker-compose logs alertmanager | grep discord

DISCORD_WEBHOOK_GENERAL
```

**Resolution**:
DISCORD_WEBHOOK_GENERAL
# Restart Discord bridge
docker-compose restart discord

# Check bridge health
curl http://localhost:9094/health

# Trigger test alert to verify
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"test","severity":"info"}}]'
```

### Issue: No signals generated

**Symptoms**: `/api/v1/signals/stats` shows 0 total signals

**Diagnosis**:
```bash
# 1. Check if IndicatorActor is running
docker-compose logs data-service | grep "Indicator actor started"

# 2. Check if SignalActor is running
docker-compose logs data-service | grep "Signal actor started"

# 3. Check if indicators are warmed up
curl http://localhost:8080/api/v1/indicators/BTCUSD/1m/status

# 4. Check for errors in logs
docker-compose logs data-service | grep -i error
```

**Resolution**:
```bash
# Force deep warmup
curl -X POST http://localhost:8080/api/v1/indicators/warmup/deep

# Restart service if needed
docker-compose restart data-service
```

### Issue: WebSocket connection rejected

**Symptoms**: WebSocket connection fails or closes immediately

**Diagnosis**:
```bash
# 1. Check if SignalActor is in AppState
docker-compose logs data-service | grep "SignalActor not available"

# 2. Check WebSocket metrics
curl http://localhost:8080/metrics | grep websocket
```

**Resolution**:
```bash
# Restart data-service to reinitialize actors
docker-compose restart data-service
```

### Issue: Backtest returns 0 trades

**Symptoms**: Backtest endpoint returns `total_trades: 0`

**Diagnosis**:
```bash
# 1. Check if signals exist in QuestDB
curl "http://localhost:9000/exec?query=SELECT+COUNT(*)+FROM+signals_crypto"

# 2. Check time range filter
curl "http://localhost:9000/exec?query=SELECT+MIN(timestamp),MAX(timestamp)+FROM+signals_crypto"
```

**Resolution**:
```bash
# Generate signals first
curl -X POST http://localhost:8080/api/v1/indicators/warmup/deep
sleep 120

# Retry backtest
curl -X POST http://localhost:8080/api/v1/signals/backtest \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSD","timeframe":"1m"}'
```

### Issue: High memory usage

**Symptoms**: data-service container using > 1GB memory

**Diagnosis**:
```bash
# Check memory stats
docker stats data-service --no-stream

# Check for memory leaks
docker-compose logs data-service | grep -i "out of memory"
```

**Resolution**:
```bash
# Restart service
docker-compose restart data-service

# If persistent, check for signal backlog
curl http://localhost:8080/api/v1/signals/stats
```

---

## Rollback Procedure

If deployment fails, follow these steps:

1. **Stop new service**
   ```bash
   docker-compose stop data-service
   ```

2. **Restore previous version**
   ```bash
   docker-compose down data-service
   git checkout <previous-commit>
   docker-compose build data-service
   docker-compose up -d data-service
   ```

3. **Verify rollback**
   ```bash
   curl http://localhost:8080/health
   docker-compose logs --tail=50 data-service
   ```

4. **Document incident**
   - Record what failed
   - Note error messages
   - Update runbook with lessons learned

---

## Success Criteria

Deployment is **successful** when ALL of the following are true:

✅ All pre-deployment checklist items completed  
✅ All post-deployment verification items passed  
✅ Signal generation active (signals visible in stats)  
✅ REST API endpoints responding < 100ms  
✅ WebSocket connections stable  
✅ Backtesting returns valid results  
✅ Prometheus metrics exposed  
✅ Grafana dashboards loaded  
✅ No critical errors in logs (last 1 hour)  
✅ CPU usage < 20%, Memory < 500MB  
✅ QuestDB partition count reasonable (< 90 days)

---

## Post-Deployment Tasks

### Immediate (0-24 hours)

- [ ] Monitor logs for errors (every hour for first 24 hours)
- [ ] Verify signal generation rate is within expected range
- [ ] Check WebSocket client connections are stable
- [ ] Validate backtest results against known historical data
- [ ] Verify Discord alerts are being received
- [ ] Test alert escalation (trigger a test critical alert)
- [ ] Run 48-hour WebSocket soak test
  ```bash
  # Install dependencies
  pip install websockets
  
  # Run soak test
  python scripts/testing/websocket-soak-test.py \
    --url ws://localhost:8080/ws/signals \
    --duration 48 \
    --clients 10 \
    --report-interval 300
  ```
- [ ] Run backtests on known strategies
  ```bash
  # Install dependencies
  pip install requests
  
  # Run backtests
  python scripts/testing/run-backtests.py \
    --host localhost:8080 \
    --output ./backtest-results
  ```

### Short-term (1-7 days)

- [ ] Review soak test results (connection stability, message rates)
- [ ] Review backtest results (win rates, profit factors)
- [ ] Run retention maintenance script manually (verify it works)
- [ ] Analyze signal quality from production data
- [ ] Tune signal thresholds based on backtest results
- [ ] Document any issues encountered and resolutions
- [ ] Set up weekly performance review meeting
- [ ] Verify Discord alert routing is working correctly
- [ ] Test alertmanager inhibition rules

### Long-term (1+ months)

- [ ] Review 30-day signal performance metrics
- [ ] Review 30-day WebSocket stability metrics
- [ ] Optimize QuestDB queries based on usage patterns
- [ ] Consider additional signal types based on trader feedback
- [ ] Plan for horizontal scaling if needed
- [ ] Evaluate ML-based signal ranking
- [ ] Review and rotate JWT secrets
- [ ] Review Discord alert effectiveness and tuning

---

## Contacts & Escalation

**Primary Contact**: DevOps Team  
**Secondary Contact**: Data Engineering Team  
**On-Call**: PagerDuty rotation

**Escalation Path**:
1. Check logs and runbook first
2. Search Slack #fks-data-service channel
3. Page on-call engineer if critical
4. Escalate to Engineering Manager if unresolved > 1 hour

---

## Sign-off

**Deployment Date**: ____________________  
**Deployed By**: ____________________  
**Verified By**: ____________________  
**JWT Enabled**: ☐ YES  ☐ NO  
**Discord Alerts**: ☐ CONFIGURED  ☐ NOT CONFIGURED  
**Soak Test**: ☐ PASSED (48h)  ☐ IN PROGRESS  ☐ NOT RUN  
**Backtests**: ☐ PASSED  ☐ FAILED  ☐ NOT RUN  
**Production Ready**: ☐ YES  ☐ NO (reason: _____________)

---

**Document Version**: 1.0  
**Last Updated**: January 2025  
**Next Review Date**: February 2025