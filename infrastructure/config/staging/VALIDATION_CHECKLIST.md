# Staging Validation Checklist
**Data Service - Week 7 Staging Deployment**

This checklist must be completed and signed off before proceeding to production deployment (Week 8).

---

## Pre-Deployment Validation

### Infrastructure Prerequisites
- [ ] Staging VMs provisioned (App: 4 vCPU/8GB RAM, Data: 4 vCPU/16GB RAM)
- [ ] Docker 24.0+ installed on all hosts
- [ ] Docker Compose 2.20+ installed
- [ ] Network connectivity verified (internal VPC + outbound internet)
- [ ] DNS entries configured for internal service discovery
- [ ] Disk space available (minimum 100GB on data VM)
- [ ] SSH access configured for deployment team
- [ ] Firewall rules allow required ports (8080-8083, 9000-9093, etc.)

### Secrets & Configuration
- [ ] `.env` file created with all required secrets
- [ ] Exchange API keys configured (testnet/sandbox where available)
- [ ] Slack webhook URL configured for alerts
- [ ] SMTP credentials configured for email alerts
- [ ] Grafana admin password set (non-default)
- [ ] Data Service API keys generated
- [ ] Secrets stored in secure location (not in git)
- [ ] Configuration file (`config.toml`) reviewed and validated

### Required Files Present
- [ ] `deployment/staging/config.toml`
- [ ] `deployment/staging/docker-compose.staging.yml`
- [ ] `deployment/staging/Dockerfile`
- [ ] `deployment/staging/prometheus-staging.yml`
- [ ] `deployment/staging/alertmanager-staging.yml`
- [ ] `deployment/staging/.env` (with actual secrets)
- [ ] `deployment/scripts/deploy-staging.sh` (executable)

---

## Deployment Execution

### Automated Deployment
- [ ] Run: `./deployment/scripts/deploy-staging.sh`
- [ ] Build completed without errors
- [ ] All infrastructure services started successfully
- [ ] QuestDB schema initialized (staging_trades table created)
- [ ] Data Service started and passed health check
- [ ] All validation tests passed (5/5)
- [ ] Deployment summary displayed with all endpoints

**Deployment Duration:** _________ minutes  
**Deployment By:** _____________  
**Deployment Date:** _____________  

### Manual Verification
- [ ] All containers running: `docker compose ps` shows "Up (healthy)"
- [ ] No error logs in any service during startup
- [ ] All port mappings correct and accessible
- [ ] Service discovery working (containers can resolve each other)

---

## Service Health Validation

### Data Service
```bash
curl http://localhost:8081/health | jq
```
- [ ] Status: `"healthy"`
- [ ] QuestDB check: `"ok"`
- [ ] Redis check: `"ok"`
- [ ] Circuit breaker check: `"ok"`
- [ ] Response time: < 200ms

### QuestDB
```bash
curl http://localhost:9000/status
curl -G http://localhost:9000/exec --data-urlencode "query=SHOW TABLES;"
```
- [ ] HTTP status: 200
- [ ] `staging_trades` table exists
- [ ] Can execute SELECT queries
- [ ] ILP port (9009) accepting connections

### Redis
```bash
docker exec redis-staging redis-cli ping
docker exec redis-staging redis-cli info
```
- [ ] Response: `PONG`
- [ ] Memory usage < 100MB (initial)
- [ ] Connected clients shown
- [ ] Persistence configured (AOF + RDB)

### Prometheus
```bash
curl http://localhost:9091/-/healthy
curl http://localhost:9091/api/v1/targets
```
- [ ] Health check: 200 OK
- [ ] At least 5 targets being scraped
- [ ] `data-service` target status: "up"
- [ ] Scrape errors: 0

### Alertmanager
```bash
curl http://localhost:9093/-/healthy
curl http://localhost:9093/api/v2/alerts
```
- [ ] Health check: 200 OK
- [ ] Configuration loaded successfully
- [ ] Receivers configured (Slack, email)
- [ ] Initial alerts count: 0

