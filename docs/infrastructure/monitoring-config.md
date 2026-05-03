# FKS Monitoring Stack Configuration

This directory contains the complete monitoring configuration for all FKS services, including Prometheus, Grafana, and Alertmanager.

---

## 📁 Directory Structure

```
config/monitor/
├── README.md                          # This file
├── prometheus.yml                     # Full Prometheus configuration
├── prometheus.slim.yml                # Lightweight config for testing
├── alertmanager.yml                   # Alert routing and notifications
├── grafana.yml                        # Grafana service configuration (if needed)
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── prometheus.yml         # Prometheus datasource config
│   │   └── dashboards/
│   │       └── dashboard.yml          # Dashboard provisioning config
│   └── dashboards/
│       ├── data-factory-rate-limiter.json
│       ├── data-factory-gap-detection.json
│       ├── data-factory-slo-error-budget.json
│       ├── data-factory-operations.json
│       └── rpc_dashboard.json
└── prometheus/
    └── alerts/
        └── data-factory.yml           # Data Factory alert rules
```

---

## 🎯 Quick Start

### 1. Deploy Monitoring Stack

```bash
# Start monitoring services
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# Verify services are running
docker compose ps prometheus grafana alertmanager
```

### 2. Access Dashboards

- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000 (admin/admin)
- **Alertmanager:** http://localhost:9093

### 3. Import Dashboards

Dashboards are auto-provisioned via Grafana's provisioning system. If manual import is needed:

```bash
cd grafana/dashboards
for dashboard in data-factory-*.json; do
  curl -X POST -H "Content-Type: application/json" \
    -d @$dashboard \
    http://admin:admin@localhost:3000/api/dashboards/db
done
```

---

## 📊 Prometheus Configuration

### Full Configuration (`prometheus.yml`)

Comprehensive monitoring for all FKS services:

**Scrape Targets:**
- `data-factory:8080` - Market data ingestion and processing
- `janus:8000` - Core Janus service
- `app:8002` - FKS application
- `monitor:8009` - Monitoring service
- `muscle:8500` - Muscle service
- `questdb:9003` - QuestDB time-series database
- `redis-exporter:9121` - Redis metrics (requires exporter)
- `postgres-exporter:9187` - PostgreSQL metrics (requires exporter)
- `node-exporter:9100` - System metrics

**Key Features:**
- 15-second scrape interval
- Alerting to Alertmanager on port 9093
- Alert rules loaded from `/etc/prometheus/alerts/*.yml`
- Metric relabeling to preserve SLI/SLO metrics
- Production-grade defaults

### Slim Configuration (`prometheus.slim.yml`)

Lightweight configuration for HyroTrader challenge and testing:

**Optimizations:**
- 5-second scrape interval for real-time performance
- Focused on critical path metrics only
- Minimal storage overhead via metric filtering
- Targets: forward, gateway, redis, questdb

**Use Cases:**
- Performance testing
- Local development
- Resource-constrained environments

---

## 🔔 Alertmanager Configuration

### Overview

Alertmanager handles alert routing, grouping, inhibition, and notification delivery.

**File:** `alertmanager.yml`

### Alert Severity Levels

| Severity | Response Time | Notification Channel | Example Alerts |
|----------|---------------|---------------------|----------------|
| **Critical** | Immediate (5s) | Slack + PagerDuty | DataCompletenessLow, AllExchangesDown |
| **Warning** | 30s | Slack only | ExchangeDisconnected, DiskUsageWarning |
| **Info** | 1m | Slack (low priority) | CircuitBreakerHalfOpen, ServiceRestart |

### Notification Channels

1. **Slack Channels:**
   - `#fks-incidents` - Critical alerts
   - `#fks-alerts` - Warnings and info
   - `#janus-alerts` - Janus-specific alerts
   - `#database-alerts` - Database-specific alerts

2. **PagerDuty:**
   - Critical alerts trigger on-call escalation
   - 4-hour repeat interval for unresolved alerts

### Configuration Steps

1. **Update Slack Webhook URL:**
   ```yaml
   global:
     slack_api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
   ```

2. **Update PagerDuty Service Key:**
   ```yaml
   pagerduty_configs:
     - service_key: 'YOUR_PAGERDUTY_SERVICE_KEY'
   ```

3. **Test Notifications:**
   ```bash
   # Send test alert
   curl -X POST http://localhost:9093/api/v1/alerts \
     -H "Content-Type: application/json" \
     -d '[{"labels":{"alertname":"TestAlert","severity":"info"},"annotations":{"summary":"Test notification"}}]'
   ```

### Inhibition Rules

Alertmanager suppresses redundant alerts:

- Warning alerts suppressed when critical alert fires for same service
- Info alerts suppressed when warning/critical fires
- Individual exchange disconnections suppressed when all exchanges are down
- Rate limit rejections suppressed when circuit breaker is open
- Disk usage warnings suppressed when critical threshold reached

---

## 📈 Grafana Dashboards

