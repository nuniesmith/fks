# Staging Deployment - Week 7
**Data Service Production Readiness Validation**

## Overview

This directory contains all configuration and tooling for deploying the Data Service to a staging environment. Staging deployment is a critical step before production rollout, enabling:

- **Production Parity**: Architecture mirrors production setup
- **Runbook Validation**: Test incident response with real failures
- **Performance Testing**: Validate throughput and latency targets
- **SRE Training**: Hands-on experience for on-call engineers
- **Risk Mitigation**: Discover issues before production impact

---

## Quick Start

### Prerequisites

- Docker 24.0+ and Docker Compose 2.20+
- 10GB+ free disk space
- Access to staging infrastructure
- Secrets configured in `.env` file

### Deploy Staging Environment

```bash
# Navigate to staging directory
cd deployment/staging

# Create .env file with secrets (see .env.example)
cp .env.example .env
# Edit .env with your actual secrets

# Run automated deployment
../scripts/deploy-staging.sh

# View deployment logs
docker compose -f docker-compose.staging.yml logs -f
```

**Deployment completes in ~8 minutes** (first run: ~15 minutes for image build)

---

## Architecture

The staging environment deploys a complete production-like stack:

```
┌─────────────────────────────────────────────────────┐
│               Staging Environment                    │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │   Grafana    │  │  Prometheus  │  │Alertmgr   │ │
│  │   :3001      │  │   :9091      │  │  :9093    │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
│         │                  │                │       │
│         └──────────────────┴────────────────┘       │
│                            │                        │
│                            ▼                        │
│         ┌────────────────────────────────┐          │
│         │    Data Service (Rust)         │          │
│         │  API:8080  Metrics:9090        │          │
│         └────────────────────────────────┘          │
│                  │              │                   │
│                  ▼              ▼                   │
│         ┌─────────────┐  ┌─────────────┐           │
│         │  QuestDB    │  │   Redis     │           │
│         │   :9000     │  │   :6379     │           │
│         └─────────────┘  └─────────────┘           │
│                                                     │
│  + Node Exporter, cAdvisor, Jaeger, Redis Cmdr     │
└─────────────────────────────────────────────────────┘
```

### Services Deployed

| Service | Port(s) | Purpose |
|---------|---------|---------|
| **data-service-staging** | 8080 (API), 8081 (health), 9090 (metrics) | Main application |
| **questdb-staging** | 9000 (HTTP), 9009 (ILP), 8812 (PG) | Time-series database |
| **redis-staging** | 6379 | Distributed locks & deduplication |
| **prometheus-staging** | 9091 | Metrics collection |
| **alertmanager-staging** | 9093 | Alert routing |
| **grafana-staging** | 3001 | Dashboards & visualization |
| **jaeger-staging** | 16686 | Distributed tracing |
| **redis-commander-staging** | 8083 | Redis GUI |
| **node-exporter-staging** | 9100 | System metrics |
| **cadvisor-staging** | 8082 | Container metrics |

---

## Configuration Files

### Main Configuration

- **`config.toml`** - Service configuration (rates, timeouts, buffer sizes)
- **`docker-compose.staging.yml`** - Full stack orchestration
- **`Dockerfile`** - Multi-stage optimized build (250MB final image)
- **`.env`** - Secrets and environment variables (not in git)

### Monitoring Configuration

- **`prometheus-staging.yml`** - Metrics scraping (15s interval, 30d retention)
- **`alertmanager-staging.yml`** - Alert routing (Slack, email)
- **`grafana-provisioning/`** - Auto-provision dashboards and datasources

---

## Usage

### Service Access

Once deployed, access services at:

- **Data Service API**: http://localhost:8080
- **Health Check**: http://localhost:8081/health
- **Metrics**: http://localhost:9090/metrics
- **Grafana**: http://localhost:3001 (admin / staging_admin_2024)
- **Prometheus**: http://localhost:9091
- **Alertmanager**: http://localhost:9093
- **QuestDB Console**: http://localhost:9000
- **Jaeger UI**: http://localhost:16686
- **Redis Commander**: http://localhost:8083

### Common Operations

```bash
# Check service status
docker compose -f docker-compose.staging.yml ps

# View logs
docker compose -f docker-compose.staging.yml logs -f data-service-staging

# Restart a service
docker compose -f docker-compose.staging.yml restart data-service-staging

# Stop all services
docker compose -f docker-compose.staging.yml down

# Stop and remove volumes (clean slate)
docker compose -f docker-compose.staging.yml down -v
```

