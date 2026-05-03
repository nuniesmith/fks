# JANUS CNS Integration Checklist

This checklist guides you through integrating the Central Nervous System with your JANUS services.

---

## 📋 Pre-Integration Checklist

### Infrastructure
- [ ] Docker installed (v20.10+)
- [ ] Docker Compose installed (v2.0+)
- [ ] Rust toolchain installed (1.70+)
- [ ] Ports available: 9090 (CNS), 9091 (Prometheus), 3000 (Grafana)
- [ ] At least 4GB RAM available
- [ ] 10GB disk space available

### Dependencies
- [ ] Redis running on port 6379
- [ ] Qdrant running on port 6333
- [ ] Network connectivity between services

### Code Preparation
- [ ] Git repository up to date
- [ ] Working branch created
- [ ] Backup of current configuration

---

## 🔧 Part 1: Add Health Endpoints to Services

### Forward Service (Rust)

#### Step 1: Add Dependencies
```toml
# services/forward/Cargo.toml
[dependencies]
axum = "0.7"
serde_json = "1.0"
```

#### Step 2: Implement Health Endpoint
```rust
// services/forward/src/main.rs

use axum::{routing::get, Json, Router};
use serde_json::json;

async fn health_handler() -> Json<serde_json::Value> {
    Json(json!({
        "status": "healthy",
        "service": "forward",
        "version": env!("CARGO_PKG_VERSION"),
        "timestamp": chrono::Utc::now(),
    }))
}

// Add to your router
let app = Router::new()
    .route("/health", get(health_handler))
    // ... other routes
```

**Checklist**:
- [ ] Health endpoint added
- [ ] Returns JSON response
- [ ] Includes service name and version
- [ ] Returns 200 OK when healthy
- [ ] Tested with curl: `curl http://localhost:8081/health`

---

### Backward Service (Rust)

#### Step 1: Add Dependencies
```toml
# services/backward/Cargo.toml
[dependencies]
axum = "0.7"
serde_json = "1.0"
```

#### Step 2: Implement Health Endpoint
```rust
// services/backward/src/main.rs

async fn health_handler() -> Json<serde_json::Value> {
    // Optional: Check training state, model availability, etc.
    let training_active = check_training_status();
    
    Json(json!({
        "status": if training_active { "healthy" } else { "degraded" },
        "service": "backward",
        "version": env!("CARGO_PKG_VERSION"),
        "training_active": training_active,
    }))
}
```

**Checklist**:
- [ ] Health endpoint added
- [ ] Checks critical subsystems
- [ ] Returns degraded status if appropriate
- [ ] Tested with curl: `curl http://localhost:8082/health`

---

### Gateway Service (Python/FastAPI)

#### Step 1: Add Health Endpoint
```python
# services/janus-gateway/src/main.py

from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "gateway",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
    }
```

**Checklist**:
- [ ] Health endpoint added
- [ ] Returns JSON response
- [ ] Tested with curl: `curl http://localhost:8080/health`

---

## 📊 Part 2: Add Metrics Instrumentation

### Forward Service Metrics

#### Step 1: Add CNS Dependency
```toml
# services/forward/Cargo.toml
[dependencies]
janus-cns = { path = "../../crates/cns" }
```

#### Step 2: Instrument Code
```rust
// services/forward/src/trading.rs

use janus_cns::metrics::CNSMetrics;

pub async fn submit_order(&self, order: Order) -> Result<OrderId> {
    // Increment orders submitted
    CNSMetrics::registry().forward_orders_submitted.inc();
    
    match self.execute_order(order).await {
        Ok(result) => {
            // Increment orders filled
            CNSMetrics::registry().forward_orders_filled.inc();
            Ok(result)
        }
        Err(e) => {
            // Increment orders rejected
            CNSMetrics::registry().forward_orders_rejected.inc();
            Err(e)
        }
    }
}
```