### Data Factory Dashboards

#### 1. Rate Limiter Dashboard (`data-factory-rate-limiter.json`)

**Metrics:**
- Request rate and throughput
- Token bucket utilization
- Circuit breaker state with color coding
- Rejection rate percentage
- Acquire latency (P50/P95/P99)
- Circuit breaker events and failure count

**Use Cases:**
- Monitor rate limiting effectiveness
- Detect circuit breaker issues
- Troubleshoot API throttling

---

#### 2. Gap Detection Dashboard (`data-factory-gap-detection.json`)

**Metrics:**
- Detection accuracy (>99% threshold)
- Active gaps count
- False positive rate
- Gap detection and fill events
- Gap check and fill latency percentiles
- Gap size distribution
- Internal state (bloom filter, sequence map)

**Use Cases:**
- Monitor data completeness
- Track backfill performance
- Identify systematic gaps

---

#### 3. SLO & Error Budget Dashboard (`data-factory-slo-error-budget.json`)

**Metrics:**
- Data completeness (99.9% SLO)
- Ingestion latency P99 (1000ms SLO)
- QuestDB disk usage
- Error budget remaining
- Latency percentiles over time
- WebSocket connection status
- SLI summary table

**Use Cases:**
- Track SLO compliance
- Monitor error budget consumption
- Executive-level health overview

---

#### 4. Operations Overview Dashboard (`data-factory-operations.json`)

**Metrics:**
- Service health status
- Active exchanges count
- Message ingestion rates
- QuestDB write performance
- CPU and memory usage
- Disk usage trends
- Network I/O
- Backfill activity

**Use Cases:**
- Daily operational monitoring
- System health checks
- Capacity planning

---

### Dashboard Features

- **Auto-refresh:** 10-30 seconds
- **Thresholds:** Color-coded based on SLO targets
- **Linked Navigation:** Jump between related dashboards
- **Time Selectors:** Flexible time range controls
- **Annotations:** Mark deployments and incidents

---

## 🚨 Alert Rules

### File Structure

Alert rules are organized in `prometheus/alerts/`:

```
prometheus/alerts/
└── data-factory.yml    # 13 alerts across 3 severity levels
```

### Alert Groups

#### Critical Alerts (5)

1. **DataCompletenessLow**
   - Condition: `data_completeness_percent < 99.9` for 5m
   - Impact: SLO violation, potential data loss
   - Runbook: `docs/runbooks/data-completeness-low.md`

2. **IngestionLatencyHigh**
   - Condition: P99 > 1000ms for 5m
   - Impact: Stale market data
   - Runbook: `docs/runbooks/ingestion-latency-high.md`

3. **CircuitBreakerOpen**
   - Condition: Circuit breaker state = 1 for 1m
   - Impact: All requests blocked
   - Runbook: `docs/runbooks/circuit-breaker-open.md`

4. **DiskUsageHigh**
   - Condition: QuestDB disk > 80% for 5m
   - Impact: Risk of write failures
   - Runbook: `docs/runbooks/disk-usage-high.md`

5. **AllExchangesDown**
   - Condition: No WebSocket connections for 1m
   - Impact: Complete data loss
   - Runbook: `docs/runbooks/all-exchanges-down.md`

#### Warning Alerts (8)

- DataCompletenessWarning (<99.95%)
- HighRateLimitRejectionRate (>10%)
- GapDetectionAccuracyLow (<99%)
- ActiveGapsHigh (>10 gaps)
- ExchangeDisconnected (single exchange)
- DiskUsageWarning (70-80%)
- HighBackfillQueueSize (>100 items)
- QuestDBWriteErrors (>0.1/sec)

#### Info Alerts (3)

- CircuitBreakerHalfOpen (testing recovery)
- DataFactoryRestarted (service restart)
- HighWebSocketReconnectionRate (frequent reconnects)

---

## 🔧 Configuration Management

### Environment-Specific Configs

1. **Development:**
   ```bash
   # Use slim config for faster iteration
   cp prometheus.slim.yml prometheus.yml
   ```

2. **Staging:**
   ```bash
   # Use full config with reduced retention
   # Set in docker-compose: --storage.tsdb.retention.time=7d
   ```

3. **Production:**
   ```bash
   # Use full config with extended retention
   # Set in docker-compose: --storage.tsdb.retention.time=30d
   ```

### Updating Configurations

1. **Reload Prometheus without restart:**
   ```bash
   curl -X POST http://localhost:9090/-/reload
   ```

2. **Reload Alertmanager:**
   ```bash
   curl -X POST http://localhost:9093/-/reload
   ```

3. **Restart Grafana (for provisioning changes):**
   ```bash
   docker compose restart grafana
   ```

### Validation

```bash
# Validate Prometheus config
promtool check config prometheus.yml

# Validate alert rules
promtool check rules prometheus/alerts/*.yml

# Test Prometheus queries
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=data_completeness_percent'
```

---

## 📊 Metrics Reference

