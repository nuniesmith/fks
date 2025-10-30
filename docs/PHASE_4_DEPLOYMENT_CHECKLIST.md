# Phase 4 Deployment Checklist

## Pre-Deployment (Before `docker-compose up`)

- [ ] **Environment Variables**: Verify `.env` file exists with:
  ```bash
  REDIS_URL=redis://:@redis:6379/1
  REDIS_PASSWORD=
  ```

- [ ] **Dockerfile Check**: Ensure `docker/Dockerfile.app` has TA-Lib and Python 3.13
  ```bash
  cat docker/Dockerfile.app | grep -E "python:3.13|ta-lib"
  ```

- [ ] **Requirements Verified**: Check `src/services/app/requirements.txt` contains:
  - pandas>=2.2.0
  - numpy>=1.26.0,<2.0
  - optuna>=4.0.0
  - ccxt>=4.0.0
  - prometheus-client>=0.20.0
  - redis>=5.0.0

## Deployment Steps

### 1. Build Containers
```bash
# Rebuild fks_app with new dependencies
docker-compose build fks_app

# Optional: Rebuild all if needed
docker-compose build
```

### 2. Start Services
```bash
# Stop existing services
docker-compose down

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

Expected output:
```
fks_app         running   0.0.0.0:8002->8002/tcp
fks_redis       running   0.0.0.0:6379->6379/tcp
celery_beat     running
celery_worker   running
prometheus      running   0.0.0.0:9090->9090/tcp
grafana         running   0.0.0.0:3000->3000/tcp
```

### 3. Verify Celery Beat Schedule
```bash
docker-compose exec celery_beat celery -A web.django.celery inspect scheduled
```

Look for:
```
asmbtr-predictions: every 60.0 seconds
```

### 4. Check ASMBTR Task Execution
```bash
# Watch live logs
docker-compose logs -f fks_app | grep asmbtr

# Expected output (every 60 seconds):
# 🚀 ASMBTR prediction task started for ['BTC/USDT', 'ETH/USDT']
# 🔮 Starting ASMBTR prediction cycle for 2 symbols
# 📈 Fetched 100 ticks for BTC/USDT
# 🔄 BTC/USDT state: 10110011
# ✅ BTC/USDT prediction: 1 (confidence: 65.00%)
# 💾 Stored prediction for BTC/USDT in Redis
# ✅ ASMBTR prediction cycle complete
```

### 5. Verify Redis Storage
```bash
# Check stored predictions
docker-compose exec redis redis-cli -a "${REDIS_PASSWORD:-}" KEYS "asmbtr:predictions:*"

# Expected output:
# 1) "asmbtr:predictions:BTC/USDT"
# 2) "asmbtr:predictions:ETH/USDT"

# View prediction data
docker-compose exec redis redis-cli -a "${REDIS_PASSWORD:-}" GET "asmbtr:predictions:BTC/USDT"

# Expected JSON output:
# {"symbol":"BTC/USDT","state":"10110011","prediction":1,"confidence":0.65,...}
```

### 6. Check Prometheus Metrics
```bash
# Test metrics endpoint
curl http://localhost:8002/metrics | grep asmbtr

# Expected output (sample):
# asmbtr_state_transitions_total{symbol="BTC/USDT",from_state="10101010",to_state="10110011"} 5.0
# asmbtr_prediction_confidence{symbol="BTC/USDT"} 0.65
# asmbtr_predictions_total{symbol="BTC/USDT",prediction="UP"} 10.0
# asmbtr_execution_duration_seconds_sum{symbol="BTC/USDT"} 1.234
```

### 7. Verify Prometheus Scraping
```bash
# Open Prometheus UI
open http://localhost:9090

# Navigate to Status → Targets
# Ensure "fks_app" target shows "UP" status
```

Or via curl:
```bash
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="fks_app")'
```

### 8. Access Grafana Dashboard
```bash
# Open Grafana
open http://localhost:3000

# Login: admin / admin
# Navigate to Dashboards → "ASMBTR Strategy Dashboard"
```

**Expected Dashboard**:
- State Distribution Pie Chart: Shows recent state transitions
- Prediction Confidence: Gauges showing 60-80% (if predictions are generated)
- Prediction Accuracy: Empty initially (needs actual outcomes)
- Predictions by Direction: Bar chart showing UP/DOWN/NEUTRAL counts
- Avg Execution Time: <2 seconds (green), should be around 0.5-1.5s
- State Transition Heatmap: Shows common BTC/USDT state paths
- Summary Stats: Total predictions, avg confidence, transitions

## Post-Deployment Verification

### Health Checks
- [ ] **fks_app Health**: `curl http://localhost:8002/health` → `{"status":"healthy"}`
- [ ] **Redis Connection**: `docker-compose exec redis redis-cli ping` → `PONG`
- [ ] **Celery Beat Running**: `docker-compose ps celery_beat` → `Up`
- [ ] **Prometheus Scraping**: `curl http://localhost:9090/api/v1/targets` → fks_app `"health":"up"`
- [ ] **Grafana Dashboard**: Access http://localhost:3000 → ASMBTR dashboard visible