#### Step 3: Expose Metrics Endpoint
```rust
// services/forward/src/main.rs

async fn metrics_handler() -> impl IntoResponse {
    match janus_cns::metrics::CNSMetrics::encode_text() {
        Ok(metrics) => (
            StatusCode::OK,
            [("Content-Type", "text/plain; version=0.0.4")],
            metrics,
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            [("Content-Type", "text/plain")],
            format!("Error: {}", e),
        ),
    }
}

let app = Router::new()
    .route("/metrics", get(metrics_handler))
    // ... other routes
```

**Checklist**:
- [ ] CNS dependency added
- [ ] Order submission instrumented
- [ ] Order fills instrumented
- [ ] Order rejections instrumented
- [ ] Metrics endpoint exposed
- [ ] Tested with curl: `curl http://localhost:8081/metrics`

---

### Backward Service Metrics

#### Step 1: Instrument Training
```rust
// services/backward/src/training.rs

use janus_cns::metrics::CNSMetrics;

pub async fn train_iteration(&mut self) -> Result<()> {
    // Training logic...
    
    // Increment training counter
    CNSMetrics::registry().backward_training_iterations.inc();
    
    Ok(())
}

pub async fn consolidate_memory(&mut self) -> Result<()> {
    // Memory consolidation logic...
    
    // Increment consolidation counter
    CNSMetrics::registry().backward_memory_consolidations.inc();
    
    Ok(())
}
```

**Checklist**:
- [ ] Training iterations instrumented
- [ ] Memory consolidations instrumented
- [ ] Regime updates instrumented
- [ ] Metrics endpoint exposed
- [ ] Tested with curl: `curl http://localhost:8082/metrics`

---

## 🐳 Part 3: Docker Configuration

### Step 1: Update docker-compose.yml

**Checklist**:
- [ ] CNS service added to docker-compose.yml
- [ ] Prometheus service added
- [ ] Grafana service added
- [ ] All services on same network
- [ ] Health checks configured for each service
- [ ] Volume mounts configured
- [ ] Environment variables set

### Step 2: Build Docker Images

```bash
# Build CNS image
docker build -t janus/cns:latest -f services/cns/Dockerfile .

# Build other services
docker build -t janus/forward:latest -f services/forward/Dockerfile .
docker build -t janus/backward:latest -f services/backward/Dockerfile .
```

**Checklist**:
- [ ] CNS image builds successfully
- [ ] Forward image builds successfully
- [ ] Backward image builds successfully
- [ ] No build errors
- [ ] Images tagged correctly

---

## ⚙️ Part 4: Configuration

### Step 1: Configure CNS

Edit `config/cns.toml`:

```toml
[endpoints]
forward_service = "http://janus-forward:8081"    # Docker service names
backward_service = "http://janus-backward:8082"
gateway_service = "http://janus-gateway:8080"
redis = "redis://janus-redis:6379"
qdrant = "http://janus-qdrant:6333"
```

**Checklist**:
- [ ] Endpoints configured correctly
- [ ] Docker service names used (not localhost)
- [ ] Health check interval set appropriately
- [ ] Circuit breaker thresholds configured
- [ ] Reflex rules reviewed

### Step 2: Configure Prometheus

Edit `config/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'janus-cns'
    static_configs:
      - targets: ['janus-cns:9090']
  
  - job_name: 'janus-forward'
    static_configs:
      - targets: ['janus-forward:8081']
  
  - job_name: 'janus-backward'
    static_configs:
      - targets: ['janus-backward:8082']
```

**Checklist**:
- [ ] All services configured for scraping
- [ ] Docker service names used
- [ ] Scrape intervals appropriate
- [ ] Alert rules file referenced

---

## 🚀 Part 5: Deployment

### Step 1: Start Stack

```bash
# Start all services
docker-compose up -d

# Wait for services to be healthy
sleep 30

# Check status
docker-compose ps
```

**Checklist**:
- [ ] All containers started
- [ ] All containers healthy
- [ ] No error logs
- [ ] Network connectivity verified