### Grafana
```bash
curl http://localhost:3001/api/health
```
- [ ] Health check: 200 OK
- [ ] Login successful (admin / staging_admin_2024)
- [ ] Prometheus datasource connected
- [ ] Can view metrics in Explore tab

---

## Metrics Validation

### Data Service Metrics
```bash
curl -s http://localhost:9090/metrics | grep -E "^(backfill|questdb|circuit_breaker|redis|exchange)_"
```

**Required Metrics (42 total):**

#### Backfill Metrics
- [ ] `backfill_executions_total`
- [ ] `backfill_duration_seconds`
- [ ] `backfill_trades_fetched`
- [ ] `backfill_errors_total`
- [ ] `backfill_active_count`
- [ ] `backfill_verification_status`

#### QuestDB Metrics
- [ ] `questdb_writes_total`
- [ ] `questdb_write_errors_total`
- [ ] `questdb_write_latency_seconds`
- [ ] `questdb_buffer_size`
- [ ] `questdb_buffer_flushes_total`
- [ ] `questdb_verification_status`

#### Circuit Breaker Metrics
- [ ] `circuit_breaker_state`
- [ ] `circuit_breaker_failures`
- [ ] `circuit_breaker_successes`
- [ ] `circuit_breaker_state_changes_total`

#### Exchange Metrics
- [ ] `exchange_requests_total`
- [ ] `exchange_errors_total`
- [ ] `exchange_latency_seconds`

#### Redis Metrics
- [ ] `redis_operations_total`
- [ ] `redis_errors_total`
- [ ] `redis_lock_acquisitions`

#### System Metrics
- [ ] `process_cpu_seconds_total`
- [ ] `process_resident_memory_bytes`
- [ ] `process_virtual_memory_bytes`

### Prometheus Scraping
```bash
curl -s http://localhost:9091/api/v1/targets | jq
```
- [ ] All targets have `"health":"up"`
- [ ] Last scrape times are recent (< 30s)
- [ ] No scrape errors reported

---

## Alert Configuration Validation

### Alert Rules Loaded
```bash
curl -s http://localhost:9091/api/v1/rules | jq '.data.groups[].rules[] | select(.type=="alerting") | .name'
```

**Required Alerts (27 total):**

#### Critical Alerts
- [ ] `CircuitBreakerOpen`
- [ ] `DataCompletenessLow`
- [ ] `BackfillVerificationFailed`
- [ ] `QuestDBWriteFailure`
- [ ] `ServiceDown`
- [ ] `HighBackfillFailureRate`

#### Warning Alerts
- [ ] `RedisConnectionFailed`
- [ ] `HighMemoryUsage`
- [ ] `HighCPUUsage`
- [ ] `HighExchangeErrorRate`
- [ ] `BackfillQueueDepthHigh`
- [ ] `SlowBackfillExecution`
- [ ] `HighWriteLatency`
- [ ] `BufferNearCapacity`

#### Info Alerts
- [ ] `BackfillCompleted`
- [ ] `NewExchangeConnected`
- [ ] `RateLimitApproaching`

### Runbook URLs Present
- [ ] All alerts have `runbook_url` annotation
- [ ] All runbook files exist in `docs/runbooks/`
- [ ] Runbook URLs are accessible

### Alert Routing
- [ ] Critical alerts route to `staging-critical-alerts` Slack channel
- [ ] Warning alerts route to `staging-alerts` Slack channel
- [ ] Inhibition rules configured to prevent alert storms

---

## Dashboard Validation

### Grafana Dashboards
Access: http://localhost:3001

- [ ] **Dashboard 1: Backfill & Orchestration**
  - [ ] Active backfills panel shows data
  - [ ] Backfill success rate graph renders
  - [ ] Circuit breaker state visible
  - [ ] Exchange-specific panels show data
  - [ ] Time range selector works

- [ ] **Dashboard 2: Performance & Ingestion**
  - [ ] QuestDB write rate displays
  - [ ] Buffer utilization visible
  - [ ] Latency histograms show data
  - [ ] Error rate graphs present
  - [ ] System metrics (CPU/memory) visible