### Data Factory Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `data_completeness_percent` | Gauge | Percentage of expected data received (SLO: 99.9%) |
| `ingestion_latency_ms` | Histogram | Time from message receipt to storage (SLO: P99 < 1000ms) |
| `circuit_breaker_state` | Gauge | 0=Closed, 1=Open, 2=Half-Open |
| `rate_limiter_total_requests` | Counter | Total requests processed |
| `rate_limiter_rejected_requests` | Counter | Requests rejected by rate limiter |
| `gap_detection_active_gaps` | Gauge | Number of gaps currently being filled |
| `gap_detection_accuracy_percent` | Gauge | Gap detection accuracy |
| `websocket_connected` | Gauge | WebSocket connection status (1=up, 0=down) |
| `websocket_messages_received_total` | Counter | Messages received per exchange |
| `questdb_disk_usage_percent` | Gauge | QuestDB disk usage percentage |
| `questdb_writes_total` | Counter | Total writes to QuestDB |
| `backfill_queue_size` | Gauge | Number of pending backfill requests |

### System Metrics (via node-exporter)

- CPU usage
- Memory usage
- Disk I/O
- Network traffic
- Filesystem usage

---

## 🔐 Security Best Practices

### 1. Secure Webhook URLs

```bash
# Store webhooks as Docker secrets
echo "https://hooks.slack.com/..." | docker secret create slack_webhook -
docker secret create pagerduty_key /path/to/key
```

### 2. Restrict Network Access

```yaml
# In docker-compose, don't expose Prometheus publicly
services:
  prometheus:
    expose:
      - "9090"  # Only accessible within Docker network
```

### 3. Enable Authentication

```yaml
# Grafana authentication
environment:
  - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
  - GF_AUTH_ANONYMOUS_ENABLED=false
```

### 4. Use HTTPS

Add reverse proxy (nginx/Traefik) for HTTPS termination in production.

---

## 🐛 Troubleshooting

### Prometheus Not Scraping Targets

**Problem:** Targets show as DOWN in Prometheus

**Solutions:**
```bash
# Check target accessibility
curl http://data-factory:8080/metrics

# Verify Docker network
docker network inspect fks_default

# Check Prometheus logs
docker logs prometheus
```

### Grafana Dashboards Empty

**Problem:** Dashboards show "No Data"

**Solutions:**
```bash
# Verify Prometheus datasource
curl -u admin:admin http://localhost:3000/api/datasources

# Check if metrics exist
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=up'

# Reimport dashboards
cd grafana/dashboards
curl -X POST -u admin:admin \
  -H "Content-Type: application/json" \
  -d @data-factory-slo-error-budget.json \
  http://localhost:3000/api/dashboards/db
```

### Alerts Not Firing

**Problem:** Conditions met but no alerts

**Solutions:**
```bash
# Validate alert rules
promtool check rules prometheus/alerts/data-factory.yml

# Check alert evaluation in Prometheus
curl http://localhost:9090/api/v1/rules | jq

# Verify Alertmanager connectivity
curl http://localhost:9090/api/v1/alertmanagers

# Check Alertmanager status
curl http://localhost:9093/api/v2/status
```

### Slack Notifications Failing

**Problem:** Alerts fire but no Slack messages

**Solutions:**
```bash
# Test webhook directly
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test from Alertmanager"}' \
  YOUR_SLACK_WEBHOOK_URL

# Check Alertmanager logs
docker logs alertmanager | grep -i slack

# Verify webhook URL in config
grep slack_api_url alertmanager.yml
```

---

## 📚 Additional Resources

### Documentation
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Alertmanager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [FKS Runbooks](../../docs/runbooks/README.md)
- [FKS SLI/SLO Definitions](../../docs/spike-validation/SLI_SLO.md)

### Configuration Examples
- [Prometheus Configuration](https://github.com/prometheus/prometheus/blob/main/documentation/examples/prometheus.yml)
- [Alertmanager Configuration](https://github.com/prometheus/alertmanager/blob/main/doc/examples/simple.yml)
- [Grafana Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)

### Query References
- [PromQL Cheat Sheet](https://promlabs.com/promql-cheat-sheet/)
- [Grafana Query Fundamentals](https://grafana.com/docs/grafana/latest/fundamentals/query/)

---

## 🔄 Maintenance

### Weekly Tasks
- Review dashboard performance
- Update alert thresholds based on actual metrics
- Check for Prometheus/Grafana updates

### Monthly Tasks
- Review alert rule effectiveness (false positive rate)
- Update dashboards based on operational feedback
- Prune old metrics (adjust retention policies)
- Rotate webhook URLs and API keys

### Quarterly Tasks
- Comprehensive monitoring stack review
- Load test monitoring system (simulate high alert volume)
- Update runbooks based on incident learnings
- Capacity planning for metrics storage

---

**Last Updated:** 2025-12-30  
**Maintained By:** FKS SRE Team  
**Questions?** Contact #fks-sre on Slack