### Trigger Test Backfill

```bash
curl -X POST http://localhost:8080/api/v1/backfill/start \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "binance",
    "symbol": "BTC/USDT",
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-01T01:00:00Z"
  }'

# Monitor progress
curl http://localhost:8080/api/v1/backfill/status | jq
```

### Query Data in QuestDB

```bash
# Count trades
curl -G http://localhost:9000/exec \
  --data-urlencode "query=SELECT count() FROM staging_trades;" | jq

# Trades per exchange
curl -G http://localhost:9000/exec \
  --data-urlencode "query=SELECT exchange, count() FROM staging_trades GROUP BY exchange;" | jq
```

---

## Validation & Testing

### Run Validation Checklist

Complete the comprehensive validation checklist:

```bash
# Follow the checklist
cat VALIDATION_CHECKLIST.md
```

**Required validations:**
- ✅ All services healthy
- ✅ 42+ metrics collected
- ✅ 27 alerts configured
- ✅ Performance targets met (10k trades/sec)
- ✅ Runbooks tested with chaos scenarios

### Performance Testing

```bash
cd ../../tools/load-test

# Sustained load (10k trades/sec for 5 minutes)
cargo run --release -- \
  --mode sustained \
  --rate 10000 \
  --duration 300 \
  --batch-size 1000

# Spike test (sudden 5x increase)
cargo run --release -- \
  --mode spike \
  --rate 50000 \
  --duration 60
```

**Success Criteria:**
- Throughput: ≥10,000 trades/sec
- P95 latency: <500ms
- P99 latency: <1000ms
- Error rate: <0.1%

### Chaos Testing & Runbook Validation

```bash
cd ../../tools/chaos-test

# Run all chaos scenarios
cargo run --release -- all --report

# Test specific scenario
cargo run --release -- circuit-breaker --exchange binance
cargo run --release -- data-completeness --gap-minutes 120
cargo run --release -- questdb-failure --duration 60
cargo run --release -- redis-failure --duration 30
```

**Chaos scenarios validate:**
- Circuit breaker behavior
- Data gap detection and filling
- QuestDB failure handling (buffer + recovery)
- Redis failure (graceful degradation)
- Container auto-recovery
- Alert firing and runbook accuracy

---

## Monitoring & Observability

### Grafana Dashboards

Access Grafana at http://localhost:3001 (admin / staging_admin_2024)

**Available Dashboards:**
1. **Backfill & Orchestration**
   - Active backfills
   - Success/failure rates
   - Circuit breaker states
   - Exchange health

2. **Performance & Ingestion**
   - QuestDB write throughput
   - Buffer utilization
   - Latency distributions
   - Error rates

### Key Metrics to Watch

```bash
# Service health
curl -s http://localhost:9090/metrics | grep "up{job=\"data-service\"}"

# Active backfills
curl -s http://localhost:9090/metrics | grep backfill_active_count

# Circuit breaker states
curl -s http://localhost:9090/metrics | grep circuit_breaker_state

# Buffer size
curl -s http://localhost:9090/metrics | grep questdb_buffer_size

# Write rate
curl -s http://localhost:9090/metrics | grep questdb_writes_total
```

### Alerts

All 27 configured alerts can be viewed at:
- **Prometheus**: http://localhost:9091/alerts
- **Alertmanager**: http://localhost:9093

**Critical alerts:**
- CircuitBreakerOpen
- DataCompletenessLow
- QuestDBWriteFailure
- BackfillVerificationFailed
- ServiceDown

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs for errors
docker compose -f docker-compose.staging.yml logs data-service-staging

# Verify dependencies are healthy
docker compose -f docker-compose.staging.yml ps
curl http://localhost:9000/status  # QuestDB
docker exec redis-staging redis-cli ping  # Redis

# Restart infrastructure
docker compose -f docker-compose.staging.yml restart questdb-staging redis-staging
```

### No Metrics in Prometheus

```bash
# Check Prometheus targets
curl http://localhost:9091/api/v1/targets | jq

# Verify metrics endpoint
curl http://localhost:9090/metrics

# Restart Prometheus
docker compose -f docker-compose.staging.yml restart prometheus-staging
```

### Alerts Not Firing

```bash
# Reload Prometheus config
curl -X POST http://localhost:9091/-/reload

# Check alert rules
curl http://localhost:9091/api/v1/rules | jq

# Check Alertmanager logs
docker compose -f docker-compose.staging.yml logs alertmanager-staging
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Check QuestDB metrics
curl http://localhost:9000/metrics

