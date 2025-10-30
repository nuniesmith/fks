# FKS Trading Platform - Monitoring & Health System

## Overview

Comprehensive monitoring and health dashboard for solo development workflow. Provides real-time visibility into all services, system resources, and development priorities.

## Components

### 1. **Health Dashboard** 
- **URL**: http://localhost:8000/health/dashboard/
- **Purpose**: Single-pane-of-glass view of all services
- **Features**:
  - Service status (Database, Redis, Celery, Prometheus, Grafana, Tailscale, RAG)
  - System metrics (CPU, Memory, Disk)
  - Recent issues with actionable fixes
  - Prioritized next development steps
  - Quick links to all monitoring tools
  - Auto-refresh every 30 seconds

### 2. **Prometheus**
- **URL**: http://localhost:9090
- **Purpose**: Metrics collection and alerting
- **Metrics Collected**:
  - System metrics (CPU, memory, disk) via node-exporter
  - PostgreSQL metrics via postgres-exporter
  - Redis metrics via redis-exporter
  - Django application metrics (requires django-prometheus)
- **Configuration**: `monitoring/prometheus/prometheus.yml`
- **Alerts**: `monitoring/prometheus/alerts.yml`

### 3. **Grafana**
- **URL**: http://localhost:3000
- **Credentials**: admin/admin (change on first login)
- **Purpose**: Visualization and dashboards
- **Pre-configured**:
  - Prometheus datasource
  - PostgreSQL datasource (for direct database queries)
  - TimescaleDB datasource (for quality_metrics hypertables)
- **Dashboards**: 
  - `monitoring/grafana/dashboards/quality_monitoring.json` - Data quality metrics (Phase 5.6)
  - (More dashboards to be created)

### 4. **Tailscale VPN**
- **Purpose**: Secure remote access to services
- **Configuration**: 
  1. Create auth key at https://login.tailscale.com/admin/settings/keys
  2. Add to `.env`: `TAILSCALE_AUTH_KEY=tskey-auth-...`
  3. Set hostname: `TAILSCALE_HOSTNAME=fks-trading`
  4. Access services via Tailscale IP from anywhere
- **DNS Setup**:
  1. Get Tailscale IP: `tailscale ip -4`
  2. Create DNS records pointing to Tailscale IP
  3. Access via public DNS over encrypted tunnel

## Quick Start

### Start All Services
```bash
make up
```

### View Health Dashboard
```bash
make health
# Opens http://localhost:8000/health/dashboard/
```

### View All Monitoring Tools
```bash
make monitoring
# Shows URLs for Grafana, Prometheus, Flower, PgAdmin
```

### Check Service Status
```bash
make status
```

### View Logs
```bash
make logs                 # All services
make logs-prometheus      # Prometheus only
make logs-grafana        # Grafana only
make logs-tailscale      # Tailscale only
```

## Tailscale Setup

### 1. Get Auth Key
```bash
# Visit https://login.tailscale.com/admin/settings/keys
# Create a reusable or ephemeral key
# Add tags if needed (e.g., tag:fks-trading)
```

### 2. Configure Environment
```bash
# Add to .env
TAILSCALE_AUTH_KEY=tskey-auth-xxxxxxxxxxxxx
TAILSCALE_HOSTNAME=fks-trading
```

### 3. Start Services
```bash
make up
```

### 4. Verify Connection
```bash
# Check Tailscale status
docker-compose exec tailscale tailscale status

# Get Tailscale IP
docker-compose exec tailscale tailscale ip
```

### 5. DNS Configuration (Optional)
```bash
# Get your Tailscale IP
TAILSCALE_IP=$(docker-compose exec -T tailscale tailscale ip -4)

# Add DNS A records pointing to Tailscale IP:
# fks.yourdomain.com -> <TAILSCALE_IP>
# grafana.yourdomain.com -> <TAILSCALE_IP>
# prometheus.yourdomain.com -> <TAILSCALE_IP>
```

### 6. Access from Anywhere
```bash
# Once DNS is configured, access from any device:
https://fks.yourdomain.com              # Main app
https://grafana.yourdomain.com          # Grafana
https://prometheus.yourdomain.com       # Prometheus

# Or use direct Tailscale IP:
http://<TAILSCALE_IP>:8000             # Main app
http://<TAILSCALE_IP>:3000             # Grafana
http://<TAILSCALE_IP>:9090             # Prometheus
```

## Health Dashboard Features

### Service Monitoring
Shows real-time status of:
- **Database**: PostgreSQL + TimescaleDB + pgvector
- **Redis**: Cache and message broker
- **Celery**: Worker and beat scheduler
- **Prometheus**: Metrics collector
- **Grafana**: Visualization platform
- **Tailscale**: VPN connectivity
- **RAG Service**: AI-powered intelligence (GPU mode)