### Dashboard Data Flow
- [ ] Trigger test backfill to generate metrics
- [ ] Dashboards update within 30 seconds
- [ ] All panels show non-zero data
- [ ] Graphs render without errors
- [ ] Annotations appear correctly

---

## Functional Testing

### Test 1: Backfill Execution
```bash
curl -X POST http://localhost:8080/api/v1/backfill/start \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "binance",
    "symbol": "BTC/USDT",
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-01T01:00:00Z"
  }'
```
- [ ] Request accepted (HTTP 200 or 202)
- [ ] Backfill ID returned
- [ ] Status endpoint shows backfill as active
- [ ] Metrics show `backfill_active_count` = 1
- [ ] Logs show backfill execution messages
- [ ] Backfill completes successfully
- [ ] Data written to QuestDB (verify with SELECT query)
- [ ] Metrics show `backfill_executions_total` incremented

**Trades Fetched:** _________  
**Duration:** _________ seconds  
**Status:** _________  

### Test 2: Concurrent Backfills
- [ ] Start 2 concurrent backfills (different symbols)
- [ ] Both execute successfully
- [ ] Metrics show `backfill_active_count` = 2
- [ ] No lock contention errors
- [ ] Both write to QuestDB without conflicts

### Test 3: Redis Lock Acquisition
```bash
# Start two identical backfills - second should fail
```
- [ ] First backfill acquires lock
- [ ] Second backfill fails with lock error (HTTP 409)
- [ ] Error message indicates lock is held
- [ ] After first completes, lock is released
- [ ] Subsequent request succeeds

### Test 4: Circuit Breaker (Manual Trigger)
```bash
# If chaos endpoints are enabled:
curl -X POST http://localhost:8080/chaos/circuit-breaker/binance/trigger-failure
```
- [ ] Repeated failures trigger circuit breaker
- [ ] Metrics show `circuit_breaker_state` = 1 (open)
- [ ] Alert fires: `CircuitBreakerOpen`
- [ ] Service stops attempting requests
- [ ] After timeout, transitions to half-open
- [ ] Eventually closes when healthy

### Test 5: Data Verification
```bash
curl -G http://localhost:9000/exec \
  --data-urlencode "query=SELECT count(), min(timestamp), max(timestamp) FROM staging_trades;"
```
- [ ] Query executes successfully
- [ ] Data matches expected backfill range
- [ ] No duplicate trade_ids
- [ ] All required fields populated

---

## Performance Testing

### Load Test Setup
```bash
cd tools/load-test
cargo build --release
```
- [ ] Load test tool compiles successfully
- [ ] Configuration validated

### Sustained Load Test
```bash
cargo run --release -- \
  --mode sustained \
  --rate 10000 \
  --duration 300 \
  --batch-size 1000 \
  --workers 4
```

**Results:**
- [ ] Throughput: _______ trades/sec (target: ≥ 10,000)
- [ ] P50 latency: _______ ms (target: < 100ms)
- [ ] P95 latency: _______ ms (target: < 500ms)
- [ ] P99 latency: _______ ms (target: < 1000ms)
- [ ] Error rate: _______ % (target: < 0.1%)
- [ ] No OOM errors during test
- [ ] Buffer utilization peak: _______ % (target: < 90%)

### Spike Test
```bash
cargo run --release -- \
  --mode spike \
  --rate 50000 \
  --duration 60
```

**Results:**
- [ ] Service handles spike without crashing
- [ ] Circuit breaker did not open inappropriately
- [ ] Buffer absorbed spike (or flushed appropriately)
- [ ] Recovery to baseline within 60 seconds
- [ ] P99 latency during spike: _______ ms

### Resource Monitoring During Load
- [ ] CPU usage < 80% sustained
- [ ] Memory usage < 80% of limit
- [ ] No memory leaks detected (stable over time)
- [ ] QuestDB write queue manageable
- [ ] Redis connection pool stable

---

## Chaos Testing & Runbook Validation

### Setup Chaos Testing Tool
```bash
cd tools/chaos-test
cargo build --release
```
- [ ] Chaos tool compiles successfully
- [ ] Can connect to all services

