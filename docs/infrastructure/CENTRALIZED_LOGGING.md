# Centralized Logging with Grafana Loki

## Overview

The FKS Trading Platform now uses **Grafana Loki** for centralized log aggregation, allowing you to view logs from all 15+ services in one place through the Grafana UI.

```
┌─────────────────────────────────────────────────────────────┐
│                    Centralized Logging Stack                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Forward  │  │ Backward │  │ Gateway  │  │  Nginx   │   │
│  │  (Rust)  │  │  (Rust)  │  │ (Python) │  │ (Access) │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │           │
│       └─────────────┴─────────────┴─────────────┘           │
│                         │                                    │
│                    ┌────▼────┐                              │
│                    │Promtail │ ◄── Collects Docker logs     │
│                    └────┬────┘                              │
│                         │                                    │
│                    ┌────▼────┐                              │
│                    │  Loki   │ ◄── Stores & indexes logs    │
│                    └────┬────┘                              │
│                         │                                    │
│                    ┌────▼────┐                              │
│                    │ Grafana │ ◄── Query & visualize        │
│                    └─────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. **Grafana Loki** (Port 3100)
- **Purpose**: Log aggregation and storage
- **Storage**: Local filesystem with 7-day retention (configurable)
- **Features**:
  - Label-based indexing (like Prometheus)
  - Compressed storage
  - Fast queries
  - Built-in log retention

### 2. **Promtail** (Port 9080)
- **Purpose**: Log collection agent
- **Source**: Reads Docker container logs via `/var/run/docker.sock`
- **Features**:
  - Automatic service discovery
  - Label extraction
  - Log parsing and enrichment
  - Batching for performance

### 3. **Grafana** (Port 3001)
- **Purpose**: Log visualization and querying
- **Features**:
  - Explore logs with LogQL
  - Build dashboards
  - Set up alerts
  - Correlate logs with metrics

## Quick Start

### 1. Start the Logging Stack

```bash
# Start all services including Loki and Promtail
./run.sh up

# Or start only logging services
docker compose up -d loki promtail grafana
```

### 2. Verify Services are Running

```bash
# Check service health
./run.sh diagnose

# Or check manually
docker ps | grep -E "loki|promtail"
curl http://localhost:3100/ready  # Loki health
```

### 3. Access Grafana

1. Open browser: http://localhost:3001
2. Login (default: admin/admin)
3. Navigate to **Explore** (compass icon on left sidebar)
4. Select **Loki** datasource from the dropdown

## Viewing Logs in Grafana

### Method 1: Explore UI (Interactive)

1. **Open Explore**: http://localhost:3001/explore
2. **Select Loki** datasource
3. **Use Label Filters**:
   - Click "Label filters" button
   - Select service (e.g., `service="gateway"`)
   - Add more filters as needed

### Method 2: LogQL Queries

LogQL is Loki's query language (similar to PromQL). Here are common queries:

#### Basic Queries

```logql
# All logs from gateway service
{service="gateway"}

# All logs from Rust services
{service=~"forward|backward|data|cns|audit"}

# All ERROR level logs
{level="ERROR"}

# Logs from specific container
{container="fks_forward"}

# Combine filters
{service="gateway", level="ERROR"}
```

#### Advanced Queries

```logql
# Search for specific text
{service="gateway"} |= "signal received"

# Exclude certain patterns
{service="nginx"} != "health check"

# Regex matching
{service="gateway"} |~ "order_id=[a-zA-Z0-9]+"

# Case-insensitive search
{service="gateway"} |~ "(?i)error"

# Rate of logs (logs per second)
rate({service="gateway"}[5m])

# Count ERROR logs in last hour
sum(count_over_time({level="ERROR"}[1h]))

# Top 10 services by log volume
topk(10, sum by (service) (rate({job="docker"}[5m])))
```

#### Time-Based Queries

```logql
# Logs from last 5 minutes
{service="forward"}

# Logs from specific time range (use time picker in UI)
# Or in query:
{service="gateway"} [2024-01-02T10:00:00Z:2024-01-02T11:00:00Z]
```

#### Aggregations

```logql
# Count logs by service
sum by (service) (count_over_time({job="docker"}[5m]))

# Average request latency (if logged)
avg_over_time({service="gateway"} | json | unwrap latency_ms [5m])