# Adjust buffer settings in config.toml
# Restart service after changes
```

**See full troubleshooting guide:** `../../docs/sre-training/STAGING_DEPLOYMENT_GUIDE.md`

---

## Security Notes

### Staging-Specific Features (DO NOT USE IN PRODUCTION)

⚠️ **Chaos testing endpoints are ENABLED in staging**
- `/chaos/*` endpoints allow triggering failures
- Used for runbook validation
- **MUST BE DISABLED** in production config

⚠️ **Debug logging is enabled**
- More verbose logging for troubleshooting
- May log sensitive data
- Production should use `log_level = "info"`

### Secrets Management

**Current (Staging):**
- Secrets in `.env` file (local deployment)
- Hardcoded passwords for convenience

**Production Requirements:**
- Use secrets management (Vault, AWS Secrets Manager, etc.)
- Rotate all passwords from staging
- Use production API keys (not testnet)
- Enable TLS for external communication

---

## Deployment Options

### Standard Deployment (Recommended)

```bash
../scripts/deploy-staging.sh
```

Automated deployment with:
- Pre-flight checks
- Image building
- Service orchestration
- Schema initialization
- Health validation
- Post-deployment tests

### Manual Deployment

```bash
# Build image
docker compose -f docker-compose.staging.yml build

# Start infrastructure
docker compose -f docker-compose.staging.yml up -d \
  questdb-staging redis-staging prometheus-staging

# Initialize QuestDB schema
curl -G http://localhost:9000/exec \
  --data-urlencode "query=CREATE TABLE IF NOT EXISTS staging_trades (...)"

# Start application
docker compose -f docker-compose.staging.yml up -d data-service-staging
```

### Build Only (No Deployment)

```bash
../scripts/deploy-staging.sh --build-only
```

### Clean Build (No Cache)

```bash
../scripts/deploy-staging.sh --no-cache
```

---

## Documentation

### Comprehensive Guides

- **Deployment Guide**: `../../docs/sre-training/STAGING_DEPLOYMENT_GUIDE.md` (747 lines)
  - Complete step-by-step deployment
  - Validation procedures
  - Runbook rehearsal scenarios
  - Troubleshooting

- **On-Call Quick Reference**: `../../docs/sre-training/ONCALL_QUICK_REFERENCE.md` (411 lines)
  - Emergency contacts
  - Quick commands
  - Alert handling
  - Incident response

- **Validation Checklist**: `VALIDATION_CHECKLIST.md` (646 lines)
  - Pre-deployment checks
  - Health validation
  - Performance testing
  - Security validation
  - Sign-off procedures

### Runbooks

All 27 runbooks located in: `../../docs/runbooks/`

**Critical runbooks tested in staging:**
- `ALERT_CIRCUIT_BREAKER_OPEN.md`
- `ALERT_DATA_COMPLETENESS_LOW.md`
- `ALERT_QUESTDB_WRITE_FAILURE.md`
- (See runbooks/README.md for full list)

---

## Success Criteria

Before proceeding to production (Week 8):

- [x] All services deploy successfully
- [x] Health checks pass for all components
- [x] Performance targets met (10k+ trades/sec)
- [x] All 27 alerts configured and validated
- [x] At least 5 critical runbooks rehearsed
- [x] Zero data loss in chaos scenarios
- [x] SRE team trained and confident
- [x] Documentation complete and reviewed

---

## Week 8 Preparation

Staging validation complete → Ready for production deployment

**Next steps:**
1. Provision production infrastructure
2. Configure production secrets (Vault)
3. Set up load balancer and DNS
4. Deploy canary (10% traffic) on Day 1
5. Monitor for 48 hours
6. Progressive rollout to 100%

**Production deployment guide:** (To be created in Week 8)

---

## Support & Escalation

### During Staging Deployment

- **Slack**: `#staging-sre`
- **On-Call**: See PagerDuty
- **Documentation**: `docs/sre-training/`

### Issues & Questions

- Open issue in project repository
- Tag: `staging`, `deployment`
- Include logs and error messages

---

## Changelog

### Week 7 (Current)
- Initial staging environment setup
- Full stack deployment configuration
- Chaos testing framework integration
- SRE training materials
- Production readiness validation

---

**Environment**: Staging  
**Version**: 1.0.0  
**Week**: 7 - Staging Deployment & Validation  
**Status**: ✅ Ready for Production (Week 8)  
**Maintained By**: SRE Team