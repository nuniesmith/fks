# JANUS Central Nervous System (CNS) Architecture

## Overview

The **Central Nervous System (CNS)** serves as the health monitoring and observability backbone for the JANUS trading system. Inspired by the biological nervous system, it provides comprehensive health monitoring, Prometheus metrics, circuit breakers, and intelligent auto-recovery mechanisms.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Biological Analogy](#biological-analogy)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [Metrics Collection](#metrics-collection)
- [Grafana Integration](#grafana-integration)
- [Deployment](#deployment)
- [Integration Guide](#integration-guide)
- [Best Practices](#best-practices)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            JANUS CNS ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────────┘

                                ┌──────────────────┐
                                │   Grafana UI     │
                                │   Dashboards     │
                                └────────┬─────────┘
                                         │ Prometheus Query
                                         ▼
                                ┌──────────────────┐
                                │   Prometheus     │
                                │   Server         │
                                └────────┬─────────┘
                                         │ HTTP Scrape
                                         │ /metrics
                                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         CNS Service (Port 9090)                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                          Brain (Coordinator)                          │  │
│  │  - Orchestrates health probes every 10s                              │  │
│  │  - Aggregates health signals                                         │  │
│  │  - Manages circuit breakers                                          │  │
│  │  - Executes reflex actions                                           │  │
│  └───────────┬──────────────────────────────────────────────────────────┘  │
│              │                                                               │
│      ┌───────┴────────┬──────────────┬─────────────┐                       │
│      ▼                ▼              ▼             ▼                       │
│  ┌────────┐      ┌─────────┐    ┌─────────┐   ┌──────────┐               │
│  │ Probes │      │ Metrics │    │Reflexes │   │ Signals  │               │
│  │(Sensors)│     │Pipeline │    │(Actions)│   │(Messages)│               │
│  └────┬───┘      └────┬────┘    └────┬────┘   └─────┬────┘               │
└───────┼───────────────┼──────────────┼──────────────┼─────────────────────┘
        │               │              │              │
        │ Health Checks │ Prom Export  │ Recovery     │ Health Status
        ▼               ▼              ▼              ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        MONITORED COMPONENTS                                 │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Forward    │  │   Backward   │  │   Gateway    │  │     Redis    │  │
│  │   Service    │  │   Service    │  │   Service    │  │  (Job Queue) │  │
│  │ (Wake State) │  │(Sleep State) │  │  (FastAPI)   │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                    │
│  │    Qdrant    │  │    Shared    │  │     gRPC     │                    │
│  │ (Vector DB)  │  │    Memory    │  │   Channels   │                    │
│  │              │  │  (Arrow IPC)  │  │              │                    │
│  └──────────────┘  └──────────────┘  └──────────────┘                    │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Biological Analogy

The CNS design mirrors the biological nervous system's architecture:

### Brain (Command Center)
**Biological**: Processes information, makes decisions, coordinates responses  
**CNS**: `brain::Brain` - Central coordinator that:
- Schedules and orchestrates health probes
- Aggregates health signals from all components
- Maintains system state and uptime tracking
- Coordinates reflex execution

### Spinal Cord (Information Highway)
**Biological**: Carries signals between brain and body  
**CNS**: Metrics pipeline - Efficient data transmission:
- Prometheus metrics registry
- Zero-copy where possible
- Buffered aggregation
- HTTP/gRPC transport

### Sensory Neurons (Input)
**Biological**: Detect stimuli from environment  
**CNS**: `probes::HealthProbe` - Health checks:
- HTTP probes for REST services
- gRPC probes for RPC services
- Redis PING commands
- Qdrant health endpoints
- Shared memory accessibility checks

### Motor Neurons (Output)
**Biological**: Execute actions in response to stimuli  
**CNS**: `reflexes::RefexAction` - Recovery actions:
- Logging and alerting
- Component restarts
- Request throttling
- Circuit breaker activation
- Graceful shutdown

### Reflex Arcs (Automatic Responses)
**Biological**: Fast, automatic responses without brain involvement  
**CNS**: `reflexes::CircuitBreaker` - Immediate protection:
- Failure detection
- Automatic circuit opening
- Half-open testing
- Automatic recovery

### Nerve Signals (Communication)
**Biological**: Electrical impulses carrying information  
**CNS**: `signals::HealthSignal` - Structured health data:
- Component status
- Response times
- Metadata
- Timestamps

---

## Component Details

### 1. Brain Module (`brain.rs`)

**Purpose**: Central coordinator and orchestrator

**Key Structures**:
```rust
pub struct Brain {
    config: BrainConfig,
    probes: Vec<Box<dyn HealthProbe>>,
    reflex: Arc<RwLock<Reflex>>,
    current_health: Arc<RwLock<Option<HealthSignal>>>,
    start_time: Instant,
    running: Arc<RwLock<bool>>,
}
```

**Responsibilities**:
- Execute health check cycles at configured intervals
- Aggregate probe results into system-wide health signal
- Update Prometheus metrics
- Process reflexes based on health status
- Expose current health state via API

**Configuration**:
```toml
[brain]
health_check_interval_secs = 10
enable_reflexes = true
```

### 2. Probes Module (`probes.rs`)

**Purpose**: Health check implementations for all component types

**Probe Types**:

| Probe Type | Target | Protocol | Timeout |
|-----------|--------|----------|---------|
| `HttpHealthProbe` | REST services | HTTP GET /health | 5s |
| `GrpcHealthProbe` | gRPC services | TCP connection | 5s |
| `RedisHealthProbe` | Redis | PING command | 5s |
| `QdrantHealthProbe` | Qdrant | HTTP GET /healthz | 5s |
| `SharedMemoryProbe` | Shared mem | File existence | 5s |
| `CompositeProbe` | Multiple | Aggregated | 5s |

**Probe Interface**:
```rust
#[async_trait]
pub trait HealthProbe: Send + Sync {
    fn component_type(&self) -> ComponentType;
    async fn check(&self) -> Result<ProbeResult>;
    fn timeout(&self) -> Duration;
}
```

**Probe Execution**:
1. All probes execute concurrently using `futures::join_all`
2. Each probe has independent timeout protection
3. Failures are non-fatal - recorded as `ProbeStatus::Down`
4. Results aggregated into `HealthSignal`

### 3. Metrics Module (`metrics.rs`)

**Purpose**: Prometheus metrics collection and export

**Metric Categories**:

1. **System-Level**
   - `janus_cns_system_health_score` (Gauge): 0.0-1.0 overall health
   - `janus_cns_system_status` (IntGauge): 0=Starting, 1=Healthy, 2=Degraded, 3=Critical
   - `janus_cns_system_uptime_seconds` (IntGauge): System uptime

2. **Component-Level**
   - `janus_cns_component_health{component}` (GaugeVec): Per-component health score
   - `janus_cns_component_response_time_ms{component}` (GaugeVec): Response times
   - `janus_cns_component_probe_total{component,status}` (IntCounterVec): Probe counts
   - `janus_cns_component_probe_failures{component,reason}` (IntCounterVec): Failures

3. **Service-Specific**
   - Forward: `janus_forward_orders_submitted_total`, `janus_forward_orders_filled_total`
   - Backward: `janus_backward_training_iterations_total`, `janus_backward_memory_consolidations_total`
   - Gateway: `janus_gateway_http_requests_total{method,endpoint,status}`

4. **Dependency**
   - Redis: `janus_redis_commands_total{command,status}`, `janus_redis_command_duration_seconds`
   - Qdrant: `janus_qdrant_vectors_stored`, `janus_qdrant_search_duration_seconds`

5. **Communication**
   - Shared Memory: `janus_shm_messages_sent_total`, `janus_shm_message_size_bytes`
   - gRPC: `janus_grpc_requests_total{service,method,status}`, `janus_grpc_request_duration_seconds`

6. **Circuit Breakers**
   - `janus_circuit_breaker_state{component}` (IntGaugeVec): 0=Closed, 1=Open, 2=HalfOpen
   - `janus_circuit_breaker_trips_total{component,reason}` (IntCounterVec): Trip count

7. **Resources**
   - `janus_resources_memory_usage_bytes` (IntGauge): Memory usage
   - `janus_resources_cpu_usage_percent` (Gauge): CPU usage
   - `janus_resources_active_tasks` (IntGauge): Active async tasks

### 4. Reflexes Module (`reflexes.rs`)

**Purpose**: Auto-recovery and circuit breaking

**Circuit Breaker States**:
```
CLOSED ──[failure_threshold exceeded]──> OPEN
   ▲                                       │
   │                                       │
   │                                       │ [recovery_timeout elapsed]
   │                                       │
   └──[success_threshold met]──── HALF-OPEN
```

**Circuit Breaker Configuration**:
```rust
pub struct CircuitBreakerConfig {
    pub failure_threshold: u32,        // Failures before opening
    pub failure_window_secs: i64,      // Time window for failures
    pub recovery_timeout_secs: i64,    // Wait before half-open
    pub success_threshold: u32,        // Successes to close
}
```

**Reflex Actions**:
- `LogWarning`: Log warning message
- `SendAlert`: Alert to external systems (Slack, PagerDuty)
- `RestartComponent`: Attempt component restart
- `ThrottleComponent`: Rate limit requests
- `OpenCircuitBreaker`: Manually open circuit
- `ExecuteCommand`: Run recovery script
- `GracefulShutdown`: Initiate system shutdown

**Reflex Rules**:
```rust
pub struct ReflexRule {
    pub id: String,
    pub description: String,
    pub condition: ReflexCondition,
    pub action: RefexAction,
    pub cooldown_secs: i64,
}
```

**Cooldown Mechanism**: Prevents action spam by tracking last execution time per rule

### 5. Signals Module (`signals.rs`)

**Purpose**: Health signal types and status definitions

**System Status Hierarchy**:
```
Starting → Healthy ⇄ Degraded → Critical → Shutdown
```

**Health Score Calculation**:
```
health_score = Σ(component.status.score()) / component_count

where:
  ProbeStatus::Up       → 1.0
  ProbeStatus::Degraded → 0.5
  ProbeStatus::Unknown  → 0.25
  ProbeStatus::Down     → 0.0
```

**Component Types**:
- Services: ForwardService, BackwardService, GatewayService, CNSService
- Dependencies: Redis, Qdrant
- Communication: SharedMemory, GrpcChannel, WebSocket
- Modules: VisionModule, LogicModule, MemoryModule, ExecutionModule
- Infrastructure: JobQueue, MetricsExporter

---

## Data Flow

### Health Check Cycle

```
┌─────────────────────────────────────────────────────────────┐
│  1. Timer Tick (every health_check_interval_secs)           │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Execute All Probes (Concurrently)                       │
│     - HttpHealthProbe × 3 (forward, backward, gateway)      │
│     - RedisHealthProbe                                      │
│     - QdrantHealthProbe                                     │
│     - SharedMemoryProbe                                     │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Aggregate Results                                        │
│     - Convert ProbeResults → ComponentHealth                │
│     - Calculate system_status (aggregate)                   │
│     - Calculate health_score                                │
│     - Create HealthSignal                                   │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Update Metrics                                           │
│     - CNSMetrics::update(signal)                            │
│     - Update all Prometheus gauges/counters                 │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Process Reflexes (if enabled)                           │
│     - For each component in signal:                         │
│       - Check circuit breakers                              │
│       - Evaluate reflex rules                               │
│       - Execute actions (respecting cooldowns)              │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  6. Store Current Health                                     │
│     - Update current_health RwLock                          │
│     - Available via /health endpoint                        │
└─────────────────────────────────────────────────────────────┘
```

### Metrics Scraping Flow

```
Prometheus ──[HTTP GET /metrics]──> CNS Service
                                     │
                                     ▼
                              MetricsRegistry::gather()
                                     │
                                     ▼
                              prometheus::TextEncoder
                                     │
                                     ▼
                              HTTP Response (text/plain)
```

---

## Metrics Collection

### Prometheus Configuration

**prometheus.yml**:
```yaml
global:
  scrape_interval: 10s
  evaluation_interval: 10s

scrape_configs:
  - job_name: 'janus-cns'
    static_configs:
      - targets: ['localhost:9090']
        labels:
          service: 'cns'
          
  - job_name: 'janus-forward'
    static_configs:
      - targets: ['localhost:8081']
        labels:
          service: 'forward'
          
  - job_name: 'janus-backward'
    static_configs:
      - targets: ['localhost:8082']
        labels:
          service: 'backward'
          
  - job_name: 'janus-gateway'
    static_configs:
      - targets: ['localhost:8080']
        labels:
          service: 'gateway'
```

### Metric Naming Convention

Pattern: `janus_{subsystem}_{metric_name}_{unit}`

Examples:
- `janus_cns_system_health_score` (no unit for ratio)
- `janus_cns_system_uptime_seconds`
- `janus_redis_command_duration_seconds`
- `janus_shm_message_size_bytes`

### Label Strategy

**Component Labels**: Identify which component the metric relates to
```
janus_cns_component_health{component="forward_service"} 1.0
janus_cns_component_health{component="redis"} 1.0
```

**Status Labels**: Categorize by outcome
```
janus_cns_component_probe_total{component="redis",status="UP"} 100
janus_cns_component_probe_total{component="redis",status="DOWN"} 2
```

**Method/Command Labels**: Granular operation tracking
```
janus_redis_commands_total{command="GET",status="success"} 1000
janus_grpc_requests_total{service="Forward",method="SubmitOrder",status="OK"} 500
```

---

## Grafana Integration

### Dashboard Structure

The Grafana dashboard (`config/grafana/janus_cns_dashboard.json`) is organized into sections:

1. **System Overview** (Row 1)
   - System Status (stat panel with color coding)
   - Health Score (gauge with thresholds)
   - System Uptime (stat)
   - Active Tasks (stat)

2. **Component Health** (Row 2-3)
   - Component Health Status (horizontal stat panels)
   - Health Over Time (timeseries graph)

3. **Services Performance** (Row 4-5)
   - Response Times (timeseries)
   - Probe Execution Rate (timeseries)
   - Forward Service: Orders submitted/filled/rejected
   - Backward Service: Training iterations, memory consolidations

4. **Dependencies** (Row 6-7)
   - Redis: Command rate and duration (p95, p99)
   - Qdrant: Vectors stored, search performance

5. **Circuit Breakers** (Row 8)
   - Circuit States (stat panels with color mapping)
   - Trip Count (timeseries)

6. **Communication Channels** (Row 9)
   - Shared Memory message rates
   - gRPC request rates and duration

7. **Resource Utilization** (Row 10)
   - Memory usage (timeseries)
   - CPU usage (timeseries)

### Alert Rules

**Prometheus Alerting Rules** (`alerts.yml`):
```yaml
groups:
  - name: janus_cns_alerts
    interval: 30s
    rules:
      - alert: SystemCritical
        expr: janus_cns_system_status >= 3
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "JANUS system is in CRITICAL state"
          
      - alert: LowHealthScore
        expr: janus_cns_system_health_score < 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "System health score below 50%"
          
      - alert: ComponentDown
        expr: janus_cns_component_health == 0
        for: 2m
        labels:
          severity: error
        annotations:
          summary: "Component {{ $labels.component }} is DOWN"
          
      - alert: HighResponseTime
        expr: janus_cns_component_response_time_ms > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High response time for {{ $labels.component }}"
```

### Variable Templates

Use Grafana variables for dynamic filtering:
```
$component = janus_cns_component_health
$service = forward_service|backward_service|gateway_service
$timerange = 1h|6h|24h|7d
```

---

## Deployment

### Docker Compose Setup

**docker-compose.yml**:
```yaml


services:
  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  # Qdrant
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 3

  # JANUS CNS
  janus-cns:
    build:
      context: .
      dockerfile: services/cns/Dockerfile
    ports:
      - "9090:9090"
    volumes:
      - ./config:/app/config:ro
      - /dev/shm:/dev/shm
    environment:
      - RUST_LOG=info
      - CONFIG_PATH=/app/config/cns.toml
    depends_on:
      - redis
      - qdrant
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9090/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  # Prometheus
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9091:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    depends_on:
      - janus-cns

  # Grafana
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana:/etc/grafana/provisioning/dashboards:ro
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    depends_on:
      - prometheus

volumes:
  qdrant_data:
  prometheus_data:
  grafana_data:
```

### Kubernetes Deployment

**k8s/cns-deployment.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: janus-cns
  labels:
    app: janus-cns
spec:
  replicas: 1
  selector:
    matchLabels:
      app: janus-cns
  template:
    metadata:
      labels:
        app: janus-cns
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: cns
        image: janus/cns:latest
        ports:
        - containerPort: 9090
          name: http
        env:
        - name: RUST_LOG
          value: "info"
        livenessProbe:
          httpGet:
            path: /health
            port: 9090
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 9090
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: janus-cns
  labels:
    app: janus-cns
spec:
  ports:
  - port: 9090
    targetPort: 9090
    name: http
  selector:
    app: janus-cns
```

---

## Integration Guide

### Adding CNS to Existing Services

#### 1. Add Health Endpoint to Services

**Forward Service (Rust)**:
```rust
// In services/forward/src/main.rs

use axum::{routing::get, Json, Router};
use serde_json::json;

async fn health_handler() -> Json<serde_json::Value> {
    Json(json!({
        "status": "healthy",
        "service": "forward",
        "version": env!("CARGO_PKG_VERSION"),
    }))
}

let app = Router::new()
    .route("/health", get(health_handler))
    // ... other routes
```

**Gateway Service (Python)**:
```python
# In services/janus-gateway/src/main.py

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "gateway",
        "version": "0.1.0"
    }
```

#### 2. Add Metrics Export

**Using CNS Metrics in Services**:
```rust
// In Forward service
use janus_cns::metrics::CNSMetrics;

// Increment order counter
CNSMetrics::registry()
    .forward_orders_submitted
    .inc();

// Record order fill
CNSMetrics::registry()
    .forward_orders_filled
    .inc();
```

#### 3. Configure Endpoints

Update `config/cns.toml`:
```toml
[endpoints]
forward_service = "http://janus-forward:8081"
backward_service = "http://janus-backward:8082"
gateway_service = "http://janus-gateway:8080"
redis = "redis://janus-redis:6379"
qdrant = "http://janus-qdrant:6333"
```

### Custom Component Monitoring

```rust
use janus_cns::{
    probes::{HealthProbe, ProbeResult, ProbeStatus},
    signals::ComponentType,
    Brain,
};

// Define custom component type (add to ComponentType enum)
// For now, use existing types or create custom probe

struct MyServiceProbe {
    url: String,
}

#[async_trait]
impl HealthProbe for MyServiceProbe {
    fn component_type(&self) -> ComponentType {
        ComponentType::Custom { name: "my_service".to_string() }
    }
    
    async fn check(&self) -> Result<ProbeResult> {
        // Custom health check logic
        Ok(ProbeResult {
            component_type: self.component_type(),
            status: ProbeStatus::Up,
            message: "Service operational".to_string(),
            response_time_ms: 10,
        })
    }
}

// Add to brain
let mut brain = Brain::new(config);
brain.add_probe(Box::new(MyServiceProbe {
    url: "http://my-service:8080".to_string(),
}));
```

---

## Best Practices

### 1. Health Check Design

**DO**:
- ✅ Make health checks lightweight (< 100ms)
- ✅ Check actual functionality, not just "is the process running"
- ✅ Return meaningful status messages
- ✅ Include version information
- ✅ Test critical dependencies (DB, cache, etc.)

**DON'T**:
- ❌ Don't perform expensive operations (full DB scan)
- ❌ Don't fail health check on non-critical issues
- ❌ Don't return 200 OK with error message in body
- ❌ Don't ignore timeouts

### 2. Metrics Naming

**DO**:
- ✅ Use consistent naming: `janus_{subsystem}_{metric}_{unit}`
- ✅ Include units in name: `_seconds`, `_bytes`, `_total`
- ✅ Use counters for cumulative values
- ✅ Use gauges for point-in-time values
- ✅ Use histograms for distributions

**DON'T**:
- ❌ Don't use spaces or special characters
- ❌ Don't change metric names in production
- ❌ Don't use high-cardinality labels (user IDs, etc.)

### 3. Circuit Breaker Tuning

**Conservative (Production)**:
```toml
failure_threshold = 10
failure_window_secs = 120
recovery_timeout_secs = 60
success_threshold = 5
```

**Aggressive (Development)**:
```toml
failure_threshold = 3
failure_window_secs = 30
recovery_timeout_secs = 20
success_threshold = 2
```

### 4. Alert Fatigue Prevention

- Use cooldown periods on reflex rules (300s minimum for critical alerts)
- Aggregate similar alerts
- Use severity levels appropriately
- Don't alert on expected transient issues
- Test alerts in staging first

### 5. Resource Management

**Memory**:
- Limit metrics cardinality
- Use bounded queues
- Regular metric cleanup

**CPU**:
- Run probes concurrently but limit parallelism
- Use timeout protection
- Avoid expensive computations in hot path

### 6. Observability

**Logging Levels**:
- `ERROR`: Circuit breakers opening, critical failures
- `WARN`: Degraded components, slow responses
- `INFO`: Health check cycles, status changes
- `DEBUG`: Detailed probe results
- `TRACE`: Individual probe executions

**Structured Logging**:
```rust
info!(
    component = %component_type,
    status = %status,
    response_time_ms = response_time,
    "Health check completed"
);
```

### 7. Testing

**Unit Tests**:
```rust
#[tokio::test]
async fn test_redis_probe() {
    let probe = RedisHealthProbe::new("redis://localhost:6379");
    let result = probe.check().await.unwrap();
    assert_eq!(result.status, ProbeStatus::Up);
}
```

**Integration Tests**:
```rust
#[tokio::test]
async fn test_full_health_cycle() {
    let brain = Brain::new(BrainConfig::default());
    let signal = brain.check_now().await.unwrap();
    assert!(signal.health_score() > 0.0);
}
```

---

## Troubleshooting

### Common Issues

#### 1. CNS Service Won't Start
```bash
# Check logs
docker logs janus-cns

# Verify configuration
cargo run --bin janus-cns -- --config config/cns.toml --validate

# Check port availability
netstat -an | grep 9090
```

#### 2. Metrics Not Appearing in Prometheus
```bash
# Test metrics endpoint
curl http://localhost:9090/metrics

# Check Prometheus targets
curl http://localhost:9091/api/v1/targets

# Verify prometheus.yml configuration
```

#### 3. False Health Check Failures
```toml
# Increase timeout in config/cns.toml
[health]
timeout_secs = 10

# Or adjust probe-specific timeouts
```

#### 4. Circuit Breaker Stuck Open
```bash
# Check component is actually healthy
curl http://localhost:8081/health

# Review circuit breaker config
# May need to adjust recovery_timeout_secs

# Force close via API (future feature)
curl -X POST http://localhost:9090/circuit-breakers/redis/reset
```

---

## Performance Considerations

### Scalability

| Metric | Current | Target |
|--------|---------|--------|
| Probes per cycle | 6 | 50+ |
| Cycle time | ~500ms | < 1s |
| Memory usage | ~50MB | < 200MB |
| CPU usage | ~2% | < 10% |
| Metrics cardinality | ~100 | < 1000 |

### Optimization Strategies

1. **Concurrent Probes**: All probes run in parallel
2. **Lazy Metrics**: Only update changed metrics
3. **Bounded Queues**: Limit buffered data
4. **Connection Pooling**: Reuse HTTP/gRPC connections
5. **Efficient Serialization**: Use binary formats where possible

---

## Future Roadmap

### Phase 1: Core Features (✅ Complete)
- [x] Basic health probes
- [x] Prometheus metrics
- [x] Circuit breakers
- [x] Reflex system
- [x] Grafana dashboard

### Phase 2: Enhanced Monitoring (🚧 In Progress)
- [ ] gRPC health check protocol
- [ ] Advanced alerting (Slack, PagerDuty)
- [ ] Historical health data storage
- [ ] Trend analysis and anomaly detection

### Phase 3: Auto-Recovery (📋 Planned)
- [ ] Automatic component restart
- [ ] Dynamic throttling
- [ ] Load-based auto-scaling triggers
- [ ] Predictive health scoring

### Phase 4: Intelligence (💡 Future)
- [ ] Machine learning for anomaly detection
- [ ] Predictive failure analysis
- [ ] Automated remediation playbooks
- [ ] Self-healing capabilities

---

## Conclusion

The JANUS CNS provides a robust, biologically-inspired health monitoring system that ensures the reliability and observability of the entire trading platform. By combining comprehensive health checks, real-time metrics, intelligent circuit breakers, and auto-recovery reflexes, it acts as the "nervous system" that keeps JANUS healthy and responsive.

**Key Takeaways**:
- 🧠 Centralized health coordination via Brain
- 📊 Comprehensive Prometheus metrics
- 🔄 Automatic recovery with reflexes
- ⚡ Circuit breakers for fault isolation
- 📈 Rich Grafana dashboards
- 🚀 Production-ready deployment options

For questions or contributions, see the main JANUS repository.