### Functional Tests
- [ ] **Predictions Generated**: Redis has `asmbtr:predictions:*` keys
- [ ] **Metrics Emitted**: `curl http://localhost:8002/metrics | grep asmbtr_predictions_total`
- [ ] **State Transitions Tracked**: Grafana pie chart shows data
- [ ] **Execution Time Healthy**: Grafana bar gauge shows <2s (green)

### Performance Baselines
- [ ] **Prediction Frequency**: 1 prediction every 60 seconds (2 symbols × 1/min = 2/min)
- [ ] **Execution Time**: <2 seconds per symbol
- [ ] **Redis TTL**: Predictions expire after 120 seconds
- [ ] **Prometheus Scrape Interval**: 30 seconds

## Troubleshooting

### No Predictions Generated
**Check**:
1. Celery Beat running: `docker-compose ps celery_beat`
2. Task logs: `docker-compose logs fks_app | grep asmbtr`
3. CCXT API access: `docker-compose exec fks_app python -c "import ccxt; ccxt.binance().fetch_ticker('BTC/USDT')"`

**Fix**:
- Restart Celery Beat: `docker-compose restart celery_beat`
- Check network connectivity to Binance
- Verify ASMBTR confidence threshold (default: 60% may be too high initially)

### Metrics Not Showing in Grafana
**Check**:
1. Prometheus targets: http://localhost:9090/targets → fks_app should be "UP"
2. Metrics endpoint: `curl http://localhost:8002/metrics | head -20`
3. Prometheus query: http://localhost:9090/graph → Query `asmbtr_predictions_total`

**Fix**:
- Reload Prometheus: `docker-compose exec prometheus kill -HUP 1`
- Restart Grafana: `docker-compose restart grafana`
- Check Prometheus config: `cat monitoring/prometheus/prometheus.yml | grep fks_app`

### High Execution Time (>5s)
**Check**:
1. CCXT rate limiting: Task logs showing rate limit errors
2. Network latency: `ping api.binance.com`
3. Redis connection: `docker-compose exec fks_app redis-cli -h redis ping`

**Fix**:
- Reduce tick fetch limit: Edit `asmbtr_prediction.py` → `fetch_latest_ticks(symbol, limit=50)`
- Add caching: Cache CCXT exchange instance
- Check Redis health: `docker-compose logs redis | tail -20`

## Monitoring Ongoing Operations

### Daily Checks
```bash
# View last 100 ASMBTR task executions
docker-compose logs --tail=100 fks_app | grep "ASMBTR prediction"

# Check prediction count (should be ~2880/day for 2 symbols at 60s)
docker-compose exec redis redis-cli -a "${REDIS_PASSWORD:-}" KEYS "asmbtr:predictions:*" | wc -l

# View Grafana summary stats (1-hour window)
open http://localhost:3000/d/asmbtr-dashboard
```

### Weekly Review
- [ ] **Prediction Accuracy**: Review Grafana accuracy time series (once actual outcomes available)
- [ ] **State Distribution**: Check if state patterns are balanced or skewed
- [ ] **Execution Performance**: Ensure avg execution time remains <2s
- [ ] **Error Rate**: Check Celery logs for task failures

### Monthly Maintenance
- [ ] **Retrain Models**: Fetch new data, re-run optimization (Phase 3.8)
- [ ] **Update Thresholds**: Adjust confidence threshold based on accuracy data
- [ ] **Review Symbols**: Add/remove trading pairs based on performance
- [ ] **Prometheus Retention**: Verify metrics retention policy

## Rollback Plan

### If Deployment Fails
```bash
# Stop services
docker-compose down

# Revert code changes (if using git)
git checkout HEAD~1 src/services/app/src/tasks/
git checkout HEAD~1 src/services/app/src/metrics/
git checkout HEAD~1 src/services/web/src/django/celery.py

# Rebuild with old code
docker-compose build fks_app

# Restart
docker-compose up -d
```

### If Performance Issues
```bash
# Disable ASMBTR task temporarily
# Edit celery.py, comment out 'asmbtr-predictions' entry
# Restart Celery Beat
docker-compose restart celery_beat
```

## Success Criteria

✅ **Deployment Successful** if:
1. Celery Beat shows `asmbtr-predictions` in schedule
2. fks_app logs show prediction cycles every 60 seconds
3. Redis contains `asmbtr:predictions:*` keys with valid JSON
4. Prometheus scrapes fks_app:8002/metrics successfully
5. Grafana dashboard displays all 7 panels with data
6. No errors in `docker-compose logs` for 5 minutes
7. Execution time consistently <2 seconds

---

**Deployment Status**: ⏳ Pending  
**Next Action**: Run through checklist during `make up` or `docker-compose up`  
**Documentation**: See `docs/PHASE_4_COMPLETE.md` for full implementation details
