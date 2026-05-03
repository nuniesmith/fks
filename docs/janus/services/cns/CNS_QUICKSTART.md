# JANUS CNS Quick Start Guide

Get the JANUS Central Nervous System up and running in minutes.

---

## 📋 Prerequisites

- Rust 1.70+ with Cargo
- Docker and Docker Compose (for dependencies)
- curl and jq (for testing)
- Optional: Prometheus, Grafana

---

## 🚀 Quick Start (5 minutes)

### Step 1: Start Dependencies

```bash
# Start Redis and Qdrant using Docker
docker run -d --name janus-redis -p 6379:6379 redis:7-alpine
docker run -d --name janus-qdrant -p 6333:6333 qdrant/qdrant:latest
```

### Step 2: Build CNS Service

```bash
# From project root
cd src/janus

# Build all workspace members including CNS
make build

# Or build just CNS
cargo build --release --bin janus-cns
```

### Step 3: Start CNS Service

```bash
# Start CNS service
make run-cns

# Or run directly
cargo run --release --bin janus-cns
```

You should see:
```
🧠 JANUS Central Nervous System (CNS) starting...
Configuration loaded successfully
Brain initialized with 6 probes
🌐 Starting HTTP server on 0.0.0.0:9090
✅ CNS service ready
📊 Metrics: http://0.0.0.0:9090/metrics
🏥 Health: http://0.0.0.0:9090/health
```

### Step 4: Verify Health

```bash
# Check system health
make health

# Or use curl
curl -s http://localhost:9090/health | jq '.'
```

Expected output:
```json
{
  "system_status": "Degraded",
  "components": [
    {
      "component_type": "forward_service",
      "status": "Down",
      "message": "HTTP request failed",
      "last_check": "2025-01-15T10:30:00Z",
      "response_time_ms": null
    },
    {
      "component_type": "redis",
      "status": "Up",
      "message": "Redis responded: PONG",
      "last_check": "2025-01-15T10:30:00Z",
      "response_time_ms": 5
    },
    {
      "component_type": "qdrant",
      "status": "Up",
      "message": "Qdrant health: 200 OK",
      "last_check": "2025-01-15T10:30:00Z",
      "response_time_ms": 12
    }
  ],
  "timestamp": "2025-01-15T10:30:00Z",
  "uptime_seconds": 60,
  "version": "0.1.0"
}
```

### Step 5: View Metrics

```bash
# Check Prometheus metrics
make metrics

# Or use curl
curl http://localhost:9090/metrics
```

You should see metrics like:
```
# HELP janus_cns_system_health_score Overall system health score (0.0 to 1.0)
# TYPE janus_cns_system_health_score gauge
janus_cns_system_health_score 0.625

# HELP janus_cns_component_health Component health status score
# TYPE janus_cns_component_health gauge
janus_cns_component_health{component="redis"} 1
janus_cns_component_health{component="qdrant"} 1
janus_cns_component_health{component="forward_service"} 0
```

---

## 🎯 Next Steps

### Start Remaining Services

For full system health monitoring, start the other JANUS services:

```bash
# Terminal 1: Forward service
make run-forward

# Terminal 2: Backward service
make run-backward

# Terminal 3: Gateway service
make run-gateway

# Terminal 4: CNS (already running)
```

### Set Up Prometheus

**Create `config/prometheus.yml`:**
```yaml
global:
  scrape_interval: 10s

scrape_configs:
  - job_name: 'janus-cns'
    static_configs:
      - targets: ['localhost:9090']
```

**Start Prometheus:**
```bash
docker run -d \
  --name janus-prometheus \
  -p 9091:9090 \
  -v $(pwd)/config/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus:latest
```

**Verify:**
```bash
# Check Prometheus UI
open http://localhost:9091

# Query metrics
curl 'http://localhost:9091/api/v1/query?query=janus_cns_system_health_score'
```

### Set Up Grafana

**Start Grafana:**
```bash
docker run -d \
  --name janus-grafana \
  -p 3000:3000 \
  grafana/grafana:latest
```

**Configure:**
1. Open http://localhost:3000 (admin/admin)
2. Add Prometheus data source: http://host.docker.internal:9091
3. Import dashboard from `config/grafana/janus_cns_dashboard.json`

---

## 🔧 Configuration

### Basic Configuration

Edit `config/cns.toml`:

```toml
[brain]
health_check_interval_secs = 10
enable_reflexes = true

[endpoints]
forward_service = "http://localhost:8081"
backward_service = "http://localhost:8082"
gateway_service = "http://localhost:8080"
redis = "redis://localhost:6379"
qdrant = "http://localhost:6333"
```

### Environment Variables

```bash
# Set log level
export RUST_LOG=info

# Use custom config file
export CONFIG_PATH=config/cns.toml

# Start CNS
make run-cns
```

---

## 📊 Monitoring Examples

### Check Specific Component

```bash
# Get detailed health with jq filtering
curl -s http://localhost:9090/health | jq '.components[] | select(.component_type == "redis")'
```

### Monitor Health Score

```bash
# Watch health score in real-time
watch -n 2 'curl -s http://localhost:9090/metrics | grep system_health_score'
```

### Check Circuit Breaker Status

```bash
# View circuit breaker states
curl -s http://localhost:9090/metrics | grep circuit_breaker_state
```

### Tail Logs

```bash
# If running with journald
journalctl -u janus-cns -f

# If running in terminal
# Just watch the output
make run-cns
```

---

## 🧪 Testing

### Test Health Probes

```bash
# Test Redis connectivity
cargo test -p janus-cns redis -- --nocapture

# Test all probes
cargo test -p janus-cns test_probe -- --nocapture

# Run full test suite
cargo test -p janus-cns
```