### Scenario 1: Circuit Breaker Opens
```bash
./target/release/chaos-test circuit-breaker --exchange binance
```
- [ ] Circuit breaker opens after failures
- [ ] Alert fires within 60 seconds
- [ ] Slack notification received
- [ ] Runbook `ALERT_CIRCUIT_BREAKER_OPEN.md` followed
- [ ] Circuit breaker recovers automatically
- [ ] No data loss confirmed

**Time to Alert:** _______ seconds  
**Recovery Time:** _______ seconds  
**Runbook Accurate:** [ ] Yes [ ] No  

### Scenario 2: Data Completeness Gap
```bash
./target/release/chaos-test data-completeness --gap-minutes 120
```
- [ ] Gap created successfully
- [ ] Gap detected within 10 minutes
- [ ] Alert fires: `DataCompletenessLow`
- [ ] Runbook followed to trigger backfill
- [ ] Gap filled successfully
- [ ] Verification query confirms data

**Gap Detection Time:** _______ minutes  
**Gap Fill Time:** _______ minutes  
**Runbook Accurate:** [ ] Yes [ ] No  

### Scenario 3: QuestDB Failure
```bash
./target/release/chaos-test questdb-failure --duration 60
```
- [ ] Writes buffered in memory during outage
- [ ] Circuit breaker engaged for writes
- [ ] Alert fires: `QuestDBWriteFailure`
- [ ] Service remains responsive (health check passes)
- [ ] On recovery, buffer flushes automatically
- [ ] Zero data loss confirmed

**Buffer Peak:** _______ trades  
**Recovery Time:** _______ seconds  
**Data Loss:** [ ] None [ ] Some (amount: _______)  
**Runbook Accurate:** [ ] Yes [ ] No  

### Scenario 4: Redis Failure
```bash
./target/release/chaos-test redis-failure --duration 30
```
- [ ] Lock acquisitions fail gracefully
- [ ] Service returns 503 for lock-dependent operations
- [ ] Alert fires: `RedisConnectionFailed`
- [ ] Service continues for non-lock operations
- [ ] Automatic reconnection on Redis recovery
- [ ] No service restart required

**Graceful Degradation:** [ ] Yes [ ] No  
**Recovery Time:** _______ seconds  
**Runbook Accurate:** [ ] Yes [ ] No  

### Scenario 5: Container Failure
```bash
./target/release/chaos-test kill-container data-service-staging --restart-after 30
```
- [ ] Container killed successfully
- [ ] Alert fires: `ServiceDown`
- [ ] Docker restart policy triggered
- [ ] Service recovers within 60 seconds
- [ ] Dependencies reconnected automatically
- [ ] In-flight requests handled appropriately

**Downtime:** _______ seconds  
**Auto-Recovery:** [ ] Yes [ ] No  
**Runbook Accurate:** [ ] Yes [ ] No  

### Additional Chaos Scenarios (Optional)
- [ ] Memory pressure test
- [ ] Network partition test
- [ ] Exchange error rate simulation
- [ ] Disk I/O saturation

---

## Security Validation

### Access Control
- [ ] Service requires API key for authenticated endpoints
- [ ] Invalid API keys rejected (HTTP 401)
- [ ] Health/metrics endpoints accessible without auth (appropriate)
- [ ] No secrets in logs
- [ ] No secrets in metrics output
- [ ] Grafana requires login (anonymous access disabled)

### Network Security
- [ ] Services use internal network for communication
- [ ] External access limited to documented ports
- [ ] TLS configured where appropriate (or documented as not needed for staging)
- [ ] Redis not exposed to public internet
- [ ] QuestDB console access controlled

### Container Security
- [ ] Data Service runs as non-root user
- [ ] Minimal base image used (debian slim)
- [ ] No unnecessary capabilities granted
- [ ] Resource limits configured
- [ ] Health checks prevent zombie containers

---

## Documentation Review

### Deployment Documentation
- [ ] `docs/sre-training/STAGING_DEPLOYMENT_GUIDE.md` reviewed
- [ ] All steps accurate and up-to-date
- [ ] Screenshots/examples match current deployment
- [ ] Troubleshooting section complete

