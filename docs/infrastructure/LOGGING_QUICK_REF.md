# Centralized Logging - Quick Reference

## Access Logs

### Grafana Explore
```
URL: http://localhost:3001/explore
Login: admin / admin (default)
Datasource: Select "Loki" from dropdown
```

## Common LogQL Queries

### By Service
```logql
# Gateway (Python API)
{service="gateway"}

# Rust services
{service=~"forward|backward|data"}

# Nginx
{service="nginx"}

# Databases
{service=~"questdb|postgres|redis"}

# Monitoring stack
{service=~"prometheus|grafana|jaeger"}
```

### By Log Level
```logql
# All errors
{level="ERROR"}

# Warnings and above
{level=~"WARN|ERROR"}

# Critical issues
{level=~"ERROR|FATAL"}

# Specific service errors
{service="gateway", level="ERROR"}
```

### Text Search
```logql
# Contains text
{service="gateway"} |= "signal"

# Exclude text
{service="nginx"} != "health"

# Regex match
{service="forward"} |~ "order_id=[0-9]+"

# Case insensitive
{service="gateway"} |~ "(?i)error"
```

### Time-Based
```logql
# Rate (logs per second)
rate({service="gateway"}[5m])

# Count in time window
count_over_time({level="ERROR"}[1h])

# Sum by service
sum by (service) (rate({job="docker"}[5m]))
```

### Aggregations
```logql
# Count errors by service (last 5min)
sum by (service) (count_over_time({level="ERROR"}[5m]))

# Top 5 services by log volume
topk(5, sum by (service) (rate({job="docker"}[5m])))

# Error rate percentage
sum(rate({level="ERROR"}[5m])) / sum(rate({job="docker"}[5m])) * 100
```

## Service-Specific Examples

### Trading Signals
```logql
# All signal logs
{service="forward"} |= "signal"

# Signal received
{service="gateway"} |= "signal_received"

# Signal execution
{service="forward"} |= "executing signal"
```

### Orders
```logql
# Order events
{service="forward"} |= "order"

# Filled orders
{service="forward"} |= "order" |= "filled"

# Order errors
{service="forward", level="ERROR"} |= "order"
```

### API Requests
```logql
# All requests
{service="gateway"} |= "request_id"

# Slow requests (assuming latency logged)
{service="gateway"} |~ "latency_ms=[5-9][0-9]{2,}"

# Specific endpoint
{service="gateway"} |= "/api/signals"
```

### Nginx Access Logs
```logql
# All access logs
{service="nginx", stream="stdout"}

# 4xx errors
{service="nginx", status=~"4.*"}

# 5xx errors
{service="nginx", status=~"5.*"}

# Slow requests
{service="nginx"} | json | request_time > 1.0
```

### Database Queries
```logql
# QuestDB errors
{service="questdb", level="ERROR"}

# PostgreSQL slow queries
{service="postgres"} |= "duration:" |~ "duration: [5-9][0-9]{2,}"

# Redis commands
{service="redis"} |= "command"
```

## Quick Commands

### Check Services Running
```bash
# Verify logging stack
docker ps | grep -E "loki|promtail|grafana"

# Check Loki health
curl http://localhost:3100/ready

# Check Promtail logs
docker logs fks_promtail --tail 50
```

### Start/Stop Services
```bash
# Start all (including logging)
./run.sh up

# Start only logging stack
docker compose up -d loki promtail grafana

# Restart Loki
docker compose restart loki

# Stop all
./run.sh down
```

### View Raw Logs
```bash
# Container logs directly
docker logs fks_forward --tail 100 -f
docker logs fks_gateway --tail 100 -f

# All containers
docker compose logs -f --tail 100
```

### Storage & Maintenance
```bash
# Check Loki storage size
docker exec fks_loki du -sh /loki

# Check disk space
df -h

# Clean up old logs (careful!)
docker compose stop loki
docker volume rm fks_loki_data
docker compose up -d loki
```

## Troubleshooting

### No Logs Appearing?
```bash
# 1. Check Promtail running and healthy
docker ps | grep promtail
docker logs fks_promtail

# 2. Verify Loki accessible
curl http://localhost:3100/ready

# 3. Check containers are producing logs
docker logs fks_forward | head -20

# 4. Verify Promtail → Loki connectivity
docker exec fks_promtail wget -O- http://loki:3100/ready
```

### Query Returns Nothing?
1. **Expand time range**: Try "Last 24 hours"
2. **Check labels**: Run `{job="docker"}` first
3. **Verify service name**: Use `{service="forward"}` not `{service="fks_forward"}`
4. **Check log volume**: `sum by (service) (count_over_time({job="docker"}[1h]))`

### Loki High Memory?
```bash
# Reduce query concurrency
# Edit: config/loki/loki-config.yml
# Set: querier.max_concurrent: 5

# Restart Loki
docker compose restart loki
```

## API Access

### Query Logs via curl
```bash
LOKI_URL="http://localhost:3100"

# Query logs
curl -G "$LOKI_URL/loki/api/v1/query_range" \
  --data-urlencode 'query={service="gateway"}' \
  --data-urlencode 'limit=100' | jq

# Get available services
curl "$LOKI_URL/loki/api/v1/label/service/values" | jq

# Health check
curl "$LOKI_URL/ready"
```

### Real-time Tail
```bash
# Using curl
curl -N -G "$LOKI_URL/loki/api/v1/tail" \
  --data-urlencode 'query={service="forward"}' \
  -H "Accept: application/json"
```

## Configuration Files

```
config/loki/loki-config.yml          → Loki settings
config/loki/promtail-config.yml      → Log collection rules
config/monitor/grafana/provisioning/ → Grafana datasources
```

## Retention Settings

**Default**: 7 days (168 hours)

To change, edit `config/loki/loki-config.yml`:
```yaml
limits_config:
  retention_period: 720h  # 30 days

table_manager:
  retention_period: 720h  # Must match
```

## Useful Labels

- `service` - Service name (forward, gateway, nginx, etc.)
- `level` - Log level (INFO, WARN, ERROR)
- `container` - Container name
- `stream` - stdout or stderr
- `environment` - dev, staging, prod

## Next Steps

1. ✅ Start logging stack: `./run.sh up`
2. 📊 Open Grafana: http://localhost:3001/explore
3. 🔍 Run query: `{service="gateway"}`
4. 📈 Create dashboard for your use case
5. 🚨 Set up alerts on error rates

## Resources

- **Full Guide**: `docs/CENTRALIZED_LOGGING.md`
- **Grafana Explore**: http://localhost:3001/explore
- **Loki API**: http://localhost:3100
- **LogQL Docs**: https://grafana.com/docs/loki/latest/logql/

---

**Last Updated**: January 2, 2026