### Simulate Component Failure

```bash
# Stop Redis
docker stop janus-redis

# Check CNS response
curl -s http://localhost:9090/health | jq '.components[] | select(.component_type == "redis")'

# Should show status: "Down"

# Restart Redis
docker start janus-redis

# Wait for recovery (check interval + recovery timeout)
# Circuit breaker will detect and transition to half-open, then closed
```

### Test Circuit Breaker

```bash
# Monitor circuit breaker state
watch -n 1 'curl -s http://localhost:9090/metrics | grep "circuit_breaker_state{component=\"redis\"}"'

# In another terminal, stop/start Redis repeatedly to trigger circuit breaker
```

---

## 🐛 Troubleshooting

### CNS Won't Start

**Problem**: Port 9090 already in use
```bash
# Check what's using the port
lsof -i :9090

# Kill the process or change CNS port in config
```

**Problem**: Can't connect to Redis/Qdrant
```bash
# Verify services are running
docker ps | grep -E "redis|qdrant"

# Check connectivity
redis-cli ping
curl http://localhost:6333/healthz

# Check CNS configuration matches
cat config/cns.toml | grep -A5 endpoints
```

### Metrics Not Updating

```bash
# Check if CNS is running
ps aux | grep janus-cns

# Verify metrics endpoint
curl -I http://localhost:9090/metrics

# Check Prometheus configuration
docker logs janus-prometheus | grep "error"

# Verify scrape targets
curl http://localhost:9091/api/v1/targets | jq '.data.activeTargets'
```

### Health Checks Timing Out

Edit `config/cns.toml`:
```toml
[health]
timeout_secs = 10  # Increase from default 5s
```

### False Positive Circuit Breaker Trips

Adjust thresholds in `config/cns.toml`:
```toml
[circuit_breakers.redis]
failure_threshold = 10      # Increase from 5
failure_window_secs = 120   # Increase window
recovery_timeout_secs = 60  # Longer recovery time
```

---

## 📚 Common Tasks

### View All Endpoints

```bash
curl http://localhost:9090/
```

Returns:
```json
{
  "name": "JANUS Central Nervous System",
  "version": "0.1.0",
  "uptime_seconds": 3600,
  "endpoints": [
    "/health - Basic health check",
    "/health/detailed - Detailed health information",
    "/metrics - Prometheus metrics",
    "/status - Service status"
  ]
}
```

### Get Service Status

```bash
curl http://localhost:9090/status | jq '.'
```

### Detailed Health Check

```bash
# Force immediate health check across all components
curl http://localhost:9090/health/detailed | jq '.'
```

### Export Metrics to File

```bash
# Save current metrics
curl -s http://localhost:9090/metrics > metrics_$(date +%Y%m%d_%H%M%S).txt
```

---

## 🚀 Production Deployment

### Docker Deployment

```bash
# Build Docker image
docker build -t janus/cns:latest -f services/cns/Dockerfile .

# Run container
docker run -d \
  --name janus-cns \
  -p 9090:9090 \
  -v $(pwd)/config:/app/config:ro \
  -v /dev/shm:/dev/shm \
  janus/cns:latest
```

### Docker Compose (Recommended)

```bash
# Start entire stack
docker-compose up -d

# View CNS logs
docker-compose logs -f janus-cns

# Check all service health
docker-compose ps
```

### Kubernetes

```bash
# Deploy CNS
kubectl apply -f k8s/cns-deployment.yaml

# Check status
kubectl get pods -l app=janus-cns

# View logs
kubectl logs -l app=janus-cns -f

# Port forward for local access
kubectl port-forward svc/janus-cns 9090:9090
```

---

## 🎓 Learning Path

### Beginner
1. ✅ Complete this quick start
2. 📖 Read `crates/cns/README.md`
3. 🧪 Run tests: `cargo test -p janus-cns`
4. 📊 Set up Grafana dashboard

### Intermediate
1. 🔧 Customize reflex rules
2. 📈 Add custom metrics
3. 🏗️ Create custom health probes
4. 🚨 Configure alerting

### Advanced
1. 🔬 Implement custom circuit breaker logic
2. 🧠 Extend Brain with machine learning
3. 🌐 Integrate with service mesh
4. 📡 Add distributed tracing

---

## 📖 Additional Resources

- [Full Architecture Guide](./CNS_ARCHITECTURE.md)
- [CNS Crate Documentation](../crates/cns/README.md)
- [Grafana Dashboard Guide](../config/grafana/README.md)
- [Main JANUS README](../README.md)

---

## 🤝 Getting Help

**Logs Location:**
- Development: stdout/stderr
- Docker: `docker logs janus-cns`
- Kubernetes: `kubectl logs -l app=janus-cns`
- Systemd: `journalctl -u janus-cns`

**Debug Mode:**
```bash
RUST_LOG=debug cargo run --bin janus-cns
```

**Common Issues:**
- Health checks failing → Verify service endpoints
- Metrics not appearing → Check Prometheus scrape config
- Circuit breakers stuck → Review threshold settings
- High CPU usage → Reduce check frequency

---

## ✅ Checklist

- [ ] Dependencies running (Redis, Qdrant)
- [ ] CNS service started successfully
- [ ] Health endpoint responding
- [ ] Metrics endpoint working
- [ ] Prometheus scraping CNS
- [ ] Grafana dashboard imported
- [ ] All JANUS services monitored
- [ ] Alerts configured
- [ ] Documentation reviewed

**Congratulations!** Your JANUS CNS is now operational. 🎉