### Step 2: Verify CNS

```bash
# Check CNS health
curl http://localhost:9090/health | jq '.'

# Check CNS metrics
curl http://localhost:9090/metrics | grep janus_cns_system_health_score
```

**Expected Output**:
```json
{
  "system_status": "Healthy",
  "components": [...],
  "timestamp": "2025-01-15T10:00:00Z",
  "uptime_seconds": 30
}
```

**Checklist**:
- [ ] CNS health endpoint responds
- [ ] System status is "Healthy" or "Degraded"
- [ ] All expected components present
- [ ] Metrics endpoint returns data

### Step 3: Verify Prometheus

```bash
# Check Prometheus targets
curl http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

**Checklist**:
- [ ] Prometheus UI accessible (http://localhost:9091)
- [ ] All targets showing as "up"
- [ ] Metrics being scraped
- [ ] No scrape errors

### Step 4: Verify Grafana

```bash
# Login to Grafana
open http://localhost:3000  # Default: admin/admin
```

**Checklist**:
- [ ] Grafana UI accessible
- [ ] Prometheus data source configured
- [ ] CNS dashboard imported
- [ ] Panels showing data
- [ ] No data errors

---

## 🧪 Part 6: Testing

### Test 1: Health Check Cycle

```bash
# Watch health checks
./scripts/cns-ctl.sh watch 5
```

**Verify**:
- [ ] Health updates every 10 seconds (or configured interval)
- [ ] Component statuses accurate
- [ ] Response times reasonable (<1000ms)
- [ ] No probe failures

### Test 2: Component Failure

```bash
# Stop Redis
docker stop janus-redis

# Wait 30 seconds and check CNS
curl http://localhost:9090/health | jq '.components[] | select(.component_type == "redis")'

# Restart Redis
docker start janus-redis
```

**Verify**:
- [ ] CNS detects Redis as "Down"
- [ ] System status changes to "Degraded" or "Critical"
- [ ] Circuit breaker opens (if configured)
- [ ] Alert fired in Prometheus
- [ ] Recovery detected after restart

### Test 3: Metrics Collection

```bash
# Generate some trading activity
# (trigger your trading logic)

# Check metrics
curl -s http://localhost:9090/metrics | grep janus_forward_orders
```

**Verify**:
- [ ] Order metrics incrementing
- [ ] Training metrics updating
- [ ] Metrics visible in Grafana
- [ ] No metric collection errors

### Test 4: Circuit Breaker

```bash
# Check circuit breaker state
./scripts/cns-ctl.sh circuit-breakers

# Trigger failures (stop/start service rapidly)
# Check state changes
```

**Verify**:
- [ ] Circuit opens after threshold
- [ ] State transitions to half-open
- [ ] Closes after successful tests
- [ ] Metrics reflect state changes

---

## 📊 Part 7: Dashboard Verification

### Grafana Dashboard Checklist

Navigate to: http://localhost:3000/d/janus-cns/janus-cns

**System Overview Section**:
- [ ] System Status showing correct state
- [ ] Health Score gauge displaying (0.0-1.0)
- [ ] Uptime counter incrementing
- [ ] Active tasks shown

**Component Health Section**:
- [ ] All components listed
- [ ] Status colors correct (green/yellow/red)
- [ ] Response times displayed
- [ ] Trends visible over time

**Service Metrics Section**:
- [ ] Forward service metrics visible
- [ ] Backward service metrics visible
- [ ] Gateway service metrics visible
- [ ] Counts incrementing with activity

**Dependencies Section**:
- [ ] Redis metrics showing
- [ ] Qdrant metrics showing
- [ ] Latency graphs displaying
- [ ] Connection counts accurate

**Circuit Breakers Section**:
- [ ] States displayed correctly
- [ ] Trip counts shown
- [ ] Historical data visible

---

## 🔔 Part 8: Alert Configuration

### Step 1: Test Alerts

```bash
# Trigger a test alert
docker stop janus-forward