# 95th percentile of response times
quantile_over_time(0.95, {service="nginx"} | json | unwrap request_time [5m])
```

## Service-Specific Log Queries

### Rust Services (Forward, Backward, Data Factory)

```logql
# All Rust service logs
{service=~"forward|backward|data"}

# Rust errors with stack traces
{service=~"forward|backward|data", level="ERROR"}

# Trading signals
{service="forward"} |= "signal"

# Order executions
{service="forward"} |= "order" |= "filled"

# Performance metrics
{service="forward"} |~ "latency|duration"

# Specific module logs
{service="forward", target=~"janus_forward.*"}
```

### Python Gateway

```logql
# All gateway logs
{service="gateway"}

# API requests
{service="gateway"} |= "request_id"

# Slow requests (>100ms)
{service="gateway"} |~ "duration.*[1-9][0-9]{2,}"

# Errors with traceback
{service="gateway", level="ERROR"}

# Specific endpoint
{service="gateway"} |= "/api/signals"
```

### Nginx Access Logs

```logql
# All access logs
{service="nginx", stream="stdout"}

# 4xx errors (client errors)
{service="nginx", stream="stdout", status=~"4.*"}

# 5xx errors (server errors)  
{service="nginx", stream="stdout", status=~"5.*"}

# Specific endpoint hits
{service="nginx"} |= "/api/health"

# High latency requests
{service="nginx"} | json | request_time > 1.0
```

### Database Logs (QuestDB, PostgreSQL)

```logql
# QuestDB logs
{service="questdb"}

# PostgreSQL logs
{service="postgres"}

# Database errors
{service=~"questdb|postgres", level=~"ERROR|FATAL"}

# Slow queries
{service="postgres"} |= "duration:" |~ "duration: [5-9][0-9]{2,}"
```

### Monitoring Stack

```logql
# Prometheus logs
{service="prometheus"}

# Grafana logs
{service="grafana"}

# Jaeger traces
{service="jaeger"}

# All monitoring errors
{service=~"prometheus|grafana|jaeger", level="ERROR"}
```

## Creating Log Dashboards

### 1. Create a New Dashboard

1. Go to **Dashboards** → **New Dashboard**
2. Click **Add visualization**
3. Select **Loki** datasource

### 2. Add Log Panels

#### Panel 1: Recent Errors
```logql
{level="ERROR"}
```
- Visualization: Logs
- Options: Show time, Show labels

#### Panel 2: Logs by Service
```logql
sum by (service) (count_over_time({job="docker"}[5m]))
```
- Visualization: Bar chart or Time series

#### Panel 3: Request Rate
```logql
sum(rate({service="gateway"} |= "request_id" [5m]))
```
- Visualization: Time series

#### Panel 4: Error Rate by Service
```logql
sum by (service) (rate({level="ERROR"}[5m]))
```
- Visualization: Time series
- Alert threshold: > 10 errors/min

### 3. Save Dashboard

- Click **Save dashboard** (top right)
- Give it a name: "FKS System Logs"
- Set folder: "FKS Trading"

## Log Retention & Storage

### Current Configuration

```yaml
Default Retention: 7 days (168 hours)
Storage Location: Docker volume 'loki_data'
Chunk Size: 256KB
Compression: Enabled
Max Storage: Unlimited (disk space dependent)
```

### Adjust Retention Period

Edit `config/loki/loki-config.yml`:

```yaml
limits_config:
  retention_period: 168h  # Change this (e.g., 720h = 30 days)

table_manager:
  retention_period: 168h  # Must match above
```

Then restart Loki:
```bash
docker compose restart loki
```

### Monitor Storage Usage

```bash
# Check Loki data volume size
docker exec fks_loki du -sh /loki/chunks