### System Metrics
- CPU usage percentage
- Memory usage and available
- Disk usage and free space
- Active service count

### Issue Detection
Automatically identifies:
- Unapplied database migrations
- Disabled Django apps
- High resource usage
- Configuration problems

### Next Steps
Prioritized development tasks:
- **High Priority**: Critical for core functionality
- **Medium Priority**: Important but not blocking
- **Low Priority**: Nice to have improvements

Each step includes:
- Category (Testing, Development, UI/UX, etc.)
- File path for quick navigation
- Command to run (if applicable)
- Clear description of what to do

## Prometheus Metrics

### Available Metrics
```prometheus
# System
node_cpu_seconds_total
node_memory_MemTotal_bytes
node_memory_MemAvailable_bytes
node_filesystem_avail_bytes

# PostgreSQL
pg_stat_database_numbackends
pg_stat_database_xact_commit
pg_stat_database_xact_rollback
pg_database_size_bytes

# Redis
redis_connected_clients
redis_used_memory_bytes
redis_memory_max_bytes
redis_commands_processed_total

# Django (requires django-prometheus)
django_http_requests_total
django_http_request_duration_seconds
django_db_query_duration_seconds
```

### Alert Rules
Configured in `monitoring/prometheus/alerts.yml`:
- Service down (2 minutes)
- High memory usage (>85% for 5 minutes)
- High CPU usage (>80% for 5 minutes)
- PostgreSQL connection pool exhaustion
- Redis memory usage (>90%)
- Low disk space (<10%)
- Celery queue backlog (>100 tasks)

## Creating Grafana Dashboards

### 1. Access Grafana
```bash
open http://localhost:3000
# Login: admin/admin
```

### 2. Create Dashboard
1. Click "+" → "Dashboard"
2. Add panel
3. Select "Prometheus" as data source
4. Write PromQL query
5. Configure visualization
6. Save dashboard

### 3. Example Dashboards to Create
- **System Overview**: CPU, Memory, Disk, Network
- **Database Performance**: Query time, connections, cache hit ratio
- **Trading Activity**: Signals generated, trades executed, P&L
- **Celery Tasks**: Queue length, task duration, success/failure rates
- **API Performance**: Request rate, latency, error rate

### 4. Export Dashboard
1. Dashboard settings → JSON Model
2. Copy JSON
3. Save to `monitoring/grafana/dashboards/`
4. Dashboard auto-loads on next restart

## Solo Developer Workflow

### Morning Routine
```bash
# Start services
make up

# Check health
make health
# Review service status, issues, and next steps

# Run tests
make test

# Check for problems
make lint
```

### During Development
```bash
# Monitor logs
make logs-web         # Watch Django logs
make logs-celery      # Watch Celery tasks

# Check metrics
# Open Grafana to monitor system during load testing
```

### End of Day
```bash
# Check health one last time
make health

# Backup database
make backup-db

# Review Grafana for any anomalies
```

## Troubleshooting

### Health Dashboard Not Loading
```bash
# Check web service
docker-compose ps web
docker-compose logs web

# Restart if needed
make restart
```

### Prometheus Not Scraping
```bash
# Check Prometheus config
docker-compose exec prometheus cat /etc/prometheus/prometheus.yml

# Check targets
open http://localhost:9090/targets
```

### Grafana Can't Connect to Prometheus
```bash
# Verify Prometheus is running
curl http://localhost:9090/-/healthy

# Check Grafana datasource
# Grafana → Configuration → Data Sources → Prometheus
# URL should be: http://prometheus:9090
```

### Tailscale Not Connecting
```bash
# Check auth key is valid
# Must be active, not expired

# Check logs
make logs-tailscale

# Restart Tailscale
docker-compose restart tailscale

# Verify status
docker-compose exec tailscale tailscale status
```

## Next Steps

1. **Add Django Prometheus Middleware**
   - Install: `django-prometheus` (already in requirements.txt)
   - Add to MIDDLEWARE in settings.py
   - Add metrics endpoint to urls.py

2. **Create Custom Grafana Dashboards**
   - System overview
   - Trading performance
   - Celery task monitoring

3. **Set Up Alerting**
   - Configure Alertmanager for Prometheus
   - Set up Discord/email notifications
   - Create alert rules for critical failures

4. **Expand Health Checks**
   - Add FKS Intelligence status
   - Check strategy health
   - Monitor signal quality metrics

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Tailscale Documentation](https://tailscale.com/kb/)
- [Django Prometheus](https://github.com/korfuri/django-prometheus)