### Runbooks
- [ ] All 27 runbooks exist in `docs/runbooks/`
- [ ] Critical runbooks fully detailed (not templates)
- [ ] Runbook URLs match Prometheus alert annotations
- [ ] Each runbook has been reviewed by SRE team

### On-Call Reference
- [ ] `docs/sre-training/ONCALL_QUICK_REFERENCE.md` reviewed
- [ ] All endpoints listed are correct
- [ ] Commands tested and work as documented
- [ ] Emergency contacts are current

### Week 7 Summary
- [ ] `docs/WEEK7_SUMMARY.md` reviewed
- [ ] All deliverables documented
- [ ] Test results recorded
- [ ] Known issues documented

---

## Observability Stack Validation

### Log Aggregation
- [ ] Logs are structured (JSON format)
- [ ] Correlation IDs present in logs
- [ ] Log levels appropriate (debug in staging)
- [ ] Can search logs by correlation ID
- [ ] Log rotation configured (max 7 days, 5 backups)

### Metrics Collection
- [ ] All services exposing metrics
- [ ] Prometheus scraping all targets successfully
- [ ] Metrics retention set (30 days)
- [ ] No gaps in metrics data
- [ ] Custom metrics documented

### Alerting
- [ ] Test alert fires successfully
- [ ] Slack integration working
- [ ] Email integration working (if configured)
- [ ] Alert routing correct
- [ ] Alert silencing works
- [ ] Inhibition rules prevent storms

### Tracing (Optional)
- [ ] Jaeger UI accessible
- [ ] Traces visible for requests
- [ ] Spans show latency breakdown
- [ ] Service dependencies visible

---

## Operational Readiness

### SRE Training
- [ ] At least 2 SREs trained on deployment
- [ ] At least 2 SREs trained on runbooks
- [ ] Chaos scenarios rehearsed with team
- [ ] On-call quick reference distributed
- [ ] Q&A session completed

### Incident Response
- [ ] On-call rotation configured
- [ ] Escalation path documented
- [ ] Slack channels configured
- [ ] PagerDuty integration tested (if used)
- [ ] Response time SLA defined

### Backup & Recovery
- [ ] QuestDB data persistence verified
- [ ] Redis persistence verified (AOF + RDB)
- [ ] Backup procedure documented
- [ ] Restore procedure documented and tested
- [ ] Rollback procedure documented

### Change Management
- [ ] Deployment procedure approved
- [ ] Rollback tested successfully
- [ ] Emergency contacts updated
- [ ] Maintenance window defined (if needed)

---

## Sign-Off

### Technical Validation
**Validated By:** _________________  
**Date:** _________________  
**Signature:** _________________  

**Issues Found:** [ ] None [ ] Minor [ ] Major  
**Production Blockers:** [ ] None [ ] List: __________________  

### SRE Team Readiness
**SRE Lead:** _________________  
**Date:** _________________  
**Team Ready for Production:** [ ] Yes [ ] No  

**Comments:** 
_________________________________________________________________
_________________________________________________________________

### Engineering Approval
**Engineering Lead:** _________________  
**Date:** _________________  
**Approve for Production:** [ ] Yes [ ] No  

**Conditions (if any):**
_________________________________________________________________
_________________________________________________________________

### Final Go/No-Go Decision

**Decision:** [ ] GO - Proceed to Week 8 Production Deployment  
             [ ] NO-GO - Address issues and revalidate  

**Decision By:** _________________  
**Date:** _________________  

**Next Steps:**
_________________________________________________________________
_________________________________________________________________

---

## Appendix: Validation Evidence

Attach screenshots, logs, or other evidence:

- [ ] Grafana dashboards showing metrics
- [ ] Load test results (JSON output)
- [ ] Chaos test reports
- [ ] Alert firing evidence (Slack screenshots)
- [ ] Health check outputs
- [ ] Docker compose ps output

**Evidence Location:** _________________

---

**Checklist Version:** 1.0  
**Last Updated:** Week 7  
**Maintained By:** SRE Team  
**Review Frequency:** Each deployment