# Full breakdown
docker exec fks_loki du -h /loki
```

### Clean Up Old Logs

```bash
# Loki automatically deletes logs based on retention policy
# To force immediate cleanup:
docker exec fks_loki rm -rf /loki/chunks/*
docker compose restart loki
```

## Alerts on Logs

### 1. Create Alert Rule in Loki

Edit `config/loki/rules/alerts.yml`:

```yaml
groups:
  - name: fks_alerts
    interval: 1m
    rules:
      # Alert on error spike
      - alert: HighErrorRate
        expr: |
          sum by (service) (rate({level="ERROR"}[5m])) > 10
        for: 2m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "High error rate in {{ $labels.service }}"
          description: "Service {{ $labels.service }} is logging > 10 errors/min"

      # Alert on service down
      - alert: ServiceNotLogging
        expr: |
          absent_over_time({service="forward"}[10m])
        for: 5m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Service forward not producing logs"
          description: "No logs from forward service in 10 minutes"

      # Alert on critical errors
      - alert: CriticalError
        expr: |
          {level="ERROR"} |= "CRITICAL" or {level="FATAL"}
        for: 0m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Critical error detected"
          description: "{{ $labels.service }} logged a critical/fatal error"
```

### 2. Configure AlertManager

Alerts will be sent to AlertManager (already running on port 9093).

Edit `config/alertmanager/alertmanager.yml` to configure notifications (Slack, email, PagerDuty, etc.)

## Performance Tuning

### For High Log Volume

If you're generating > 100 MB/day of logs:

1. **Increase Loki Resources** (`docker-compose.yml`):
```yaml
loki:
  deploy:
    resources:
      limits:
        cpus: "2.0"
        memory: 2g
      reservations:
        cpus: "0.5"
        memory: 512m
```

2. **Tune Promtail Batch Size** (`config/loki/promtail-config.yml`):
```yaml
clients:
  - url: http://loki:3100/loki/api/v1/push
    batchwait: 500ms      # Smaller wait = faster
    batchsize: 2097152    # 2MB batches
```

3. **Increase Ingestion Rate** (`config/loki/loki-config.yml`):
```yaml
limits_config:
  ingestion_rate_mb: 32
  ingestion_burst_size_mb: 64
```

### For Better Query Performance

1. **Use specific labels** in queries (faster):
   ```logql
   {service="gateway", level="ERROR"}  # Good
   {level="ERROR"}                     # Slower
   ```

2. **Limit time range**:
   - Use time picker to query shorter periods
   - Default: Last 1 hour is fast
   - Last 7 days: can be slow

3. **Use `|=` for simple text search**:
   ```logql
   {service="gateway"} |= "error"      # Fast
   {service="gateway"} |~ "err.*"      # Slower (regex)
   ```

## Structured Logging Best Practices

### Rust Services (Forward, Backward, etc.)

Already using `tracing` with structured logging:

```rust
use tracing::{info, warn, error};

// Good: Structured fields
info!(
    order_id = %order.id,
    symbol = %order.symbol,
    price = %order.price,
    "Order executed successfully"
);

// Avoid: Unstructured
info!("Order {} executed at price {}", order.id, order.price);
```

### Python Gateway

Use `structlog` for better log structure:

```python
import structlog

logger = structlog.get_logger()

# Good: Structured
logger.info(
    "signal_received",
    signal_id=signal.id,
    symbol=signal.symbol,
    confidence=signal.confidence,
    request_id=request_id
)

# Avoid: String formatting
logger.info(f"Received signal {signal.id} for {signal.symbol}")
```

### Include These Fields

For better correlation and debugging:

- `request_id` or `trace_id`: Link related logs
- `user_id` or `session_id`: Track user actions
- `order_id`, `signal_id`: Business context
- `latency_ms`, `duration_ms`: Performance tracking
- `error_code`, `error_type`: Error classification

## Troubleshooting

### Logs Not Appearing

1. **Check Promtail is running**:
   ```bash
   docker ps | grep promtail
   docker logs fks_promtail
   ```

2. **Check Loki is accessible**:
   ```bash
   curl http://localhost:3100/ready
   ```

3. **Verify containers are logging**:
   ```bash
   docker logs fks_forward | head
   ```

4. **Check Promtail can reach Loki**:
   ```bash
   docker exec fks_promtail wget -O- http://loki:3100/ready
   ```

### Query Returns No Data

1. **Check time range**: Expand to "Last 24 hours"
2. **Verify labels exist**: Run `{job="docker"}` first
3. **Check service name**: Use `{service="forward"}` not `{service="fks_forward"}`

### Loki Running Out of Disk

1. **Check disk usage**:
   ```bash
   df -h
   docker exec fks_loki du -sh /loki
   ```

2. **Reduce retention period** (see above)

3. **Clean up manually**:
   ```bash
   docker compose stop loki
   docker volume rm fks_loki_data
   docker compose up -d loki
   ```

### High Memory Usage

1. **Reduce query concurrency** (`loki-config.yml`):
   ```yaml
   querier:
     max_concurrent: 5  # Reduce from 10
   ```

2. **Limit query results**:
   ```yaml
   limits_config:
     max_entries_limit_per_query: 5000  # Reduce from 10000
   ```

## API Access

### Query Logs via API

```bash
# Query API endpoint
LOKI_URL="http://localhost:3100"

# Get logs from last hour
curl -G "$LOKI_URL/loki/api/v1/query_range" \
  --data-urlencode 'query={service="gateway"}' \
  --data-urlencode 'start='$(date -d '1 hour ago' +%s)000000000 \
  --data-urlencode 'end='$(date +%s)000000000 \
  --data-urlencode 'limit=100' | jq

# Get label values
curl "$LOKI_URL/loki/api/v1/label/service/values" | jq

# Get series (available label combinations)
curl -G "$LOKI_URL/loki/api/v1/series" \
  --data-urlencode 'match={job="docker"}' | jq
```

### Tail Logs in Real-Time

```bash
# Using logcli (install: go install github.com/grafana/loki/cmd/logcli@latest)
logcli --addr=http://localhost:3100 query '{service="forward"}' --tail

# Or use curl with tail endpoint
curl -G "$LOKI_URL/loki/api/v1/tail" \
  --data-urlencode 'query={service="gateway"}' \
  -H "Accept: application/json"
```

## Integration with Other Tools

### 1. Link to Jaeger Traces

Add trace IDs to your logs:

```rust
// Rust
info!(trace_id = %trace_id, "Processing request");
```

```python
# Python
logger.info("processing_request", trace_id=trace_id)
```

In Grafana, Loki will automatically create links to Jaeger traces.

### 2. Link to Prometheus Metrics

Use consistent labels:

```rust
// Metrics
counter!("orders_total", "service" => "forward", "symbol" => symbol);

// Logs
info!(service = "forward", symbol = %symbol, "Order executed");
```

### 3. Export to External Systems

```bash
# Export logs to S3 (using logcli)
logcli --addr=http://localhost:3100 query '{service="forward"}' \
  --from='2024-01-01T00:00:00Z' \
  --to='2024-01-02T00:00:00Z' \
  --limit=1000000 > logs_export.json

# Import to Elasticsearch, Splunk, etc.
```

## Useful Grafana Dashboards

Pre-built dashboards (import via Grafana UI):

1. **Loki Overview**: Dashboard ID 13639
2. **Container Logs**: Dashboard ID 15141  
3. **Nginx Logs**: Dashboard ID 12559

To import:
1. Go to **Dashboards** → **Import**
2. Enter dashboard ID
3. Select Loki datasource
4. Click **Import**

## Cost & Performance Metrics

```
Storage Efficiency:
  - Raw logs: ~1 GB/day (15 services, moderate volume)
  - Compressed in Loki: ~100-200 MB/day
  - 7-day retention: ~700 MB - 1.4 GB

Query Performance:
  - Simple query (<1 hour): <1 second
  - Complex query (24 hours): 2-5 seconds
  - Full retention scan (7 days): 10-30 seconds

Resource Usage:
  - Loki: ~256 MB RAM, <10% CPU
  - Promtail: ~64 MB RAM, <5% CPU
  - Storage: ~200 MB/day compressed
```

## Next Steps

1. ✅ **Setup Complete**: Loki + Promtail + Grafana configured
2. 📊 **Create Dashboards**: Build log visualization dashboards
3. 🚨 **Configure Alerts**: Set up log-based alerts
4. 📝 **Structured Logging**: Update services for better log structure
5. 🔗 **Trace Correlation**: Link logs to traces and metrics
6. 📦 **Log Retention**: Adjust based on compliance needs
7. 🎯 **Performance Tune**: Optimize based on log volume

## Resources

- **Loki Documentation**: https://grafana.com/docs/loki/latest/
- **LogQL Guide**: https://grafana.com/docs/loki/latest/logql/
- **Promtail Config**: https://grafana.com/docs/loki/latest/clients/promtail/
- **Grafana Explore**: http://localhost:3001/explore

---

**Last Updated**: January 2, 2026  
**Maintainer**: Platform Team  
**Related Docs**: 
- [Docker Compose Configuration](../docker-compose.yml)
- [Run Script Documentation](../run.sh)
- [Monitoring Overview](./MONITORING.md)