# Wait for alert to fire (check Prometheus)
curl http://localhost:9091/api/v1/alerts

# Restore service
docker start janus-forward
```

**Checklist**:
- [ ] Alert fires after configured duration
- [ ] Alert shows in Prometheus UI
- [ ] Alert resolves after recovery
- [ ] Alert annotations correct

### Step 2: Configure Alert Routing (Optional)

Edit `config/alertmanager.yml`:

```yaml
receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'YOUR_WEBHOOK_URL'
        channel: '#janus-alerts'
```

**Checklist**:
- [ ] Alert manager configured
- [ ] Slack/PagerDuty integrated (if needed)
- [ ] Test alerts sent successfully
- [ ] Alert routing works correctly

---

## 📝 Part 9: Documentation

### Update Your Documentation

**Checklist**:
- [ ] README updated with CNS information
- [ ] Runbooks created for common issues
- [ ] Team trained on dashboard usage
- [ ] On-call procedures documented
- [ ] Recovery procedures documented

### Create Runbooks

Create these runbooks in `docs/runbooks/`:

- [ ] `forward-service-down.md`
- [ ] `backward-service-down.md`
- [ ] `redis-down.md`
- [ ] `high-rejection-rate.md`
- [ ] `circuit-breaker-stuck.md`

---

## ✅ Part 10: Final Verification

### Complete System Check

```bash
# Run complete health check
./scripts/cns-ctl.sh health-detailed

# Check all components
./scripts/cns-ctl.sh components

# Verify metrics
./scripts/cns-ctl.sh metrics

# Check alerts
./scripts/cns-ctl.sh alerts

# Open dashboards
./scripts/cns-ctl.sh dashboard
```

**Final Checklist**:
- [ ] All services healthy
- [ ] All metrics collecting
- [ ] All dashboards working
- [ ] Alerts configured
- [ ] Circuit breakers operational
- [ ] Documentation complete
- [ ] Team trained
- [ ] Backup procedures in place

---

## 🎯 Post-Integration Tasks

### Week 1
- [ ] Monitor dashboard daily
- [ ] Review any alerts
- [ ] Adjust thresholds if needed
- [ ] Document any issues

### Week 2
- [ ] Tune circuit breaker settings
- [ ] Optimize health check intervals
- [ ] Add custom metrics as needed
- [ ] Create additional dashboards

### Month 1
- [ ] Review all metrics for usefulness
- [ ] Optimize Prometheus retention
- [ ] Set up long-term storage if needed
- [ ] Conduct disaster recovery drill

---

## 🆘 Troubleshooting

### Common Issues

**CNS won't start**:
- [ ] Check port 9090 availability
- [ ] Verify config file exists
- [ ] Check Docker logs: `docker logs janus-cns`

**Metrics not appearing**:
- [ ] Verify Prometheus scraping
- [ ] Check service metrics endpoints
- [ ] Review Prometheus targets

**Health checks failing**:
- [ ] Verify service endpoints
- [ ] Check network connectivity
- [ ] Increase timeout values

**Dashboard blank**:
- [ ] Verify Prometheus data source
- [ ] Check time range
- [ ] Confirm metrics exist

---

## 📞 Support

If you encounter issues:

1. Check logs: `docker-compose logs -f janus-cns`
2. Review documentation: `docs/CNS_*.md`
3. Use control script: `./scripts/cns-ctl.sh --help`
4. Check Prometheus targets: http://localhost:9091/targets
5. Verify Grafana data source: http://localhost:3000/datasources

---

## 🎉 Success Criteria

You've successfully integrated CNS when:

✅ All services have health endpoints  
✅ Metrics are being collected  
✅ Prometheus is scraping all targets  
✅ Grafana dashboards show data  
✅ Alerts fire and resolve correctly  
✅ Circuit breakers work as expected  
✅ Team can use CNS for daily operations  
✅ Documentation is complete  

**Congratulations! Your JANUS system now has a comprehensive nervous system!** 🧠💚